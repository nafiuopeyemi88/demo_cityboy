"""
Async SQLite database layer using aiosqlite.
For production, swap to asyncpg + PostGIS.
"""

import aiosqlite
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from .models import LocationPing

logger = logging.getLogger(__name__)
DB_PATH = "tracker.db"


async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id   TEXT NOT NULL,
                worker_name TEXT NOT NULL,
                latitude    REAL NOT NULL,
                longitude   REAL NOT NULL,
                accuracy_meters REAL,
                battery_pct INTEGER,
                status      TEXT DEFAULT 'active',
                notes       TEXT,
                timestamp   TEXT NOT NULL
            )
        """)
        # Index for fast worker lookups
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_worker_time 
            ON locations(worker_id, timestamp DESC)
        """)
        await db.commit()
    logger.info("Database ready at %s", DB_PATH)


async def get_db():
    """Dependency — yields a db connection (use in FastAPI Depends if needed)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def save_location(ping: LocationPing) -> Dict[str, Any]:
    """Insert a new location record and return it."""
    ts = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO locations 
                (worker_id, worker_name, latitude, longitude,
                 accuracy_meters, battery_pct, status, notes, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ping.worker_id, ping.worker_name,
            ping.latitude, ping.longitude,
            ping.accuracy_meters, ping.battery_pct,
            ping.status or "active", ping.notes, ts
        ))
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "worker_id": ping.worker_id,
            "timestamp": ts
        }


async def get_all_workers() -> List[Dict[str, Any]]:
    """Return the latest location for each worker."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT l.*
            FROM locations l
            INNER JOIN (
                SELECT worker_id, MAX(timestamp) AS max_ts
                FROM locations
                GROUP BY worker_id
            ) latest ON l.worker_id = latest.worker_id 
                     AND l.timestamp = latest.max_ts
            ORDER BY l.worker_name
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_worker_history(worker_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Return last N locations for a specific worker, newest first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM locations
            WHERE worker_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (worker_id, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
