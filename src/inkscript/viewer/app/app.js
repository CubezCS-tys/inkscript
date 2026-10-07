/* inkscript viewer — the scan with its ALTO words, the JATS article, the two linked, and the XML as written.
   No library. Data comes from data/... (served by `inkscript view`, or .js files in a --static bundle). */
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const enc = p => p.split('/').map(encodeURIComponent).join('/');
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const WIDE = () => window.innerWidth >= 1000;
const HOVER = matchMedia('(hover: hover)').matches;      // no hover cards on touch screens: a tap pins one
const ROLE = {title: ['title', '--r-title'], rubric: ['rubric', '--r-rubric'], author: ['author', '--r-author'],
  sectionHeading: ['heading', '--r-heading'], footnote: ['footnote', '--r-footnote'],
  pageHeader: ['furniture: running head', '--r-furn'], pageFooter: ['furniture: footer', '--r-furn'],
  pageNumber: ['furniture: page number', '--r-furn'], body: ['text', '--r-body']};
const FURNITURE = new Set(['pageHeader', 'pageFooter', 'pageNumber']);
const MARK_WORD = {flagged: 'flagged', corrected: 'corrected', verified: 'verified', agreed: 'agreed'};

/* ------------------------------------------------------------------ data */
const cache = new Map(), pending = {};
window.__put = (path, value) => { const r = pending[path]; delete pending[path]; if (r) r(value); };
function load(path) {
  if (cache.has(path)) return cache.get(path);
  let p;
  if (window.STATIC) {
    p = new Promise((res, rej) => {
      pending[path] = res;
      const s = document.createElement('script');
      s.src = 'data/' + enc(path) + '.js';
      s.onload = () => s.remove();
      s.onerror = () => { delete pending[path]; cache.delete(path); rej(new Error('not in this bundle: ' + path)); };
      document.head.appendChild(s);
    });
  } else {
    p = fetch('data/' + enc(path)).then(r => {
      if (!r.ok) { cache.delete(path); throw new Error(r.status + ' ' + path); }
      return path.endsWith('.xml') ? r.text() : r.json();
    });
  }
  cache.set(path, p);
  return p;
}
const imgURL = (stem, n) => 'data/' + enc(stem) + '/page-' + n + '.png';

/* ------------------------------------------------------------------ state */
const prefs = (() => { try { return JSON.parse(localStorage.getItem('inkscript-view') || '{}'); } catch { return {}; } })();
const S = Object.assign({tint: {flag: true, corr: true, ver: false}, lines: false, blocks: false, roles: false, zoom: 1},
  {tint: prefs.tint || {flag: true, corr: true, ver: false}, lines: !!prefs.lines, blocks: !!prefs.blocks,
   roles: !!prefs.roles, zoom: prefs.zoom || 1});
S.stem = null; S.doc = null; S.view = null; S.sel = null; S.words = new Map(); S.pageData = new Map();
S.drawn = new Set(); S.xml = {which: 'alto'};
function savePrefs() {
  try { localStorage.setItem('inkscript-view', JSON.stringify({tint: S.tint, lines: S.lines, blocks: S.blocks, roles: S.roles, zoom: S.zoom})); } catch {}
}

/* ------------------------------------------------------------------ theme */
(function theme() {
  try { const t = localStorage.getItem('inkscript-theme'); if (t) document.documentElement.dataset.theme = t; } catch {}
  $('#theme').onclick = () => {
    const cur = document.documentElement.dataset.theme ||
      (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const nxt = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = nxt;
    try { localStorage.setItem('inkscript-theme', nxt); } catch {}
  };
})();

function toast(msg, ms = 3200) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, ms);
}

/* ------------------------------------------------------------------ routing: #/  #/doc/<id>/<view>?w=<word> */
function parseHash() {
  const h = location.hash.replace(/^#/, '') || '/';
  const [path, q] = h.split('?');
  return {parts: path.split('/').filter(Boolean).map(decodeURIComponent), params: new URLSearchParams(q || '')};
}
function docHash(stem, view, w) {
  return '#/doc/' + encodeURIComponent(stem) + '/' + view + (w ? '?w=' + encodeURIComponent(w) : '');
}
async function route() {
  const {parts, params} = parseHash();
  hidePop(true);
  if (parts[0] === 'doc' && parts[1]) {
    let view = parts[2] || (WIDE() ? 'both' : 'page');
    if (view === 'both' && !WIDE()) view = 'page';
    await openDoc(parts[1], view);
    const w = params.get('w');
    if (w && w !== S.sel) selectWord(w, 'url');
  } else showPicker();
}
window.addEventListener('hashchange', route);
window.addEventListener('resize', () => { if (S.view === 'both' && !WIDE()) goView('page'); });

function goView(view) { location.hash = docHash(S.stem, view, S.sel); }

/* ------------------------------------------------------------------ picker */
let pickerSort = {k: 'id', dir: 1};
async function showPicker() {
  S.stem = null; S.view = null;
  $('#views').hidden = true; $('#doctitle').textContent = '';
  document.title = 'inkscript viewer';
  const main = $('#main');
  main.innerHTML = '<div class="picker"><div class="inner"><div class="loading">reading the documents…</div></div></div>';
  let idx;
  try { idx = await load('index.json'); } catch (e) { main.innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; return; }
  const inner = $('.picker .inner');
  const docs = idx.docs;
  const tf = docs.reduce((a, d) => a + d.flagged, 0), tp = docs.reduce((a, d) => a + d.pages, 0);
  inner.innerHTML = `<h1>${docs.length} document${docs.length === 1 ? '' : 's'}</h1>
    <p class="sub">${tp.toLocaleString()} pages · ${tf.toLocaleString()} flagged words · from <code>${esc(idx.out_dir)}</code></p>
    <input type="search" id="q" placeholder="filter: title, author, journal, id…" autocomplete="off">
    <table class="docs"><thead><tr>
      <th data-k="title">Title · authors</th><th data-k="journal">Journal</th><th data-k="year">Year</th>
      <th data-k="pages">Pages</th><th data-k="flagged">Flagged</th><th data-k="corrected">Corrected</th>
      <th data-k="quotations">Quran</th><th data-k="id">Id</th></tr></thead><tbody></tbody></table>`;
  const tbody = $('tbody', inner), q = $('#q', inner);
  const draw = () => {
    const f = q.value.trim().toLowerCase();
    const {k, dir} = pickerSort;
    const rows = docs.filter(d => !f || [d.title, d.journal, d.id, d.year, ...(d.authors || [])].join(' ').toLowerCase().includes(f))
      .sort((a, b) => (a[k] > b[k] ? 1 : a[k] < b[k] ? -1 : 0) * dir);
    tbody.innerHTML = rows.map(d => `<tr class="row" data-id="${esc(d.id)}">
      <td class="t">${esc(d.title) || '<span class="au">(no title found)</span>'}<span class="au">${esc((d.authors || []).join('، '))}</span></td>
      <td dir="auto">${d.journal ? esc(d.journal) : `<span class="au">${esc(d.journal_id)}</span>`}</td><td class="n" data-l="year">${esc(d.year)}</td>
      <td class="n" data-l="pages">${d.pages}</td>
      <td class="n" data-l="flagged"><span class="pill ${d.flagged ? 'f' : 'z'}">${d.flagged}</span></td>
      <td class="n" data-l="corrected"><span class="pill ${d.corrected ? 'c' : 'z'}">${d.corrected}</span></td>
      <td class="n" data-l="Quran">${d.quotations || ''}</td><td class="id">${esc(d.id)}</td></tr>`).join('');
    inner.querySelectorAll('th').forEach(th => th.classList.toggle('sorted', th.dataset.k === k));
  };
  q.oninput = draw;
  inner.querySelector('thead').onclick = e => {
    const k = e.target.closest('th')?.dataset.k; if (!k) return;
    pickerSort = {k, dir: pickerSort.k === k ? -pickerSort.dir : (['flagged', 'pages', 'corrected', 'quotations'].includes(k) ? -1 : 1)};
    draw();
  };
  tbody.onclick = e => { const tr = e.target.closest('tr.row'); if (tr) location.hash = docHash(tr.dataset.id, WIDE() ? 'both' : 'page'); };
  draw();
  q.focus();
}

/* ------------------------------------------------------------------ the document */
async function openDoc(stem, view) {
  if (S.stem !== stem) {
    S.stem = stem; S.sel = null; S.words = new Map(); S.pageData = new Map(); S.drawn = new Set();
    S.article = null; S.xml = {which: 'alto', built: {}};
    $('#main').innerHTML = '<div class="loading">opening ' + esc(stem) + '…</div>';
    try { S.doc = await load(stem + '/doc.json'); }
    catch (e) { $('#main').innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; return; }
    if (S.stem !== stem) return;
    $('#doctitle').textContent = S.doc.title || stem;
    $('#doctitle').title = stem;
    document.title = (S.doc.title || stem) + ' · inkscript';
    buildDocView();
  }
  setView(view);
}

function buildDocView() {
  const d = S.doc, main = $('#main');
  main.innerHTML = `<div class="docview">
   <section class="pane pagep">
    <div class="bar">
      <span class="grp">page <input class="pg" id="pgno" inputmode="numeric" value="1"> / ${d.pages}
        <button class="btn" id="zout" title="smaller">−</button><button class="btn" id="zin" title="larger">+</button></span>
      <span class="grp marks">
        <button class="chip flag" data-t="flag"><span class="dot"></span>flagged ${d.flagged}</button>
        <button class="chip corr" data-t="corr"><span class="dot"></span>corrected ${d.corrected}</button>
        <button class="chip ver" data-t="ver"><span class="dot"></span>verified ${d.verified}</button></span>
      <span class="grp">
        <button class="chip lines" data-o="lines"><span class="dot"></span>lines</button>
        <button class="chip blocks" data-o="blocks"><span class="dot"></span>blocks</button>
        <button class="chip roles" data-o="roles"><span class="dot"></span>roles</button></span>
    </div>
    <div class="legend">${['title', 'rubric', 'author', 'sectionHeading', 'footnote', 'pageNumber', 'body'].map(r =>
      `<span><i style="border-color:var(${ROLE[r][1]})"></i>${ROLE[r][0].replace('furniture: page number', 'furniture (heads, footers, page numbers)')}</span>`).join('')}</div>
    <div class="scroll" id="pscroll"><div class="pages" id="pages">${d.page_list.map(p => `
      <div class="pg" id="pg-${p.n}" data-n="${p.n}"><div class="ph"><span>page ${p.n}</span>${p.printed ? `<span>printed ${esc(p.printed)}</span>` : ''}${p.born ? '<span>born-digital text</span>' : ''}</div>
      <div class="sheet" style="aspect-ratio:${p.w}/${p.h}">${d.has_pdf ? '' : '<div class="noimg">no PDF beside the XML to draw this page from</div>'}</div></div>`).join('')}
    </div></div>
   </section>
   <section class="pane artp">
    <div class="bar">
      <span class="grp marks">
        <button class="chip flag" data-t="flag"><span class="dot"></span>flagged</button>
        <button class="chip corr" data-t="corr"><span class="dot"></span>corrected</button>
        <button class="chip ver" data-t="ver"><span class="dot"></span>verified</button></span>
      <span class="sp"></span><span class="xmlinfo" id="artinfo"></span>
    </div>
    <div class="scroll" id="ascroll"><div class="art" id="art"><div class="loading">…</div></div></div>
   </section>
   <section class="pane xmlp">
    <div class="bar xmlbar">
      <span class="grp"><button class="chip" data-x="alto">ALTO</button><button class="chip" data-x="jats">JATS</button></span>
      <span class="grp">go to id <input class="pg" id="xid" style="width:8em" placeholder="p1w0002"><button class="btn" id="xgo">go</button></span>
      <span class="grp"><button class="btn" id="xopen">open all</button><button class="btn" id="xclose">close all</button></span>
      <span class="sp"></span><a class="xmlinfo" id="xraw" target="_blank">raw file</a>
    </div>
    <div class="scroll" id="xscroll"><div class="xml" id="xml"></div></div>
   </section></div>`;
  applyToggles();
  main.querySelectorAll('.chip[data-t]').forEach(b => b.onclick = () => { S.tint[b.dataset.t] = !S.tint[b.dataset.t]; applyToggles(); savePrefs(); });
  main.querySelectorAll('.chip[data-o]').forEach(b => b.onclick = () => {
    const o = b.dataset.o; S[o] = !S[o];
    if (o === 'roles' && S.roles) S.blocks = false;
    if (o === 'blocks' && S.blocks) S.roles = false;
    applyToggles(); savePrefs();
  });
  $('#zin').onclick = () => zoom(1); $('#zout').onclick = () => zoom(-1);
  const pg = $('#pgno');
  pg.onchange = () => { const n = Math.max(1, Math.min(S.doc.pages, parseInt(pg.value, 10) || 1)); scrollToPage(n); };
  setupPages();
  setupArticleEvents();
  setupXml();
  applyZoom();
}

function applyToggles() {
  const dv = $('.docview'); if (!dv) return;
  dv.classList.toggle('tint-flag', S.tint.flag); dv.classList.toggle('tint-corr', S.tint.corr);
  dv.classList.toggle('tint-ver', S.tint.ver);
  dv.classList.toggle('show-lines', S.lines); dv.classList.toggle('show-blocks', S.blocks);
  dv.classList.toggle('show-roles', S.roles);
  dv.querySelectorAll('.chip[data-t]').forEach(b => b.classList.toggle('on', !!S.tint[b.dataset.t]));
  dv.querySelectorAll('.chip[data-o]').forEach(b => b.classList.toggle('on', !!S[b.dataset.o]));
}

function setView(view) {
  S.view = view;
  const dv = $('.docview'); if (!dv) return;
  document.querySelectorAll('#views button').forEach(b => b.classList.toggle('on', b.dataset.view === view));
  $('#views').hidden = false;
  dv.classList.toggle('both', view === 'both');
  $('.pagep').hidden = !(view === 'page' || view === 'both');
  $('.artp').hidden = !(view === 'article' || view === 'both');
  $('.xmlp').hidden = view !== 'xml';
  if (view === 'article' || view === 'both') ensureArticle();
  if (view === 'xml') showXml(S.xml.which);
}
document.querySelectorAll('#views button').forEach(b => b.onclick = () => goView(b.dataset.view));

/* ------------------------------------------------------------------ page view */
const ZOOMS = [0.5, 0.75, 1, 1.5, 2, 3];
function zoom(dir) {
  const cur = currentPage();
  let i = ZOOMS.indexOf(S.zoom); if (i < 0) i = 2;
  S.zoom = ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, i + dir))];
  applyZoom(); savePrefs(); scrollToPage(cur, true);
}
function applyZoom() {
  const pages = $('#pages'); if (!pages) return;
  pages.style.width = S.zoom > 1 ? (S.zoom * 100) + '%' : '100%';
  pages.querySelectorAll('.pg').forEach(p => { p.style.maxWidth = S.zoom > 1 ? 'none' : (900 * S.zoom) + 'px'; });
}

let io;
function setupPages() {
  const scroll = $('#pscroll');
  // a page is drawn once it has stayed near the view for a moment, so a long jump does not load every page on the way
  const near = new Set();
  io = new IntersectionObserver(es => es.forEach(e => {
    const n = +e.target.dataset.n;
    if (e.isIntersecting) { near.add(n); setTimeout(() => { if (near.has(n)) showPage(n); }, 150); }
    else near.delete(n);
  }), {root: scroll, rootMargin: '800px 0px'});
  scroll.querySelectorAll('.pg').forEach(p => io.observe(p));
  let tick = 0;
  scroll.addEventListener('scroll', () => {
    if (tick) return;
    tick = requestAnimationFrame(() => { tick = 0; const n = currentPage(); const i = $('#pgno'); if (i && document.activeElement !== i) i.value = n; });
  }, {passive: true});
  const pages = $('#pages');
  pages.addEventListener('mouseover', e => {
    const r = e.target.closest('rect.w'); if (!r || popPinned || !HOVER) return;
    showPop(r.dataset.w, r.getBoundingClientRect(), false);
  });
  pages.addEventListener('mouseout', e => { if (e.target.closest('rect.w') && !popPinned) hidePop(); });
  pages.addEventListener('click', e => {
    const r = e.target.closest('rect.w');
    if (r) { selectWord(r.dataset.w, 'page'); return; }
    const b = e.target.closest('rect.bk');
    if (b) { selectBlock(b.dataset.b, 'page'); return; }
    hidePop(true);
  });
}

function currentPage() {
  const scroll = $('#pscroll'); if (!scroll) return 1;
  const mid = scroll.getBoundingClientRect().top + scroll.clientHeight / 3;
  let best = 1;
  for (const p of scroll.querySelectorAll('.pg')) { if (p.getBoundingClientRect().top <= mid) best = +p.dataset.n; else break; }
  return best;
}
function scrollToPage(n, instant) {
  const el = $('#pg-' + n); if (!el) return;
  const scroll = $('#pscroll');
  const far = Math.abs(n - currentPage()) > 2;
  scroll.scrollTo({top: el.offsetTop - 8, behavior: instant || far ? 'auto' : 'smooth'});
}

async function pageData(n) {
  if (S.pageData.has(n)) return S.pageData.get(n);
  const pd = await load(S.stem + '/page-' + n + '.json');
  if (!S.pageData.has(n)) {
    S.pageData.set(n, pd);
    for (const b of pd.blocks) for (const l of b.lines) for (const w of l.w) S.words.set(w.id, {w, page: n, block: b, line: l});
  }
  return S.pageData.get(n);
}

async function showPage(n) {
  if (S.drawn.has(n)) return;
  S.drawn.add(n);
  const stem = S.stem;
  const sheet = $('#pg-' + n + ' .sheet');
  if (S.doc.has_pdf) {
    const img = new Image(); img.alt = 'page ' + n; img.decoding = 'async'; img.src = imgURL(stem, n);
    img.onerror = () => { sheet.insertAdjacentHTML('afterbegin', '<div class="noimg">page image could not be drawn</div>'); };
    sheet.prepend(img);
  }
  let pd;
  try { pd = await pageData(n); } catch (e) { S.drawn.delete(n); return; }
  if (S.stem !== stem) return;
  sheet.insertAdjacentHTML('beforeend', overlay(pd));
  if (S.sel && S.words.get(S.sel)?.page === n) markSelected(S.sel);
}

function overlay(pd) {
  const out = [`<svg viewBox="0 0 ${pd.w} ${pd.h}" preserveAspectRatio="none">`];
  for (const b of pd.blocks) {
    const [x, y, w, h] = b.b, role = ROLE[b.role] || ROLE.body;
    out.push(`<rect class="bk" data-b="${b.id}" x="${x - 6}" y="${y - 6}" width="${w + 12}" height="${h + 12}" style="--rc:var(${role[1]});--rf:transparent"/>`);
    if (b.role !== 'body') out.push(`<text class="rl" x="${x + w + 6}" y="${Math.max(24, y - 12)}" text-anchor="end" style="fill:var(${role[1]})">${esc(role[0])}</text>`);
    for (const l of b.lines) {
      const [lx, ly, lw, lh] = l.b;
      out.push(`<rect class="ln" x="${lx}" y="${ly}" width="${lw}" height="${lh}"/>`);
      for (const wd of l.w) {
        const [wx, wy, ww, wh] = wd.b;
        out.push(`<rect class="w${wd.m ? ' m-' + wd.m : ''}" data-w="${wd.id}" x="${wx}" y="${wy}" width="${ww}" height="${wh}" rx="4"/>`);
      }
    }
  }
  out.push('</svg>');
  return out.join('');
}

async function scrollPageToWord(id, flash = true) {
  const n = pageOf(id); if (!n) return false;
  await pageData(n);
  if (!S.drawn.has(n)) { await showPage(n); }
  let r = document.querySelector(`#pg-${n} rect.w[data-w="${id}"]`);
  if (!r) { await new Promise(res => setTimeout(res, 50)); r = document.querySelector(`#pg-${n} rect.w[data-w="${id}"]`); }
  if (!r) return false;
  centreIn($('#pscroll'), r);
  if (flash) { r.classList.remove('flash'); void r.getBBox(); r.classList.add('flash'); }
  return true;
}
function centreIn(scroll, el) {
  const sr = scroll.getBoundingClientRect(), er = el.getBoundingClientRect();
  const dy = er.top - sr.top - sr.height / 2 + er.height / 2;
  scroll.scrollBy({top: dy, left: er.left - sr.left - sr.width / 2 + er.width / 2,
    behavior: Math.abs(dy) > 3 * sr.height ? 'auto' : 'smooth'});
}
const pageOf = id => { const m = /^p(\d+)[wb]/.exec(id || ''); return m ? +m[1] : 0; };

/* ------------------------------------------------------------------ article view */
async function ensureArticle() {
  if (S.article) return S.article;
  const stem = S.stem;
  S.article = load(stem + '/article.json').then(a => {
    if (S.stem !== stem) return a;
    $('#art').innerHTML = a.html;
    $('#artinfo').textContent = a.words ? `${a.linked.toLocaleString()} of ${a.words.toLocaleString()} words linked to the page` : '';
    if (S.sel) markSelected(S.sel);
    return a;
  }).catch(e => { $('#art').innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; });
  return S.article;
}

function setupArticleEvents() {
  const art = $('#art');
  art.addEventListener('mouseover', e => {
    const s = e.target.closest('.w[data-w]'); if (!s || popPinned || !HOVER) return;
    showPop(s.dataset.w, s.getBoundingClientRect(), false);
  });
  art.addEventListener('mouseout', e => { if (e.target.closest('.w[data-w]') && !popPinned) hidePop(); });
  art.addEventListener('click', e => {
    const fr = e.target.closest('a.fnref');
    if (fr) { e.preventDefault(); const t = $('#j-' + CSS.escape(fr.dataset.rid)); if (t) { centreIn($('#ascroll'), t); flashEl(t); } return; }
    const fl = e.target.closest('a.fnlabel');
    if (fl) { e.preventDefault(); const x = art.querySelector(`a.fnref[data-rid="${CSS.escape(fl.dataset.back)}"]`); if (x) { centreIn($('#ascroll'), x); flashEl(x); } return; }
    if (e.target.closest('a[href^="http"]')) return;
    const s = e.target.closest('.w[data-w]');
    if (s) { selectWord(s.dataset.w, 'article'); return; }
    const b = e.target.closest('[data-b]');
    if (b) { selectBlock(b.dataset.b.split(' ')[0], 'article', b.dataset.b.split(' ')); return; }
    const t = e.target.closest('[data-words]');
    if (t) { selectWord(t.dataset.words.split(' ')[0], 'article'); return; }
    hidePop(true);
  });
}
function flashEl(el) { el.classList.remove('blk-flash'); void el.offsetWidth; el.classList.add('blk-flash'); }

async function scrollArticleTo(id) {
  await ensureArticle();
  const art = $('#art');
  let el = art.querySelector(`.w[data-w="${CSS.escape(id)}"]`);
  if (el) { centreIn($('#ascroll'), el); el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); return 'word'; }
  el = art.querySelector(`[data-words~="${CSS.escape(id)}"]`);
  const info = S.words.get(id);
  if (!el && info) el = art.querySelector(`[data-b~="${CSS.escape(info.block.id)}"]`);
  if (el) { centreIn($('#ascroll'), el); flashEl(el); return 'block'; }
  return 'none';
}

/* ------------------------------------------------------------------ selection and links */
function markSelected(id) {
  document.querySelectorAll('.sel').forEach(e => e.classList.remove('sel'));
  if (!id) return;
  document.querySelectorAll(`rect.w[data-w="${CSS.escape(id)}"], #art .w[data-w="${CSS.escape(id)}"]`).forEach(e => e.classList.add('sel'));
}

async function selectWord(id, from) {
  if (!pageOf(id)) return;
  S.sel = id;
  history.replaceState(null, '', docHash(S.stem, S.view, id));
  try { await pageData(pageOf(id)); } catch { toast('no such word: ' + id); return; }
  markSelected(id);
  const pageShown = S.view === 'page' || S.view === 'both', artShown = S.view === 'article' || S.view === 'both';
  if (pageShown && from !== 'page') await scrollPageToWord(id);
  let where = null;
  if (artShown && from !== 'article') where = await scrollArticleTo(id);
  if (where === 'none') notInArticle(id);
  const anchor = (from === 'article' ? $(`#art .w[data-w="${CSS.escape(id)}"]`) : null) ||
    (pageShown ? $(`rect.w[data-w="${CSS.escape(id)}"]`) : null) || $(`#art .w[data-w="${CSS.escape(id)}"]`);
  let wait = from === 'page' || from === 'article' ? 0 : 450;
  if (anchor && innerWidth <= 620) {             // on a phone the card is a sheet at the bottom: lift the word above it
    const sc = anchor.closest('.scroll'), r = anchor.getBoundingClientRect();
    if (sc && r.top > innerHeight * 0.35) { sc.scrollBy({top: r.top - innerHeight * 0.25, behavior: 'smooth'}); wait = Math.max(wait, 400); }
  }
  if (S.view !== 'xml') setTimeout(() => showPop(id, anchor ? anchor.getBoundingClientRect() : null, true), wait);
}

function notInArticle(id) {
  const info = S.words.get(id); if (!info) return;
  const r = info.block.role;
  toast(FURNITURE.has(r) ? `Not in the article: ${ROLE[r][0]} (page furniture stays in the ALTO file only).`
    : 'This word has no place in the article text (see the ALTO file).');
}

async function selectBlock(bid, from, all) {
  const ids = all || [bid];
  document.querySelectorAll('rect.bk.hl').forEach(e => e.classList.remove('hl'));
  const pageShown = S.view === 'page' || S.view === 'both', artShown = S.view === 'article' || S.view === 'both';
  for (const b of ids) {
    const n = pageOf(b); if (!n) continue;
    await pageData(n); if (!S.drawn.has(n)) await showPage(n);
    document.querySelectorAll(`rect.bk[data-b="${CSS.escape(b)}"]`).forEach(e => e.classList.add('hl'));
  }
  if (from === 'article' && pageShown) {
    const r = $(`rect.bk[data-b="${CSS.escape(ids[0])}"]`); if (r) centreIn($('#pscroll'), r);
  }
  if (from === 'page') {
    if (artShown) {
      await ensureArticle();
      const el = $(`#art [data-b~="${CSS.escape(bid)}"]`);
      if (el) { centreIn($('#ascroll'), el); flashEl(el); }
      else {
        const b = [...S.pageData.get(pageOf(bid))?.blocks || []].find(x => x.id === bid);
        toast(b && FURNITURE.has(b.role) ? `Not in the article: ${ROLE[b.role][0]}.` : 'This block has no element in the article.');
      }
    } else toast('block ' + bid + (S.view === 'page' ? ' — open “Both” or “Article” to see it in the article' : ''));
  }
}

/* ------------------------------------------------------------------ the word card */
let popPinned = false;
function hidePop(force) {
  if (popPinned && !force) return;
  popPinned = false; const p = $('#pop'); p.hidden = true; p.classList.remove('pinned');
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') hidePop(true); });

async function showPop(id, rect, pin) {
  let info = S.words.get(id);
  if (!info) { try { await pageData(pageOf(id)); } catch { return; } info = S.words.get(id); }
  if (!info) return;
  if (!pin && popPinned) return;
  const {w, block, line, page} = info, tags = S.doc.tags || {};
  const mark = w.m || '';
  const why = (w.why || []).map(r => tags['why.' + r] || {label: r});
  const conf = w.c;
  const h = [];
  if (pin) h.push('<button class="x" title="close (Esc)">×</button>');
  h.push(`<div class="wd">${esc(w.t)}</div>`);
  if (mark) {
    let desc = (tags['trust.' + mark] || {}).desc || '';
    if (mark === 'agreed') desc = desc.split('. ')[0] + '.';     // the usual case: one line is enough
    h.push(`<span class="badge ${mark}">${MARK_WORD[mark] || mark}</span><div class="desc">${esc(desc)}</div>`);
  }
  if (why.length) h.push('<b>why</b><ul>' + why.map(r => `<li>${esc(r.label)}</li>`).join('') + '</ul>');
  if (conf != null) h.push(`<div class="conf">Azure's confidence <span class="bar_"><i class="${conf < 0.8 ? 'lo' : ''}" style="width:${Math.round(conf * 100)}%"></i></span> ${conf.toFixed(2)}</div>`);
  for (const [purpose, text] of w.alt || []) {
    if (purpose === 'azure-reading' && mark === 'corrected')
      h.push(`<div class="alt">corrected: <span class="ar">${esc(text)}</span> → <span class="ar">${esc(w.t)}</span><br><small>Azure's reading kept as ALTERNATIVE; the ink was judged to show the new one.</small></div>`);
    else if (purpose === 'azure-reading')
      h.push(`<div class="alt">Azure read <span class="ar">${esc(text)}</span><br><small>the PDF carries the other reading (page 1 read again by Gemini)</small></div>`);
    else if (purpose === 'quran-verse')
      h.push(`<div class="alt">the verse has <span class="ar">${esc(text)}</span></div>`);
    else h.push(`<div class="alt">${esc(purpose)}: <span class="ar">${esc(text)}</span></div>`);
  }
  if (w.q && tags[w.q]) {
    const q = tags[w.q];
    h.push(`<div>Quran: <a href="${esc(q.uri)}" target="_blank" rel="noopener" class="ar">${esc(q.label)}</a> — ${esc(q.desc || '')}</div>`);
  }
  const role = ROLE[block.role] || ROLE.body;
  h.push(`<div class="ids">${esc(w.id)} · page ${page} · ${esc(role[0])} (${esc(block.id)}) · line ${esc(line.id)}<br>box ${w.b.join(', ')} px` +
    (w.g ? ` · glyph${w.g.length > 1 ? 's' : ''} #${w.g.join(', #')} in shapes.json` : '') + '</div>');
  if (pin) {
    const acts = [];
    if (S.view !== 'page' && S.view !== 'both') acts.push('<button data-go="page">on the page</button>');
    if (S.view !== 'article' && S.view !== 'both') acts.push('<button data-go="article">in the article</button>');
    acts.push('<button data-go="alto">ALTO XML</button>');
    acts.push('<button data-go="jats">JATS XML</button>');
    h.push('<div class="acts">' + acts.join('') + '</div>');
  }
  const p = $('#pop');
  p.innerHTML = h.join('');
  p.hidden = false;
  popPinned = !!pin;
  p.classList.toggle('pinned', !!pin);
  place(p, rect);
  if (pin) {
    p.querySelector('.x').onclick = () => hidePop(true);
    p.querySelectorAll('[data-go]').forEach(b => b.onclick = () => go(b.dataset.go, id, block));
  }
}

function place(p, rect) {
  p.style.left = '0px'; p.style.top = '0px';
  const pw = p.offsetWidth, ph = p.offsetHeight, vw = innerWidth, vh = innerHeight;
  if (!rect) { p.style.left = (vw - pw) / 2 + 'px'; p.style.top = (vh - ph - 16) + 'px'; return; }
  let x = rect.left + rect.width / 2 - pw / 2, y = rect.bottom + 10;
  if (y + ph > vh - 8) y = rect.top - ph - 10;
  if (y < 56) y = Math.min(vh - ph - 8, rect.bottom + 10);
  x = Math.max(8, Math.min(vw - pw - 8, x));
  p.style.left = x + 'px'; p.style.top = Math.max(8, y) + 'px';
}

async function go(where, id, block) {
  hidePop(true);
  if (where === 'page' || where === 'article') {
    location.hash = docHash(S.stem, where, id);
    await new Promise(r => setTimeout(r, 60));
    if (where === 'page') await scrollPageToWord(id);
    else if (await scrollArticleTo(id) === 'none') notInArticle(id);
    return;
  }
  S.xml.which = where;
  S.xml.goto = where === 'alto' ? id : (block.href || block.id);
  location.hash = docHash(S.stem, 'xml', id);
}

/* ------------------------------------------------------------------ XML: the files as written, collapsible */
function setupXml() {
  document.querySelectorAll('.xmlbar .chip[data-x]').forEach(b => b.onclick = () => { S.xml.which = b.dataset.x; showXml(b.dataset.x); });
  const goId = () => { const v = $('#xid').value.trim(); if (v) xmlGoto(v); };
  $('#xgo').onclick = goId;
  $('#xid').onkeydown = e => { if (e.key === 'Enter') goId(); };
  $('#xopen').onclick = () => xmlAll(true);
  $('#xclose').onclick = () => xmlAll(false);
}

async function showXml(which) {
  document.querySelectorAll('.xmlbar .chip[data-x]').forEach(b => b.classList.toggle('on', b.dataset.x === which));
  $('#xraw').href = 'data/' + enc(S.stem + '/' + which + '.xml') + (window.STATIC ? '.js' : '');
  $('#xraw').textContent = S.stem + '.' + which + '.xml';
  const box = $('#xml');
  const st = S.xml;
  if (st.shown !== which) {
    box.innerHTML = '<div class="loading">reading ' + which.toUpperCase() + '…</div>';
    let text;
    try { text = await load(S.stem + '/' + which + '.xml'); } catch (e) { box.innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; return; }
    if (S.xml !== st) return;
    const doc = new DOMParser().parseFromString(text, 'application/xml');
    st.doc = doc; st.map = new WeakMap(); st.shown = which;
    box.innerHTML = '';
    if (doc.doctype) box.insertAdjacentHTML('beforeend', `<div class="more">&lt;!DOCTYPE ${esc(doc.doctype.name)} PUBLIC "${esc(doc.doctype.publicId)}" "${esc(doc.doctype.systemId)}"&gt;</div>`);
    const rootEl = xmlEl(doc.documentElement);
    box.appendChild(rootEl);
    openEl(rootEl, 2);
    $('#xid').placeholder = which === 'alto' ? 'p1w0002' : 'p1b4';
  }
  if (st.goto) { const g = st.goto; st.goto = null; $('#xid').value = g; xmlGoto(g); }
}

function attrs(node) {
  let s = '';
  for (const a of node.attributes) s += ` <span class="an">${esc(a.name)}</span>=<span class="av">"${esc(a.value)}"</span>`;
  return s;
}
const kidsOf = node => [...node.childNodes].filter(c => c.nodeType === 1 || ((c.nodeType === 3 || c.nodeType === 4) && c.nodeValue.trim()) || c.nodeType === 8);

function xmlEl(node) {
  const d = document.createElement('div');
  d.className = 'el'; d._x = node; S.xml.map.set(node, d);
  const kids = kidsOf(node), tag = esc(node.tagName);
  if (!kids.length) { d.innerHTML = `<span class="hd"><span class="tg">&lt;${tag}</span>${attrs(node)}<span class="tg">/&gt;</span></span>`; return d; }
  if (kids.every(k => k.nodeType === 3 || k.nodeType === 4) || (!node.children.length && kids.length)) {
    d.innerHTML = `<span class="hd"><span class="tg">&lt;${tag}</span>${attrs(node)}<span class="tg">&gt;</span><span class="tx" dir="auto">${esc(node.textContent.trim())}</span><span class="tg">&lt;/${tag}&gt;</span></span>`;
    return d;
  }
  const n = node.children.length;
  d.innerHTML = `<span class="hd" data-t="1"><span class="tw">▸</span><span class="tg">&lt;${tag}</span>${attrs(node)}<span class="tg">&gt;</span><span class="more"> ${n} element${n === 1 ? '' : 's'} …&lt;/${tag}&gt;</span></span>`;
  d._open = false;
  d.firstChild.onclick = () => toggleEl(d);
  return d;
}
function toggleEl(d, want) {
  const open = want ?? !d._open;
  if (open === d._open) return;
  d._open = open;
  const hd = d.firstChild;
  hd.querySelector('.tw').textContent = open ? '▾' : '▸';
  hd.querySelector('.more').hidden = open;
  if (open && !d._kids) {
    const box = document.createElement('div');
    const frag = document.createDocumentFragment();
    for (const k of kidsOf(d._x)) {
      if (k.nodeType === 1) frag.appendChild(xmlEl(k));
      else {
        const t = document.createElement('div'); t.className = 'el';
        t.innerHTML = k.nodeType === 8 ? `<span class="more">&lt;!--${esc(k.nodeValue)}--&gt;</span>` : `<span class="tx" dir="auto">${esc(k.nodeValue.trim())}</span>`;
        frag.appendChild(t);
      }
    }
    box.appendChild(frag);
    const close = document.createElement('div');
    close.innerHTML = `<span class="tg">&lt;/${esc(d._x.tagName)}&gt;</span>`;
    box.appendChild(close);
    d._kids = box; d.appendChild(box);
  }
  if (d._kids) d._kids.hidden = !open;
}
function openEl(d, depth) {
  if (depth <= 0 || !d.firstChild?.dataset?.t) return;
  toggleEl(d, true);
  for (const c of d._kids.children) if (c._x) openEl(c, depth - 1);
}
function xmlAll(open) {
  const root = $('#xml > .el:last-of-type') || $('#xml > .el'); if (!root) return;
  if (!open) { toggleEl(root, false); return; }
  const count = S.xml.doc.getElementsByTagName('*').length;
  if (count > 6000) { toast(`${count.toLocaleString()} elements: opening three levels; use “go to id” for the rest.`); openEl(root, 3); return; }
  openEl(root, 99);
}
function xmlGoto(id) {
  const st = S.xml; if (!st.doc) return;
  const node = st.doc.querySelector(`[ID="${CSS.escape(id)}"], [id="${CSS.escape(id)}"]`);
  if (!node) { toast('no element with id ' + id + ' in this file'); return; }
  const chain = []; for (let n = node; n && n.nodeType === 1; n = n.parentNode) chain.unshift(n);
  for (const n of chain.slice(0, -1)) { const d = st.map.get(n); if (d) toggleEl(d, true); }
  const d = st.map.get(node); if (!d) return;
  if (d.firstChild?.dataset?.t) toggleEl(d, true);
  document.querySelectorAll('.xml .hit').forEach(e => e.classList.remove('hit'));
  d.classList.add('hit');
  const sc = $('#xscroll');
  sc.scrollTo({top: d.offsetTop - sc.clientHeight / 3, behavior: 'smooth'});
}

route();
