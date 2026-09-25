# SeaPath — AI-Assisted Ship Route & Fuel Optimization Platform

A full-stack ship-routing project: a **FastAPI + Python** backend that computes
fuel-, safety-, and speed-optimized sea routes with a real A\* search over a
navigable ocean grid, and a **React + TypeScript + Tailwind CSS** frontend
with an interactive Leaflet map, a risk-radar heatmap, fleet dashboard, and
voyage history/reporting — all behind JWT authentication.

## Architecture

```
seapath/
├── backend/            FastAPI app, routing engine, ML fuel model, DB
│   └── app/
│       ├── routing/     geo math, land mask, grid, A* pathfinding, cost model
│       ├── services/    weather client, fuel ML model, emissions, PDF reports,
│       │                 route planner, port seeding, voyage simulator, tracking
│       │                 └── ais/   AISProvider interface + mock/real providers
│       ├── data/        indian_ports.py — seeded Indian port dataset
│       ├── api/         REST endpoints (auth, routing, fleet, voyages, alerts,
│       │                 weather, ports, tracking + WebSocket)
│       ├── db/          SQLAlchemy models (User, Vessel, Voyage, Waypoint,
│       │                 WeatherSnapshot, Alert, Report, VesselPosition, Port)
│       └── security.py  password hashing + JWT
└── frontend/            React + TS + Tailwind app
    └── src/
        ├── components/  MapView (+risk radar, ship marker, track, ports),
        │                 RouteForm, PortSearch, ShipMarker, PortMarkers,
        │                 LiveVesselPanel, comparison cards, alerts, nav bar
        ├── hooks/        useVesselTracking (WebSocket + polling fallback)
        ├── pages/        Home (planner), Fleet, History, Login, Register
        ├── context/      AuthContext (JWT session)
        ├── api/          typed axios client (auto-attaches JWT)
        ├── store/        Zustand global state
        └── test/         Vitest + Testing Library suites
```

## How routing works

1. A rectangular lat/lon **grid** is built around the origin/destination (with
   the search box widened automatically if a landmass blocks the direct
   corridor — e.g. routing around a subcontinent).
2. Each grid cell is classified **ocean or land** using the offline
   `global-land-mask` package (no external data download required).
3. **A\*** search runs three times per request with different edge-cost
   weightings — `fastest`, `efficient` (fuel-optimal), and `safest`
   (wave/wind-risk averse) — each returning a distinct route.
4. Live **wave/wind data** is sampled (concurrently) from the free Open-Meteo
   Marine API across the search area and factored into the cost function,
   the route's overall risk score, and a **per-point risk array** used by the
   frontend's risk-radar heatmap.
5. A small **RandomForest ML model** (trained on synthetic, physically
   plausible data at startup) refines the physics-based fuel estimate.
6. Results include distance, duration, fuel burn, CO₂ emissions, a risk
   score, and a 0–100 sustainability score.

## Feature set

- **Authentication** — JWT-based register/login; fleets and voyages are
  scoped to the signed-in user.
- **Fleet dashboard** — vessel profiles with type, cruise speed, draft,
  deadweight, and an optional custom fuel-burn rate.
- **Route planner** — three strategy options per request, a what-if speed
  simulator, and high-risk alert banners.
- **Risk-radar heatmap** — toggle an overlay that colors the route
  segment-by-segment (green/amber/red) by local wave/wind risk.
- **Voyage history** — status tracking (Planned → In-Progress → Completed),
  waypoints, and downloadable PDF reports.
- **Alerts** — automatic `StormWarning` alerts when a saved route crosses
  high-risk weather, and a **dynamic re-routing** endpoint that re-evaluates
  a saved voyage against live conditions and raises a `RouteChange` alert if
  the fuel/risk estimate has shifted materially. The alerts bell in the nav
  bar polls for updates.
- **Spatial search (PostGIS)** — `GET /api/voyages/nearby?lat=&lon=&radius_km=`
  finds saved voyages passing within a radius of a point using a real
  `ST_DWithin` geography query (falls back to a Python haversine calculation
  on SQLite).

### New in v1.1 — Indian ports & live tracking

- **Indian port search** — a seeded dataset of 45 Indian ports (all 12 Major
  Ports plus major non-major/private ports) with searchable, keyboard-accessible
  origin/destination dropdowns. Search by port name, state, or UN/LOCODE.
- **Live ship tracking** — the vessel's current position streams to the map
  over a WebSocket (with an automatic polling fallback), rendered as a
  heading-rotated ship marker.
- **AIS provider architecture** — positions are read through a pluggable
  `AISProvider` interface. Ships with `MockAISProvider` (the built-in voyage
  simulator) so the project is fully demonstrable without a paid AIS feed;
  a real feed is an environment-variable swap.
- **Demo ship simulation** — the vessel moves along the *actual A\*-calculated
  route*, interpolated between waypoints for smooth motion. Start / pause /
  reset with 1x–10x playback.
- **Voyage progress** — distance travelled, distance remaining, percentage and
  ETA, all derived from real route geometry.
- **Ship track history** — persisted breadcrumb positions drawn as a polyline,
  visually distinct from the remaining (dashed) route.
- **Live vessel weather & risk** — the existing Open-Meteo client and wave-risk
  model are re-used at the vessel's current position, raising `StormWarning`
  alerts through the existing alert system when conditions deteriorate.
- **Port map overlay** — toggle **Show Indian Ports** to plot every port; click
  one to set - **Conditions at current location** — a card that uses the browser's
  geolocation (on explicit click, not automatically) to show live wave,
  wind and sea-temperature conditions at wherever you're standing, reusing
  the same weather service as the origin/destination cards.
  
## Quick start (local, no Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://localhost:8000
```
Interactive API docs: http://localhost:8000/docs
(Set a real `SECRET_KEY` env var before deploying — the default is dev-only.)

By default this uses **SQLite** (`backend/seapath.db`, created automatically)
— zero extra setup. To use **PostgreSQL + PostGIS** instead, see the next
section.

### Frontend
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```
The Vite dev server proxies `/api/*` to `http://localhost:8000`, so just
run both and open the frontend URL.

## Running with PostgreSQL + PostGIS

The app works with either SQLite (default, zero setup) or PostgreSQL +
PostGIS. Switching just requires setting `DATABASE_URL` — no code changes.
When PostGIS is active, the `/api/voyages/nearby` endpoint runs a real
`ST_DWithin` spatial query (great-circle distance, not flat-plane) to find
saved voyages passing near a point; if PostGIS isn't available (SQLite, or
a Postgres user without `CREATE EXTENSION` rights) it falls back to an
equivalent haversine calculation in Python automatically, so the endpoint
never breaks either way.

`app/db/session.py` also normalizes the connection string: a `postgres://`
URL (what Heroku/Render/Railway/Supabase hand you) is rewritten to
`postgresql+psycopg2://` automatically, so you can paste a cloud dashboard's
URL straight into `DATABASE_URL` without editing it.

### A. Local PostgreSQL

```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-16-postgis-3 postgresql-contrib
sudo service postgresql start

# macOS
brew install postgresql@16 postgis
brew services start postgresql@16
```
Create the database and set a password:
```bash
sudo -u postgres createdb seapath
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
```
Point the backend at it (copy `backend/.env.example` to `backend/.env`, or
export directly) and run as normal:
```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/seapath"
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
On startup the app runs `CREATE EXTENSION IF NOT EXISTS postgis` and then
creates all tables — no manual migration step needed. (This exact flow —
auth, fleet, route optimize, voyage save, and the PostGIS `ST_DWithin`
nearby-search — was verified end-to-end against a real local Postgres 16 +
PostGIS 3.4 instance while building this project.)

### B. Local via Docker Compose

```bash
docker compose up --build
```
This starts a `postgis/postgis:16-3.4` container alongside the backend and
frontend, with `DATABASE_URL` already wired up to it — nothing to configure.
- Frontend: http://localhost:5173
- Backend:  http://localhost:8000/docs
- Postgres+PostGIS: localhost:5432 (db/user/password: seapath/postgres/postgres)

### C. Cloud deployment

The only thing that changes between providers is the connection string and
whether PostGIS needs enabling manually. General shape:

```bash
export DATABASE_URL="<connection string from your provider>"
export SECRET_KEY="<a long random value — do not use the dev default>"
export ALLOWED_ORIGINS="https://your-frontend-domain.com"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Managed Postgres with PostGIS built in (Supabase, Neon, Render, Railway,
Aiven, ElephantSQL, AWS RDS with the PostGIS parameter/extension enabled):**
- Copy the connection string from the provider's dashboard straight into
  `DATABASE_URL` — `postgres://` and `postgresql://` forms both work.
- If PostGIS is already enabled by the provider (Supabase and most modern
  managed Postgres offer a one-click toggle), the app detects it and the
  spatial search runs as real PostGIS `ST_DWithin` queries.
- If the app's database user can't run `CREATE EXTENSION` (common on
  managed platforms — verified in testing that this fails safely), you'll
  see a one-time warning in the logs on startup and nothing else changes:
  the app still starts, and `/api/voyages/nearby` automatically falls back
  to the Python haversine calculation instead of erroring.
- If you want true PostGIS spatial queries on such a provider, enable the
  extension yourself once via the provider's SQL console or dashboard
  toggle (e.g. Supabase → Database → Extensions → postgis), or run
  `CREATE EXTENSION IF NOT EXISTS postgis;` as an admin/superuser role.

**AWS RDS specifically:** PostGIS must be listed in the DB parameter
group's supported extensions (RDS Postgres ships with it available) and
the connecting user needs `rds_superuser` (or equivalent) to run
`CREATE EXTENSION`. If using a least-privilege app user instead, enable the
extension once with an admin user before pointing the app at it.

**SSL:** most cloud Postgres providers require SSL. If you see an SSL
negotiation error, append `?sslmode=require` to `DATABASE_URL`, e.g.
`postgresql://user:pass@host:5432/db?sslmode=require`.

**Frontend on a separate host from the backend:** set
`VITE_API_BASE_URL` to the deployed backend's `/api` URL at build time
(see `frontend/Dockerfile`'s `ARG VITE_API_BASE_URL`), and set the
backend's `ALLOWED_ORIGINS` to the frontend's deployed URL so CORS allows
the requests through.

### Inspecting the database
```bash
# SQLite
sqlite3 backend/seapath.db
.tables

# PostgreSQL (local or cloud — psql accepts the same DATABASE_URL)
psql "$DATABASE_URL"
\dt
SELECT PostGIS_Version();   -- only works if the extension is enabled
```

## Live tracking configuration

All values have working defaults — the app runs with no `.env` at all. See
`backend/.env.example`.

```env
AIS_PROVIDER=mock              # mock | real
LOCATION_UPDATE_INTERVAL=5     # seconds between position pushes
ENABLE_LIVE_TRACKING=true      # master switch for all tracking endpoints
POSITION_PERSIST_INTERVAL_S=60 # min seconds between DB position writes
MAX_TRACK_POINTS=500           # cap on history returned per track request
LIVE_ALERT_WAVE_HEIGHT_M=4.0   # wave height that raises a StormWarning
```

### How live tracking works

```
AIS provider (MockAISProvider | RealAISProvider)
        |                 selected by AIS_PROVIDER
        v
Backend tracking service  (throttled persistence, weather + risk, alerts)
        |
        v
WebSocket  /ws/vessels/{id}/location     <-- preferred
   or polling  GET /api/vessels/{id}/location   <-- automatic fallback
        |
        v
Frontend  useVesselTracking hook -> Zustand store
        |
        v
Leaflet ship marker (rotated to heading) + track polyline
```

**Simulated positions are never presented as real AIS data.** Every position
carries `source` and `is_simulated`, and the UI renders a
`LIVE TRACKING — DEMO SIMULATION` badge whenever the mock provider is active.

### Switching to a real AIS feed

1. Set `AIS_PROVIDER=real`, `AIS_API_URL` and `AIS_API_KEY` in the environment
   (never commit these).
2. Implement `_parse_vessel()` in `backend/app/services/ais/real_provider.py`
   to normalise your vendor's payload into a `VesselFix`.
3. Add an `mmsi` (or `imo`) column to the `Vessel` model to map SeaPath vessel
   IDs onto AIS identifiers.

Nothing else changes — the API, WebSocket, store and map all consume the same
`VesselFix` shape. Until step 2 is done the real provider returns no positions
rather than silently falling back to simulated data.

### Using AISstream.io

SeaPath also includes a server-side AISstream WebSocket adapter. Set the
following in the repository-root `.env` file (Compose passes them only to the
backend):

```env
AIS_PROVIDER=aisstream
AIS_API_URL=wss://stream.aisstream.io/v0/stream
AIS_API_KEY=your_private_aisstream_key
AISSTREAM_STALE_SECONDS=180
```

Add a vessel's nine-digit MMSI in the Fleet form, then restart the backend so
the AISstream subscription includes it. The backend keeps one WebSocket open,
filters the subscription to fleet MMSIs, and the existing API/UI display the
received positions. Use one backend process because AISstream limits open
connections per account and originating IP. Positions older than the stale
limit are omitted. Never expose or commit the API key. A valid AISstream key
and MMSI are required; the placeholder key does not authenticate.

### How port search works

```
backend/app/data/indian_ports.py   (dataset, extensible)
        |  seed_ports() upserts on every boot
        v
ports table  ->  GET /api/ports?search=&state=&port_type=
        |
        v
Frontend loads once, filters locally  ->  PortSearch dropdown
        |
        v
Selected port -> latitude / longitude -> existing A* routing engine
```

To add a port, append a record to `INDIAN_PORTS` and restart. The seed is an
idempotent upsert keyed on `id`, so no migration is needed.

## Using the app

1. **Register** an account (Operator role by default).
2. Go to **Fleet Dashboard** and add a vessel — voyages are linked to a
   vessel ID.
3. Go to **Route Planner** and search for an **Origin** and **Destination**
   port (type a name, a state, or a UN/LOCODE — e.g. "Chennai", "Kerala",
   "INBOM"). Pick the vessel you just added, then click **Calculate Route**.
   Three route options render on the map. Toggle **Risk radar overlay** to see
   wave/wind risk color-coded along the route, or **Show Indian Ports** to plot
   every port and set origin/destination straight from the map.
4. Click a comparison card to preview that route, or start the voyage to
   persist it and begin live tracking (this also raises a StormWarning alert if
   the route crosses high-risk weather).
5. Use the **live tracking panel** to Start / Pause / Reset the simulation and
   change playback speed. The ship marker moves along the calculated route,
   leaving a green track behind it; progress, ETA and current wave/wind risk
   update as it sails. **Track Ship** re-centres the map on the vessel.
6. In **Voyage History**, update a voyage's status, download its PDF report,
   or click **Re-optimize now** to simulate dynamic re-routing against
   current conditions.
7. Check the 🔔 bell in the nav bar for alerts.

## Testing

```bash
# Backend (71 tests: ports, simulation, tracking, auth scoping, WebSocket)
cd backend
source .venv/bin/activate
pip install pytest httpx
pytest -q

# Frontend (33 tests: port dropdown, tracking panel, store)
cd frontend
npm install
npm test
```

Tests use a throwaway SQLite database and the mock AIS provider, so no network
access or external services are required.

## Extending toward production

- The app already runs on **PostgreSQL + PostGIS** (see above) — for scale,
  add indexes on `waypoints(latitude, longitude)` or a proper `geography`
  column with a GiST index if the spatial search needs to cover a very large
  voyage history.
- Swap the synthetic ML training set in `services/fuel_model.py` for real
  historical voyage logs.
- Swap `global-land-mask` for GSHHG/Natural Earth polygons in PostGIS for
  higher-resolution coastlines.
- Run `/api/route/reoptimize/{voyage_id}` on a scheduler (APScheduler /
  Celery beat) instead of on-demand, for true continuous dynamic re-routing.
- Add refresh tokens / shorter-lived access tokens for stronger auth.

## Tech stack

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, React Router,
Leaflet/react-leaflet, Zustand, Axios, Recharts.

**Backend:** FastAPI, Pydantic, SQLAlchemy, SQLite (PostgreSQL-ready),
NumPy/Pandas, scikit-learn, httpx, global-land-mask, ReportLab, python-jose
(JWT), bcrypt.

**Data sources:** Open-Meteo Marine Weather API (live), synthetic training
data for the ML fuel model (swap for real logs in production).

