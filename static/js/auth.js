// Employer register / login / company setup — small progressive enhancements.
// Every form works without JavaScript; this only adds polish.
(function () {
  // Show / hide password
  document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.togglePassword);
      if (!input) return;
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-pressed', String(show));
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      btn.querySelector('[data-eye-on]')?.classList.toggle('hidden', show);
      btn.querySelector('[data-eye-off]')?.classList.toggle('hidden', !show);
    });
  });

  // Flag next to country selects follows the selected country
  document.querySelectorAll('[data-flag-select]').forEach((select) => {
    select.addEventListener('change', () => {
      const img = document.querySelector(`[data-flag-for="${select.id}"]`);
      if (!img) return;
      img.src = `https://flagcdn.com/w40/${select.value.toLowerCase()}.png`;
    });
  });

  // Loading state on submit (prevents double submits); reset if the page comes back from cache
  document.querySelectorAll('[data-auth-form]').forEach((form) => {
    form.addEventListener('submit', () => {
      const btn = form.querySelector('button[type="submit"]');
      if (btn) btn.classList.add('is-loading');
    });
  });
  window.addEventListener('pageshow', (e) => {
    if (e.persisted) document.querySelectorAll('.btn.is-loading').forEach((b) => b.classList.remove('is-loading'));
  });

  // Company setup: ABN only applies to registered businesses, and is grouped as 12 345 678 901
  const abnGroup = document.querySelector('[data-abn-group]');
  const abnInput = document.getElementById('abn');
  if (abnGroup && abnInput) {
    document.querySelectorAll('input[name="is_registered"]').forEach((radio) => {
      radio.addEventListener('change', () => {
        const registered = radio.value === 'yes' && radio.checked;
        if (radio.checked) {
          abnGroup.hidden = !registered;
          if (!registered) abnInput.value = '';
        }
      });
    });
    abnInput.addEventListener('input', () => {
      const d = abnInput.value.replace(/\D/g, '').slice(0, 11);
      abnInput.value = [d.slice(0, 2), d.slice(2, 5), d.slice(5, 8), d.slice(8, 11)].filter(Boolean).join(' ');
    });
  }

  // Focus the first field that needs attention
  const target = document.querySelector('.is-invalid') ||
    document.querySelector('[data-auth-form] input:not([type="hidden"]):not([type="radio"]):not([hidden])');
  if (target && !target.value) target.focus({ preventScroll: false });
  else if (target && target.classList.contains('is-invalid')) target.focus();
})();
