from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List, Sequence

import numpy as np
import pandas as pd

try:  # Support both package and direct execution contexts.
    from .config import PlantConfig, PROCESSED_DATA_DIR
except ImportError:  # pragma: no cover - fallback for CLI execution
    from config import PlantConfig, PROCESSED_DATA_DIR


UNIT_DISPLAY_OVERRIDES: dict[str, str] = {
    "sima_g1_hydro": "SIMA G1 HYDRO",
    "sima_g2_hydro": "SIMA G2 HYDRO",
    "sima_g3_hydro": "SIMA G3 HYDRO",
    "sima_g4_hydro": "SIMA G4 HYDRO",
    "aurland1g1_hydro": "AURLAND1G1 HYDRO",
    "aurland1g2_hydro": "AURLAND1G2 HYDRO",
    "aurland1g3_hydro": "AURLAND1G3 HYDRO",
    "aurland2g1_hydro": "AURLAND2G1 HYDRO",
    "aurland2g2_hydro": "AURLAND2G2 HYDRO",
    "aurland2g3_hydro": "AURLAND2G3 HYDRO",
    "aurland3g1_hydro": "AURLAND3G1 HYDRO",
    "aurland3g2_hydro": "AURLAND3G2 HYDRO",
    "kvilldalg1_hydro": "KVILLDALG1 HYDRO",
    "kvilldalg2_hydro": "KVILLDALG2 HYDRO",
    "kvilldalg3_hydro": "KVILLDALG3 HYDRO",
    "kvilldalg4_hydro": "KVILLDALG4 HYDRO",
    "saurdal_g1_hydro": "SAURDAL G1 HYDRO",
    "saurdal_g2_hydro": "SAURDAL G2 HYDRO",
    "saurdal_g3_hydro": "SAURDAL G3 HYDRO",
    "saurdal_g4_hydro": "SAURDAL G4 HYDRO",
}


def normalize_unit_filter(name: str | None) -> List[str]:
    if not name:
        return []
    cleaned = " ".join(str(name).strip().split())
    if not cleaned:
        return []
    return [cleaned.upper()]


def load_unit_metadata(csv_path: str | Path, *, usecols: Iterable[str] | None = None) -> dict[str, Any]:
    path = Path(csv_path)
    if not path.exists():
        return {}

    candidate_cols = ["production_mw", "detail_id", "unit_name"]
    if usecols is not None:
        chosen_cols = [col for col in candidate_cols if col in set(usecols)]
        if chosen_cols:
            candidate_cols = chosen_cols

    try:
        df = pd.read_csv(path, usecols=[col for col in candidate_cols if col])
    except Exception:
        return {}

    production = pd.to_numeric(df.get("production_mw"), errors="coerce")
    max_installed = float(production.max()) if not production.empty else np.nan

    detail_series = df.get("detail_id")
    if detail_series is not None:
        detail_ids = (
            detail_series.astype(str)
            .str.strip()
            .replace("", np.nan)
            .dropna()
            .unique()
            .tolist()
        )
    else:
        detail_ids = []

    name_series = df.get("unit_name")
    display_name = None
    if name_series is not None:
        cleaned = name_series.astype(str).str.strip()
        cleaned = cleaned.replace("", np.nan).dropna()
        if not cleaned.empty:
            display_name = " ".join(str(cleaned.iloc[0]).split())

    return {
        "display_name": display_name,
        "detail_ids": detail_ids,
        "max_installed": max_installed,
    }


def _resolve_unit_entries(plant: PlantConfig, summary_df: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    unit_entries: dict[str, dict[str, Any]] = {}
    if summary_df is not None and not summary_df.empty and "unit_csvs" in summary_df.columns:
        matching_rows = summary_df[summary_df["plant_id"] == plant.id]
        for _, row in matching_rows.iterrows():
            for entry in row.get("unit_csvs", []) or []:
                if not isinstance(entry, dict):
                    continue
                csv_rel = entry.get("csv")
                if not csv_rel:
                    continue
                slug = entry.get("slug")
                if not isinstance(slug, str) or not slug:
                    slug = Path(csv_rel).stem
                unit_entries[slug] = dict(entry, csv=csv_rel)

    for slug in getattr(plant, "combine_from_units", []) or []:
        unit_entries.setdefault(
            slug,
            {
                "csv": f"processed/{slug}_production.csv",
                "slug": slug,
            },
        )

    return unit_entries


def derive_unit_plants(
    base_plants: Sequence[PlantConfig],
    *,
    summary_df: pd.DataFrame | None = None,
    split_parent_capacity: bool = False,
) -> List[PlantConfig]:
    """Build PlantConfig entries for unit-level datasets.

    Parameters
    ----------
    base_plants:
        Iterable of configured plants scoped to a price area.
    summary_df:
        Optional pipeline summary used to recover rich metadata for unit CSVs.
    split_parent_capacity:
        When true, fall back to an even split of the parent plant's max_installed
        when unit metadata lacks a credible maximum value.
    """
    extras: List[PlantConfig] = []
    if not base_plants:
        return extras

    seen_ids = {plant.id for plant in base_plants}

    for plant in base_plants:
        unit_entries = _resolve_unit_entries(plant, summary_df)
        if not unit_entries:
            continue

        unit_slugs = list(getattr(plant, "combine_from_units", []) or [])
        unit_count = max(1, len(unit_slugs) or len(unit_entries))

        for slug, entry in unit_entries.items():
            if slug in seen_ids:
                continue

            csv_rel = entry.get("csv")
            csv_path: Path
            if isinstance(csv_rel, str) and csv_rel:
                rel_path = Path(csv_rel)
                if rel_path.is_absolute():
                    csv_path = rel_path
                else:
                    if rel_path.parts and rel_path.parts[0] != "processed":
                        rel_path = Path("processed") / rel_path
                    csv_path = PROCESSED_DATA_DIR.parent / rel_path
            else:
                csv_path = PROCESSED_DATA_DIR / f"{slug}_production.csv"

            if not csv_path.exists():
                fallback_path = PROCESSED_DATA_DIR / f"{slug}_production.csv"
                if not fallback_path.exists():
                    continue
                csv_path = fallback_path

            metadata = load_unit_metadata(csv_path)
            detail_ids = metadata.get("detail_ids") or []
            max_installed = metadata.get("max_installed")
            if (
                not isinstance(max_installed, (int, float))
                or not np.isfinite(max_installed)
                or max_installed <= 0
            ):
                if split_parent_capacity:
                    max_installed = plant.max_installed / unit_count
                else:
                    max_installed = plant.max_installed

            display_name = (
                UNIT_DISPLAY_OVERRIDES.get(slug)
                or metadata.get("display_name")
                or entry.get("name")
                or slug.replace("_", " ")
            )
            display_name = " ".join(str(display_name).split()).upper()

            unit_filters = (
                normalize_unit_filter(entry.get("name"))
                or normalize_unit_filter(metadata.get("display_name"))
                or normalize_unit_filter(display_name)
            )
            if not unit_filters:
                unit_filters = normalize_unit_filter(slug.replace("_", " "))

            extras.append(
                PlantConfig(
                    id=slug,
                    name=display_name,
                    registered_resources=detail_ids,
                    price_area=plant.price_area,
                    max_installed=float(max_installed),
                    prodlimits=[],
                    pump_resources=[],
                    entsoe_web_name=plant.entsoe_web_name,
                    entsoe_web_unit_filters=unit_filters,
                    combine_from_units=[],
                )
            )
            seen_ids.add(slug)

    return extras
