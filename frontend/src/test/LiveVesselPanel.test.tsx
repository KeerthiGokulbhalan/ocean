import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LiveVesselPanel from "../components/LiveVesselPanel";
import type { TrackingStatus, VesselPosition, VoyageTracking } from "../types";

const POSITION: VesselPosition = {
  vessel_id: 1,
  voyage_id: 7,
  latitude: 12.8475,
  longitude: 80.3512,
  speed_knots: 14.6,
  heading_deg: 285,
  status: "UNDERWAY",
  source: "simulated",
  is_simulated: true,
  timestamp: new Date().toISOString(),
  progress_percent: 34,
};

const TRACKING: VoyageTracking = {
  voyage_id: 7,
  vessel_id: 1,
  vessel_name: "MV SeaPath",
  start_port: "Chennai Port",
  end_port: "Mumbai Port",
  status: "In-Progress",
  simulation_running: true,
  speed_multiplier: 1,
  position: POSITION,
  total_distance_nm: 1240,
  distance_travelled_nm: 420,
  distance_remaining_nm: 820,
  progress_percent: 34,
  eta: "2026-09-18T16:30:00Z",
};

const MOCK_STATUS: TrackingStatus = {
  enabled: true,
  provider: "mock",
  simulated: true,
  label: "LIVE TRACKING — DEMO SIMULATION",
  detail: "Simulated positions.",
  update_interval_s: 5,
};

function setup(overrides: Partial<React.ComponentProps<typeof LiveVesselPanel>> = {}) {
  const onControl = vi.fn();
  const onFocusVessel = vi.fn();
  render(
    <LiveVesselPanel
      tracking={TRACKING}
      position={POSITION}
      status={MOCK_STATUS}
      connection="live"
      onControl={onControl}
      onFocusVessel={onFocusVessel}
      {...overrides}
    />
  );
  return { onControl, onFocusVessel };
}

describe("LiveVesselPanel", () => {
  it("shows vessel, route and voyage figures", () => {
    setup();
    expect(screen.getByText("MV SeaPath")).toBeInTheDocument();
    expect(screen.getByText(/Chennai Port → Mumbai Port/)).toBeInTheDocument();
    expect(screen.getByText("14.6 kn")).toBeInTheDocument();
    expect(screen.getByText("285°")).toBeInTheDocument();
    expect(screen.getByText("420 nm")).toBeInTheDocument();
    expect(screen.getByText("820 nm")).toBeInTheDocument();
  });

  it("reports progress from the tracking payload", () => {
    setup();
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "34");
    expect(screen.getByText("34%")).toBeInTheDocument();
  });

  it("labels simulated feeds so they are not mistaken for real AIS", () => {
    setup();
    expect(screen.getByText(/DEMO SIMULATION/i)).toBeInTheDocument();
  });

  it("marks a real AIS feed differently and hides demo controls", () => {
    setup({
      status: {
        ...MOCK_STATUS,
        provider: "real",
        simulated: false,
        label: "LIVE TRACKING — AIS",
      },
      showDemoControls: false,
    });
    expect(screen.getByText(/LIVE TRACKING — AIS/)).toBeInTheDocument();
    expect(screen.queryByText(/DEMO SIMULATION/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /pause/i })).not.toBeInTheDocument();
  });

  it("shows Pause while the simulation runs and Start when paused", () => {
    const { unmount } = render(
      <LiveVesselPanel
        tracking={{ ...TRACKING, simulation_running: false }}
        position={POSITION}
        status={MOCK_STATUS}
        connection="live"
        onControl={vi.fn()}
        onFocusVessel={vi.fn()}
      />
    );
    expect(screen.getByRole("button", { name: /start/i })).toBeInTheDocument();
    unmount();

    setup();
    expect(screen.getByRole("button", { name: /pause/i })).toBeInTheDocument();
  });

  it("fires simulation controls", async () => {
    const user = userEvent.setup();
    const { onControl } = setup();

    await user.click(screen.getByRole("button", { name: /pause/i }));
    expect(onControl).toHaveBeenCalledWith("pause");

    await user.click(screen.getByRole("button", { name: /reset/i }));
    expect(onControl).toHaveBeenCalledWith("reset");

    await user.click(screen.getByRole("button", { name: "5x" }));
    expect(onControl).toHaveBeenCalledWith("speed", 5);
  });

  it("focuses the map on the vessel", async () => {
    const user = userEvent.setup();
    const { onFocusVessel } = setup();
    await user.click(screen.getByRole("button", { name: /track ship/i }));
    expect(onFocusVessel).toHaveBeenCalled();
  });

  it("disables Track Ship with no position", () => {
    setup({ position: null });
    expect(screen.getByRole("button", { name: /track ship/i })).toBeDisabled();
  });

  it("explains the polling fallback", () => {
    setup({ connection: "polling" });
    expect(screen.getByText(/polling for updates/i)).toBeInTheDocument();
  });

  it("renders live conditions and risk labels", () => {
    setup({
      tracking: {
        ...TRACKING,
        conditions: {
          weather: {
            lat: 12.8,
            lon: 80.3,
            wave_height_m: 2.4,
            wind_speed_kmh: 38,
          },
          wave_risk: 0.4,
          wind_risk: 0.42,
          overall_risk: 0.42,
          wave_risk_label: "Moderate",
          wind_risk_label: "Moderate",
          overall_risk_label: "Moderate",
        },
      },
    });
    expect(screen.getByText("2.4 m")).toBeInTheDocument();
    expect(screen.getByText("38 km/h")).toBeInTheDocument();
    expect(screen.getByText("Overall: Moderate")).toBeInTheDocument();
  });

  it("surfaces a tracking error", () => {
    setup({ error: "Not authorized to track this vessel." });
    expect(screen.getByText(/not authorized/i)).toBeInTheDocument();
  });
});
