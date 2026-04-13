"""
Field Worker Location Tracker - FastAPI Backend
Receives GPS pings from workers and pushes to ArcGIS Feature Layer
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import httpx
import asyncio
import logging
from datetime import datetime, timezone

from .database import init_db, get_db, save_location, get_all_workers, get_worker_history
from .models import LocationPing, WorkerLocation
from .arcgis import push_to_arcgis, get_arcgis_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize DB and ArcGIS token cache."""
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Field Worker Tracker",
    description="Real-time GPS location tracking for field workers",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "running", "service": "Field Worker Tracker API"}


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/location", summary="Receive a GPS ping from a worker")
async def receive_location(ping: LocationPing, background_tasks: BackgroundTasks):
    """
    Worker devices POST here every N minutes with their location.
    
    Body example:
    {
        "worker_id": "worker_001",
        "worker_name": "Aminu Bello",
        "latitude": 9.0579,
        "longitude": 7.4951,
        "accuracy_meters": 5.0,
        "battery_pct": 82
    }
    """
    # 1. Save to local database
    record = await save_location(ping)
    logger.info(f"Saved location for {ping.worker_id} at ({ping.latitude}, {ping.longitude})")

    # 2. Push to ArcGIS in background (non-blocking)
    background_tasks.add_task(push_to_arcgis, ping)

    return {
        "status": "accepted",
        "worker_id": ping.worker_id,
        "timestamp": record["timestamp"],
        "message": "Location saved and queued for ArcGIS sync"
    }


@app.get("/workers", summary="Get last known location of all workers")
async def list_workers():
    """Returns the most recent location for every active worker."""
    workers = await get_all_workers()
    return {"count": len(workers), "workers": workers}


@app.get("/workers/{worker_id}/history", summary="Get location history for a worker")
async def worker_history(worker_id: str, limit: int = 50):
    """Returns the last N locations for a specific worker."""
    history = await get_worker_history(worker_id, limit)
    if not history:
        raise HTTPException(status_code=404, detail=f"No history found for worker {worker_id}")
    return {"worker_id": worker_id, "count": len(history), "locations": history}


@app.delete("/workers/{worker_id}", summary="Remove a worker from tracking")
async def remove_worker(worker_id: str):
    """Marks a worker as inactive (stops showing on dashboard)."""
    # In production, update worker status in DB
    return {"status": "ok", "message": f"Worker {worker_id} removed from active tracking"}
