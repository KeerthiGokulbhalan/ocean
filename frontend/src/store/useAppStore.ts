import { create } from "zustand";
import type {
  Port,
  RouteResponse,
  TrackPoint,
  TrackingStatus,
  VesselPosition,
  VesselProfile,
  VoyageTracking,
} from "../types";

interface AppState {
  // --- existing route-planning state (unchanged) ---
  lastRoute: RouteResponse | null;
  selectedStrategy: string;
  vessel: VesselProfile;
  setLastRoute: (r: RouteResponse | null) => void;
  setSelectedStrategy: (s: string) => void;
  setVessel: (v: VesselProfile) => void;

  // --- port selection ---
  ports: Port[];
  portsLoaded: boolean;
  selectedOriginPort: Port | null;
  selectedDestinationPort: Port | null;
  setPorts: (p: Port[]) => void;
  setSelectedOriginPort: (p: Port | null) => void;
  setSelectedDestinationPort: (p: Port | null) => void;

  // --- live tracking ---
  trackingStatus: TrackingStatus | null;
  activeVesselId: number | null;
  activeVoyageId: number | null;
  currentVesselPosition: VesselPosition | null;
  vesselTrack: TrackPoint[];
  voyageProgress: VoyageTracking | null;
  showPorts: boolean;
  setTrackingStatus: (s: TrackingStatus | null) => void;
  setActiveVessel: (vesselId: number | null, voyageId: number | null) => void;
  setCurrentVesselPosition: (p: VesselPosition | null) => void;
  setVesselTrack: (t: TrackPoint[]) => void;
  appendTrackPoint: (p: TrackPoint) => void;
  setVoyageProgress: (v: VoyageTracking | null) => void;
  setShowPorts: (show: boolean) => void;
  resetTracking: () => void;
}

/** Keep the in-memory trail bounded so a long simulation can't grow without limit. */
const MAX_CLIENT_TRACK_POINTS = 500;

export const useAppStore = create<AppState>((set) => ({
  lastRoute: null,
  selectedStrategy: "efficient",
  vessel: {
    name: "MV Demo",
    vessel_type: "container",
    cruise_speed_knots: 18,
    draft_m: 10,
    deadweight_tons: 20000,
  },
  setLastRoute: (r) => set({ lastRoute: r }),
  setSelectedStrategy: (s) => set({ selectedStrategy: s }),
  setVessel: (v) => set({ vessel: v }),

  ports: [],
  portsLoaded: false,
  selectedOriginPort: null,
  selectedDestinationPort: null,
  setPorts: (p) => set({ ports: p, portsLoaded: true }),
  setSelectedOriginPort: (p) => set({ selectedOriginPort: p }),
  setSelectedDestinationPort: (p) => set({ selectedDestinationPort: p }),

  trackingStatus: null,
  activeVesselId: null,
  activeVoyageId: null,
  currentVesselPosition: null,
  vesselTrack: [],
  voyageProgress: null,
  showPorts: false,
  setTrackingStatus: (s) => set({ trackingStatus: s }),
  setActiveVessel: (vesselId, voyageId) =>
    set({ activeVesselId: vesselId, activeVoyageId: voyageId }),
  setCurrentVesselPosition: (p) => set({ currentVesselPosition: p }),
  setVesselTrack: (t) => set({ vesselTrack: t.slice(-MAX_CLIENT_TRACK_POINTS) }),
  appendTrackPoint: (p) =>
    set((state) => ({
      vesselTrack: [...state.vesselTrack, p].slice(-MAX_CLIENT_TRACK_POINTS),
    })),
  setVoyageProgress: (v) => set({ voyageProgress: v }),
  setShowPorts: (show) => set({ showPorts: show }),
  resetTracking: () =>
    set({
      activeVesselId: null,
      activeVoyageId: null,
      currentVesselPosition: null,
      vesselTrack: [],
      voyageProgress: null,
    }),
}));
