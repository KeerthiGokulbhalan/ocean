"""
Shared pytest fixtures.

Each test run gets a throwaway SQLite database so tests never touch the
developer's real seapath.db. The DATABASE_URL override must happen before
any `app.*` module is imported, because app.db.session builds the engine at
import time.
"""
import os
import tempfile

import pytest

_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="seapath-test-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["ENABLE_LIVE_TRACKING"] = "true"
os.environ["AIS_PROVIDER"] = "mock"
# no throttling in tests — we want every fix persisted deterministically
os.environ["POSITION_PERSIST_INTERVAL_S"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.simulation import simulation_registry  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_simulations():
    """Simulations are process-global; reset between tests for isolation."""
    simulation_registry.clear()
    yield
    simulation_registry.clear()


@pytest.fixture()
def auth_client(client):
    """A TestClient carrying a JWT for a freshly registered user."""
    import uuid

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": email, "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    client.user_email = email  # type: ignore[attr-defined]
    return client


@pytest.fixture()
def vessel(auth_client):
    resp = auth_client.post(
        "/api/fleet",
        json={
            "name": "MV SeaPath",
            "vessel_type": "container",
            "cruise_speed_knots": 18.0,
            "draft_m": 10.0,
            "deadweight_tons": 20000.0,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def voyage(auth_client, vessel):
    """A saved voyage with a real multi-point route, Chennai -> Mumbai-ish.

    Uses a hand-built polyline rather than calling the optimizer so the test
    suite stays fast and does not depend on network weather calls.
    """
    route_points = [
        {"lat": 13.0980, "lon": 80.2930},
        {"lat": 11.5000, "lon": 79.5000},
        {"lat": 8.5000, "lon": 77.5000},
        {"lat": 8.0000, "lon": 76.0000},
        {"lat": 12.0000, "lon": 74.0000},
        {"lat": 15.5000, "lon": 73.0000},
        {"lat": 18.9500, "lon": 72.8400},
    ]
    resp = auth_client.post(
        "/api/voyages",
        json={
            "vessel_id": vessel["id"],
            "start_port": "Chennai Port",
            "end_port": "Mumbai Port",
            "origin": {"lat": 13.0980, "lon": 80.2930},
            "destination": {"lat": 18.9500, "lon": 72.8400},
            "strategy": "fastest",
            "status": "Planned",
            "distance_nm": 1200.0,
            "duration_hr": 66.0,
            "fuel_tons": 210.0,
            "co2_tons": 650.0,
            "route_points": route_points,
            "risk_segments": [0.1] * len(route_points),
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()
