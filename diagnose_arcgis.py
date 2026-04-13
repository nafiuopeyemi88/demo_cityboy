#!/usr/bin/env python3
"""
ArcGIS token diagnostic (generateToken version)

Usage:
    pip install httpx python-dotenv
    python diagnose_arcgis.py
"""

import asyncio
import httpx
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()


async def get_token(username, password):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            "https://www.arcgis.com/sharing/rest/generateToken",
            data={
                "username": username,
                "password": password,
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
        print("\n❌ Failed to get token — check username/password")
        return None, None

    expires = data.get("expires")  # milliseconds
    expires_at = time.time() + (expires / 1000 if expires else 0)

    print(f"\n✓ Token ({len(token)} chars): {token[:50]}...")
    print(f"✓ Expires at: {time.ctime(expires_at)}")

    return token, expires_at


async def test_query(layer_url, token):
    print("\n── 2. Test READ (query) ─")

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{layer_url}/query",
            params={"token": token, "f": "json"},
            data={
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "false",
                "resultRecordCount": "1",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    print(f"HTTP {r.status_code}")
    print(r.text[:500])


async def test_add_feature(layer_url, token):
    print("\n── 3. Test WRITE (addFeatures) ──────")

    feature = {
        "geometry": {
            "x": 7.4951,
            "y": 9.0579,
            "spatialReference": {"wkid": 4326},
        },
        "attributes": {
            "worker_id": "diag_test",
            "worker_name": "Diagnostic Test",
            "latitude": 9.0579,
            "longitude": 7.4951,
            "battery_pct": 99,
            "status": "active",
            "notes": "diagnostic test point",
            "last_updated": "2025-01-01T00:00:00Z",
        },
    }

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{layer_url}/addFeatures",
            params={"token": token, "f": "json"},
            data={"features": json.dumps([feature])},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    print(f"HTTP {r.status_code}")
    result = r.json()
    print(json.dumps(result, indent=2))

    if "error" in result:
        print(f"\n Write failed: {result['error']}")
        return None

    if result.get("addResults", [{}])[0].get("success"):
        oid = result["addResults"][0].get("objectId")
        print(f"\n✓ Write succeeded! ObjectID: {oid}")
        return oid

    return None


async def cleanup(layer_url, token, oid):
    print("\n── 4. Cleanup (deleteFeatures) ───────────")

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{layer_url}/deleteFeatures",
            params={"token": token, "f": "json"},
            data={"objectIds": str(oid)},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    print(f"HTTP {r.status_code}")
    print(r.text)


async def diagnose():
    username = os.getenv("ARCGIS_USERNAME") or input("Username: ").strip()
    password = os.getenv("ARCGIS_PASSWORD") or input("Password: ").strip()
    layer_url = os.getenv("ARCGIS_FEATURE_LAYER_URL") or input(
        "Feature Layer URL (/FeatureServer/0): "
    ).strip()

    print("\n── 1. Fetch token ─────────────────────────────────────")

    token, _ = await get_token(username, password)
    if not token:
        return

    await test_query(layer_url, token)

    oid = await test_add_feature(layer_url, token)

    if oid:
        await cleanup(layer_url, token, oid)


if __name__ == "__main__":
    asyncio.run(diagnose())