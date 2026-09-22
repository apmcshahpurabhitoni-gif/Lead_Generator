import ast
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_main_has_single_root_and_health_routes():
    text=(ROOT/"main.py").read_text()
    assert '@app.get("/",' in text  # root redirect (decorator carries extra kwargs)
    assert '@app.get("/health")' in text
    assert '@app.head("/")' not in text  # root redirect only; no HEAD stub

def test_workflow_uses_worker_client():
    text=(ROOT/"lead_workflow.py").read_text()
    assert "from research_client import research_business" in text

def test_single_runtime_version_source_and_dashboard_router():
    tree=ast.parse((ROOT/"config.py").read_text())
    assert any(isinstance(n,ast.Assign) and any(getattr(t,"id","")=="APP_VERSION" for t in n.targets) for n in tree.body)
    text=(ROOT/"dashboard.py").read_text()
    assert "router = APIRouter()" in text
    assert '"/dashboard"' in text

def test_mobile_dashboard_routes_and_contract():
    text=(ROOT/"dashboard.py").read_text()
    assert '"/m"' in text and '"/dashboard/m"' in text
    mobile=(ROOT/"dashboard_ui"/"mobile.py").read_text()
    assert "/dashboard/api" in mobile
    # same public contract as the desktop dashboard — no invented endpoints
    for endpoint in ("/overview","/datasets","/leads/","/analytics","/outreach","/health","/discover","/jobs/"):
        assert endpoint in mobile

def test_migration_numbers_are_unique():
    names=[p.name.split("_",1)[0] for p in (ROOT/"migrations").glob("*.sql")]
    assert len(names)==len(set(names))
