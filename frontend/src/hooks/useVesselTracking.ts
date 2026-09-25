import { useCallback, useEffect, useRef, useState } from "react";
import api from "../api/client";
import { useAppStore } from "../store/useAppStore";
import type { SimulationAction, VesselPosition } from "../types";

type ConnectionState = "idle" | "connecting" | "live" | "polling" | "error";

interface UseVesselTrackingOptions {
  vesselId: number | null;
  voyageId: number | null;
  enabled: boolean;
}

/**
 * Live vessel tracking.
 *
 * Prefers a WebSocket; if the socket fails to open or drops, falls back to
 * polling on the same interval the backend advertises. Both paths yield the
 * identical VesselPosition shape, so nothing downstream cares which is live.
 *
 * Voyage progress (distance, %, ETA, weather, risk) comes from the richer
 * /api/voyages/{id}/tracking endpoint, polled a little more slowly since it
 * makes an upstream weather call.
 */
export function useVesselTracking({ vesselId, voyageId, enabled }: UseVesselTrackingOptions) {
  const {
    setCurrentVesselPosition,
    setVesselTrack,
    appendTrackPoint,
    setVoyageProgress,
    setTrackingStatus,
    trackingStatus,
  } = useAppStore();

  const [connection, setConnection] = useState<ConnectionState>("idle");
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<number | null>(null);
  const progressRef = useRef<number | null>(null);
  // Guards against a reconnect storm if the socket keeps failing.
  const reconnectsRef = useRef(0);
  const closedByUsRef = useRef(false);

  const intervalMs = (trackingStatus?.update_interval_s ?? 5) * 1000;

  // --- feed provenance ------------------------------------------------------
  useEffect(() => {
    api
      .trackingStatus()
      .then(setTrackingStatus)
      .catch(() => setTrackingStatus(null));
  }, [setTrackingStatus]);

  // --- seed the trail from history -----------------------------------------
  useEffect(() => {
    if (!vesselId || !enabled) return;
    api
      .vesselTrack(vesselId, voyageId ?? undefined)
      .then((t) => setVesselTrack(t.points))
      .catch(() => setVesselTrack([]));
  }, [vesselId, voyageId, enabled, setVesselTrack]);

  const applyPosition = useCallback(
    (pos: VesselPosition) => {
      setCurrentVesselPosition(pos);
      appendTrackPoint({
        latitude: pos.latitude,
        longitude: pos.longitude,
        speed_knots: pos.speed_knots,
        heading_deg: pos.heading_deg,
        timestamp: pos.timestamp,
      });
    },
    [setCurrentVesselPosition, appendTrackPoint]
  );

  // --- polling fallback -----------------------------------------------------
  const startPolling = useCallback(() => {
    if (!vesselId || pollRef.current !== null) return;
    setConnection("polling");

    const tick = async () => {
      try {
        applyPosition(await api.vesselLocation(vesselId));
        setError(null);
      } catch (e: unknown) {
        // 404 simply means no simulation is running yet — not an error state.
        const status = (e as { response?: { status?: number } })?.response?.status;
        if (status === 401) setError("Your session expired. Log in again to reconnect to this voyage.");
        else if (status !== 404) setError("Lost contact with the vessel position feed.");
      }
    };

    tick();
    pollRef.current = window.setInterval(tick, intervalMs);
  }, [vesselId, intervalMs, applyPosition]);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // --- websocket ------------------------------------------------------------
  useEffect(() => {
    if (!vesselId || !enabled) {
      setConnection("idle");
      return;
    }

    closedByUsRef.current = false;
    reconnectsRef.current = 0;
    let cancelled = false;

    function connect() {
      const url = api.vesselLocationSocketUrl(vesselId!);
      if (!url) {
        startPolling();
        return;
      }

      setConnection("connecting");
      let socket: WebSocket;
      try {
        socket = new WebSocket(url);
      } catch {
        startPolling();
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        if (cancelled) return;
        stopPolling();
        reconnectsRef.current = 0;
        setConnection("live");
        setError(null);
      };

      socket.onmessage = (event) => {
        if (cancelled) return;
        try {
          const data = JSON.parse(event.data);
          if (data?.status === "NO_FIX") return; // no simulation running yet
          applyPosition(data as VesselPosition);
        } catch {
          // ignore a single malformed frame rather than tearing down the feed
        }
      };

      socket.onerror = () => {
        if (!cancelled) startPolling();
      };

      socket.onclose = (event) => {
        if (cancelled || closedByUsRef.current) return;
        socketRef.current = null;

        // 1008 = policy violation: bad token or not your vessel. Reconnecting
        // cannot fix that, so stop and surface it.
        if (event.code === 1008) {
          setConnection("error");
          setError("Not authorized to track this vessel.");
          return;
        }

        if (reconnectsRef.current < 3) {
          reconnectsRef.current += 1;
          startPolling(); // keep data flowing while we retry
          window.setTimeout(connect, 2000 * reconnectsRef.current);
        } else {
          startPolling(); // settle on polling for the rest of the session
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      closedByUsRef.current = true;
      socketRef.current?.close();
      socketRef.current = null;
      stopPolling();
    };
  }, [vesselId, enabled, applyPosition, startPolling, stopPolling]);

  // --- voyage progress ------------------------------------------------------
  useEffect(() => {
    if (!voyageId || !enabled) return;

    const tick = async () => {
      try {
        setVoyageProgress(await api.voyageTracking(voyageId));
      } catch {
        // progress is supplementary; the position feed keeps the map alive
      }
    };

    tick();
    progressRef.current = window.setInterval(tick, Math.max(intervalMs, 8000));
    return () => {
      if (progressRef.current !== null) window.clearInterval(progressRef.current);
      progressRef.current = null;
    };
  }, [voyageId, enabled, intervalMs, setVoyageProgress]);

  // --- simulation controls --------------------------------------------------
  const control = useCallback(
    async (action: SimulationAction, speedMultiplier?: number) => {
      if (!voyageId) return;
      try {
        const result = await api.controlSimulation(voyageId, {
          action,
          speed_multiplier: speedMultiplier,
        });
        setVoyageProgress(result);
        if (result.position) applyPosition(result.position);
        if (action === "reset") setVesselTrack([]);
        setError(null);
      } catch (e: unknown) {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
        setError(detail ?? "Could not update the simulation.");
      }
    },
    [voyageId, setVoyageProgress, applyPosition, setVesselTrack]
  );

  return { connection, error, control };
}

export default useVesselTracking;
