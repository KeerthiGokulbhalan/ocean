from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

VesselType = Literal["container", "tanker", "bulk_carrier", "cruise", "fishing"]
RouteStrategy = Literal["fastest", "efficient", "safest"]
VoyageStatus = Literal["Planned", "In-Progress", "Completed"]
AlertType = Literal["StormWarning", "RouteChange"]
AlertStatus = Literal["Read", "Unread"]
UserRole = Literal["Operator", "Admin"]


# --- Auth --------------------------------------------------------------
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: UserRole = "Operator"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Geo / routing --------------------------------------------------------
class Coordinate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class VesselProfile(BaseModel):
    name: str = "Vessel"
    vessel_type: VesselType = "container"
    cruise_speed_knots: float = Field(18.0, gt=0, le=40)
    draft_m: float = Field(10.0, gt=0)
    deadweight_tons: float = Field(20000.0, gt=0)
    fuel_rate_ton_per_hr: Optional[float] = None  # overrides the type default if given


class RouteRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    vessel: VesselProfile
    depart_time: Optional[datetime] = None


class VoyageReoptimizeRequest(BaseModel):
    current_position: Coordinate


class RoutePoint(BaseModel):
    lat: float
    lon: float


class WeatherRouteAlert(BaseModel):
    """Weather warning tied to one consecutive pair of route points."""
    segment_index: int
    start: Coordinate
    end: Coordinate
    midpoint: Coordinate
    wave_height_m: float
    wind_speed_kmh: float
    severity: Literal["warning", "severe"]
    message: str


class RouteOption(BaseModel):
    strategy: RouteStrategy
    points: list[RoutePoint]
    # per-point risk score (0-1), same length/order as `points` — powers the
    # risk-radar heatmap overlay on the frontend map
    risk_segments: list[float]
    weather_data_available: bool = False
    weather_coverage_percent: float = 0.0
    weather_alerts: list[WeatherRouteAlert] = Field(default_factory=list)
    distance_nm: float
    duration_hr: float
    fuel_tons: float
    co2_tons: float
    risk_score: float  # 0 (safe) - 1 (high risk), max risk along the route
    sustainability_score: float  # 0-100, higher is better


class RouteResponse(BaseModel):
    origin: Coordinate
    destination: Coordinate
    vessel: VesselProfile
    options: list[RouteOption]
    warnings: list[str] = []


# --- Fleet ---------------------------------------------------------------
class VesselCreate(BaseModel):
    name: str
    vessel_type: VesselType
    cruise_speed_knots: float = 18.0
    draft_m: float = 10.0
    deadweight_tons: float = 20000.0
    fuel_rate_ton_per_hr: Optional[float] = None
    mmsi: Optional[str] = Field(None, pattern=r"^\d{9}$")


class VesselOut(VesselCreate):
    id: int
    owner_id: Optional[int] = None

    class Config:
        from_attributes = True


class VesselMmsiUpdate(BaseModel):
    mmsi: Optional[str] = Field(None, pattern=r"^\d{9}$")


# --- Voyages ---------------------------------------------------------------
class VoyageCreate(BaseModel):
    vessel_id: int
    start_port: Optional[str] = None
    end_port: Optional[str] = None
    origin: Coordinate
    destination: Coordinate
    strategy: RouteStrategy
    status: VoyageStatus = "Planned"
    distance_nm: float
    duration_hr: float
    fuel_tons: float
    co2_tons: float
    route_points: list[RoutePoint]
    risk_segments: list[float] = []
    weather_alerts: list[WeatherRouteAlert] = Field(default_factory=list)


class VoyageOut(BaseModel):
    id: int
    vessel_id: int
    created_by: Optional[int] = None
    start_port: Optional[str] = None
    end_port: Optional[str] = None
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    strategy: str
    status: str
    distance_nm: float
    duration_hr: float
    fuel_tons: float
    co2_tons: float
    created_at: datetime

    class Config:
        from_attributes = True


class VoyageAnalytics(BaseModel):
    voyage_id: int
    data_source: str
    is_simulated: bool
    tracking_points: int
    actual_available: bool
    planned_distance_nm: float
    actual_distance_nm: Optional[float] = None
    distance_variance_nm: Optional[float] = None
    planned_duration_hr: float
    actual_duration_hr: Optional[float] = None
    duration_variance_hr: Optional[float] = None
    planned_fuel_tons: float
    actual_fuel_tons: Optional[float] = None
    fuel_variance_tons: Optional[float] = None
    planned_co2_tons: float
    actual_co2_tons: Optional[float] = None
    co2_variance_tons: Optional[float] = None
    progress_percent: Optional[float] = None
    fuel_calculation_method: str
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    note: str


class VoyageStatusUpdate(BaseModel):
    status: VoyageStatus


# --- Waypoints ---------------------------------------------------------------
class WaypointOut(BaseModel):
    id: int
    voyage_id: int
    sequence: int
    latitude: float
    longitude: float
    eta: Optional[datetime] = None
    risk_score: float

    class Config:
        from_attributes = True


# --- Weather ---------------------------------------------------------------
class WeatherPoint(BaseModel):
    lat: float
    lon: float
    wave_height_m: float
    wave_direction_deg: Optional[float] = None
    wave_period_s: Optional[float] = None
    swell_wave_height_m: Optional[float] = None
    wind_wave_height_m: Optional[float] = None
    sea_surface_temperature_c: Optional[float] = None
    ocean_current_velocity_kmh: Optional[float] = None
    ocean_current_direction_deg: Optional[float] = None
    wind_speed_kmh: float
    wind_direction_deg: Optional[float] = None
    data_available: bool = False
    marine_data_available: bool = False
    wind_data_available: bool = False
    retrieved_at_utc: Optional[str] = None


# --- Alerts ---------------------------------------------------------------
class AlertOut(BaseModel):
    id: int
    voyage_id: int
    type: str
    message: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AlertStatusUpdate(BaseModel):
    status: AlertStatus


# --- Reports ---------------------------------------------------------------
class ReportOut(BaseModel):
    id: int
    voyage_id: int
    fuel_used_tons: float
    co2_emitted_tons: float
    distance_covered_nm: float
    created_at: datetime

    class Config:
        from_attributes = True


# --- Ports -----------------------------------------------------------------
class PortOut(BaseModel):
    id: str
    name: str
    display_name: str
    state: str
    country: str
    latitude: float
    longitude: float
    port_type: str
    port_code: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class PortListResponse(BaseModel):
    ports: list[PortOut]
    count: int


# --- Live tracking ----------------------------------------------------------
VesselStatusLiteral = Literal["UNDERWAY", "MOORED", "STOPPED", "ARRIVED", "UNKNOWN"]
PositionSourceLiteral = Literal["simulated", "ais", "manual"]


class VesselPositionIn(BaseModel):
    """Externally-reported position (manual entry or an AIS bridge)."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed_knots: float = Field(0.0, ge=0, le=60)
    heading_deg: float = Field(0.0, ge=0, lt=360)
    status: VesselStatusLiteral = "UNDERWAY"
    voyage_id: Optional[int] = None
    timestamp: Optional[datetime] = None


class VesselPositionOut(BaseModel):
    vessel_id: int
    voyage_id: Optional[int] = None
    latitude: float
    longitude: float
    speed_knots: float = 0.0
    heading_deg: float = 0.0
    status: str = "UNKNOWN"
    source: str = "simulated"
    is_simulated: bool = True
    timestamp: datetime

    # voyage progress, present when the position is tied to an active voyage
    distance_travelled_nm: Optional[float] = None
    distance_remaining_nm: Optional[float] = None
    progress_percent: Optional[float] = None
    eta: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrackPoint(BaseModel):
    latitude: float
    longitude: float
    speed_knots: Optional[float] = None
    heading_deg: Optional[float] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class VesselTrackResponse(BaseModel):
    vessel_id: int
    voyage_id: Optional[int] = None
    points: list[TrackPoint]
    count: int


class LiveConditions(BaseModel):
    weather: WeatherPoint
    wave_risk: float
    wind_risk: float
    overall_risk: float
    wave_risk_label: str
    wind_risk_label: str
    overall_risk_label: str


class VoyageTracking(BaseModel):
    """Everything the voyage-progress panel needs, in one round trip."""

    voyage_id: int
    vessel_id: int
    vessel_name: Optional[str] = None
    start_port: Optional[str] = None
    end_port: Optional[str] = None
    status: str
    simulation_running: bool = False
    speed_multiplier: float = 1.0
    position: Optional[VesselPositionOut] = None
    total_distance_nm: float = 0.0
    distance_travelled_nm: float = 0.0
    distance_remaining_nm: float = 0.0
    progress_percent: float = 0.0
    eta: Optional[datetime] = None
    conditions: Optional[LiveConditions] = None
    # --- dummy hindrance / rerouting demo ---------------------------------
    hindrance_state: str = "NONE"  # NONE | DETECTED | AVOIDED
    obstacle: Optional[Coordinate] = None
    original_route: Optional[list[RoutePoint]] = None
    alternate_route: Optional[list[RoutePoint]] = None



class SimulationControl(BaseModel):
    action: Literal["start", "pause", "reset", "speed"]
    speed_multiplier: Optional[float] = Field(None, gt=0, le=50)


class TrackingStatus(BaseModel):
    """Describes the active position feed so the UI can label it honestly."""

    enabled: bool
    provider: str
    simulated: bool
    label: str
    detail: str
    update_interval_s: float
