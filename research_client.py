"""Authenticated client for the separate LeadHunter Research Worker."""
from __future__ import annotations
import os
import httpx
from typing import Any

class ResearchWorkerError(RuntimeError):
    pass

def _base() -> str:
    value = os.getenv("RESEARCH_WORKER_URL", "").strip().rstrip("/")
    if not value:
        raise ResearchWorkerError("RESEARCH_WORKER_URL is required")
    return value

def _headers() -> dict[str, str]:
    key = os.getenv("WORKER_API_KEY", "").strip()
    if not key:
        raise ResearchWorkerError("WORKER_API_KEY is required")
    return {"X-API-Key": key, "Authorization": f"Bearer {key}"}

async def research_business(business: dict[str, Any]) -> dict[str, Any]:
    base = _base()
    path = os.getenv("RESEARCH_WORKER_PATH", "/research").strip() or "/research"
    if not path.startswith("/"):
        path = "/" + path
    timeout = float(os.getenv("RESEARCH_WORKER_TIMEOUT", "90"))
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(base + path, json=business, headers=_headers())
    if response.status_code >= 400:
        raise ResearchWorkerError(f"Research Worker returned HTTP {response.status_code}: {response.text[:500]}")
    data = response.json()
    if isinstance(data, dict) and isinstance(data.get("research"), dict):
        return data["research"]
    if isinstance(data, dict):
        return data
    raise ResearchWorkerError("Research Worker returned an invalid response")

async def worker_status() -> dict[str, Any]:
    base = _base()
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(base + "/")
        response.raise_for_status()
        data = response.json() if "application/json" in response.headers.get("content-type", "") else {"status": "healthy"}
        return {"configured": True, "reachable": True, "response": data}
    except Exception as exc:
        return {"configured": True, "reachable": False, "error": f"{type(exc).__name__}: {exc}"}
