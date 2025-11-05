"""Streamlit dashboard for analysing live (ENTSO-E/Nord Pool) production runs."""

from __future__ import annotations

import json
import os
import textwrap
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from html import escape

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from config import PLANTS, PRICE_AREA_CODES, PROCESSED_DATA_DIR, OUTPUT_DIR, PlantConfig, ensure_directories
from pipeline import DEFAULT_MAX_SAMPLES, run_pipeline
from unit_utils import derive_unit_plants

PLANT_ORDER_BY_AREA: dict[str, list[str]] = {
    "NO5": [
        "sima_g1_hydro",
        "sima_g2_hydro",
        "sima_g3_hydro",
        "sima_g4_hydro",
        "sima_combined",
        "aurland1g1_hydro",
        "aurland1g2_hydro",
        "aurland1g3_hydro",
        "aurland1_combined",
        "aurland2g1_hydro",
        "aurland2g2_hydro",
        "aurland2g3_hydro",
        "aurland2_combined",
        "aurland3g1_hydro",
        "aurland3g2_hydro",
        "aurland3_combined",
        "aurland_total",
    ],
    "NO2": [
        "kvilldalg1_hydro",
        "kvilldalg2_hydro",
        "kvilldalg3_hydro",
        "kvilldalg4_hydro",
        "kvilldal",
        "saurdal_g1_hydro",
        "saurdal_g2_hydro",
        "saurdal_g3_hydro",
        "saurdal_g4_hydro",
        "saurdal",
    ],
}


def _load_local_env() -> None:
    """Populate os.environ with entries from a project-local .env file."""
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()
ensure_directories()
SUMMARY_PATH = OUTPUT_DIR / "production_summary.json"
PIPELINE_METHODS = ["minimum", "jump"]
# SAMBA/05/11 Section 2.2 specifies |s| = 0.5 as the curvature cutoff.
PIPELINE_STRICTNESS = 0.5
# Section 2.3.1 applies a ±60 minute breakpoint neighbourhood.
PIPELINE_JUMP = 60
PIPELINE_MAX_SAMPLES = DEFAULT_MAX_SAMPLES
UMM_MESSAGES_PATH = Path(__file__).resolve().parents[3] / "UMM" / "data" / "umm_messages.csv"
DISPLAY_TIMEZONE = "Europe/Oslo"
_SECTION_HELP_KEY = "_wv_section_help_css"


def _cache_key_for_path(path: Path) -> tuple[str, int]:
    """Return a cache key combining absolute path and modification time."""
    try:
        mtime = int(path.stat().st_mtime_ns)
    except FileNotFoundError:
        mtime = -1
    return (str(path.resolve()), mtime)


def _inject_section_help_css() -> None:
    """Ensure the tooltip styles for section headers are only injected once."""
    if st.session_state.get(_SECTION_HELP_KEY):
        return
    st.markdown(
        """
        <style>
        .section-header {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            margin-top: 1.75rem;
            margin-bottom: 0.5rem;
        }
        .section-header h3 {
            margin: 0;
            font-size: 1.35rem;
        }
        .section-help {
            position: relative;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.25rem;
            height: 1.25rem;
            border-radius: 999px;
            background: rgba(120, 120, 120, 0.2);
            color: inherit;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: help;
            border: 1px solid rgba(120, 120, 120, 0.45);
        }
        .section-help:focus-visible {
            outline: 2px solid var(--primary-color);
            outline-offset: 2px;
        }
        .section-help-tooltip {
            visibility: hidden;
            opacity: 0;
            transition: opacity 0.18s ease;
            position: absolute;
            left: 50%;
            transform: translateX(-50%);
            bottom: 150%;
            background: rgba(15, 15, 15, 0.9);
            color: #f0f0f0;
            padding: 0.55rem 0.75rem;
            border-radius: 0.35rem;
            font-size: 0.75rem;
            width: 240px;
            line-height: 1.3;
            box-shadow: 0 8px 18px rgba(0, 0, 0, 0.2);
            z-index: 1000;
        }
        html[data-theme="light"] .section-help-tooltip {
            background: #ffffff;
            color: #1f1f1f;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
        }
        .section-help:hover .section-help-tooltip,
        .section-help:focus .section-help-tooltip {
            visibility: visible;
            opacity: 1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state[_SECTION_HELP_KEY] = True


def render_section_header(title: str, help_text: str) -> None:
    """Render a subheader with a contextual tooltip."""
    _inject_section_help_css()
    safe_title = escape(title)
    safe_help = escape(help_text)
    st.markdown(
        f"""
        <div class="section-header">
            <h3>{safe_title}</h3>
            <span class="section-help" tabindex="0">?
                <span class="section-help-tooltip">{safe_help}</span>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _clean_levels(levels_df: pd.DataFrame) -> pd.DataFrame:
    df = levels_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["level"] = pd.to_numeric(df.get("level"), errors="coerce")
    df["price_eur_per_mwh"] = pd.to_numeric(df.get("price_eur_per_mwh"), errors="coerce")
    df["production_mw"] = pd.to_numeric(df.get("production_mw"), errors="coerce")
    df["segment_mean_mw"] = pd.to_numeric(df.get("segment_mean_mw"), errors="coerce")
    return df.dropna(subset=["timestamp", "price_eur_per_mwh", "production_mw"]).sort_values("timestamp")


def build_segment_summary(levels_df: pd.DataFrame, breakpoints_df: pd.DataFrame) -> pd.DataFrame:
    """Summarise contiguous production segments per SAMBA/05/11 Section 2.3."""
    cleaned = _clean_levels(levels_df)
    if cleaned.empty:
        return pd.DataFrame(
            columns=[
                "segment_id",
                "start_ts",
                "end_ts",
                "mid_ts",
                "level",
                "price_min",
                "price_max",
                "price_mean",
                "entry_price",
                "exit_price",
                "production_mean",
                "duration_hours",
                "samples",
            ]
        )

    cleaned["segment_key"] = cleaned["segment_mean_mw"].round(3)
    cleaned["level_label"] = pd.to_numeric(cleaned.get("level"), errors="coerce")
    change_flags = cleaned["segment_key"].ne(cleaned["segment_key"].shift())
    if not breakpoints_df.empty and "timestamp" in breakpoints_df.columns:
        breakpoint_times = pd.to_datetime(breakpoints_df["timestamp"], utc=True, errors="coerce").dropna().unique()
        if breakpoint_times.size:
            change_flags |= cleaned["timestamp"].isin(breakpoint_times)
    cleaned["segment_id"] = change_flags.cumsum()
    if not cleaned.empty and cleaned["segment_id"].iloc[0] == 0:
        cleaned["segment_id"] += 1

    grouped = (
        cleaned.groupby("segment_id")
        .agg(
            start_ts=("timestamp", "min"),
            end_ts=("timestamp", "max"),
            level=("level_label", "first"),
            price_min=("price_eur_per_mwh", "min"),
            price_max=("price_eur_per_mwh", "max"),
            price_mean=("price_eur_per_mwh", "mean"),
            entry_price=("price_eur_per_mwh", "first"),
            exit_price=("price_eur_per_mwh", "last"),
            production_mean=("production_mw", "mean"),
            segment_mean=("segment_mean_mw", "mean"),
            samples=("timestamp", "count"),
        )
        .reset_index()
    )
    grouped["mid_ts"] = grouped["start_ts"] + (grouped["end_ts"] - grouped["start_ts"]) / 2
    grouped["duration_hours"] = (grouped["end_ts"] - grouped["start_ts"]).dt.total_seconds() / 3600
    grouped["level"] = (
        pd.to_numeric(grouped["level"], errors="coerce")
        .round()
        .astype("Int64")
    )
    grouped["segment_label"] = grouped["segment_id"].astype(int)
    return grouped


def build_transition_summary(segment_df: pd.DataFrame) -> pd.DataFrame:
    """Return price/level pairs at each production transition (Section 2.3.1)."""
    if segment_df.empty or len(segment_df) < 2:
        return pd.DataFrame(
            columns=[
                "change_ts",
                "from_level",
                "to_level",
                "price_before",
                "price_after",
                "price_trigger_estimate",
                "price_window_min",
                "price_window_max",
                "downtime_hours",
            ]
        )

    transitions = segment_df.sort_values("start_ts").copy()
    transitions["to_level"] = transitions["level"].shift(-1)
    transitions["from_segment"] = transitions["segment_id"]
    transitions["to_segment"] = transitions["segment_id"].shift(-1)
    transitions["next_start"] = transitions["start_ts"].shift(-1)
    transitions["next_price_min"] = transitions["price_min"].shift(-1)
    transitions["next_price_max"] = transitions["price_max"].shift(-1)
    transitions["next_entry_price"] = transitions["entry_price"].shift(-1)
    transitions["change_ts"] = transitions["end_ts"]
    transitions = transitions[:-1]  # drop last row (no forward transition)

    transitions["from_level"] = transitions["level"]
    transitions["price_before"] = transitions["exit_price"]
    transitions["price_after"] = transitions["next_entry_price"]
    transitions["price_trigger_estimate"] = (
        transitions[["price_before", "price_after"]].mean(axis=1)
    )
    transitions["price_window_min"] = transitions[["price_min", "next_price_min"]].min(axis=1)
    transitions["price_window_max"] = transitions[["price_max", "next_price_max"]].max(axis=1)
    transitions["downtime_hours"] = (
        (transitions["next_start"] - transitions["change_ts"]).dt.total_seconds() / 3600
    )

    keep_cols = [
        "change_ts",
        "from_segment",
        "to_segment",
        "from_level",
        "to_level",
        "price_before",
        "price_after",
        "price_trigger_estimate",
        "price_window_min",
        "price_window_max",
        "downtime_hours",
    ]
    return transitions.loc[:, keep_cols].dropna(subset=["price_before", "price_after"])


@st.cache_data(show_spinner=False)
def load_umm_messages() -> pd.DataFrame:
    """Load cached UMM market messages."""
    if not UMM_MESSAGES_PATH.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(UMM_MESSAGES_PATH)
    except Exception:
        return pd.DataFrame()
    return df.fillna("")


def _normalise_json_blob(raw: str | float | int | None) -> list[dict]:
    if raw in ("", None) or pd.isna(raw):
        return []
    if not isinstance(raw, str):
        return []
    normalised = raw.strip()
    if not normalised:
        return []
    if normalised.startswith('"') and normalised.endswith('"'):
        normalised = normalised[1:-1]
    normalised = normalised.replace('""', '"')
    try:
        result = json.loads(normalised)
    except json.JSONDecodeError:
        return []
    if isinstance(result, list):
        return [entry for entry in result if isinstance(entry, dict)]
    if isinstance(result, dict):
        return [result]
    return []


def _extract_area_codes(message: dict) -> set[str]:
    codes: set[str] = set()
    for entry in _normalise_json_blob(message.get("areas_json")):
        for key in ("code", "areaEic"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                codes.add(value.upper())
        name = entry.get("name")
        if isinstance(name, str) and name:
            codes.add(name.upper())
    return codes


def _extract_unit_codes(message: dict) -> set[str]:
    codes: set[str] = set()
    for column in (
        "assets_json",
        "generation_units_json",
        "production_units_json",
        "consumption_units_json",
        "transmission_units_json",
        "other_market_units_json",
    ):
        for entry in _normalise_json_blob(message.get(column)):
            for key in ("eic", "productionUnitEic", "assetEic", "consumptionUnitEic"):
                value = entry.get(key)
                if isinstance(value, str) and value:
                    codes.add(value.upper())
    return codes


def filter_umm_events(
    plant,
    area_code: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    limit: int = 6,
) -> pd.DataFrame:
    """Return relevant UMM events for the plant/area within the selected window."""
    df = load_umm_messages()
    if df.empty:
        return df

    area_norm = area_code.upper()
    resource_codes = {code.upper() for code in getattr(plant, "registered_resources", [])}
    relevant_rows: list[dict] = []

    for _, row in df.iterrows():
        payload = row.to_dict()
        areas = _extract_area_codes(payload)
        units = _extract_unit_codes(payload)
        matches_area = not areas or area_norm in areas
        matches_unit = bool(resource_codes & units) if resource_codes else False
        if not matches_area and not matches_unit:
            continue

        pub_ts = pd.to_datetime(payload.get("publication_date"), utc=True, errors="coerce")
        start_event = pd.to_datetime(payload.get("event_start"), utc=True, errors="coerce")
        stop_event = pd.to_datetime(payload.get("event_stop"), utc=True, errors="coerce")
        window_start = start_event if pd.notna(start_event) else pub_ts
        window_end = stop_event if pd.notna(stop_event) else start_event
        if pd.isna(window_start):
            window_start = pub_ts
        if pd.isna(window_end):
            window_end = window_start

        if pd.isna(window_start):
            continue
        if window_end < start_ts or window_start > end_ts:
            continue

        headline_candidates = (
            payload.get("unavailability_reason"),
            payload.get("remarks"),
            payload.get("reason_code"),
        )
        headline = next((h for h in headline_candidates if isinstance(h, str) and h.strip()), "Operational update")

        description_parts: list[str] = []
        for key in ("remarks", "cancellation_reason"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                description_parts.append(value.strip())
        unavailability_type = payload.get("unavailability_type")
        if isinstance(unavailability_type, str) and unavailability_type.strip():
            description_parts.append(f"Unavailability type: {unavailability_type.strip()}")

        relevant_rows.append(
            {
                "publication_date": pub_ts,
                "event_start": start_event,
                "event_stop": stop_event,
                "headline": headline.strip(),
                "description": " ".join(description_parts).strip(),
                "publisher": payload.get("publisher_name", ""),
                "areas": ", ".join(sorted(areas)) if areas else "",
                "unit_codes": ", ".join(sorted(units)) if units else "",
                "raw_message_id": payload.get("message_id"),
                "window_start": window_start,
                "window_end": window_end,
            }
        )

    if not relevant_rows:
        return pd.DataFrame()

    result = pd.DataFrame(relevant_rows).sort_values("window_start")
    if limit and len(result) > limit:
        result = result.head(limit)
    return result.reset_index(drop=True)


def _build_events_prompt(
    plant_name: str,
    area_code: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    events: pd.DataFrame,
) -> str:
    records = []
    for _, row in events.iterrows():
        pub_iso = row["publication_date"].isoformat() if pd.notna(row["publication_date"]) else "unknown publication time"
        start_iso = row["event_start"].isoformat() if pd.notna(row["event_start"]) else "unknown start"
        stop_iso = row["event_stop"].isoformat() if pd.notna(row["event_stop"]) else "unknown stop"
        description = row["description"] if row["description"] else "No detailed remarks provided."
        records.append(
            f"- Headline: {row['headline']}\n"
            f"  Publisher: {row['publisher'] or 'unknown'}\n"
            f"  Publication: {pub_iso}\n"
            f"  Window: {start_iso} to {stop_iso}\n"
            f"  Notes: {description}"
        )

    events_block = "\n".join(records)
    prompt = textwrap.dedent(
        f"""
        You are an analyst explaining operational events for a Norwegian hydro power plant.
        Plant: {plant_name} (price area {area_code}).
        Analysis window: {start_ts.isoformat()} to {end_ts.isoformat()} (UTC).

        UMM event excerpts:
        {events_block}

        Summarise in at most four bullet points how these events could relate to major price or production changes.
        Highlight timing overlaps with potential spikes or dips, distinguish confirmed impacts from speculation, and note gaps in information.
        Keep the tone factual and concise.
        """
    ).strip()
    return prompt


@st.cache_data(show_spinner=False)
def _generate_llm_summary(prompt: str) -> str | None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
    except ImportError:
        return None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-flash-latest")
        response = model.generate_content(prompt)
        if hasattr(response, "text") and response.text:
            return response.text
        if getattr(response, "candidates", None):
            part = response.candidates[0].content.parts[0]  # type: ignore[attr-defined]
            return getattr(part, "text", None)
    except Exception:  # pragma: no cover - guard against API/runtime errors
        return None
    return None

@st.cache_data(show_spinner=False, hash_funcs={Path: _cache_key_for_path})
def load_csv(path: Path, timestamp_col: str | None = None) -> pd.DataFrame:
    """Load a cached CSV, optionally parsing a timestamp column to UTC."""
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    if timestamp_col and timestamp_col in df.columns:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col], utc=True)
    return df


@st.cache_data(show_spinner=False)
def load_summary(summary_mtime: int | None) -> pd.DataFrame:
    """Read the pipeline summary JSON for quick filtering in the UI."""
    if not SUMMARY_PATH.exists():
        return pd.DataFrame()
    payload = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    return pd.DataFrame(payload)


def add_local_time(df: pd.DataFrame, column: str = "timestamp") -> pd.DataFrame:
    """Return a copy of the dataframe with an extra *_local column converted to DISPLAY_TIMEZONE."""
    if df.empty or column not in df.columns:
        return df.copy()
    result = df.copy()
    if not pd.api.types.is_datetime64tz_dtype(result[column]):
        result[column] = pd.to_datetime(result[column], utc=True, errors="coerce")
    result[f"{column}_local"] = result[column].dt.tz_convert(DISPLAY_TIMEZONE)
    return result


def to_local_timestamp(ts: pd.Timestamp | None) -> pd.Timestamp | None:
    """Convert a pandas timestamp (UTC or naive) to DISPLAY_TIMEZONE."""
    if ts is None or pd.isna(ts):
        return None
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(DISPLAY_TIMEZONE)


def _methods_from_output(plant_id: str) -> list[str]:
    """Return available estimation methods for a plant based on output CSVs."""
    output_dir = OUTPUT_DIR / plant_id
    if not output_dir.exists():
        return []
    methods: set[str] = set()
    prefix = f"{plant_id}_"
    suffix = "_levels"
    for path in output_dir.glob(f"{plant_id}_*_levels.csv"):
        stem = path.stem
        if not stem.startswith(prefix) or not stem.endswith(suffix):
            continue
        method = stem[len(prefix) : -len(suffix)]
        if method:
            methods.add(method)
    return sorted(methods)


def resolve_methods_for_plant(plant_id: str, summary_df: pd.DataFrame, allow_raw: bool = False) -> list[str]:
    """Combine methods recorded in the summary with those inferred from output files."""
    summary_methods: list[str] = []
    if not summary_df.empty and {"plant_id", "method"}.issubset(summary_df.columns):
        summary_methods = (
            summary_df.loc[summary_df["plant_id"] == plant_id, "method"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
    methods = list(summary_methods)
    for method in _methods_from_output(plant_id):
        if method not in methods:
            methods.append(method)
    if allow_raw and "raw" not in methods:
        methods.append("raw")
    return methods


def build_production_series(
    production_df: pd.DataFrame,
    price_df: pd.DataFrame,
    segments_df: pd.DataFrame,
) -> pd.DataFrame:
    """Return production data aligned with price and segment information."""
    if production_df.empty:
        return production_df.copy()

    series = production_df.copy()
    series["timestamp"] = pd.to_datetime(series["timestamp"], utc=True, errors="coerce")
    series = series.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    series["production_mw"] = pd.to_numeric(series["production_mw"], errors="coerce")
    series = add_local_time(series, "timestamp")

    if not price_df.empty and {"timestamp", "price_eur_per_mwh"}.issubset(price_df.columns):
        price_data = price_df[["timestamp", "price_eur_per_mwh"]].copy()
        price_data["timestamp"] = pd.to_datetime(price_data["timestamp"], utc=True, errors="coerce")
        price_data = price_data.dropna(subset=["timestamp"]).sort_values("timestamp")
        series = pd.merge_asof(
            series,
            price_data,
            on="timestamp",
            direction="backward",
            tolerance=pd.Timedelta(hours=1),
        )
        series["price_eur_per_mwh"] = pd.to_numeric(series["price_eur_per_mwh"], errors="coerce")
        series["price_eur_per_mwh"] = series["price_eur_per_mwh"].ffill().bfill()
    else:
        series["price_eur_per_mwh"] = np.nan

    if not segments_df.empty:
        segments = segments_df.copy()
        segments["timestamp"] = pd.to_datetime(segments["timestamp"], utc=True, errors="coerce")
        segments = segments.dropna(subset=["timestamp"]).sort_values("timestamp")
        segments = add_local_time(segments, "timestamp")
        segments = segments.drop(columns=["timestamp_local"], errors="ignore")
        segments = segments.drop(columns=["production_mw"], errors="ignore")
        tolerance = pd.Timedelta(hours=12)
        if len(segments) > 1:
            diffs = segments["timestamp"].diff().dropna()
            if not diffs.empty:
                tolerance = diffs.median()
        series = pd.merge_asof(
            series,
            segments,
            on="timestamp",
            direction="backward",
            tolerance=tolerance,
        )
        for column in ("segment_mean_mw", "level"):
            if column in series.columns:
                series[column] = series[column].ffill().bfill()
    else:
        series["segment_mean_mw"] = np.nan
        series["level"] = np.nan

    return series.reset_index(drop=True)


def filter_by_range(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Return subset of dataframe rows between two UTC timestamps."""
    mask = (df["timestamp"] >= start) & (df["timestamp"] < end)
    return df.loc[mask].copy()


def _price_scale(df: pd.DataFrame | None) -> alt.Scale:
    """Return a stable Altair scale based on the dataframe's price range."""
    if df is None or df.empty or "price_eur_per_mwh" not in df.columns:
        return alt.Scale(zero=False)

    series = pd.to_numeric(df["price_eur_per_mwh"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return alt.Scale(zero=False)

    min_val = float(series.min())
    max_val = float(series.max())
    if not np.isfinite(min_val) or not np.isfinite(max_val):
        return alt.Scale(zero=False)

    if np.isclose(min_val, max_val):
        pad = max(1.0, abs(min_val) * 0.1)
        domain = [min_val - pad, max_val + pad]
    else:
        pad = 0.05 * (max_val - min_val)
        domain = [min_val - pad, max_val + pad]

    return alt.Scale(domain=domain, nice=False)


def render_charts(
    price_df: pd.DataFrame,
    price_intraday_df: pd.DataFrame | None,
    production_series_df: pd.DataFrame,
    breakpoints_df: pd.DataFrame,
    price_quarter_df: pd.DataFrame | None = None,
) -> None:
    """Render price, intraday, and production segment charts (cf. SAMBA/05/11 Figures 1–2)."""
    def _time_encoding(df: pd.DataFrame) -> str:
        return "timestamp_local:T" if "timestamp_local" in df.columns else "timestamp:T"

    price_scale = _price_scale(price_df)
    price_chart = (
        alt.Chart(price_df)
        .mark_line(color="#1f77b4")
        .encode(
            x=_time_encoding(price_df),
            y=alt.Y(
                "price_eur_per_mwh:Q",
                title="Day-ahead price (EUR/MWh)",
                scale=price_scale,
            ),
        )
        .properties(height=200)
    )

    production_line = (
        alt.Chart(production_series_df)
        .mark_line(color="#ff7f0e")
        .encode(x=_time_encoding(production_series_df), y=alt.Y("production_mw:Q", title="Production (MW)"))
    )

    has_segment_mean = (
        "segment_mean_mw" in production_series_df.columns and production_series_df["segment_mean_mw"].notna().any()
    )
    if has_segment_mean:
        # Highlight the piecewise constant production means from Section 2.1.
        segment_line = (
            alt.Chart(production_series_df)
            .mark_line(color="#2ca02c", strokeDash=[4, 4])
            .encode(x=_time_encoding(production_series_df), y="segment_mean_mw:Q")
        )
    else:
        segment_line = None

    has_breakpoints = not breakpoints_df.empty
    if has_breakpoints:
        # Valid breakpoint candidates from Section 2.3.1 are shown as red rules.
        breakpoint_rules = (
            alt.Chart(breakpoints_df)
            .mark_rule(color="#d62728", strokeWidth=1)
            .encode(x=_time_encoding(breakpoints_df))
        )
    else:
        breakpoint_rules = None

    st.altair_chart(price_chart, use_container_width=True)

    if price_intraday_df is not None and not price_intraday_df.empty:
        intraday_scale = _price_scale(price_intraday_df)
        intraday_chart = (
            alt.Chart(price_intraday_df)
            .mark_line(color="#17becf")
            .encode(
                x=_time_encoding(price_intraday_df),
                y=alt.Y(
                    "price_eur_per_mwh:Q",
                    title="Intraday auction price (EUR/MWh)",
                    scale=intraday_scale,
                ),
                tooltip=[
                    alt.Tooltip("timestamp:T", title="Timestamp"),
                    alt.Tooltip("price_eur_per_mwh:Q", title="Price"),
                ],
            )
            .properties(height=180)
        )
        st.altair_chart(intraday_chart, use_container_width=True)

    if price_quarter_df is not None and not price_quarter_df.empty:
        quarter_scale = _price_scale(price_quarter_df)
        quarter_chart = (
            alt.Chart(price_quarter_df)
            .mark_line(color="#9467bd")
            .encode(
                x=_time_encoding(price_quarter_df),
                y=alt.Y(
                    "price_eur_per_mwh:Q",
                    title="Quarter-hour price (EUR/MWh)",
                    scale=quarter_scale,
                ),
            )
            .properties(height=150)
        )
        st.altair_chart(quarter_chart, use_container_width=True)
    combined_chart = production_line
    if segment_line is not None:
        combined_chart += segment_line
    if breakpoint_rules is not None:
        combined_chart += breakpoint_rules
    st.altair_chart(combined_chart, use_container_width=True)


def build_water_value_curve(
    levels_df: pd.DataFrame,
    water_values_df: pd.DataFrame,
    history_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Return water value history per interval (SAMBA/05/11 Sections 2.3.3–2.3.4).

    The function favours the incremental history produced by the pipeline. When
    that history is unavailable we anchor the static water value output to the
    first observed occurrence of each production interval. Only intervals that
    appear in the segmented production series are retained so the chart mirrors
    the SAMBA/05/11 presentation (one trace per active interval).
    """

    def _coerce_bounds(frame: pd.DataFrame) -> pd.DataFrame:
        """Normalise lower/upper/value columns to floats."""
        df = frame.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df["interval"] = pd.to_numeric(df["interval"], errors="coerce").astype("Int64")
        if {"lower", "upper"}.issubset(df.columns):
            df["lower"] = pd.to_numeric(df["lower"], errors="coerce")
            df["upper"] = pd.to_numeric(df["upper"], errors="coerce")
            both_na = df["lower"].isna() & df["upper"].isna()
            df = df.loc[~both_na, ["timestamp", "interval", "lower", "upper"]]
        elif "value" in df.columns:
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.loc[~df["value"].isna(), ["timestamp", "interval", "value"]]
            df = df.assign(lower=df["value"], upper=df["value"]).drop(columns=["value"])
        else:
            return pd.DataFrame(columns=["timestamp", "interval", "lower", "upper"])
        return df.dropna(subset=["timestamp", "interval"]).astype(
            {"interval": int}
        )

    def _from_static(static_df: pd.DataFrame) -> pd.DataFrame:
        """Map static water values onto the first appearance of each interval."""
        if static_df.empty:
            return pd.DataFrame(columns=["timestamp", "interval", "lower", "upper"])
        df = static_df.copy()
        if {"lower", "upper"}.issubset(df.columns):
            df["lower"] = pd.to_numeric(df["lower"], errors="coerce")
            df["upper"] = pd.to_numeric(df["upper"], errors="coerce")
        elif "value" in df.columns:
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.assign(lower=df["value"], upper=df["value"]).drop(columns=["value"])
        else:
            return pd.DataFrame(columns=["timestamp", "interval", "lower", "upper"])

        levels = levels_df.copy()
        levels["timestamp"] = pd.to_datetime(levels["timestamp"], utc=True, errors="coerce")
        first_timestamp_map = (
            levels.dropna(subset=["timestamp", "level"])
            .drop_duplicates(subset=["level"], keep="first")
            .set_index("level")["timestamp"]
            .to_dict()
        )
        last_timestamp_map = (
            levels.dropna(subset=["timestamp", "level"])
            .drop_duplicates(subset=["level"], keep="last")
            .set_index("level")["timestamp"]
            .to_dict()
        )
        records: list[dict] = []
        for _, row in static_df.iterrows():
            interval = int(row["interval"])
            start_ts = first_timestamp_map.get(interval)
            end_ts = last_timestamp_map.get(interval)
            for ts in {start_ts, end_ts}:
                if ts is None or pd.isna(ts):
                    continue
                # Section 2.3.4: anchor interval estimates to the first/last appearance that day.
                records.append(
                    {
                        "timestamp": ts,
                        "interval": interval,
                        "lower": row.get("lower"),
                        "upper": row.get("upper"),
                    }
                )
        if not records:
            return pd.DataFrame(columns=["timestamp", "interval", "lower", "upper"])
        df = pd.DataFrame.from_records(records)
        df["lower"] = pd.to_numeric(df.get("lower"), errors="coerce")
        df["upper"] = pd.to_numeric(df.get("upper"), errors="coerce")
        mask = df["upper"].isna() & ~df["lower"].isna()
        df.loc[mask, "upper"] = df.loc[mask, "lower"]
        df.loc[mask, "lower"] = df.loc[mask, "upper"]
        df = df.dropna(subset=["upper"])
        return df

    if history_df is not None and not history_df.empty:
        curve = _coerce_bounds(history_df)
    else:
        curve = _from_static(water_values_df)

    if curve.empty:
        return curve

    active_levels = (
        pd.to_numeric(levels_df.get("level"), errors="coerce")
        .dropna()
        .astype(int)
        .unique()
    )
    if active_levels.size:
        curve = curve[curve["interval"].isin({int(level) for level in active_levels if level > 0})]

    if curve.empty:
        return curve

    curve = curve.sort_values(["timestamp", "interval"]).reset_index(drop=True)
    mask = curve["upper"].isna() & ~curve["lower"].isna()
    curve.loc[mask, "upper"] = curve.loc[mask, "lower"]
    mask = curve["lower"].isna() & ~curve["upper"].isna()
    curve.loc[mask, "lower"] = curve.loc[mask, "upper"]
    return curve.dropna(subset=["upper"])


def main() -> None:
    """Entry point for `streamlit run`."""
    st.set_page_config(page_title="Water Value Production Sandbox", layout="wide")
    st.title("Water Value Production Sandbox")

    all_areas = sorted(PRICE_AREA_CODES.keys())
    default_area_index = all_areas.index("NO2") if "NO2" in all_areas else 0
    selected_area = st.sidebar.selectbox("Price area", all_areas, index=default_area_index)

    today = pd.Timestamp.utcnow().floor("D").date()
    default_start = (pd.Timestamp.utcnow().floor("D") - pd.Timedelta(days=30)).date()

    strictness_value = st.sidebar.slider(
        "Segmentation strictness",
        min_value=0.05,
        max_value=1.0,
        value=PIPELINE_STRICTNESS,
        step=0.05,
        help=(
            "Controls how aggressively production is grouped into segments. "
            "Lower values keep more breakpoints (higher sensitivity); higher values merge segments."
        ),
    )
    jump_window = st.sidebar.slider(
        "Jump window (minutes)",
        min_value=15,
        max_value=180,
        value=PIPELINE_JUMP,
        step=5,
        help=(
            "Time span around each price jump used by the jump estimator. "
            "Smaller windows focus on local spikes; larger windows smooth the response."
        ),
    )

    disable_resampling = st.sidebar.checkbox(
        "Disable automatic resampling",
        value=False,
        help=(
            "When checked, the full-resolution time series is used regardless of length. "
            "Uncheck to allow automatic downsampling when the merged price/production series exceeds the threshold."
        ),
    )
    if disable_resampling:
        max_samples_threshold = None
    else:
        max_samples_threshold = st.sidebar.slider(
            "Max observations before resample",
            min_value=500,
            max_value=60000,
            value=PIPELINE_MAX_SAMPLES,
            step=500,
            help=(
                "If the aligned price/production series has more points than this threshold, "
                "it will be downsampled to increasingly coarse intervals until it fits."
            ),
        )

    fetch_range = st.sidebar.date_input(
        "Fetch date range",
        (default_start, today),
        min_value=datetime(2010, 1, 1).date(),
        max_value=today,
    )

    st.sidebar.markdown(
        '<span style="color:#c00000;font-weight:bold;font-size:0.95rem;">WARNING: RE-DOWNLOADING VIA THE WEB SCRAPER CAN TAKE 2+ HOURS.</span>',  # noqa: E501
        unsafe_allow_html=True,
    )
    refresh_from_web = st.sidebar.checkbox(
        "Re-download production data (web scraper)",
        value=False,
        help=(
            "Enable to fetch a fresh price/production dataset from the ENTSO-E transparency website. "
            "Leave unchecked to reuse cached CSVs and only rerun the algorithm."
        ),
    )

    if st.sidebar.button("Run analysis"):
        if isinstance(fetch_range, tuple) and len(fetch_range) == 2:
            start_date, end_date = fetch_range
        else:
            start_date = end_date = fetch_range
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)
        progress_bar = st.sidebar.progress(0, text="Preparing fetch…")
        with st.spinner("Running analysis…"):
            try:
                def progress_callback(message: str, fraction: float) -> None:
                    progress_bar.progress(int(min(1.0, max(0.0, fraction)) * 100), text=message)
                run_pipeline(
                    start=start_dt,
                    end=end_dt,
                    area=selected_area,
                    methods=PIPELINE_METHODS,
                    strictness=strictness_value,
                    jumpm=jump_window,
                    summary_path=SUMMARY_PATH,
                    progress_cb=progress_callback,
                    max_samples=max_samples_threshold,
                    refresh_data=refresh_from_web,
                    production_source="web",
                )
            except Exception as exc:  # pragma: no cover - surfaced in UI
                st.error(f"Data fetch failed: {exc}")
            else:
                load_summary.clear()
                load_csv.clear()
                st.success("Data updated successfully.")
                st.rerun()
            finally:
                progress_bar.empty()

    summary_mtime = int(SUMMARY_PATH.stat().st_mtime_ns) if SUMMARY_PATH.exists() else None
    summary_df = load_summary(summary_mtime)
    if summary_df.empty:
        st.info("No pipeline summary found; using processed datasets for visualisation.")
    elif "area" in summary_df.columns:
        area_series = summary_df["area"].astype(str).str.upper()
        summary_df = summary_df[area_series == selected_area]

    base_plants_in_area = [
        plant
        for plant in PLANTS
        if plant.price_area.upper() == selected_area
        and (PROCESSED_DATA_DIR / f"{plant.id}_production.csv").exists()
    ]
    if not base_plants_in_area:
        st.warning(f"No processed production files found for area {selected_area}.")
        st.stop()
    unit_plants = derive_unit_plants(base_plants_in_area, summary_df=summary_df)
    plants_by_id = {plant.id: plant for plant in base_plants_in_area}
    for extra in unit_plants:
        plants_by_id.setdefault(extra.id, extra)
    ordered_ids = PLANT_ORDER_BY_AREA.get(selected_area, [])
    order_lookup = {plant_id: idx for idx, plant_id in enumerate(ordered_ids)}

    def _sort_key(cfg: PlantConfig) -> tuple[int, str]:
        return (order_lookup.get(cfg.id, len(ordered_ids)), cfg.name.lower())

    plants_in_area = sorted(plants_by_id.values(), key=_sort_key)

    plant_options = {plant.name: plant for plant in plants_in_area}
    plant_name = st.sidebar.selectbox("Plant", list(plant_options))
    plant = plant_options[plant_name]

    allow_raw = not (OUTPUT_DIR / plant.id).exists()
    methods = resolve_methods_for_plant(plant.id, summary_df, allow_raw=allow_raw)
    if not methods:
        st.warning(f"No datasets available for {plant.name}.")
        st.stop()
    method = st.sidebar.selectbox("Estimation method", methods)
    is_raw_method = method == "raw"

    price_path = PROCESSED_DATA_DIR / f"price_{selected_area}.csv"
    try:
        price_df = load_csv(price_path, "timestamp").copy()
    except FileNotFoundError:
        st.error(f"Expected price dataset not found at {price_path}.")
        st.stop()
    price_df = add_local_time(price_df)
    price_intraday_path = PROCESSED_DATA_DIR / f"price_{selected_area}_intraday.csv"
    try:
        price_intraday_df = load_csv(price_intraday_path, "timestamp").copy()
    except FileNotFoundError:
        price_intraday_df = pd.DataFrame(columns=["timestamp", "price_eur_per_mwh"]).astype(
            {"price_eur_per_mwh": "float64"}
        )
    else:
        price_intraday_df = add_local_time(price_intraday_df)

    price_quarter_path = PROCESSED_DATA_DIR / f"price_{selected_area}_15min.csv"
    try:
        price_quarter_df = load_csv(price_quarter_path, "timestamp").copy()
    except FileNotFoundError:
        price_quarter_df = pd.DataFrame(columns=["timestamp", "price_eur_per_mwh"]).astype(
            {"price_eur_per_mwh": "float64"}
        )
    else:
        price_quarter_df = add_local_time(price_quarter_df)
    try:
        production_df = load_csv(PROCESSED_DATA_DIR / f"{plant.id}_production.csv", "timestamp").copy()
    except FileNotFoundError:
        st.error(f"Processed production dataset missing for {plant.name}.")
        st.stop()
    levels_path = OUTPUT_DIR / plant.id / f"{plant.id}_{method}_levels.csv"
    water_values_path = OUTPUT_DIR / plant.id / f"{plant.id}_{method}_water_values.csv"
    breakpoints_path = OUTPUT_DIR / plant.id / f"{plant.id}_{method}_breakpoints.csv"
    history_path = OUTPUT_DIR / plant.id / f"{plant.id}_{method}_water_history.csv"

    if is_raw_method:
        segments_df = pd.DataFrame(columns=["timestamp", "segment_mean_mw", "level"])
        water_values_df = pd.DataFrame()
        breakpoints_df = pd.DataFrame(columns=["timestamp", "breakpoint_code"])
        history_df = pd.DataFrame()
    else:
        try:
            segments_df = load_csv(levels_path, "timestamp").copy()
        except FileNotFoundError:
            st.error(f"Segmented production file not found at {levels_path}.")
            st.stop()
        try:
            water_values_df = load_csv(water_values_path).copy()
        except FileNotFoundError:
            water_values_df = pd.DataFrame()
        try:
            breakpoints_df = load_csv(breakpoints_path, "timestamp").copy()
            breakpoints_df = breakpoints_df[breakpoints_df["breakpoint_code"] == 2]
        except FileNotFoundError:
            breakpoints_df = pd.DataFrame(columns=["timestamp", "breakpoint_code"])
        try:
            history_df = load_csv(history_path, "timestamp").copy()
        except FileNotFoundError:
            history_df = pd.DataFrame()

    breakpoints_df = add_local_time(breakpoints_df)

    production_series_df = build_production_series(production_df, price_df, segments_df)
    if production_series_df.empty:
        st.warning(f"No production rows available for {plant.name}.")
        st.stop()

    min_ts = production_series_df["timestamp"].min()
    max_ts = production_series_df["timestamp"].max()
    if pd.isna(min_ts) or pd.isna(max_ts):
        st.warning(f"Timestamp coverage unavailable for {plant.name}.")
        st.stop()
    min_ts_local = to_local_timestamp(min_ts)
    max_ts_local = to_local_timestamp(max_ts)
    if min_ts_local is None or max_ts_local is None:
        st.warning(f"Could not determine display range for {plant.name}.")
        st.stop()
    min_ts_local_naive = min_ts_local.tz_localize(None)
    max_ts_local_naive = max_ts_local.tz_localize(None)
    min_display_date = min_ts_local_naive.date()
    max_display_date = max_ts_local_naive.date()
    if min_display_date > max_display_date:
        min_display_date = max_display_date
    default_range = (min_display_date, max_display_date)
    date_input_key = f"date_range_{plant.id}"
    bounds_state_key = f"{date_input_key}_bounds"
    stored_bounds = st.session_state.get(bounds_state_key)
    stored_bounds_tuple = tuple(stored_bounds) if isinstance(stored_bounds, (list, tuple)) else None
    # Expand the widget's default window whenever the cached dataset grows.
    if stored_bounds_tuple != default_range:
        st.session_state[bounds_state_key] = default_range
        st.session_state[date_input_key] = default_range

    st.sidebar.caption(
        f"Data coverage (local time): {default_range[0].isoformat()} → {default_range[1].isoformat()}"
    )

    selected_default = st.session_state.get(date_input_key, default_range)
    if isinstance(selected_default, list):
        selected_default = tuple(selected_default)
    selected_range = st.sidebar.date_input(
        "Date range",
        value=selected_default,
        min_value=min_display_date,
        max_value=max_display_date,
        key=date_input_key,
    )
    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        start_date, end_date = selected_range
    else:
        start_date = selected_range
        end_date = selected_range

    start_date = max(start_date, default_range[0])
    end_date = min(end_date, default_range[1])
    if start_date > end_date:
        start_date = end_date = default_range[0]

    normalized_range: tuple | date
    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        normalized_range = (start_date, end_date)
    else:
        normalized_range = start_date
    if normalized_range != selected_range:
        st.session_state[date_input_key] = normalized_range

    start_ts_local = pd.Timestamp(start_date).tz_localize(DISPLAY_TIMEZONE)
    end_ts_local = pd.Timestamp(end_date).tz_localize(DISPLAY_TIMEZONE) + pd.Timedelta(days=1)
    start_ts = start_ts_local.tz_convert("UTC")
    end_ts = end_ts_local.tz_convert("UTC")

    price_filtered = filter_by_range(price_df, start_ts, end_ts)
    price_intraday_filtered = (
        filter_by_range(price_intraday_df, start_ts, end_ts) if not price_intraday_df.empty else price_intraday_df
    )
    production_filtered = filter_by_range(production_series_df, start_ts, end_ts)
    breakpoints_filtered = filter_by_range(breakpoints_df, start_ts, end_ts)

    render_section_header(
        f"{plant.name} – {method.title()} method",
        "Aligned price and production series together with segmentation outputs for the chosen plant and estimation method (SAMBA/05/11 Sections 2.1–2.3).",
    )
    price_quarter_filtered = filter_by_range(price_quarter_df, start_ts, end_ts) if not price_quarter_df.empty else price_quarter_df

    render_charts(price_filtered, price_intraday_filtered, production_filtered, breakpoints_filtered, price_quarter_filtered)

    segment_summary = pd.DataFrame()
    if not is_raw_method and not segments_df.empty:
        segment_summary = build_segment_summary(production_filtered, breakpoints_filtered)
        if not segment_summary.empty:
            for column in ("start_ts", "end_ts", "mid_ts"):
                if column in segment_summary.columns:
                    segment_summary[f"{column}_local"] = segment_summary[column].dt.tz_convert(DISPLAY_TIMEZONE)
            legend_config = alt.Legend(orient="top", direction="horizontal")
            segment_chart = (
                alt.Chart(segment_summary)
                .mark_rect(opacity=0.25)
                .encode(
                    x=alt.X("start_ts_local:T", title="Date"),
                    x2="end_ts_local:T",
                    y=alt.Y("price_min:Q", title="Price (EUR/MWh)"),
                    y2="price_max:Q",
                    color=alt.Color("segment_label:N", title="Segment", legend=legend_config),
                    tooltip=[
                        alt.Tooltip("start_ts_local:T", title="Segment start"),
                        alt.Tooltip("end_ts_local:T", title="Segment end"),
                        alt.Tooltip("segment_label:N", title="Segment"),
                        alt.Tooltip("level:N", title="Production interval"),
                        alt.Tooltip("price_min:Q", title="Min price"),
                        alt.Tooltip("price_max:Q", title="Max price"),
                        alt.Tooltip("price_mean:Q", title="Mean price"),
                        alt.Tooltip("production_mean:Q", title="Average production (MW)"),
                        alt.Tooltip("duration_hours:Q", title="Duration (h)"),
                    ],
                )
            )
            segment_means = (
                alt.Chart(segment_summary)
                .mark_line(size=2)
                .encode(
                    x=alt.X("mid_ts_local:T", title="Date"),
                    y=alt.Y("price_mean:Q", title="Price (EUR/MWh)"),
                    color=alt.Color("segment_label:N", title="Segment", legend=None),
                )
            )
            render_section_header(
                "Production price envelopes",
                "Shows the price range observed while each segmented production block was active; see SAMBA/05/11 Section 2.3.1 for the breakpoint rationale.",
            )
            st.altair_chart(segment_chart + segment_means, use_container_width=True)

            segment_table = segment_summary.copy()
            for column in ("start_ts", "end_ts", "mid_ts"):
                local_column = f"{column}_local"
                if local_column in segment_table.columns:
                    segment_table[local_column] = segment_table[local_column].dt.strftime("%Y-%m-%d %H:%M")
            segment_table["price_min"] = segment_table["price_min"].round(3)
            segment_table["price_max"] = segment_table["price_max"].round(3)
            segment_table["price_mean"] = segment_table["price_mean"].round(3)
            segment_table["production_mean"] = segment_table["production_mean"].round(3)
            segment_table["segment_mean"] = segment_table["segment_mean"].round(3)
            segment_table["duration_hours"] = segment_table["duration_hours"].round(2)

            st.caption("Price ranges by production segment (SAMBA/05/11 Section 2.3.1).")
            st.dataframe(
                segment_table[
                    [
                        "segment_label",
                        "level",
                        "segment_mean",
                        "start_ts_local",
                        "end_ts_local",
                        "price_min",
                        "price_max",
                        "price_mean",
                        "production_mean",
                        "duration_hours",
                        "samples",
                    ]
                ].rename(
                    columns={
                        "segment_label": "segment",
                        "level": "interval",
                        "segment_mean": "segment_mean_mw",
                        "start_ts_local": "start_local",
                        "end_ts_local": "end_local",
                    }
                ),
                hide_index=True,
            )
        else:
            st.info("No constant production segments found in the selected window.")
    elif is_raw_method:
        st.info("Segmentation requires a water-value run. Displaying raw production only.")
    else:
        st.info("Segmentation data unavailable for this plant.")

    transition_summary = build_transition_summary(segment_summary) if not segment_summary.empty else pd.DataFrame()
    if not transition_summary.empty:
        if "change_ts" in transition_summary.columns:
            transition_summary["change_ts_local"] = transition_summary["change_ts"].dt.tz_convert(DISPLAY_TIMEZONE)
        render_section_header(
            "Production transitions",
            "Breakpoints validated by the estimator with estimated trigger prices and price windows (SAMBA/05/11 Section 2.3.1).",
        )
        transition_legend = alt.Legend(orient="top", direction="horizontal", title="To segment")
        transition_rules = (
            alt.Chart(transition_summary)
            .mark_rule()
            .encode(
                x=alt.X("change_ts_local:T", title="Timestamp"),
                y=alt.Y("price_window_min:Q", title="Price (EUR/MWh)"),
                y2="price_window_max:Q",
                color=alt.Color("to_segment:N", legend=transition_legend),
                tooltip=[
                    alt.Tooltip("change_ts_local:T", title="Timestamp"),
                    alt.Tooltip("from_segment:N", title="From segment"),
                    alt.Tooltip("to_segment:N", title="To segment"),
                    alt.Tooltip("from_level:N", title="From interval"),
                    alt.Tooltip("to_level:N", title="To interval"),
                    alt.Tooltip("price_window_min:Q", title="Window min"),
                    alt.Tooltip("price_window_max:Q", title="Window max"),
                ],
            )
        )
        transition_points = (
            alt.Chart(transition_summary)
            .mark_circle(size=80)
            .encode(
                x="change_ts_local:T",
                y=alt.Y("price_trigger_estimate:Q", title="Estimated trigger price (EUR/MWh)"),
                color=alt.Color("to_segment:N", legend=None),
                tooltip=[
                    alt.Tooltip("change_ts_local:T", title="Timestamp"),
                     alt.Tooltip("from_segment:N", title="From segment"),
                     alt.Tooltip("to_segment:N", title="To segment"),
                    alt.Tooltip("from_level:N", title="From interval"),
                    alt.Tooltip("to_level:N", title="To interval"),
                    alt.Tooltip("price_before:Q", title="Price before change"),
                    alt.Tooltip("price_after:Q", title="Price after change"),
                    alt.Tooltip("price_trigger_estimate:Q", title="Estimated trigger"),
                ],
            )
        )
        st.altair_chart(transition_rules + transition_points, use_container_width=True)

        transition_display = transition_summary.copy()
        if "change_ts_local" in transition_display.columns:
            transition_display["change_ts_local"] = transition_display["change_ts_local"].dt.strftime("%Y-%m-%d %H:%M")
        for col in [
            "price_before",
            "price_after",
            "price_trigger_estimate",
            "price_window_min",
            "price_window_max",
            "downtime_hours",
        ]:
            transition_display[col] = transition_display[col].round(3)
        transition_display = transition_display.drop(columns=["change_ts"], errors="ignore")
        st.dataframe(
            transition_display.rename(
                columns={
                    "change_ts_local": "timestamp",
                    "from_segment": "from_segment",
                    "to_segment": "to_segment",
                    "from_level": "from_interval",
                    "to_level": "to_interval",
                    "price_before": "price_before_change",
                    "price_after": "price_after_change",
                    "price_trigger_estimate": "trigger_price_estimate",
                    "price_window_min": "window_price_min",
                    "price_window_max": "window_price_max",
                    "downtime_hours": "hours_until_next_change",
                }
            ),
            hide_index=True,
        )

    render_section_header(
        "Water values (SAMBA/05/11)",
        "Displays the interval estimates from SAMBA/05/11 Sections 2.3.2–2.3.4 mapped onto the production history.",
    )
    if is_raw_method or water_values_df.empty:
        st.caption("Water value estimates require a completed water-value run for the selected plant/method.")
    else:
        water_curve_df = build_water_value_curve(production_series_df, water_values_df, history_df)
        if not water_curve_df.empty and "timestamp" in water_curve_df.columns:
            water_curve_df["timestamp_local"] = water_curve_df["timestamp"].dt.tz_convert(DISPLAY_TIMEZONE)
        water_curve_filtered = water_curve_df[
            (water_curve_df["timestamp"] >= start_ts) & (water_curve_df["timestamp"] < end_ts)
        ]
        if water_curve_filtered.empty:
            st.caption("No water value estimates fall inside the chosen date window (SAMBA/05/11 Section 2.3.3).")
        else:
            base_curve = alt.Chart(water_curve_filtered).encode(
                x=alt.X("timestamp_local:T", title="Date"),
                color=alt.Color("interval:N", title="Production interval"),
                tooltip=[
                    alt.Tooltip("timestamp_local:T", title="Timestamp"),
                    alt.Tooltip("interval:N", title="Production interval"),
                    alt.Tooltip("lower:Q", title="Lower bound"),
                    alt.Tooltip("upper:Q", title="Upper bound"),
                ],
            )
            band = base_curve.transform_filter(
                (alt.datum.lower != None) & (alt.datum.upper != None) & (alt.datum.upper > alt.datum.lower)
            ).mark_area(opacity=0.18).encode(
                y=alt.Y("lower:Q", title="Water value (EUR/MWh)"),
                y2="upper:Q",
            )
            line = base_curve.mark_line(size=2).encode(
                y=alt.Y("upper:Q", title="Water value (EUR/MWh)"),
            )
            points = base_curve.mark_point(size=40, filled=True).encode(
                y=alt.Y("upper:Q"),
            )
            st.altair_chart(band + line + points, use_container_width=True)
            st.caption("Estimated water value intervals per production level (SAMBA/05/11 Sections 2.3.2–2.3.4).")

            latest_rows = (
                water_curve_filtered.dropna(subset=["upper"])
                .sort_values(["interval", "timestamp"])
                .groupby("interval", as_index=False)
                .tail(1)
                .sort_values("interval")
            )
            if latest_rows.empty:
                st.caption("The estimator did not produce interval bounds for this window.")
            else:
                latest_rows["timestamp_display"] = latest_rows["timestamp_local"].dt.strftime("%Y-%m-%d %H:%M")
                display_df = latest_rows[["interval", "lower", "upper", "timestamp_display"]].rename(
                    columns={
                        "lower": "lower_bound",
                        "upper": "upper_bound",
                        "timestamp_display": "timestamp_local",
                    }
                )
                st.dataframe(display_df, hide_index=True)

    render_section_header(
        "Operational context",
        "UMM market messages overlapping the analysis window, complementing the live data sources described in SAMBA/05/11 Section 1.",
    )
    umm_events = filter_umm_events(plant, selected_area, start_ts, end_ts)
    if umm_events.empty:
        st.caption("No UMM market messages matched this plant and date range.")
    else:
        display_events = umm_events.copy()
        for col in ("publication_date", "event_start", "event_stop"):
            if col in display_events:
                display_events[col] = (
                    display_events[col].dt.tz_convert(DISPLAY_TIMEZONE).dt.strftime("%Y-%m-%d %H:%M")
                )  # type: ignore[assignment]
        st.dataframe(
            display_events.drop(columns=["window_start", "window_end"]),
            hide_index=True,
        )
        prompt = _build_events_prompt(plant.name, selected_area, start_ts, end_ts, umm_events)
        summary_text = None
        if not os.environ.get("GEMINI_API_KEY"):
            st.caption("Set GEMINI_API_KEY in .env to enable automated event summaries.")
        else:
            summary_text = _generate_llm_summary(prompt)
            if summary_text is None:
                st.caption(
                    "Gemini summary unavailable. Ensure the google-generativeai package is installed and the API key is valid."
                )
        if summary_text:
            st.markdown(summary_text)

    render_section_header(
        "Summary",
        "Key run metadata, including observation counts, resolved prodlimits, and the effective parameters used for the latest pipeline execution (SAMBA/05/11 Summary steps 1–4).",
    )
    if not summary_df.empty and {"plant_id", "method"}.issubset(summary_df.columns):
        summary_rows = summary_df[(summary_df["plant_id"] == plant.id) & (summary_df["method"] == method)]
    else:
        summary_rows = pd.DataFrame()
    summary_data = summary_rows.iloc[0].to_dict() if not summary_rows.empty else {}
    observations_metric = int(summary_data.get("observations", len(production_series_df)))
    valid_breakpoints_metric = int(summary_data.get("valid_breakpoints", len(breakpoints_df)))
    max_installed_metric = summary_data.get("max_installed", plant.max_installed)
    prodlimits_values = summary_data.get("prodlimits", plant.prodlimits)
    if not isinstance(prodlimits_values, (list, tuple)):
        prodlimits_values = plant.prodlimits
    cols = st.columns(4)
    cols[0].metric("Observations", observations_metric)
    cols[1].metric("Valid breakpoints", valid_breakpoints_metric)
    cols[2].metric("Max installed (MW)", max_installed_metric)
    cols[3].metric("Prodlimits", ", ".join(str(v) for v in prodlimits_values))
    fallback_start_local = to_local_timestamp(production_series_df["timestamp"].min())
    fallback_end_local = to_local_timestamp(production_series_df["timestamp"].max())
    start_dt_summary = to_local_timestamp(pd.to_datetime(summary_data.get("start_date"), errors="coerce"))
    end_dt_summary = to_local_timestamp(pd.to_datetime(summary_data.get("end_date"), errors="coerce"))
    if pd.isna(start_dt_summary):
        start_dt_summary = fallback_start_local
    if pd.isna(end_dt_summary):
        end_dt_summary = fallback_end_local
    if pd.notna(start_dt_summary) and pd.notna(end_dt_summary):
        coverage_end = end_dt_summary - pd.Timedelta(seconds=1)
        st.caption(
            f"Latest dataset covers {start_dt_summary.date()} to {coverage_end.date()} ({selected_area}, {DISPLAY_TIMEZONE})."
        )
    resample_rule = summary_data.get("resample_rule")
    if isinstance(resample_rule, str) and resample_rule:
        st.caption(f"Series resampled to {resample_rule.upper()} resolution for estimation.")
    raw_observations = summary_data.get("raw_observations")
    native_spacing_seconds = summary_data.get("native_timestep_seconds")
    if isinstance(raw_observations, (int, float)) and raw_observations:
        if isinstance(native_spacing_seconds, (int, float)):
            native_td = pd.to_timedelta(int(native_spacing_seconds), unit="s")
            native_label = str(native_td).replace("0 days ", "")
        else:
            native_label = "unknown cadence"
        st.caption(f"Raw observations before resampling: {int(raw_observations)} (@ {native_label}).")
    param_cols = st.columns(4)
    strictness_display = summary_data.get("strictness")
    if strictness_display is None:
        strictness_display = strictness_value
    param_cols[0].metric("Strictness", f"{float(strictness_display):.2f}")
    jump_display = summary_data.get("jumpm")
    if jump_display is None:
        jump_display = jump_window
    param_cols[1].metric("Jump window (min)", int(jump_display))
    threshold_display = summary_data.get("max_samples_threshold")
    if threshold_display is None:
        if max_samples_threshold is None:
            threshold_text = "Disabled"
        else:
            threshold_text = str(int(max_samples_threshold))
    else:
        threshold_text = "Disabled" if threshold_display in (None, -1) else str(int(threshold_display))
    param_cols[2].metric("Max samples", threshold_text)
    param_cols[3].metric("Methods", ", ".join(PIPELINE_METHODS))
    st.caption(
        "Strictness applies the curvature criterion from SAMBA/05/11 Section 2.2, while the jump window mirrors the breakpoint neighbourhood in Section 2.3.1."
    )

    render_section_header(
        "Download data",
        "Export the aligned price and production series underpinning the estimator (SAMBA/05/11 Section 1).",
    )
    st.download_button(
        "Price CSV",
        data=price_df.to_csv(index=False),
        file_name=f"price_{selected_area}.csv",
    )
    st.download_button(
        f"{plant.name} production CSV",
        data=production_df.to_csv(index=False),
        file_name=f"{plant.id}_production.csv",
    )


if __name__ == "__main__":
    main()
