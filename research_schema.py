"""Canonical future-ready research contract for LeadHunter.

Each module always reports one explicit state:
AVAILABLE, NOT_FOUND, NOT_CONFIGURED or FAILED.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
AVAILABLE="AVAILABLE"; NOT_FOUND="NOT_FOUND"; NOT_CONFIGURED="NOT_CONFIGURED"; FAILED="FAILED"

def module(status:str=NOT_CONFIGURED, data:dict|None=None, message:str|None=None)->dict:
    out={"status":status}
    if message: out["message"]=message
    if data: out.update(data)
    return out

def _serp(raw:Any)->list[dict]:
    if isinstance(raw,list): return [x for x in raw if isinstance(x,dict)]
    if isinstance(raw,dict):
        for k in ("results","organic","items","serp"):
            if isinstance(raw.get(k),list): return [x for x in raw[k] if isinstance(x,dict)]
    return []

def normalize_research(business:dict[str,Any], worker:dict[str,Any]|None=None)->dict[str,Any]:
    """Convert discovery + current/future worker responses into one stable schema."""
    worker=worker or {}
    raw=worker.get("worker_response") if isinstance(worker,dict) else {}
    serp=_serp(raw or worker.get("serp") or [])
    website_url=str(business.get("website") or "").strip()
    rating=business.get("google_rating")
    reviews=business.get("google_review_count")
    maps_url=business.get("google_maps_url")
    phone=str(business.get("phone") or "").strip()
    email=str(business.get("email") or "").strip()

    website=module(AVAILABLE if website_url else NOT_FOUND,
        {"exists":bool(website_url),"url":website_url or None} if website_url else {"exists":False},
        None if website_url else "No official website was found in available discovery sources.")
    google_exists=bool(maps_url or rating is not None or reviews is not None)
    google=module(AVAILABLE if google_exists else NOT_FOUND,{
        "exists":google_exists,"rating":rating,"review_count":reviews,"maps_url":maps_url,
        "local_rank":business.get("google_local_rank"),"provider_rank":business.get("google_provider_rank"),
        "match_confidence":business.get("google_match_confidence"),"types":business.get("google_types") or []
    },None if google_exists else "No Google Business data was found in available discovery sources.")

    future=lambda label: module(NOT_CONFIGURED,{},f"{label} data source is not connected yet.")
    result={
      "research_status":"COMPLETE" if worker else "PARTIAL",
      "industry":business.get("industry") or business.get("requested_industry"),
      "website":website,
      "google":google,
      "reviews":future("Review intelligence"),
      "search":module(AVAILABLE,{"query":business.get("research_query") or business.get("requested_query"),"serp_results":serp,"result_count":len(serp)}) if worker else future("Search intelligence"),
      "maps":future("Google Maps ranking"),
      "organic_ranking":future("Google organic ranking"),
      "competitors":future("Competitor intelligence"),
      "keywords":future("Keyword intelligence"),
      "social":future("Social intelligence"),
      "seo":future("Website SEO audit"),
      "local":module(AVAILABLE,{"phone_found":bool(phone),"email_found":bool(email)}),
      "profiles":{},
      "problems":[],
      "opportunities":[],
      "buying_signals":[],
      "intelligence":module(AVAILABLE,{"summary":""}),
      "meta":{"contract_version":"1.0","sources_used":["discovery"]+(["research_worker"] if worker else []),
              "sources_missing":["organic_ranking","maps_ranking","review_intelligence","competitor_intelligence","keyword_intelligence","social_intelligence"],
              "researched_at":datetime.now(timezone.utc).isoformat(),
              "worker_version":worker.get("worker_version") if worker else None}
    }
    if not website_url: result["problems"].append("No verified official website was found from available discovery sources.")
    if not phone: result["problems"].append("No public business phone was found in the researched sources.")
    if not email: result["problems"].append("No public business email was found in the researched sources.")
    if not website_url: result["opportunities"].append("Websites")
    if google_exists: result["opportunities"].append("Google Business Profile")
    return result
