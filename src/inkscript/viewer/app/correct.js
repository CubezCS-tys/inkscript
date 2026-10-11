/* inkscript gold — the correction mode (experiment 34). The owner corrects the drafted gold pages: the line's
   crop of the scan, under it the draft text in a field, the readers' disagreements marked; tables as a grid,
   equations as LaTeX, articles by clicking regions. The server file is the truth: every page is loaded from it
   and saved back (whole) after each accepted line, every 20 s while there are changes, and on leaving. No library. */
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const norm = s => String(s ?? '').replace(/\s+/g, ' ').trim();
const LINE_KINDS = ['text', 'heading', 'title', 'footnote', 'caption', 'cell', 'equation', 'furniture', 'verse'];
const REGION_TYPES = ['text', 'heading', 'title', 'footnote', 'caption', 'table', 'equation', 'figure', 'furniture',
  'handwriting', 'decorative', 'verse'];
const LST = {todo: 'to do', ok: 'correct', edited: 'corrected', added: 'added', deleted: 'not text', unsure: 'unsure'};
const PST = {todo: 'to do', doing: 'started', done: 'done', skip: 'skipped', error: 'broken file'};
const MARKS = ['\u064E', '\u064F', '\u0650', '\u064B', '\u064C', '\u064D', '\u0651', '\u0652'];
const PALETTE = [...MARKS, 'ء', 'ا', 'أ', 'إ', 'آ', 'ٱ', 'ى', 'ي', 'ة', 'ه', 'ﷺ', '«', '»', '(', ')',
  '٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
const ART_COL = ['#D9480F', '#1971C2', '#2F9E44', '#9C36B5', '#E67700', '#0C8599', '#C2255C', '#5C940D', '#6741D9'];
const PREF_KEY = 'inkscript-gold';
const prefs = (() => { try { return JSON.parse(localStorage.getItem(PREF_KEY) || '{}'); } catch { return {}; } })();
function savePrefs() { try { localStorage.setItem(PREF_KEY, JSON.stringify(prefs)); } catch {} }

const S = {
  g: null, pid: null, mode: 'lines', pos: 0, entry: '', zoom: prefs.zoom || 1, numbers: false, draw: null,
  seq: 0, savedSeq: 0, timeDirty: false, saving: null, again: false, state: 'saved', lastInput: Date.now(),
  t: 0, e: 0, model: null, cell: 0, art: null, sel: null, clicks: null, pickTitle: false, modal: null,
  lastField: null, img: null, loading: false,
};

/* ------------------------------------------------------------------ small helpers */
function toast(msg, ms = 2600) {
  const t = $('#toast');
  t.textContent = msg; t.hidden = false;
  clearTimeout(toast.h); toast.h = setTimeout(() => { t.hidden = true; }, ms);
}
async function getJSON(url) {
  const r = await fetch(url, {cache: 'no-store'});
  const txt = await r.text();
  let v;
  try { v = JSON.parse(txt); } catch (e) {
    throw new Error(`${r.status}: the server's answer for ${url} is not JSON (${txt.slice(0, 120)})`);
  }
  if (!r.ok) throw new Error(`${r.status}: ${v.error || txt.slice(0, 200)}`);
  return v;
}
const imgURL = pid => 'img/' + encodeURIComponent(pid) + '.jpg';
const fmtH = s => s >= 3600 ? (s / 3600).toFixed(1) + ' h' : Math.round(s / 60) + ' min';
const disagrees = ln => !!((ln.disagree && ln.disagree.length) || (ln.flags || []).includes('gemini-differs'));
const flagged = ln => !!((ln.disagree && ln.disagree.length) || (ln.flags && ln.flags.length));
function lineById(id) { return S.g.lines.find(l => l.id === id); }
function curLine() { return S.g && S.g.order.length ? lineById(S.g.order[S.pos]) : null; }
function curItem() {
  if (!S.g) return null;
  if (S.mode === 'lines') return curLine();
  if (S.mode === 'tables') return (S.g.tables || [])[S.t] || null;
  if (S.mode === 'equations') return (S.g.equations || [])[S.e] || null;
  return null;
}
function changed() {
  S.seq++;
  if (S.g && S.g.status === 'todo') S.g.status = 'doing';
  setSaved('dirty');
  clearTimeout(changed.h); changed.h = setTimeout(() => { if (S.seq !== S.savedSeq) save(); }, 4000);
}
function lcsKeep(a, b) {          // a[i] kept (in a longest common subsequence with b)?
  const n = a.length, m = b.length, L = Array.from({length: n + 1}, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const keep = new Array(n).fill(false);
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { keep[i] = true; i++; j++; } else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
  }
  return keep;
}
const words = s => norm(s).split(' ').filter(Boolean);
function nextId(prefix, list, width) {
  let n = 0;
  for (const x of list) { const m = String(x.id || '').match(/(\d+)$/); if (m) n = Math.max(n, +m[1]); }
  return prefix + String(n + 1).padStart(width, '0');
}

/* ------------------------------------------------------------------ saving */
function setSaved(state, why) {
  S.state = state;
  const el = $('#saved');
  if (!S.g) { el.textContent = ''; el.className = 'saved'; return; }
  el.className = 'saved s-' + state;
  el.textContent = {saved: 'saved ✓', saving: 'saving…', dirty: 'changes…', error: 'not saved!'}[state];
  el.title = why || '';
}
function payload(g) { return JSON.stringify(g, (k, v) => k === 'words' ? undefined : v); }
function save() {
  if (!S.g) return Promise.resolve(true);
  if (S.saving) { S.again = true; return S.saving; }
  const g = S.g, seq = S.seq;
  S.timeDirty = false;
  setSaved('saving');
  S.saving = (async () => {
    try {
      const r = await fetch('api/page/' + encodeURIComponent(g.page_id),
        {method: 'POST', headers: {'Content-Type': 'application/json'}, body: payload(g)});
      let a;
      try { a = await r.json(); } catch { a = {error: 'bad answer from the server (' + r.status + ')'}; }
      if (r.ok && a.ok) {
        g.rev = a.rev;
        if (S.g === g) { S.savedSeq = Math.max(S.savedSeq, seq); setSaved(S.seq === S.savedSeq ? 'saved' : 'dirty'); }
        return true;
      }
      if (r.status === 409) { if (S.g === g) conflict(); return false; }
      if (S.g === g) setSaved('error', (a.error || r.status) + ': ' + (a.problems || []).join('; '));
      if (r.status === 400) toast('Not saved: ' + (a.problems || [a.error]).slice(0, 3).join('; '), 6000);
      return false;
    } catch (err) {
      if (S.g === g) setSaved('error', String(err.message || err));
      return false;
    } finally {
      S.saving = null;
      if (S.again && S.g === g) { S.again = false; save(); }
    }
  })();
  return S.saving;
}
async function flush() {            // save until nothing is left to save; false if the server refused
  for (let i = 0; i < 4 && S.g; i++) {
    if (S.saving) { await S.saving; continue; }
    if (S.seq === S.savedSeq && !S.timeDirty) return true;
    if (!await save()) return false;
  }
  return !S.g || (S.seq === S.savedSeq);
}
function conflict() {
  setSaved('error', 'changed in another tab');
  modal('This page was saved from another tab',
    'Another tab or window saved this page after you opened it here.',
    [['Load the saved page', 'main', () => openPage(S.pid, S.mode, true)],
     ['Keep this tab’s version', '', async () => {
       try { const cur = await getJSON('api/page/' + encodeURIComponent(S.pid)); S.g.rev = cur.rev || 0; save(); }
       catch (e) { toast(String(e.message || e), 6000); }
     }]]);
}
function leaveSave() {                    // the tab is closing: a keepalive request outlives the page
  if (!S.g || (S.seq === S.savedSeq && !S.timeDirty)) return;
  const body = payload(S.g), url = 'api/page/' + encodeURIComponent(S.g.page_id);
  try {
    fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body, keepalive: body.length < 60000});
  } catch {
    try { navigator.sendBeacon(url, new Blob([body], {type: 'application/json'})); } catch {}
  }
}
document.addEventListener('visibilitychange', () => { if (document.hidden && S.g) save(); });
window.addEventListener('pagehide', leaveSave);
window.addEventListener('pageshow', e => { if (e.persisted && S.g) openPage(S.pid, S.mode, true); });
window.addEventListener('beforeunload', e => { if (S.g && S.state === 'error') { e.preventDefault(); e.returnValue = ''; } });

/* ------------------------------------------------------------------ timing: active seconds only */
['keydown', 'pointerdown', 'input', 'wheel'].forEach(t => document.addEventListener(t, () => { S.lastInput = Date.now(); }, true));
setInterval(() => {
  if (!S.g || document.hidden || Date.now() - S.lastInput > 60000 || S.modal) return;
  S.g.seconds = Math.round((+S.g.seconds || 0) + 1);
  const it = curItem();
  if (it) it.seconds = Math.round((+it.seconds || 0) + 1);
  S.timeDirty = true;
  const c = $('#clock');
  if (c) c.textContent = '⏱ ' + fmtClock(S.g.seconds);
}, 1000);
setInterval(() => { if (S.g && !S.saving && (S.seq !== S.savedSeq || S.timeDirty)) save(); }, 20000);
const fmtClock = s => { s = Math.round(s || 0); const m = Math.floor(s / 60); return m + ':' + String(s % 60).padStart(2, '0'); };

/* ------------------------------------------------------------------ modal */
function modal(title, text, buttons) {   // buttons: [label, cls, fn]; Enter = the first, Esc = the last
  const box = $('#modalbox');
  box.innerHTML = `<h2>${esc(title)}</h2><p>${esc(text)}</p><div class="btns"></div>`;
  const row = $('.btns', box);
  const close = fn => () => { $('#modal').hidden = true; S.modal = null; fn && fn(); };
  const fns = buttons.map(([label, cls, fn]) => {
    const b = document.createElement('button');
    b.innerHTML = label; if (cls) b.className = cls;
    const f = close(fn); b.onclick = f; row.appendChild(b); return f;
  });
  $('#modal').hidden = false;
  S.modal = {yes: fns[0], no: fns[fns.length - 1]};
  row.firstChild && row.firstChild.focus();
}

/* ------------------------------------------------------------------ routing */
window.addEventListener('hashchange', route);
window.addEventListener('load', route);
let routing = Promise.resolve();
function route() { routing = routing.then(doRoute, doRoute); return routing; }
async function doRoute() {
  const m = location.hash.match(/^#\/p\/([^/]+)(?:\/(\w+))?/);
  const pid = m ? decodeURIComponent(m[1]) : null;
  if (S.g && pid !== S.pid) {
    if (!await flush() && !confirm('This page could not be saved (' + ($('#saved').title || 'server') + '). Leave it anyway? Your last changes will be lost.')) {
      history.replaceState(null, '', '#/p/' + encodeURIComponent(S.pid) + '/' + S.mode);
      return;
    }
    closePage();
  }
  if (!pid) return startScreen();
  const mode = ['lines', 'tables', 'equations', 'articles'].includes(m[2]) ? m[2] : 'lines';
  if (S.g && S.pid === pid) return setMode(mode);
  return openPage(pid, mode);
}
function closePage() {
  S.g = null; S.pid = null; S.draw = null; S.clicks = null; S.pickTitle = false;
  $('#modes').hidden = true; $('#pgbtns').hidden = true; $('#clock').textContent = ''; $('#ptitle').innerHTML = '';
  setSaved('saved');
}

/* ------------------------------------------------------------------ start screen */
function ordered(rows) {
  const groups = new Map();
  for (const r of rows) {
    const k = r.primary || 'other';
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(r);
  }
  const names = [...groups.keys()].sort();
  if (prefs.disFirst) for (const k of names)
    groups.get(k).sort((a, b) => (b.flagged || 0) / Math.max(1, b.lines || 0) - (a.flagged || 0) / Math.max(1, a.lines || 0));
  return names.map(k => [k, groups.get(k)]);
}
function pickNext(rows, after) {
  const flat = ordered(rows).flatMap(([, rs]) => rs).filter(r => r.status !== 'error');
  const open = flat.filter(r => r.status !== 'done' && r.status !== 'skip');
  if (!open.length) return null;
  if (after) {
    const i = flat.findIndex(r => r.page_id === after);
    const later = flat.slice(i + 1).find(r => r.status !== 'done' && r.status !== 'skip' && r.page_id !== after);
    return (later || open.find(r => r.page_id !== after) || null)?.page_id || null;
  }
  return (open.find(r => r.status === 'doing') || open[0]).page_id;
}
async function startScreen() {
  $('#ptitle').innerHTML = '';
  const main = $('#main');
  main.innerHTML = '<div class="msg">Loading…</div>';
  let rows, pr;
  try { [{pages: rows}, pr] = await Promise.all([getJSON('api/pages'), getJSON('api/progress')]); }
  catch (e) { main.innerHTML = `<div class="msg err">Could not load the pages.\n${esc(e.message || e)}</div>`; return; }
  const est = pr.estimate || {};
  const pct = (a, b) => b ? Math.round(100 * a / b) : 0;
  const next = pickNext(rows);
  const basis = est.basis === 'own'
    ? `Estimate from your own times (${est.timed_lines} lines timed): ${est.per_clean_line} s a clean line, ${est.per_flagged_line} s a marked line, ${est.per_page} s a page.`
    : `First guess until 30 lines are timed: ${est.per_clean_line} s a clean line, ${est.per_flagged_line} s a marked line, ${est.per_page} s a page, ${est.per_table_cell} s a table cell, ${est.per_equation} s an equation.`;
  main.innerHTML = `<div class="start"><div class="inner">
    <div class="stats">
      <div class="stat"><div class="big">${pr.pages_done} / ${pr.pages}</div><div class="lab">pages done</div><div class="bar"><i style="width:${pct(pr.pages_done, pr.pages)}%"></i></div></div>
      <div class="stat"><div class="big">${pr.lines_done} / ${pr.lines}</div><div class="lab">lines checked</div><div class="bar"><i style="width:${pct(pr.lines_done, pr.lines)}%"></i></div></div>
      <div class="stat"><div class="big">${(pr.seconds / 3600).toFixed(1)} h</div><div class="lab">time spent</div></div>
      <div class="stat"><div class="big">≈ ${est.hours_left ?? '?'} h</div><div class="lab">time left (estimate)</div></div>
    </div>
    <div class="basis">${esc(basis)}</div>
    <div class="actions">
      ${next ? `<button class="main cont" id="cont">Continue ▸ <span style="font:12px var(--mono)">${esc(next)}</span></button>` : '<b>All pages are done.</b>'}
      <label><input type="checkbox" id="disfirst" ${prefs.disFirst ? 'checked' : ''}> Disagreements first</label>
    </div>
    ${ordered(rows).map(([k, rs]) => `<section class="group"><h2>${esc(k)} <span style="font-weight:400">(${rs.length})</span></h2><div class="chips">
      ${rs.map(r => `<a class="chip p-${esc(r.status)}" href="#/p/${encodeURIComponent(r.page_id)}" title="${esc(r.error || (r.journal || '') + ' ' + (r.year || ''))}">
        <span class="id">${esc(r.page_id)}</span>
        <span class="st">${esc(PST[r.status] || r.status)}</span>
        ${r.status === 'error' ? `<span class="sub">${esc(r.error)}</span>` : `<span class="sub">${r.lines_done}/${r.lines} lines · <span class="fl">${r.flagged} marked</span>${r.tables ? ' · ' + r.tables + ' table' : ''}${r.equations ? ' · ' + r.equations + ' eq.' : ''}${r.seconds ? ' · ' + fmtClock(r.seconds) : ''}</span>
        <span class="sub">${esc([r.journal, r.year, r.decade, r.split].filter(Boolean).join(' · '))}</span>`}
      </a>`).join('')}</div></section>`).join('')}
  </div></div>`;
  const c = $('#cont');
  if (c) { c.onclick = () => { location.hash = '#/p/' + encodeURIComponent(next); }; c.focus(); }
  $('#disfirst').onchange = e => { prefs.disFirst = e.target.checked; savePrefs(); startScreen(); };
}

/* ------------------------------------------------------------------ page */
async function openPage(pid, mode, reload) {
  const main = $('#main');
  if (!reload) main.innerHTML = '<div class="msg">Loading page…</div>';
  let g;
  try {
    g = await getJSON('api/page/' + encodeURIComponent(pid));
    if (!g || !Array.isArray(g.lines) || !Array.isArray(g.order) || !g.image) throw new Error('the page file has no lines/order/image');
  } catch (e) {
    main.innerHTML = `<div class="msg err">Could not open ${esc(pid)}.\n${esc(e.message || e)}\n\n<a href="#/">◂ all pages</a></div>`;
    return;
  }
  for (const k of ['tables', 'equations', 'articles', 'regions']) if (!Array.isArray(g[k])) g[k] = [];
  const keepPos = reload && S.g && S.pid === pid ? S.pos : null;
  S.g = g; S.pid = pid; S.seq = 0; S.savedSeq = 0; S.timeDirty = false; S.again = false;
  S.t = 0; S.e = 0; S.model = null; S.sel = null; S.clicks = null; S.pickTitle = false; S.draw = null;
  S.art = g.articles[0]?.id || null;
  const firstTodo = g.order.findIndex(id => (lineById(id) || {}).status === 'todo');
  S.pos = keepPos != null && keepPos < g.order.length ? keepPos : Math.max(0, firstTodo);
  S.entry = (curLine() || {}).text || '';
  setSaved('saved');
  $('#ptitle').innerHTML = `<b>${esc(pid)}</b> · ${esc([g.primary, g.journal, g.year, g.split].filter(Boolean).join(' · '))}`;
  $('#modes').hidden = false; $('#pgbtns').hidden = false;
  $('#clock').textContent = '⏱ ' + fmtClock(g.seconds);
  S.mode = mode;
  renderPage();
}
function setMode(mode) {
  if (S.mode === 'lines') commitField();
  S.mode = mode; S.draw = null; S.clicks = null; S.pickTitle = false;
  const h = '#/p/' + encodeURIComponent(S.pid) + '/' + mode;
  if (location.hash !== h) history.replaceState(null, '', h);
  renderPage();
}
function modeCounts() {
  const g = S.g;
  return {lines: g.lines.filter(l => l.status === 'todo').length,
    tables: g.tables.filter(t => (t.status || 'todo') === 'todo').length + '/' + g.tables.length,
    equations: g.equations.filter(t => (t.status || 'todo') === 'todo').length + '/' + g.equations.length,
    articles: g.articles.length};
}
function renderModes() {
  const c = modeCounts();
  for (const b of $('#modes').querySelectorAll('button')) {
    const m = b.dataset.mode;
    b.classList.toggle('on', m === S.mode);
    const label = {lines: 'Lines', tables: 'Tables', equations: 'Equations', articles: 'Articles'}[m];
    const n = m === 'lines' ? c.lines + ' left' : m === 'articles' ? c.articles : c[m] + '';
    b.innerHTML = `${label}<span class="n">${esc(n)}</span>`;
  }
}
$('#modes').addEventListener('click', e => {
  const b = e.target.closest('button[data-mode]');
  if (b && S.g) location.hash = '#/p/' + encodeURIComponent(S.pid) + '/' + b.dataset.mode;
});
$('#pgbtns').addEventListener('click', e => {
  const b = e.target.closest('button[data-act]');
  if (b) act(b.dataset.act);
});

function renderPage() {
  const g = S.g;
  renderModes();
  const drawLabel = {lines: '+ Missing line', tables: '+ Table box', equations: '+ Equation box', articles: '+ Region'}[S.mode];
  $('#main').innerHTML = `<div class="pg ${S.mode === 'articles' ? 'wide' : ''}">
    <aside class="sheetpane">
      <div class="sheetbar">
        <button data-act="zoomout" title="smaller">−</button><button data-act="zoomin" title="bigger">+</button>
        <button data-act="fit" title="fit the width">Fit</button>
        ${S.mode === 'lines' ? `<button data-act="numbers" class="${S.numbers ? 'on' : ''}" title="show the reading order">Order numbers</button>` : ''}
        <button data-act="draw" id="drawbtn" title="drag a box on the page">${drawLabel}</button>
        <span class="hint" id="hint"></span>
      </div>
      <div class="sheetwrap" id="sheetwrap"><div class="sheet" id="sheet">
        <img id="pgimg" alt="" src="${imgURL(g.page_id)}" draggable="false">
        <svg id="svg" viewBox="0 0 ${g.image.width} ${g.image.height}" preserveAspectRatio="none"></svg>
      </div></div>
    </aside>
    <section class="work" id="work"></section>
  </div>`;
  $('#main').querySelector('.pg').addEventListener('click', e => {
    const b = e.target.closest('button[data-act]');
    if (b) act(b.dataset.act, b);
  });
  sizeSheet();
  setupSvg();
  renderWork();
}
function sizeSheet() {
  const wrap = $('#sheetwrap'), sheet = $('#sheet');
  if (!wrap || !sheet) return;
  let fit = Math.max(120, wrap.clientWidth - 14);
  if (S.mode === 'articles')        // the whole page in view: blocks are clicked together
    fit = Math.max(120, Math.min(fit, (wrap.clientHeight - 14) * S.g.image.width / S.g.image.height));
  const w = fit * S.zoom;
  sheet.style.width = w + 'px';
  sheet.style.height = (w * S.g.image.height / S.g.image.width) + 'px';
}
let rz;
window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { if (S.g && $('#work')) { sizeSheet(); renderWork(true); } }, 120); });

function renderWork(keepFocus) {
  if (S.mode === 'lines') renderLine(keepFocus);
  else if (S.mode === 'tables') renderTable();
  else if (S.mode === 'equations') renderEquation();
  else renderArticles();
  drawBoxes();
  updateHint();
}
function updateHint() {
  const h = $('#hint');
  if (!h) return;
  const b = $('#drawbtn');
  if (b) b.classList.toggle('on', !!S.draw);
  h.textContent = S.draw ? 'drag a box on the page (Esc = stop)' : S.clicks ? `click regions in reading order (${S.clicks.n} done; Esc = finish)` :
    S.pickTitle ? 'click the title line' : '';
}

/* ------------------------------------------------------------------ the page image: boxes, clicks, drawing */
function rect(b, cls, id) {
  const [x0, y0, x1, y1] = b;
  return `<rect class="${cls}" ${id ? `data-id="${esc(id)}"` : ''} x="${x0}" y="${y0}" width="${Math.max(1, x1 - x0)}" height="${Math.max(1, y1 - y0)}"/>`;
}
function scale() { const s = $('#sheet'); return s ? s.clientWidth / S.g.image.width : 1; }
function drawBoxes() {
  const svg = $('#svg');
  if (!svg) return;
  const g = S.g, k = 1 / scale(), out = [];
  if (S.mode === 'lines') {
    const cur = g.order[S.pos];
    const idx = new Map(g.order.map((id, i) => [id, i]));
    for (const ln of g.lines) {
      const b = ln.box;
      if (disagrees(ln)) out.push(rect([b[0] - 3 * k, b[1] - 3 * k, b[2] + 3 * k, b[3] + 3 * k], 'ring'));
      out.push(rect(b, `b st-${ln.status}${ln.id === cur ? ' cur' : ''}`, ln.id));
      if (ln.status === 'deleted') out.push(`<line class="strike" x1="${b[0]}" y1="${(b[1] + b[3]) / 2}" x2="${b[2]}" y2="${(b[1] + b[3]) / 2}"/>`);
      if (S.numbers) out.push(`<text class="num" style="font-size:${12 * k}px;stroke-width:${3 * k}px" x="${b[2] + 2 * k}" y="${(b[1] + b[3]) / 2 + 4 * k}">${idx.get(ln.id) + 1}</text>`);
    }
  } else if (S.mode === 'tables' || S.mode === 'equations') {
    for (const ln of g.lines) out.push(rect(ln.box, 'faint'));
    const items = S.mode === 'tables' ? g.tables : g.equations, cur = S.mode === 'tables' ? S.t : S.e;
    items.forEach((t, i) => { if (t.box) out.push(rect(t.box, `b st-${t.status === 'todo' || !t.status ? 'todo' : t.status === 'ok' ? 'ok' : 'edited'}${i === cur ? ' cur' : ''}`, 'i' + i)); });
  } else {
    for (const ln of g.lines) out.push(rect(ln.box, 'faint' + (S.pickTitle ? ' pick' : ''), S.pickTitle ? ln.id : null));
    const arts = g.articles.map(a => a.id);
    for (const r of g.regions) {
      if (!r.box) continue;
      const ai = arts.indexOf(r.article), col = ai >= 0 ? ART_COL[ai % ART_COL.length] : '#8DA0AF';
      const fillOp = ai >= 0 ? .13 : .03;
      out.push(`<rect class="rg${ai < 0 ? ' noart' : ''}${S.sel === r.id ? ' sel' : ''}" data-id="${esc(r.id)}" x="${r.box[0]}" y="${r.box[1]}" width="${r.box[2] - r.box[0]}" height="${r.box[3] - r.box[1]}" style="stroke:${col};fill:${col};fill-opacity:${fillOp}${S.pickTitle ? ';pointer-events:none' : ''}"/>`);
      const lab = `${r.order} · col ${r.column}${ai >= 0 ? ' · A' + (ai + 1) : ''}${r.type !== 'text' ? ' · ' + r.type : ''}`;
      out.push(`<text class="rlab" style="font-size:${12 * k}px;stroke-width:${3 * k}px;fill:${col}" x="${r.box[2] - 3 * k}" y="${r.box[1] + 13 * k}" text-anchor="end">${esc(lab)}</text>`);
    }
    if (S.pickTitle) for (const ln of g.lines) out.push(rect(ln.box, 'faint pick', ln.id));
  }
  svg.innerHTML = out.join('');
  svg.classList.toggle('drawing', !!S.draw);
}
function scrollToBox(b) {
  const wrap = $('#sheetwrap');
  if (!wrap || !b) return;
  const s = scale(), sheet = $('#sheet');
  const top = sheet.offsetTop + b[1] * s, bot = sheet.offsetTop + b[3] * s;
  if (top < wrap.scrollTop + 20 || bot > wrap.scrollTop + wrap.clientHeight - 20)
    wrap.scrollTop = Math.max(0, (top + bot) / 2 - wrap.clientHeight / 2);
  const left = sheet.offsetLeft + b[0] * s, right = sheet.offsetLeft + b[2] * s;
  if (left < wrap.scrollLeft || right > wrap.scrollLeft + wrap.clientWidth)
    wrap.scrollLeft = Math.max(0, (left + right) / 2 - wrap.clientWidth / 2);
}
function svgPoint(ev) {
  const r = $('#svg').getBoundingClientRect();
  return [(ev.clientX - r.left) * S.g.image.width / r.width, (ev.clientY - r.top) * S.g.image.height / r.height];
}
function setupSvg() {
  const svg = $('#svg');
  let start = null, rub = null;
  svg.addEventListener('pointerdown', ev => {
    if (!S.draw || ev.button !== 0) return;
    ev.preventDefault();
    start = svgPoint(ev);
    svg.setPointerCapture(ev.pointerId);
    rub = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rub.setAttribute('class', 'rubber');
    svg.appendChild(rub);
  });
  svg.addEventListener('pointermove', ev => {
    if (!start || !rub) return;
    const p = svgPoint(ev);
    rub.setAttribute('x', Math.min(start[0], p[0])); rub.setAttribute('y', Math.min(start[1], p[1]));
    rub.setAttribute('width', Math.abs(p[0] - start[0])); rub.setAttribute('height', Math.abs(p[1] - start[1]));
  });
  svg.addEventListener('pointerup', ev => {
    if (!start) return;
    const p = svgPoint(ev), W = S.g.image.width, H = S.g.image.height;
    const c = v => Math.round(v * 10) / 10;
    const box = [c(Math.max(0, Math.min(start[0], p[0]))), c(Math.max(0, Math.min(start[1], p[1]))),
      c(Math.min(W, Math.max(start[0], p[0]))), c(Math.min(H, Math.max(start[1], p[1])))];
    start = null; rub = null;
    if (box[2] - box[0] < 6 || box[3] - box[1] < 6) { drawBoxes(); toast('Too small: drag a bigger box'); return; }
    drew(box);
  });
  svg.addEventListener('click', ev => {
    if (S.draw) return;
    const el = ev.target.closest('[data-id]');
    if (!el) return;
    const id = el.dataset.id;
    if (S.mode === 'lines') { const i = S.g.order.indexOf(id); if (i >= 0) gotoLine(i); }
    else if (S.mode === 'tables') { commitTable(); S.t = +id.slice(1); S.model = null; renderWork(); }
    else if (S.mode === 'equations') { commitEquation(); S.e = +id.slice(1); renderWork(); }
    else clickRegion(id);
  });
}
function setDraw(on) {
  S.draw = on ? S.mode : null;
  drawBoxes(); updateHint();
}
function drew(box) {
  const g = S.g, mode = S.draw;
  S.draw = null;
  if (mode === 'lines') addLine(box);
  else if (mode === 'tables') {
    const t = {id: nextId('t', g.tables, 1), region: regionAt(box), box, html: '', draft_html: '', status: 'todo'};
    g.tables.push(t); S.t = g.tables.length - 1; S.model = null; changed(); renderModes(); renderWork();
  } else if (mode === 'equations') {
    const e = {id: nextId('e', g.equations, 1), region: regionAt(box), box, latex: '', mathml: '', display: true, draft_latex: '', status: 'todo'};
    g.equations.push(e); S.e = g.equations.length - 1; changed(); renderModes(); renderWork();
  } else if (mode === 'articles') {
    const r = {id: nextId('r', g.regions, 2), type: 'text', box, column: 1, article: S.art, order: g.regions.length + 1};
    g.regions.push(r); S.sel = r.id; syncArticles(); changed(); renderWork();
  }
}
function regionAt(box) {
  const cx = (box[0] + box[2]) / 2, cy = (box[1] + box[3]) / 2;
  const r = S.g.regions.find(r => r.box && r.box[0] <= cx && cx <= r.box[2] && r.box[1] <= cy && cy <= r.box[3]);
  return r ? r.id : null;
}

/* ------------------------------------------------------------------ actions (buttons and keys) */
function act(a, btn) {
  if (!S.g) return;
  const z = {zoomin: 1.25, zoomout: 0.8}[a];
  if (z) { S.zoom = Math.min(5, Math.max(0.5, S.zoom * z)); prefs.zoom = S.zoom; savePrefs(); sizeSheet(); drawBoxes(); return; }
  switch (a) {
    case 'fit': S.zoom = 1; prefs.zoom = 1; savePrefs(); sizeSheet(); drawBoxes(); return;
    case 'numbers': S.numbers = !S.numbers; if (btn) btn.classList.toggle('on', S.numbers); drawBoxes(); return;
    case 'draw': setDraw(!S.draw); return;
    case 'save': save(); return;
    case 'pagedone': return askDone(true);
    case 'skip': return modal('Skip this page?', 'It will not be used for scoring.',
      [['Skip page', 'main', () => finishPage('skip')], ['Cancel', '', null]]);
    // lines
    case 'accept': return accept();
    case 'next': return gotoLine(S.pos + 1);
    case 'prev': return gotoLine(S.pos - 1);
    case 'nextflag': return nextFlag();
    case 'take1': return take(1);
    case 'take2': return take(2);
    case 'undo': return undoLine();
    case 'deleted': return markLine('deleted');
    case 'unsure': return markLine('unsure');
    case 'kind': return cycleKind();
    case 'earlier': return moveOrder(-1);
    case 'later': return moveOrder(1);
    // tables
    case 'tprev': return goTable(S.t - 1);
    case 'tnext': return goTable(S.t + 1);
    case 'tdel': return delItem('tables');
    case 'taccept': return acceptTable();
    case 'tdraft': return tableFromDraft();
    case 'rowabove': case 'rowbelow': case 'colright': case 'colleft': case 'delrow': case 'delcol':
    case 'mergeleft': case 'mergedown': case 'split': return gridOp(a);
    // equations
    case 'eprev': return goEq(S.e - 1);
    case 'enext': return goEq(S.e + 1);
    case 'edel': return delItem('equations');
    case 'eaccept': return acceptEq();
    case 'edraft': { const t = $('#tex'); if (t) { t.value = S.g.equations[S.e].draft_latex || ''; t.dispatchEvent(new Event('input')); } return; }
    // articles
    case 'newart': return newArticle();
    case 'delart': return delArticle();
    case 'clicks': return S.clicks ? endClicks() : startClicks();
    case 'title': S.pickTitle = !S.pickTitle; S.clicks = null; drawBoxes(); updateHint(); return;
    case 'colminus': case 'colplus': return regionCol(a === 'colplus' ? 1 : -1);
    case 'unassign': { const r = S.g.regions.find(r => r.id === S.sel); if (r) { r.article = null; syncArticles(); changed(); renderWork(); } return; }
  }
}

document.addEventListener('keydown', onKey, true);
function onKey(e) {
  if (e.isComposing || e.keyCode === 229) return;
  if (S.modal) {
    if (e.key === 'Enter') { e.preventDefault(); S.modal.yes(); }
    else if (e.key === 'Escape') { e.preventDefault(); S.modal.no(); }
    return;
  }
  if (!S.g || !$('#work')) return;
  const k = e.code, alt = e.altKey, ctrl = e.ctrlKey || e.metaKey, sh = e.shiftKey;
  const stop = () => { e.preventDefault(); e.stopPropagation(); };
  if (ctrl && !alt && k === 'KeyS') { stop(); save(); return; }
  if (e.key === 'Escape' && (S.draw || S.clicks || S.pickTitle)) {
    stop(); if (S.clicks) endClicks(); S.draw = null; S.pickTitle = false; drawBoxes(); updateHint(); return;
  }
  if (S.mode === 'lines') {
    if (e.key === 'Enter' && !alt && !ctrl && !sh) { stop(); accept(); }
    else if (e.key === 'Enter' && sh) { stop(); }
    else if (e.key === 'Enter' && ctrl && !alt) { stop(); take(2); }
    else if (alt && !ctrl && !sh && k === 'Digit1') { stop(); take(1); }
    else if (alt && !ctrl && !sh && k === 'Digit2') { stop(); take(2); }
    else if (e.key === 'Escape') { stop(); undoLine(); }
    else if (alt && sh && !ctrl && k === 'ArrowUp') { stop(); moveOrder(-1); }
    else if (alt && sh && !ctrl && k === 'ArrowDown') { stop(); moveOrder(1); }
    else if ((alt && !ctrl && k === 'ArrowDown') || (k === 'PageDown' && !alt && !ctrl)) { stop(); gotoLine(S.pos + 1); }
    else if ((alt && !ctrl && k === 'ArrowUp') || (k === 'PageUp' && !alt && !ctrl)) { stop(); gotoLine(S.pos - 1); }
    else if (alt && !ctrl && k === 'KeyN') { stop(); nextFlag(); }
    else if (ctrl && !alt && k === 'Delete') { stop(); markLine('deleted'); }
    else if (alt && !ctrl && k === 'KeyU') { stop(); markLine('unsure'); }
    else if (alt && !ctrl && k === 'KeyK') { stop(); cycleKind(); }
    else if (alt && !ctrl && (k === 'ArrowLeft' || k === 'ArrowRight')) { stop(); }   // Alt+← is "back" in Chrome
  } else if (S.mode === 'tables') {
    const td = e.target.closest && e.target.closest('table.grid td');
    if (e.key === 'Tab' && td) { stop(); moveCell(sh ? -1 : 1); }
    else if (e.key === 'Enter' && ctrl) { stop(); acceptTable(); }
    else if (e.key === 'Enter' && td && !alt) { stop(); moveCell(sh ? -1 : 1); }
    else if (alt && !ctrl && k === 'ArrowDown') { stop(); goTable(S.t + 1); }
    else if (alt && !ctrl && k === 'ArrowUp') { stop(); goTable(S.t - 1); }
    else if (alt && !ctrl && (k === 'ArrowLeft' || k === 'ArrowRight')) { stop(); }
  } else if (S.mode === 'equations') {
    if (e.key === 'Enter' && ctrl) { stop(); acceptEq(); }
    else if (alt && !ctrl && k === 'ArrowDown') { stop(); goEq(S.e + 1); }
    else if (alt && !ctrl && k === 'ArrowUp') { stop(); goEq(S.e - 1); }
    else if (e.key === 'Escape') { stop(); const t = $('#tex'); const q = S.g.equations[S.e]; if (t && q) { t.value = q.latex || q.draft_latex || ''; } }
    else if (alt && !ctrl && (k === 'ArrowLeft' || k === 'ArrowRight')) { stop(); }
  } else if (S.mode === 'articles') {
    const typing = e.target.matches && e.target.matches('input,textarea,select,[contenteditable]');
    if (typing || alt || ctrl) return;
    const d = k.match(/^(?:Digit|Numpad)([1-9])$/);
    if (d) {
      stop();
      const i = +d[1] - 1;
      if (i < S.g.articles.length) { S.art = S.g.articles[i].id; renderWork(); }
      else if (i === S.g.articles.length) newArticle();
    } else if (k === 'KeyN') { stop(); newArticle(); }
    else if (k === 'KeyO') { stop(); S.clicks ? endClicks() : startClicks(); }
  }
}

/* ------------------------------------------------------------------ lines mode */
function renderLine(keepFocus) {
  const work = $('#work'), g = S.g, ln = curLine();
  if (!ln) {
    work.innerHTML = `<div class="empty">This page has no lines. Use <b>+ Missing line</b> to draw one, or mark the page done.</div>`;
    return;
  }
  const had = keepFocus && $('#txt') ? {v: $('#txt').value, s: $('#txt').selectionStart, e: $('#txt').selectionEnd} : null;
  const done = g.lines.filter(l => l.status !== 'todo').length;
  const dir = ln.lang === 'la' ? 'ltr' : 'rtl';
  work.innerHTML = `
    <div class="lhead"><b>Line ${S.pos + 1} / ${g.order.length}</b>
      <span class="tag st-${esc(ln.status)}">${esc(LST[ln.status] || ln.status)}</span>
      <span class="tag" title="Alt+K changes it">${esc(ln.kind || 'text')}</span>
      ${(ln.flags || []).map(f => `<span class="tag fl">${esc(f)}</span>`).join(' ')}
      ${ln.disagree && ln.disagree.length ? `<span class="tag fl">${ln.disagree.length} disagreement${ln.disagree.length > 1 ? 's' : ''}</span>` : ''}
      <span class="grow"></span><span>${done} / ${g.lines.length} checked · ${esc(ln.id)}</span></div>
    <div class="cropbox"><div class="crop" id="crop"><div class="fade t"></div><div class="fade b"></div></div></div>
    <div class="mirror ar" id="mirror" dir="${dir}" lang="ar"></div>
    <textarea id="txt" class="txt ar" rows="1" dir="${dir}" lang="ar" autocomplete="off" spellcheck="false"></textarea>
    <div class="rd" id="rd1" title="click (or Alt+1) to put this reading in the field"><span class="lab">1 · Azure</span><span class="words ar" dir="${dir}" id="rd1w"></span></div>
    <div class="rd" id="rd2" title="click (or Alt+2, Ctrl+Enter) to put this reading in the field"><span class="lab">2 · Second</span><span class="words ar" dir="${dir}" id="rd2w"></span></div>
    <div class="pal" id="pal">${PALETTE.map(c => `<button data-ins="${esc(c)}" tabindex="-1" title="insert ${esc(c)}">${MARKS.includes(c) ? '◌' + c : esc(c)}</button>`).join('')}</div>
    <div class="btns">
      <button class="main" data-act="accept">✓ Correct, next<kbd>Enter</kbd></button>
      <button data-act="prev">▲ Previous<kbd>Alt+↑</kbd></button>
      <button data-act="next">▼ Next<kbd>Alt+↓</kbd></button>
      <button data-act="nextflag">Next marked<kbd>Alt+N</kbd></button>
      <button data-act="take1">Azure<kbd>Alt+1</kbd></button>
      <button data-act="take2">Second<kbd>Alt+2</kbd></button>
      <button data-act="undo">Undo<kbd>Esc</kbd></button>
    </div>
    <div class="btns">
      <button data-act="deleted">Not text<kbd>Ctrl+Del</kbd></button>
      <button data-act="unsure">Unsure<kbd>Alt+U</kbd></button>
      <button data-act="kind">Kind<kbd>Alt+K</kbd></button>
      <button data-act="earlier">Earlier in order<kbd>Alt+Shift+↑</kbd></button>
      <button data-act="later">Later in order<kbd>Alt+Shift+↓</kbd></button>
      <button data-act="save">Save<kbd>Ctrl+S</kbd></button>
    </div>
    <div class="legend">Correct the text so it is <b>exactly as printed</b> (marks as printed, no kashida). Yellow = the readers disagree there; blue = your change; orange/red word = Azure was not sure.</div>`;
  const inp = $('#txt');
  inp.value = had ? had.v : ln.text ?? '';
  inp.addEventListener('input', onTyping);
  inp.addEventListener('input', () => autosize(inp));
  inp.addEventListener('focus', () => { S.lastField = inp; });
  $('#rd1').onclick = () => take(1);
  $('#rd2').onclick = () => take(2);
  setupPalette();
  layoutCrop();
  updateMirror();
  autosize(inp);
  inp.focus();
  if (had) inp.setSelectionRange(had.s, had.e); else inp.setSelectionRange(inp.value.length, inp.value.length);
  scrollToBox(ln.box);
}
function autosize(el) { el.style.height = 'auto'; el.style.height = (el.scrollHeight + 4) + 'px'; }
function layoutCrop() {
  const ln = curLine(), el = $('#crop'), work = $('#work');
  if (!ln || !el) return;
  const avail = work.clientWidth - 32;
  const maxH = Math.max(120, Math.min(280, window.innerHeight * 0.3));
  cropInto(el, ln.box, avail * 0.92, maxH, 1.0);
}
function cropInto(el, box, maxW, maxH, ctx) {
  const g = S.g, [x0, y0, x1, y1] = box;
  const h = Math.max(8, y1 - y0), w = Math.max(8, x1 - x0);
  const px = Math.max(6, w * 0.015), cy = ctx * h + 4;
  const X0 = x0 - px, X1 = x1 + px, Y0 = y0 - cy, Y1 = y1 + cy;
  const s = Math.min(maxW / (X1 - X0), maxH / (Y1 - Y0), 3);
  el.style.width = (X1 - X0) * s + 'px';
  el.style.height = (Y1 - Y0) * s + 'px';
  el.style.backgroundImage = `url("${imgURL(g.page_id)}")`;
  el.style.backgroundSize = `${g.image.width * s}px ${g.image.height * s}px`;
  el.style.backgroundPosition = `${-X0 * s}px ${-Y0 * s}px`;
  const t = $('.fade.t', el), b = $('.fade.b', el);
  if (t) t.style.height = (ctx ? (cy - 2) * s : 0) + 'px';
  if (b) b.style.height = (ctx ? (cy - 2) * s : 0) + 'px';
}
function onTyping() {
  const ln = curLine();
  if (!ln) return;
  ln.text = $('#txt').value;
  changed();
  updateMirror();
}
function updateMirror() {
  const ln = curLine(), inp = $('#txt');
  if (!ln || !inp) return;
  const cur = inp.value, orig = ln.draft && ln.draft.azure != null ? ln.draft.azure : (ln.status === 'added' ? '' : ln.text || '');
  // marks: 1 = the readers disagree here (spans of the draft text, carried over to the edited text), 2 = changed
  let p = 0;
  while (p < orig.length && p < cur.length && orig[p] === cur[p]) p++;
  let s = 0;
  while (s < orig.length - p && s < cur.length - p && orig[orig.length - 1 - s] === cur[cur.length - 1 - s]) s++;
  const d = cur.length - orig.length, cS = p, cE = cur.length - s;
  const map = i => i <= p ? i : (i >= orig.length - s ? i + d : null);
  const mk = new Uint8Array(cur.length);
  for (const sp of ln.disagree || []) {
    if (!Array.isArray(sp) || sp.length < 2) continue;
    let a = map(sp[0]), b = map(sp[1]);
    if (a == null) a = cS; if (b == null) b = cE;
    for (let i = Math.max(0, a); i < Math.min(cur.length, b); i++) mk[i] = 1;
  }
  if (orig !== cur) for (let i = cS; i < cE; i++) mk[i] = 2;
  let html = '', i = 0;
  while (i < cur.length) {
    let j = i;
    while (j < cur.length && mk[j] === mk[i]) j++;
    const t = esc(cur.slice(i, j));
    html += mk[i] === 1 ? `<mark>${t}</mark>` : mk[i] === 2 ? `<span class="chg">${t}</span>` : t;
    i = j;
  }
  const m = $('#mirror');
  const any = mk.some(v => v);       // shown only when it has something to mark; otherwise one empty line
  m.innerHTML = any ? html : '&nbsp;';
  m.title = 'what you typed, with the disagreements (yellow) and your changes (blue)';
  // the readings, with the words that differ from the field underlined
  const cw = words(cur);
  const az = ln.draft && ln.draft.azure != null ? ln.draft.azure : '';
  const aw = words(az), keepA = lcsKeep(aw, cw);
  const confs = Array.isArray(ln.words) && ln.words.length === aw.length ? ln.words.map(w => w.conf) : null;
  $('#rd1w').innerHTML = aw.length ? aw.map((w, i) => {
    const c = confs ? confs[i] : null;
    const lo = c == null ? '' : c < 0.5 ? ' lo2' : c < 0.8 ? ' lo1' : '';
    return `<span class="w${lo}${keepA[i] ? '' : ' diff'}" title="${c == null ? '' : 'Azure is ' + Math.round(c * 100) + '% sure'}">${esc(w)}</span>`;
  }).join(' ') : '<span class="none">no reading</span>';
  const gm = ln.draft && ln.draft.gemini;
  if (gm != null && gm !== '') {
    const gw = words(gm), keepG = lcsKeep(gw, cw);
    $('#rd2w').innerHTML = gw.map((w, i) => `<span class="w${keepG[i] ? '' : ' diff'}">${esc(w)}</span>`).join(' ');
  } else $('#rd2w').innerHTML = '<span class="none">no second reading</span>';
}
function setupPalette() {
  const pal = $('#pal');
  if (!pal) return;
  pal.addEventListener('mousedown', e => { if (e.target.closest('button')) e.preventDefault(); });
  pal.addEventListener('click', e => { const b = e.target.closest('button[data-ins]'); if (b) insertText(b.dataset.ins); });
}
function insertText(ch) {
  let el = document.activeElement;
  if (!el || !(el.matches('textarea,input[type=text]') || el.isContentEditable)) el = S.lastField;
  if (!el || !document.body.contains(el)) { el = $('#txt') || $('#tex') || $('table.grid td'); }
  if (!el) return;
  el.focus();
  if (el.isContentEditable) { document.execCommand('insertText', false, ch); return; }
  el.setRangeText(ch, el.selectionStart, el.selectionEnd, 'end');
  el.dispatchEvent(new Event('input', {bubbles: true}));
}
function commitField() {
  const inp = $('#txt'), ln = curLine();
  if (inp && ln && inp.value !== ln.text) { ln.text = inp.value; changed(); }
}
function gotoLine(i) {
  if (!S.g.order.length) return;
  commitField();
  S.pos = Math.max(0, Math.min(S.g.order.length - 1, i));
  S.entry = (curLine() || {}).text || '';
  renderWork();
}
function accept() {
  const ln = curLine(), inp = $('#txt');
  if (!ln || !inp) return;
  const v = norm(inp.value);
  if (ln.status === 'added' && !v) { toast('Type the line first (or Ctrl+Del to remove the box)'); return; }
  ln.text = v;
  if (ln.status !== 'added') ln.status = v === norm(ln.draft && ln.draft.azure) ? 'ok' : 'edited';
  changed();
  save();
  advance();
}
function advance() {              // the next line still to do (after this one, then from the top); then "page done?"
  const g = S.g, n = g.order.length, todo = i => (lineById(g.order[i]) || {}).status === 'todo';
  renderModes();
  const first = g.order.findIndex((_, i) => todo(i));
  if (first < 0) {                 // nothing left to do: a page being read again goes line by line
    if (S.pos < n - 1) return gotoLine(S.pos + 1);
    renderWork();
    return askDone(false);
  }
  for (let i = S.pos + 1; i < n; i++) if (todo(i)) return gotoLine(i);
  gotoLine(first);
  toast('Back to the first line still to do');
}
function askDone(explicit) {
  const g = S.g;
  commitField();
  const lt = g.lines.filter(l => l.status === 'todo').length;
  const tt = g.tables.filter(t => (t.status || 'todo') === 'todo').length;
  const et = g.equations.filter(t => (t.status || 'todo') === 'todo').length;
  if (!explicit && tt) { toast('Lines done. Now the table' + (tt > 1 ? 's' : '')); setMode('tables'); return; }
  if (!explicit && et) { toast('Lines done. Now the equation' + (et > 1 ? 's' : '')); setMode('equations'); return; }
  const left = [lt && `${lt} line(s)`, tt && `${tt} table(s)`, et && `${et} equation(s)`].filter(Boolean).join(', ');
  modal('Page done?', left ? `Still to do: ${left}. Mark the page done anyway?` : 'Every line is checked. Enter = yes, go to the next page.',
    [['Yes, page done <kbd>Enter</kbd>', 'main', () => finishPage('done')], ['Not yet <kbd>Esc</kbd>', '', null]]);
}
async function finishPage(status) {
  const g = S.g;
  g.status = status;
  if (status === 'done') g.checked = {by: (g.checked && g.checked.by) || 'owner', at: new Date().toISOString().slice(0, 19)};
  S.seq++;
  if (!await flush()) { toast('Not saved — the page stays open', 5000); return; }
  let rows = [];
  try { rows = (await getJSON('api/pages')).pages; } catch {}
  const next = pickNext(rows, g.page_id);
  if (next) { toast(status === 'done' ? 'Page done ✓' : 'Page skipped'); location.hash = '#/p/' + encodeURIComponent(next); }
  else { toast('All pages done ✓', 5000); location.hash = '#/'; }
}
function nextFlag() {              // disagreements first, then other marks (low confidence...), lines to do first
  const g = S.g, n = g.order.length;
  const tests = [ln => disagrees(ln) && ln.status === 'todo', ln => flagged(ln) && ln.status === 'todo',
    ln => disagrees(ln), ln => flagged(ln)];
  for (const t of tests) for (let k = 1; k <= n; k++) {
    const i = (S.pos + k) % n, ln = lineById(g.order[i]);
    if (ln && t(ln)) return gotoLine(i);
  }
  toast('No marked lines on this page');
}
function take(which) {
  const ln = curLine(), inp = $('#txt');
  if (!ln || !inp) return;
  const v = which === 1 ? (ln.draft && ln.draft.azure) : (ln.draft && ln.draft.gemini);
  if (v == null || v === '') { toast(which === 1 ? 'No Azure reading' : 'No second reading for this line'); return; }
  inp.value = v;
  onTyping();
  autosize(inp);
  inp.focus();
}
function undoLine() {
  const inp = $('#txt'), ln = curLine();
  if (!inp || !ln) return;
  inp.value = S.entry;
  autosize(inp);
  if (ln.text !== S.entry) { ln.text = S.entry; changed(); }
  updateMirror();
}
function markLine(st) {
  const ln = curLine();
  if (!ln) return;
  if (st === 'deleted' && ln.status === 'added') {          // an added box that is not wanted: remove it
    const g = S.g;
    g.lines = g.lines.filter(l => l !== ln);
    g.order = g.order.filter(id => id !== ln.id);
    S.pos = Math.min(S.pos, g.order.length - 1);
    S.entry = (curLine() || {}).text || '';
    changed(); save(); renderModes(); renderWork(); return;
  }
  commitField();
  if (ln.status === st) { ln.status = 'todo'; changed(); renderWork(); return; }   // pressed again: undone
  ln.status = st;
  ln.text = norm(ln.text);
  changed(); save();
  advance();
}
function cycleKind() {
  const ln = curLine();
  if (!ln) return;
  commitField();
  const i = LINE_KINDS.indexOf(ln.kind || 'text');
  ln.kind = LINE_KINDS[(i + 1) % LINE_KINDS.length];
  changed(); renderWork(true);
}
function moveOrder(d) {
  const g = S.g, j = S.pos + d;
  if (j < 0 || j >= g.order.length) return;
  commitField();
  [g.order[S.pos], g.order[j]] = [g.order[j], g.order[S.pos]];
  S.pos = j;
  if (!S.numbers) { S.numbers = true; const b = $('[data-act=numbers]'); if (b) b.classList.add('on'); }
  changed(); renderWork(true);
}
function addLine(box) {
  const g = S.g;
  commitField();
  const cy = (box[1] + box[3]) / 2;
  const overlapX = l => Math.min(l.box[2], box[2]) - Math.max(l.box[0], box[0]) > 0;
  let above = null;
  for (const l of g.lines) {
    if (l.status === 'deleted' && false) continue;
    const lc = (l.box[1] + l.box[3]) / 2;
    if (lc < cy && overlapX(l) && (!above || l.box[3] > above.box[3])) above = l;
  }
  if (!above) for (const l of g.lines) {
    const lc = (l.box[1] + l.box[3]) / 2;
    if (lc < cy && (!above || lc > (above.box[1] + above.box[3]) / 2)) above = l;
  }
  const ln = {id: nextId('l', g.lines, 3), region: above ? above.region : regionAt(box), box, poly: [],
    kind: above && above.kind !== 'furniture' ? above.kind : 'text', lang: 'ar', text: '', status: 'added',
    draft: {azure: '', gemini: ''}, words: [], disagree: [], flags: []};
  g.lines.push(ln);
  const at = above ? g.order.indexOf(above.id) + 1 : 0;
  g.order.splice(at, 0, ln.id);
  S.pos = at; S.entry = '';
  changed(); renderModes(); renderWork();
  toast('New line: type what is printed, then Enter');
}

/* ------------------------------------------------------------------ tables mode */
function parseTable(html) {
  const cells = [];
  let R = 0, C = 0;
  if (html && /<table/i.test(html)) {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const tb = doc.querySelector('table');
    const occ = [];
    const trs = tb ? [...tb.querySelectorAll('tr')] : [];
    trs.forEach((tr, r) => {
      occ[r] = occ[r] || [];
      let c = 0;
      for (const td of tr.children) {
        if (!/^t[dh]$/i.test(td.tagName)) continue;
        while (occ[r][c]) c++;
        const rs = Math.max(1, Math.min(50, parseInt(td.getAttribute('rowspan') || '1', 10) || 1));
        const cs = Math.max(1, Math.min(50, parseInt(td.getAttribute('colspan') || '1', 10) || 1));
        const rsC = Math.min(rs, trs.length - r);
        cells.push({r, c, rs: rsC, cs, text: norm(td.textContent), th: td.tagName.toLowerCase() === 'th'});
        for (let i = 0; i < rsC; i++) { occ[r + i] = occ[r + i] || []; for (let j = 0; j < cs; j++) occ[r + i][c + j] = true; }
        c += cs;
      }
    });
    R = trs.length;
    C = Math.max(0, ...occ.map(row => (row || []).length));
  }
  if (!R || !C) { R = 2; C = 2; cells.length = 0; }
  const m = {R, C, cells};
  fillTable(m);
  return m;
}
function gridOf(m) {
  const grid = Array.from({length: m.R}, () => new Array(m.C).fill(null));
  for (const c of m.cells) for (let i = 0; i < c.rs; i++) for (let j = 0; j < c.cs; j++)
    if (c.r + i < m.R && c.c + j < m.C) grid[c.r + i][c.c + j] = c;
  return grid;
}
function fillTable(m) {
  const grid = gridOf(m);
  for (let r = 0; r < m.R; r++) for (let c = 0; c < m.C; c++)
    if (!grid[r][c]) { const x = {r, c, rs: 1, cs: 1, text: '', th: false}; m.cells.push(x); grid[r][c] = x; }
  m.cells.sort((a, b) => a.r - b.r || a.c - b.c);
}
function serialiseTable(m) {
  let h = '<table>';
  for (let r = 0; r < m.R; r++) {
    h += '<tr>';
    for (const c of m.cells.filter(c => c.r === r).sort((a, b) => a.c - b.c)) {
      const tag = c.th ? 'th' : 'td';
      h += `<${tag}${c.rs > 1 ? ` rowspan="${c.rs}"` : ''}${c.cs > 1 ? ` colspan="${c.cs}"` : ''}>${esc(norm(c.text)).replace(/&#39;/g, "'").replace(/&quot;/g, '"')}</${tag}>`;
    }
    h += '</tr>';
  }
  return h + '</table>';
}
function goTable(i) {
  const n = S.g.tables.length;
  if (!n) return;
  commitTable();
  S.t = Math.max(0, Math.min(n - 1, i)); S.model = null; S.cell = 0;
  renderWork();
}
function commitTable() {
  const t = S.g.tables[S.t];
  if (!t || !S.model) return;
  const h = serialiseTable(S.model);
  if (h !== (t.html || '') && !(t.html === '' && h === serialiseTable(parseTable(t.draft_html || '')))) { t.html = h; changed(); }
}
function renderTable() {
  const work = $('#work'), g = S.g, t = g.tables[S.t];
  if (!t) {
    work.innerHTML = `<div class="empty">No tables on this page. If there is one, press <b>+ Table box</b> and drag a box round it on the page.</div>`;
    return;
  }
  if (!S.model) S.model = parseTable(t.html || t.draft_html || '');
  work.innerHTML = `
    <div class="lhead"><b>Table ${S.t + 1} / ${g.tables.length}</b>
      <span class="tag st-${t.status === 'ok' ? 'ok' : t.status === 'edited' ? 'edited' : 'todo'}">${esc(LST[t.status] || t.status || 'to do')}</span>
      <span class="grow"></span>
      <button data-act="tprev">◀ Previous table<kbd>Alt+↑</kbd></button><button data-act="tnext">Next table ▶<kbd>Alt+↓</kbd></button>
      <button data-act="tdel" title="remove this table box">Remove table</button></div>
    <div class="twrap">
      <div class="crop" id="tcrop"><div class="fade t"></div><div class="fade b"></div></div>
      <div class="gridbox"><table class="grid" dir="rtl" id="grid"></table></div>
    </div>
    <div class="btns">
      <button data-act="rowabove">+ Row above</button><button data-act="rowbelow">+ Row below</button>
      <button data-act="colright">+ Column right</button><button data-act="colleft">+ Column left</button>
      <button data-act="delrow">− Row</button><button data-act="delcol">− Column</button>
      <button data-act="mergeleft">Merge with left</button><button data-act="mergedown">Merge with below</button>
      <button data-act="split">Split</button>
    </div>
    <div class="btns">
      <button class="main" data-act="taccept">✓ Table correct<kbd>Ctrl+Enter</kbd></button>
      <button data-act="tdraft">Start again from the draft</button>
    </div>
    <div class="pal" id="pal">${PALETTE.map(c => `<button data-ins="${esc(c)}" tabindex="-1">${MARKS.includes(c) ? '◌' + c : esc(c)}</button>`).join('')}</div>
    <div class="legend"><kbd>Tab</kbd>/<kbd>Enter</kbd> next cell (right to left, then down) · <kbd>Shift+Tab</kbd> previous · <kbd>Ctrl+Enter</kbd> table correct · cells in reading order, merged cells as printed.</div>`;
  const wide = work.clientWidth > 900;
  if (t.box) cropInto($('#tcrop'), t.box, wide ? work.clientWidth * 0.48 : work.clientWidth - 30, window.innerHeight * 0.45, 0);
  else $('#tcrop').hidden = true;
  setupPalette();
  drawGrid();
  scrollToBox(t.box);
}
function drawGrid(focusIdx) {
  const m = S.model, tb = $('#grid');
  if (!tb) return;
  tb.innerHTML = '';
  for (let r = 0; r < m.R; r++) {
    const tr = document.createElement('tr');
    for (const c of m.cells.filter(c => c.r === r).sort((a, b) => a.c - b.c)) {
      const td = document.createElement('td');
      td.contentEditable = 'true'; td.dir = 'auto'; td.lang = 'ar';
      if (c.rs > 1) td.rowSpan = c.rs;
      if (c.cs > 1) td.colSpan = c.cs;
      if (c.th) td.className = 'th';
      td.textContent = c.text;
      td.dataset.i = m.cells.indexOf(c);
      td.addEventListener('focus', () => { S.cell = m.cells.indexOf(c); S.lastField = td; });
      td.addEventListener('input', () => { c.text = td.innerText.replace(/\s*\n\s*/g, ' '); tableTyped(); });
      td.addEventListener('paste', e => { e.preventDefault(); document.execCommand('insertText', false, (e.clipboardData.getData('text/plain') || '').replace(/\s+/g, ' ')); });
      tr.appendChild(td);
    }
    tb.appendChild(tr);
  }
  const i = focusIdx != null ? focusIdx : Math.min(S.cell, m.cells.length - 1);
  const td = tb.querySelector(`td[data-i="${i}"]`);
  if (td) { td.focus(); placeEnd(td); }
}
function placeEnd(el) {
  const r = document.createRange(); r.selectNodeContents(el); r.collapse(false);
  const s = getSelection(); s.removeAllRanges(); s.addRange(r);
}
function tableTyped() {
  clearTimeout(tableTyped.h);
  tableTyped.h = setTimeout(commitTable, 600);
  S.seq++; setSaved('dirty');
  if (S.g.status === 'todo') S.g.status = 'doing';
}
function moveCell(d) {
  const m = S.model;
  const i = Math.max(0, Math.min(m.cells.length - 1, S.cell + d));
  const td = $(`#grid td[data-i="${i}"]`);
  if (td) { td.focus(); placeEnd(td); }
}
function gridOp(op) {
  const m = S.model;
  if (!m) return;
  const c = m.cells[S.cell] || m.cells[0];
  const keep = c;
  const grid = gridOf(m);
  if (op === 'rowabove' || op === 'rowbelow') {
    const at = op === 'rowabove' ? c.r : c.r + c.rs;
    for (const x of m.cells) { if (x.r >= at) x.r++; else if (x.r + x.rs > at) x.rs++; }
    m.R++;
  } else if (op === 'colright' || op === 'colleft') {        // the table is right to left: column 0 is the rightmost
    const at = op === 'colright' ? c.c : c.c + c.cs;
    for (const x of m.cells) { if (x.c >= at) x.c++; else if (x.c + x.cs > at) x.cs++; }
    m.C++;
  } else if (op === 'delrow') {
    if (m.R <= 1) { toast('A table needs one row'); return; }
    const r = c.r;
    m.cells = m.cells.filter(x => !(x.r === r && x.rs === 1));
    for (const x of m.cells) { if (x.r > r) x.r--; else if (x.r <= r && x.r + x.rs > r) x.rs--; }
    m.R--;
  } else if (op === 'delcol') {
    if (m.C <= 1) { toast('A table needs one column'); return; }
    const k = c.c;
    m.cells = m.cells.filter(x => !(x.c === k && x.cs === 1));
    for (const x of m.cells) { if (x.c > k) x.c--; else if (x.c <= k && x.c + x.cs > k) x.cs--; }
    m.C--;
  } else if (op === 'mergeleft') {
    const n = c.c + c.cs < m.C ? grid[c.r][c.c + c.cs] : null;
    if (!n || n.r !== c.r || n.rs !== c.rs) { toast('Cannot merge: the cell on the left has another height'); return; }
    c.cs += n.cs; c.text = norm(c.text + ' ' + n.text);
    m.cells = m.cells.filter(x => x !== n);
  } else if (op === 'mergedown') {
    const n = c.r + c.rs < m.R ? grid[c.r + c.rs][c.c] : null;
    if (!n || n.c !== c.c || n.cs !== c.cs) { toast('Cannot merge: the cell below has another width'); return; }
    c.rs += n.rs; c.text = norm(c.text + ' ' + n.text);
    m.cells = m.cells.filter(x => x !== n);
  } else if (op === 'split') {
    if (c.rs === 1 && c.cs === 1) { toast('This cell is not merged'); return; }
    c.rs = 1; c.cs = 1;
  }
  fillTable(m);
  let target = keep;
  if (op === 'rowabove' || op === 'rowbelow') {
    const at = op === 'rowabove' ? keep.r - 1 : keep.r + keep.rs;     // keep has moved down when a row went above
    target = m.cells.find(x => x.r === at && x.c === 0) || m.cells.find(x => x.r === at) || keep;
  } else if (op === 'colright' || op === 'colleft') {
    const at = op === 'colright' ? keep.c - 1 : keep.c + keep.cs;
    target = m.cells.find(x => x.c === at && x.r === keep.r) || keep;
  }
  const idx = m.cells.indexOf(target);
  S.cell = idx >= 0 ? idx : Math.min(S.cell, m.cells.length - 1);
  drawGrid(S.cell);
  commitTable();
}
function acceptTable() {
  const t = S.g.tables[S.t];
  if (!t || !S.model) return;
  t.html = serialiseTable(S.model);
  t.status = t.html === serialiseTable(parseTable(t.draft_html || '')) && t.draft_html ? 'ok' : 'edited';
  changed(); save(); renderModes();
  const next = S.g.tables.findIndex(x => (x.status || 'todo') === 'todo');
  if (next >= 0) { S.t = next; S.model = null; renderWork(); return; }
  renderWork();
  if (!S.g.lines.some(l => l.status === 'todo')) askDone(false);
  else toast('Table saved ✓');
}
function tableFromDraft() {
  const t = S.g.tables[S.t];
  if (!t) return;
  S.model = parseTable(t.draft_html || ''); S.cell = 0;
  drawGrid(0); commitTable();
}
function delItem(kind) {
  const list = S.g[kind], i = kind === 'tables' ? S.t : S.e;
  if (!list[i]) return;
  modal('Remove this box?', kind === 'tables' ? 'The table box and its grid are removed (the lines inside stay).' : 'The equation box is removed.',
    [['Remove', 'main', () => { list.splice(i, 1); if (kind === 'tables') { S.t = Math.max(0, S.t - 1); S.model = null; } else S.e = Math.max(0, S.e - 1); changed(); renderModes(); renderWork(); }],
     ['Cancel', '', null]]);
}

/* ------------------------------------------------------------------ equations mode */
function renderEquation() {
  const work = $('#work'), g = S.g, q = g.equations[S.e];
  if (!q) {
    work.innerHTML = `<div class="empty">No equations on this page. If there is one, press <b>+ Equation box</b> and drag a box round it.</div>`;
    return;
  }
  work.innerHTML = `
    <div class="lhead"><b>Equation ${S.e + 1} / ${g.equations.length}</b>
      <span class="tag st-${q.status === 'ok' ? 'ok' : q.status === 'edited' ? 'edited' : 'todo'}">${esc(LST[q.status] || q.status || 'to do')}</span>
      <span class="grow"></span>
      <button data-act="eprev">◀ Previous<kbd>Alt+↑</kbd></button><button data-act="enext">Next ▶<kbd>Alt+↓</kbd></button>
      <button data-act="edel">Remove box</button></div>
    <div class="cropbox"><div class="crop" id="ecrop"><div class="fade t"></div><div class="fade b"></div></div></div>
    <textarea id="tex" class="tex" dir="ltr" spellcheck="false" placeholder="LaTeX, e.g. \\frac{a}{b}"></textarea>
    <div class="lab" style="font-size:12px;color:var(--mut);margin-top:.4rem">Draft</div>
    <pre class="draft" id="edraft"></pre>
    <div class="btns">
      <button class="main" data-act="eaccept">✓ Equation correct<kbd>Ctrl+Enter</kbd></button>
      <button data-act="edraft">Take the draft</button>
      <label style="align-self:center"><input type="checkbox" id="edisp" ${q.display !== false ? 'checked' : ''}> on its own line (display)</label>
    </div>
    <div class="legend">LaTeX (amsmath) source, as printed. <kbd>Esc</kbd> back to the saved text.</div>`;
  if (q.box) cropInto($('#ecrop'), q.box, work.clientWidth - 40, window.innerHeight * 0.35, 0.3);
  const tex = $('#tex');
  tex.value = q.latex || q.draft_latex || '';
  $('#edraft').textContent = q.draft_latex || '(none)';
  tex.addEventListener('input', () => { q.latex = tex.value; changed(); });
  tex.addEventListener('focus', () => { S.lastField = tex; });
  $('#edisp').onchange = e => { q.display = e.target.checked; changed(); };
  tex.focus();
  scrollToBox(q.box);
}
function commitEquation() {
  const tex = $('#tex'), q = S.g.equations[S.e];
  if (tex && q && tex.value !== (q.latex || '')) { q.latex = tex.value; changed(); }
}
function goEq(i) {
  const n = S.g.equations.length;
  if (!n) return;
  commitEquation();
  S.e = Math.max(0, Math.min(n - 1, i));
  renderWork();
}
function acceptEq() {
  const q = S.g.equations[S.e], tex = $('#tex');
  if (!q || !tex) return;
  q.latex = tex.value.trim();
  q.status = q.latex === (q.draft_latex || '').trim() && q.latex ? 'ok' : 'edited';
  changed(); save(); renderModes();
  const next = S.g.equations.findIndex(x => (x.status || 'todo') === 'todo');
  if (next >= 0) { S.e = next; renderWork(); return; }
  renderWork();
  if (!S.g.lines.some(l => l.status === 'todo') && !S.g.tables.some(t => (t.status || 'todo') === 'todo')) askDone(false);
  else toast('Equation saved ✓');
}

/* ------------------------------------------------------------------ articles mode */
function syncArticles() {
  const g = S.g;
  for (const a of g.articles)
    a.regions = g.regions.filter(r => r.article === a.id).sort((x, y) => (x.order || 0) - (y.order || 0)).map(r => r.id);
}
function newArticle() {
  const g = S.g;
  const a = {id: nextId('a', g.articles, 1), title: null, regions: []};
  g.articles.push(a); S.art = a.id;
  changed(); renderModes(); renderWork();
}
function delArticle() {
  const g = S.g, a = g.articles.find(a => a.id === S.art);
  if (!a) return;
  for (const r of g.regions) if (r.article === a.id) r.article = null;
  g.articles = g.articles.filter(x => x !== a);
  S.art = g.articles[0]?.id || null;
  changed(); renderModes(); renderWork();
}
function clickRegion(id) {
  const g = S.g;
  if (S.pickTitle) {
    const a = g.articles.find(a => a.id === S.art);
    if (a && lineById(id)) { a.title = id; S.pickTitle = false; changed(); renderWork(); }
    return;
  }
  const r = g.regions.find(r => r.id === id);
  if (!r) return;
  if (S.clicks) {
    if (!S.clicks.done.has(id)) { S.clicks.done.add(id); r.order = ++S.clicks.n; changed(); }
    S.sel = id; renderWork(); return;
  }
  S.sel = id;
  if (S.art) { r.article = r.article === S.art ? null : S.art; syncArticles(); changed(); }
  renderWork();
}
function startClicks() { S.clicks = {n: 0, done: new Set()}; S.pickTitle = false; S.draw = null; drawBoxes(); updateHint(); renderWork(); }
function endClicks() {
  const g = S.g, c = S.clicks;
  S.clicks = null;
  if (c && c.n) {
    const rest = g.regions.filter(r => !c.done.has(r.id)).sort((a, b) => (a.order || 0) - (b.order || 0));
    let n = c.n;
    for (const r of rest) r.order = ++n;
    syncArticles(); changed();
  }
  renderWork();
}
function regionCol(d) {
  const r = S.g.regions.find(r => r.id === S.sel);
  if (!r) return;
  r.column = Math.max(0, (r.column || 0) + d);
  changed(); renderWork();
}
function renderArticles() {
  const work = $('#work'), g = S.g;
  syncArticles();
  const r = g.regions.find(r => r.id === S.sel);
  const lineText = id => { const l = id && lineById(id); return l ? norm(l.text) : ''; };
  work.innerHTML = `
    <div class="lhead"><b>Articles and blocks</b><span class="grow"></span><span>${g.regions.length} regions</span></div>
    <div class="legend" style="margin-top:0">Choose an article (keys <kbd>1</kbd>–<kbd>9</kbd>, <kbd>N</kbd> new), then click its blocks on the page. Click again to take a block out. Numbers on a box: order · column · article.</div>
    <div class="arts">${g.articles.map((a, i) => `<div class="art ${a.id === S.art ? 'on' : ''}" data-art="${esc(a.id)}">
        <span class="sw" style="background:${ART_COL[i % ART_COL.length]}"></span><span class="k">${i + 1}</span>
        <span class="t" title="title line">${esc(lineText(a.title)) || '<i style="color:var(--mut)">no title</i>'}</span>
        <span class="k">${a.regions.length} block${a.regions.length === 1 ? '' : 's'}</span></div>`).join('') || '<div class="empty" style="padding:.3rem 0">No articles yet.</div>'}</div>
    <div class="btns">
      <button data-act="newart">+ New article<kbd>N</kbd></button>
      <button data-act="title" class="${S.pickTitle ? 'on' : ''}" ${S.art ? '' : 'disabled'}>Set title: click a line</button>
      <button data-act="delart" ${S.art ? '' : 'disabled'}>Remove article</button>
    </div>
    <div class="btns">
      <button data-act="clicks" class="${S.clicks ? 'on' : ''}">${S.clicks ? 'Finish order (' + S.clicks.n + ')' : 'Order by clicks'}<kbd>O</kbd></button>
      <button data-act="draw">+ Draw a block</button>
    </div>
    ${r ? `<div class="regbox"><h3 style="margin-top:0">Block ${esc(r.id)}</h3>
      <div class="row"><span>Type</span><select id="rtype">${REGION_TYPES.map(t => `<option ${t === r.type ? 'selected' : ''}>${t}</option>`).join('')}</select></div>
      <div class="row"><span>Column</span><button data-act="colminus">−</button><b>${r.column}</b><button data-act="colplus">+</button>
        <span style="color:var(--mut);font-size:.8rem">1 = rightmost, 0 = across columns</span></div>
      <div class="row"><span>Order</span><b>${r.order}</b></div>
      <div class="row"><span>Article</span><b>${r.article ? 'A' + (g.articles.findIndex(a => a.id === r.article) + 1) : 'none'}</b>
        ${r.article ? '<button data-act="unassign">take out</button>' : ''}</div>
    </div>` : '<div class="empty">Click a block on the page to see its type, column and order.</div>'}`;
  work.querySelectorAll('[data-art]').forEach(el => el.onclick = () => { S.art = el.dataset.art; renderWork(); });
  const sel = $('#rtype');
  if (sel) sel.onchange = () => { r.type = sel.value; changed(); drawBoxes(); };
}
