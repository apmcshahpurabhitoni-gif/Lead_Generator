"""LeadHunter dashboard visual/presentation layer.

Keeps dashboard_v6's working backend/discovery APIs and upgrades the UI only:
- four selectable appearance combinations
- sales-critical evidence surfaced before secondary details
- colorful, emoji-assisted research evidence cards
- mobile-friendly appearance controls
"""
import dashboard_v6 as _base

THEME_CSS = r'''
/* LeadHunter appearance system: four deliberate combinations */
.appearance{position:relative}.appearance-toggle{min-height:42px;padding:8px 11px;border:1.5px solid var(--line);border-radius:12px;background:var(--surface);color:var(--text);font-weight:850;display:inline-flex;align-items:center;gap:7px;cursor:pointer}.appearance-menu{position:absolute;right:0;top:48px;z-index:100;display:none;width:270px;padding:10px;border:1.5px solid var(--line);border-radius:16px;background:var(--surface);box-shadow:6px 7px 0 var(--shadow)}.appearance.open .appearance-menu{display:block}.appearance-menu h4{margin:2px 4px 8px;font-size:10px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted)}.theme-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.theme-choice{border:1.5px solid var(--softline);background:var(--surface2);color:var(--text);border-radius:12px;padding:10px 8px;text-align:left;cursor:pointer;font-weight:800}.theme-choice b{display:block;font-size:11px}.theme-choice small{display:block;margin-top:2px;color:var(--muted);font-size:9px}.theme-choice.active{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 13%,var(--surface))}.theme-choice:focus-visible,.appearance-toggle:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
/* Four themes */
body.theme-dark-modern{--bg:#07111f;--surface:#0d1d30;--surface2:#11263d;--text:#f5f8ff;--muted:#91a7bd;--line:#37516c;--softline:#31475e;--accent:#55d8ff;--green:#2ee59a;--yellow:#ffd45a;--red:#ff687b;--shadow:#020712}
body.theme-light-neo{--bg:#efe8d9;--surface:#fffaf0;--surface2:#e5dccb;--text:#171717;--muted:#625d55;--line:#171717;--softline:#8e8579;--accent:#ff5b35;--green:#087a4b;--yellow:#a06c00;--red:#b42336;--shadow:#171717}.theme-light-neo .topbar,.theme-light-neo .metric,.theme-light-neo .workspace,.theme-light-neo .lead,.theme-light-neo .section,.theme-light-neo .appearance-menu{box-shadow:6px 7px 0 var(--shadow)}.theme-light-neo .btn,.theme-light-neo .iconbtn{box-shadow:3px 3px 0 var(--shadow)}
body.theme-dark-neo{--bg:#090b10;--surface:#12161e;--surface2:#1b202a;--text:#f6f7f9;--muted:#9ba5b3;--line:#f0f2f5;--softline:#596575;--accent:#ffcf33;--green:#3ee7a3;--yellow:#ffd45a;--red:#ff6678;--shadow:#000}.theme-dark-neo .topbar,.theme-dark-neo .metric,.theme-dark-neo .workspace,.theme-dark-neo .lead,.theme-dark-neo .section,.theme-dark-neo .appearance-menu{box-shadow:6px 7px 0 #000}.theme-dark-neo .btn,.theme-dark-neo .iconbtn{box-shadow:3px 3px 0 #000}.theme-dark-neo .btn.primary{background:var(--accent);color:#111}
body.theme-dark-modern{background:radial-gradient(900px 500px at 0 0,#40208044,transparent 65%),radial-gradient(700px 500px at 100% 0,#007f9540,transparent 65%),var(--bg)}
/* Sales intelligence: make the data that matters visually dominant */
.sales-priority{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0}.sales-item{border:1.5px solid var(--softline);border-radius:13px;padding:10px;background:var(--surface2);min-height:76px}.sales-item .sales-icon{font-size:18px}.sales-item small{display:block;margin-top:3px;font-size:8px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:900}.sales-item strong{display:block;margin-top:2px;font-size:13px;line-height:1.25}.sales-item.problem{border-color:#d05a6b;background:color-mix(in srgb,#ff4d62 8%,var(--surface))}.sales-item.opportunity{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 8%,var(--surface))}.sales-item.contact{border-color:var(--green);background:color-mix(in srgb,var(--green) 7%,var(--surface))}.sales-item.google{border-color:#00a9b8;background:color-mix(in srgb,#00a9b8 7%,var(--surface))}
.evidence .evidence-row,.evidence div{border-left:4px solid var(--accent);padding:10px 11px}.section h3{font-size:10px;font-weight:950}.critical-label{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border-radius:999px;background:var(--surface2);border:1px solid var(--softline);font-size:9px;font-weight:900;margin-bottom:7px}.details .telegram{margin-top:9px}.details .links .link{font-weight:750}
@media(max-width:700px){.appearance-menu{position:fixed;right:9px;top:68px;width:min(300px,calc(100vw - 18px))}.sales-priority{grid-template-columns:1fr 1fr;gap:6px}.sales-item{min-height:70px;padding:8px}.top-actions{flex-wrap:wrap}.appearance-toggle{flex:1}.top-actions .btn{flex:1}}
'''

THEME_HTML = r'''
<div class="appearance" id="appearance">
  <button class="appearance-toggle" type="button" onclick="toggleAppearance()" aria-expanded="false">🎨 <span id="appearanceLabel">Dark · Modern</span> ▾</button>
  <div class="appearance-menu" role="dialog" aria-label="Dashboard appearance">
    <h4>Choose your dashboard look</h4>
    <div class="theme-grid">
      <button class="theme-choice" data-theme="light-modern" onclick="setTheme('light-modern')">☀️ <b>Light · Modern</b><small>Clean premium</small></button>
      <button class="theme-choice active" data-theme="dark-modern" onclick="setTheme('dark-modern')">🌙 <b>Dark · Modern</b><small>Focused &amp; polished</small></button>
      <button class="theme-choice" data-theme="light-neo" onclick="setTheme('light-neo')">🟠 <b>Light · Neo</b><small>Bold &amp; tactile</small></button>
      <button class="theme-choice" data-theme="dark-neo" onclick="setTheme('dark-neo')">⚡ <b>Dark · Neo</b><small>High-contrast command</small></button>
    </div>
  </div>
</div>
'''

THEME_JS = r'''
<script>
(function(){
  const labels={
    'light-modern':'Light · Modern','dark-modern':'Dark · Modern',
    'light-neo':'Light · Neo','dark-neo':'Dark · Neo'
  };
  window.toggleAppearance=function(){
    const box=document.getElementById('appearance'); if(!box)return;
    box.classList.toggle('open');
    const b=box.querySelector('.appearance-toggle'); if(b)b.setAttribute('aria-expanded',box.classList.contains('open'));
  };
  window.setTheme=function(theme){
    if(!labels[theme])return;
    document.body.classList.remove('theme-light-modern','theme-dark-modern','theme-light-neo','theme-dark-neo');
    document.body.classList.add('theme-'+theme);
    const label=document.getElementById('appearanceLabel'); if(label)label.textContent=labels[theme];
    document.querySelectorAll('.theme-choice').forEach(x=>x.classList.toggle('active',x.dataset.theme===theme));
    localStorage.setItem('leadhunter-theme',theme);
    const box=document.getElementById('appearance'); if(box)box.classList.remove('open');
  };
  const saved=localStorage.getItem('leadhunter-theme')||'dark-modern';
  document.addEventListener('DOMContentLoaded',()=>{
    setTheme(saved);
    document.addEventListener('click',e=>{const box=document.getElementById('appearance');if(box&&!box.contains(e.target))box.classList.remove('open')});
  });
})();

/* Surface the sales-critical facts on every collapsed lead card as soon as the
   existing renderer creates its details. This does not alter API/data logic. */
(function(){
  function textOf(el){return (el&&el.textContent||'').replace(/\s+/g,' ').trim()}
  function valueAfter(t,labels){for(const label of labels){const i=t.toLowerCase().indexOf(label.toLowerCase());if(i>=0){let s=t.slice(i+label.length).replace(/^\s*[:·-]\s*/,'').trim();return s.split(/\s{2,}/)[0].slice(0,90)}}return ''}
  function addSalesStrip(card){
    if(!card||card.querySelector('.sales-priority'))return;
    const details=card.querySelector('.details'); if(!details)return;
    const t=textOf(details);
    const google=valueAfter(t,['Google Local Position','Google Local','Local Position'])||'Not measured';
    const website=valueAfter(t,['Website'])||'Not found';
    const phone=valueAfter(t,['Phone'])||'Not found';
    const email=valueAfter(t,['Email'])||'Not found';
    const strip=document.createElement('div'); strip.className='sales-priority';
    const items=[
      ['google','📍','Google / Local',google],
      ['contact','🌐','Website',website],
      ['contact','📞','Phone',phone],
      ['contact','✉️','Email',email]
    ];
    items.forEach(([cls,ico,label,val])=>{const d=document.createElement('div');d.className='sales-item '+cls;d.innerHTML='<span class="sales-icon">'+ico+'</span><small>'+label+'</small><strong>'+escapeHtml(val)+'</strong>';strip.appendChild(d)});
    const hero=details.querySelector('.hero');
    if(hero)hero.after(strip); else details.prepend(strip);
  }
  function escapeHtml(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
  function scan(){document.querySelectorAll('.lead').forEach(addSalesStrip)}
  new MutationObserver(scan).observe(document.body,{childList:true,subtree:true});
  document.addEventListener('DOMContentLoaded',scan);
})();
</script>
'''

# The base module keeps all existing API routes and working discovery logic.
# Only the rendered PAGE is transformed here.
page = _base.PAGE
page = page.replace('<body>', '<body class="theme-dark-modern">', 1)
page = page.replace('</style>', THEME_CSS + '</style>', 1)
# Put the appearance picker beside the existing header actions.
page = page.replace('<div class="top-actions">', '<div class="top-actions"><div class="appearance-slot">' + THEME_HTML + '</div>', 1)
page = page.replace('</body>', THEME_JS + '</body>', 1)

# Make the collapsed lead row communicate the sales purpose immediately.
page = page.replace('Lead Intelligence</small>', 'Lead intelligence · Sales workspace</small>', 1)

_base.PAGE = page
router = _base.router
'''

# Fix accidental literal terminator if this file is ever edited as a raw string.
content = content.replace("\n'''\n\n# Fix accidental literal terminator if this file is ever edited as a raw string.\ncontent = content.replace(\"\\n'''\", \"\")\n", "") if False else None
