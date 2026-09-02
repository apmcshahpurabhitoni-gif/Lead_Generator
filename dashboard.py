import base64, os, secrets
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse
from database import Database
router=APIRouter()

def authorized(value:str|None)->bool:
    user=os.getenv("DASHBOARD_USER",""); password=os.getenv("DASHBOARD_PASSWORD","")
    if not user or not password or not value or not value.startswith("Basic "): return False
    try:
        decoded=base64.b64decode(value[6:]).decode(); supplied_user,supplied_password=decoded.split(":",1)
        return secrets.compare_digest(supplied_user,user) and secrets.compare_digest(supplied_password,password)
    except Exception: return False

@router.get("/dashboard",response_class=HTMLResponse)
async def dashboard(authorization:str|None=Header(default=None)):
    if not authorized(authorization): raise HTTPException(status_code=401,detail="Dashboard authentication required",headers={"WWW-Authenticate":"Basic"})
    db=Database(); stats=await db.today_stats(); history=await db.history(14)
    cards=[("🔎","Leads",stats["leads_found"]),("🎯","Qualified",stats["qualified"]),("🔥","Hot",stats["hot_leads"]),("📞","Calls",stats["calls"]),("💬","Contacted",stats["contacted"]),("↩️","Replies",stats["replies"]),("📅","Meetings",stats["meetings"]),("📄","Proposals",stats["proposals"]),("💰","Won",stats["won"]),("❌","Lost",stats["lost"])]
    cards_html="".join(f'<div class="card"><div>{icon} {label}</div><strong>{value}</strong></div>' for icon,label,value in cards)
    rows="".join(f'<tr><td>{r.get("date","")}</td><td>{r.get("leads_found",0)}</td><td>{r.get("contacted",0)}</td><td>{r.get("replies",0)}</td><td>{r.get("meetings",0)}</td><td>{r.get("won",0)}</td></tr>' for r in history)
    return HTMLResponse(f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LeadHunter</title><style>body{{font-family:system-ui,Arial;max-width:1100px;margin:25px auto;padding:0 16px;background:#f5f7fb;color:#172033}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}}.card{{background:#fff;padding:16px;border-radius:14px;box-shadow:0 2px 10px #0000000d}}strong{{display:block;font-size:30px;margin-top:6px}}table{{width:100%;background:#fff;border-collapse:collapse}}th,td{{padding:12px;border-bottom:1px solid #eee;text-align:left}}.muted{{color:#697386}}</style></head><body><h1>🚀 LeadHunter</h1><p class="muted">Private daily sales activity</p><div class="grid">{cards_html}</div><h2>📈 14-day history</h2><table><thead><tr><th>Date</th><th>Leads</th><th>Contacted</th><th>Replies</th><th>Meetings</th><th>Won</th></tr></thead><tbody>{rows or '<tr><td colspan="6">No history yet.</td></tr>'}</tbody></table></body></html>''')
