from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from database import Database
from lead_workflow import run_discovery_job
from research_client import research_business
from scoring import score_lead
import asyncio

router = APIRouter()

class SearchRequest(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    max_results: int = Field(default=20, ge=1, le=50)

def db(request: Request) -> Database:
    return request.app.state.db

@router.get("/health")
async def health():
    return {"ok": True, "service": "leadhunter-dashboard-api"}

@router.get("/overview")
async def overview(request: Request):
    database = db(request)
    leads = await database.list_leads(limit=1000)
    searches = await database.list_searches(limit=100)
    researched = sum(1 for x in leads if x.get("status") in {"RESEARCHED","QUALIFIED"} or x.get("score") is not None)
    ready = sum(1 for x in leads if x.get("status") == "QUALIFIED")
    return {"ok": True, "metrics":{"datasets":len(searches),"leads":len(leads),"researched":researched,"ready":ready},
            "recent": searches[:5]}

@router.get("/datasets")
async def datasets(request: Request, limit: int = 50):
    return {"ok": True, "items": await db(request).list_searches(limit=limit)}

@router.post("/discover")
async def discover(req: SearchRequest, request: Request):
    database = db(request)
    job_id = await database.create_job("DISCOVERY", req.city.strip(), req.category.strip())
    if not job_id:
        raise HTTPException(500, "Could not create discovery job")
    asyncio.create_task(run_discovery_job(job_id, req.city.strip(), req.category.strip(), req.max_results))
    return {"ok": True, "job_id": job_id, "status": "RUNNING"}

@router.get("/datasets/{search_id}/leads")
async def dataset_leads(search_id: int, request: Request, limit: int = 100):
    return {"ok": True, "items": await db(request).list_search_results(search_id, limit=limit)}

@router.get("/leads")
async def leads(request: Request, search_id: int | None = None, limit: int = 100):
    database = db(request)
    items = await (database.list_search_results(search_id, limit=limit) if search_id else database.list_leads_with_research(limit=limit))
    return {"ok": True, "items": items}

@router.get("/leads/{lead_id}")
async def lead_detail(lead_id: int, request: Request):
    item = await db(request).get_lead(lead_id)
    if not item: raise HTTPException(404, "Lead not found")
    item["research"] = await db(request).get_research(lead_id)
    return {"ok": True, "item": item}

@router.post("/leads/{lead_id}/research")
async def research(lead_id: int, request: Request):
    database = db(request)
    lead = await database.get_lead(lead_id)
    if not lead: raise HTTPException(404, "Lead not found")
    try:
        result = await research_business(lead)
        score = score_lead(result)
        result["score_breakdown"] = score.get("breakdown", [])
        await database.save_research_and_score(lead_id, result, score)
        return {"ok": True, "research": result, "score": score}
    except Exception as exc:
        raise HTTPException(502, f"Research failed: {type(exc).__name__}: {str(exc)[:300]}")

@router.post("/leads/{lead_id}/pitch")
async def pitch(lead_id: int, request: Request):
    lead = await db(request).get_lead(lead_id)
    if not lead: raise HTTPException(404, "Lead not found")
    raise HTTPException(501, "Pitch generation is not implemented in the canonical backend yet")

@router.get("/analytics")
async def analytics(request: Request):
    leads = await db(request).list_leads(limit=1000)
    pipeline = {}
    priorities = {}
    for lead in leads:
        pipeline[lead.get("status") or "NEW"] = pipeline.get(lead.get("status") or "NEW", 0) + 1
        priorities[lead.get("priority") or "UNSCORED"] = priorities.get(lead.get("priority") or "UNSCORED", 0) + 1
    return {"ok": True, "pipeline": pipeline, "priorities": priorities,
            "coverage":{"total":len(leads),"researched":sum(1 for x in leads if x.get("score") is not None)}}
