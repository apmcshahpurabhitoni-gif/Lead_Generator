from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,Field
from database import Database
from lead_workflow import run_discovery_job
from research_client import research_business
from research_schema import normalize_research
from scoring import score_lead
from ai import generate_whatsapp_message
import asyncio
router=APIRouter()
class SearchRequest(BaseModel):
    category:str=Field(min_length=1,max_length=100); city:str=Field(min_length=1,max_length=100); max_results:int=Field(default=20,ge=1,le=50); refresh:bool=False
class OutreachRequest(BaseModel): stage:str=Field(default="READY",max_length=30); notes:str=""; value:float|None=None; services:list[str]=[]
def db(r:Request)->Database:return r.app.state.db
@router.get("/health")
async def health(r:Request): return {"ok":True,"services":getattr(r.app.state,"service_status",{})}
@router.get("/overview")
async def overview(r:Request):
    d=db(r); leads=await d.list_leads(limit=1000); datasets=await d.list_searches(limit=100)
    researched=sum(1 for x in leads if x.get("score") is not None or x.get("status") in {"RESEARCHED","QUALIFIED"}); qualified=sum(1 for x in leads if x.get("status")=="QUALIFIED")
    return {"ok":True,"metrics":{"datasets":len(datasets),"leads":len(leads),"researched":researched,"ready":qualified},"recent":datasets[:5]}
@router.get("/datasets")
async def datasets(r:Request,limit:int=50): return {"ok":True,"items":await db(r).list_searches(limit=limit)}
@router.post("/discover")
async def discover(req:SearchRequest,r:Request):
    d=db(r); city=req.city.strip(); industry=req.category.strip(); existing=await d.list_searches(limit=100)
    match=next((x for x in existing if str(x.get("city","")).strip().lower()==city.lower() and str(x.get("industry","")).strip().lower()==industry.lower() and x.get("status")=="DONE"),None)
    if match and not req.refresh:return {"ok":True,"job_id":match["id"],"dataset_id":match["id"],"status":"DONE","reused":True}
    job_id=await d.create_job("DISCOVERY",city,industry)
    if not job_id: raise HTTPException(500,"Could not create discovery job")
    asyncio.create_task(run_discovery_job(job_id,city,industry,req.max_results)); return {"ok":True,"job_id":job_id,"dataset_id":job_id,"status":"RUNNING","reused":False}
@router.get("/jobs/{job_id}")
async def job(job_id:int,r:Request):
    item=await db(r).get_job(job_id)
    if not item: raise HTTPException(404,"Job not found")
    processed=int(item.get("processed") or 0);succeeded=int(item.get("succeeded") or 0);done=succeeded+int(item.get("failed") or 0);progress=100 if item.get("status") in {"DONE","FAILED"} else (min(95,round(done/max(processed,1)*100)) if processed else 5)
    return {"ok":True,"item":item,"progress":progress,"businesses_found":succeeded}
@router.get("/datasets/{search_id}/leads")
async def dataset_leads(search_id:int,r:Request,limit:int=100): return {"ok":True,"items":await db(r).list_search_results(search_id,limit=limit)}
@router.get("/leads/{lead_id}")
async def lead_detail(lead_id:int,r:Request):
    item=await db(r).get_lead(lead_id)
    if not item: raise HTTPException(404,"Lead not found")
    item["research"]=await db(r).get_research(lead_id);return {"ok":True,"item":item}
@router.post("/leads/{lead_id}/research")
async def research(lead_id:int,r:Request):
    d=db(r);lead=await d.get_lead(lead_id)
    if not lead:raise HTTPException(404,"Lead not found")
    try:
        raw=await research_business(lead);result=normalize_research(lead,raw);score=score_lead(result);result["score_breakdown"]=score.get("breakdown",[]);await d.save_research_and_score(lead_id,result,score);return {"ok":True,"research":result,"score":score}
    except Exception as e:raise HTTPException(502,f"Research failed: {type(e).__name__}: {str(e)[:300]}")
@router.post("/leads/{lead_id}/pitch")
async def pitch(lead_id:int,r:Request):
    d=db(r);lead=await d.get_lead(lead_id)
    if not lead:raise HTTPException(404,"Lead not found")
    research=await d.get_research(lead_id)
    try:message=await generate_whatsapp_message(lead,research)
    except Exception as e:raise HTTPException(502,f"Pitch generation failed: {type(e).__name__}")
    return {"ok":True,"pitch":message,"lead_id":lead_id}
@router.get("/analytics")
async def analytics(r:Request):return {"ok":True,**(await db(r).analytics())}
@router.get("/outreach")
async def outreach(r:Request):
    d=db(r);deals=await d.list_deals(limit=100);followups=await d.due_followups(limit=100);counts={}
    for x in deals:counts[x.get("stage") or "READY"]=counts.get(x.get("stage") or "READY",0)+1
    return {"ok":True,"counts":counts,"items":deals,"followups":followups}
@router.post("/outreach/{lead_id}")
async def save_outreach(lead_id:int,req:OutreachRequest,r:Request):
    d=db(r);lead=await d.get_lead(lead_id)
    if not lead:raise HTTPException(404,"Lead not found")
    did=await d.upsert_deal(lead_id,req.value,req.services,req.stage,req.notes);return {"ok":True,"deal_id":did}
