SERVICE_NAMES=["SEO","GEO","AEO","Google Business Profile","EPR","Websites","Automations","AI Integration","Custom Software","BigQuery","Cloud"]
STATUS_VALUES=["NEW","RESEARCHED","QUALIFIED","CONTACTED","RESPONDED","MEETING","PROPOSAL","NEGOTIATION","WON","LOST","NOT_INTERESTED","DO_NOT_CONTACT"]

def score_lead(research:dict)->dict:
    website=research.get("website",{}); seo=research.get("seo",{}); local=research.get("local",{}); google=research.get("google",{}); buying=research.get("buying_signals",[])
    score=30; breakdown=[("Base opportunity",30)]
    reasons=list(research.get("problems",[]))
    if not website.get("exists"):
        score+=30; breakdown.append(("No verified website",30)); reasons.append("No verified official website was found.")
    else:
        s=int(seo.get("score",100) or 0); bonus=20 if s<50 else 12 if s<75 else 0; score+=bonus; breakdown.append((f"Website SEO quality {s}/100",bonus))
    if not local.get("phone_found"): score+=5; breakdown.append(("No visible phone",5)); reasons.append("No public business phone was found in the researched sources.")
    if not local.get("email_found"): score+=5; breakdown.append(("No visible email",5)); reasons.append("No public business email was found in the researched sources.")
    rank=google.get("local_rank")
    if rank:
        bonus=12 if rank>10 else 8 if rank>5 else 3
        score+=bonus; breakdown.append((f"Google local position #{rank}",bonus))
        if rank>5: reasons.append(f"Google local search position is #{rank} for the tested query.")
    score+=min(8,len(buying)*2); breakdown.append(("Buying signals",min(8,len(buying)*2))) if buying else None
    score=max(0,min(100,score))
    priority="HOT" if score>=80 else "HIGH" if score>=60 else "MEDIUM" if score>=40 else "LOW"
    services=[]; s=int(seo.get("score",100) or 0)
    if not website.get("exists"): services.append("Websites")
    if website.get("exists") and s<75: services.append("SEO")
    if website.get("exists") and s<60: services.extend(["AEO","GEO"])
    if rank and rank>5: services.append("Google Business Profile")
    if buying: services.append("Automations")
    return {"score":score,"priority":priority,"recommended_services":list(dict.fromkeys(services)),"reasons":reasons[:20],"breakdown":breakdown}
