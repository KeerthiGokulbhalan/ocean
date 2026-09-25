import heapq

from app.config import NEIGHBOR_OFFSETS
from app.routing.cost import edge_cost
from app.routing.geo import haversine_nm
from app.routing.grid import NavigableGrid
from app.routing.weather_field import WeatherField
from app.schemas import RouteStrategy, VesselProfile


class NoRouteFoundError(Exception):
    pass


def astar_route(
    grid: NavigableGrid,
    start: tuple[int, int],
    goal: tuple[int, int],
    vessel: VesselProfile,
    weather: WeatherField,
    strategy: RouteStrategy,
):
    """Returns (path_latlon, total_time_hr, total_fuel_tons, avg_risk)."""

    def heuristic(i, j):
        lat1, lon1 = grid.index_to_latlon(i, j)
        lat2, lon2 = grid.index_to_latlon(*goal)
        # nm -> hours at cruise speed, a consistent under-estimate for A*
        return haversine_nm(lat1, lon1, lat2, lon2) / vessel.cruise_speed_knots

    open_set = [(0.0, start)]
    came_from: dict = {}
    g_score = {start: 0.0}
    time_acc = {start: 0.0}
    fuel_acc = {start: 0.0}
    risk_acc = {start: 0.0}
    visited = set()

    max_iterations = 200_000
    iterations = 0

    while open_set:
        iterations += 1
        if iterations > max_iterations:
            raise NoRouteFoundError("Search exceeded iteration budget")

        _, current = heapq.heappop(open_set)
        if current in visited:
            continue
        visited.add(current)

        if current == goal:
            return _reconstruct(came_from, current, grid, time_acc, fuel_acc, risk_acc)

        ci, cj = current
        clat, clon = grid.index_to_latlon(ci, cj)

        for di, dj in NEIGHBOR_OFFSETS:
            ni, nj = ci + di, cj + dj
            if not grid.in_bounds(ni, nj) or (ni, nj) in visited:
                continue
            if not grid.is_navigable(ni, nj):
                continue

            nlat, nlon = grid.index_to_latlon(ni, nj)
            ec = edge_cost(clat, clon, nlat, nlon, vessel, weather, strategy)

            tentative_g = g_score[current] + ec.total
            if tentative_g < g_score.get((ni, nj), float("inf")):
                came_from[(ni, nj)] = current
                g_score[(ni, nj)] = tentative_g
                time_acc[(ni, nj)] = time_acc[current] + ec.time_hr
                fuel_acc[(ni, nj)] = fuel_acc[current] + ec.fuel_tons
                risk_acc[(ni, nj)] = max(risk_acc[current], ec.risk)
                f_score = tentative_g + heuristic(ni, nj)
                heapq.heappush(open_set, (f_score, (ni, nj)))

    raise NoRouteFoundError("No navigable path found between origin and destination")


def _reconstruct(came_from, current, grid, time_acc, fuel_acc, risk_acc):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()

    latlon_path = [grid.index_to_latlon(i, j) for i, j in path]
    end = path[-1]
    return latlon_path, time_acc[end], fuel_acc[end], risk_acc[end]
