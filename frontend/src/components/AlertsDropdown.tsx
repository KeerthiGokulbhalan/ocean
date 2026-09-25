import { Bell, RefreshCw, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import api from "../api/client";
import type { AlertOut } from "../types";

export default function AlertsDropdown() {
  const [alerts, setAlerts] = useState<AlertOut[]>([]);
  const [open, setOpen] = useState(false);

  async function refresh() {
    try {
      setAlerts(await api.listAlerts());
    } catch {
      // not authenticated yet, or request failed — fail quietly in the nav bar
    }
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30_000);
    return () => clearInterval(interval);
  }, []);

  const unreadCount = alerts.filter((a) => a.status === "Unread").length;

  async function markRead(id: number) {
    await api.updateAlertStatus(id, "Read");
    refresh();
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative rounded-md px-2 py-2 text-slate-300 hover:text-white"
        aria-label="Alerts"
      >
        <Bell className="h-5 w-5" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-amber text-[10px] font-bold text-navy">
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-[1000] mt-2 w-80 rounded-xl bg-white p-2 shadow-lg border border-slate-100">
          <div className="mb-1 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Alerts
          </div>
          {alerts.length === 0 ? (
            <div className="px-2 py-4 text-center text-xs text-slate-400">No alerts yet.</div>
          ) : (
            <ul className="max-h-80 space-y-1 overflow-y-auto">
              {alerts.map((a) => (
                <li
                  key={a.id}
                  className={`rounded-lg px-3 py-2 text-xs ${
                    a.status === "Unread" ? "bg-amber/10" : "bg-slate-50"
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span
                      className={`flex items-center gap-1 font-semibold ${
                        a.type === "StormWarning" ? "text-red-600" : "text-deepblue"
                      }`}
                    >
                      {a.type === "StormWarning" ? (
                        <TriangleAlert className="h-3.5 w-3.5" aria-hidden="true" />
                      ) : (
                        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                      )}
                      {a.type === "StormWarning" ? "Storm Warning" : "Route Change"}
                    </span>
                    {a.status === "Unread" && (
                      <button
                        onClick={() => markRead(a.id)}
                        className="text-[10px] font-medium text-deepblue hover:underline"
                      >
                        Mark read
                      </button>
                    )}
                  </div>
                  <p className="text-slate-600">{a.message}</p>
                  <p className="mt-1 text-[10px] text-slate-400">
                    {new Date(a.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
