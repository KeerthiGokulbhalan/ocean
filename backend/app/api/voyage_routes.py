import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import ALERT_RISK_THRESHOLD, CO2_PER_TON_FUEL, DEFAULT_FUEL_RATE_TON_PER_HR, MAX_TRACK_POINTS
from app.db.models import Alert, User, VesselPosition, Voyage, Waypoint
from app.db.session import get_db
from app.routing.geo import haversine_nm
from app.schemas import VoyageAnalytics, VoyageCreate, VoyageOut, VoyageStatusUpdate, WaypointOut
from app.services.report import build_voyage_report_pdf
from app.services.spatial import find_voyages_near

router = APIRouter(prefix="/api/voyages", tags=["voyages"])

STRATEGY_TO_MODE = {"fastest": "Fastest", "efficient": "Fuel-Efficient", "safest": "Safest"}


@router.get("", response_model=list[VoyageOut])
def list_voyages(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Voyage)
        .filter(Voyage.created_by == current_user.id)
        .order_by(Voyage.created_at.desc())
        .all()
    )


@router.post("", response_model=VoyageOut)
def create_voyage(
    payload: VoyageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    voyage = Voyage(
        vessel_id=payload.vessel_id,
        created_by=current_user.id,
        start_port=payload.start_port,
        end_port=payload.end_port,
        origin_lat=payload.origin.lat,
        origin_lon=payload.origin.lon,
        dest_lat=payload.destination.lat,
        dest_lon=payload.destination.lon,
        mode=STRATEGY_TO_MODE.get(payload.strategy, "Fastest"),
        status=payload.status,
        strategy=payload.strategy,
        distance_nm=payload.distance_nm,
        duration_hr=payload.duration_hr,
        fuel_tons=payload.fuel_tons,
        co2_tons=payload.co2_tons,
        route_points_json=json.dumps([[p.lat, p.lon] for p in payload.route_points]),
    )
    db.add(voyage)
    db.commit()
    db.refresh(voyage)

    # persist waypoints (sampled — every point would be excessive for a long route)
    step = max(1, len(payload.route_points) // 50)
    risks = payload.risk_segments or [0.0] * len(payload.route_points)
    max_risk_seen = 0.0
    for seq, idx in enumerate(range(0, len(payload.route_points), step)):
        point = payload.route_points[idx]
        risk = risks[idx] if idx < len(risks) else 0.0
        max_risk_seen = max(max_risk_seen, risk)
        db.add(
            Waypoint(
                voyage_id=voyage.id,
                sequence=seq,
                latitude=point.lat,
                longitude=point.lon,
                risk_score=risk,
            )
        )

    # auto-raise a StormWarning alert if any segment of the route is high-risk
    if max_risk_seen >= ALERT_RISK_THRESHOLD:
        db.add(
            Alert(
                voyage_id=voyage.id,
                type="StormWarning",
                message=(
                    f"The {payload.strategy} route for voyage #{voyage.id} passes through "
                    f"high-risk weather (peak risk score {max_risk_seen:.2f})."
                ),
                status="Unread",
            )
        )

    db.commit()
    return voyage


@router.get("/nearby", response_model=list[VoyageOut])
def get_voyages_near(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(100, gt=0, le=20000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Spatial search: find the current user's voyages that pass within
    `radius_km` of a given point. Runs a real PostGIS ST_DWithin query when
    the backend is configured with PostgreSQL + PostGIS; falls back to an
    equivalent haversine calculation in Python on SQLite.
    """
    return find_voyages_near(db, current_user.id, lat, lon, radius_km)


@router.patch("/{voyage_id}/status", response_model=VoyageOut)
def update_voyage_status(
    voyage_id: int,
    payload: VoyageStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    voyage = db.query(Voyage).get(voyage_id)
    if not voyage or voyage.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Voyage not found")
    voyage.status = payload.status
    db.commit()
    db.refresh(voyage)
    return voyage


@router.get("/{voyage_id}/analytics", response_model=VoyageAnalytics)
def get_voyage_analytics(
    voyage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare planned metrics with the persisted vessel track.

    Fuel is a transparent estimate from the vessel's configured/default
    hourly burn rate. It is not claimed to be a reading from an onboard meter.
    """
    voyage = db.query(Voyage).get(voyage_id)
    if not voyage or voyage.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Voyage not found")

    positions = (
        db.query(VesselPosition)
        .filter(
            VesselPosition.voyage_id == voyage_id,
            VesselPosition.vessel_id == voyage.vessel_id,
        )
        .order_by(VesselPosition.timestamp.asc())
        .limit(MAX_TRACK_POINTS)
        .all()
    )

    actual_available = len(positions) >= 2
    actual_distance = None
    actual_duration = None
    actual_fuel = None
    actual_co2 = None
    progress = None
    start_time = positions[0].timestamp if positions else None
    end_time = positions[-1].timestamp if positions else None

    sources = {p.source for p in positions if p.source}
    is_simulated = bool("simulated" in sources)
    if not sources:
        source_label = "NO TRACK DATA"
    elif len(sources) > 1:
        source_label = "MIXED TRACK"
    elif "simulated" in sources:
        source_label = "SIMULATED"
    elif "ais" in sources:
        source_label = "AIS"
    else:
        source_label = next(iter(sources)).upper()

    fuel_rate = (
        voyage.vessel.fuel_rate_ton_per_hr
        if voyage.vessel and voyage.vessel.fuel_rate_ton_per_hr
        else DEFAULT_FUEL_RATE_TON_PER_HR.get(
            voyage.vessel.vessel_type if voyage.vessel else "container",
            DEFAULT_FUEL_RATE_TON_PER_HR["container"],
        )
    )
    cruise_speed = (
        voyage.vessel.cruise_speed_knots
        if voyage.vessel and voyage.vessel.cruise_speed_knots
        else 18.0
    )

    if actual_available:
        actual_distance = sum(
            haversine_nm(a.latitude, a.longitude, b.latitude, b.longitude)
            for a, b in zip(positions, positions[1:])
        )
        actual_duration = max(
            0.0, (positions[-1].timestamp - positions[0].timestamp).total_seconds() / 3600.0
        )
        # Estimate sailing fuel from sailed distance and the vessel's hourly
        # burn rate at its configured cruise speed; do not imply a fuel sensor.
        estimated_sailing_hours = actual_distance / cruise_speed
        actual_fuel = estimated_sailing_hours * fuel_rate
        actual_co2 = actual_fuel * CO2_PER_TON_FUEL
        progress = min(100.0, actual_distance / max(voyage.distance_nm, 0.01) * 100.0)

    return VoyageAnalytics(
        voyage_id=voyage.id,
        data_source=source_label,
        is_simulated=is_simulated,
        tracking_points=len(positions),
        actual_available=actual_available,
        planned_distance_nm=round(voyage.distance_nm or 0.0, 2),
        actual_distance_nm=round(actual_distance, 2) if actual_distance is not None else None,
        distance_variance_nm=round(actual_distance - voyage.distance_nm, 2) if actual_distance is not None else None,
        planned_duration_hr=round(voyage.duration_hr or 0.0, 2),
        actual_duration_hr=round(actual_duration, 2) if actual_duration is not None else None,
        duration_variance_hr=round(actual_duration - voyage.duration_hr, 2) if actual_duration is not None else None,
        planned_fuel_tons=round(voyage.fuel_tons or 0.0, 3),
        actual_fuel_tons=round(actual_fuel, 3) if actual_fuel is not None else None,
        fuel_variance_tons=round(actual_fuel - voyage.fuel_tons, 3) if actual_fuel is not None else None,
        planned_co2_tons=round(voyage.co2_tons or 0.0, 3),
        actual_co2_tons=round(actual_co2, 3) if actual_co2 is not None else None,
        co2_variance_tons=round(actual_co2 - voyage.co2_tons, 3) if actual_co2 is not None else None,
        progress_percent=round(progress, 1) if progress is not None else None,
        fuel_calculation_method="Estimated from tracked distance ÷ vessel cruise speed × configured/default fuel rate; not an onboard fuel-meter reading.",
        actual_start_time=start_time,
        actual_end_time=end_time,
        note=(
            "Tracking positions are simulated. Fuel and CO₂ are model estimates."
            if is_simulated
            else "Fuel and CO₂ are model estimates from track distance and vessel fuel rate, not onboard sensor readings."
            if actual_available
            else "Not enough persisted tracking points yet. Start tracking and allow at least two positions to be recorded."
        ),
    )


@router.get("/{voyage_id}/waypoints", response_model=list[WaypointOut])
def get_waypoints(
    voyage_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    voyage = db.query(Voyage).get(voyage_id)
    if not voyage or voyage.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Voyage not found")
    return (
        db.query(Waypoint)
        .filter(Waypoint.voyage_id == voyage_id)
        .order_by(Waypoint.sequence)
        .all()
    )


@router.get("/{voyage_id}/report")
def get_voyage_report(
    voyage_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    voyage = db.query(Voyage).get(voyage_id)
    if not voyage or voyage.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Voyage not found")
    pdf_bytes = build_voyage_report_pdf(voyage)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=voyage_{voyage_id}_report.pdf"},
    )
