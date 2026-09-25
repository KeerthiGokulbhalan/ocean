"""
Land/ocean classification.

Uses the `global-land-mask` package, which ships a bundled low-resolution
raster and needs no network access or external dataset download. This keeps
the whole project runnable offline out of the box.

For higher-fidelity coastlines in production, swap `is_ocean()` for a lookup
against GSHHG / Natural Earth polygons loaded into PostGIS.
"""
from functools import lru_cache

from global_land_mask import globe


@lru_cache(maxsize=200_000)
def is_ocean(lat: float, lon: float) -> bool:
    # global_land_mask expects lon in [-180, 180]
    lon_wrapped = ((lon + 180) % 360) - 180
    return not bool(globe.is_land(lat, lon_wrapped))
