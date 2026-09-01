import re
from collections import deque
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from discovery import normalize_website, request

MAX_PAGES = 5
MAX_BYTES = 1_500_000
MAX_LINKS_PER_PAGE = 20
_robots_cache: dict[str, RobotFileParser | None] = {}


def extract_page(url: str, html: bytes) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    description = (meta.get("content") or "").strip() if meta else ""
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])][:30]
    host = urlparse(url).netloc
    links = []
    for a in soup.find_all("a", href=True):
        target = urljoin(url, a["href"]).split("#", 1)[0]
        if urlparse(target).netloc == host: links.append(target)
    text = soup.get_text(" ", strip=True)
    phones = re.findall(r"(?:\+91[\s-]?)?[6-9]\d{9}", text)
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)
    html_lower = html.decode("utf-8", errors="ignore").lower()
    scripts = " ".join((s.get("src") or "") for s in soup.find_all("script")).lower()
    tech = [name for marker, name in [("wp-content", "WordPress"), ("woocommerce", "WooCommerce"), ("shopify", "Shopify"), ("gtag(", "Google Analytics"), ("googletagmanager", "Google Tag Manager")] if marker in html_lower or marker in scripts]
    return {"url": url, "title": title, "description": description, "headings": headings, "internal_links": sorted(set(links))[:MAX_LINKS_PER_PAGE], "schema": bool(soup.find("script", attrs={"type": "application/ld+json"})), "mobile_viewport": bool(soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})), "phones": list(dict.fromkeys(phones))[:5], "emails": list(dict.fromkeys(emails))[:5], "text_length": len(text), "technology": sorted(set(tech))}


async def robots_allowed(website: str, target: str) -> bool:
    host_key = urlparse(website).netloc
    if host_key not in _robots_cache:
        robots_url = urljoin(website + "/", "robots.txt")
        try:
            response = await request("website", "GET", robots_url, timeout=10)
            parser = RobotFileParser(); parser.set_url(robots_url); parser.parse(response.text.splitlines()); _robots_cache[host_key] = parser
        except Exception:
            _robots_cache[host_key] = None
    parser = _robots_cache[host_key]
    return bool(parser and parser.can_fetch("LeadHunter/1.0", target))


async def research_business(business: dict[str, Any]) -> dict[str, Any]:
    website = normalize_website(business.get("website"))
    result: dict[str, Any] = {"website": {"exists": bool(website), "pages": [], "errors": [], "robots_checked": False}, "seo": {}, "local": {}, "search": {"status": "NOT_CONFIGURED"}, "technology": {"signals": []}, "buying_signals": [], "problems": []}
    if not website:
        result["problems"].append("No business website was supplied by the discovery source."); result["seo"] = {"score": 0, "reason": "No website"}; return result
    if not await robots_allowed(website, website + "/"):
        result["website"]["robots_checked"] = True; result["website"]["errors"].append("Crawling not permitted by robots.txt or robots.txt could not be read."); result["problems"].append("Website could not be crawled because robots.txt did not permit LeadHunter."); return result
    result["website"]["robots_checked"] = True
    queue, seen = deque([website]), set()
    while queue and len(seen) < MAX_PAGES:
        url = queue.popleft()
        if url in seen or urlparse(url).netloc != urlparse(website).netloc: continue
        seen.add(url)
        try:
            response = await request("website", "GET", url, timeout=15)
            if len(response.content) > MAX_BYTES: result["website"]["errors"].append(f"{url}: response too large"); continue
            final_url = str(response.url)
            if not await robots_allowed(website, final_url): continue
            page = extract_page(final_url, response.content); result["website"]["pages"].append(page)
            for link in page["internal_links"]:
                if link not in seen and link not in queue: queue.append(link)
        except Exception as exc:
            result["website"]["errors"].append(f"{url}: {type(exc).__name__}")
    pages = result["website"]["pages"]
    if not pages:
        result["problems"].append("Website could not be successfully researched."); result["seo"] = {"score": 0, "reason": "No readable pages"}; return result
    home = pages[0]; score = 100
    if not home["title"]: score -= 20; result["problems"].append("Homepage title is missing.")
    if not home["description"]: score -= 15; result["problems"].append("Homepage meta description is missing.")
    if not home["schema"]: score -= 5; result["problems"].append("JSON-LD structured data was not detected on the homepage.")
    if not home["mobile_viewport"]: score -= 15; result["problems"].append("Mobile viewport metadata was not detected.")
    if not home["headings"]: score -= 10; result["problems"].append("No heading structure was detected on the homepage.")
    result["seo"] = {"score": max(0, score), "title_present": bool(home["title"]), "description_present": bool(home["description"]), "schema": home["schema"], "mobile_viewport": home["mobile_viewport"]}
    result["local"] = {"phone_found": bool(home["phones"]), "email_found": bool(home["emails"]), "city": business.get("city")}
    result["technology"] = {"signals": sorted(set(x for p in pages for x in p.get("technology", [])))}
    return result
