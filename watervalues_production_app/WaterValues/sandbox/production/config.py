from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUT_DIR = BASE_DIR / "output"

ENTSOE_CONTROL_AREA_NO = "10YNO-0--------C"
PRICE_AREA_CODES = {
    "NO1": "10YNO-1--------2",
    "NO2": "10YNO-2--------T",
    "NO3": "10YNO-3--------J",
    "NO4": "10YNO-4--------9",
    "NO5": "10Y1001A1001A48H",
}


@dataclass(frozen=True)
class PlantConfig:
    id: str
    name: str
    registered_resources: List[str]
    price_area: str
    max_installed: float
    prodlimits: List[float] = field(default_factory=list)
    pump_resources: List[str] = field(default_factory=list)
    entsoe_web_name: str | None = None
    entsoe_web_unit_filters: List[str] = field(default_factory=list)
    combine_from_units: List[str] = field(default_factory=list)

    def resolved_prodlimits(self, segments: int = 4) -> List[float]:
        if self.prodlimits:
            return self.prodlimits
        if segments < 1:
            return [self.max_installed]
        step = self.max_installed / segments
        limits = [round(step * idx, 3) for idx in range(segments + 1)]
        limits[0] = 0.0
        limits[-1] = round(self.max_installed, 3)
        if len(limits) > 1 and limits[1] == 0.0:
            limits[1] = round(step, 3)
        return limits

    def resolved_web_name(self) -> str:
        return self.entsoe_web_name or self.name


PLANTS: List[PlantConfig] = [
    PlantConfig(
        id="aurland_total",
        name="AURLAND TOTAL (Combined)",
        registered_resources=[
            "50WP00000000020T",  # Aurland I
            "50WP00000000022P",  # Aurland II
            "50WP00000000023N",  # Aurland III
        ],
        price_area="NO5",
        max_installed=840 + 143 + 290,
        prodlimits=[0.0, 200.0, 400.0, 650.0, 900.0, 1150.0],
        entsoe_web_name="Aurland",
        combine_from_units=[
            "aurland1g1_hydro",
            "aurland1g2_hydro",
            "aurland1g3_hydro",
            "aurland2g1_hydro",
            "aurland2g2_hydro",
            "aurland2g3_hydro",
            "aurland3g1_hydro",
            "aurland3g2_hydro",
        ],
    ),
    PlantConfig(
        id="aurland1_combined",
        name="AURLAND 1 (Combined)",
        registered_resources=[],
        price_area="NO5",
        max_installed=840,
        prodlimits=[0.0, 180.0, 360.0, 540.0, 720.0],
        combine_from_units=[
            "aurland1g1_hydro",
            "aurland1g2_hydro",
            "aurland1g3_hydro",
        ],
    ),
    PlantConfig(
        id="aurland2_combined",
        name="AURLAND 2 (Combined)",
        registered_resources=[],
        price_area="NO5",
        max_installed=143,
        prodlimits=[0.0, 30.0, 60.0, 90.0, 120.0],
        combine_from_units=[
            "aurland2g1_hydro",
            "aurland2g2_hydro",
            "aurland2g3_hydro",
        ],
    ),
    PlantConfig(
        id="aurland3_combined",
        name="AURLAND 3 (Combined)",
        registered_resources=[],
        price_area="NO5",
        max_installed=290,
        prodlimits=[0.0, 70.0, 140.0, 210.0, 260.0],
        combine_from_units=[
            "aurland3g1_hydro",
            "aurland3g2_hydro",
        ],
    ),
    PlantConfig(
        id="sima_combined",
        name="Sima (Combined)",
        registered_resources=["50WP000000008783", "50WV00000009609M"],
        price_area="NO5",
        max_installed=500 + 420,
        prodlimits=[0.0, 120.0, 240.0, 360.0, 480.0, 620.0, 750.0, 920.0],
        entsoe_web_name="Sima",
        combine_from_units=[
            "sima_g1_hydro",
            "sima_g2_hydro",
            "sima_g3_hydro",
            "sima_g4_hydro",
        ],
    ),
    PlantConfig(
        id="saurdal",
        name="Saurdal kraftverk",
        registered_resources=["50WP00000000607Y"],
        price_area="NO2",
        max_installed=640,
        prodlimits=[0.0, 25.0, 40.0, 55.0, 75.0],
        pump_resources=["50WG00000001439U", "50WG00000001458Q"],
        entsoe_web_name="Saurdal",
        combine_from_units=[
            "saurdal_g1_hydro",
            "saurdal_g2_hydro",
            "saurdal_g3_hydro",
            "saurdal_g4_hydro",
        ],
    ),
    PlantConfig(
        id="kvilldal",
        name="Kvilldal (Suldal)",
        registered_resources=["50WP00000000389I"],
        price_area="NO2",
        max_installed=1240,
        prodlimits=[0.0, 250.0, 500.0, 750.0, 1000.0, 1240.0],
        pump_resources=[],
        entsoe_web_name="Kvilldal",
        combine_from_units=[
            "kvilldalg1_hydro",
            "kvilldalg2_hydro",
            "kvilldalg3_hydro",
            "kvilldalg4_hydro",
        ],
    ),
]


def ensure_directories() -> None:
    for path in (DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, OUTPUT_DIR):
        path.mkdir(parents=True, exist_ok=True)
