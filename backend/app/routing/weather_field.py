"""
Samples marine weather (wave height, wind speed) at a coarse set of points
across the routing bounding box, then serves nearest-neighbour lookups so
the A* search doesn't need one HTTP call per grid node.
"""
import math

from app.services.weather import fetch_marine_point


class WeatherField:
    def __init__(self, samples: list[dict]):
        # each sample: {"lat", "lon", "wave_height_m", "wind_speed_kmh"}
        self.samples = samples

    def at(self, lat: float, lon: float) -> dict:
        if not self.samples:
            return {"wave_height_m": 0.0, "wind_speed_kmh": 0.0}
        best, best_d = None, math.inf
        for s in self.samples:
            d = (s["lat"] - lat) ** 2 + (s["lon"] - lon) ** 2
            if d < best_d:
                best, best_d = s, d
        return best

    @classmethod
    async def build(cls, min_lat, max_lat, min_lon, max_lon, n_samples_per_axis=4):
        """Fetch a sparse n x n grid of weather samples across the bbox, concurrently."""
        import asyncio

        lat_step = (max_lat - min_lat) / max(1, n_samples_per_axis - 1)
        lon_step = (max_lon - min_lon) / max(1, n_samples_per_axis - 1)

        points = [
            (min_lat + i * lat_step, min_lon + j * lon_step)
            for i in range(n_samples_per_axis)
            for j in range(n_samples_per_axis)
        ]

        results = await asyncio.gather(
            *(fetch_marine_point(lat, lon) for lat, lon in points)
        )
        samples = [{"lat": lat, "lon": lon, **data} for (lat, lon), data in zip(points, results)]
        return cls(samples)

    @classmethod
    def empty(cls):
        return cls(samples=[])
