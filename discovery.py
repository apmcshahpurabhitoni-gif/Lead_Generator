import asyncio, logging, os, time
from collections import defaultdict, deque
from typing import Any
from urllib.parse import urlparse
import httpx

log = logging.getLogger(__name__)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
# OSM remains a no-cost fallback when Google Places is not configured or unavailable.
OVERPASS_URLS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "LeadHunter/3.2 (business research; Google Places + OSM discovery)"
POLICIES = {
    "nominatim": {"rpm": 50, "daily": 500, "delay": 1.1, "retries": 0},
    "overpass": {"rpm": 6, "daily": 100, "delay": 10.0, "retries": 0},
    "website": {"rpm": 12, "daily": 500, "delay": 1.0, "retries": 1},
    "google": {"rpm": 30, "daily": 100, "delay": 0.2, "retries": 1},
}
_usage: dict[str, deque[float]] = defaultdict(deque)
_daily: dict[str, tuple[str, int]] = {}
_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_city_cache: dict[str, tuple[int, str]] = {}

INDUSTRY_TAGS = {
    "dental": [("amenity", "dentist")], "dentist": [("amenity", "dentist")],
    "hospital": [("amenity", "hospital")], "clinic": [("amenity", "clinic")],
    "restaurant": [("amenity", "restaurant")], "cafe": [("amenity", "cafe")],
    "bakery": [("shop", "bakery")], "hotel": [("tourism", "hotel")],
    "resort": [("tourism", "resort")], "school": [("amenity", "school")],
    "college": [("amenity", "college")], "university": [("amenity", "university")],
    "pharmacy": [("amenity", "pharmacy")], "gym": [("leisure", "fitness_centre")],
    "salon": [("shop", "hairdresser")], "beauty": [("shop", "beauty")],
    "car dealer": [("shop", "car")], "car repair": [("shop", "car_repair")],
    "car wash": [("amenity", "car_wash")], "real estate": [("office", "estate_agent")],
    "lawyer": [("office", "lawyer")], "accountant": [("office", "accountant")],
    "travel agency": [("shop", "travel_agency")], "electronics": [("shop", "electronics")],
    "clothing": [("shop", "clothes")], "furniture": [("shop", "furniture")],
    "jewellery": [("shop", "jewelry")], "jewelry": [("shop", "jewelry")],
    "supermarket": [("shop", "supermarket")], "hardware": [("shop", "hardware")],
    "bank": [("amenity", "bank")], "insurance": [("office", "insurance")],
    "architect": [("office", "architect")], "construction": [("office", "construction_company")],
    "printing": [("shop", "printing")], "photographer": [("shop", "photo")],
    "fuel": [("amenity", "fuel")], "veterinary": [("amenity", "veterinary")],
}
ALL_TAGS = (
    [("amenity", x) for x in ["dentist", "hospital", "clinic", "restaurant", "cafe", "pharmacy", "school", "college", "university", "bank", "veterinary", "car_wash", "fuel"]]
    + [("shop", x) for x in ["bakery", "hairdresser", "beauty", "car", "car_repair", "electronics", "clothes", "furniture", "jewelry", "supermarket", "hardware", "printing", "photo", "travel_agency"]]
    + [("tourism", x) for x in ["hotel", "resort"]]
    + [("office", x) for x in ["estate_agent", "lawyer", "accountant", "insurance", "architect", "construction_company"]]
)


def _day():
    return time.strftime("%Y-%m-%d", time.gmtime())


async def _budget(source):
    policy = POLICIES[source]
    async with _locks[source]:
        now = time.monotonic()
        q = _usage[source]
        while q and now - q[0] >= 60:
            q.popleft()
        day, count = _daily.get(source, (_day(), 0))
        if day != _day():
            day, count = _day(), 0
        if count >= policy["daily"]:
            raise RuntimeError(f"{source} daily safety budget reached")
        if q and len(q) >= policy["rpm"]:
            await asyncio.sleep(max(0.5, 60 - (now - q[0])))
        if q:
            elapsed = time.monotonic() - q[-1]
            if elapsed < policy["delay"]:
                await asyncio.sleep(policy["delay"] - elapsed)
        q.append(time.monotonic())
        _daily[source] = (day, count + 1)


def _timeout(seconds):
    return httpx.Timeout(seconds, connect=min(10.0, seconds))


async def request(source: str, method: str, url: str, *, timeout: float = 20, **kwargs: Any) -> httpx.Response:
    if source not in POLICIES:
        raise ValueError(f"Unknown request source: {source}")
    await _budget(source)
    headers = {"User-Agent": USER_AGENT, **(kwargs.pop("headers", {}) or {})}
    referer = kwargs.pop("referer", None)
    if referer:
        headers["Referer"] = referer
    last = None
    for attempt in range(POLICIES[source]["retries"] + 1):
        try:
            async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=_timeout(timeout)) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
        except Exception as exc:
            last = exc
            log.warning("%s request failed | attempt=%s | %s | %s", source, attempt + 1, url, exc)
            if attempt < POLICIES[source]["retries"]:
                await asyncio.sleep(min(8, 2 ** attempt))
    raise last or RuntimeError("request failed")


def normalize_website(url: str | None) -> str | None:
    if not url:
        return None
    value = url.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    p = urlparse(value)
    return f"{p.scheme}://{p.netloc}".rstrip("/") if p.netloc else None


async def _google_discover(city: str, industry: str, limit: int) -> list[dict[str, Any]]:
    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        return []

    query = "businesses in " + city if industry.strip().lower() in {"all", "business", "businesses"} else f"{industry} in {city}"
    fields = ",".join([
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.googleMapsUri",
        "places.rating",
        "places.userRatingCount",
    ])
    page_size = min(20, max(1, int(limit)))
    body = {"textQuery": query, "pageSize": page_size, "rankPreference": "RELEVANCE", "regionCode": "IN"}
    try:
        response = await request(
            "google", "POST", GOOGLE_PLACES_URL, timeout=20,
            headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": fields, "Content-Type": "application/json"},
            json=body,
        )
        places = response.json().get("places", [])
    except Exception as exc:
        log.warning("Google Places discovery failed | city=%s | industry=%s | %s", city, industry, exc)
        return []

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rank, place in enumerate(places[:limit], start=1):
        name = ((place.get("displayName") or {}).get("text") or "").strip()
        if not name:
            continue
        place_id = str(place.get("id") or "").strip()
        website = normalize_website(place.get("websiteUri"))
        identity = place_id or website or f"{name.lower()}|{city.lower()}"
        if identity in seen:
            continue
        seen.add(identity)
        results.append({
            "name": name,
            "industry": industry,
            "city": city,
            "website": website,
            "phone": place.get("nationalPhoneNumber"),
            "email": None,
            "source": "google_places_text_search",
            "source_attribution": "Google Maps Platform / Places API",
            "source_place_id": f"google:{place_id}" if place_id else None,
            "resolved_city": city,
            "google_local_rank": rank,
            "google_match_confidence": 1.0,
            "google_maps_url": place.get("googleMapsUri") or "",
            "google_rating": place.get("rating"),
            "google_review_count": place.get("userRatingCount"),
            "_google_enriched": True,
        })
    log.info("Google Places discovery complete | city=%s | industry=%s | results=%s", city, industry, len(results))
    return results


async def _city_area(city: str):
    key = city.strip().lower()
    if key in _city_cache:
        return _city_cache[key]
    rows = (await request("nominatim", "GET", NOMINATIM_URL, params={"q": f"{city}, India", "format": "jsonv2", "limit": 1, "countrycodes": "in"}, timeout=15, referer=os.getenv("WEBHOOK_BASE_URL"))).json()
    if not rows:
        raise RuntimeError(f"Could not locate city in India: {city}")
    row = rows[0]
    osm_type = row.get("osm_type")
    osm_id = int(row["osm_id"])
    if osm_type == "relation":
        area_id = 3600000000 + osm_id
    elif osm_type == "way":
        area_id = 2400000000 + osm_id
    else:
        raise RuntimeError(f"City '{city}' did not resolve to an OSM area")
    result = (area_id, row.get("display_name", city))
    _city_cache[key] = result
    return result


def _filters(industry: str):
    key = industry.strip().lower()
    tags = ALL_TAGS if key in {"all", "business", "businesses"} else INDUSTRY_TAGS.get(key)
    if tags:
        return "".join(f'node["{k}"="{v}"](area.searchArea);way["{k}"="{v}"](area.searchArea);relation["{k}"="{v}"](area.searchArea);' for k, v in tags)
    safe = "".join(c for c in key if c.isalnum() or c in " _-")[:50]
    return f'node["name"~"{safe}",i](area.searchArea);way["name"~"{safe}",i](area.searchArea);relation["name"~"{safe}",i](area.searchArea);'


async def _overpass(query: str):
    errors = []
    for url in OVERPASS_URLS:
        try:
            return await request("overpass", "POST", url, data=query, timeout=20)
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
            continue
    raise RuntimeError("All discovery connections failed. Overpass mirrors are currently unavailable. Please retry shortly. " + " | ".join(errors)[-1400:])


async def _osm_discover(city: str, industry: str, limit: int) -> list[dict[str, Any]]:
    area_id, resolved_city = await _city_area(city)
    safe_limit = max(1, min(int(limit), 50))
    query = f"[out:json][timeout:20];area({area_id})->.searchArea;({_filters(industry)});out center tags;"
    payload = (await _overpass(query)).json()
    if payload.get("remark") and not payload.get("elements"):
        raise RuntimeError("Overpass rejected or terminated the discovery query: " + str(payload["remark"])[:500])
    elements = payload.get("elements", [])[:safe_limit]
    results = []
    seen = set()
    for item in elements:
        tags = item.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name:
            continue
        website = normalize_website(tags.get("website") or tags.get("contact:website"))
        identity = website or f"{name.lower()}|{city.lower()}"
        if identity in seen:
            continue
        seen.add(identity)
        results.append({
            "name": name, "industry": industry, "city": city, "website": website,
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "email": tags.get("email") or tags.get("contact:email"),
            "source": "openstreetmap_overpass", "source_attribution": "© OpenStreetMap contributors",
            "source_place_id": f"osm:{item.get('type')}:{item.get('id')}", "resolved_city": resolved_city,
        })
    log.info("OSM discovery complete | city=%s | industry=%s | results=%s", city, industry, len(results))
    return results


async def discover_businesses(city: str, industry: str, limit: int = 50) -> list[dict[str, Any]]:
    city = city.strip(); industry = industry.strip()
    if not city:
        raise ValueError("City is required")
    if not industry:
        raise ValueError("Business type is required")

    # Google Places is the primary discovery source when its server-side key is configured.
    # This prevents transient public Overpass outages from blocking lead searches.
    google_results = await _google_discover(city, industry, min(limit, 20))
    if google_results:
        return google_results

    # If Google is not configured or temporarily unavailable, retain the OSM fallback.
    return await _osm_discover(city, industry, limit)
