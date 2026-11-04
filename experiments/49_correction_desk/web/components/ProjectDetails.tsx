import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle, ArrowRight, BookA, CalendarClock, Check, CheckCircle2, Circle, Compass, ExternalLink, Gavel, Hourglass,
  Info, Lightbulb, MapPin, Milestone, Search, Target, Wallet,
} from 'lucide-react';
import { Card, Chip } from './Bits';

// The project page's Details tab (the page as first built, 2026-10-26; the Map tab is ProjectMap.tsx): the Web-of-Science project at a glance, the page the owner opens first when they
// come back. Everything on it is read from desk/project/project.json (API desk/project.py), in which every item
// carries its source; the source shows on hover and in the small "source" fold under each item. The Gemini spend is
// also computed live from the log, so the page says when the log has moved past the written figure.

type Link_ = { label: string; href: string };
type Src = { source?: string[] };

// pages served from web/public or proxied (not Next pages): plain links, not client-side routing
export const STATIC = /^\/(gate1|gate2|pitch|inventory|mindmap|mockup|views)(\/|$)/;
export const DLink: React.FC<{ href: string; className?: string; children: React.ReactNode; title?: string }> = ({ href, className, children, title }) =>
  STATIC.test(href) ? <a href={href} className={className} title={title}>{children}</a> : <Link href={href} className={className} title={title}>{children}</Link>;

// mixed English / Arabic text: each Arabic run is isolated (bdi, rtl, Naskh) so numbers and brackets beside it stay put
const AR = /([\u0600-\u06FF][\u0600-\u06FF\u064B-\u065F\s«»،.]*[\u0600-\u06FF»])/;
export const Tx: React.FC<{ t?: string | null }> = ({ t }) => !t ? null : (
  <>{t.split(AR).map((part, i) => (i % 2 ? <bdi key={i} dir="rtl" lang="ar" className="font-naskh">{part}</bdi> : <React.Fragment key={i}>{part}</React.Fragment>))}</>);

export const srcTitle = (s?: string[]) => (s && s.length ? 'Source:\n' + s.join('\n') : 'No source recorded');

// the source of an item: hover the icon for all of it, or open the fold
export function Sources({ s, className = '' }: { s?: string[]; className?: string }) {
  if (!s || !s.length) return null;
  return (
    <details className={`group text-[11px] text-gray-500 ${className}`}>
      <summary className="cursor-pointer list-none inline-flex items-center gap-1 hover:text-indigo-700 select-none" title={srcTitle(s)}>
        <Info className="w-3 h-3" aria-hidden /> source{s.length > 1 ? `s (${s.length})` : ''}
      </summary>
      <ul className="mt-1 space-y-0.5 border-l-2 border-gray-200 pl-2">
        {s.map((x, i) => <li key={i} className="break-words" dir="auto">{x.startsWith('conversation') ? <span className="italic">{x}</span> : <code className="text-[11px] text-gray-600 break-all">{x}</code>}</li>)}
      </ul>
    </details>
  );
}

export const Links: React.FC<{ links?: Link_[] }> = ({ links }) => !links || !links.length ? null : (
  <div className="flex flex-wrap gap-1.5 mt-1.5">
    {links.map(l => (
      <DLink key={l.href} href={l.href} className="inline-flex items-center gap-1 text-xs text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded px-1.5 py-0.5">
        {l.label}<ArrowRight className="w-3 h-3" aria-hidden />
      </DLink>))}
  </div>);

export const STATUS_TONE: Record<string, 'green' | 'amber' | 'indigo' | 'gray' | 'red'> = {
  done: 'green', 'in progress': 'indigo', open: 'amber', parked: 'gray', dropped: 'red',
};

function Section({ id, icon: Icon, title, right, children, className }: { id: string; icon: any; title: string; right?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <Card id={id} className={className} title={<span className="flex items-center gap-2"><Icon className="w-4 h-4 text-indigo-600" aria-hidden />{title}</span>} right={right}>
      {children}
    </Card>);
}

// ---------- the "Where we are" banner with the gates strip ----------
function GateStrip({ roadmap, current }: { roadmap: any[]; current: string }) {
  const idx = roadmap.findIndex(g => g.id === current);
  return (
    <ol className="grid grid-cols-1 sm:grid-cols-4 gap-2" aria-label="The gates">
      {roadmap.map((g, i) => {
        const done = g.status === 'done';
        const here = g.id === current;
        const cls = done ? 'border-green-300 bg-green-50' : here ? 'border-amber-400 bg-amber-50 ring-2 ring-amber-200' : 'border-gray-200 bg-white';
        return (
          <li key={g.id} className={`relative rounded-xl border p-3 ${cls}`} title={srcTitle(g.source)} data-testid={`gate-${g.id}`}>
            <div className="flex items-center gap-2">
              {done ? <CheckCircle2 className="w-5 h-5 text-green-600" aria-hidden />
                : here ? <Hourglass className="w-5 h-5 text-amber-600" aria-hidden />
                : <Circle className="w-5 h-5 text-gray-300" aria-hidden />}
              <span className="font-semibold text-gray-900">{g.name}</span>
              <span className={`ml-auto text-[11px] font-medium rounded-full px-2 py-0.5 ${done ? 'bg-green-100 text-green-800' : here ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'}`}>{g.status}</span>
            </div>
            <p className="text-xs text-gray-700 mt-1.5" dir="auto"><Tx t={g.scope} /></p>
            <p className="text-xs text-gray-500 mt-1"><span className="font-medium text-gray-700">Cost:</span> {g.cost}</p>
            <p className="text-xs text-gray-500 mt-0.5"><span className="font-medium text-gray-700">Proves:</span> <Tx t={g.proves} /></p>
            <Links links={g.links} />
            {i < roadmap.length - 1 && <ArrowRight className={`hidden sm:block absolute -right-[13px] top-4 w-4 h-4 z-10 ${i < idx ? 'text-green-500' : 'text-gray-300'}`} aria-hidden />}
          </li>);
      })}
    </ol>);
}

// ---------- filterable lists ----------
function FilterBar({ q, setQ, chips, value, setValue, counts }: { q: string; setQ: (s: string) => void; chips: string[]; value: string; setValue: (s: string) => void; counts: Record<string, number> }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 mb-3">
      {['all', ...chips].map(c => (
        <button key={c} onClick={() => setValue(c)} aria-pressed={value === c}
          className={`text-xs rounded-full px-2.5 py-1 border ${value === c ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'}`}>
          {c} <span className="opacity-70">{c === 'all' ? Object.values(counts).reduce((a, b) => a + b, 0) : counts[c] || 0}</span>
        </button>))}
      <label className="relative ml-auto">
        <span className="sr-only">Filter</span>
        <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2 top-2" aria-hidden />
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="Filter…" dir="auto" className="pl-7 pr-2 py-1 w-44 rounded-lg border-gray-300 text-xs" />
      </label>
    </div>);
}
const matches = (o: any, q: string) => !q || JSON.stringify(o).toLowerCase().includes(q.toLowerCase());

function Decisions({ items }: { items: any[] }) {
  const [q, setQ] = useState(''); const [by, setBy] = useState('all');
  const kind = (d: any) => (d.id.startsWith('D') ? 'D-numbers' : 'owner decisions');
  const counts = items.reduce((a: any, d) => { a[kind(d)] = (a[kind(d)] || 0) + 1; return a; }, {});
  const shown = items.filter(d => (by === 'all' || kind(d) === by) && matches(d, q)).sort((a, b) => b.date.localeCompare(a.date));
  return (<>
    <FilterBar q={q} setQ={setQ} chips={['D-numbers', 'owner decisions']} value={by} setValue={setBy} counts={counts} />
    <ul className="divide-y divide-gray-100">
      {shown.map(d => (
        <li key={d.id} className="py-2.5 grid grid-cols-[5.5rem_1fr] gap-3" title={srcTitle(d.source)}>
          <div><Chip tone={d.id.startsWith('D') ? 'indigo' : 'amber'}>{d.id.startsWith('D') ? d.id : 'owner'}</Chip><div className="text-[11px] text-gray-500 mt-1 tabular-nums">{d.date}</div></div>
          <div className="min-w-0">
            <p className="text-sm text-gray-900"><Tx t={d.choice} /></p>
            {d.why && <p className="text-xs text-gray-500 mt-0.5">Why: <Tx t={d.why} /></p>}
            <Sources s={d.source} className="mt-1" />
          </div>
        </li>))}
      {!shown.length && <li className="py-3 text-sm text-gray-500">Nothing matches.</li>}
    </ul>
  </>);
}

function Ideas({ items }: { items: any[] }) {
  const [q, setQ] = useState(''); const [st, setSt] = useState('all');
  const order = ['in progress', 'open', 'parked', 'done', 'dropped'];
  const counts = items.reduce((a: any, d) => { a[d.status] = (a[d.status] || 0) + 1; return a; }, {});
  const shown = items.filter(d => (st === 'all' || d.status === st) && matches(d, q))
    .sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status));
  return (<>
    <FilterBar q={q} setQ={setQ} chips={order} value={st} setValue={setSt} counts={counts} />
    <ul className="grid md:grid-cols-2 gap-2">
      {shown.map(d => (
        <li key={d.id} className="rounded-lg border border-gray-200 p-3" title={srcTitle(d.source)}>
          <div className="flex items-start gap-2">
            <p className="text-sm font-medium text-gray-900 flex-1" dir="auto"><Tx t={d.title} /></p>
            <Chip tone={STATUS_TONE[d.status] || 'gray'}>{d.status}</Chip>
          </div>
          <p className="text-xs text-gray-600 mt-1" dir="auto"><Tx t={d.detail} /></p>
          {d.pick_up && <p className="text-[11px] text-gray-500 mt-1">Pick up: {d.pick_up.startsWith('/') ? <DLink href={d.pick_up} className="text-indigo-700 hover:underline">{d.pick_up}</DLink> : <code className="break-all">{d.pick_up}</code>}</p>}
          <Sources s={d.source} className="mt-1" />
        </li>))}
      {!shown.length && <li className="text-sm text-gray-500">Nothing matches.</li>}
    </ul>
  </>);
}

// ---------- money ----------
export const usd = (x: number) => `$${x.toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
function Money({ m, live }: { m: any; live: any }) {
  const total = m.spent.value_usd;
  const liveUsd = live?.spend?.usd;
  const moved = liveUsd != null && Math.abs(liveUsd - total) > 0.01;
  const max = Math.max(...m.spent_by.map((x: any) => x.usd));
  return (
    <div className="grid lg:grid-cols-3 gap-4">
      <div>
        <div className="text-xs text-gray-500">Gemini spent since {m.spent.since}</div>
        <div className="text-3xl font-semibold text-gray-900 tabular-nums" title={srcTitle(m.spent.source)} data-testid="spent">{usd(total)}</div>
        <div className="text-[11px] text-gray-500">{m.spent.rows.toLocaleString('en')} calls, last on {m.spent.last_entry}; {m.spent.computed}</div>
        {liveUsd != null && (
          <div className={`mt-2 text-xs rounded-lg px-2 py-1.5 ${moved ? 'bg-amber-50 text-amber-800 border border-amber-200' : 'bg-green-50 text-green-800 border border-green-200'}`} data-testid="spend-live">
            {moved ? <>The log now says <b>{usd(liveUsd)}</b> (last entry {live.spend.last_entry}): this page is behind; update project.json.</>
              : <>Checked live against the log just now: {usd(liveUsd)}, {live.spend.rows.toLocaleString('en')} rows.</>}
          </div>)}
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5" title={srcTitle(m.credit.source)}>
          <div className="text-xs text-amber-900 font-medium">Credit left: {m.credit.left} <Chip tone="amber">{m.credit.kind}</Chip></div>
          <div className="text-[11px] text-amber-900 mt-0.5">Top-up {m.credit.topup}. {m.credit.note}</div>
          <Sources s={m.credit.source} className="mt-1" />
        </div>
      </div>
      <div>
        <div className="text-xs text-gray-500 mb-1.5">Where it went</div>
        <ul className="space-y-1.5">
          {m.spent_by.map((x: any) => (
            <li key={x.label} title={srcTitle(x.source)}>
              <div className="flex justify-between text-xs"><span className="text-gray-700"><Tx t={x.label} /></span><span className="tabular-nums text-gray-900">{usd(x.usd)}</span></div>
              <div className="h-1.5 bg-gray-100 rounded"><div className="h-1.5 bg-indigo-400 rounded" style={{ width: `${(100 * x.usd) / max}%` }} /></div>
            </li>))}
        </ul>
        <div className="text-xs text-gray-500 mt-3 mb-1">By day</div>
        <div className="flex gap-3 text-[11px] text-gray-600 tabular-nums" title={srcTitle(m.by_day_source)}>
          {m.by_day.map((d: any) => <span key={d.date}>{d.date.slice(5)}: {usd(d.usd)}</span>)}
        </div>
        <Sources s={m.by_day_source} className="mt-1" />
      </div>
      <div>
        <div className="text-xs text-gray-500 mb-1.5">What comes next would cost <Chip tone="amber">estimates</Chip></div>
        <ul className="divide-y divide-gray-100">
          {m.projections.map((p: any) => (
            <li key={p.label} className="py-1.5 flex justify-between gap-3 text-xs" title={srcTitle(p.source)}>
              <span className="text-gray-700"><Tx t={p.label} /></span><span className="text-gray-900 text-right whitespace-nowrap">{p.usd}</span>
            </li>))}
        </ul>
        <p className="text-[11px] text-red-700 mt-2 flex gap-1" title={srcTitle(m.deadline.source)}><CalendarClock className="w-3.5 h-3.5 shrink-0" aria-hidden />{m.deadline.text}</p>
        <p className="text-[11px] text-gray-500 mt-1" title={srcTitle(m.not_priced.source)}>Not priced yet: {m.not_priced.text}</p>
      </div>
    </div>);
}

// ---------- the page ----------
const NAV: [string, string][] = [['where', 'Where we are'], ['waiting', 'Waiting on you'], ['next', 'Next'], ['numbers', 'Numbers'],
  ['timeline', 'Timeline'], ['decisions', 'Decisions'], ['ideas', 'Ideas'], ['money', 'Money'], ['places', 'Where things live'],
  ['risks', 'Risks'], ['glossary', 'Words'], ['notes', 'Notes on the sources']];

export default function ProjectDetails({ d }: { d: any }) {
  const byWhen = useMemo(() => {
    const g: Record<string, any[]> = {};
    (d?.next_steps || []).forEach((s: any) => { (g[s.when] = g[s.when] || []).push(s); });
    return g;
  }, [d]);
  const numberGroups = useMemo(() => {
    const g: [string, any[]][] = [];
    (d?.numbers || []).forEach((x: any) => { const e = g.find(([k]) => k === x.group); if (e) e[1].push(x); else g.push([x.group, [x]]); });
    return g;
  }, [d]);
  const timelineByDate = useMemo(() => {
    const g: [string, any[]][] = [];
    (d?.timeline || []).forEach((x: any) => { const e = g.find(([k]) => k === x.date); if (e) e[1].push(x); else g.push([x.date, [x]]); });
    return g;
  }, [d]);
  const [allTimeline, setAllTimeline] = useState(false);

  const g2 = d.waiting_on_owner || [];

  return (
    <div className="space-y-4" data-testid="details">
      <p className="text-xs text-gray-500">{d.meta.how_to_read}</p>
      <nav aria-label="Sections of this page" className="flex flex-wrap gap-1">
        {NAV.map(([id, label]) => <a key={id} href={`#${id}`} className="text-xs text-gray-600 bg-white border border-gray-200 rounded-full px-2.5 py-1 hover:border-indigo-300 hover:text-indigo-700">{label}</a>)}
      </nav>

      {/* where we are */}
      <section id="where" className="rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-white p-5 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Compass className="w-5 h-5 text-indigo-600" aria-hidden />
          <h2 className="font-semibold text-gray-900">Where we are</h2>
          <span className="text-xs font-medium bg-amber-100 text-amber-900 rounded-full px-2.5 py-0.5" title={srcTitle(d.stage.source)} data-testid="stage">{d.stage.label}</span>
        </div>
        <p className="text-[15px] leading-relaxed text-gray-800 max-w-5xl" title={srcTitle(d.headline.source)} dir="auto"><Tx t={d.headline.text} /></p>
        <Sources s={d.headline.source} />
        <GateStrip roadmap={d.roadmap} current={d.stage.current} />
      </section>

      {/* waiting on you + next */}
      <div className="grid lg:grid-cols-3 gap-4">
        <Section id="waiting" className="lg:col-span-2" icon={Hourglass} title={`Waiting on you (${g2.length})`} right={<span className="text-xs text-gray-500">recommended answer in green</span>}>
          <ul className="grid md:grid-cols-2 gap-3">
            {g2.map((w: any) => (
              <li key={w.id} className="rounded-xl border border-gray-200 p-3 flex flex-col" title={srcTitle(w.source)} data-testid="waiting-card">
                <div className="flex items-start gap-2">
                  <p className="text-sm font-semibold text-gray-900 flex-1"><Tx t={w.title} /></p>
                  <Chip tone={/meeting|week/.test(w.urgency) ? 'red' : /soon|before/.test(w.urgency) ? 'amber' : 'gray'}>{w.urgency}</Chip>
                </div>
                <p className="text-xs text-gray-600 mt-1" dir="auto"><Tx t={w.question} /></p>
                <div className="mt-2 rounded-lg bg-green-50 border border-green-200 px-2.5 py-1.5 text-xs text-green-900 flex gap-1.5" dir="auto">
                  <Check className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden /><span><span className="font-medium">Recommended:</span> <Tx t={w.recommended} /></span>
                </div>
                {w.unblocks && <p className="text-[11px] text-gray-500 mt-1.5"><span className="font-medium text-gray-700">Unblocks:</span> <Tx t={w.unblocks} /></p>}
                <Links links={w.links} />
                <Sources s={w.source} className="mt-auto pt-1.5" />
              </li>))}
          </ul>
        </Section>
        <Section id="next" className="lg:sticky lg:top-16 self-start" icon={Milestone} title="Next">
          {['this week', 'next', 'later'].map(k => (byWhen[k] || []).length ? (
            <div key={k} className="mb-3">
              <div className="text-[11px] uppercase tracking-wide font-semibold text-gray-500 mb-1">{k}</div>
              <ol className="space-y-1.5">
                {byWhen[k].sort((a: any, b: any) => a.order - b.order).map((s: any) => (
                  <li key={s.order} className="flex gap-2" title={srcTitle(s.source)}>
                    <span className="w-5 h-5 shrink-0 rounded-full bg-indigo-100 text-indigo-700 text-[11px] grid place-items-center font-medium">{s.order}</span>
                    <div className="min-w-0">
                      <p className="text-sm text-gray-900"><Tx t={s.title} /></p>
                      <p className="text-[11px] text-gray-500"><Tx t={s.detail} /> <span className="text-gray-700">· {s.cost}</span></p>
                      <Sources s={s.source} />
                    </div>
                  </li>))}
              </ol>
            </div>) : null)}
        </Section>
      </div>

      {/* north star and the picture */}
      <div className="grid lg:grid-cols-2 gap-4">
        <Section id="goals" icon={Target} title="What we are aiming at">
          <ul className="space-y-2">
            {d.north_star.map((g: any) => (
              <li key={g.id} title={srcTitle(g.source)}>
                <p className="text-sm font-medium text-gray-900"><Tx t={g.title} /></p>
                <p className="text-xs text-gray-600"><Tx t={g.detail} /></p>
                <Sources s={g.source} />
              </li>))}
          </ul>
        </Section>
        <Section id="picture" icon={MapPin} title="The picture">
          <ul className="grid sm:grid-cols-2 gap-2">
            {d.picture.map((p: any) => (
              <li key={p.id} className="rounded-lg border border-gray-200 p-2.5" title={srcTitle(p.source)}>
                <div className="flex items-center gap-2"><span className="text-sm font-semibold text-gray-900">{p.name}</span><Chip tone="indigo">{p.status}</Chip></div>
                <p className="text-xs text-gray-600 mt-1"><Tx t={p.detail} /></p>
                <Sources s={p.source} className="mt-1" />
              </li>))}
          </ul>
        </Section>
      </div>

      {/* numbers */}
      <Section id="numbers" icon={CheckCircle2} title="Key numbers" right={<span className="text-xs text-gray-500">measured unless marked estimate; hover for the source</span>}>
        <div className="space-y-3">
          {numberGroups.map(([grp, xs]) => (
            <div key={grp}>
              <div className="text-[11px] uppercase tracking-wide font-semibold text-gray-500 mb-1">{grp}</div>
              <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-2">
                {xs.map((x: any) => (
                  <div key={x.id} className="bg-white rounded-xl border border-gray-200 p-3 min-w-0" title={srcTitle(x.source)} data-testid="number-tile">
                    <div className="text-[11px] text-gray-500 leading-tight"><Tx t={x.label} /></div>
                    <div className="text-xl font-semibold text-gray-900 tabular-nums mt-1">{x.value}</div>
                    <div className="text-[11px] text-gray-500 mt-0.5"><Tx t={x.sub} /></div>
                    <div className="flex items-center gap-1.5 mt-1"><span className="text-[10px] text-gray-400 tabular-nums">{x.date}</span>{x.kind === 'estimate' && <Chip tone="amber">estimate</Chip>}</div>
                    <Sources s={x.source} className="mt-0.5" />
                  </div>))}
              </div>
            </div>))}
        </div>
      </Section>

      {/* timeline */}
      <Section id="timeline" icon={CalendarClock} title={`Timeline (${d.timeline.length}), newest first`}
        right={<button onClick={() => setAllTimeline(!allTimeline)} className="text-xs text-indigo-700 hover:underline">{allTimeline ? 'Show the last days only' : 'Show all'}</button>}>
        <ol className="relative border-l-2 border-indigo-100 ml-2 space-y-4">
          {timelineByDate.filter((_, i) => allTimeline || i < 3).map(([date, xs]) => (
            <li key={date} className="ml-4">
              <span className="absolute -left-[7px] mt-1 w-3 h-3 rounded-full bg-indigo-400 ring-4 ring-white" aria-hidden />
              <div className="text-xs font-semibold text-indigo-700 tabular-nums">{date}</div>
              <ul className="mt-1 grid md:grid-cols-2 gap-2">
                {xs.map((t: any) => (
                  <li key={t.title} className="rounded-lg border border-gray-200 p-2.5" title={srcTitle(t.source)}>
                    <p className="text-sm font-medium text-gray-900" dir="auto"><Tx t={t.title} /></p>
                    <p className="text-xs text-gray-600 mt-0.5" dir="auto"><Tx t={t.what} /></p>
                    {t.why && <p className="text-xs text-gray-500 mt-0.5"><span className="font-medium text-gray-700">Why it matters:</span> <Tx t={t.why} /></p>}
                    <Links links={t.links} />
                    <Sources s={t.source} className="mt-1" />
                  </li>))}
              </ul>
            </li>))}
        </ol>
        {!allTimeline && timelineByDate.length > 3 && <button onClick={() => setAllTimeline(true)} className="mt-3 text-xs text-indigo-700 hover:underline">Show {timelineByDate.length - 3} earlier days…</button>}
      </Section>

      <div className="grid xl:grid-cols-2 gap-4">
        <Section id="decisions" icon={Gavel} title={`Decisions (${d.decisions.length})`}><Decisions items={d.decisions} /></Section>
        <Section id="ideas" icon={Lightbulb} title={`Ideas (${d.ideas.length})`}><Ideas items={d.ideas} /></Section>
      </div>

      <Section id="money" icon={Wallet} title="Money"><Money m={d.money} live={d.live} /></Section>

      <Section id="places" icon={MapPin} title="Where things live">
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
          {Array.from(new Set(d.where_things_live.map((w: any) => w.group))).map((grp: any) => (
            <div key={grp}>
              <div className="text-[11px] uppercase tracking-wide font-semibold text-gray-500 mb-1">{grp}</div>
              <ul className="space-y-1.5">
                {d.where_things_live.filter((w: any) => w.group === grp).map((w: any) => (
                  <li key={w.name} title={srcTitle(w.source)}>
                    {w.href
                      ? <DLink href={w.href} className="text-sm text-indigo-700 hover:underline inline-flex items-center gap-1">{w.name}{STATIC.test(w.href) && <ExternalLink className="w-3 h-3" aria-hidden />}</DLink>
                      : <span className="text-sm text-gray-900">{w.name}</span>}
                    <span className="text-[11px] text-gray-400 ml-1.5">{w.href || ''}</span>
                    <p className="text-[11px] text-gray-600"><Tx t={w.what} /></p>
                    {w.path && <code className="block text-[11px] text-gray-500 break-all">{w.path}</code>}
                  </li>))}
              </ul>
            </div>))}
        </div>
      </Section>

      <div className="grid lg:grid-cols-2 gap-4">
        <Section id="risks" icon={AlertTriangle} title={`Risks and unknowns (${d.risks.length})`}>
          <ul className="space-y-2">
            {d.risks.map((r: any) => (
              <li key={r.id} className="flex gap-2" title={srcTitle(r.source)}>
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-1" aria-hidden />
                <div className="min-w-0"><p className="text-sm text-gray-900"><Tx t={r.title} /></p><p className="text-xs text-gray-600" dir="auto"><Tx t={r.detail} /></p><Sources s={r.source} /></div>
              </li>))}
          </ul>
        </Section>
        <Section id="glossary" icon={BookA} title="Words we use">
          <dl className="grid sm:grid-cols-2 gap-x-4 gap-y-2">
            {d.glossary.map((g: any) => (
              <div key={g.term} title={srcTitle(g.source)}>
                <dt className="text-sm font-medium text-gray-900">{g.term}</dt>
                <dd className="text-xs text-gray-600"><Tx t={g.means} /></dd>
              </div>))}
          </dl>
        </Section>
      </div>

      <Section id="notes" icon={Info} title="Notes on the sources" right={<span className="text-xs text-gray-500">where two documents give different figures</span>}>
        <ul className="grid md:grid-cols-2 gap-2">
          {d.source_notes.map((s: any) => (
            <li key={s.title} className="rounded-lg border border-gray-200 bg-gray-50 p-2.5" title={srcTitle(s.source)}>
              <p className="text-sm font-medium text-gray-900"><Tx t={s.title} /></p>
              <p className="text-xs text-gray-600 mt-0.5"><Tx t={s.detail} /></p>
              <Sources s={s.source} className="mt-1" />
            </li>))}
        </ul>
      </Section>
      <p className="text-[11px] text-gray-400">Kept in <code>experiments/49_correction_desk/desk/project/project.json</code>; how to update it: <code>{d.meta.how_to_update}</code>.</p>
    </div>
  );
}
