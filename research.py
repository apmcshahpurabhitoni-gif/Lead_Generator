import re
from urllib.parse import urljoin, urlparse
from typing import Any

from bs4 import BeautifulSoup

from discovery import normalize_website, permitted_get

MAX_PAGES = 7
MAX_BYTES = 2_000_000


def extract_page(url: str, html: bytes) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description = ""
    meta = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta:
        description = (meta.get("content") or "").strip()

    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])][:30]
    links: list[str] = []
    host = urlparse(url).netloc
    for a in soup.find_all("a", href=True):
        target = urljoin(url, a["href"])
        if urlparse(target).netloc == host:
            links.append(target.split("#", 1)[0])

    text = soup.get_text(" ", strip=True)
    phones = re.findall(r"(?:\+91[\s-]?)?[6-9]\d{9}", text)
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)

    return {
        "url": url,
        "title": title,
        "description": description,
        "headings": headings,
        "internal_links": sorted(set(links)),
        "schema": bool(soup.find("script", attrs={"type": "application/ld+json"})),
        "mobile_viewport": bool(soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})),
        "phones": list(dict.fromkeys(phones))[:5],
        "emails": list(dict.fromkeys(emails))[:5],
        "text_length": len(text),
    }


async def research_business(business: dict[str, Any]) -> dict[str, Any]:
    website = normalize_website(business.get("website"))
    result: dict[str, Any] = {
        "website": {"exists": bool(website), "pages": [], "errors": []},
        "seo": {},
        "local": {},
        "search": {"status": "NOT_CONFIGURED"},
        "technology": {"signals": []},
        "buying_signals": [],
        "problems": [],
    }

    if not website:
        result["problems"].append("No business website was supplied by the discovery source.")
        result["seo"] = {"score": 0, "reason": "No website"}
        return result

    queue = [website]
    seen: set[str] = set()
    while queue and len(seen) < MAX_PAGES:
        url = queue.pop(0)
        parsed = urlparse(url)
        if parsed.netloc != urlparse(website).netloc or url in seen:
            continue
        seen.add(url)
        try:
            response = await permitted_get(url, timeout=15)
            if len(response.content) > MAX_BYTES:
                result["website"]["errors"].append(f"{url}: response too large")
                continue
            final_url = str(response.url)
            page = extract_page(final_url, response.content)
            result["website"]["pages"].append(page)
            for link in page["internal_links"][:25]:
                if link not in seen and link not in queue:
                    queue.append(link)
        except Exception as exc:
            result["website"]["errors"].append(f"{url}: {type(exc).__name__}")

    pages = result["website"]["pages"]
    if not pages:
        result["problems"].append("Website could not be successfully researched.")
        return result

    home = pages[0]
    seo_score = 100
    if not home["title"]:
        seo_score -= 20
        result["problems"].append("Homepage title is missing.")
    if not home["description"]:
        seo_score -= 15
        result["problems"].append("Homepage meta description is missing.")
    if not home["schema"]:
        seo_score -= 5
        result["problems"].append("JSON-LD structured data was not detected on the homepage.")
    if not home["mobile_viewport"]:
        seo_score -= 15
        result["problems"].append("Mobile viewport metadata was not detected.")
    if not any(h.strip() for h in home["headings"]):
        seo_score -= 10
        result["problems"].append("No useful heading structure was detected on the homepage.")

    result["seo"] = {
        "score": max(0, seo_score),
        "title_present": bool(home["title"]),
        "description_present": bool(home["description"]),
        "schema": home["schema"],
        "mobile_viewport": home["mobile_viewport"],
    }
    result["local"] = {
        "phone_found": bool(home["phones"]),
        "email_found": bool(home["emails"]),
        "profile_optimized": True,
        "city": business.get("city"),
    }
    return result
