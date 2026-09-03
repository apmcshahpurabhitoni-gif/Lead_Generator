import re, os
from collections import deque
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup
from discovery import normalize_website, request

MAX_PAGES=5
MAX_BYTES=1_500_000
from config import APP_VERSION
MAX_LINKS_PER_PAGE=20
MAX_PROFILE_LINKS=20
_robots_cache: dict[str, RobotFileParser|None]={}
GOOGLE_PLACES_URL="https://places.googleapis.com/v1/places:searchText"

# Only links explicitly published by the business website are collected. Protected
# third-party sites are not directly scraped.
PROFILE_PATTERNS={
    "linkedin":("linkedin.com/",), "justdial":("justdial.com/",),
    "facebook":("facebook.com/","fb.com/"), "instagram":("instagram.com/",),
    "youtube":("youtube.com/","youtu.be/"), "x":("x.com/","twitter.com/"),
    "google_business":("google.com/maps","maps.google.com/"), "sulekha":("sulekha.com/",),
    "indiamart":("indiamart.com/",), "practo":("practo.com/",), "lybrate":("lybrate.com/",),
    "zomato":("zomato.com/",), "swiggy":("swiggy.com/",), "booking":("booking.com/",),
    "makemytrip":("makemytrip.com/",), "goibibo":("goibibo.com/",), "tripadvisor":("tripadvisor.",),
    "agoda":("agoda.com/",), "weddingwire":("weddingwire.in/",), "edustoke":("edustoke.com/",),
    "schoolmykids":("schoolmykids.com/",), "cardekho":("cardekho.com/",), "carwale":("carwale.com/",),
    "99acres":("99acres.com/",), "magicbricks":("magicbricks.com/",), "housing":("housing.com/",),
    "nobroker":("nobroker.in/",), "houzz":("houzz.in/","houzz.com/"),
}

def _norm_name(value:str)->str: return re.sub(r"[^a-z0-9]+"," ",(value or "").lower()).strip()
def _match_score(a:str,b:str)->float:
    aa,bb=_norm_name(a),_norm_name(b)
    if not aa or not bb:return 0.0
    if aa==bb:return 1.0
    if aa in bb or bb in aa:return 0.90
    return SequenceMatcher(None,aa,bb).ratio()
def _classify_profile(url:str)->str|None:
    parsed=urlparse(url); host=parsed.netloc.lower().split(":",1)[0]; path=(host+parsed.path).lower()
    for kind,markers in PROFILE_PATTERNS.items():
        if any(marker in path for marker in markers): return kind
    return None
def _external_profile_links(url:str,soup:BeautifulSoup)->dict[str,list[str]]:
    profiles={}; source_host=urlparse(url).netloc.lower().split(":",1)[0]
    for a in soup.find_all("a",href=True):
        target=urljoin(url,a["href"]).split("#",1)[0]; host=urlparse(target).netloc.lower().split(":",1)[0]
        if not host or host==source_host: continue
        kind=_classify_profile(target)
        if kind: profiles.setdefault(kind,[]).append(target)
    return {k:list(dict.fromkeys(v))[:5] for k,v in profiles.items()}

async def google_places_enrich(city:str,industry:str,businesses:list[dict[str,Any]])->dict[str,Any]:
    query=f"{industry} in {city}"
    if businesses and all(bool(b.get("_google_enriched")) for b in businesses):
        return {"status":"OK","query":query,"results":len(businesses),"source":"google_places_text_search"}
    key=os.getenv("GOOGLE_MAPS_API_KEY","").strip(); base={"status":"NOT_CONFIGURED","query":query,"results":0}
    if not key:return base
    body={"textQuery":query,"pageSize":20,"rankPreference":"RELEVANCE","regionCode":"IN"}
    fields="places.displayName,places.formattedAddress,places.websiteUri,places.nationalPhoneNumber,places.googleMapsUri,places.rating,places.userRatingCount"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r=await client.post(GOOGLE_PLACES_URL,headers={"X-Goog-Api-Key":key,"X-Goog-FieldMask":fields,"Content-Type":"application/json"},json=body); r.raise_for_status(); places=r.json().get("places",[])
        base.update({"status":"OK","results":len(places)})
        for business in businesses:
            best=None; best_score=0.0
            for place in places:
                name=(place.get("displayName") or {}).get("text",""); score=_match_score(business.get("name",""),name)
                if score>best_score: best_score,best=score,place
            if best and best_score>=0.60:
                business["google_local_rank"]=next((i+1 for i,p in enumerate(places) if p is best),None); business["google_match_confidence"]=round(best_score,2)
                business["google_maps_url"]=best.get("googleMapsUri") or ""; business["google_rating"]=best.get("rating"); business["google_review_count"]=best.get("userRatingCount")
                if not business.get("website") and best.get("websiteUri"): business["website"]=normalize_website(best.get("websiteUri"))
                if not business.get("phone") and best.get("nationalPhoneNumber"): business["phone"]=best.get("nationalPhoneNumber")
        return base
    except Exception as exc:
        base.update({"status":"ERROR","error":f"{type(exc).__name__}: {exc}"}); return base

def extract_page(url:str,content:bytes)->dict[str,Any]:
    soup=BeautifulSoup(content,"lxml"); title=soup.title.get_text(" ",strip=True) if soup.title else ""
    meta=soup.find("meta",attrs={"name":re.compile(r"^description$",re.I)}); description=(meta.get("content") or "").strip() if meta else ""
    headings=[h.get_text(" ",strip=True) for h in soup.find_all(["h1","h2"])][:30]; host=urlparse(url).netloc; links=[]
    for a in soup.find_all("a",href=True):
        target=urljoin(url,a["href"]).split("#",1)[0]
        if urlparse(target).netloc==host: links.append(target)
    profiles=_external_profile_links(url,soup); text=soup.get_text(" ",strip=True)
    phones=re.findall(r"(?:\+91[\s-]?)?[6-9]\d{9}",text); emails=re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",text,re.I)
    raw=content.decode("utf-8",errors="ignore").lower(); scripts=" ".join((s.get("src") or "") for s in soup.find_all("script")).lower()
    tech=[name for marker,name in [("wp-content","WordPress"),("woocommerce","WooCommerce"),("shopify","Shopify"),("gtag(","Google Analytics"),("googletagmanager","Google Tag Manager")] if marker in raw or marker in scripts]
    return {"url":url,"title":title,"description":description,"headings":headings,"internal_links":sorted(set(links))[:MAX_LINKS_PER_PAGE],"profile_links":profiles,"schema":bool(soup.find("script",attrs={"type":"application/ld+json"})),"mobile_viewport":bool(soup.find("meta",attrs={"name":re.compile(r"^viewport$",re.I)})),"phones":list(dict.fromkeys(phones))[:5],"emails":list(dict.fromkeys(emails))[:5],"text_length":len(text),"technology":sorted(set(tech))}

async def robots_allowed(website:str,target:str)->bool:
    host=urlparse(website).netloc
    if host not in _robots_cache:
        robots_url=urljoin(website.rstrip("/")+"/","robots.txt")
        try:
            response=await request("website","GET",robots_url,timeout=10); parser=RobotFileParser(); parser.set_url(robots_url); parser.parse(response.text.splitlines()); _robots_cache[host]=parser
        except httpx.HTTPStatusError as exc: _robots_cache[host]=RobotFileParser() if exc.response is not None and exc.response.status_code==404 else None
        except Exception: _robots_cache[host]=None
    parser=_robots_cache[host]
    if parser is None:return False
    if not parser.entries and not parser.default_entry:return True
    return parser.can_fetch(f"LeadHunter/{APP_VERSION}",target)

async def research_business(business:dict[str,Any])->dict[str,Any]:
    website=normalize_website(business.get("website")); result={"industry":business.get("industry"),"research_status":"STARTED","confidence":0,"website":{"exists":bool(website),"pages":[],"errors":[],"robots_checked":False},"seo":{},"local":{},"search":{"status":"NOT_CONFIGURED","organic_rank":None},"google":{"local_rank":business.get("google_local_rank"),"match_confidence":business.get("google_match_confidence"),"maps_url":business.get("google_maps_url"),"rating":business.get("google_rating"),"review_count":business.get("google_review_count")},"profiles":{},"profile_check_note":"Only public profile links published by the business website are reported; third-party directory absence is not established.","technology":{"signals":[]},"buying_signals":[],"problems":[]}
    if not website:
        result["problems"].append("No official website was found from the discovery source or Google Places."); result["seo"]={"score":0,"reason":"No verified website"}; result["research_status"]="PARTIAL"; result["confidence"]=55; result["local"]={"phone_found":bool(business.get("phone")),"email_found":bool(business.get("email")),"city":business.get("city")}; return result
    if not await robots_allowed(website,website+"/"):
        result["website"]["robots_checked"]=True; result["website"]["errors"].append("Website could not be crawled under its robots policy."); result["problems"].append("Website could not be crawled under the site's robots policy."); result["research_status"]="UNAVAILABLE"; result["confidence"]=35; return result
    result["website"]["robots_checked"]=True; queue=deque([website]); seen=set()
    while queue and len(seen)<MAX_PAGES:
        url=queue.popleft()
        if url in seen or urlparse(url).netloc!=urlparse(website).netloc: continue
        seen.add(url)
        try:
            response=await request("website","GET",url,timeout=15)
            if len(response.content)>MAX_BYTES: result["website"]["errors"].append(f"{url}: response too large"); continue
            final_url=str(response.url)
            if not await robots_allowed(website,final_url): continue
            page=extract_page(final_url,response.content); result["website"]["pages"].append(page)
            for link in page["internal_links"]:
                if link not in seen and link not in queue: queue.append(link)
        except Exception as exc: result["website"]["errors"].append(f"{url}: {type(exc).__name__}")
    pages=result["website"]["pages"]
    if not pages:
        result["problems"].append("Website was found but could not be successfully researched."); result["seo"]={"score":0,"reason":"No readable pages"}; result["research_status"]="UNAVAILABLE"; result["confidence"]=35; return result
    profile_links={}
    for page in pages:
        for kind,urls in (page.get("profile_links") or {}).items(): profile_links.setdefault(kind,[]).extend(urls)
    result["profiles"]={k:list(dict.fromkeys(v))[:5] for k,v in profile_links.items() if v}
    home=pages[0]; score=100
    if not home["title"]:score-=20;result["problems"].append("Homepage title is missing.")
    if not home["description"]:score-=15;result["problems"].append("Homepage meta description is missing.")
    if not home["schema"]:score-=5;result["problems"].append("JSON-LD structured data was not detected on the homepage.")
    if not home["mobile_viewport"]:score-=15;result["problems"].append("Mobile viewport metadata was not detected.")
    if not home["headings"]:score-=10;result["problems"].append("No heading structure was detected on the homepage.")
    result["seo"]={"score":max(0,score),"title_present":bool(home["title"]),"description_present":bool(home["description"]),"schema":home["schema"],"mobile_viewport":home["mobile_viewport"]}
    result["local"]={"phone_found":bool(home["phones"] or business.get("phone")),"email_found":bool(home["emails"] or business.get("email")),"phones":list(dict.fromkeys((home["phones"] or [])+[business.get("phone")] if business.get("phone") else home["phones"]))[:5],"emails":list(dict.fromkeys((home["emails"] or [])+[business.get("email")] if business.get("email") else home["emails"]))[:5],"city":business.get("city")}
    if result["local"]["phones"] and not business.get("phone"):business["phone"]=result["local"]["phones"][0]
    if result["local"]["emails"] and not business.get("email"):business["email"]=result["local"]["emails"][0]
    result["technology"]={"signals":sorted(set(x for p in pages for x in p.get("technology",[])))}; result["research_status"]="COMPLETE"; result["confidence"]=90 if not result["website"]["errors"] else 75; return result
