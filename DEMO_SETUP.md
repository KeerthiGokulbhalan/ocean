# SeaPath Demo Setup Guide

Complete setup for both **local laptop demo** and **production deployment**.

---

## 🚀 Quick Start (Laptop Demo - 5 minutes)

### Option A: Docker Compose (Recommended - Zero Config)

```bash
# Clone and navigate
git clone https://github.com/Manoshankari78/SeaPath.git
cd SeaPath

# Start everything (backend + frontend + PostgreSQL)
docker compose up --build

# Wait for all services to start (2-3 min)
# Then open your browser:
# Frontend: http://localhost:5173
# Backend API Docs: http://localhost:8000/docs
# Database: postgres://postgres:postgres@localhost:5432/seapath
```

**That's it!** Everything runs in Docker with zero local setup.

✅ **Frontend**: http://localhost:5173  
✅ **Backend**: http://localhost:8000  
✅ **Database**: PostgreSQL + PostGIS (auto-configured)

---

### Option B: Local Setup (SQLite - No Database Required)

**Prerequisites:**
- Python 3.10+
- Node.js 18+

#### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run backend (uses SQLite by default)
uvicorn app.main:app --reload

# Terminal output:
# INFO:     Uvicorn running on http://127.0.0.1:8000
# INFO:     Application startup complete
```

Visit API docs: http://localhost:8000/docs

#### 2. Frontend Setup (New Terminal)

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev

# Terminal output:
# Local:   http://localhost:5173/
```

Visit http://localhost:5173 in your browser.

---

## 📝 Demo Walkthrough (For Your Mentor)

### 1. **Register & Login**
- Click **Register** (top right)
- Email: `demo@example.com`
- Password: `DemoPass123`
- Click **Register**
- Auto-redirected to login, enter same credentials

### 2. **Add a Vessel (Fleet Dashboard)**
- Navigate to **Fleet Dashboard** (sidebar)
- Click **+ Add Vessel**
- Fill in:
  - **Name**: "Demo Tanker"
  - **Type**: Container (or Tanker)
  - **Cruise Speed**: 18 knots
  - **Draft**: 10 m
- Click **Save**

### 3. **Generate Your First Route (Route Planner)**
- Navigate to **Route Planner** (home icon)
- Use preset: **Singapore → Port Said** (Suez Canal crossing)
  - Or enter custom coordinates
- Click **Optimize Route**
- **Wait 3-5 seconds** (fetches live weather from Open-Meteo API)

### 4. **Visualize Results**
- **3 Route Options** appear on the left:
  - ⚡ **Fastest** (shortest time)
  - 💰 **Efficient** (lowest fuel + CO₂)
  - 🛡️ **Safest** (avoids storms)
- Each shows:
  - Distance (nautical miles)
  - Duration (hours)
  - Fuel consumption (tons)
  - CO₂ emissions (tons)
  - Risk score (0-100)
  - Sustainability score

### 5. **Toggle Risk Radar**
- Check the **Risk radar overlay** checkbox
- Map updates with **color-coded risk heatmap**:
  - 🟢 Green = Safe (low wave height)
  - 🟡 Amber = Moderate risk
  - 🔴 Red = High risk (storms, strong winds)
- This is powered by **live Open-Meteo weather API**

### 6. **Run Speed Simulator**
- On the left panel, see **"What-If Simulator"**
- Adjust ship speed: drag slider or enter speed (knots)
- See real-time updates:
  - ⏱️ ETA changes
  - ⛽ Fuel consumption adjusts
  - 💨 How wave/wind affects the journey

### 7. **Save to Voyage History**
- Click a route comparison card (bottom right)
- Click **Save to voyage history**
- Success message: "Saved the efficient route..."

### 8. **View Voyage History**
- Navigate to **Voyage History** (sidebar)
- Your saved voyage appears with:
  - Route details
  - Status (Planned → In-Progress → Completed)
  - Waypoints list
  - PDF report download button

### 9. **Dynamic Re-routing**
- In Voyage History, click **"Re-optimize now"**
- App re-fetches **live weather** and recomputes the route
- If fuel/risk changed significantly, a **RouteChange alert** appears
- Check 🔔 **Alerts bell** (top nav) to see notifications

### 10. **Explore API Docs**
- Open http://localhost:8000/docs (Swagger UI)
- Test endpoints interactively:
  - `POST /api/route/optimize` - Compute routes
  - `POST /api/route/reoptimize/{voyage_id}` - Re-route live
  - `GET /api/voyages` - List saved voyages
  - `GET /api/alerts` - Check alerts

---

## 🔐 Pre-Made Test Accounts

| Email | Password | Role |
|-------|----------|------|
| demo@example.com | DemoPass123 | Operator |
| admin@example.com | AdminPass123 | Admin |

_(Or register new accounts as needed)_

---

## 🌍 Test Routes (For Demo)

Copy-paste these into the Route Planner:

### Route 1: Singapore → Port Said (Suez)
```
Origin:      1.35°N, 103.82°E
Destination: 31.86°N, 32.30°E
Vessel:      Container, 18 knots
```
**Duration**: ~7,000 nm, typically 4-5 days  
**Weather**: Tropical → Mediterranean (risk varies by season)

### Route 2: Los Angeles → Shanghai (Trans-Pacific)
```
Origin:      33.75°N, 118.19°W
Destination: 30.58°N, 114.27°E
Vessel:      Bulk Carrier, 15 knots
```
**Duration**: ~5,200 nm, typically 12-15 days  
**Weather**: Pacific storm season risk (Jul-Oct)

### Route 3: Rotterdam → Singapore (Via Suez)
```
Origin:      51.96°N, 4.13°E
Destination: 1.35°N, 103.82°E
Vessel:      Tanker, 18 knots
```
**Duration**: ~7,600 nm, 3-4 weeks  
**Weather**: Atlantic → Mediterranean → Indian Ocean

---

## 🛑 Troubleshooting (Laptop Demo)

### Problem: "Could not compute a route"
- ✅ **Solution 1**: Backend might be slow. Wait 5-10 seconds (first run trains ML model)
- ✅ **Solution 2**: Check backend logs:
  ```bash
  # Terminal with backend running
  # Should show: "INFO: Application startup complete"
  ```
- ✅ **Solution 3**: Ensure internet (Open-Meteo API needs it)

### Problem: Docker Compose won't start
```bash
# Clear containers and rebuild
docker compose down --volumes
docker compose up --build

# Or check Docker is running
docker ps  # Should list containers
```

### Problem: Frontend can't reach backend
- Check `ALLOWED_ORIGINS` in `backend/.env`
- Must include `http://localhost:5173`
- Restart backend after changing

### Problem: "Vessel not found" when saving routes
- First, add a vessel in **Fleet Dashboard**
- Routes need a vessel_id to save

---

## 🚀 Production Deployment

### Deploy to Render, Railway, or Heroku

#### Step 1: Push to GitHub (Already Done ✅)

#### Step 2: Set Environment Variables on Your Host

```bash
# Get these from your hosting provider's dashboard
# Example for Render:

DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/seapath_prod
SECRET_KEY=your-very-long-random-secret-key-here-minimum-32-chars
ALLOWED_ORIGINS=https://your-frontend-domain.com,https://your-backend-domain.com
VITE_API_BASE_URL=https://your-backend-domain.com/api
```

#### Step 3: Deploy Backend

**For Render, Railway, or Heroku:**

```bash
# 1. Connect your GitHub repo to the hosting platform
# 2. Set environment variables (as above)
# 3. Point to `backend/Dockerfile`
# 4. Set start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
# 5. Deploy
```

#### Step 4: Deploy Frontend

```bash
# 1. Connect your GitHub repo
# 2. Set build command: npm run build
# 3. Set output directory: dist/
# 4. Set environment variables (VITE_API_BASE_URL)
# 5. Deploy
```

#### Step 5: Verify Production URLs

```bash
curl https://your-backend-domain.com/api/health
# Response: {"status": "ok", "service": "seapath-api"}

# Visit frontend
https://your-frontend-domain.com
```

---

## 📊 Architecture Diagram

```
┌─────────────────────────────────────────────┐
│         LAPTOP DEMO SETUP                   │
├─────────────────────────────────────────────┤
│                                             │
│  Browser (http://localhost:5173)            │
│      ↓                                       │
│  React Frontend (Vite dev server)           │
│      ↓                                       │
│  FastAPI Backend (http://localhost:8000)    │
│      ↓                                       │
│  ┌─ SQLite (seapath.db)                     │
│  └─ OR PostgreSQL (localhost:5432)          │
│      ↓                                       │
│  Open-Meteo Marine Weather API (External)   │
│      ↓                                       │
│  A* Pathfinding + ML Fuel Model             │
│      ↓                                       │
│  Route Results + Alerts                     │
│                                             │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│      PRODUCTION DEPLOYMENT                  │
├─────────────────────────────────────────────┤
│                                             │
│  Browser (https://your-domain.com)          │
│      ↓                                       │
│  React Frontend (on CDN or hosting)         │
│      ↓                                       │
│  FastAPI Backend (Render/Railway/Heroku)    │
│      ↓                                       │
│  PostgreSQL + PostGIS (Managed DB)          │
│      ↓                                       │
│  Open-Meteo Marine Weather API              │
│      ↓                                       │
│  Real-Time Route Optimization               │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 📋 Demo Checklist (For Your Mentor)

- [ ] Backend running (`http://localhost:8000/docs` accessible)
- [ ] Frontend running (`http://localhost:5173` loads)
- [ ] Can register/login
- [ ] Can add a vessel to fleet
- [ ] Can generate a route (wait for weather data)
- [ ] Can see 3 route options with metrics
- [ ] Can toggle risk radar overlay
- [ ] Can run speed simulator
- [ ] Can save voyage to history
- [ ] Can re-optimize and trigger alerts
- [ ] Can view PDF report (Voyage History)
- [ ] API docs at `/docs` show all endpoints

---

## 🎯 Key Features to Highlight in Demo

1. **Live Weather Integration**: Open-Meteo API provides real wave/wind data
2. **3 Optimization Strategies**: Fastest vs Efficient vs Safest
3. **AI/ML Fuel Prediction**: RandomForest model refines estimates
4. **Risk Visualization**: Heatmap shows danger zones
5. **Dynamic Re-routing**: Mid-voyage scenario (reoptimize button)
6. **Alerts System**: Automatic warnings for high-risk conditions
7. **Voyage Persistence**: Full history with PDFs and status tracking
8. **Spatial Queries**: Find voyages near a point (if PostGIS enabled)
9. **JWT Authentication**: User scoping
10. **Production-Ready**: Deployable to Render/Railway/Heroku

---

## 📚 Additional Resources

- **Backend API**: http://localhost:8000/docs (Swagger UI)
- **GitHub Repo**: https://github.com/Manoshankari78/SeaPath
- **Open-Meteo API Docs**: https://open-meteo.com/en/docs/marine-weather-api
- **Leaflet Map Docs**: https://leafletjs.com/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **React + TypeScript**: https://react.dev/

---

## ✅ You're Ready!

**For Mentor Demo on Laptop:**
1. Run `docker compose up --build` OR follow Option B (local setup)
2. Walk through the 10-step demo walkthrough above
3. Show API docs at `/docs`
4. Highlight real Open-Meteo weather integration

**For Production:**
1. Push to GitHub
2. Deploy to Render/Railway/Heroku
3. Set environment variables
4. Share deployed URL with stakeholders

Good luck with your presentation! 🚀
