import L from "leaflet";
import { useMemo } from "react";
import { Marker, Popup } from "react-leaflet";
import type { Port } from "../types";

interface PortMarkersProps {
  ports: Port[];
  onSetOrigin?: (port: Port) => void;
  onSetDestination?: (port: Port) => void;
  originPortId?: string | null;
  destinationPortId?: string | null;
}

/**
 * Small circular markers for the port overlay. Major Ports get a larger,
 * darker dot so the twelve national gateways stand out from minor ports at
 * a glance. Built as divIcons to avoid loading 45 image assets.
 */
function portIcon(port: Port, isSelected: boolean): L.DivIcon {
  const isMajor = port.port_type === "Major Port";
  const size = isMajor ? 12 : 9;
  const color = isSelected ? "#F2A65A" : isMajor ? "#065A82" : "#1C7293";

  return L.divIcon({
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:9999px;
      background:${color};border:2px solid #ffffff;
      box-shadow:0 0 0 1px rgba(14,34,51,0.25);
    "></div>`,
    className: "seapath-port-marker",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}

export default function PortMarkers({
  ports,
  onSetOrigin,
  onSetDestination,
  originPortId,
  destinationPortId,
}: PortMarkersProps) {
  const markers = useMemo(
    () =>
      ports.map((port) => ({
        port,
        icon: portIcon(port, port.id === originPortId || port.id === destinationPortId),
      })),
    [ports, originPortId, destinationPortId]
  );

  return (
    <>
      {markers.map(({ port, icon }) => (
        <Marker key={port.id} position={[port.latitude, port.longitude]} icon={icon}>
          <Popup>
            <div className="min-w-[180px] space-y-2 text-xs">
              <div>
                <div className="text-sm font-bold text-ink">{port.name}</div>
                <div className="text-slate-500">{port.state}</div>
              </div>

              <div className="flex flex-wrap items-center gap-1">
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                    port.port_type === "Major Port"
                      ? "bg-deepblue/10 text-deepblue"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {port.port_type}
                </span>
                {port.port_code && (
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                    {port.port_code}
                  </span>
                )}
              </div>

              <div className="text-[11px] text-slate-500">
                {port.latitude.toFixed(4)}° N, {port.longitude.toFixed(4)}° E
              </div>

              {(onSetOrigin || onSetDestination) && (
                <div className="flex gap-1.5 border-t border-slate-200 pt-2">
                  {onSetOrigin && (
                    <button
                      type="button"
                      onClick={() => onSetOrigin(port)}
                      className="flex-1 rounded border border-deepblue/40 px-2 py-1 text-[11px] font-semibold text-deepblue hover:bg-deepblue hover:text-white"
                    >
                      Set as Origin
                    </button>
                  )}
                  {onSetDestination && (
                    <button
                      type="button"
                      onClick={() => onSetDestination(port)}
                      className="flex-1 rounded border border-deepblue/40 px-2 py-1 text-[11px] font-semibold text-deepblue hover:bg-deepblue hover:text-white"
                    >
                      Set as Destination
                    </button>
                  )}
                </div>
              )}
            </div>
          </Popup>
        </Marker>
      ))}
    </>
  );
}
