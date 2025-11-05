"""Python implementation of the water value algorithm described in SAMBA/05/11.

The logic mirrors the original R function in `watervalue.R`, including:
  * Piecewise constant segmentation of production data.
  * Breakpoint validation based on joint price/production changes.
  * Water value estimation through jump-based and minimum-value methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


@dataclass
class WaterValueResult:
    water_values: List[float]
    level_means: List[float]
    production_levels: List[int]
    breakpoints: List[int]


DEFAULT_TIMERES_SECONDS = 240


class WaterValueError(ValueError):
    """Raised when input validation fails."""


def _ensure_series(
    values: Sequence[float],
    timestamps: Sequence[float],
    name: str,
    freq_seconds: Optional[int] = None,
) -> pd.Series:
    """Convert paired arrays into a deduplicated, timezone-aware pandas Series."""
    if len(values) != len(timestamps):
        raise WaterValueError(f"{name} and timestamps must have identical length")

    values_arr = np.asarray(values, dtype=float)
    time_arr = np.asarray(timestamps, dtype=float)
    if time_arr.size == 0:
        raise WaterValueError(f"No timestamps supplied for {name}")

    if freq_seconds is not None and freq_seconds > 0:
        time_arr = freq_seconds * np.floor_divide(time_arr.astype(np.int64), freq_seconds)

    index = pd.to_datetime(time_arr, unit="s", utc=True)
    series = pd.Series(values_arr, index=index).sort_index()
    if series.index.has_duplicates:
        series = series.groupby(level=0).mean()
    return series


def _resolve_prodlimits(
    prodlimits: Optional[Sequence[float]],
    negativeprod: bool,
    maxinstalled: Optional[float],
) -> np.ndarray:
    """Normalise production interval limits, falling back to `maxinstalled`."""
    if prodlimits is not None:
        limits = np.asarray(prodlimits, dtype=float)
        if not np.all(np.diff(limits) > 0):
            raise WaterValueError("prodlimits must be strictly increasing when supplied")
        return limits

    if maxinstalled is None:
        upper = 50.0
    else:
        upper = 0.1 * float(maxinstalled)

    if negativeprod:
        lower = -upper
        return np.array([lower, upper], dtype=float)

    return np.array([upper], dtype=float)


def _segment_costs(values: np.ndarray) -> np.ndarray:
    """Return SSE cost matrix used by the dynamic programming segmentation."""
    n = len(values)
    # SAMBA/05/11 Section 2.1: the negative log-likelihood reduces to residual sums of squares.
    prefix_sum = np.concatenate(([0.0], np.cumsum(values, dtype=float)))
    prefix_sq = np.concatenate(([0.0], np.cumsum(values**2, dtype=float)))
    cost = np.zeros((n, n), dtype=float)
    for i in range(n):
        s = prefix_sum[i + 1 :] - prefix_sum[i]
        sq = prefix_sq[i + 1 :] - prefix_sq[i]
        lengths = np.arange(1, n - i + 1, dtype=float)
        cost[i, i:] = sq - (s**2) / lengths
    return cost


def _segselect(J: np.ndarray, strictness: float, nsamples: int) -> int:
    """Select segment count using the pre-Monday curvature criterion."""
    kmax = len(J)
    if kmax <= 1:
        return 1

    J = np.asarray(J, dtype=float)
    denom = J[-1] - J[0]
    if np.isclose(denom, 0.0):
        return 1

    Jtilde = (kmax - 1) * ((J[-1] - J) / denom) + 1.0
    curvature = np.diff(Jtilde, n=2)
    hits = np.where(curvature >= strictness)[0]
    if hits.size > 0:
        return int(hits[-1] + 2)
    return 1


def _piecewise_constant_segmentation(
    production: pd.Series,
    nsegments: Optional[int],
    strictness: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Fit piecewise-constant segments and return means plus breakpoint flags."""
    values = production.to_numpy(dtype=float)
    n = len(values)
    if nsegments is not None and (nsegments < 1 or nsegments > min(24, n)):
        raise WaterValueError("nsegments must be between 1 and min(24, number of samples)")

    kmax = min(24, n)
    cost = _segment_costs(values)

    # SAMBA/05/11 Section 2.1: dynamic programming enumerates optimal breakpoints.
    dp = np.full((kmax, n), np.inf, dtype=float)
    prev = np.full((kmax, n), -1, dtype=int)

    dp[0, :] = cost[0, :]

    for k in range(1, kmax):
        for j in range(k, n):
            best_val = np.inf
            best_idx = -1
            for i in range(k - 1, j):
                candidate = dp[k - 1, i] + cost[i + 1, j]
                if candidate < best_val:
                    best_val = candidate
                    best_idx = i
            dp[k, j] = best_val
            prev[k, j] = best_idx

    J_est = np.array([dp[k, n - 1] for k in range(kmax)], dtype=float)
    if nsegments is None:
        Kselect = _segselect(J_est, strictness, n)
    else:
        Kselect = nsegments

    endpoints = []
    j = n - 1
    for k in range(Kselect - 1, -1, -1):
        endpoints.append(j)
        if k == 0:
            break
        j = prev[k, j]
    endpoints = sorted(endpoints)

    segment_means = np.empty(n, dtype=float)
    bp_flags = np.zeros(n, dtype=int)
    start = 0
    for end in endpoints:
        segment = values[start : end + 1]
        mu = float(np.mean(segment))
        segment_means[start : end + 1] = mu
        bp_flags[end] = 1
        start = end + 1

    shifted_bp = np.zeros_like(bp_flags)
    shifted_bp[1:] = bp_flags[:-1]

    return segment_means, shifted_bp


def _prepare_fine_index(
    production_index: pd.DatetimeIndex,
    timeres_seconds: int,
) -> pd.DatetimeIndex:
    """Build high-resolution timestamp index used for alignment and windows."""
    freq = f"{int(max(timeres_seconds, 1))}s"
    return pd.date_range(start=production_index[0], end=production_index[-1], freq=freq)


def _align_series(
    base_index: pd.DatetimeIndex,
    series: pd.Series,
) -> pd.Series:
    """Align a series to a dense index, forward/back filling as needed."""
    aligned = series.reindex(base_index).ffill().bfill()
    return aligned.astype(float)


def _enforce_monotonic_intervals(
    lower: np.ndarray,
    upper: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Ensure ŵ1min ≤ ŵ1max ≤ ŵ2min ≤ … as prescribed in Section 2.3."""
    lower_adj = lower.copy()
    upper_adj = upper.copy()
    running_max = -np.inf

    for idx in range(len(upper_adj)):
        if np.isnan(upper_adj[idx]) and np.isnan(lower_adj[idx]):
            continue

        if np.isnan(upper_adj[idx]):
            upper_adj[idx] = lower_adj[idx]
        if np.isnan(lower_adj[idx]):
            lower_adj[idx] = upper_adj[idx]

        lower_adj[idx] = max(lower_adj[idx], running_max)
        if upper_adj[idx] < lower_adj[idx]:
            upper_adj[idx] = lower_adj[idx]

        running_max = max(running_max, upper_adj[idx])

    return lower_adj, upper_adj


def _mark_valid_breakpoints(
    bp_flags: np.ndarray,
    production_index: pd.DatetimeIndex,
    prodlevel_fine: pd.Series,
    price_fine: pd.Series,
    jumpm: int,
) -> Tuple[
    np.ndarray,
    List[pd.Timestamp],
    List[pd.Timestamp],
    List[pd.Series],
    List[pd.Series],
]:
    """Filter candidate breakpoints by checking joint price/production jumps."""
    bp_times_all = list(production_index[bp_flags > 0])
    if len(bp_times_all) == 0:
        return bp_flags, bp_times_all, [], [], []

    updated_flags = bp_flags.copy()
    jump_delta = pd.Timedelta(minutes=int(jumpm))

    valid_times: List[pd.Timestamp] = []
    price_windows: List[pd.Series] = []
    prod_windows: List[pd.Series] = []
    for time in bp_times_all:
        # SAMBA/05/11 Section 2.3.1: validate breakpoints where price and production move together.
        window_slice = slice(time - jump_delta, time + jump_delta)
        prod_window = prodlevel_fine.loc[window_slice]
        price_window = price_fine.loc[window_slice]
        if prod_window.empty or price_window.empty:
            continue

        p_change = float(price_window.iloc[-1] - price_window.iloc[0])
        l_change = float(prod_window.iloc[-1] - prod_window.iloc[0])
        if p_change * l_change > 0:
            loc = np.where(production_index == time)[0]
            if loc.size:
                updated_flags[loc[0]] = 2
            valid_times.append(time)
            price_windows.append(price_window)
            prod_windows.append(prod_window)

    return updated_flags, bp_times_all, valid_times, prod_windows, price_windows


def _jump_method(
    n_wv: int,
    prod_window_levels: List[pd.Series],
    price_windows: List[pd.Series],
    prodlevel_fine: pd.Series,
    production_index: pd.DatetimeIndex,
    valid_times: Sequence[pd.Timestamp],
    estinterval: bool,
) -> np.ndarray:
    """Estimate water values using the breakpoint-change method (Section 2.3.1)."""
    if not valid_times:
        return np.full(2 * n_wv if estinterval else n_wv, np.nan, dtype=float)

    last_day = production_index[-1].normalize()
    bounds_by_level: Dict[int, List[tuple[float, float, float]]] = {}

    for idx, time in enumerate(valid_times):
        if time.normalize() != last_day:
            continue
        price_window = price_windows[idx]
        prod_window = prod_window_levels[idx]
        if price_window.empty or prod_window.empty:
            continue

        level = int(prod_window.max())
        if level <= 0 or level > n_wv:
            continue

        # Narrowest neighbourhood interval per Section 2.3.1 determines the candidate water value.
        upper = float(price_window.max())
        lower = float(price_window.min())
        width = float(max(0.0, upper - lower))
        bounds_by_level.setdefault(level, []).append((lower, upper, width))

    wvl = np.full(n_wv, np.nan, dtype=float)
    wvh = np.full(n_wv, np.nan, dtype=float)

    for level, candidates in bounds_by_level.items():
        best = min(candidates, key=lambda entry: (entry[2], entry[1]))
        lower, upper, _ = best
        wvh[level - 1] = upper
        wvl[level - 1] = lower

    # Enforce ŵ1min ≤ ŵ1max ≤ ŵ2min ≤ … as mandated in Section 2.3.
    wvl, wvh = _enforce_monotonic_intervals(wvl, wvh)

    if estinterval:
        stacked = np.column_stack([wvl, wvh]).reshape(-1)
        result = np.full_like(stacked, np.nan)
        mask = ~np.isnan(stacked)
        result[mask] = np.maximum.accumulate(stacked[mask])
        return result

    point = np.copy(wvh)
    mask = ~np.isnan(point)
    point[mask] = np.maximum.accumulate(point[mask])
    return point


def _minimum_method(
    n_wv: int,
    prodlevel_fine: pd.Series,
    price_fine: pd.Series,
    valid_bp_times: Sequence[pd.Timestamp],
    production_end: pd.Timestamp,
    discardend: int,
    estinterval: bool,
) -> np.ndarray:
    """Estimate water values using the minimum-value method (Section 2.3.2)."""
    result = np.full(2 * n_wv if estinterval else n_wv, np.nan, dtype=float)
    if prodlevel_fine.empty or price_fine.empty:
        return result

    price_for_min = price_fine.copy()
    price_for_max = price_fine.copy()

    adjust_delta = pd.Timedelta(minutes=59)
    for time in valid_bp_times:
        window_slice = slice(time - adjust_delta, time + adjust_delta)
        window_index = price_fine.loc[window_slice].index
        if not len(window_index):
            continue
        window_prices = price_fine.loc[window_index]
        price_for_min.loc[window_index] = float(window_prices.max())
        price_for_max.loc[window_index] = float(window_prices.min())

    discard_minutes = max(int(discardend), 0)
    if discard_minutes > 0:
        cutoff = production_end - pd.Timedelta(minutes=discard_minutes)
        if cutoff > price_for_min.index[0]:
            mask = price_for_min.index <= cutoff
            price_for_min = price_for_min[mask]
            price_for_max = price_for_max[mask]
            prodlevel_fine = prodlevel_fine[mask]

    if prodlevel_fine.empty:
        return result

    # SAMBA/05/11 Section 2.3.2: use minimum prices at interval i and maximum prices below i.
    frame = pd.DataFrame(
        {
            "level": prodlevel_fine.astype(float),
            "price_min": price_for_min.astype(float),
            "price_max": price_for_max.astype(float),
        }
    ).dropna(subset=["level"])
    frame["level"] = frame["level"].astype(int)

    positive = frame[frame["level"] > 0]
    if positive.empty:
        return result

    min_per_level = positive.groupby("level")["price_min"].min()
    max_per_level = frame.groupby("level")["price_max"].max()

    wvh = np.full(n_wv, np.nan, dtype=float)
    wvl = np.full(n_wv, np.nan, dtype=float)

    for level in sorted(min_per_level.index):
        idx = level - 1
        if idx < 0 or idx >= n_wv:
            continue
        upper = float(min_per_level.loc[level])
        wvh[idx] = upper

        lower_candidates = max_per_level.loc[max_per_level.index < level]
        if lower_candidates.empty:
            lower = upper
        else:
            lower = min(upper, float(lower_candidates.max()))
        wvl[idx] = lower

    wvl, wvh = _enforce_monotonic_intervals(wvl, wvh)

    if estinterval:
        stacked = np.column_stack([wvl, wvh]).reshape(-1)
        mask = ~np.isnan(stacked)
        result[mask] = np.maximum.accumulate(stacked[mask])
        return result

    point = np.copy(wvh)
    mask = ~np.isnan(point)
    point[mask] = np.maximum.accumulate(point[mask])
    return point


def watervalue(
    productiondata: Sequence[float],
    productiontime: Sequence[float],
    pricedata: Sequence[float],
    pricetime: Sequence[float],
    prodlimits: Optional[Sequence[float]] = None,
    negativeprod: bool = False,
    maxinstalled: Optional[float] = None,
    strictness: float = 0.5,
    estinterval: bool = True,
    estmethod: str = "minimum",
    jumpm: int = 60,
    nsegments: Optional[int] = None,
    discardend: int = 60,
    doprint: bool = True,
) -> WaterValueResult:
    """High-level estimator returning water values and supporting diagnostics."""
    production = _ensure_series(
        productiondata,
        productiontime,
        name="productiondata",
        freq_seconds=DEFAULT_TIMERES_SECONDS,
    )
    price = _ensure_series(pricedata, pricetime, name="pricedata")

    n = len(production)
    if n < 10:
        raise WaterValueError(f"Not enough input data: Required samples 10, got {n}")

    timerange = production.index[-1] - production.index[0]
    if timerange < pd.Timedelta(hours=3):
        raise WaterValueError(
            "Not enough input data: Required time span 3 hours, "
            f"got {timerange.total_seconds():.0f} seconds",
        )

    limits = _resolve_prodlimits(prodlimits, negativeprod, maxinstalled)
    n_wv = len(limits)

    if doprint:
        print("Production data begins at", production.index[0])
        print("Production data ends at  ", production.index[-1])
        print("Price data begins at     ", price.index[0])
        print("Price data ends at       ", price.index[-1])

    # Step 2 of SAMBA/05/11 Summary: estimate the segmented production curve.
    levelmeans, bp_flags = _piecewise_constant_segmentation(production, nsegments, strictness)

    # SAMBA/05/11 Section 2.3: translate prodlimits γ into discrete production intervals.
    bins = np.concatenate(([-np.inf], limits, [np.inf]))
    prod_levels = pd.cut(levelmeans, bins, labels=False, include_lowest=True)
    if hasattr(prod_levels, "to_numpy"):
        prod_levels = prod_levels.to_numpy()
    prod_levels = np.asarray(prod_levels, dtype=int)

    production_index = production.index
    level_series = pd.Series(prod_levels, index=production_index)

    if len(production_index) > 1:
        timeres_seconds = int(
            level_series.index.to_series().diff().dropna().dt.total_seconds().min()
        )
    else:
        timeres_seconds = DEFAULT_TIMERES_SECONDS

    fine_index = _prepare_fine_index(production_index, timeres_seconds)
    prodlevel_fine = _align_series(fine_index, level_series).round().astype(int)
    price_fine = _align_series(fine_index, price)

    # Section 2.3.1: retain breakpoints where production and price move in sync.
    bp_flags, _, valid_times, prod_windows, price_windows = _mark_valid_breakpoints(
        bp_flags,
        production_index,
        prodlevel_fine,
        price_fine,
        jumpm,
    )

    if estmethod not in {"minimum", "jump"}:
        raise WaterValueError("estmethod must be 'minimum' or 'jump'")

    if estmethod == "jump":
        # Section 2.3.1 breakpoint-change interval estimation.
        water_values = _jump_method(
            n_wv,
            prod_windows,
            price_windows,
            prodlevel_fine,
            production_index,
            valid_times,
            estinterval,
        )
    else:
        # Section 2.3.2 minimum-value interval estimation.
        water_values = _minimum_method(
            n_wv,
            prodlevel_fine,
            price_fine,
            valid_times,
            production.index[-1],
            discardend,
            estinterval,
        )

    return WaterValueResult(
        water_values=water_values.tolist(),
        level_means=levelmeans.tolist(),
        production_levels=prod_levels.tolist(),
        breakpoints=bp_flags.tolist(),
    )


__all__ = ["WaterValueError", "WaterValueResult", "watervalue"]
