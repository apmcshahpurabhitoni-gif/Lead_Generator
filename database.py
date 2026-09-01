import os
from datetime import date, datetime, timezone
from typing import Any

from supabase import Client, create_client


class Database:
    def __init__(self) -> None:
        url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
        if not url or not key: raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")
        self.client: Client = create_client(url, key)

    async def upsert_business(self, business: dict[str, Any]) -> tuple[int | None, bool]:
        identity = business.get("identity_key") or self.identity_key(business.get("name", ""), business.get("city", ""), business.get("website"))
        existing = self.client.table("businesses").select("id").eq("identity_key", identity).limit(1).execute()
        created = not bool(existing.data)
        row = {"name": business.get("name"), "industry": business.get("industry"), "city": business.get("city"), "website": business.get("website"), "phone": business.get("phone"), "email": business.get("email"), "source": business.get("source"), "source_attribution": business.get("source_attribution"), "source_place_id": business.get("source_place_id"), "identity_key": identity}
        result = self.client.table("businesses").upsert(row, on_conflict="identity_key").execute()
        if not result.data: return None, False
        bid = int(result.data[0]["id"])
        if created:
            await self.record_activity(bid, "DISCOVERED", "system", business.get("source", "unknown")); await self.increment_stats(leads_found=1)
        return bid, created

    async def save_research_and_score(self, business_id: int, research: dict[str, Any], score: dict[str, Any]) -> None:
        self.client.table("research").insert({"business_id": business_id, "research_json": research, "problems": research.get("problems", [])}).execute()
        self.client.table("businesses").update({"score": score["score"], "priority": score["priority"], "recommended_services": score["recommended_services"], "problems": score["reasons"], "status": "QUALIFIED" if score["score"] >= 60 else "RESEARCHED", "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", business_id).execute()
        await self.record_activity(business_id, "RESEARCHED", "system", f"Score={score['score']}")
        if score["score"] >= 60: await self.increment_stats(qualified=1)
        if score["priority"] == "HOT": await self.increment_stats(hot_leads=1)

    async def get_lead(self, business_id: int) -> dict[str, Any] | None:
        result = self.client.table("businesses").select("*").eq("id", business_id).limit(1).execute(); return result.data[0] if result.data else None

    async def list_leads(self, priority: str | None = None, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 50)); query = self.client.table("businesses").select("*").order("score", desc=True).range(offset, offset + limit - 1)
        if priority: query = query.eq("priority", priority)
        result = query.execute(); return result.data or []

    async def get_research(self, business_id: int) -> dict[str, Any]:
        result = self.client.table("research").select("research_json").eq("business_id", business_id).order("created_at", desc=True).limit(1).execute(); return result.data[0]["research_json"] if result.data else {}

    async def set_status(self, business_id: int, status: str) -> None:
        self.client.table("businesses").update({"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", business_id).execute()

    async def record_activity(self, business_id: int, action: str, channel: str, notes: str = "") -> None:
        self.client.table("activities").insert({"business_id": business_id, "action": action, "channel": channel, "notes": notes[:2000]}).execute()
        mapping = {"STATUS_CONTACTED": {"contacted": 1}, "STATUS_RESPONDED": {"replies": 1}, "STATUS_MEETING": {"meetings": 1}, "STATUS_PROPOSAL": {"proposals": 1}, "STATUS_WON": {"won": 1}, "STATUS_LOST": {"lost": 1}, "CALL_COMPLETED": {"calls": 1}, "DEAL_PROPOSAL": {"proposals": 1}, "DEAL_WON": {"won": 1}, "DEAL_LOST": {"lost": 1}}
        if action in mapping: await self.increment_stats(**mapping[action])

    async def record_telegram_event(self, business_id: int, event: str, telegram_message_id: int | None) -> None:
        self.client.table("telegram_events").insert({"business_id": business_id, "event": event, "telegram_message_id": telegram_message_id}).execute()

    async def activities(self, business_id: int, limit: int = 30) -> list[dict[str, Any]]:
        result = self.client.table("activities").select("*").eq("business_id", business_id).order("created_at", desc=True).limit(min(limit, 100)).execute(); return result.data or []

    async def create_followup(self, business_id: int, due_at: datetime, notes: str = "") -> None:
        self.client.table("followups").insert({"business_id": business_id, "due_at": due_at.astimezone(timezone.utc).isoformat(), "status": "OPEN", "notes": notes}).execute()

    async def due_followups(self, limit: int = 10) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat(); result = self.client.table("followups").select("id,business_id,due_at,notes,businesses(name)").eq("status", "OPEN").lte("due_at", now).order("due_at").limit(min(limit, 20)).execute()
        return [{"id": x["id"], "business_id": x["business_id"], "business_name": (x.get("businesses") or {}).get("name", "Unknown"), "due_at": x["due_at"], "notes": x.get("notes") or ""} for x in (result.data or [])]

    async def create_job(self, job_type: str, city: str | None = None, industry: str | None = None) -> int | None:
        result = self.client.table("jobs").insert({"job_type": job_type, "city": city, "industry": industry, "status": "RUNNING", "started_at": datetime.now(timezone.utc).isoformat()}).execute(); return int(result.data[0]["id"]) if result.data else None

    async def finish_job(self, job_id: int, processed: int, succeeded: int, failed: int, error: str | None = None) -> None:
        self.client.table("jobs").update({"status": "FAILED" if error else "DONE", "finished_at": datetime.now(timezone.utc).isoformat(), "processed": processed, "succeeded": succeeded, "failed": failed, "error": error}).eq("id", job_id).execute()

    async def upsert_deal(self, business_id: int, value: float | None, services: list[str], stage: str, notes: str = "") -> int | None:
        existing = self.client.table("deals").select("id").eq("business_id", business_id).eq("stage", stage).limit(1).execute()
        row: dict[str, Any] = {"business_id": business_id, "value": value, "services": services, "stage": stage, "notes": notes, "updated_at": datetime.now(timezone.utc).isoformat()}
        if stage == "WON": row["won_at"] = datetime.now(timezone.utc).isoformat()
        if stage == "LOST": row["lost_at"] = datetime.now(timezone.utc).isoformat()
        result = self.client.table("deals").update(row).eq("id", existing.data[0]["id"]).execute() if existing.data else self.client.table("deals").insert(row).execute()
        deal_id = int(result.data[0]["id"]) if result.data else None
        if deal_id: await self.record_activity(business_id, f"DEAL_{stage}", "telegram", f"Value={value}; Services={', '.join(services)}")
        return deal_id

    async def increment_stats(self, **increments: int) -> None:
        today = date.today().isoformat(); result = self.client.table("daily_stats").select("*").eq("date", today).limit(1).execute(); row = result.data[0] if result.data else {"date": today}
        allowed = {"leads_found", "qualified", "hot_leads", "calls", "contacted", "replies", "meetings", "proposals", "won", "lost"}
        for key, value in increments.items():
            if key in allowed: row[key] = int(row.get(key, 0) or 0) + int(value)
        self.client.table("daily_stats").upsert(row, on_conflict="date").execute()

    async def history(self, days: int = 14) -> list[dict[str, Any]]:
        result = self.client.table("daily_stats").select("*").order("date", desc=True).limit(min(days, 90)).execute(); return result.data or []

    async def today_stats(self) -> dict[str, Any]:
        today = date.today().isoformat(); result = self.client.table("daily_stats").select("*").eq("date", today).limit(1).execute(); row = result.data[0] if result.data else {}
        fields = ["leads_found", "qualified", "hot_leads", "calls", "contacted", "replies", "meetings", "proposals", "won", "lost"]
        return {field: int(row.get(field, 0) or 0) for field in fields}

    @staticmethod
    def identity_key(name: str, city: str, website: str | None) -> str:
        if website: return website.strip().lower().replace("https://", "").replace("http://", "").strip("/")
        return f"{name.strip().lower()}|{city.strip().lower()}"

    @staticmethod
    def format_research(research: dict[str, Any]) -> str:
        if not research: return "No research available."
        lines = [f"🔴 {p}" for p in research.get("problems", [])[:12]]; seo = research.get("seo", {})
        if seo: lines.append(f"🔎 SEO score: {seo.get('score', '—')}/100")
        tech = research.get("technology", {}).get("signals", [])
        if tech: lines.append(f"💻 Technology: {', '.join(tech)}")
        lines.append(f"🌐 Pages researched: {len(research.get('website', {}).get('pages', []))}")
        return "\n".join(lines) or "No major findings recorded."
