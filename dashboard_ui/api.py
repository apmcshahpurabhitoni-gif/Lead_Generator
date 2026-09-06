from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
import os, importlib, asyncio

router = APIRouter()

class SearchRequest(BaseModel):
    category: str
    city: str
    state: Optional[str] = None
    country: str = "IN"
    max_results: int = 20

def _load(name):
    try:
        return importlib.import_module(name)
    except Exception:
        return None

@router.get("/health")
async def health():
    return {"ok": True, "service": "leadhunter-dashboard-api"}

@router.get("/overview")
async def overview():
    # Safe baseline. Replace/extend with database aggregation when available.
    return {"ok": True, "metrics": {"datasets": 0, "leads": 0, "researched": 0, "ready": 0},
            "recent": []}

@router.get("/datasets")
async def datasets():
    db = _load("database")
    if db:
        for fn in ("get_datasets", "list_datasets", "get_search_groups"):
            f = getattr(db, fn, None)
            if callable(f):
                try:
                    return {"ok": True, "items": f()}
                except Exception:
                    pass
    return {"ok": True, "items": []}

@router.post("/discover")
async def discover(req: SearchRequest):
    # Adapter: use existing discovery/workflow without hard-coding provider schema.
    mod = _load("lead_workflow") or _load("discovery")
    if not mod:
        raise HTTPException(503, "Discovery module unavailable")
    payload = req.model_dump()
    for fn in ("discover_leads", "search_leads", "run_discovery", "discover"):
        f = getattr(mod, fn, None)
        if callable(f):
            result = f(payload)
            if asyncio.iscoroutine(result):
                result = await result
            return {"ok": True, "result": result}
    raise HTTPException(503, "No supported discovery entry point found")

@router.get("/leads")
async def leads(dataset: Optional[str] = None):
    db = _load("database")
    if db:
        for fn in ("get_leads", "list_leads", "get_dataset_leads"):
            f = getattr(db, fn, None)
            if callable(f):
                try:
                    result = f(dataset) if dataset else f()
                    return {"ok": True, "items": result}
                except TypeError:
                    try: return {"ok": True, "items": f()}
                    except Exception: pass
                except Exception: pass
    return {"ok": True, "items": []}

@router.post("/leads/{lead_id}/research")
async def research(lead_id: str):
    mod = _load("research_client") or _load("lead_workflow")
    if not mod:
        raise HTTPException(503, "Research service unavailable")
    for fn in ("research_lead", "research_business", "run_research"):
        f = getattr(mod, fn, None)
        if callable(f):
            result = f(lead_id)
            if asyncio.iscoroutine(result): result = await result
            return {"ok": True, "result": result}
    raise HTTPException(503, "Research entry point unavailable")

@router.post("/leads/{lead_id}/pitch")
async def pitch(lead_id: str):
    mod = _load("lead_workflow")
    if mod:
        for fn in ("generate_pitch", "create_pitch"):
            f = getattr(mod, fn, None)
            if callable(f):
                result = f(lead_id)
                if asyncio.iscoroutine(result): result = await result
                return {"ok": True, "result": result}
    raise HTTPException(503, "Pitch service unavailable")

@router.get("/analytics")
async def analytics():
    return {"ok": True, "coverage": {}, "opportunities": {}, "pipeline": {}}
