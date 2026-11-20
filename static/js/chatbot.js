/* JOBFLEX assistant — floating chat widget for the job seeker and employer dashboards. */
(function () {
  'use strict';
  var root = document.getElementById('jf-bot');
  if (!root) return;
  var role = root.dataset.role || 'seeker';
  var STORE = 'jf-bot-chat-' + role;
  var history = [];
  var busy = false;

  var ICON_CHAT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/><path d="M8.5 11h.01M12 11h.01M15.5 11h.01"/></svg>';
  var ICON_X = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>';
  var ICON_SEND = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></svg>';
  var ICON_BIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>';
  var ICON_SPARK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/></svg>';

  root.innerHTML =
    '<div class="jf-bot-panel" role="dialog" aria-label="JOBFLEX assistant">' +
      '<div class="jf-bot-head"><span class="jf-bot-avatar">' + ICON_SPARK + '</span>' +
        '<div><strong>JOBFLEX Assistant</strong><small>' + (role === 'employer' ? 'Hiring help' : 'Career help') + ' · online</small></div>' +
        '<button type="button" class="jf-bot-clear" aria-label="Clear chat" title="Clear chat">' + ICON_BIN + '</button>' +
        '<button type="button" class="jf-bot-close" aria-label="Close assistant">' + ICON_X + '</button></div>' +
      '<div class="jf-bot-body" aria-live="polite"></div>' +
      '<div class="jf-chips"></div>' +
      '<form class="jf-bot-form" autocomplete="off"><input type="text" maxlength="600" placeholder="Ask me anything…" aria-label="Message"><button type="submit" aria-label="Send">' + ICON_SEND + '</button></form>' +
    '</div>' +
    '<button type="button" class="jf-bot-fab" aria-label="Open JOBFLEX assistant" aria-expanded="false">' + ICON_CHAT + '</button>';

  var panel = root.querySelector('.jf-bot-panel');
  var body = root.querySelector('.jf-bot-body');
  var chips = root.querySelector('.jf-chips');
  var form = root.querySelector('form');
  var input = form.querySelector('input');
  var sendBtn = form.querySelector('button');
  var fab = root.querySelector('.jf-bot-fab');

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function fmt(text) { return esc(text).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>'); }
  function scroll() { body.scrollTop = body.scrollHeight; }
  function save() { try { sessionStorage.setItem(STORE, JSON.stringify(history.slice(-20))); } catch (e) {} }

  function addMsg(who, text, jobs) {
    var el = document.createElement('div');
    el.className = 'jf-msg ' + who;
    if (who === 'bot') el.innerHTML = fmt(text); else el.textContent = text;
    body.appendChild(el);
    if (jobs && jobs.length) {
      var list = document.createElement('div'); list.className = 'jf-jobs';
      jobs.forEach(function (j) {
        var a = document.createElement('a'); a.className = 'jf-job'; a.href = j.url;
        a.innerHTML = '<strong>' + esc(j.title) + '</strong><span>' + esc(j.company) + ' · ' + esc(j.location) + (j.salary ? ' · ' + esc(j.salary) : '') + '</span>';
        list.appendChild(a);
      });
      body.appendChild(list);
    }
    scroll();
  }
  function setChips(list) {
    chips.innerHTML = '';
    (list || []).forEach(function (t) {
      var b = document.createElement('button'); b.type = 'button'; b.className = 'jf-chip'; b.textContent = t;
      b.addEventListener('click', function () { send(t); });
      chips.appendChild(b);
    });
  }
  function typing(on) {
    var old = body.querySelector('.jf-typing-wrap');
    if (old) old.remove();
    if (!on) return;
    var w = document.createElement('div'); w.className = 'jf-msg bot jf-typing-wrap';
    w.innerHTML = '<span class="jf-typing"><i></i><i></i><i></i></span>';
    body.appendChild(w); scroll();
  }

  function send(text) {
    text = (text || '').trim();
    if (!text || busy) return;
    busy = true; sendBtn.disabled = true; input.value = '';
    addMsg('user', text);
    history.push({ role: 'user', content: text });
    typing(true);
    fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
      body: JSON.stringify({ message: text, history: history.slice(-9, -1) })
    }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        typing(false);
        if (res.ok && res.d.ok) {
          addMsg('bot', res.d.reply, res.d.jobs);
          history.push({ role: 'assistant', content: res.d.reply });
          if (res.d.suggestions) setChips(res.d.suggestions);
        } else {
          addMsg('bot', (res.d && res.d.error) || 'Sorry, something went wrong. Please try again.');
        }
        save();
      })
      .catch(function () { typing(false); addMsg('bot', 'I can\'t reach the server right now. Please check your connection and try again.'); })
      .then(function () { busy = false; sendBtn.disabled = false; input.focus(); });
  }

  function open(state) {
    root.classList.toggle('is-open', state);
    fab.setAttribute('aria-expanded', String(state));
    fab.innerHTML = state ? ICON_X : ICON_CHAT;
    if (state) { setTimeout(function () { input.focus(); }, 60); scroll(); }
  }

  function greet() {
    fetch('/api/chat/hello', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.ok) { addMsg('bot', d.greeting); setChips(d.suggestions); }
    }).catch(function () { addMsg('bot', 'Hi! I\'m your JOBFLEX assistant. How can I help?'); });
  }

  try {
    var saved = JSON.parse(sessionStorage.getItem(STORE) || '[]');
    if (saved.length) { history = saved; saved.forEach(function (m) { addMsg(m.role === 'user' ? 'user' : 'bot', m.content); }); }
    else greet();
  } catch (e) { greet(); }

  fab.addEventListener('click', function () { open(!root.classList.contains('is-open')); });
  root.querySelector('.jf-bot-close').addEventListener('click', function () { open(false); });
  root.querySelector('.jf-bot-clear').addEventListener('click', function () { history = []; save(); body.innerHTML = ''; chips.innerHTML = ''; greet(); });
  form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && root.classList.contains('is-open')) open(false); });
})();
