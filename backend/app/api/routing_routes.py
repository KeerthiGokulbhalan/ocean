import json

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import REROUTE_CHANGE_THRESHOLD
from app.db.models import Alert, User, Voyage
from app.db.session import get_db
from app.schemas import Coordinate, RouteRequest, RouteResponse, VesselProfile, VoyageReoptimizeRequest
from app.services.route_planner import plan_routes

router = APIRouter(prefix="/api/route", tags=["routing"])


@router.post("/optimize", response_model=RouteResponse)
async def optimize_route(req: RouteRequest):
    """Compute fastest / most fuel-efficient / safest route options
    between an origin and destination for the given vessel."""
    return await plan_routes(req)


@router.post("/reoptimize/{voyage_id}", response_model=RouteResponse)
async def reoptimize_route(
    voyage_id: int,
    payload: VoyageReoptimizeRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dynamic re-routing: re-fetches live weather for a saved voyage's
    corridor and recomputes the route. If the recommended route's fuel
    cost or risk has shifted materially since it was planned, a
    RouteChange alert is raised — simulating the mid-voyage re-evaluation
    described in the project brief. In production this would run on a
    scheduler (e.g. APScheduler / Celery beat) rather than on demand.
    """
    voyage = db.query(Voyage).get(voyage_id)
    if not voyage or voyage.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Voyage not found")

    vessel = VesselProfile(
        name=voyage.vessel.name if voyage.vessel else "Vessel",
        vessel_type=voyage.vessel.vessel_type if voyage.vessel else "container",
        cruise_speed_knots=voyage.vessel.cruise_speed_knots if voyage.vessel else 18.0,
        draft_m=voyage.vessel.draft_m if voyage.vessel else 10.0,
        deadweight_tons=voyage.vessel.deadweight_tons if voyage.vessel else 20000.0,
        fuel_rate_ton_per_hr=(
            voyage.vessel.fuel_rate_ton_per_hr if voyage.vessel else None
        ),
    )
    current = payload.current_position if payload else Coordinate(lat=voyage.origin_lat, lon=voyage.origin_lon)
    req = RouteRequest(
        origin=current,
        destination=Coordinate(lat=voyage.dest_lat, lon=voyage.dest_lon),
        vessel=vessel,
    )
    resp = await plan_routes(req)

    if payload:
        # Import lazily: the AIS package's mock provider imports the
        # simulation registry, so a module-level import here creates a cycle
        # during FastAPI startup.
        from app.services.simulation import simulation_registry

        chosen = next((o for o in resp.options if o.strategy == voyage.strategy), None)
        if chosen:
            # Update the active simulator at the vessel's present location so
            # the new A* leg is used immediately without resetting playback.
            sim = simulation_registry.get(voyage_id)
            new_points = [(p.lat, p.lon) for p in chosen.points]
            if sim:
                sim.replace_remaining_route(new_points)
                stored_points = sim.route
            else:
                stored_points = new_points
            voyage.route_points_json = json.dumps([[lat, lon] for lat, lon in stored_points])

    updated = next((o for o in resp.options if o.strategy == voyage.strategy), None)
    if updated:
        fuel_change = abs(updated.fuel_tons - voyage.fuel_tons) / max(voyage.fuel_tons, 0.01)
        if fuel_change >= REROUTE_CHANGE_THRESHOLD or updated.risk_score >= 0.5:
            db.add(
                Alert(
                    voyage_id=voyage.id,
                    type="RouteChange",
                    message=(
                        f"Conditions have changed since voyage #{voyage.id} was planned — "
                        f"re-optimized fuel estimate shifted by {fuel_change * 100:.0f}% "
                        f"(risk score now {updated.risk_score})."
                    ),
                    status="Unread",
                )
            )
            db.commit()

    if payload and updated:
        voyage.distance_nm = updated.distance_nm
        voyage.duration_hr = updated.duration_hr
        voyage.fuel_tons = updated.fuel_tons
        voyage.co2_tons = updated.co2_tons
        db.commit()

    return resp
