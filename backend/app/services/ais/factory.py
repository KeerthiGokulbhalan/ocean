"""
Chooses the AIS provider implementation from configuration.

Swapping the demo simulator for a real feed is an environment change, not a
code change:

    AIS_PROVIDER=mock   # default — simulated positions, clearly labelled
    AIS_PROVIDER=real       # generic REST feed adapter
    AIS_PROVIDER=aisstream  # AISstream.io WebSocket feed
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.config import AIS_PROVIDER
from app.services.ais.base import AISProvider
from app.services.ais.mock_provider import MockAISProvider
from app.services.ais.real_provider import RealAISProvider
from app.services.ais.aisstream_provider import AISStreamProvider

logger = logging.getLogger("seapath.ais")

_PROVIDERS: dict[str, type[AISProvider]] = {
    "mock": MockAISProvider,
    "real": RealAISProvider,
    "aisstream": AISStreamProvider,
}


@lru_cache(maxsize=1)
def get_ais_provider() -> AISProvider:
    """Process-wide singleton for the configured provider."""
    provider_cls = _PROVIDERS.get(AIS_PROVIDER)
    if provider_cls is None:
        logger.warning(
            "Unknown AIS_PROVIDER=%r — falling back to the mock provider. "
            "Valid values: %s",
            AIS_PROVIDER, ", ".join(_PROVIDERS),
        )
        provider_cls = MockAISProvider
    provider = provider_cls()
    logger.info("AIS provider initialised: %s", provider.name)
    return provider


def reset_ais_provider() -> None:
    """Clear the cached singleton. Used by tests that swap providers."""
    get_ais_provider.cache_clear()
