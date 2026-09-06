import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_main_has_single_root_and_health_routes():
    text = (ROOT / "main.py").read_text()
    assert text.count('@app.get("/")') == 1
    assert text.count('@app.get("/health")') == 1
    assert text.count('@app.head("/")') == 1

def test_workflow_uses_worker_client():
    text = (ROOT / "lead_workflow.py").read_text()
    assert 'from research_client import research_business' in text
    assert 'from research import research_business' not in text

def test_config_is_single_runtime_version_source():
    tree = ast.parse((ROOT / "config.py").read_text())
    assert any(isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "APP_VERSION" for t in n.targets) for n in tree.body)
    assert '__APP_VERSION__' in (ROOT / "dashboard.py").read_text()

def test_migration_numbers_are_unique():
    names = [p.name.split('_', 1)[0] for p in (ROOT / 'migrations').glob('*.sql')]
    assert len(names) == len(set(names))
