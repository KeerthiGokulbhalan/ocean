import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    alert_routes,
    auth_routes,
    fleet_routes,
    port_routes,
    routing_routes,
    tracking_routes,
    voyage_routes,
    weather_routes,
)
from app.config import ALLOWED_ORIGINS
from app.db.session import Base, engine, ensure_postgis_extension, migrate_existing_schema
from app.services.port_seed import seed_ports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seapath")

ensure_postgis_extension()
Base.metadata.create_all(bind=engine)
migrate_existing_schema()

# Populate the port reference table. Idempotent — safe to run on every boot.
seed_ports()

app = FastAPI(
    title="SeaPath API",
    description=(
        "AI-assisted ship route, fuel and emissions optimization engine, "
        "with Indian port search and live vessel tracking."
    ),
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return a clean message instead of leaking a Python stack trace.

    The full traceback is logged server-side for debugging; the client only
    ever sees a generic message.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong processing that request."},
    )


app.include_router(auth_routes.router)
app.include_router(routing_routes.router)
app.include_router(fleet_routes.router)
app.include_router(voyage_routes.router)
app.include_router(weather_routes.router)
app.include_router(alert_routes.router)
app.include_router(port_routes.router)
app.include_router(tracking_routes.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "seapath-api"}
