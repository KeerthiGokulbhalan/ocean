"""
Spatial "voyages near a point" search.

On PostgreSQL + PostGIS this runs a real ST_DWithin query against the
waypoints table (geography cast, so distances are true great-circle metres,
not flat-plane approximations). On SQLite — supported as a zero-setup local
fallback — the same result is computed in Python with the haversine formula
instead, so the feature still works without PostGIS installed.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Voyage, Waypoint
from app.db.session import IS_POSTGRES
from app.routing.geo import haversine_nm

NM_PER_KM = 0.539957


def find_voyages_near(db: Session, user_id: int, lat: float, lon: float, radius_km: float) -> list[Voyage]:
    if IS_POSTGRES:
        try:
            return _find_voyages_near_postgis(db, user_id, lat, lon, radius_km)
        except Exception:
            # PostGIS functions unavailable at query time (extension not
            # enabled on this database) — fall back rather than 500ing.
            db.rollback()
            return _find_voyages_near_python(db, user_id, lat, lon, radius_km)
    return _find_voyages_near_python(db, user_id, lat, lon, radius_km)


def _find_voyages_near_postgis(db: Session, user_id: int, lat: float, lon: float, radius_km: float) -> list[Voyage]:
    radius_m = radius_km * 1000
    rows = db.execute(
        text(
            """
            SELECT DISTINCT v.id
            FROM voyages v
            JOIN waypoints w ON w.voyage_id = v.id
            WHERE v.created_by = :user_id
              AND ST_DWithin(
                    ST_MakePoint(w.longitude, w.latitude)::geography,
                    ST_MakePoint(:lon, :lat)::geography,
                    :radius_m
                  )
            """
        ),
        {"user_id": user_id, "lat": lat, "lon": lon, "radius_m": radius_m},
    ).fetchall()

    ids = [r[0] for r in rows]
    if not ids:
        return []
    return db.query(Voyage).filter(Voyage.id.in_(ids)).all()


def _find_voyages_near_python(db: Session, user_id: int, lat: float, lon: float, radius_km: float) -> list[Voyage]:
    radius_nm = radius_km * NM_PER_KM
    voyages = db.query(Voyage).filter(Voyage.created_by == user_id).all()
    matches = []
    for voyage in voyages:
        waypoints = db.query(Waypoint).filter(Waypoint.voyage_id == voyage.id).all()
        if any(haversine_nm(lat, lon, w.latitude, w.longitude) <= radius_nm for w in waypoints):
            matches.append(voyage)
    return matches
