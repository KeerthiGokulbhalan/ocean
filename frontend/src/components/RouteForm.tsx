import { useEffect, useMemo, useState } from "react";
import PortSearch from "./PortSearch";
import type { Coordinate, Port, VesselOut, VesselProfile, VesselType } from "../types";

interface RouteFormProps {
  onSubmit: (
    origin: Coordinate,
    destination: Coordinate,
    vessel: VesselProfile,
    context: { originPort: Port | null; destinationPort: Port | null; vesselId: number | null }
  ) => void;
  loading: boolean;

  ports: Port[];
  portsLoading: boolean;
  originPort: Port | null;
  destinationPort: Port | null;
  onOriginPortChange: (p: Port | null) => void;
  onDestinationPortChange: (p: Port | null) => void;

  /** Fleet vessels, so a voyage can be attached to a real vessel for tracking. */
  fleet: VesselOut[];
  selectedVesselId: number | null;
  onVesselChange: (id: number | null) => void;
}

const VESSEL_TYPES: { value: VesselType; label: string }[] = [
  { value: "container", label: "Container Ship" },
  { value: "tanker", label: "Tanker" },
  { value: "bulk_carrier", label: "Bulk Carrier" },
  { value: "cruise", label: "Cruise Ship" },
  { value: "fishing", label: "Fishing Vessel" },
];

/** Popular Indian corridors, expressed as port ids from the seeded dataset. */
const PRESETS = [
  { label: "Chennai → Mumbai", origin: "IN_CHENNAI", destination: "IN_MUMBAI" },
  { label: "Mumbai → Kochi", origin: "IN_MUMBAI", destination: "IN_COCHIN" },
  { label: "Kandla → Visakhapatnam", origin: "IN_DEENDAYAL", destination: "IN_VISAKHAPATNAM" },
];

export default function RouteForm({
  onSubmit,
  loading,
  ports,
  portsLoading,
  originPort,
  destinationPort,
  onOriginPortChange,
  onDestinationPortChange,
  fleet,
  selectedVesselId,
  onVesselChange,
}: RouteFormProps) {
  const [vesselType, setVesselType] = useState<VesselType>("container");
  const [speed, setSpeed] = useState(18);
  const [draft, setDraft] = useState(10);
  const [deadweight, setDeadweight] = useState(20000);
  const [submitted, setSubmitted] = useState(false);

  const selectedVessel = useMemo(
    () => fleet.find((v) => v.id === selectedVesselId) ?? null,
    [fleet, selectedVesselId]
  );

  // Picking a fleet vessel adopts its real profile, so the route is planned
  // with the same figures the voyage will later be tracked against.
  useEffect(() => {
    if (!selectedVessel) return;
    setVesselType(selectedVessel.vessel_type);
    setSpeed(selectedVessel.cruise_speed_knots);
    setDraft(selectedVessel.draft_m);
    setDeadweight(selectedVessel.deadweight_tons);
  }, [selectedVessel]);

  function applyPreset(preset: (typeof PRESETS)[number]) {
    const from = ports.find((p) => p.id === preset.origin) ?? null;
    const to = ports.find((p) => p.id === preset.destination) ?? null;
    if (from) onOriginPortChange(from);
    if (to) onDestinationPortChange(to);
  }

  // --- validation ---------------------------------------------------------
  const sameportError =
    originPort && destinationPort && originPort.id === destinationPort.id
      ? "Origin and destination must be different ports."
      : null;

  function coordsValid(port: Port | null): boolean {
    return (
      !!port &&
      Number.isFinite(port.latitude) &&
      Number.isFinite(port.longitude) &&
      Math.abs(port.latitude) <= 90 &&
      Math.abs(port.longitude) <= 180
    );
  }

  const originError = submitted
    ? !originPort
      ? "Select an origin port."
      : !coordsValid(originPort)
        ? "This port has invalid coordinates and cannot be routed from."
        : sameportError
    : sameportError;

  const destinationError = submitted
    ? !destinationPort
      ? "Select a destination port."
      : !coordsValid(destinationPort)
        ? "This port has invalid coordinates and cannot be routed to."
        : null
    : null;

  const canSubmit =
    coordsValid(originPort) && coordsValid(destinationPort) && !sameportError;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    if (!canSubmit || !originPort || !destinationPort) return;

    onSubmit(
      { lat: originPort.latitude, lon: originPort.longitude },
      { lat: destinationPort.latitude, lon: destinationPort.longitude },
      {
        name: selectedVessel?.name ?? "SeaPath Demo Vessel",
        vessel_type: vesselType,
        cruise_speed_knots: speed,
        draft_m: draft,
        deadweight_tons: deadweight,
      },
      { originPort, destinationPort, vesselId: selectedVesselId }
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-xl border border-slate-100 bg-white p-5 shadow-sm"
    >
      <h2 className="text-sm font-bold uppercase tracking-wide text-ink">Plan voyage</h2>

      <div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
          Quick presets
        </label>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              type="button"
              key={p.label}
              onClick={() => applyPreset(p)}
              disabled={portsLoading}
              className="rounded-full border border-deepblue/30 px-3 py-1 text-xs font-medium text-deepblue transition hover:bg-deepblue hover:text-white disabled:opacity-40"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <PortSearch
        label="Origin"
        value={originPort}
        onChange={onOriginPortChange}
        ports={ports}
        loading={portsLoading}
        excludePortId={destinationPort?.id ?? null}
        error={originError}
      />

      <PortSearch
        label="Destination"
        value={destinationPort}
        onChange={onDestinationPortChange}
        ports={ports}
        loading={portsLoading}
        excludePortId={originPort?.id ?? null}
        error={destinationError}
      />

      <div>
        <label
          htmlFor="vessel-select"
          className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500"
        >
          Vessel
        </label>
        <select
          id="vessel-select"
          className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
          value={selectedVesselId ?? ""}
          onChange={(e) => onVesselChange(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Ad-hoc vessel (not saved to fleet)</option>
          {fleet.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name} · {v.vessel_type.replace("_", " ")}
            </option>
          ))}
        </select>
        {fleet.length === 0 && (
          <p className="mt-1 text-xs text-slate-400">
            A demo vessel will be added to your fleet automatically when you start a voyage.
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="vessel-type"
          className="mb-1 block text-xs font-semibold text-slate-500"
        >
          Vessel type
        </label>
        <select
          id="vessel-type"
          className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
          value={vesselType}
          onChange={(e) => setVesselType(e.target.value as VesselType)}
        >
          {VESSEL_TYPES.map((v) => (
            <option key={v.value} value={v.value}>
              {v.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-xs font-semibold text-slate-500">
            Cruise speed: {speed} kn
          </label>
          <input
            type="range"
            min={8}
            max={28}
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            className="w-full accent-deepblue"
          />
        </div>
        <div>
          <label htmlFor="draft" className="mb-1 block text-xs font-semibold text-slate-500">
            Draft (m)
          </label>
          <input
            id="draft"
            type="number"
            min={1}
            max={25}
            value={draft}
            onChange={(e) => setDraft(Number(e.target.value))}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div>
        <label htmlFor="dwt" className="mb-1 block text-xs font-semibold text-slate-500">
          Deadweight (tons)
        </label>
        <input
          id="dwt"
          type="number"
          min={500}
          value={deadweight}
          onChange={(e) => setDeadweight(Number(e.target.value))}
          className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-md bg-deepblue py-2.5 text-sm font-semibold text-white transition hover:bg-navy disabled:opacity-50"
      >
        {loading ? "Computing optimal routes…" : "Calculate Route"}
      </button>
    </form>
  );
}
