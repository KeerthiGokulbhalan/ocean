import { useEffect, useState } from "react";
import api from "../api/client";
import type { VoyageOut, VoyageStatus } from "../types";

const STATUS_OPTIONS: VoyageStatus[] = ["Planned", "In-Progress", "Completed"];

const STATUS_STYLES: Record<VoyageStatus, string> = {
  Planned: "bg-slate-100 text-slate-600",
  "In-Progress": "bg-amber/20 text-amber",
  Completed: "bg-emerald-100 text-emerald-700",
};

export default function History() {
  const [voyages, setVoyages] = useState<VoyageOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

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
      refresh();
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

  const totalFuel = voyages.reduce((sum, v) => sum + v.fuel_tons, 0);
  const totalCo2 = voyages.reduce((sum, v) => sum + v.co2_tons, 0);
  const totalDistance = voyages.reduce((sum, v) => sum + v.distance_nm, 0);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Voyage History</h1>
        <p className="text-sm text-slate-500">Analytics across every voyage saved from the route planner.</p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl bg-white p-4 text-center shadow-sm border border-slate-100">
          <div className="text-xl font-bold text-deepblue">{totalDistance.toFixed(0)}</div>
          <div className="text-xs text-slate-500">Total nautical miles</div>
        </div>
        <div className="rounded-xl bg-white p-4 text-center shadow-sm border border-slate-100">
          <div className="text-xl font-bold text-amber">{totalFuel.toFixed(1)} t</div>
          <div className="text-xs text-slate-500">Total fuel used</div>
        </div>
        <div className="rounded-xl bg-white p-4 text-center shadow-sm border border-slate-100">
          <div className="text-xl font-bold text-teal">{totalCo2.toFixed(1)} t</div>
          <div className="text-xs text-slate-500">Total CO₂ emitted</div>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-slate-400">Loading voyages…</div>
      ) : voyages.length === 0 ? (
        <div className="flex h-32 items-center justify-center rounded-xl border-2 border-dashed border-slate-200 text-sm text-slate-400">
          No voyages saved yet — plan and save a route from the Route Planner tab.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl bg-white shadow-sm border border-slate-100">
          <table className="w-full text-left text-sm">
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
                  <td className="px-4 py-3 capitalize font-medium text-ink">{v.strategy}</td>
                  <td className="px-4 py-3">
                    <select
                      value={v.status}
                      disabled={busyId === v.id}
                      onChange={(e) => handleStatusChange(v.id, e.target.value as VoyageStatus)}
                      className={`rounded-full border-0 px-2 py-1 text-xs font-semibold ${STATUS_STYLES[v.status as VoyageStatus] ?? "bg-slate-100"}`}
                    >
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">{v.distance_nm.toFixed(0)} nm</td>
                  <td className="px-4 py-3">{v.fuel_tons.toFixed(1)} t</td>
                  <td className="px-4 py-3">{v.co2_tons.toFixed(1)} t</td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {new Date(v.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => handleDownload(v.id)}
                        className="text-left text-xs font-semibold text-deepblue hover:underline"
                      >
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
    </div>
  );
}
