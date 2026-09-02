"""LeadHunter V11 runtime hardening over the V10 workspace.

V10's visual structure is retained. V11 fixes the mobile blank-screen failure
by rendering a fallback immediately, loading the lead list from a lightweight
endpoint, and booting the UI before waiting for network data.
"""
import asyncio
from fastapi import Header, Query
import dashboard_v10 as _base
router=_base.router

@router.get('/dashboard/api/leads_fast')
async def leads_fast(authorization:str|None=Header(default=None),limit:int=Query(100,ge=1,le=200)):
    _base.auth(authorization); db=_base._base.Database(); rows=await db.list_leads(None,limit,0)
    async def enrich(row):
        try: row['research']=await db.get_research(int(row['id']))
        except Exception: row['research']={}
        return row
    rows=await asyncio.gather(*(enrich(x) for x in rows))
    return {'ok':True,'leads':rows,'count':len(rows)}

PAGE=_base.PAGE
# The browser must paint useful content before API calls complete.
PAGE=PAGE.replace(
    '<section class="view active" id="leads"></section>',
    '<section class="view active" id="leads"><div class="head"><div class="eyebrow">Lead workspace</div><h1>Your leads.</h1><div class="sub">Loading your saved searches and leads…</div></div><div class="section"><div class="empty">⏳ Loading LeadHunter workspace…</div></div></section>'
)
# Avoid the expensive V6 endpoint that performs two database queries per lead.
PAGE=PAGE.replace("/dashboard/api/leads?limit=1000", "/dashboard/api/leads_fast?limit=100")
# Paint the navigation and current page immediately, then hydrate asynchronously.
PAGE=PAGE.replace(
    "(async()=>{applyTheme();try{await load();render()}catch(e){toast('⚠️ '+e.message);render()}})();",
    "(function(){applyTheme();render();load().then(()=>render()).catch(e=>{toast('⚠️ '+e.message);render()})})();"
)
_base.PAGE=PAGE
