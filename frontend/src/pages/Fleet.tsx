import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";
import { useAppStore } from "../store/useAppStore";
import type { VesselOut, VesselPosition, VesselType } from "../types";

const VESSEL_TYPES: VesselType[] = ["container", "tanker", "bulk_carrier", "cruise", "fishing"];

const STATUS_STYLES: Record<string, { dot: string; label: string }> = {
  UNDERWAY: { dot: "bg-emerald-500", label: "Underway" },
  ARRIVED: { dot: "bg-deepblue", label: "Arrived" },
  STOPPED: { dot: "bg-amber", label: "Stopped" },
  MOORED: { dot: "bg-slate-400", label: "Moored" },
  UNKNOWN: { dot: "bg-slate-300", label: "No signal" },
};

function relativeTime(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds} seconds ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  return `${Math.floor(seconds / 3600)} hr ago`;
}

function formatCoord(lat: number, lon: number): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(4)}° ${ns}, ${Math.abs(lon).toFixed(4)}° ${ew}`;
}

export default function Fleet() {
  const navigate = useNavigate();
  const { setActiveVessel, resetTracking, trackingStatus, setTrackingStatus } = useAppStore();

  const [vessels, setVessels] = useState<VesselOut[]>([]);
  const [positions, setPositions] = useState<Record<number, VesselPosition>>({});
  const [name, setName] = useState("");
  const [type, setType] = useState<VesselType>("container");
  const [speed, setSpeed] = useState(18);
  const [draft, setDraft] = useState(10);
  const [deadweight, setDeadweight] = useState(20000);
  const [fuelRate, setFuelRate] = useState<number | "">("");
  const [mmsi, setMmsi] = useState("");
  const [mmsiEdits, setMmsiEdits] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setVessels(await api.listFleet());
      setError(null);
    } catch {
      setError("Could not load your fleet. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    api.trackingStatus().then(setTrackingStatus).catch(() => setTrackingStatus(null));
  }, [setTrackingStatus]);

  // Poll live positions for the whole fleet in one request.
  useEffect(() => {
    const tick = async () => {
      try {
        const fixes = await api.fleetLocations();
        setPositions(Object.fromEntries(fixes.map((f) => [f.vessel_id, f])));
      } catch {
        // tracking may be disabled or nothing is sailing — leave columns empty
      }
    };
    tick();
    const interval = (trackingStatus?.update_interval_s ?? 5) * 1000;
    pollRef.current = window.setInterval(tick, Math.max(interval, 5000));
    return () => {
      if (pollRef.current !== null) window.clearInterval(pollRef.current);
    };
  }, [trackingStatus?.update_interval_s]);

  const liveCount = useMemo(
    () => Object.values(positions).filter((p) => p.status === "UNDERWAY").length,
    [positions]
  );

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.createVessel({
        name,
        vessel_type: type,
        cruise_speed_knots: speed,
        draft_m: draft,
        deadweight_tons: deadweight,
        fuel_rate_ton_per_hr: fuelRate === "" ? null : fuelRate,
        mmsi: mmsi.trim() || null,
      });
      setName("");
      setFuelRate("");
      setMmsi("");
      refresh();
    } catch {
      setError("Could not add that vessel. Please check the details and try again.");
    }
  }

  async function handleDelete(id: number) {
    try {
      await api.deleteVessel(id);
      refresh();
    } catch {
      setError("Could not remove that vessel.");
    }
  }

  async function handleSaveMmsi(id: number) {
    try {
      const updated = await api.updateVesselMmsi(id, mmsiEdits[id]?.trim() || null);
      setVessels((current) => current.map((v) => v.id === id ? updated : v));
      setMmsiEdits((current) => { const next = { ...current }; delete next[id]; return next; });
      setError(null);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Could not save the MMSI. Check that it has nine digits and is not assigned to another vessel.");
    }
  }

  /** Focus the map on a vessel's live position by making it the active one. */
  function handleFocus(position: VesselPosition) {
    resetTracking();
    setActiveVessel(position.vessel_id, position.voyage_id ?? null);
    navigate("/");
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Fleet Dashboard</h1>
          <p className="text-sm text-slate-500">
            Manage vessel profiles and monitor live positions.
          </p>
        </div>
        {trackingStatus && (
          <span
            className={`rounded px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${
              trackingStatus.simulated
                ? "bg-amber/20 text-[#8a5a12]"
                : "bg-emerald-100 text-emerald-700"
            }`}
          >
            {trackingStatus.label} · {liveCount} underway
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form
        onSubmit={handleAdd}
        className="grid grid-cols-1 gap-3 rounded-xl border border-slate-100 bg-white p-5 shadow-sm sm:grid-cols-3 lg:grid-cols-4"
      >
        <input
          className="rounded-md border border-slate-200 px-3 py-2 text-sm sm:col-span-2"
          placeholder="Vessel name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <select
          className="rounded-md border border-slate-200 px-3 py-2 text-sm"
          value={type}
          onChange={(e) => setType(e.target.value as VesselType)}
        >
          {VESSEL_TYPES.map((t) => (
            <option key={t} value={t}>
              {t.replace("_", " ")}
            </option>
          ))}
        </select>
        <input
          type="number"
          className="rounded-md border border-slate-200 px-3 py-2 text-sm"
          value={speed}
          onChange={(e) => setSpeed(Number(e.target.value))}
          placeholder="Speed (kn)"
        />
        <input
          type="number"
          className="rounded-md border border-slate-200 px-3 py-2 text-sm"
          value={draft}
          onChange={(e) => setDraft(Number(e.target.value))}
          placeholder="Draft (m)"
        />
        <input
          type="number"
          className="rounded-md border border-slate-200 px-3 py-2 text-sm"
          value={deadweight}
          onChange={(e) => setDeadweight(Number(e.target.value))}
          placeholder="Deadweight (t)"
        />
        <input
          type="number"
          step="0.1"
          className="rounded-md border border-slate-200 px-3 py-2 text-sm"
          value={fuelRate}
          onChange={(e) => setFuelRate(e.target.value === "" ? "" : Number(e.target.value))}
          placeholder="Fuel rate (t/hr, optional)"
        />
        <input
          inputMode="numeric"
          pattern="[0-9]{9}"
          maxLength={9}
          className="rounded-md border border-slate-200 px-3 py-2 text-sm"
          value={mmsi}
          onChange={(e) => setMmsi(e.target.value.replace(/\D/g, "").slice(0, 9))}
          placeholder="MMSI (9 digits, AIS)"
          aria-label="Vessel MMSI for AIS tracking"
        />
        <button className="rounded-md bg-deepblue px-3 py-2 text-sm font-semibold text-white hover:bg-navy sm:col-span-3 lg:col-span-1">
          Add vessel
        </button>
      </form>

      {loading ? (
        <div className="text-sm text-slate-400">Loading fleet…</div>
      ) : vessels.length === 0 ? (
        <div className="flex h-32 items-center justify-center rounded-xl border-2 border-dashed border-slate-200 text-sm text-slate-400">
          No vessels yet — add one above to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {vessels.map((v) => {
            const pos = positions[v.id];
            const style = STATUS_STYLES[pos?.status ?? "UNKNOWN"] ?? STATUS_STYLES.UNKNOWN;

            return (
              <div
                key={v.id}
                className="flex flex-col rounded-xl border border-slate-100 bg-white p-4 shadow-sm"
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-bold text-ink">{v.name}</div>
                    <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
                      <span className={`h-2 w-2 rounded-full ${style.dot}`} />
                      {style.label}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(v.id)}
                    className="shrink-0 text-xs font-medium text-red-500 hover:underline"
                  >
                    Remove
                  </button>
                </div>

                <dl className="space-y-1 text-xs text-slate-600">
                  <Row label="Type" value={v.vessel_type.replace("_", " ")} capitalize />
                  <Row label="Cruise speed" value={`${v.cruise_speed_knots} kn`} />
                  <Row label="Draft" value={`${v.draft_m} m`} />
                  <Row label="Deadweight" value={`${v.deadweight_tons.toLocaleString()} t`} />
                  {v.mmsi && <Row label="MMSI" value={v.mmsi} />}
                  <div className="mt-2 flex gap-2">
                    <input
                      inputMode="numeric"
                      pattern="[0-9]{9}"
                      maxLength={9}
                      className="min-w-0 flex-1 rounded-md border border-slate-200 px-2 py-1.5 text-xs"
                      value={mmsiEdits[v.id] ?? v.mmsi ?? ""}
                      onChange={(e) => setMmsiEdits((current) => ({
                        ...current,
                        [v.id]: e.target.value.replace(/\D/g, "").slice(0, 9),
                      }))}
                      placeholder="AIS MMSI (9 digits)"
                      aria-label={`MMSI for ${v.name}`}
                    />
                    <button
                      type="button"
                      onClick={() => handleSaveMmsi(v.id)}
                      className="rounded-md border border-slate-200 px-2 py-1.5 text-xs font-medium text-deepblue hover:bg-slate-50"
                    >
                      Save MMSI
                    </button>
                  </div>
                  {v.fuel_rate_ton_per_hr != null && (
                    <Row label="Fuel rate" value={`${v.fuel_rate_ton_per_hr} t/hr`} />
                  )}
                </dl>

                {pos ? (
                  <div className="mt-3 space-y-1 border-t border-slate-100 pt-3 text-xs text-slate-600">
                    <Row label="Location" value={formatCoord(pos.latitude, pos.longitude)} />
                    <Row label="Speed" value={`${pos.speed_knots.toFixed(1)} kn`} />
                    <Row label="Heading" value={`${Math.round(pos.heading_deg)}°`} />
                    {pos.progress_percent != null && (
                      <Row label="Progress" value={`${pos.progress_percent.toFixed(0)}%`} />
                    )}
                    <Row label="Updated" value={relativeTime(pos.timestamp)} />

                    <button
                      onClick={() => handleFocus(pos)}
                      className="mt-2 w-full rounded-md border border-deepblue/30 px-3 py-1.5 text-xs font-semibold text-deepblue transition hover:bg-deepblue hover:text-white"
                    >
                      Show on map
                    </button>
                  </div>
                ) : (
                  <div className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-400">
                    No live position — start a voyage to begin tracking.
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  capitalize = false,
}: {
  label: string;
  value: string;
  capitalize?: boolean;
}) {
  return (
    <div className="flex justify-between gap-2">
      <dt>{label}</dt>
      <dd className={`truncate font-medium text-ink ${capitalize ? "capitalize" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
