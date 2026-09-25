"""Port dataset, seeding and search API tests."""
import pytest

from app.data.indian_ports import PORTS

MAJOR_PORT_NAMES = {
    "Chennai Port",
    "Cochin Port",
    "Deendayal Port",
    "Jawaharlal Nehru Port",
    "Mormugao Port",
    "Mumbai Port",
    "New Mangalore Port",
    "Paradip Port",
    "Visakhapatnam Port",
    "V.O. Chidambaranar Port",
    "Kamarajar Port",
    "Syama Prasad Mookerjee Port",
}


# --- dataset integrity ------------------------------------------------------
def test_all_twelve_major_ports_present():
    majors = {p["name"] for p in PORTS if p["port_type"] == "Major Port"}
    assert majors == MAJOR_PORT_NAMES


def test_port_ids_are_unique():
    ids = [p["id"] for p in PORTS]
    assert len(ids) == len(set(ids))


def test_coordinates_are_valid_and_within_indian_region():
    for p in PORTS:
        assert -90 <= p["latitude"] <= 90, p["name"]
        assert -180 <= p["longitude"] <= 180, p["name"]
        # sanity band covering mainland India + Andamans + Lakshadweep
        assert 6 <= p["latitude"] <= 25, p["name"]
        assert 68 <= p["longitude"] <= 94, p["name"]


def test_every_port_has_required_fields():
    for p in PORTS:
        for field in ("id", "name", "display_name", "state", "country", "port_type"):
            assert p.get(field), f"{p['id']} missing {field}"
        assert p["country"] == "India"


# --- API --------------------------------------------------------------------
def test_list_ports_returns_seeded_dataset(client):
    resp = client.get("/api/ports")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == len(PORTS)
    assert len(body["ports"]) == len(PORTS)


def test_major_ports_are_listed_first(client):
    ports = client.get("/api/ports").json()["ports"]
    types = [p["port_type"] for p in ports]
    assert types[:12] == ["Major Port"] * 12


def test_search_by_partial_name(client):
    ports = client.get("/api/ports", params={"search": "chenn"}).json()["ports"]
    assert any(p["name"] == "Chennai Port" for p in ports)


def test_search_is_case_insensitive(client):
    lower = client.get("/api/ports", params={"search": "mumbai"}).json()["count"]
    upper = client.get("/api/ports", params={"search": "MUMBAI"}).json()["count"]
    assert lower == upper >= 1


def test_search_by_state(client):
    ports = client.get("/api/ports", params={"search": "Tamil Nadu"}).json()["ports"]
    assert len(ports) >= 3
    assert all(p["state"] == "Tamil Nadu" for p in ports)


def test_search_by_port_code(client):
    ports = client.get("/api/ports", params={"search": "INMAA"}).json()["ports"]
    assert ports and ports[0]["name"] == "Chennai Port"


def test_filter_by_state_exact(client):
    ports = client.get("/api/ports", params={"state": "Kerala"}).json()["ports"]
    assert ports
    assert all(p["state"] == "Kerala" for p in ports)


def test_filter_by_port_type(client):
    ports = client.get("/api/ports", params={"port_type": "Major Port"}).json()["ports"]
    assert len(ports) == 12


def test_search_with_no_match_returns_empty(client):
    body = client.get("/api/ports", params={"search": "zzzznotaport"}).json()
    assert body["count"] == 0
    assert body["ports"] == []


def test_get_single_port(client):
    port = client.get("/api/ports/IN_CHENNAI").json()
    assert port["name"] == "Chennai Port"
    assert port["state"] == "Tamil Nadu"
    assert port["port_code"] == "INMAA"


def test_get_unknown_port_returns_404(client):
    assert client.get("/api/ports/NOPE").status_code == 404


def test_list_states(client):
    states = client.get("/api/ports/states").json()
    assert "Tamil Nadu" in states
    assert "Gujarat" in states
    assert states == sorted(states)


def test_seeding_is_idempotent(client):
    """Re-running the seed must not duplicate rows."""
    from app.services.port_seed import seed_ports

    before = client.get("/api/ports").json()["count"]
    result = seed_ports()
    after = client.get("/api/ports").json()["count"]
    assert before == after
    assert result["created"] == 0
