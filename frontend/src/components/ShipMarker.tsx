import L from "leaflet";
import { useMemo } from "react";
import { Marker, Popup } from "react-leaflet";
import type { VesselPosition } from "../types";

interface ShipMarkerProps {
  position: VesselPosition;
  vesselName: string;
  originName?: string | null;
  destinationName?: string | null;
  progressPercent?: number | null;
}

const STATUS_COLORS: Record<string, string> = {
  UNDERWAY: "#065A82",
  ARRIVED: "#16A34A",
  STOPPED: "#F2A65A",
  MOORED: "#64748B",
  UNKNOWN: "#94A3B8",
};

/**
 * Builds the vessel icon as an inline SVG divIcon rather than a bitmap, so it
 * can be rotated to the vessel's heading and recoloured by status without
 * shipping extra image assets. The arrow points "up" at 0deg and the wrapper
 * is rotated by the heading, matching Leaflet's north-up orientation.
 */
function shipIcon(headingDeg: number, status: string): L.DivIcon {
  const color = STATUS_COLORS[status] ?? STATUS_COLORS.UNKNOWN;
  const html = `
    <div style="
      width:34px;height:34px;
      display:flex;align-items:center;justify-content:center;
      transform: rotate(${headingDeg}deg);
      transform-origin:center center;
      transition: transform 0.6s ease-out;
    ">
      <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">
        <circle cx="12" cy="12" r="11" fill="${color}" fill-opacity="0.18"/>
        <path d="M12 2 L18 20 L12 16.5 L6 20 Z"
              fill="${color}" stroke="#ffffff" stroke-width="1.4"
              stroke-linejoin="round"/>
      </svg>
    </div>`;

  return L.divIcon({
    html,
    className: "seapath-ship-marker", // strips Leaflet's default white box
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -14],
  });
}

function relativeTime(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds} sec ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  return `${Math.floor(seconds / 3600)} hr ago`;
}

export default function ShipMarker({
  position,
  vesselName,
  originName,
  destinationName,
  progressPercent,
}: ShipMarkerProps) {
  const icon = useMemo(
    () => shipIcon(position.heading_deg ?? 0, position.status),
    [position.heading_deg, position.status]
  );

  const lat = position.latitude;
  const lon = position.longitude;

  return (
    <Marker position={[lat, lon]} icon={icon} zIndexOffset={1000}>
      <Popup>
        <div className="min-w-[190px] space-y-1 text-xs">
          <div className="flex items-center gap-1.5 border-b border-slate-200 pb-1.5 text-sm font-bold text-ink">
            <span aria-hidden="true">🚢</span>
            <span>{vesselName}</span>
          </div>

          {position.is_simulated && (
            <div className="rounded bg-amber/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#8a5a12]">
              Demo / simulated position
            </div>
          )}

          <Row label="Status" value={position.status} />
          <Row label="Speed" value={`${position.speed_knots?.toFixed(1) ?? "—"} knots`} />
          <Row label="Heading" value={`${Math.round(position.heading_deg ?? 0)}°`} />
          <Row label="Latitude" value={lat.toFixed(4)} />
          <Row label="Longitude" value={lon.toFixed(4)} />
          <Row label="Updated" value={relativeTime(position.timestamp)} />

          {(originName || destinationName) && (
            <div className="space-y-1 border-t border-slate-200 pt-1.5">
              {originName && <Row label="Origin" value={originName} />}
              {destinationName && <Row label="Destination" value={destinationName} />}
              {progressPercent != null && (
                <Row label="Progress" value={`${progressPercent.toFixed(0)}%`} />
              )}
            </div>
          )}
        </div>
      </Popup>
    </Marker>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-ink">{value}</span>
    </div>
  );
}
