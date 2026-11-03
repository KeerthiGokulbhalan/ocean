import { AlertTriangle, CheckCircle2, CloudOff } from "lucide-react";
import type { RouteOption, RouteStrategy } from "../types";

interface Props {
  options: RouteOption[];
  activeStrategy: RouteStrategy;
  onSelect: (s: RouteStrategy) => void;
  onSaveVoyage: (opt: RouteOption) => void;
}

const LABELS: Record<RouteStrategy, string> = {
  fastest: "Fastest",
  efficient: "Most fuel-efficient",
  safest: "Safest",
};

const COLORS: Record<RouteStrategy, string> = {
  fastest: "border-amber-500",
  efficient: "border-deepblue",
  safest: "border-teal-600",
};

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-100 py-1.5 last:border-0">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-semibold tabular-nums text-ink">{value}</dd>
    </div>
  );
}

export default function RouteComparisonCards({
  options,
  activeStrategy,
  onSelect,
  onSaveVoyage,
}: Props) {
  if (options.length === 0) return null;

  const bestDistance = Math.min(...options.map((o) => o.distance_nm));
  const bestDuration = Math.min(...options.map((o) => o.duration_hr));
  const bestFuel = Math.min(...options.map((o) => o.fuel_tons));
  const bestCo2 = Math.min(...options.map((o) => o.co2_tons));

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-bold text-ink">Route comparison</h2>
        <p className="text-xs text-slate-500">
          Compare the three route strategies using the same vessel and voyage endpoints.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {options.map((opt) => {
          const selected = opt.strategy === activeStrategy;
          const alerts = opt.weather_alerts ?? [];
          return (
            <article
              key={opt.strategy}
              className={`rounded-xl border-2 bg-white p-4 shadow-sm transition ${selected ? COLORS[opt.strategy] : "border-slate-200"}`}
            >
              <button
                type="button"
                onClick={() => onSelect(opt.strategy)}
                aria-pressed={selected}
                className="w-full text-left"
              >
                <div className="mb-3 flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-bold text-ink">{LABELS[opt.strategy]}</h3>
                    <p className="mt-0.5 text-[11px] text-slate-500">Select route to preview on map</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">
                    {opt.sustainability_score}/100
                  </span>
                </div>
                <dl className="space-y-0.5 text-xs">
                  <Metric label="Distance" value={`${opt.distance_nm.toFixed(1)} nm${opt.distance_nm === bestDistance ? " · shortest" : ""}`} />
                  <Metric label="Estimated time" value={`${opt.duration_hr.toFixed(1)} hr${opt.duration_hr === bestDuration ? " · fastest" : ""}`} />
                  <Metric label="Fuel consumption" value={`${opt.fuel_tons.toFixed(2)} t${opt.fuel_tons === bestFuel ? " · lowest" : ""}`} />
                  <Metric label="CO₂ emissions" value={`${opt.co2_tons.toFixed(2)} t${opt.co2_tons === bestCo2 ? " · lowest" : ""}`} />
                  <Metric label="Weather risk" value={opt.risk_score.toFixed(2)} />
                </dl>
              </button>

              <div className="mt-3 border-t border-slate-100 pt-3">
                {opt.weather_data_available ? (
                  alerts.length > 0 ? (
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-700">
                        <AlertTriangle className="h-4 w-4" />
                        {alerts.length} weather-affected segment{alerts.length === 1 ? "" : "s"}
                      </div>
                      {alerts.slice(0, 2).map((alert) => (
                        <p key={alert.segment_index} className="text-[11px] leading-4 text-slate-600">
                          Segment {alert.segment_index + 1}: {alert.message}
                        </p>
                      ))}
                      {alerts.length > 2 && (
                        <p className="text-[11px] text-slate-500">+{alerts.length - 2} more on the map</p>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 text-xs text-emerald-700">
                      <CheckCircle2 className="h-4 w-4" />
                      No threshold-based weather alerts on this route
                    </div>
                  )
                ) : (
                  <div className="flex items-center gap-1.5 text-xs text-slate-500">
                    <CloudOff className="h-4 w-4" />
                    Weather feed unavailable — risk is not verified
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => onSaveVoyage(opt)}
                className="mt-3 w-full rounded-md bg-deepblue px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800"
              >
                Start demo voyage
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
