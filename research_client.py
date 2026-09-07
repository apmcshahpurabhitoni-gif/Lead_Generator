"""Authenticated LeadHunter Research Worker client."""
from __future__ import annotations
import os
from typing import Any
import httpx
class ResearchWorkerError(RuntimeError): pass
def configured()->bool:return bool(os.getenv("RESEARCH_WORKER_URL","").strip() and os.getenv("WORKER_API_KEY","").strip())
def _base()->str:
 v=os.getenv("RESEARCH_WORKER_URL","").strip().rstrip("/")
 if not v: raise ResearchWorkerError("RESEARCH_WORKER_URL is not configured")
 return v
def _headers()->dict[str,str]:
 k=os.getenv("WORKER_API_KEY","").strip()
 if not k: raise ResearchWorkerError("WORKER_API_KEY is not configured")
 return {"X-API-Key":k}
def _timeout()->float:
 try:return max(5,min(float(os.getenv("RESEARCH_WORKER_TIMEOUT","90")),300))
 except ValueError:raise ResearchWorkerError("RESEARCH_WORKER_TIMEOUT must be numeric")
async def research_business(business:dict[str,Any])->dict[str,Any]:
 if not configured(): return {}
 path=os.getenv("RESEARCH_WORKER_PATH","/serp").strip() or "/serp"; path=path if path.startswith("/") else "/"+path
 query=str(business.get("research_query") or business.get("requested_query") or f"{business.get('name','')} {business.get('city','')}").strip()
 if not query: raise ResearchWorkerError("Research query cannot be empty")
 payload={"query":query[:300],"location":str(business.get("city") or "").strip() or None,"country":"in","language":"en","max_results":max(1,min(int(os.getenv("RESEARCH_WORKER_MAX_RESULTS","10")),50))}
 try:
  async with httpx.AsyncClient(timeout=_timeout()) as c:r=await c.post(_base()+path,json=payload,headers=_headers());r.raise_for_status()
 except httpx.HTTPStatusError as e:raise ResearchWorkerError(f"Worker HTTP {e.response.status_code}: {e.response.text[:300]}") from e
 except httpx.HTTPError as e:raise ResearchWorkerError(f"Worker request failed: {e}") from e
 try:data=r.json()
 except ValueError as e:raise ResearchWorkerError("Worker returned invalid JSON") from e
 if not isinstance(data,dict):raise ResearchWorkerError("Worker returned invalid response")
 return {"source":"leadhunter-research-worker","worker_version":data.get("version") or "unknown","serp":data.get("results") or data.get("serp") or [],"worker_response":data}
async def worker_status()->dict[str,Any]:
 if not os.getenv("RESEARCH_WORKER_URL","").strip():return {"configured":False,"reachable":False}
 try:
  async with httpx.AsyncClient(timeout=8) as c:r=await c.get(_base()+"/health");r.raise_for_status();data=r.json()
  return {"configured":configured(),"reachable":True,"response":data}
 except Exception as e:return {"configured":configured(),"reachable":False,"error":f"{type(e).__name__}: {e}"}
