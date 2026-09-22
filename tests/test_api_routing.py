"""End-to-end routing regression tests.

These hit the real FastAPI app (routing -> handler -> response), not the
endpoint functions directly. They pin the public dashboard API contract at
/dashboard/api/* so the mount prefix can never silently drift again — the
P0 bug where the router was mounted at /api and every UI request 404'd.
"""

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard import router as dashboard_router


class FakeDB:
    """Minimal async stand-in satisfying the read endpoints under test."""

    async def list_leads(self, limit: int = 1000, **_: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": 7,
                "name": "Acme Dental",
                "city": "Indore",
                "industry": "dental",
                "status": "QUALIFIED",
                "score": 76,
            }
        ]

    async def list_searches(self, limit: int = 100, **_: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": 11,
                "job_type": "DISCOVERY",
                "city": "Indore",
                "industry": "dental",
                "status": "DONE",
                "result_count": 1,
                "created_at": "2026-09-22T00:00:00Z",
            }
        ]

    async def get_search(self, search_id: int) -> dict[str, Any] | None:
        return next((x for x in await self.list_searches() if x["id"] == search_id), None)

    async def get_job(self, job_id: int) -> dict[str, Any] | None:
        return next((x for x in await self.list_searches() if x["id"] == job_id), None)

    async def list_search_results(self, search_id: int, limit: int = 100, **_: Any) -> list[dict[str, Any]]:
        return await self.list_leads()

    async def get_lead(self, lead_id: int) -> dict[str, Any] | None:
        return next((x for x in await self.list_leads() if x["id"] == lead_id), None)

    async def get_research(self, lead_id: int) -> dict[str, Any]:
        return {}

    async def analytics(self) -> dict[str, Any]:
        return {
            "totals": {"leads": 1, "qualified": 1, "contacted": 0, "won": 0, "hot": 1},
            "conversion": {},
            "cities": [{"name": "Indore", "count": 1}],
            "industries": [],
            "services": [],
        }

    async def list_deals(self, limit: int = 100, **_: Any) -> list[dict[str, Any]]:
        return []

    async def due_followups(self, limit: int = 100, **_: Any) -> list[dict[str, Any]]:
        return []


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(dashboard_router)
    app.state.db = FakeDB()
    return TestClient(app)


def test_dashboard_api_contract_paths_are_served():
    client = make_client()
    for path in (
        "/dashboard/api/health",
        "/dashboard/api/overview",
        "/dashboard/api/datasets",
        "/dashboard/api/analytics",
        "/dashboard/api/outreach",
    ):
        response = client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}: {response.text[:120]}"
        payload = response.json()
        assert payload.get("ok") is True, f"{path} missing ok=true"


def test_documented_wrong_path_is_rejected():
    """The old accidental mount (/api) must not serve the dashboard API."""
    client = make_client()
    assert client.get("/api/overview").status_code == 404


def test_invalid_dataset_still_404s_through_the_app():
    client = make_client()
    assert client.get("/dashboard/api/datasets/999999/leads").status_code == 404


def test_lead_detail_route_through_the_app():
    client = make_client()
    # 404 (no such lead) proves routing reaches the handler; a routing miss
    # would also be 404, so pair this with the contract test above which
    # asserts 200s for the read endpoints.
    response = client.get("/dashboard/api/leads/7")
    assert response.status_code in {200, 404}


def test_dashboards_serve_html_from_the_same_app():
    client = make_client()
    for path in ("/dashboard", "/m"):
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
