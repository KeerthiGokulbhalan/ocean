import { useCallback, useEffect, useRef, useState } from "react";
import { Globe } from "lucide-react";
import AlertBanner from "../components/AlertBanner";
import LiveVesselPanel from "../components/LiveVesselPanel";
import MapView from "../components/MapView";
import CurrentLocationWeatherCard from "../components/CurrentLocationWeatherCard";
import MarineWeatherCard from "../components/MarineWeatherCard";
import RiskRadarLegend from "../components/RiskRadarLegend";
import RouteComparisonCards from "../components/RouteComparisonCards";
import RouteForm from "../components/RouteForm";
import WhatIfSimulator from "../components/WhatIfSimulator";
import api from "../api/client";
import useVesselTracking from "../hooks/useVesselTracking";
import { useAppStore } from "../store/useAppStore";
import type {
  Coordinate,
  Port,
  RouteOption,
  RouteStrategy,
  VesselOut,
  VesselProfile,
} from "../types";

export default function Home() {
  const {
    lastRoute,
    setLastRoute,
    selectedStrategy,
    setSelectedStrategy,
    ports,
    portsLoaded,
    setPorts,
    selectedOriginPort,
    selectedDestinationPort,
    setSelectedOriginPort,
    setSelectedDestinationPort,
    showPorts,
    setShowPorts,
    activeVesselId,
    activeVoyageId,
    setActiveVessel,
    currentVesselPosition,
    vesselTrack,
    voyageProgress,
    trackingStatus,
    resetTracking,
  } = useAppStore();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [showRiskRadar, setShowRiskRadar] = useState(false);
  const [fleet, setFleet] = useState<VesselOut[]>([]);
  const [selectedVesselId, setSelectedVesselId] = useState<number | null>(null);
  const [portsLoading, setPortsLoading] = useState(false);
  const [focusSignal, setFocusSignal] = useState(0);
  const [reoptimizing, setReoptimizing] = useState(false);
  const rerouteInFlight = useRef(false);
  const lastReroutePosition = useRef<{
    voyageId: number;
    lat: number;
    lon: number;
  } | null>(null);

  // --- load the port dataset once, then filter locally -------------------
  useEffect(() => {
    if (portsLoaded) return;
    setPortsLoading(true);
    api
      .listPorts()
      .then((r) => setPorts(r.ports))
      .catch(() =>
        setError("Could not load the port list. Is the backend running?"),
      )
      .finally(() => setPortsLoading(false));
  }, [portsLoaded, setPorts]);

  // --- fleet, for the vessel picker --------------------------------------
  useEffect(() => {
    api
      .listFleet()
      .then((v) => {
        setFleet(v);
        setSelectedVesselId((current) => current ?? v[0]?.id ?? null);
      })
      .catch(() => setFleet([]));
  }, []);

  const {
    connection,
    error: trackingError,
    control,
  } = useVesselTracking({
    vesselId: activeVesselId,
    voyageId: activeVoyageId,
    enabled: Boolean(activeVesselId && activeVoyageId),
  });

  // Recalculate from the moving ship's actual position during demo playback.
  // The interval reads the latest store snapshot so frequent position updates
  // do not continually restart its timer.
  useEffect(() => {
    if (!activeVoyageId || !activeVesselId) return;
    rerouteInFlight.current = false;
    lastReroutePosition.current = null;
    const timer = window.setInterval(async () => {
      const state = useAppStore.getState();
      const position = state.currentVesselPosition;
      if (
        !position ||
        state.voyageProgress?.simulation_running !== true ||
        rerouteInFlight.current
      )
        return;
      const previous = lastReroutePosition.current;
      if (previous?.voyageId === activeVoyageId) {
        const latDelta = (position.latitude - previous.lat) * 111;
        const lonDelta =
          (position.longitude - previous.lon) *
          111 *
          Math.cos((position.latitude * Math.PI) / 180);
        if (Math.hypot(latDelta, lonDelta) < 0.5) return;
      }
      rerouteInFlight.current = true;
      setReoptimizing(true);
      try {
        const response = await api.reoptimizeVoyage(activeVoyageId, {
          lat: position.latitude,
          lon: position.longitude,
        });
        if (response.options.length) {
          lastReroutePosition.current = {
            voyageId: activeVoyageId,
            lat: position.latitude,
            lon: position.longitude,
          };
          setLastRoute({
            ...response,
            origin: state.lastRoute?.origin ?? response.origin,
          });
          setSavedMsg(
            "Route dynamically re-optimized from the ship’s current position using A* and the Random Forest fuel estimate.",
          );
        }
      } catch {
        // Keep playback going if a weather or routing request is temporarily unavailable.
      } finally {
        rerouteInFlight.current = false;
        setReoptimizing(false);
      }
    }, 60000);
    return () => window.clearInterval(timer);
  }, [activeVoyageId, activeVesselId, setLastRoute]);

  async function handleSubmit(
    origin: Coordinate,
    destination: Coordinate,
    vessel: VesselProfile,
  ) {
    setLoading(true);
    setError(null);
    setSavedMsg(null);
    try {
      const resp = await api.optimizeRoute({ origin, destination, vessel });
      setLastRoute(resp);
      if (resp.options.length > 0)
        setSelectedStrategy(resp.options[0].strategy);
    } catch {
      setError(
        "Could not compute a route. Make sure the backend server is running.",
      );
    } finally {
      setLoading(false);
    }
  }

  /** Saves the chosen route as a voyage and begins live tracking on it. */
  async function handleStartVoyage(opt: RouteOption) {
    if (!lastRoute) return;
    setSavedMsg(null);
    try {
      // The planner offers an ad-hoc profile. Create a demo fleet record on
      // demand so that profile can be attached to a trackable voyage.
      let vesselId = selectedVesselId;
      if (!vesselId) {
        const created = await api.createVessel({
          name: lastRoute.vessel.name || "SeaPath Demo Vessel",
          vessel_type: lastRoute.vessel.vessel_type,
          cruise_speed_knots: lastRoute.vessel.cruise_speed_knots,
          draft_m: lastRoute.vessel.draft_m,
          deadweight_tons: lastRoute.vessel.deadweight_tons,
          fuel_rate_ton_per_hr: lastRoute.vessel.fuel_rate_ton_per_hr ?? null,
        });
        vesselId = created.id;
        setSelectedVesselId(created.id);
        setFleet((current) => [...current, created]);
      }

      const voyage = await api.createVoyage({
        vessel_id: vesselId,
        start_port: selectedOriginPort?.name,
        end_port: selectedDestinationPort?.name,
        origin: lastRoute.origin,
        destination: lastRoute.destination,
        strategy: opt.strategy as RouteStrategy,
        status: "Planned",
        distance_nm: opt.distance_nm,
        duration_hr: opt.duration_hr,
        fuel_tons: opt.fuel_tons,
        co2_tons: opt.co2_tons,
        route_points: opt.points,
        risk_segments: opt.risk_segments,
        weather_alerts: opt.weather_alerts,
      });

      resetTracking();
      setActiveVessel(vesselId, voyage.id);
      await api.controlSimulation(voyage.id, { action: "start" });
      setSavedMsg(
        `Voyage #${voyage.id} started — tracking the ${opt.strategy} route.`,
      );
    } catch (e: unknown) {
      const detail = (
        e as { response?: { status?: number; data?: { detail?: string } } }
      )?.response;
      setSavedMsg(
        detail?.status === 401
          ? "Your session has expired. Log in again, then start the demo voyage."
          : detail?.data?.detail
            ? `Could not start the voyage: ${detail.data.detail}`
            : "Could not start the demo voyage. Check that the backend is running, then try again.",
      );
    }
  }

  const handleFocusVessel = useCallback(() => setFocusSignal((n) => n + 1), []);

  const handleSetOriginFromMap = useCallback(
    (port: Port) => setSelectedOriginPort(port),
    [setSelectedOriginPort],
  );
  const handleSetDestinationFromMap = useCallback(
    (port: Port) => setSelectedDestinationPort(port),
    [setSelectedDestinationPort],
  );

  const activeOption = lastRoute?.options.find(
    (o) => o.strategy === selectedStrategy,
  );
  const activeVesselName =
    fleet.find((v) => v.id === activeVesselId)?.name ??
    voyageProgress?.vessel_name ??
    "Vessel";
  const isTracking = Boolean(activeVesselId && activeVoyageId);

  return (
    <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 p-4 sm:p-6 lg:grid-cols-[380px_1fr]">
      <div className="space-y-4">
        <RouteForm
          onSubmit={handleSubmit}
          loading={loading}
          ports={ports}
          portsLoading={portsLoading}
          originPort={selectedOriginPort}
          destinationPort={selectedDestinationPort}
          onOriginPortChange={setSelectedOriginPort}
          onDestinationPortChange={setSelectedDestinationPort}
          fleet={fleet}
          selectedVesselId={selectedVesselId}
          onVesselChange={setSelectedVesselId}
        />

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {savedMsg && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {savedMsg}
          </div>
        )}
        {reoptimizing && (
          <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
            Recalculating the remaining route and fuel estimate from the ship’s
            current position…
          </div>
        )}

        {isTracking && (
          <LiveVesselPanel
            tracking={voyageProgress}
            position={currentVesselPosition}
            status={trackingStatus}
            connection={connection}
            error={trackingError}
            onControl={control}
            onFocusVessel={handleFocusVessel}
            showDemoControls={trackingStatus?.simulated ?? true}
          />
        )}

        {activeOption && <WhatIfSimulator baseline={activeOption} />}
      </div>

      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm font-medium text-ink">
              <input
                type="checkbox"
                checked={showRiskRadar}
                onChange={(e) => setShowRiskRadar(e.target.checked)}
                className="h-4 w-4 accent-deepblue"
              />
              Risk radar overlay
            </label>

            <button
              type="button"
              onClick={() => setShowPorts(!showPorts)}
              aria-pressed={showPorts}
              className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-semibold transition ${
                showPorts
                  ? "border-deepblue bg-deepblue text-white"
                  : "border-slate-200 text-slate-600 hover:bg-slate-50"
              }`}
            >
              <Globe size={13} />
              Show Indian Ports
            </button>
          </div>

          {showRiskRadar && <RiskRadarLegend />}
        </div>

        <div className="h-[420px] overflow-hidden rounded-xl shadow-sm">
          <MapView
            origin={
              lastRoute?.origin ??
              (selectedOriginPort
                ? {
                    lat: selectedOriginPort.latitude,
                    lon: selectedOriginPort.longitude,
                  }
                : null)
            }
            destination={
              lastRoute?.destination ??
              (selectedDestinationPort
                ? {
                    lat: selectedDestinationPort.latitude,
                    lon: selectedDestinationPort.longitude,
                  }
                : null)
            }
            options={lastRoute?.options ?? []}
            activeStrategy={selectedStrategy}
            showRiskRadar={showRiskRadar}
            weatherAlerts={activeOption?.weather_alerts ?? []}
            vesselId={activeVesselId}
            vesselName={activeVesselName}
            vesselPosition={currentVesselPosition}
            vesselTrack={vesselTrack}
            originPort={selectedOriginPort}
            destinationPort={selectedDestinationPort}
            ports={ports}
            showPorts={showPorts}
            onSetOriginPort={handleSetOriginFromMap}
            onSetDestinationPort={handleSetDestinationFromMap}
            focusVesselSignal={focusSignal}
            obstacle={voyageProgress?.obstacle}
            originalRoute={voyageProgress?.original_route}
            alternateRoute={voyageProgress?.alternate_route}
          />
        </div>

        {lastRoute && (
          <AlertBanner
            options={lastRoute.options}
            warnings={lastRoute.warnings}
          />
        )}

        {lastRoute && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <MarineWeatherCard
              label="Conditions at origin"
              point={lastRoute.origin}
            />
            <MarineWeatherCard
              label="Conditions at destination"
              point={lastRoute.destination}
            />
            <CurrentLocationWeatherCard />
          </div>
        )}

        {!lastRoute && <CurrentLocationWeatherCard />}

        {lastRoute && (
          <RouteComparisonCards
            options={lastRoute.options}
            activeStrategy={selectedStrategy as RouteStrategy}
            onSelect={setSelectedStrategy}
            onSaveVoyage={handleStartVoyage}
          />
        )}

        {!lastRoute && !loading && (
          <div className="flex h-40 items-center justify-center rounded-xl border-2 border-dashed border-slate-200 px-4 text-center text-sm text-slate-400">
            Search for an origin and destination port, then click “Calculate
            Route”.
          </div>
        )}
      </div>
    </div>
  );
}
