import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import {
  AlertTriangle, ArrowRight, CalendarCheck, Check, CheckCircle2, Expand, Gavel, Hourglass, Lightbulb, MapPin, Maximize2,
  Maximize, Milestone, Minimize, Minus, Plus, RotateCcw, Shrink, Target, Wallet, X, BarChart3, Flag, ExternalLink,
} from 'lucide-react';
import { DLink, Links, Sources, STATIC, Tx } from './ProjectDetails';

// The project page's Map tab (2026-10-26): the same project.json as the Details tab, drawn as a picture.
// Top: the journey line (gate 1 → gate 2 → gate 3 → the archive) with "you are here".
// Below: a mind map in the style of experiment 50's product map, drawn without any library: the centre, ten
// branches (five each side), each closed with a count; a click opens it into short labels (each item's `short`,
// at most six words); a click on a label opens the side panel with the item's full text and sources. Colour is
// status. Nodes drag (a branch takes its labels with it), the background pans, the wheel zooms; "Reset layout"
// forgets the drags. On a phone the map becomes a plain list that opens the same panel.

// ---------- status colours ----------
type Tone = 'done' | 'waiting' | 'next' | 'open' | 'parked' | 'risk' | 'fact';
const TONE: Record<Tone, { pill: string; dot: string; edge: string; label: string }> = {
  done:    { pill: 'bg-green-50 border-green-400 text-green-950',            dot: 'bg-green-500',  edge: '#86efac', label: 'Done / decided' },
  waiting: { pill: 'bg-amber-50 border-amber-400 text-amber-950',            dot: 'bg-amber-500',  edge: '#fcd34d', label: 'Waiting on you' },
  next:    { pill: 'bg-blue-50 border-blue-400 text-blue-950',               dot: 'bg-blue-500',   edge: '#93c5fd', label: 'Next / in progress' },
  open:    { pill: 'bg-white border-blue-300 border-dashed text-gray-900',   dot: 'bg-white ring-2 ring-inset ring-blue-400', edge: '#bfdbfe', label: 'Open idea' },
  parked:  { pill: 'bg-gray-100 border-gray-300 text-gray-600',              dot: 'bg-gray-400',   edge: '#d1d5db', label: 'Parked / dropped' },
  risk:    { pill: 'bg-red-50 border-red-300 text-red-950',                  dot: 'bg-red-500',    edge: '#fca5a5', label: 'Risk' },
  fact:    { pill: 'bg-white border-gray-300 text-gray-800',                 dot: 'bg-slate-400',  edge: '#cbd5e1', label: 'Fact / place' },
};
const IDEA_TONE: Record<string, Tone> = { done: 'done', 'in progress': 'next', open: 'open', parked: 'parked', dropped: 'parked' };
const STATUS_WORD: Record<Tone, string> = {
  done: 'done', waiting: 'waiting on you', next: 'next', open: 'open', parked: 'parked', risk: 'risk', fact: 'fact',
};

// ---------- the tree ----------
type Kind = 'goal' | 'waiting' | 'next' | 'done' | 'decision' | 'idea' | 'number' | 'money' | 'place' | 'risk' | 'gate';
export type MapNode = {
  id: string; label: string; level: 0 | 1 | 2 | 3; tone: Tone; side?: 1 | -1;
  icon?: any; value?: string; sub?: string; href?: string;
  kind?: Kind; data?: any; status?: string; children?: MapNode[];
};
const fmtDay = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][m - 1]}${y !== 2026 ? ' ' + y : ''}`;
};
const usd = (x: number) => `$${x.toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const label = (x: any, fallback: string) => x.short || fallback;

function groupBy<T>(xs: T[], key: (x: T) => string): [string, T[]][] {
  const out: [string, T[]][] = [];
  xs.forEach(x => { const k = key(x); const e = out.find(([kk]) => kk === k); if (e) e[1].push(x); else out.push([k, [x]]); });
  return out;
}

export function buildTree(d: any): MapNode {
  const leaf = (id: string, l: string, tone: Tone, kind: Kind, data: any, extra: Partial<MapNode> = {}): MapNode =>
    ({ id, label: l, level: 2, tone, kind, data, ...extra });
  const group = (id: string, l: string, tone: Tone, children: MapNode[]): MapNode =>
    ({ id, label: l, level: 2, tone, children: children.map(c => ({ ...c, level: 3 as const })) });

  const goals = (d.north_star || []).map((g: any) => leaf(`goal:${g.id}`, label(g, g.title), 'fact', 'goal', g));
  const waiting = (d.waiting_on_owner || []).map((w: any) => leaf(`wait:${w.id}`, label(w, w.title), 'waiting', 'waiting', w, { sub: w.urgency }));
  const nextG = ['this week', 'next', 'later'].map(k => [k, (d.next_steps || []).filter((s: any) => s.when === k).sort((a: any, b: any) => a.order - b.order)] as [string, any[]])
    .filter(([, xs]) => xs.length)
    .map(([k, xs]) => group(`next:${k}`, k[0].toUpperCase() + k.slice(1), 'next',
      xs.map((s: any) => leaf(`next:${s.order}`, label(s, s.title), 'next', 'next', s, { sub: s.cost && s.cost !== '$0' ? s.cost : undefined }))));
  const doneG = groupBy(d.timeline || [], (t: any) => t.date).map(([date, xs]) =>
    group(`done:${date}`, fmtDay(date), 'done', xs.map((t: any, i: number) => leaf(`done:${date}:${i}`, label(t, t.title), 'done', 'done', t))));
  const decG = [['Rules (D-numbers)', (x: any) => x.id.startsWith('D')], ["The owner's choices", (x: any) => !x.id.startsWith('D')]]
    .map(([l, f]: any) => group(`dec:${l}`, l, 'done', (d.decisions || []).filter(f).sort((a: any, b: any) => b.date.localeCompare(a.date))
      .map((x: any) => leaf(`dec:${x.id}`, label(x, x.choice), 'done', 'decision', x, { sub: x.id.startsWith('D') ? x.id : undefined }))))
    .filter(g => g.children!.length);
  const ideaOrder = ['in progress', 'open', 'parked', 'done', 'dropped'];
  const ideaG = ideaOrder.map(st => [st, (d.ideas || []).filter((x: any) => x.status === st)] as [string, any[]]).filter(([, xs]) => xs.length)
    .map(([st, xs]) => group(`idea:${st}`, st[0].toUpperCase() + st.slice(1), IDEA_TONE[st] || 'fact',
      xs.map((x: any) => leaf(`idea:${x.id}`, label(x, x.title), IDEA_TONE[x.status] || 'fact', 'idea', x, { status: x.status }))));
  const numG = groupBy(d.numbers || [], (x: any) => x.group).map(([g, xs]) => group(`num:${g}`, g, 'fact',
    xs.map((x: any) => leaf(`num:${x.id}`, label(x, x.label), 'fact', 'number', x, { value: x.value, sub: x.kind === 'estimate' ? 'estimate' : undefined }))));
  const m = d.money || {};
  const money: MapNode[] = [];
  if (m.spent) money.push(group('money:spent', `Spent ${usd(m.spent.value_usd)}`, 'fact',
    (m.spent_by || []).map((x: any, i: number) => leaf(`money:by:${i}`, label(x, x.label), 'fact', 'money', { ...x, _what: 'spent' }, { value: usd(x.usd) }))));
  if (m.credit) money.push(leaf('money:credit', `Credit left ${m.credit.left}`, 'waiting', 'money', { ...m.credit, _what: 'credit' }, { sub: m.credit.kind }));
  if (m.projections) money.push(group('money:next', 'What comes next would cost', 'next',
    m.projections.map((x: any, i: number) => leaf(`money:proj:${i}`, label(x, x.label), 'next', 'money', { ...x, _what: 'projection' }, { value: x.usd.replace(/^about /, '≈ ').replace(/\s*\(.*\)$/, '').replace(/, about .*$/, '') }))));
  if (m.deadline) money.push(leaf('money:deadline', label(m.deadline, m.deadline.text), 'risk', 'money', { ...m.deadline, _what: 'deadline' }));
  if (m.not_priced) money.push(leaf('money:notpriced', label(m.not_priced, m.not_priced.text), 'parked', 'money', { ...m.not_priced, _what: 'not priced' }));
  const placeG = groupBy(d.where_things_live || [], (x: any) => x.group).map(([g, xs]) => group(`place:${g}`, g, 'fact',
    xs.map((x: any) => leaf(`place:${x.name}`, label(x, x.name), 'fact', 'place', x, { href: x.href || undefined }))));
  const risks = (d.risks || []).map((r: any) => leaf(`risk:${r.id}`, label(r, r.title), 'risk', 'risk', r));

  const br = (id: string, l: string, icon: any, tone: Tone, side: 1 | -1, children: MapNode[]): MapNode =>
    ({ id: `b:${id}`, label: l, level: 1, icon, tone, side, children });
  return {
    id: 'root', label: 'Arabic Web of Science', level: 0, tone: 'fact',
    children: [
      // right: what to do (read first)
      br('goals', 'Goals', Target, 'fact', 1, goals),
      br('waiting', 'Waiting on you', Hourglass, 'waiting', 1, waiting),
      br('next', 'Next', Milestone, 'next', 1, nextG),
      br('done', 'Done', CalendarCheck, 'done', 1, doneG),
      br('risks', 'Risks', AlertTriangle, 'risk', 1, risks),
      // left: what we know
      br('decisions', 'Decisions', Gavel, 'done', -1, decG),
      br('ideas', 'Ideas', Lightbulb, 'next', -1, ideaG),
      br('numbers', 'Numbers', BarChart3, 'fact', -1, numG),
      br('money', 'Money', Wallet, 'fact', -1, money),
      br('places', 'Where things live', MapPin, 'fact', -1, placeG),
    ],
  };
}
const leaves = (n: MapNode): number => (n.children ? n.children.reduce((a, c) => a + leaves(c), 0) : 1);

// ---------- layout: a two-sided tidy tree ----------
const W = { root: 250, branch: 224, group: 190 };                  // fixed widths (edges start at the outer edge)
const GAP_X = { root: 70, branch: 56, group: 44 };
const ROW = { branch: 58, group: 38, leaf: 34 };
const BRANCH_GAP = 14;
const TOP = 46, BOTTOM = 46;                                       // the map's own bands: the tools above, the legend below
type Pos = { x: number; y: number; side: 1 | -1 | 0; parent?: string; w?: number; tone: Tone };

function layout(root: MapNode, open: Set<string>): Record<string, Pos> {
  const pos: Record<string, Pos> = { root: { x: 0, y: 0, side: 0, tone: 'fact', w: W.root } };
  const rowH = (n: MapNode) => (n.level === 1 ? ROW.branch : n.children ? ROW.group : ROW.leaf);
  const h = (n: MapNode): number => {
    const kids = n.children && open.has(n.id) ? n.children : null;
    if (!kids) return rowH(n);
    const sum = kids.reduce((a, c) => a + h(c), 0) + (kids.some(k => k.children) ? 8 * (kids.length - 1) : 0);
    return Math.max(rowH(n), sum);
  };
  const place = (n: MapNode, x: number, top: number, side: 1 | -1, parent: string) => {
    const hh = h(n);
    const w = n.level === 1 ? W.branch : n.children ? W.group : undefined;
    pos[n.id] = { x, y: top + hh / 2, side, parent, w, tone: n.tone };
    if (n.children && open.has(n.id)) {
      const cx = x + side * ((w || 0) + (n.level === 1 ? GAP_X.branch : GAP_X.group));
      const kids = n.children; const gap = kids.some(k => k.children) ? 8 : 0;
      const inner = kids.reduce((a, c) => a + h(c), 0) + gap * (kids.length - 1);
      let t = top + (hh - inner) / 2;
      kids.forEach(c => { place(c, cx, t, side, n.id); t += h(c) + gap; });
    }
  };
  ([1, -1] as const).forEach(side => {
    const bs = (root.children || []).filter(b => b.side === side);
    const total = bs.reduce((a, b) => a + h(b), 0) + BRANCH_GAP * (bs.length - 1);
    let t = -total / 2;
    bs.forEach(b => { place(b, side * (W.root / 2 + GAP_X.root), t, side, 'root'); t += h(b) + BRANCH_GAP; });
  });
  return pos;
}

// ---------- small persistence (per viewer, never needed) ----------
const KEY = 'project_map_v1';
const loadSaved = (): { open?: string[]; off?: Record<string, [number, number]> } => {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch { return {}; }
};
const save = (v: any) => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch { /* private window */ } };

function useNarrow(px = 768) {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const q = window.matchMedia(`(max-width: ${px - 1}px)`);
    const f = () => setNarrow(q.matches); f();
    q.addEventListener('change', f); return () => q.removeEventListener('change', f);
  }, [px]);
  return narrow;
}

// ---------- the journey line ----------
export function Journey({ d, onPick }: { d: any; onPick: (n: MapNode) => void }) {
  const roadmap: any[] = d.roadmap || [];
  const cur = roadmap.findIndex(g => g.id === d.stage?.current);
  const sizes = [44, 52, 62, 74];       // the stations grow: one journal → ten → the slice → the archive
  return (
    <section aria-label="The journey" className="rounded-2xl border border-gray-200 bg-white px-4 sm:px-8 pt-4 pb-4" data-testid="journey">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-2">
        <h2 className="text-base font-semibold text-gray-900">The journey</h2>
        <p className="text-sm text-gray-600" data-testid="stage">{d.stage?.label}</p>
      </div>
      <ol className="relative grid grid-cols-1 md:grid-cols-4 gap-6 md:gap-4">
        {/* the line behind the stations (desktop): green as far as we have come */}
        <div aria-hidden className="hidden md:block absolute left-[12.5%] right-[12.5%] top-[37px] h-1.5 rounded-full bg-gray-200" />
        <div aria-hidden className="hidden md:block absolute left-[12.5%] top-[37px] h-1.5 rounded-full bg-green-400"
          style={{ width: `${Math.max(0, cur) * 25}%` }} />
        {roadmap.map((g, i) => {
          const done = g.status === 'done'; const here = i === cur;
          const s = sizes[Math.min(i, sizes.length - 1)];
          return (
            <li key={g.id} className="relative flex md:flex-col items-center md:text-center gap-4 md:gap-0" data-testid={`station-${g.id}`}>
              <button type="button" onClick={() => onPick({ id: `gate:${g.id}`, label: g.name, level: 2, tone: done ? 'done' : here ? 'waiting' : 'parked', kind: 'gate', data: g })}
                className="relative shrink-0 md:h-[80px] flex items-center justify-center w-[80px] focus:outline-none group" aria-label={`${g.name}: ${g.status}`}>
                {here && <span aria-hidden className="absolute rounded-full bg-amber-300/50 animate-ping [animation-iteration-count:3]" style={{ width: s + 4, height: s + 4 }} />}
                <span className={`relative rounded-full grid place-items-center border-4 transition group-hover:scale-105 ${done ? 'bg-green-500 border-green-100 text-white' : here ? 'bg-amber-400 border-amber-100 text-amber-950' : 'bg-white border-gray-200 text-gray-400'}`}
                  style={{ width: s, height: s }}>
                  {done ? <Check className="w-6 h-6" strokeWidth={3} aria-hidden /> : here ? <Flag className="w-5 h-5" aria-hidden /> : <span className="text-sm font-semibold">{i + 1}</span>}
                </span>
                {here && <span className="hidden md:block absolute left-[calc(50%+40px)] top-1/2 -translate-y-1/2 whitespace-nowrap text-[11px] font-semibold uppercase tracking-wide text-amber-900 bg-amber-100 border border-amber-300 rounded-full px-2.5 py-0.5 shadow-sm" data-testid="you-are-here">◀ You are here</span>}
              </button>
              <div className="min-w-0 md:mt-1">
                {here && <div className="md:hidden inline-block mb-1 text-[11px] font-semibold uppercase tracking-wide text-amber-900 bg-amber-100 rounded-full px-2 py-0.5">You are here</div>}
                <div className={`text-lg font-semibold leading-tight ${done || here ? 'text-gray-900' : 'text-gray-500'}`}>{g.name}</div>
                <div className="text-xs text-gray-500 mt-0.5">{g.scope_short}</div>
                <div className={`text-sm mt-1.5 ${done || here ? 'text-gray-800' : 'text-gray-500'}`}>{g.short || g.proves}</div>
                <div className={`inline-block text-xs mt-1.5 rounded-full px-2 py-0.5 ${done ? 'bg-green-50 text-green-800' : here ? 'bg-amber-50 text-amber-900' : 'bg-gray-50 text-gray-500'}`}>{g.cost_short || g.cost}</div>
              </div>
            </li>);
        })}
      </ol>
    </section>);
}

// ---------- the side panel ----------
const Field: React.FC<{ k: string; children: React.ReactNode }> = ({ k, children }) => (
  <div><h3 className="text-[11px] uppercase tracking-wide font-semibold text-gray-500 mb-0.5">{k}</h3><div className="text-sm text-gray-800 leading-relaxed" dir="auto">{children}</div></div>);

function PanelBody({ n }: { n: MapNode }) {
  const x = n.data || {};
  switch (n.kind) {
    case 'goal': return <><Field k="Goal"><Tx t={x.title} /></Field><Field k="What it means"><Tx t={x.detail} /></Field></>;
    case 'waiting': return <>
      <Field k="Question"><Tx t={x.question} /></Field>
      <div className="rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-sm text-green-900 flex gap-2" dir="auto" data-testid="panel-recommended">
        <Check className="w-4 h-4 shrink-0 mt-0.5" aria-hidden /><span><span className="font-semibold">Recommended:</span> <Tx t={x.recommended} /></span></div>
      {x.unblocks && <Field k="Unblocks"><Tx t={x.unblocks} /></Field>}
      <Field k="When">{x.urgency}</Field>
      <Links links={x.links} /></>;
    case 'next': return <><Field k="Step"><Tx t={x.title} /></Field><Field k="Detail"><Tx t={x.detail} /></Field><Field k="When">{x.when} · step {x.order}</Field><Field k="Cost">{x.cost}</Field></>;
    case 'done': return <><Field k="Date">{x.date}</Field><Field k="What happened"><Tx t={x.what} /></Field>{x.why && <Field k="Why it matters"><Tx t={x.why} /></Field>}<Links links={x.links} /></>;
    case 'decision': return <><Field k="Decision"><Tx t={x.choice} /></Field>{x.why && <Field k="Why"><Tx t={x.why} /></Field>}<Field k="Decided">{x.date}{x.by ? ` · by ${x.by}` : ''}{x.id?.startsWith('D') ? ` · ${x.id}` : ''}</Field></>;
    case 'idea': return <><Field k="Idea"><Tx t={x.title} /></Field><Field k="Detail"><Tx t={x.detail} /></Field>
      {x.pick_up && <Field k="Pick up">{x.pick_up.startsWith('/') ? <DLink href={x.pick_up} className="text-indigo-700 hover:underline">{x.pick_up}</DLink> : <code className="text-xs break-all">{x.pick_up}</code>}</Field>}</>;
    case 'number': return <>
      <div className="text-3xl font-semibold text-gray-900 tabular-nums">{x.value}</div>
      <Field k="What it counts"><Tx t={x.label} /></Field>{x.sub && <Field k="Beside it"><Tx t={x.sub} /></Field>}
      <Field k="Measured">{x.date} · {x.kind}</Field></>;
    case 'money': return <>
      {x.usd != null && <div className="text-2xl font-semibold text-gray-900 tabular-nums">{typeof x.usd === 'number' ? usd(x.usd) : x.usd}</div>}
      {x.left && <div className="text-2xl font-semibold text-gray-900">{x.left}</div>}
      {x.label && <Field k={x._what === 'projection' ? 'Would pay for' : 'Spent on'}><Tx t={x.label} /></Field>}
      {x.text && <Field k={x._what === 'deadline' ? 'Deadline' : 'Not priced yet'}><Tx t={x.text} /></Field>}
      {x.topup && <Field k="Top-up">{x.topup}</Field>}{x.note && <Field k="Note"><Tx t={x.note} /></Field>}
      {x.kind && <Field k="Kind">{x.kind}</Field>}</>;
    case 'place': return <>
      {x.href && <DLink href={x.href} className="inline-flex items-center gap-1 text-sm text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded px-2 py-1">Open {x.name}<ArrowRight className="w-3.5 h-3.5" aria-hidden /></DLink>}
      <Field k="What is there"><Tx t={x.what} /></Field>{x.path && <Field k="Path"><code className="text-xs break-all">{x.path}</code></Field>}</>;
    case 'risk': return <><Field k="Risk"><Tx t={x.title} /></Field><Field k="Detail"><Tx t={x.detail} /></Field></>;
    case 'gate': return <><Field k="What it covers"><Tx t={x.scope} /></Field><Field k="Cost"><Tx t={x.cost} /></Field><Field k="What it proves"><Tx t={x.proves} /></Field><Field k="Status">{x.status}</Field><Links links={x.links} /></>;
    default: return null;
  }
}

function Panel({ n, onClose }: { n: MapNode; onClose: () => void }) {
  const x = n.data || {};
  const date = x.date || (n.kind === 'number' ? x.date : null);
  const status = n.kind === 'idea' ? x.status : n.kind === 'gate' ? x.status : n.kind === 'decision' ? 'decided' : n.kind === 'number' ? x.kind : STATUS_WORD[n.tone];
  useEffect(() => {
    const f = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', f); return () => window.removeEventListener('keydown', f);
  }, [onClose]);
  return (
    <aside role="dialog" aria-label={n.label} data-testid="map-panel"
      className="fixed z-30 bg-white border border-gray-200 shadow-2xl flex flex-col
                 inset-x-0 bottom-0 max-h-[70vh] rounded-t-2xl
                 md:inset-x-auto md:bottom-4 md:top-20 md:right-4 md:w-[26rem] md:max-h-none md:rounded-2xl">
      <header className="px-5 pt-4 pb-3 border-b border-gray-100 relative">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className={`inline-block w-2.5 h-2.5 rounded-full ${TONE[n.tone].dot}`} aria-hidden />
          <span className="font-medium text-gray-700">{status}</span>{date && <span className="tabular-nums">· {date}</span>}
        </div>
        <h2 className="text-lg font-semibold text-gray-900 mt-1 pr-8 leading-snug" dir="auto"><Tx t={n.kind === 'gate' ? x.name : x.title || x.choice || x.name || x.label || n.label} /></h2>
        <button onClick={onClose} className="absolute top-3 right-3 p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100" aria-label="Close"><X className="w-5 h-5" /></button>
      </header>
      <div className="px-5 py-4 space-y-3 overflow-auto">
        <PanelBody n={n} />
        <Sources s={x.source} className="pt-1" />
      </div>
    </aside>);
}

// ---------- the map ----------
function Pill({ n, here, sel, isOpen, count, onDown, onKey, refFn }: { n: MapNode; here: Pos; sel: boolean; isOpen: boolean; count: number; onDown: (e: React.PointerEvent, n: MapNode) => void; onKey: (n: MapNode) => void; refFn: (el: HTMLElement | null) => void }) {
  const t = TONE[n.tone];
  const side = here.side;
  const tf = side === 0 ? 'translate(-50%,-50%)' : side === -1 ? 'translate(-100%,-50%)' : 'translate(0,-50%)';
  const style: React.CSSProperties = { left: here.x, top: here.y, transform: tf, width: here.w };
  const common = {
    ref: refFn as any, style, 'data-node': n.id, onPointerDown: (e: React.PointerEvent) => onDown(e, n), title: n.href ? `Open ${n.href}` : undefined,
    tabIndex: n.level === 0 || n.href ? undefined : 0,
    onKeyDown: (e: React.KeyboardEvent) => { if (!n.href && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onKey(n); } },
    // a link opens on pointer-up (so a drag never follows it); the keyboard's Enter still follows it natively
    onClick: n.href ? (e: React.MouseEvent) => { if (e.detail !== 0) e.preventDefault(); } : undefined,
  };
  if (n.level === 0) return (
    <div {...common} className="absolute select-none cursor-grab rounded-3xl bg-indigo-600 text-white text-center px-5 py-4 shadow-lg" data-testid="map-root">
      <div className="text-lg font-semibold leading-tight">{n.label}</div>
      <div className="text-xs text-indigo-100 mt-0.5">the project, on one page</div>
    </div>);
  if (n.level === 1) {
    const Icon = n.icon;
    return (
      <div {...common} role="button" aria-expanded={isOpen} data-testid={`branch-${n.id.slice(2)}`}
        className={`absolute select-none cursor-pointer rounded-2xl border-2 bg-white px-3.5 py-2.5 shadow-sm hover:shadow-md flex items-center gap-2.5 ${sel ? 'ring-4 ring-indigo-200' : ''} ${side === -1 ? 'flex-row-reverse text-right' : ''}`}
        style={{ ...style, borderColor: n.tone === 'fact' ? '#cbd5e1' : t.edge }}>
        <span className={`w-8 h-8 rounded-xl grid place-items-center shrink-0 ${t.pill.split(' ').filter(c => c.startsWith('bg-') || c.startsWith('text-')).join(' ')}`}><Icon className="w-4.5 h-4.5 w-[18px] h-[18px]" aria-hidden /></span>
        <span className="text-[15px] font-semibold text-gray-900 flex-1 leading-tight whitespace-nowrap">{n.label}</span>
        <span className={`min-w-[1.75rem] text-center text-xs font-semibold rounded-full px-1.5 py-0.5 ${n.tone === 'waiting' ? 'bg-amber-500 text-white' : isOpen ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`} data-testid="count">{isOpen ? '−' : count}</span>
      </div>);
  }
  if (n.children) return (
    <div {...common} role="button" aria-expanded={isOpen}
      className={`absolute select-none cursor-pointer rounded-xl border ${t.pill} px-3 py-1.5 flex items-center gap-2 text-[13px] font-semibold ${side === -1 ? 'flex-row-reverse text-right' : ''}`}>
      <span className="flex-1 truncate" dir="auto">{n.label}</span>
      <span className="text-[11px] font-medium rounded-full bg-white/80 border border-black/5 px-1.5 text-gray-600">{isOpen ? '−' : count}</span>
    </div>);
  const inner = (<>
    <span className={`w-2 h-2 rounded-full shrink-0 ${t.dot}`} aria-hidden />
    {n.value && <span className="font-semibold tabular-nums whitespace-nowrap">{n.value}</span>}
    <span className="whitespace-nowrap" dir="auto"><Tx t={n.label} /></span>
    {n.sub && <span className="text-[11px] text-gray-500 whitespace-nowrap">· {n.sub}</span>}
    {n.href && <ExternalLink className="w-3 h-3 text-indigo-500 shrink-0" aria-hidden />}
  </>);
  const cls = `absolute select-none cursor-pointer rounded-full border ${t.pill} px-3 py-[3px] text-[13px] flex items-center gap-1.5 hover:shadow ${sel ? 'ring-4 ring-indigo-200' : ''} ${side === -1 ? 'flex-row-reverse' : ''}`;
  return n.href
    ? <a {...common} href={n.href} draggable={false} className={`${cls} no-underline`} data-testid="map-link">{inner}</a>
    : <div {...common} role="button" className={cls} data-testid="map-leaf">{inner}</div>;
}

export default function ProjectMap({ d }: { d: any }) {
  const router = useRouter();
  const narrow = useNarrow();
  const tree = useMemo(() => buildTree(d), [d]);
  const byId = useMemo(() => { const m: Record<string, MapNode> = {}; const w = (n: MapNode) => { m[n.id] = n; n.children?.forEach(w); }; w(tree); return m; }, [tree]);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [off, setOff] = useState<Record<string, [number, number]>>({});
  const [sel, setSel] = useState<MapNode | null>(null);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const [anim, setAnim] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const els = useRef<Record<string, HTMLElement | null>>({});
  const pendingFocus = useRef<string | null>('__fit');
  const ready = useRef(false);

  useEffect(() => { const s = loadSaved(); if (s.open) setOpen(new Set(s.open.filter(x => byId[x]))); if (s.off) setOff(s.off); ready.current = true; }, [byId]);
  useEffect(() => { if (ready.current) save({ open: Array.from(open), off }); }, [open, off]);

  const base = useMemo(() => layout(tree, open), [tree, open]);
  // drags add up down the tree: a dragged branch takes its children along
  const pos = useMemo(() => {
    const out: Record<string, Pos> = {};
    const acc = (id: string): [number, number] => {
      const p = base[id]; const o = off[id] || [0, 0];
      if (!p?.parent) return o;
      const a = acc(p.parent); return [a[0] + o[0], a[1] + o[1]];
    };
    Object.entries(base).forEach(([id, p]) => { const [dx, dy] = acc(id); out[id] = { ...p, x: p.x + dx, y: p.y + dy }; });
    return out;
  }, [base, off]);

  const bbox = useCallback((ids: string[]) => {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    ids.forEach(id => {
      const p = pos[id]; const el = els.current[id]; if (!p) return;
      const w = el?.offsetWidth || p.w || 180; const h = el?.offsetHeight || 32;
      const l = p.side === 0 ? p.x - w / 2 : p.side === -1 ? p.x - w : p.x;
      x0 = Math.min(x0, l); x1 = Math.max(x1, l + w); y0 = Math.min(y0, p.y - h / 2); y1 = Math.max(y1, p.y + h / 2);
    });
    return { x0, y0, x1, y1 };
  }, [pos]);
  const animate = () => { setAnim(true); window.setTimeout(() => setAnim(false), 420); };
  const fit = useCallback((smooth = true) => {
    const el = box.current; if (!el || !el.clientWidth) return;
    const b = bbox(Object.keys(pos)); const pad = 24;
    const H_ = el.clientHeight - TOP - BOTTOM;
    const k = Math.min(1.1, Math.max(0.35, Math.min((el.clientWidth - 2 * pad) / (b.x1 - b.x0), H_ / (b.y1 - b.y0))));
    if (smooth) animate();
    setView({ k, x: el.clientWidth / 2 - k * (b.x0 + b.x1) / 2, y: TOP + H_ / 2 - k * (b.y0 + b.y1) / 2 });
  }, [bbox, pos]);
  // after an opening: bring the opened part into view, readable (scale at least 0.8), its top first if it is tall
  const reveal = useCallback((id: string) => {
    const el = box.current; if (!el || !el.clientWidth) return;
    const ids: string[] = []; const w = (n: MapNode) => { if (pos[n.id]) ids.push(n.id); if (open.has(n.id)) n.children?.forEach(w); }; w(byId[id]);
    const all = bbox(Object.keys(pos)); const b = bbox(ids); const pad = 24; const W_ = el.clientWidth, H_ = el.clientHeight - TOP - BOTTOM;
    // the whole map at a readable size if it fits, else the opened part (its top first when it is tall)
    const kAll = Math.min((W_ - 2 * pad) / (all.x1 - all.x0), H_ / (all.y1 - all.y0));
    if (kAll >= 0.8) { animate(); const k = Math.min(1.1, kAll); setView({ k, x: W_ / 2 - k * (all.x0 + all.x1) / 2, y: TOP + H_ / 2 - k * (all.y0 + all.y1) / 2 }); return; }
    const k = Math.max(0.85, Math.min(1, (W_ - 2 * pad) / (b.x1 - b.x0), H_ / (b.y1 - b.y0)));
    // horizontally: the centre too, when it fits beside the opened part
    const r = bbox(['root']); const ux0 = Math.min(b.x0, r.x0), ux1 = Math.max(b.x1, r.x1);
    const x = k * (ux1 - ux0) <= W_ - 2 * pad ? W_ / 2 - k * (ux0 + ux1) / 2 : W_ / 2 - k * (b.x0 + b.x1) / 2;
    const tall = k * (b.y1 - b.y0) > H_;
    const y = tall ? TOP - k * b.y0 : TOP + H_ / 2 - k * (b.y0 + b.y1) / 2;
    animate(); setView({ k, x, y });
  }, [bbox, pos, open, byId]);
  useLayoutEffect(() => {
    const f = pendingFocus.current; if (!f) return;
    pendingFocus.current = null;
    if (f === '__fit') fit(false); else reveal(f);
  });
  useEffect(() => { const r = () => fit(false); window.addEventListener('resize', r); return () => window.removeEventListener('resize', r); }, [fit]);

  const toggle = (n: MapNode) => {
    setOpen(prev => {
      const s = new Set(prev);
      if (s.has(n.id)) {
        s.delete(n.id);
        const w = (m: MapNode) => { s.delete(m.id); m.children?.forEach(w); }; n.children?.forEach(w);
      } else {
        s.add(n.id);
        // a branch of groups opens its groups too, unless that makes a long column: then only the first
        const gs = (n.children || []).filter(c => c.children);
        // (the first groups, while they stay within about twelve labels; always the first)
        let shown = 0;
        gs.forEach((g, i) => { const c = leaves(g); if (i === 0 || shown + c <= 12) { s.add(g.id); shown += c; } else shown = Infinity; });
      }
      return s;
    });
    pendingFocus.current = n.id;
  };
  const setAll = (on: boolean) => {
    if (on) { const s = new Set<string>(); Object.values(byId).forEach(n => { if (n.children) s.add(n.id); }); setOpen(s); }
    else setOpen(new Set());
    pendingFocus.current = '__fit';
  };

  // pointer: drag a node, pan the background, click = open / show
  const drag = useRef<{ id: string | null; sx: number; sy: number; moved: boolean; vx: number; vy: number; o: [number, number]; n?: MapNode } | null>(null);
  const onNodeDown = (e: React.PointerEvent, n: MapNode) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    drag.current = { id: n.id, sx: e.clientX, sy: e.clientY, moved: false, vx: view.x, vy: view.y, o: off[n.id] || [0, 0], n };
  };
  const onBgDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    drag.current = { id: null, sx: e.clientX, sy: e.clientY, moved: false, vx: view.x, vy: view.y, o: [0, 0] };
  };
  const onMove = (e: React.PointerEvent) => {
    const g = drag.current; if (!g) return;
    const dx = e.clientX - g.sx, dy = e.clientY - g.sy;
    if (!g.moved && Math.hypot(dx, dy) < 4) return;
    g.moved = true;
    if (g.id) { const id = g.id; setOff(o => ({ ...o, [id]: [g.o[0] + dx / view.k, g.o[1] + dy / view.k] })); }
    else setView(v => ({ ...v, x: g.vx + dx, y: g.vy + dy }));
  };
  const activate = (n: MapNode) => {
    if (n.level === 0) return;
    if (n.children) { toggle(n); return; }
    if (n.href) { if (STATIC.test(n.href)) window.location.href = n.href; else router.push(n.href); return; }
    setSel(n);
  };
  const onUp = () => {
    const g = drag.current; drag.current = null;
    if (g && !g.moved && g.n) activate(g.n);
  };
  // wheel zooms round the pointer
  useEffect(() => {
    const el = box.current; if (!el) return;
    const f = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect(); const cx = e.clientX - r.left, cy = e.clientY - r.top;
      setView(v => { const k = Math.min(2.5, Math.max(0.3, v.k * Math.exp(-e.deltaY * 0.0015))); return { k, x: cx - (cx - v.x) * (k / v.k), y: cy - (cy - v.y) * (k / v.k) }; });
    };
    el.addEventListener('wheel', f, { passive: false }); return () => el.removeEventListener('wheel', f);
  }, [narrow]);
  const zoomBy = (f: number) => { const el = box.current; if (!el) return; const cx = el.clientWidth / 2, cy = el.clientHeight / 2; animate(); setView(v => { const k = Math.min(2.5, Math.max(0.3, v.k * f)); return { k, x: cx - (cx - v.x) * (k / v.k), y: cy - (cy - v.y) * (k / v.k) }; }); };

  const shown = Object.keys(pos);
  const edges = shown.filter(id => pos[id].parent).map(id => {
    const c = pos[id], p = pos[c.parent!];
    const px = p.side === 0 ? p.x + c.side * (W.root / 2) : p.x + p.side * (p.w || 0);
    const mx = (px + c.x) / 2;
    return { id, d: `M${px},${p.y} C${mx},${p.y} ${mx},${c.y} ${c.x},${c.y}`, color: TONE[c.tone].edge, w: byId[id].level === 1 ? 3 : 2 };
  });

  // full screen: the map and its side panel together (the browser's Fullscreen API; Esc leaves it)
  const full = useRef<HTMLDivElement>(null);
  const [isFull, setIsFull] = useState(false);
  useEffect(() => {
    const on = () => { setIsFull(document.fullscreenElement === full.current); pendingFocus.current = '__fit'; setTimeout(() => fit(), 120); };
    document.addEventListener('fullscreenchange', on);
    return () => document.removeEventListener('fullscreenchange', on);
  });
  const toggleFull = () => {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else full.current?.requestFullscreen?.().catch(() => {});
  };

  return (<>
    <Journey d={d} onPick={setSel} />
    <div ref={full} className={isFull ? 'bg-[#fbfbf9]' : ''}>
    {narrow ? <MapList tree={tree} onPick={setSel} /> : (
      <section aria-label="The project map" className={`relative bg-[#fbfbf9] overflow-hidden ${isFull ? '' : 'rounded-2xl border border-gray-200'}`}
        style={{ height: isFull ? '100vh' : 'max(460px, calc(100vh - 400px))' }} data-testid="project-map">
        <div ref={box} className="absolute inset-0 cursor-grab active:cursor-grabbing touch-none"
          onPointerDown={onBgDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={() => { drag.current = null; }}>
          <div className="absolute left-0 top-0 origin-top-left" style={{ transform: `translate(${view.x}px,${view.y}px) scale(${view.k})`, transition: anim ? 'transform 400ms cubic-bezier(.2,.7,.2,1)' : undefined }}>
            <svg className="absolute left-0 top-0 overflow-visible pointer-events-none" width="1" height="1" aria-hidden>
              {edges.map(e => <path key={e.id} d={e.d} fill="none" stroke={e.color} strokeWidth={e.w} strokeLinecap="round" />)}
            </svg>
            {shown.map(id => {
              const n = byId[id];
              return <Pill key={id} n={n} here={pos[id]} sel={sel?.id === id} isOpen={open.has(id)} count={leaves(n)} onDown={onNodeDown} onKey={activate} refFn={el => { els.current[id] = el; }} />;
            })}
          </div>
        </div>
        {/* tools */}
        <div className="absolute top-3 right-3 flex items-center gap-1.5" onPointerDown={e => e.stopPropagation()}>
          <ToolBtn onClick={() => setAll(true)} icon={Expand} label="Open all" />
          <ToolBtn onClick={() => setAll(false)} icon={Shrink} label="Close all" />
          <ToolBtn onClick={() => fit()} icon={Maximize2} label="Fit" />
          <ToolBtn onClick={toggleFull} icon={isFull ? Minimize : Maximize} label={isFull ? 'Exit full screen' : 'Full screen'} testid="map-fullscreen" />
          <ToolBtn onClick={() => { setOff({}); pendingFocus.current = '__fit'; }} icon={RotateCcw} label="Reset layout" testid="reset-layout" />
          <span className="inline-flex rounded-lg border border-gray-200 bg-white overflow-hidden">
            <button onClick={() => zoomBy(1.2)} className="p-1.5 hover:bg-gray-50" aria-label="Zoom in"><Plus className="w-4 h-4 text-gray-600" /></button>
            <button onClick={() => zoomBy(1 / 1.2)} className="p-1.5 hover:bg-gray-50 border-l border-gray-200" aria-label="Zoom out"><Minus className="w-4 h-4 text-gray-600" /></button>
          </span>
        </div>
        <div className="absolute top-3 left-3 text-xs text-gray-500 pointer-events-none bg-[#fbfbf9]/90 rounded-lg px-1.5 py-1">Click a branch to open it · click a label for the full story · drag to move · scroll to zoom</div>
        <Legend className="absolute left-3 bottom-3" />
      </section>)}
    {sel && <Panel n={sel} onClose={() => setSel(null)} />}
    </div>
  </>);
}

const ToolBtn: React.FC<{ onClick: () => void; icon: any; label: string; testid?: string }> = ({ onClick, icon: Icon, label, testid }) => (
  <button onClick={onClick} data-testid={testid} className="inline-flex items-center gap-1.5 text-xs text-gray-700 bg-white border border-gray-200 hover:border-indigo-300 hover:text-indigo-700 rounded-lg px-2.5 py-1.5">
    <Icon className="w-3.5 h-3.5" aria-hidden />{label}</button>);

function Legend({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-white/95 border border-gray-200 rounded-xl px-3 py-2 flex flex-wrap gap-x-3.5 gap-y-1 text-[11px] text-gray-600 ${className}`} data-testid="legend" onPointerDown={e => e.stopPropagation()}>
      {(Object.keys(TONE) as Tone[]).map(t => <span key={t} className="inline-flex items-center gap-1.5"><span className={`w-2.5 h-2.5 rounded-full ${TONE[t].dot}`} aria-hidden />{TONE[t].label}</span>)}
    </div>);
}

// ---------- the phone: the same tree as a plain list ----------
function MapList({ tree, onPick }: { tree: MapNode; onPick: (n: MapNode) => void }) {
  const Leaf = ({ n }: { n: MapNode }) => {
    const inner = (<><span className={`w-2.5 h-2.5 rounded-full shrink-0 mt-1.5 ${TONE[n.tone].dot}`} aria-hidden />
      <span className="flex-1 min-w-0">{n.value && <b className="tabular-nums mr-1">{n.value}</b>}<Tx t={n.label} />{n.sub && <span className="text-xs text-gray-500"> · {n.sub}</span>}</span>
      {n.href ? <ExternalLink className="w-3.5 h-3.5 text-indigo-500 mt-1" aria-hidden /> : <ArrowRight className="w-3.5 h-3.5 text-gray-300 mt-1" aria-hidden />}</>);
    const cls = 'w-full text-left flex items-start gap-2 py-2 text-sm text-gray-800';
    return <li>{n.href ? <DLink href={n.href} className={cls}>{inner}</DLink> : <button type="button" onClick={() => onPick(n)} className={cls}>{inner}</button>}</li>;
  };
  return (
    <section aria-label="The project, as a list" className="space-y-2" data-testid="map-list">
      <Legend />
      {(tree.children || []).map(b => {
        const Icon = b.icon;
        return (
          <details key={b.id} className="rounded-2xl border border-gray-200 bg-white group">
            <summary className="list-none flex items-center gap-3 px-4 py-3 cursor-pointer">
              <span className={`w-8 h-8 rounded-xl grid place-items-center ${TONE[b.tone].pill.split(' ').filter(c => c.startsWith('bg-') || c.startsWith('text-')).join(' ')}`}><Icon className="w-[18px] h-[18px]" aria-hidden /></span>
              <span className="flex-1 font-semibold text-gray-900">{b.label}</span>
              <span className={`text-xs font-semibold rounded-full px-2 py-0.5 ${b.tone === 'waiting' ? 'bg-amber-500 text-white' : 'bg-gray-100 text-gray-700'}`}>{leaves(b)}</span>
            </summary>
            <div className="px-4 pb-3 divide-y divide-gray-100 border-t border-gray-100">
              {(b.children || []).map(c => c.children ? (
                <div key={c.id} className="pt-2">
                  <div className="text-[11px] uppercase tracking-wide font-semibold text-gray-500">{c.label}</div>
                  <ul>{c.children.map(x => <Leaf key={x.id} n={x} />)}</ul>
                </div>) : <ul key={c.id}><Leaf n={c} /></ul>)}
            </div>
          </details>);
      })}
    </section>);
}
