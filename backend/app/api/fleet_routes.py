from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User, Vessel
from app.db.session import get_db
from app.schemas import VesselCreate, VesselMmsiUpdate, VesselOut

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


@router.get("", response_model=list[VesselOut])
def list_vessels(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Vessel).filter(Vessel.owner_id == current_user.id).all()


@router.post("", response_model=VesselOut)
def create_vessel(
    payload: VesselCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vessel = Vessel(**payload.model_dump(), owner_id=current_user.id)
    db.add(vessel)
    db.commit()
    db.refresh(vessel)
    return vessel


@router.delete("/{vessel_id}")
def delete_vessel(
    vessel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vessel = db.query(Vessel).get(vessel_id)
    if not vessel or vessel.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Vessel not found")
    db.delete(vessel)
    db.commit()
    return {"ok": True}


@router.patch("/{vessel_id}/mmsi", response_model=VesselOut)
def update_vessel_mmsi(
    vessel_id: int,
    payload: VesselMmsiUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vessel = db.query(Vessel).get(vessel_id)
    if not vessel or vessel.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Vessel not found")
    if payload.mmsi and db.query(Vessel).filter(
        Vessel.mmsi == payload.mmsi, Vessel.id != vessel_id
    ).first():
        raise HTTPException(status_code=409, detail="That MMSI is already assigned to another vessel.")
    vessel.mmsi = payload.mmsi
    db.commit()
    db.refresh(vessel)
    return vessel
