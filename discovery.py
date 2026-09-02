import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]
USER_AGENT = "LeadHunter/1.0 (business research; contact: LeadHunter operator)"

POLICIES = {
    "nominatim": {"rpm": 50, "daily": 500, "delay": 1.1, "retries": 1},
    "overpass": {"rpm": 6, "daily": 100, "delay": 10.0, "retries": 1},
}

_usage: dict[str, deque[float]] = defaultdict(deque)
_daily: dict[str, tuple[str, int]] = {}
_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_city_cache: dict[str, tuple[int, str]] = {}

INDUSTRY_TAGS = {
    "dental": [("amenity", "dentist")],
    "dentist": [("amenity", "dentist")],
    "hospital": [("amenity", "hospital")],
    "clinic": [("amenity", "clinic")],
    "restaurant": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "bakery": [("shop", "bakery")],
    "hotel": [("tourism", "hotel")],
    "resort": [("tourism", "resort")],
    "school": [("amenity", "school")],
    "college": [("amenity", "college")],
    "university": [("amenity", "university")],
    "pharmacy": [("amenity", "pharmacy")],
    "gym": [("leisure", "fitness_centre")],
    "salon": [("shop", "hairdresser")],
    "beauty": [("shop", "beauty")],
    "car dealer": [("shop", "car")],
    "car repair": [("shop", "car_repair")],
    "real estate": [("office", "estate_agent")],
    "lawyer": [("office", "lawyer")],
    "accountant": [("office", "accountant")],
    "travel agency": [("shop", "travel_agency")],
    "electronics": [("shop", "electronics")],
    "clothing": [("shop", "clothes")],
    "furniture": [("shop", "furniture")],
    "jewellery": [("shop", "jewelry")],
    "jewelry": [("shop", "jewelry")],
    "supermarket": [("shop", "supermarket")],
    "hardware": [("shop", "hardware")],
    "bank": [("amenity", "bank")],
    "insurance": [("office", "insurance")],
    "architect": [("office", "architect")],
    "printing": [("shop", "printing")],
    "photographer": [("shop", "photo")],
    "car wash": [("amenity", "car_wash")],
    "fuel": [("amenity", "fuel")],
    "veterinary": [("amenity", "veterinary")],
}

ALL_TAGS = [
    ("amenity", x)
    for x in [
        "dentist", "hospital", "clinic", "restaurant", "cafe", "pharmacy",
        "school", "college", "university", "bank", "veterinary", "car_wash", "fuel",
    ]
] + [
    ("shop", x)
    for x in [
        "bakery", "hairdresser", "beauty", "car", "car_repair", "electronics",
        "clothes", "furniture", "jewelry", "supermarket", "hardware", "printing",
        "photo", "travel_agency",
    ]
] + [
    ("tourism", x) for x in ["hotel", "resort"]
] + [
    ("office", x)
    for x in ["estate_agent", "lawyer", "accountant", "insurance", "architect"]
]


def _day() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


async def _budget(source: str) -> None:
    policy = POLICIES[source]
    async with _locks[source]:
        now = time.monotonic()
        queue = _usage[source]
        while queue and now - queue[0] >= 60:
            queue.popleft()

        day, count = _daily.get(source, (_day(), 0))
        if day != _day():
            day, count = _day(), 0
        if count >= policy["daily"]:
            raise RuntimeError(f"{source} daily safety budget reached")

        if queue and len(queue) >= policy["rpm"]:
            await asyncio.sleep(max(0.5, 60 - (now - queue[0])))

        if queue:
            elapsed = time.monotonic() - queue[-1]
            if elapsed < policy["delay"]:
                await asyncio.sleep(policy["delay"] - elapsed)

        queue.append(time.monotonic())
        _daily[source] = (day, count + 1)


def _timeout(seconds: float) -> httpx.Timeout:
    return httpx.Timeout(seconds, connect=min(8.0, seconds))


async def _request_once(
    source: str,
    method: str,
    url: str,
    *,
    timeout: float,
    **kwargs: Any,
) -> httpx.Response:
    await _budget(source)
    extra_headers = kwargs.pop("headers", {}) or {}
    headers = {"User-Agent": USER_AGENT, **extra_headers}
    referer = kwargs.pop("referer", None)
    if referer:
        headers["Referer"] = referer

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers=headers,
        timeout=_timeout(timeout),
    ) as client:
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return response


async def _request_with_retries(
    source: str,
    method: str,
    url: str,
    *,
    timeout: float,
    **kwargs: Any,
) -> httpx.Response:
    retries = POLICIES[source]["retries"]
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = await _request_once(source, method, url, timeout=timeout, **kwargs)
            log.info("%s request succeeded: %s", source, url)
            return response
        except Exception as exc:
            last = exc
            log.warning(
                "%s endpoint failed: %s attempt=%s error=%s",
                source,
                url,
                attempt + 1,
                exc,
            )
            if attempt < retries:
                await asyncio.sleep(min(10.0, 2.0 ** attempt))
    raise last or RuntimeError(f"{source} request failed")


async def _overpass_request(query: str) -> httpx.Response:
    errors: list[str] = []
    for url in OVERPASS_URLS:
        try:
            return await _request_with_retries(
                "overpass",
                "POST",
                url,
                data=query,
                timeout=35,
            )
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
            continue

    detail = " | ".join(errors)[-1600:]
    raise RuntimeError(
        "All discovery connections failed. Overpass providers were unavailable. "
        "Please retry in a moment. "
        f"Details: {detail}"
    )


def normalize_website(url: str | None) -> str | None:
    if not url:
        return None
    value = url.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    parsed = urlparse(value)
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/") if parsed.netloc else None


async def _city_area(city: str) -> tuple[int, str]:
    key = city.strip().lower()
    if key in _city_cache:
        return _city_cache[key]

    base_url = os.environ.get("WEBHOOK_BASE_URL")
    response = await _request_with_retries(
        "nominatim",
        "GET",
        NOMINATIM_URL,
        params={
            "q": f"{city}, India",
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "in",
        },
        timeout=15,
        referer=base_url,
    )
    rows = response.json()
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
        raise RuntimeError(
            f"City '{city}' resolved to a point instead of a boundary. Try another city spelling."
        )

    result = (area_id, row.get("display_name", city))
    _city_cache[key] = result
    return result


def _overpass_filters(industry: str) -> str:
    key = industry.strip().lower()
    tags = ALL_TAGS if key in {"all", "business", "businesses"} else INDUSTRY_TAGS.get(key)
    if tags:
        return "".join(
            f'node["{k}"="{v}"](area.searchArea);'
            f'way["{k}"="{v}"](area.searchArea);'
            f'relation["{k}"="{v}"](area.searchArea);'
            for k, v in tags
        )

    safe = "".join(c for c in key if c.isalnum() or c in " _-")[:50]
    return (
        f'node["name"~"{safe}",i](area.searchArea);'
        f'way["name"~"{safe}",i](area.searchArea);'
        f'relation["name"~"{safe}",i](area.searchArea);'
    )


async def discover_businesses(
    city: str,
    industry: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    city = city.strip()
    industry = industry.strip()
    if not city:
        raise ValueError("City is required")
    if not industry:
        raise ValueError("Business type is required")

    area_id, resolved_city = await _city_area(city)
    safe_limit = max(1, min(int(limit), 50))
    query = (
        f"[out:json][timeout:25];"
        f"area({area_id})->.searchArea;"
        f"({_overpass_filters(industry)});"
        f"out center tags;"
    )

    response = await _overpass_request(query)
    payload = response.json()
    elements = payload.get("elements", [])[:safe_limit]

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in elements:
        tags = item.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name:
            continue

        website = tags.get("website") or tags.get("contact:website")
        identity = normalize_website(website) or f"{name.lower()}|{city.lower()}"
        if identity in seen:
            continue
        seen.add(identity)

        results.append(
            {
                "name": name,
                "industry": industry,
                "city": city,
                "website": normalize_website(website),
                "phone": tags.get("phone") or tags.get("contact:phone"),
                "email": tags.get("email") or tags.get("contact:email"),
                "source": "openstreetmap_overpass",
                "source_attribution": "© OpenStreetMap contributors",
                "source_place_id": f"osm:{item.get('type')}:{item.get('id')}",
                "resolved_city": resolved_city,
            }
        )

    log.info(
        "Discovery complete | city=%s | industry=%s | results=%s",
        city,
        industry,
        len(results),
    )
    return results
