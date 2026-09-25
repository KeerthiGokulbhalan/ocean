"""
Indian port reference API.

Read-only: ports are seeded from app/data/indian_ports.py at startup, so
there is no create/update/delete surface to secure. Left unauthenticated to
match the existing /api/weather endpoint — this is public reference data and
the route planner needs it before a voyage exists.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import Port
from app.db.session import get_db
from app.schemas import PortListResponse, PortOut

router = APIRouter(prefix="/api/ports", tags=["ports"])


@router.get("", response_model=PortListResponse)
def list_ports(
    search: str | None = Query(
        None, description="Case-insensitive match on port name, state or UN/LOCODE."
    ),
    state: str | None = Query(None, description="Exact (case-insensitive) state filter."),
    port_type: str | None = Query(None, description='e.g. "Major Port".'),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List ports, optionally filtered.

    Deliberately returns the whole dataset by default: it is small enough
    (tens of records) that the frontend caches it once and filters locally,
    which keeps the search dropdown instant. The `search` parameter exists so
    the same endpoint still scales if the dataset grows.
    """
    query = db.query(Port)

    if search:
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Port.name).like(term),
                func.lower(Port.display_name).like(term),
                func.lower(Port.state).like(term),
                func.lower(Port.port_code).like(term),
            )
        )

    if state:
        query = query.filter(func.lower(Port.state) == state.strip().lower())

    if port_type:
        query = query.filter(func.lower(Port.port_type) == port_type.strip().lower())

    # Major Ports first, then alphabetically — the most likely pick surfaces first
    ports = (
        query.order_by(
            func.lower(Port.port_type) != "major port",
            Port.name.asc(),
        )
        .limit(limit)
        .all()
    )
    return PortListResponse(ports=[PortOut.model_validate(p) for p in ports], count=len(ports))


@router.get("/states", response_model=list[str])
def list_states(db: Session = Depends(get_db)):
    """Distinct coastal states/UTs present in the dataset — powers a filter."""
    rows = db.query(Port.state).distinct().order_by(Port.state.asc()).all()
    return [r[0] for r in rows]


@router.get("/{port_id}", response_model=PortOut)
def get_port(port_id: str, db: Session = Depends(get_db)):
    port = db.query(Port).get(port_id)
    if not port:
        raise HTTPException(status_code=404, detail="Port not found")
    return port
