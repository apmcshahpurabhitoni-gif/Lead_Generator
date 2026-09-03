"""Canonical lead identity and normalization helpers."""
import re
from urllib.parse import urlparse

def norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())

def domain(website: str | None) -> str | None:
    if not website:
        return None
    value = str(website).strip()
    if not value.startswith(("http://","https://")):
        value="https://"+value
    host=urlparse(value).netloc.lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host or None

def identity_key(name: str, city: str, website: str | None, *,
                source_place_id: str | None = None, phone: str | None = None,
                address: str | None = None) -> str:
    if source_place_id:
        return "place:"+norm(source_place_id)
    d=domain(website)
    if d:
        return "domain:"+d
    digits=re.sub(r"\D+","",str(phone or ""))
    if digits:
        return f"phone:{digits}|{norm(city)}"
    return f"name:{norm(name)}|{norm(address or city)}"
