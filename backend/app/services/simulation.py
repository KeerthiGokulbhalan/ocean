"""
Voyage movement simulator.

Drives a vessel along the *actual A*-calculated route* for a voyage — not a
straight line between origin and destination. Given the route polyline
already stored on the voyage (`route_points_json`), the simulator:

  1. precomputes the cumulative great-circle distance of each leg
  2. converts wall-clock elapsed time into distance travelled,
     using the vessel's cruise speed and a demo speed multiplier
  3. locates which leg that distance falls on and linearly interpolates
     between its two waypoints, so movement is smooth rather than jumping
     from waypoint to waypoint
  4. derives heading from the bearing of the current leg

State lives in memory and is keyed by voyage. That is the right trade-off
for a demo/simulation feature: it needs no migration, survives the whole
run of the server process, and a restart simply resets the simulation —
while the *positions it produces* are persisted to the database (see
services/tracking.py) so the historical track is durable.

Progress is always computed from real route geometry. No arbitrary
percentages are used anywhere.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.routing.geo import haversine_nm
from app.services.ais.base import VesselFix

# Supported demo playback rates (x real time).
ALLOWED_SPEED_MULTIPLIERS = (1.0, 2.0, 5.0, 10.0, 50.0)


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing, degrees clockwise from north."""
    import math

    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


@dataclass
class VoyageSimulation:
    """In-memory playback state for a single voyage."""

    voyage_id: int
    vessel_id: int
    route: list[tuple[float, float]]
    cruise_speed_knots: float

    # cumulative distance (nm) at each route point; cumulative[0] == 0
    cumulative_nm: list[float] = field(default_factory=list)
    total_nm: float = 0.0

    distance_travelled_nm: float = 0.0
    speed_multiplier: float = 1.0
    running: bool = False
    finished: bool = False

    # wall-clock instant the simulation was last resumed
    last_tick: Optional[datetime] = None
    # --- dummy obstacle / hindrance detection & rerouting ------------------
    # Demo-only feature: an obstacle is a simulated hindrance (blocked
    # passage, restricted zone) placed on the route so the ship is forced to
    # detect it and reroute mid-voyage. It never comes from real project
    # data — see SimulationRegistry._default_obstacle().
    obstacle: Optional[tuple[float, float]] = None
    obstacle_radius_nm: float = 25.0  # distance at which detection triggers
    obstacle_block_radius_deg: float = 0.6  # patch blocked on the grid for rerouting
    hindrance_state: str = "NONE"  # NONE | DETECTED | AVOIDED
    rerouted: bool = False
    reroute_pause_until: Optional[datetime] = None
    original_route: Optional[list[tuple[float, float]]] = None
    alternate_route: Optional[list[tuple[float, float]]] = None

    def __post_init__(self) -> None:
        self.cumulative_nm = [0.0]
        total = 0.0
        for (lat1, lon1), (lat2, lon2) in zip(self.route, self.route[1:]):
            total += haversine_nm(lat1, lon1, lat2, lon2)
            self.cumulative_nm.append(total)
        self.total_nm = total

    # --- playback controls ------------------------------------------------
    def start(self) -> None:
        if self.finished:
            self.reset()
        self.running = True
        self.last_tick = datetime.now(timezone.utc)

    def pause(self) -> None:
        self.advance()  # bank the distance covered up to this moment
        self.running = False
        self.last_tick = None

    def reset(self) -> None:
        self.distance_travelled_nm = 0.0
        self.running = False
        self.finished = False
        self.last_tick = None
        # restore the original route if a reroute had happened, so Reset
        # always returns to a clean, pre-hindrance state
        if self.original_route:
            self.route = self.original_route
            self.__post_init__()
        self.hindrance_state = "NONE"
        self.rerouted = False
        self.reroute_pause_until = None
        self.original_route = None
        self.alternate_route = None

    def set_speed_multiplier(self, multiplier: float) -> None:
        self.advance()  # settle progress at the old rate before switching
        self.speed_multiplier = multiplier

    def set_obstacle(
        self, lat: float, lon: float, trigger_radius_nm: float = 25.0,
        block_radius_deg: float = 0.6,
    ) -> None:
        """Place a dummy obstacle for this voyage's simulation to detect."""
        self.obstacle = (lat, lon)
        self.obstacle_radius_nm = trigger_radius_nm
        self.obstacle_block_radius_deg = block_radius_deg
    # --- movement ---------------------------------------------------------
    def advance(self, now: Optional[datetime] = None) -> None:
        """Convert elapsed wall-clock time into distance along the route."""
        if not self.running or self.last_tick is None:
            return

        now = now or datetime.now(timezone.utc)
        elapsed_hr = (now - self.last_tick).total_seconds() / 3600.0
        self.last_tick = now
        if elapsed_hr <= 0:
            return

        self.distance_travelled_nm += (
            self.cruise_speed_knots * self.speed_multiplier * elapsed_hr
        )

        if self.distance_travelled_nm >= self.total_nm:
            self.distance_travelled_nm = self.total_nm
            self.running = False
            self.finished = True
            self.last_tick = None

    def position(self) -> tuple[float, float, float]:
        """Interpolated (lat, lon, heading) at the current distance."""
        if len(self.route) == 1:
            lat, lon = self.route[0]
            return lat, lon, 0.0

        travelled = min(self.distance_travelled_nm, self.total_nm)

        # locate the leg containing `travelled`
        leg = 0
        for i in range(len(self.cumulative_nm) - 1):
            if self.cumulative_nm[i + 1] >= travelled:
                leg = i
                break
        else:
            leg = len(self.route) - 2

        start_nm = self.cumulative_nm[leg]
        end_nm = self.cumulative_nm[leg + 1]
        lat1, lon1 = self.route[leg]
        lat2, lon2 = self.route[leg + 1]

        leg_length = end_nm - start_nm
        t = 0.0 if leg_length <= 0 else (travelled - start_nm) / leg_length
        t = min(max(t, 0.0), 1.0)

        # linear interpolation is accurate here because grid legs are short
        lat = lat1 + (lat2 - lat1) * t
        lon = lon1 + (lon2 - lon1) * t
        return lat, lon, _bearing_deg(lat1, lon1, lat2, lon2)
        # --- hindrance detection & automatic rerouting -------------------------
    def _tick(self, now: Optional[datetime] = None) -> None:
        """Advance the simulation one step, handling the obstacle state
        machine (NONE -> DETECTED -> AVOIDED) along the way.

        While `hindrance_state == "DETECTED"` the ship is deliberately
        frozen (no call to `advance()`) so it never crosses the obstacle —
        movement resumes only once the reroute has been computed.
        """
        now = now or datetime.now(timezone.utc)

        if self.hindrance_state == "DETECTED":
            if self.reroute_pause_until and now >= self.reroute_pause_until:
                self._reroute_around_obstacle(now)
            return

        self.advance(now)

        if self.obstacle and not self.rerouted and self.running:
            lat, lon, _ = self.position()
            if haversine_nm(lat, lon, *self.obstacle) <= self.obstacle_radius_nm:
                self.original_route = list(self.route)
                self.hindrance_state = "DETECTED"
                self.running = False
                self.last_tick = None
                # brief pause so the dashboard visibly shows "Hindrance
                # Detected" before "Rerouting" — matches the demo timeline.
                self.reroute_pause_until = now + timedelta(seconds=4)

    def _reroute_around_obstacle(self, now: datetime) -> None:
        """Recompute a route from the current position to the destination
        that avoids the obstacle, using the existing A* engine, then resume
        movement along it."""
        from app.routing.grid import build_grid_for_voyage
        from app.routing.pathfinding import NoRouteFoundError, astar_route
        from app.routing.weather_field import WeatherField
        from app.schemas import VesselProfile

        lat, lon, _ = self.position()
        dest_lat, dest_lon = self.route[-1]

        try:
            grid = build_grid_for_voyage(lat, lon, dest_lat, dest_lon, margin_deg=5.0)
            if self.obstacle:
                grid.block_radius(
                    self.obstacle[0], self.obstacle[1], self.obstacle_block_radius_deg
                )
            start = grid.nearest_navigable(lat, lon)
            goal = grid.nearest_navigable(dest_lat, dest_lon)
            vessel = VesselProfile(cruise_speed_knots=min(self.cruise_speed_knots, 40.0))
            path, _time_hr, _fuel, _risk = astar_route(
                grid, start, goal, vessel, WeatherField.empty(), "safest"
            )
            self.alternate_route = list(path)
            self.route = list(path)
            self.__post_init__()  # rebuild cumulative_nm/total_nm for the new route
            self.distance_travelled_nm = 0.0
        except NoRouteFoundError:
            # Demo must never get stuck: keep the original route rather than
            # crash the simulation if no detour can be found.
            self.alternate_route = None

        self.hindrance_state = "AVOIDED"
        self.rerouted = True
        self.running = True
        self.last_tick = now

    def replace_remaining_route(self, new_route: list[tuple[float, float]]) -> None:
        """Splice a newly planned leg onto the sailed prefix without teleporting."""
        self.advance()
        if len(new_route) < 2:
            return
        old_distance = self.distance_travelled_nm
        lat, lon, _ = self.position()
        leg = max(
            0,
            next((i for i in range(len(self.cumulative_nm) - 1)
                  if self.cumulative_nm[i + 1] >= old_distance), len(self.route) - 2),
        )
        prefix = self.route[: leg + 1] + [(lat, lon)]
        route = prefix + new_route[1:]
        # Drop duplicate adjacent points at the splice.
        self.route = [route[0]] + [p for i, p in enumerate(route[1:], 1)
                                   if haversine_nm(*route[i - 1], *p) > 0.01]
        self.cumulative_nm = [0.0]
        for (a, b), (c, d) in zip(self.route, self.route[1:]):
            self.cumulative_nm.append(self.cumulative_nm[-1] + haversine_nm(a, b, c, d))
        self.total_nm = self.cumulative_nm[-1] if self.cumulative_nm else 0.0
        # Preserve the traveled distance based on the actual prefix geometry.
        self.distance_travelled_nm = sum(
            haversine_nm(a[0], a[1], b[0], b[1])
            for a, b in zip(prefix, prefix[1:])
        )
        self.finished = False
        if self.running:
            self.last_tick = datetime.now(timezone.utc)

    @property
    def progress_percent(self) -> float:
        if self.total_nm <= 0:
            return 100.0 if self.finished else 0.0
        return round(min(self.distance_travelled_nm / self.total_nm, 1.0) * 100.0, 1)

    @property
    def status(self) -> str:
        if self.finished:
            return "ARRIVED"
        if self.hindrance_state == "DETECTED":      # <-- add this line
            return "HINDRANCE_DETECTED" 
        if self.running:
            return "UNDERWAY"
        return "STOPPED"

    @property
    def current_speed_knots(self) -> float:
        return self.cruise_speed_knots if self.running else 0.0

    def eta(self) -> Optional[datetime]:
        """Projected arrival, from remaining distance at cruise speed.

        Reported in real sailing hours, deliberately ignoring the demo speed
        multiplier — a 5x playback should not claim the ship arrives 5x
        sooner in the real world.
        """
        remaining = max(self.total_nm - self.distance_travelled_nm, 0.0)
        if self.cruise_speed_knots <= 0:
            return None
        return datetime.now(timezone.utc) + timedelta(
            hours=remaining / self.cruise_speed_knots
        )

    def to_fix(self) -> VesselFix:
        """Snapshot the simulation as a position report."""
        self._tick()
        lat, lon, heading = self.position()
        return VesselFix(
            vessel_id=self.vessel_id,
            voyage_id=self.voyage_id,
            latitude=round(lat, 6),
            longitude=round(lon, 6),
            speed_knots=round(self.current_speed_knots, 1),
            heading_deg=round(heading, 1),
            status=self.status,  # type: ignore[arg-type]
            source="simulated",
            distance_travelled_nm=round(self.distance_travelled_nm, 1),
            distance_remaining_nm=round(
                max(self.total_nm - self.distance_travelled_nm, 0.0), 1
            ),
            progress_percent=self.progress_percent,
            eta=self.eta(),
        )


class SimulationRegistry:
    """Thread-safe store of active voyage simulations.

    Access is guarded because FastAPI serves requests from a thread pool and
    the WebSocket push loop touches the same objects.
    """

    def __init__(self) -> None:
        self._sims: dict[int, VoyageSimulation] = {}
        self._lock = threading.RLock()

    def create(
        self,
        voyage_id: int,
        vessel_id: int,
        route_points_json: str | None,
        cruise_speed_knots: float,
        origin: tuple[float, float] | None = None,
        destination: tuple[float, float] | None = None,
    ) -> VoyageSimulation:
        """Build (or rebuild) the simulation for a voyage from its saved route."""
        route = self._parse_route(route_points_json)

        # Fall back to a two-point route if the voyage predates route storage,
        # so tracking still works on older saved voyages.
        if len(route) < 2 and origin and destination:
            route = [origin, destination]
        if len(route) < 2:
            raise ValueError(
                "Voyage has no usable route geometry to simulate movement along."
            )

        sim = VoyageSimulation(
            voyage_id=voyage_id,
            vessel_id=vessel_id,
            route=route,
            cruise_speed_knots=max(cruise_speed_knots, 0.1),
        )
        # Dummy demo obstacle: placed ~40% of the way along the route so the
        # simulation reliably detects it and demonstrates rerouting, without
        # needing any real maritime hazard feed. Skipped for very short
        # routes where there isn't room to detect-then-detour meaningfully.
        if len(route) >= 4:
            idx = max(1, min(len(route) - 2, round(len(route) * 0.4)))
            obstacle_lat, obstacle_lon = route[idx]
            sim.set_obstacle(obstacle_lat, obstacle_lon)
        with self._lock:
            self._sims[voyage_id] = sim
        return sim

    @staticmethod
    def _parse_route(route_points_json: str | None) -> list[tuple[float, float]]:
        if not route_points_json:
            return []
        try:
            raw = json.loads(route_points_json)
        except (TypeError, ValueError):
            return []
        route: list[tuple[float, float]] = []
        for item in raw or []:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                route.append((float(item[0]), float(item[1])))
            elif isinstance(item, dict) and "lat" in item:
                route.append((float(item["lat"]), float(item["lon"])))
        return route

    def get(self, voyage_id: int) -> Optional[VoyageSimulation]:
        with self._lock:
            return self._sims.get(voyage_id)

    def get_by_vessel(self, vessel_id: int) -> Optional[VoyageSimulation]:
        """Most relevant simulation for a vessel: prefer a running one,
        otherwise the most recently created."""
        with self._lock:
            matches = [s for s in self._sims.values() if s.vessel_id == vessel_id]
        if not matches:
            return None
        running = [s for s in matches if s.running]
        return (running or matches)[-1]

    def all(self) -> list[VoyageSimulation]:
        with self._lock:
            return list(self._sims.values())

    def remove(self, voyage_id: int) -> None:
        with self._lock:
            self._sims.pop(voyage_id, None)

    def clear(self) -> None:
        with self._lock:
            self._sims.clear()


# process-wide registry
simulation_registry = SimulationRegistry()
