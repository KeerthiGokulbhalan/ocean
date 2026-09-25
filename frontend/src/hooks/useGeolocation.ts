import { useCallback, useState } from "react";
import type { Coordinate } from "../types";

type GeoStatus = "idle" | "locating" | "success" | "denied" | "unavailable" | "error";

interface UseGeolocationResult {
  position: Coordinate | null;
  status: GeoStatus;
  error: string | null;
  /** Call from a click handler — most browsers require a user gesture
   * before they will show the location permission prompt. */
  locate: () => void;
}

/**
 * Wraps the browser Geolocation API for a one-shot "where am I right now"
 * lookup (not a continuous watch — the location card refreshes on demand,
 * matching how MarineWeatherCard already fetches once per coordinate).
 */
export function useGeolocation(): UseGeolocationResult {
  const [position, setPosition] = useState<Coordinate | null>(null);
  const [status, setStatus] = useState<GeoStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const locate = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setStatus("unavailable");
      setError("This browser does not support location services.");
      return;
    }

    setStatus("locating");
    setError(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPosition({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setStatus("success");
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          setStatus("denied");
          setError("Location access was denied. Allow it in your browser settings to use this.");
        } else {
          setStatus("error");
          setError("Could not determine your current location. Please try again.");
        }
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
    );
  }, []);

  return { position, status, error, locate };
}

export default useGeolocation;
