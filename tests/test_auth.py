import os
import pytest
from auth import verify_credentials, validate_auth_config

def test_credentials(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER","admin"); monkeypatch.setenv("DASHBOARD_PASSWORD","secret")
    assert verify_credentials("admin","secret")
    assert not verify_credentials("admin","wrong")

def test_production_requires_auth(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT","production"); monkeypatch.setenv("DASHBOARD_AUTH_ENABLED","false")
    with pytest.raises(RuntimeError): validate_auth_config()

def test_auth_requires_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT","development"); monkeypatch.setenv("DASHBOARD_AUTH_ENABLED","true")
    monkeypatch.delenv("SESSION_SECRET",raising=False); monkeypatch.setenv("DASHBOARD_USER","a"); monkeypatch.setenv("DASHBOARD_PASSWORD","b")
    with pytest.raises(RuntimeError): validate_auth_config()
