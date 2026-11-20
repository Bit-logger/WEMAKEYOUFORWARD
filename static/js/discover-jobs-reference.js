(function () {
  'use strict';
  const jobs = Array.isArray(window.JOBFLEX_JOBS || window.NEXORA_JOBS) ? (window.JOBFLEX_JOBS || window.NEXORA_JOBS) : [];
  const opts = window.JOBFLEX_FILTER_OPTIONS || window.NEXORA_FILTER_OPTIONS || {};
  const savedIds = new Set((window.JOBFLEX_SAVED || window.NEXORA_SAVED || []).map(Number));
  const appliedIds = new Set((window.JOBFLEX_APPLIED || window.NEXORA_APPLIED || []).map(Number));
  const preview = Boolean(window.JOBFLEX_PREVIEW !== undefined ? window.JOBFLEX_PREVIEW : window.NEXORA_PREVIEW);
  const state = { keyword: '', location: '', type: '', experience: '', modes: new Set(), types: new Set(), industries: new Set(), minSalary: 0, sort: 'relevance' };
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const fmt = value => Number(value || 0).toLocaleString('en-AU');
  const postedLabel = days => Number(days) <= 0 ? 'Today' : Number(days) === 1 ? '1 day ago' : Number(days) < 7 ? `${days} days ago` : Number(days) < 14 ? '1 week ago' : `${Math.floor(Number(days) / 7)} weeks ago`;
  const companyLogoClass = company => {
    const c = String(company || '').toLowerCase();
    if (c.includes('google')) return 'nx-logo-google';
    if (c.includes('canva')) return 'nx-logo-canva';
    if (c.includes('atlassian')) return 'nx-logo-atlassian';
    if (c.includes('commonwealth') || c.includes('cba')) return 'nx-logo-cba';
    if (c.includes('seek')) return 'nx-logo-seek';
    if (c.includes('deloitte')) return 'nx-logo-deloitte';
    if (c.includes('woolworth')) return 'nx-logo-woolworths';
    return '';
  };
  const logoContents = job => {
    const c = String(job.company || '').toLowerCase();
    if (c.includes('canva')) return 'Canva';
    if (c.includes('google')) return 'G';
    if (c.includes('seek')) return '✣';
    if (c.includes('deloitte')) return 'D<span style="color:#65bd45">.</span>';
    if (c.includes('woolworth')) return '✿';
    return escapeHtml(job.company_initials || String(job.company || 'NX').slice(0, 2).toUpperCase());
  };

  function showNotice(message) {
    if (!preview && typeof window.showToast === 'function') { window.showToast(message, { icon: 'info' }); return; }
    const toast = $('#nx-discover-toast');
    if (!toast) return;
    toast.textContent = message; toast.classList.add('is-visible');
    window.clearTimeout(showNotice.timer); showNotice.timer = window.setTimeout(() => toast.classList.remove('is-visible'), 3000);
  }

  /* ---- search helpers: every typed word must match (title / company / skills / industry / place) ---- */
  const norm = value => String(value ?? '').toLowerCase().replace(/[^a-z0-9+#.\s-]/g, ' ').replace(/\s+/g, ' ').trim();
  const tokens = text => norm(text).split(' ').filter(Boolean);
  const SYNONYMS = { dev: 'developer', developer: 'engineer', swe: 'software engineer', js: 'javascript', ml: 'machine learning', ai: 'machine learning', ux: 'design', ui: 'design', hr: 'people', infosec: 'security', cyber: 'security' };
  function haystack(job) {
    return {
      title: norm(job.title), company: norm(job.company),
      tags: norm(Array.isArray(job.tags) ? job.tags.join(' ') : ''),
      other: norm([job.industry, job.location, job.type, job.mode, job.experience].join(' '))
    };
  }
  function tokenScore(h, tok) {
    const alt = SYNONYMS[tok] ? norm(SYNONYMS[tok]) : '';
    let best = 0;
    [tok, alt].filter(Boolean).forEach((t, i) => {
      const w = i ? 0.6 : 1;
      if (h.title.split(' ').includes(t)) best = Math.max(best, 6 * w);
      else if (h.title.includes(t)) best = Math.max(best, 4 * w);
      if (h.tags.includes(t)) best = Math.max(best, 4 * w);
      if (h.company.includes(t)) best = Math.max(best, 3 * w);
      if (h.other.includes(t)) best = Math.max(best, 2 * w);
    });
    return best;
  }
  function relevance(job) {
    const toks = tokens(state.keyword);
    if (!toks.length) return 0;
    const h = haystack(job);
    let total = 0;
    for (const tok of toks) { const sc = tokenScore(h, tok); if (!sc) return -1; total += sc; }
    if (h.title.includes(toks.join(' '))) total += 5;   // exact phrase in the title
    return total;
  }

  function matches(job) {
    if (tokens(state.keyword).length && relevance(job) < 0) return false;
    if (state.location.trim()) {
      const loc = norm(job.location) + ' ' + norm(job.mode);
      if (!tokens(state.location).every(t => loc.includes(t) || (t === 'australia'))) return false;
    }
    if (state.type && job.type !== state.type) return false;
    if (state.experience && job.experience !== state.experience) return false;
    if (state.modes.size && !state.modes.has(job.mode)) return false;
    if (state.types.size && !state.types.has(job.type)) return false;
    if (state.industries.size && !state.industries.has(industry)) return false;
    if (Number(job.salary_max || 0) < state.minSalary) return false;
    return true;
  }

  function sortJobs(list) {
    const items = [...list];
    if (state.sort === 'newest') items.sort((a, b) => Number(a.posted_days_ago || 0) - Number(b.posted_days_ago || 0));
    else if (state.sort === 'salary') items.sort((a, b) => Number(b.salary_max || 0) - Number(a.salary_max || 0));
    else if (state.keyword.trim()) items.sort((a, b) => relevance(b) - relevance(a) || Number(Boolean(b.featured)) - Number(Boolean(a.featured)));
    else items.sort((a, b) => Number(Boolean(b.featured)) - Number(Boolean(a.featured)) || Number(Boolean(b.urgent)) - Number(Boolean(a.urgent)) || Number(a.posted_days_ago || 0) - Number(b.posted_days_ago || 0));
    return items;
  }

  function hl(text) {
    const safe = escapeHtml(text);
    const toks = tokens(state.keyword).filter(t => t.length > 1);
    if (!toks.length) return safe;
    const re = new RegExp('(' + toks.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'ig');
    return safe.replace(re, '<mark class="nx-hl">$1</mark>');
  }

  function card(job) {
    const id = Number(job.id);
    const isSaved = savedIds.has(id);
    const isApplied = appliedIds.has(id);
    const tags = (Array.isArray(job.tags) ? job.tags : []).slice(0, 4).map(t => `<span class="nx-discover-tag">${escapeHtml(t)}</span>`).join('');
    const featured = job.featured ? '<span class="nx-discover-featured"><i data-lucide="star"></i>Featured</span>' : '';
    const urgent = job.urgent ? '<span class="nx-discover-featured nx-discover-urgent">Urgent hire</span>' : '';
    const rating = job.rating ? `<span class="nx-discover-rating"><b>★</b>${escapeHtml(job.rating)}${job.reviews ? ` (${escapeHtml(job.reviews)} reviews)` : ''}</span>` : '';
    const logoClass = companyLogoClass(job.company);
    const logoColor = /^#[0-9a-f]{3,8}$/i.test(String(job.company_color || '')) ? job.company_color : '#147de5';
    const isEmployer = (window.JOBFLEX_ROLE || window.NEXORA_ROLE) === 'employer';
    const showQuickApply = !isEmployer;
    const viewBtn = isEmployer ? `<a class="nx-discover-apply-button" href="/jobs/${id}">View job <i data-lucide="arrow-right"></i></a>` : '';
    return `<article class="nx-discover-job-card" data-job-card="${id}">
      <span class="nx-discover-job-logo ${logoClass}" style="${logoClass ? '' : `background:${logoColor};color:#fff`}" aria-label="${escapeHtml(job.company)} logo">${logoContents(job)}</span>
      <div class="nx-discover-job-info">
        <div class="nx-discover-job-title-row"><a class="nx-discover-job-title" href="/jobs/${id}">${hl(job.title)}</a>${featured}${urgent}</div>
        <div class="nx-discover-company">${hl(job.company)}${rating}</div>
        <div class="nx-discover-tags">${tags}</div>
      </div>
      <div class="nx-discover-job-meta">
        <span class="nx-discover-salary"><i data-lucide="briefcase-business"></i><strong>A$${fmt(job.salary_min)} – ${fmt(job.salary_max)}</strong></span>
        <span><i data-lucide="map-pin"></i>${escapeHtml(job.location)}</span>
        <span><i data-lucide="briefcase"></i>${escapeHtml(job.type)} · ${escapeHtml(job.mode)}</span>
        <span><i data-lucide="clock-3"></i>${escapeHtml(postedLabel(job.posted_days_ago))}</span>
      </div>
      <div class="nx-discover-job-actions">
        ${isEmployer ? viewBtn : ''}${isEmployer ? '' : `<button type="button" class="nx-discover-save-button ${isSaved ? 'is-saved' : ''}" data-save-btn="${id}" onclick="nxDiscoverSave(${id}, this)"><i data-lucide="bookmark" ${isSaved ? 'fill="currentColor"' : ''}></i><span data-save-label>${isSaved ? 'Saved' : 'Save'}</span></button>`}
        ${showQuickApply ? (isApplied ? '<button type="button" class="nx-discover-apply-button" disabled>Applied</button>' : `<button type="button" class="nx-discover-apply-button" data-apply="${id}" onclick="nxDiscoverApply(${id}, this)">Apply Now <i data-lucide="arrow-right"></i></button>`) : ''}
      </div>
    </article>`;
  }

  function syncActiveChips() {
    $$('[data-work-mode]').forEach(button => button.classList.toggle('is-active', state.modes.has(button.dataset.workMode)));
    $$('[data-job-type]').forEach(button => button.classList.toggle('is-active', state.types.has(button.dataset.jobType)));
    $$('[data-popular-query]').forEach(button => button.classList.toggle('is-active', state.keyword.toLowerCase() === button.dataset.popularQuery.toLowerCase()));
    $$('[data-industry-filter]').forEach(input => input.checked = state.industries.has(input.value));
  }

  function syncCategoryCounts() {
    const counts = {};
    jobs.forEach(job => { const key = job.industry || 'Other'; counts[key] = (counts[key] || 0) + 1; });
    $$('[data-category-count]').forEach(el => { el.textContent = counts[el.dataset.categoryCount] || 0; });
  }

  function render() {
    const results = sortJobs(jobs.filter(matches));
    const list = $('#job-list'); const empty = $('#empty-state');
    if (!list || !empty) return;
    $('#results-count').textContent = results.length.toLocaleString('en-AU');
    list.innerHTML = results.map(card).join('');
    empty.hidden = results.length > 0;
    syncActiveChips();
    renderActiveFilters(results.length);
    syncUrl();
    if (window.lucide) window.lucide.createIcons();
  }

  function activeFilterList() {
    const out = [];
    if (state.keyword.trim()) out.push({ label: `“${state.keyword.trim()}”`, clear: () => { state.keyword = ''; $('#filter-keyword').value = ''; const g = $('#nx-discover-global-query'); if (g) g.value = ''; } });
    if (state.location.trim()) out.push({ label: state.location.trim(), clear: () => { state.location = ''; $('#filter-location').value = ''; } });
    if (state.type) out.push({ label: state.type, clear: () => { state.type = ''; $('#discover-filter-type').value = ''; } });
    if (state.experience) out.push({ label: state.experience, clear: () => { state.experience = ''; $('#discover-filter-experience').value = ''; } });
    state.modes.forEach(v => out.push({ label: v, clear: () => state.modes.delete(v) }));
    state.types.forEach(v => out.push({ label: v, clear: () => state.types.delete(v) }));
    state.industries.forEach(v => out.push({ label: v, clear: () => state.industries.delete(v) }));
    if (state.minSalary) out.push({ label: `A$${fmt(state.minSalary)}+`, clear: () => { state.minSalary = 0; $('#discover-min-salary').value = '0'; $('#discover-min-salary-label').textContent = 'A$0+'; } });
    return out;
  }

  function renderActiveFilters() {
    const box = $('#active-filters'); if (!box) return;
    const list = activeFilterList();
    box.hidden = !list.length;
    box.innerHTML = list.map((f, i) => `<button type="button" class="nx-active-chip" data-chip="${i}">${escapeHtml(f.label)}<i data-lucide="x"></i></button>`).join('') + (list.length ? '<button type="button" class="nx-active-clear" id="active-clear-all">Clear all</button>' : '');
    $$('[data-chip]', box).forEach(b => b.addEventListener('click', () => { list[Number(b.dataset.chip)].clear(); render(); }));
    $('#active-clear-all')?.addEventListener('click', clearFilters);
  }

  function syncUrl() {
    try {
      const url = new URL(window.location.href);
      state.keyword.trim() ? url.searchParams.set('q', state.keyword.trim()) : url.searchParams.delete('q');
      state.location.trim() ? url.searchParams.set('location', state.location.trim()) : url.searchParams.delete('location');
      window.history.replaceState(null, '', url);
    } catch (_) { /* non-critical */ }
  }

  function collectFields() {
    state.keyword = $('#filter-keyword')?.value || '';
    state.location = $('#filter-location')?.value || '';
    state.type = $('#discover-filter-type')?.value || '';
    state.experience = $('#discover-filter-experience')?.value || '';
    state.sort = $('#discover-sort')?.value || 'relevance';
  }

  function clearFilters() {
    state.keyword = ''; state.location = ''; state.type = ''; state.experience = '';
    state.modes.clear(); state.types.clear(); state.industries.clear(); state.minSalary = 0; state.sort = 'relevance';
    $('#filter-keyword').value = ''; $('#filter-location').value = '';
    const g = $('#nx-discover-global-query'); if (g) g.value = '';
    $('#discover-filter-type').value = ''; $('#discover-filter-experience').value = '';
    $('#discover-sort').value = 'relevance'; $('#discover-min-salary').value = '0'; $('#discover-min-salary-label').textContent = 'A$0+';
    $('#discover-more-panel').hidden = true; $('#discover-more-toggle').setAttribute('aria-expanded', 'false');
    render();
  }

  window.nxDiscoverSave = function (id, button) {
    if (preview) {
      if (savedIds.has(id)) savedIds.delete(id); else savedIds.add(id);
      button.classList.toggle('is-saved', savedIds.has(id));
      button.innerHTML = `<i data-lucide="bookmark" ${savedIds.has(id) ? 'fill="currentColor"' : ''}></i><span data-save-label>${savedIds.has(id) ? 'Saved' : 'Save'}</span>`;
      if (window.lucide) window.lucide.createIcons();
      showNotice(savedIds.has(id) ? 'Job saved to your demo list.' : 'Removed from your demo saved list.');
      return;
    }
    if (typeof window.toggleSaveJob === 'function') window.toggleSaveJob(id);
    else showNotice('Save jobs requires the application API to be running.');
  };

  window.nxDiscoverApply = function (id, button) {
    if (preview) {
      appliedIds.add(id); button.disabled = true; button.textContent = 'Applied';
      showNotice('Demo application submitted. This preview does not save data.');
      return;
    }
    if (typeof window.quickApply === 'function') window.quickApply(id, button);
    else showNotice('Applying requires the application API to be running.');
  };

  document.addEventListener('DOMContentLoaded', function () {
    const params = new URLSearchParams(window.location.search);
    if (params.get('q')) $('#filter-keyword').value = params.get('q');
    if (params.get('location')) $('#filter-location').value = params.get('location');
    if (params.get('industry')) state.industries.add(params.get('industry'));
    const globalQuery = $('#nx-discover-global-query');
    if (globalQuery) globalQuery.value = params.get('q') || '';
    collectFields();

    $('#discover-search-form').addEventListener('submit', event => { event.preventDefault(); collectFields(); render(); });
    $('#nx-discover-global-form')?.addEventListener('submit', event => {
      event.preventDefault(); $('#filter-keyword').value = globalQuery.value || ''; collectFields(); render();
      const y = $('.nx-discover-search-panel').getBoundingClientRect().top + window.scrollY - 95; window.scrollTo({ top: y, behavior: 'smooth' });
    });
    ['filter-keyword','filter-location','discover-filter-type','discover-filter-experience'].forEach(id => {
      const el = document.getElementById(id); el?.addEventListener('change', () => { collectFields(); render(); });
    });
    let typingTimer;
    ['filter-keyword','filter-location'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', () => { window.clearTimeout(typingTimer); typingTimer = window.setTimeout(() => { collectFields(); render(); }, 180); });
    });
    $('#filter-keyword')?.addEventListener('keydown', e => { if (e.key === 'Escape') { e.target.value = ''; collectFields(); render(); } });
    globalQuery?.addEventListener('input', () => { window.clearTimeout(typingTimer); typingTimer = window.setTimeout(() => { $('#filter-keyword').value = globalQuery.value; collectFields(); render(); }, 180); });
    $('#discover-sort').addEventListener('change', () => { collectFields(); render(); });
    $$('[data-work-mode]').forEach(button => button.addEventListener('click', () => { const value = button.dataset.workMode; state.modes.has(value) ? state.modes.delete(value) : state.modes.add(value); render(); }));
    $$('[data-job-type]').forEach(button => button.addEventListener('click', () => { const value = button.dataset.jobType; state.types.has(value) ? state.types.delete(value) : state.types.add(value); render(); }));
    $$('[data-popular-query]').forEach(button => button.addEventListener('click', () => { $('#filter-keyword').value = button.dataset.popularQuery; collectFields(); render(); }));
    $$('[data-industry-filter]').forEach(input => input.addEventListener('change', () => { input.checked ? state.industries.add(input.value) : state.industries.delete(input.value); render(); }));
    $$('[data-category]').forEach(button => button.addEventListener('click', () => { const value = button.dataset.category; state.industries.has(value) ? state.industries.delete(value) : state.industries.add(value); $('#discover-more-panel').hidden = false; $('#discover-more-toggle').setAttribute('aria-expanded','true'); render(); $('.nx-discover-more-panel').scrollIntoView({ behavior:'smooth', block:'nearest' }); }));
    $('#discover-min-salary').addEventListener('input', event => { state.minSalary = Number(event.target.value); $('#discover-min-salary-label').textContent = `A$${fmt(state.minSalary)}+`; render(); });
    $('#discover-more-toggle').addEventListener('click', () => { const panel = $('#discover-more-panel'); panel.hidden = !panel.hidden; $('#discover-more-toggle').setAttribute('aria-expanded', String(!panel.hidden)); });
    $('#discover-clear-filters').addEventListener('click', clearFilters); $('#discover-empty-clear').addEventListener('click', clearFilters);
    $$('[data-saved-search]').forEach(el => {
      const applySavedSearch = () => { $('#filter-keyword').value = el.dataset.savedSearch; collectFields(); render(); window.scrollTo({ top:0, behavior:'smooth' }); };
      el.addEventListener('click', applySavedSearch); el.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); applySavedSearch(); } });
    });
    $('#discover-create-alert').addEventListener('click', () => showNotice('Job alert preferences will be connected to your account in a follow-up integration step.'));
    $('#discover-view-saved').addEventListener('click', event => { event.preventDefault(); showNotice('Your saved searches are shown here. Select one to run it.'); });
    $('#discover-view-categories').addEventListener('click', event => { event.preventDefault(); $('#discover-more-panel').hidden = false; $('#discover-more-toggle').setAttribute('aria-expanded','true'); });
    syncCategoryCounts(); render();
  });
})();
