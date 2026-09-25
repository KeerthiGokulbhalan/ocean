import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

logger = logging.getLogger("seapath.db")


def _normalize_database_url(url: str) -> str:
    """
    Many managed Postgres providers (Heroku, Render, Railway, Supabase, ECS
    secrets, etc.) hand out connection strings starting with `postgres://`,
    which SQLAlchemy 2.x no longer accepts — it needs `postgresql://` (and
    we want the psycopg2 driver explicitly). This rewrites the scheme so the
    same DATABASE_URL a cloud dashboard gives you can be pasted in as-is.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = _normalize_database_url(DATABASE_URL)
IS_POSTGRES = DATABASE_URL.startswith("postgresql")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_postgis_extension():
    """When running against PostgreSQL, try to enable the PostGIS extension
    so spatial queries (see services/spatial.py) work. No-op for SQLite.

    On many managed cloud databases (Render, Railway, Supabase, RDS with a
    restricted app user, etc.) PostGIS is either already enabled by the
    provider or the app user lacks CREATE EXTENSION privileges. Either way
    this must not crash startup — it logs a warning and the app falls back
    to the Python haversine spatial search (see services/spatial.py) if the
    extension truly isn't available.
    """
    if not IS_POSTGRES:
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.commit()
    except Exception as exc:
        logger.warning(
            "Could not create the PostGIS extension automatically (%s). "
            "If your database user lacks CREATE EXTENSION privileges, ask "
            "your cloud provider to enable PostGIS for this database, or "
            "run `CREATE EXTENSION IF NOT EXISTS postgis;` manually as an "
            "admin. The app will still run — spatial search falls back to "
            "a Python calculation if PostGIS isn't available.",
            exc,
        )


def migrate_existing_schema():
    """Apply small additive fixes that ``metadata.create_all`` cannot do.

    ``create_all`` creates missing tables but does not add columns to tables
    already present in a persistent database volume. Keep this migration
    additive so existing voyage and vessel records remain intact.
    """
    inspector = inspect(engine)
    if inspector.has_table("vessels"):
        vessel_columns = {column["name"] for column in inspector.get_columns("vessels")}
        if "mmsi" not in vessel_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE vessels ADD COLUMN mmsi VARCHAR(9)"))
                logger.info("Added missing vessels.mmsi database column")
        with engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_vessels_mmsi ON vessels (mmsi)"))

    if not inspector.has_table("vessel_positions"):
        return

    columns = {column["name"] for column in inspector.get_columns("vessel_positions")}
    if "voyage_id" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE vessel_positions "
                    "ADD COLUMN voyage_id INTEGER REFERENCES voyages(id)"
                )
            )
            logger.info("Added missing vessel_positions.voyage_id database column")

    # This index is declared in the ORM model. Ensure it is also present on
    # databases whose tables predate that declaration.
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_vessel_positions_voyage_id "
                "ON vessel_positions (voyage_id)"
            )
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
