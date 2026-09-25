"""AISstream.io WebSocket adapter, normalized to SeaPath VesselFix objects."""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from app.config import AIS_API_KEY, AIS_API_URL, AISSTREAM_STALE_SECONDS
from app.db.session import SessionLocal
from app.services.ais.base import AISProvider, VesselFix

logger = logging.getLogger("seapath.ais.aisstream")


class AISStreamProvider(AISProvider):
    """Maintains one server-side AISstream subscription for MMSIs in the fleet."""

    name = "aisstream"
    simulated = False

    def __init__(self, api_url: str | None = None, api_key: str | None = None):
        self.api_url = api_url or AIS_API_URL or "wss://stream.aisstream.io/v0/stream"
        self.api_key = api_key or AIS_API_KEY
        self._fixes: dict[int, VesselFix] = {}
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()
        if not self.api_key:
            logger.warning("AISstream selected but AIS_API_KEY is not configured")

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.api_key)

    def _vessel_map(self) -> dict[str, tuple[int, int | None]]:
        """Return MMSI -> SeaPath vessel ID from the existing fleet table."""
        from app.db.models import Vessel, Voyage

        db = SessionLocal()
        try:
            rows = (
                db.query(Vessel.id, Vessel.mmsi, Voyage.id)
                .outerjoin(
                    Voyage,
                    (Voyage.vessel_id == Vessel.id) & (Voyage.status == "In-Progress"),
                )
                .filter(Vessel.mmsi.isnot(None))
                .all()
            )
            return {
                str(mmsi).strip(): (vessel_id, voyage_id)
                for vessel_id, mmsi, voyage_id in rows if mmsi
            }
        finally:
            db.close()

    def _start(self) -> None:
        if not self.configured:
            return
        with self._thread_lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run, name="aisstream-reader", daemon=True
            )
            self._thread.start()

    def _run(self) -> None:
        backoff = 1
        while True:
            mmsi_to_vessel = self._vessel_map()
            if not mmsi_to_vessel:
                time.sleep(15)
                continue
            try:
                from websockets.sync.client import connect

                # AISstream requires a bounding box even when filtering by MMSI.
                # The MMSI filter keeps this subscription limited to this fleet.
                subscription = {
                    "APIKey": self.api_key,
                    "BoundingBoxes": [[[90, -180], [-90, 180]]],
                    "FiltersShipMMSI": list(mmsi_to_vessel.keys())[:200],
                    "FilterMessageTypes": [
                        "PositionReport",
                        "StandardClassBPositionReport",
                        "ExtendedClassBPositionReport",
                    ],
                }
                with connect(
                    self.api_url,
                    compression="deflate",
                    open_timeout=10,
                    close_timeout=3,
                ) as socket:
                    socket.send(json.dumps(subscription))
                    logger.info(
                        "Connected to AISstream for %s configured vessel(s)",
                        min(len(mmsi_to_vessel), 200),
                    )
                    backoff = 1
                    while True:
                        message = socket.recv()
                        if isinstance(message, bytes):
                            message = message.decode("utf-8")
                        backoff = 1
                        self._consume(json.loads(message), mmsi_to_vessel)
            except Exception as exc:
                logger.warning("AISstream connection ended: %s; reconnecting", exc)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def _consume(self, event: dict, mmsi_to_vessel: dict[str, tuple[int, int | None]]) -> None:
        kind = event.get("MessageType")
        if kind not in {
            "PositionReport",
            "StandardClassBPositionReport",
            "ExtendedClassBPositionReport",
        }:
            return
        metadata = event.get("MetaData") or {}
        payload = event.get("Message", {}).get(kind) or {}
        mmsi = str(metadata.get("MMSI") or payload.get("UserID") or "")
        vessel_mapping = mmsi_to_vessel.get(mmsi)
        if vessel_mapping is None or payload.get("Valid") is False:
            return
        vessel_id, voyage_id = vessel_mapping
        if vessel_id is None:
            return
        try:
            raw_latitude = metadata.get("Latitude", payload.get("Latitude"))
            raw_longitude = metadata.get("Longitude", payload.get("Longitude"))
            latitude = float(raw_latitude)
            longitude = float(raw_longitude)
            speed = max(0.0, float(payload.get("Sog") or 0.0))
            raw_heading = payload.get("TrueHeading")
            if raw_heading is None or raw_heading >= 360:
                raw_heading = payload.get("Cog", 0.0)
            heading = float(raw_heading or 0.0)
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                return
            fix = VesselFix(
                vessel_id=vessel_id,
                latitude=latitude,
                longitude=longitude,
                speed_knots=speed,
                heading_deg=heading % 360,
                status="UNDERWAY" if speed >= 0.5 else "STOPPED",
                source="ais",
                timestamp=datetime.now(timezone.utc),
                voyage_id=voyage_id,
            )
        except (KeyError, TypeError, ValueError):
            logger.debug("Ignoring malformed AISstream position for MMSI %s", mmsi)
            return
        with self._lock:
            self._fixes[vessel_id] = fix

    def _fresh_fixes(self) -> list[VesselFix]:
        self._start()
        cutoff = time.time() - AISSTREAM_STALE_SECONDS
        with self._lock:
            return [
                fix for fix in self._fixes.values()
                if fix.timestamp.timestamp() >= cutoff
            ]

    def get_vessel_position(self, vessel_id: int) -> Optional[VesselFix]:
        return next((fix for fix in self._fresh_fixes() if fix.vessel_id == vessel_id), None)

    def get_vessels(self) -> list[VesselFix]:
        return self._fresh_fixes()

    def describe(self) -> dict:
        return {
            "provider": self.name,
            "simulated": False,
            "label": "LIVE TRACKING — AISSTREAM",
            "detail": "Real positions from the AISstream.io feed.",
            "configured": self.configured,
        }
