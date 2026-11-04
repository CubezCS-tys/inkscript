import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import { GanttChartSquare, List, RefreshCw } from 'lucide-react';
import Layout from '../components/Layout';
import { ErrorBox } from '../components/Bits';
import { api } from '../lib/api';
import { useMe } from '../lib/me';
import PlanChart, { Sel } from '../components/plan/PlanChart';
import PlanPanel from '../components/plan/PlanPanel';
import PlanList from '../components/plan/PlanList';
import AddItem from '../components/plan/AddItem';
import { C, LANE_COLOR, PlanData, ZOOMS, Zoom, agoText, ep, hm, nextInOrder, tzShort, whenUK, windowFor } from '../components/plan/model';

// The plan (/plan, 2026-11-02): everything in the project on one time axis, so nothing is forgotten — what agents are
// running now, what is live, what is done, what waits on the owner, what we promised and what comes next. One file,
// desk/plan/plan.json (written by desk/plan_cli.py), plus what the API reads live (releases, the live Desk's last
// build, heartbeats). The window is always worked out from "now" (day / week / month / all); the axis is UK time.
// Refreshes every 30 s. On a phone the default view is the stacked list.

const ZOOM_LABEL: Record<Zoom, string> = { day: 'Day', week: 'Week', month: 'Month', all: 'All' };
const MIN_W: Record<Zoom, number> = { day: 860, week: 900, month: 1000, all: 1100 };

export default function PlanPage() {
  const router = useRouter();
  const { me } = useMe();
  const [d, setD] = useState<PlanData | null>(null);
  const [err, setErr] = useState('');
  const [fetchedAt, setFetchedAt] = useState(0);
  const [tick, setTick] = useState(0);
  const [sel, setSel] = useState<Sel | null>(null);
  const zoom: Zoom = ZOOMS.includes(router.query.zoom as Zoom) ? (router.query.zoom as Zoom) : 'week';
  const [view, setView] = useState<'timeline' | 'list' | null>(null);
  const [needsOpen, setNeedsOpen] = useState(false);
  const skew = useRef(0);

  const load = useCallback(() => {
    api<PlanData>('/plan').then(x => { skew.current = x.now - Date.now() / 1000; setD(x); setErr(''); setFetchedAt(Date.now() / 1000); })
      .catch(e => setErr(String(e.message || e)));
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);
  useEffect(() => { const t = setInterval(() => setTick(x => x + 1), 30000); return () => clearInterval(t); }, []);
  useEffect(() => {
    if (view) return;
    const q = router.query.view;
    if (q === 'list' || q === 'timeline') setView(q);
    else if (router.isReady) setView(typeof window !== 'undefined' && window.innerWidth < 768 ? 'list' : 'timeline');
  }, [router.isReady, router.query.view, view]);
  useEffect(() => { const on = (e: KeyboardEvent) => { if (e.key === 'Escape') setSel(null); }; window.addEventListener('keydown', on); return () => window.removeEventListener('keydown', on); }, []);

  // "now" on the server's clock, moved on between fetches
  const now = useMemo(() => Math.floor(Date.now() / 1000 + skew.current), [d, tick]);  // eslint-disable-line react-hooks/exhaustive-deps
  const win = useMemo(() => (d ? windowFor(zoom, now, d) : { start: 0, end: 1 }), [d, zoom, now]);
  const setQ = (k: string, v: string) => router.replace({ pathname: '/plan', query: { ...router.query, [k]: v } }, undefined, { shallow: true, scroll: false });
  const selKey = sel?.kind === 'item' ? `item:${sel.id}` : null;

  if (err && !d) return <Layout wide><ErrorBox>{err}</ErrorBox></Layout>;
  if (!d) return <Layout wide><p className="text-sm text-gray-500">Loading the plan…</p></Layout>;
  const tz = d.server_tz;
  const edited = d.file_mtime;
  const next = nextInOrder(d.plan.items);
  const unscheduled = next.filter(i => !i.planned_start);
  const openProm = d.plan.promises.filter(p => p.status === 'open');
  const c = d.counts;
  const pill = (n: number, label: string, color: string, bg: string, tid: string) => (
    <span data-testid={tid} className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm" style={{ background: bg, color }}><b className="text-base leading-none">{n}</b>{label}</span>);

  return (
    <Layout wide>
      <div onClick={() => setSel(null)} className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2"><GanttChartSquare className="w-5 h-5 text-teal-600" aria-hidden />The plan</h1>
            <p className="text-xs text-gray-500 mt-1" data-testid="plan-clock">
              Now <b className="text-gray-700">{whenUK(now)} UK</b> <span title={`the server's clock, ${tz}`}>· {hm(tz, now)} server ({tzShort(tz)})</span>
              {' · '}plan edited {edited ? agoText(now - edited) : '—'} · refreshes every 30 s{err ? <span className="text-red-600"> · last refresh failed</span> : null}
              <button onClick={e => { e.stopPropagation(); load(); }} className="ml-1 align-middle p-0.5 rounded hover:bg-gray-100" aria-label="Refresh now" title={`fetched ${agoText(Date.now() / 1000 - fetchedAt)}`}><RefreshCw className="w-3 h-3" /></button>
            </p>
            <div className="flex flex-wrap gap-2 mt-2">
              {pill(c.running, 'running now', '#115e59', '#ccfbf1', 'count-running')}
              {pill(c.needs_you, 'need you', '#9a3412', '#ffedd5', 'count-needs')}
              {pill(c.next, 'next', '#3730a3', '#e0e7ff', 'count-next')}
              {pill(c.live, 'live', '#166534', '#dcfce7', 'count-live')}
              {c.stale > 0 && pill(c.stale, 'quiet for an hour', '#92400e', '#fef3c7', 'count-stale')}
              {c.overdue > 0 && pill(c.overdue, 'promise overdue', '#991b1b', '#fee2e2', 'count-overdue')}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2" onClick={e => e.stopPropagation()}>
            {me?.role === 'admin' && <AddItem d={d} onDone={load} />}
            <div className="flex rounded-xl border border-gray-200 bg-white p-1 text-sm" role="tablist" aria-label="View">
              {([['timeline', 'Timeline', GanttChartSquare], ['list', 'List', List]] as const).map(([k, l, Icon]) => (
                <button key={k} role="tab" aria-selected={view === k} data-testid={`view-${k}`} onClick={() => { setView(k); setQ('view', k); }}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg font-medium ${view === k ? 'bg-indigo-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}><Icon className="w-4 h-4" aria-hidden />{l}</button>))}
            </div>
            {view === 'timeline' && <div className="flex rounded-xl border border-gray-200 bg-white p-1 text-sm" role="tablist" aria-label="Zoom">
              {ZOOMS.map(z => (
                <button key={z} role="tab" aria-selected={zoom === z} data-testid={`zoom-${z}`} onClick={() => setQ('zoom', z)}
                  className={`px-3 py-1 rounded-lg font-medium ${zoom === z ? 'bg-gray-800 text-white' : 'text-gray-600 hover:bg-gray-50'}`}>{ZOOM_LABEL[z]}</button>))}
            </div>}
          </div>
        </div>

        {view === 'timeline' && <>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-gray-600" data-testid="plan-legend">
            <Lg><svg width="26" height="12"><rect x="1" y="1" width="24" height="10" rx="3" fill={LANE_COLOR.extraction} /></svg>done</Lg>
            <Lg><svg width="26" height="12"><rect x="1" y="1" width="24" height="10" rx="3" fill={LANE_COLOR.extraction} /><rect x="12" y="1" width="13" height="10" fill="url(#lg-stripes)" /><defs><pattern id="lg-stripes" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="3" height="6" fill="rgba(255,255,255,.5)" /></pattern></defs><circle cx="23" cy="6" r="3" fill={C.now} /></svg>running (up to now)</Lg>
            <Lg><svg width="26" height="12"><rect x="1" y="1" width="24" height="10" rx="3" fill={LANE_COLOR.platform} /><circle cx="19" cy="6" r="2.6" fill="#fff" stroke={C.live} strokeWidth="1.6" /></svg>live</Lg>
            <Lg><svg width="26" height="12"><rect x="1" y="1" width="24" height="10" rx="3" fill={LANE_COLOR.reconciliation} fillOpacity=".12" stroke={LANE_COLOR.reconciliation} strokeDasharray="3 2" /></svg>planned</Lg>
            <Lg><svg width="26" height="12"><rect x="1" y="1" width="24" height="10" rx="3" fill={C.stale} /></svg>no sign of life for an hour</Lg>
            <Lg><svg width="26" height="12"><rect x="1" y="1" width="24" height="10" rx="3" fill="#fed7aa" stroke={C.owner} /></svg>needs you (waiting since)</Lg>
            <Lg><svg width="14" height="14"><path d="M7 1 L13 7 L7 13 L1 7 Z" fill="#0d9488" /></svg>Desk release</Lg>
            <Lg><svg width="14" height="14"><path d="M7 1 L13 12 L1 12 Z" fill="#4f46e5" /></svg>live Desk rebuilt</Lg>
            <Lg><svg width="12" height="12"><circle cx="6" cy="6" r="4.5" fill="#059669" /></svg>result</Lg>
            <Lg><svg width="12" height="14"><line x1="2" x2="2" y1="1" y2="13" stroke="#4f46e5" strokeWidth="1.6" /><path d="M2 1 L10 4 L2 7 Z" fill="#4f46e5" /></svg>promise due</Lg>
            <Lg><svg width="8" height="14"><line x1="4" x2="4" y1="1" y2="13" stroke={C.alert} strokeWidth="2.5" /></svg>alert</Lg>
            <Lg><svg width="8" height="14"><line x1="4" x2="4" y1="1" y2="13" stroke={C.now} strokeWidth="2" /></svg>now</Lg>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden" onClick={e => e.stopPropagation()}>
            <PlanChart d={d} now={now} win={win} minWidth={MIN_W[zoom]} selected={selKey} onSelect={setSel}
              needsExpanded={needsOpen} onToggleNeeds={() => setNeedsOpen(x => !x)} />
          </div>
          <p className="text-xs text-gray-500 leading-relaxed">
            Times are UK time (the server&apos;s, {tzShort(tz)}, on hover). Tap a bar or a mark for what it is, its times and where it came from.
            A solid bar is what happened; a faint dashed one is what was planned. Work without dates yet is listed below, in order.
            Releases come from the Desk&apos;s release files and the rebuild mark from the live Desk&apos;s build, both read as they are; running work shows when it last showed a sign of life.
          </p>
          <div className="grid gap-3 md:grid-cols-2" onClick={e => e.stopPropagation()}>
            <section className="rounded-2xl border border-gray-200 bg-white p-4" data-testid="next-card">
              <h2 className="text-sm font-semibold text-indigo-900">Next, in order <span className="font-normal text-gray-400">— no dates yet ({unscheduled.length})</span></h2>
              <ol className="mt-2 space-y-1">
                {unscheduled.map((it, i) => (
                  <li key={it.id}><button className="text-left text-sm hover:underline" onClick={() => setSel({ kind: 'item', id: it.id })}>
                    <span className="text-gray-400 tabular-nums mr-1.5">{i + 1}.</span><span className="w-2 h-2 rounded-full inline-block mr-1.5 align-middle" style={{ background: LANE_COLOR[it.lane] }} />
                    <span className="text-gray-900">{it.title}</span>
                    {it.waits_on && <span className="text-xs ml-1.5" style={{ color: C.owner }}>waits on you</span>}
                    {it.cost && <span className="text-xs text-gray-500 ml-1.5">{it.cost}</span>}</button></li>))}
              </ol>
            </section>
            <section className="rounded-2xl border border-gray-200 bg-white p-4" data-testid="promises-card">
              <h2 className="text-sm font-semibold text-indigo-900">Promises <span className="font-normal text-gray-400">({openProm.length} open)</span></h2>
              <ul className="mt-2 space-y-1.5">
                {openProm.map(p => { const late = d.live.overdue.includes(p.id); return (
                  <li key={p.id}><button className="text-left text-sm hover:underline" onClick={() => setSel({ kind: 'promise', p })}>
                    <span className="text-gray-900">{p.title}</span>
                    <span className="block text-xs" style={{ color: late ? C.alert : '#6b7280' }}>{p.due ? `${late ? 'overdue — ' : ''}due ${whenUK(ep(p.due), now)} UK` : 'no time given'}{p.by ? ` · ${p.by}` : ''}</span></button></li>); })}
              </ul>
            </section>
          </div>
        </>}
        {view === 'list' && <div onClick={e => e.stopPropagation()}><PlanList d={d} now={now} onPick={setSel} /></div>}
        {d.problems.length > 0 && <ErrorBox>The plan file has {d.problems.length} problem(s): {d.problems.slice(0, 3).join('; ')}</ErrorBox>}
      </div>
      {sel && <PlanPanel d={d} now={now} sel={sel} onClose={() => setSel(null)} onPick={setSel} />}
    </Layout>
  );
}

const Lg: React.FC<{ children: React.ReactNode }> = ({ children }) => <span className="inline-flex items-center gap-1.5">{children}</span>;
