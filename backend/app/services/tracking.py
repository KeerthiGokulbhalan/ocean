"""
Live vessel tracking service.

Sits between the AIS provider and the API layer and owns three jobs:

  1. **Throttled persistence** — position fixes arrive every few seconds, but
     only one row per POSITION_PERSIST_INTERVAL_S is written, so the track is
     reviewable without unbounded database growth.

  2. **Live conditions** — reuses the existing `fetch_marine_point` weather
     service and the existing `wave_risk_score` cost model. No second weather
     system and no second risk model are introduced here.

  3. **Live alerts** — when the vessel's current position exceeds the
     configured wave threshold, raises a StormWarning through the existing
     Alert table, with a cooldown so a vessel inside a storm cell does not
     flood the alert feed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import (
    LIVE_ALERT_COOLDOWN_S,
    LIVE_ALERT_WAVE_HEIGHT_M,
    MAX_TRACK_POINTS,
    POSITION_PERSIST_INTERVAL_S,
)
from app.db.models import Alert, VesselPosition
from app.routing.cost import wave_risk_score
from app.services.ais.base import VesselFix
from app.services.weather import fetch_marine_point

logger = logging.getLogger("seapath.tracking")

# Wind speed (km/h) mapped onto the same 0-1 scale used for wave risk.
WIND_RISK_SATURATION_KMH = 90.0


def _as_naive_utc(dt: datetime) -> datetime:
    """The existing models store naive UTC datetimes; normalise before write."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def persist_fix(db: Session, fix: VesselFix, force: bool = False) -> VesselPosition | None:
    """Write a fix to the track, honouring the persistence interval.

    Returns the created row, or None when the fix was throttled away.
    A terminal fix (ARRIVED) is always written so tracks end cleanly.
    """
    now = _as_naive_utc(fix.timestamp)

    if not force and fix.status != "ARRIVED":
        latest = (
            db.query(VesselPosition)
            .filter(VesselPosition.vessel_id == fix.vessel_id)
            .order_by(VesselPosition.timestamp.desc())
            .first()
        )
        if latest and latest.timestamp is not None:
            age_s = (now - latest.timestamp).total_seconds()
            if age_s < POSITION_PERSIST_INTERVAL_S:
                return None

    row = VesselPosition(
        vessel_id=fix.vessel_id,
        voyage_id=fix.voyage_id,
        latitude=fix.latitude,
        longitude=fix.longitude,
        speed_knots=fix.speed_knots,
        heading_deg=fix.heading_deg,
        status=fix.status,
        source=fix.source,
        timestamp=now,
        distance_remaining_nm=fix.distance_remaining_nm,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_track(
    db: Session, vessel_id: int, voyage_id: int | None = None, limit: int | None = None
) -> list[VesselPosition]:
    """Historical positions, oldest first, capped at MAX_TRACK_POINTS."""
    limit = min(limit or MAX_TRACK_POINTS, MAX_TRACK_POINTS)
    query = db.query(VesselPosition).filter(VesselPosition.vessel_id == vessel_id)
    if voyage_id is not None:
        query = query.filter(VesselPosition.voyage_id == voyage_id)

    # take the newest `limit` rows, then flip so the polyline draws forward
    rows = query.order_by(VesselPosition.timestamp.desc()).limit(limit).all()
    return list(reversed(rows))


async def live_conditions(lat: float, lon: float) -> dict:
    """Weather + risk at the vessel's current position.

    Reuses the existing Open-Meteo client and the existing wave risk model,
    so live-tracking risk is consistent with route-planning risk.
    """
    weather = await fetch_marine_point(lat, lon)

    wave_m = weather.get("wave_height_m") or 0.0
    wind_kmh = weather.get("wind_speed_kmh") or 0.0

    wave_risk = wave_risk_score(wave_m)
    wind_risk = min(1.0, wind_kmh / WIND_RISK_SATURATION_KMH)
    overall = max(wave_risk, wind_risk)

    return {
        "weather": weather,
        "wave_risk": round(wave_risk, 2),
        "wind_risk": round(wind_risk, 2),
        "overall_risk": round(overall, 2),
        "wave_risk_label": _risk_label(wave_risk),
        "wind_risk_label": _risk_label(wind_risk),
        "overall_risk_label": _risk_label(overall),
    }


def _risk_label(risk: float) -> str:
    if risk >= 0.66:
        return "High"
    if risk >= 0.33:
        return "Moderate"
    return "Low"


def maybe_raise_live_alert(
    db: Session, voyage_id: int | None, conditions: dict, lat: float, lon: float
) -> Alert | None:
    """Raise a StormWarning if the vessel is in dangerous live conditions.

    Uses the existing Alert model and StormWarning type rather than inventing
    a parallel alerting mechanism.
    """
    if voyage_id is None:
        return None

    wave_m = conditions.get("weather", {}).get("wave_height_m") or 0.0
    if wave_m < LIVE_ALERT_WAVE_HEIGHT_M:
        return None

    cutoff = datetime.utcnow() - timedelta(seconds=LIVE_ALERT_COOLDOWN_S)
    recent = (
        db.query(Alert)
        .filter(
            Alert.voyage_id == voyage_id,
            Alert.type == "StormWarning",
            Alert.created_at >= cutoff,
        )
        .first()
    )
    if recent:
        return None

    alert = Alert(
        voyage_id=voyage_id,
        type="StormWarning",
        message=(
            f"Vessel on voyage #{voyage_id} is in heavy seas at "
            f"{lat:.2f}, {lon:.2f} — significant wave height {wave_m:.1f} m "
            f"(overall risk {conditions.get('overall_risk_label', 'High')})."
        ),
        status="Unread",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    logger.info("Raised live StormWarning for voyage %s", voyage_id)
    return alert
