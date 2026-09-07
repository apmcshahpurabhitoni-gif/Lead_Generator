"""Canonical discovery -> normalization -> scoring -> persistence workflow."""
import logging
from database import Database
from discovery import discover_businesses
from research_client import research_business
from research_schema import normalize_research
from scoring import score_lead
log=logging.getLogger(__name__)
async def process_candidates(db,job_id,candidates,industry,city):
 saved=failed=0
 for candidate in candidates:
  try:
   candidate["requested_industry"]=industry;candidate["requested_city"]=city
   raw=await research_business(candidate)
   research=normalize_research(candidate,raw)
   score=score_lead(research);research["score_breakdown"]=score.get("breakdown",[])
   bid,_=await db.upsert_business(candidate)
   if not bid:failed+=1;continue
   await db.save_research_and_score(bid,research,score)
   await db.add_search_result(job_id,bid,candidate.get("google_provider_rank") or candidate.get("google_local_rank"))
   saved+=1
  except Exception:
   failed+=1;log.exception("lead processing failed | city=%s industry=%s",city,industry)
 return saved,failed
async def run_discovery_job(job_id,city,industry,limit):
 db=Database();processed=saved=failed=0
 try:
  candidates=await discover_businesses(city,industry,max(1,min(int(limit),50)))
  processed=len(candidates);saved,failed=await process_candidates(db,job_id,candidates,industry,city)
  await db.finish_job(job_id,processed,saved,failed)
 except Exception as e:
  log.exception("discovery job failed");await db.finish_job(job_id,processed,saved,max(failed,1),str(e)[:1000])
