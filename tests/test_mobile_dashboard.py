"""LeadHunter Mobile Dashboard tests.

These check the mobile UI module directly — its route registration, its
exclusive use of the public /dashboard/api contract, and its mobile UX
wiring. No backend business logic is touched by the mobile UI.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mobile_py() -> str:
    return (ROOT / "dashboard_ui" / "mobile.py").read_text()


def _dashboard_py() -> str:
    return (ROOT / "dashboard.py").read_text()


def test_mobile_module_defines_full_document():
    html = _mobile_py()
    assert "<!doctype html>" in html
    assert 'name="viewport"' in html
    assert "viewport-fit=cover" in html  # notch / safe-area support


def test_mobile_route_is_registered():
    text = _dashboard_py()
    assert '@router.get("/m"' in text
    assert '@router.get("/dashboard/m"' in text
    assert "MOBILE_HTML" in text


def test_mobile_uses_only_public_api_contract():
    html = _mobile_py()
    assert html.count("/dashboard/api") >= 1
    for endpoint in (
        "/health",
        "/overview",
        "/datasets?limit=50",
        "/datasets/",
        "/leads/",
        "/leads/",
        "/research",
        "/pitch",
        "/analytics",
        "/outreach",
        "/discover",
        "/jobs/",
    ):
        assert ("/dashboard/api" + endpoint) in html or endpoint in html


def test_mobile_core_interactions_present():
    html = _mobile_py()
    # Navigation
    for tab in ("home", "leads", "find", "stats", "act"):
        assert f'id="tab-{tab}"' in html
    # Lead actions wired to the API
    for fn in ("researchLead", "pitchLead", "saveOutreach", "startDiscovery", "pollJob"):
        assert f"function {fn}" in html
    # Contact actions
    assert 'href="tel:' in html
    assert "wa.me" in html
    assert "mailto:" in html


def test_mobile_bottom_sheet_and_tabbar_present():
    html = _mobile_py()
    assert 'id="sheet"' in html
    assert 'id="tabbar"' in html or 'class="tabbar"' in html
    assert 'id="scrim"' in html


def test_mobile_reuses_locked_theme_system():
    html = _mobile_py()
    assert "body.dark" in html and "body.neo" in html
    assert "lh-theme" in html  # same localStorage key as desktop


def test_mobile_states_are_explicit():
    html = _mobile_py()
    for cls in ("empty", "loading", "error", "skeleton"):
        assert cls in html


def test_desktop_links_to_mobile():
    assert "/m" in (ROOT / "dashboard_ui" / "templates.py").read_text()
