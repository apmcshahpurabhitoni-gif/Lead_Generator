"""LeadHunter dashboard visual system over the working dashboard_v6 router.

This file intentionally keeps dashboard_v6's backend, discovery flow and data
rendering intact. It only replaces the presentation layer so the dashboard is
clean, responsive and readable on mobile.
"""
import dashboard_v6 as _base

CSS = r'''
/* ================================================================
   LeadHunter V8 — visual system
   ================================================================ */
:root{
  --bg:#f5f1e8;--surface:#fffdf8;--surface2:#eee9df;--surface3:#e7e1d6;
  --text:#17191c;--muted:#70777d;--line:#20252a;--softline:#c9c2b7;
  --accent:#7050ff;--accent2:#08aeb9;--green:#087a4b;--yellow:#9a7200;
  --red:#b42336;--shadow:#17191c;--focus:#7050ff;--radius:18px
}

/* Four real looks. The existing dashboard keeps its functionality; these
   classes only change the visual language. */
body.theme-light-modern{
  --bg:#f5f1e8;--surface:#fffdf8;--surface2:#eee9df;--surface3:#e5ded1;
  --text:#17191c;--muted:#6d747a;--line:#20252a;--softline:#cbc4b9;
  --accent:#7050ff;--accent2:#08aeb9;--green:#087a4b;--yellow:#986f00;
  --red:#b42336;--shadow:#17191c
}
body.theme-dark-modern{
  --bg:#0b1117;--surface:#111b24;--surface2:#172530;--surface3:#1c2d3a;
  --text:#f5f7f8;--muted:#9baab4;--line:#dce4e8;--softline:#465865;
  --accent:#8b72ff;--accent2:#22d2dc;--green:#35d79a;--yellow:#ffd45a;
  --red:#ff7180;--shadow:#020508
}
body.theme-light-neo{
  --bg:#eee7d8;--surface:#fffaf0;--surface2:#e6ddcd;--surface3:#ded4c2;
  --text:#171717;--muted:#625d55;--line:#171717;--softline:#8d8478;
  --accent:#ff5b35;--accent2:#00a9b8;--green:#087a4b;--yellow:#a06c00;
  --red:#b42336;--shadow:#171717
}
body.theme-dark-neo{
  --bg:#090b10;--surface:#12161e;--surface2:#1b202a;--surface3:#242b35;
  --text:#f6f7f9;--muted:#9ba5b3;--line:#f0f2f5;--softline:#596575;
  --accent:#ffcf33;--accent2:#35d9e3;--green:#3ee7a3;--yellow:#ffd45a;
  --red:#ff6678;--shadow:#000
}

html,body{background:var(--bg)!important;color:var(--text)!important}
body{transition:background .25s ease,color .25s ease}

/* ---------- Header ---------- */
.topbar{
  position:relative;isolation:isolate;overflow:visible!important;
  border:1.5px solid var(--line)!important;border-radius:22px!important;
  background:var(--surface)!important;box-shadow:5px 6px 0 var(--shadow)!important;
  padding:14px 16px!important
}
.brand{gap:12px!important}.logo{border-color:var(--line)!important;background:linear-gradient(135deg,#e8ddff,#dff8f5)!important}
.brand b{font-size:18px!important;letter-spacing:-.02em}.brand small{letter-spacing:.16em!important}
.top-actions{gap:7px!important}.iconbtn,.btn{border-color:var(--line)!important;background:var(--surface)!important;color:var(--text)!important}
.btn.primary{background:var(--text)!important;color:var(--surface)!important;box-shadow:3px 3px 0 var(--shadow)!important}

/* Theme picker */
.appearance{position:relative}.appearance-toggle{
  min-height:43px;padding:8px 12px;border:1.5px solid var(--line);border-radius:13px;
  background:var(--surface);color:var(--text);font-weight:850;display:inline-flex;
  align-items:center;gap:7px;cursor:pointer;white-space:nowrap
}
.appearance-menu{
  position:absolute;right:0;top:51px;z-index:200;display:none;width:292px;padding:11px;
  border:1.5px solid var(--line);border-radius:17px;background:var(--surface);
  box-shadow:7px 8px 0 var(--shadow)
}
.appearance.open .appearance-menu{display:block;animation:pop .16s ease-out}
.appearance-menu h4{margin:2px 4px 9px;font-size:10px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted)}
.theme-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.theme-choice{
  min-height:72px;border:1.5px solid var(--softline);background:var(--surface2);color:var(--text);
  border-radius:13px;padding:10px;text-align:left;cursor:pointer;font-weight:800;transition:.16s
}.theme-choice:hover{transform:translateY(-1px);border-color:var(--accent)}
.theme-choice b{display:block;font-size:11px}.theme-choice small{display:block;margin-top:3px;color:var(--muted);font-size:9px;font-weight:650}
.theme-choice.active{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent);background:color-mix(in srgb,var(--accent) 12%,var(--surface))}

/* ---------- Navigation / page header ---------- */
.nav{margin:18px 0 28px!important;gap:8px!important}.nav button{padding:9px 12px!important;color:var(--muted)!important}
.nav button.active{background:var(--text)!important;color:var(--surface)!important;border-color:var(--text)!important}
.pagehead{margin-bottom:4px}.eyebrow{color:var(--accent)!important;font-size:10px!important;letter-spacing:.19em!important}
h1{font-weight:950!important;letter-spacing:-.055em!important}.sub{font-size:15px!important;line-height:1.55!important}

/* ---------- Search workspace ---------- */
.workspace{
  border:1.5px solid var(--line)!important;border-radius:20px!important;background:var(--surface)!important;
  box-shadow:4px 5px 0 color-mix(in srgb,var(--shadow) 14%,transparent)!important;padding:13px!important
}
.searchrow input{background:var(--bg)!important;color:var(--text)!important;border-color:var(--line)!important}
.searchrow input::placeholder{color:var(--muted)!important}.filters{gap:8px!important}
.pill{background:var(--surface)!important;color:var(--text)!important;border-color:var(--softline)!important}
.pill.active{background:color-mix(in srgb,var(--accent) 14%,var(--surface))!important;border-color:var(--accent)!important}

/* ---------- Lead list / collapsed cards ---------- */
.lead{
  border:1.5px solid var(--line)!important;border-radius:18px!important;background:var(--surface)!important;
  margin-top:10px!important;overflow:hidden!important;transition:box-shadow .2s,transform .2s
}
.lead:hover{transform:translateY(-1px)}.lead.open{box-shadow:5px 6px 0 var(--shadow)!important;transform:none}
.summary{
  min-height:76px;grid-template-columns:minmax(0,2.5fr) 90px 82px 28px!important;
  gap:10px!important;padding:12px 13px!important;background:var(--surface);cursor:pointer
}
.name{font-size:15px!important;font-weight:950!important}.subline{font-size:11px!important;color:var(--muted)!important}
.score{font-size:16px!important;font-weight:950!important}.priority{font-size:9px!important;padding:5px 8px!important}
.chev{color:var(--muted);font-size:17px!important}

/* ---------- Expanded lead ---------- */
.details{
  display:block!important;max-height:0;overflow:hidden;opacity:0;padding:0 12px!important;
  border-top:0!important;transition:max-height .42s cubic-bezier(.2,.8,.2,1),opacity .2s ease,padding .25s ease
}
.lead.open .details{max-height:6000px;opacity:1;padding:13px 12px 16px!important;border-top:1.5px solid var(--line)!important}
.hero{
  border:1.5px solid var(--line)!important;border-radius:17px!important;
  background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 10%,var(--surface)),color-mix(in srgb,var(--accent2) 12%,var(--surface)))!important;
  padding:16px!important
}
.hero h2{font-size:24px!important;font-weight:950!important;letter-spacing:-.035em!important}.badges{margin-top:9px!important}
.badge{background:color-mix(in srgb,var(--surface) 72%,transparent)!important;border-color:var(--line)!important}

/* The original importance block is the single source of truth for the four
   sales-critical signals. The previous V8 injected a second, text-parsing
   copy of these cards; that caused the broken strings visible in the screenshots.
   Keep one clean block and never duplicate it. */
.importance{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:8px!important;margin-top:9px!important}
.imp{
  position:relative;min-height:92px;border:1.5px solid var(--line)!important;border-radius:14px!important;
  background:var(--surface)!important;padding:12px!important;overflow:hidden
}
.imp:before{display:block;font-size:19px;line-height:1;margin-bottom:7px}
.imp:nth-child(1):before{content:'📍'}.imp:nth-child(2):before{content:'🌐'}.imp:nth-child(3):before{content:'📞'}.imp:nth-child(4):before{content:'✉️'}
.imp b{font-size:9px!important;letter-spacing:.12em!important;color:var(--muted)!important}.imp strong{font-size:16px!important;font-weight:950!important;margin-top:4px!important;overflow-wrap:anywhere}
.imp:nth-child(1){border-color:var(--accent2)!important}.imp:nth-child(2){border-color:var(--green)!important}.imp:nth-child(3){border-color:var(--green)!important}.imp:nth-child(4){border-color:var(--green)!important}
.good{color:var(--green)!important}.bad{color:var(--red)!important}.warn{color:var(--yellow)!important}

/* ---------- Detail sections ---------- */
.grid2{gap:9px!important}.section{
  border:1.5px solid var(--line)!important;border-radius:16px!important;background:var(--surface)!important;
  padding:13px!important;margin-top:9px!important
}
.section h3{font-size:10px!important;letter-spacing:.15em!important;margin-bottom:10px!important;color:var(--text)!important}
.facts{gap:8px!important}.facts b{font-size:11px!important;color:var(--muted)!important}.facts span{font-size:12px!important}
.chips,.services,.links{gap:7px!important}.chip,.service,.link{border-color:var(--softline)!important;border-radius:10px!important;padding:7px 9px!important}
.chip{background:color-mix(in srgb,var(--red) 9%,var(--surface))!important;color:var(--text)!important}
.service{background:color-mix(in srgb,var(--green) 10%,var(--surface))!important;color:var(--green)!important}
.link{background:var(--bg)!important}.link:hover{border-color:var(--accent)!important}
.evidence{gap:7px!important}.evidence div{background:var(--bg)!important;border:1px solid var(--softline)!important;border-left:4px solid var(--accent)!important;border-radius:10px!important;padding:9px 10px!important}
/* Pitch block: make it an actual sales explanation, not a giant yellow wall. */
.section .pitch,.pitch{background:color-mix(in srgb,var(--yellow) 13%,var(--surface))!important;border-color:color-mix(in srgb,var(--yellow) 65%,var(--line))!important}
.telegram{background:color-mix(in srgb,var(--accent2) 12%,var(--surface))!important;border:1.5px solid var(--accent2)!important;border-radius:15px 15px 15px 5px!important}
.telegram p{font-size:13px!important;line-height:1.55!important}.telegram time{font-size:9px!important}
.stage{gap:8px!important}.stage select{background:var(--surface)!important;color:var(--text)!important;border-color:var(--line)!important}
.actionsline{gap:7px!important}.activity{gap:7px!important}.act{background:var(--bg)!important;border-color:var(--softline)!important;border-radius:0 12px 12px 12px!important;padding:10px!important}
.act b{font-size:12px!important}.act small{font-size:10px!important}

/* ---------- Panels / metrics ---------- */
.metric{border-color:var(--line)!important;background:var(--surface)!important}.metric small{color:var(--muted)!important}
.panel{border-color:var(--line)!important;background:var(--surface)!important}.field select{background:var(--bg)!important;color:var(--text)!important;border-color:var(--line)!important}

/* ---------- Mobile ---------- */
@media(max-width:1050px){
  .summary{grid-template-columns:minmax(0,1fr) 86px 28px!important}.summary .subline{display:block!important}
  .importance{grid-template-columns:repeat(2,minmax(0,1fr))!important}
}
@media(max-width:700px){
  .shell{padding:8px 8px 82px!important}.topbar{border-radius:17px!important;padding:9px 10px!important;box-shadow:3px 4px 0 var(--shadow)!important}
  .logo{width:42px!important;height:42px!important}.brand b{font-size:16px!important}.brand small{font-size:9px!important}
  .appearance-toggle{min-height:39px;font-size:12px;padding:7px 9px}.appearance-menu{position:fixed;right:9px;top:72px;width:min(308px,calc(100vw - 18px))}
  .nav{margin:12px 0 18px!important;scrollbar-width:none}.nav::-webkit-scrollbar{display:none}.nav button{font-size:12px!important;padding:8px 9px!important}
  .pagehead h1{font-size:34px!important;line-height:.99!important}.sub{font-size:14px!important}.metrics{gap:6px!important;margin:15px 0!important}
  .metric{min-height:84px!important;padding:10px!important}.metric strong{font-size:22px!important}
  .workspace{border-radius:17px!important;padding:9px!important}.searchrow{grid-template-columns:minmax(0,1fr) auto!important}.searchrow input{min-height:47px!important;font-size:14px!important}
  .summary{grid-template-columns:minmax(0,1fr) 58px 23px!important;min-height:74px!important;padding:11px!important;gap:7px!important}
  .summary .priority{display:none!important}.summary .score{font-size:13px!important}.name{font-size:14px!important}.subline{font-size:10px!important}
  .details{padding:0 8px!important}.lead.open .details{padding:9px 8px 13px!important}
  .hero{padding:13px!important}.hero h2{font-size:20px!important}.badges{gap:5px!important}.badge{font-size:10px!important;padding:6px 8px!important}
  .importance{grid-template-columns:1fr 1fr!important;gap:7px!important}.imp{min-height:101px!important;padding:11px!important}.imp strong{font-size:14px!important;line-height:1.25}
  .grid2{grid-template-columns:1fr!important}.section{padding:12px!important;border-radius:15px!important}.facts{grid-template-columns:92px 1fr!important}
  .mobile-bottom{display:flex!important;left:8px!important;right:8px!important;bottom:7px!important;border-radius:17px!important;box-shadow:4px 5px 0 var(--shadow)!important;background:var(--surface)!important}
  .mobile-bottom button{font-size:10px!important;padding:9px 3px!important}.toast{left:12px!important;right:12px!important;bottom:14px!important}
}
@media(max-width:390px){.appearance-toggle span{display:none}.summary{grid-template-columns:minmax(0,1fr) 52px 20px!important}.importance{gap:6px!important}.imp{min-height:96px!important}.imp b{font-size:8px!important}}

/* Neo looks are intentionally tactile and more playful, while modern looks
   stay quieter. */
body.theme-light-neo .topbar,body.theme-light-neo .workspace,body.theme-light-neo .lead,body.theme-light-neo .panel,body.theme-light-neo .metric,body.theme-light-neo .section,body.theme-light-neo .modalbox{box-shadow:5px 6px 0 var(--shadow)!important}
body.theme-light-neo .btn,body.theme-light-neo .iconbtn,body.theme-light-neo .pill{border-width:2px!important}
body.theme-dark-neo .topbar,body.theme-dark-neo .workspace,body.theme-dark-neo .lead,body.theme-dark-neo .panel,body.theme-dark-neo .metric,body.theme-dark-neo .section,body.theme-dark-neo .modalbox{box-shadow:5px 6px 0 var(--shadow)!important}
body.theme-dark-neo .btn.primary{background:var(--accent)!important;color:#111!important}

@keyframes pop{from{opacity:0;transform:translateY(-5px) scale(.98)}to{opacity:1;transform:none}}
'''

HTML = r'''
<div class="appearance" id="appearance">
  <button class="appearance-toggle" type="button" onclick="toggleAppearance()" aria-expanded="false" aria-haspopup="true">
    🎨 <span id="appearanceLabel">Light · Modern</span> ▾
  </button>
  <div class="appearance-menu" role="dialog" aria-label="Choose dashboard look">
    <h4>Choose dashboard look</h4>
    <div class="theme-grid">
      <button class="theme-choice" data-theme="light-modern" onclick="setTheme('light-modern')">☀️ <b>Light · Modern</b><small>Clean · premium · calm</small></button>
      <button class="theme-choice" data-theme="dark-modern" onclick="setTheme('dark-modern')">🌙 <b>Dark · Modern</b><small>Focused · polished · deep</small></button>
      <button class="theme-choice" data-theme="light-neo" onclick="setTheme('light-neo')">🟠 <b>Light · Neo</b><small>Bold · tactile · energetic</small></button>
      <button class="theme-choice" data-theme="dark-neo" onclick="setTheme('dark-neo')">⚡ <b>Dark · Neo</b><small>High contrast · punchy</small></button>
    </div>
  </div>
</div>
'''

JS = r'''
<script>
(function(){
  const labels={
    'light-modern':'Light · Modern','dark-modern':'Dark · Modern',
    'light-neo':'Light · Neo','dark-neo':'Dark · Neo'
  };
  window.toggleAppearance=function(){
    const x=document.getElementById('appearance'); if(!x)return;
    x.classList.toggle('open');
    const b=x.querySelector('.appearance-toggle');
    if(b)b.setAttribute('aria-expanded',String(x.classList.contains('open')));
  };
  window.setTheme=function(t){
    if(!labels[t])return;
    document.body.classList.remove('theme-light-modern','theme-dark-modern','theme-light-neo','theme-dark-neo');
    document.body.classList.add('theme-'+t);
    const l=document.getElementById('appearanceLabel'); if(l)l.textContent=labels[t];
    document.querySelectorAll('.theme-choice').forEach(x=>x.classList.toggle('active',x.dataset.theme===t));
    try{localStorage.setItem('leadhunter-theme',t)}catch(e){}
    const m=document.getElementById('appearance'); if(m)m.classList.remove('open');
  };
  document.addEventListener('DOMContentLoaded',function(){
    let t='light-modern';
    try{t=localStorage.getItem('leadhunter-theme')||'light-modern'}catch(e){}
    setTheme(labels[t]?t:'light-modern');
    document.addEventListener('click',function(e){
      const x=document.getElementById('appearance');
      if(x&&!x.contains(e.target))x.classList.remove('open');
    });
  });
})();
</script>
'''

# Use the proven backend and renderer from v6. Do not inject a second copy of
# lead intelligence data: v6 already renders the canonical importance,
# problems, evidence, pitch, links, stage and activity sections.
page=_base.PAGE
page=page.replace('</style>',CSS+'</style>',1)
if '<div class="top-actions">' in page:
    page=page.replace('<div class="top-actions">','<div class="top-actions"><div class="appearance-slot">'+HTML+'</div>',1)
else:
    page=page.replace('<body>','<body>'+HTML,1)
page=page.replace('</body>',JS+'</body>',1)
_base.PAGE=page
router=_base.router
