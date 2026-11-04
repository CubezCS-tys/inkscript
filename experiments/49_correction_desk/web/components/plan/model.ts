// The plan page (pages/plan.tsx): the shape of GET /desk/api/plan (desk/plan.py) and the pure maths of the timeline
// (time zones, the window, the layout of bars and their labels). No React here. Times are epoch seconds; the axis is
// UK time (the owner's), the server's time is shown on hover.

export type Status = 'planned' | 'running' | 'done' | 'live' | 'parked' | 'dropped' | 'blocked-on-owner';
export type Link = { label: string; href: string };
export type Item = {
  id: string; title: string; desc?: string; lane: string; status: Status;
  planned_start?: string; planned_end?: string; start?: string; end?: string;
  outcome?: string; cost?: string; links?: Link[]; readme?: string; source?: string[]; approx?: string;
  exp?: string; after?: string; waits_on?: string; watch?: string; urgency?: string; recommended?: string;
  unblocks?: string; by?: string; by_whom?: string; added_by?: string; priority?: number;
  synthetic?: 'more-needs';       // the page's own "+N more waiting on you" row, never in the file
};
export type Promise_ = {
  id: string; title: string; detail?: string; made_at?: string; due?: string; status: 'open' | 'kept' | 'dropped';
  closed_at?: string; by?: string; item?: string; outcome?: string; source?: string[];
};
export type Marker = {
  id: string; kind: 'release' | 'deploy' | 'eval' | 'alert' | 'milestone'; at: string; end?: string; label: string;
  detail?: string; href?: string; item?: string; source?: string[];
};
export type Lane = { key: string; label: string; sub?: string };
export type Activity = { at: number; source: 'beat' | 'folder' | 'start'; note?: string; by?: string };
export type PlanData = {
  now: number; server_tz: string; owner_tz: string; file: string; file_mtime: number | null;
  plan: { meta: any; lanes: Lane[]; items: Item[]; promises: Promise_[]; markers: Marker[];
    log: { at: string; by: string; action: string; id: string | null }[] };
  live: {
    releases: { id: string; at: number; live: boolean; copy: boolean; summary: boolean }[];
    deploys: { at: number; label: string; detail: string }[];
    results: { item: string; at: number; readme: string }[];
    activity: Record<string, Activity>; stale: string[]; overdue: string[]; stale_after_s: number;
  };
  counts: { running: number; needs_you: number; next: number; live: number; stale: number; overdue: number; promises_open: number };
  problems: string[];
};

export const ep = (s?: string | null): number | null => {
  if (!s) return null;
  const t = Date.parse(s);
  return Number.isFinite(t) ? t / 1000 : null;
};

// ── time zones ──────────────────────────────────────────────────────────────────────────────────────────────
export const UK = 'Europe/London';
const fmts: Record<string, Intl.DateTimeFormat> = {};
const fmt = (tz: string, o: Intl.DateTimeFormatOptions) => {
  const k = tz + JSON.stringify(o);
  if (!fmts[k]) fmts[k] = new Intl.DateTimeFormat('en-GB', { timeZone: tz, ...o });
  return fmts[k];
};
export type Parts = { y: number; mo: number; d: number; h: number; mi: number; wd: string; mon: string };
const partsCache = new Map<string, Parts>();
export const partsIn = (tz: string, t: number): Parts => {
  const key = `${tz}|${Math.floor(t / 60)}`;
  const c = partsCache.get(key);
  if (c) return c;
  const ps = fmt(tz, { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', weekday: 'short', hourCycle: 'h23' })
    .formatToParts(new Date(t * 1000));
  const g = (k: string) => ps.find(p => p.type === k)?.value || '';
  const mon = fmt(tz, { month: 'short' }).format(new Date(t * 1000));
  const r = { y: +g('year'), mo: +g('month'), d: +g('day'), h: +g('hour') % 24, mi: +g('minute'), wd: g('weekday'), mon };
  if (partsCache.size > 20000) partsCache.clear();
  partsCache.set(key, r);
  return r;
};
const p2 = (n: number) => String(n).padStart(2, '0');
export const hm = (tz: string, t: number) => { const p = partsIn(tz, t); return `${p2(p.h)}:${p2(p.mi)}`; };
export const dayLabel = (tz: string, t: number) => { const p = partsIn(tz, t); return `${p.wd} ${p.d} ${p.mon}`; };
export const sameDay = (tz: string, a: number, b: number) => { const p = partsIn(tz, a), q = partsIn(tz, b); return p.y === q.y && p.mo === q.mo && p.d === q.d; };
// "Mon 2 Nov 16:20" (UK), the day left out when it is today
export const whenUK = (t: number | null | undefined, now?: number) => {
  if (t == null) return '—';
  return now != null && sameDay(UK, t, now) ? `today ${hm(UK, t)}` : `${dayLabel(UK, t)} ${hm(UK, t)}`;
};
export const whenTz = (tz: string, t: number | null | undefined) => (t == null ? '—' : `${dayLabel(tz, t)} ${hm(tz, t)}`);
export const tzShort = (tz: string) => (tz.split('/').pop() || tz).replace(/_/g, ' ');

// "45 min", "3.5 h", "2.1 days"
export const durText = (s: number): string => {
  const m = Math.max(0, Math.round(s / 60));
  if (m < 90) return `${m} min`;
  if (m < 48 * 60) return `${(m / 60).toFixed(1).replace(/\.0$/, '')} h`;
  return `${(m / 1440).toFixed(1).replace(/\.0$/, '')} days`;
};
export const agoText = (s: number) => (s < 90 ? 'just now' : `${durText(s)} ago`);

// ── the window, always from "now" ───────────────────────────────────────────────────────────────────────────
export type Zoom = 'day' | 'week' | 'month' | 'all';
export const ZOOMS: Zoom[] = ['day', 'week', 'month', 'all'];
const H = 3600, D = 86400;
export const windowFor = (z: Zoom, now: number, d: PlanData): { start: number; end: number } => {
  if (z === 'day') return { start: now - 18 * H, end: now + 6 * H };
  if (z === 'week') return { start: now - 7 * D, end: now + 7 * D };
  if (z === 'month') return { start: now - 30 * D, end: now + 7 * D };
  let a = now - 7 * D, b = now + 2 * D;
  for (const it of d.plan.items) {
    for (const s of [it.start, it.planned_start]) { const t = ep(s); if (t != null) a = Math.min(a, t); }
    for (const s of [it.end, it.planned_end]) { const t = ep(s); if (t != null && t < now + 90 * D) b = Math.max(b, t); }
  }
  for (const p of d.plan.promises) { const t = ep(p.due); if (t != null && t < now + 90 * D) b = Math.max(b, t); }
  return { start: a - 12 * H, end: b + 12 * H };
};

// ── what a bar is ───────────────────────────────────────────────────────────────────────────────────────────
// the solid span (what happened) and the faint one (what was planned)
export const spans = (it: Item, now: number) => {
  const s = ep(it.start), e = ep(it.end);
  const ps = ep(it.planned_start), pe = ep(it.planned_end);
  let actual: [number, number] | null = null;
  if (s != null) {
    if (it.status === 'running' || it.status === 'live' || it.status === 'blocked-on-owner') actual = [s, Math.max(s, now)];
    else if (e != null) actual = [s, e];
  }
  let planned: [number, number] | null = null;
  if (ps != null && pe != null) planned = [ps, pe];
  return { actual, planned, due: it.lane === 'needs_you' && ps == null ? pe : null };
};

// How urgent a needs-you item is (lower first): an explicit `priority` in the file wins, else its urgency words,
// then the nearest due time, then the newest ask. The lane shows the first NEEDS_SHOWN; the rest fold into one row.
export const NEEDS_SHOWN = 3;
const URGENCY: [RegExp, number][] = [[/urgent|now|today/i, 0], [/soon|this week/i, 1], [/before|after|next/i, 2], [/when ready/i, 3], [/any ?time/i, 4]];
export const needsRank = (it: Item): number => {
  if (typeof it.priority === 'number') return it.priority;
  const u = it.urgency || '';
  const hit = URGENCY.find(([re]) => re.test(u));
  return hit ? hit[1] : 3;
};
export const needsInOrder = (items: Item[]): Item[] => items
  .filter(i => i.lane === 'needs_you' && i.status === 'blocked-on-owner')
  .sort((a, b) => needsRank(a) - needsRank(b) || (ep(a.planned_end) ?? Infinity) - (ep(b.planned_end) ?? Infinity) || (ep(b.start) ?? 0) - (ep(a.start) ?? 0));

export const isOpen = (it: Item) => ['running', 'blocked-on-owner', 'planned', 'live'].includes(it.status);

// "Next": planned items, each after the one it follows (a simple topological order, ties in file order)
export const nextInOrder = (items: Item[]): Item[] => {
  const planned = items.filter(i => i.status === 'planned');
  const ids = new Set(planned.map(i => i.id));
  const out: Item[] = [], done = new Set<string>();
  let guard = 0;
  while (out.length < planned.length && guard++ < 1000) {
    for (const i of planned) {
      if (done.has(i.id)) continue;
      if (i.after && ids.has(i.after) && !done.has(i.after)) continue;
      out.push(i); done.add(i.id);
    }
  }
  for (const i of planned) if (!done.has(i.id)) out.push(i);
  return out;
};

// ── layout ──────────────────────────────────────────────────────────────────────────────────────────────────
export type Measure = (s: string) => number;
export const estimateWidth: Measure = s => s.length * 6.3;
let ctx: CanvasRenderingContext2D | null | undefined;
export const textMeasurer = (font: string): Measure => {
  if (typeof document === 'undefined') return estimateWidth;
  try {
    if (ctx === undefined) ctx = document.createElement('canvas').getContext('2d');
    if (!ctx) return estimateWidth;
    const c = ctx;
    return (s: string) => { c.font = font; return c.measureText(s).width; };
  } catch { return estimateWidth; }
};

export const AXIS_H = 40, BAR_H = 22, ROW_GAP = 6, LANE_PAD = 10, MIN_LANE_H = 56, STRIP_H = 30, MIN_W = 5;
export type Bar = {
  item: Item; y: number; row: number;
  solid: [number, number] | null;   // px, clipped to the window
  faint: [number, number] | null;
  dueX: number | null;
  label: string; labelX: number; labelInside: boolean;
};
export type LaneBox = { lane: Lane; y: number; h: number; owner: boolean; empty: boolean };
export type Layout = {
  x: (t: number) => number; width: number; lanes: LaneBox[]; bars: Bar[]; lanesBottom: number;
  strips: { key: StripKey; label: string; y: number; h: number }[]; height: number;
};
export type StripKey = 'releases' | 'results' | 'promises' | 'alerts';
export const STRIPS: { key: StripKey; label: string }[] = [
  { key: 'releases', label: 'Releases' }, { key: 'results', label: 'Results' },
  { key: 'promises', label: 'Promises' }, { key: 'alerts', label: 'Alerts' },
];

export function layout(d: PlanData, win: { start: number; end: number }, now: number, width: number, measure: Measure,
  needsExpanded = false): Layout {
  const span = Math.max(1, win.end - win.start);
  const x = (t: number) => 4 + ((t - win.start) / span) * (width - 8);
  const clip = (a: number, b: number): [number, number] | null => {
    const s = Math.max(a, win.start), e = Math.min(b, win.end);
    if (e < s || (e === s && (a < win.start || b > win.end))) return null;
    const x0 = x(s), x1 = Math.max(x(e), x0 + MIN_W);
    return [x0, Math.min(x1, width - 2)];
  };
  const lanes: LaneBox[] = [];
  const bars: Bar[] = [];
  let y = AXIS_H;
  for (const lane of d.plan.lanes) {
    const owner = lane.key === 'needs_you';
    let mine = d.plan.items.filter(i => i.lane === lane.key);
    if (owner && !needsExpanded) {
      const open = needsInOrder(d.plan.items);
      const rest = open.slice(NEEDS_SHOWN);
      const resolved = mine.filter(i => i.status !== 'blocked-on-owner');
      mine = open.slice(0, NEEDS_SHOWN);
      if (rest.length || resolved.length) {
        const first = Math.min(...rest.map(i => ep(i.start) ?? now), now - 3600);
        const title = `${rest.length ? `+${rest.length} more waiting on you` : 'Nothing else waiting'}${resolved.length ? ` · ${resolved.length} resolved` : ''} — show`;
        mine.push({ id: '__more-needs', title, lane: 'needs_you', status: 'blocked-on-owner', start: new Date(Math.max(first, win.start) * 1000).toISOString(), synthetic: 'more-needs' });
      }
    } else if (owner && mine.length > NEEDS_SHOWN) {
      mine = [...mine, { id: '__more-needs', title: `Show only the ${NEEDS_SHOWN} most urgent`, lane: 'needs_you', status: 'blocked-on-owner',
        start: new Date((now - 3 * 3600) * 1000).toISOString(), synthetic: 'more-needs' }];
    }
    type R = { it: Item; solid: [number, number] | null; faint: [number, number] | null; dueX: number | null; occ: [number, number]; label: string; labelX: number; inside: boolean };
    const rs: R[] = [];
    for (const it of mine) {
      const { actual, planned, due } = spans(it, now);
      const solid = actual ? clip(actual[0], actual[1]) : null;
      const faint = planned ? clip(planned[0], planned[1]) : null;
      const dueX = due != null && due >= win.start && due <= win.end ? x(due) : null;
      if (!solid && !faint) continue;
      const box: [number, number] = [Math.min(solid?.[0] ?? Infinity, faint?.[0] ?? Infinity), Math.max(solid?.[1] ?? -Infinity, faint?.[1] ?? -Infinity)];
      const text = owner && !it.synthetic && it.status !== 'blocked-on-owner' ? `✓ ${it.title} (resolved)` : it.title;
      const tw = measure(text);
      const tail = it.status === 'running' ? 12 : 0;
      let label = text, labelX = box[0] + 7, inside = true;
      let occ: [number, number] = [box[0], box[1]];
      if (box[1] - box[0] - 14 - tail < tw) {
        inside = false;
        if (box[1] + 6 + tw <= width - 4) { labelX = box[1] + 6; occ = [box[0], box[1] + 6 + tw]; }
        else if (box[0] - 6 - tw >= 0) { labelX = box[0] - 6 - tw; occ = [labelX, box[1]]; }
        else { labelX = Math.max(2, width - 4 - tw); occ = [Math.min(box[0], labelX), width]; }
      }
      rs.push({ it, solid, faint, dueX, occ, label, labelX, inside });
    }
    if (owner) {   // urgent first, one per row; the folded row last
      const rank = (r: R) => (r.it.synthetic ? 1e9 : r.it.status === 'blocked-on-owner' ? needsRank(r.it) * 1e6 + mine.indexOf(r.it) : 5e8 + (ep(r.it.end) ?? 0) / 1e3);
      rs.sort((a, b) => rank(a) - rank(b));
    } else rs.sort((a, b) => a.occ[0] - b.occ[0]);
    const rowEnd: number[] = [];
    const rowOf = new Map<R, number>();
    for (const r of rs) {
      let row = owner ? -1 : rowEnd.findIndex(e => e + 8 <= r.occ[0]);
      if (row < 0) { row = rowEnd.length; rowEnd.push(0); }
      rowEnd[row] = r.occ[1];
      rowOf.set(r, row);
    }
    const nRows = Math.max(1, rowEnd.length);
    const h = Math.max(MIN_LANE_H, LANE_PAD * 2 + nRows * BAR_H + (nRows - 1) * ROW_GAP);
    for (const r of rs) {
      const row = rowOf.get(r)!;
      bars.push({ item: r.it, y: y + LANE_PAD + row * (BAR_H + ROW_GAP), row, solid: r.solid, faint: r.faint, dueX: r.dueX,
        label: r.label, labelX: r.labelX, labelInside: r.inside });
    }
    lanes.push({ lane, y, h, owner, empty: rs.length === 0 });
    y += h;
  }
  const lanesBottom = y;
  const strips = STRIPS.map((s, i) => ({ ...s, y: y + i * STRIP_H, h: STRIP_H }));
  return { x, width, lanes, bars, lanesBottom, strips, height: y + STRIPS.length * STRIP_H + 24 };
}

// axis ticks in UK time: every `step` hours on UK hour boundaries (step ≥ 24: UK midnights, every step/24 days)
export const tickStep = (pxPerHour: number) => [1, 2, 3, 6, 12, 24, 48, 168].find(s => s * pxPerHour >= 60) || 168;
export const ticks = (win: { start: number; end: number }, step: number): { t: number; midnight: boolean }[] => {
  const out: { t: number; midnight: boolean }[] = [];
  let t = Math.ceil(win.start / 3600) * 3600;
  for (; t <= win.end; t += 3600) {
    const p = partsIn(UK, t);
    if (p.mi !== 0) continue;
    const midnight = p.h === 0;
    if (step < 24 ? p.h % step === 0 : midnight && (step === 24 || (step === 48 ? p.d % 2 === 1 : p.wd === 'Mon'))) out.push({ t, midnight });
  }
  return out;
};

export const LANE_COLOR: Record<string, string> = {
  extraction: '#0d9488', reconciliation: '#4f46e5', platform: '#0284c7', evals: '#059669', docs: '#64748b', needs_you: '#ea580c',
};
export const C = { now: '#dc2626', alert: '#dc2626', stale: '#d97706', owner: '#ea580c', ownerBg: '#fff7ed', rule: '#e5e7eb', ink: '#1f2937', muted: '#6b7280', grey: '#9ca3af', live: '#16a34a' };
export const STATUS_LABEL: Record<Status, string> = {
  planned: 'Planned', running: 'Running', done: 'Done', live: 'Live', parked: 'Parked', dropped: 'Dropped', 'blocked-on-owner': 'Needs you',
};
