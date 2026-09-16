from types import SimpleNamespace

import pytest

from dashboard_ui.api import analytics, dataset_leads, outreach


class FakeDB:
    def __init__(self):
        self.leads = {
            7: {
                "id": 7,
                "name": "Acme Dental",
                "city": "Indore",
                "industry": "dental",
                "website": "https://example.com",
                "phone": "9999999999",
                "email": "hello@example.com",
            }
        }

    async def analytics(self):
        return {
            "totals": {"leads": 12, "qualified": 5, "contacted": 3, "won": 1, "hot": 2},
            "conversion": {},
            "cities": [{"name": "Indore", "count": 12}],
            "industries": [],
            "services": [{"name": "SEO", "count": 4}],
        }

    async def get_search(self, search_id):
        return {"id": search_id, "job_type": "DISCOVERY"} if search_id == 11 else None

    async def list_search_results(self, search_id, limit=100):
        return [{"id": 7, "name": "Acme Dental", "city": "Indore"}]

    async def list_deals(self, limit=100):
        return [
            {
                "id": 3,
                "business_id": 7,
                "business_name": "Acme Dental",
                "stage": "READY",
                "services": ["SEO"],
                "notes": "Call this week",
            }
        ]

    async def due_followups(self, limit=100):
        return []

    async def get_lead(self, lead_id):
        return self.leads.get(lead_id)


@pytest.fixture
def request_with_db():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=FakeDB())))


@pytest.mark.asyncio
async def test_analytics_exposes_flat_ui_contract(request_with_db):
    result = await analytics(request_with_db)
    assert result["leads"] == 12
    assert result["qualified"] == 5
    assert result["hot"] == 2
    assert result["contacted"] == 3
    assert result["cities"][0]["name"] == "Indore"


@pytest.mark.asyncio
async def test_invalid_dataset_is_not_silently_treated_as_empty(request_with_db):
    with pytest.raises(Exception) as exc:
        await dataset_leads(999, request_with_db)
    assert getattr(exc.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_outreach_returns_real_lead_context(request_with_db):
    result = await outreach(request_with_db)
    item = result["items"][0]
    assert item["business_id"] == 7
    assert item["name"] == "Acme Dental"
    assert item["city"] == "Indore"
    assert item["industry"] == "dental"
    assert result["counts"] == {"READY": 1}
