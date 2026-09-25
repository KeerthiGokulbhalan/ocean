from app.routing.cost import wave_risk_score
from app.routing.geo import haversine_nm
from app.routing.grid import build_grid_for_voyage
from app.routing.pathfinding import NoRouteFoundError, astar_route
from app.routing.weather_field import WeatherField
from app.schemas import Coordinate, RouteOption, RoutePoint, RouteRequest, RouteResponse
from app.services.emissions import co2_tons_from_fuel, sustainability_score
from app.services.fuel_model import fuel_predictor

STRATEGIES = ["fastest", "efficient", "safest"]


# Progressively widen the search box if the straight-line corridor is
# blocked by a landmass (e.g. two ports on opposite coasts of a
# subcontinent, which requires routing around its southern tip).
MARGIN_STEPS_DEG = [3.0, 8.0, 15.0, 25.0]


async def plan_routes(req: RouteRequest) -> RouteResponse:
    warnings: list[str] = []
    options: list[RouteOption] = []
    weather = None
    grid = None

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
                warnings.append("Live weather data unavailable — routed using calm-sea defaults.")
                weather = WeatherField.empty()

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

            # blend the physics-based estimate with the ML predictor for a
            # more realistic figure (see services/fuel_model.py)
            avg_wave = _average_wave(latlon_path, weather)
            ml_fuel_tons = fuel_predictor.predict(
                speed_knots=req.vessel.cruise_speed_knots,
                distance_nm=distance_nm,
                wave_height_m=avg_wave,
                vessel_type=req.vessel.vessel_type,
            )
            fuel_tons = round((physics_fuel_tons + ml_fuel_tons) / 2, 2)
            co2_tons = round(co2_tons_from_fuel(fuel_tons), 2)

            # per-point risk score — powers the risk-radar heatmap overlay
            risk_segments = [
                round(wave_risk_score(weather.at(lat, lon).get("wave_height_m", 0.0)), 2)
                for lat, lon in latlon_path
            ]

            options.append(
                RouteOption(
                    strategy=strategy,
                    points=[RoutePoint(lat=lat, lon=lon) for lat, lon in latlon_path],
                    risk_segments=risk_segments,
                    distance_nm=round(distance_nm, 1),
                    duration_hr=round(time_hr, 1),
                    fuel_tons=fuel_tons,
                    co2_tons=co2_tons,
                    risk_score=round(risk, 2),
                    sustainability_score=sustainability_score(fuel_tons, distance_nm),
                )
            )

        if any_found:
            break  # got at least one usable route — no need to widen further

        if attempt == len(MARGIN_STEPS_DEG) - 1:
            warnings.append(
                "No navigable route found even after widening the search area. "
                "The origin/destination may be inland or too far from open water."
            )
        else:
            warnings.append(
                f"Search area widened to {MARGIN_STEPS_DEG[attempt + 1]}\u00b0 margin "
                "to route around a landmass."
            )

    return RouteResponse(
        origin=req.origin,
        destination=req.destination,
        vessel=req.vessel,
        options=options,
        warnings=warnings,
    )


def _path_distance(latlon_path: list[tuple[float, float]]) -> float:
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(latlon_path, latlon_path[1:]):
        total += haversine_nm(lat1, lon1, lat2, lon2)
    return total


def _average_wave(latlon_path, weather: WeatherField) -> float:
    if not latlon_path:
        return 0.0
    sample = latlon_path[:: max(1, len(latlon_path) // 20)]  # cap samples for speed
    heights = [weather.at(lat, lon).get("wave_height_m", 0.0) for lat, lon in sample]
    return sum(heights) / len(heights) if heights else 0.0
