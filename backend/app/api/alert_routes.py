from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Alert, User, Voyage
from app.db.session import get_db
from app.schemas import AlertOut, AlertStatusUpdate

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Alert)
        .join(Voyage, Alert.voyage_id == Voyage.id)
        .filter(Voyage.created_by == current_user.id)
        .order_by(Alert.created_at.desc())
        .all()
    )


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(Alert).get(alert_id)
    if not alert or alert.voyage.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = payload.status
    db.commit()
    db.refresh(alert)
    return alert
