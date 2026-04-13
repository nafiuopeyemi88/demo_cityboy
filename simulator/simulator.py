#!/usr/bin/env python3
"""
Field Worker Location Simulator
================================
Simulates N workers moving around a city and POSTing GPS pings
to your the backend at a configurable interval.

Usage:
    python simulator.py                         # defaults (5 workers, Abuja, 10s interval)
    python simulator.py --workers 8             # 8 workers
    python simulator.py --interval 600          # 10-minute real interval
    python simulator.py --city lagos            # use Lagos coords
    python simulator.py --api http://localhost:8000

Workers move semi-realistically: they travel toward a random waypoint,
slow down, pick a new one. Battery drains over time.
"""

import asyncio
import httpx
import random
import argparse
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

####################City centres & bounding boxes 
CITIES = {
    "abuja": {
        "center": (9.0579, 7.4951),
        "bbox":   (8.95, 7.38, 9.15, 7.60),   # (lat_min, lon_min, lat_max, lon_max)
    },
    "lagos": {
        "center": (6.5244, 3.3792),
        "bbox":   (6.43, 3.27, 6.63, 3.49),
    },
    "kano": {
        "center": (12.0022, 8.5920),
        "bbox":   (11.92, 8.48, 12.08, 8.70),
    },
    "port_harcourt": {
        "center": (4.8156, 7.0498),
        "bbox":   (4.73, 6.96, 4.90, 7.14),
    },
}

WORKER_NAMES = [
    "Aminu Bello", "Fatima Usman", "Chukwuemeka Obi", "Ngozi Adeyemi",
    "Musa Ibrahim", "Aisha Garba", "Tunde Adebayo", "Blessing Nwosu",
    "Yakubu Sule", "Chidinma Eze", "Abdullahi Danbatta", "Grace Okonkwo",
    "Uche Nnamdi", "Halima Kwara", "Emeka Okafor", "Stella Obi",
]

STATUSES = ["active", "active", "active", "idle", "active"]  # weighted


@dataclass
class SimWorker:
    worker_id: str
    worker_name: str
    lat: float
    lon: float
    battery: int = field(default_factory=lambda: random.randint(60, 100))
    status: str = "active"
    waypoint: Tuple[float, float] = None
    steps_to_waypoint: int = 0

    def pick_waypoint(self, bbox):
        lat_min, lon_min, lat_max, lon_max = bbox
        self.waypoint = (
            random.uniform(lat_min, lat_max),
            random.uniform(lon_min, lon_max),
        )
        self.steps_to_waypoint = random.randint(3, 12)

    def move(self, bbox):
        """Take one step toward current waypoint, then maybe pick a new one."""
        if not self.waypoint or self.steps_to_waypoint <= 0:
            self.pick_waypoint(bbox)

        # Step a small fraction toward waypoint
        fraction = 1.0 / max(self.steps_to_waypoint, 1)
        d_lat = (self.waypoint[0] - self.lat) * fraction
        d_lon = (self.waypoint[1] - self.lon) * fraction

        # Add a tiny jitter (GPS noise)
        self.lat += d_lat + random.gauss(0, 0.0002)
        self.lon += d_lon + random.gauss(0, 0.0002)
        self.steps_to_waypoint -= 1

        # Drain battery slowly
        if random.random() < 0.15:
            self.battery = max(5, self.battery - random.randint(1, 3))

        # Occasionally go idle
        self.status = random.choices(
            ["active", "idle"], weights=[85, 15]
        )[0]


async def post_location(client: httpx.AsyncClient, api_url: str, worker: SimWorker):
    payload = {
        "worker_id":        worker.worker_id,
        "worker_name":      worker.worker_name,
        "latitude":         round(worker.lat, 6),
        "longitude":        round(worker.lon, 6),
        "accuracy_meters":  round(random.uniform(3, 15), 1),
        "battery_pct":      worker.battery,
        "status":           worker.status,
        "notes":            "",
    }
    try:
        resp = await client.post(f"{api_url}/location", json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(
            "✓ %-20s  lat=%.5f  lon=%.5f  bat=%d%%  [%s]",
            worker.worker_name, worker.lat, worker.lon,
            worker.battery, worker.status
        )
    except httpx.HTTPStatusError as e:
        logger.error("HTTP %d for %s: %s", e.response.status_code, worker.worker_id, e.response.text)
    except httpx.RequestError as e:
        logger.error("Request failed for %s: %s", worker.worker_id, e)


async def run_simulation(
    api_url: str,
    n_workers: int,
    interval_seconds: int,
    city: str,
    max_rounds: int = 0,
):
    city_cfg = CITIES.get(city.lower(), CITIES["abuja"])
    bbox = city_cfg["bbox"]
    center_lat, center_lon = city_cfg["center"]

    # Initialise workers near the city centre
    names = random.sample(WORKER_NAMES, min(n_workers, len(WORKER_NAMES)))
    workers: List[SimWorker] = []
    for i, name in enumerate(names):
        workers.append(SimWorker(
            worker_id=f"worker_{i+1:03d}",
            worker_name=name,
            lat=center_lat + random.uniform(-0.03, 0.03),
            lon=center_lon + random.uniform(-0.03, 0.03),
        ))

    logger.info(
        "Simulator started — %d workers in %s | interval=%ds | API=%s",
        n_workers, city.title(), interval_seconds, api_url
    )
    logger.info("Press Ctrl+C to stop\n")

    round_num = 0
    async with httpx.AsyncClient() as client:
        while True:
            round_num += 1
            logger.info("─── Round %d  (%s UTC) ───────────────────",
                        round_num, datetime.now(timezone.utc).strftime("%H:%M:%S"))

            tasks = []
            for w in workers:
                w.move(bbox)
                tasks.append(post_location(client, api_url, w))

            await asyncio.gather(*tasks)

            if max_rounds and round_num >= max_rounds:
                logger.info("Reached max rounds (%d). Stopping.", max_rounds)
                break

            logger.info("Sleeping %ds until next ping...\n", interval_seconds)
            await asyncio.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description="Field worker GPS simulator")
    parser.add_argument("--api",      default="http://localhost:8000", help="FastAPI base URL")
    parser.add_argument("--workers",  type=int, default=5,   help="Number of workers to simulate")
    parser.add_argument("--interval", type=int, default=10,  help="Seconds between pings (use 600 for real 10-min)")
    parser.add_argument("--city",     default="abuja",       help="City: abuja|lagos|kano|port_harcourt")
    parser.add_argument("--rounds",   type=int, default=0,   help="Stop after N rounds (0 = run forever)")
    args = parser.parse_args()

    asyncio.run(run_simulation(
        api_url=args.api,
        n_workers=args.workers,
        interval_seconds=args.interval,
        city=args.city,
        max_rounds=args.rounds,
    ))


if __name__ == "__main__":
    main()
