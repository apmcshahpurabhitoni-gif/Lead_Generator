"""Small dashboard runtime adapters for API/UI contract hardening.

Keep this separate from the large embedded template so the UI can be locked
without duplicating the full HTML document. These adapters only consume the
public /dashboard/api contract and do not contain business logic.
"""

DASHBOARD_RUNTIME_FIX = r'''<script>
(function () {
  "use strict";

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
            const services = Array.isArray(d.services) && d.services.length
              ? ' · ' + d.services.join(', ')
              : '';
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
        : '<div class="empty"><div class="empty-icon">➤</div><b>No saved opportunities</b>'
          + '<div class="tiny" style="margin-top:4px">Expand a lead and save it to Act when you are ready.</div></div>';
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
