(function () {
  const STATUS_CHIP_CLASS = {
    Approved: 'chip chip-mint',
    Rejected: 'chip chip-rose',
    Suspended: 'chip chip-rose',
    Review: 'chip',
    Pending: 'chip',
  };

  let activeFilter = 'all';

  function applyFilter() {
    document.querySelectorAll('[data-job-row]').forEach((row) => {
      const show = activeFilter === 'all' || row.dataset.status === activeFilter;
      row.style.display = show ? '' : 'none';
    });
    document.querySelectorAll('[data-job-row-mobile]').forEach((row) => {
      const show = activeFilter === 'all' || row.dataset.status === activeFilter;
      row.style.display = show ? '' : 'none';
    });
  }

  document.querySelectorAll('.moderation-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.moderation-tab').forEach((t) => t.classList.remove('active', 'bg-white', 'shadow-sm', 'text-navy'));
      tab.classList.add('active', 'bg-white', 'shadow-sm', 'text-navy');
      activeFilter = tab.dataset.filter;
      applyFilter();
    });
  });
  document.querySelector('.moderation-tab.active')?.classList.add('bg-white', 'shadow-sm', 'text-navy');

  window.moderate = async function (jobId, action) {
    if (action === 'delete') {
      if (!confirm('Are you sure you want to permanently delete this job posting? This will remove all associated applications.')) return;
      try {
        const resp = await fetch(`/api/admin/jobs/${jobId}/delete`, { method: 'POST' });
        const res = await resp.json();
        if (res.ok) {
          document.querySelector(`[data-job-row="${jobId}"]`)?.remove();
          document.querySelector(`[data-job-row-mobile="${jobId}"]`)?.remove();
          if (typeof showToast === 'function') showToast('Job permanently deleted.', { icon: 'trash-2' });
        } else {
          alert(res.error || 'Failed to delete job.');
        }
      } catch (err) {
        alert('Network error while deleting job.');
      }
      return;
    }

    const labelMap = { approve: 'Approved', reject: 'Rejected', review: 'Review', suspend: 'Suspended' };
    const newStatus = labelMap[action];
    try {
      await fetch(`/api/admin/jobs/${jobId}/moderate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }),
      });
    } catch (e) {}
    const row = document.querySelector(`[data-job-row="${jobId}"]`);
    const rowMobile = document.querySelector(`[data-job-row-mobile="${jobId}"]`);
    if (row) row.dataset.status = newStatus;
    if (rowMobile) rowMobile.dataset.status = newStatus;
    const chip = document.querySelector(`[data-status-chip="${jobId}"]`);
    const chipMobile = document.querySelector(`[data-status-chip-mobile="${jobId}"]`);
    [chip, chipMobile].forEach((el) => {
      if (!el) return;
      el.className = STATUS_CHIP_CLASS[newStatus] || 'chip';
      el.textContent = newStatus;
    });
    applyFilter();
    if (typeof showToast === 'function') showToast(`Job marked as ${newStatus.toLowerCase()}.`, { icon: 'shield-check' });
  };

  window.adminDeleteUser = async function(userType, userId, email) {
    if (!confirm(`Are you sure you want to permanently delete ${userType} account (${email})? All data and associated listings will be removed.`)) return;
    try {
      const resp = await fetch(`/api/admin/users/${userType}/${userId}/delete`, { method: 'POST' });
      const res = await resp.json();
      if (res.ok) {
        document.querySelector(`[data-user-row="${userType}-${userId}"]`)?.remove();
        if (typeof showToast === 'function') showToast(`${userType.toUpperCase()} account deleted.`, { icon: 'trash-2' });
      } else {
        alert(res.error || 'Failed to delete account.');
      }
    } catch (err) {
      alert('Network error while deleting account.');
    }
  };

  window.resolveReport = async function (id) {
    const row = document.querySelector(`[data-report-row="${id}"]`);
    if (!row) return;
    try {
      const res = await fetch(`/api/admin/reports/${id}/resolve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (!res.ok) { showToast('Could not update the report. Please try again.', { icon: 'alert-circle' }); return; }
    } catch (e) { showToast('Network error. Please try again.', { icon: 'alert-circle' }); return; }
    const statusEl = row.querySelector(`[data-report-status="${id}"]`);
    statusEl.textContent = 'Resolved';
    statusEl.style.color = '#0E7A64';
    statusEl.classList.remove('text-rose');
    row.querySelector('button')?.remove();
    showToast('Report marked resolved.', { icon: 'check-circle-2' });
  };

  document.addEventListener('click', function(e) {
    const modBtn = e.target.closest('[data-moderate-id]');
    if (modBtn) {
      e.preventDefault();
      const id = modBtn.getAttribute('data-moderate-id');
      const act = modBtn.getAttribute('data-moderate-action');
      if (id && act && window.moderate) window.moderate(id, act);
      return;
    }
    const resBtn = e.target.closest('[data-resolve-report]');
    if (resBtn) {
      e.preventDefault();
      const rid = resBtn.getAttribute('data-resolve-report');
      if (rid && window.resolveReport) window.resolveReport(rid);
      return;
    }
  });

  applyFilter();
})();
