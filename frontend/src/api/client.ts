import axios from "axios";
import type {
  AlertOut,
  AlertStatus,
  AuthResponse,
  Port,
  PortListResponse,
  RouteRequest,
  RouteResponse,
  SimulationControl,
  TrackingStatus,
  User,
  VesselCreate,
  VesselOut,
  VesselPosition,
  VesselTrackResponse,
  VoyageCreate,
  VoyageOut,
  VoyageStatus,
  VoyageTracking,
  WaypointOut,
  WeatherPoint,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

const client = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// attach the JWT (if present) to every outgoing request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("seapath_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const api = {
  health: () => client.get("/health").then((r) => r.data),

  // --- auth ---
  register: (name: string, email: string, password: string) =>
    client.post<AuthResponse>("/auth/register", { name, email, password }).then((r) => r.data),

  login: (email: string, password: string) =>
    client.post<AuthResponse>("/auth/login", { email, password }).then((r) => r.data),

  me: () => client.get<User>("/auth/me").then((r) => r.data),

  // --- routing ---
  optimizeRoute: (req: RouteRequest) =>
    client.post<RouteResponse>("/route/optimize", req).then((r) => r.data),

  reoptimizeVoyage: (voyageId: number, currentPosition?: { lat: number; lon: number }) =>
    client
      .post<RouteResponse>(`/route/reoptimize/${voyageId}`, currentPosition ? { current_position: currentPosition } : null)
      .then((r) => r.data),

  // --- fleet ---
  listFleet: () => client.get<VesselOut[]>("/fleet").then((r) => r.data),

  createVessel: (v: VesselCreate) => client.post<VesselOut>("/fleet", v).then((r) => r.data),

  updateVesselMmsi: (id: number, mmsi: string | null) =>
    client.patch<VesselOut>(`/fleet/${id}/mmsi`, { mmsi }).then((r) => r.data),

  deleteVessel: (id: number) => client.delete(`/fleet/${id}`),

  // --- voyages ---
  listVoyages: () => client.get<VoyageOut[]>("/voyages").then((r) => r.data),

  createVoyage: (v: VoyageCreate) => client.post<VoyageOut>("/voyages", v).then((r) => r.data),

  updateVoyageStatus: (id: number, status: VoyageStatus) =>
    client.patch<VoyageOut>(`/voyages/${id}/status`, { status }).then((r) => r.data),

  getWaypoints: (voyageId: number) =>
    client.get<WaypointOut[]>(`/voyages/${voyageId}/waypoints`).then((r) => r.data),

  voyageReportUrl: (id: number) => `${API_BASE}/voyages/${id}/report`,

  downloadVoyageReport: async (id: number) => {
    const resp = await client.get(`/voyages/${id}/report`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([resp.data], { type: "application/pdf" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `voyage_${id}_report.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  // --- weather ---
  weather: (lat: number, lon: number) =>
    client.get<WeatherPoint>("/weather", { params: { lat, lon } }).then((r) => r.data),

  // --- alerts ---
  listAlerts: () => client.get<AlertOut[]>("/alerts").then((r) => r.data),

  updateAlertStatus: (id: number, status: AlertStatus) =>
    client.patch<AlertOut>(`/alerts/${id}`, { status }).then((r) => r.data),

  // --- ports ---
  listPorts: (params?: { search?: string; state?: string; port_type?: string }) =>
    client.get<PortListResponse>("/ports", { params }).then((r) => r.data),

  getPort: (portId: string) => client.get<Port>(`/ports/${portId}`).then((r) => r.data),

  listPortStates: () => client.get<string[]>("/ports/states").then((r) => r.data),

  // --- live tracking ---
  trackingStatus: () => client.get<TrackingStatus>("/tracking/status").then((r) => r.data),

  vesselLocation: (vesselId: number) =>
    client.get<VesselPosition>(`/vessels/${vesselId}/location`).then((r) => r.data),

  reportVesselLocation: (vesselId: number, body: Partial<VesselPosition>) =>
    client.post<VesselPosition>(`/vessels/${vesselId}/location`, body).then((r) => r.data),

  vesselTrack: (vesselId: number, voyageId?: number) =>
    client
      .get<VesselTrackResponse>(`/vessels/${vesselId}/track`, {
        params: voyageId ? { voyage_id: voyageId } : undefined,
      })
      .then((r) => r.data),

  fleetLocations: () =>
    client.get<VesselPosition[]>("/vessels/locations").then((r) => r.data),

  voyageTracking: (voyageId: number) =>
    client.get<VoyageTracking>(`/voyages/${voyageId}/tracking`).then((r) => r.data),

  controlSimulation: (voyageId: number, control: SimulationControl) =>
    client.post<VoyageTracking>(`/voyages/${voyageId}/tracking`, control).then((r) => r.data),

  /**
   * WebSocket URL for a vessel's live position feed.
   *
   * A browser cannot set an Authorization header on a WebSocket handshake,
   * so the JWT travels as a query parameter — the backend validates it with
   * the same signature check used by the REST dependency.
   */
  vesselLocationSocketUrl: (vesselId: number): string | null => {
    const token = localStorage.getItem("seapath_token");
    if (!token) return null;

    const base = import.meta.env.VITE_API_BASE_URL;
    let origin = window.location.origin;
    if (base && /^https?:\/\//i.test(base)) {
      origin = new URL(base).origin;
    }
    const wsOrigin = origin.replace(/^http/i, "ws");
    return `${wsOrigin}/ws/vessels/${vesselId}/location?token=${encodeURIComponent(token)}`;
  },
};

export default api;
