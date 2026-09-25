"""Voyage simulator unit tests — geometry, interpolation and playback."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.services.simulation import SimulationRegistry, VoyageSimulation

ROUTE = [
    (13.0, 80.0),
    (13.0, 79.0),
    (13.0, 78.0),
    (13.0, 77.0),
]


def make_sim(speed=60.0) -> VoyageSimulation:
    return VoyageSimulation(
        voyage_id=1, vessel_id=1, route=list(ROUTE), cruise_speed_knots=speed
    )


def test_cumulative_distance_is_monotonic():
    sim = make_sim()
    assert sim.cumulative_nm[0] == 0.0
    assert sim.cumulative_nm == sorted(sim.cumulative_nm)
    assert sim.total_nm == pytest.approx(sim.cumulative_nm[-1])
    assert sim.total_nm > 0


def test_starts_at_origin_with_zero_progress():
    sim = make_sim()
    lat, lon, _ = sim.position()
    assert (round(lat, 4), round(lon, 4)) == ROUTE[0]
    assert sim.progress_percent == 0.0
    assert sim.status == "STOPPED"


def test_position_follows_route_not_straight_line():
    """Ship must sit on the route polyline, not on the origin->dest chord."""
    bent_route = [(13.0, 80.0), (5.0, 78.0), (13.0, 76.0)]
    sim = VoyageSimulation(
        voyage_id=1, vessel_id=1, route=bent_route, cruise_speed_knots=60.0
    )
    sim.distance_travelled_nm = sim.total_nm / 2
    lat, lon, _ = sim.position()
    # halfway along the bent path is near the southern vertex, far from the
    # chord midpoint of lat 13
    assert lat < 10.0


def test_interpolates_between_waypoints():
    sim = make_sim()
    sim.distance_travelled_nm = sim.cumulative_nm[1] / 2
    lat, lon, _ = sim.position()
    # halfway along the first leg: between lon 80 and lon 79
    assert 79.0 < lon < 80.0
    assert lat == pytest.approx(13.0, abs=0.01)


def test_advance_moves_ship_with_elapsed_time():
    sim = make_sim(speed=60.0)  # 60 kn -> 1 nm per minute
    sim.start()
    sim.last_tick = datetime.now(timezone.utc) - timedelta(hours=1)
    sim.advance()
    assert sim.distance_travelled_nm == pytest.approx(60.0, rel=0.05)


def test_speed_multiplier_scales_movement():
    # 30 min at 60 kn x5 = 150 nm, which stays inside this ~175 nm route so
    # the result is not clamped at the destination
    sim = make_sim(speed=60.0)
    sim.start()
    sim.set_speed_multiplier(5.0)
    sim.last_tick = datetime.now(timezone.utc) - timedelta(minutes=30)
    sim.advance()
    assert sim.distance_travelled_nm == pytest.approx(150.0, rel=0.05)
    assert not sim.finished


def test_pause_banks_progress_and_stops_movement():
    sim = make_sim(speed=60.0)
    sim.start()
    sim.last_tick = datetime.now(timezone.utc) - timedelta(hours=1)
    sim.pause()
    banked = sim.distance_travelled_nm
    assert banked > 0
    assert not sim.running
    sim.advance()  # must be a no-op while paused
    assert sim.distance_travelled_nm == banked


def test_reset_returns_to_origin():
    sim = make_sim()
    sim.distance_travelled_nm = sim.total_nm / 2
    sim.reset()
    assert sim.distance_travelled_nm == 0.0
    assert sim.progress_percent == 0.0
    lat, lon, _ = sim.position()
    assert (round(lat, 4), round(lon, 4)) == ROUTE[0]


def test_voyage_completes_and_clamps_at_destination():
    sim = make_sim(speed=60.0)
    sim.start()
    sim.last_tick = datetime.now(timezone.utc) - timedelta(days=10)
    sim.advance()
    assert sim.finished
    assert not sim.running
    assert sim.distance_travelled_nm == pytest.approx(sim.total_nm)
    assert sim.progress_percent == 100.0
    assert sim.status == "ARRIVED"
    lat, lon, _ = sim.position()
    assert (round(lat, 4), round(lon, 4)) == ROUTE[-1]


def test_progress_derived_from_real_geometry():
    sim = make_sim()
    sim.distance_travelled_nm = sim.total_nm * 0.25
    assert sim.progress_percent == pytest.approx(25.0, abs=0.5)


def test_heading_is_a_valid_bearing():
    sim = make_sim()
    _, _, heading = sim.position()
    assert 0 <= heading < 360
    # route runs due west -> bearing ~270
    assert heading == pytest.approx(270.0, abs=2.0)


def test_eta_ignores_demo_speed_multiplier():
    """5x playback must not claim a 5x earlier real-world arrival."""
    sim_1x = make_sim(speed=60.0)
    sim_5x = make_sim(speed=60.0)
    sim_5x.set_speed_multiplier(5.0)
    delta_1x = sim_1x.eta() - datetime.now(timezone.utc)
    delta_5x = sim_5x.eta() - datetime.now(timezone.utc)
    assert delta_1x.total_seconds() == pytest.approx(delta_5x.total_seconds(), rel=0.01)


def test_speed_is_zero_when_not_running():
    sim = make_sim()
    assert sim.current_speed_knots == 0.0
    sim.start()
    assert sim.current_speed_knots == 60.0


# --- registry ---------------------------------------------------------------
def test_registry_parses_route_json():
    reg = SimulationRegistry()
    sim = reg.create(
        voyage_id=7,
        vessel_id=3,
        route_points_json=json.dumps([[13.0, 80.0], [14.0, 79.0]]),
        cruise_speed_knots=18.0,
    )
    assert len(sim.route) == 2
    assert reg.get(7) is sim
    assert reg.get_by_vessel(3) is sim


def test_registry_falls_back_to_origin_destination():
    """Voyages saved before route storage still track."""
    reg = SimulationRegistry()
    sim = reg.create(
        voyage_id=8,
        vessel_id=4,
        route_points_json=None,
        cruise_speed_knots=18.0,
        origin=(13.0, 80.0),
        destination=(18.0, 72.0),
    )
    assert len(sim.route) == 2


def test_registry_rejects_unusable_route():
    reg = SimulationRegistry()
    with pytest.raises(ValueError):
        reg.create(voyage_id=9, vessel_id=5, route_points_json=None, cruise_speed_knots=18.0)


def test_registry_prefers_running_simulation_for_vessel():
    reg = SimulationRegistry()
    idle = reg.create(1, 42, json.dumps([[1.0, 1.0], [2.0, 2.0]]), 18.0)
    active = reg.create(2, 42, json.dumps([[3.0, 3.0], [4.0, 4.0]]), 18.0)
    active.start()
    assert reg.get_by_vessel(42) is active
    assert idle is not active
