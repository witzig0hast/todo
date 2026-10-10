'use strict';
/* Todo – Single-Page-App ohne Build-Schritt. Alle Texte werden per textContent gesetzt (kein innerHTML mit Daten). */

// ------------------------------------------------------------------ Hilfsfunktionen
const ICONS = {
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>', plus: '<path d="M12 5v14M5 12h14"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  cal: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M8 3v4M16 3v4M3 10h18"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  done: '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/>',
  bus: '<rect x="3" y="4" width="18" height="12" rx="3"/><path d="M3 11h18M7 20v-4M17 20v-4M7 8h.01M17 8h.01"/>',
  bot: '<rect x="4" y="8" width="16" height="12" rx="4"/><path d="M12 8V4M9 14h.01M15 14h.01M2 14h2M20 14h2"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>',
  shield: '<path d="M12 3l8 3v6c0 4.5-3.2 8.3-8 9-4.8-.7-8-4.5-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>',
  spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>', send: '<path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
  bell: '<path d="M6 8a6 6 0 1112 0c0 7 3 8 3 8H3s3-1 3-8M10 21a2 2 0 004 0"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3"/>', out: '<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 012-2h9"/>', more: '<path d="M5 12h.01M12 12h.01M19 12h.01"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>', refresh: '<path d="M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5M21 12a9 9 0 01-15 6.7L3 16M3 21v-5h5"/>',
};
function icon(name, cls) {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('aria-hidden', 'true');
  if (cls) s.setAttribute('class', cls);
  s.innerHTML = ICONS[name] || ''; // statische Konstanten, keine Nutzerdaten
  return s;
}
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  if (props instanceof Node || typeof props !== 'object' || Array.isArray(props)) { kids.unshift(props); props = {}; }
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'value' || k === 'checked' || k === 'disabled' || k === 'selected') el[k] = v;
    else if (k === 'style') v.split(';').forEach((decl) => { const i = decl.indexOf(':'); if (i > 0) el.style.setProperty(decl.slice(0, i).trim(), decl.slice(i + 1).trim()); }); // CSSOM statt Inline-Attribut (CSP)
    else if (k === 'vars') for (const [n, val] of Object.entries(v)) el.style.setProperty(n, val);
    else el.setAttribute(k, v === true ? '' : v);
  }
  const add = (c) => {
    if (Array.isArray(c)) c.forEach(add);
    else if (c instanceof Node) el.appendChild(c);
    else if (c !== null && c !== undefined && c !== false) el.appendChild(document.createTextNode(String(c)));
  };
  kids.forEach(add);
  return el;
}
const $ = (sel, root = document) => root.querySelector(sel);
const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); return el; };
const btn = (label, cls, onclick, ic) => h('button', { class: 'btn ' + (cls || ''), onclick, type: 'button' }, ic ? icon(ic) : null, label);

function toast(msg, kind) {
  const t = h('div', { class: 'toast ' + (kind || ''), role: 'status' }, msg);
  $('#toasts').appendChild(t);
  setTimeout(() => t.remove(), 4200);
}

// ------------------------------------------------------------------ API
const state = {
  user: null, csrf: null, todos: [], lists: [], agents: [], messages: [], settings: {}, route: 'today',
  selected: null, unread: 0, pendingUsers: 0, chat: [], sse: null,
};

async function api(path, opts = {}) {
  const init = { method: opts.method || 'GET', headers: {}, credentials: 'same-origin' };
  if (state.csrf && init.method !== 'GET') init.headers['X-CSRF-Token'] = state.csrf;
  if (opts.body !== undefined) {
    if (opts.raw) { init.body = opts.body; init.headers['Content-Type'] = opts.type || 'application/octet-stream'; }
    else { init.body = JSON.stringify(opts.body); init.headers['Content-Type'] = 'application/json'; }
  }
  let res;
  try { res = await fetch('/api' + path, init); } catch (_) { throw new Error('Keine Verbindung zum Server.'); }
  if (res.status === 401 && !opts.noAuthRedirect && state.user) { state.user = null; boot(); throw new Error('Sitzung abgelaufen.'); }
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch (_) { /* leerer Body */ }
  if (!res.ok) {
    let msg = data && data.detail;
    if (Array.isArray(msg)) msg = msg.map((e) => (e.msg || '').replace(/^Value error, /, '')).join(' ');
    throw new Error(msg || 'Fehler ' + res.status);
  }
  return data;
}
const guard = (fn) => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message, 'err'); } };

// ------------------------------------------------------------------ Datum
const pad = (n) => String(n).padStart(2, '0');
const dayStart = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const endOfToday = () => new Date(dayStart(new Date()).getTime() + 86400000 - 1);
const toLocalInput = (iso) => { if (!iso) return ''; const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const fromLocalInput = (v) => (v ? new Date(v).toISOString() : null);
function fmtDue(iso) {
  const d = new Date(iso), diff = Math.round((dayStart(d) - dayStart(new Date())) / 86400000);
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const day = diff === 0 ? 'Heute' : diff === 1 ? 'Morgen' : diff === -1 ? 'Gestern'
    : d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' });
  return time === '00:00' ? day : `${day} ${time}`;
}
function fmtTs(iso) { return new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }); }
const aiCtx = () => { const n = new Date(); return { now_local: toLocalInput(n.toISOString()), tz_offset: n.getTimezoneOffset() }; };

// ------------------------------------------------------------------ Start / Anmeldung
async function boot() {
  const root = clear($('#root'));
  try {
    const me = await api('/auth/me', { noAuthRedirect: true });
    state.user = me.user; state.csrf = me.csrf;
  } catch (_) { state.user = null; }
  const ssoCode = new URLSearchParams(location.search).get('sso');
  if (ssoCode) history.replaceState(null, '', location.pathname + location.hash); // Parameter aus der URL entfernen
  if (!state.user) {
    closeStream();
    if (ssoCode === 'choose') {
      try { return renderChoose(root, await api('/auth/sso/pending', { noAuthRedirect: true })); } catch (_) { /* abgelaufen -> normale Anmeldung */ }
    }
    let sso = { providers: [], local_auth: true };
    try { sso = await api('/auth/oidc/providers', { noAuthRedirect: true }); } catch (_) { /* nur lokale Anmeldung */ }
    return renderAuth(root, sso, ssoCode === 'choose' ? 'error' : ssoCode);
  }
  await loadAll();
  renderApp(root);
  openStream();
  loadPendingCount();
  initAndroid();
  if (ssoCode === 'linked') toast('Anmeldung verknüpft', 'ok');
  if (ssoCode === 'link_taken') toast('Dieses SSO-Konto ist bereits mit einem anderen Benutzer verknüpft.', 'err');
}

const SSO_MESSAGES = {
  pending: ['notice', 'Dein Konto wurde angelegt und wartet auf die Freigabe durch einen Administrator.'],
  denied: ['error', 'Dein Konto ist gesperrt oder wurde abgelehnt.'],
  error: ['error', 'Die SSO-Anmeldung ist fehlgeschlagen. Bitte versuche es erneut.'],
};

function renderAuth(root, sso = { providers: [], local_auth: true }, ssoCode = null) {
  let mode = 'login';
  const err = h('div', { class: 'error', role: 'alert' });
  const user = h('input', { type: 'text', autocomplete: 'username', autocapitalize: 'none', spellcheck: 'false', required: true, maxlength: 64 });
  const pw = h('input', { type: 'password', required: true, maxlength: 256 });
  const submit = h('button', { class: 'btn primary', type: 'submit' }, 'Anmelden');
  const title = h('h1', {}, 'Willkommen zurück');
  const sub = h('p', { class: 'muted small' }, 'Melde dich an, um deine Aufgaben zu sehen.');
  const toggle = h('button', { type: 'button', class: 'btn sm', onclick: () => setMode(mode === 'login' ? 'register' : 'login') });
  function setMode(m) {
    mode = m; err.textContent = ''; err.className = 'error';
    const reg = m === 'register';
    submit.textContent = reg ? 'Konto anlegen' : 'Anmelden';
    title.textContent = reg ? 'Konto erstellen' : 'Willkommen zurück';
    sub.textContent = reg ? 'Der erste Benutzer wird Administrator. Alle weiteren müssen freigegeben werden.' : 'Melde dich an, um deine Aufgaben zu sehen.';
    toggle.textContent = reg ? 'Ich habe schon ein Konto' : 'Neues Konto registrieren';
    pw.autocomplete = reg ? 'new-password' : 'current-password';
    pw.setAttribute('minlength', reg ? '10' : '1');
    pw.placeholder = reg ? 'Mindestens 10 Zeichen' : '';
  }
  const local = sso.local_auth;
  const fieldUser = h('label', { class: 'field' }, 'Benutzername', user), fieldPw = h('label', { class: 'field' }, 'Passwort', pw);
  const toggleRow = h('div', { class: 'row', style: 'justify-content:center' }, toggle);
  const ssoButtons = sso.providers.map((p) => h('a', { class: 'btn' + (local ? '' : ' primary'), href: '/api/auth/oidc/' + encodeURIComponent(p.id) + '/login' }, icon('key'), 'Mit ' + p.name + ' anmelden'));
  const form = h('form', { class: 'col', onsubmit: async (e) => {
    e.preventDefault(); err.textContent = ''; submit.disabled = true;
    try {
      const r = await api(mode === 'login' ? '/auth/login' : '/auth/register', { method: 'POST', body: { username: user.value, password: pw.value }, noAuthRedirect: true });
      if (mode === 'register' && r.status === 'pending') {
        err.className = 'error notice'; err.textContent = 'Registriert! Ein Administrator muss dein Konto noch freigeben.'; setMode('login'); err.className = 'error notice'; err.textContent = 'Registriert! Ein Administrator muss dein Konto noch freigeben.'; pw.value = '';
      } else { boot(); }
    } catch (ex) { err.textContent = ex.message; } finally { submit.disabled = false; }
  } },
  h('div', { style: 'text-align:center' }, h('div', { class: 'logo' }, icon('check')), title, sub),
  ssoButtons, ssoButtons.length > 0 && local ? h('div', { class: 'divider' }, h('span', {}, 'oder')) : null,
  local ? [fieldUser, fieldPw] : null, err, local ? submit : null, local ? toggleRow : null);
  setMode('login');
  if (!local) sub.textContent = 'Melde dich mit deinem Single-Sign-On-Konto an.';
  if (ssoCode && SSO_MESSAGES[ssoCode]) { err.className = 'error ' + (SSO_MESSAGES[ssoCode][0] === 'notice' ? 'notice' : ''); err.textContent = SSO_MESSAGES[ssoCode][1]; }
  root.appendChild(h('div', { class: 'auth' }, h('div', { class: 'auth-card glass' }, form)));
  if (local) user.focus();
}

// Nach dem ersten SSO-Login, wenn es schon Passwort-Konten gibt: neues Konto anlegen oder bestehendes verknüpfen.
function renderChoose(root, info) {
  const err = h('div', { class: 'error', role: 'alert' });
  const user = h('input', { type: 'text', autocomplete: 'username', autocapitalize: 'none', spellcheck: 'false', required: true, maxlength: 64 });
  const pw = h('input', { type: 'password', autocomplete: 'current-password', required: true, maxlength: 256 });
  const submit = h('button', { class: 'btn primary', type: 'submit' }, icon('key'), 'Mit diesem Konto verknüpfen');
  const done = async (r) => {
    if (r.status === 'ok') return boot();
    const [kind, text] = SSO_MESSAGES[r.status] || SSO_MESSAGES.error;
    err.className = 'error ' + (kind === 'notice' ? 'notice' : ''); err.textContent = text;
    if (r.status === 'pending') setTimeout(() => boot(), 2500);
  };
  const form = h('form', { class: 'col', onsubmit: async (e) => {
    e.preventDefault(); err.textContent = ''; submit.disabled = true;
    try { await done(await api('/auth/sso/pending/link', { method: 'POST', body: { username: user.value, password: pw.value }, noAuthRedirect: true })); }
    catch (ex) { err.className = 'error'; err.textContent = ex.message; } finally { submit.disabled = false; }
  } },
  h('div', { style: 'text-align:center' }, h('div', { class: 'logo' }, icon('key')), h('h1', {}, 'Mit ' + info.provider_name + ' angemeldet'),
    h('p', { class: 'muted small' }, (info.email || info.username || '') + (info.email || info.username ? ' · ' : '') + 'Hast du schon ein Konto in Todo?')),
  h('p', { class: 'small muted' }, 'Verknüpfe ' + info.provider_name + ' mit deinem bestehenden Konto – zur Bestätigung gibst du dessen Zugangsdaten ein. Danach meldest du dich künftig direkt per SSO an.'),
  h('label', { class: 'field' }, 'Benutzername des bestehenden Kontos', user), h('label', { class: 'field' }, 'Passwort', pw), err, submit,
  h('div', { class: 'divider' }, h('span', {}, 'oder')),
  btn('Neues Konto erstellen', '', guard(async () => { err.textContent = ''; try { await done(await api('/auth/sso/pending/create', { method: 'POST', noAuthRedirect: true })); } catch (ex) { err.className = 'error'; err.textContent = ex.message; } })),
  h('div', { class: 'row', style: 'justify-content:center' }, btn('Abbrechen', 'sm', guard(async () => { await api('/auth/sso/pending', { method: 'DELETE', noAuthRedirect: true }); boot(); }))));
  root.appendChild(h('div', { class: 'auth' }, h('div', { class: 'auth-card glass' }, form)));
  user.focus();
}

async function loadAll() {
  const [t, l, s] = await Promise.all([api('/todos'), api('/lists'), api('/settings')]);
  state.todos = t.todos; state.lists = l.lists; state.settings = s;
}
const loadPendingCount = guard(async () => {
  if (state.user.role !== 'admin') return;
  const { users } = await api('/admin/users');
  state.pendingUsers = users.filter((u) => u.status === 'pending').length; renderChrome();
});

// ------------------------------------------------------------------ Live-Stream (SSE)
function openStream() {
  closeStream();
  const es = new EventSource('/api/agent-bus/stream');
  state.sse = es;
  es.addEventListener('todo', guard(async () => { state.todos = (await api('/todos')).todos; renderTodos(); renderChrome(); renderDetail(); }));
  es.addEventListener('bus', (e) => {
    const m = JSON.parse(e.data);
    const i = state.messages.findIndex((x) => x.id === m.id);
    if (i >= 0) state.messages[i] = m; else { state.messages.unshift(m); if (m.from_label !== 'todo' && state.route !== 'bus') { state.unread++; toast(`Neue Nachricht von ${m.from_label}`); } }
    if (state.route === 'bus') renderLog(); renderChrome();
  });
  es.addEventListener('admin', (e) => { const d = JSON.parse(e.data); if (d.op === 'pending_user') { state.pendingUsers++; toast(`${d.username} wartet auf Freigabe`); renderChrome(); if (state.route === 'admin') route(); } if (d.op === 'deleted') boot(); });
}
function closeStream() { if (state.sse) { state.sse.close(); state.sse = null; } }

// ------------------------------------------------------------------ App-Gerüst
const NAV = [
  { id: 'today', label: 'Heute', icon: 'sun' }, { id: 'upcoming', label: 'Geplant', icon: 'cal' },
  { id: 'all', label: 'Alle', icon: 'list' }, { id: 'done', label: 'Erledigt', icon: 'done' },
];
const open = (t) => !t.done && !t.parent_id;
const counts = () => ({
  today: state.todos.filter((t) => open(t) && t.due_at && new Date(t.due_at) <= endOfToday()).length,
  upcoming: state.todos.filter((t) => open(t) && t.due_at && new Date(t.due_at) > endOfToday()).length,
  all: state.todos.filter(open).length, done: state.todos.filter((t) => t.done && !t.parent_id).length,
});

function renderApp(root) {
  clear(root);
  root.appendChild(h('div', { class: 'app', id: 'app' },
    h('nav', { class: 'side', id: 'side', 'aria-label': 'Navigation' }),
    h('main', { class: 'main', id: 'main' }, h('div', { class: 'main-inner', id: 'view' })),
    h('aside', { class: 'detail-pane', id: 'detail-pane', 'aria-label': 'Details' }),
    h('nav', { class: 'tabbar', id: 'tabbar', 'aria-label': 'Hauptnavigation' }),
    h('button', { class: 'fab', id: 'fab', 'aria-label': 'Neue Aufgabe', onclick: () => { go('today'); setTimeout(() => { const i = $('#quick-input'); if (i) i.focus(); }, 50); } }, icon('plus'))));
  window.removeEventListener('hashchange', route); window.addEventListener('hashchange', route);
  route();
}
function go(r) { location.hash = '#/' + r; }
function currentRoute() { return (location.hash.replace(/^#\/?/, '').split('?')[0]) || 'today'; }

function route() {
  state.route = currentRoute();
  if (state.route === 'bus') state.unread = 0;
  state.selected = null;
  const view = clear($('#view'));
  const r = state.route;
  if (NAV.some((n) => n.id === r) || r.startsWith('list/')) viewTasks(view);
  else if (r === 'bus') viewBus(view);
  else if (r === 'assistant') viewAssistant(view);
  else if (r === 'settings') viewSettings(view);
  else if (r === 'admin' && state.user.role === 'admin') viewAdmin(view);
  else { go('today'); return; }
  $('#fab').classList.toggle('hidden', !(NAV.some((n) => n.id === r) || r.startsWith('list/')) || r === 'done');
  $('#main').scrollTop = 0;
  renderChrome(); renderDetail();
}

function renderChrome() {
  const c = counts();
  const item = (id, label, ic, extra) => h('button', { class: 'nav-item' + (state.route === id ? ' on' : ''), onclick: () => go(id) }, icon(ic), label, extra);
  const side = clear($('#side'));
  if (!side) return;
  side.appendChild(h('div', { class: 'brand' }, h('div', { class: 'logo' }, icon('check')), 'Todo'));
  NAV.forEach((n) => side.appendChild(item(n.id, n.label, n.icon, h('span', { class: 'count' }, n.id === 'done' ? '' : c[n.id] || ''))));
  side.appendChild(h('div', { class: 'nav-sep' }));
  side.appendChild(h('div', { class: 'nav-title' }, 'Listen', h('button', { class: 'icon-btn', style: 'width:28px;height:28px', 'aria-label': 'Neue Liste', onclick: newList }, icon('plus'))));
  state.lists.forEach((l) => {
    const n = state.todos.filter((t) => open(t) && t.list_id === l.id).length;
    side.appendChild(h('button', { class: 'nav-item' + (state.route === 'list/' + l.id ? ' on' : ''), onclick: () => go('list/' + l.id) }, icon('list'), h('span', { class: 'grow', style: 'overflow:hidden;text-overflow:ellipsis' }, l.name), h('span', { class: 'count' }, n || '')));
  });
  side.appendChild(h('div', { class: 'nav-sep' }));
  side.appendChild(item('bus', 'Agent Bus', 'bus', state.unread ? h('span', { class: 'count chip solid' }, state.unread) : null));
  side.appendChild(item('assistant', 'Assistent', 'bot'));
  if (state.user.role === 'admin') side.appendChild(item('admin', 'Admin', 'shield', state.pendingUsers ? h('span', { class: 'count chip solid' }, state.pendingUsers) : null));
  side.appendChild(h('div', { class: 'grow' }));
  side.appendChild(item('settings', 'Einstellungen', 'gear'));
  side.appendChild(h('div', { class: 'muted small', style: 'padding:6px 12px' }, `${state.user.username} · ${state.user.role === 'admin' ? 'Admin' : 'Benutzer'}`));

  const tabs = clear($('#tabbar'));
  const tab = (id, label, ic, badge, active) => h('button', { class: 'tab' + (active ? ' on' : ''), onclick: () => go(id) }, icon(ic), label, badge ? h('span', { class: 'badge' }, badge) : null);
  const taskRoute = NAV.some((n) => n.id === state.route) || state.route.startsWith('list/');
  tabs.appendChild(tab('today', 'Aufgaben', 'check', c.today, taskRoute));
  tabs.appendChild(tab('bus', 'Bus', 'bus', state.unread, state.route === 'bus'));
  tabs.appendChild(tab('assistant', 'Assistent', 'bot', 0, state.route === 'assistant'));
  const more = state.route === 'settings' || state.route === 'admin';
  tabs.appendChild(tab('settings', 'Mehr', 'gear', state.pendingUsers, more));
}

const guardList = guard;
const newList = guardList(async () => {
  const name = prompt('Name der neuen Liste:');
  if (!name || !name.trim()) return;
  const colors = ['#8b6bff', '#3ed1c0', '#ff6b81', '#ffb454', '#5ab0ff', '#9be15d'];
  const l = await api('/lists', { method: 'POST', body: { name: name.trim(), color: colors[state.lists.length % colors.length] } });
  state.lists.push(l); renderChrome(); go('list/' + l.id);
});

// ------------------------------------------------------------------ Aufgaben-Ansicht
function filteredTodos() {
  const r = state.route, end = endOfToday();
  let items = state.todos.filter((t) => !t.parent_id);
  if (r === 'today') items = items.filter((t) => !t.done && t.due_at && new Date(t.due_at) <= end);
  else if (r === 'upcoming') items = items.filter((t) => !t.done && t.due_at && new Date(t.due_at) > end);
  else if (r === 'all') items = items.filter((t) => !t.done);
  else if (r === 'done') items = items.filter((t) => t.done).sort((a, b) => (b.done_at || '').localeCompare(a.done_at || ''));
  else if (r.startsWith('list/')) items = items.filter((t) => t.list_id === Number(r.slice(5)));
  return items;
}
const titles = { today: 'Heute', upcoming: 'Geplant', all: 'Alle Aufgaben', done: 'Erledigt' };

function viewTasks(view) {
  const r = state.route;
  const list = r.startsWith('list/') ? state.lists.find((l) => l.id === Number(r.slice(5))) : null;
  if (r.startsWith('list/') && !list) { go('today'); return; }
  const hour = new Date().getHours();
  const greet = hour < 11 ? 'Guten Morgen' : hour < 18 ? 'Hallo' : 'Guten Abend';
  view.appendChild(h('div', { class: 'page-head' },
    h('div', {}, h('h1', {}, list ? list.name : titles[r]), h('div', { class: 'muted small', id: 'subtitle' }, `${greet}, ${state.user.username}`)),
    list ? h('div', { class: 'row' },
      h('button', { class: 'icon-btn', 'aria-label': 'Liste umbenennen', onclick: guard(async () => { const n = prompt('Neuer Name:', list.name); if (!n || !n.trim()) return; Object.assign(list, await api('/lists/' + list.id, { method: 'PATCH', body: { name: n.trim() } })); route(); }) }, icon('more')),
      h('button', { class: 'icon-btn', 'aria-label': 'Liste löschen', onclick: guard(async () => { if (!confirm(`Liste „${list.name}“ löschen? Aufgaben bleiben erhalten.`)) return; await api('/lists/' + list.id, { method: 'DELETE' }); state.lists = state.lists.filter((x) => x.id !== list.id); state.todos.forEach((t) => { if (t.list_id === list.id) t.list_id = null; }); go('today'); }) }, icon('trash'))) : null,
    r === 'done' ? btn('Aufräumen', 'sm danger', guard(async () => { if (!confirm('Alle erledigten Aufgaben löschen?')) return; await api('/todos/clear-done', { method: 'POST' }); }), 'trash') : null));
  if (r !== 'done') view.appendChild(quickBar());
  view.appendChild(h('div', { id: 'draft' }));
  view.appendChild(h('div', { id: 'progress' }));
  view.appendChild(h('div', { class: 'todo-list', id: 'todos' }));
  renderTodos();
  if (location.hash.includes('new=1')) setTimeout(() => { const i = $('#quick-input'); if (i) i.focus(); }, 50);
}

function quickBar() {
  const input = h('input', { type: 'text', id: 'quick-input', placeholder: 'Neue Aufgabe oder einfach sprechen …', maxlength: 300, autocomplete: 'off', enterkeyhint: 'done' });
  const bar = h('form', { class: 'quick glass', onsubmit: guard(async (e) => {
    e.preventDefault();
    const title = input.value.trim(); if (!title) return;
    const t = await api('/todos', { method: 'POST', body: { title, list_id: currentListId() } });
    state.todos.push(t); input.value = ''; renderTodos(); renderChrome();
  }) },
  input,
  h('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Mit KI auswerten', title: 'Mit KI auswerten', onclick: () => aiDraft(input.value.trim(), input) }, icon('spark')),
  h('button', { class: 'icon-btn mic', type: 'button', id: 'mic', 'aria-label': 'Spracheingabe', title: 'Spracheingabe', onclick: () => toggleRecord(input, bar) }, icon('mic')),
  h('button', { class: 'icon-btn', type: 'submit', 'aria-label': 'Hinzufügen' }, icon('plus')));
  return bar;
}
const currentListId = () => (state.route.startsWith('list/') ? Number(state.route.slice(5)) : null);

const aiDraft = guard(async (text, input) => {
  if (!text) { toast('Bitte zuerst Text eingeben oder sprechen.'); return; }
  const slot = clear($('#draft'));
  slot.appendChild(h('div', { class: 'glass card row' }, h('div', { class: 'spinner' }), h('span', { class: 'muted' }, 'KI analysiert …')));
  let d;
  try { d = await api('/ai/parse', { method: 'POST', body: { text, ...aiCtx() } }); } catch (e) { clear(slot); throw e; }
  showDraft(d, input);
});

function showDraft(d, input) {
  const slot = clear($('#draft'));
  const title = h('input', { type: 'text', value: d.title, maxlength: 300 });
  const due = h('input', { type: 'datetime-local', value: toLocalInput(d.due_at) });
  let prio = d.priority;
  const seg = prioSeg(prio, (p) => { prio = p; });
  slot.appendChild(h('div', { class: 'glass draft col' },
    h('div', { class: 'row muted small' }, icon('spark'), 'KI-Vorschlag – bitte prüfen'),
    title, h('div', { class: 'row wrap' }, h('div', { class: 'grow' }, due)), seg,
    h('div', { class: 'row' }, h('div', { class: 'grow' }),
      btn('Verwerfen', 'sm', () => clear(slot)),
      btn('Speichern', 'sm primary', guard(async () => {
        const t = await api('/todos', { method: 'POST', body: { title: title.value, notes: d.notes || '', priority: prio, due_at: fromLocalInput(due.value), list_id: currentListId() } });
        state.todos.push(t); if (input) input.value = ''; clear(slot); renderTodos(); renderChrome(); toast('Aufgabe gespeichert', 'ok');
      }), 'check'))));
}

function prioSeg(initial, onChange) {
  const labels = ['Keine', 'Niedrig', 'Mittel', 'Hoch'];
  const seg = h('div', { class: 'seg', role: 'group', 'aria-label': 'Priorität' });
  const draw = (cur) => { clear(seg); labels.forEach((l, i) => seg.appendChild(h('button', { type: 'button', class: i === cur ? 'on' : '', onclick: () => { onChange(i); draw(i); } }, l))); };
  draw(initial); return seg;
}

function renderTodos() {
  const box = $('#todos'); if (!box) return;
  clear(box);
  const items = filteredTodos();
  const r = state.route;
  const p = clear($('#progress'));
  if (r === 'today') {
    const isToday = (iso) => iso && dayStart(new Date(iso)).getTime() === dayStart(new Date()).getTime();
    const doneToday = state.todos.filter((t) => !t.parent_id && t.done && isToday(t.done_at)).length;
    if (doneToday + items.length > 0) {
      const bar = h('i'); bar.style.width = Math.round((100 * doneToday) / (doneToday + items.length)) + '%';
      p.appendChild(h('div', { class: 'col', style: 'gap:6px' }, h('div', { class: 'muted small' }, `${doneToday} von ${doneToday + items.length} erledigt`), h('div', { class: 'progress' }, bar)));
    }
  }
  if (!items.length) {
    box.appendChild(h('div', { class: 'empty' }, icon(r === 'done' ? 'done' : 'check'), h('div', {}, r === 'done' ? 'Noch nichts erledigt.' : r === 'today' ? 'Alles erledigt.' : 'Keine Aufgaben hier.')));
    return;
  }
  const grouped = r === 'upcoming' || r === 'today';
  const groupName = (t) => {
    if (!grouped || !t.due_at) return null;
    const d = new Date(t.due_at);
    if (d < dayStart(new Date())) return 'Überfällig';
    return fmtDue(t.due_at).replace(/ \d\d:\d\d$/, '');
  };
  let last, rows;
  items.forEach((t) => {
    const g = groupName(t);
    if (!rows || g !== last) {
      rows = h('div', { class: 'rows glass' });
      box.appendChild(h('section', { class: 'group' }, g ? h('div', { class: 'group-title' }, g) : null, rows));
      last = g;
    }
    rows.appendChild(todoRow(t));
  });
}

function todoRow(t) {
  const subs = state.todos.filter((s) => s.parent_id === t.id);
  const list = state.lists.find((l) => l.id === t.list_id);
  const overdue = !t.done && t.due_at && new Date(t.due_at) < new Date();
  const row = h('div', { class: 'todo' + (t.done ? ' done' : '') + (state.selected === t.id ? ' sel' : ''), 'data-id': t.id },
    h('button', { class: 'check p' + t.priority, type: 'button', role: 'checkbox', 'aria-checked': String(t.done), 'aria-label': t.done ? 'Als offen markieren' : 'Erledigen', onclick: (e) => { e.stopPropagation(); toggleDone(t); } }, icon('check')),
    h('div', { class: 't-body', onclick: () => select(t.id) },
      h('div', { class: 't-title' }, t.title),
      h('div', { class: 't-meta' },
        t.due_at ? h('span', { class: 'chip' + (overdue ? ' danger' : '') }, icon('clock'), fmtDue(t.due_at)) : null,
        list ? h('span', { class: 'chip' }, list.name) : null,
        subs.length ? h('span', { class: 'chip' }, `${subs.filter((s) => s.done).length}/${subs.length}`) : null,
        t.priority > 0 ? h('span', { class: 'chip' + (t.priority === 3 ? ' danger' : '') }, icon('flag'), ['', 'Niedrig', 'Mittel', 'Hoch'][t.priority]) : null,
        t.created_by !== 'user' ? h('span', { class: 'chip' }, icon('bus'), t.created_by) : null)));
  const wrap = h('div', { class: 'todo-wrap' },
    h('div', { class: 'swipe-bg' }, h('span', { class: 'l' }, icon('check')), h('span', { class: 'r' }, icon('trash'))), row);
  attachSwipe(row, t);
  return wrap;
}

function attachSwipe(row, t) {
  let x0 = null, y0 = 0, dx = 0, locked = false;
  row.addEventListener('pointerdown', (e) => { if (e.pointerType === 'mouse') return; x0 = e.clientX; y0 = e.clientY; dx = 0; locked = false; });
  row.addEventListener('pointermove', (e) => {
    if (x0 === null) return;
    dx = e.clientX - x0;
    if (!locked && Math.abs(e.clientY - y0) > 14 && Math.abs(dx) < 14) { x0 = null; return; }
    if (Math.abs(dx) > 12) { locked = true; row.classList.add('dragging'); row.parentElement.classList.add('swiping'); row.style.transform = `translateX(${dx}px)`; try { row.setPointerCapture(e.pointerId); } catch (_) { /* ignorieren */ } }
  });
  const end = guard(async () => {
    if (x0 === null) return; x0 = null;
    row.classList.remove('dragging'); row.parentElement.classList.remove('swiping'); row.style.transform = '';
    if (dx > 90) await toggleDone(t); else if (dx < -90) await deleteTodo(t);
  });
  row.addEventListener('pointerup', end); row.addEventListener('pointercancel', end);
}

const toggleDone = guard(async (t) => {
  const u = await api('/todos/' + t.id, { method: 'PATCH', body: { done: !t.done } });
  Object.assign(t, u); renderTodos(); renderChrome(); renderDetail();
});
const deleteTodo = guard(async (t) => {
  await api('/todos/' + t.id, { method: 'DELETE' });
  state.todos = state.todos.filter((x) => x.id !== t.id && x.parent_id !== t.id);
  if (state.selected === t.id) state.selected = null;
  renderTodos(); renderChrome(); renderDetail(); toast('Aufgabe gelöscht');
});

// ------------------------------------------------------------------ Detail (Sheet auf Mobil, Seitenleiste am PC)
const wide = () => window.matchMedia('(min-width: 1280px)').matches;
function select(id) { state.selected = id; renderTodos(); renderDetail(); }
function renderDetail() {
  const app = $('#app'), pane = clear($('#detail-pane'));
  document.querySelectorAll('.overlay.detail').forEach((o) => o.remove());
  const t = state.todos.find((x) => x.id === state.selected);
  const show = !!t && !['bus', 'assistant', 'settings', 'admin'].includes(state.route);
  app.classList.toggle('has-detail', show && wide());
  if (!show) return;
  const body = detailBody(t);
  if (wide()) pane.appendChild(body);
  else {
    const ov = h('div', { class: 'overlay detail', onclick: (e) => { if (e.target === ov) { state.selected = null; renderTodos(); renderDetail(); } } }, h('div', { class: 'sheet', role: 'dialog', 'aria-modal': 'true' }, h('div', { class: 'grab' }), body));
    document.body.appendChild(ov);
  }
}

function detailBody(t) {
  const save = guard(async (patch) => { Object.assign(t, await api('/todos/' + t.id, { method: 'PATCH', body: patch })); renderTodos(); renderChrome(); });
  const title = h('input', { type: 'text', value: t.title, maxlength: 300, 'aria-label': 'Titel', onchange: () => title.value.trim() && save({ title: title.value }) });
  const notes = h('textarea', { 'aria-label': 'Notizen', placeholder: 'Notizen …', maxlength: 5000, onchange: () => save({ notes: notes.value }) }, t.notes);
  notes.value = t.notes;
  const due = h('input', { type: 'datetime-local', value: toLocalInput(t.due_at), 'aria-label': 'Fälligkeit', onchange: () => save({ due_at: fromLocalInput(due.value) }) });
  const sel = h('select', { 'aria-label': 'Liste', onchange: () => save({ list_id: sel.value ? Number(sel.value) : null }) },
    h('option', { value: '' }, 'Keine Liste'), state.lists.map((l) => h('option', { value: l.id, selected: l.id === t.list_id }, l.name)));
  const subsBox = h('div', { class: 'col', style: 'gap:2px' });
  const drawSubs = () => {
    clear(subsBox);
    state.todos.filter((s) => s.parent_id === t.id).forEach((s) => subsBox.appendChild(h('div', { class: 'sub' + (s.done ? ' done' : '') },
      h('button', { class: 'check', style: 'width:22px;height:22px', type: 'button', role: 'checkbox', 'aria-checked': String(s.done), 'aria-label': 'Unteraufgabe erledigen', onclick: guard(async () => { Object.assign(s, await api('/todos/' + s.id, { method: 'PATCH', body: { done: !s.done } })); drawSubs(); renderTodos(); }) }, icon('check')),
      h('span', { class: 'grow' }, s.title),
      h('button', { class: 'icon-btn', style: 'width:32px;height:32px', 'aria-label': 'Entfernen', onclick: guard(async () => { await api('/todos/' + s.id, { method: 'DELETE' }); state.todos = state.todos.filter((x) => x.id !== s.id); drawSubs(); renderTodos(); }) }, icon('x')))));
  };
  const subInput = h('input', { type: 'text', placeholder: 'Unteraufgabe hinzufügen …', maxlength: 300, enterkeyhint: 'done' });
  const addSub = guard(async (title) => { state.todos.push(await api('/todos', { method: 'POST', body: { title, parent_id: t.id, list_id: t.list_id } })); drawSubs(); renderTodos(); });
  drawSubs();
  const aiBtn = btn('Mit KI zerlegen', 'sm', guard(async () => {
    aiBtn.disabled = true;
    try {
      const { subtasks } = await api('/ai/breakdown', { method: 'POST', body: { title: t.title, notes: t.notes } });
      for (const s of subtasks) await addSub(s);
      toast(`${subtasks.length} Unteraufgaben angelegt`, 'ok');
    } finally { aiBtn.disabled = false; }
  }), 'spark');
  return h('div', { class: 'col', style: 'gap:14px' },
    h('div', { class: 'row' }, h('h2', { class: 'grow' }, 'Details'), h('button', { class: 'icon-btn', 'aria-label': 'Schließen', onclick: () => { state.selected = null; renderTodos(); renderDetail(); } }, icon('x'))),
    h('label', { class: 'field' }, 'Titel', title), h('label', { class: 'field' }, 'Notizen', notes),
    h('label', { class: 'field' }, 'Fällig', due), h('label', { class: 'field' }, 'Liste', sel),
    h('div', { class: 'field' }, 'Priorität', prioSeg(t.priority, (p) => save({ priority: p }))),
    h('div', { class: 'col', style: 'gap:6px' }, h('div', { class: 'row' }, h('span', { class: 'muted small grow' }, 'Unteraufgaben'), aiBtn), subsBox,
      h('form', { class: 'row', onsubmit: (e) => { e.preventDefault(); const v = subInput.value.trim(); if (v) { subInput.value = ''; addSub(v); } } }, subInput, h('button', { class: 'icon-btn', type: 'submit', 'aria-label': 'Hinzufügen' }, icon('plus')))),
    h('div', { class: 'muted small' }, `Erstellt ${fmtTs(t.created_at)}${t.created_by !== 'user' ? ' von Agent ' + t.created_by : ''}`),
    btn('Aufgabe löschen', 'danger', () => deleteTodo(t), 'trash'));
}

// ------------------------------------------------------------------ Spracheingabe (Whisper)
let rec = null;
async function toggleRecord(input, bar) {
  const mic = $('#mic');
  if (rec) { rec.stop(); return; }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { toast('Mikrofon nur über HTTPS verfügbar.', 'err'); return; }
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } }); }
  catch (_) { toast('Mikrofon-Zugriff verweigert.', 'err'); return; }
  const mr = new MediaRecorder(stream), chunks = [];
  mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  mr.onstop = async () => {
    stream.getTracks().forEach((tr) => tr.stop()); rec = null;
    mic.classList.remove('rec'); bar.classList.remove('rec');
    input.placeholder = 'Wird transkribiert …'; input.disabled = true;
    try {
      const wav = await blobToWav16k(new Blob(chunks, { type: mr.mimeType }));
      const { text } = await api('/voice/transcribe', { method: 'POST', body: wav, raw: true, type: 'audio/wav' });
      if (!text) { toast('Nichts verstanden – bitte nochmal versuchen.'); return; }
      input.value = text; input.disabled = false;
      await aiDraft(text, input).catch(() => {});
    } catch (e) { toast(e.message, 'err'); }
    finally { input.disabled = false; input.placeholder = 'Neue Aufgabe …'; }
  };
  rec = mr; mr.start(); mic.classList.add('rec'); bar.classList.add('rec');
  setTimeout(() => { if (rec === mr) mr.stop(); }, 110000);
}

async function blobToWav16k(blob) {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  const ctx = new Ctx();
  const decoded = await ctx.decodeAudioData(await blob.arrayBuffer()); ctx.close();
  const off = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * 16000)), 16000);
  const src = off.createBufferSource(); src.buffer = decoded; src.connect(off.destination); src.start();
  const data = (await off.startRendering()).getChannelData(0);
  const buf = new ArrayBuffer(44 + data.length * 2), v = new DataView(buf);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, 'RIFF'); v.setUint32(4, 36 + data.length * 2, true); str(8, 'WAVEfmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
  v.setUint16(22, 1, true); v.setUint32(24, 16000, true); v.setUint32(28, 32000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, 'data'); v.setUint32(40, data.length * 2, true);
  for (let i = 0; i < data.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, data[i])) * 0x7fff, true);
  return new Blob([buf], { type: 'audio/wav' });
}

// ------------------------------------------------------------------ Agent Bus
function viewBus(view) {
  view.appendChild(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, 'Agent Bus'), h('div', { class: 'muted small' }, 'Nachrichten & Aufgaben zwischen deinen Projekten und Todo')),
    btn('Agent', 'sm primary', newAgentSheet, 'plus')));
  view.appendChild(h('div', { id: 'agents', class: 'col' }));
  view.appendChild(h('details', { class: 'glass card' }, h('summary', {}, 'So verbindest du ein Projekt'),
    h('div', { class: 'col', style: 'margin-top:12px' }, h('p', { class: 'muted small' }, 'Jeder Agent hat einen eigenen Key (Header X-Agent-Key). Beispiele:'),
      h('pre', { class: 'code' }, apiExamples()))));
  view.appendChild(sendForm());
  view.appendChild(h('div', { class: 'row' }, h('h2', { class: 'grow' }, 'Log'), h('select', { id: 'log-filter', style: 'width:auto', 'aria-label': 'Filter', onchange: guard(loadMessages) }, h('option', { value: '' }, 'Alle'))));
  view.appendChild(h('div', { id: 'log', class: 'col' }));
  refreshAgents().then(loadMessages);
}
function apiExamples() {
  const o = location.origin;
  return `# Todo anlegen (Scope todos:write)
curl -X POST ${o}/api/agent-bus/agent/messages \\
  -H "X-Agent-Key: tdo_…" -H "Content-Type: application/json" \\
  -d '{"to":"todo","kind":"task","task_type":"todo.create",
       "payload":{"title":"Backup prüfen","due_at":"2026-10-06T09:00:00Z"}}'

# Nachricht an dich (löst Push aus)
curl -X POST ${o}/api/agent-bus/agent/messages -H "X-Agent-Key: tdo_…" \\
  -H "Content-Type: application/json" -d '{"to":"todo","kind":"text","content":"Deploy fertig"}'

# Posteingang pollen / Live-Stream (SSE)
curl -H "X-Agent-Key: tdo_…" "${o}/api/agent-bus/inbox?after_id=0"
curl -N -H "X-Agent-Key: tdo_…" ${o}/api/agent-bus/inbox/stream

# Task-Ergebnis melden
curl -X POST ${o}/api/agent-bus/messages/ID/result -H "X-Agent-Key: tdo_…" \\
  -H "Content-Type: application/json" -d '{"status":"completed","result":{"ok":true}}'

# Benachrichtigung an ein Gerät (Scope notify; "device" weglassen = alle Geräte)
curl -X POST ${o}/api/agent-bus/agent/messages -H "X-Agent-Key: tdo_…" \\
  -H "Content-Type: application/json" -d '{"to":"todo","kind":"task","task_type":"device.notify",
  "payload":{"device":"Pixel 8","title":"Build fertig","body":"main ist grün","url":"/#/bus"}}'

# Task-Typen: todo.create, todo.list, todo.complete, device.notify`;
}
const refreshAgents = guard(async () => {
  state.agents = (await api('/agent-bus/agents')).agents;
  const box = $('#agents'); if (!box) return; clear(box);
  if (!state.agents.length) box.appendChild(h('div', { class: 'empty glass' }, icon('bus'), h('div', {}, 'Noch keine Agents. Lege einen an, um ein Projekt anzubinden.')));
  state.agents.forEach((a) => box.appendChild(h('div', { class: 'glass card col', style: 'gap:10px' },
    h('div', { class: 'row' }, h('div', { class: 'avatar' }, a.name[0]), h('div', { class: 'grow' }, h('h3', {}, a.name), h('div', { class: 'muted small' }, a.description || 'Keine Beschreibung')),
      h('button', { class: 'icon-btn', 'aria-label': 'Neuen Key erzeugen', title: 'Key rotieren', onclick: guard(async () => { if (!confirm('Neuen Key erzeugen? Der alte wird sofort ungültig.')) return; keySheet(a.name, (await api(`/agent-bus/agents/${a.id}/rotate`, { method: 'POST' })).api_key); }) }, icon('key')),
      h('button', { class: 'icon-btn', 'aria-label': 'Agent löschen', onclick: guard(async () => { if (!confirm(`Agent „${a.name}“ löschen?`)) return; await api('/agent-bus/agents/' + a.id, { method: 'DELETE' }); refreshAgents(); }) }, icon('trash'))),
    h('div', { class: 'row wrap' }, a.scopes.map((s) => h('span', { class: 'chip' }, s)), h('span', { class: 'chip' }, a.key_prefix + '…'), h('span', { class: 'chip' }, a.last_seen_at ? 'zuletzt ' + fmtTs(a.last_seen_at) : 'noch nie verbunden')))));
  const f = $('#log-filter');
  if (f) { const cur = f.value; clear(f); f.appendChild(h('option', { value: '' }, 'Alle')); state.agents.forEach((a) => f.appendChild(h('option', { value: a.name, selected: a.name === cur }, a.name))); }
  const to = $('#send-to');
  if (to) { clear(to); state.agents.forEach((a) => to.appendChild(h('option', { value: a.name }, a.name))); }
});

function sheet(content, onClose) {
  const ov = h('div', { class: 'overlay', onclick: (e) => { if (e.target === ov) close(); } }, h('div', { class: 'sheet', role: 'dialog', 'aria-modal': 'true' }, h('div', { class: 'grab' }), content));
  const close = () => { ov.remove(); if (onClose) onClose(); };
  document.body.appendChild(ov); return close;
}
function keySheet(name, key) {
  const close = sheet(h('div', { class: 'col' }, h('h2', {}, `Key für „${name}“`),
    h('p', { class: 'muted small' }, 'Dieser Key wird nur jetzt angezeigt. Speichere ihn sicher – später ist nur noch ein Hash hinterlegt.'),
    h('div', { class: 'key-box' }, key),
    h('div', { class: 'row' }, btn('Kopieren', 'primary', async () => { try { await navigator.clipboard.writeText(key); toast('Kopiert', 'ok'); } catch (_) { toast('Bitte manuell kopieren.'); } }, 'copy'), btn('Fertig', '', () => close()))));
}
function newAgentSheet() {
  const name = h('input', { type: 'text', maxlength: 64, placeholder: 'z. B. shop-backend', autocapitalize: 'none', required: true });
  const desc = h('input', { type: 'text', maxlength: 512, placeholder: 'Wofür ist der Agent?' });
  const scopes = { send: true, 'todos:read': false, 'todos:write': false, notify: false };
  const labels = { send: 'Nachrichten senden', 'todos:read': 'Todos lesen', 'todos:write': 'Todos anlegen & abhaken', notify: 'Nachrichten an Geräte senden' };
  const boxes = Object.keys(scopes).map((s) => h('label', { class: 'row', style: 'justify-content:space-between' }, labels[s],
    h('input', { type: 'checkbox', checked: scopes[s], style: 'width:22px;height:22px', onchange: (e) => { scopes[s] = e.target.checked; } })));
  const close = sheet(h('form', { class: 'col', onsubmit: guard(async (e) => {
    e.preventDefault();
    const a = await api('/agent-bus/agents', { method: 'POST', body: { name: name.value.trim(), description: desc.value.trim() || null, scopes: Object.keys(scopes).filter((s) => scopes[s]) } });
    close(); keySheet(a.name, a.api_key); refreshAgents();
  }) }, h('h2', {}, 'Neuer Agent'), h('label', { class: 'field' }, 'Name', name), h('label', { class: 'field' }, 'Beschreibung', desc),
  h('div', { class: 'col', style: 'gap:8px' }, h('span', { class: 'muted small' }, 'Berechtigungen'), boxes),
  h('div', { class: 'row' }, h('div', { class: 'grow' }), btn('Abbrechen', '', () => close()), h('button', { class: 'btn primary', type: 'submit' }, 'Anlegen'))));
  name.focus();
}
function sendForm() {
  let kind = 'text';
  const to = h('select', { id: 'send-to', 'aria-label': 'Empfänger' });
  const content = h('textarea', { placeholder: 'Nachricht …', maxlength: 10000, style: 'min-height:70px' });
  const ttype = h('input', { type: 'text', placeholder: 'task_type, z. B. report', maxlength: 64 });
  const payload = h('textarea', { placeholder: 'Payload als JSON (optional)', style: 'min-height:70px;font-family:monospace' });
  const taskBox = h('div', { class: 'col hidden' }, ttype, payload);
  const seg = h('div', { class: 'seg' });
  const draw = () => { clear(seg); [['text', 'Text'], ['task', 'Task']].forEach(([k, l]) => seg.appendChild(h('button', { type: 'button', class: kind === k ? 'on' : '', onclick: () => { kind = k; draw(); content.classList.toggle('hidden', k === 'task'); taskBox.classList.toggle('hidden', k === 'text'); } }, l))); };
  draw();
  return h('details', { class: 'glass card' }, h('summary', {}, 'Nachricht an einen Agent senden'),
    h('form', { class: 'col', style: 'margin-top:12px', onsubmit: guard(async (e) => {
      e.preventDefault();
      if (!to.value) { toast('Zuerst einen Agent anlegen.', 'err'); return; }
      const body = { to: to.value, kind };
      if (kind === 'text') body.content = content.value;
      else { body.task_type = ttype.value.trim(); if (payload.value.trim()) { try { body.payload = JSON.parse(payload.value); } catch (_) { throw new Error('Payload ist kein gültiges JSON.'); } } }
      await api('/agent-bus/messages', { method: 'POST', body }); content.value = ''; toast('Gesendet', 'ok');
    }) }, to, seg, content, taskBox, h('button', { class: 'btn primary', type: 'submit' }, icon('send'), 'Senden')));
}
const loadMessages = guard(async () => {
  const f = $('#log-filter');
  state.messages = (await api('/agent-bus/messages' + (f && f.value ? '?agent=' + encodeURIComponent(f.value) : ''))).messages;
  renderLog();
});
function renderLog() {
  const box = $('#log'); if (!box) return; clear(box);
  const f = $('#log-filter');
  const items = state.messages.filter((m) => !f || !f.value || m.from_label === f.value || m.to_label === f.value);
  if (!items.length) { box.appendChild(h('div', { class: 'empty' }, icon('bus'), h('div', {}, 'Noch keine Nachrichten.'))); return; }
  items.forEach((m) => {
    const incoming = m.to_label === 'todo';
    const stCls = m.status === 'completed' ? 'ok' : m.status === 'failed' ? 'danger' : m.status === 'sent' ? '' : 'warn';
    box.appendChild(h('div', { class: 'glass msg ' + (incoming ? 'in' : 'out') },
      h('div', { class: 'row wrap' }, h('strong', {}, `${m.from_label} → ${m.to_label}`), h('span', { class: 'chip' }, m.kind === 'task' ? 'Task: ' + m.task_type : 'Text'), h('span', { class: 'chip dotted ' + stCls }, m.status), h('span', { class: 'muted small grow', style: 'text-align:right' }, fmtTs(m.created_at))),
      m.content ? h('div', {}, m.content) : null,
      m.payload ? h('pre', {}, JSON.stringify(m.payload, null, 2)) : null,
      m.result ? h('pre', {}, '→ ' + JSON.stringify(m.result, null, 2)) : null,
      incoming && m.kind === 'task' && ['pending', 'in_progress'].includes(m.status) ? h('div', { class: 'row' }, btn('Erledigt', 'sm', guard(async () => { await api(`/agent-bus/messages/${m.id}/ack`, { method: 'POST', body: { status: 'completed' } }); }), 'check'), btn('Ablehnen', 'sm danger', guard(async () => { await api(`/agent-bus/messages/${m.id}/ack`, { method: 'POST', body: { status: 'failed' } }); }))) : null));
  });
}

// ------------------------------------------------------------------ Assistent
function viewAssistant(view) {
  const log = h('div', { class: 'chat', 'aria-live': 'polite' });
  const input = h('input', { type: 'text', placeholder: 'Frag den Assistenten …', maxlength: 4000, enterkeyhint: 'send' });
  const draw = () => { clear(log); if (!state.chat.length) log.appendChild(h('div', { class: 'empty' }, icon('bot'), h('div', {}, 'Ich kenne deine offenen Aufgaben und helfe beim Planen und Priorisieren.'))); state.chat.forEach((m) => log.appendChild(h('div', { class: 'bubble ' + (m.role === 'user' ? 'me' : 'ai') }, m.content))); $('#main').scrollTop = $('#main').scrollHeight; };
  const ask = guard(async (fn, userText) => {
    if (userText) state.chat.push({ role: 'user', content: userText });
    draw(); log.appendChild(h('div', { class: 'bubble ai' }, h('div', { class: 'spinner' })));
    try { state.chat.push({ role: 'assistant', content: (await fn()).reply }); } finally { draw(); }
  });
  view.appendChild(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, 'Assistent'), h('div', { class: 'muted small' }, 'Modell: ' + state.settings.ollama_model)),
    btn('Tagesplan', 'sm', () => ask(() => api('/ai/plan', { method: 'POST', body: aiCtx() }), 'Erstelle meinen Tagesplan.'), 'spark')));
  view.appendChild(log);
  view.appendChild(h('form', { class: 'quick glass', style: 'position:sticky;bottom:0', onsubmit: (e) => { e.preventDefault(); const v = input.value.trim(); if (!v) return; input.value = ''; state.chat = state.chat.slice(-18); ask(() => api('/ai/chat', { method: 'POST', body: { ...aiCtx(), messages: state.chat.map(({ role, content }) => ({ role, content })) } }), v); } },
    input, h('button', { class: 'icon-btn', type: 'submit', 'aria-label': 'Senden' }, icon('send'))));
  draw();
}

// ------------------------------------------------------------------ Einstellungen
function viewSettings(view) {
  view.appendChild(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, 'Einstellungen'), h('div', { class: 'muted small' }, `Angemeldet als ${state.user.username}`))));
  // Design
  const theme = localStorage.getItem('theme') || 'auto';
  const tseg = h('div', { class: 'seg' });
  const drawT = (cur) => { clear(tseg); [['auto', 'Auto'], ['light', 'Hell'], ['dark', 'Dunkel']].forEach(([k, l]) => tseg.appendChild(h('button', { type: 'button', class: cur === k ? 'on' : '', onclick: () => { localStorage.setItem('theme', k); applyTheme(); drawT(k); } }, l))); };
  drawT(theme);
  view.appendChild(h('div', { class: 'glass card col' }, h('h3', {}, 'Design'), tseg));
  // Ollama
  const model = h('select', { 'aria-label': 'Ollama-Modell' }, h('option', { value: state.settings.ollama_model }, state.settings.ollama_model));
  api('/ai/models').then(({ models }) => { clear(model); const all = new Set([state.settings.ollama_model, ...models]); all.forEach((m) => model.appendChild(h('option', { value: m, selected: m === state.settings.ollama_model }, m))); }).catch(() => toast('Ollama-Modelle konnten nicht geladen werden.', 'err'));
  model.addEventListener('change', guard(async () => { state.settings = { ...state.settings, ...(await api('/settings', { method: 'PUT', body: { ollama_model: model.value } })) }; toast('Modell gespeichert', 'ok'); }));
  view.appendChild(h('div', { class: 'glass card col' }, h('h3', {}, 'KI-Modell (Ollama)'), model));
  // Push
  view.appendChild(pushCard());
  const devicesBox = h('div', { class: 'glass card col' });
  view.appendChild(devicesBox);
  refreshDevices(devicesBox);
  // Single Sign-On
  const ssoBox = h('div', { class: 'glass card col' });
  view.appendChild(ssoBox);
  refreshSso(ssoBox);
  // Passwort
  const cur = h('input', { type: 'password', autocomplete: 'current-password', maxlength: 256 });
  const nw = h('input', { type: 'password', autocomplete: 'new-password', minlength: 10, maxlength: 256, placeholder: 'Mindestens 10 Zeichen' });
  view.appendChild(h('form', { class: 'glass card col', onsubmit: guard(async (e) => { e.preventDefault(); await api('/auth/password', { method: 'POST', body: { current_password: cur.value, new_password: nw.value } }); cur.value = nw.value = ''; state.user.has_password = true; toast('Passwort gespeichert – andere Geräte wurden abgemeldet.', 'ok'); route(); }) },
    h('h3', {}, state.user.has_password ? 'Passwort ändern' : 'Passwort festlegen'), state.user.has_password ? h('label', { class: 'field' }, 'Aktuell', cur) : h('p', { class: 'muted small' }, 'Dein Konto wurde über SSO angelegt und hat noch kein Passwort. Mit einem Passwort kannst du dich zusätzlich lokal anmelden.'), h('label', { class: 'field' }, 'Neu', nw), h('button', { class: 'btn', type: 'submit' }, state.user.has_password ? 'Ändern' : 'Festlegen')));
  view.appendChild(h('div', { class: 'row wrap' }, state.user.role === 'admin' ? btn('Administration', '', () => go('admin'), 'shield') : null,
    btn('Abmelden', 'danger', guard(async () => { await androidUnregister(); await api('/auth/logout', { method: 'POST' }); state.user = null; state.csrf = null; closeStream(); boot(); }), 'out')));
}
const refreshSso = guard(async (box) => {
  const [info, ids] = await Promise.all([api('/auth/oidc/providers', { noAuthRedirect: true }), api('/auth/identities')]);
  state.user.has_password = ids.has_password;
  if (!info.providers.length && !ids.identities.length) { box.remove(); return; }
  clear(box);
  box.appendChild(h('h3', {}, 'Single Sign-On'));
  ids.identities.forEach((i) => box.appendChild(h('div', { class: 'row' },
    h('div', { class: 'grow' }, h('strong', {}, i.provider_name), h('div', { class: 'muted small' }, (i.email || 'verknüpft') + (i.last_login_at ? ' · zuletzt ' + fmtTs(i.last_login_at) : ''))),
    btn('Trennen', 'sm danger', guard(async () => { if (!confirm(`Verknüpfung mit ${i.provider_name} trennen?`)) return; await api('/auth/identities/' + i.id, { method: 'DELETE' }); refreshSso(box); })))));
  const linked = new Set(ids.identities.map((i) => i.provider));
  info.providers.filter((p) => !linked.has(p.id)).forEach((p) => box.appendChild(h('a', { class: 'btn', href: '/api/auth/oidc/' + encodeURIComponent(p.id) + '/login?link=1' }, icon('key'), p.name + ' verknüpfen')));
  if (!ids.has_password && ids.identities.length === 1) box.appendChild(h('div', { class: 'muted small' }, 'Tipp: Lege unten ein Passwort fest, um die Verknüpfung später trennen zu können.'));
});

// ------------------------------------------------------------------ Geräte & Android-App
// In der Android-App (WebView) stellt die App ein Objekt `TodoAndroid` bereit (nur für die eigene Server-Origin).
const android = { info: null, deviceId: null };
const hasAndroid = () => typeof window.TodoAndroid === 'object' && window.TodoAndroid !== null;
const nativeSend = (msg) => { if (hasAndroid()) window.TodoAndroid.postMessage(JSON.stringify(msg)); };

function initAndroid() {
  if (!hasAndroid()) return;
  window.TodoAndroid.onmessage = guard(async (e) => {
    let msg; try { msg = JSON.parse(e.data); } catch (_) { return; }
    if (msg.type === 'info') {
      android.info = msg; android.deviceId = null;
      const { devices } = await api('/devices');
      const known = msg.registered && devices.some((d) => d.id === msg.deviceId);
      if (known) android.deviceId = msg.deviceId;
      else {
        const d = await api('/devices/register', { method: 'POST', body: { name: msg.name || 'Android', platform: 'android', app_version: msg.appVersion || null } });
        android.deviceId = d.id;
        nativeSend({ type: 'register', deviceId: d.id, token: d.token, name: d.name, serverUrl: location.origin });
      }
      const box = $('#devices-card'); if (box) refreshDevices(box);
    } else if (msg.type === 'registered') { const box = $('#devices-card'); if (box) refreshDevices(box); }
  });
  nativeSend({ type: 'hello' });
}
async function androidUnregister() {
  if (!hasAndroid()) return;
  try { if (android.deviceId) await api('/devices/' + android.deviceId, { method: 'DELETE' }); } catch (_) { /* egal */ }
  nativeSend({ type: 'unregister' }); android.deviceId = null;
}

const refreshDevices = guard(async (box) => {
  box.id = 'devices-card';
  const { devices } = await api('/devices');
  clear(box);
  box.appendChild(h('div', { class: 'row' }, h('h3', { class: 'grow' }, 'Geräte'), devices.length ? btn('An alle', 'sm', () => deviceSheet(null), 'send') : null));
  box.appendChild(h('p', { class: 'muted small' }, 'Geräte mit der Android-App erhalten Nachrichten direkt als Benachrichtigung – auch Erinnerungen, Agent-Bus-Meldungen und Freigaben.'));
  if (!devices.length) box.appendChild(h('div', { class: 'muted small' }, 'Noch kein Gerät registriert. Installiere die Android-App und melde dich dort an.'));
  devices.forEach((d) => box.appendChild(h('div', { class: 'row', style: 'align-items:flex-start' },
    h('div', { class: 'grow' },
      h('div', { class: 'row wrap', style: 'gap:6px' }, h('strong', {}, d.name), d.id === android.deviceId ? h('span', { class: 'chip' }, 'dieses Gerät') : null,
        h('span', { class: 'chip dotted ' + (d.online ? 'ok' : '') }, d.online ? 'online' : 'offline'), d.pending ? h('span', { class: 'chip dotted warn' }, d.pending + ' offen') : null),
      h('div', { class: 'muted small' }, [d.platform === 'android' ? 'Android' : 'Gerät', d.app_version ? 'v' + d.app_version : null, d.last_seen_at ? 'zuletzt ' + fmtTs(d.last_seen_at) : null].filter(Boolean).join(' · '))),
    h('button', { class: 'icon-btn', 'aria-label': 'Nachricht senden', title: 'Nachricht senden', onclick: () => deviceSheet(d) }, icon('send')),
    h('button', { class: 'icon-btn', 'aria-label': 'Umbenennen', title: 'Umbenennen', onclick: guard(async () => { const n = prompt('Neuer Name:', d.name); if (!n || !n.trim()) return; await api('/devices/' + d.id, { method: 'PATCH', body: { name: n.trim() } }); refreshDevices(box); }) }, icon('more')),
    h('button', { class: 'icon-btn', 'aria-label': 'Gerät entfernen', title: 'Entfernen', onclick: guard(async () => { if (!confirm(`„${d.name}“ entfernen? Die App registriert sich beim nächsten Öffnen neu.`)) return; await api('/devices/' + d.id, { method: 'DELETE' }); refreshDevices(box); }) }, icon('trash')))));
  if (hasAndroid() && android.info) {
    const i = android.info;
    box.appendChild(h('div', { class: 'nav-sep' }));
    box.appendChild(h('div', { class: 'col', style: 'gap:8px' },
      h('div', { class: 'muted small' }, `Diese App (${i.name}): Benachrichtigungen ${i.notificationsAllowed ? 'erlaubt' : 'AUS'} · Hintergrundverbindung ${i.connected ? 'aktiv' : 'inaktiv'}`),
      h('div', { class: 'row wrap' },
        !i.notificationsAllowed ? btn('Benachrichtigungen erlauben', 'sm', () => nativeSend({ type: 'openNotificationSettings' }), 'bell') : null,
        !i.batteryUnrestricted ? btn('Akku-Optimierung ausschalten', 'sm', () => nativeSend({ type: 'openBatterySettings' })) : null)));
  }
});

function deviceSheet(device) {
  const title = h('input', { type: 'text', maxlength: 80, placeholder: 'Titel', required: true });
  const body = h('textarea', { maxlength: 500, placeholder: 'Nachricht (optional)', style: 'min-height:80px' });
  const close = sheet(h('form', { class: 'col', onsubmit: guard(async (e) => {
    e.preventDefault();
    const r = await api('/devices/send', { method: 'POST', body: { device_id: device ? device.id : null, title: title.value.trim(), body: body.value.trim() } });
    close(); toast(`An ${r.sent} Gerät${r.sent === 1 ? '' : 'e'} gesendet (${r.online} online)`, 'ok');
    const box = $('#devices-card'); if (box) refreshDevices(box);
  }) }, h('h2', {}, device ? 'Nachricht an ' + device.name : 'Nachricht an alle Geräte'),
  h('label', { class: 'field' }, 'Titel', title), h('label', { class: 'field' }, 'Nachricht', body),
  h('div', { class: 'row' }, h('div', { class: 'grow' }), btn('Abbrechen', '', () => close()), h('button', { class: 'btn primary', type: 'submit' }, icon('send'), 'Senden'))));
  title.focus();
}

function applyTheme() {
  const t = localStorage.getItem('theme') || 'auto';
  if (t === 'auto') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', t);
}
function pushCard() {
  const supported = 'serviceWorker' in navigator && 'PushManager' in window && window.isSecureContext;
  const sw = h('button', { class: 'switch', role: 'switch', 'aria-checked': 'false', 'aria-label': 'Push-Benachrichtigungen', disabled: !supported });
  const info = h('div', { class: 'muted small' }, supported ? 'Erinnerungen bei Fälligkeit, Agent-Nachrichten und Freigaben.' : 'Benötigt HTTPS und einen unterstützten Browser (iOS: zuerst zum Home-Bildschirm hinzufügen).');
  const set = (on) => { sw.classList.toggle('on', on); sw.setAttribute('aria-checked', String(on)); };
  if (supported) navigator.serviceWorker.ready.then((r) => r.pushManager.getSubscription()).then((s) => set(!!s)).catch(() => {});
  sw.addEventListener('click', guard(async () => {
    const reg = await navigator.serviceWorker.ready;
    const existing = await reg.pushManager.getSubscription();
    if (existing) { await api('/push/unsubscribe', { method: 'POST', body: { endpoint: existing.endpoint } }); await existing.unsubscribe(); set(false); return; }
    if ((await Notification.requestPermission()) !== 'granted') throw new Error('Benachrichtigungen wurden nicht erlaubt.');
    const { public_key } = await api('/push/key');
    const pad2 = '='.repeat((4 - (public_key.length % 4)) % 4);
    const key = Uint8Array.from(atob((public_key + pad2).replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
    const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
    await api('/push/subscribe', { method: 'POST', body: sub.toJSON() }); set(true); toast('Push aktiviert', 'ok');
  }));
  return h('div', { class: 'glass card col' }, h('div', { class: 'row' }, h('h3', { class: 'grow' }, 'Push-Benachrichtigungen'), sw), info,
    supported ? btn('Test senden', 'sm', guard(async () => { await api('/push/test', { method: 'POST' }); toast('Test gesendet'); }), 'bell') : null);
}

// ------------------------------------------------------------------ Admin
function viewAdmin(view) {
  view.appendChild(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, 'Administration'), h('div', { class: 'muted small' }, 'Benutzer freigeben und verwalten'))));
  const users = h('div', { class: 'col' }), audit = h('div', { class: 'col', style: 'gap:4px' });
  view.appendChild(users);
  view.appendChild(h('details', { class: 'glass card', ontoggle: (e) => e.target.open && loadAudit() }, h('summary', {}, 'Protokoll (letzte 200 Einträge)'), h('div', { style: 'margin-top:10px' }, audit)));
  const act = (u, a, label, cls, ic) => btn(label, 'sm ' + (cls || ''), guard(async () => { if (a === 'delete') { if (!confirm(`„${u.username}“ samt allen Daten löschen?`)) return; await api('/admin/users/' + u.id, { method: 'DELETE' }); } else await api(`/admin/users/${u.id}/${a}`, { method: 'POST' }); await loadUsers(); }), ic);
  const loadUsers = guard(async () => {
    const list = (await api('/admin/users')).users; clear(users);
    state.pendingUsers = list.filter((u) => u.status === 'pending').length; renderChrome();
    if (state.pendingUsers) users.appendChild(h('div', { class: 'group-title' }, 'Wartet auf Freigabe'));
    list.forEach((u) => {
      if (u.status !== 'pending' && !users.querySelector('.rest')) users.appendChild(h('div', { class: 'group-title rest' }, 'Alle Benutzer'));
      const me = u.id === state.user.id;
      const actions = u.status === 'pending' ? [act(u, 'approve', 'Freigeben', 'primary', 'check'), act(u, 'reject', 'Ablehnen', 'danger')]
        : me ? []
          : [u.status === 'approved' ? act(u, 'block', 'Sperren', 'danger') : act(u, 'unblock', 'Entsperren'),
            u.status === 'approved' ? act(u, u.role === 'admin' ? 'demote' : 'promote', u.role === 'admin' ? 'Zum Benutzer' : 'Zum Admin') : null, act(u, 'delete', '', 'danger', 'trash')];
      users.appendChild(h('div', { class: 'glass user-row' }, h('div', { class: 'avatar' }, u.username[0]),
        h('div', { class: 'grow' }, h('strong', {}, u.username + (me ? ' (du)' : '')), h('div', { class: 'muted small' }, 'seit ' + fmtTs(u.created_at))),
        h('span', { class: 'chip dotted ' + (u.status === 'approved' ? 'ok' : u.status === 'pending' ? 'warn' : 'danger') }, ({ approved: 'aktiv', pending: 'wartet', rejected: 'abgelehnt', blocked: 'gesperrt' })[u.status]),
        u.role === 'admin' ? h('span', { class: 'chip' }, 'Admin') : null, h('div', { class: 'row wrap' }, actions)));
    });
  });
  const loadAudit = guard(async () => { const { entries } = await api('/admin/audit'); clear(audit); entries.forEach((e) => audit.appendChild(h('div', { class: 'small row wrap' }, h('span', { class: 'muted' }, fmtTs(e.at)), h('strong', {}, e.actor), h('span', {}, e.action + (e.detail ? ' · ' + e.detail : '')), h('span', { class: 'muted' }, e.ip || '')))); });
  loadUsers();
}

// ------------------------------------------------------------------ Start
applyTheme();
// Der Service Worker erhält dieselbe Versionsnummer wie app.js, damit auch er nach Updates nicht aus einem CDN-Cache kommt.
const ASSET_VERSION = document.currentScript && document.currentScript.src ? new URL(document.currentScript.src).search : '';
if ('serviceWorker' in navigator && window.isSecureContext) navigator.serviceWorker.register('/sw.js' + ASSET_VERSION).catch(() => {});
window.addEventListener('resize', () => { if (state.user && state.selected) renderDetail(); });
document.addEventListener('keydown', (e) => {
  if (!state.user) return;
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
  if (e.key === 'Escape' && state.selected) { state.selected = null; renderTodos(); renderDetail(); }
  if (typing) return;
  if (e.key === 'n' || e.key === '/') { const i = $('#quick-input'); if (i) { e.preventDefault(); i.focus(); } }
});
boot();
