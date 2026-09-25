"""
Central configuration for the SeaPath backend.
Values can be overridden with environment variables of the same name.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Database -------------------------------------------------------------
# SQLite by default so the project runs with zero external setup.
# For production, point this at a PostgreSQL + PostGIS instance instead, e.g.:
#   postgresql+psycopg2://user:password@localhost:5432/seapath
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'seapath.db'}")

# --- External APIs ---------------------------------------------------------
OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
OPEN_METEO_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# --- Routing grid -----------------------------------------------------------
# Grid resolution in degrees. Smaller = more accurate but much slower.
GRID_RESOLUTION_DEG = float(os.getenv("GRID_RESOLUTION_DEG", "0.5"))

# Diagonal + straight neighbour directions (8-connected grid)
NEIGHBOR_OFFSETS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]

# --- Vessel defaults --------------------------------------------------------
DEFAULT_FUEL_RATE_TON_PER_HR = {
    "container": 3.2,
    "tanker": 4.1,
    "bulk_carrier": 2.8,
    "cruise": 5.0,
    "fishing": 0.6,
}

# CO2 emitted per ton of heavy fuel oil burned (IMO default factor)
CO2_PER_TON_FUEL = 3.114

# CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

# --- Auth ---------------------------------------------------------------
# In production, set SECRET_KEY via environment variable to a long random value.
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Risk score (0-1) above which an automatic StormWarning alert is raised
ALERT_RISK_THRESHOLD = 0.5
# Fractional change in a route's risk/fuel that triggers a RouteChange alert
REROUTE_CHANGE_THRESHOLD = 0.15


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# --- Live vessel tracking / AIS ---------------------------------------------
# "mock"  -> MockAISProvider: positions come from the built-in voyage
#            simulator. Clearly labelled as simulated in the API and UI.
# "real"      -> generic commercial AIS REST adapter.
# "aisstream" -> AISstream.io WebSocket with MMSI-mapped fleet vessels.
AIS_PROVIDER = os.getenv("AIS_PROVIDER", "mock").strip().lower()
AIS_API_URL = os.getenv("AIS_API_URL", "")
AIS_API_KEY = os.getenv("AIS_API_KEY", "")  # never hard-code — env only
AISSTREAM_STALE_SECONDS = int(os.getenv("AISSTREAM_STALE_SECONDS", "180"))

# Master switch: when false, tracking endpoints return 503 rather than 404,
# so the frontend can hide live-tracking UI cleanly.
ENABLE_LIVE_TRACKING = _env_bool("ENABLE_LIVE_TRACKING", True)

# Seconds between position pushes over the WebSocket / expected polling period.
LOCATION_UPDATE_INTERVAL = float(os.getenv("LOCATION_UPDATE_INTERVAL", "5"))

# Minimum seconds between writing a position row to the database. Decoupled
# from the push interval so a 5s live feed doesn't produce 720 rows/hour.
POSITION_PERSIST_INTERVAL_S = float(os.getenv("POSITION_PERSIST_INTERVAL_S", "60"))

# Cap on how many historical positions a single track request returns.
MAX_TRACK_POINTS = int(os.getenv("MAX_TRACK_POINTS", "500"))

# Wave height (m) at the vessel's live position that triggers a StormWarning
# alert via the existing alert architecture.
LIVE_ALERT_WAVE_HEIGHT_M = float(os.getenv("LIVE_ALERT_WAVE_HEIGHT_M", "4.0"))

# Minimum seconds between repeat live alerts for the same voyage, so a vessel
# sitting inside a storm cell doesn't spam the alert feed.
LIVE_ALERT_COOLDOWN_S = float(os.getenv("LIVE_ALERT_COOLDOWN_S", "1800"))
