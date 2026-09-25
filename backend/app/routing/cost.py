"""
Multi-objective edge cost model.

Each edge (grid cell -> neighbouring grid cell) is scored on three
components which are then blended according to the chosen strategy:

  time_cost   -> hours to traverse the edge at cruise speed
  fuel_cost   -> tons of fuel burned, penalised further by rough seas
  risk_cost   -> 0-1 danger score from wave height at the edge midpoint

strategy weight profiles:
  fastest   : time dominates
  efficient : fuel dominates
  safest    : risk dominates, heavily
"""
from dataclasses import dataclass

from app.config import DEFAULT_FUEL_RATE_TON_PER_HR
from app.routing.geo import haversine_nm
from app.routing.weather_field import WeatherField
from app.schemas import RouteStrategy, VesselProfile

STRATEGY_WEIGHTS = {
    "fastest":   {"time": 0.7, "fuel": 0.15, "risk": 0.15},
    "efficient": {"time": 0.2, "fuel": 0.65, "risk": 0.15},
    "safest":    {"time": 0.15, "fuel": 0.15, "risk": 0.70},
}

# Wave height (m) beyond which risk saturates to maximum
RISK_SATURATION_WAVE_M = 6.0

# Extra fuel burned (fractional) per metre of significant wave height
FUEL_WAVE_PENALTY_PER_M = 0.06


@dataclass
class EdgeCost:
    total: float
    time_hr: float
    fuel_tons: float
    risk: float


def wave_risk_score(wave_height_m: float) -> float:
    return min(1.0, wave_height_m / RISK_SATURATION_WAVE_M)


def fuel_rate_for_vessel(vessel: VesselProfile) -> float:
    if vessel.fuel_rate_ton_per_hr:
        return vessel.fuel_rate_ton_per_hr
    return DEFAULT_FUEL_RATE_TON_PER_HR.get(vessel.vessel_type, 3.2)


def edge_cost(
    lat1: float, lon1: float, lat2: float, lon2: float,
    vessel: VesselProfile, weather: WeatherField, strategy: RouteStrategy,
) -> EdgeCost:
    distance_nm = haversine_nm(lat1, lon1, lat2, lon2)
    speed = vessel.cruise_speed_knots
    time_hr = distance_nm / speed if speed > 0 else float("inf")

    mid_lat, mid_lon = (lat1 + lat2) / 2, (lon1 + lon2) / 2
    w = weather.at(mid_lat, mid_lon)
    wave_m = w.get("wave_height_m", 0.0)

    base_fuel_rate = fuel_rate_for_vessel(vessel)
    fuel_tons = base_fuel_rate * time_hr * (1 + FUEL_WAVE_PENALTY_PER_M * wave_m)

    risk = wave_risk_score(wave_m)

    weights = STRATEGY_WEIGHTS[strategy]
    # normalise each component to a comparable ~0-1-ish scale before blending
    total = (
        weights["time"] * time_hr
        + weights["fuel"] * fuel_tons
        + weights["risk"] * risk * 50  # scaled so risk meaningfully influences path choice
    )
    return EdgeCost(total=total, time_hr=time_hr, fuel_tons=fuel_tons, risk=risk)
