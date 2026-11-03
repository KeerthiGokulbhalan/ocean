import { useEffect, useState } from "react";
import api from "../api/client";
import type { VoyageAnalytics, VoyageOut, VoyageStatus } from "../types";

const STATUS_OPTIONS: VoyageStatus[] = ["Planned", "In-Progress", "Completed"];

const STATUS_STYLES: Record<VoyageStatus, string> = {
  Planned: "bg-slate-100 text-slate-600",
  "In-Progress": "bg-amber/20 text-amber",
  Completed: "bg-emerald-100 text-emerald-700",
};

function valueOrWaiting(value: number | null | undefined, digits = 1) {
  return value == null ? "Waiting for tracking" : value.toFixed(digits);
}

function variance(value: number | null | undefined, unit: string) {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)} ${unit}`;
}

export default function History() {
  const [voyages, setVoyages] = useState<VoyageOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [analytics, setAnalytics] = useState<VoyageAnalytics | null>(null);
  const [analyticsLoadingId, setAnalyticsLoadingId] = useState<number | null>(null);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      setVoyages(await api.listVoyages());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleStatusChange(id: number, status: VoyageStatus) {
    setBusyId(id);
    try {
      await api.updateVoyageStatus(id, status);
      await refresh();
    } finally {
      setBusyId(null);
    }
  }

  async function handleReoptimize(id: number) {
    setBusyId(id);
    try {
      await api.reoptimizeVoyage(id);
      alert("Re-optimization complete. Check the alerts bell for any route-change notice.");
    } catch {
      alert("Could not re-optimize this voyage.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDownload(id: number) {
    await api.downloadVoyageReport(id);
  }

  async function handleAnalytics(id: number) {
    setAnalyticsLoadingId(id);
    setAnalyticsError(null);
    try {
      setAnalytics(await api.voyageAnalytics(id));
    } catch {
      setAnalytics(null);
      setAnalyticsError("Could not load voyage analytics. Check that the backend is updated and the voyage has tracking enabled.");
    } finally {
      setAnalyticsLoadingId(null);
    }
  }

  const totalFuel = voyages.reduce((sum, v) => sum + v.fuel_tons, 0);
  const totalCo2 = voyages.reduce((sum, v) => sum + v.co2_tons, 0);
  const totalDistance = voyages.reduce((sum, v) => sum + v.distance_nm, 0);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Voyage History & Performance</h1>
        <p className="text-sm text-slate-500">Review planned voyages and compare them with recorded vessel tracking.</p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-100 bg-white p-4 text-center shadow-sm">
          <div className="text-xl font-bold text-deepblue">{totalDistance.toFixed(0)} nm</div>
          <div className="text-xs text-slate-500">Planned distance</div>
        </div>
        <div className="rounded-xl border border-slate-100 bg-white p-4 text-center shadow-sm">
          <div className="text-xl font-bold text-amber">{totalFuel.toFixed(1)} t</div>
          <div className="text-xs text-slate-500">Planned fuel</div>
        </div>
        <div className="rounded-xl border border-slate-100 bg-white p-4 text-center shadow-sm">
          <div className="text-xl font-bold text-teal">{totalCo2.toFixed(1)} t</div>
          <div className="text-xs text-slate-500">Planned CO₂</div>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-slate-400">Loading voyages…</div>
      ) : voyages.length === 0 ? (
        <div className="flex h-32 items-center justify-center rounded-xl border-2 border-dashed border-slate-200 text-sm text-slate-400">
          No voyages saved yet — plan and save a route from the Route Planner tab.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-100 bg-white shadow-sm">
          <table className="w-full min-w-[850px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Route</th>
                <th className="px-4 py-3">Strategy</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Distance</th>
                <th className="px-4 py-3">Fuel</th>
                <th className="px-4 py-3">CO₂</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {voyages.map((v) => (
                <tr key={v.id}>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {v.start_port && v.end_port
                      ? `${v.start_port} → ${v.end_port}`
                      : `(${v.origin_lat.toFixed(1)}, ${v.origin_lon.toFixed(1)}) → (${v.dest_lat.toFixed(1)}, ${v.dest_lon.toFixed(1)})`}
                  </td>
                  <td className="px-4 py-3 font-medium capitalize text-ink">{v.strategy}</td>
                  <td className="px-4 py-3">
                    <select
                      value={v.status}
                      disabled={busyId === v.id}
                      onChange={(e) => handleStatusChange(v.id, e.target.value as VoyageStatus)}
                      className={`rounded-full border-0 px-2 py-1 text-xs font-semibold ${STATUS_STYLES[v.status as VoyageStatus] ?? "bg-slate-100"}`}
                    >
                      {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3">{v.distance_nm.toFixed(0)} nm</td>
                  <td className="px-4 py-3">{v.fuel_tons.toFixed(1)} t</td>
                  <td className="px-4 py-3">{v.co2_tons.toFixed(1)} t</td>
                  <td className="px-4 py-3 text-xs text-slate-500">{new Date(v.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1.5">
                      <button
                        onClick={() => handleAnalytics(v.id)}
                        disabled={analyticsLoadingId === v.id}
                        className="text-left text-xs font-semibold text-deepblue hover:underline disabled:opacity-50"
                      >
                        {analyticsLoadingId === v.id ? "Loading analytics…" : "View performance"}
                      </button>
                      <button onClick={() => handleDownload(v.id)} className="text-left text-xs font-semibold text-deepblue hover:underline">
                        Download PDF
                      </button>
                      <button
                        onClick={() => handleReoptimize(v.id)}
                        disabled={busyId === v.id}
                        className="text-left text-xs font-semibold text-teal hover:underline disabled:opacity-50"
                      >
                        Re-optimize now
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {analyticsError && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{analyticsError}</div>
      )}

      {analytics && (
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-ink">Voyage #{analytics.voyage_id} performance</h2>
              <p className="text-xs text-slate-500">{analytics.tracking_points} persisted tracking points</p>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-bold ${analytics.is_simulated ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>
              {analytics.data_source}
            </span>
          </div>

          {!analytics.actual_available ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              {analytics.note}
            </div>
          ) : (
            <>
              {analytics.is_simulated && (
                <p className="text-xs font-medium text-amber-700">DEMO SIMULATION — the tracking positions are simulated, not real AIS.</p>
              )}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {[
                  ["Distance", analytics.planned_distance_nm, analytics.actual_distance_nm, analytics.distance_variance_nm, "nm"],
                  ["Duration", analytics.planned_duration_hr, analytics.actual_duration_hr, analytics.duration_variance_hr, "hr"],
                  ["Fuel", analytics.planned_fuel_tons, analytics.actual_fuel_tons, analytics.fuel_variance_tons, "t"],
                  ["CO₂", analytics.planned_co2_tons, analytics.actual_co2_tons, analytics.co2_variance_tons, "t"],
                ].map(([label, planned, actual, delta, unit]) => (
                  <div key={String(label)} className="rounded-lg border border-slate-100 p-3">
                    <div className="text-sm font-semibold text-ink">{String(label)}</div>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                      <div><div className="text-slate-500">Planned</div><div className="mt-1 font-semibold tabular-nums">{Number(planned).toFixed(2)} {String(unit)}</div></div>
                      <div><div className="text-slate-500">Tracked / estimated</div><div className="mt-1 font-semibold tabular-nums">{valueOrWaiting(actual as number | null, 2)}{actual == null ? "" : ` ${String(unit)}`}</div></div>
                    </div>
                    <div className="mt-2 text-[11px] text-slate-500">Variance: {variance(delta as number | null, String(unit))}</div>
                  </div>
                ))}
              </div>
              {analytics.progress_percent != null && (
                <div>
                  <div className="mb-1 flex justify-between text-xs text-slate-500"><span>Tracked distance progress</span><span>{analytics.progress_percent.toFixed(1)}%</span></div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-deepblue" style={{ width: `${analytics.progress_percent}%` }} /></div>
                </div>
              )}
            </>
          )}
          {analytics.actual_available && (
            <p className="text-[11px] leading-5 text-slate-500">{analytics.fuel_calculation_method} {analytics.note}</p>
          )}
        </section>
      )}
    </div>
  );
}
