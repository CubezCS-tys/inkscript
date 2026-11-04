import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, ArrowLeftRight, Square, LayoutPanelTop, ImageOff, Loader2 } from 'lucide-react';
import { Chip } from './Bits';
import { FigNotes, ROLE, TableFig, Verses, withCalls } from './ArticleText';
import { enc } from '../lib/api';
import { useApi } from '../lib/me';

// The article beside its scan (2026-10-23). The full page scans on one side, the reading on the other, kept in step
// as either side scrolls: the block at the top of the reading lines up with its ink on the scan, and the other way
// round. Hovering a block outlines its box on the scan; clicking jumps the other side to it. Boxes come from the
// platform's block_parts (ALTO frame), drawn as fractions of the page, so the image's size does not matter.
// Scan images load lazily (an IntersectionObserver on the scan pane), downscaled by the API (/evidence/page).

export type View = 'text' | 'beside' | 'scan' | 'classic';
export const VIEW_LABEL: Record<View, string> = { text: 'Text', beside: 'Beside the scan', scan: 'Scan only', classic: 'Classic page' };

// noScan (experiment 73, M8): an article built from the publisher's Word file has no scan, so the three scan views
// are shown disabled with one line saying why.
export const ViewSwitch: React.FC<{ value: View; onChange: (v: View) => void; noScan?: boolean }> = ({ value, onChange, noScan }) => (
  <div className="flex flex-col items-end gap-1">
    <div className="inline-flex rounded-lg border border-gray-200 bg-white overflow-hidden text-sm shadow-sm" role="radiogroup" aria-label="View" data-testid="view-switch">
      {(['text', 'beside', 'scan', 'classic'] as View[]).map(v => {
        const off = noScan && v !== 'text';
        return (
          <button key={v} role="radio" aria-checked={value === v} onClick={() => !off && onChange(v)} data-view={v} disabled={off} aria-disabled={off}
            title={off ? 'This article was built from the publisher\'s Word file: there is no scan to show.' : undefined}
            className={`px-3 py-1.5 ${value === v ? 'bg-gray-900 text-white' : off ? 'text-gray-300 cursor-not-allowed' : 'text-gray-600 hover:bg-gray-50'}`}>{VIEW_LABEL[v]}</button>
        );
      })}
    </div>
    {noScan && <p className="text-xs text-gray-500" data-testid="no-scan-note">No scan: this article was built from the publisher's Word file, so its page numbers are estimates.</p>}
  </div>
);

// one colour per kind of block, the same on the scan and in the legend
const COLOR: Record<string, string> = {
  title: '#e11d48', 'title-translated': '#e11d48', heading: '#4f46e5', paragraph: '#0284c7', 'list-item': '#0284c7',
  quote: '#0891b2', abstract: '#0d9488', keywords: '#0d9488', footnote: '#d97706', endnote: '#d97706', ref: '#16a34a',
  caption: '#7c3aed', figure: '#7c3aed', table: '#7c3aed', 'verse-group': '#9333ea', byline: '#db2777',
  affiliation: '#db2777', 'front-matter': '#6b7280', 'back-matter': '#6b7280',
};
const LEGEND: [string, string][] = [['Title', '#e11d48'], ['Heading', '#4f46e5'], ['Text', '#0284c7'], ['Abstract', '#0d9488'],
  ['Note', '#d97706'], ['Reference', '#16a34a'], ['Table / figure', '#7c3aed'], ['Byline', '#db2777']];
const NICE: Record<string, string> = { 'title-translated': 'translated title', 'list-item': 'list item', 'verse-group': 'verse',
  'front-matter': 'front matter', 'back-matter': 'back matter', ref: 'reference', table: 'table', figure: 'figure' };
const OFF = 12;                      // px from a pane's top where the two sides line up

const STYLE = `
.bs-box{position:absolute;border:1px solid transparent;border-radius:2px;cursor:pointer;transition:background-color .12s,border-color .12s}
.bs-boxes .bs-box{border-color:color-mix(in srgb,var(--c) 38%,transparent)}
.bs-box:hover,.bs-box.bs-hot{border:2px solid var(--c);background:color-mix(in srgb,var(--c) 13%,transparent);z-index:2}
.bs-box.bs-flash{animation:bsflash 1.4s ease-out}
.bs-reg{position:absolute;border:1px dashed #9ca3af;border-radius:2px;background:repeating-linear-gradient(45deg,rgba(156,163,175,.10) 0 6px,transparent 6px 12px);pointer-events:auto}
.bs-reg span{position:absolute;top:-1.15rem;inset-inline-start:0;font:500 10px/1.4 ui-sans-serif,system-ui;color:#6b7280;background:#fff;border:1px solid #e5e7eb;border-radius:3px;padding:0 4px;white-space:nowrap;opacity:0;transition:opacity .12s}
.bs-reg:hover span{opacity:1}
.bs-item{border-radius:6px;padding:2px 8px;margin-inline:-8px;cursor:pointer;transition:background-color .12s,box-shadow .12s}
.bs-item:hover,.bs-item.bs-hot{background:color-mix(in srgb,var(--c) 7%,#fff);box-shadow:inset 3px 0 0 var(--c)}
[dir=rtl].bs-item:hover,[dir=rtl].bs-item.bs-hot{box-shadow:inset -3px 0 0 var(--c)}
.bs-item.bs-flash{animation:bsflash2 1.4s ease-out}
@keyframes bsflash{0%{background:color-mix(in srgb,var(--c) 40%,transparent);border:2px solid var(--c)}100%{background:transparent}}
@keyframes bsflash2{0%{background:color-mix(in srgb,var(--c) 22%,#fff)}100%{background:transparent}}
`;

type Box = { id: string; page: number; x: number; y: number; w: number; h: number; role: string };

function topIn(el: Element, pane: HTMLElement) {
  return el.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop;
}
// the last element whose top is at or above y (elements in document order, so their tops increase)
function lastAbove(els: HTMLElement[], pane: HTMLElement, y: number): number {
  let lo = 0, hi = els.length - 1, ans = 0;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (topIn(els[mid], pane) <= y) { ans = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return ans;
}
const clamp = (x: number) => Math.max(0, Math.min(1, x));

// ------------------------------------------------------------------ the reading, page by page
const Reading: React.FC<{ a: any; pageOf: Record<number, any> }> = React.memo(({ a, pageOf }) => {
  const callsByBlock = useMemo(() => {
    const m: Record<string, any[]> = {};
    a.calls.forEach((c: any) => { (m[c.block_id] ||= []).push(c); });
    return m;
  }, [a]);
  const figs = useMemo(() => Object.fromEntries(a.figures.map((x: any) => [x.figure_id, x])), [a]);
  const notesByFirst = useMemo(() => Object.fromEntries(a.notes.map((x: any) => [x.first_block_id, x])), [a]);
  const shown = new Set<string>();
  const groups: Record<number, React.ReactNode[]> = {};
  const push = (page: number, node: React.ReactNode) => { (groups[page || 1] ||= []).push(node); };
  a.blocks.forEach((b: any) => {
    if (b.role === 'table-cell') {
      const fig = b.figure_id && figs[b.figure_id];
      if (fig && !shown.has(fig.figure_id)) {
        shown.add(fig.figure_id);
        push(fig.page || b.page, <div key={`t${fig.figure_id}`} className="bs-item" data-bid={`fig:${fig.figure_id}`} data-page={fig.page || b.page} style={{ '--c': COLOR.table } as any}><TableFig fig={fig} /></div>);
      }
      return;
    }
    const ar = b.script === 'ar';
    const note = (b.role === 'footnote' || b.role === 'endnote') ? notesByFirst[b.block_id] : null;
    const isNote = b.role === 'footnote' || b.role === 'endnote';
    const fig = b.role === 'caption' && b.figure_id ? figs[b.figure_id] : null;
    if (fig) shown.add(fig.figure_id);
    const cls = isNote ? 'text-[14px] leading-7 text-gray-700' : (ROLE[b.role] || 'text-[16px] leading-8 text-gray-900');
    const body = b.verses?.length ? <Verses verses={b.verses} />
      : <p className={`${ar ? 'ar' : ''} ${cls} whitespace-pre-wrap`}>{withCalls(b.text || '', callsByBlock[b.block_id])}</p>;
    push(b.page, (
      <div key={b.block_id} id={note ? `note-${note.note_id}` : undefined} dir={ar ? 'rtl' : 'ltr'}
        className={`bs-item ${isNote ? 'border-t border-dashed border-gray-200 pt-1' : ''}`} data-bid={b.block_id} data-page={b.page} data-role={b.role}
        style={{ '--c': COLOR[b.role] || '#0284c7' } as any}>
        {(b.role !== 'paragraph' && b.role !== 'list-item') && <span className={`block text-[10px] uppercase tracking-wide text-gray-400 ${ar ? 'text-right' : ''}`} dir="ltr">{NICE[b.role] || b.role}{note ? ` ${note.label || ''}` : ''}</span>}
        {fig && fig.kind !== 'table' && <p className="text-xs text-gray-500" dir="ltr">Figure {fig.figure_id}{fig.fig_type && <> <Chip tone="indigo">{fig.fig_type}</Chip></>}{fig.alt_en ? ` · ${fig.alt_en}` : ''}</p>}
        {body}
        {fig && <FigNotes fig={fig} />}
        {fig && fig.kind === 'table' && fig.cells?.length > 0 && <TableFig fig={fig} />}
      </div>));
  });
  const pages = Object.keys(pageOf).map(Number).sort((x, y) => x - y);
  return (
    <div className="space-y-2 relative">
      {pages.map(p => (
        <section key={p} data-page-group={p} className="space-y-2.5">
          <div className="flex items-center gap-3 pt-3 pb-1 select-none" data-page-sep={p}>
            <span className="text-[11px] font-medium text-gray-500 tabular-nums whitespace-nowrap">Page {p}{pageOf[p]?.folio ? ` · printed ${pageOf[p].folio}` : ''}</span>
            <span className="h-px flex-1 bg-gray-200" />
          </div>
          {(groups[p] || []).length ? groups[p] : <p className="text-xs text-gray-400 italic">Nothing on this page is part of the article's text.</p>}
        </section>))}
    </div>
  );
});
Reading.displayName = 'Reading';

// ------------------------------------------------------------------ one page of the scan with its boxes
const ScanPage: React.FC<{ stem: string; p: any; boxes: Box[]; regions: boolean; load: boolean; width: number; titleOf: (id: string) => string }> =
  React.memo(({ stem, p, boxes, regions, load, width, titleOf }) => {
    const [bad, setBad] = useState(false);
    const W = p.w || 1, H = p.h || 1;
    const pct = (v: number, of: number) => `${(100 * v / of).toFixed(3)}%`;
    return (
      <figure className="relative" data-scan-page={p.page}>
        <figcaption className="flex items-center justify-between text-[11px] text-gray-500 mb-1 px-0.5 tabular-nums">
          <span>Page {p.page}</span>{p.folio && <span>printed {p.folio}</span>}
        </figcaption>
        <div className="relative bg-white shadow-sm ring-1 ring-gray-200 rounded-sm overflow-hidden" style={{ aspectRatio: `${W} / ${H}` }}>
          {!p.image || bad
            ? <div className="crop-empty absolute inset-0 flex items-center justify-center text-xs text-gray-400 gap-1"><ImageOff className="w-4 h-4" /> no page image on this server</div>
            : load
              // eslint-disable-next-line @next/next/no-img-element
              ? <img src={`/desk/api/evidence/page?stem=${enc(stem)}&page=${p.page}&w=${width}`} alt={`scan of page ${p.page}`} decoding="async"
                  onError={() => setBad(true)} className="absolute inset-0 w-full h-full select-none" draggable={false} data-scan-img={p.page} />
              : <div className="absolute inset-0 flex items-center justify-center text-gray-300"><Loader2 className="w-5 h-5 animate-spin" /></div>}
          {regions && p.regions.map((r: any) => (
            <div key={r.id} className="bs-reg" title={`${r.label} — kept out of the text${r.text ? `: ${r.text}` : ''}`}
              style={{ left: pct(r.x, W), top: pct(r.y, H), width: pct(r.w, W), height: pct(r.h, H) }}><span>{r.label}</span></div>))}
          {boxes.map((b, i) => (
            <div key={`${b.id}-${i}`} className="bs-box" data-box={b.id} title={titleOf(b.id)}
              style={{ left: pct(b.x, W), top: pct(b.y, H), width: pct(b.w, W), height: pct(b.h, H), '--c': COLOR[b.role] || '#0284c7' } as any} />))}
        </div>
      </figure>
    );
  });
ScanPage.displayName = 'ScanPage';

// ------------------------------------------------------------------ the view
const BesideScan: React.FC<{ a: any; view: View; onView: (v: View) => void }> = ({ a, view, onView }) => {
  const { data: L, err } = useApi<any>(`/articles/${enc(a.stem)}/scan`);
  const R = useRef<HTMLDivElement>(null);
  const K = useRef<HTMLDivElement>(null);
  const driver = useRef<'R' | 'K' | null>(null);
  const tick = useRef(0);
  const rEls = useRef<HTMLElement[]>([]);
  const [page, setPage] = useState(1);
  const [loaded, setLoaded] = useState<Set<number>>(() => new Set([1, 2]));
  const [showBoxes, setShowBoxes] = useState(true);
  const [regions, setRegions] = useState(true);
  // an Arabic article (by the length of its running text, table cells aside) puts its reading on the right
  const ar = useMemo(() => {
    let x = 0, all = 0;
    a.blocks.forEach((b: any) => { if (b.role !== 'table-cell') { const l = (b.text || '').length; all += l; if (b.script === 'ar') x += l; } });
    return x >= all / 2;
  }, [a]);
  const [swap, setSwap] = useState(false);
  const readingFirst = ar ? swap : !swap;               // Arabic: the reading on the right, the scan on the left

  // boxes: blocks (table cells folded into their table's figure box), figures; and lookups both ways
  const { boxesOf, byPage, pageOf, textOf } = useMemo(() => {
    const boxesOf: Record<string, Box[]> = {};
    const byPage: Record<number, Box[]> = {};
    const pageOf: Record<number, any> = {};
    const textOf: Record<string, string> = {};
    a.blocks.forEach((b: any) => { textOf[b.block_id] = `${NICE[b.role] || b.role} · ${(b.text || '').slice(0, 140)}`; });
    a.figures.forEach((f: any) => { textOf[`fig:${f.figure_id}`] = `${f.kind} ${f.figure_id}${f.caption ? ' · ' + f.caption.slice(0, 120) : ''}`; });
    (L?.pages || []).forEach((p: any) => {
      pageOf[p.page] = p;
      const list: Box[] = [];
      p.blocks.forEach((b: any) => { if (b.role !== 'table-cell') list.push({ ...b, page: p.page }); });
      p.figures.forEach((f: any) => list.push({ id: `fig:${f.id}`, role: f.kind === 'table' ? 'table' : 'figure', page: p.page, x: f.x, y: f.y, w: f.w, h: f.h }));
      list.sort((x, y) => x.y - y.y);
      byPage[p.page] = list;
      list.forEach(b => { (boxesOf[b.id] ||= []).push(b); });
    });
    // a table whose figure has no box: the union of its cells
    const fig = Object.fromEntries(a.blocks.filter((b: any) => b.role === 'table-cell').map((b: any) => [b.block_id, b.figure_id]));
    (L?.pages || []).forEach((p: any) => {
      const cells: Record<string, any[]> = {};
      p.blocks.forEach((b: any) => { if (b.role === 'table-cell' && fig[b.id]) (cells[fig[b.id]] ||= []).push(b); });
      Object.entries(cells).forEach(([fid, cs]) => {
        const id = `fig:${fid}`;
        if ((boxesOf[id] || []).some(x => x.page === p.page)) return;
        const x0 = Math.min(...cs.map(c => c.x)), y0 = Math.min(...cs.map(c => c.y));
        const x1 = Math.max(...cs.map(c => c.x + c.w)), y1 = Math.max(...cs.map(c => c.y + c.h));
        const b: Box = { id, role: 'table', page: p.page, x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
        (boxesOf[id] ||= []).push(b); byPage[p.page].push(b); byPage[p.page].sort((u, v) => u.y - v.y);
      });
    });
    return { boxesOf, byPage, pageOf, textOf };
  }, [a, L]);
  const titleOf = useCallback((id: string) => textOf[id] || id, [textOf]);
  const nPages = L?.pages?.length || 0;

  // ---- hover: outline the twin on the other side (straight on the DOM: no re-render of hundreds of boxes)
  const hot = useRef<string | null>(null);
  const setHot = (id: string | null) => {
    if (hot.current === id) return;
    const sel = (x: string) => `[data-box="${CSS.escape(x)}"],[data-bid="${CSS.escape(x)}"]`;
    if (hot.current) document.querySelectorAll(sel(hot.current)).forEach(e => e.classList.remove('bs-hot'));
    hot.current = id;
    if (id) document.querySelectorAll(sel(id)).forEach(e => e.classList.add('bs-hot'));
  };
  const flash = (els: Element[]) => els.forEach(e => { e.classList.remove('bs-flash'); void (e as HTMLElement).offsetWidth; e.classList.add('bs-flash'); });

  // ---- keeping the sides in step
  const collect = () => { if (R.current) rEls.current = Array.from(R.current.querySelectorAll<HTMLElement>('[data-bid]')); };
  useEffect(() => { collect(); }, [L, view]);
  const pageEl = (p: number) => K.current?.querySelector<HTMLElement>(`[data-scan-page="${p}"] > div`) || null;
  const scanY = (b: Box, frac: number) => {
    const el = pageEl(b.page);
    if (!el || !K.current) return null;
    return topIn(el, K.current) + ((b.y + frac * b.h) / (pageOf[b.page]?.h || 1)) * el.offsetHeight;
  };
  const followReading = () => {
    const r = R.current, k = K.current;
    if (!r || !k || !rEls.current.length) return;
    const y = r.scrollTop + OFF;
    const el = rEls.current[lastAbove(rEls.current, r, y)];
    const top = topIn(el, r);
    let frac = clamp((y - top) / Math.max(1, el.offsetHeight));
    const bs = boxesOf[el.dataset.bid!] || [];
    let target: number | null = null;
    if (bs.length) {
      const i = Math.min(bs.length - 1, Math.floor(frac * bs.length));
      frac = clamp(frac * bs.length - i);
      target = scanY(bs[i], frac);
      if (bs[i].page !== page) setPage(bs[i].page);
    } else {
      const p = Number(el.dataset.page || 1);
      const pe = pageEl(p);
      if (pe) target = topIn(pe, k);
    }
    if (target != null) k.scrollTop = target - OFF;
  };
  const followScan = () => {
    const r = R.current, k = K.current;
    if (!r || !k || !L) return;
    const y = k.scrollTop + OFF;
    const figs = Array.from(k.querySelectorAll<HTMLElement>('[data-scan-page] > div'));
    if (!figs.length) return;
    const pe = figs[lastAbove(figs, k, y)];
    const p = Number(pe.parentElement!.dataset.scanPage);
    if (p !== page) setPage(p);
    const H = pageOf[p]?.h || 1;
    const fy = ((y - topIn(pe, k)) / Math.max(1, pe.offsetHeight)) * H;
    const list = byPage[p] || [];
    if (!list.length) return;
    let pick = list.filter(b => b.y <= fy && fy <= b.y + b.h).sort((u, v) => u.h - v.h)[0];
    let frac = 0;
    if (pick) frac = clamp((fy - pick.y) / Math.max(1, pick.h));
    else { pick = list.find(b => b.y > fy) || list[list.length - 1]; frac = pick.y > fy ? 0 : 1; }
    const el = r.querySelector<HTMLElement>(`[data-bid="${CSS.escape(pick.id)}"]`);
    if (!el) return;
    const parts = boxesOf[pick.id] || [pick];
    const i = Math.max(0, parts.indexOf(pick));
    const f2 = (i + frac) / parts.length;
    r.scrollTop = topIn(el, r) + f2 * el.offsetHeight - OFF;
  };
  const onScroll = (who: 'R' | 'K') => () => {
    if (who === 'K') {
      // which page is in view, for the indicator, whoever drives
      if (view === 'scan' && K.current) {
        const figs = Array.from(K.current.querySelectorAll<HTMLElement>('[data-scan-page] > div'));
        if (figs.length) { const p = Number(figs[lastAbove(figs, K.current, K.current.scrollTop + OFF + 80)].parentElement!.dataset.scanPage); if (p !== page) setPage(p); }
      }
    }
    if (view !== 'beside' || driver.current !== who) return;
    if (tick.current) return;
    tick.current = requestAnimationFrame(() => { tick.current = 0; who === 'R' ? followReading() : followScan(); });
  };
  const drive = (who: 'R' | 'K') => () => { driver.current = who; };

  // ---- lazy images: load a page when it comes within two screens of the scan pane
  useEffect(() => {
    const k = K.current;
    if (!k || !L) return;
    const io = new IntersectionObserver(es => {
      const add: number[] = [];
      es.forEach(e => { if (e.isIntersecting) add.push(Number((e.target as HTMLElement).dataset.scanPage)); });
      if (add.length) setLoaded(s => { const n = new Set(s); add.forEach(x => n.add(x)); return n.size === s.size ? s : n; });
    }, { root: k, rootMargin: '200% 0px 200% 0px' });
    k.querySelectorAll('[data-scan-page]').forEach(e => io.observe(e));
    return () => io.disconnect();
  }, [L, view]);

  // ---- jumps
  const goPage = (p: number) => {
    const k = K.current, pe = pageEl(p);
    if (!k || !pe) return;
    driver.current = 'K';
    setLoaded(s => new Set([...Array.from(s), p, p + 1]));
    k.scrollTo({ top: topIn(pe, k) - OFF - 18, behavior: 'smooth' });
    setPage(p);
  };
  const toBlockOnScan = (id: string) => {
    const k = K.current, b = (boxesOf[id] || [])[0];
    if (!k || !b) return;
    driver.current = 'R';
    setLoaded(s => new Set([...Array.from(s), b.page]));
    setPage(b.page);
    const y = scanY(b, 0);
    if (y != null) k.scrollTo({ top: Math.max(0, y - k.clientHeight / 3), behavior: 'smooth' });
    flash(Array.from(k.querySelectorAll(`[data-box="${CSS.escape(id)}"]`)));
  };
  const toBlockInReading = (id: string) => {
    const r = R.current;
    const el = r?.querySelector<HTMLElement>(`[data-bid="${CSS.escape(id)}"]`);
    if (!r || !el) return;
    driver.current = 'K';
    const b0 = (boxesOf[id] || [])[0];
    if (b0) setPage(b0.page);
    r.scrollTo({ top: Math.max(0, topIn(el, r) - r.clientHeight / 3), behavior: 'smooth' });
    flash([el]);
  };
  const pending = useRef<string | null>(null);

  // the reading side: hover and click on a block; note calls scroll inside the pane
  const onReadingOver = (e: React.MouseEvent) => { const t = (e.target as HTMLElement).closest<HTMLElement>('[data-bid]'); setHot(t?.dataset.bid || null); };
  const onReadingClick = (e: React.MouseEvent) => {
    const call = (e.target as HTMLElement).closest('a.notecall') as HTMLAnchorElement | null;
    if (call) {
      const h = call.getAttribute('href') || '';
      const el = h.startsWith('#') ? R.current?.querySelector<HTMLElement>(`[id="${CSS.escape(h.slice(1))}"]`) : null;
      e.preventDefault();
      if (el && el.dataset.bid) { toBlockInReading(el.dataset.bid); toBlockOnScan(el.dataset.bid); }
      return;
    }
    if (window.getSelection()?.toString()) return;          // selecting text, not jumping
    const t = (e.target as HTMLElement).closest<HTMLElement>('[data-bid]');
    if (t?.dataset.bid) toBlockOnScan(t.dataset.bid);
    const sep = (e.target as HTMLElement).closest<HTMLElement>('[data-page-sep]');
    if (sep) goPage(Number(sep.dataset.pageSep));
  };
  const onScanOver = (e: React.MouseEvent) => { const t = (e.target as HTMLElement).closest<HTMLElement>('[data-box]'); setHot(t?.dataset.box || null); };
  const onScanClick = (e: React.MouseEvent) => {
    const t = (e.target as HTMLElement).closest<HTMLElement>('[data-box]');
    if (!t?.dataset.box) return;
    if (view === 'scan') { pending.current = t.dataset.box; onView('beside'); return; }
    toBlockInReading(t.dataset.box);
  };
  // after switching from "Scan only" to "Beside the scan" by a click on a box, bring its text into view
  useEffect(() => {
    if (view === 'beside' && pending.current) {
      const id = pending.current; pending.current = null;
      setTimeout(() => { collect(); toBlockInReading(id); }, 60);
    } else if (view === 'beside') {
      setTimeout(() => { collect(); driver.current = 'K'; followScan(); }, 60);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);
  // keys: [ and ] (or PageUp / PageDown with Alt) step through the pages
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.key === ']') goPage(Math.min(nPages, page + 1));
      if (e.key === '[') goPage(Math.max(1, page - 1));
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  });

  const scanWidth = view === 'scan' ? 1400 : 1000;
  const paneH = 'h-[calc(100vh-8.5rem)] min-h-[28rem]';
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm" data-testid="beside-scan-view" data-view={view}>
      <style>{STYLE}</style>
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-gray-200 sticky top-[3.25rem] z-10 bg-white/95 backdrop-blur rounded-t-xl">
        <ViewSwitch value={view} onChange={onView} />
        <div className="flex items-center gap-1 text-sm text-gray-600 ms-1" aria-label="Pages">
          <button className="p-1.5 rounded-md hover:bg-gray-100 disabled:opacity-40" onClick={() => goPage(Math.max(1, page - 1))} disabled={page <= 1} aria-label="Previous page" title="Previous page ( [ )"><ChevronLeft className="w-4 h-4" /></button>
          <span className="tabular-nums min-w-[7.5rem] text-center" data-testid="page-indicator">Page {page} of {nPages || '…'}{pageOf[page]?.folio ? <span className="text-gray-400"> · p. {pageOf[page].folio}</span> : null}</span>
          <button className="p-1.5 rounded-md hover:bg-gray-100 disabled:opacity-40" onClick={() => goPage(Math.min(nPages, page + 1))} disabled={page >= nPages} aria-label="Next page" title="Next page ( ] )"><ChevronRight className="w-4 h-4" /></button>
        </div>
        <div className="ms-auto flex flex-wrap items-center gap-1.5 text-xs">
          <div className="hidden xl:flex items-center gap-2.5 me-2 text-gray-500" aria-label="Legend">
            {LEGEND.map(([k, c]) => <span key={k} className="inline-flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm border-2" style={{ borderColor: c }} />{k}</span>)}
            {regions && <span className="inline-flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm border border-dashed border-gray-400" />Kept out</span>}
          </div>
          <button onClick={() => setShowBoxes(!showBoxes)} aria-pressed={showBoxes} className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border ${showBoxes ? 'border-indigo-200 bg-indigo-50 text-indigo-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`} title="Outline every block on the scan"><Square className="w-3.5 h-3.5" />Boxes</button>
          <button onClick={() => setRegions(!regions)} aria-pressed={regions} className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border ${regions ? 'border-indigo-200 bg-indigo-50 text-indigo-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`} title="Show what the reader kept out of the text: running heads, page numbers, another article"><LayoutPanelTop className="w-3.5 h-3.5" />Page furniture</button>
          {view === 'beside' && <button onClick={() => setSwap(!swap)} className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50" title="Swap the two sides"><ArrowLeftRight className="w-3.5 h-3.5" />Swap</button>}
        </div>
      </div>
      {err && <div className="p-4 text-sm text-red-700">{err}</div>}
      {!L ? !err && <div className="p-6 text-sm text-gray-500 flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />Loading the scan…</div> : (
        <div className={`grid ${view === 'beside' ? 'md:grid-cols-2' : 'grid-cols-1'} divide-x divide-gray-200`}>
          <div ref={R} onScroll={onScroll('R')} onWheel={drive('R')} onTouchStart={drive('R')} onPointerDown={drive('R')} onPointerEnter={drive('R')}
            onMouseOver={onReadingOver} onMouseLeave={() => setHot(null)} onClick={onReadingClick}
            className={`${view === 'beside' ? '' : 'hidden'} ${readingFirst ? 'order-1' : 'order-2'} ${paneH} overflow-y-auto overscroll-contain px-6 pb-[60vh] relative`} data-testid="reading-pane">
            <Reading a={a} pageOf={pageOf} />
          </div>
          <div ref={K} onScroll={onScroll('K')} onWheel={drive('K')} onTouchStart={drive('K')} onPointerDown={drive('K')} onPointerEnter={drive('K')}
            onMouseOver={onScanOver} onMouseLeave={() => setHot(null)} onClick={onScanClick}
            className={`${readingFirst ? 'order-2' : 'order-1'} ${paneH} overflow-y-auto overscroll-contain bg-gray-100 relative ${showBoxes ? 'bs-boxes' : ''}`} data-testid="scan-pane">
            <div className={`space-y-5 px-4 pt-3 pb-[60vh] mx-auto ${view === 'scan' ? 'max-w-4xl' : ''}`}>
              {L.pages.map((p: any) => (
                <ScanPage key={p.page} stem={a.stem} p={p} boxes={byPage[p.page] || []} regions={regions} load={loaded.has(p.page)} width={scanWidth} titleOf={titleOf} />))}
            </div>
          </div>
        </div>)}
      <p className="px-4 py-2 text-[11px] text-gray-400 border-t border-gray-100">
        {view === 'beside' ? 'Scroll either side: the other follows. Hover a block to outline it on the other side; click to jump there. [ and ] step through the pages.'
          : 'Hover a box to see what the reading made of it; click it to open the text beside the scan.'}
        {' '}Boxes are the platform's own (block parts on the ALTO page); dashed boxes are page furniture kept out of the text.
      </p>
    </div>
  );
};
export default BesideScan;

// the owner's "old platform" page (experiment 41's mirror page: every page of the scan with the reading beside it),
// shown inside the Desk as a fourth view (2026-10-23)
export const ClassicPage: React.FC<{ a: any; onView: (v: View) => void }> = ({ a, onView }) => (
  <div className="space-y-2" data-testid="classic-view">
    <div className="flex items-center justify-end gap-3">
      {a.version?.mirror && <a href={a.version.mirror} target="_blank" rel="noopener" className="text-xs text-indigo-700 hover:underline">open in a new tab ↗</a>}
      <ViewSwitch value="classic" onChange={onView} />
    </div>
    {a.version?.mirror
      ? <iframe src={a.version.mirror} title="Classic page" className="w-full h-[85vh] rounded-xl border border-gray-200 bg-white shadow-sm" />
      : <div className="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-500">No classic page was made for this article.</div>}
  </div>
);
