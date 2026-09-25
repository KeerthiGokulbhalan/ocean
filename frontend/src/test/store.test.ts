import { beforeEach, describe, expect, it } from "vitest";
import { act } from "@testing-library/react";
import { useAppStore } from "../store/useAppStore";
import type { Port, TrackPoint, VesselPosition } from "../types";

const PORT: Port = {
  id: "IN_CHENNAI",
  name: "Chennai Port",
  display_name: "Chennai Port — Tamil Nadu",
  state: "Tamil Nadu",
  country: "India",
  latitude: 13.098,
  longitude: 80.293,
  port_type: "Major Port",
  port_code: "INMAA",
};

function point(lon: number): TrackPoint {
  return { latitude: 13, longitude: lon, timestamp: new Date().toISOString() };
}

const POSITION: VesselPosition = {
  vessel_id: 1,
  voyage_id: 7,
  latitude: 12.8,
  longitude: 80.3,
  speed_knots: 14,
  heading_deg: 285,
  status: "UNDERWAY",
  source: "simulated",
  is_simulated: true,
  timestamp: new Date().toISOString(),
};

describe("useAppStore", () => {
  beforeEach(() => {
    act(() => {
      useAppStore.getState().resetTracking();
      useAppStore.getState().setSelectedOriginPort(null);
      useAppStore.getState().setSelectedDestinationPort(null);
      useAppStore.getState().setVesselTrack([]);
    });
  });

  it("preserves the existing route-planning state", () => {
    const state = useAppStore.getState();
    expect(state.selectedStrategy).toBe("efficient");
    expect(state.vessel.vessel_type).toBe("container");
    expect(state.lastRoute).toBeNull();
  });

  it("stores origin and destination port selections", () => {
    act(() => useAppStore.getState().setSelectedOriginPort(PORT));
    expect(useAppStore.getState().selectedOriginPort?.id).toBe("IN_CHENNAI");
  });

  it("marks ports as loaded once set", () => {
    act(() => useAppStore.getState().setPorts([PORT]));
    expect(useAppStore.getState().portsLoaded).toBe(true);
    expect(useAppStore.getState().ports).toHaveLength(1);
  });

  it("tracks the active vessel and voyage", () => {
    act(() => useAppStore.getState().setActiveVessel(3, 9));
    expect(useAppStore.getState().activeVesselId).toBe(3);
    expect(useAppStore.getState().activeVoyageId).toBe(9);
  });

  it("appends track points in order", () => {
    act(() => {
      useAppStore.getState().appendTrackPoint(point(80));
      useAppStore.getState().appendTrackPoint(point(79));
    });
    const track = useAppStore.getState().vesselTrack;
    expect(track).toHaveLength(2);
    expect(track[1].longitude).toBe(79);
  });

  it("bounds the in-memory trail so long voyages cannot grow without limit", () => {
    act(() => {
      for (let i = 0; i < 600; i++) useAppStore.getState().appendTrackPoint(point(i));
    });
    const track = useAppStore.getState().vesselTrack;
    expect(track).toHaveLength(500);
    // keeps the most recent points
    expect(track[track.length - 1].longitude).toBe(599);
  });

  it("resetTracking clears live state but keeps port selections", () => {
    act(() => {
      useAppStore.getState().setSelectedOriginPort(PORT);
      useAppStore.getState().setActiveVessel(1, 7);
      useAppStore.getState().setCurrentVesselPosition(POSITION);
      useAppStore.getState().appendTrackPoint(point(80));
    });

    act(() => useAppStore.getState().resetTracking());

    const state = useAppStore.getState();
    expect(state.activeVesselId).toBeNull();
    expect(state.currentVesselPosition).toBeNull();
    expect(state.vesselTrack).toHaveLength(0);
    // port selection is planning state, not tracking state
    expect(state.selectedOriginPort?.id).toBe("IN_CHENNAI");
  });

  it("toggles the port overlay", () => {
    act(() => useAppStore.getState().setShowPorts(true));
    expect(useAppStore.getState().showPorts).toBe(true);
  });
});
