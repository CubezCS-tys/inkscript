/* Experiment 43: the correction tool, version 1 (correct43.py builds the pages). For the owner alone, in the browser.
   Every correction is a patch with source "person" (patches43.py format), keyed to Azure's line ids; kept in this
   browser (localStorage) and exported as one JSON file for `correct43.py import`. No server, no model. */
(function () {
  'use strict';
  var PREFIX = 'inkscript.correct.v1:';
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } }
  function lsKeys(run) {
    var o = [];
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && k.indexOf(PREFIX + run + ':') === 0) o.push(k);
      }
    } catch (e) { /* storage blocked: nothing kept */ }
    return o;
  }
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === 'text') e.textContent = attrs[k];
      else if (k === 'on') for (var ev in attrs.on) e.addEventListener(ev, attrs.on[ev]);
      else if (attrs[k] !== null && attrs[k] !== undefined && attrs[k] !== false) e.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function download(name, obj) {
    var b = new Blob([JSON.stringify(obj, null, 1)], { type: 'application/json' });
    var a = el('a', { href: URL.createObjectURL(b), download: name });
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function exportAll(run) {
    var arts = {}, n = 0;
    lsKeys(run).forEach(function (k) {
      try {
        var v = JSON.parse(lsGet(k));
        if (v && ((v.patches && v.patches.length) || v.gold)) { arts[k.slice((PREFIX + run + ':').length)] = v; n += (v.patches || []).length; }
      } catch (e) { /* a broken entry is left out */ }
    });
    var stamp = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 16);
    download('corrections_' + run + '_' + stamp + '.json',
      { kind: 'inkscript-corrections', version: 1, run: run, exported: new Date().toISOString(), articles: arts });
    return n;
  }

  /* ---------------------------------------------------------------- the index page */
  if (window.CINDEX) {
    var run0 = window.CINDEX, tot = 0;
    document.querySelectorAll('tr[data-stem]').forEach(function (tr) {
      var v = null;
      try { v = JSON.parse(lsGet(PREFIX + run0 + ':' + tr.dataset.stem) || 'null'); } catch (e) { v = null; }
      var n = v && v.patches ? v.patches.length : 0;
      tot += n;
      tr.querySelector('.mine').textContent = (n ? n : '') + (v && v.gold ? ' · now right' : '');
    });
    document.getElementById('ccount').textContent = tot ? tot + ' correction(s) in this browser' : 'no corrections yet';
    document.getElementById('cexport-all').addEventListener('click', function () { exportAll(run0); });
    return;
  }

  var dataEl = document.getElementById('cdata');
  if (!dataEl) return;
  var D = JSON.parse(dataEl.textContent);
  var KEY = PREFIX + D.run + ':' + D.stem;
  var store = { patches: [], gold: false, title: D.title };
  try { var s0 = JSON.parse(lsGet(KEY) || 'null'); if (s0 && s0.patches) store = s0; } catch (e) { /* fresh */ }
  var saved = true;
  function save() { store.title = D.title; saved = lsSet(KEY, JSON.stringify(store)); render(); }

  var KINDS = [
    ['paragraph', 'Paragraph'], ['title', 'Title'], ['heading1', 'Heading, level 1'], ['heading2', 'Heading, level 2'],
    ['heading3', 'Heading, level 3'], ['byline', 'Author line'], ['abstract', 'Abstract'], ['footnote', 'Footnote'],
    ['endnote', 'Endnote'], ['verse', 'Verse'], ['list_item', 'List item'], ['caption', 'Caption'], ['quote', 'Quotation'],
    ['boxed', 'Boxed text'], ['reference', 'Reference'], ['header', 'Running head (top)'], ['footer', 'Page foot / number'],
    ['other_article', 'From another article'], ['noise', 'Not on the page (noise)']];
  var NOISE = [['show-through', 'show-through (the other side of the sheet)'], ['scanner-junk', 'junk (specks, marks)'],
    ['bleed', 'bleed (the facing page)']];
  function kindOf(b) {
    if (b.type === 'heading') return 'heading' + Math.min(3, Math.max(1, +b.level || 2));
    if (b.type === 'footnote' && b.note_kind === 'endnote') return 'endnote';
    return b.type;
  }
  function kindName(b) {
    var k = kindOf(b);
    for (var i = 0; i < KINDS.length; i++) if (KINDS[i][0] === k) return KINDS[i][1];
    return k;
  }

  /* ---------------------------------------------------------------- the model: the page's blocks after my patches
     (the same rules as patches43.apply_one, for what the panel shows; the import applies the real thing) */
  function sameLines(a, b) { return a.length === b.length && a.every(function (x, i) { return x === b[i]; }); }
  function findBlock(bl, t) {
    var want = (t.lines || []).map(String);
    if (want.length) {
      for (var i = 0; i < bl.length; i++) if (sameLines(bl[i].lines, want)) return i;
      for (i = 0; i < bl.length; i++) if (bl[i].lines.indexOf(want[0]) >= 0) return i;
      return -1;
    }
    for (i = 0; i < bl.length; i++) {
      var bb = bl[i].box, tb = t.box;
      if (bl[i].type === t.type && bb && tb && bb.length === 4 &&
          bb.every(function (x, j) { return Math.abs(x - tb[j]) <= 1.5; })) return i;
    }
    return -1;
  }
  function fp(b) { return { lines: b.lines.slice(), type: b.type, box: b.box || null }; }
  function applyJS(M, p) {
    var a = p.action, pay = p.payload || {}, t = p.targets || {}, bl = M.blocks;
    if (a === 'fix_word') return null;
    if (a === 'mark_noise') {
      var ids = (t.lines || []).map(String), hit = false;
      bl.forEach(function (b) {
        var n = b.lines.length;
        b.lines = b.lines.filter(function (x) { return ids.indexOf(x) < 0; });
        if (b.lines.length !== n) hit = true;
        if (b.calls) b.calls = b.calls.filter(function (c) { return ids.indexOf(String(c.line)) < 0; });
      });
      if (!hit) return 'lines not in any block';
      M.blocks = bl.filter(function (b) { return b.lines.length || b.box; });
      ids.forEach(function (x) { M.noise[x] = pay.kind || 'noise'; });
      return null;
    }
    var idx = (t.blocks || []).map(function (x) { return findBlock(bl, x); });
    if (a !== 'reorder' && (!idx.length || idx.some(function (i) { return i < 0; }))) return 'block not found';
    var b = bl[idx[0]];
    if (a === 'set_kind') {
      b.type = pay.kind; if (pay.kind === 'heading') b.level = pay.level || b.level || 2;
      if (pay.note_kind) b.note_kind = pay.note_kind;
      return null;
    }
    if (a === 'mark_other_article') { idx.forEach(function (i) { bl[i]._was = bl[i].type; bl[i].type = 'other_article'; }); return null; }
    if (a === 'unmark_other_article') {
      if (b.type !== 'other_article') return 'not marked another article';
      b.type = pay.kind || b._was || 'paragraph'; if (pay.kind === 'heading') b.level = pay.level || 2;
      return null;
    }
    if (a === 'fix_picture_box') { if (!b.box) return 'no box'; b.box = pay.box.map(Math.round); return null; }
    if (a === 'split_block') {
      var k = b.shape === 'lines' ? b.lines.indexOf(String(pay.at_line)) : -1;
      if (k <= 0) return 'split line not inside a lines block';
      var nb = clone(b); nb.uid = b.uid + '/' + p.id;
      nb.lines = b.lines.slice(k); b.lines = b.lines.slice(0, k);
      if (b.calls) {
        b.calls = b.calls.filter(function (c) { return b.lines.indexOf(String(c.line)) >= 0; });
        nb.calls = nb.calls.filter(function (c) { return nb.lines.indexOf(String(c.line)) >= 0; });
      }
      if (pay.kind) nb.type = pay.kind;
      bl.splice(idx[0] + 1, 0, nb);
      return null;
    }
    if (a === 'merge_blocks') {
      if (idx.length < 2) return 'fewer than two blocks';
      var rest = idx.slice(1).map(function (i) { return bl[i]; });
      if (b.shape !== 'lines' || rest.some(function (r) { return r.shape !== 'lines'; })) return 'only blocks of lines merge';
      rest.forEach(function (r) {
        b.lines = b.lines.concat(r.lines);
        if (r.calls) b.calls = (b.calls || []).concat(r.calls);
        bl.splice(bl.indexOf(r), 1);
      });
      return null;
    }
    if (a === 'relink_call') {
      var line = String(pay.line);
      if (b.lines.indexOf(line) < 0) return "call's line not in the block";
      b.calls = b.calls || [];
      for (var j = 0; j < b.calls.length; j++) {
        var c = b.calls[j];
        if (String(c.line) === line && (c.marker === pay.marker || !pay.marker)) { c.fn = pay.fn; return null; }
      }
      b.calls.push({ line: line, marker: pay.marker, fn: pay.fn });
      return null;
    }
    if (a === 'reorder') {
      var cur = [];
      for (var q = 0; q < (pay.order || []).length; q++) {
        var i2 = findBlock(bl, (pay.fp || {})[pay.order[q]] || {});
        if (i2 < 0) return 'block not found';
        cur.push(bl[i2]);
      }
      if (cur.length !== bl.length || cur.some(function (x, i) { return cur.indexOf(x) !== i; })) return 'not a permutation';
      M.blocks = cur;
      return null;
    }
    return 'unknown action';
  }
  function model(pg) {
    var P = D.pages[pg];
    var M = { blocks: P.blocks.map(function (b, i) { var c = clone(b); c.uid = pg + '#' + i; return c; }), noise: {}, status: {} };
    P.noise.forEach(function (x) { M.noise[x] = 'noise'; });
    store.patches.forEach(function (p) { if (String(p.page) === String(pg)) M.status[p.id] = applyJS(M, p); });
    return M;
  }

  /* ---------------------------------------------------------------- patches */
  var created = 0;
  function newPatch(page, action, targets, payload, label) {
    var now = new Date(), iso = now.toISOString();
    var p = {
      id: 'h-' + D.stem.slice(0, 4) + '-p' + page + '-' + now.getTime().toString(36) + (created++).toString(36),
      run: D.run, article: D.stem, page: +page, action: action,
      targets: { lines: targets.lines || [], blocks: targets.blocks || [] }, payload: payload || {},
      source: 'person', confidence: 1, evidence: '', reason: label, created: iso, apply: true
    };
    store.patches.push(p);
    save();
    return p;
  }
  function blk(b) { return Object.assign({ id: 'b' }, fp(b)); }

  /* ---------------------------------------------------------------- selection */
  var sel = null;            // {p, uid, lines: Set of selected line ids, word: {lid, i}}
  function pageOf(node) { var s = node.closest('section.mrow'); return s ? s.dataset.p : null; }
  function curBlock() {
    if (!sel) return null;
    var M = model(sel.p);
    for (var i = 0; i < M.blocks.length; i++) if (M.blocks[i].uid === sel.uid) return { M: M, b: M.blocks[i], k: i };
    if (sel.anchor) for (i = 0; i < M.blocks.length; i++) if (M.blocks[i].lines.indexOf(sel.anchor) >= 0) {
      sel.uid = M.blocks[i].uid; return { M: M, b: M.blocks[i], k: i };
    }
    return { M: M, b: null, k: -1 };
  }
  function selectByLines(pg, lines, uidHint) {
    var M = model(pg), hit = null;
    if (lines && lines.length) {
      for (var i = 0; i < M.blocks.length && !hit; i++)
        if (lines.some(function (x) { return M.blocks[i].lines.indexOf(x) >= 0; })) hit = M.blocks[i];
    }
    if (!hit && uidHint !== undefined) hit = M.blocks.filter(function (b) { return b.uid === uidHint; })[0];
    if (!hit && lines && lines.length) {           // a line no block holds (noise)
      sel = { p: pg, uid: null, lines: new Set(), noiseLines: lines.slice() };
    } else if (hit) {
      sel = { p: pg, uid: hit.uid, anchor: hit.lines[0], lines: new Set() };
    }
    openPanel(); render();
  }
  function altoOf(piece) { return D.alto[piece.dataset.alto] || null; }
  function onClickLayout(ev) {
    if (!document.body.classList.contains('cedit')) return;
    var piece = ev.target.closest('.lpage .pc[data-alto]');
    var scan = ev.target.closest('.mscan');
    if (!piece && !scan) return;
    if (ev.target.closest('.chandle,.cboxedit')) return;
    ev.preventDefault(); ev.stopPropagation();
    if (piece) {
      var A = altoOf(piece);
      if (!A) return;
      var pg = String(A.p), uid;
      if (!A.lines.length) {                         // a picture: its block by box
        var P = D.pages[pg];
        uid = bestBoxBlock(P, A.box);
      }
      selectByLines(pg, A.lines, uid);
      return;
    }
    var pg2 = pageOf(scan), img = scan.querySelector('img'), P2 = D.pages[pg2];
    if (!img || !P2) return;
    var r = img.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width * P2.W, y = (ev.clientY - r.top) / r.height * P2.H;
    var best = null, ba = 1e18;
    Object.keys(P2.lines).forEach(function (lid) {
      var b = P2.lines[lid].px;
      if (x >= b[0] - 4 && x <= b[2] + 4 && y >= b[1] - 4 && y <= b[3] + 4) {
        var ar = (b[2] - b[0]) * (b[3] - b[1]);
        if (ar < ba) { ba = ar; best = lid; }
      }
    });
    if (best) { selectByLines(pg2, [best]); return; }
    var M = model(pg2);                                 // a picture on the scan
    for (var i = 0; i < M.blocks.length; i++) {
      var bb = M.blocks[i].box;
      if (bb && !M.blocks[i].lines.length && x >= bb[0] * P2.W / 1000 && x <= bb[2] * P2.W / 1000 &&
          y >= bb[1] * P2.H / 1000 && y <= bb[3] * P2.H / 1000) { selectByLines(pg2, [], M.blocks[i].uid); return; }
    }
  }
  function bestBoxBlock(P, box) {
    if (!box) return undefined;
    var best, bo = 0, pg = null;
    for (var k in D.pages) if (D.pages[k] === P) pg = k;
    P.blocks.forEach(function (b, i) {
      if (!b.box) return;
      var x0 = b.box[0] * P.W / 1000, y0 = b.box[1] * P.H / 1000, x1 = b.box[2] * P.W / 1000, y1 = b.box[3] * P.H / 1000;
      var w = Math.max(0, Math.min(x1, box[2]) - Math.max(x0, box[0])), h = Math.max(0, Math.min(y1, box[3]) - Math.max(y0, box[1]));
      if (w * h > bo) { bo = w * h; best = pg + '#' + i; }
    });
    return best;
  }

  /* ---------------------------------------------------------------- what the page shows */
  function pctBox(P, b) { return 'left:' + (b[0] / P.W * 100) + '%;top:' + (b[1] / P.H * 100) + '%;width:' + ((b[2] - b[0]) / P.W * 100) + '%;height:' + ((b[3] - b[1]) / P.H * 100) + '%'; }
  function union(bs) {
    if (!bs.length) return null;
    return [Math.min.apply(null, bs.map(function (b) { return b[0]; })), Math.min.apply(null, bs.map(function (b) { return b[1]; })),
      Math.max.apply(null, bs.map(function (b) { return b[2]; })), Math.max.apply(null, bs.map(function (b) { return b[3]; }))];
  }
  function blockPx(P, b) {
    var bs = b.lines.map(function (x) { return (P.lines[x] || {}).px; }).filter(Boolean);
    if (bs.length) return union(bs);
    return b.box ? [b.box[0] * P.W / 1000, b.box[1] * P.H / 1000, b.box[2] * P.W / 1000, b.box[3] * P.H / 1000] : null;
  }
  function iso(x) { return '\u2068' + (x === undefined || x === null ? '' : x) + '\u2069'; }   // a word kept whole among English
  function label(p) {
    var y = p.payload || {};
    switch (p.action) {
      case 'set_kind': return '→ ' + (y.kind === 'heading' ? 'heading ' + (y.level || 2) : y.note_kind === 'endnote' ? 'endnote' : y.kind);
      case 'mark_other_article': return '→ another article';
      case 'unmark_other_article': return '→ this article (' + (y.kind || 'paragraph') + ')';
      case 'mark_noise': return (p.targets.lines || []).length + ' line(s) → noise (' + y.kind + ')';
      case 'split_block': return 'split before line ' + y.at_line;
      case 'merge_blocks': return 'merged with the next block';
      case 'reorder': return 'reading order: ' + (y.what || 'moved');
      case 'relink_call': return 'call ' + iso(y.marker || '') + ' on ' + y.line + ' → note ' + y.fn;
      case 'fix_picture_box': return 'picture box redrawn';
      case 'fix_word': return (y.kind === 'misprint' ? 'misprint flagged: ' : 'word corrected: ') + iso(y.from) + ' → ' + iso(y.to);
    }
    return p.action;
  }
  function render() {
    document.querySelectorAll('.csel,.cedited').forEach(function (e) { e.classList.remove('csel', 'cedited'); });
    document.querySelectorAll('.cbox,.ctag,.cline,.cboxedit').forEach(function (e) { if (!boxEdit || !e.classList.contains('cboxedit')) e.remove(); });
    var pagesTouched = {};
    store.patches.forEach(function (p) { (pagesTouched[p.page] = pagesTouched[p.page] || []).push(p); });
    Object.keys(pagesTouched).forEach(function (pg) {
      var M = model(pg), sec = document.getElementById('p' + pg);
      if (!sec) return;
      pagesTouched[pg].forEach(function (p) {
        var ls = (p.targets.lines || []).slice();
        (p.targets.blocks || []).forEach(function (b) { ls = ls.concat(b.lines || []); });
        if (p.action === 'fix_word' || p.action === 'relink_call') ls = [String(p.payload.line)];
        if (p.action === 'reorder') ls = p.payload.moved || [];
        var first = null;
        sec.querySelectorAll('.lpage .pc[data-alto]').forEach(function (pc) {
          var A = altoOf(pc);
          if (A && A.lines.some(function (x) { return ls.indexOf(x) >= 0; })) { pc.classList.add('cedited'); first = first || pc; }
        });
        if (first && !first.querySelector('.ctag[data-id="' + p.id + '"]')) {
          var bad = M.status[p.id];
          first.appendChild(el('span', { class: 'ctag' + (bad ? ' stale' : ''), 'data-id': p.id, text: label(p) + (bad ? ' (no longer applies)' : '') }));
        }
      });
    });
    var cb = curBlock();
    if (sel) {
      var sec2 = document.getElementById('p' + sel.p), P = D.pages[sel.p];
      var lines = cb && cb.b ? cb.b.lines : (sel.noiseLines || []);
      if (sec2) {
        sec2.querySelectorAll('.lpage .pc[data-alto]').forEach(function (pc) {
          var A = altoOf(pc);
          if (!A) return;
          if (A.lines.some(function (x) { return lines.indexOf(x) >= 0; }) ||
              (!A.lines.length && cb && cb.b && cb.b.box && bestBoxBlock(P, A.box) === cb.b.uid.split('/')[0])) pc.classList.add('csel');
        });
        var ms = sec2.querySelector('.mscan');
        var bx = cb && cb.b ? blockPx(P, cb.b) : union(lines.map(function (x) { return P.lines[x].px; }));
        if (ms && bx && !boxEdit) ms.appendChild(el('div', { class: 'cbox', style: pctBox(P, bx) }));
        if (ms) sel.lines.forEach(function (x) { if (P.lines[x]) ms.appendChild(el('div', { class: 'cline', style: pctBox(P, P.lines[x].px) })); });
        if (ms && sel.word) {
          var w = P.lines[sel.word.lid].w[sel.word.i];
          if (w) ms.appendChild(el('div', { class: 'cline cword', style: pctBox(P, w.slice(2)) }));
        }
      }
    }
    var n = store.patches.length;
    btnMine.textContent = 'My corrections' + (n ? ' (' + n + ')' : '');
    warn.hidden = saved;
    renderPanel(cb);
  }

  /* ---------------------------------------------------------------- the panel */
  var panel = el('aside', { id: 'cpanel', class: 'cpanel', 'aria-label': 'Correction panel', dir: 'ltr' });
  var warn = el('p', { class: 'cwarn', hidden: true, text: 'This browser does not keep data here: export before you leave the page.' });
  var view = 'block';
  function openPanel() { document.body.classList.add('cpanel-open'); panel.classList.remove('min'); }
  function section(title, kids, cls) { return el('section', { class: 'csec ' + (cls || '') }, [el('h3', { text: title })].concat(kids)); }
  function button(text, fn, cls, title) { return el('button', { type: 'button', class: cls || '', title: title || null, on: { click: fn } }, [text]); }

  function renderPanel(cb) {
    panel.innerHTML = '';
    var head = el('div', { class: 'chead' }, [
      el('strong', { text: 'Correct' }),
      button('Block', function () { view = 'block'; render(); }, view === 'block' ? 'on' : ''),
      button(btnMine.textContent, function () { view = 'mine'; openPanel(); render(); }, view === 'mine' ? 'on' : ''),
      button('Export', function () { exportAll(D.run); }, '', 'Save the corrections of every article in this browser as one file'),
      button('▾', function () { panel.classList.toggle('min'); }, 'cmin', 'Fold the panel')]);
    panel.appendChild(head);
    panel.appendChild(warn);
    var body = el('div', { class: 'cbody' });
    panel.appendChild(body);
    if (view === 'mine') { renderMine(body); return; }
    if (!sel) {
      body.appendChild(el('p', { class: 'chelp', text: 'Click a block on our page (or a line on the scan) to correct it. Every change is kept as a correction you can undo; nothing in the masters changes until the corrections are imported.' }));
      return;
    }
    var P = D.pages[sel.p];
    if (!cb.b) {                                   // lines no block holds
      body.appendChild(el('p', { text: 'Page ' + sel.p + ': ' + (sel.noiseLines || []).join(', ') + ' — not in any block (noise).' }));
      (sel.noiseLines || []).forEach(function (x) { body.appendChild(lineRow(P, x, false)); });
      if (sel.word) body.appendChild(wordBox(P));
      return;
    }
    var b = cb.b, M = cb.M;
    body.appendChild(el('p', { class: 'cwhere' }, [el('b', { text: 'Page ' + sel.p + ' · block ' + (cb.k + 1) + ' of ' + M.blocks.length }), ' · ' + kindName(b) + (b.shape !== 'lines' ? ' (' + b.shape + ')' : '')]));

    // kind
    var kinds = KINDS.some(function (k) { return k[0] === kindOf(b); }) ? KINDS : [[kindOf(b), kindOf(b) + ' (as Gemini said)']].concat(KINDS);
    var ksel = el('select', { 'aria-label': 'kind' }, kinds.map(function (k) { return el('option', { value: k[0], selected: k[0] === kindOf(b) ? 'selected' : null, text: k[1] }); }));
    var nsel = el('select', { 'aria-label': 'noise kind', class: 'cnk' }, NOISE.map(function (k) { return el('option', { value: k[0], text: k[1] }); }));
    function syncN() { nsel.hidden = ksel.value !== 'noise'; }
    ksel.addEventListener('change', syncN); syncN();
    body.appendChild(section('What this block is', [el('div', { class: 'crow' }, [ksel, nsel, button('Apply', function () { setKind(b, ksel.value, nsel.value); }, 'primary')])]));

    // lines
    var ls = el('div', { class: 'clines' });
    b.lines.forEach(function (x) { ls.appendChild(lineRow(P, x, true)); });
    var n2 = el('select', { 'aria-label': 'noise kind of the selected lines' }, NOISE.map(function (k) { return el('option', { value: k[0], text: k[1] }); }));
    body.appendChild(section('Lines (tick to select; click a word to correct it)', [ls,
      el('div', { class: 'crow' }, [button('Selected lines are noise', function () { markNoise(Array.from(sel.lines), n2.value); }), n2]),
      el('div', { class: 'crow' }, [button('Split before the first selected line', function () { split(b); }, '', 'The block ends before that line; a new block of the same kind starts there')])]));
    if (sel.word) body.appendChild(wordBox(P));

    // order
    body.appendChild(section('Reading order', [el('div', { class: 'crow' }, [
      button('Move up', function () { move(cb, -1); }), button('Move down', function () { move(cb, +1); }),
      button('Merge with the next block', function () { merge(cb); })]), pageList(M, cb.k)]));

    // notes
    var calls = b.calls || [];
    var notes = D.notes.slice().sort(function (x, y) { return (x.page === +sel.p ? 0 : 1) - (y.page === +sel.p ? 0 : 1) || x.page - y.page; });
    function noteSel(cur) {
      return el('select', { 'aria-label': 'note' }, [el('option', { value: '', text: '— pick a note —' })].concat(notes.map(function (n) {
        return el('option', { value: n.id, selected: n.id === cur ? 'selected' : null, text: 'p' + n.page + ' ' + (n.marker || '') + ' ' + n.text.slice(0, 40) });
      })));
    }
    var callRows = calls.map(function (c) {
      var s = noteSel(c.fn);
      return el('div', { class: 'crow' }, [el('span', { class: 'cmk', text: (c.marker || '?') + ' (' + c.line + ')' }), s,
        button('Link', function () { if (s.value) relink(b, c.line, c.marker, s.value); })]);
    });
    var lsel = el('select', { 'aria-label': 'line of the call' }, b.lines.map(function (x) { return el('option', { value: x, text: x }); }));
    var mk = el('input', { type: 'text', size: 5, placeholder: '(3)', 'aria-label': 'marker as printed' });
    var ns = noteSel(null);
    if (notes.length || calls.length)
      body.appendChild(section('Note calls', callRows.concat([el('div', { class: 'crow' }, [el('span', { text: 'New:' }), lsel, mk, ns,
        button('Link', function () { if (ns.value) relink(b, lsel.value, mk.value.trim() || null, ns.value); })])])));

    // picture box
    if (b.box) body.appendChild(section('Picture box', [el('div', { class: 'crow' }, boxEdit ?
      [button('Save the box', function () { saveBox(b); }, 'primary'), button('Cancel', function () { boxEdit = null; render(); })] :
      [button('Redraw the box on the scan', function () { startBox(b); })])]));

    // this block's corrections
    var mine = store.patches.filter(function (p) { return String(p.page) === String(sel.p) && touches(p, b); });
    if (mine.length) body.appendChild(section('Corrections here', mine.map(function (p) { return patchRow(p, M.status[p.id]); })));
  }
  function touches(p, b) {
    var ls = (p.targets.lines || []).slice();
    (p.targets.blocks || []).forEach(function (x) { ls = ls.concat(x.lines || []); });
    if (p.payload && p.payload.line) ls.push(String(p.payload.line));
    if (p.payload && p.payload.at_line) ls.push(String(p.payload.at_line));
    return ls.some(function (x) { return b.lines.indexOf(x) >= 0; }) || (p.action === 'reorder');
  }
  function patchRow(p, bad) {
    return el('div', { class: 'cpatch' + (bad ? ' stale' : '') }, [
      el('span', { text: 'p' + p.page + ' · ' + label(p) + (bad ? ' — no longer applies (' + bad + ')' : '') }),
      button('Undo', function () { store.patches = store.patches.filter(function (x) { return x.id !== p.id; }); save(); }, 'undo')]);
  }
  function pageList(M, k) {
    return el('ol', { class: 'cblocks' }, M.blocks.map(function (b, i) {
      var P = D.pages[sel.p], t = b.lines.slice(0, 1).map(function (x) { return (P.lines[x] || {}).t || ''; }).join(' ');
      return el('li', { class: i === k ? 'on' : '', on: { click: function () { sel = { p: sel.p, uid: b.uid, anchor: b.lines[0], lines: new Set() }; render(); } } },
        [el('b', { text: kindName(b) }), ' ', el('span', { dir: 'auto', text: t.slice(0, 50) || (b.box ? '[picture]' : '') })]);
    }));
  }
  function lineRow(P, x, tick) {
    var L = P.lines[x] || { t: '?', w: [] };
    var cb = el('input', { type: 'checkbox', 'aria-label': 'select line ' + x, checked: sel.lines.has(x) ? 'checked' : null,
      on: { change: function () { if (this.checked) sel.lines.add(x); else sel.lines.delete(x); render(); } } });
    var words = el('span', { class: 'cwords', dir: 'auto' });
    if (L.w.length) L.w.forEach(function (w, i) {
      words.appendChild(el('button', { type: 'button', class: 'cw' + (sel.word && sel.word.lid === x && sel.word.i === i ? ' on' : '') + (w[1] !== null && w[1] < 0.6 ? ' low' : ''),
        title: 'Azure: ' + w[0] + (w[1] !== null ? ' (' + w[1] + ')' : ''),
        on: { click: function () { sel.word = { lid: x, i: i }; render(); } } }, [w[0]]));
      words.appendChild(document.createTextNode(' '));
    }); else words.textContent = L.t;
    var fixed = L.t !== L.az ? el('div', { class: 'cnow', dir: 'auto', text: 'now: ' + L.t }) : null;
    return el('div', { class: 'cl' + (sel.lines.has(x) ? ' on' : '') }, [tick ? cb : null, el('code', { text: x }), words, fixed]);
  }
  function wordBox(P) {
    var L = P.lines[sel.word.lid], w = L && L.w[sel.word.i];
    if (!w) return el('p', { text: 'word not found' });
    var lid = sel.word.lid, fx = (D.fixes[lid] || []).filter(function (f) { return f[0] && (f[0].indexOf(w[0]) >= 0 || w[0].indexOf(f[0]) >= 0); });
    var sc = (D.sic[lid] || []).filter(function (f) { return f[0] && f[0].indexOf(w[0]) >= 0; });
    var mine = store.patches.filter(function (p) { return p.action === 'fix_word' && String(p.payload.line) === lid && p.payload.from === w[0]; }).pop();
    var now = mine ? mine.payload.to : fx.length ? fx[0][1] : w[0];
    var canvas = el('canvas', { class: 'ccrop', width: 10, height: 10, 'aria-label': 'the word on the scan' });
    drawCrop(canvas, P, w.slice(2));
    var inp = el('input', { type: 'text', dir: 'auto', value: now, 'aria-label': 'what the print shows', class: 'cin' });
    var kids = [canvas, el('p', {}, ['Azure read ', el('b', { dir: 'auto', text: w[0] }), w[1] !== null ? ' (confidence ' + w[1] + ')' : ''])];
    fx.forEach(function (f) { kids.push(el('p', {}, ['Gemini corrected ', el('b', { dir: 'auto', text: f[0] }), ' → ', el('b', { dir: 'auto', text: f[1] || '(nothing)' }), f[2] ? ' — ' + f[2] : ''])); });
    sc.forEach(function (f) { kids.push(el('p', {}, ['Flagged as a misprint, intended ', el('b', { dir: 'auto', text: f[1] })])); });
    if (mine) kids.push(el('p', { class: 'cmine' }, ['Your correction: ' + label(mine)]));
    kids.push(el('div', { class: 'crow' }, [inp]));
    kids.push(el('div', { class: 'crow' }, [
      button('Azure misread → correct to this', function () { fixWord(lid, w[0], inp.value.trim(), 'misread'); }, 'primary'),
      button('Misprint in the print → flag with this correction', function () { fixWord(lid, w[0], inp.value.trim(), 'misprint'); }, '', 'The printed text stays as printed (D30); the correction is recorded beside it')]));
    if (fx.length) kids.push(el('div', { class: 'crow' }, [button('Azure was right: take Gemini\'s correction away', function () { fixWord(lid, w[0], w[0], 'misread'); })]));
    return section('Word', kids, 'cword-sec');
  }
  function drawCrop(c, P, b) {
    var sec = document.getElementById('p' + sel.p), img = sec && sec.querySelector('.mscan img');
    if (!img) return;
    function go() {
      var s = img.naturalWidth / P.W, pad = (b[3] - b[1]) * 0.6;
      var x0 = Math.max(0, b[0] - pad), y0 = Math.max(0, b[1] - pad / 2), x1 = Math.min(P.W, b[2] + pad), y1 = Math.min(P.H, b[3] + pad / 2);
      var scale = Math.min(3, 300 / Math.max(1, x1 - x0));
      c.width = Math.round((x1 - x0) * scale); c.height = Math.round((y1 - y0) * scale);
      try { c.getContext('2d').drawImage(img, x0 * s, y0 * s, (x1 - x0) * s, (y1 - y0) * s, 0, 0, c.width, c.height); } catch (e) { /* not loaded */ }
    }
    if (img.complete && img.naturalWidth) go(); else img.addEventListener('load', go, { once: true });
  }
  function renderMine(body) {
    var byPage = {};
    var Ms = {};
    store.patches.forEach(function (p) { Ms[p.page] = Ms[p.page] || model(p.page); });
    body.appendChild(el('p', { class: 'chelp', text: store.patches.length + ' correction(s) in this article, in the order made. Undo takes one away; Export saves those of every article.' }));
    store.patches.forEach(function (p) {
      var row = patchRow(p, Ms[p.page].status[p.id]);
      row.insertBefore(button('Show', function () {
        var ls = (p.targets.lines || []).concat((p.targets.blocks || []).reduce(function (a, b) { return a.concat(b.lines || []); }, []));
        if (p.payload.line) ls.push(String(p.payload.line));
        view = 'block'; selectByLines(String(p.page), ls);
        var s = document.getElementById('p' + p.page); if (s) s.scrollIntoView({ block: 'start' });
      }, 'show'), row.lastChild);
      body.appendChild(row);
    });
    var g = el('input', { type: 'checkbox', id: 'cgold', checked: store.gold ? 'checked' : null, on: { change: function () { store.gold = this.checked; save(); } } });
    body.appendChild(el('p', { class: 'cgold' }, [g, el('label', { for: 'cgold', text: ' This article is now right: make it a gold item (gold43.py import)' })]));
  }

  /* ---------------------------------------------------------------- actions */
  function setKind(b, k, nk) {
    var p = sel.p, t = { blocks: [blk(b)] };
    if (k === kindOf(b)) return;
    if (k === 'noise') { markNoise(b.lines.slice(), nk); return; }
    if (k === 'other_article') { newPatch(p, 'mark_other_article', t, {}, 'another article'); return; }
    var pay = { kind: k };
    if (/^heading\d$/.test(k)) pay = { kind: 'heading', level: +k.slice(7) };
    if (k === 'endnote') pay = { kind: 'footnote', note_kind: 'endnote' };
    if (k === 'footnote') pay = { kind: 'footnote', note_kind: 'footnote' };
    if (b.type === 'other_article') { newPatch(p, 'unmark_other_article', t, pay, 'this article'); return; }
    newPatch(p, 'set_kind', t, pay, 'kind');
  }
  function markNoise(ls, kind) {
    if (!ls.length) { alert('Tick the lines first.'); return; }
    newPatch(sel.p, 'mark_noise', { lines: ls }, { kind: kind }, 'noise');
    sel.lines = new Set();
    var cb = curBlock(); if (!cb.b) sel = null;
    render();
  }
  function split(b) {
    var first = b.lines.filter(function (x) { return sel.lines.has(x); })[0];
    if (!first || first === b.lines[0]) { alert('Tick a line after the first one: the new block starts there.'); return; }
    newPatch(sel.p, 'split_block', { blocks: [blk(b)] }, { at_line: first }, 'split');
    sel.lines = new Set(); sel.anchor = first; sel.uid = null;
    render();
  }
  function merge(cb) {
    var nx = cb.M.blocks[cb.k + 1];
    if (!nx) { alert('This is the last block of the page.'); return; }
    if (cb.b.shape !== 'lines' || nx.shape !== 'lines') { alert('Only blocks of lines merge (not verse, tables or pictures).'); return; }
    newPatch(sel.p, 'merge_blocks', { blocks: [blk(cb.b), blk(nx)] }, {}, 'merge');
  }
  function move(cb, d) {
    var bl = cb.M.blocks.slice(), j = cb.k + d;
    if (j < 0 || j >= bl.length) return;
    var fps = {}, ids = bl.map(function (b, i) { fps['b' + i] = Object.assign({ id: 'b' + i }, fp(b)); return 'b' + i; });
    var t = ids[cb.k]; ids[cb.k] = ids[j]; ids[j] = t;
    newPatch(sel.p, 'reorder', { blocks: [] }, { order: ids, fp: fps, moved: cb.b.lines.slice(), what: 'block ' + (cb.k + 1) + (d < 0 ? ' up' : ' down') }, 'reorder');
  }
  function relink(b, line, marker, fn) { newPatch(sel.p, 'relink_call', { blocks: [blk(b)] }, { line: line, marker: marker, fn: fn }, 'note link'); }
  function fixWord(lid, from, to, kind) {
    if (!to) { alert('Type what the print shows.'); return; }
    if (kind === 'misprint' && to === from) { alert('A misprint needs the intended word.'); return; }
    store.patches = store.patches.filter(function (p) { return !(p.action === 'fix_word' && String(p.payload.line) === lid && p.payload.from === from); });
    newPatch(sel.p, 'fix_word', { lines: [lid] }, { kind: kind, line: lid, from: from, to: to, why: 'person: ' + kind }, 'word');
  }

  /* ---------------------------------------------------------------- the picture box (corners dragged on the scan) */
  var boxEdit = null;
  function startBox(b) {
    var sec = document.getElementById('p' + sel.p), ms = sec.querySelector('.mscan'), P = D.pages[sel.p];
    boxEdit = { b: b, box: b.box.slice() };
    var div = el('div', { class: 'cboxedit' });
    ['nw', 'ne', 'sw', 'se'].forEach(function (c) { div.appendChild(el('span', { class: 'chandle ' + c, 'data-c': c })); });
    ms.appendChild(div);
    function place() { var x = boxEdit.box; div.setAttribute('style', 'left:' + x[0] / 10 + '%;top:' + x[1] / 10 + '%;width:' + (x[2] - x[0]) / 10 + '%;height:' + (x[3] - x[1]) / 10 + '%'); }
    place();
    div.addEventListener('pointerdown', function (ev) {
      var h = ev.target.closest('.chandle'); if (!h) return;
      ev.preventDefault(); h.setPointerCapture(ev.pointerId);
      var c = h.dataset.c;
      function mv(e) {
        var r = ms.getBoundingClientRect();
        var x = Math.max(0, Math.min(1000, (e.clientX - r.left) / r.width * 1000)), y = Math.max(0, Math.min(1000, (e.clientY - r.top) / r.height * 1000));
        var B = boxEdit.box;
        if (c[1] === 'w') B[0] = Math.min(x, B[2] - 5); else B[2] = Math.max(x, B[0] + 5);
        if (c[0] === 'n') B[1] = Math.min(y, B[3] - 5); else B[3] = Math.max(y, B[1] + 5);
        place();
      }
      function up() { h.removeEventListener('pointermove', mv); h.removeEventListener('pointerup', up); }
      h.addEventListener('pointermove', mv); h.addEventListener('pointerup', up);
    });
    void P;
    render();
  }
  function saveBox(b) {
    var box = boxEdit.box.map(Math.round);
    boxEdit = null;
    document.querySelectorAll('.cboxedit').forEach(function (e) { e.remove(); });
    newPatch(sel.p, 'fix_picture_box', { blocks: [blk(b)] }, { box: box }, 'box');
  }

  /* ---------------------------------------------------------------- start */
  var btnMine = el('button', { type: 'button' }, ['My corrections']);
  var tog = el('button', { type: 'button', id: 'cedit', 'aria-pressed': 'true', title: 'Click blocks to correct them (e)' }, ['Correcting']);
  tog.addEventListener('click', function () {
    var on = document.body.classList.toggle('cedit');
    tog.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (!on) document.body.classList.remove('cpanel-open'); else openPanel();
  });
  var bar = document.querySelector('nav.bar');
  if (bar) bar.insertBefore(tog, bar.querySelector('#theme'));
  document.body.classList.add('cedit', 'cpanel-open');
  document.body.appendChild(panel);
  document.addEventListener('click', onClickLayout, true);
  window.CORRECT = { data: D, store: function () { return store; }, model: model, select: selectByLines, exportAll: function () { return exportAll(D.run); } };
  render();
})();
