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
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3-6 7-6s7 2.5 7 6M16 4.5a3.5 3.5 0 010 7M22 20c0-3-2-5-5-5.7"/>', clip: '<path d="M21 11l-8.5 8.5a5 5 0 01-7-7L14 4a3.5 3.5 0 015 5l-8.5 8.5a2 2 0 01-3-3L15 7"/>', chevl: '<path d="M15 18l-6-6 6-6"/>', chevr: '<path d="M9 18l6-6-6-6"/>',
  link: '<path d="M10 14a5 5 0 007 0l3-3a5 5 0 00-7-7l-1 1"/><path d="M14 10a5 5 0 00-7 0l-3 3a5 5 0 007 7l1-1"/>', bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  moon: '<path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/>', pin: '<path d="M12 22s7-6.2 7-12a7 7 0 10-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/>', lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>', share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>', tag: '<path d="M3 12V4a1 1 0 011-1h8l9 9-9 9z"/><path d="M7.5 7.5h.01"/>', repeat: '<path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 013-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 01-3 3H3"/>', filter: '<path d="M3 5h18l-7 8v6l-4 2v-8z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>', chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 010 10h-3"/>', play: '<path d="M7 4l13 8-13 8z"/>', pause: '<path d="M8 4v16M16 4v16"/>',
  stop: '<rect x="5" y="5" width="14" height="14" rx="2"/>', select: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M8 12l3 3 5-6"/>',
  layers: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>', board: '<rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="10" y="4" width="5" height="10" rx="1.5"/><rect x="17" y="4" width="4" height="13" rx="1.5"/>',
  comment: '<path d="M21 12a8 8 0 01-11.6 7.1L4 20l1-4.6A8 8 0 1121 12z"/>', folder: '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>', timer: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6"/>', refresh: '<path d="M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5M21 12a9 9 0 01-15 6.7L3 16M3 21v-5h5"/>',
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

// Hinweise: höchstens 3 gleichzeitig, gleiche Meldung ersetzt die alte; optional mit Aktion (z. B. „Rückgängig“)
function toast(msg, kind, action) {
  const box = $('#toasts'); if (!box) return;
  [...box.children].forEach((x) => { if (x.dataset.msg === msg) x.remove(); });
  while (box.children.length >= 3) box.firstChild.remove();
  const t = h('div', { class: 'toast ' + (kind || ''), role: 'status' }, h('span', {}, msg),
    action ? h('button', { type: 'button', class: 'toast-act', onclick: () => { t.remove(); action.fn(); } }, action.label) : null);
  t.dataset.msg = msg;
  box.appendChild(t);
  setTimeout(() => t.remove(), action ? 8000 : 4200);
}
const clearToasts = () => { const box = $('#toasts'); if (box) clear(box); };

// ------------------------------------------------------------------ API
const state = {
  user: null, csrf: null, todos: [], lists: [], agents: [], messages: [], settings: {}, route: 'today',
  selected: null, unread: 0, pendingUsers: 0, chat: [], sse: null, filters: [],
  search: { q: '', tags: [], due: 'any', priority_min: 0, list_id: null, include_done: false },
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
  clearToasts(); stopSelecting(false);
  const fb = $('#focusbar'); if (fb) fb.remove();
  try {
    const me = await api('/auth/me', { noAuthRedirect: true });
    state.user = me.user; state.csrf = me.csrf;
  } catch (_) { state.user = null; }
  const qp = new URLSearchParams(location.search);
  const shared = [qp.get('title'), qp.get('text'), qp.get('url')].filter(Boolean).join('\n').trim();
  if (shared) { state.shareText = shared.slice(0, 4000); history.replaceState(null, '', '/#/share'); }
  const ssoCode = qp.get('sso');
  if (ssoCode) history.replaceState(null, '', location.pathname + location.hash); // Parameter aus der URL entfernen
  if (qp.get('invite')) { state.invite = qp.get('invite').slice(0, 100); history.replaceState(null, '', location.pathname + location.hash); }
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
  renderFocus();
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
      const body = { username: user.value, password: pw.value };
      if (mode === 'register' && state.invite) body.invite = state.invite;
      const r = await api(mode === 'login' ? '/auth/login' : '/auth/register', { method: 'POST', body, noAuthRedirect: true });
      if (mode === 'register' && state.invite) state.invite = null;
      if (mode === 'register' && r.status === 'pending') {
        err.className = 'error notice'; err.textContent = 'Registriert! Ein Administrator muss dein Konto noch freigeben.'; setMode('login'); err.className = 'error notice'; err.textContent = 'Registriert! Ein Administrator muss dein Konto noch freigeben.'; pw.value = '';
      } else if (r.twofa_required) { renderTwoFactor(root, r.ticket); } else { boot(); }
    } catch (ex) { err.textContent = ex.message; } finally { submit.disabled = false; }
  } },
  h('div', { style: 'text-align:center' }, h('div', { class: 'logo' }, icon('check')), title, sub),
  ssoButtons, local && window.PublicKeyCredential ? h('button', { type: 'button', class: 'btn', onclick: () => passkeyLogin(err) }, icon('key'), 'Mit Passkey anmelden') : null,
  (ssoButtons.length > 0 || window.PublicKeyCredential) && local ? h('div', { class: 'divider' }, h('span', {}, 'oder')) : null,
  local ? [fieldUser, fieldPw] : null, err, local ? submit : null, local ? toggleRow : null);
  setMode('login');
  if (!local) sub.textContent = 'Melde dich mit deinem Single-Sign-On-Konto an.';
  if (state.invite && local) {
    setMode('register');
    api('/auth/invite/' + encodeURIComponent(state.invite), { noAuthRedirect: true }).then((r) => {
      if (r.valid) { title.textContent = 'Willkommen!'; sub.textContent = (r.by ? `${r.by} hat dich eingeladen` : 'Du wurdest eingeladen') + (r.note ? ` (${r.note})` : '') + '. Dein Konto ist sofort aktiv.'; }
      else { state.invite = null; err.textContent = 'Diese Einladung ist ungültig oder abgelaufen. Du kannst dich trotzdem registrieren – dann muss ein Admin freigeben.'; }
    }).catch(() => {});
  }
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

function renderTwoFactor(root, ticket) {
  clear(root);
  const err = h('div', { class: 'error', role: 'alert' });
  const code = h('input', { type: 'text', inputmode: 'numeric', autocomplete: 'one-time-code', maxlength: 40, placeholder: '123456', 'aria-label': 'Code' });
  const submit = h('button', { class: 'btn primary', type: 'submit' }, 'Bestätigen');
  root.appendChild(h('div', { class: 'auth' }, h('div', { class: 'auth-card glass' }, h('form', { class: 'col', onsubmit: async (e) => {
    e.preventDefault(); err.textContent = ''; submit.disabled = true;
    try {
      const r = await api('/auth/login/2fa', { method: 'POST', body: { ticket, code: code.value }, noAuthRedirect: true });
      if (r.used_recovery) setTimeout(() => toast(`Wiederherstellungscode verwendet – noch ${r.recovery_left} übrig.`), 800);
      boot();
    } catch (ex) { err.textContent = ex.message; code.select(); if (/abgelaufen/.test(ex.message)) setTimeout(boot, 1500); } finally { submit.disabled = false; }
  } },
  h('div', { style: 'text-align:center' }, h('div', { class: 'logo' }, icon('lock')), h('h1', {}, 'Bestätigung'), h('p', { class: 'muted small' }, 'Gib den 6-stelligen Code aus deiner Authenticator-App ein – oder einen Wiederherstellungscode.')),
  h('label', { class: 'field' }, 'Code', code), err, submit, h('div', { class: 'row', style: 'justify-content:center' }, btn('Zurück', 'sm', () => boot()))))));
  code.focus();
}

// ------------------------------------------------------------------ Passkeys (WebAuthn)
const b64uToBuf = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)), (c) => c.charCodeAt(0)).buffer;
const bufToB64u = (b) => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
function credToJSON(c) {
  const r = c.response, out = { id: c.id, rawId: bufToB64u(c.rawId), type: c.type, clientExtensionResults: c.getClientExtensionResults ? c.getClientExtensionResults() : {}, response: { clientDataJSON: bufToB64u(r.clientDataJSON) } };
  if (c.authenticatorAttachment) out.authenticatorAttachment = c.authenticatorAttachment;
  if (r.attestationObject) { out.response.attestationObject = bufToB64u(r.attestationObject); out.response.transports = r.getTransports ? r.getTransports() : []; }
  if (r.authenticatorData) { out.response.authenticatorData = bufToB64u(r.authenticatorData); out.response.signature = bufToB64u(r.signature); if (r.userHandle) out.response.userHandle = bufToB64u(r.userHandle); }
  return out;
}
async function passkeyLogin(err) {
  try {
    const o = await api('/auth/passkeys/login/options', { method: 'POST', body: {}, noAuthRedirect: true });
    o.challenge = b64uToBuf(o.challenge);
    (o.allowCredentials || []).forEach((c) => { c.id = b64uToBuf(c.id); });
    const cred = await navigator.credentials.get({ publicKey: o });
    await api('/auth/passkeys/login/verify', { method: 'POST', body: { credential: credToJSON(cred) }, noAuthRedirect: true });
    boot();
  } catch (ex) { if (err) { err.className = 'error'; err.textContent = ex.name === 'NotAllowedError' ? 'Passkey-Anmeldung abgebrochen.' : ex.message; } }
}
async function passkeyRegister() {
  const o = await api('/auth/passkeys/register/options', { method: 'POST' });
  o.challenge = b64uToBuf(o.challenge); o.user.id = b64uToBuf(o.user.id);
  (o.excludeCredentials || []).forEach((c) => { c.id = b64uToBuf(c.id); });
  let cred;
  try { cred = await navigator.credentials.create({ publicKey: o }); }
  catch (ex) { throw new Error(ex.name === 'NotAllowedError' ? 'Abgebrochen.' : ex.name === 'InvalidStateError' ? 'Dieses Gerät hat bereits einen Passkey.' : ex.message); }
  const name = (prompt('Name für diesen Passkey:', navigator.userAgentData && navigator.userAgentData.platform ? navigator.userAgentData.platform : 'Passkey') || 'Passkey').slice(0, 60);
  await api('/auth/passkeys/register/verify', { method: 'POST', body: { name, credential: credToJSON(cred) } });
}

async function loadAll() {
  const [t, l, s, f, pp] = await Promise.all([api('/todos'), api('/lists'), api('/settings'), api('/filters'), api('/people')]);
  state.todos = t.todos; state.lists = l.lists; state.settings = s; state.filters = f.filters; state.people = pp.people;
  const tz = (Intl.DateTimeFormat().resolvedOptions() || {}).timeZone;
  if (tz && s.tz !== tz) api('/settings', { method: 'PUT', body: { tz } }).then((r) => { state.settings = r; }).catch(() => {});
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
  es.addEventListener('todo', guard(async (e) => {
    let op = null; try { op = JSON.parse(e.data).op; } catch (_) { /* */ }
    const [t, l, pp] = await Promise.all([api('/todos'), op === 'reload' ? api('/lists') : null, op === 'reload' ? api('/people') : null]);
    state.todos = t.todos; if (l) state.lists = l.lists; if (pp) state.people = pp.people;
    const typing = document.activeElement && document.activeElement.closest && document.activeElement.closest('#detail-pane, .overlay.detail');
    if (state.route === 'calendar') route(); else { renderTodos(); renderChrome(); if (!typing) renderDetail(); }
  }));
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
const isTaskRoute = (r) => NAV.some((n) => n.id === r) || /^(list|filter|tag)\//.test(r) || r === 'search' || r === 'assigned';
const personName = (id) => { const p = (state.people || []).find((x) => x.id === id); return p ? p.username : null; };
const byId = (id) => state.todos.find((x) => x.id === id);
const openBlockers = (t) => (t.blocked_by || []).map(byId).filter((b) => b && !b.done);
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
  if (state.selecting) stopSelecting(false);
  state.route = currentRoute();
  if (state.route === 'bus') state.unread = 0;
  state.selected = null;
  const view = clear($('#view'));
  const r = state.route;
  if (r === 'calendar') viewCalendar(view);
  else if (isTaskRoute(r)) viewTasks(view);
  else if (r === 'share') viewShare(view);
  else if (r === 'stats') viewStats(view);
  else if (r === 'templates') viewTemplates(view);
  else if (r === 'trash') viewTrash(view);
  else if (r === 'bus') viewBus(view);
  else if (r === 'assistant') viewAssistant(view);
  else if (r === 'settings') viewSettings(view);
  else if (r === 'admin' && state.user.role === 'admin') viewAdmin(view);
  else { go('today'); return; }
  $('#fab').classList.toggle('hidden', !isTaskRoute(r) || r === 'done' || r === 'search');
  $('#main').scrollTop = 0;
  renderChrome(); renderDetail();
}

function renderChrome() {
  const c = counts();
  const item = (id, label, ic, extra) => h('button', { class: 'nav-item' + (state.route === id ? ' on' : ''), onclick: () => go(id) }, icon(ic), label, extra);
  const side = clear($('#side'));
  if (!side) return;
  side.appendChild(h('div', { class: 'brand' }, h('div', { class: 'logo' }, icon('check')), 'Todo'));
  side.appendChild(item('search', 'Suche', 'search', h('span', { class: 'count' }, '/')));
  NAV.forEach((n) => side.appendChild(item(n.id, n.label, n.icon, h('span', { class: 'count' }, n.id === 'done' ? '' : c[n.id] || ''))));
  const assigned = state.todos.filter((t) => open(t) && t.assignee_id === state.user.id).length;
  if (assigned || state.route === 'assigned') side.appendChild(item('assigned', 'Mir zugewiesen', 'user', h('span', { class: 'count' }, assigned || '')));
  side.appendChild(item('calendar', 'Kalender', 'cal'));
  side.appendChild(item('stats', 'Statistik', 'chart'));
  side.appendChild(h('div', { class: 'nav-sep' }));
  const listItem = (l) => {
    const n = state.todos.filter((t) => open(t) && t.list_id === l.id).length;
    const shared = l.mine === false || (l.members || []).length;
    const extra = l.kind === 'project' ? h('span', { class: 'count' }, projectProgress(l).pct + ' %') : h('span', { class: 'count' }, n || '');
    return h('button', { class: 'nav-item' + (state.route === 'list/' + l.id ? ' on' : ''), onclick: () => go('list/' + l.id) }, icon(l.kind === 'project' ? 'folder' : shared ? 'users' : 'list'), h('span', { class: 'grow', style: 'overflow:hidden;text-overflow:ellipsis' }, l.name), extra);
  };
  const projects = state.lists.filter((l) => l.kind === 'project');
  if (projects.length) { side.appendChild(h('div', { class: 'nav-title' }, 'Projekte')); projects.forEach((l) => side.appendChild(listItem(l))); }
  side.appendChild(h('div', { class: 'nav-title' }, 'Listen', h('button', { class: 'icon-btn', style: 'width:28px;height:28px', 'aria-label': 'Neue Liste oder Projekt', onclick: newList }, icon('plus'))));
  state.lists.filter((l) => l.kind !== 'project').forEach((l) => side.appendChild(listItem(l)));
  if (state.filters.length) {
    side.appendChild(h('div', { class: 'nav-title' }, 'Filter'));
    state.filters.forEach((f) => side.appendChild(item('filter/' + f.id, f.name, 'filter', h('span', { class: 'count' }, applyQuery(state.todos.filter((t) => !t.parent_id), f.query).length || ''))));
  }
  const tagCounts = {};
  state.todos.filter(open).forEach((t) => (t.tags || []).forEach((g) => { tagCounts[g] = (tagCounts[g] || 0) + 1; }));
  const topTags = Object.entries(tagCounts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 8);
  if (topTags.length) {
    side.appendChild(h('div', { class: 'nav-title' }, 'Tags'));
    topTags.forEach(([g, n]) => side.appendChild(item('tag/' + encodeURIComponent(g), '#' + g, 'tag', h('span', { class: 'count' }, n))));
  }
  side.appendChild(h('div', { class: 'nav-sep' }));
  side.appendChild(item('bus', 'Agent Bus', 'bus', state.unread ? h('span', { class: 'count chip solid' }, state.unread) : null));
  side.appendChild(item('assistant', 'Assistent', 'bot'));
  if (state.user.role === 'admin') side.appendChild(item('admin', 'Admin', 'shield', state.pendingUsers ? h('span', { class: 'count chip solid' }, state.pendingUsers) : null));
  side.appendChild(h('div', { class: 'grow' }));
  side.appendChild(item('templates', 'Vorlagen', 'layers'));
  side.appendChild(item('trash', 'Papierkorb', 'trash'));
  side.appendChild(item('settings', 'Einstellungen', 'gear'));
  side.appendChild(h('div', { class: 'muted small', style: 'padding:6px 12px' }, `${state.user.username} · ${state.user.role === 'admin' ? 'Admin' : 'Benutzer'}`));

  const tabs = clear($('#tabbar'));
  const tab = (id, label, ic, badge, active) => h('button', { class: 'tab' + (active ? ' on' : ''), onclick: () => go(id) }, icon(ic), label, badge ? h('span', { class: 'badge' }, badge) : null);
  const taskRoute = isTaskRoute(state.route) || state.route === 'calendar';
  tabs.appendChild(tab('today', 'Aufgaben', 'check', c.today, taskRoute));
  tabs.appendChild(tab('bus', 'Bus', 'bus', state.unread, state.route === 'bus'));
  tabs.appendChild(tab('assistant', 'Assistent', 'bot', 0, state.route === 'assistant'));
  const more = ['settings', 'admin', 'stats', 'templates', 'trash'].includes(state.route);
  tabs.appendChild(tab('settings', 'Mehr', 'gear', state.pendingUsers, more));
}

const newList = () => listSheet();
function listSheet(list) {
  const editing = !!list; list = list || { name: '', kind: 'list', due_at: null };
  let kind = list.kind || 'list';
  const name = h('input', { type: 'text', maxlength: 60, value: list.name, placeholder: 'z. B. Einkauf oder Umzug 2027', required: true });
  const due = h('input', { type: 'date', value: list.due_at ? toLocalInput(list.due_at).slice(0, 10) : '', 'aria-label': 'Termin' });
  const dueField = h('label', { class: 'field' + (kind === 'project' ? '' : ' hidden') }, 'Projekt-Termin (optional)', due);
  const seg = h('div', { class: 'seg' });
  const drawSeg = () => { clear(seg); [['list', 'Liste'], ['project', 'Projekt']].forEach(([k, l]) => seg.appendChild(h('button', { type: 'button', class: kind === k ? 'on' : '', onclick: () => { kind = k; drawSeg(); dueField.classList.toggle('hidden', k !== 'project'); } }, l))); };
  drawSeg();
  const close = sheet(h('form', { class: 'col', onsubmit: guard(async (e) => {
    e.preventDefault();
    const body = { name: name.value.trim(), kind, due_at: kind === 'project' && due.value ? new Date(due.value + 'T18:00').toISOString() : null };
    if (editing) { Object.assign(list, await api('/lists/' + list.id, { method: 'PATCH', body })); close(); route(); return; }
    const colors = ['#8b6bff', '#3ed1c0', '#ff6b81', '#ffb454', '#5ab0ff', '#9be15d'];
    const l = await api('/lists', { method: 'POST', body: { ...body, color: colors[state.lists.length % colors.length] } });
    state.lists.push(l); close(); renderChrome(); go('list/' + l.id);
  }) }, h('h2', {}, editing ? 'Bearbeiten' : 'Neue Liste'), h('label', { class: 'field' }, 'Name', name),
  h('div', { class: 'field' }, 'Art', seg, h('span', { class: 'small muted' }, 'Projekte zeigen Fortschritt und Termin – ideal für Vorhaben mit vielen Schritten.')), dueField,
  h('div', { class: 'row' }, h('div', { class: 'grow' }), btn('Abbrechen', '', () => close()), h('button', { class: 'btn primary', type: 'submit' }, editing ? 'Speichern' : 'Anlegen'))));
  name.focus();
}
function projectProgress(l) {
  const items = state.todos.filter((t) => !t.parent_id && t.list_id === l.id);
  const done = items.filter((t) => t.done).length;
  return { done, total: items.length, pct: items.length ? Math.round((100 * done) / items.length) : 0 };
}
function projectBar(l) {
  const p = projectProgress(l), bar = h('i'); bar.style.width = p.pct + '%';
  const late = l.due_at && new Date(l.due_at) < new Date() && p.done < p.total;
  return h('div', { class: 'glass card col', style: 'gap:8px;padding:14px 16px' },
    h('div', { class: 'row small' }, h('strong', { class: 'grow' }, `${p.pct} %`), h('span', { class: 'muted' }, `${p.done} von ${p.total} erledigt`),
      l.due_at ? h('span', { class: 'chip' + (late ? ' danger' : '') }, icon('flag'), 'bis ' + new Date(l.due_at).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })) : null),
    h('div', { class: 'progress' }, bar));
}

// ------------------------------------------------------------------ Aufgaben-Ansicht
function applyQuery(items, f) {
  const end = endOfToday(), week = new Date(end.getTime() + 6 * 86400000), q = (f.q || '').toLowerCase().trim();
  return items.filter((t) => {
    if (!f.include_done && t.done) return false;
    if (q && !(t.title.toLowerCase().includes(q) || (t.notes || '').toLowerCase().includes(q) || (t.tags || []).some((g) => g.includes(q.replace(/^#/, ''))))) return false;
    if ((f.tags || []).length && !f.tags.every((g) => (t.tags || []).includes(g))) return false;
    if (f.list_id && t.list_id !== f.list_id) return false;
    if ((f.priority_min || 0) > t.priority) return false;
    const d = t.due_at ? new Date(t.due_at) : null;
    if (f.due === 'overdue' && !(d && d < new Date())) return false;
    if (f.due === 'today' && !(d && d <= end)) return false;
    if (f.due === 'week' && !(d && d <= week)) return false;
    if (f.due === 'none' && d) return false;
    return true;
  });
}
const routeTag = () => (state.route.startsWith('tag/') ? decodeURIComponent(state.route.slice(4)) : null);
const routeFilter = () => (state.route.startsWith('filter/') ? state.filters.find((f) => f.id === Number(state.route.slice(7))) : null);

function filteredTodos() {
  const r = state.route, end = endOfToday();
  let items = state.todos.filter((t) => !t.parent_id);
  if (r === 'search') return applyQuery(items, state.search);
  if (r.startsWith('tag/')) return applyQuery(items, { tags: [routeTag()] });
  if (r.startsWith('filter/')) { const f = routeFilter(); return f ? applyQuery(items, f.query) : []; }
  if (r === 'assigned') items = items.filter((t) => !t.done && t.assignee_id === state.user.id);
  else if (r === 'today') items = items.filter((t) => !t.done && t.due_at && new Date(t.due_at) <= end);
  else if (r === 'upcoming') items = items.filter((t) => !t.done && t.due_at && new Date(t.due_at) > end);
  else if (r === 'all') items = items.filter((t) => !t.done);
  else if (r === 'done') items = items.filter((t) => t.done).sort((a, b) => (b.done_at || '').localeCompare(a.done_at || ''));
  else if (r.startsWith('list/')) items = items.filter((t) => t.list_id === Number(r.slice(5)));
  return items;
}
const titles = { today: 'Heute', upcoming: 'Geplant', all: 'Alle Aufgaben', done: 'Erledigt', assigned: 'Mir zugewiesen' };

function viewTasks(view) {
  const r = state.route;
  const list = r.startsWith('list/') ? state.lists.find((l) => l.id === Number(r.slice(5))) : null;
  if (r.startsWith('list/') && !list) { go('today'); return; }
  if (r === 'search') return viewSearch(view);
  if (r.startsWith('filter/') || r.startsWith('tag/')) {
    const f = routeFilter();
    if (r.startsWith('filter/') && !f) { go('today'); return; }
    view.appendChild(h('div', { class: 'page-head' },
      h('div', {}, h('h1', {}, f ? f.name : '#' + routeTag()), h('div', { class: 'muted small' }, f ? describeQuery(f.query) : 'Alle offenen Aufgaben mit diesem Tag')),
      f ? h('button', { class: 'icon-btn', 'aria-label': 'Filter löschen', onclick: guard(async () => { if (!confirm(`Filter „${f.name}“ löschen?`)) return; await api('/filters/' + f.id, { method: 'DELETE' }); state.filters = state.filters.filter((x) => x.id !== f.id); go('today'); }) }, icon('trash')) : null));
    addHeadTools(view);
    if (!f) view.appendChild(quickBar());
    view.appendChild(h('div', { id: 'draft' }));
    view.appendChild(h('div', { id: 'progress' }));
    view.appendChild(h('div', { class: 'todo-list', id: 'todos' }));
    return renderTodos();
  }
  const hour = new Date().getHours();
  const greet = hour < 11 ? 'Guten Morgen' : hour < 18 ? 'Hallo' : 'Guten Abend';
  view.appendChild(h('div', { class: 'page-head' },
    h('div', {}, h('h1', {}, list ? list.name : titles[r]), h('div', { class: 'muted small', id: 'subtitle' },
      list && list.mine === false ? `Geteilt von ${list.owner}` : list && (list.members || []).length ? 'Geteilt mit ' + list.members.join(', ') : `${greet}, ${state.user.username}`)),
    list ? h('div', { class: 'row' },
      list.mine !== false ? h('button', { class: 'icon-btn', 'aria-label': 'Liste teilen', title: 'Teilen', onclick: () => shareListSheet(list) }, icon('users')) : null,
      list.mine === false ? btn('Verlassen', 'sm', guard(async () => { if (!confirm(`Geteilte Liste „${list.name}“ verlassen?`)) return; await api(`/lists/${list.id}/members/${encodeURIComponent(state.user.username)}`, { method: 'DELETE' }); state.lists = state.lists.filter((x) => x.id !== list.id); go('today'); })) : null,
      list.mine === false ? null : h('button', { class: 'icon-btn', 'aria-label': 'Liste bearbeiten', title: 'Bearbeiten', onclick: () => listSheet(list) }, icon('more')),
      list.mine === false ? null : h('button', { class: 'icon-btn', 'aria-label': 'Liste löschen', onclick: guard(async () => { if (!confirm(`Liste „${list.name}“ löschen? Aufgaben bleiben erhalten.`)) return; await api('/lists/' + list.id, { method: 'DELETE' }); state.lists = state.lists.filter((x) => x.id !== list.id); state.todos.forEach((t) => { if (t.list_id === list.id) t.list_id = null; }); go('today'); }) }, icon('trash'))) : null,
    !list && r !== 'done' ? h('div', { class: 'row search-btn', style: 'gap:0' }, h('button', { class: 'icon-btn', 'aria-label': 'Kalender', onclick: () => go('calendar') }, icon('cal')),
      h('button', { class: 'icon-btn', 'aria-label': 'Suchen', onclick: () => go('search') }, icon('search'))) : null,
    r === 'done' ? btn('Aufräumen', 'sm danger', guard(async () => {
      if (!confirm('Alle erledigten Aufgaben in den Papierkorb verschieben?')) return;
      const x = await api('/todos/clear-done', { method: 'POST' });
      state.todos = (await api('/todos')).todos; renderTodos(); renderChrome();
      if (x.count) undoToast(`${x.count} erledigte Aufgabe${x.count === 1 ? '' : 'n'} im Papierkorb`, x.trash_id);
    }), 'trash') : null));
  addHeadTools(view);
  if (list && list.kind === 'project') view.appendChild(projectBar(list));
  if (r !== 'done') view.appendChild(quickBar());
  view.appendChild(h('div', { id: 'draft' }));
  view.appendChild(h('div', { id: 'progress' }));
  view.appendChild(h('div', { class: 'todo-list', id: 'todos' }));
  renderTodos();
  if (location.hash.includes('new=1')) setTimeout(() => { const i = $('#quick-input'); if (i) i.focus(); }, 50);
}

const DUE_LABELS = { any: 'Beliebig', overdue: 'Überfällig', today: 'Bis heute', week: 'Nächste 7 Tage', none: 'Ohne Datum' };
function describeQuery(f) {
  const parts = [];
  if (f.q) parts.push(`„${f.q}“`);
  (f.tags || []).forEach((g) => parts.push('#' + g));
  if (f.due && f.due !== 'any') parts.push(DUE_LABELS[f.due]);
  if (f.priority_min) parts.push('Priorität ≥ ' + ['Keine', 'Niedrig', 'Mittel', 'Hoch'][f.priority_min]);
  if (f.list_id) { const l = state.lists.find((x) => x.id === f.list_id); if (l) parts.push(l.name); }
  if (f.include_done) parts.push('inkl. erledigt');
  return parts.join(' · ') || 'Alle Aufgaben';
}

function viewShare(view) {
  const hashText = new URLSearchParams(location.hash.split('?')[1] || '').get('text');
  const text = h('textarea', { maxlength: 4000, style: 'min-height:140px', 'aria-label': 'Geteilter Text' });
  text.value = (hashText || state.shareText || '').slice(0, 4000);
  state.shareText = null;
  const save = guard(async () => {
    const raw = text.value.trim(); if (!raw) return;
    const [first, ...rest] = raw.split('\n');
    const { title, tags } = splitTags(first.slice(0, 300));
    await api('/todos', { method: 'POST', body: { title: title || first.slice(0, 300), notes: rest.join('\n').slice(0, 5000), tags } });
    state.todos = (await api('/todos')).todos; toast('Aufgabe gespeichert', 'ok'); go('all');
  });
  view.appendChild(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, 'Geteilt'), h('div', { class: 'muted small' }, 'Aus einer anderen App empfangen – als Aufgabe übernehmen'))));
  view.appendChild(h('div', { class: 'glass card col' }, text, h('div', { class: 'row wrap' },
    btn('Mit KI auswerten', 'primary', () => aiDraft(text.value.trim(), null), 'spark'),
    btn('Unverändert speichern', '', save, 'check'),
    btn('Verwerfen', 'sm', () => go('today')))));
  view.appendChild(h('div', { id: 'draft' }));
}

function shareListSheet(list) {
  const name = h('input', { type: 'text', placeholder: 'Benutzername', autocapitalize: 'none', maxlength: 64 });
  const members = h('div', { class: 'col', style: 'gap:6px' });
  const draw = () => {
    clear(members);
    if (!(list.members || []).length) members.appendChild(h('div', { class: 'muted small' }, 'Noch mit niemandem geteilt.'));
    (list.members || []).forEach((m) => members.appendChild(h('div', { class: 'row' }, h('div', { class: 'avatar' }, m[0]), h('span', { class: 'grow' }, m),
      btn('Entfernen', 'sm danger', guard(async () => { await api(`/lists/${list.id}/members/${encodeURIComponent(m)}`, { method: 'DELETE' }); list.members = list.members.filter((x) => x !== m); draw(); renderChrome(); })))));
  };
  draw();
  sheet(h('div', { class: 'col' }, h('h2', {}, `„${list.name}“ teilen`),
    h('p', { class: 'muted small' }, 'Mitglieder sehen alle Aufgaben dieser Liste, können neue anlegen, bearbeiten und abhaken. Deine anderen Aufgaben bleiben privat.'),
    members,
    h('form', { class: 'row', onsubmit: guard(async (e) => {
      e.preventDefault(); const u = name.value.trim(); if (!u) return;
      const r = await api(`/lists/${list.id}/members`, { method: 'POST', body: { username: u } });
      list.members = [...new Set([...(list.members || []), r.username])].sort(); name.value = ''; draw(); renderChrome(); toast(`Mit ${r.username} geteilt`, 'ok');
    }) }, name, h('button', { class: 'btn primary', type: 'submit' }, 'Hinzufügen'))));
  name.focus();
}

function viewCalendar(view) {
  const today = dayStart(new Date());
  state.calMonth = state.calMonth || new Date(today.getFullYear(), today.getMonth(), 1);
  state.calDay = state.calDay || today;
  const m = state.calMonth;
  const monthName = m.toLocaleDateString('de-DE', { month: 'long', year: 'numeric' });
  const shift = (n) => { state.calMonth = new Date(m.getFullYear(), m.getMonth() + n, 1); route(); };
  view.appendChild(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, monthName), h('div', { class: 'muted small' }, 'Fällige Aufgaben im Überblick')),
    h('div', { class: 'row', style: 'gap:4px' }, h('button', { class: 'icon-btn', 'aria-label': 'Vorheriger Monat', onclick: () => shift(-1) }, icon('chevl')),
      btn('Heute', 'sm', () => { state.calMonth = new Date(today.getFullYear(), today.getMonth(), 1); state.calDay = today; route(); }),
      h('button', { class: 'icon-btn', 'aria-label': 'Nächster Monat', onclick: () => shift(1) }, icon('chevr')))));
  const byDay = {};
  state.todos.filter((t) => !t.parent_id && t.due_at).forEach((t) => { const k = dayStart(new Date(t.due_at)).getTime(); (byDay[k] = byDay[k] || []).push(t); });
  const grid = h('div', { class: 'cal glass' });
  ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'].forEach((d) => grid.appendChild(h('div', { class: 'cal-head' }, d)));
  const first = new Date(m.getFullYear(), m.getMonth(), 1);
  const start = new Date(first); start.setDate(1 - ((first.getDay() + 6) % 7));
  for (let i = 0; i < 42; i++) {
    const d = new Date(start); d.setDate(start.getDate() + i);
    if (i >= 35 && d.getMonth() !== m.getMonth()) break;
    const items = (byDay[dayStart(d).getTime()] || []).sort((a, b) => a.done - b.done || a.due_at.localeCompare(b.due_at));
    const cls = ['cal-day', d.getMonth() !== m.getMonth() ? 'other' : '', d.getTime() === today.getTime() ? 'today' : '',
      d.getTime() === state.calDay.getTime() ? 'sel' : ''].join(' ');
    grid.appendChild(h('button', { class: cls, type: 'button', 'aria-label': d.toLocaleDateString('de-DE', { dateStyle: 'full' }) + `, ${items.length} Aufgaben`,
      onclick: () => { state.calDay = d; route(); } },
      h('span', { class: 'cal-num' }, d.getDate()),
      h('div', { class: 'cal-items' }, items.slice(0, 3).map((t) => h('span', { class: 'cal-item' + (t.done ? ' done' : '') + (t.priority === 3 ? ' high' : '') }, t.title))),
      items.length > 3 ? h('span', { class: 'cal-more' }, '+' + (items.length - 3)) : null,
      items.length ? h('span', { class: 'cal-dots' }, items.slice(0, 4).map((t) => h('i', { class: t.done ? 'done' : '' }))) : null));
  }
  view.appendChild(grid);
  const sel = state.calDay;
  const input = h('input', { type: 'text', placeholder: 'Aufgabe für diesen Tag …', maxlength: 300, enterkeyhint: 'done' });
  view.appendChild(h('div', { class: 'row' }, h('h2', { class: 'grow' }, sel.toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long' }))));
  view.appendChild(h('form', { class: 'quick glass', onsubmit: guard(async (e) => {
    e.preventDefault(); const { title, tags } = splitTags(input.value); if (!title) return;
    const due = new Date(sel); due.setHours(9, 0, 0, 0);
    state.todos.push(await api('/todos', { method: 'POST', body: { title, tags, due_at: due.toISOString() } })); input.value = ''; route();
  }) }, input, h('button', { class: 'icon-btn', type: 'submit', 'aria-label': 'Hinzufügen' }, icon('plus'))));
  const dayItems = byDay[sel.getTime()] || [];
  const rows = h('div', { class: 'rows glass' });
  dayItems.forEach((t) => rows.appendChild(todoRow(t)));
  view.appendChild(dayItems.length ? rows : h('div', { class: 'empty' }, 'Nichts fällig an diesem Tag.'));
}

async function uploadFiles(todoId, files) {
  for (const f of files) {
    if (f.size > 10 * 1024 * 1024) { toast(`${f.name}: zu groß (max. 10 MB)`, 'err'); continue; }
    const res = await fetch(`/api/todos/${todoId}/attachments`, { method: 'POST', credentials: 'same-origin', body: f,
      headers: { 'X-CSRF-Token': state.csrf, 'X-Filename': encodeURIComponent(f.name), 'Content-Type': 'application/octet-stream' } });
    if (!res.ok) { let msg = 'Upload fehlgeschlagen'; try { msg = (await res.json()).detail || msg; } catch (_) { /* */ } toast(`${f.name}: ${msg}`, 'err'); }
  }
}
const fmtSize = (n) => (n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(0) + ' KB' : (n / 1048576).toFixed(1) + ' MB');

function viewSearch(view) {
  const f = state.search;
  const input = h('input', { type: 'text', placeholder: 'Titel, Notizen oder #tag …', value: f.q, maxlength: 100, 'aria-label': 'Suche', enterkeyhint: 'search' });
  input.addEventListener('input', () => { f.q = input.value; renderTodos(); });
  const due = h('select', { 'aria-label': 'Fälligkeit', onchange: () => { f.due = due.value; renderTodos(); } }, Object.entries(DUE_LABELS).map(([k, l]) => h('option', { value: k, selected: f.due === k }, l)));
  const prio = h('select', { 'aria-label': 'Mindest-Priorität', onchange: () => { f.priority_min = Number(prio.value); renderTodos(); } }, ['Alle Prioritäten', 'ab Niedrig', 'ab Mittel', 'Nur Hoch'].map((l, i) => h('option', { value: i, selected: f.priority_min === i }, l)));
  const list = h('select', { 'aria-label': 'Liste', onchange: () => { f.list_id = list.value ? Number(list.value) : null; renderTodos(); } }, h('option', { value: '' }, 'Alle Listen'), state.lists.map((l) => h('option', { value: l.id, selected: f.list_id === l.id }, l.name)));
  const done = h('input', { type: 'checkbox', checked: f.include_done, onchange: () => { f.include_done = done.checked; renderTodos(); } });
  const tagBox = h('div', { class: 'row wrap', style: 'gap:6px' });
  const allTags = [...new Set(state.todos.flatMap((t) => t.tags || []))].sort();
  const drawTags = () => { clear(tagBox); allTags.forEach((g) => tagBox.appendChild(h('button', { type: 'button', class: 'chip' + (f.tags.includes(g) ? ' solid' : ''), onclick: () => { f.tags = f.tags.includes(g) ? f.tags.filter((x) => x !== g) : [...f.tags, g]; drawTags(); renderTodos(); } }, '#' + g))); };
  drawTags();
  view.appendChild(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, 'Suche'), h('div', { class: 'muted small' }, 'Filter kombinieren und als eigene Ansicht speichern')),
    btn('Als Filter speichern', 'sm', guard(async () => {
      const name = prompt('Name des Filters:', f.q || (f.tags[0] ? '#' + f.tags[0] : '')); if (!name || !name.trim()) return;
      const saved = await api('/filters', { method: 'POST', body: { name: name.trim(), query: f } });
      state.filters.push(saved); toast('Filter gespeichert', 'ok'); go('filter/' + saved.id);
    }), 'filter')));
  view.appendChild(h('div', { class: 'glass card col' }, h('div', { class: 'quick', style: 'padding:0;border:0' }, icon('search'), input),
    h('div', { class: 'search-grid' }, due, prio, list), allTags.length ? tagBox : null,
    h('label', { class: 'row small muted' }, done, 'Erledigte einbeziehen')));
  view.appendChild(h('div', { id: 'draft' }));
  view.appendChild(h('div', { id: 'progress' }));
  view.appendChild(h('div', { class: 'todo-list', id: 'todos' }));
  renderTodos();
  setTimeout(() => input.focus(), 30);
}

// Schnelleingabe: „morgen 15 Uhr Zahnarzt #privat !!“ – der Server erkennt Datum, Priorität, @Liste, Wiederholung (ohne KI)
function quickBar() {
  const input = h('input', { type: 'text', id: 'quick-input', placeholder: 'Neue Aufgabe, z. B. „morgen 15 Uhr Zahnarzt #privat !!“', maxlength: 300, autocomplete: 'off', enterkeyhint: 'done' });
  const preview = h('div', { class: 'quick-preview hidden', 'aria-live': 'polite' });
  let raw = false, seq = 0, timer = null;
  const drawPreview = (p) => {
    clear(preview);
    const list = p && p.list_id ? state.lists.find((l) => l.id === p.list_id) : null;
    const parts = p ? [p.due_at ? h('span', { class: 'chip' }, icon('clock'), fmtDue(p.due_at)) : null,
      p.recurrence_text ? h('span', { class: 'chip' }, icon('repeat'), p.recurrence_text) : null,
      p.priority ? h('span', { class: 'chip' + (p.priority === 3 ? ' danger' : '') }, icon('flag'), ['', 'Niedrig', 'Mittel', 'Hoch'][p.priority]) : null,
      list ? h('span', { class: 'chip' }, icon('list'), list.name) : null, (p.tags || []).map((g) => h('span', { class: 'chip' }, '#' + g))].flat().filter(Boolean) : [];
    if (raw) preview.append(h('span', { class: 'small muted' }, 'Wird genau so gespeichert, ohne Erkennung.'), h('button', { type: 'button', class: 'link-btn', onclick: () => { raw = false; refresh(); } }, 'Erkennung an'));
    else if (parts.length) preview.append(h('span', { class: 'small muted' }, '„' + p.title + '“'), ...parts, h('button', { type: 'button', class: 'link-btn', onclick: () => { raw = true; drawPreview(null); } }, 'Nur Text'));
    preview.classList.toggle('hidden', !raw && !parts.length);
  };
  const refresh = () => {
    clearTimeout(timer);
    const v = input.value.trim(), my = ++seq;
    if (!v || raw) { drawPreview(null); return; }
    timer = setTimeout(async () => { try { const p = await api('/quick/parse', { method: 'POST', body: { text: v } }); if (my === seq) drawPreview(p); } catch (_) { /* Vorschau ist optional */ } }, 160);
  };
  input.addEventListener('input', () => { if (!input.value.trim()) raw = false; refresh(); });
  const bar = h('form', { class: 'quick glass', onsubmit: guard(async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    const t = await api('/todos/quick', { method: 'POST', body: { text, raw, list_id: currentListId(), tags: routeTag() ? [routeTag()] : [] } });
    if (!state.todos.some((x) => x.id === t.id)) state.todos.push(t);
    input.value = ''; raw = false; seq++; drawPreview(null); renderTodos(); renderChrome();
    if (!filteredTodos().some((x) => x.id === t.id)) toast(`„${t.title}“ gespeichert` + (t.due_at ? ' – ' + fmtDue(t.due_at) : ''), 'ok');
  }) },
  input,
  h('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Mit KI auswerten', title: 'Mit KI auswerten', onclick: () => aiDraft(input.value.trim(), input) }, icon('spark')),
  h('button', { class: 'icon-btn mic', type: 'button', id: 'mic', 'aria-label': 'Spracheingabe', title: 'Spracheingabe', onclick: () => toggleRecord(input, bar) }, icon('mic')),
  h('button', { class: 'icon-btn', type: 'submit', 'aria-label': 'Hinzufügen' }, icon('plus')));
  return h('div', { class: 'col', style: 'gap:6px' }, bar, preview);
}
const TAG_RE = /(^|\s)#([\wäöüßÄÖÜ-]{1,30})/g;
function splitTags(text) {
  const tags = [];
  const title = text.replace(TAG_RE, (_, pre, g) => { const t = g.toLowerCase(); if (!tags.includes(t)) tags.push(t); return pre; }).replace(/\s+/g, ' ').trim();
  return { title, tags: tags.slice(0, 10) };
}
const currentListId = () => (state.route.startsWith('list/') ? Number(state.route.slice(5)) : null);

const aiDraft = guard(async (text, input) => {
  if (!text) { toast('Bitte zuerst Text eingeben oder sprechen.'); return; }
  const slot = clear($('#draft'));
  slot.appendChild(h('div', { class: 'glass card row' }, h('div', { class: 'spinner' }), h('span', { class: 'muted' }, 'KI analysiert …')));
  let r;
  try { r = await api('/ai/interpret', { method: 'POST', body: { text, ...aiCtx() } }); } catch (e) { clear(slot); throw e; }
  const acts = r.actions || [];
  if (!acts.length) { clear(slot); toast(r.reply || 'Nichts erkannt – bitte genauer formulieren.'); return; }
  if (acts.length === 1 && acts[0].type === 'create') return showDraft(acts[0], input);
  clear(slot).appendChild(actionPanel(acts, r.reply, () => { if (input) input.value = ''; }));
});

// ------------------------------------------------------------------ KI-Aktionen (immer erst nach Bestätigung)
async function executeAction(a) {
  if (a.type === 'create') await api('/todos', { method: 'POST', body: { title: a.title, notes: a.notes || '', priority: a.priority || 0, due_at: a.due_at || null, tags: a.tags || [], list_id: currentListId() } });
  else if (a.type === 'complete') await api('/todos/' + a.todo_id, { method: 'PATCH', body: { done: true } });
  else if (a.type === 'reschedule') await api('/todos/' + a.todo_id, { method: 'PATCH', body: { due_at: a.due_at } });
  else if (a.type === 'snooze') await api(`/todos/${a.todo_id}/snooze`, { method: 'POST', body: { minutes: a.minutes } });
  else if (a.type === 'message_agent') await api('/agent-bus/messages', { method: 'POST', body: { to: a.agent, kind: 'text', content: a.content } });
}
function actionDetail(a) {
  return [a.due_at ? fmtDue(a.due_at) : null, a.priority ? ['', 'Niedrig', 'Mittel', 'Hoch'][a.priority] : null,
    (a.tags || []).map((g) => '#' + g).join(' ') || null, a.type === 'message_agent' ? `„${a.content}“` : null].filter(Boolean).join(' · ');
}
function actionPanel(actions, reply, onDone) {
  const box = h('div', { class: 'glass card col', style: 'gap:10px' });
  const chosen = new Set(actions.map((_, i) => i));
  const runBtn = btn('Ausgewählte ausführen', 'sm primary', guard(async () => {
    runBtn.disabled = true;
    let n = 0;
    try { for (const i of [...chosen].sort()) { await executeAction(actions[i]); n++; } }
    finally {
      state.todos = (await api('/todos')).todos; renderTodos(); renderChrome();
      toast(`${n} Aktion${n === 1 ? '' : 'en'} ausgeführt`, 'ok'); box.remove(); if (onDone) onDone();
    }
  }), 'check');
  box.appendChild(h('div', { class: 'row muted small' }, icon('spark'), reply || 'Vorschläge – bitte prüfen'));
  actions.forEach((a, i) => {
    const cb = h('input', { type: 'checkbox', checked: true, onchange: () => { if (cb.checked) chosen.add(i); else chosen.delete(i); runBtn.disabled = !chosen.size; } });
    box.appendChild(h('label', { class: 'row', style: 'align-items:flex-start' }, cb, h('div', { class: 'grow' }, h('div', {}, a.label), actionDetail(a) ? h('div', { class: 'small muted' }, actionDetail(a)) : null)));
  });
  box.appendChild(h('div', { class: 'row' }, h('div', { class: 'grow' }), btn('Verwerfen', 'sm', () => box.remove()), runBtn));
  return box;
}

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
        const t = await api('/todos', { method: 'POST', body: { title: title.value, notes: d.notes || '', priority: prio, due_at: fromLocalInput(due.value), list_id: currentListId(), tags: d.tags || [] } });
        state.todos.push(t); if (input) input.value = ''; clear(slot); renderTodos(); renderChrome(); toast('Aufgabe gespeichert', 'ok');
        if (state.route === 'share') go('all');
      }), 'check'))));
}

function prioSeg(initial, onChange) {
  const labels = ['Keine', 'Niedrig', 'Mittel', 'Hoch'];
  const seg = h('div', { class: 'seg', role: 'group', 'aria-label': 'Priorität' });
  const draw = (cur) => { clear(seg); labels.forEach((l, i) => seg.appendChild(h('button', { type: 'button', class: i === cur ? 'on' : '', onclick: () => { onChange(i); draw(i); } }, l))); };
  draw(initial); return seg;
}

function renderTodos() {
  renderBulk();
  const box = $('#todos'); if (!box) return;
  clear(box);
  box.classList.toggle('board-mode', boardOn());
  if (boardOn()) { clear($('#progress')); return renderBoard(box); }
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

function collabChips(t) {
  const blockers = openBlockers(t), who = t.assignee_id ? personName(t.assignee_id) : null;
  return [
    !t.done && t.stage === 'doing' ? h('span', { class: 'chip' }, icon('play'), 'In Arbeit') : null,
    who ? h('span', { class: 'chip', title: 'Zuständig: ' + who }, h('b', { class: 'mini-avatar' }, who[0]), who === state.user.username ? 'Du' : who) : null,
    !t.done && blockers.length ? h('span', { class: 'chip', title: 'Wartet auf: ' + blockers.map((b) => b.title).join(', ') }, icon('lock'), 'wartet auf ' + (blockers.length === 1 ? '„' + blockers[0].title.slice(0, 24) + '“' : blockers.length)) : null,
    t.comment_count ? h('span', { class: 'chip', title: 'Kommentare' }, icon('comment'), t.comment_count) : null];
}

function todoRow(t) {
  const subs = state.todos.filter((s) => s.parent_id === t.id);
  const list = state.lists.find((l) => l.id === t.list_id);
  const overdue = !t.done && t.due_at && new Date(t.due_at) < new Date();
  const picking = state.selecting, picked = picking && state.picked.has(t.id);
  const row = h('div', { class: 'todo' + (t.done ? ' done' : '') + (state.selected === t.id ? ' sel' : '') + (picked ? ' picked' : ''), 'data-id': t.id },
    picking ? h('button', { class: 'check pick', type: 'button', role: 'checkbox', 'aria-checked': String(picked), 'aria-label': 'Auswählen', onclick: (e) => { e.stopPropagation(); togglePick(t.id); } }, icon('check'))
      : h('button', { class: 'check p' + t.priority, type: 'button', role: 'checkbox', 'aria-checked': String(t.done), 'aria-label': t.done ? 'Als offen markieren' : 'Erledigen', onclick: (e) => { e.stopPropagation(); toggleDone(t); } }, icon('check')),
    h('div', { class: 't-body', onclick: () => { if (row.dataset.lp) { delete row.dataset.lp; return; } if (state.selecting) togglePick(t.id); else select(t.id); } },
      h('div', { class: 't-title' }, t.title),
      h('div', { class: 't-meta' },
        t.due_at ? h('span', { class: 'chip' + (overdue ? ' danger' : '') }, icon('clock'), fmtDue(t.due_at)) : null,
        list ? h('span', { class: 'chip' }, list.name) : null,
        subs.length ? h('span', { class: 'chip' }, `${subs.filter((s) => s.done).length}/${subs.length}`) : null,
        t.priority > 0 ? h('span', { class: 'chip' + (t.priority === 3 ? ' danger' : '') }, icon('flag'), ['', 'Niedrig', 'Mittel', 'Hoch'][t.priority]) : null,
        t.location ? h('span', { class: 'chip' }, icon('pin'), t.location.name || 'Ort') : null,
        t.recurrence_text ? h('span', { class: 'chip', title: t.recurrence_text }, icon('repeat'), t.recurrence_text.replace(' (ab Erledigung)', '')) : null,
        t.tracked_min ? h('span', { class: 'chip', title: 'Erfasste Fokuszeit' }, icon('timer'), fmtMin(t.tracked_min)) : null,
        ...collabChips(t),
        (t.tags || []).map((g) => h('button', { type: 'button', class: 'chip tag', onclick: (e) => { e.stopPropagation(); go('tag/' + encodeURIComponent(g)); } }, '#' + g)),
        t.created_by !== 'user' ? h('span', { class: 'chip' }, icon('bus'), t.created_by) : null)));
  const wrap = h('div', { class: 'todo-wrap' },
    h('div', { class: 'swipe-bg' }, h('span', { class: 'l' }, icon('check')), h('span', { class: 'r' }, icon('trash'))), row);
  attachSwipe(row, t);
  return wrap;
}

function attachSwipe(row, t) {
  let x0 = null, y0 = 0, dx = 0, locked = false, lp = null;
  const cancelLp = () => { clearTimeout(lp); lp = null; };
  // Langes Drücken: Mehrfachauswahl starten
  row.addEventListener('pointerdown', (e) => {
    if (e.target.closest('button')) return;
    cancelLp();
    lp = setTimeout(() => { lp = null; x0 = null; row.dataset.lp = '1'; if (navigator.vibrate) navigator.vibrate(15); if (state.selecting) togglePick(t.id); else startSelecting(t.id); }, 520);
    if (e.pointerType === 'mouse' || state.selecting) return;
    x0 = e.clientX; y0 = e.clientY; dx = 0; locked = false;
  });
  row.addEventListener('pointerup', cancelLp); row.addEventListener('pointercancel', cancelLp); row.addEventListener('pointerleave', cancelLp);
  row.addEventListener('contextmenu', (e) => { if (row.dataset.lp) e.preventDefault(); });
  row.addEventListener('pointermove', (e) => {
    if (lp && Math.hypot(e.movementX, e.movementY) > 2) cancelLp();
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
  const blockers = !t.done ? openBlockers(t) : [];
  if (blockers.length && !confirm(`„${t.title}“ wartet noch auf: ${blockers.map((b) => b.title).join(', ')}. Trotzdem erledigen?`)) return;
  const u = await api('/todos/' + t.id, { method: 'PATCH', body: { done: !t.done } });
  const next = u.next; delete u.next;
  Object.assign(t, u);
  if (next) { state.todos = (await api('/todos')).todos; toast('Nächste Wiederholung: ' + fmtDue(next.due_at), 'ok'); }
  renderTodos(); renderChrome(); renderDetail();
});
const deleteTodo = guard(async (t) => {
  const r = await api('/todos/' + t.id, { method: 'DELETE' });
  state.todos = state.todos.filter((x) => x.id !== t.id && x.parent_id !== t.id);
  if (state.selected === t.id) state.selected = null;
  renderTodos(); renderChrome(); renderDetail(); undoToast('Aufgabe gelöscht', r.trash_id);
});
const restoreTrash = guard(async (id) => {
  const r = await api(`/trash/${id}/restore`, { method: 'POST' });
  state.todos = (await api('/todos')).todos;
  if (state.route === 'trash') route(); else { renderTodos(); renderChrome(); }
  toast(r.restored === 1 ? 'Wiederhergestellt' : `${r.restored} Aufgaben wiederhergestellt`, 'ok');
});
const undoToast = (msg, trashId) => toast(msg, '', trashId ? { label: 'Rückgängig', fn: () => restoreTrash(trashId) } : null);

// ------------------------------------------------------------------ Detail (Sheet auf Mobil, Seitenleiste am PC)
const wide = () => window.matchMedia('(min-width: 1280px)').matches;
function select(id) { state.selected = id; renderTodos(); renderDetail(); }
function renderDetail() {
  const app = $('#app'), pane = clear($('#detail-pane'));
  document.querySelectorAll('.overlay.detail').forEach((o) => o.remove());
  const t = state.todos.find((x) => x.id === state.selected);
  const show = !!t && !state.selecting && !['bus', 'assistant', 'settings', 'admin', 'stats', 'templates', 'trash'].includes(state.route);
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
  const save = guard(async (patch) => { const u = await api('/todos/' + t.id, { method: 'PATCH', body: patch }); delete u.next; Object.assign(t, u); renderTodos(); renderChrome(); });
  const title = h('input', { type: 'text', value: t.title, maxlength: 300, 'aria-label': 'Titel', onchange: () => title.value.trim() && save({ title: title.value }) });
  const notes = h('textarea', { 'aria-label': 'Notizen', placeholder: 'Notizen …', maxlength: 5000, onchange: () => save({ notes: notes.value }) }, t.notes);
  notes.value = t.notes;
  const due = h('input', { type: 'datetime-local', value: toLocalInput(t.due_at), 'aria-label': 'Fälligkeit', onchange: () => save({ due_at: fromLocalInput(due.value) }) });
  const sel = h('select', { 'aria-label': 'Liste', onchange: () => save({ list_id: sel.value ? Number(sel.value) : null }) },
    h('option', { value: '' }, 'Keine Liste'), state.lists.map((l) => h('option', { value: l.id, selected: l.id === t.list_id }, l.name)));
  const tagsIn = h('input', { type: 'text', value: (t.tags || []).join(', '), placeholder: 'z. B. arbeit, dringend', 'aria-label': 'Tags',
    onchange: () => save({ tags: tagsIn.value.split(/[,\s]+/).map((x) => x.replace(/^#/, '').trim()).filter(Boolean) }) });
  // Wiederholung
  const rec = t.recurrence || null;
  const freq = h('select', { 'aria-label': 'Wiederholung' }, [['', 'Keine'], ['daily', 'Täglich'], ['weekdays', 'Werktags (Mo–Fr)'], ['weekly', 'Wöchentlich'], ['monthly', 'Monatlich'], ['yearly', 'Jährlich']]
    .map(([v, l]) => h('option', { value: v, selected: (rec ? rec.freq : '') === v }, l)));
  const interval = h('input', { type: 'number', min: 1, max: 365, value: rec ? rec.interval : 1, 'aria-label': 'Intervall', class: 'num' });
  const afterDone = h('input', { type: 'checkbox', checked: !!(rec && rec.after_done) });
  const recExtra = h('div', { class: 'row wrap small muted' + (rec ? '' : ' hidden') }, 'alle', interval, h('span', { id: 'rec-unit' }), h('label', { class: 'row', style: 'gap:6px' }, afterDone, 'ab Erledigung zählen'));
  const unitText = () => ({ daily: 'Tag(e)', weekly: 'Woche(n)', monthly: 'Monat(e)', yearly: 'Jahr(e)', weekdays: '' })[freq.value] || '';
  const saveRec = () => {
    recExtra.classList.toggle('hidden', !freq.value); recExtra.querySelector('#rec-unit').textContent = unitText();
    interval.classList.toggle('hidden', freq.value === 'weekdays');
    save({ recurrence: freq.value ? { freq: freq.value, interval: Math.max(1, Math.min(365, Number(interval.value) || 1)), after_done: afterDone.checked } : null });
  };
  freq.addEventListener('change', saveRec); interval.addEventListener('change', saveRec); afterDone.addEventListener('change', saveRec);
  recExtra.querySelector('#rec-unit').textContent = unitText(); interval.classList.toggle('hidden', freq.value === 'weekdays');
  // Erinnerungen
  const OFFSETS = [[0, 'Zur Fälligkeit'], [10, '10 Min. vorher'], [30, '30 Min.'], [60, '1 Std.'], [1440, '1 Tag'], [10080, '1 Woche']];
  let offsets = [...(t.remind_offsets || [0])];
  const remBox = h('div', { class: 'row wrap', style: 'gap:6px' });
  const drawRem = () => { clear(remBox); OFFSETS.forEach(([v, l]) => remBox.appendChild(h('button', { type: 'button', class: 'chip' + (offsets.includes(v) ? ' solid' : ''), 'aria-pressed': String(offsets.includes(v)),
    onclick: () => { offsets = offsets.includes(v) ? offsets.filter((x) => x !== v) : [...offsets, v].slice(-5); drawRem(); save({ remind_offsets: offsets }); } }, l))); };
  drawRem();
  const tomorrow9 = () => { const d = new Date(); d.setDate(d.getDate() + 1); d.setHours(9, 0, 0, 0); return Math.max(1, Math.round((d - new Date()) / 60000)); };
  const snoozeBtn = (label, min) => btn(label, 'sm', guard(async () => { const r = await api(`/todos/${t.id}/snooze`, { method: 'POST', body: { minutes: typeof min === 'function' ? min() : min } }); toast('Ich erinnere dich ' + fmtDue(r.snoozed_until), 'ok'); }));
  // Ort (Erinnerung beim Ankommen – über die Android-App)
  const locBox = h('div', { class: 'col', style: 'gap:8px' });
  const drawLoc = () => {
    clear(locBox);
    const l = t.location;
    if (l) {
      const radius = h('select', { 'aria-label': 'Radius', onchange: () => save({ location: { ...l, radius: Number(radius.value) } }) },
        [100, 200, 500, 1000, 2000].map((r) => h('option', { value: r, selected: l.radius === r }, r < 1000 ? r + ' m' : r / 1000 + ' km')));
      const name = h('input', { type: 'text', value: l.name || '', placeholder: 'Name, z. B. Supermarkt', maxlength: 80, onchange: () => save({ location: { ...l, name: name.value.trim() } }) });
      locBox.appendChild(h('div', { class: 'row' }, icon('pin'), h('span', { class: 'small muted grow' }, `${l.lat.toFixed(5)}, ${l.lon.toFixed(5)}`),
        h('a', { class: 'small muted', href: `https://www.openstreetmap.org/?mlat=${l.lat}&mlon=${l.lon}#map=17/${l.lat}/${l.lon}`, target: '_blank', rel: 'noopener noreferrer' }, 'Karte')));
      locBox.appendChild(h('div', { class: 'search-grid' }, name, radius));
      locBox.appendChild(btn('Ort entfernen', 'sm', async () => { await save({ location: null }); drawLoc(); }));
    } else {
      const manual = h('input', { type: 'text', placeholder: 'Breite, Länge – z. B. 52.5200, 13.4050', 'aria-label': 'Koordinaten' });
      locBox.appendChild(h('div', { class: 'row wrap' },
        btn('Aktueller Standort', 'sm', () => {
          if (!navigator.geolocation) { toast('Standort wird nicht unterstützt.', 'err'); return; }
          navigator.geolocation.getCurrentPosition(async (p) => { await save({ location: { name: '', lat: p.coords.latitude, lon: p.coords.longitude, radius: 200 } }); drawLoc(); },
            () => toast('Standort nicht verfügbar oder nicht erlaubt.', 'err'), { enableHighAccuracy: true, timeout: 15000 });
        }, 'pin')));
      locBox.appendChild(h('form', { class: 'row', onsubmit: async (e) => {
        e.preventDefault();
        const m = manual.value.match(/(-?\d+(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d+(?:[.,]\d+)?)/);
        if (!m) { toast('Bitte als „Breite, Länge“ eingeben.', 'err'); return; }
        await save({ location: { name: '', lat: Number(m[1].replace(',', '.')), lon: Number(m[2].replace(',', '.')), radius: 200 } }); drawLoc();
      } }, manual, h('button', { class: 'icon-btn', type: 'submit', 'aria-label': 'Ort setzen' }, icon('plus'))));
    }
  };
  drawLoc();
  const attBox = h('div', { class: 'col', style: 'gap:8px' });
  const file = h('input', { type: 'file', multiple: true, class: 'hidden', accept: 'image/png,image/jpeg,image/gif,image/webp,application/pdf,text/plain' });
  file.addEventListener('change', guard(async () => { await uploadFiles(t.id, [...file.files]); file.value = ''; drawAtt(); }));
  const drawAtt = guard(async () => {
    const { attachments } = await api(`/todos/${t.id}/attachments`);
    clear(attBox);
    const grid = h('div', { class: 'att-grid' });
    attachments.forEach((a) => grid.appendChild(h('div', { class: 'att' },
      a.mime.startsWith('image/') ? h('a', { href: a.url, target: '_blank', rel: 'noopener' }, h('img', { src: a.url, alt: a.filename, loading: 'lazy' }))
        : h('a', { class: 'att-file', href: a.url, target: '_blank', rel: 'noopener' }, icon('clip'), h('span', {}, a.filename)),
      h('div', { class: 'row small muted', style: 'gap:4px' }, h('span', { class: 'grow', style: 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap' }, fmtSize(a.size)),
        h('button', { class: 'icon-btn', style: 'width:28px;height:28px', 'aria-label': 'Anhang löschen', onclick: guard(async () => { if (!confirm(`„${a.filename}“ löschen?`)) return; await api('/attachments/' + a.id, { method: 'DELETE' }); drawAtt(); }) }, icon('trash'))))));
    if (attachments.length) attBox.appendChild(grid);
    attBox.appendChild(h('div', { class: 'row' }, btn('Datei anhängen', 'sm', () => file.click(), 'clip'), h('span', { class: 'small muted' }, 'Bilder, PDF, Text · max. 10 MB'), file));
  });
  drawAtt();
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
  const collab = collabSection(t, save);
  return h('div', { class: 'col', style: 'gap:14px' },
    h('div', { class: 'row' }, h('h2', { class: 'grow' }, 'Details'), h('button', { class: 'icon-btn', 'aria-label': 'Schließen', onclick: () => { state.selected = null; renderTodos(); renderDetail(); } }, icon('x'))),
    h('label', { class: 'field' }, 'Titel', title), h('label', { class: 'field' }, 'Notizen', notes),
    h('label', { class: 'field' }, 'Fällig', due), h('label', { class: 'field' }, 'Liste', sel),
    h('div', { class: 'field' }, 'Priorität', prioSeg(t.priority, (p) => save({ priority: p }))),
    collab.top,
    h('label', { class: 'field' }, 'Tags', tagsIn),
    h('div', { class: 'field' }, 'Wiederholung', freq, recExtra),
    h('div', { class: 'field' }, 'Erinnerungen' + (t.due_at ? '' : ' (wirken erst mit Fälligkeit)'), remBox),
    h('div', { class: 'field' }, 'Anhänge', attBox),
    h('div', { class: 'field' }, 'Ort (Erinnerung beim Ankommen, Android-App)', locBox),
    !t.done ? h('div', { class: 'field' }, 'Erinnere mich', h('div', { class: 'row wrap' }, snoozeBtn('in 10 Min.', 10), snoozeBtn('in 1 Std.', 60), snoozeBtn('morgen 9:00', tomorrow9))) : null,
    h('div', { class: 'col', style: 'gap:6px' }, h('div', { class: 'row' }, h('span', { class: 'muted small grow' }, 'Unteraufgaben'), aiBtn), subsBox,
      h('form', { class: 'row', onsubmit: (e) => { e.preventDefault(); const v = subInput.value.trim(); if (v) { subInput.value = ''; addSub(v); } } }, subInput, h('button', { class: 'icon-btn', type: 'submit', 'aria-label': 'Hinzufügen' }, icon('plus')))),
    collab.bottom,
    h('div', { class: 'field' }, 'Fokus-Timer' + (t.tracked_min ? ` · bisher ${fmtMin(t.tracked_min)} erfasst` : ''),
      !t.done ? h('div', { class: 'row wrap' }, [15, 25, 50].map((m) => btn(m + ' min', 'sm', () => startFocus(t, m), 'play'))) : null),
    h('div', { class: 'muted small' }, `Erstellt ${fmtTs(t.created_at)}${t.created_by !== 'user' ? ' von Agent ' + t.created_by : ''}`),
    h('div', { class: 'row wrap' }, btn('Als Vorlage', '', () => templateFromTodo(t), 'layers'), btn('Aufgabe löschen', 'danger', () => deleteTodo(t), 'trash')));
}

// ------------------------------------------------------------------ Mehrfachauswahl
function startSelecting(id) {
  state.selecting = true; state.picked = new Set(id ? [id] : []); state.selected = null;
  document.body.classList.add('selecting'); renderTodos(); renderDetail();
}
function stopSelecting(redraw = true) {
  state.selecting = false; state.picked = new Set();
  document.body.classList.remove('selecting');
  const bar = $('#bulkbar'); if (bar) bar.remove();
  if (redraw) renderTodos();
}
function togglePick(id) { if (state.picked.has(id)) state.picked.delete(id); else state.picked.add(id); renderTodos(); }
function choiceSheet(title, options, extra) {
  const close = sheet(h('div', { class: 'col' }, h('h2', {}, title),
    h('div', { class: 'col', style: 'gap:6px' }, options.map(([label, fn, cls]) => btn(label, cls || '', () => { close(); fn(); }))), extra || null));
  return close;
}
function renderBulk() {
  let bar = $('#bulkbar');
  if (!state.selecting) { if (bar) bar.remove(); return; }
  if (!bar) { bar = h('div', { class: 'bulkbar glass', id: 'bulkbar', role: 'toolbar', 'aria-label': 'Auswahl bearbeiten' }); document.body.appendChild(bar); }
  const ids = [...state.picked], n = ids.length;
  const run = (body, msg) => guard(async () => {
    const r = await api('/todos/bulk', { method: 'POST', body: { ids, ...body } });
    state.todos = (await api('/todos')).todos; stopSelecting(); renderChrome();
    if (body.action === 'delete') undoToast(`${r.count} Aufgabe${r.count === 1 ? '' : 'n'} gelöscht`, r.trash_id);
    else toast(`${msg} (${r.count})`, 'ok');
  })();
  const at = (days, hour) => { const d = new Date(); d.setDate(d.getDate() + days); d.setHours(hour, 0, 0, 0); return d.toISOString(); };
  const nextMonday = () => { const d = new Date(); return at(((8 - d.getDay()) % 7) || 7, 9); };
  const act = (ic, label, fn) => h('button', { class: 'bulk-btn', type: 'button', title: label, 'aria-label': label, disabled: !n, onclick: fn }, icon(ic), h('span', {}, label));
  const dueInput = h('input', { type: 'datetime-local', 'aria-label': 'Datum und Uhrzeit' });
  const tagInput = h('input', { type: 'text', placeholder: 'z. B. arbeit, dringend', 'aria-label': 'Tags' });
  const tagList = () => tagInput.value.split(/[,\s]+/).map((x) => x.replace(/^#/, '').trim()).filter(Boolean);
  clear(bar).append(
    h('strong', { class: 'small bulk-count' }, String(n), h('span', { class: 'bulk-word' }, ' ausgewählt')),
    h('button', { class: 'link-btn', type: 'button', onclick: () => { filteredTodos().forEach((t) => state.picked.add(t.id)); renderTodos(); } }, 'Alle'),
    h('div', { class: 'grow' }),
    act('check', 'Erledigt', () => run({ action: 'done' }, 'Erledigt')),
    act('list', 'Liste', () => choiceSheet('In Liste verschieben', [['Keine Liste', () => run({ action: 'move', list_id: null }, 'Verschoben')],
      ...state.lists.map((l) => [l.name, () => run({ action: 'move', list_id: l.id }, 'Verschoben')])])),
    act('tag', 'Tags', () => { const close = sheet(h('div', { class: 'col' }, h('h2', {}, 'Tags'), tagInput, h('div', { class: 'row wrap' },
      btn('Hinzufügen', 'primary', () => { if (tagList().length) { close(); run({ action: 'tag', tags: tagList() }, 'Tags ergänzt'); } }),
      btn('Entfernen', '', () => { if (tagList().length) { close(); run({ action: 'untag', tags: tagList() }, 'Tags entfernt'); } })))); tagInput.focus(); }),
    act('cal', 'Datum', () => choiceSheet('Fälligkeit setzen', [['Heute 18:00', () => run({ action: 'due', due_at: at(0, 18) }, 'Datum gesetzt')],
      ['Morgen 9:00', () => run({ action: 'due', due_at: at(1, 9) }, 'Datum gesetzt')], ['Nächster Montag 9:00', () => run({ action: 'due', due_at: nextMonday() }, 'Datum gesetzt')],
      ['Datum entfernen', () => run({ action: 'due', due_at: null }, 'Datum entfernt')]],
      h('form', { class: 'row', onsubmit: (e) => { e.preventDefault(); if (!dueInput.value) return; document.querySelectorAll('.overlay').forEach((o) => o.remove()); run({ action: 'due', due_at: fromLocalInput(dueInput.value) }, 'Datum gesetzt'); } },
        dueInput, h('button', { class: 'btn', type: 'submit' }, 'Setzen')))),
    act('flag', 'Priorität', () => choiceSheet('Priorität', [3, 2, 1, 0].map((p) => [['Keine', 'Niedrig', 'Mittel', 'Hoch'][p], () => run({ action: 'priority', priority: p }, 'Priorität gesetzt')]))),
    act('trash', 'Löschen', () => run({ action: 'delete' })),
    h('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Auswahl beenden', title: 'Fertig', onclick: () => stopSelecting() }, icon('x')));
}
function addHeadTools(view) {
  const head = view.querySelector('.page-head'); if (!head) return;
  const tools = h('div', { class: 'row', style: 'gap:0' });
  [...head.children].slice(1).forEach((c) => tools.appendChild(c));
  if (state.route !== 'done') tools.appendChild(h('button', { class: 'icon-btn', 'aria-label': 'Aus Vorlage anlegen', title: 'Aus Vorlage', onclick: templatePicker }, icon('layers')));
  if (boardable()) tools.appendChild(h('button', { class: 'icon-btn' + (boardOn() ? ' on' : ''), 'aria-label': boardOn() ? 'Als Liste anzeigen' : 'Als Board anzeigen', title: boardOn() ? 'Liste' : 'Board', 'aria-pressed': String(boardOn()), onclick: () => setBoard(!boardOn()) }, icon(boardOn() ? 'list' : 'board')));
  tools.appendChild(h('button', { class: 'icon-btn', 'aria-label': 'Mehrere auswählen', title: 'Mehrere auswählen', onclick: () => (state.selecting ? stopSelecting() : startSelecting()) }, icon('select')));
  head.appendChild(tools);
}

// ------------------------------------------------------------------ Board (Kanban): Offen · In Arbeit · Erledigt
const boardable = () => /^(list|tag|filter)\//.test(state.route) || ['all', 'assigned'].includes(state.route);
const boardOn = () => { if (!boardable()) return false; try { return localStorage.getItem('board:' + state.route) === '1'; } catch (_) { return false; } };
const setBoard = (on) => { try { localStorage.setItem('board:' + state.route, on ? '1' : '0'); } catch (_) { /* privat */ } route(); };
const COLUMNS = [['todo', 'Offen'], ['doing', 'In Arbeit'], ['done', 'Erledigt']];
function boardItems() {
  const r = state.route, top = state.todos.filter((t) => !t.parent_id);
  if (r.startsWith('list/')) return top.filter((t) => t.list_id === Number(r.slice(5)));
  if (r === 'assigned') return top.filter((t) => t.assignee_id === state.user.id);
  if (r.startsWith('tag/')) return applyQuery(top, { tags: [routeTag()], include_done: true });
  if (r.startsWith('filter/')) { const f = routeFilter(); return f ? applyQuery(top, { ...f.query, include_done: true }) : []; }
  return top;
}
const moveCard = guard(async (t, col) => {
  if ((col === 'done') === t.done && (col === 'done' || t.stage === col)) return;
  if (col === 'done' && openBlockers(t).length && !confirm(`„${t.title}“ wartet noch auf andere Aufgaben. Trotzdem erledigen?`)) return;
  const u = await api('/todos/' + t.id, { method: 'PATCH', body: col === 'done' ? { done: true } : { stage: col } });
  const next = u.next; delete u.next; Object.assign(t, u);
  if (next) state.todos = (await api('/todos')).todos;
  renderTodos(); renderChrome();
});
function renderBoard(box) {
  const items = boardItems();
  const weekAgo = Date.now() - 14 * 86400000;
  const cols = {
    todo: items.filter((t) => !t.done && t.stage !== 'doing'),
    doing: items.filter((t) => !t.done && t.stage === 'doing'),
    done: items.filter((t) => t.done && (!t.done_at || new Date(t.done_at).getTime() > weekAgo)).sort((a, b) => (b.done_at || '').localeCompare(a.done_at || '')).slice(0, 30),
  };
  const board = h('div', { class: 'board' });
  COLUMNS.forEach(([key, label]) => {
    const list = h('div', { class: 'board-list' });
    const col = h('section', { class: 'board-col glass', 'data-col': key, 'aria-label': label },
      h('div', { class: 'board-head' }, h('span', {}, label), h('span', { class: 'count' }, cols[key].length)), list);
    col.addEventListener('dragover', (e) => { e.preventDefault(); col.classList.add('drop'); });
    col.addEventListener('dragleave', (e) => { if (!col.contains(e.relatedTarget)) col.classList.remove('drop'); });
    col.addEventListener('drop', (e) => { e.preventDefault(); col.classList.remove('drop'); const t = byId(Number(e.dataTransfer.getData('text/plain'))); if (t) moveCard(t, key); });
    cols[key].forEach((t) => list.appendChild(boardCard(t, key)));
    if (!cols[key].length) list.appendChild(h('div', { class: 'board-empty small muted' }, key === 'done' ? 'Noch nichts erledigt' : 'Hierher ziehen'));
    board.appendChild(col);
  });
  box.appendChild(board);
}
function boardCard(t, key) {
  const list = state.lists.find((l) => l.id === t.list_id);
  const overdue = !t.done && t.due_at && new Date(t.due_at) < new Date();
  const picked = state.selecting && state.picked.has(t.id);
  const card = h('div', { class: 'kcard' + (t.done ? ' done' : '') + (state.selected === t.id ? ' sel' : '') + (picked ? ' picked' : ''), draggable: 'true', tabindex: 0, role: 'button', 'aria-label': t.title,
    onclick: () => (state.selecting ? togglePick(t.id) : select(t.id)), onkeydown: (e) => { if (e.key === 'Enter') select(t.id); } },
  h('div', { class: 'row', style: 'align-items:flex-start;gap:8px' }, h('div', { class: 'grow kcard-title' }, t.title),
    h('button', { class: 'icon-btn kcard-move', type: 'button', 'aria-label': 'Verschieben', onclick: (e) => { e.stopPropagation(); choiceSheet('„' + t.title + '“ verschieben', COLUMNS.filter(([k]) => k !== key).map(([k, l]) => [l, () => moveCard(t, k)])); } }, icon('more'))),
  h('div', { class: 't-meta' },
    t.due_at ? h('span', { class: 'chip' + (overdue ? ' danger' : '') }, icon('clock'), fmtDue(t.due_at)) : null,
    t.priority === 3 ? h('span', { class: 'chip danger' }, icon('flag'), 'Hoch') : null,
    list && !state.route.startsWith('list/') ? h('span', { class: 'chip' }, list.name) : null,
    ...collabChips(t).filter((c) => c && !/In Arbeit/.test(c.textContent))));
  card.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/plain', String(t.id)); e.dataTransfer.effectAllowed = 'move'; card.classList.add('dragging'); });
  card.addEventListener('dragend', () => card.classList.remove('dragging'));
  return card;
}

// ------------------------------------------------------------------ Vorlagen
function templateInfo(tp) {
  const list = tp.list_id ? state.lists.find((l) => l.id === tp.list_id) : null;
  return [tp.title !== tp.name ? `„${tp.title}“` : null, tp.subtasks.length ? `${tp.subtasks.length} Unteraufgabe${tp.subtasks.length === 1 ? '' : 'n'}` : null,
    tp.due_days === null || tp.due_days === undefined ? null : (tp.due_days === 0 ? 'fällig am selben Tag' : `fällig nach ${tp.due_days} Tag${tp.due_days === 1 ? '' : 'en'}`) + (tp.due_time ? ' um ' + tp.due_time : ''),
    list ? list.name : null, (tp.tags || []).map((g) => '#' + g).join(' ') || null].filter(Boolean).join(' · ');
}
const useTemplate = guard(async (tp, listId) => {
  const t = await api(`/templates/${tp.id}/use`, { method: 'POST', body: { list_id: listId === undefined ? null : listId } });
  state.todos = (await api('/todos')).todos; renderTodos(); renderChrome();
  toast(`„${t.title}“ angelegt`, 'ok', { label: 'Öffnen', fn: () => { if (!isTaskRoute(state.route) || state.route === 'done') go('all'); setTimeout(() => select(t.id), 60); } });
});
const templatePicker = guard(async () => {
  const { templates } = await api('/templates');
  const close = sheet(h('div', { class: 'col' }, h('h2', {}, 'Aus Vorlage anlegen'),
    templates.length ? h('div', { class: 'col', style: 'gap:6px' }, templates.map((tp) => h('button', { class: 'pick-row', type: 'button', onclick: () => { close(); useTemplate(tp, currentListId()); } },
      icon('layers'), h('div', { class: 'grow' }, h('div', {}, tp.name), h('div', { class: 'small muted' }, templateInfo(tp) || 'Einfache Aufgabe')))))
      : h('div', { class: 'muted small' }, 'Noch keine Vorlagen. Speichere eine Aufgabe als Vorlage (in den Details) oder lege eine neue an.'),
    h('div', { class: 'row' }, btn('Vorlagen verwalten', 'sm', () => { close(); go('templates'); }), h('div', { class: 'grow' }), btn('Neue Vorlage', 'sm', () => { close(); templateSheet(); }, 'plus'))));
});
function templateSheet(tp = {}, onSaved) {
  const name = h('input', { type: 'text', maxlength: 60, value: tp.name || '', placeholder: 'z. B. Urlaub packen', required: true });
  const title = h('input', { type: 'text', maxlength: 300, value: tp.title || '', placeholder: 'Titel der Aufgabe', required: true });
  const notes = h('textarea', { maxlength: 5000, placeholder: 'Notizen (optional)', style: 'min-height:70px' }); notes.value = tp.notes || '';
  let prio = tp.priority || 0;
  const tags = h('input', { type: 'text', value: (tp.tags || []).join(', '), placeholder: 'Tags, z. B. reise' });
  const list = h('select', { 'aria-label': 'Liste' }, h('option', { value: '' }, 'Keine Liste'), state.lists.map((l) => h('option', { value: l.id, selected: l.id === tp.list_id }, l.name)));
  const dueOpts = [['', 'Ohne Fälligkeit'], ['0', 'Am selben Tag'], ['1', 'Nach 1 Tag'], ['2', 'Nach 2 Tagen'], ['3', 'Nach 3 Tagen'], ['7', 'Nach 1 Woche'], ['14', 'Nach 2 Wochen'], ['30', 'Nach 30 Tagen']];
  const cur = tp.due_days === null || tp.due_days === undefined ? '' : String(tp.due_days);
  if (!dueOpts.some(([v]) => v === cur)) dueOpts.push([cur, `Nach ${cur} Tagen`]);
  const due = h('select', { 'aria-label': 'Fälligkeit' }, dueOpts.map(([v, l]) => h('option', { value: v, selected: v === cur }, l)));
  const time = h('input', { type: 'time', value: tp.due_time || '09:00', 'aria-label': 'Uhrzeit' });
  const subs = h('textarea', { placeholder: 'Eine Unteraufgabe pro Zeile', style: 'min-height:110px' }); subs.value = (tp.subtasks || []).join('\n');
  const close = sheet(h('form', { class: 'col', onsubmit: guard(async (e) => {
    e.preventDefault();
    const body = { name: name.value.trim(), title: title.value.trim(), notes: notes.value, priority: prio,
      tags: tags.value.split(/[,\s]+/).map((x) => x.replace(/^#/, '').trim()).filter(Boolean), list_id: list.value ? Number(list.value) : null,
      due_days: due.value === '' ? null : Number(due.value), due_time: due.value === '' ? null : time.value || null,
      subtasks: subs.value.split('\n').map((x) => x.trim()).filter(Boolean).slice(0, 50) };
    const saved = await api(tp.id ? '/templates/' + tp.id : '/templates', { method: tp.id ? 'PUT' : 'POST', body });
    close(); toast('Vorlage gespeichert', 'ok'); if (onSaved) onSaved(saved); else if (state.route === 'templates') route();
  }) }, h('h2', {}, tp.id ? 'Vorlage bearbeiten' : 'Neue Vorlage'),
  h('label', { class: 'field' }, 'Name der Vorlage', name), h('label', { class: 'field' }, 'Aufgabe', title), notes,
  h('div', { class: 'field' }, 'Priorität', prioSeg(prio, (p) => { prio = p; })),
  h('div', { class: 'search-grid' }, h('label', { class: 'field' }, 'Fälligkeit', due), h('label', { class: 'field' }, 'Uhrzeit', time)),
  h('div', { class: 'search-grid' }, h('label', { class: 'field' }, 'Liste', list), h('label', { class: 'field' }, 'Tags', tags)),
  h('label', { class: 'field' }, 'Unteraufgaben', subs),
  h('div', { class: 'row' }, h('div', { class: 'grow' }), btn('Abbrechen', '', () => close()), h('button', { class: 'btn primary', type: 'submit' }, 'Speichern'))));
  name.focus();
}
function templateFromTodo(t) {
  let days = null, time = null;
  if (t.due_at) { const d = new Date(t.due_at); days = Math.max(0, Math.round((dayStart(d) - dayStart(new Date())) / 86400000)); time = `${pad(d.getHours())}:${pad(d.getMinutes())}`; }
  templateSheet({ name: t.title.slice(0, 60), title: t.title, notes: t.notes, priority: t.priority, tags: t.tags, list_id: t.list_id, due_days: days, due_time: time,
    subtasks: state.todos.filter((s) => s.parent_id === t.id).map((s) => s.title) }, () => toast('Vorlage gespeichert – „Aus Vorlage“ legt sie neu an', 'ok'));
}
function viewTemplates(view) {
  view.appendChild(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, 'Vorlagen'), h('div', { class: 'muted small' }, 'Wiederkehrende Checklisten mit einem Klick anlegen')),
    btn('Vorlage', 'sm primary', () => templateSheet(), 'plus')));
  const box = h('div', { class: 'col' }); view.appendChild(box);
  guard(async () => {
    const { templates } = await api('/templates'); clear(box);
    if (!templates.length) box.appendChild(h('div', { class: 'empty glass' }, icon('layers'), h('div', {}, 'Noch keine Vorlagen. Lege eine an – oder öffne eine Aufgabe und wähle „Als Vorlage“.')));
    templates.forEach((tp) => box.appendChild(h('div', { class: 'glass card row', style: 'align-items:flex-start' },
      h('div', { class: 'grow col', style: 'gap:4px' }, h('strong', {}, tp.name), h('div', { class: 'small muted' }, templateInfo(tp) || 'Einfache Aufgabe'),
        tp.used_count ? h('div', { class: 'small muted' }, `${tp.used_count}× verwendet`) : null),
      btn('Anlegen', 'sm primary', () => useTemplate(tp, tp.list_id), 'plus'),
      h('button', { class: 'icon-btn', 'aria-label': 'Bearbeiten', onclick: () => templateSheet(tp) }, icon('more')),
      h('button', { class: 'icon-btn', 'aria-label': 'Vorlage löschen', onclick: guard(async () => { if (!confirm(`Vorlage „${tp.name}“ löschen?`)) return; await api('/templates/' + tp.id, { method: 'DELETE' }); route(); }) }, icon('trash')))));
  })();
}

// ------------------------------------------------------------------ Papierkorb
function viewTrash(view) {
  const box = h('div', { class: 'col' });
  view.appendChild(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, 'Papierkorb'), h('div', { class: 'muted small', id: 'trash-sub' }, 'Gelöschte Aufgaben')),
    btn('Leeren', 'sm danger', guard(async () => { if (!confirm('Papierkorb endgültig leeren? Das kann nicht rückgängig gemacht werden.')) return; await api('/trash', { method: 'DELETE' }); route(); }), 'trash')));
  view.appendChild(box);
  guard(async () => {
    const { entries, keep_days } = await api('/trash'); clear(box);
    $('#trash-sub').textContent = `Gelöschte Aufgaben bleiben ${keep_days} Tage hier und lassen sich vollständig wiederherstellen.`;
    if (!entries.length) box.appendChild(h('div', { class: 'empty glass' }, icon('trash'), h('div', {}, 'Der Papierkorb ist leer.')));
    entries.forEach((e) => box.appendChild(h('div', { class: 'glass card row', style: 'align-items:flex-start' },
      h('div', { class: 'grow col', style: 'gap:4px' }, h('strong', {}, e.title),
        h('div', { class: 'small muted' }, ['gelöscht ' + fmtTs(e.deleted_at), e.count > 1 ? `${e.count} Aufgaben` : null, e.subtasks ? `${e.subtasks} Unteraufgabe${e.subtasks === 1 ? '' : 'n'}` : null].filter(Boolean).join(' · ')),
        e.count > 1 ? h('div', { class: 'small muted' }, e.items.map((i) => i.title).join(', ') + (e.count > e.items.length ? ' …' : '')) : null),
      btn('Wiederherstellen', 'sm', () => restoreTrash(e.id), 'undo'),
      h('button', { class: 'icon-btn', 'aria-label': 'Endgültig löschen', title: 'Endgültig löschen', onclick: guard(async () => { if (!confirm(`„${e.title}“ endgültig löschen?`)) return; await api('/trash/' + e.id, { method: 'DELETE' }); route(); }) }, icon('x')))));
  })();
}

// ------------------------------------------------------------------ Fokus-Timer (läuft im Browser, Zeit wird an der Aufgabe erfasst)
const FOCUS_KEY = 'focus';
const readFocus = () => { try { return JSON.parse(localStorage.getItem(FOCUS_KEY) || 'null'); } catch (_) { return null; } };
const writeFocus = (f) => { try { if (f) localStorage.setItem(FOCUS_KEY, JSON.stringify(f)); else localStorage.removeItem(FOCUS_KEY); } catch (_) { /* privat */ } };
const fmtMin = (m) => (m >= 60 ? `${Math.floor(m / 60)} h${m % 60 ? ' ' + (m % 60) + ' min' : ''}` : `${m} min`);
let focusTick = null;
const focusLeft = (f) => (typeof f.paused === 'number' ? f.paused : Math.max(0, f.endAt - Date.now()));
async function startFocus(t, minutes) {
  if (readFocus()) await finishFocus(false);
  writeFocus({ todoId: t.id, title: t.title, minutes, startedAt: new Date().toISOString(), endAt: Date.now() + minutes * 60000, paused: null });
  if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission().catch(() => {});
  renderFocus(); toast(`Fokus: ${minutes} min`, 'ok');
}
function renderFocus() {
  clearInterval(focusTick); focusTick = null;
  const f = state.user ? readFocus() : null;
  let bar = $('#focusbar');
  if (!f) { if (bar) bar.remove(); return; }
  if (!bar) { bar = h('div', { class: 'focusbar glass', id: 'focusbar', role: 'timer', 'aria-label': 'Fokus-Timer' }); document.body.appendChild(bar); }
  const paused = typeof f.paused === 'number';
  const time = h('strong', { class: 'focus-time' });
  const draw = () => {
    const ms = focusLeft(f);
    time.textContent = `${Math.floor(ms / 60000)}:${pad(Math.floor(ms / 1000) % 60)}`;
    if (ms <= 0 && !paused) finishFocus(true);
  };
  clear(bar).append(icon('timer'),
    h('button', { class: 'grow focus-title', type: 'button', title: 'Aufgabe öffnen', onclick: () => { if (!isTaskRoute(state.route) || state.route === 'done') go('all'); setTimeout(() => select(f.todoId), 60); } }, f.title),
    time,
    h('button', { class: 'icon-btn', 'aria-label': paused ? 'Weiter' : 'Pause', onclick: () => { if (paused) { f.endAt = Date.now() + f.paused; f.paused = null; } else f.paused = focusLeft(f); writeFocus(f); renderFocus(); } }, icon(paused ? 'play' : 'pause')),
    h('button', { class: 'icon-btn', 'aria-label': 'Beenden und Zeit erfassen', title: 'Beenden', onclick: () => finishFocus(false) }, icon('stop')));
  draw();
  if (!paused) focusTick = setInterval(draw, 1000);
}
async function finishFocus(completed) {
  const f = readFocus(); if (!f) return;
  writeFocus(null); renderFocus();
  const spent = Math.min(600, completed ? f.minutes : Math.round((f.minutes * 60000 - focusLeft(f)) / 60000));
  if (spent >= 1) {
    try {
      const u = await api(`/todos/${f.todoId}/time`, { method: 'POST', body: { minutes: spent, started_at: f.startedAt } });
      const t = state.todos.find((x) => x.id === f.todoId); if (t) Object.assign(t, u);
    } catch (_) { /* Aufgabe gelöscht o. ä. */ }
  }
  if (completed) {
    toast(`Fokus-Zeit vorbei: ${f.title}`, 'ok');
    try {
      if ('Notification' in window && Notification.permission === 'granted') {
        const reg = navigator.serviceWorker && navigator.serviceWorker.controller ? await navigator.serviceWorker.ready : null;
        if (reg) reg.showNotification('Fokus-Zeit vorbei', { body: f.title, tag: 'focus' }); else new Notification('Fokus-Zeit vorbei', { body: f.title });
      }
    } catch (_) { /* nicht unterstützt */ }
  } else if (spent >= 1) toast(`${fmtMin(spent)} erfasst`, 'ok');
}

// ------------------------------------------------------------------ Statistik
function barChart(values, labels, { fmt = String, highlight = -1, aria = '' } = {}) {
  const max = Math.max(1, ...values);
  const top = values.indexOf(Math.max(...values));
  const chart = h('div', { class: 'bars', role: 'img', 'aria-label': aria });
  values.forEach((v, i) => {
    const tip = `${labels[i]}: ${fmt(v)}`;
    const bar = h('div', { class: 'bar' + (i === highlight ? ' hi' : ''), title: tip });
    bar.style.height = (v ? Math.max(3, Math.round((100 * v) / max)) : 0) + '%';
    const showVal = v && (i === highlight || i === top);
    chart.appendChild(h('div', { class: 'bar-col', tabindex: 0, 'aria-label': tip, 'data-tip': tip },
      h('div', { class: 'bar-track' }, showVal ? h('span', { class: 'bar-val' }, fmt(v)) : null, bar), h('span', { class: 'bar-label' }, labels[i])));
  });
  return chart;
}
function dataTable(head, rows) {
  return h('details', { class: 'small' }, h('summary', { class: 'muted' }, 'Als Tabelle'),
    h('table', { class: 'data-table' }, h('thead', {}, h('tr', {}, head.map((x) => h('th', {}, x)))), h('tbody', {}, rows.map((r) => h('tr', {}, r.map((c) => h('td', {}, c)))))));
}
function viewStats(view) {
  view.appendChild(h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, 'Statistik'), h('div', { class: 'muted small' }, 'Deine letzten 8 Wochen'))));
  const box = h('div', { class: 'col' }); view.appendChild(box);
  box.appendChild(h('div', { class: 'glass card row' }, h('div', { class: 'spinner' }), h('span', { class: 'muted' }, 'Wird berechnet …')));
  guard(async () => {
    const s = await api('/stats'); clear(box);
    const diff = s.week_done - s.last_week_done;
    const tile = (label, value, sub, cls) => h('div', { class: 'glass tile' }, h('div', { class: 'small muted' }, label), h('div', { class: 'tile-val' }, value), h('div', { class: 'small ' + (cls || 'muted') }, sub));
    box.appendChild(h('div', { class: 'tiles' },
      tile('Diese Woche erledigt', s.week_done, diff ? `${diff > 0 ? '+' : '−'}${Math.abs(diff)} zur Vorwoche` : 'wie in der Vorwoche'),
      tile('Serie', s.streak, s.streak === 1 ? 'Tag mit Erledigtem' : 'Tage in Folge'),
      tile('Fokus diese Woche', s.week_focus_min ? fmtMin(s.week_focus_min) : '–', s.week_focus_min ? 'mit dem Fokus-Timer' : 'Timer in den Aufgaben-Details'),
      tile('Offen', s.open, s.overdue ? `${s.overdue} überfällig` : 'nichts überfällig', s.overdue ? 'danger-text' : 'muted')));
    const wl = s.weeks.map((w) => { const d = new Date(w.start + 'T00:00:00'); return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.`; });
    const last = s.weeks.length - 1;
    box.appendChild(h('div', { class: 'glass card col' }, h('div', { class: 'row' }, h('h3', { class: 'grow' }, 'Erledigt pro Woche'), h('span', { class: 'small muted' }, 'Woche ab')),
      barChart(s.weeks.map((w) => w.done), wl, { highlight: last, aria: 'Erledigte Aufgaben pro Woche, letzte 8 Wochen', fmt: (v) => String(v) }),
      dataTable(['Woche ab', 'Erledigt', 'Fokus'], s.weeks.map((w, i) => [wl[i], String(w.done), fmtMin(w.focus_min)]))));
    if (s.weeks.some((w) => w.focus_min)) {
      box.appendChild(h('div', { class: 'glass card col' }, h('h3', {}, 'Fokuszeit pro Woche'),
        barChart(s.weeks.map((w) => w.focus_min), wl, { highlight: last, aria: 'Fokuszeit pro Woche', fmt: (v) => fmtMin(v) })));
    }
    const wd = [1, 2, 3, 4, 5, 6, 0].map((_, i) => s.weekday[i]);
    box.appendChild(h('div', { class: 'glass card col' }, h('h3', {}, 'Nach Wochentag'),
      barChart(wd, ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'], { aria: 'Erledigte Aufgaben nach Wochentag', fmt: (v) => String(v) })));
    if (s.top_tags.length) {
      const max = Math.max(...s.top_tags.map((t) => t.count));
      box.appendChild(h('div', { class: 'glass card col' }, h('h3', {}, 'Häufigste Tags (erledigt)'),
        h('div', { class: 'col', style: 'gap:8px' }, s.top_tags.map((t) => { const b = h('i'); b.style.width = Math.round((100 * t.count) / max) + '%';
          return h('button', { type: 'button', class: 'hbar', onclick: () => go('tag/' + encodeURIComponent(t.name)) }, h('span', { class: 'hbar-name' }, '#' + t.name), h('span', { class: 'hbar-track' }, b), h('span', { class: 'hbar-val' }, t.count)); }))));
    }
    if (s.longest_overdue.length) {
      box.appendChild(h('div', { class: 'glass card col' }, h('h3', {}, 'Dauerbrenner'), h('div', { class: 'small muted' }, 'Am längsten überfällig – erledigen, verschieben oder loslassen.'),
        h('div', { class: 'col', style: 'gap:2px' }, s.longest_overdue.map((t) => h('button', { type: 'button', class: 'pick-row', onclick: () => { go('all'); setTimeout(() => select(t.id), 60); } },
          h('span', { class: 'grow' }, t.title), h('span', { class: 'chip danger' }, icon('clock'), fmtDue(t.due_at)))))));
    }
    if (s.avg_days_to_done !== null) box.appendChild(h('div', { class: 'small muted', style: 'text-align:center' }, `Im Schnitt nach ${String(s.avg_days_to_done).replace('.', ',')} Tagen erledigt (letzte 30 Tage)`));
    const sw = h('button', { class: 'switch' + (s.review_enabled ? ' on' : ''), role: 'switch', 'aria-checked': String(s.review_enabled), 'aria-label': 'Wochenrückblick' });
    sw.addEventListener('click', guard(async () => { const r = await api('/stats/review', { method: 'PUT', body: { enabled: !sw.classList.contains('on') } }); sw.classList.toggle('on', r.enabled); sw.setAttribute('aria-checked', String(r.enabled)); toast(r.enabled ? 'Wochenrückblick sonntags um 18 Uhr' : 'Wochenrückblick aus', 'ok'); }));
    box.appendChild(h('div', { class: 'glass card col' }, h('div', { class: 'row' }, h('h3', { class: 'grow' }, 'Wochenrückblick'), sw),
      h('div', { class: 'small muted' }, 'Jeden Sonntag um 18 Uhr eine Benachrichtigung. So sähe sie gerade aus:'),
      h('div', { class: 'preview-note' }, h('strong', {}, s.review_preview.title), h('div', { class: 'small muted' }, s.review_preview.body))));
  })();
}

// ------------------------------------------------------------------ Zusammenarbeit in den Details
const HIST = {
  created: () => 'hat die Aufgabe angelegt', notes: () => 'Notizen geändert', recurrence: () => 'Wiederholung geändert',
  title: (d) => `Titel: „${d.from}“ → „${d.to}“`, due_at: (d) => (d.to ? 'Fällig: ' + fmtDue(d.to) : 'Fälligkeit entfernt'),
  done: (d) => (d.to ? 'erledigt' : 'wieder geöffnet'), priority: (d) => 'Priorität: ' + ['Keine', 'Niedrig', 'Mittel', 'Hoch'][d.to],
  list_id: (d) => { const l = state.lists.find((x) => x.id === d.to); return 'Liste: ' + (l ? l.name : d.to ? 'andere Liste' : 'keine'); },
  assignee: (d) => (d.to ? 'zugewiesen an ' + d.to : 'Zuweisung entfernt'), stage: (d) => (d.to === 'doing' ? 'in Arbeit genommen' : 'zurück auf offen'),
  dep_added: (d) => `wartet jetzt auf „${d.title}“`, dep_removed: (d) => `wartet nicht mehr auf „${d.title}“`,
};
function mentionText(body) {
  return body.split(/(@[A-Za-z0-9_.-]{3,32})/).map((part) => (part.startsWith('@') ? h('span', { class: 'mention' }, part) : part));
}
function collabSection(t, save) {
  const list = state.lists.find((l) => l.id === t.list_id);
  const shared = list && (list.mine === false || (list.members || []).length);
  // Status (Board) und Zuständigkeit
  const stageSeg = h('div', { class: 'seg', role: 'group', 'aria-label': 'Status' });
  const drawStage = () => { clear(stageSeg); [['todo', 'Offen'], ['doing', 'In Arbeit']].forEach(([k, l]) => stageSeg.appendChild(h('button', { type: 'button', class: (t.stage || 'todo') === k ? 'on' : '', onclick: async () => { await save({ stage: k }); drawStage(); } }, l))); };
  drawStage();
  const names = shared ? [...new Set([list.owner, ...(list.members || [])])].sort((a, b) => a.localeCompare(b)) : [state.user.username];
  const current = t.assignee_id ? personName(t.assignee_id) : '';
  const assignee = h('select', { 'aria-label': 'Zuständig', onchange: () => save({ assignee: assignee.value }) },
    h('option', { value: '' }, 'Niemand'), names.map((n) => h('option', { value: n, selected: n === current }, n === state.user.username ? n + ' (ich)' : n)));
  const top = h('div', { class: 'search-grid' }, !t.done ? h('div', { class: 'field' }, 'Status', stageSeg) : null, h('label', { class: 'field' }, 'Zuständig', assignee));
  // Abhängigkeiten
  const depBox = h('div', { class: 'col', style: 'gap:6px' });
  const drawDeps = () => {
    clear(depBox);
    (t.blocked_by || []).forEach((id) => { const b = byId(id);
      depBox.appendChild(h('div', { class: 'row small' }, icon(b && b.done ? 'check' : 'lock'), h('button', { type: 'button', class: 'grow link-btn', style: 'text-align:left;font-size:.875rem', onclick: () => select(id) }, b ? b.title : 'Aufgabe #' + id),
        h('button', { class: 'icon-btn', style: 'width:28px;height:28px', 'aria-label': 'Abhängigkeit entfernen', onclick: guard(async () => { Object.assign(t, await api(`/todos/${t.id}/deps/${id}`, { method: 'DELETE' })); drawDeps(); renderTodos(); }) }, icon('x')))); });
    const options = state.todos.filter((x) => !x.parent_id && !x.done && x.id !== t.id && !(t.blocked_by || []).includes(x.id)).sort((a, b) => a.title.localeCompare(b.title)).slice(0, 300);
    if (options.length) {
      const sel = h('select', { 'aria-label': 'Wartet auf', onchange: guard(async () => { if (!sel.value) return; Object.assign(t, await api(`/todos/${t.id}/deps`, { method: 'POST', body: { blocked_by: Number(sel.value) } })); drawDeps(); renderTodos(); }) },
        h('option', { value: '' }, '+ Wartet auf …'), options.map((x) => h('option', { value: x.id }, x.title.slice(0, 80))));
      depBox.appendChild(sel);
    }
  };
  drawDeps();
  // Kommentare
  const cBox = h('div', { class: 'col', style: 'gap:6px' });
  const cInput = h('textarea', { maxlength: 2000, placeholder: shared ? 'Kommentar … (@name erwähnt jemanden)' : 'Kommentar oder Notiz zum Verlauf …', style: 'min-height:64px', 'aria-label': 'Kommentar' });
  const drawComments = guard(async () => {
    const { comments } = await api(`/todos/${t.id}/comments`); clear(cBox);
    comments.forEach((c) => cBox.appendChild(h('div', { class: 'comment' }, h('div', { class: 'row small muted' }, h('strong', { class: 'grow', style: 'color:var(--text)' }, c.author), fmtTs(c.created_at),
      c.mine ? h('button', { class: 'icon-btn', style: 'width:24px;height:24px', 'aria-label': 'Kommentar löschen', onclick: guard(async () => { await api('/comments/' + c.id, { method: 'DELETE' }); drawComments(); }) }, icon('x')) : null),
      h('div', { class: 'comment-body' }, mentionText(c.body)))));
  });
  drawComments();
  const cForm = h('form', { class: 'col', style: 'gap:6px', onsubmit: guard(async (e) => {
    e.preventDefault(); const body = cInput.value.trim(); if (!body) return;
    await api(`/todos/${t.id}/comments`, { method: 'POST', body: { body } }); cInput.value = ''; drawComments();
  }) }, cInput, h('div', { class: 'row' }, h('div', { class: 'grow' }), h('button', { class: 'btn sm', type: 'submit' }, icon('send'), 'Senden')));
  cInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) cForm.requestSubmit(); });
  // Verlauf
  const hBox = h('div', { class: 'history' });
  const hist = h('details', { class: 'small', ontoggle: guard(async () => {
    if (!hist.open) return;
    const { history } = await api(`/todos/${t.id}/history`); clear(hBox);
    history.forEach((x) => hBox.appendChild(h('div', {}, h('b', {}, x.actor), ' ' + (HIST[x.action] ? HIST[x.action](x.detail || {}) : x.action), h('span', { class: 'muted' }, ' · ' + fmtTs(x.at)))));
  }) }, h('summary', { class: 'muted' }, 'Verlauf'), hBox);
  const bottom = h('div', { class: 'col', style: 'gap:14px' },
    h('div', { class: 'field' }, 'Wartet auf', depBox),
    h('div', { class: 'field' }, 'Kommentare', cBox, cForm), hist);
  return { top, bottom };
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
  view.appendChild(h('div', { class: 'row' }, h('h2', { class: 'grow' }, 'Regeln'), btn('Regel', 'sm', () => ruleSheet(), 'plus')));
  view.appendChild(h('div', { id: 'rules', class: 'col' }));
  view.appendChild(sendForm());
  view.appendChild(h('div', { class: 'row' }, h('h2', { class: 'grow' }, 'Log'), h('select', { id: 'log-filter', style: 'width:auto', 'aria-label': 'Filter', onchange: guard(loadMessages) }, h('option', { value: '' }, 'Alle'))));
  view.appendChild(h('div', { id: 'log', class: 'col' }));
  refreshAgents().then(loadMessages); refreshRules();
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

# Rückfrage an dich (Antwort per Benachrichtigung oder Web, Ergebnis via /inbox/stream "result")
curl -X POST ${o}/api/agent-bus/agent/messages -H "X-Agent-Key: tdo_…" \\
  -H "Content-Type: application/json" -d '{"to":"todo","kind":"task","task_type":"ask",
  "payload":{"question":"Produktion deployen?","options":["Ja","Nein"]}}'

# Task-Typen: todo.create, todo.list, todo.complete, device.notify, ask`;
}
const refreshAgents = guard(async () => {
  state.agents = (await api('/agent-bus/agents')).agents;
  const box = $('#agents'); if (!box) return; clear(box);
  if (!state.agents.length) box.appendChild(h('div', { class: 'empty glass' }, icon('bus'), h('div', {}, 'Noch keine Agents. Lege einen an, um ein Projekt anzubinden.')));
  state.agents.forEach((a) => box.appendChild(h('div', { class: 'glass card col', style: 'gap:10px' },
    h('div', { class: 'row' }, h('div', { class: 'avatar' }, a.name[0]), h('div', { class: 'grow' }, h('h3', {}, a.name), h('div', { class: 'muted small' }, a.description || 'Keine Beschreibung')),
      h('button', { class: 'icon-btn', 'aria-label': 'Webhook', title: a.webhook ? 'Webhook-URL erneuern' : 'Webhook-URL erzeugen', onclick: () => webhookSheet(a) }, icon('link')),
      h('button', { class: 'icon-btn', 'aria-label': 'Neuen Key erzeugen', title: 'Key rotieren', onclick: guard(async () => { if (!confirm('Neuen Key erzeugen? Der alte wird sofort ungültig.')) return; keySheet(a.name, (await api(`/agent-bus/agents/${a.id}/rotate`, { method: 'POST' })).api_key); }) }, icon('key')),
      h('button', { class: 'icon-btn', 'aria-label': 'Agent löschen', onclick: guard(async () => { if (!confirm(`Agent „${a.name}“ löschen?`)) return; await api('/agent-bus/agents/' + a.id, { method: 'DELETE' }); refreshAgents(); }) }, icon('trash'))),
    h('div', { class: 'row wrap' }, a.scopes.map((s) => h('span', { class: 'chip' }, s)), h('span', { class: 'chip' }, a.key_prefix + '…'), a.webhook ? h('span', { class: 'chip dotted ok' }, 'Webhook aktiv') : null, h('span', { class: 'chip' }, a.last_seen_at ? 'zuletzt ' + fmtTs(a.last_seen_at) : 'noch nie verbunden')))));
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
function webhookSheet(a) {
  const close = sheet(h('div', { class: 'col' }, h('h2', {}, 'Webhook für „' + a.name + '“'),
    h('p', { class: 'muted small' }, 'Dienste wie GitHub, Uptime Kuma, Home Assistant oder Grafana posten an diese URL – ganz ohne Agent-Key. Jede Meldung landet im Log und kann Regeln auslösen. Die URL ist das Geheimnis: Sie wird nur jetzt angezeigt.'),
    h('div', { class: 'row wrap' },
      btn(a.webhook ? 'Neue URL erzeugen (alte wird ungültig)' : 'URL erzeugen', 'primary', guard(async () => {
        const { url } = await api(`/agent-bus/agents/${a.id}/webhook`, { method: 'POST' });
        close(); keySheet(a.name + ' (Webhook)', url); refreshAgents();
      }), 'link'),
      a.webhook ? btn('Webhook ausschalten', 'danger', guard(async () => { await api(`/agent-bus/agents/${a.id}/webhook`, { method: 'DELETE' }); close(); refreshAgents(); })) : null,
      btn('Abbrechen', '', () => close())),
    h('pre', { class: 'code' }, `# Beispiel
curl -X POST "<Webhook-URL>" -H "Content-Type: application/json" -d '{"text":"Backup fehlgeschlagen"}'
# Titel auch per Query: <Webhook-URL>?title=Deploy%20fertig`)));
}

const refreshRules = guard(async () => {
  const box = $('#rules'); if (!box) return;
  const { rules } = await api('/rules'); clear(box);
  if (!rules.length) { box.appendChild(h('div', { class: 'muted small' }, 'Keine Regeln. Beispiel: „Wenn kuma ‚down‘ meldet → Aufgabe mit hoher Priorität + Nachricht aufs Handy“.')); return; }
  rules.forEach((r) => {
    const sw = h('button', { class: 'switch' + (r.enabled ? ' on' : ''), role: 'switch', 'aria-checked': String(r.enabled), 'aria-label': 'Regel aktiv',
      onclick: guard(async () => { await api('/rules/' + r.id, { method: 'PATCH', body: { enabled: !r.enabled } }); refreshRules(); }) });
    const m = r.match, a = r.action;
    const cond = [m.agent ? 'von ' + m.agent : 'von jedem Agent', m.kind !== 'any' ? (m.kind === 'text' ? 'Text' : 'Task') : null,
      m.task_type ? 'Typ ' + m.task_type : null, m.contains ? `enthält „${m.contains}“` : null].filter(Boolean).join(', ');
    const act = a.type === 'create_todo' ? `Aufgabe „${a.title}“` + (a.priority ? ` (Priorität ${['', 'Niedrig', 'Mittel', 'Hoch'][a.priority]})` : '')
      : `Nachricht an ${a.device || 'alle Geräte'}${a.urgent ? ' (dringend)' : ''}`;
    box.appendChild(h('div', { class: 'glass card row', style: 'align-items:flex-start' }, h('span', { class: 'muted', style: 'padding-top:2px' }, icon('bolt')),
      h('div', { class: 'grow col', style: 'gap:4px' }, h('strong', {}, r.name), h('div', { class: 'small muted' }, 'Wenn ' + cond), h('div', { class: 'small' }, '→ ' + act),
        h('div', { class: 'small muted' }, r.fire_count ? `${r.fire_count}× ausgelöst, zuletzt ${fmtTs(r.last_fired_at)}` : 'noch nicht ausgelöst')),
      sw, h('button', { class: 'icon-btn', 'aria-label': 'Regel löschen', onclick: guard(async () => { if (!confirm(`Regel „${r.name}“ löschen?`)) return; await api('/rules/' + r.id, { method: 'DELETE' }); refreshRules(); }) }, icon('trash'))));
  });
});

function ruleSheet() {
  const name = h('input', { type: 'text', maxlength: 60, placeholder: 'z. B. Server-Ausfall', required: true });
  const agentSel = h('select', { 'aria-label': 'Agent' }, h('option', { value: '' }, 'Jeder Agent'), state.agents.map((a) => h('option', { value: a.name }, a.name)));
  const kind = h('select', { 'aria-label': 'Art' }, [['any', 'Text oder Task'], ['text', 'Nur Text'], ['task', 'Nur Task']].map(([v, l]) => h('option', { value: v }, l)));
  const contains = h('input', { type: 'text', maxlength: 200, placeholder: 'enthält … (z. B. down, error)' });
  const taskType = h('input', { type: 'text', maxlength: 64, placeholder: 'Task-Typ (optional)' });
  const type = h('select', { 'aria-label': 'Aktion' }, h('option', { value: 'create_todo' }, 'Aufgabe anlegen'), h('option', { value: 'notify' }, 'Nachricht an Gerät(e)'));
  const title = h('input', { type: 'text', maxlength: 300, value: '{agent}: {content}' });
  const body = h('input', { type: 'text', maxlength: 500, placeholder: 'Text/Notiz (optional), Platzhalter möglich' });
  let prio = 2;
  const prioBox = prioSeg(prio, (p) => { prio = p; });
  const tags = h('input', { type: 'text', placeholder: 'Tags, z. B. ops' });
  const devSel = h('select', { 'aria-label': 'Gerät' }, h('option', { value: '' }, 'Alle Geräte'));
  api('/devices').then(({ devices }) => devices.forEach((d) => devSel.appendChild(h('option', { value: d.name }, d.name)))).catch(() => {});
  const urgent = h('input', { type: 'checkbox' });
  const todoBox = h('div', { class: 'col' }, h('div', { class: 'field' }, 'Priorität', prioBox), h('label', { class: 'field' }, 'Tags', tags));
  const notifyBox = h('div', { class: 'col hidden' }, h('label', { class: 'field' }, 'Gerät', devSel), h('label', { class: 'row small muted' }, urgent, 'Dringend (auch in der Ruhezeit)'));
  type.addEventListener('change', () => { todoBox.classList.toggle('hidden', type.value !== 'create_todo'); notifyBox.classList.toggle('hidden', type.value !== 'notify'); });
  const close = sheet(h('form', { class: 'col', onsubmit: guard(async (e) => {
    e.preventDefault();
    await api('/rules', { method: 'POST', body: { name: name.value.trim(),
      match: { agent: agentSel.value, kind: kind.value, contains: contains.value.trim(), task_type: taskType.value.trim() },
      action: { type: type.value, title: title.value.trim() || '{content}', body: body.value.trim(), priority: prio,
        tags: tags.value.split(/[,\s]+/).map((x) => x.replace(/^#/, '')).filter(Boolean), device: devSel.value, urgent: urgent.checked } } });
    close(); refreshRules(); toast('Regel gespeichert', 'ok');
  }) }, h('h2', {}, 'Neue Regel'), h('label', { class: 'field' }, 'Name', name),
  h('div', { class: 'field' }, 'Wenn …', h('div', { class: 'search-grid' }, agentSel, kind), contains, taskType),
  h('div', { class: 'field' }, '… dann', type), h('label', { class: 'field' }, 'Titel (Platzhalter: {agent} {content} {task_type} {payload.feld})', title),
  h('label', { class: 'field' }, 'Text', body), todoBox, notifyBox,
  h('div', { class: 'row' }, h('div', { class: 'grow' }), btn('Abbrechen', '', () => close()), h('button', { class: 'btn primary', type: 'submit' }, 'Speichern'))));
  name.focus();
}

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
      m.payload && m.task_type !== 'ask' ? h('pre', {}, JSON.stringify(m.payload, null, 2)) : null,
      m.task_type === 'ask' && m.payload && m.status !== 'pending' ? h('div', { class: 'small muted' }, 'Frage: ' + (m.payload.question || '')) : null,
      m.result ? h('pre', {}, '→ ' + JSON.stringify(m.result, null, 2)) : null,
      (m.rules_fired || []).length || (m.deliveries || []).length || m.delivered_at ? h('div', { class: 'row wrap', style: 'gap:6px' },
        (m.rules_fired || []).map((r) => h('span', { class: 'chip' }, icon('bolt'), r)),
        (m.deliveries || []).map((d) => h('span', { class: 'chip dotted ' + (d.delivered_at ? 'ok' : 'warn') }, d.device + (d.delivered_at ? ' · ' + fmtTs(d.delivered_at) : ' · ausstehend'))),
        m.delivered_at ? h('span', { class: 'chip dotted ok' }, 'abgeholt ' + fmtTs(m.delivered_at)) : null) : null,
      incoming && m.task_type === 'ask' && m.status === 'pending' ? answerBox(m) :
      incoming && m.kind === 'task' && ['pending', 'in_progress'].includes(m.status) ? h('div', { class: 'row' }, btn('Erledigt', 'sm', guard(async () => { await api(`/agent-bus/messages/${m.id}/ack`, { method: 'POST', body: { status: 'completed' } }); }), 'check'), btn('Ablehnen', 'sm danger', guard(async () => { await api(`/agent-bus/messages/${m.id}/ack`, { method: 'POST', body: { status: 'failed' } }); }))) : null));
  });
}

function answerBox(m) {
  const p = m.payload || {};
  const input = h('input', { type: 'text', maxlength: 500, placeholder: 'Antwort …' });
  const send = (text) => guard(async () => { if (!text.trim()) return; await api(`/agent-bus/messages/${m.id}/answer`, { method: 'POST', body: { text: text.trim() } }); toast('Antwort gesendet', 'ok'); })();
  return h('div', { class: 'col', style: 'gap:8px' }, p.question ? h('strong', {}, p.question) : null,
    (p.options || []).length ? h('div', { class: 'row wrap' }, p.options.slice(0, 3).map((o) => btn(String(o), 'sm', () => send(String(o))))) : null,
    h('form', { class: 'row', onsubmit: (e) => { e.preventDefault(); send(input.value); } }, input, h('button', { class: 'icon-btn', type: 'submit', 'aria-label': 'Antworten' }, icon('send'))));
}

// ------------------------------------------------------------------ Assistent
function viewAssistant(view) {
  const log = h('div', { class: 'chat', 'aria-live': 'polite' });
  const input = h('input', { type: 'text', placeholder: 'Frag den Assistenten …', maxlength: 4000, enterkeyhint: 'send' });
  const draw = () => { clear(log); if (!state.chat.length) log.appendChild(h('div', { class: 'empty' }, icon('bot'), h('div', {}, 'Ich kenne deine offenen Aufgaben und helfe beim Planen und Priorisieren.'))); state.chat.forEach((m) => { log.appendChild(h('div', { class: 'bubble ' + (m.role === 'user' ? 'me' : 'ai') }, m.content)); if ((m.actions || []).length) log.appendChild(actionPanel(m.actions, 'Vorgeschlagene Aktionen', () => { m.actions = []; })); }); $('#main').scrollTop = $('#main').scrollHeight; };
  const ask = guard(async (fn, userText) => {
    if (userText) state.chat.push({ role: 'user', content: userText });
    draw(); log.appendChild(h('div', { class: 'bubble ai' }, h('div', { class: 'spinner' })));
    try { const r = await fn(); state.chat.push({ role: 'assistant', content: r.reply || '…', actions: r.actions || [] }); } finally { draw(); }
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
  view.appendChild(h('div', { class: 'glass card col mobile-only' }, h('h3', {}, 'Bereiche'), h('div', { class: 'row wrap' },
    btn('Kalender', 'sm', () => go('calendar'), 'cal'), btn('Statistik', 'sm', () => go('stats'), 'chart'),
    btn('Vorlagen', 'sm', () => go('templates'), 'layers'), btn('Papierkorb', 'sm', () => go('trash'), 'trash'))));
  view.appendChild(h('div', { class: 'glass card col' }, h('h3', {}, 'Design'), tseg));
  // Ollama
  const model = h('select', { 'aria-label': 'Ollama-Modell' }, h('option', { value: state.settings.ollama_model }, state.settings.ollama_model));
  const modelHint = h('div', { class: 'small muted hidden' }, 'Ollama ist gerade nicht erreichbar – die Modellliste fehlt, KI-Funktionen melden sich mit einem Fehler.');
  api('/ai/models').then(({ models }) => { clear(model); const all = new Set([state.settings.ollama_model, ...models]); all.forEach((m) => model.appendChild(h('option', { value: m, selected: m === state.settings.ollama_model }, m))); }).catch(() => modelHint.classList.remove('hidden'));
  model.addEventListener('change', guard(async () => { state.settings = { ...state.settings, ...(await api('/settings', { method: 'PUT', body: { ollama_model: model.value } })) }; toast('Modell gespeichert', 'ok'); }));
  view.appendChild(h('div', { class: 'glass card col' }, h('h3', {}, 'KI-Modell (Ollama)'), model, modelHint));
  // Push
  view.appendChild(pushCard());
  const secBox = h('div', { class: 'glass card col' });
  view.appendChild(secBox); securityCard(secBox);
  view.appendChild(summaryCard());
  const icsBox = h('div', { class: 'glass card col' });
  view.appendChild(icsBox); icsCard(icsBox);
  const mailBox = h('div', { class: 'glass card col' });
  view.appendChild(mailBox); mailCard(mailBox);
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
        h('span', { class: 'chip dotted ' + (d.online ? 'ok' : '') }, d.online ? 'online' : 'offline'), d.pending ? h('span', { class: 'chip dotted warn' }, d.pending + ' offen') : null,
        d.quiet_start ? h('span', { class: 'chip' }, icon('moon'), `${d.quiet_start}–${d.quiet_end}`) : null),
      h('div', { class: 'muted small' }, [d.platform === 'android' ? 'Android' : 'Gerät', d.app_version ? 'v' + d.app_version : null, d.last_seen_at ? 'zuletzt ' + fmtTs(d.last_seen_at) : null].filter(Boolean).join(' · '))),
    h('button', { class: 'icon-btn', 'aria-label': 'Nachricht senden', title: 'Nachricht senden', onclick: () => deviceSheet(d) }, icon('send')),
    h('button', { class: 'icon-btn', 'aria-label': 'Ruhezeiten', title: 'Ruhezeiten', onclick: () => quietSheet(d, box) }, icon('moon')),
    h('button', { class: 'icon-btn', 'aria-label': 'Umbenennen', title: 'Umbenennen', onclick: guard(async () => { const n = prompt('Neuer Name:', d.name); if (!n || !n.trim()) return; await api('/devices/' + d.id, { method: 'PATCH', body: { name: n.trim() } }); refreshDevices(box); }) }, icon('more')),
    h('button', { class: 'icon-btn', 'aria-label': 'Gerät entfernen', title: 'Entfernen', onclick: guard(async () => { if (!confirm(`„${d.name}“ entfernen? Die App registriert sich beim nächsten Öffnen neu.`)) return; await api('/devices/' + d.id, { method: 'DELETE' }); refreshDevices(box); }) }, icon('trash')))));
  if (hasAndroid() && android.info) {
    const i = android.info;
    box.appendChild(h('div', { class: 'nav-sep' }));
    box.appendChild(h('div', { class: 'col', style: 'gap:8px' },
      h('div', { class: 'muted small' }, `Diese App (${i.name}): Benachrichtigungen ${i.notificationsAllowed ? 'erlaubt' : 'AUS'} · Hintergrundverbindung ${i.connected ? 'aktiv' : 'inaktiv'}`),
      h('div', { class: 'row wrap' },
        !i.notificationsAllowed ? btn('Benachrichtigungen erlauben', 'sm', () => nativeSend({ type: 'openNotificationSettings' }), 'bell') : null,
        !i.batteryUnrestricted ? btn('Akku-Optimierung ausschalten', 'sm', () => nativeSend({ type: 'openBatterySettings' })) : null,
        btn(i.appLock ? 'App-Sperre aus' : 'App-Sperre (Fingerabdruck/PIN)', 'sm', () => { nativeSend({ type: 'setAppLock', enabled: !i.appLock }); i.appLock = !i.appLock; refreshDevices(box); }, 'lock'),
        !i.locationAllowed ? btn('Standort-Erinnerungen erlauben', 'sm', () => nativeSend({ type: 'enableLocation' }), 'pin') : h('span', { class: 'chip dotted ok' }, 'Standort-Erinnerungen aktiv'))));
  }
});

function quietSheet(d, box) {
  const start = h('input', { type: 'time', value: d.quiet_start || '22:00', 'aria-label': 'Beginn' });
  const end = h('input', { type: 'time', value: d.quiet_end || '07:00', 'aria-label': 'Ende' });
  const saveQ = (qs, qe) => guard(async () => { await api('/devices/' + d.id, { method: 'PATCH', body: { quiet_start: qs, quiet_end: qe } }); close(); refreshDevices(box); toast(qs ? `Ruhezeit ${qs}–${qe}` : 'Ruhezeit aus', 'ok'); })();
  const close = sheet(h('form', { class: 'col', onsubmit: (e) => { e.preventDefault(); saveQ(start.value, end.value); } },
    h('h2', {}, 'Ruhezeiten: ' + d.name),
    h('p', { class: 'muted small' }, 'In dieser Zeit sammelt der Server Nachrichten für dieses Gerät und stellt sie danach zu. Dringende Nachrichten (z. B. Aufgaben mit Priorität „Hoch“) kommen trotzdem sofort.'),
    h('div', { class: 'search-grid' }, h('label', { class: 'field' }, 'Von', start), h('label', { class: 'field' }, 'Bis', end)),
    h('div', { class: 'row' }, d.quiet_start ? btn('Ruhezeit aus', 'sm danger', () => saveQ(null, null)) : null, h('div', { class: 'grow' }), btn('Abbrechen', '', () => close()), h('button', { class: 'btn primary', type: 'submit' }, 'Speichern'))));
}

function deviceSheet(device) {
  const title = h('input', { type: 'text', maxlength: 80, placeholder: 'Titel', required: true });
  const body = h('textarea', { maxlength: 500, placeholder: 'Nachricht (optional)', style: 'min-height:80px' });
  const urgent = h('input', { type: 'checkbox' });
  const close = sheet(h('form', { class: 'col', onsubmit: guard(async (e) => {
    e.preventDefault();
    const r = await api('/devices/send', { method: 'POST', body: { device_id: device ? device.id : null, title: title.value.trim(), body: body.value.trim(), urgent: urgent.checked } });
    close(); toast(`An ${r.sent} Gerät${r.sent === 1 ? '' : 'e'} gesendet (${r.online} online${r.held ? ', ' + r.held + ' in Ruhezeit' : ''})`, 'ok');
    const box = $('#devices-card'); if (box) refreshDevices(box);
  }) }, h('h2', {}, device ? 'Nachricht an ' + device.name : 'Nachricht an alle Geräte'),
  h('label', { class: 'field' }, 'Titel', title), h('label', { class: 'field' }, 'Nachricht', body),
  h('label', { class: 'row small muted' }, urgent, 'Dringend – auch während der Ruhezeit zustellen'),
  h('div', { class: 'row' }, h('div', { class: 'grow' }), btn('Abbrechen', '', () => close()), h('button', { class: 'btn primary', type: 'submit' }, icon('send'), 'Senden'))));
  title.focus();
}

const securityCard = guard(async (box) => {
  const [tf, pks, ses] = await Promise.all([api('/auth/2fa'), api('/auth/passkeys'), api('/auth/sessions')]);
  clear(box);
  box.appendChild(h('h3', {}, 'Sicherheit'));
  // 2FA
  const tfBox = h('div', { class: 'col', style: 'gap:8px' });
  const showCodes = (codes) => sheet(h('div', { class: 'col' }, h('h2', {}, 'Wiederherstellungscodes'),
    h('p', { class: 'muted small' }, 'Jeder Code funktioniert genau einmal, falls du dein Handy verlierst. Jetzt sicher aufbewahren – sie werden nicht erneut angezeigt.'),
    h('div', { class: 'key-box codes' }, codes.join('\n'))));
  if (tf.enabled) {
    const code = h('input', { type: 'text', inputmode: 'numeric', placeholder: 'aktueller Code', maxlength: 40, style: 'max-width:180px' });
    tfBox.append(h('div', { class: 'row' }, h('span', { class: 'chip dotted ok' }, '2FA aktiv'), h('span', { class: 'small muted' }, `${tf.recovery_left} Wiederherstellungscodes übrig`)),
      h('div', { class: 'row wrap' }, code,
        btn('Neue Wiederherstellungscodes', 'sm', guard(async () => { const r = await api('/auth/2fa/recovery', { method: 'POST', body: { code: code.value } }); showCodes(r.recovery_codes); securityCard(box); })),
        btn('2FA ausschalten', 'sm danger', guard(async () => { if (!confirm('2FA wirklich ausschalten?')) return; await api('/auth/2fa/disable', { method: 'POST', body: { code: code.value } }); toast('2FA ausgeschaltet'); securityCard(box); }))));
  } else {
    tfBox.append(h('div', { class: 'row' }, h('span', { class: 'small muted grow' }, 'Zwei-Faktor-Anmeldung mit einer Authenticator-App (z. B. Aegis, 2FAS, Google Authenticator).'),
      btn('2FA einrichten', 'sm', guard(async () => {
        const s = await api('/auth/2fa/setup', { method: 'POST' });
        const code = h('input', { type: 'text', inputmode: 'numeric', autocomplete: 'one-time-code', maxlength: 6, placeholder: '123456' });
        const close = sheet(h('form', { class: 'col', onsubmit: guard(async (e) => {
          e.preventDefault();
          const r = await api('/auth/2fa/enable', { method: 'POST', body: { code: code.value } });
          close(); showCodes(r.recovery_codes); securityCard(box); toast('2FA aktiviert – andere Geräte wurden abgemeldet.', 'ok');
        }) }, h('h2', {}, '2FA einrichten'), h('p', { class: 'muted small' }, '1. QR-Code mit der Authenticator-App scannen (oder Schlüssel abtippen). 2. Den angezeigten Code eingeben.'),
        h('div', { class: 'qr' }, h('img', { src: s.qr_svg, alt: 'QR-Code für die Authenticator-App', width: 200, height: 200 })),
        h('div', { class: 'key-box' }, s.secret.replace(/(.{4})/g, '$1 ').trim()),
        h('label', { class: 'field' }, 'Code aus der App', code), h('button', { class: 'btn primary', type: 'submit' }, 'Aktivieren')));
        code.focus();
      }), 'lock')));
  }
  box.appendChild(h('div', { class: 'field' }, 'Zwei-Faktor-Anmeldung', tfBox));
  // Passkeys
  const pkBox = h('div', { class: 'col', style: 'gap:6px' });
  pks.passkeys.forEach((p) => pkBox.appendChild(h('div', { class: 'row' }, icon('key'), h('div', { class: 'grow' }, h('div', {}, p.name), h('div', { class: 'small muted' }, 'hinzugefügt ' + fmtTs(p.created_at) + (p.last_used_at ? ' · zuletzt ' + fmtTs(p.last_used_at) : ''))),
    h('button', { class: 'icon-btn', 'aria-label': 'Passkey löschen', onclick: guard(async () => { if (!confirm(`Passkey „${p.name}“ löschen?`)) return; await api('/auth/passkeys/' + p.id, { method: 'DELETE' }); securityCard(box); }) }, icon('trash')))));
  if (!pks.passkeys.length) pkBox.appendChild(h('div', { class: 'small muted' }, 'Anmelden per Fingerabdruck, Gesicht oder Geräte-PIN – ohne Passwort.'));
  if (window.PublicKeyCredential) pkBox.appendChild(h('div', {}, btn('Passkey hinzufügen', 'sm', guard(async () => { await passkeyRegister(); toast('Passkey gespeichert', 'ok'); securityCard(box); }), 'plus')));
  else pkBox.appendChild(h('div', { class: 'small muted' }, 'Dieser Browser unterstützt keine Passkeys.'));
  box.appendChild(h('div', { class: 'field' }, 'Passkeys', pkBox));
  // Sitzungen
  const sBox = h('div', { class: 'col', style: 'gap:6px' });
  const agent = (ua) => { ua = ua || ''; const os = /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Windows/.test(ua) ? 'Windows' : /Mac OS/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : 'Gerät';
    const br = /TodoAndroid/.test(ua) ? 'Todo-App' : /Edg\//.test(ua) ? 'Edge' : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : 'Browser'; return `${br} · ${os}`; };
  ses.sessions.forEach((x) => sBox.appendChild(h('div', { class: 'row' }, h('div', { class: 'grow' }, h('div', {}, agent(x.user_agent), x.current ? h('span', { class: 'chip', style: 'margin-left:6px' }, 'dieses Gerät') : null),
    h('div', { class: 'small muted' }, [x.ip, x.last_seen_at ? 'aktiv ' + fmtTs(x.last_seen_at) : 'angemeldet ' + fmtTs(x.created_at)].filter(Boolean).join(' · '))),
    x.current ? null : btn('Abmelden', 'sm', guard(async () => { await api('/auth/sessions/' + x.id, { method: 'DELETE' }); securityCard(box); })))));
  if (ses.sessions.length > 1) sBox.appendChild(h('div', {}, btn('Alle anderen abmelden', 'sm danger', guard(async () => { await api('/auth/sessions/revoke-others', { method: 'POST' }); securityCard(box); toast('Andere Geräte abgemeldet', 'ok'); }))));
  box.appendChild(h('div', { class: 'field' }, 'Angemeldete Geräte', sBox));
  // Export
  box.appendChild(h('div', { class: 'field' }, 'Deine Daten', h('div', { class: 'row wrap' },
    h('a', { class: 'btn sm', href: '/api/export?format=json', download: '' }, 'Export (JSON, komplett)'), h('a', { class: 'btn sm', href: '/api/export?format=csv', download: '' }, 'Aufgaben als CSV'))));
});

const icsCard = guard(async (box) => {
  const { enabled } = await api('/calendar/feed');
  clear(box);
  box.appendChild(h('h3', {}, 'Kalender-Abo (ICS)'));
  box.appendChild(h('p', { class: 'muted small' }, 'Fällige Aufgaben als Termine in deinem Handy-, Thunderbird-, Outlook- oder Nextcloud-Kalender. Der Link ist geheim – wer ihn hat, sieht deine Termine.'));
  box.appendChild(h('div', { class: 'row wrap' },
    btn(enabled ? 'Neuen Link erzeugen' : 'Link erzeugen', 'sm', guard(async () => {
      if (enabled && !confirm('Neuer Link – der alte funktioniert dann nicht mehr. Weiter?')) return;
      const { url } = await api('/calendar/feed', { method: 'POST' }); keySheet('Kalender-Abo', url); icsCard(box);
    }), 'cal'),
    enabled ? btn('Abo abschalten', 'sm danger', guard(async () => { await api('/calendar/feed', { method: 'DELETE' }); icsCard(box); })) : null,
    enabled ? h('span', { class: 'chip dotted ok' }, 'aktiv') : null));
});

function summaryCard() {
  const cur = state.settings.summary_time;
  const time = h('input', { type: 'time', value: cur || '08:00', 'aria-label': 'Uhrzeit' });
  const sw = h('button', { class: 'switch' + (cur ? ' on' : ''), role: 'switch', 'aria-checked': String(!!cur), 'aria-label': 'Morgen-Zusammenfassung' });
  const save = guard(async (on) => {
    const r = await api('/ai/summary', { method: 'PUT', body: { time: on ? time.value : null } });
    state.settings.summary_time = r.time; sw.classList.toggle('on', !!r.time); sw.setAttribute('aria-checked', String(!!r.time));
    toast(r.time ? 'Zusammenfassung täglich um ' + r.time : 'Zusammenfassung aus', 'ok');
  });
  sw.addEventListener('click', () => save(!state.settings.summary_time));
  time.addEventListener('change', () => { if (state.settings.summary_time) save(true); });
  return h('div', { class: 'glass card col' }, h('div', { class: 'row' }, h('h3', { class: 'grow' }, 'Morgen-Zusammenfassung'), sw),
    h('div', { class: 'muted small' }, 'Jeden Tag eine Benachrichtigung mit deinen heute fälligen und überfälligen Aufgaben (Browser und Geräte).'),
    h('div', { class: 'row wrap' }, h('label', { class: 'field', style: 'flex:0 0 140px' }, 'Uhrzeit', time),
      btn('Vorschau', 'sm', guard(async () => { const p = await api('/ai/summary/preview', { method: 'POST' }); toast(p.title + (p.body ? ': ' + p.body : '')); }))));
}

const mailCard = guard(async (box) => {
  const cfg = await api('/mail');
  clear(box);
  const host = h('input', { type: 'text', value: cfg.host || '', placeholder: 'imap.example.com', maxlength: 200 });
  const port = h('select', { 'aria-label': 'Port' }, [[993, '993 (TLS)'], [143, '143 (STARTTLS)']].map(([v, l]) => h('option', { value: v, selected: (cfg.port || 993) === v }, l)));
  const user = h('input', { type: 'text', value: cfg.username || '', placeholder: 'todo@example.com', autocomplete: 'off', maxlength: 200 });
  const pw = h('input', { type: 'password', placeholder: cfg.configured ? '(unverändert)' : 'Passwort', autocomplete: 'new-password', maxlength: 500 });
  const folder = h('input', { type: 'text', value: cfg.folder || 'INBOX', maxlength: 100 });
  const senders = h('input', { type: 'text', value: (cfg.allowed_senders || []).join(', '), placeholder: 'du@example.com, kollege@example.com' });
  const enabled = h('input', { type: 'checkbox', checked: cfg.configured ? cfg.enabled : true });
  const status = cfg.configured ? h('div', { class: 'small ' + (cfg.last_error ? 'error' : 'muted') },
    cfg.last_error ? 'Fehler: ' + cfg.last_error : (cfg.last_check_at ? `Zuletzt geprüft ${fmtTs(cfg.last_check_at)} · ${cfg.imported} importiert` : 'Noch nicht geprüft')) : null;
  box.appendChild(h('h3', {}, 'Aufgaben per E-Mail'));
  box.appendChild(h('p', { class: 'muted small' }, 'Mails an ein eigenes Postfach werden zu Aufgaben: Betreff = Titel (#tags möglich), Text = Notizen. Nur erlaubte Absender werden angenommen. Am besten ein eigenes Postfach dafür anlegen.'));
  box.appendChild(h('form', { class: 'col', onsubmit: guard(async (e) => {
    e.preventDefault();
    await api('/mail', { method: 'PUT', body: { host: host.value.trim(), port: Number(port.value), username: user.value.trim(), password: pw.value || null,
      folder: folder.value.trim() || 'INBOX', allowed_senders: senders.value.split(/[,\s]+/).filter(Boolean), enabled: enabled.checked } });
    toast('Postfach gespeichert', 'ok'); mailCard(box);
  }) },
  h('div', { class: 'search-grid' }, h('label', { class: 'field' }, 'IMAP-Server', host), h('label', { class: 'field' }, 'Port', port)),
  h('div', { class: 'search-grid' }, h('label', { class: 'field' }, 'Benutzer', user), h('label', { class: 'field' }, 'Passwort', pw)),
  h('div', { class: 'search-grid' }, h('label', { class: 'field' }, 'Ordner', folder), h('label', { class: 'field' }, 'Erlaubte Absender', senders)),
  h('label', { class: 'row small muted' }, enabled, 'Aktiv (alle 2 Minuten prüfen)'), status,
  h('div', { class: 'row wrap' }, h('button', { class: 'btn primary', type: 'submit' }, 'Speichern'),
    cfg.configured ? btn('Verbindung testen', '', guard(async () => { const r = await api('/mail/test', { method: 'POST' }); toast(`Verbunden · ${r.unseen} ungelesen`, 'ok'); })) : null,
    cfg.configured ? btn('Entfernen', 'danger', guard(async () => { if (!confirm('Postfach-Verbindung entfernen?')) return; await api('/mail', { method: 'DELETE' }); mailCard(box); })) : null)));
});

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
  const iBox = h('div', { class: 'glass card col' });
  view.appendChild(iBox);
  const loadInvites = guard(async () => {
    const { invites } = await api('/admin/invites'); clear(iBox);
    iBox.appendChild(h('div', { class: 'row' }, h('h3', { class: 'grow' }, 'Einladungen'), btn('Einladen', 'sm', () => inviteSheet(loadInvites), 'mail')));
    iBox.appendChild(h('div', { class: 'small muted' }, 'Wer sich über einen Einladungslink registriert, ist sofort freigegeben – ohne Warten auf einen Admin.'));
    invites.slice(0, 10).forEach((i) => iBox.appendChild(h('div', { class: 'row small' },
      h('span', { class: 'chip dotted ' + (i.active ? 'ok' : '') }, i.active ? 'aktiv' : 'abgelaufen'),
      h('span', { class: 'grow' }, (i.note || 'Ohne Notiz') + ` · ${i.uses}/${i.max_uses} genutzt · bis ${fmtTs(i.expires_at)}`),
      h('button', { class: 'icon-btn', 'aria-label': 'Einladung löschen', onclick: guard(async () => { await api('/admin/invites/' + i.id, { method: 'DELETE' }); loadInvites(); }) }, icon('trash')))));
  });
  loadInvites();
  const bBox = h('div', { class: 'glass card col' });
  view.appendChild(bBox);
  const loadBackups = guard(async () => {
    const { backups, keep } = await api('/admin/backups'); clear(bBox);
    bBox.appendChild(h('div', { class: 'row' }, h('h3', { class: 'grow' }, 'Backups'), btn('Jetzt sichern', 'sm', guard(async () => { await api('/admin/backups', { method: 'POST' }); toast('Backup erstellt', 'ok'); loadBackups(); }))));
    bBox.appendChild(h('div', { class: 'small muted' }, `Täglich automatisch, die letzten ${keep} werden aufbewahrt (Volume /data/backups). Anhänge liegen unter /data/attachments – das ganze Volume sichern.`));
    backups.slice(0, 10).forEach((b) => bBox.appendChild(h('div', { class: 'row small' }, h('span', { class: 'grow' }, b.name), h('span', { class: 'muted' }, fmtSize(b.size)), h('a', { class: 'btn sm', href: '/api/admin/backups/' + b.name, download: '' }, 'Laden'))));
  });
  loadBackups();
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

function inviteSheet(onDone) {
  const note = h('input', { type: 'text', maxlength: 80, placeholder: 'Für wen? z. B. Familie, Anna' });
  const days = h('select', { 'aria-label': 'Gültig' }, [[1, '1 Tag'], [7, '7 Tage'], [14, '14 Tage'], [30, '30 Tage']].map(([v, l]) => h('option', { value: v, selected: v === 7 }, l)));
  const uses = h('select', { 'aria-label': 'Nutzungen' }, [[1, 'Einmalig'], [5, 'Bis zu 5 Personen'], [20, 'Bis zu 20 Personen']].map(([v, l]) => h('option', { value: v }, l)));
  const close = sheet(h('form', { class: 'col', onsubmit: guard(async (e) => {
    e.preventDefault();
    const r = await api('/admin/invites', { method: 'POST', body: { note: note.value.trim(), days: Number(days.value), max_uses: Number(uses.value) } });
    close(); keySheet('Einladungslink', r.url); onDone();
  }) }, h('h2', {}, 'Einladungslink'), h('label', { class: 'field' }, 'Notiz', note),
  h('div', { class: 'search-grid' }, h('label', { class: 'field' }, 'Gültig', days), h('label', { class: 'field' }, 'Nutzungen', uses)),
  h('div', { class: 'row' }, h('div', { class: 'grow' }), btn('Abbrechen', '', () => close()), h('button', { class: 'btn primary', type: 'submit' }, 'Link erzeugen'))));
  note.focus();
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
  if (e.key === 'Escape' && state.selecting) stopSelecting();
  else if (e.key === 'Escape' && state.selected) { state.selected = null; renderTodos(); renderDetail(); }
  if (typing) return;
  if (e.key === '/') { e.preventDefault(); go('search'); }
  if (e.key === 'n') { const i = $('#quick-input'); if (i) { e.preventDefault(); i.focus(); } }
});
boot();
