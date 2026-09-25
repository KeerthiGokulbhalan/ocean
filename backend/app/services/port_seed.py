"""
Seeds the `ports` table from app/data/indian_ports.py.

Runs at application startup. The operation is an idempotent upsert keyed on
the string primary key, which means:

  * adding a port to the dataset makes it appear on the next boot
  * editing a coordinate or description in the dataset corrects the row
  * nothing is ever deleted, so ports referenced by saved voyages survive
  * running it repeatedly (tests, reloads, multiple workers) is harmless

Works identically on SQLite and PostgreSQL — deliberately uses plain ORM
reads/writes rather than a dialect-specific ON CONFLICT clause.
"""
import logging

from sqlalchemy.orm import Session

from app.data.indian_ports import PORTS
from app.db.models import Port
from app.db.session import SessionLocal

logger = logging.getLogger("seapath.ports")

_SEEDABLE_FIELDS = (
    "name",
    "display_name",
    "state",
    "country",
    "latitude",
    "longitude",
    "port_type",
    "port_code",
    "description",
)


def seed_ports(db: Session | None = None) -> dict[str, int]:
    """Upsert every port in the dataset. Returns counts for logging/tests."""
    owns_session = db is None
    db = db or SessionLocal()
    created = updated = unchanged = 0

    try:
        existing = {p.id: p for p in db.query(Port).all()}

        for record in PORTS:
            row = existing.get(record["id"])

            if row is None:
                db.add(Port(**{k: record.get(k) for k in ("id", *_SEEDABLE_FIELDS)}))
                created += 1
                continue

            # only write when something actually differs, so `updated_at`
            # stays meaningful instead of churning on every restart
            changed = False
            for field in _SEEDABLE_FIELDS:
                if getattr(row, field) != record.get(field):
                    setattr(row, field, record.get(field))
                    changed = True
            if changed:
                updated += 1
            else:
                unchanged += 1

        db.commit()
        logger.info(
            "Port seed complete: %d created, %d updated, %d unchanged.",
            created, updated, unchanged,
        )
    except Exception as exc:
        db.rollback()
        # A failed seed must never prevent the API from starting — the rest of
        # SeaPath (routing, fleet, voyages) works without the port table.
        logger.warning("Port seeding failed (%s). Port search may be empty.", exc)
    finally:
        if owns_session:
            db.close()

    return {"created": created, "updated": updated, "unchanged": unchanged}
