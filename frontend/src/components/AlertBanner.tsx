import { Info, TriangleAlert } from "lucide-react";
import type { RouteOption } from "../types";

interface Props {
  options: RouteOption[];
  warnings: string[];
}

export default function AlertBanner({ options, warnings }: Props) {
  const highRisk = options.filter((o) => o.risk_score >= 0.5);

  if (highRisk.length === 0 && warnings.length === 0) return null;

  return (
    <div className="space-y-2">
      {highRisk.map((opt) => (
        <div
          key={opt.strategy}
          className="flex items-start gap-3 rounded-lg border border-amber/40 bg-amber/10 px-4 py-3 text-sm text-ink"
        >
          <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber" aria-hidden="true" />
          <div>
            <span className="font-semibold capitalize">{opt.strategy} route</span> passes through
            elevated wave/wind conditions (risk score {opt.risk_score}). Consider the safest option
            or adjust departure time.
          </div>
        </div>
      ))}
      {warnings.map((w, i) => (
        <div
          key={i}
          className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600"
        >
          <Info className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />
          <div>{w}</div>
        </div>
      ))}
    </div>
  );
}
