"""Live tracking API: auth scoping, validation, simulation control, WS."""
import pytest


# --- provider status --------------------------------------------------------
def test_tracking_status_declares_simulation_honestly(client):
    body = client.get("/api/tracking/status").json()
    assert body["enabled"] is True
    assert body["provider"] == "mock"
    assert body["simulated"] is True
    assert "DEMO SIMULATION" in body["label"]
    assert body["update_interval_s"] > 0


# --- authentication ---------------------------------------------------------
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/vessels/1/location"),
        ("post", "/api/vessels/1/location"),
        ("get", "/api/vessels/1/track"),
        ("get", "/api/vessels/locations"),
        ("get", "/api/voyages/1/tracking"),
        ("post", "/api/voyages/1/tracking"),
    ],
)
def test_tracking_endpoints_require_auth(client, method, path):
    kwargs = {"json": {}} if method == "post" else {}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 401


def test_cannot_access_another_users_vessel(client, auth_client, vessel):
    """A second user must not see the first user's vessel."""
    import uuid

    other = client
    resp = other.post(
        "/api/auth/register",
        json={
            "name": "Other",
            "email": f"other-{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
        },
    )
    token = resp.json()["access_token"]
    resp = other.get(
        f"/api/vessels/{vessel['id']}/track",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 404 rather than 403 — don't leak that the ID exists
    assert resp.status_code == 404


def test_cannot_track_another_users_voyage(client, auth_client, voyage):
    import uuid

    resp = client.post(
        "/api/auth/register",
        json={
            "name": "Other",
            "email": f"other-{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
        },
    )
    token = resp.json()["access_token"]
    resp = client.get(
        f"/api/voyages/{voyage['id']}/tracking",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# --- simulation lifecycle ---------------------------------------------------
def test_no_position_before_simulation_starts(auth_client, vessel):
    resp = auth_client.get(f"/api/vessels/{vessel['id']}/location")
    assert resp.status_code == 404


def test_start_simulation_places_ship_at_origin(auth_client, voyage):
    resp = auth_client.post(
        f"/api/voyages/{voyage['id']}/tracking", json={"action": "start"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["simulation_running"] is True
    assert body["position"] is not None
    assert body["position"]["latitude"] == pytest.approx(13.0980, abs=0.01)
    assert body["position"]["is_simulated"] is True
    assert body["position"]["source"] == "simulated"
    assert body["total_distance_nm"] > 0


def test_starting_simulation_marks_voyage_in_progress(auth_client, voyage):
    auth_client.post(f"/api/voyages/{voyage['id']}/tracking", json={"action": "start"})
    voyages = auth_client.get("/api/voyages").json()
    this = next(v for v in voyages if v["id"] == voyage["id"])
    assert this["status"] == "In-Progress"


def test_vessel_location_available_after_start(auth_client, vessel, voyage):
    auth_client.post(f"/api/voyages/{voyage['id']}/tracking", json={"action": "start"})
    resp = auth_client.get(f"/api/vessels/{vessel['id']}/location")
    assert resp.status_code == 200
    body = resp.json()
    assert body["vessel_id"] == vessel["id"]
    assert body["status"] == "UNDERWAY"
    assert 0 <= body["heading_deg"] < 360


def test_pause_stops_the_ship(auth_client, voyage):
    auth_client.post(f"/api/voyages/{voyage['id']}/tracking", json={"action": "start"})
    body = auth_client.post(
        f"/api/voyages/{voyage['id']}/tracking", json={"action": "pause"}
    ).json()
    assert body["simulation_running"] is False
    assert body["position"]["speed_knots"] == 0.0


def test_reset_returns_to_origin(auth_client, voyage):
    vid = voyage["id"]
    auth_client.post(f"/api/voyages/{vid}/tracking", json={"action": "start"})
    auth_client.post(f"/api/voyages/{vid}/tracking", json={"action": "speed", "speed_multiplier": 50.0})
    body = auth_client.post(f"/api/voyages/{vid}/tracking", json={"action": "reset"}).json()
    assert body["progress_percent"] == 0.0
    assert body["distance_travelled_nm"] == 0.0


def test_speed_multiplier_accepted(auth_client, voyage):
    body = auth_client.post(
        f"/api/voyages/{voyage['id']}/tracking",
        json={"action": "speed", "speed_multiplier": 5.0},
    ).json()
    assert body["speed_multiplier"] == 5.0


def test_invalid_speed_multiplier_rejected(auth_client, voyage):
    resp = auth_client.post(
        f"/api/voyages/{voyage['id']}/tracking",
        json={"action": "speed", "speed_multiplier": 3.0},
    )
    assert resp.status_code == 400


def test_out_of_range_speed_multiplier_rejected_by_schema(auth_client, voyage):
    resp = auth_client.post(
        f"/api/voyages/{voyage['id']}/tracking",
        json={"action": "speed", "speed_multiplier": 999},
    )
    assert resp.status_code == 422


def test_progress_is_derived_from_route(auth_client, voyage):
    """Progress must be real geometry, never a placeholder."""
    vid = voyage["id"]
    body = auth_client.post(f"/api/voyages/{vid}/tracking", json={"action": "start"}).json()
    total = body["total_distance_nm"]
    travelled = body["distance_travelled_nm"]
    remaining = body["distance_remaining_nm"]
    assert total == pytest.approx(travelled + remaining, abs=1.0)


# --- manual position reporting & validation ---------------------------------
def test_report_position_persists(auth_client, vessel, voyage):
    resp = auth_client.post(
        f"/api/vessels/{vessel['id']}/location",
        json={
            "latitude": 12.5,
            "longitude": 79.9,
            "speed_knots": 14.6,
            "heading_deg": 285,
            "status": "UNDERWAY",
            "voyage_id": voyage["id"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "manual"

    track = auth_client.get(f"/api/vessels/{vessel['id']}/track").json()
    assert track["count"] >= 1
    assert track["points"][-1]["latitude"] == pytest.approx(12.5)


@pytest.mark.parametrize(
    "payload",
    [
        {"latitude": 91, "longitude": 80},       # lat > 90
        {"latitude": -91, "longitude": 80},      # lat < -90
        {"latitude": 13, "longitude": 181},      # lon > 180
        {"latitude": 13, "longitude": -181},     # lon < -180
        {"latitude": 13, "longitude": 80, "speed_knots": -1},    # negative speed
        {"latitude": 13, "longitude": 80, "heading_deg": 360},   # heading must be < 360
        {"latitude": 13, "longitude": 80, "heading_deg": -5},    # negative heading
    ],
)
def test_invalid_position_rejected(auth_client, vessel, payload):
    resp = auth_client.post(f"/api/vessels/{vessel['id']}/location", json=payload)
    assert resp.status_code == 422


def test_cannot_attach_position_to_foreign_voyage(client, auth_client, vessel):
    import uuid

    # second user with their own vessel + voyage
    r = client.post(
        "/api/auth/register",
        json={
            "name": "Other",
            "email": f"o-{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
        },
    )
    other_token = r.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    other_vessel = client.post(
        "/api/fleet",
        json={"name": "Other Ship", "vessel_type": "tanker"},
        headers=other_headers,
    ).json()
    other_voyage = client.post(
        "/api/voyages",
        json={
            "vessel_id": other_vessel["id"],
            "origin": {"lat": 13.0, "lon": 80.0},
            "destination": {"lat": 18.0, "lon": 72.0},
            "strategy": "fastest",
            "distance_nm": 100,
            "duration_hr": 10,
            "fuel_tons": 10,
            "co2_tons": 30,
            "route_points": [{"lat": 13.0, "lon": 80.0}, {"lat": 18.0, "lon": 72.0}],
        },
        headers=other_headers,
    ).json()

    # first user tries to attach a position to the second user's voyage
    resp = auth_client.post(
        f"/api/vessels/{vessel['id']}/location",
        json={"latitude": 13, "longitude": 80, "voyage_id": other_voyage["id"]},
    )
    assert resp.status_code == 404


def test_unknown_vessel_returns_404(auth_client):
    assert auth_client.get("/api/vessels/999999/location").status_code == 404
    assert auth_client.get("/api/vessels/999999/track").status_code == 404


def test_unknown_voyage_returns_404(auth_client):
    assert auth_client.get("/api/voyages/999999/tracking").status_code == 404


# --- track ------------------------------------------------------------------
def test_track_is_ordered_oldest_first(auth_client, vessel, voyage):
    for lon in (80.0, 79.0, 78.0):
        auth_client.post(
            f"/api/vessels/{vessel['id']}/location",
            json={"latitude": 13.0, "longitude": lon, "voyage_id": voyage["id"]},
        )
    points = auth_client.get(f"/api/vessels/{vessel['id']}/track").json()["points"]
    timestamps = [p["timestamp"] for p in points]
    assert timestamps == sorted(timestamps)


def test_track_can_filter_by_voyage(auth_client, vessel, voyage):
    auth_client.post(
        f"/api/vessels/{vessel['id']}/location",
        json={"latitude": 13.0, "longitude": 80.0, "voyage_id": voyage["id"]},
    )
    body = auth_client.get(
        f"/api/vessels/{vessel['id']}/track", params={"voyage_id": voyage["id"]}
    ).json()
    assert body["count"] >= 1
    assert body["voyage_id"] == voyage["id"]


def test_fleet_locations_only_returns_own_vessels(auth_client, vessel, voyage):
    auth_client.post(f"/api/voyages/{voyage['id']}/tracking", json={"action": "start"})
    body = auth_client.get("/api/vessels/locations").json()
    assert all(p["vessel_id"] == vessel["id"] for p in body)


# --- WebSocket --------------------------------------------------------------
def test_websocket_rejects_missing_token(client, vessel):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/vessels/{vessel['id']}/location") as ws:
            ws.receive_text()


def test_websocket_rejects_bad_token(client, vessel):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/ws/vessels/{vessel['id']}/location?token=not-a-real-token"
        ) as ws:
            ws.receive_text()


def test_websocket_streams_position(client, auth_client, vessel, voyage):
    auth_client.post(f"/api/voyages/{voyage['id']}/tracking", json={"action": "start"})
    token = auth_client.headers["Authorization"].split()[1]

    with client.websocket_connect(
        f"/ws/vessels/{vessel['id']}/location?token={token}"
    ) as ws:
        msg = ws.receive_json()

    assert msg["vessel_id"] == vessel["id"]
    assert msg["is_simulated"] is True
    assert -90 <= msg["latitude"] <= 90
    assert -180 <= msg["longitude"] <= 180


def test_websocket_reports_no_fix_when_not_simulating(client, auth_client, vessel):
    token = auth_client.headers["Authorization"].split()[1]
    with client.websocket_connect(
        f"/ws/vessels/{vessel['id']}/location?token={token}"
    ) as ws:
        msg = ws.receive_json()
    assert msg["status"] == "NO_FIX"
