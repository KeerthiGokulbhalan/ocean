import { LocateFixed, MapPinOff } from "lucide-react";
import MarineWeatherCard from "./MarineWeatherCard";
import useGeolocation from "../hooks/useGeolocation";

/**
 * "Conditions at current location" — reuses MarineWeatherCard (and so the
 * existing weather service) once the browser has supplied a coordinate via
 * useGeolocation. No new backend endpoint: this is purely a new coordinate
 * source feeding the same /api/weather call already used for origin and
 * destination.
 *
 * Location is only requested on a user click, not on mount — most browsers
 * only show the permission prompt in response to a real user gesture, and
 * silently asking on page load is poor practice regardless.
 */
export default function CurrentLocationWeatherCard() {
  const { position, status, error, locate } = useGeolocation();

  if (status === "success" && position) {
    return (
      <div>
        <MarineWeatherCard label="Conditions at your location" point={position} />
        <button
          type="button"
          onClick={locate}
          className="mt-2 flex items-center gap-1.5 text-xs font-medium text-deepblue hover:underline"
        >
          <LocateFixed size={13} />
          Refresh my location
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 rounded-xl border border-slate-100 bg-white p-4 text-center shadow-sm">
      {status === "denied" || status === "unavailable" || status === "error" ? (
        <>
          <MapPinOff className="h-6 w-6 text-slate-300" aria-hidden="true" />
          <p className="text-xs text-slate-500">{error}</p>
          <button
            type="button"
            onClick={locate}
            className="rounded-md border border-deepblue/30 px-3 py-1.5 text-xs font-semibold text-deepblue transition hover:bg-deepblue hover:text-white"
          >
            Try again
          </button>
        </>
      ) : (
        <>
          <LocateFixed
            className={`h-6 w-6 text-deepblue ${status === "locating" ? "animate-pulse" : ""}`}
            aria-hidden="true"
          />
          <p className="text-xs text-slate-500">
            {status === "locating"
              ? "Getting your current location…"
              : "See live wave, wind and sea conditions where you are right now."}
          </p>
          <button
            type="button"
            onClick={locate}
            disabled={status === "locating"}
            className="rounded-md bg-deepblue px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-navy disabled:opacity-50"
          >
            {status === "locating" ? "Locating…" : "Use my current location"}
          </button>
        </>
      )}
    </div>
  );
}
