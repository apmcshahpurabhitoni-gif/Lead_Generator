SERVICE_NAMES=["SEO","GEO","AEO","Google Business Profile","EPR","Websites","Automations","AI Integration","Custom Software","BigQuery","Cloud"]
STATUS_VALUES=["NEW","RESEARCHED","QUALIFIED","CONTACTED","RESPONDED","MEETING","PROPOSAL","NEGOTIATION","WON","LOST","NOT_INTERESTED","DO_NOT_CONTACT"]

def score_lead(research:dict)->dict:
    score=40; reasons=list(research.get("problems",[])); website=research.get("website",{}); seo=research.get("seo",{}); local=research.get("local",{}); buying=research.get("buying_signals",[])
    if not website.get("exists"): score+=25
    else:
        s=int(seo.get("score",100)); score += 20 if s<50 else 10 if s<75 else 0
    if not local.get("phone_found"): reasons.append("No business phone was detected in researched homepage content.")
    score+=min(10,len(buying)*3); score=max(0,min(100,score))
    priority="HOT" if score>=80 else "HIGH" if score>=60 else "MEDIUM" if score>=40 else "LOW"
    services=[]; s=int(seo.get("score",100))
    if not website.get("exists"): services.append("Websites")
    if s<75: services.append("SEO")
    if s<60: services.extend(["AEO","GEO"])
    if local.get("profile_optimized") is False: services.append("Google Business Profile")
    if buying: services.append("Automations")
    return {"score":score,"priority":priority,"recommended_services":list(dict.fromkeys(services)),"reasons":reasons[:20]}
