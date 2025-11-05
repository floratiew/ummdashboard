#!/usr/bin/env python3
"""
Utilities for retrieving Norwegian power market datasets from ENTSO-E, Statnett,
NVE HydAPI, and Elhub's open energy-data service.

Example CLI usage:
  python power.py entsoe prices --zones NO1 NO2 --start 2024-01-01 --end 2024-01-07 \
      --token $ENTSOE_TOKEN --out data/entsoe_prices.csv
  python power.py statnett download --dataset produksjon --year 2023 --out raw/production_2023.csv
  python power.py nve observations --station 6.10.0 --parameter reservoir_level \
      --start 2024-01-01 --end 2024-02-01 --resolution week --api-key $NVE_API_KEY
  python power.py elhub fetch --resource price-areas --dataset CONSUMPTION_PER_GROUP_MBA_HOUR \
      --start 2024-08-01 --end 2024-08-07 --filter consumptionGroup=private --out data/elhub.csv
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover - pandas expected in workflow
    raise SystemExit("pandas is required: pip install pandas") from exc


LOG = logging.getLogger("power_data")


def load_env_file(filename: str = ".env") -> None:
    """Populate os.environ with entries from a simple KEY=VALUE .env file."""
    env_path = Path(__file__).resolve().parent / filename
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_env_file()


# -------------------------- shared helpers -------------------------- #


def ensure_output_path(path: Optional[str]) -> Optional[Path]:
    if not path:
        return None
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def parse_datetime(value: str, default_time: dt.time | None = None) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"Invalid datetime '{value}': {err}") from err
    if parsed.tzinfo:
        return parsed.astimezone(dt.timezone.utc)
    if isinstance(default_time, dt.time):
        parsed = dt.datetime.combine(parsed.date(), default_time)
    return parsed


def to_entsoe_period(value: dt.datetime) -> str:
    return value.strftime("%Y%m%d%H%M")


def parse_iso_duration(resolution: str) -> dt.timedelta:
    match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", resolution)
    if not match:
        raise ValueError(f"Unsupported ENTSO-E resolution '{resolution}'")
    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    return dt.timedelta(days=days, hours=hours, minutes=minutes)


def write_dataframe(df: pd.DataFrame, destination: Optional[Path]) -> None:
    if destination is None:
        df.to_csv(sys.stdout, index=False)
        return
    suffix = destination.suffix.lower()
    if suffix in (".csv", ".txt"):
        df.to_csv(destination, index=False)
    elif suffix in (".parquet", ".pq"):
        try:
            df.to_parquet(destination, index=False)
        except Exception as err:
            raise SystemExit(f"Failed to write parquet: {err}") from err
    elif suffix in (".json", ".ndjson"):
        if suffix == ".ndjson":
            destination.write_text("\n".join(df.to_json(orient="records", lines=True)))
        else:
            destination.write_text(df.to_json(orient="records", date_format="iso"))
    else:
        raise SystemExit(f"Unsupported output format '{destination.suffix}'")


def suffix_match(tag: str, name: str) -> bool:
    return tag.split("}")[-1] == name


def find_child(node: ET.Element, name: str) -> Optional[ET.Element]:
    for child in node:
        if suffix_match(child.tag, name):
            return child
    return None


def find_text(node: ET.Element, name: str, default: Optional[str] = None) -> Optional[str]:
    child = find_child(node, name)
    if child is not None and child.text is not None:
        return child.text
    return default


# -------------------------- ENTSO-E --------------------------------- #


class EntsoeClient:
    BASE_URL = "https://web-api.tp.entsoe.eu/api"

    def __init__(self, token: str, timeout: int = 120) -> None:
        if not token:
            raise SystemExit("ENTSO-E security token is required. Use --token or ENTSOE_TOKEN.")
        self._session = requests.Session()
        self._session.params = {"securityToken": token}
        self.timeout = timeout

    def fetch(
        self,
        document_type: str,
        period_start: dt.datetime,
        period_end: dt.datetime,
        *,
        in_domain: Optional[str] = None,
        out_domain: Optional[str] = None,
        process_type: Optional[str] = None,
        additional_params: Optional[Dict[str, str]] = None,
    ) -> pd.DataFrame:
        params: Dict[str, str] = {
            "documentType": document_type,
            "periodStart": to_entsoe_period(period_start),
            "periodEnd": to_entsoe_period(period_end),
        }
        if in_domain:
            params["in_Domain"] = in_domain
        if out_domain:
            params["out_Domain"] = out_domain
        if process_type:
            params["processType"] = process_type
        if additional_params:
            params.update(additional_params)

        response = self._session.get(self.BASE_URL, params=params, timeout=self.timeout)
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            msg = f"ENTSO-E request failed ({err.response.status_code}): {err.response.text[:200]}"
            raise SystemExit(msg) from err
        return self._parse_timeseries(response.text, params)

    def _parse_timeseries(self, xml_text: str, params: Dict[str, str]) -> pd.DataFrame:
        root = ET.fromstring(xml_text)
        records: List[Dict[str, Any]] = []
        for ts in root.iter():
            if not suffix_match(ts.tag, "TimeSeries"):
                continue
            metadata = {
                "document_type": params.get("documentType"),
                "in_domain": find_text(ts, "in_Domain.mRID") or params.get("in_Domain"),
                "out_domain": find_text(ts, "out_Domain.mRID") or params.get("out_Domain"),
                "bidding_zone": find_text(ts, "BiddingZone_Domain.mRID"),
                "business_type": find_text(ts, "businessType"),
                "psr_type": find_text(find_child(ts, "MktPSRType"), "psrType")
                if find_child(ts, "MktPSRType")
                else None,
                "unit": find_text(ts, "measurementUnit.name"),
                "currency": find_text(ts, "currency_Unit.name"),
            }
            for period in ts:
                if not suffix_match(period.tag, "Period"):
                    continue
                interval = find_child(period, "timeInterval")
                if interval is None:
                    continue
                start_text = find_text(interval, "start")
                resolution_text = find_text(period, "resolution")
                if not start_text or not resolution_text:
                    continue
                try:
                    start = dt.datetime.fromisoformat(start_text.replace("Z", "+00:00"))
                except ValueError:
                    LOG.warning("Skipping malformed start timestamp '%s'", start_text)
                    continue
                step = parse_iso_duration(resolution_text)
                for point in period:
                    if not suffix_match(point.tag, "Point"):
                        continue
                    pos_text = find_text(point, "position")
                    if not pos_text:
                        continue
                    try:
                        offset = int(pos_text) - 1
                    except ValueError:
                        continue
                    timestamp = start + offset * step
                    value_tag, value = _extract_point_value(point)
                    if value is None:
                        continue
                    records.append(
                        {
                            **metadata,
                            "timestamp": timestamp,
                            "value": value,
                            "value_tag": value_tag,
                            "position": int(pos_text),
                        }
                    )
        if not records:
            raise SystemExit("ENTSO-E response parsed to zero rows. Check parameters or token.")
        df = pd.DataFrame.from_records(records)
        df.sort_values("timestamp", inplace=True)
        return df


def _extract_point_value(point: ET.Element) -> Tuple[str, Optional[float]]:
    candidates = ("price.amount", "quantity", "flow", "capacityAssigned.value", "capacity.value", "volume")
    for name in candidates:
        text = find_text(point, name)
        if text is None:
            continue
        try:
            return name, float(text)
        except ValueError:
            return name, None
    return "value", None


# -------------------------- Nord Pool ------------------------------ #


class NordpoolClient:
    BASE_URL = "https://dataportal-api.nordpoolgroup.com/api"

    def __init__(self, subscription_key: Optional[str] = None, timeout: int = 60) -> None:
        self._session = requests.Session()
        self.timeout = timeout
        self.subscription_key = subscription_key or os.getenv("NORDPOOL_API_KEY")

    def day_ahead_prices(
        self,
        date: str,
        delivery_areas: Sequence[str],
        *,
        market: str = "DayAhead",
        currency: str = "EUR",
    ) -> pd.DataFrame:
        if not date:
            raise SystemExit("Nord Pool day-ahead prices require --date (YYYY-MM-DD).")
        try:
            dt.date.fromisoformat(date)
        except ValueError as err:
            raise SystemExit(f"Invalid date '{date}': {err}") from err
        areas = [area.strip().upper() for area in delivery_areas if area and area.strip()]
        if not areas:
            raise SystemExit("Provide at least one delivery area code (e.g. NO1).")
        params = {
            "date": date,
            "market": market,
            "deliveryArea": ",".join(areas),
            "currency": currency,
        }
        headers: Dict[str, str] = {}
        if not self.subscription_key:
            raise SystemExit(
                "Nord Pool API access requires NORDPOOL_API_KEY (subscription key). "
                "Set it in toolkit/.env or environment variables."
            )
        headers["Ocp-Apim-Subscription-Key"] = self.subscription_key
        response = self._session.get(
            f"{self.BASE_URL}/DayAheadPrices", params=params, headers=headers, timeout=self.timeout
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            message = err.response.text[:200] if err.response is not None else str(err)
            raise SystemExit(f"Nord Pool request failed ({err.response.status_code}): {message}") from err
        payload = response.json()
        entries = payload.get("multiAreaEntries") or []
        if not entries:
            raise SystemExit("Nord Pool response returned no price entries.")

        area_states = _expand_area_states(payload.get("areaStates"))
        area_averages = {
            entry.get("areaCode"): _coerce_float(entry.get("price")) for entry in payload.get("areaAverages") or []
        }
        metadata = {
            "market": payload.get("market"),
            "currency": payload.get("currency"),
            "delivery_date_cet": payload.get("deliveryDateCET"),
            "updated_at": payload.get("updatedAt"),
            "exchange_rate": _coerce_float(payload.get("exchangeRate")),
            "version": payload.get("version"),
        }
        records: List[Dict[str, Any]] = []
        for slot in entries:
            delivery_start = slot.get("deliveryStart")
            delivery_end = slot.get("deliveryEnd")
            per_area = slot.get("entryPerArea") or {}
            for area, price in per_area.items():
                record = {
                    **metadata,
                    "area": area,
                    "delivery_start": delivery_start,
                    "delivery_end": delivery_end,
                    "price": _coerce_float(price),
                }
                if area in area_states:
                    record["area_state"] = area_states[area]
                if area in area_averages:
                    record["area_average"] = area_averages[area]
                records.append(record)
        if not records:
            raise SystemExit("Nord Pool response returned no price entries.")

        df = pd.DataFrame.from_records(records)
        for column in ("delivery_start", "delivery_end", "updated_at"):
            if column in df.columns:
                df[column] = pd.to_datetime(df[column], utc=True, errors="coerce")
        df.sort_values(["area", "delivery_start"], inplace=True)
        return df.reset_index(drop=True)


def _expand_area_states(area_states: Optional[Sequence[Dict[str, Any]]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not area_states:
        return mapping
    for entry in area_states:
        state = entry.get("state")
        for area in entry.get("areas") or []:
            if state:
                mapping[str(area)] = state
    return mapping


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


# -------------------------- Statnett -------------------------------- #


class StatnettClient:
    BASE_URL = "https://driftsdata.statnett.no/restapi/Download"
    TRANSLATOR_URL = "https://driftsdata.statnett.no/restapi/Translator/Translations"
    DATASETS: Tuple[Tuple[str, str], ...] = (
        ("productionconsumption", "ProdConsSourceName"),
        ("physicalflow", "PhysicalFlowSourceName"),
        ("primaryreservesday", "PrimaryReservesDaySourceName"),
        ("primaryreservesdaytwo", "PrimaryReservesDayTwoSourceName"),
        ("primaryreservesweek", "PrimaryReservesWeekSourceName"),
        ("secondaryreserves", "SecondaryReservesSourceName"),
        ("rkomdata", "RkomSourceName"),
        ("rkom", "RkomOldSourceName"),
    )
    EARLIEST_YEAR = 2006

    def __init__(self, timeout: int = 60) -> None:
        self._session = requests.Session()
        self.timeout = timeout
        self._translations: Optional[Dict[str, str]] = None

    def list_datasets(self) -> pd.DataFrame:
        translations = self._fetch_translations()
        current_year = dt.datetime.now(dt.timezone.utc).year
        rows = []
        for dataset, translation_key in self.DATASETS:
            title = translations.get(translation_key, dataset.replace("-", " ").title())
            rows.append(
                {
                    "title": title,
                    "slug": dataset,
                    "download_template": f"{self.BASE_URL}/{dataset}/{{year}}",
                    "first_year": self.EARLIEST_YEAR,
                    "latest_year": current_year,
                }
            )
        return pd.DataFrame(rows)

    def download(self, slug: str, year: Optional[str], destination: Path) -> Path:
        dataset = self._normalise_slug(slug)
        valid_slugs = {entry for entry, _ in self.DATASETS}
        if dataset not in valid_slugs:
            raise SystemExit(
                f"Dataset '{slug}' not recognised. Run 'statnett list' to inspect available slugs."
            )
        target_year = int(year) if year else dt.datetime.now(dt.timezone.utc).year
        if target_year < self.EARLIEST_YEAR:
            raise SystemExit(f"Year must be >= {self.EARLIEST_YEAR}.")
        url = f"{self.BASE_URL}/{dataset}/{target_year}"
        response = self._session.get(url, timeout=self.timeout)
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            raise SystemExit(f"Statnett download failed: {err}") from err
        destination.write_bytes(response.content)
        return destination

    def _fetch_translations(self) -> Dict[str, str]:
        if self._translations is not None:
            return self._translations
        for language in ("en", "no"):
            response = self._session.get(
                self.TRANSLATOR_URL,
                params={"language": language, "prefix": ""},
                timeout=self.timeout,
            )
            response.raise_for_status()
            section = response.json().get("Download") or {}
            if section:
                self._translations = section
                return section
        self._translations = {}
        return self._translations

    @staticmethod
    def _normalise_slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())


# -------------------------- NVE HydAPI ------------------------------- #


class NVEHydroClient:
    BASE_URL = "https://hydapi.nve.no/api/v1"

    def __init__(self, api_key: str, timeout: int = 60) -> None:
        if not api_key:
            raise SystemExit("NVE HydAPI requires an API key. Use --api-key or NVE_API_KEY.")
        self._session = requests.Session()
        self._session.headers["X-API-Key"] = api_key
        self.timeout = timeout
        self._parameter_cache: Optional[pd.DataFrame] = None

    def list_stations(
        self,
        *,
        name: Optional[str] = None,
        station_id: Optional[str] = None,
        active: int = 1,
    ) -> pd.DataFrame:
        params: Dict[str, Any] = {"Active": active}
        if name:
            params["StationName"] = name
        if station_id:
            params["StationId"] = station_id
        response = self._session.get(f"{self.BASE_URL}/Stations", params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        return pd.json_normalize(data)

    def list_parameters(self) -> pd.DataFrame:
        if self._parameter_cache is None:
            response = self._session.get(f"{self.BASE_URL}/Parameters", timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            records = payload.get("data") or []
            self._parameter_cache = pd.DataFrame.from_records(records)
        return self._parameter_cache.copy()

    def observations(
        self,
        station_id: str,
        parameter: str,
        *,
        resolution: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        include_quality: bool = False,
        aggregation: str = "mean",
    ) -> pd.DataFrame:
        parameter_id = self._resolve_parameter(parameter)
        api_resolution, resample_rule = _map_resolution(resolution)
        self._validate_station_supports(station_id, parameter_id, api_resolution)
        payload: Dict[str, Any] = {
            "stationId": station_id,
            "parameter": parameter_id,
            "resolutionTime": api_resolution,
        }
        if start or end:
            payload["referenceTime"] = _format_reference_time(start, end)
        headers = {"Content-Type": "application/json"}
        response = self._session.post(
            f"{self.BASE_URL}/Observations", headers=headers, data=json.dumps([payload]), timeout=self.timeout
        )
        response.raise_for_status()
        payload = response.json()
        records = payload.get("data") or []
        if not records:
            raise SystemExit("No observations returned.")
        entry = records[0]
        series = entry.get("observations") or entry.get("Observations") or []
        if not series:
            raise SystemExit("Observation payload returned no data points.")
        df = pd.DataFrame(series)
        df.columns = [col.lower() for col in df.columns]
        df.rename(
            columns={
                "time": "timestamp",
                "value": "value",
                "quality": "qualitycode",
                "correction": "correctioncode",
            },
            inplace=True,
        )
        if not include_quality:
            df = df.drop(columns=[c for c in ("qualitycode", "correctioncode") if c in df.columns])
        df["Timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df.sort_values("Timestamp", inplace=True)
        if resample_rule:
            df = _resample_values(df, resample_rule, aggregation)
        return df.reset_index(drop=True)

    def _resolve_parameter(self, parameter: str) -> str:
        if parameter is None:
            raise SystemExit("Parameter is required.")
        text = str(parameter).strip()
        if not text:
            raise SystemExit("Parameter cannot be empty.")
        if text.isdigit():
            return text
        normalized = text.lower()
        alias_map = {
            "reservoirlevel": "magasinvolum",
            "reservoirlevels": "magasinvolum",
            "reservoir_volume": "magasinvolum",
            "reservoirvolume": "magasinvolum",
            "magazinevolume": "magasinvolum",
        }
        normalized = alias_map.get(normalized, normalized)
        params = self.list_parameters()
        norwegian = params["parameterName"].astype(str).str.lower()
        english = params["parameterNameEng"].astype(str).str.lower()
        normalized_english = normalized.replace("_", " ")
        matches = params[norwegian.eq(normalized) | english.eq(normalized_english)]
        if matches.empty:
            raise SystemExit(
                f"Unknown parameter '{parameter}'. "
                "Use a numeric parameter id or run 'power.py nve parameters' to inspect available names."
            )
        return str(matches.iloc[0]["parameter"])

    def _validate_station_supports(self, station_id: str, parameter_id: str, resolution: str) -> None:
        metadata = self._fetch_station_metadata(station_id)
        if metadata is None:
            raise SystemExit(f"Station '{station_id}' not found or inactive.")
        series_list = metadata.get("seriesList") or []
        required_minutes = {"hour": 60, "day": 1440, "inst": 0}[resolution]
        for series in series_list:
            if str(series.get("parameter")) != str(parameter_id):
                continue
            available = {item.get("resTime") for item in series.get("resolutionList", [])}
            if required_minutes not in available:
                friendly = ", ".join(sorted(str(v) for v in available)) or "none"
                raise SystemExit(
                    f"Station {station_id} publishes parameter {parameter_id} but not at requested resolution "
                    f"('{resolution}'). Available resolution minutes: {friendly}"
                )
            return
        readable = ", ".join(
            f"{entry.get('parameter')} ({entry.get('parameterName')})" for entry in series_list
        ) or "none"
        raise SystemExit(
            f"Station {station_id} does not publish parameter {parameter_id}. "
            f"Available parameters: {readable}"
        )

    def _fetch_station_metadata(self, station_id: str) -> Optional[Dict[str, Any]]:
        params = {"StationId": station_id, "Active": 1}
        response = self._session.get(f"{self.BASE_URL}/Stations", params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or []
        if not data:
            return None
        return data[0]


def _format_reference_time(start: Optional[str], end: Optional[str]) -> str:
    if start and end:
        return f"{start}/{end}"
    if start:
        return f"{start}/"
    if end:
        return f"/{end}"
    raise ValueError("reference time requires start or end")


def _map_resolution(resolution: str) -> Tuple[str, Optional[str]]:
    key = resolution.lower()
    if key in {"hour", "hours", "h", "60"}:
        return "hour", None
    if key in {"day", "daily", "d", "1440"}:
        return "day", None
    if key in {"inst", "instant", "instantaneous", "raw", "0"}:
        return "inst", None
    if key in {"week", "weekly", "w"}:
        return "day", "W"
    if key in {"month", "monthly", "m"}:
        return "day", "MS"
    raise SystemExit(f"Unsupported resolution '{resolution}'. Valid options: hour, day, inst, week, month.")


def _resample_values(df: pd.DataFrame, rule: str, aggregation: str) -> pd.DataFrame:
    agg_options = {
        "mean": "mean",
        "sum": "sum",
        "min": "min",
        "max": "max",
        "first": "first",
        "last": "last",
        "median": "median",
    }
    agg_key = aggregation.lower()
    if agg_key not in agg_options:
        raise SystemExit(f"Unsupported aggregation '{aggregation}'. Choose from {', '.join(sorted(agg_options))}.")
    df = (
        df.set_index("Timestamp")
        .resample(rule)
        .agg({"value": agg_options[agg_key]})
        .dropna(subset=["value"])
        .reset_index()
    )
    return df


# -------------------------- Elhub energy data ----------------------- #


ELHUB_BASE = "https://api.elhub.no/energy-data/v0"


def elhub_fetch(
    resource: str,
    dataset: str,
    *,
    start: Optional[str],
    end: Optional[str],
    filters: Dict[str, str],
    timeout: int = 60,
) -> pd.DataFrame:
    if not dataset:
        raise SystemExit("Elhub dataset is required.")
    params: List[Tuple[str, str]] = [("dataset", dataset)]
    if start:
        params.append(("start", start))
    if end:
        params.append(("end", end))
    for key, value in filters.items():
        params.append(("filter", f"{key}:{value}"))
    resource = resource.strip("/")
    url = f"{ELHUB_BASE}/{resource}"
    response = requests.get(url, params=params, timeout=timeout, headers={"Accept": "application/json"})
    try:
        response.raise_for_status()
    except requests.HTTPError as err:
        raise SystemExit(f"Elhub request failed ({err.response.status_code}): {err.response.text[:200]}") from err
    payload = response.json()
    records: List[Dict[str, Any]] = []
    for entry in payload.get("data", []):
        attributes = entry.get("attributes", {})
        nested_field = next(
            (
                key
                for key, value in attributes.items()
                if isinstance(value, list) and value and isinstance(value[0], dict)
            ),
            None,
        )
        series = attributes.get(nested_field, []) if nested_field else []
        meta = {k: v for k, v in attributes.items() if not isinstance(v, list)}
        meta["entity_id"] = entry.get("id")
        meta["entity_type"] = entry.get("type")
        for row in series:
            record = {**meta, **row}
            records.append(record)
    return pd.DataFrame.from_records(records)


# -------------------------- CLI wiring ------------------------------ #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Norwegian power market data extraction toolkit.")
    parser.add_argument("--log-level", default="INFO", help="Logging verbosity (DEBUG, INFO, WARNING, ERROR).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ENTSO-E
    entsoe_parser = subparsers.add_parser("entsoe", help="Interact with ENTSO-E Transparency API.")
    entsoe_parser.add_argument("--token", default=os.getenv("ENTSOE_TOKEN"), help="Security token.")
    entsoe_parser.add_argument("--start", required=True, help="Start datetime (ISO8601).")
    entsoe_parser.add_argument("--end", required=True, help="End datetime (ISO8601).")
    entsoe_parser.add_argument("--document", default="A44", help="Document type code (default A44 Day-Ahead prices).")
    entsoe_parser.add_argument("--process", default="A01", help="Process type code (default A01 Day-Ahead).")
    entsoe_parser.add_argument("--in-domain", dest="in_domain", help="ENTSO-E in_Domain EIC (e.g. BZN|NO1).")
    entsoe_parser.add_argument("--out-domain", dest="out_domain", help="ENTSO-E out_Domain EIC.")
    entsoe_parser.add_argument("--extra", action="append", default=[], help="Additional key=value query params.")
    entsoe_parser.add_argument("--out", help="Output file (csv, parquet, json, ndjson). Defaults to stdout.")

    # Statnett
    statnett_parser = subparsers.add_parser("statnett", help="Download Statnett grunndata CSV archives.")
    statnett_sub = statnett_parser.add_subparsers(dest="statnett_cmd", required=True)
    statnett_list = statnett_sub.add_parser("list", help="List available download links.")
    statnett_list.add_argument("--out", help="Optional output file.")

    statnett_dl = statnett_sub.add_parser("download", help="Download a dataset by slug.")
    statnett_dl.add_argument("--dataset", required=True, help="Slug from the list output.")
    statnett_dl.add_argument("--year", help="Optional year filter.")
    statnett_dl.add_argument("--out", required=True, help="Destination path.")

    # NVE HydAPI
    nve_parser = subparsers.add_parser("nve", help="Interact with NVE HydAPI.")
    nve_parser.add_argument("--api-key", default=os.getenv("NVE_API_KEY"), help="HydAPI X-API-Key header.")
    nve_sub = nve_parser.add_subparsers(dest="nve_cmd", required=True)

    nve_stations = nve_sub.add_parser("stations", help="List hydrological stations.")
    nve_stations.add_argument("--name", help="Substring filter for station name.")
    nve_stations.add_argument("--station", dest="station", help="StationId or pattern (supports wildcards).")
    nve_stations.add_argument("--active", type=int, default=1, help="Active flag (0 or 1).")
    nve_stations.add_argument("--out", help="Optional output path.")

    nve_params = nve_sub.add_parser("parameters", help="List HydAPI parameters.")
    nve_params.add_argument("--out", help="Optional output path.")

    nve_obs = nve_sub.add_parser("observations", help="Download observation time series.")
    nve_obs.add_argument("--station", required=True, help="StationId like 6.10.0.")
    nve_obs.add_argument("--parameter", required=True, help="Parameter id or name, e.g. reservoirlevel.")
    nve_obs.add_argument("--resolution", required=True, help="Resolution (hour, day, week, inst, etc).")
    nve_obs.add_argument("--start", help="Reference time start (ISO).")
    nve_obs.add_argument("--end", help="Reference time end (ISO).")
    nve_obs.add_argument("--include-quality", action="store_true", help="Keep quality/correction columns.")
    nve_obs.add_argument(
        "--aggregation",
        default="mean",
        help="Aggregation when resampling (mean, sum, min, max, first, last, median).",
    )
    nve_obs.add_argument("--out", help="Output file.")

    # Nord Pool
    nordpool_parser = subparsers.add_parser("nordpool", help="Interact with Nord Pool Data Portal APIs.")
    nordpool_sub = nordpool_parser.add_subparsers(dest="nordpool_cmd", required=True)

    nordpool_dayahead = nordpool_sub.add_parser("dayahead", help="Fetch day-ahead price curves.")
    nordpool_dayahead.add_argument("--date", required=True, help="Delivery date (YYYY-MM-DD).")
    nordpool_dayahead.add_argument(
        "--areas",
        nargs="+",
        required=True,
        help="Delivery area codes (e.g. NO1 NO2 NO3).",
    )
    nordpool_dayahead.add_argument("--market", default="DayAhead", help="Market name (default DayAhead).")
    nordpool_dayahead.add_argument("--currency", default="EUR", help="Currency code (default EUR).")
    nordpool_dayahead.add_argument("--out", help="Output file (csv, parquet, json, ndjson). Defaults to stdout.")

    # Elhub
    elhub_parser = subparsers.add_parser("elhub", help="Download open Elhub energy-data CSV extracts.")
    elhub_parser.add_argument("--resource", required=True, help="Resource (price-areas, grid-areas, municipalities, ...).")
    elhub_parser.add_argument("--dataset", required=True, help="Dataset identifier.")
    elhub_parser.add_argument("--start", help="Optional ISO8601 startDate.")
    elhub_parser.add_argument("--end", help="Optional ISO8601 endDate.")
    elhub_parser.add_argument("--filter", dest="filters", action="append", default=[], help="Extra query filters key=value.")
    elhub_parser.add_argument("--out", required=True, help="Destination file.")

    return parser


def parse_key_value(pairs: Sequence[str]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for item in pairs:
        if "=" not in item:
            raise SystemExit(f"Expected key=value, got '{item}'")
        key, value = item.split("=", 1)
        values[key] = value
    return values


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    if args.command == "entsoe":
        start = parse_datetime(args.start, dt.time(0, 0))
        end = parse_datetime(args.end, dt.time(0, 0))
        parsed_extra = parse_key_value(args.extra)
        client = EntsoeClient(args.token)
        df = client.fetch(
            document_type=args.document,
            period_start=start,
            period_end=end,
            in_domain=args.in_domain,
            out_domain=args.out_domain,
            process_type=args.process,
            additional_params=parsed_extra,
        )
        write_dataframe(df, ensure_output_path(args.out))
        return

    if args.command == "statnett":
        client = StatnettClient()
        if args.statnett_cmd == "list":
            df = client.list_datasets()
            write_dataframe(df, ensure_output_path(args.out))
            return
        if args.statnett_cmd == "download":
            destination = ensure_output_path(args.out)
            if destination is None:
                raise SystemExit("Specify --out for Statnett downloads.")
            client.download(args.dataset, args.year, destination)
            LOG.info("Downloaded Statnett dataset to %s", destination)
            return

    if args.command == "nve":
        client = NVEHydroClient(args.api_key)
        if args.nve_cmd == "stations":
            df = client.list_stations(name=args.name, station_id=args.station, active=args.active)
            write_dataframe(df, ensure_output_path(args.out))
            return
        if args.nve_cmd == "parameters":
            df = client.list_parameters()
            write_dataframe(df, ensure_output_path(args.out))
            return
        if args.nve_cmd == "observations":
            df = client.observations(
                station_id=args.station,
                parameter=args.parameter,
                resolution=args.resolution,
                start=args.start,
                end=args.end,
                include_quality=args.include_quality,
                aggregation=args.aggregation,
            )
            write_dataframe(df, ensure_output_path(args.out))
            return

    if args.command == "nordpool":
        client = NordpoolClient()
        if args.nordpool_cmd == "dayahead":
            df = client.day_ahead_prices(
                date=args.date,
                delivery_areas=args.areas,
                market=args.market,
                currency=args.currency,
            )
            write_dataframe(df, ensure_output_path(args.out))
            return

    if args.command == "elhub":
        filters = parse_key_value(args.filters)
        destination = ensure_output_path(args.out)
        if destination is None:
            raise SystemExit("Elhub download requires --out with file path.")
        df = elhub_fetch(
            resource=args.resource,
            dataset=args.dataset,
            start=args.start,
            end=args.end,
            filters=filters,
        )
        write_dataframe(df, destination)
        LOG.info("Saved Elhub dataset to %s", destination)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
