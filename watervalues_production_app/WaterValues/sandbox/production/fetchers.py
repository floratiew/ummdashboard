"""Remote data utilities for the production sandbox.

Wraps ENTSO-E, Nord Pool, and Statnett clients from `toolkit.power` to fetch
price and production series as pandas dataframes.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import re
from pathlib import Path
from typing import Callable, Iterable, Sequence

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parents[3]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

try:
    from toolkit.power import EntsoeClient, StatnettClient, NordpoolClient, load_env_file
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("toolkit package is unavailable; ensure repository root is on PYTHONPATH.") from exc

try:
    from .config import (
        ENTSOE_CONTROL_AREA_NO,
        PRICE_AREA_CODES,
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
    )
except ImportError:
    from config import (
        ENTSOE_CONTROL_AREA_NO,
        PRICE_AREA_CODES,
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
    )

PRICE_CHUNK_DAYS = 90
PRODUCTION_CHUNK_DAYS = 90
OSLO_TZ = ZoneInfo("Europe/Oslo")
ENTSOE_WEB_BASE = "https://transparency.entsoe.eu"
ENTSOE_WEB_PRODUCTION_TYPES = [
    "B01",
    "B25",
    "B02",
    "B03",
    "B04",
    "B05",
    "B06",
    "B07",
    "B08",
    "B09",
    "B10",
    "B11",
    "B12",
    "B13",
    "B14",
    "B20",
    "B15",
    "B16",
    "B17",
    "B18",
    "B19",
]
LOGGER = logging.getLogger(__name__)


def _create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


@dataclass(frozen=True)
class EntsoeWebUnitSeries:
    slug: str
    name: str
    detail_id: str
    data: pd.DataFrame


@dataclass(frozen=True)
class EntsoeWebSeries:
    total: pd.DataFrame
    units: dict[str, EntsoeWebUnitSeries]


def _ensure_env_loaded() -> None:
    """Load `.env` fallbacks so ENTSO-E/Nord Pool tokens are available."""
    if "ENTSOE_TOKEN" not in os.environ:
        load_env_file()


def _make_entsoe_client() -> EntsoeClient:
    """Instantiate an ENTSO-E client using the configured security token."""
    _ensure_env_loaded()
    token = os.environ.get("ENTSOE_TOKEN")
    return EntsoeClient(token=token)


def _iter_periods(start: datetime, end: datetime, chunk_days: int) -> Iterable[tuple[datetime, datetime]]:
    """Yield (start, end) windows limited by `chunk_days`."""
    if chunk_days <= 0:
        raise ValueError("chunk_days must be positive")
    delta = timedelta(days=chunk_days)
    current = start
    while current < end:
        next_end = min(end, current + delta)
        yield current, next_end
        current = next_end


def fetch_price_series(
    area: str,
    start: datetime,
    end: datetime,
    *,
    progress_cb: Callable[[int, int], None] | None = None,
    process_type: str = "A01",
) -> pd.DataFrame:
    """Fetch day-ahead (default) or intraday auction prices from ENTSO-E."""
    area_code = PRICE_AREA_CODES.get(area.upper())
    if area_code is None:
        raise ValueError(f"Unknown price area '{area}'. Expected one of: {', '.join(PRICE_AREA_CODES)}")
    client = _make_entsoe_client()
    frames = []
    periods = list(_iter_periods(start, end, PRICE_CHUNK_DAYS))
    for idx, (chunk_start, chunk_end) in enumerate(periods, start=1):
        df = client.fetch(
            document_type="A44",
            period_start=chunk_start,
            period_end=chunk_end,
            in_domain=area_code,
            out_domain=area_code,
            process_type=process_type,
        )
        chunk = (
            df.assign(timestamp=pd.to_datetime(df["timestamp"], utc=True), price_eur_per_mwh=df["value"].astype(float))
            .loc[:, ["timestamp", "price_eur_per_mwh"]]
            .dropna()
        )
        frames.append(chunk)
        if progress_cb is not None:
            progress_cb(idx, len(periods))

    if not frames:
        raise ValueError("Price fetch returned no data.")

    combined = (
        pd.concat(frames)
        .drop_duplicates(subset="timestamp", keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    return combined


def fetch_price_series_quarter_hour(
    area: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """
    Retrieve quarter-hour day-ahead prices from Nord Pool's data portal.

    Requires the environment variable NORDPOOL_API_KEY (subscription key).
    """
    if start >= end:
        raise ValueError("Start must be before end for quarter-hour price fetch.")
    client = NordpoolClient()
    records: list[pd.DataFrame] = []
    current = start.date()
    stop_date = (end - timedelta(days=0)).date()
    while current < stop_date:
        try:
            frame = client.day_ahead_prices(current.isoformat(), [area.upper()], currency="EUR")
        except SystemExit as exc:
            raise RuntimeError(str(exc)) from exc
        subset = frame[frame["area"] == area.upper()].copy()
        if subset.empty:
            current += timedelta(days=1)
            continue
        subset["timestamp"] = pd.to_datetime(subset["delivery_start"], utc=True)
        subset = subset.loc[:, ["timestamp", "price"]].rename(columns={"price": "price_eur_per_mwh"})
        records.append(subset)
        current += timedelta(days=1)

    if not records:
        raise ValueError("Nord Pool quarter-hour price fetch returned no data. Ensure NORDPOOL_API_KEY is set.")

    df = (
        pd.concat(records)
        .sort_values("timestamp")
        .drop_duplicates(subset="timestamp", keep="last")
    )
    mask = (df["timestamp"] >= pd.Timestamp(start, tz="UTC")) & (df["timestamp"] < pd.Timestamp(end, tz="UTC"))
    df = df.loc[mask].reset_index(drop=True)
    if df.empty:
        raise ValueError("Quarter-hour price series is empty after filtering to the requested window.")
    return df


_PSR_SIGN = {
    # Pumped-storage pumping (treat as consumption)
    "B19": -1.0,
}


def fetch_production_series(
    resources: Iterable[str],
    start: datetime,
    end: datetime,
    *,
    per_resource_cb: Callable[[str, int, int, int, int], None] | None = None,
    pump_resources: Iterable[str] | None = None,  # kept for future use
) -> pd.DataFrame:
    """Aggregate net production from ENTSO-E for the supplied resource codes."""
    resource_list = list(dict.fromkeys(resources))
    if not resource_list:
        raise ValueError("No registered resources supplied for production fetch.")

    def fetch_single(
        code: str,
        resource_idx: int,
        resource_total: int,
    ) -> tuple[pd.Series, list[tuple[str, int, int, int, int]]]:
        client = _make_entsoe_client()
        chunk_periods = list(_iter_periods(start, end, PRODUCTION_CHUNK_DAYS))
        chunk_series: list[pd.Series] = []
        events: list[tuple[str, int, int, int, int]] = []
        for chunk_idx, (chunk_start, chunk_end) in enumerate(chunk_periods, start=1):
            frame = client.fetch(
                document_type="A75",
                period_start=chunk_start,
                period_end=chunk_end,
                in_domain=ENTSOE_CONTROL_AREA_NO,
                process_type="A16",
                additional_params={"registeredResource": code},
            )
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
            frame["value"] = frame["value"].astype(float)
            multiplier = frame["business_type"].map({"A01": 1.0, "A93": -1.0}).fillna(0.0)
            frame = frame.copy()
            frame["net_mw"] = frame["value"] * multiplier
            net = (
                frame
                .loc[:, ["timestamp", "net_mw"]]
                .groupby("timestamp", sort=True)["net_mw"]
                .sum()
            )
            if per_resource_cb:
                events.append((code, chunk_idx, len(chunk_periods), resource_idx, resource_total))
            if net.empty:
                continue

            series = (
                frame.assign(psr_sign=frame["psr_type"].str.upper().map(_PSR_SIGN).fillna(1.0))
                .assign(adjusted=lambda df: df["net_mw"] * df["psr_sign"])
                .groupby("timestamp", sort=True)["adjusted"]
                .sum()
            )
            chunk_series.append((series * 0.01).rename(code))

        if not chunk_series:
            return pd.Series(dtype=float, name=code), events

        combined = (
            pd.concat(chunk_series)
            .groupby(level=0)
            .mean()
            .sort_index()
        )
        combined.name = code
        return combined, events

    series = []
    total_resources = len(resource_list)
    with ThreadPoolExecutor(max_workers=min(total_resources, 3)) as executor:
        future_map = {
            executor.submit(fetch_single, code, idx, total_resources): code
            for idx, code in enumerate(resource_list, start=1)
        }
        for future in as_completed(future_map):
            series_result, events = future.result()
            series.append(series_result)
            if per_resource_cb:
                for event in events:
                    per_resource_cb(*event)

    if not series:
        raise ValueError("Production fetch returned no data.")

    combined = pd.concat(series, axis=1).fillna(0.0).sort_index()
    total = combined.sum(axis=1, min_count=1).rename("production_mw")
    return total.reset_index()


def _entsoe_web_params(
    area_code: str,
    web_name: str,
    *,
    control_area: str = ENTSOE_CONTROL_AREA_NO,
    production_types: Sequence[str] = ENTSOE_WEB_PRODUCTION_TYPES,
) -> dict[str, str] | dict[str, Sequence[str]]:
    params: dict[str, str] | dict[str, Sequence[str]] = {
        "name": "",
        "defaultValue": "false",
        "viewType": "TABLE",
        "areaType": "BZN",
        "atch": "false",
        "area.values": f"CTY|{control_area}!BZN|{area_code}",
        "masterDataFilterName": web_name,
        "masterDataFilterCode": "",
        "dateTime.timezone": "CET_CEST",
        "dateTime.timezone_input": "CET (UTC+1) / CEST (UTC+2)",
    }
    params["productionType.values"] = list(production_types)
    return params


def _format_web_day(day_local: datetime) -> str:
    return day_local.strftime("%d.%m.%Y 00:00|CET|DAYTIMERANGE")


def _clean_cell(value: str | None) -> float:
    if not value:
        return 0.0
    stripped = value.replace("\xa0", " ").strip()
    if not stripped or stripped.lower() in {"n/e", "n/a"}:
        return 0.0
    # Remove HTML tags if present
    while "<" in stripped and ">" in stripped:
        start = stripped.find("<")
        end = stripped.find(">", start)
        if end == -1:
            break
        stripped = stripped[:start] + stripped[end + 1 :]
    stripped = stripped.strip()
    if not stripped:
        return 0.0
    parts = stripped.split()
    if not parts:
        return 0.0
    text = parts[0].replace(",", ".")
    normalized = text.replace("\u2212", "-").replace("–", "-")  # handle unicode minus/en dash
    if normalized in {"-", "--"}:
        return 0.0
    try:
        return float(normalized)
    except ValueError:  # pragma: no cover - defensive
        LOGGER.warning("Unable to parse numeric value from '%s'; defaulting to 0.0", value)
        return 0.0


def _matches_filter(value: str, filters: Sequence[str] | None) -> bool:
    if not filters:
        return True
    normalized = value.replace(" ", "").upper()
    return any(filter_value.replace(" ", "").upper() in normalized for filter_value in filters)


def _slugify_unit(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^0-9A-Za-z]+", "_", name.strip().lower()).strip("_") or "unit"
    candidate = base
    counter = 2
    while candidate in taken:
        candidate = f"{base}_{counter}"
        counter += 1
    taken.add(candidate)
    return candidate


def _fetch_entsoe_web_summary(session: requests.Session, params: dict[str, object]) -> list[list[str]]:
    response = session.post(
        f"{ENTSOE_WEB_BASE}/generation/r2/actualGenerationPerGenerationUnit/getDataTableData",
        params=params,
        json={
            "sEcho": 1,
            "iColumns": 5,
            "sColumns": "type,alternativeCode,generationAverage,consumptionAverage,",
            "iDisplayStart": 0,
            "iDisplayLength": 200,
            "amDataProp": [0, 1, 2, 3, 4],
        },
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("aaData", [])


def _fetch_entsoe_web_detail(
    session: requests.Session,
    params: dict[str, object],
    detail_id: str,
    *,
    length: int = 200,
) -> list[list[str]]:
    detail_params = dict(params)
    detail_params["detailId"] = detail_id
    response = session.post(
        f"{ENTSOE_WEB_BASE}/generation/r2/actualGenerationPerGenerationUnit/getDataTableDetailData",
        params=detail_params,
        json={
            "sEcho": 1,
            "iColumns": 3,
            "sColumns": "mtu,generation,consumption",
            "iDisplayStart": 0,
            "iDisplayLength": length,
            "amDataProp": [0, 1, 2],
        },
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("aaData", [])


def fetch_production_series_web(
    *,
    web_name: str,
    area_code: str,
    start: datetime,
    end: datetime,
    unit_filters: Sequence[str] | None = None,
    control_area: str = ENTSOE_CONTROL_AREA_NO,
    session_factory: Callable[[], requests.Session] | None = None,
) -> EntsoeWebSeries:
    """Scrape ENTSO-E transparency website to obtain quarter-hour production."""
    if start >= end:
        raise ValueError("Start must be before end for ENTSO-E web scraping.")

    start_utc = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end_utc = end if end.tzinfo else end.replace(tzinfo=timezone.utc)

    session = session_factory() if session_factory else _create_session()

    current_local = start_utc.astimezone(OSLO_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = end_utc.astimezone(OSLO_TZ)

    records: list[pd.Series] = []
    unit_frames: dict[str, list[pd.DataFrame]] = {}
    unit_details: dict[str, str] = {}
    while current_local < end_local:
        params = _entsoe_web_params(area_code, web_name, control_area=control_area)
        day_string = _format_web_day(current_local)
        params["dateTime.dateTime"] = day_string
        params["dateTime.endDateTime"] = day_string
        session.get(
            f"{ENTSOE_WEB_BASE}/generation/r2/actualGenerationPerGenerationUnit/show",
            params=params,
            timeout=30,
        )
        summary_rows = _fetch_entsoe_web_summary(session, params)
        if not summary_rows:
            current_local += timedelta(days=1)
            continue

        detail_rows: list[pd.DataFrame] = []
        for row in summary_rows:
            if len(row) < 5:
                continue
            unit_name = row[1].strip()
            detail_id = row[4]
            if not detail_id or not _matches_filter(unit_name, unit_filters):
                continue
            detail_data = _fetch_entsoe_web_detail(session, params, detail_id)
            if not detail_data:
                continue
            entries = []
            for mtu, gen, cons in detail_data:
                start_str = mtu.split(" - ")[0]
                hour, minute = [int(part) for part in start_str.split(":")]
                local_timestamp = current_local.replace(hour=hour, minute=minute)
                timestamp = local_timestamp.astimezone(timezone.utc)
                generation = _clean_cell(gen)
                consumption = _clean_cell(cons)
                entries.append(
                    {
                        "timestamp": timestamp,
                        "generation_mw": generation,
                        "consumption_mw": consumption,
                    }
                )
            frame = pd.DataFrame(entries)
            frame["unit_name"] = unit_name
            frame["detail_id"] = detail_id
            detail_rows.append(frame)
            unit_frames.setdefault(unit_name, []).append(frame)
            unit_details[unit_name] = detail_id

        if detail_rows:
            day_frame = pd.concat(detail_rows, ignore_index=True)
            grouped = (
                day_frame.groupby("timestamp", as_index=False)
                .agg({"generation_mw": "sum", "consumption_mw": "sum"})
                .assign(production_mw=lambda df: df["generation_mw"] - df["consumption_mw"])
                .loc[:, ["timestamp", "production_mw"]]
            )
            records.append(grouped.set_index("timestamp")["production_mw"])

        current_local += timedelta(days=1)

    if not records:
        raise ValueError(f"ENTSO-E web scraping returned no data for {web_name}.")

    combined = (
        pd.concat(records)
        .groupby(level=0)
        .sum()
        .sort_index()
        .to_frame(name="production_mw")
    )

    mask = (combined.index >= start_utc) & (combined.index < end_utc)
    filtered = combined.loc[mask]
    if filtered.empty:
        raise ValueError(f"ENTSO-E web scraping produced no rows within {start}–{end}.")
    total_df = filtered.reset_index().rename(columns={"index": "timestamp"})

    unit_series: dict[str, EntsoeWebUnitSeries] = {}
    taken_slugs: set[str] = set()
    for unit_name, frames in unit_frames.items():
        unit_df = pd.concat(frames, ignore_index=True)
        aggregated = (
            unit_df.groupby("timestamp", as_index=False)
            .agg({"generation_mw": "sum", "consumption_mw": "sum"})
            .assign(
                production_mw=lambda df: df["generation_mw"] - df["consumption_mw"],
            )
            .loc[:, ["timestamp", "production_mw"]]
            .sort_values("timestamp")
        )
        aggregated = aggregated.loc[
            (aggregated["timestamp"] >= start_utc) & (aggregated["timestamp"] < end_utc)
        ].copy()
        aggregated["unit_name"] = unit_name
        aggregated["detail_id"] = unit_details.get(unit_name, "")
        slug = _slugify_unit(unit_name, taken=taken_slugs)
        unit_series[slug] = EntsoeWebUnitSeries(
            slug=slug,
            name=unit_name,
            detail_id=unit_details.get(unit_name, ""),
            data=aggregated.reset_index(drop=True),
        )

    return EntsoeWebSeries(total_df, unit_series)


def fetch_statnett_production(year: int) -> pd.DataFrame:
    """Download Statnett annual production table and store derived CSV."""
    client = StatnettClient()
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    destination = RAW_DATA_DIR / f"statnett_production_{year}.html"
    client.download("productionconsumption", str(year), destination)
    tables = pd.read_html(destination.read_text(encoding="utf-8"))
    if not tables:
        raise ValueError(f"Statnett response for {year} did not contain tables.")
    table = tables[0]
    if table.shape[1] < 3:
        raise ValueError(f"Unexpected Statnett table shape {table.shape}.")
    renamed = table.rename(columns={table.columns[0]: "time_local", table.columns[1]: "production_mw", table.columns[2]: "consumption_mw"})
    renamed["timestamp"] = pd.to_datetime(renamed["time_local"], utc=True)
    processed = renamed.loc[:, ["timestamp", "production_mw", "consumption_mw"]].dropna()
    processed.to_csv(PROCESSED_DATA_DIR / f"statnett_production_{year}.csv", index=False)
    return processed
