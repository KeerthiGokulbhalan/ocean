import { useMemo, useState } from "react";
import type { RouteOption } from "../types";

interface Props {
  baseline: RouteOption;
}

export default function WhatIfSimulator({ baseline }: Props) {
  const [speed, setSpeed] = useState(18);

  // client-side quick re-estimate for instant feedback (server call happens
  // only if the user commits to a full re-optimize)
  const { duration, fuel } = useMemo(() => {
    const baselineSpeed = baseline.duration_hr > 0 ? baseline.distance_nm / baseline.duration_hr : 18;
    const duration = baseline.distance_nm / speed;
    const speedRatio = speed / baselineSpeed;
    // fuel roughly scales with the cube of speed for a fixed distance-time trade
    const fuel = baseline.fuel_tons * Math.pow(speedRatio, 2.2) * (baselineSpeed / speed);
    return { duration, fuel };
  }, [speed, baseline]);

  return (
    <div className="rounded-xl bg-white p-5 shadow-sm border border-slate-100">
      <h3 className="mb-1 text-sm font-bold text-ink">What-If Simulator</h3>
      <p className="mb-3 text-xs text-slate-500">
        Drag the speed slider to see the live effect on ETA and fuel burn for the {baseline.strategy} route.
      </p>
      <input
        type="range"
        min={8}
        max={28}
        step={0.5}
        value={speed}
        onChange={(e) => setSpeed(Number(e.target.value))}
        className="w-full accent-amber"
      />
      <div className="mt-2 flex justify-between text-xs text-slate-500">
        <span>8 kn</span>
        <span className="font-semibold text-ink">{speed} kn</span>
        <span>28 kn</span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-slate-50 p-3 text-center">
          <div className="text-lg font-bold text-deepblue">{duration.toFixed(1)} hr</div>
          <div className="text-[11px] text-slate-500">Estimated duration</div>
        </div>
        <div className="rounded-lg bg-slate-50 p-3 text-center">
          <div className="text-lg font-bold text-amber">{fuel.toFixed(1)} t</div>
          <div className="text-[11px] text-slate-500">Estimated fuel</div>
        </div>
      </div>
    </div>
  );
}
