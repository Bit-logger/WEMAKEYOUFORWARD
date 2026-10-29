(function () {
  const page = document.querySelector('.nx-apps-page');
  if (!page) return;
  const preview = page.dataset.previewMode === 'true';
  const rows = Array.from(document.querySelectorAll('[data-app-row]'));
  const searchInput = document.querySelector('[data-application-search]');
  const tabs = Array.from(document.querySelectorAll('[data-filter]'));
  const noResults = document.querySelector('[data-no-results]');
  let activeFilter = 'all';

  function updateVisibleRows() {
    const term = (searchInput?.value || '').trim().toLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const categoryMatch = activeFilter === 'all' || row.dataset.category === activeFilter;
      const searchMatch = !term || (row.dataset.searchText || '').includes(term);
      const show = categoryMatch && searchMatch;
      row.hidden = !show;
      if (show) visible += 1;
    });
    if (noResults) noResults.hidden = visible !== 0;
  }

  if (searchInput) searchInput.addEventListener('input', updateVisibleRows);
  if (preview) {
    tabs.forEach((tab) => tab.addEventListener('click', () => {
      activeFilter = tab.dataset.filter || 'all';
      tabs.forEach((other) => other.classList.toggle('is-active', other === tab));
      updateVisibleRows();
    }));
  }

  function closeMenus(except) {
    document.querySelectorAll('[data-app-menu]').forEach((menu) => {
      if (menu !== except) {
        menu.classList.remove('is-open');
        const button = menu.parentElement?.querySelector('[data-menu-btn]');
        button?.setAttribute('aria-expanded', 'false');
      }
    });
  }
  document.querySelectorAll('[data-menu-btn]').forEach((button) => button.addEventListener('click', (event) => {
    event.stopPropagation();
    const menu = button.parentElement?.querySelector('[data-app-menu]');
    if (!menu) return;
    const shouldOpen = !menu.classList.contains('is-open');
    closeMenus(menu);
    menu.classList.toggle('is-open', shouldOpen);
    button.setAttribute('aria-expanded', String(shouldOpen));
  }));
  document.addEventListener('click', () => closeMenus());
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeMenus(); });

  function notify(message, ok = true) {
    if (typeof window.showToast === 'function') {
      window.showToast(message, { icon: ok ? 'check-circle-2' : 'alert-circle' });
      return;
    }
    const el = document.createElement('div');
    el.className = 'nx-apps-local-toast'; el.textContent = message;
    Object.assign(el.style, {position:'fixed',right:'20px',bottom:'20px',zIndex:'200',padding:'12px 16px',background:'#0d2d57',border:'1px solid #1e69a6',borderRadius:'10px',color:'#fff',fontSize:'13px'});
    document.body.appendChild(el); setTimeout(() => el.remove(), 2800);
  }

  const statusDisplay = { Applied: ['Applied', 'applied'], Shortlisted: ['Under Review', 'review'], Interview: ['Interview Scheduled', 'interviews'], Rejected: ['Not Selected', 'rejected'] };
  async function postJSON(url, body) {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    const result = await response.json().catch(() => ({}));
    return response.ok && result.ok !== false;
  }

  document.querySelectorAll('[data-set-status]').forEach((button) => button.addEventListener('click', async () => {
    const id = button.dataset.appId;
    const status = button.dataset.setStatus;
    closeMenus();
    try {
      const ok = await postJSON(`/api/seeker/applications/${encodeURIComponent(id)}/status`, { status });
      if (!ok) { notify('Could not update the application. Please try again.', false); return; }
      if (preview) {
        const row = document.querySelector(`[data-app-row][data-app-id="${CSS.escape(String(id))}"]`);
        if (row) {
          const [label, category] = statusDisplay[status] || [status, 'applied'];
          row.dataset.status = status; row.dataset.category = category;
          const chip = row.querySelector('[data-app-status]');
          if (chip) { chip.textContent = label; chip.className = `nx-app-status nx-status-${category}`; }
          row.dataset.searchText = `${row.dataset.searchText || ''} ${label}`.toLowerCase();
        }
        notify(`Preview status changed to ${statusDisplay[status]?.[0] || status}.`);
        updateVisibleRows();
      } else {
        notify('Application status updated.');
        setTimeout(() => window.location.reload(), 450);
      }
    } catch (_) { notify('Could not connect. Please try again.', false); }
  }));

  document.querySelectorAll('[data-remove]').forEach((button) => button.addEventListener('click', async () => {
    if (!window.confirm('Remove this application from your list?')) return;
    const id = button.dataset.remove;
    closeMenus();
    try {
      const ok = await postJSON(`/api/seeker/applications/${encodeURIComponent(id)}/remove`, {});
      if (!ok) { notify('Could not remove the application. Please try again.', false); return; }
      if (preview) {
        const row = document.querySelector(`[data-app-row][data-app-id="${CSS.escape(String(id))}"]`);
        row?.remove();
        notify('Demo application removed.'); updateVisibleRows();
      } else {
        notify('Application removed.'); setTimeout(() => window.location.reload(), 450);
      }
    } catch (_) { notify('Could not connect. Please try again.', false); }
  }));
  updateVisibleRows();
})();
