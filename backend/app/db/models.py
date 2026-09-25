from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="Operator")  # Operator | Admin

    vessels = relationship("Vessel", back_populates="owner")
    voyages = relationship("Voyage", back_populates="created_by_user")


class Vessel(Base):
    __tablename__ = "vessels"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    name = Column(String, nullable=False)
    vessel_type = Column(String, nullable=False)
    cruise_speed_knots = Column(Float, default=18.0)  # maxSpeed
    draft_m = Column(Float, default=10.0)
    deadweight_tons = Column(Float, default=20000.0)
    fuel_rate_ton_per_hr = Column(Float, nullable=True)  # overrides type default if set
    mmsi = Column(String(9), nullable=True, unique=True, index=True)

    owner = relationship("User", back_populates="vessels")
    voyages = relationship("Voyage", back_populates="vessel")
    positions = relationship(
        "VesselPosition", back_populates="vessel", cascade="all, delete-orphan"
    )


class Voyage(Base):
    __tablename__ = "voyages"

    id = Column(Integer, primary_key=True, index=True)
    vessel_id = Column(Integer, ForeignKey("vessels.id"))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    start_port = Column(String, nullable=True)
    end_port = Column(String, nullable=True)
    origin_lat = Column(Float)
    origin_lon = Column(Float)
    dest_lat = Column(Float)
    dest_lon = Column(Float)

    mode = Column(String, default="Fastest")  # Fastest | Fuel-Efficient | Safest (display label)
    strategy = Column(String, default="fastest")  # fastest | efficient | safest (routing engine key)
    status = Column(String, default="Planned")  # Planned | In-Progress | Completed

    distance_nm = Column(Float)
    duration_hr = Column(Float)
    fuel_tons = Column(Float)
    co2_tons = Column(Float)

    # store the route polyline as JSON text ("[[lat,lon], ...]")
    route_points_json = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    vessel = relationship("Vessel", back_populates="voyages")
    created_by_user = relationship("User", back_populates="voyages")
    waypoints = relationship("Waypoint", back_populates="voyage", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="voyage", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="voyage", cascade="all, delete-orphan")
    positions = relationship(
        "VesselPosition", back_populates="voyage", cascade="all, delete-orphan"
    )


class Waypoint(Base):
    __tablename__ = "waypoints"

    id = Column(Integer, primary_key=True, index=True)
    voyage_id = Column(Integer, ForeignKey("voyages.id"))
    sequence = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    eta = Column(DateTime, nullable=True)
    risk_score = Column(Float, default=0.0)

    voyage = relationship("Voyage", back_populates="waypoints")


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    wave_height_m = Column(Float, default=0.0)
    wind_speed_kmh = Column(Float, default=0.0)
    current_speed_kmh = Column(Float, default=0.0)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    voyage_id = Column(Integer, ForeignKey("voyages.id"))
    type = Column(String, nullable=False)  # StormWarning | RouteChange
    message = Column(Text, nullable=False)
    status = Column(String, default="Unread")  # Read | Unread
    created_at = Column(DateTime, default=datetime.utcnow)

    voyage = relationship("Voyage", back_populates="alerts")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    voyage_id = Column(Integer, ForeignKey("voyages.id"))
    fuel_used_tons = Column(Float)
    co2_emitted_tons = Column(Float)
    distance_covered_nm = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    voyage = relationship("Voyage", back_populates="reports")


# --- Live vessel positions -------------------------------------------------
class VesselPosition(Base):
    """A single timestamped AIS-style position report for a vessel.

    Rows are appended by the tracking service (see services/tracking.py) at a
    throttled interval — see POSITION_PERSIST_INTERVAL_S — so a long voyage
    produces a reviewable track without unbounded high-frequency writes.
    """

    __tablename__ = "vessel_positions"

    id = Column(Integer, primary_key=True, index=True)
    vessel_id = Column(Integer, ForeignKey("vessels.id"), nullable=False, index=True)
    voyage_id = Column(Integer, ForeignKey("voyages.id"), nullable=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed_knots = Column(Float, nullable=True)
    heading_deg = Column(Float, nullable=True)
    status = Column(String, default="UNDERWAY")  # UNDERWAY | MOORED | STOPPED | ARRIVED
    source = Column(String, default="simulated")  # simulated | ais | manual
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    fuel_remaining_tons = Column(Float, nullable=True)
    distance_remaining_nm = Column(Float, nullable=True)

    vessel = relationship("Vessel", back_populates="positions")
    voyage = relationship("Voyage", back_populates="positions")


# composite index: the hot query is "latest positions for this vessel"
Index("ix_vessel_positions_vessel_time", VesselPosition.vessel_id, VesselPosition.timestamp)


# --- Port reference data ----------------------------------------------------
class Port(Base):
    """Reference table of Indian ports, seeded from app/data/indian_ports.py.

    Uses a string primary key (e.g. "IN_CHENNAI") so the dataset is the source
    of truth and re-seeding is a stable upsert rather than an append.
    """

    __tablename__ = "ports"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    state = Column(String, nullable=False, index=True)
    country = Column(String, nullable=False, default="India")
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    port_type = Column(String, nullable=False, index=True)
    port_code = Column(String, nullable=True, index=True)  # UN/LOCODE where known
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# supports the "ports within this map viewport" bounding-box query
Index("ix_ports_lat_lon", Port.latitude, Port.longitude)
