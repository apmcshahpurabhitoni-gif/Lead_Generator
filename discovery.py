import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from typing import Any
from urllib.parse import urlparse

import httpx

from config import APP_VERSION

log = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

OVERPASS_URLS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

USER_AGENT = (
    f"LeadHunter/{APP_VERSION} "
    "(business research; Google Places + OSM discovery)"
)

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
    "car wash": [("amenity", "car_wash")],
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
    "construction": [("office", "construction_company")],
    "printing": [("shop", "printing")],
    "photographer": [("shop", "photo")],
    "fuel": [("amenity", "fuel")],
    "veterinary": [("amenity", "veterinary")],
}

ALL_TAGS = (
    [
        ("amenity", x)
        for x in [
            "dentist",
            "hospital",
            "clinic",
            "restaurant",
            "cafe",
            "pharmacy",
            "school",
            "college",
            "university",
            "bank",
            "veterinary",
            "car_wash",
            "fuel",
        ]
    ]
    + [
        ("shop", x)
        for x in [
            "bakery",
            "hairdresser",
            "beauty",
            "car",
            "car_repair",
            "electronics",
            "clothes",
            "furniture",
            "jewelry",
            "supermarket",
            "hardware",
            "printing",
            "photo",
            "travel_agency",
        ]
    ]
    + [("tourism", x) for x in ["hotel", "resort"]]
    + [
        ("office", x)
        for x in [
            "estate_agent",
            "lawyer",
            "accountant",
            "insurance",
            "architect",
            "construction_company",
        ]
    ]
)


def _day() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


async def _budget(source: str) -> None:
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


def _timeout(seconds: float) -> httpx.Timeout:
    return httpx.Timeout(seconds, connect=min(10.0, seconds))


async def request(
    source: str,
    method: str,
    url: str,
    *,
    timeout: float = 20,
    **kwargs: Any,
) -> httpx.Response:
    if source not in POLICIES:
        raise ValueError(f"Unknown request source: {source}")

    await _budget(source)

    headers = {
        "User-Agent": USER_AGENT,
        **(kwargs.pop("headers", {}) or {}),
    }
    referer = kwargs.pop("referer", None)
    if referer:
        headers["Referer"] = referer

    last: Exception | None = None
    for attempt in range(POLICIES[source]["retries"] + 1):
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                headers=headers,
                timeout=_timeout(timeout),
            ) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
        except Exception as exc:
            last = exc
            log.warning(
                "%s request failed | attempt=%s | %s | %s",
                source,
                attempt + 1,
                url,
                exc,
            )
            if attempt < POLICIES[source]["retries"]:
                await asyncio.sleep(min(8, 2**attempt))

    raise last or RuntimeError("request failed")


def normalize_website(url: str | None) -> str | None:
    if not url:
        return None

    value = url.strip()
    if not value:
        return None

    if not value.startswith(("http://", "https://")):
        value = "https://" + value

    parsed = urlparse(value)
    return (
        f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if parsed.netloc
        else None
    )


# Google Places types are used to verify that a result actually belongs to the
# requested category. The old implementation labelled every returned place
# with the requested industry, which is why a dental search could contain
# restaurants/hotels.
GOOGLE_INDUSTRY_TYPES = {
    "dental": {"dentist"},
    "dentist": {"dentist"},
    "hospital": {"hospital"},
    "clinic": {"medical_clinic", "doctor", "medical_center"},
    "restaurant": {"restaurant"},
    "cafe": {"cafe", "coffee_shop"},
    "bakery": {"bakery"},
    "hotel": {"hotel", "lodging"},
    "resort": {"resort_hotel", "hotel", "lodging"},
    "school": {"school"},
    "college": {"college"},
    "university": {"university"},
    "pharmacy": {"pharmacy"},
    "gym": {"gym", "fitness_center"},
    "salon": {"hair_salon"},
    "beauty": {"beauty_salon", "spa"},
    "car dealer": {"car_dealer"},
    "car repair": {"car_repair", "auto_repair"},
    "car wash": {"car_wash"},
    "real estate": {"real_estate_agency"},
    "lawyer": {"lawyer"},
    "accountant": {"accounting"},
    "travel agency": {"travel_agency"},
    "electronics": {"electronics_store"},
    "clothing": {"clothing_store"},
    "furniture": {"furniture_store"},
    "jewellery": {"jewelry_store"},
    "jewelry": {"jewelry_store"},
    "supermarket": {"supermarket", "grocery_store"},
    "hardware": {"hardware_store"},
    "bank": {"bank"},
    "insurance": {"insurance_agency"},
    "architect": {"architect"},
    "construction": {"general_contractor"},
    "printing": {"printing_service"},
    "photographer": {"photographer"},
    "fuel": {"gas_station"},
    "veterinary": {"veterinary_care"},
}


def _google_match(industry: str, types: list[str]) -> tuple[bool, float]:
    key = industry.strip().lower()
    if key in {"all", "business", "businesses"}:
        return True, 1.0

    wanted = GOOGLE_INDUSTRY_TYPES.get(key)
    if not wanted:
        # Unknown/custom searches cannot be type-verified safely.
        return True, 0.5

    normalized = {str(item).strip().lower() for item in types}
    matched = wanted.intersection(normalized)
    if matched:
        return True, 1.0

    # Google can return a useful generic type such as "point_of_interest".
    # Do not pretend that generic results are a verified category.
    return False, 0.0


async def _google_discover(
    city: str, industry: str, limit: int
) -> list[dict[str, Any]]:
    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        return []

    query = (
        "businesses in " + city
        if industry.strip().lower() in {"all", "business", "businesses"}
        else f"{industry} in {city}"
    )

    fields = ",".join(
        [
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.websiteUri",
            "places.nationalPhoneNumber",
            "places.googleMapsUri",
            "places.rating",
            "places.userRatingCount",
            "places.types",
        ]
    )

    wanted = max(1, min(int(limit), 50))
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    page_token: str | None = None

    try:
        # When filtering by Places type we may have to inspect more Google
        # results than the requested final limit to fill the requested count.
        max_pages = 5

        for _ in range(max_pages):
            if len(results) >= wanted:
                break

            remaining = max(1, min(20, wanted - len(results)))
            body: dict[str, Any] = {
                "textQuery": query,
                "pageSize": remaining,
                "rankPreference": "RELEVANCE",
                "regionCode": "IN",
            }
            if page_token:
                body["pageToken"] = page_token

            response = await request(
                "google",
                "POST",
                GOOGLE_PLACES_URL,
                timeout=20,
                headers={
                    "X-Goog-Api-Key": key,
                    "X-Goog-FieldMask": fields + ",nextPageToken",
                    "Content-Type": "application/json",
                },
                json=body,
            )

            data = response.json()
            places = data.get("places", [])
            if not places:
                break

            for place in places:
                if len(results) >= wanted:
                    break

                name = (
                    (place.get("displayName") or {}).get("text") or ""
                ).strip()
                if not name:
                    continue

                google_types = [
                    str(item)
                    for item in (place.get("types") or [])
                    if item
                ]
                is_match, confidence = _google_match(
                    industry, google_types
                )

                if not is_match:
                    log.info(
                        "Google result rejected by type filter | "
                        "name=%s | requested=%s | types=%s",
                        name,
                        industry,
                        google_types,
                    )
                    continue

                place_id = str(place.get("id") or "").strip()
                website = normalize_website(place.get("websiteUri"))
                identity = (
                    place_id
                    or website
                    or f"{name.lower()}|{city.lower()}"
                )
                if identity in seen:
                    continue
                seen.add(identity)

                rank = len(results) + 1
                results.append(
                    {
                        "name": name,
                        "industry": industry,
                        "city": city,
                        "address": place.get("formattedAddress"),
                        "website": website,
                        "phone": place.get("nationalPhoneNumber"),
                        "email": None,
                        "source": "google_places_text_search",
                        "source_attribution": "Google Maps Platform / Places API",
                        "source_place_id": (
                            f"google:{place_id}" if place_id else None
                        ),
                        "resolved_city": city,
                        "requested_industry": industry,
                        "google_provider_rank": rank,
                        "google_local_rank": rank,
                        "google_match_confidence": confidence,
                        "google_types": google_types,
                        "google_maps_url": place.get("googleMapsUri") or "",
                        "google_rating": place.get("rating"),
                        "google_review_count": place.get(
                            "userRatingCount"
                        ),
                        "_google_enriched": True,
                    }
                )

            page_token = data.get("nextPageToken")
            if not page_token:
                break

            await asyncio.sleep(0.25)

    except Exception as exc:
        log.warning(
            "Google Places discovery failed | city=%s | industry=%s | %s",
            city,
            industry,
            exc,
        )
        return results

    log.info(
        "Google Places discovery complete | city=%s | industry=%s | results=%s",
        city,
        industry,
        len(results),
    )
    return results


async def _city_area(city: str) -> tuple[int, str]:
    key = city.strip().lower()
    if key in _city_cache:
        return _city_cache[key]

    rows = (
        await request(
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
            referer=os.getenv("WEBHOOK_BASE_URL"),
        )
    ).json()

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
            f"City '{city}' did not resolve to an OSM area"
        )

    result = (area_id, row.get("display_name", city))
    _city_cache[key] = result
    return result


def _filters(industry: str) -> str:
    key = industry.strip().lower()
    tags = (
        ALL_TAGS
        if key in {"all", "business", "businesses"}
        else INDUSTRY_TAGS.get(key)
    )

    if tags:
        return "".join(
            f'node["{k}"="{v}"](area.searchArea);'
            f'way["{k}"="{v}"](area.searchArea);'
            f'relation["{k}"="{v}"](area.searchArea);'
            for k, v in tags
        )

    safe = "".join(
        c for c in key if c.isalnum() or c in " _-"
    )[:50]
    escaped = safe.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f'node["name"~"{escaped}",i](area.searchArea);'
        f'way["name"~"{escaped}",i](area.searchArea);'
        f'relation["name"~"{escaped}",i](area.searchArea);'
    )


async def _overpass(query: str) -> httpx.Response:
    errors: list[str] = []
    for url in OVERPASS_URLS:
        try:
            return await request(
                "overpass",
                "POST",
                url,
                data=query,
                timeout=20,
            )
        except Exception as exc:
            errors.append(
                f"{url}: {type(exc).__name__}: {exc}"
            )

    raise RuntimeError(
        "All discovery connections failed. Overpass mirrors are "
        "currently unavailable. Please retry shortly. "
        + " | ".join(errors)[-1400:]
    )


async def _osm_discover(
    city: str, industry: str, limit: int
) -> list[dict[str, Any]]:
    area_id, resolved_city = await _city_area(city)
    safe_limit = max(1, min(int(limit), 50))
    query = (
        f"[out:json][timeout:20];"
        f"area({area_id})->.searchArea;"
        f"({_filters(industry)});"
        f"out center tags;"
    )

    payload = (await _overpass(query)).json()
    if payload.get("remark") and not payload.get("elements"):
        raise RuntimeError(
            "Overpass rejected or terminated the discovery query: "
            + str(payload["remark"])[:500]
        )

    elements = payload.get("elements", [])[:safe_limit]
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in elements:
        tags = item.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name:
            continue

        website = normalize_website(
            tags.get("website") or tags.get("contact:website")
        )
        identity = website or f"{name.lower()}|{city.lower()}"
        if identity in seen:
            continue
        seen.add(identity)

        # The previous implementation referenced an undefined `place`
        # variable here, causing the entire OSM fallback to fail.
        address_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:suburb"),
            tags.get("addr:city"),
            tags.get("addr:postcode"),
        ]
        address = ", ".join(
            str(part).strip()
            for part in address_parts
            if part and str(part).strip()
        ) or None

        results.append(
            {
                "name": name,
                "industry": industry,
                "city": city,
                "address": address,
                "website": website,
                "phone": tags.get("phone")
                or tags.get("contact:phone"),
                "email": tags.get("email")
                or tags.get("contact:email"),
                "source": "openstreetmap_overpass",
                "source_attribution": "© OpenStreetMap contributors",
                "source_place_id": (
                    f"osm:{item.get('type')}:{item.get('id')}"
                ),
                "resolved_city": resolved_city,
                "requested_industry": industry,
                "google_provider_rank": len(results) + 1,
                "google_local_rank": None,
                "google_match_confidence": 1.0,
                "google_types": [],
                "google_maps_url": "",
                "google_rating": None,
                "google_review_count": None,
            }
        )

    log.info(
        "OSM discovery complete | city=%s | industry=%s | results=%s",
        city,
        industry,
        len(results),
    )
    return results


async def discover_businesses(
    city: str, industry: str, limit: int = 50
) -> list[dict[str, Any]]:
    city = city.strip()
    industry = industry.strip()

    if not city:
        raise ValueError("City is required")
    if not industry:
        raise ValueError("Business type is required")

    safe_limit = max(1, min(int(limit), 50))

    google_results = await _google_discover(
        city, industry, safe_limit
    )
    if google_results:
        return google_results

    return await _osm_discover(
        city, industry, safe_limit
    )
