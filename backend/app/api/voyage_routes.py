import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import ALERT_RISK_THRESHOLD
from app.db.models import Alert, User, Voyage, Waypoint
from app.db.session import get_db
from app.schemas import VoyageCreate, VoyageOut, VoyageStatusUpdate, WaypointOut
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
