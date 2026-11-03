from app.routing.geo import haversine_nm


def test_voyage_analytics_compares_planned_metrics_to_manual_track(auth_client, vessel, voyage):
    first = auth_client.post(
        f"/api/vessels/{vessel['id']}/location",
        json={
            "latitude": 13.0980,
            "longitude": 80.2930,
            "speed_knots": 18.0,
            "heading_deg": 270.0,
            "status": "UNDERWAY",
            "voyage_id": voyage["id"],
            "timestamp": "2026-11-03T00:00:00Z",
        },
    )
    second = auth_client.post(
        f"/api/vessels/{vessel['id']}/location",
        json={
            "latitude": 13.0980,
            "longitude": 79.2930,
            "speed_knots": 18.0,
            "heading_deg": 270.0,
            "status": "UNDERWAY",
            "voyage_id": voyage["id"],
            "timestamp": "2026-11-03T01:00:00Z",
        },
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    response = auth_client.get(f"/api/voyages/{voyage['id']}/analytics")
    assert response.status_code == 200, response.text
    body = response.json()

    expected_distance = haversine_nm(13.0980, 80.2930, 13.0980, 79.2930)
    assert body["actual_available"] is True
    assert body["data_source"] == "MANUAL"
    assert body["is_simulated"] is False
    assert body["tracking_points"] == 2
    assert body["planned_distance_nm"] == 1200.0
    assert body["actual_distance_nm"] == round(expected_distance, 2)
    assert body["actual_duration_hr"] == 1.0
    assert body["actual_fuel_tons"] > 0
    assert body["actual_co2_tons"] > 0
    assert "not an onboard fuel-meter reading" in body["fuel_calculation_method"]


def test_voyage_analytics_waits_until_two_positions_exist(auth_client, vessel, voyage):
    response = auth_client.get(f"/api/voyages/{voyage['id']}/analytics")
    assert response.status_code == 200
    body = response.json()
    assert body["actual_available"] is False
    assert body["actual_distance_nm"] is None
    assert body["actual_fuel_tons"] is None
    assert body["tracking_points"] == 0


def test_voyage_analytics_is_scoped_to_owner(client, auth_client, voyage):
    import uuid

    other = client.post(
        "/api/auth/register",
        json={
            "name": "Other",
            "email": f"analytics-{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
        },
    )
    token = other.json()["access_token"]
    response = client.get(
        f"/api/voyages/{voyage['id']}/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
