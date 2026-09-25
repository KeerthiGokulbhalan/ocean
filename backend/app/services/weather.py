"""
Client for the Open-Meteo Marine Weather API, supplemented with the
standard Open-Meteo Forecast API for wind (wind is not part of the marine
dataset itself).

Marine API docs: https://open-meteo.com/en/docs/marine-weather-api
Forecast API docs: https://open-meteo.com/en/docs/

Both are free and require no API key. If either request fails (offline
dev, rate limiting, a point far from any covered ocean model), we fail soft
and return calm-weather defaults so routing and the UI never break because
of a flaky external API.
"""
import asyncio

import httpx

from app.config import OPEN_METEO_MARINE_URL, OPEN_METEO_WEATHER_URL

DEFAULT_WEATHER = {
    "wave_height_m": 0.0,
    "wave_direction_deg": None,
    "wave_period_s": None,
    "swell_wave_height_m": None,
    "wind_wave_height_m": None,
    "sea_surface_temperature_c": None,
    "ocean_current_velocity_kmh": None,
    "ocean_current_direction_deg": None,
    "wind_speed_kmh": 0.0,
    "wind_direction_deg": None,
}

MARINE_HOURLY_VARS = ",".join(
    [
        "wave_height",
        "wave_direction",
        "wave_period",
        "wind_wave_height",
        "swell_wave_height",
        "sea_surface_temperature",
        "ocean_current_velocity",
        "ocean_current_direction",
    ]
)

FORECAST_HOURLY_VARS = "wind_speed_10m,wind_direction_10m"


def _first(series: list | None) -> float | None:
    if not series:
        return None
    value = series[0]
    return float(value) if value is not None else None


async def _fetch_marine(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    params = {
        "latitude": round(lat, 3),
        "longitude": round(lon, 3),
        "hourly": MARINE_HOURLY_VARS,
        "length_unit": "metric",
        "timezone": "UTC",
        "forecast_days": 1,
    }
    resp = await client.get(OPEN_METEO_MARINE_URL, params=params)
    resp.raise_for_status()
    hourly = resp.json().get("hourly", {})
    return {
        "wave_height_m": _first(hourly.get("wave_height")) or 0.0,
        "wave_direction_deg": _first(hourly.get("wave_direction")),
        "wave_period_s": _first(hourly.get("wave_period")),
        "swell_wave_height_m": _first(hourly.get("swell_wave_height")),
        "wind_wave_height_m": _first(hourly.get("wind_wave_height")),
        "sea_surface_temperature_c": _first(hourly.get("sea_surface_temperature")),
        "ocean_current_velocity_kmh": _first(hourly.get("ocean_current_velocity")),
        "ocean_current_direction_deg": _first(hourly.get("ocean_current_direction")),
    }


async def _fetch_wind(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    params = {
        "latitude": round(lat, 3),
        "longitude": round(lon, 3),
        "hourly": FORECAST_HOURLY_VARS,
        "wind_speed_unit": "kmh",
        "timezone": "UTC",
        "forecast_days": 1,
    }
    resp = await client.get(OPEN_METEO_WEATHER_URL, params=params)
    resp.raise_for_status()
    hourly = resp.json().get("hourly", {})
    return {
        "wind_speed_kmh": _first(hourly.get("wind_speed_10m")) or 0.0,
        "wind_direction_deg": _first(hourly.get("wind_direction_10m")),
    }


async def fetch_marine_point(lat: float, lon: float) -> dict:
    """Fetch combined marine + wind conditions for a single point.
    Always returns every key in DEFAULT_WEATHER; fields the API didn't
    have data for come back as None (visualised as "—" in the UI)."""
    result = dict(DEFAULT_WEATHER)
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            marine_task = _fetch_marine(client, lat, lon)
            wind_task = _fetch_wind(client, lat, lon)
            marine, wind = await asyncio.gather(
                marine_task, wind_task, return_exceptions=True
            )
        if isinstance(marine, dict):
            result.update(marine)
        if isinstance(wind, dict):
            result.update(wind)
    except Exception:
        # both requests failed outright (offline, DNS, etc.) — degrade
        # gracefully rather than failing the route/weather request
        pass
    return result
