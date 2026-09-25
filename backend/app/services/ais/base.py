"""
AIS provider abstraction.

SeaPath reads live vessel positions through this interface so that the
simulated demo feed and a real commercial AIS feed are interchangeable. The
concrete provider is chosen at startup from the AIS_PROVIDER environment
variable (see app/services/ais/factory.py).

Design rule enforced throughout: a position always carries `source` and
`is_simulated`. Simulated positions are never presented as real AIS data —
the API returns the flag and the UI renders a "DEMO SIMULATION" badge.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

PositionSource = Literal["simulated", "ais", "manual"]
VesselStatus = Literal["UNDERWAY", "MOORED", "STOPPED", "ARRIVED", "UNKNOWN"]


@dataclass
class VesselFix:
    """One position report — the common currency between every provider."""

    vessel_id: int
    latitude: float
    longitude: float
    speed_knots: float = 0.0
    heading_deg: float = 0.0
    status: VesselStatus = "UNDERWAY"
    source: PositionSource = "simulated"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    voyage_id: Optional[int] = None

    # progress along the active voyage, when the provider can determine it
    distance_travelled_nm: Optional[float] = None
    distance_remaining_nm: Optional[float] = None
    progress_percent: Optional[float] = None
    eta: Optional[datetime] = None

    @property
    def is_simulated(self) -> bool:
        return self.source == "simulated"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["eta"] = self.eta.isoformat() if self.eta else None
        data["is_simulated"] = self.is_simulated
        return data


class AISProvider(ABC):
    """Interface every position source must implement."""

    #: Human-readable name surfaced in the API so clients can label the feed.
    name: str = "abstract"

    #: Whether fixes from this provider are simulated rather than real AIS.
    simulated: bool = True

    @abstractmethod
    def get_vessel_position(self, vessel_id: int) -> Optional[VesselFix]:
        """Latest known fix for one vessel, or None if the provider has none."""

    @abstractmethod
    def get_vessels(self) -> list[VesselFix]:
        """Latest known fix for every vessel this provider is tracking."""

    def describe(self) -> dict:
        """Metadata for the /api/tracking/status endpoint."""
        return {"provider": self.name, "simulated": self.simulated}
