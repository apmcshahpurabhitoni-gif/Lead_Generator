import os
from datetime import date, datetime, timezone
import re
from typing import Any

from constants import PIPELINE_STATUSES, STATUS_RANK
from identity import domain, identity_key as canonical_identity_key, norm
from supabase import Client, create_client


class Database:
    def __init__(self) -> None:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")
        self.client: Client = create_client(url, key)

    @staticmethod
    def _norm(value: str | None) -> str:
        return norm(value)

    @staticmethod
    def _domain(website: str | None) -> str | None:
        return domain(website)

    @staticmethod
    def identity_key(name: str, city: str, website: str | None, **kwargs: Any) -> str:
        return canonical_identity_key(name, city, website, **kwargs)

    async def upsert_business(self, business: dict[str, Any]) -> tuple[int | None, bool]:
        identity = business.get("identity_key") or canonical_identity_key(
            business.get("name"),
            business.get("city"),
            business.get("website"),
            source_place_id=business.get("source_place_id"),
            phone=business.get("phone"),
            address=business.get("address"),
        )
        place_id = business.get("source_place_id")
        domain_name = domain(business.get("website"))
        phone_digits = re.sub(r"\D+", "", str(business.get("phone") or "")) or None
        name_norm = norm(business.get("name"))
        address_norm = norm(business.get("address") or business.get("city"))

        old = None
        if place_id:
            r = (
                self.client.table("businesses")
                .select("*")
                .eq("source_place_id", place_id)
                .limit(1)
                .execute()
            )
            old = r.data[0] if r.data else None
        if not old and domain_name:
            r = (
                self.client.table("businesses")
                .select("*")
                .eq("identity_key", "domain:" + domain_name)
                .limit(1)
                .execute()
            )
            old = r.data[0] if r.data else None
        if not old and business.get("website"):
            r = (
                self.client.table("businesses")
                .select("*")
                .eq("website", business.get("website"))
                .limit(1)
                .execute()
            )
            old = r.data[0] if r.data else None
        if not old and phone_digits:
            r = (
                self.client.table("businesses")
                .select("*")
                .eq("normalized_phone", phone_digits)
                .eq("city", business.get("city"))
                .limit(1)
                .execute()
            )
            old = r.data[0] if r.data else None
        if not old:
            r = (
                self.client.table("businesses")
                .select("*")
                .eq("identity_key", identity)
                .limit(1)
                .execute()
            )
            old = r.data[0] if r.data else None

        fields = [
            "name",
            "industry",
            "city",
            "website",
            "phone",
            "email",
            "source",
            "source_attribution",
            "source_place_id",
            "address",
        ]
        row = {k: business.get(k) for k in fields}
        row.update(
            {
                "identity_key": identity,
                "website_domain": domain_name,
                "normalized_phone": phone_digits,
                "normalized_name": name_norm,
                "normalized_address": address_norm,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        if old:
            for key in fields:
                if not row.get(key) and old.get(key):
                    row[key] = old[key]
            self.client.table("businesses").update(row).eq("id", old["id"]).execute()
            return int(old["id"]), False

        result = self.client.table("businesses").insert(row).execute()
        if not result.data:
            return None, False

        bid = int(result.data[0]["id"])
        await self.record_activity(
            bid, "DISCOVERED", "system", business.get("source", "unknown")
        )
        await self.increment_stats(leads_found=1)
        return bid, True

    async def save_research_and_score(
        self, bid: int, research: dict[str, Any], score: dict[str, Any]
    ) -> None:
        self.client.table("research").insert(
            {
                "business_id": bid,
                "research_json": research,
                "problems": research.get("problems", []),
            }
        ).execute()

        current = await self.get_lead(bid)
        current_status = (current or {}).get("status", "NEW")
        new_status = (
            "QUALIFIED" if int(score.get("score", 0)) >= 60 else "RESEARCHED"
        )

        if current_status not in PIPELINE_STATUSES or STATUS_RANK.get(
            new_status, 0
        ) > STATUS_RANK.get(current_status, 0):
            status = new_status
        else:
            status = current_status

        self.client.table("businesses").update(
            {
                "score": int(score.get("score", 0)),
                "priority": score.get("priority"),
                "recommended_services": score.get("recommended_services", []),
                "problems": score.get("reasons", []),
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", bid).execute()

        await self.record_activity(
            bid,
            "RESEARCHED",
            "system",
            f"Score={score.get('score', 0)}; Confidence={score.get('confidence', 0)}",
        )

    async def add_search_result(
        self, search_id: int | None, business_id: int | None, result_rank: int | None = None
    ) -> None:
        if not search_id or not business_id:
            return

        payload = {
            "search_id": int(search_id),
            "business_id": int(business_id),
            "result_rank": result_rank,
        }
        self.client.table("search_results").upsert(
            payload, on_conflict="search_id,business_id"
        ).execute()

    async def get_lead(self, bid: int) -> dict[str, Any] | None:
        r = (
            self.client.table("businesses")
            .select("*")
            .eq("id", bid)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    async def list_leads(
        self, priority: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        q = (
            self.client.table("businesses")
            .select("*")
            .order("score", desc=True)
            .range(offset, offset + limit - 1)
        )
        if priority:
            q = q.eq("priority", priority)
        r = q.execute()
        return r.data or []

    async def list_leads_with_research(
        self, priority: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        rows = await self.list_leads(priority, limit, offset)
        return await self._attach_research(rows)

    async def list_search_results(
        self, search_id: int, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))

        links = (
            self.client.table("search_results")
            .select("business_id,result_rank")
            .eq("search_id", int(search_id))
            .order("result_rank", desc=False, nullsfirst=False)
            .range(offset, offset + limit - 1)
            .execute()
            .data
            or []
        )

        ids = [int(x["business_id"]) for x in links if x.get("business_id") is not None]

        if ids:
            rank_by_id = {
                int(item["business_id"]): item.get("result_rank")
                for item in links
            }
            rows = (
                self.client.table("businesses")
                .select("*")
                .in_("id", ids)
                .execute()
                .data
                or []
            )

            # Supabase does not preserve the order of an IN() query. Restore the
            # original discovery order and expose it explicitly to the dashboard.
            rows.sort(
                key=lambda row: (
                    rank_by_id.get(int(row["id"])) is None,
                    rank_by_id.get(int(row["id"])) or 10**9,
                    -(int(row.get("score") or 0)),
                )
            )
            for row in rows:
                row["search_result_rank"] = rank_by_id.get(int(row["id"]))

            return await self._attach_research(rows)

        # Legacy databases may contain jobs created before search_results existed.
        search = await self.get_search(int(search_id))
        if not search or not search.get("city") or not search.get("industry"):
            return []

        rows = (
            self.client.table("businesses")
            .select("*")
            .eq("city", search["city"])
            .eq("industry", search["industry"])
            .order("score", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
            .data
            or []
        )
        return await self._attach_research(rows)

    async def _attach_research(
        self, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        ids = [int(x["id"]) for x in rows if x.get("id") is not None]
        if not ids:
            return rows

        items = (
            self.client.table("research")
            .select("business_id,research_json,created_at")
            .in_("business_id", ids)
            .order("created_at", desc=True)
            .limit(min(5000, max(100, len(ids) * 20)))
            .execute()
            .data
            or []
        )

        latest: dict[int, dict[str, Any]] = {}
        for item in items:
            latest.setdefault(
                int(item["business_id"]), item.get("research_json") or {}
            )

        for row in rows:
            row["research"] = latest.get(int(row["id"]), {})
        return rows

    async def list_searches(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        rows = (
            self.client.table("jobs")
            .select(
                "id,job_type,city,industry,status,started_at,finished_at,"
                "processed,succeeded,failed,error,created_at"
            )
            .eq("job_type", "DISCOVERY")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

        for row in rows:
            count = (
                self.client.table("search_results")
                .select("business_id", count="exact")
                .eq("search_id", row["id"])
                .execute()
            )
            row["result_count"] = int(count.count or 0)
            if not row["result_count"] and row.get("succeeded"):
                row["result_count"] = int(row["succeeded"] or 0)
        return rows

    async def get_search(self, search_id: int) -> dict[str, Any] | None:
        r = (
            self.client.table("jobs")
            .select(
                "id,job_type,city,industry,status,started_at,finished_at,"
                "processed,succeeded,failed,error,created_at"
            )
            .eq("id", int(search_id))
            .eq("job_type", "DISCOVERY")
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    async def get_job(self, job_id: int) -> dict[str, Any] | None:
        r = (
            self.client.table("jobs")
            .select("*")
            .eq("id", int(job_id))
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    async def get_research(self, bid: int) -> dict[str, Any]:
        r = (
            self.client.table("research")
            .select("research_json")
            .eq("business_id", bid)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return r.data[0]["research_json"] if r.data else {}

    async def set_status(self, bid: int, status: str) -> None:
        if status not in PIPELINE_STATUSES:
            raise ValueError(f"Invalid pipeline status: {status}")

        current = await self.get_lead(bid)
        if not current:
            raise ValueError("Lead not found")

        old_status = current.get("status") or "NEW"
        if (
            old_status in PIPELINE_STATUSES
            and STATUS_RANK.get(status, 0) < STATUS_RANK.get(old_status, 0)
        ):
            raise ValueError(
                f"Pipeline cannot move backwards from {old_status} to {status}"
            )

        self.client.table("businesses").update(
            {
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", bid).execute()

    async def record_activity(
        self, bid: int, action: str, channel: str, notes: str = ""
    ) -> None:
        self.client.table("activities").insert(
            {
                "business_id": bid,
                "action": action,
                "channel": channel,
                "notes": notes[:2000],
            }
        ).execute()

        mapping = {
            "CALL_COMPLETED": {"calls": 1},
            "STATUS_CONTACTED": {"contacted": 1},
            "STATUS_RESPONDED": {"replies": 1},
            "STATUS_MEETING": {"meetings": 1},
            "STATUS_PROPOSAL": {"proposals": 1},
            "STATUS_WON": {"won": 1},
            "STATUS_LOST": {"lost": 1},
            "DEAL_PROPOSAL": {"proposals": 1},
            "DEAL_WON": {"won": 1},
            "DEAL_LOST": {"lost": 1},
        }
        if action in mapping:
            await self.increment_stats(**mapping[action])

    async def activities(self, bid: int, limit: int = 30) -> list[dict[str, Any]]:
        r = (
            self.client.table("activities")
            .select("*")
            .eq("business_id", bid)
            .order("created_at", desc=True)
            .limit(min(int(limit), 100))
            .execute()
        )
        return r.data or []

    async def record_telegram_event(
        self, bid: int, event: str, message_id: int | None
    ) -> None:
        self.client.table("telegram_events").insert(
            {
                "business_id": bid,
                "event": event,
                "telegram_message_id": message_id,
            }
        ).execute()

    async def create_followup(
        self, bid: int, due_at: datetime, notes: str = ""
    ) -> None:
        self.client.table("followups").insert(
            {
                "business_id": bid,
                "due_at": due_at.astimezone(timezone.utc).isoformat(),
                "status": "OPEN",
                "notes": notes,
            }
        ).execute()

    async def due_followups(self, limit: int = 10) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        r = (
            self.client.table("followups")
            .select("id,business_id,due_at,notes,businesses(name)")
            .eq("status", "OPEN")
            .lte("due_at", now)
            .order("due_at")
            .limit(min(int(limit), 20))
            .execute()
        )
        return [
            {
                "id": x["id"],
                "business_id": x["business_id"],
                "business_name": (x.get("businesses") or {}).get(
                    "name", "Unknown"
                ),
                "due_at": x["due_at"],
                "notes": x.get("notes") or "",
            }
            for x in (r.data or [])
        ]

    async def create_job(
        self,
        job_type: str,
        city: str | None = None,
        industry: str | None = None,
    ) -> int | None:
        r = self.client.table("jobs").insert(
            {
                "job_type": job_type,
                "city": city,
                "industry": industry,
                "status": "RUNNING",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
        return int(r.data[0]["id"]) if r.data else None

    async def finish_job(
        self,
        jid: int,
        processed: int,
        succeeded: int,
        failed: int,
        error: str | None = None,
    ) -> None:
        self.client.table("jobs").update(
            {
                "status": "FAILED" if error else "DONE",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "processed": int(processed),
                "succeeded": int(succeeded),
                "failed": int(failed),
                "error": error,
            }
        ).eq("id", jid).execute()

    async def upsert_deal(
        self,
        bid: int,
        value: float | None,
        services: list[str],
        stage: str,
        notes: str = "",
    ) -> int | None:
        old = (
            self.client.table("deals")
            .select("id")
            .eq("business_id", bid)
            .eq("stage", stage)
            .limit(1)
            .execute()
        )
        row = {
            "business_id": bid,
            "value": value,
            "services": services,
            "stage": stage,
            "notes": notes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if stage == "WON":
            row["won_at"] = datetime.now(timezone.utc).isoformat()
        if stage == "LOST":
            row["lost_at"] = datetime.now(timezone.utc).isoformat()

        if old.data:
            r = (
                self.client.table("deals")
                .update(row)
                .eq("id", old.data[0]["id"])
                .execute()
            )
        else:
            r = self.client.table("deals").insert(row).execute()

        did = int(r.data[0]["id"]) if r.data else None
        if did:
            await self.record_activity(
                bid,
                f"DEAL_{stage}",
                "telegram",
                f"Value={value}; Services={', '.join(services)}",
            )
        return did

    async def list_deals(self, limit: int = 20) -> list[dict[str, Any]]:
        r = (
            self.client.table("deals")
            .select(
                "id,business_id,value,services,stage,notes,created_at,businesses(name)"
            )
            .order("updated_at", desc=True)
            .limit(min(int(limit), 50))
            .execute()
        )
        return [
            {
                "id": x["id"],
                "business_id": x["business_id"],
                "business_name": (x.get("businesses") or {}).get(
                    "name", "Unknown"
                ),
                "value": x.get("value"),
                "services": x.get("services") or [],
                "stage": x.get("stage"),
                "notes": x.get("notes") or "",
            }
            for x in (r.data or [])
        ]

    async def increment_stats(self, **inc: int) -> None:
        today = date.today().isoformat()
        r = (
            self.client.table("daily_stats")
            .select("*")
            .eq("date", today)
            .limit(1)
            .execute()
        )
        row = r.data[0] if r.data else {"date": today}
        allowed = {
            "leads_found",
            "qualified",
            "hot_leads",
            "calls",
            "contacted",
            "replies",
            "meetings",
            "proposals",
            "won",
            "lost",
        }
        for k, v in inc.items():
            if k in allowed:
                row[k] = int(row.get(k, 0) or 0) + int(v)
        self.client.table("daily_stats").upsert(
            row, on_conflict="date"
        ).execute()

    async def history(self, days: int = 14) -> list[dict[str, Any]]:
        r = (
            self.client.table("daily_stats")
            .select("*")
            .order("date", desc=True)
            .limit(min(int(days), 90))
            .execute()
        )
        return r.data or []

    async def today_stats(self) -> dict[str, int]:
        today = date.today().isoformat()
        r = (
            self.client.table("daily_stats")
            .select("*")
            .eq("date", today)
            .limit(1)
            .execute()
        )
        row = r.data[0] if r.data else {}
        fields = [
            "leads_found",
            "qualified",
            "hot_leads",
            "calls",
            "contacted",
            "replies",
            "meetings",
            "proposals",
            "won",
            "lost",
        ]
        return {f: int(row.get(f, 0) or 0) for f in fields}

    async def analytics(self) -> dict[str, Any]:
        rows = (
            self.client.table("businesses")
            .select(
                "id,status,priority,city,industry,recommended_services"
            )
            .limit(10000)
            .execute()
            .data
            or []
        )

        qualified_statuses = {
            "RESEARCHED",
            "QUALIFIED",
            "CONTACTED",
            "RESPONDED",
            "MEETING",
            "PROPOSAL",
            "NEGOTIATION",
            "WON",
        }
        contacted_statuses = {
            "CONTACTED",
            "RESPONDED",
            "MEETING",
            "PROPOSAL",
            "NEGOTIATION",
            "WON",
        }

        def exact_count(field: str | None = None, value: str | None = None) -> int:
            q = self.client.table("businesses").select("id", count="exact")
            if field:
                q = q.eq(field, value)
            return int(q.execute().count or 0)

        total = exact_count()
        qualified = sum(
            exact_count("status", status) for status in qualified_statuses
        )
        contacted = sum(
            exact_count("status", status) for status in contacted_statuses
        )
        won = exact_count("status", "WON")
        hot = exact_count("priority", "HOT")

        def counts(field: str) -> list[dict[str, Any]]:
            data: dict[str, int] = {}
            for row in rows:
                key = str(row.get(field) or "Unknown")
                data[key] = data.get(key, 0) + 1
            return [
                {"name": k, "count": v}
                for k, v in sorted(
                    data.items(), key=lambda x: x[1], reverse=True
                )[:8]
            ]

        services: dict[str, int] = {}
        for row in rows:
            for service in row.get("recommended_services") or []:
                key = str(service)
                services[key] = services.get(key, 0) + 1

        return {
            "totals": {
                "leads": total,
                "qualified": qualified,
                "contacted": contacted,
                "won": won,
                "hot": hot,
            },
            "conversion": {
                "qualified_rate": round(qualified / total * 100, 1)
                if total
                else 0,
                "contact_rate": round(contacted / total * 100, 1)
                if total
                else 0,
                "win_rate": round(won / contacted * 100, 1)
                if contacted
                else 0,
            },
            "cities": counts("city"),
            "industries": counts("industry"),
            "services": [
                {"name": k, "count": v}
                for k, v in sorted(
                    services.items(), key=lambda x: x[1], reverse=True
                )[:8]
            ],
        }

    @staticmethod
    def format_research(r: dict[str, Any]) -> str:
        if not r:
            return "No research available."

        lines = [str(p) for p in r.get("problems", [])[:12]]
        seo = r.get("seo", {})
        tech = r.get("technology", {}).get("signals", [])

        if seo:
            lines.append(f"SEO score: {seo.get('score', '—')}/100")
        if tech:
            lines.append("Technology: " + ", ".join(tech))

        lines.append(
            f"Pages researched: {len(r.get('website', {}).get('pages', []))}"
        )
        return "\n".join(lines) or "No major findings recorded."
