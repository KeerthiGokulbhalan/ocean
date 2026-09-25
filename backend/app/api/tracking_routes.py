"""
Live vessel tracking API.

Every endpoint here is scoped to the authenticated user's own fleet: a vessel
or voyage belonging to someone else returns 404 (not 403) so the API does not
leak which IDs exist.

Transport: a WebSocket at /ws/vessels/{vessel_id}/location pushes fixes at
LOCATION_UPDATE_INTERVAL seconds. Clients that cannot hold a socket open fall
back to polling GET /api/vessels/{vessel_id}/location on the same interval —
both paths return the identical payload shape.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import ENABLE_LIVE_TRACKING, LOCATION_UPDATE_INTERVAL
from app.db.models import User, Vessel, Voyage
from app.db.session import SessionLocal, get_db
from app.schemas import (
    Coordinate,
    RoutePoint,
    LiveConditions,
    SimulationControl,
    TrackingStatus,
    VesselPositionIn,
    VesselPositionOut,
    VesselTrackResponse,
    TrackPoint,
    VoyageTracking,
    WeatherPoint,
)
from app.security import decode_access_token
from app.services.ais import get_ais_provider
from app.services.simulation import ALLOWED_SPEED_MULTIPLIERS, simulation_registry
from app.services.tracking import (
    get_track,
    live_conditions,
    maybe_raise_live_alert,
    persist_fix,
)

logger = logging.getLogger("seapath.tracking.api")

router = APIRouter(tags=["tracking"])


# --- helpers ---------------------------------------------------------------
def _require_tracking_enabled() -> None:
    if not ENABLE_LIVE_TRACKING:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live tracking is disabled on this deployment.",
        )


def _owned_vessel(db: Session, vessel_id: int, user: User) -> Vessel:
    vessel = db.query(Vessel).get(vessel_id)
    if not vessel or vessel.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return vessel


def _owned_voyage(db: Session, voyage_id: int, user: User) -> Voyage:
    voyage = db.query(Voyage).get(voyage_id)
    if not voyage or voyage.created_by != user.id:
        raise HTTPException(status_code=404, detail="Voyage not found")
    return voyage


def _fix_to_out(fix) -> VesselPositionOut:
    return VesselPositionOut(**fix.to_dict())


# --- status ----------------------------------------------------------------
@router.get("/api/tracking/status", response_model=TrackingStatus)
def tracking_status():
    """What feed is active and whether it is simulated.

    The frontend uses this to render the honest provenance badge — it never
    assumes positions are real AIS data.
    """
    provider = get_ais_provider()
    info = provider.describe()
    return TrackingStatus(
        enabled=ENABLE_LIVE_TRACKING,
        provider=info.get("provider", "unknown"),
        simulated=info.get("simulated", True),
        label=info.get("label", "LIVE TRACKING"),
        detail=info.get("detail", ""),
        update_interval_s=LOCATION_UPDATE_INTERVAL,
    )


# --- vessel position -------------------------------------------------------
@router.get("/api/vessels/{vessel_id}/location", response_model=VesselPositionOut)
def get_vessel_location(
    vessel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Latest position for a vessel. Polling fallback for the WebSocket."""
    _require_tracking_enabled()
    _owned_vessel(db, vessel_id, current_user)

    fix = get_ais_provider().get_vessel_position(vessel_id)
    if not fix:
        raise HTTPException(
            status_code=404,
            detail="No live position for this vessel. Start a voyage simulation first.",
        )

    persist_fix(db, fix)
    return _fix_to_out(fix)


@router.post("/api/vessels/{vessel_id}/location", response_model=VesselPositionOut)
def report_vessel_location(
    vessel_id: int,
    payload: VesselPositionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually report a position (or bridge one in from an external AIS feed).

    Coordinate/speed/heading ranges are enforced by the schema; voyage
    ownership is re-checked here so a caller cannot attach a position to
    someone else's voyage.
    """
    _require_tracking_enabled()
    _owned_vessel(db, vessel_id, current_user)

    if payload.voyage_id is not None:
        _owned_voyage(db, payload.voyage_id, current_user)

    from app.services.ais.base import VesselFix

    fix = VesselFix(
        vessel_id=vessel_id,
        voyage_id=payload.voyage_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed_knots=payload.speed_knots,
        heading_deg=payload.heading_deg,
        status=payload.status,
        source="manual",
        timestamp=payload.timestamp or datetime.now(timezone.utc),
    )
    persist_fix(db, fix, force=True)
    return _fix_to_out(fix)


@router.get("/api/vessels/{vessel_id}/track", response_model=VesselTrackResponse)
def get_vessel_track(
    vessel_id: int,
    voyage_id: int | None = Query(None),
    limit: int | None = Query(None, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Historical breadcrumb trail, oldest first — drawn as a Leaflet polyline."""
    _owned_vessel(db, vessel_id, current_user)
    if voyage_id is not None:
        _owned_voyage(db, voyage_id, current_user)

    rows = get_track(db, vessel_id, voyage_id, limit)
    return VesselTrackResponse(
        vessel_id=vessel_id,
        voyage_id=voyage_id,
        points=[TrackPoint.model_validate(r) for r in rows],
        count=len(rows),
    )


@router.get("/api/vessels/locations", response_model=list[VesselPositionOut])
def get_fleet_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Latest position for every vessel in the user's fleet — powers the
    Fleet dashboard's live columns in a single request."""
    _require_tracking_enabled()
    owned_ids = {
        v.id for v in db.query(Vessel).filter(Vessel.owner_id == current_user.id).all()
    }
    fixes = [f for f in get_ais_provider().get_vessels() if f.vessel_id in owned_ids]
    return [_fix_to_out(f) for f in fixes]


# --- voyage tracking & simulation control ----------------------------------
@router.get("/api/voyages/{voyage_id}/tracking", response_model=VoyageTracking)
async def get_voyage_tracking(
    voyage_id: int,
    include_weather: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full progress snapshot for the voyage-tracking panel.

    Progress figures come from the route geometry via the simulator — never
    from an arbitrary placeholder value.
    """
    _require_tracking_enabled()
    voyage = _owned_voyage(db, voyage_id, current_user)
    sim = simulation_registry.get(voyage_id)

    result = VoyageTracking(
        voyage_id=voyage.id,
        vessel_id=voyage.vessel_id,
        vessel_name=voyage.vessel.name if voyage.vessel else None,
        start_port=voyage.start_port,
        end_port=voyage.end_port,
        status=voyage.status,
        simulation_running=bool(sim and sim.running),
        speed_multiplier=sim.speed_multiplier if sim else 1.0,
    )

    provider = get_ais_provider()
    if not provider.simulated:
        fix = provider.get_vessel_position(voyage.vessel_id)
        if fix:
            fix.voyage_id = voyage.id
            persist_fix(db, fix)
            result.position = _fix_to_out(fix)
            result.status = voyage.status
        return result

    if not sim:
        return result

    fix = sim.to_fix()
    persist_fix(db, fix)

    result.position = _fix_to_out(fix)
    result.total_distance_nm = round(sim.total_nm, 1)
    result.distance_travelled_nm = round(sim.distance_travelled_nm, 1)
    result.distance_remaining_nm = round(
        max(sim.total_nm - sim.distance_travelled_nm, 0.0), 1
    )
    result.progress_percent = sim.progress_percent
    result.eta = sim.eta()
    result.status = "Completed" if sim.finished else voyage.status
    result.hindrance_state = sim.hindrance_state
    if sim.obstacle:
        result.obstacle = Coordinate(lat=sim.obstacle[0], lon=sim.obstacle[1])
    if sim.original_route:
        result.original_route = [RoutePoint(lat=p[0], lon=p[1]) for p in sim.original_route]
    if sim.alternate_route:
        result.alternate_route = [RoutePoint(lat=p[0], lon=p[1]) for p in sim.alternate_route]

    if include_weather:
        try:
            conditions = await live_conditions(fix.latitude, fix.longitude)
            result.conditions = LiveConditions(
                weather=WeatherPoint(
                    lat=fix.latitude, lon=fix.longitude, **conditions["weather"]
                ),
                wave_risk=conditions["wave_risk"],
                wind_risk=conditions["wind_risk"],
                overall_risk=conditions["overall_risk"],
                wave_risk_label=conditions["wave_risk_label"],
                wind_risk_label=conditions["wind_risk_label"],
                overall_risk_label=conditions["overall_risk_label"],
            )
            maybe_raise_live_alert(
                db, voyage.id, conditions, fix.latitude, fix.longitude
            )
        except Exception as exc:
            # weather is supplementary — tracking must survive its outage
            logger.warning("Live conditions unavailable for voyage %s: %s", voyage_id, exc)

    # keep voyage lifecycle in step with the simulation
    if sim.finished and voyage.status != "Completed":
        voyage.status = "Completed"
        db.commit()
    elif sim.running and voyage.status == "Planned":
        voyage.status = "In-Progress"
        db.commit()

    return result


@router.post("/api/voyages/{voyage_id}/tracking", response_model=VoyageTracking)
async def control_voyage_simulation(
    voyage_id: int,
    control: SimulationControl,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start / pause / reset the demo simulation, or change playback speed."""
    _require_tracking_enabled()
    voyage = _owned_voyage(db, voyage_id, current_user)

    sim = simulation_registry.get(voyage_id)
    if not get_ais_provider().simulated:
        if control.action == "start" and voyage.status == "Planned":
            voyage.status = "In-Progress"
            db.commit()
        elif control.action == "reset" and voyage.status != "Planned":
            voyage.status = "Planned"
            db.commit()
        return await get_voyage_tracking(
            voyage_id, include_weather=False, db=db, current_user=current_user
        )

    if sim is None:
        speed = voyage.vessel.cruise_speed_knots if voyage.vessel else 18.0
        try:
            sim = simulation_registry.create(
                voyage_id=voyage.id,
                vessel_id=voyage.vessel_id,
                route_points_json=voyage.route_points_json,
                cruise_speed_knots=speed,
                origin=(voyage.origin_lat, voyage.origin_lon),
                destination=(voyage.dest_lat, voyage.dest_lon),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    if control.action == "start":
        sim.start()
        if voyage.status == "Planned":
            voyage.status = "In-Progress"
            db.commit()
    elif control.action == "pause":
        sim.pause()
    elif control.action == "reset":
        sim.reset()
        if voyage.status != "Planned":
            voyage.status = "Planned"
            db.commit()
    elif control.action == "speed":
        multiplier = control.speed_multiplier or 1.0
        if multiplier not in ALLOWED_SPEED_MULTIPLIERS:
            raise HTTPException(
                status_code=400,
                detail=f"speed_multiplier must be one of {list(ALLOWED_SPEED_MULTIPLIERS)}",
            )
        sim.set_speed_multiplier(multiplier)

    return await get_voyage_tracking(
        voyage_id, include_weather=False, db=db, current_user=current_user
    )


# --- WebSocket -------------------------------------------------------------
def _authenticate_ws(token: str | None, db: Session) -> User | None:
    """Browsers cannot set Authorization headers on a WebSocket handshake, so
    the JWT arrives as a query parameter instead. Same token, same signature
    check as the REST dependency."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    return db.query(User).get(int(payload["sub"]))


@router.websocket("/ws/vessels/{vessel_id}/location")
async def vessel_location_socket(
    websocket: WebSocket,
    vessel_id: int,
    token: str | None = Query(None),
):
    """Push position fixes for one vessel every LOCATION_UPDATE_INTERVAL seconds.

    Closes with 1008 (policy violation) on an invalid token or a vessel the
    caller does not own, so the client can distinguish auth failure from a
    transient network drop and avoid a pointless reconnect loop.
    """
    await websocket.accept()

    if not ENABLE_LIVE_TRACKING:
        await websocket.close(code=1011, reason="Live tracking disabled")
        return

    db = SessionLocal()
    try:
        user = _authenticate_ws(token, db)
        if not user:
            await websocket.close(code=1008, reason="Unauthorized")
            return

        vessel = db.query(Vessel).get(vessel_id)
        if not vessel or vessel.owner_id != user.id:
            await websocket.close(code=1008, reason="Vessel not found")
            return

        provider = get_ais_provider()

        while True:
            fix = provider.get_vessel_position(vessel_id)
            if fix:
                persist_fix(db, fix)
                await websocket.send_text(json.dumps(fix.to_dict()))
            else:
                await websocket.send_text(
                    json.dumps({"vessel_id": vessel_id, "status": "NO_FIX"})
                )
            await asyncio.sleep(LOCATION_UPDATE_INTERVAL)

    except WebSocketDisconnect:
        logger.debug("Client disconnected from vessel %s location socket", vessel_id)
    except Exception as exc:
        logger.warning("Vessel location socket error (vessel %s): %s", vessel_id, exc)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
    finally:
        db.close()
