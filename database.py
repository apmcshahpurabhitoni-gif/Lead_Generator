import os
from datetime import date, datetime, timezone
from typing import Any
from supabase import Client, create_client

class Database:
    def __init__(self)->None:
        url=os.getenv("SUPABASE_URL","").strip(); key=os.getenv("SUPABASE_KEY","").strip()
        if not url or not key: raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")
        self.client: Client=create_client(url,key)
    @staticmethod
    def identity_key(name:str,city:str,website:str|None)->str:
        if website: return website.strip().lower().replace("https://","").replace("http://","").strip("/")
        return f"{name.strip().lower()}|{city.strip().lower()}"
    async def upsert_business(self,business:dict[str,Any])->tuple[int|None,bool]:
        identity=business.get("identity_key") or self.identity_key(business.get("name", ""),business.get("city", ""),business.get("website"))
        old=self.client.table("businesses").select("id").eq("identity_key",identity).limit(1).execute(); created=not bool(old.data)
        row={k:business.get(k) for k in ["name","industry","city","website","phone","email","source","source_attribution","source_place_id"]}; row["identity_key"]=identity
        result=self.client.table("businesses").upsert(row,on_conflict="identity_key").execute()
        if not result.data: return None,False
        bid=int(result.data[0]["id"])
        if created: await self.record_activity(bid,"DISCOVERED","system",business.get("source","unknown")); await self.increment_stats(leads_found=1)
        return bid,created
    async def save_research_and_score(self,bid:int,research:dict[str,Any],score:dict[str,Any])->None:
        self.client.table("research").insert({"business_id":bid,"research_json":research,"problems":research.get("problems",[])}).execute()
        self.client.table("businesses").update({"score":score["score"],"priority":score["priority"],"recommended_services":score["recommended_services"],"problems":score["reasons"],"status":"QUALIFIED" if score["score"]>=60 else "RESEARCHED","updated_at":datetime.now(timezone.utc).isoformat()}).eq("id",bid).execute()
        await self.record_activity(bid,"RESEARCHED","system",f"Score={score['score']}")
        if score["score"]>=60: await self.increment_stats(qualified=1)
        if score["priority"]=="HOT": await self.increment_stats(hot_leads=1)
    async def get_lead(self,bid:int)->dict[str,Any]|None:
        r=self.client.table("businesses").select("*").eq("id",bid).limit(1).execute(); return r.data[0] if r.data else None
    async def list_leads(self,priority:str|None=None,limit:int=10,offset:int=0)->list[dict[str,Any]]:
        limit=max(1,min(limit,50)); q=self.client.table("businesses").select("*").order("score",desc=True).range(offset,offset+limit-1)
        if priority: q=q.eq("priority",priority)
        r=q.execute(); return r.data or []
    async def list_search_results(self,city:str,industry:str,limit:int=8,offset:int=0)->list[dict[str,Any]]:
        limit=max(1,min(limit,50)); q=self.client.table("businesses").select("*").eq("city",city).eq("industry",industry).order("score",desc=True).range(offset,offset+limit-1); r=q.execute(); return r.data or []
    async def get_research(self,bid:int)->dict[str,Any]:
        r=self.client.table("research").select("research_json").eq("business_id",bid).order("created_at",desc=True).limit(1).execute(); return r.data[0]["research_json"] if r.data else {}
    async def set_status(self,bid:int,status:str)->None:
        self.client.table("businesses").update({"status":status,"updated_at":datetime.now(timezone.utc).isoformat()}).eq("id",bid).execute()
    async def record_activity(self,bid:int,action:str,channel:str,notes:str="")->None:
        self.client.table("activities").insert({"business_id":bid,"action":action,"channel":channel,"notes":notes[:2000]}).execute()
        mapping={"CALL_COMPLETED":{"calls":1},"STATUS_CONTACTED":{"contacted":1},"STATUS_RESPONDED":{"replies":1},"STATUS_MEETING":{"meetings":1},"STATUS_PROPOSAL":{"proposals":1},"STATUS_WON":{"won":1},"STATUS_LOST":{"lost":1},"DEAL_PROPOSAL":{"proposals":1},"DEAL_WON":{"won":1},"DEAL_LOST":{"lost":1}}
        if action in mapping: await self.increment_stats(**mapping[action])
    async def activities(self,bid:int,limit:int=30)->list[dict[str,Any]]:
        r=self.client.table("activities").select("*").eq("business_id",bid).order("created_at",desc=True).limit(min(limit,100)).execute(); return r.data or []
    async def record_telegram_event(self,bid:int,event:str,message_id:int|None)->None:
        self.client.table("telegram_events").insert({"business_id":bid,"event":event,"telegram_message_id":message_id}).execute()
    async def create_followup(self,bid:int,due_at:datetime,notes:str="")->None:
        self.client.table("followups").insert({"business_id":bid,"due_at":due_at.astimezone(timezone.utc).isoformat(),"status":"OPEN","notes":notes}).execute()
    async def due_followups(self,limit:int=10)->list[dict[str,Any]]:
        now=datetime.now(timezone.utc).isoformat(); r=self.client.table("followups").select("id,business_id,due_at,notes,businesses(name)").eq("status","OPEN").lte("due_at",now).order("due_at").limit(min(limit,20)).execute()
        return [{"id":x["id"],"business_id":x["business_id"],"business_name":(x.get("businesses") or {}).get("name","Unknown"),"due_at":x["due_at"],"notes":x.get("notes") or ""} for x in (r.data or [])]
    async def create_job(self,job_type:str,city:str|None=None,industry:str|None=None)->int|None:
        r=self.client.table("jobs").insert({"job_type":job_type,"city":city,"industry":industry,"status":"RUNNING","started_at":datetime.now(timezone.utc).isoformat()}).execute(); return int(r.data[0]["id"]) if r.data else None
    async def finish_job(self,jid:int,processed:int,succeeded:int,failed:int,error:str|None=None)->None:
        self.client.table("jobs").update({"status":"FAILED" if error else "DONE","finished_at":datetime.now(timezone.utc).isoformat(),"processed":processed,"succeeded":succeeded,"failed":failed,"error":error}).eq("id",jid).execute()
    async def upsert_deal(self,bid:int,value:float|None,services:list[str],stage:str,notes:str="")->int|None:
        old=self.client.table("deals").select("id").eq("business_id",bid).eq("stage",stage).limit(1).execute(); row={"business_id":bid,"value":value,"services":services,"stage":stage,"notes":notes,"updated_at":datetime.now(timezone.utc).isoformat()}
        if stage=="WON": row["won_at"]=datetime.now(timezone.utc).isoformat()
        if stage=="LOST": row["lost_at"]=datetime.now(timezone.utc).isoformat()
        r=self.client.table("deals").update(row).eq("id",old.data[0]["id"]).execute() if old.data else self.client.table("deals").insert(row).execute(); did=int(r.data[0]["id"]) if r.data else None
        if did: await self.record_activity(bid,f"DEAL_{stage}","telegram",f"Value={value}; Services={', '.join(services)}")
        return did
    async def list_deals(self,limit:int=20)->list[dict[str,Any]]:
        r=self.client.table("deals").select("id,business_id,value,services,stage,notes,created_at,businesses(name)").order("updated_at",desc=True).limit(min(limit,50)).execute()
        return [{"id":x["id"],"business_id":x["business_id"],"business_name":(x.get("businesses") or {}).get("name","Unknown"),"value":x.get("value"),"services":x.get("services") or [],"stage":x.get("stage"),"notes":x.get("notes") or ""} for x in (r.data or [])]
    async def increment_stats(self,**inc:int)->None:
        today=date.today().isoformat(); r=self.client.table("daily_stats").select("*").eq("date",today).limit(1).execute(); row=r.data[0] if r.data else {"date":today}; allowed={"leads_found","qualified","hot_leads","calls","contacted","replies","meetings","proposals","won","lost"}
        for k,v in inc.items():
            if k in allowed: row[k]=int(row.get(k,0) or 0)+int(v)
        self.client.table("daily_stats").upsert(row,on_conflict="date").execute()
    async def history(self,days:int=14)->list[dict[str,Any]]:
        r=self.client.table("daily_stats").select("*").order("date",desc=True).limit(min(days,90)).execute(); return r.data or []
    async def today_stats(self)->dict[str,int]:
        today=date.today().isoformat(); r=self.client.table("daily_stats").select("*").eq("date",today).limit(1).execute(); row=r.data[0] if r.data else {}; fields=["leads_found","qualified","hot_leads","calls","contacted","replies","meetings","proposals","won","lost"]; return {f:int(row.get(f,0) or 0) for f in fields}
    @staticmethod
    def format_research(r:dict[str,Any])->str:
        if not r: return "No research available."
        lines=[str(p) for p in r.get("problems",[])[:12]]; seo=r.get("seo",{}); tech=r.get("technology",{}).get("signals",[])
        if seo: lines.append(f"SEO score: {seo.get('score','—')}/100")
        if tech: lines.append("Technology: "+", ".join(tech))
        lines.append(f"Pages researched: {len(r.get('website',{}).get('pages',[]))}"); return "\n".join(lines) or "No major findings recorded."
