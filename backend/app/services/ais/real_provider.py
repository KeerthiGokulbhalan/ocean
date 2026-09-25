"""
RealAISProvider — adapter for a commercial AIS feed.

Deliberately NOT wired to any specific vendor, because AIS feeds are paid
services with differing schemas. What is fixed here is the contract: whatever
the upstream returns must be normalised into `VesselFix` objects tagged
`source="ais"`.

To enable:

    AIS_PROVIDER=real
    AIS_API_URL=https://<vendor>/v1/vessels
    AIS_API_KEY=<key>          # from the environment, never committed

Then implement `_parse_vessel` for the vendor's payload shape and map your
SeaPath vessel IDs to MMSI/IMO numbers (add an `mmsi` column to the Vessel
model — the rest of the tracking stack needs no changes).

Until that mapping exists this provider returns nothing rather than
fabricating positions. Failing closed is intentional: a silent fallback to
simulated data presented as real AIS would be worse than an empty feed.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import AIS_API_KEY, AIS_API_URL
from app.services.ais.base import AISProvider, VesselFix

logger = logging.getLogger("seapath.ais")


class RealAISProvider(AISProvider):
    name = "real"
    simulated = False

    def __init__(self, api_url: str | None = None, api_key: str | None = None):
        self.api_url = api_url or AIS_API_URL
        self.api_key = api_key or AIS_API_KEY
        if not self.api_url or not self.api_key:
            logger.warning(
                "AIS_PROVIDER=real but AIS_API_URL/AIS_API_KEY are not set. "
                "The live feed will return no positions until they are configured."
            )

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.api_key)

    def _request(self, params: dict) -> Optional[dict]:
        if not self.configured:
            return None
        try:
            resp = httpx.get(
                self.api_url,
                params=params,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=6.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            # Upstream outages must degrade to "no fix", never crash tracking.
            logger.warning("AIS upstream request failed: %s", exc)
            return None

    def _parse_vessel(self, payload: dict) -> Optional[VesselFix]:
        """Vendor-specific normalisation. Implement for your AIS provider."""
        raise NotImplementedError(
            "Map your AIS vendor's payload to VesselFix here."
        )

    def get_vessel_position(self, vessel_id: int) -> Optional[VesselFix]:
        data = self._request({"vessel_id": vessel_id})
        if not data:
            return None
        try:
            return self._parse_vessel(data)
        except NotImplementedError:
            logger.warning(
                "RealAISProvider._parse_vessel is not implemented — "
                "returning no position rather than fabricating one."
            )
            return None

    def get_vessels(self) -> list[VesselFix]:
        data = self._request({})
        if not data:
            return []
        fixes = []
        for item in data.get("vessels", []):
            try:
                fix = self._parse_vessel(item)
            except NotImplementedError:
                return []
            if fix:
                fixes.append(fix)
        return fixes

    def describe(self) -> dict:
        return {
            "provider": self.name,
            "simulated": False,
            "label": "LIVE TRACKING — AIS",
            "detail": "Positions sourced from a commercial AIS feed.",
            "configured": self.configured,
        }
