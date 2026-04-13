"""
ArcGIS Online Integration
Pushes location pings to a hosted Feature Layer via the ArcGIS REST API.

Auth: OAuth 2.0 "For app authentication" (client_credentials grant).
Token is passed as a URL query parameter (?token=...) which is what
ArcGIS hosted Feature Layers require to avoid 498 errors.
"""

import httpx
import json
import logging
import os
from datetime import datetime, timezone, timedelta
import time
from typing import Optional

from .models import LocationPing

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
ARCGIS_TOKEN_URL     = "https://www.arcgis.com/sharing/rest/oauth2/token"
ARCGIS_CLIENT_ID     = os.getenv("ARCGIS_CLIENT_ID", "")
ARCGIS_CLIENT_SECRET = os.getenv("ARCGIS_CLIENT_SECRET", "")
ARCGIS_FEATURE_LAYER_URL = os.getenv("ARCGIS_FEATURE_LAYER_URL", "")
ARCGIS_USERNAME = os.getenv("ARCGIS_USERNAME", "")
ARCGIS_PASSWORD = os.getenv("ARCGIS_PASSWORD", "")


# ── Token cache ────────────────────────────────────────────────────────────────
_token: Optional[str] = None
_token_expires: Optional[datetime] = None


# async def get_arcgis_token() -> Optional[str]:
#     """
#     Fetch (or return cached) ArcGIS OAuth2 access token.
#     Requires 'For app authentication' credential type from developers.arcgis.com.
#     """
#     global _token, _token_expires

#     if not ARCGIS_CLIENT_ID or not ARCGIS_CLIENT_SECRET:
#         logger.warning("ArcGIS credentials not configured — skipping push")
#         return None

#     now = datetime.now(timezone.utc)
#     if _token and _token_expires and now < _token_expires:
#         return _token

#     _token = None
#     logger.info("Fetching new ArcGIS token...")

#     async with httpx.AsyncClient(timeout=15) as client:
#         resp = await client.post(
#             ARCGIS_TOKEN_URL,
#             data={
#                 "client_id":     ARCGIS_CLIENT_ID,
#                 "client_secret": ARCGIS_CLIENT_SECRET,
#                 "grant_type":    "client_credentials",
#                 "f":             "json",
#             },
#             headers={"Content-Type": "application/x-www-form-urlencoded"},
#         )

#     logger.debug("Token response %d: %s", resp.status_code, resp.text[:300])

#     if resp.status_code != 200:
#         logger.error("Token request failed HTTP %d: %s", resp.status_code, resp.text)
#         return None

#     data = resp.json()
#     if "access_token" not in data:
#         logger.error("No access_token in response: %s", data)
#         return None

#     _token = data["access_token"]
#     expires_in = data.get("expires_in", 7200)
#     _token_expires = now + timedelta(seconds=expires_in - 120)
#     logger.info("ArcGIS token acquired, valid for %ds", expires_in)
#     return _token

async def get_arcgis_token():
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            "https://www.arcgis.com/sharing/rest/generateToken",
            data={
                "username": ARCGIS_USERNAME,
                "password": ARCGIS_PASSWORD,
                "referer": "https://www.arcgis.com",
                "expiration": 60,  # minutes (adjust if needed)
                "f": "json",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    print(f"HTTP {r.status_code}")
    data = r.json()
    print(json.dumps(data, indent=2))

    token = data.get("token")  # 
    if not token:
        print("\n Failed to get token — check username/password")
        return None, None

    expires = data.get("expires")  # milliseconds
    expires_at = time.time() + (expires / 1000 if expires else 0)

    print(f"\n Token ({len(token)} chars): {token[:50]}...")
    print(f" Expires at: {time.ctime(expires_at)}")

    return token

async def push_to_arcgis(ping: LocationPing):
    """
    Upsert worker position in the ArcGIS hosted Feature Layer.
    One feature per worker = current position on the map.
    Token is sent as a URL query param — required to avoid 498 errors.
    """
    if not ARCGIS_FEATURE_LAYER_URL:
        logger.debug("ARCGIS_FEATURE_LAYER_URL not set — skipping")
        return

    token = await get_arcgis_token()
    if not token:
        return

    feature = {
        "geometry": {
            "x": ping.longitude,
            "y": ping.latitude,
            "spatialReference": {"wkid": 4326},
        },
        "attributes": {
            "worker_id":    ping.worker_id,
            "worker_name":  ping.worker_name,
            "latitude":     ping.latitude,
            "longitude":    ping.longitude,
            "battery_pct":  ping.battery_pct if ping.battery_pct is not None else -1,
            "status":       ping.status or "active",
            "notes":        ping.notes or "",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
    }

    existing_oid = await _find_existing_feature(ping.worker_id, token)

    if existing_oid:
        feature["attributes"]["objectid"] = existing_oid
        form_key = "updates"
        action = "update"
    else:
        form_key = "adds"
        action = "add"

    
    url = f"{ARCGIS_FEATURE_LAYER_URL}/applyEdits"
    params = {"token": token, "f": "json"}
    form_data = {form_key: json.dumps([feature])}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            params=params,
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    logger.debug("applyEdits response %d: %s", resp.status_code, resp.text[:500])

    if resp.status_code != 200:
        logger.error("applyEdits HTTP %d: %s", resp.status_code, resp.text[:300])
        return

    result = resp.json()

    if "error" in result:
        logger.error("ArcGIS %s error for %s: %s", action, ping.worker_id, result["error"])
        return

    key = "updateResults" if action == "update" else "addResults"
    results = result.get(key, [])
    if results and results[0].get("success"):
        oid = results[0].get("objectId") or existing_oid
        logger.info("ArcGIS %s OK — %s (OID %s)", action, ping.worker_id, oid)
    else:
        logger.error("ArcGIS %s failed for %s: %s", action, ping.worker_id, result)


async def _find_existing_feature(worker_id: str, token: str) -> Optional[int]:
    """Query the feature layer for an existing feature with this worker_id."""
    url = f"{ARCGIS_FEATURE_LAYER_URL}/query"
    params = {"token": token, "f": "json"}
    form_data = {
        "where":          f"worker_id='{worker_id}'",
        "outFields":      "objectid,OBJECTID",
        "returnGeometry": "false",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            params=params,
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        logger.warning("Query HTTP %d for %s", resp.status_code, worker_id)
        return None

    data = resp.json()
    if "error" in data:
        logger.warning("Query error for %s: %s", worker_id, data["error"])
        return None

    features = data.get("features", [])
    if features:
        attrs = features[0]["attributes"]
        return attrs.get("objectid") or attrs.get("OBJECTID") or attrs.get("ObjectID")
    return None


async def add_location_history(ping: LocationPing):
    """
    Push to a SEPARATE history layer — one feature per ping (full trail).
    Set ARCGIS_HISTORY_LAYER_URL in .env to activate.
    """
    history_url = os.getenv("ARCGIS_HISTORY_LAYER_URL", "")
    if not history_url:
        return

    token = await get_arcgis_token()
    if not token:
        return

    feature = {
        "geometry": {
            "x": ping.longitude,
            "y": ping.latitude,
            "spatialReference": {"wkid": 4326},
        },
        "attributes": {
            "worker_id":   ping.worker_id,
            "worker_name": ping.worker_name,
            "battery_pct": ping.battery_pct if ping.battery_pct is not None else -1,
            "status":      ping.status or "active",
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        },
    }

    url = f"{history_url}/addFeatures"
    params = {"token": token, "f": "json"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            params=params,
            data={"features": json.dumps([feature])},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    result = resp.json()
    if "error" in result:
        logger.error("History layer add failed: %s", result["error"])
    else:
        logger.info("History point added for %s", ping.worker_id)
