"""Authenticated client for the separate LeadHunter Research Worker v0.5.x."""
from __future__ import annotations

import os
from typing import Any

import httpx


class ResearchWorkerError(RuntimeError):
    """Raised when the Research Worker cannot complete a request."""


def _base() -> str:
    value = os.getenv("RESEARCH_WORKER_URL", "").strip().rstrip("/")
    if not value:
        raise ResearchWorkerError("RESEARCH_WORKER_URL is required")
    return value


def _headers() -> dict[str, str]:
    key = os.getenv("WORKER_API_KEY", "").strip()
    if not key:
        raise ResearchWorkerError("WORKER_API_KEY is required")
    return {"X-API-Key": key}


def _timeout() -> float:
    raw = os.getenv("RESEARCH_WORKER_TIMEOUT", "90").strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ResearchWorkerError("RESEARCH_WORKER_TIMEOUT must be a number") from exc
    return max(5.0, min(value, 300.0))


async def research_business(business: dict[str, Any]) -> dict[str, Any]:
    """Run SERP research through the deployed worker's /serp contract.

    The worker v0.5.1 API accepts a compact SERP request rather than a full
    business object. Normalize the main LeadHunter business into that contract.
    """
    base = _base()
    path = os.getenv("RESEARCH_WORKER_PATH", "/serp").strip() or "/serp"
    if not path.startswith("/"):
        path = "/" + path

    query = str(
        business.get("research_query")
        or business.get("requested_query")
        or f"{business.get('industry', '')} in {business.get('city', '')}"
    ).strip()
    if not query:
        raise ResearchWorkerError("Research query cannot be empty")

    payload = {
        "query": query[:300],
        "location": str(business.get("city") or "").strip() or None,
        "country": "in",
        "language": "en",
        "max_results": max(1, min(int(os.getenv("RESEARCH_WORKER_MAX_RESULTS", "10")), 50)),
    }

    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            response = await client.post(base + path, json=payload, headers=_headers())
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else ""
        raise ResearchWorkerError(
            f"Research Worker returned HTTP {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ResearchWorkerError(f"Research Worker request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise ResearchWorkerError("Research Worker returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise ResearchWorkerError("Research Worker returned an invalid response")

    # Preserve worker response intact under a stable envelope for LeadHunter.
    return {
        "research_status": "COMPLETE",
        "source": "leadhunter-research-worker",
        "worker_version": data.get("version") or "0.5.1",
        "serp": data.get("results") if isinstance(data.get("results"), list) else data.get("serp", data),
        "worker_response": data,
    }


async def worker_status() -> dict[str, Any]:
    """Read the public worker health endpoint without sending the API key."""
    base = _base()
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(base + "/health")
            response.raise_for_status()
            data = response.json()
        return {
            "configured": True,
            "reachable": True,
            "response": data,
        }
    except Exception as exc:
        return {
            "configured": True,
            "reachable": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
