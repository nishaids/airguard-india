"""Central configuration for the AirGuard India project.

All paths, the global random seed, pollutant definitions, CPCB National AQI
breakpoints and event windows used across the pipeline are declared here so
that every module and notebook consumes a single, immutable source of truth.

References
----------
CPCB (2014). *National Air Quality Index: Report of the Expert Group*.
    Central Pollution Control Board, Ministry of Environment, Forest and
    Climate Change, Government of India.
    https://cpcb.nic.in/upload/Downloads/AQI_Report_0.pdf
"""

from __future__ import annotations

import logging
import os
import random
from pathlib import Path
from typing import Dict, Final, List, Tuple

import numpy as np

# --------------------------------------------------------------------------- #
# Reproducibility
# --------------------------------------------------------------------------- #
RANDOM_SEED: Final[int] = 42


def set_global_seed(seed: int = RANDOM_SEED) -> None:
    """Seed every stochastic component used in this project.

    Parameters
    ----------
    seed:
        Integer seed applied to ``random``, ``numpy`` and the ``PYTHONHASHSEED``
        environment variable. scikit-learn, XGBoost and LightGBM estimators are
        additionally constructed with ``random_state=seed`` at their call sites.
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
RAW_DIR: Final[Path] = DATA_DIR / "raw"
INTERIM_DIR: Final[Path] = DATA_DIR / "interim"
PROCESSED_DIR: Final[Path] = DATA_DIR / "processed"

SRC_DIR: Final[Path] = PROJECT_ROOT / "src"
MODELS_DIR: Final[Path] = PROJECT_ROOT / "models"
RESULTS_DIR: Final[Path] = PROJECT_ROOT / "results"
REPORTS_DIR: Final[Path] = PROJECT_ROOT / "reports"
FIGURES_DIR: Final[Path] = REPORTS_DIR / "figures"
NOTEBOOKS_DIR: Final[Path] = PROJECT_ROOT / "notebooks"
APP_DIR: Final[Path] = PROJECT_ROOT / "app"

def portable(path: Path | str) -> str:
    """Render a filesystem path for a generated artefact.

    Generated JSON and Markdown are published, reviewed and compared across
    checkouts, so they must never carry a local absolute path: it leaks the
    machine layout and the operator's account name, and it does not reproduce
    anywhere else. Paths inside the repository become repository-relative POSIX
    strings; anything outside is reduced to its final component behind an
    explicit marker, because the rest of it is nobody else's business.
    """
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        # Keep the last two components: a bare final name can be a version
        # number such as "12", which says nothing about what the path held.
        tail = [part for part in candidate.parts if part not in ("/", "\\")][-2:]
        return "/".join(["<outside-repository>", *tail])


ALL_DIRS: Final[Tuple[Path, ...]] = (
    RAW_DIR,
    INTERIM_DIR,
    PROCESSED_DIR,
    MODELS_DIR,
    RESULTS_DIR,
    REPORTS_DIR,
    FIGURES_DIR,
)


def ensure_dirs() -> None:
    """Create every directory the pipeline writes to, if absent."""
    for directory in ALL_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Dataset identity
# --------------------------------------------------------------------------- #
KAGGLE_DATASET_SLUG: Final[str] = "rohanrao/air-quality-data-in-india"
KAGGLE_DATASET_URL: Final[str] = (
    "https://www.kaggle.com/datasets/rohanrao/air-quality-data-in-india"
)
UPSTREAM_SOURCE_NAME: Final[str] = (
    "Central Pollution Control Board (CPCB), Ministry of Environment, Forest "
    "and Climate Change, Government of India"
)
UPSTREAM_SOURCE_URL: Final[str] = "https://cpcb.nic.in/"
CPCB_REALTIME_PORTAL: Final[str] = "https://app.cpcbccr.com/AQI_India/"

PRIMARY_FILE: Final[str] = "city_day.csv"
STATION_META_FILE: Final[str] = "stations.csv"
HOURLY_FILE: Final[str] = "city_hour.csv"
EXPECTED_FILES: Final[Tuple[str, ...]] = (
    "city_day.csv",
    "city_hour.csv",
    "station_day.csv",
    "station_hour.csv",
    "stations.csv",
)

RAW_ZIP_NAME: Final[str] = "air-quality-data-in-india.zip"

# --------------------------------------------------------------------------- #
# Pollutants and targets
# --------------------------------------------------------------------------- #
#: Pollutants carried by ``city_day.csv``. ``CO`` is reported in mg/m3, every
#: other species in ug/m3 (NOx in ppb).
POLLUTANT_COLS: Final[List[str]] = [
    "PM2.5",
    "PM10",
    "NO",
    "NO2",
    "NOx",
    "NH3",
    "CO",
    "SO2",
    "O3",
    "Benzene",
    "Toluene",
    "Xylene",
]

#: Subset for which CPCB publishes National AQI sub-index breakpoints.
AQI_POLLUTANTS: Final[List[str]] = ["PM2.5", "PM10", "NO2", "NH3", "SO2", "CO", "O3"]

#: Pollutants used by the Health Advisory Index. Benzene, Toluene and Xylene are
#: excluded: their coverage in ``city_day.csv`` is too sparse for a daily index.
HAI_POLLUTANTS: Final[List[str]] = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]

POLLUTANT_UNITS: Final[Dict[str, str]] = {
    "PM2.5": "ug/m3",
    "PM10": "ug/m3",
    "NO": "ug/m3",
    "NO2": "ug/m3",
    "NOx": "ppb",
    "NH3": "ug/m3",
    "CO": "mg/m3",
    "SO2": "ug/m3",
    "O3": "ug/m3",
    "Benzene": "ug/m3",
    "Toluene": "ug/m3",
    "Xylene": "ug/m3",
}

#: Physically plausible ceiling per pollutant. Values above these are treated as
#: sensor artefacts rather than genuine pollution events (see ``data/clean.py``).
POLLUTANT_PLAUSIBLE_MAX: Final[Dict[str, float]] = {
    "PM2.5": 1000.0,
    "PM10": 1200.0,
    "NO": 500.0,
    "NO2": 500.0,
    "NOx": 600.0,
    "NH3": 600.0,
    "CO": 50.0,
    "SO2": 800.0,
    "O3": 400.0,
    "Benzene": 100.0,
    "Toluene": 500.0,
    "Xylene": 200.0,
}

TARGET_REGRESSION: Final[str] = "AQI_next"
TARGET_CLASSIFICATION: Final[str] = "AQI_Bucket_next"

#: CPCB National AQI categories, ordered from cleanest to most polluted.
AQI_BUCKETS: Final[List[str]] = [
    "Good",
    "Satisfactory",
    "Moderate",
    "Poor",
    "Very Poor",
    "Severe",
]
AQI_BUCKET_ORDINAL: Final[Dict[str, int]] = {b: i for i, b in enumerate(AQI_BUCKETS)}
AQI_BUCKET_BOUNDS: Final[List[Tuple[str, float, float]]] = [
    ("Good", 0.0, 50.0),
    ("Satisfactory", 50.0, 100.0),
    ("Moderate", 100.0, 200.0),
    ("Poor", 200.0, 300.0),
    ("Very Poor", 300.0, 400.0),
    ("Severe", 400.0, float("inf")),
]

#: CPCB (2014) sub-index breakpoints: ``(C_low, C_high, I_low, I_high)`` in the
#: pollutant's own reporting unit.
CPCB_BREAKPOINTS: Final[Dict[str, List[Tuple[float, float, float, float]]]] = {
    "PM2.5": [
        (0, 30, 0, 50),
        (30, 60, 50, 100),
        (60, 90, 100, 200),
        (90, 120, 200, 300),
        (120, 250, 300, 400),
        (250, 1000, 400, 500),
    ],
    "PM10": [
        (0, 50, 0, 50),
        (50, 100, 50, 100),
        (100, 250, 100, 200),
        (250, 350, 200, 300),
        (350, 430, 300, 400),
        (430, 1200, 400, 500),
    ],
    "NO2": [
        (0, 40, 0, 50),
        (40, 80, 50, 100),
        (80, 180, 100, 200),
        (180, 280, 200, 300),
        (280, 400, 300, 400),
        (400, 1000, 400, 500),
    ],
    "NH3": [
        (0, 200, 0, 50),
        (200, 400, 50, 100),
        (400, 800, 100, 200),
        (800, 1200, 200, 300),
        (1200, 1800, 300, 400),
        (1800, 3000, 400, 500),
    ],
    "SO2": [
        (0, 40, 0, 50),
        (40, 80, 50, 100),
        (80, 380, 100, 200),
        (380, 800, 200, 300),
        (800, 1600, 300, 400),
        (1600, 2400, 400, 500),
    ],
    "CO": [
        (0, 1, 0, 50),
        (1, 2, 50, 100),
        (2, 10, 100, 200),
        (10, 17, 200, 300),
        (17, 34, 300, 400),
        (34, 50, 400, 500),
    ],
    "O3": [
        (0, 50, 0, 50),
        (50, 100, 50, 100),
        (100, 168, 100, 200),
        (168, 208, 200, 300),
        (208, 748, 300, 400),
        (748, 1000, 400, 500),
    ],
}

# --------------------------------------------------------------------------- #
# Health Advisory Index bands (0-100 scale)
# --------------------------------------------------------------------------- #
HAI_BANDS: Final[List[Tuple[str, float, float]]] = [
    ("Low", 0.0, 20.0),
    ("Moderate", 20.0, 40.0),
    ("High", 40.0, 60.0),
    ("Very High", 60.0, 80.0),
    ("Extreme", 80.0, 100.0001),
]

COHORTS: Final[List[str]] = [
    "healthy_adult",
    "children",
    "elderly_60plus",
    "asthma_copd",
    "cardiac",
    "pregnant",
    "outdoor_worker",
]

COHORT_LABELS: Final[Dict[str, str]] = {
    "healthy_adult": "Healthy adult",
    "children": "Children (under 14)",
    "elderly_60plus": "Elderly (60+)",
    "asthma_copd": "Asthma / COPD",
    "cardiac": "Cardiac patients",
    "pregnant": "Pregnant women",
    "outdoor_worker": "Outdoor workers",
}

# --------------------------------------------------------------------------- #
# Event windows
# --------------------------------------------------------------------------- #
#: Diwali (Lakshmi Puja / firecracker night) for the covered years.
DIWALI_DATES: Final[Dict[int, str]] = {
    2015: "2015-11-11",
    2016: "2016-10-30",
    2017: "2017-10-19",
    2018: "2018-11-07",
    2019: "2019-10-27",
    2020: "2020-11-14",
}
#: Days either side of Diwali counted as the festival window.
DIWALI_WINDOW_DAYS: Final[int] = 3

#: North-Indian post-monsoon crop-residue (stubble) burning season, as
#: inclusive ``(month, day)`` pairs.
STUBBLE_SEASON: Final[Tuple[Tuple[int, int], Tuple[int, int]]] = ((10, 1), (11, 30))

#: Nationwide COVID-19 lockdown, phases 1 to 4.
LOCKDOWN_START: Final[str] = "2020-03-25"
LOCKDOWN_END: Final[str] = "2020-05-31"

SEASON_OF_MONTH: Final[Dict[int, str]] = {
    1: "Winter",
    2: "Winter",
    3: "Summer",
    4: "Summer",
    5: "Summer",
    6: "Summer",
    7: "Monsoon",
    8: "Monsoon",
    9: "Monsoon",
    10: "Post-Monsoon",
    11: "Post-Monsoon",
    12: "Winter",
}

SEASON_ORDER: Final[List[str]] = ["Winter", "Summer", "Monsoon", "Post-Monsoon"]

# --------------------------------------------------------------------------- #
# Modelling policy
# --------------------------------------------------------------------------- #
#: A city is retained only if at least this fraction of the calendar days
#: between its own first and last record carries a usable AQI value.
CITY_COMPLETENESS_THRESHOLD: Final[float] = 0.80

#: A city must also contribute at least this many usable daily records.
CITY_MIN_RECORDS: Final[int] = 730

#: Fraction of the time-ordered record reserved for the held-out test set.
TEST_FRACTION: Final[float] = 0.20

#: Lag orders and rolling windows built per city in ``features/build.py``.
LAG_ORDERS: Final[Tuple[int, ...]] = (1, 2, 3, 7)
ROLLING_WINDOWS: Final[Tuple[int, ...]] = (3, 7, 14)

N_SPLITS_TS_CV: Final[int] = 4

#: Columns that must never enter a feature matrix predicting next-day AQI or
#: its bucket, because they are the target or a deterministic function of it.
LEAKAGE_COLS: Final[Tuple[str, ...]] = (
    "AQI",
    "AQI_Bucket",
    "AQI_next",
    "AQI_Bucket_next",
    "AQI_Bucket_ordinal",
    "AQI_Bucket_next_ordinal",
)

# --------------------------------------------------------------------------- #
# Plotting
# --------------------------------------------------------------------------- #
FIG_DPI: Final[int] = 300
#: Okabe-Ito qualitative palette: colour-blind safe (Okabe and Ito, 2008).
PALETTE: Final[List[str]] = [
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#E69F00",
    "#56B4E9",
    "#F0E442",
    "#000000",
]
#: Sequential, perceptually uniform, legible in greyscale.
SEQ_CMAP: Final[str] = "viridis"
DIV_CMAP: Final[str] = "RdBu_r"

# --------------------------------------------------------------------------- #
# Academic metadata (used verbatim on report cover pages)
# --------------------------------------------------------------------------- #
ACADEMIC: Final[Dict[str, str]] = {
    "institution": (
        "Rajalakshmi Engineering College (Autonomous, affiliated to Anna "
        "University, Chennai)"
    ),
    "course_code": "AD23532",
    "course_name": "Principles of Data Science",
    "course_type": "Lab Oriented Theory",
    "category": "Professional Core (PC)",
    "ltpc": "2-0-4-4",
    "regulation": "2023",
    "academic_year": "2026-27 (ODD)",
    "semester": "V",
    "degree_branch": "B.Tech. Artificial Intelligence and Data Science",
    "batch": "2024-2028",
    "project_title": "AirGuard India",
    "project_subtitle": (
        "A Vulnerability-Weighted Health Advisory Index and Next-Day Air "
        "Quality Forecasting System for Indian Cities"
    ),
}

TEAM: Final[List[Dict[str, str]]] = [
    {"register_no": "260586", "name": "Nishanth Rajendran"},
    {"register_no": "260598", "name": "<NAME>"},
    {"register_no": "260600", "name": "<NAME>"},
]

REVIEW_MARKS: Final[Dict[str, int]] = {"Review 1": 30, "Review 2": 30, "Review 3": 40}

REPO_URL: Final[str] = "https://github.com/nishaids/airguard-india"

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-7s | %(name)-24s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a module logger attached to a single stream handler.

    Parameters
    ----------
    name:
        Logger name, conventionally ``__name__`` of the calling module.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%H:%M:%S"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
