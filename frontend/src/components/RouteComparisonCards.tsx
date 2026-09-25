import type { RouteOption, RouteStrategy } from "../types";

interface Props {
  options: RouteOption[];
  activeStrategy: RouteStrategy;
  onSelect: (s: RouteStrategy) => void;
  onSaveVoyage: (opt: RouteOption) => void;
}

const LABELS: Record<RouteStrategy, string> = {
  fastest: "Fastest",
  efficient: "Most Efficient",
  safest: "Safest",
};

const COLORS: Record<RouteStrategy, string> = {
  fastest: "border-amber",
  efficient: "border-deepblue",
  safest: "border-teal",
};

export default function RouteComparisonCards({ options, activeStrategy, onSelect, onSaveVoyage }: Props) {
  if (options.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {options.map((opt) => (
        <button
          key={opt.strategy}
          onClick={() => onSelect(opt.strategy)}
          className={`rounded-xl border-2 bg-white p-4 text-left shadow-sm transition ${
            opt.strategy === activeStrategy ? COLORS[opt.strategy] : "border-transparent"
          } hover:shadow-md`}
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-bold text-ink">{LABELS[opt.strategy]}</span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500">
              {opt.sustainability_score}/100
            </span>
          </div>
          <dl className="space-y-1 text-xs text-slate-600">
            <div className="flex justify-between">
              <dt>Distance</dt>
              <dd className="font-medium text-ink">{opt.distance_nm} nm</dd>
            </div>
            <div className="flex justify-between">
              <dt>Duration</dt>
              <dd className="font-medium text-ink">{opt.duration_hr} hr</dd>
            </div>
            <div className="flex justify-between">
              <dt>Fuel</dt>
              <dd className="font-medium text-ink">{opt.fuel_tons} t</dd>
            </div>
            <div className="flex justify-between">
              <dt>CO₂</dt>
              <dd className="font-medium text-ink">{opt.co2_tons} t</dd>
            </div>
            <div className="flex justify-between">
              <dt>Risk score</dt>
              <dd className="font-medium text-ink">{opt.risk_score}</dd>
            </div>
          </dl>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onSaveVoyage(opt);
            }}
            className="mt-3 w-full rounded-md bg-slate-50 py-1.5 text-xs font-semibold text-deepblue hover:bg-slate-100"
          >
            Start demo voyage
          </button>
        </button>
      ))}
    </div>
  );
}
