import { Compass, Droplets, Thermometer, Waves, Wind } from "lucide-react";
import { useEffect, useState } from "react";
import api from "../api/client";
import type { Coordinate, WeatherPoint } from "../types";

interface Props {
  label: string;
  point: Coordinate;
}

function formatValue(value: number | null | undefined, unit: string, decimals = 1): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(decimals)} ${unit}`;
}

function DirectionArrow({ degrees }: { degrees: number | null | undefined }) {
  if (degrees === null || degrees === undefined) {
    return <Compass className="h-3.5 w-3.5 text-slate-300" aria-hidden="true" />;
  }
  return (
    <Compass
      className="h-3.5 w-3.5 text-slate-400 transition-transform"
      style={{ transform: `rotate(${degrees}deg)` }}
      aria-hidden="true"
    />
  );
}

export default function MarineWeatherCard({ label, point }: Props) {
  const [weather, setWeather] = useState<WeatherPoint | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    api
      .weather(point.lat, point.lon)
      .then((data) => {
        if (!cancelled) setWeather(data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [point.lat, point.lon]);

  const hasWeather = Boolean(weather?.data_available);
  const hasMarine = Boolean(weather?.marine_data_available);
  const hasWind = Boolean(weather?.wind_data_available);

  return (
    <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="text-sm font-bold text-ink">{label}</span>
        <span className="text-[11px] text-slate-400">
          {point.lat.toFixed(2)}, {point.lon.toFixed(2)}
        </span>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-lg bg-slate-100" />
          ))}
        </div>
      ) : error || !weather || !hasWeather ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-4 text-center text-xs text-slate-500">
          Weather feed unavailable. No calm-sea or safe-condition assumption is being made.
        </div>
      ) : (
        <>
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-700">Weather feed received</span>
            {weather.retrieved_at_utc && (
              <span className="text-[10px] text-slate-400">
                {new Date(weather.retrieved_at_utc).toLocaleTimeString()}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg bg-slate-50 px-3 py-2">
              <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
                <Waves className="h-3.5 w-3.5 text-deepblue" aria-hidden="true" />
                Wave height
              </div>
              <div className="text-sm font-bold text-ink">
                {hasMarine ? formatValue(weather.wave_height_m, "m") : "—"}
              </div>
            </div>

            <div className="rounded-lg bg-slate-50 px-3 py-2">
              <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
                <Wind className="h-3.5 w-3.5 text-teal" aria-hidden="true" />
                Wind speed
              </div>
              <div className="flex items-center gap-1 text-sm font-bold text-ink">
                {hasWind ? formatValue(weather.wind_speed_kmh, "km/h", 0) : "—"}
                {hasWind && <DirectionArrow degrees={weather.wind_direction_deg} />}
              </div>
            </div>

            <div className="rounded-lg bg-slate-50 px-3 py-2">
              <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
                <Thermometer className="h-3.5 w-3.5 text-amber" aria-hidden="true" />
                Sea temp
              </div>
              <div className="text-sm font-bold text-ink">
                {hasMarine ? formatValue(weather.sea_surface_temperature_c, "°C") : "—"}
              </div>
            </div>

            <div className="rounded-lg bg-slate-50 px-3 py-2">
              <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
                <Droplets className="h-3.5 w-3.5 text-deepblue" aria-hidden="true" />
                Ocean current
              </div>
              <div className="flex items-center gap-1 text-sm font-bold text-ink">
                {hasMarine ? formatValue(weather.ocean_current_velocity_kmh, "km/h") : "—"}
                {hasMarine && <DirectionArrow degrees={weather.ocean_current_direction_deg} />}
              </div>
            </div>
          </div>
          {(!hasMarine || !hasWind) && (
            <p className="mt-2 text-[10px] text-amber-700">
              Partial feed: unavailable weather fields are shown as dashes.
            </p>
          )}
        </>
      )}

      {!loading && hasWeather && weather && (weather.wave_period_s || weather.swell_wave_height_m) && (
        <div className="mt-2 flex gap-4 border-t border-slate-100 pt-2 text-[11px] text-slate-500">
          {hasMarine && weather.wave_period_s && <span>Wave period: {formatValue(weather.wave_period_s, "s")}</span>}
          {hasMarine && weather.swell_wave_height_m && (
            <span>Swell height: {formatValue(weather.swell_wave_height_m, "m")}</span>
          )}
        </div>
      )}
    </div>
  );
}
