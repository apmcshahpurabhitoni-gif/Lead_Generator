import asyncio, logging, os, time
from collections import defaultdict, deque
from typing import Any
from urllib.parse import urlparse
import httpx

log = logging.getLogger(__name__)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = ["https://overpass.private.coffee/api/interpreter", "https://overpass-api.de/api/interpreter", "https://overpass.osm.jp/api/interpreter"]
USER_AGENT = "LeadHunter/1.0 (business research; contact: LeadHunter operator)"
POLICIES = {
    "nominatim": {"rpm": 50, "daily": 500, "delay": 1.1, "retries": 1},
    "overpass": {"rpm": 6, "daily": 100, "delay": 10.0, "retries": 1},
    "website": {"rpm": 12, "daily": 500, "delay": 1.0, "retries": 1},
}
_usage: dict[str, deque[float]] = defaultdict(deque)
_daily: dict[str, tuple[str, int]] = {}
_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_city_cache: dict[str, tuple[int, str]] = {}

INDUSTRY_TAGS = {
    "dental": [("amenity", "dentist")], "dentist": [("amenity", "dentist")], "hospital": [("amenity", "hospital")], "clinic": [("amenity", "clinic")],
    "restaurant": [("amenity", "restaurant")], "cafe": [("amenity", "cafe")], "bakery": [("shop", "bakery")], "hotel": [("tourism", "hotel")], "resort": [("tourism", "resort")],
    "school": [("amenity", "school")], "college": [("amenity", "college")], "university": [("amenity", "university")], "pharmacy": [("amenity", "pharmacy")], "gym": [("leisure", "fitness_centre")],
    "salon": [("shop", "hairdresser")], "beauty": [("shop", "beauty")], "car dealer": [("shop", "car")], "car repair": [("shop", "car_repair")], "car wash": [("amenity", "car_wash")],
    "real estate": [("office", "estate_agent")], "lawyer": [("office", "lawyer")], "accountant": [("office", "accountant")], "travel agency": [("shop", "travel_agency")],
    "electronics": [("shop", "electronics")], "clothing": [("shop", "clothes")], "furniture": [("shop", "furniture")], "jewellery": [("shop", "jewelry")], "jewelry": [("shop", "jewelry")],
    "supermarket": [("shop", "supermarket")], "hardware": [("shop", "hardware")], "bank": [("amenity", "bank")], "insurance": [("office", "insurance")], "architect": [("office", "architect")],
    "construction": [("office", "construction_company")], "printing": [("shop", "printing")], "photographer": [("shop", "photo")], "fuel": [("amenity", "fuel")], "veterinary": [("amenity", "veterinary")],
}
ALL_TAGS = [("amenity", x) for x in ["dentist","hospital","clinic","restaurant","cafe","pharmacy","school","college","university","bank","veterinary","car_wash","fuel"]] + [("shop", x) for x in ["bakery","hairdresser","beauty","car","car_repair","electronics","clothes","furniture","jewelry","supermarket","hardware","printing","photo","travel_agency"]] + [("tourism", x) for x in ["hotel","resort"]] + [("office", x) for x in ["estate_agent","lawyer","accountant","insurance","architect","construction_company"]]

def _day() -> str: return time.strftime("%Y-%m-%d", time.gmtime())

async def _budget(source: str) -> None:
    policy = POLICIES[source]
    async with _locks[source]:
        now = time.monotonic(); q = _usage[source]
        while q and now - q[0] >= 60: q.popleft()
        day, count = _daily.get(source, (_day(), 0))
        if day != _day(): day, count = _day(), 0
        if count >= policy["daily"]: raise RuntimeError(f"{source} daily safety budget reached")
        if q and len(q) >= policy["rpm"]: await asyncio.sleep(max(0.5, 60 - (now - q[0])))
        if q:
            elapsed = time.monotonic() - q[-1]
            if elapsed < policy["delay"]: await asyncio.sleep(policy["delay"] - elapsed)
        q.append(time.monotonic()); _daily[source] = (day, count + 1)

def _timeout(seconds: float) -> httpx.Timeout: return httpx.Timeout(seconds, connect=min(8.0, seconds))

async def request(source: str, method: str, url: str, *, timeout: float = 20, **kwargs: Any) -> httpx.Response:
    """Shared HTTP request helper used by discovery and research."""
    if source not in POLICIES: raise ValueError(f"Unknown request source: {source}")
    await _budget(source)
    headers = {"User-Agent": USER_AGENT, **(kwargs.pop("headers", {}) or {})}
    referer = kwargs.pop("referer", None)
    if referer: headers["Referer"] = referer
    last: Exception | None = None
    for attempt in range(POLICIES[source]["retries"] + 1):
        try:
            async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=_timeout(timeout)) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status(); return response
        except Exception as exc:
            last = exc; log.warning("%s request failed | attempt=%s | %s | %s", source, attempt + 1, url, exc)
            if attempt < POLICIES[source]["retries"]: await asyncio.sleep(min(10.0, 2 ** attempt))
    raise last or RuntimeError("request failed")

async def _city_area(city: str) -> tuple[int, str]:
    key = city.strip().lower()
    if key in _city_cache: return _city_cache[key]
    rows = (await request("nominatim", "GET", NOMINATIM_URL, params={"q": f"{city}, India", "format": "jsonv2", "limit": 1, "countrycodes": "in"}, timeout=15, referer=os.getenv("WEBHOOK_BASE_URL"))).json()
    if not rows: raise RuntimeError(f"Could not locate city in India: {city}")
    row = rows[0]; osm_type = row.get("osm_type"); osm_id = int(row["osm_id"])
    if osm_type == "relation": area_id = 3600000000 + osm_id
    elif osm_type == "way": area_id = 2400000000 + osm_id
    else: raise RuntimeError(f"City '{city}' resolved to a point. Try another spelling.")
    result = (area_id, row.get("display_name", city)); _city_cache[key] = result; return result

def _filters(industry: str) -> str:
    key = industry.strip().lower(); tags = ALL_TAGS if key in {"all", "business", "businesses"} else INDUSTRY_TAGS.get(key)
    if tags: return "".join(f'node["{k}"="{v}"](area.searchArea);way["{k}"="{v}"](area.searchArea);relation["{k}"="{v}"](area.searchArea);' for k,v in tags)
    safe = "".join(c for c in key if c.isalnum() or c in " _-")[:50]
    return f'node["name"~"{safe}",i](area.searchArea);way["name"~"{safe}",i](area.searchArea);relation["name"~"{safe}",i](area.searchArea);'

async def _overpass(query: str) -> httpx.Response:
    errors=[]
    for url in OVERPASS_URLS:
        try: return await request("overpass", "POST", url, data=query, timeout=35)
        except Exception as exc: errors.append(f"{url}: {type(exc).__name__}: {exc}")
    raise RuntimeError("All discovery connections failed. Please retry in a moment. " + " | ".join(errors)[-1200:])

def normalize_website(url: str | None) -> str | None:
    if not url: return None
    value=url.strip()
    if not value: return None
    if not value.startswith(("http://","https://")): value="https://"+value
    p=urlparse(value)
    return f"{p.scheme}://{p.netloc}".rstrip("/") if p.netloc else None

async def discover_businesses(city: str, industry: str, limit: int = 50) -> list[dict[str,Any]]:
    city=city.strip(); industry=industry.strip()
    if not city: raise ValueError("City is required")
    if not industry: raise ValueError("Business type is required")
    area_id,resolved_city=await _city_area(city); safe_limit=max(1,min(int(limit),50))
    query=f"[out:json][timeout:25];area({area_id})->.searchArea;({_filters(industry)});out center tags;"
    elements=(await _overpass(query)).json().get("elements",[])[:safe_limit]
    results=[]; seen=set()
    for item in elements:
        tags=item.get("tags") or {}; name=(tags.get("name") or "").strip()
        if not name: continue
        website=normalize_website(tags.get("website") or tags.get("contact:website")); identity=website or f"{name.lower()}|{city.lower()}"
        if identity in seen: continue
        seen.add(identity)
        results.append({"name":name,"industry":industry,"city":city,"website":website,"phone":tags.get("phone") or tags.get("contact:phone"),"email":tags.get("email") or tags.get("contact:email"),"source":"openstreetmap_overpass","source_attribution":"© OpenStreetMap contributors","source_place_id":f"osm:{item.get('type')}:{item.get('id')}","resolved_city":resolved_city})
    log.info("Discovery complete | city=%s | industry=%s | results=%s",city,industry,len(results)); return results
