"""
Builds a rectangular lat/lon grid spanning the origin and destination
(plus a margin so the search can route around coastlines), and marks
each node navigable or not using the land mask.
"""
from dataclasses import dataclass

from app.config import GRID_RESOLUTION_DEG
from app.routing.landmask import is_ocean


@dataclass(frozen=True)
class GridNode:
    i: int
    j: int
    lat: float
    lon: float


class NavigableGrid:
    def __init__(self, min_lat, max_lat, min_lon, max_lon, resolution=GRID_RESOLUTION_DEG):
        self.min_lat = min_lat
        self.max_lat = max_lat
        self.min_lon = min_lon
        self.max_lon = max_lon
        self.res = resolution

        self.n_rows = max(2, int((max_lat - min_lat) / resolution) + 1)
        self.n_cols = max(2, int((max_lon - min_lon) / resolution) + 1)

        # lazily-evaluated ocean/land cache: (i, j) -> bool
        self._navigable_cache: dict[tuple[int, int], bool] = {}

    def latlon_to_index(self, lat: float, lon: float) -> tuple[int, int]:
        i = round((lat - self.min_lat) / self.res)
        j = round((lon - self.min_lon) / self.res)
        i = min(max(i, 0), self.n_rows - 1)
        j = min(max(j, 0), self.n_cols - 1)
        return i, j

    def index_to_latlon(self, i: int, j: int) -> tuple[float, float]:
        return self.min_lat + i * self.res, self.min_lon + j * self.res

    def in_bounds(self, i: int, j: int) -> bool:
        return 0 <= i < self.n_rows and 0 <= j < self.n_cols

    def is_navigable(self, i: int, j: int) -> bool:
        key = (i, j)
        if key not in self._navigable_cache:
            lat, lon = self.index_to_latlon(i, j)
            self._navigable_cache[key] = is_ocean(round(lat, 2), round(lon, 2))
        return self._navigable_cache[key]
    def block_radius(self, lat: float, lon: float, radius_deg: float) -> None:
        """Mark every cell within `radius_deg` of (lat, lon) as non-navigable.

        Used to inject a simulated obstacle (blocked passage / restricted
        zone) into an otherwise-normal ocean grid so A* is forced to route
        around it. Overwrites whatever the land mask previously said for
        those cells — this only ever removes navigability, never adds it.
        """
        i0, j0 = self.latlon_to_index(lat, lon)
        ring = max(1, int(radius_deg / self.res) + 1)
        for di in range(-ring, ring + 1):
            for dj in range(-ring, ring + 1):
                i, j = i0 + di, j0 + dj
                if not self.in_bounds(i, j):
                    continue
                clat, clon = self.index_to_latlon(i, j)
                if (clat - lat) ** 2 + (clon - lon) ** 2 <= radius_deg ** 2:
                    self._navigable_cache[(i, j)] = False

    def nearest_navigable(self, lat: float, lon: float, max_ring: int = 6) -> tuple[int, int]:
        """If the requested point lands on a grid cell classified as land
        (common for ports right on the coast), spiral outward to the
        nearest navigable cell."""
        i0, j0 = self.latlon_to_index(lat, lon)
        if self.is_navigable(i0, j0):
            return i0, j0
        for ring in range(1, max_ring + 1):
            for di in range(-ring, ring + 1):
                for dj in range(-ring, ring + 1):
                    if max(abs(di), abs(dj)) != ring:
                        continue
                    i, j = i0 + di, j0 + dj
                    if self.in_bounds(i, j) and self.is_navigable(i, j):
                        return i, j
        # fall back to the original cell if nothing navigable was found nearby
        return i0, j0


def build_grid_for_voyage(origin_lat, origin_lon, dest_lat, dest_lon, margin_deg=3.0) -> NavigableGrid:
    min_lat = min(origin_lat, dest_lat) - margin_deg
    max_lat = max(origin_lat, dest_lat) + margin_deg
    min_lon = min(origin_lon, dest_lon) - margin_deg
    max_lon = max(origin_lon, dest_lon) + margin_deg
    return NavigableGrid(min_lat, max_lat, min_lon, max_lon)
