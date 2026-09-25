"""Pluggable AIS / vessel-position providers."""

from app.services.ais.base import AISProvider, VesselFix
from app.services.ais.factory import get_ais_provider, reset_ais_provider
from app.services.ais.aisstream_provider import AISStreamProvider
from app.services.ais.mock_provider import MockAISProvider
from app.services.ais.real_provider import RealAISProvider

__all__ = [
    "AISProvider",
    "VesselFix",
    "MockAISProvider",
    "RealAISProvider",
    "AISStreamProvider",
    "get_ais_provider",
    "reset_ais_provider",
]
