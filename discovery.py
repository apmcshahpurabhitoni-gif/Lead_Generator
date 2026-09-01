import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "LeadHunter/1.0 (business research; contact: admin)"
POLICIES = {"nominatim": {"rpm": 50, "daily": 500, "delay": 1.1, "retries": 2}, "overpass": {"rpm": 6, "daily": 100, "delay": 10.0, "retries": 2}, "website": {"rpm": 12, "daily": 500, "delay": 5.0, "retries": 2}}
_usage: dict[str, deque[float]] = defaultdict(deque); _daily: dict[str, tuple[str, int]] = {}; _locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
INDUSTRY_TAGS = {"dental":[("amenity","dentist")],"dentist":[("amenity","dentist")],"hospital":[("amenity","hospital")],"clinic":[("amenity","clinic")],"restaurant":[("amenity","restaurant")],"cafe":[("amenity","cafe")],"bakery":[("shop","bakery")],"hotel":[("tourism","hotel")],"resort":[("tourism","resort")],"school":[("amenity","school")],"college":[("amenity","college")],"university":[("amenity","university")],"pharmacy":[("amenity","pharmacy")],"gym":[("leisure","fitness_centre")],"salon":[("shop","hairdresser")],"beauty":[("shop","beauty")],"car dealer":[("shop","car")],"car repair":[("shop","car_repair")],"real estate":[("office","estate_agent")],"lawyer":[("office","lawyer")],"accountant":[("office","accountant")],"travel agency":[("shop","travel_agency")],"electronics":[("shop","electronics")],"clothing":[("shop","clothes")],"furniture":[("shop","furniture")],"jewellery":[("shop","jewelry")],"jewelry":[("shop","jewelry")],"supermarket":[("shop","supermarket")],"hardware":[("shop","hardware")],"bank":[("amenity","bank")],"insurance":[("office","insurance")],"architect":[("office","architect")],"printing":[("shop","printing")],"photographer":[("shop","photo")],"car wash":[("amenity","car_wash")],"fuel":[("amenity","fuel")],"veterinary":[("amenity","veterinary")],}
ALL_TAGS = [("amenity", x) for x in ["dentist","hospital","clinic","restaurant","cafe","pharmacy","school","college","university","bank","veterinary","car_wash","fuel"]] + [("shop", x) for x in ["bakery","hairdresser","beauty","car","car_repair","electronics","clothes","furniture","jewelry","supermarket","hardware","printing","photo","travel_agency"]] + [("tourism", x) for x in ["hotel","resort"]] + [("office", x) for x in ["estate_agent","lawyer","accountant","insurance","architect"]]


def _day() -> str: return time.strftime("%Y-%m-%d", time.gmtime())


async def _budget(source: str) -> None:
    p = POLICIES[source]
    async with _locks[source]:
        now=time.monotonic(); q=_usage[source]
        while q and now-q[0]>=60: q.popleft()
        day,count=_daily.get(source,(_day(),0))
        if day!=_day(): day,count=_day(),0
        if count>=p["daily"]: raise RuntimeError(f"{source} daily safety budget reached")
        if q and len(q)>=p["rpm"]: await asyncio.sleep(max(.5,60-(now-q[0])))
        if q:
            elapsed=time.monotonic()-q[-1]
            if elapsed<p["delay"]: await asyncio.sleep(p["delay"]-elapsed)
        q.append(time.monotonic()); _daily[source]=(day,count+1)


async def request(source: str, method: str, url: str, **kwargs: Any) -> httpx.Response:
    await _budget(source); p=POLICIES[source]; last=None; headers={"User-Agent":USER_AGENT,**kwargs.pop("headers",{})}
    async with httpx.AsyncClient(follow_redirects=True,headers=headers) as client:
        for attempt in range(p["retries"]+1):
            try:
                response=await client.request(method,url,timeout=kwargs.pop("timeout",30),**kwargs)
                if response.status_code==429:
                    await asyncio.sleep(30 if source=="overpass" else min(60,2**attempt*5)); continue
                response.raise_for_status(); return response
            except Exception as exc:
                last=exc
                if attempt<p["retries"]: await asyncio.sleep(min(30,2**attempt*2))
    raise last or RuntimeError("request failed")


def normalize_website(url: str | None) -> str | None:
    if not url:return None
    value=url.strip()
    if not value:return None
    if not value.startswith(("http://","https://")): value="https://"+value
    parsed=urlparse(value)
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/") if parsed.netloc else None


async def _city_area(city: str) -> tuple[int,str]:
    response=await request("nominatim","GET",NOMINATIM_URL,params={"q":f"{city}, India","format":"jsonv2","limit":1,"countrycodes":"in"},timeout=15)
    rows=response.json()
    if not rows: raise RuntimeError(f"Could not locate city: {city}")
    row=rows[0]; osm_type=row.get("osm_type"); osm_id=int(row["osm_id"])
    if osm_type=="relation": area_id=3600000000+osm_id
    elif osm_type=="way": area_id=2400000000+osm_id
    else: raise RuntimeError("City resolved to a point; use a supported city/town boundary")
    return area_id,row.get("display_name",city)


def _overpass_filters(industry: str) -> str:
    key=industry.strip().lower(); tags=ALL_TAGS if key in {"all","business","businesses"} else INDUSTRY_TAGS.get(key)
    if tags: return "".join(f'node["{k}"="{v}"](area.searchArea);way["{k}"="{v}"](area.searchArea);relation["{k}"="{v}"](area.searchArea);' for k,v in tags)
    safe="".join(c for c in key if c.isalnum() or c in " _-")[:50]
    return f'node["name"~"{safe}",i](area.searchArea);way["name"~"{safe}",i](area.searchArea);relation["name"~"{safe}",i](area.searchArea);'


async def discover_businesses(city: str, industry: str, limit: int=50) -> list[dict[str,Any]]:
    area_id,resolved_city=await _city_area(city)
    query=f"[out:json][timeout:25];area({area_id})->.searchArea;({_overpass_filters(industry)});out center tags;"
    response=await request("overpass","POST",OVERPASS_URL,data=query,timeout=40)
    elements=response.json().get("elements",[])[:max(1,min(limit,50))]; results=[]; seen=set()
    for item in elements:
        tags=item.get("tags") or {}; name=(tags.get("name") or "").strip()
        if not name: continue
        website=tags.get("website") or tags.get("contact:website"); identity=normalize_website(website) or f"{name.lower()}|{city.lower()}"
        if identity in seen: continue
        seen.add(identity)
        results.append({"name":name,"industry":industry,"city":city,"website":normalize_website(website),"phone":tags.get("phone") or tags.get("contact:phone"),"email":tags.get("email") or tags.get("contact:email"),"source":"openstreetmap_overpass","source_attribution":"© OpenStreetMap contributors","source_place_id":f"osm:{item.get('type')}:{item.get('id')}","resolved_city":resolved_city})
    return results
