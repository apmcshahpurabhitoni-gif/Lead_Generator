import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from supabase import Client, create_client

class Database:
    def __init__(self) -> None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")
        self.client: Client = create_client(url, key)

    async def upsert_business(self, business: dict[str, Any]) -> int | None:
        identity = business.get("identity_key") or self.identity_key(
            business.get("name", ""), business.get("city", ""), business.get("website")
        )
        row = {
            "name": business.get("name"),
            "industry": business.get("industry"),
            "city": business.get("city"),
            "website": business.get("website"),
            "phone": business.get("phone"),
            "email": business.get("email"),
            "source": business.get("source"),
            "identity_key": identity,
        }
        result = self.client.table("businesses").upsert(row, on_conflict="identity_key").execute()
        return result.data[0]["id"] if result.data else None

    async def save_research_and_score(self, business_id: int, research: dict[str, Any], score: dict[str, Any]) -> None:
        self.client.table("research").insert({
            "business_id": business_id,
            "research_json": research,
            "problems": research.get("problems", []),
        }).execute()
        self.client.table("businesses").update({
            "score": score["score"],
            "priority": score["priority"],
            "recommended_services": score["recommended_services"],
            "problems": score["reasons"],
            "status": "QUALIFIED" if score["score"] >= 60 else "RESEARCHED",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", business_id).execute()
        await self.record_activity(business_id, "RESEARCHED", "system", f"Score={score['score']}")

    async def get_lead(self, business_id: int) -> dict[str, Any] | None:
        result = self.client.table("businesses").select("*").eq("id", business_id).limit(1).execute()
        return result.data[0] if result.data else None

    async def list_leads(self, priority: str | None = None, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        query = self.client.table("businesses").select("*").order("score", desc=True).range(offset, offset + max(1, limit) - 1)
        if priority:
            query = query.eq("priority", priority)
        result = query.execute()
        return result.data or []

    async def get_research(self, business_id: int) -> dict[str, Any]:
        result = self.client.table("research").select("research_json").eq("business_id", business_id).order("created_at", desc=True).limit(1).execute()
        return result.data[0]["research_json"] if result.data else {}

    async def set_status(self, business_id: int, status: str) -> None:
        self.client.table("businesses").update({
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", business_id).execute()

    async def record_activity(self, business_id: int, action: str, channel: str, notes: str = "") -> None:
        self.client.table("activities").insert({
            "business_id": business_id,
            "action": action,
            "channel": channel,
            "notes": notes,
        }).execute()

    async def record_telegram_event(self, business_id: int, event: str, telegram_message_id: int | None) -> None:
        self.client.table("telegram_events").insert({
            "business_id": business_id,
            "event": event,
            "telegram_message_id": telegram_message_id,
        }).execute()

    async def activities(self, business_id: int, limit: int = 30) -> list[dict[str, Any]]:
        result = self.client.table("activities").select("*").eq("business_id", business_id).order("created_at", desc=True).limit(limit).execute()
        return result.data or []

    async def create_followup(self, business_id: int, due_at: datetime, notes: str = "") -> None:
        self.client.table("followups").insert({
            "business_id": business_id,
            "due_at": due_at.astimezone(timezone.utc).isoformat(),
            "status": "OPEN",
            "notes": notes,
        }).execute()

    async def due_followups(self, limit: int = 10) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        result = self.client.table("followups").select("id,business_id,due_at,notes,businesses(name)").eq("status", "OPEN").lte("due_at", now).order("due_at").limit(limit).execute()
        rows = []
        for item in result.data or []:
            rows.append({
                "id": item["id"],
                "business_id": item["business_id"],
                "business_name": (item.get("businesses") or {}).get("name", "Unknown"),
                "due_at": item["due_at"],
                "notes": item.get("notes") or "",
            })
        return rows

    async def complete_followup(self, followup_id: int) -> None:
        self.client.table("followups").update({
            "status": "DONE",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", followup_id).execute()

    async def history(self, days: int = 14) -> list[dict[str, Any]]:
        result = self.client.table("daily_stats").select("*").order("date", desc=True).limit(days).execute()
        return result.data or []

    async def today_stats(self) -> dict[str, Any]:
        today = date.today().isoformat()
        result = self.client.table("daily_stats").select("*").eq("date", today).limit(1).execute()
        row = result.data[0] if result.data else {}
        fields = ["leads_found", "qualified", "hot_leads", "calls", "contacted", "replies", "meetings", "proposals", "won", "lost"]
        return {field: int(row.get(field, 0) or 0) for field in fields}

    @staticmethod
    def identity_key(name: str, city: str, website: str | None) -> str:
        if website:
            return website.strip().lower().replace("https://", "").replace("http://", "").strip("/")
        return f"{name.strip().lower()}|{city.strip().lower()}"
