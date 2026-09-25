import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CurrentLocationWeatherCard from "../components/CurrentLocationWeatherCard";
import api from "../api/client";

vi.mock("../api/client", () => ({
  default: {
    weather: vi.fn(),
  },
}));

function mockGeolocation(impl: (success: PositionCallback, error?: PositionErrorCallback) => void) {
  Object.defineProperty(navigator, "geolocation", {
    value: { getCurrentPosition: vi.fn(impl) },
    configurable: true,
  });
}

describe("CurrentLocationWeatherCard", () => {
  beforeEach(() => {
    vi.mocked(api.weather).mockResolvedValue({
      lat: 13.05,
      lon: 80.28,
      wave_height_m: 1.2,
      wind_speed_kmh: 22,
      wind_direction_deg: 180,
      sea_surface_temperature_c: 28.5,
      ocean_current_velocity_kmh: 2.1,
      ocean_current_direction_deg: 90,
      wave_period_s: 6,
      swell_wave_height_m: 0.8,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    // @ts-expect-error cleaning up the test-defined property
    delete navigator.geolocation;
  });

  it("prompts the user to opt in before requesting location", () => {
    mockGeolocation(() => {});
    render(<CurrentLocationWeatherCard />);
    expect(screen.getByRole("button", { name: /use my current location/i })).toBeInTheDocument();
    // must not call the browser API before the user clicks
    expect(navigator.geolocation.getCurrentPosition).not.toHaveBeenCalled();
  });

  it("shows live conditions once location is granted", async () => {
    mockGeolocation((success) => {
      success({
        coords: { latitude: 13.05, longitude: 80.28 },
      } as GeolocationPosition);
    });
    const user = userEvent.setup();
    render(<CurrentLocationWeatherCard />);

    await user.click(screen.getByRole("button", { name: /use my current location/i }));

    await waitFor(() => {
      expect(screen.getByText("Conditions at your location")).toBeInTheDocument();
    });
    expect(screen.getByText(/refresh my location/i)).toBeInTheDocument();
    expect(api.weather).toHaveBeenCalledWith(13.05, 80.28);
  });

  it("shows a helpful message when permission is denied", async () => {
    mockGeolocation((_success, error) => {
      error?.({ code: 1, PERMISSION_DENIED: 1 } as GeolocationPositionError);
    });
    const user = userEvent.setup();
    render(<CurrentLocationWeatherCard />);

    await user.click(screen.getByRole("button", { name: /use my current location/i }));

    await waitFor(() => {
      expect(screen.getByText(/location access was denied/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows a fallback message when geolocation is unsupported", async () => {
    // no navigator.geolocation defined at all
    const user = userEvent.setup();
    render(<CurrentLocationWeatherCard />);
    await user.click(screen.getByRole("button", { name: /use my current location/i }));
    await waitFor(() => {
      expect(screen.getByText(/does not support location services/i)).toBeInTheDocument();
    });
  });

  it("allows retrying after an error", async () => {
    let calls = 0;
    mockGeolocation((success, error) => {
      calls += 1;
      if (calls === 1) {
        error?.({ code: 2, PERMISSION_DENIED: 1 } as GeolocationPositionError);
      } else {
        success({ coords: { latitude: 10, longitude: 80 } } as GeolocationPosition);
      }
    });
    const user = userEvent.setup();
    render(<CurrentLocationWeatherCard />);

    await user.click(screen.getByRole("button", { name: /use my current location/i }));
    await waitFor(() => screen.getByRole("button", { name: /try again/i }));

    await user.click(screen.getByRole("button", { name: /try again/i }));
    await waitFor(() => {
      expect(screen.getByText("Conditions at your location")).toBeInTheDocument();
    });
  });
});
