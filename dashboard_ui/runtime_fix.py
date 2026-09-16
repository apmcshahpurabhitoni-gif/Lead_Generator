"""Small dashboard runtime adapters for API/UI contract hardening.

Keep this separate from the large embedded template so the UI can be locked
without duplicating the full HTML document. These adapters only consume the
public /dashboard/api contract and do not contain business logic.
"""

DASHBOARD_RUNTIME_FIX = r'''<style>
.dataset-picker-wrap{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin:0 0 12px}
.dataset-picker-label{font-size:11px;font-weight:800;color:var(--muted);letter-spacing:.03em}
.dataset-picker{height:38px;min-width:280px;max-width:100%;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);padding:0 11px;outline:none}
.dataset-picker:focus{border-color:#4ade80;box-shadow:0 0 0 3px rgba(34,197,94,.10)}
.dataset-picker-note{font-size:11px;color:var(--muted)}
@media(max-width:700px){.dataset-picker{min-width:0;width:100%}.dataset-picker-wrap{display:grid}}
</style>
<script>
(function () {
  "use strict";

  function ensureDatasetPicker() {
    const anchor = document.getElementById('leadList');
    if (!anchor) return null;
    let wrap = document.getElementById('datasetPickerWrap');
    if (wrap) return wrap;

    wrap = document.createElement('div');
    wrap.id = 'datasetPickerWrap';
    wrap.className = 'dataset-picker-wrap';

    const label = document.createElement('span');
    label.className = 'dataset-picker-label';
    label.textContent = 'DATASET';

    const picker = document.createElement('select');
    picker.id = 'datasetPicker';
    picker.className = 'dataset-picker';
    picker.setAttribute('aria-label', 'Select dataset');

    const note = document.createElement('span');
    note.id = 'datasetPickerNote';
    note.className = 'dataset-picker-note';

    wrap.append(label, picker, note);
    anchor.parentNode.insertBefore(wrap, anchor);
    return wrap;
  }

  function datasetId(item) {
    return Number(item?.id ?? item?.search_id ?? item?.dataset_id ?? 0);
  }

  function datasetLabel(item) {
    const id = datasetId(item);
    const place = [item?.city, item?.industry].filter(Boolean).join(' · ');
    const status = String(item?.status || '').toUpperCase();
    const count = Number(item?.result_count ?? item?.succeeded ?? 0);
    return [place || ('Dataset #' + id), status || null, count + ' leads']
      .filter(Boolean)
      .join(' · ');
  }

  window.loadDatasets = async function loadDatasets() {
    const pickerWrap = ensureDatasetPicker();
    if (!pickerWrap) return;
    const picker = document.getElementById('datasetPicker');
    const note = document.getElementById('datasetPickerNote');
    if (!picker) return;

    picker.disabled = true;
    picker.replaceChildren(new Option('Loading datasets…', ''));
    if (note) note.textContent = '';

    try {
      const x = await api('/datasets?limit=50');
      const items = Array.isArray(x.items) ? x.items : [];
      $('datasetCount').textContent = items.length + ' dataset' + (items.length === 1 ? '' : 's');
      picker.replaceChildren();

      if (!items.length) {
        picker.disabled = true;
        picker.appendChild(new Option('No datasets yet', ''));
        selectedDataset = null;
        allLeads = [];
        $('leadTitle').textContent = 'No dataset selected';
        $('leadMeta').textContent = 'Use Find Leads to create a dataset.';
        $('leadList').innerHTML = '<div class="empty"><div class="empty-icon">⌕</div><b>No datasets available</b><div class="tiny" style="margin-top:4px">Create a dataset from Find Leads, then select it here.</div></div>';
        return;
      }

      items.forEach(item => {
        const id = datasetId(item);
        if (id > 0) picker.appendChild(new Option(datasetLabel(item), String(id)));
      });

      const preferred = Number(selectedDataset || 0);
      const match = items.find(item => datasetId(item) === preferred) || items[0];
      picker.value = String(datasetId(match));
      picker.disabled = false;
      if (note) note.textContent = 'Select a dataset to load its leads';

      picker.onchange = async function () {
        const id = Number(this.value);
        if (!Number.isInteger(id) || id <= 0) return;
        await window.selectDataset(id);
      };

      await window.selectDataset(datasetId(match));
    } catch (e) {
      picker.disabled = true;
      picker.replaceChildren(new Option('Datasets unavailable', ''));
      error('datasets', e);
      $('datasetCount').textContent = 'Unavailable';
    }
  };

  window.loadAnalytics = async function loadAnalytics() {
    try {
      const x = await api('/analytics');
      const totals = x.totals || {};
      $('aLeads').textContent = totals.leads ?? x.leads ?? 0;
      $('aHot').textContent = totals.hot ?? x.hot ?? 0;
      $('aQualified').textContent = totals.qualified ?? x.qualified ?? 0;
      $('aContacted').textContent = totals.contacted ?? x.contacted ?? 0;
      renderBars('cityChart', x.cities || [], 'No city data');
      renderBars('serviceChart', x.services || [], 'No service data');
    } catch (e) {
      error('cityChart', e);
      error('serviceChart', e);
    }
  };

  window.openLeadDirect = async function openLeadDirect(leadId) {
    const id = Number(leadId);
    if (!Number.isInteger(id) || id <= 0) {
      toast('This opportunity has no valid lead ID');
      return;
    }
    try {
      const x = await api('/leads/' + id);
      const lead = x.item;
      if (!lead) throw new Error('Lead not found');

      // Do not call go('leads') here: go() also starts dataset loading, which
      // can race this direct-lead render and replace the selected lead.
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('leads')?.classList.add('active');
      document.querySelector('.nav-btn[data-page="leads"]')?.classList.add('active');
      $('crumb').innerHTML = '<strong>Leads</strong> <span>›</span> Direct lead';
      if (typeof closeSidebar === 'function') closeSidebar();

      selectedDataset = null;
      allLeads = [lead];
      $('leadTitle').textContent = nameOf(lead);
      $('leadMeta').textContent = (cityOf(lead) || 'Unknown location') + ' · direct lead view';
      document.getElementById('datasetPickerWrap')?.remove();
      $('leadList').innerHTML = leadCard(lead, 0);
      document.getElementById('lead-' + CSS.escape(String(id)))?.classList.add('open');
    } catch (e) {
      toast(e.message || 'Could not open lead');
    }
  };

  window.loadOutreach = async function loadOutreach() {
    loading('outreachList', 'Loading outreach…');
    try {
      const x = await api('/outreach');
      const items = x.items || [];
      const counts = x.counts || {};
      $('outreachCounts').innerHTML = Object.entries(counts)
        .map(([k, v]) => '<span class="badge blue">' + esc(k) + ': ' + esc(v) + '</span>')
        .join('');

      $('outreachList').innerHTML = items.length
        ? items.map(d => {
            const id = Number(d.business_id || d.lead_id || 0);
            const name = d.name || d.business_name || ('Lead #' + id);
            const location = [d.city, d.industry].filter(Boolean).join(' · ');
            const services = Array.isArray(d.services) && d.services.length ? ' · ' + d.services.join(', ') : '';
            const notes = d.notes ? ' · ' + d.notes : '';
            return '<div class="list-row"><div class="outreach-card">'
              + '<div class="outreach-info">'
              + '<div class="outreach-title">' + esc(name) + '</div>'
              + '<div class="outreach-meta">' + esc(d.stage || 'READY')
              + (location ? ' · ' + esc(location) : '')
              + esc(services) + esc(notes) + '</div>'
              + '</div><div class="outreach-actions">'
              + (id > 0
                ? '<button class="btn sm" onclick="openLeadDirect(' + id + ')">Open lead</button>'
                : '<span class="badge gray">No lead ID</span>')
              + '</div></div></div>';
          }).join('')
        : '<div class="empty"><div class="empty-icon">➤</div><b>No saved opportunities</b><div class="tiny" style="margin-top:4px">Expand a lead and save it to Act when you are ready.</div></div>';
    } catch (e) {
      error('outreachList', e);
    }
  };

  window.researchLead = async function researchLead(id) {
    const numericId = Number(id);
    if (!Number.isInteger(numericId) || numericId <= 0) {
      toast('This lead has no valid ID');
      return;
    }
    try {
      toast('Researching lead…');
      const x = await api('/leads/' + numericId + '/research', { method: 'POST' });
      const lead = allLeads.find(v => Number(v.id ?? v.lead_id) === numericId);
      if (lead) {
        lead.research = x.research || {};
        lead.score = x.score?.score ?? lead.score;
        lead.priority = x.score?.priority ?? lead.priority;
        lead.status = Number(x.score?.score ?? 0) >= 60 ? 'QUALIFIED' : 'RESEARCHED';
      }
      renderLeads();
      document.getElementById('lead-' + CSS.escape(String(numericId)))?.classList.add('open');
      toast('Research complete');
    } catch (e) {
      toast(e.message || 'Research failed');
    }
  };
})();
</script>'''