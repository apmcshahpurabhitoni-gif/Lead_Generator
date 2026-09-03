from constants import PIPELINE_STATUSES, SERVICE_NAMES
STATUS_VALUES = PIPELINE_STATUSES

# Business-type-specific presence rules. These are sales-audit rules, not claims that
# every business must be listed on every platform. Conditional sources only apply
# when the business actually offers the matching service/channel.
PRESENCE_MATRIX={
 "dental":{"required":["google_business","website"],"recommended":["practo","justdial","instagram","facebook"],"conditional":["lybrate"]},
 "hospital":{"required":["google_business","website"],"recommended":["practo","justdial","sulekha","facebook"],"conditional":["youtube","instagram"]},
 "clinic":{"required":["google_business","website"],"recommended":["practo","justdial","sulekha","facebook"],"conditional":["lybrate","instagram"]},
 "pharmacy":{"required":["google_business"],"recommended":["justdial","sulekha","facebook","instagram"],"conditional":["website","zomato","swiggy"]},
 "veterinary":{"required":["google_business","website"],"recommended":["justdial","sulekha","facebook","instagram"],"conditional":["youtube"]},
 "restaurant":{"required":["google_business"],"recommended":["website","zomato","instagram","facebook"],"conditional":["swiggy","justdial"]},
 "cafe":{"required":["google_business"],"recommended":["website","zomato","instagram","facebook"],"conditional":["swiggy","justdial"]},
 "bakery":{"required":["google_business"],"recommended":["website","instagram","facebook","zomato"],"conditional":["swiggy","indiamart"]},
 "hotel":{"required":["google_business","website"],"recommended":["booking","makemytrip","goibibo","tripadvisor","instagram","facebook"],"conditional":["agoda"]},
 "resort":{"required":["google_business","website"],"recommended":["booking","makemytrip","goibibo","tripadvisor","instagram","facebook"],"conditional":["weddingwire"]},
 "school":{"required":["google_business","website"],"recommended":["edustoke","schoolmykids","facebook","instagram"],"conditional":["youtube"]},
 "college":{"required":["google_business","website"],"recommended":["facebook","instagram","youtube"],"conditional":["linkedin"]},
 "university":{"required":["google_business","website"],"recommended":["facebook","instagram","youtube","linkedin"],"conditional":[]},
 "gym":{"required":["google_business"],"recommended":["website","instagram","facebook","justdial","sulekha"],"conditional":["youtube"]},
 "salon":{"required":["google_business","instagram"],"recommended":["website","facebook","justdial"],"conditional":["sulekha"]},
 "beauty":{"required":["google_business","instagram"],"recommended":["website","facebook","justdial","sulekha"],"conditional":[]},
 "car dealer":{"required":["google_business","website"],"recommended":["cardekho","carwale","facebook","instagram"],"conditional":["manufacturer"]},
 "car repair":{"required":["google_business"],"recommended":["website","justdial","sulekha","facebook","instagram"],"conditional":["cardekho"]},
 "car wash":{"required":["google_business"],"recommended":["justdial","sulekha","instagram","facebook"],"conditional":["website"]},
 "real estate":{"required":["google_business","website"],"recommended":["99acres","magicbricks","housing","nobroker","instagram","facebook"],"conditional":["linkedin"]},
 "lawyer":{"required":["google_business","website"],"recommended":["justdial","sulekha","linkedin"],"conditional":["facebook"]},
 "accountant":{"required":["google_business","website"],"recommended":["linkedin","justdial","sulekha"],"conditional":["indiamart"]},
 "insurance":{"required":["google_business","website"],"recommended":["linkedin","justdial","sulekha"],"conditional":["facebook","instagram"]},
 "travel agency":{"required":["google_business","website"],"recommended":["instagram","facebook","justdial","sulekha"],"conditional":["tripadvisor"]},
 "electronics":{"required":["google_business"],"recommended":["website","justdial","facebook","instagram"],"conditional":["indiamart"]},
 "clothing":{"required":["google_business","instagram"],"recommended":["website","facebook","justdial"],"conditional":[]},
 "furniture":{"required":["google_business","website"],"recommended":["instagram","facebook","justdial"],"conditional":["indiamart"]},
 "jewellery":{"required":["google_business","instagram"],"recommended":["website","facebook","justdial"],"conditional":[]},
 "supermarket":{"required":["google_business"],"recommended":["website","justdial","facebook","instagram"],"conditional":["swiggy","zomato"]},
 "hardware":{"required":["google_business"],"recommended":["justdial","sulekha","website","facebook"],"conditional":["indiamart"]},
 "bank":{"required":["google_business","website"],"recommended":["official_branch_locator"],"conditional":["facebook","linkedin"]},
 "architect":{"required":["google_business","website"],"recommended":["instagram","linkedin","justdial","sulekha"],"conditional":["houzz"]},
 "construction":{"required":["google_business","website"],"recommended":["justdial","sulekha","linkedin","facebook"],"conditional":["indiamart"]},
 "printing":{"required":["google_business"],"recommended":["justdial","sulekha","website","instagram","facebook"],"conditional":["indiamart"]},
 "photographer":{"required":["google_business","website","instagram"],"recommended":["facebook","justdial"],"conditional":["weddingwire"]},
 "fuel":{"required":["google_business"],"recommended":["official_fuel_locator","justdial"],"conditional":["website"]},
 "all":{"required":["google_business"],"recommended":["website","facebook","instagram"],"conditional":[]},
}
PROFILE_LABELS={"google_business":"Google Business Profile","website":"Official Website","practo":"Practo","justdial":"Justdial","sulekha":"Sulekha","lybrate":"Lybrate","zomato":"Zomato","swiggy":"Swiggy","instagram":"Instagram","facebook":"Facebook","youtube":"YouTube","linkedin":"LinkedIn","booking":"Booking.com","makemytrip":"MakeMyTrip","goibibo":"Goibibo","tripadvisor":"Tripadvisor","agoda":"Agoda","weddingwire":"WeddingWire","edustoke":"Edustoke","schoolmykids":"SchoolMyKids","cardekho":"CarDekho","carwale":"CarWale","manufacturer":"Manufacturer dealer page","99acres":"99acres","magicbricks":"MagicBricks","housing":"Housing.com","nobroker":"NoBroker","indiamart":"IndiaMART","official_branch_locator":"Official branch locator","official_fuel_locator":"Official fuel-company locator","houzz":"Houzz"}

def _infer_industry(research):
    value=str(research.get("industry") or "").strip().lower()
    if value in PRESENCE_MATRIX: return value
    query=str((research.get("search") or {}).get("query") or "").lower()
    for key in sorted(PRESENCE_MATRIX,key=len,reverse=True):
        if key != "all" and key in query: return key
    return "all"

def _presence_audit(research):
    industry=_infer_industry(research); rules=PRESENCE_MATRIX.get(industry,PRESENCE_MATRIX["all"])
    profiles=research.get("profiles") or {}; website=research.get("website") or {}; google=research.get("google") or {}
    found=set(profiles)
    if website.get("exists"): found.add("website")
    if google.get("local_rank") or google.get("maps_url"): found.add("google_business")
    audit={}
    for tier,keys in (("required",rules["required"]),("recommended",rules["recommended"]),("conditional",rules["conditional"])):
        for key in keys:
            audit[key]={"tier":tier,"label":PROFILE_LABELS.get(key,key.replace("_"," ").title()),"status":"FOUND" if key in found else "NOT_FOUND_ON_CHECKED_SOURCES","checked_via":"google_places" if key=="google_business" else "business_website_links"}
    applicable=[v for v in audit.values() if v["tier"]!="conditional"]
    found_count=sum(v["status"]=="FOUND" for v in applicable)
    presence_score=round(100*found_count/len(applicable)) if applicable else 100
    missing_required=[v["label"] for v in audit.values() if v["tier"]=="required" and v["status"]!="FOUND"]
    missing_recommended=[v["label"] for v in audit.values() if v["tier"]=="recommended" and v["status"]!="FOUND"]
    return {"business_type":industry,"rules":rules,"audit":audit,"presence_score":presence_score,"missing_required":missing_required,"missing_recommended":missing_recommended,"note":"NOT_FOUND_ON_CHECKED_SOURCES means the source was not found through the permitted checks; it is not proof that the business is unregistered there."}

def score_lead(research: dict) -> dict:
    website = research.get("website") or {}
    seo = research.get("seo") or {}
    local = research.get("local") or {}
    google = research.get("google") or {}
    buying = research.get("buying_signals") or []
    score = 25
    breakdown = [("Base opportunity", 25)]
    reasons = list(research.get("problems") or [])

    if not website.get("exists"):
        score += 22
        breakdown.append(("No verified official website", 22))
        reasons.append("No verified official website was found from the available discovery sources.")
    else:
        seo_score = int(seo.get("score", 0) or 0)
        bonus = 18 if seo_score < 50 else 10 if seo_score < 75 else 0
        if bonus:
            score += bonus
            breakdown.append((f"Website SEO quality {seo_score}/100", bonus))
        if seo_score < 75:
            reasons.append(f"Website has basic technical/SEO gaps (audit score {seo_score}/100).")

    # Directory absence is not scored: the crawler only knows what was checked on
    # the business's own website, not whether a protected third-party listing exists.
    presence = _presence_audit(research)

    if not local.get("phone_found"):
        score += 4
        breakdown.append(("No publicly found phone", 4))
        reasons.append("No public business phone was found in the researched sources.")
    if not local.get("email_found"):
        score += 3
        breakdown.append(("No publicly found email", 3))
        reasons.append("No public business email was found in the researched sources.")

    rank = google.get("local_rank")
    if rank:
        bonus = 10 if int(rank) > 10 else 6 if int(rank) > 5 else 2
        score += bonus
        breakdown.append((f"Provider result position #{int(rank)}", bonus))
        if int(rank) > 5:
            reasons.append(f"Google Places result position is #{int(rank)} for the tested discovery query.")

    buying_bonus = min(6, len(buying) * 2)
    if buying_bonus:
        score += buying_bonus
        breakdown.append(("Verified buying signals", buying_bonus))

    score = max(0, min(100, score))
    priority = "HOT" if score >= 80 else "HIGH" if score >= 60 else "MEDIUM" if score >= 40 else "LOW"
    services = []
    seo_score = int(seo.get("score", 0) or 0)
    if not website.get("exists"):
        services.append("Websites")
    elif seo_score < 75:
        services.append("SEO")
    if website.get("exists") and seo_score < 60:
        services.extend(["AEO", "GEO"])
    if rank and int(rank) > 5:
        services.append("Google Business Profile")
    if buying:
        services.append("Automations")

    return {
        "score": score, "priority": priority,
        "recommended_services": list(dict.fromkeys(services)),
        "reasons": reasons[:20], "breakdown": breakdown,
        "presence": presence,
        "confidence": _confidence(research),
    }

def _confidence(research: dict) -> int:
    website = research.get("website") or {}
    if not research:
        return 0
    if website.get("exists") and website.get("pages"):
        return 90 if not website.get("errors") else 75
    if research.get("google") or research.get("local"):
        return 55
    return 30

