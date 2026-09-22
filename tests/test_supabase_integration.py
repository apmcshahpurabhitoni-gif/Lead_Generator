"""Supabase credential resolution tests.

The integration accepts every canonical Supabase key name so the app boots
from either the Keys tab contract (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY /
SUPABASE_ANON_KEY) or the legacy SUPABASE_KEY alias.
"""

import pytest

from database import supabase_credentials, supabase_project_ref, supabase_url


def test_service_role_key_wins_over_anon_and_legacy(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("SUPABASE_KEY", "legacy")
    assert supabase_credentials() == ("https://ref.supabase.co", "service")


def test_anon_key_beats_legacy_alias(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("SUPABASE_KEY", "legacy")
    assert supabase_credentials() == ("https://ref.supabase.co", "anon")


def test_legacy_alias_still_works(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_KEY", "legacy")
    assert supabase_credentials() == ("https://ref.supabase.co", "legacy")


def test_missing_key_raises_actionable_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://ref.supabase.co")
    for name in ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY", "SUPABASE_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError) as exc:
        supabase_credentials()
    assert "SUPABASE_SERVICE_ROLE_KEY" in str(exc.value)


def test_missing_url_raises_actionable_error(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    with pytest.raises(RuntimeError) as exc:
        supabase_credentials()
    assert "SUPABASE_URL" in str(exc.value)


def test_next_public_url_is_accepted(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://alt.supabase.co/")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    assert supabase_credentials() == ("https://alt.supabase.co", "anon")
    assert supabase_url() == "https://alt.supabase.co"


def test_project_ref_is_extracted_for_diagnostics(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://qwtptifskzwjokotysms.supabase.co")
    assert supabase_project_ref() == "qwtptifskzwjokotysms"
    assert supabase_project_ref("https://other.supabase.co") == "other"
    assert supabase_project_ref("https://example.com") is None
