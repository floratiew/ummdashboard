"""Production data pipeline for water value estimation.

This module fetches ENTSO-E production and price series, aligns them, feeds
them into the `water_value` estimator, and writes CSV artefacts consumed by the
Streamlit dashboard. The workflow mirrors the methodology in SAMBA/05/11.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
import sys
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[3]
SANDBOX_DIR = Path(__file__).resolve().parents[1]
for candidate in (BASE_DIR, SANDBOX_DIR):
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.append(path_str)

from water_value import WaterValueError, watervalue

try:
    from .config import (
        OUTPUT_DIR,
        PLANTS,
        PRICE_AREA_CODES,
        PROCESSED_DATA_DIR,
        PlantConfig,
        ensure_directories,
    )
    from .fetchers import fetch_price_series, fetch_price_series_quarter_hour, fetch_production_series_web
    from .unit_utils import derive_unit_plants
except ImportError:
    from config import (
        OUTPUT_DIR,
        PLANTS,
        PRICE_AREA_CODES,
        PROCESSED_DATA_DIR,
        PlantConfig,
        ensure_directories,
    )
    from fetchers import fetch_price_series, fetch_price_series_quarter_hour, fetch_production_series_web
    from unit_utils import derive_unit_plants


def _to_epoch_seconds(index: pd.Series) -> np.ndarray:
    return index.astype("int64", copy=False) // 10**9


def _align_series(price_df: pd.DataFrame, production_df: pd.DataFrame) -> pd.DataFrame:
    """Align hourly prices to production timestamps, forward/back filling gaps."""
    if price_df.empty or production_df.empty:
        raise ValueError("Price and production data frames must be non-empty.")

    # SAMBA/05/11 Section 2 requires both series on the same time grid before segmentation.
    price_series = (
        price_df.sort_values("timestamp")
        .set_index("timestamp")["price_eur_per_mwh"]
        .astype(float)
    )
    production_series = (
        production_df.sort_values("timestamp")
        .set_index("timestamp")["production_mw"]
        .astype(float)
    )
    production_series = production_series[~production_series.index.duplicated(keep="last")]

    overlap_start = max(price_series.index.min(), production_series.index.min())
    overlap_end = min(price_series.index.max(), production_series.index.max())
    if overlap_start >= overlap_end:
        raise ValueError("Price and production series have no overlapping coverage.")

    production_slice = production_series.loc[(production_series.index >= overlap_start) & (production_series.index <= overlap_end)]
    price_aligned = price_series.reindex(production_slice.index, method="ffill")
    price_aligned = price_aligned.bfill()
    if price_aligned.isna().any():
        raise ValueError("Failed to align price series to production timestamps.")

    return (
        pd.DataFrame(
            {
                "timestamp": production_slice.index,
                "price_eur_per_mwh": price_aligned.to_numpy(dtype=float),
                "production_mw": production_slice.to_numpy(dtype=float),
            }
        )
        .reset_index(drop=True)
    )


def _infer_native_spacing(timestamps: pd.Series) -> pd.Timedelta | None:
    """Return the median spacing between consecutive timestamps."""
    if timestamps.empty:
        return None
    deltas = timestamps.sort_values().diff().dropna()
    if deltas.empty:
        return None
    return deltas.median()


def _downsample_rules(native_spacing: pd.Timedelta | None) -> tuple[str, ...]:
    """
    Return an ordered collection of resample rules that progressively coarsen the series.

    The rules are aligned with SAMBA/05/11, which works on hourly data but tolerates
    finer resolutions. We therefore prefer 30-minute or hourly coarsening before
    resorting to multi-hour buckets.
    """
    if native_spacing is None:
        return ("1h", "2h", "3h", "4h", "6h", "12h", "24h")
    if native_spacing <= pd.Timedelta(minutes=20):
        return ("30min", "1h", "90min", "2h", "3h", "4h", "6h", "12h", "24h")
    if native_spacing <= pd.Timedelta(hours=1):
        return ("2h", "3h", "4h", "6h", "12h", "24h")
    if native_spacing <= pd.Timedelta(hours=3):
        return ("4h", "6h", "12h", "24h")
    return ("12h", "24h")


def _format_water_values(values: List[float], estinterval: bool) -> pd.DataFrame:
    """Return water value array as tidy dataframe (interval or point estimates)."""
    array = np.asarray(values, dtype=float)
    if estinterval:
        matrix = array.reshape(-1, 2)
        df = pd.DataFrame(
            {
                "interval": np.arange(1, len(matrix) + 1, dtype=int),
                "lower": matrix[:, 0],
                "upper": matrix[:, 1],
            }
        )
    else:
        df = pd.DataFrame({"interval": np.arange(1, len(array) + 1, dtype=int), "value": array})
    return df.dropna(how="all")


def _unit_csv_path(unit_slug: str) -> Path:
    return PROCESSED_DATA_DIR / f"{unit_slug}_production.csv"


def _first_non_empty(series: pd.Series | None) -> str:
    if series is None:
        return ""
    cleaned = series.dropna()
    if cleaned.empty:
        return ""
    value = str(cleaned.iloc[0]).strip()
    return value


def _aggregate_units_from_csvs(
    unit_slugs: Sequence[str],
    start: datetime,
    end: datetime,
) -> Tuple[pd.DataFrame, List[Dict[str, str]]]:
    """Aggregate production from cached unit CSVs into a combined series."""
    if not unit_slugs:
        raise RuntimeError("No unit slugs supplied for aggregation.")

    start_utc = pd.Timestamp(start, tz="UTC")
    end_utc = pd.Timestamp(end, tz="UTC")

    frames: list[pd.Series] = []
    unit_records: list[Dict[str, str]] = []

    for slug in unit_slugs:
        path = _unit_csv_path(slug)
        if not path.exists():
            raise RuntimeError(
                f"Unit dataset '{path.relative_to(PROCESSED_DATA_DIR.parent)}' is required but missing."
            )
        df = pd.read_csv(path)
        if {"timestamp", "production_mw"} - set(df.columns):
            raise RuntimeError(f"{path.name} is missing required columns ['timestamp', 'production_mw'].")
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
        series = df.set_index("timestamp")["production_mw"].astype(float)
        frames.append(series.rename(slug))
        unit_records.append(
            {
                "slug": slug,
                "name": _first_non_empty(df.get("unit_name")),
                "detail_id": _first_non_empty(df.get("detail_id")),
                "csv": str(path.relative_to(PROCESSED_DATA_DIR.parent)),
            }
        )

    combined = pd.concat(frames, axis=1, join="outer").fillna(0.0).sort_index()
    combined_window = combined.loc[(combined.index >= start_utc) & (combined.index < end_utc)]
    if combined_window.empty:
        raise RuntimeError("Aggregated unit series is empty for the requested window.")

    combined_df = combined_window.sum(axis=1).rename("production_mw").reset_index()
    combined_df["production_mw"] = combined_df["production_mw"].astype(float)
    return combined_df, unit_records


MIN_HISTORY_SAMPLES = 10
HISTORY_MAX_POINTS = 60


def _compute_water_value_history(
    aligned: pd.DataFrame,
    plant,
    method: str,
    strictness: float,
    jumpm: int,
) -> pd.DataFrame:
    """Re-run the estimator on cumulative days to approximate a rolling history."""
    if aligned.empty:
        return pd.DataFrame()

    timestamps = pd.to_datetime(aligned["timestamp"], utc=True)
    unique_days = timestamps.dt.floor("D").drop_duplicates().sort_values()
    if unique_days.empty:
        return pd.DataFrame()

    if len(unique_days) > HISTORY_MAX_POINTS:
        indices = np.linspace(0, len(unique_days) - 1, HISTORY_MAX_POINTS, dtype=int)
        selected_days = unique_days.iloc[indices]
    else:
        selected_days = unique_days

    records: list[pd.DataFrame] = []

    for day in selected_days:
        cutoff = day + pd.Timedelta(days=1)
        subset = aligned[timestamps < cutoff]
        if subset.shape[0] < MIN_HISTORY_SAMPLES:
            continue

        production = subset["production_mw"].to_numpy(dtype=float)
        prices = subset["price_eur_per_mwh"].to_numpy(dtype=float)
        epoch = subset["epoch_seconds"].to_numpy(dtype=float)

        # SAMBA/05/11 Sections 2.1–2.3: rerun segmentation and water value estimation on the partial history.
        result = watervalue(
            productiondata=production,
            productiontime=epoch,
            pricedata=prices,
            pricetime=epoch,
            prodlimits=plant.resolved_prodlimits(),
            negativeprod=False,
            maxinstalled=plant.max_installed,
            estinterval=True,
            estmethod=method,
            strictness=strictness,
            jumpm=jumpm,
            doprint=False,
        )

        wv_df = _format_water_values(result.water_values, estinterval=True)
        if wv_df.empty:
            continue

        midpoint = day + pd.Timedelta(hours=12)
        if midpoint.tzinfo is None:
            midpoint = midpoint.tz_localize("UTC")
        else:
            midpoint = midpoint.tz_convert("UTC")

        records.append(wv_df.assign(timestamp=midpoint))

    if not records:
        return pd.DataFrame()

    history_df = pd.concat(records, ignore_index=True)
    history_df["interval"] = history_df["interval"].astype(int)
    history_df["timestamp"] = pd.to_datetime(history_df["timestamp"], utc=True)
    return history_df.sort_values(["timestamp", "interval"]).reset_index(drop=True)


def _build_arg_parser() -> argparse.ArgumentParser:
    """CLI definition for end-to-end pipeline execution."""
    parser = argparse.ArgumentParser(description="Fetch real production data and run the water value algorithm.")
    parser.add_argument("--start", type=str, help="Inclusive UTC start (YYYY-MM-DD)", default=None)
    parser.add_argument("--end", type=str, help="Exclusive UTC end (YYYY-MM-DD)", default=None)
    parser.add_argument("--area", type=str, default="NO2", help="ENTSO-E price area (default: NO2)")
    parser.add_argument(
        "--methods",
        nargs="*",
        default=["minimum", "jump"],
        help="Estimation methods to run (SAMBA/05/11 Sections 2.3.1 and 2.3.2).",
    )
    parser.add_argument(
        "--strictness",
        type=float,
        default=0.5,
        help="Curvature threshold |s| for segment selection (SAMBA/05/11 Section 2.2).",
    )
    parser.add_argument(
        "--jumpm",
        type=int,
        default=60,
        help="Breakpoint neighbourhood half-width c in minutes (SAMBA/05/11 Section 2.3.1).",
    )
    parser.add_argument("--output-summary", type=Path, default=OUTPUT_DIR / "production_summary.json")
    parser.add_argument(
        "--max-samples",
        type=int,
        default=DEFAULT_MAX_SAMPLES,
        help=(
            "Maximum aligned samples before automatic resampling. "
            "Lower values shorten runtime for long fetch windows."
        ),
    )
    parser.add_argument(
        "--production-source",
        choices=["web"],
        default="web",
        help="Source for production data. Only the ENTSO-E transparency website scraper is supported.",
    )
    return parser


def _parse_dates(start: str | None, end: str | None) -> tuple[datetime, datetime]:
    """Parse ISO date strings (UTC) with defaults covering the previous week."""
    if start:
        dt_start = datetime.fromisoformat(start)
    else:
        dt_start = datetime.utcnow() - timedelta(days=7)
    if end:
        dt_end = datetime.fromisoformat(end)
    else:
        dt_end = datetime.utcnow()
    if dt_end <= dt_start:
        raise ValueError("End datetime must be after start datetime.")
    return dt_start, dt_end


def _write_processed(df: pd.DataFrame, path: Path) -> None:
    """Persist processed dataframe to CSV, ensuring parent directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


DEFAULT_MAX_SAMPLES = 20000

def run_pipeline(
    start: datetime,
    end: datetime,
    area: str,
    methods: Iterable[str],
    strictness: float,
    jumpm: int,
    summary_path: Path,
    progress_cb: Callable[[str, float], None] | None = None,
    max_samples: int | None = DEFAULT_MAX_SAMPLES,
    refresh_data: bool = True,
    production_source: str = "web",
) -> None:
    """Fetch, align, and analyse production/price data for the configured plants."""
    sample_threshold = max_samples
    if sample_threshold is not None and sample_threshold <= 0:
        sample_threshold = None
    threshold_token = -1 if sample_threshold is None else int(sample_threshold)
    method_list = list(methods)
    area_key = area.upper()
    selected_plants = [plant for plant in PLANTS if plant.price_area.upper() == area_key]
    if not selected_plants:
        available = ", ".join(sorted({plant.price_area for plant in PLANTS}))
        raise ValueError(f"No configured plants found for area '{area}'. Available areas: {available}")

    unit_plants = derive_unit_plants(selected_plants, split_parent_capacity=True)
    if unit_plants:
        selected_plants = list(selected_plants) + unit_plants

    total_steps = max(1, 1 + len(selected_plants) * (1 + len(method_list)))
    completed = 0

    def advance(message: str, increment: bool = True) -> None:
        nonlocal completed
        if increment:
            completed += 1
        if progress_cb is not None:
            progress_cb(message, min(1.0, completed / total_steps))

    if progress_cb is not None:
        progress_cb("Starting pipeline…", 0.0)

    ensure_directories()

    def price_progress(chunk_idx: int, chunk_total: int) -> None:
        if progress_cb is not None and chunk_total > 0:
            progress_cb(
                f"Fetching prices ({chunk_idx}/{chunk_total})",
                min(1.0, completed / total_steps),
            )

    price_path = PROCESSED_DATA_DIR / f"price_{area_key}.csv"
    if refresh_data or not price_path.exists():
        price_df = fetch_price_series(area_key, start, end, progress_cb=price_progress)
        _write_processed(price_df, price_path)
        advance("Fetched price series")
    else:
        price_df = pd.read_csv(price_path, parse_dates=["timestamp"])
        advance("Loaded cached price series")

    intraday_path = PROCESSED_DATA_DIR / f"price_{area_key}_intraday.csv"
    price_intraday_rel: str | None = None
    if refresh_data or not intraday_path.exists():
        try:
            price_intraday_df = fetch_price_series(
                area_key,
                start,
                end,
                # ENTSO-E process type A07 returns the intraday auction series.
                process_type="A07",
            )
        except Exception as exc:
            if progress_cb is not None:
                progress_cb(
                    f"Skipping intraday prices ({exc})",
                    min(1.0, completed / total_steps),
                )
            if intraday_path.exists():
                price_intraday_rel = str(intraday_path.relative_to(PROCESSED_DATA_DIR.parent))
        else:
            _write_processed(price_intraday_df, intraday_path)
            price_intraday_rel = str(intraday_path.relative_to(PROCESSED_DATA_DIR.parent))
    else:
        price_intraday_rel = str(intraday_path.relative_to(PROCESSED_DATA_DIR.parent))

    price_15_path = PROCESSED_DATA_DIR / f"price_{area_key}_15min.csv"
    price_15_rel: str | None = None
    if refresh_data or not price_15_path.exists():
        try:
            price_df_15 = fetch_price_series_quarter_hour(area_key, start, end)
        except Exception as exc:
            if progress_cb is not None:
                progress_cb(f"Skipping 15-min prices ({exc})", min(1.0, completed / total_steps))
            if price_15_path.exists():
                price_15_rel = str(price_15_path.relative_to(PROCESSED_DATA_DIR.parent))
        else:
            _write_processed(price_df_15, price_15_path)
            price_15_rel = str(price_15_path.relative_to(PROCESSED_DATA_DIR.parent))
    else:
        price_15_rel = str(price_15_path.relative_to(PROCESSED_DATA_DIR.parent))
    price_df["timestamp"] = pd.to_datetime(price_df["timestamp"], utc=True)

    summary: List[Dict[str, object]] = []

    for plant in selected_plants:
        resource_total = len(plant.registered_resources)

        if progress_cb is not None:
            progress_cb(f"{plant.name}: fetching production…", min(1.0, completed / total_steps))

        def resource_progress(
            code: str,
            chunk_index: int,
            chunk_total: int,
            resource_index: int,
            total_resources: int,
        ) -> None:
            if progress_cb is not None and chunk_total > 0:
                if chunk_total > 1:
                    message = (
                        f"{plant.name}: {code} ({resource_index}/{total_resources}) "
                        f"chunk {chunk_index}/{chunk_total}"
                    )
                else:
                    message = f"{plant.name}: {code} ({resource_index}/{total_resources})"
                progress_cb(message, min(1.0, completed / total_steps))

        production_path = PROCESSED_DATA_DIR / f"{plant.id}_production.csv"
        production_source_used: str | None = None
        unit_csv_records: list[dict[str, str]] = []
        production_df: pd.DataFrame | None = None

        if not plant.registered_resources and plant.combine_from_units:
            try:
                production_df, unit_csv_records = _aggregate_units_from_csvs(plant.combine_from_units, start, end)
            except Exception as exc:
                raise RuntimeError(f"{plant.name}: {exc}") from exc
            production_source_used = "unit-sum"
            _write_processed(production_df, production_path)
            advance(f"{plant.name}: aggregated unit series")
        elif refresh_data or not production_path.exists():
            if production_source != "web":
                raise RuntimeError("Unsupported production source requested. Only 'web' is allowed.")
            try:
                web_result = fetch_production_series_web(
                    web_name=plant.resolved_web_name(),
                    area_code=PRICE_AREA_CODES[plant.price_area.upper()],
                    start=start,
                    end=end,
                    unit_filters=getattr(plant, "entsoe_web_unit_filters", None),
                )
            except Exception as exc:
                raise RuntimeError(f"{plant.name}: failed to fetch production via ENTSO-E transparency ({exc}).") from exc
            production_df = web_result.total
            production_source_used = "web"
            for unit_slug, unit_series in web_result.units.items():
                unit_path = _unit_csv_path(unit_slug)
                unit_df = unit_series.data.copy()
                unit_df = unit_df.loc[:, ["timestamp", "unit_name", "detail_id", "production_mw"]]
                _write_processed(unit_df, unit_path)
                unit_csv_records.append(
                    {
                        "slug": unit_slug,
                        "name": unit_series.name,
                        "detail_id": unit_series.detail_id,
                        "csv": str(unit_path.relative_to(PROCESSED_DATA_DIR.parent)),
                    }
                )
            _write_processed(production_df, production_path)
            advance(f"{plant.name}: fetched production ({production_source_used})")
        else:
            production_df = pd.read_csv(production_path, parse_dates=["timestamp"])
            production_source_used = "cached"
            if progress_cb is not None:
                progress_cb(f"{plant.name}: using cached production", min(1.0, completed / total_steps))
            advance(f"{plant.name}: cached production loaded")

        production_df["timestamp"] = pd.to_datetime(production_df["timestamp"], utc=True)

        if plant.combine_from_units and plant.registered_resources:
            try:
                production_df, unit_csv_records = _aggregate_units_from_csvs(plant.combine_from_units, start, end)
            except Exception as exc:
                raise RuntimeError(f"{plant.name}: {exc}") from exc
            _write_processed(production_df, production_path)
            production_source_used = "unit-sum"
        elif plant.combine_from_units and not unit_csv_records:
            # Ensure summary captures the unit CSVs even when aggregation happened earlier.
            try:
                _, unit_csv_records = _aggregate_units_from_csvs(plant.combine_from_units, start, end)
            except Exception:
                unit_csv_records = []

        aligned = _align_series(price_df, production_df)
        # SAMBA/05/11 Section 2: segmentation assumes a chronological grid.
        resample_rule: str | None = None
        aligned = aligned.sort_values("timestamp").reset_index(drop=True)
        native_spacing = _infer_native_spacing(aligned["timestamp"])
        native_spacing_seconds = (
            int(native_spacing.total_seconds()) if native_spacing is not None else None
        )
        original_samples = len(aligned)
        if sample_threshold is not None and original_samples > sample_threshold:
            # Dynamically widen the resampling interval until the merged series drops below the threshold.
            base_aligned = aligned
            last_candidate = aligned
            for rule in _downsample_rules(native_spacing):
                resampled_candidate = (
                    base_aligned.set_index("timestamp")
                    .resample(rule)
                    .mean()
                    .dropna()
                    .reset_index()
                )
                if resampled_candidate.empty:
                    continue
                last_candidate = resampled_candidate
                resample_rule = rule
                if len(resampled_candidate) <= sample_threshold:
                    aligned = resampled_candidate
                    break
            else:
                aligned = last_candidate
        aligned["epoch_seconds"] = _to_epoch_seconds(aligned["timestamp"])
        aligned_path = PROCESSED_DATA_DIR / f"{plant.id}_aligned.csv"
        _write_processed(aligned, aligned_path)

        plant_output_dir = OUTPUT_DIR / plant.id
        plant_output_dir.mkdir(parents=True, exist_ok=True)

        epoch = aligned["epoch_seconds"].to_numpy(dtype=float)
        production = aligned["production_mw"].to_numpy(dtype=float)
        prices = aligned["price_eur_per_mwh"].to_numpy(dtype=float)

        for method in method_list:
            if progress_cb is not None:
                progress_cb(f"{plant.name}: running {method}…", min(1.0, completed / total_steps))
            # SAMBA/05/11 Summary steps 2–4: feed the aligned series into the estimator.
            args = dict(
                productiondata=production,
                productiontime=epoch,
                pricedata=prices,
                pricetime=epoch,
                prodlimits=plant.resolved_prodlimits(),
                negativeprod=False,
                maxinstalled=plant.max_installed,
                estinterval=True,
                estmethod=method,
                strictness=strictness,
                jumpm=jumpm,
            )
            try:
                result = watervalue(**args, doprint=False)
            except WaterValueError as exc:
                summary.append(
                    {
                        "plant_id": plant.id,
                        "plant_name": plant.name,
                        "production_source": production_source_used,
                        "production_csv": str(production_path.relative_to(PROCESSED_DATA_DIR.parent)),
                        "method": method,
                        "status": "error",
                        "message": str(exc),
                        "area": area,
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                        "strictness": strictness,
                        "jumpm": jumpm,
                        "max_samples_threshold": threshold_token,
                        "resample_rule": resample_rule,
                        "raw_observations": int(original_samples),
                        "native_timestep_seconds": native_spacing_seconds,
                        "price_intraday_file": price_intraday_rel,
                        "price_quarter_hour_file": price_15_rel,
                        "unit_csvs": unit_csv_records,
                    }
                )
                advance(f"{plant.name}: {method} failed")
                continue

            wv_df = _format_water_values(result.water_values, estinterval=True)
            wv_path = plant_output_dir / f"{plant.id}_{method}_water_values.csv"
            _write_processed(wv_df, wv_path)

            levels_path = plant_output_dir / f"{plant.id}_{method}_levels.csv"
            level_df = pd.DataFrame(
                {
                    "timestamp": aligned["timestamp"],
                    "production_mw": production,
                    "segment_mean_mw": result.level_means,
                    "level": result.production_levels,
                }
            )
            _write_processed(level_df, levels_path)

            breakpoints_path = plant_output_dir / f"{plant.id}_{method}_breakpoints.csv"
            bp_df = pd.DataFrame({"timestamp": aligned["timestamp"], "breakpoint_code": result.breakpoints})
            _write_processed(bp_df, breakpoints_path)

            history_df = _compute_water_value_history(aligned, plant, method, strictness, jumpm)
            history_path = plant_output_dir / f"{plant.id}_{method}_water_history.csv"
            if history_df.empty:
                if history_path.exists():
                    history_path.unlink()
            else:
                _write_processed(history_df, history_path)

            valid_bp = int(np.sum(np.array(result.breakpoints) == 2))
            summary.append(
                {
                    "plant_id": plant.id,
                    "plant_name": plant.name,
                    "production_source": production_source_used,
                    "production_csv": str(production_path.relative_to(PROCESSED_DATA_DIR.parent)),
                    "method": method,
                    "status": "ok",
                    "water_values_file": str(wv_path.relative_to(OUTPUT_DIR.parent)),
                    "levels_file": str(levels_path.relative_to(OUTPUT_DIR.parent)),
                    "breakpoints_file": str(breakpoints_path.relative_to(OUTPUT_DIR.parent)),
                    "valid_breakpoints": valid_bp,
                    "observations": len(aligned),
                    "prodlimits": plant.resolved_prodlimits(),
                    "max_installed": plant.max_installed,
                    "area": area_key,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "strictness": strictness,
                    "jumpm": jumpm,
                    "max_samples_threshold": threshold_token,
                    "resample_rule": resample_rule,
                    "raw_observations": int(original_samples),
                    "native_timestep_seconds": native_spacing_seconds,
                    "price_intraday_file": price_intraday_rel,
                    "price_quarter_hour_file": price_15_rel,
                    "unit_csvs": unit_csv_records,
                }
            )
            advance(f"{plant.name}: {method} completed")

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    advance("Pipeline complete", increment=False)


def main() -> None:
    args = _build_arg_parser().parse_args()
    if args.area.upper() not in PRICE_AREA_CODES:
        raise SystemExit(f"Unsupported price area '{args.area}'. Expected one of {', '.join(PRICE_AREA_CODES)}.")
    start_dt, end_dt = _parse_dates(args.start, args.end)
    run_pipeline(
        start=start_dt,
        end=end_dt,
        area=args.area,
        methods=args.methods,
        strictness=args.strictness,
        jumpm=args.jumpm,
        summary_path=args.output_summary,
        max_samples=args.max_samples,
        production_source=args.production_source,
    )


if __name__ == "__main__":
    main()
