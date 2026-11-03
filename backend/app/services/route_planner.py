from app.routing.cost import wave_risk_score
from app.routing.geo import haversine_nm
from app.routing.grid import build_grid_for_voyage
from app.routing.pathfinding import NoRouteFoundError, astar_route
from app.routing.weather_field import WeatherField
from app.schemas import (
    Coordinate,
    RouteOption,
    RoutePoint,
    RouteRequest,
    RouteResponse,
    WeatherRouteAlert,
)
from app.services.emissions import co2_tons_from_fuel, sustainability_score
from app.services.fuel_model import fuel_predictor

STRATEGIES = ["fastest", "efficient", "safest"]

# Weather alert thresholds are operational demo thresholds, not navigation
# limits. A real vessel operator must follow official marine warnings.
WAVE_WARNING_M = 2.5
WAVE_SEVERE_M = 4.0
WIND_WARNING_KMH = 45.0
WIND_SEVERE_KMH = 65.0

MARGIN_STEPS_DEG = [3.0, 8.0, 15.0, 25.0]


async def plan_routes(req: RouteRequest) -> RouteResponse:
    warnings: list[str] = []
    options: list[RouteOption] = []
    weather = None

    for attempt, margin in enumerate(MARGIN_STEPS_DEG):
        grid = build_grid_for_voyage(
            req.origin.lat, req.origin.lon, req.destination.lat, req.destination.lon,
            margin_deg=margin,
        )
        start = grid.nearest_navigable(req.origin.lat, req.origin.lon)
        goal = grid.nearest_navigable(req.destination.lat, req.destination.lon)

        if weather is None:
            try:
                weather = await WeatherField.build(
                    grid.min_lat, grid.max_lat, grid.min_lon, grid.max_lon
                )
            except Exception:
                warnings.append("Weather provider unavailable — route weather alerts are disabled.")
                weather = WeatherField.empty()

        if not weather.data_available:
            warnings.append(
                "Marine weather data is unavailable. Calm defaults were used for route planning; "
                "no weather segment is being described as safe."
            )

        options = []
        any_found = False

        for strategy in STRATEGIES:
            try:
                latlon_path, time_hr, physics_fuel_tons, risk = astar_route(
                    grid, start, goal, req.vessel, weather, strategy
                )
            except NoRouteFoundError:
                continue

            any_found = True
            distance_nm = _path_distance(latlon_path)
            avg_wave = _average_wave(latlon_path, weather)
            ml_fuel_tons = fuel_predictor.predict(
                speed_knots=req.vessel.cruise_speed_knots,
                distance_nm=distance_nm,
                wave_height_m=avg_wave,
                vessel_type=req.vessel.vessel_type,
            )
            fuel_tons = round((physics_fuel_tons + ml_fuel_tons) / 2, 2)
            co2_tons = round(co2_tons_from_fuel(fuel_tons), 2)

            risk_segments = []
            for lat, lon in latlon_path:
                conditions = weather.at(lat, lon)
                if not conditions.get("data_available", False):
                    # -1 is a map-only "no sample" value, not a risk score.
                    risk_segments.append(-1.0)
                    continue
                wave_risk = wave_risk_score(conditions.get("wave_height_m", 0.0))
                wind_risk = min(1.0, (conditions.get("wind_speed_kmh") or 0.0) / 90.0)
                risk_segments.append(round(max(wave_risk, wind_risk), 2))

            weather_alerts = _weather_alerts(latlon_path, weather) if weather.data_available else []
            options.append(
                RouteOption(
                    strategy=strategy,
                    points=[RoutePoint(lat=lat, lon=lon) for lat, lon in latlon_path],
                    risk_segments=risk_segments,
                    weather_data_available=weather.data_available,
                    weather_coverage_percent=weather.coverage_percent,
                    weather_alerts=weather_alerts,
                    distance_nm=round(distance_nm, 1),
                    duration_hr=round(time_hr, 1),
                    fuel_tons=fuel_tons,
                    co2_tons=co2_tons,
                    risk_score=round(max([risk, *risk_segments]), 2),
                    sustainability_score=sustainability_score(fuel_tons, distance_nm),
                )
            )

        if any_found:
            break

        if attempt == len(MARGIN_STEPS_DEG) - 1:
            warnings.append(
                "No navigable route found even after widening the search area. "
                "The origin/destination may be inland or too far from open water."
            )
        else:
            warnings.append(
                f"Search area widened to {MARGIN_STEPS_DEG[attempt + 1]}° margin "
                "to route around a landmass."
            )

    return RouteResponse(
        origin=req.origin,
        destination=req.destination,
        vessel=req.vessel,
        options=options,
        warnings=warnings,
    )


def _weather_alerts(
    latlon_path: list[tuple[float, float]], weather: WeatherField
) -> list[WeatherRouteAlert]:
    alerts: list[WeatherRouteAlert] = []
    for index, ((lat1, lon1), (lat2, lon2)) in enumerate(zip(latlon_path, latlon_path[1:])):
        mid_lat = (lat1 + lat2) / 2
        mid_lon = (lon1 + lon2) / 2
        conditions = weather.at(mid_lat, mid_lon)
        if not conditions.get("data_available", False):
            continue
        wave = float(conditions.get("wave_height_m") or 0.0)
        wind = float(conditions.get("wind_speed_kmh") or 0.0)

        severe = wave >= WAVE_SEVERE_M or wind >= WIND_SEVERE_KMH
        warning = wave >= WAVE_WARNING_M or wind >= WIND_WARNING_KMH
        if not warning:
            continue

        severity = "severe" if severe else "warning"
        factors = []
        if wave >= WAVE_WARNING_M:
            factors.append(f"waves {wave:.1f} m")
        if wind >= WIND_WARNING_KMH:
            factors.append(f"wind {wind:.0f} km/h")
        alerts.append(
            WeatherRouteAlert(
                segment_index=index,
                start=Coordinate(lat=lat1, lon=lon1),
                end=Coordinate(lat=lat2, lon=lon2),
                midpoint=Coordinate(lat=mid_lat, lon=mid_lon),
                wave_height_m=round(wave, 2),
                wind_speed_kmh=round(wind, 1),
                severity=severity,
                message=f"{severity.title()} weather on route segment {index + 1}: " + " and ".join(factors),
            )
        )
    return alerts


def _path_distance(latlon_path: list[tuple[float, float]]) -> float:
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(latlon_path, latlon_path[1:]):
        total += haversine_nm(lat1, lon1, lat2, lon2)
    return total


def _average_wave(latlon_path, weather: WeatherField) -> float:
    if not latlon_path:
        return 0.0
    sample = latlon_path[:: max(1, len(latlon_path) // 20)]
    heights = [weather.at(lat, lon).get("wave_height_m", 0.0) for lat, lon in sample]
    return sum(heights) / len(heights) if heights else 0.0
