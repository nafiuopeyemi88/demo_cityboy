# Field Worker Location Tracker — Setup Guide

## What you're building

```
Mobile app / Simulator  →  FastAPI Backend  →  ArcGIS Feature Layer
                                    ↓                    ↓
                              SQLite (local)     ArcGIS Dashboard
```

---

## Part 1 — ArcGIS Online Setup (do this first)

### Step 1: Create a free developer account

1. Go to https://developers.arcgis.com
2. Click **Sign Up Free**
3. Confirm your email

### Step 2: Create an OAuth application (for API access)

1. Log into https://developers.arcgis.com
2. Go to **Dashboard → Applications → New Application**
3. Name it `WorkerTrackerApp`
4. Copy the **Client ID** and **Client Secret** → paste into your `.env`

### Step 3: Create a hosted Feature Layer (current positions)

This is where your FastAPI backend will push live locations.

1. Go to https://www.arcgis.com/home → sign in
2. Click **Content → New Item → Feature Layer → Define your own layer**
3. Choose **Point** geometry type
4. Name the layer: `WorkerTracker`
5. Add these fields (click Add Field for each):

| Field Name    | Type    | Length | Alias         |
|---------------|---------|--------|---------------|
| worker_id     | String  | 50     | Worker ID     |
| worker_name   | String  | 100    | Name          |
| latitude      | Double  |        | Latitude      |
| longitude     | Double  |        | Longitude     |
| battery_pct   | Integer |        | Battery %     |
| status        | String  | 20     | Status        |
| notes         | String  | 255    | Notes         |
| last_updated  | String  | 50     | Last Updated  |

6. Save and publish
7. Open the layer's **Item Details** page
8. Click **View** → look at the URL bar, copy the URL up to `/FeatureServer/0`
   It looks like: `https://services.arcgis.com/ABC123/arcgis/rest/services/WorkerTracker/FeatureServer/0`
9. Paste this into `ARCGIS_FEATURE_LAYER_URL` in your `.env`

### Step 4: Create the ArcGIS Dashboard

1. Go to https://www.arcgis.com/apps/dashboards/new
2. Click **Add Widget → Map**
3. In the map, click **Add Layer** → select your `WorkerTracker` layer
4. Style the points:
   - Go to the layer symbology
   - Use a **Unique Values** renderer on the `status` field
   - Green dot = active, Yellow = idle, Red = offline
5. Add more widgets:
   - **List** widget → show worker names with last_updated
   - **Indicator** widget → count of active workers
   - **Serial Chart** → battery levels by worker
6. Save the dashboard and share it (or keep it private for demo)

---

## Part 2 — Local Setup

### Install dependencies

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### Configure environment

```bash
cp .env.example .env
# Edit .env with your ArcGIS credentials and Feature Layer URL
nano .env
```

### Start the FastAPI server

```bash
python run.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Database ready at tracker.db
```

Open http://localhost:8000/docs to see the interactive API docs (Swagger UI).

---

## Part 3 — Run the Simulator

In a **new terminal**, with the venv active:

```bash
# Quick demo — 5 workers in Abuja, ping every 10 seconds
python simulator/simulator.py

# Production-realistic — 10-minute intervals
python simulator/simulator.py --interval 600 --workers 8

# Different city
python simulator/simulator.py --city lagos --workers 6

# Run exactly 20 rounds then stop
python simulator/simulator.py --rounds 20 --interval 5
```

You'll see output like:
```
10:23:01  INFO     ─── Round 1 (10:23:01 UTC) ───
10:23:01  INFO     ✓ Aminu Bello          lat=9.05234  lon=7.49821  bat=82%  [active]
10:23:01  INFO     ✓ Fatima Usman         lat=9.06112  lon=7.50123  bat=91%  [active]
10:23:01  INFO     Sleeping 10s until next ping...
```

---

## Part 4 — Verify the pipeline

### Check local API
```bash
# List all workers (latest positions)
curl http://localhost:8000/workers | python -m json.tool

# Post a manual location
curl -X POST http://localhost:8000/location \
  -H "Content-Type: application/json" \
  -d '{"worker_id":"test_1","worker_name":"Test Worker","latitude":9.06,"longitude":7.50}'
```

### Check ArcGIS

1. Go to your Feature Layer's Item Details → click **View**
2. You should see points appearing on the map
3. Open your Dashboard — workers should show as dots on the map

If the Feature Layer URL or credentials are wrong, the API still works and saves locally — check the logs for `ArcGIS update OK` or error messages.

---

## Part 5 — ArcGIS Dashboard configuration tips

### Real-time refresh
1. Open the Dashboard settings (gear icon)
2. Set **Data refresh interval** to 30 seconds or 1 minute
3. This polls the Feature Layer automatically — no websocket needed

### Worker track lines (show movement trails)
If you want to show where workers have been:
1. Create a second Feature Layer: `WorkerHistory` (same fields + a `timestamp` Date field)
2. Set `ARCGIS_HISTORY_LAYER_URL` in `.env`
3. In the dashboard, add the history layer with a **Track** renderer
4. Group by `worker_id`

### Mobile app (future)
Replace the simulator with a React Native or Flutter app that:
1. Gets GPS from device (`navigator.geolocation` on web, `expo-location` on RN)
2. POSTs to `POST /location` every 10 minutes (use a background task)
3. Sends the worker's JWT token in an `Authorization` header (add auth middleware to FastAPI)

---

## Project structure

```
field-tracker/
├── app/
│   ├── __init__.py
│   ├── main.py          ← FastAPI app, all endpoints
│   ├── models.py        ← Pydantic request/response models
│   ├── database.py      ← SQLite async layer (swap to PostGIS for prod)
│   └── arcgis.py        ← ArcGIS REST API integration + token cache
├── simulator/
│   └── simulator.py     ← Multi-worker GPS simulator
├── run.py               ← Entry point (loads .env, starts uvicorn)
├── requirements.txt
├── .env.example
└── SETUP.md             ← This file
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ArcGIS credentials not set` | Check `.env` has `ARCGIS_CLIENT_ID` and `ARCGIS_CLIENT_SECRET` |
| `ArcGIS update failed: 400` | The Feature Layer URL is wrong — check it ends in `/FeatureServer/0` |
| `ArcGIS update failed: 403` | Token expired or wrong client secret — regenerate in ArcGIS developer dashboard |
| Workers appear but don't move | Dashboard refresh interval might be off — enable auto-refresh |
| `ModuleNotFoundError` | Make sure you activated the venv: `source venv/bin/activate` |
| Port 8000 in use | Change `APP_PORT=8001` in `.env` and update simulator `--api` flag |
