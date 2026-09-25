export type VesselType =
  | "container"
  | "tanker"
  | "bulk_carrier"
  | "cruise"
  | "fishing";
export type RouteStrategy = "fastest" | "efficient" | "safest";
export type VoyageStatus = "Planned" | "In-Progress" | "Completed";
export type AlertType = "StormWarning" | "RouteChange";
export type AlertStatus = "Read" | "Unread";
export type UserRole = "Operator" | "Admin";

export interface User {
  id: number;
  name: string;
  email: string;
  role: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Coordinate {
  lat: number;
  lon: number;
}

export interface VesselProfile {
  name: string;
  vessel_type: VesselType;
  cruise_speed_knots: number;
  draft_m: number;
  deadweight_tons: number;
  fuel_rate_ton_per_hr?: number | null;
}

export interface RouteRequest {
  origin: Coordinate;
  destination: Coordinate;
  vessel: VesselProfile;
  depart_time?: string | null;
}

export interface RoutePoint {
  lat: number;
  lon: number;
}

export interface RouteOption {
  strategy: RouteStrategy;
  points: RoutePoint[];
  risk_segments: number[];
  distance_nm: number;
  duration_hr: number;
  fuel_tons: number;
  co2_tons: number;
  risk_score: number;
  sustainability_score: number;
}

export interface RouteResponse {
  origin: Coordinate;
  destination: Coordinate;
  vessel: VesselProfile;
  options: RouteOption[];
  warnings: string[];
}

export interface VesselCreate {
  name: string;
  vessel_type: VesselType;
  cruise_speed_knots: number;
  draft_m: number;
  deadweight_tons: number;
  fuel_rate_ton_per_hr?: number | null;
  mmsi?: string | null;
}

export interface VesselOut extends VesselCreate {
  id: number;
  owner_id?: number | null;
}

export interface VoyageOut {
  id: number;
  vessel_id: number;
  created_by?: number | null;
  start_port?: string | null;
  end_port?: string | null;
  origin_lat: number;
  origin_lon: number;
  dest_lat: number;
  dest_lon: number;
  strategy: string;
  status: string;
  distance_nm: number;
  duration_hr: number;
  fuel_tons: number;
  co2_tons: number;
  created_at: string;
}

export interface VoyageCreate {
  vessel_id: number;
  start_port?: string;
  end_port?: string;
  origin: Coordinate;
  destination: Coordinate;
  strategy: RouteStrategy;
  status?: VoyageStatus;
  distance_nm: number;
  duration_hr: number;
  fuel_tons: number;
  co2_tons: number;
  route_points: RoutePoint[];
  risk_segments?: number[];
}

export interface WaypointOut {
  id: number;
  voyage_id: number;
  sequence: number;
  latitude: number;
  longitude: number;
  eta?: string | null;
  risk_score: number;
}

export interface WeatherPoint {
  lat: number;
  lon: number;
  wave_height_m: number;
  wave_direction_deg?: number | null;
  wave_period_s?: number | null;
  swell_wave_height_m?: number | null;
  wind_wave_height_m?: number | null;
  sea_surface_temperature_c?: number | null;
  ocean_current_velocity_kmh?: number | null;
  ocean_current_direction_deg?: number | null;
  wind_speed_kmh: number;
  wind_direction_deg?: number | null;
}

export interface AlertOut {
  id: number;
  voyage_id: number;
  type: AlertType;
  message: string;
  status: AlertStatus;
  created_at: string;
}

// --- Ports -----------------------------------------------------------------
export type PortType = "Major Port" | "Other Port";

export interface Port {
  id: string;
  name: string;
  display_name: string;
  state: string;
  country: string;
  latitude: number;
  longitude: number;
  port_type: string;
  port_code?: string | null;
  description?: string | null;
}

export interface PortListResponse {
  ports: Port[];
  count: number;
}

// --- Live tracking ----------------------------------------------------------
export type VesselStatus =
  | "UNDERWAY"
  | "MOORED"
  | "STOPPED"
  | "ARRIVED"
  | "UNKNOWN";
export type PositionSource = "simulated" | "ais" | "manual";

export interface VesselPosition {
  vessel_id: number;
  voyage_id?: number | null;
  latitude: number;
  longitude: number;
  speed_knots: number;
  heading_deg: number;
  status: VesselStatus;
  source: PositionSource;
  is_simulated: boolean;
  timestamp: string;
  distance_travelled_nm?: number | null;
  distance_remaining_nm?: number | null;
  progress_percent?: number | null;
  eta?: string | null;
}

export interface TrackPoint {
  latitude: number;
  longitude: number;
  speed_knots?: number | null;
  heading_deg?: number | null;
  timestamp: string;
}

export interface VesselTrackResponse {
  vessel_id: number;
  voyage_id?: number | null;
  points: TrackPoint[];
  count: number;
}

export interface LiveConditions {
  weather: WeatherPoint;
  wave_risk: number;
  wind_risk: number;
  overall_risk: number;
  wave_risk_label: string;
  wind_risk_label: string;
  overall_risk_label: string;
}

export interface VoyageTracking {
  voyage_id: number;
  vessel_id: number;
  vessel_name?: string | null;
  start_port?: string | null;
  end_port?: string | null;
  status: string;
  simulation_running: boolean;
  speed_multiplier: number;
  position?: VesselPosition | null;
  total_distance_nm: number;
  distance_travelled_nm: number;
  distance_remaining_nm: number;
  progress_percent: number;
  eta?: string | null;
  conditions?: LiveConditions | null;
  // --- dummy hindrance / rerouting demo ---------------------------------
  hindrance_state?: "NONE" | "DETECTED" | "AVOIDED";
  obstacle?: Coordinate | null;
  original_route?: RoutePoint[] | null;
  alternate_route?: RoutePoint[] | null;
}

export type SimulationAction = "start" | "pause" | "reset" | "speed";

export interface SimulationControl {
  action: SimulationAction;
  speed_multiplier?: number;
}

export interface TrackingStatus {
  enabled: boolean;
  provider: string;
  simulated: boolean;
  label: string;
  detail: string;
  update_interval_s: number;
}
