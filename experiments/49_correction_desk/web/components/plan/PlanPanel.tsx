import React from 'react';
import Link from 'next/link';
import { X } from 'lucide-react';
import { C, Item, LANE_COLOR, PlanData, STATUS_LABEL, agoText, durText, ep, tzShort, whenTz, whenUK } from './model';
import type { Sel } from './PlanChart';

// The card for what was tapped (pages/plan.tsx): a side panel on a wide screen, a bottom sheet on a phone. Plain
// words first (what it is, where it stands, what came of it), then the times (UK; the server's under each), the
// links into the Desk, and where every word came from.

export const StatusPill: React.FC<{ it: Item; stale?: boolean }> = ({ it, stale }) => {
  const s = it.status;
  const [bg, fg] = stale ? ['#fef3c7', '#92400e']
    : s === 'running' ? ['#ccfbf1', '#115e59'] : s === 'live' ? ['#dcfce7', '#166534'] : s === 'done' ? ['#f3f4f6', '#374151']
    : s === 'blocked-on-owner' ? ['#ffedd5', '#9a3412'] : s === 'planned' ? ['#e0e7ff', '#3730a3'] : ['#f3f4f6', '#6b7280'];
  return <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide" style={{ background: bg, color: fg }}>
    {stale ? 'No sign of life' : STATUS_LABEL[s]}</span>;
};

const T: React.FC<{ t: number | null; tz: string; now: number }> = ({ t, tz, now }) => (t == null ? <span>—</span> : (
  <span title={`${whenTz(tz, t)} server time (${tzShort(tz)})`}>{whenUK(t, now)} <span className="text-gray-400">UK</span>
    <span className="block text-[11px] text-gray-400">{whenTz(tz, t)} {tzShort(tz)}</span></span>));

const Row: React.FC<{ k: string; children: React.ReactNode }> = ({ k, children }) => (
  <div className="grid grid-cols-[92px_1fr] gap-2 py-1.5 border-b border-gray-100 last:border-0 text-sm">
    <div className="text-gray-500 text-xs pt-0.5">{k}</div><div className="text-gray-800">{children}</div></div>);

const Links: React.FC<{ links?: { label: string; href: string }[] }> = ({ links }) => (!links?.length ? null : (
  <div className="flex flex-wrap gap-1.5">{links.map(l => (
    <Link key={l.href + l.label} href={l.href} className="inline-flex items-center rounded-lg border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100">{l.label} →</Link>))}</div>));

const Sources: React.FC<{ s?: string[]; approx?: string }> = ({ s, approx }) => (
  <div className="mt-3 text-[11px] text-gray-500 leading-snug">
    {approx && <p className="mb-1"><b className="text-gray-600">Times:</b> {approx}.</p>}
    {s?.length ? <><b className="text-gray-600">From:</b><ul className="list-disc ml-4">{s.map((x, i) => <li key={i} className="break-words">{x}</li>)}</ul></> : null}
  </div>);

const PlanPanel: React.FC<{ d: PlanData; now: number; sel: Sel; onClose: () => void; onPick: (s: Sel) => void }> = ({ d, now, sel, onClose, onPick }) => {
  const tz = d.server_tz;
  const byId = (id?: string) => d.plan.items.find(i => i.id === id);
  let body: React.ReactNode = null, title = '', top: React.ReactNode = null;
  if (sel.kind === 'item' || sel.kind === 'stall') {
    const it = byId(sel.id);
    if (!it) return null;
    const stale = d.live.stale.includes(it.id);
    const act = d.live.activity[it.id];
    const s = ep(it.start), e = ep(it.end), ps = ep(it.planned_start), pe = ep(it.planned_end);
    const lane = d.plan.lanes.find(l => l.key === it.lane);
    const res = d.live.results.find(r => r.item === it.id);
    const after = byId(it.after), waits = byId(it.waits_on);
    const followers = d.plan.items.filter(i => i.after === it.id);
    const slip = pe != null && (e ?? (it.status === 'running' ? now : null)) != null ? ((e ?? now) - pe) : null;
    title = it.title;
    top = <div className="flex flex-wrap items-center gap-2 mt-1">
      <StatusPill it={it} stale={stale} />
      <span className="text-xs font-medium" style={{ color: it.lane === 'needs_you' ? C.owner : LANE_COLOR[it.lane] }}>{lane?.label}</span>
      {it.exp && <span className="text-xs text-gray-400">experiment {it.exp}</span>}</div>;
    body = <>
      {it.desc && <p className="text-sm text-gray-700 leading-relaxed">{it.desc}</p>}
      {it.outcome && <div className="mt-3 rounded-lg bg-gray-50 border border-gray-100 px-3 py-2 text-sm text-gray-800"><b className="text-gray-600 text-xs uppercase tracking-wide block mb-0.5">Outcome</b>{it.outcome}</div>}
      {it.lane === 'needs_you' && (it.recommended || it.unblocks) && <div className="mt-3 rounded-lg px-3 py-2 text-sm" style={{ background: C.ownerBg }}>
        {it.recommended && <p><b className="text-orange-800">We suggest:</b> {it.recommended}</p>}
        {it.unblocks && <p className="mt-1"><b className="text-orange-800">It unblocks:</b> {it.unblocks}</p>}</div>}
      {stale && <p className="mt-3 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-900">No sign of life for over an hour. The agent may have stopped, or it is working elsewhere without a heartbeat.</p>}
      <div className="mt-3">
        {s != null && <Row k={it.lane === 'needs_you' ? 'Asked' : 'Started'}><T t={s} tz={tz} now={now} /></Row>}
        {e != null && <Row k={it.lane === 'needs_you' ? 'Answered' : 'Ended'}><T t={e} tz={tz} now={now} /></Row>}
        {s != null && <Row k={it.status === 'blocked-on-owner' ? 'Waiting' : 'Took'}>{durText((e ?? now) - s)}{e == null ? ' so far' : ''}</Row>}
        {(ps != null || pe != null) && <Row k={it.lane === 'needs_you' ? 'Due' : 'Planned'}>{ps != null && <T t={ps} tz={tz} now={now} />}{ps != null && pe != null && ' → '}{pe != null && <T t={pe} tz={tz} now={now} />}
          {slip != null && it.lane !== 'needs_you' && <span className="block text-xs text-gray-500">{Math.abs(slip) < 600 ? 'on time' : `${durText(Math.abs(slip))} ${slip > 0 ? 'late' : 'early'}`}</span>}</Row>}
        {it.status === 'running' && act && <Row k="Last seen">{agoText(now - act.at)} <span className="text-xs text-gray-500">({act.source === 'beat' ? `heartbeat${act.note ? `: ${act.note}` : ''}` : act.source === 'folder' ? act.note : 'its start'})</span></Row>}
        {it.status === 'planned' && !ps && <Row k="When">Not on the clock yet{after ? <> — after <button className="text-indigo-700 underline" onClick={() => onPick({ kind: 'item', id: after.id })}>{after.title}</button></> : ''}</Row>}
        {waits && <Row k="Waits on">you: <button className="text-orange-700 underline" onClick={() => onPick({ kind: 'item', id: waits.id })}>{waits.title}</button></Row>}
        {followers.length > 0 && <Row k="Then">{followers.map((f, i) => <React.Fragment key={f.id}>{i ? ', ' : ''}<button className="text-indigo-700 underline" onClick={() => onPick({ kind: 'item', id: f.id })}>{f.title}</button></React.Fragment>)}</Row>}
        {it.urgency && <Row k="Urgency">{it.urgency}</Row>}
        {it.cost && <Row k="Cost">{it.cost}</Row>}
        {(it.by_whom || it.by) && <Row k="By">{it.by_whom || it.by}</Row>}
        {it.readme && <Row k="Write-up"><code className="text-[11px] break-all">{it.readme}</code>{res && <span className="block text-[11px] text-gray-400">last written {agoText(now - res.at)}</span>}</Row>}
      </div>
      <div className="mt-3"><Links links={it.links} /></div>
      <Sources s={it.source} approx={it.approx} />
    </>;
  } else if (sel.kind === 'marker') {
    const m = sel.m, t = ep(m.at)!;
    const it = byId(m.item);
    title = m.label;
    top = <div className="mt-1 text-xs font-medium text-gray-500 uppercase tracking-wide">{m.kind === 'eval' ? 'Result' : m.kind}</div>;
    body = <>
      {m.detail && <p className="text-sm text-gray-700">{m.detail}</p>}
      <div className="mt-3"><Row k="When"><T t={t} tz={tz} now={now} /></Row>
        {m.end && <Row k="Until"><T t={ep(m.end)} tz={tz} now={now} /></Row>}
        {it && <Row k="Work"><button className="text-indigo-700 underline" onClick={() => onPick({ kind: 'item', id: it.id })}>{it.title}</button></Row>}</div>
      {m.href && <div className="mt-3"><Links links={[{ label: 'Open', href: m.href }]} /></div>}
      <Sources s={m.source} />
    </>;
  } else if (sel.kind === 'promise') {
    const p = sel.p, it = byId(p.item);
    const late = d.live.overdue.includes(p.id);
    title = p.title;
    top = <div className="mt-1 text-xs font-semibold uppercase tracking-wide" style={{ color: late ? C.alert : p.status === 'kept' ? C.live : '#4f46e5' }}>
      Promise · {late ? 'overdue' : p.status}</div>;
    body = <>
      {p.detail && <p className="text-sm text-gray-700">{p.detail}</p>}
      <div className="mt-3">
        <Row k="Promised"><T t={ep(p.made_at)} tz={tz} now={now} /></Row>
        <Row k="Due">{p.due ? <T t={ep(p.due)} tz={tz} now={now} /> : 'no time given'}</Row>
        {p.closed_at && <Row k={p.status === 'kept' ? 'Kept' : 'Closed'}><T t={ep(p.closed_at)} tz={tz} now={now} /></Row>}
        {p.outcome && <Row k="Outcome">{p.outcome}</Row>}
        {p.by && <Row k="By">{p.by}</Row>}
        {it && <Row k="Work"><button className="text-indigo-700 underline" onClick={() => onPick({ kind: 'item', id: it.id })}>{it.title}</button></Row>}
      </div>
      <Sources s={p.source} />
    </>;
  } else if (sel.kind === 'release') {
    title = `Desk release ${sel.id}`;
    top = <div className="mt-1 text-xs font-medium uppercase tracking-wide" style={{ color: sel.live ? '#0d9488' : C.muted }}>{sel.live ? 'Live: the Desk reads this one' : 'Release'}</div>;
    body = <><p className="text-sm text-gray-700">A release is the Desk's reading with every decision re-applied. Its time comes from its name (UTC).</p>
      <div className="mt-3"><Row k="Built"><T t={sel.at} tz={tz} now={now} /></Row></div>
      <div className="mt-3"><Links links={[{ label: 'Releases', href: '/releases' }]} /></div></>;
  } else if (sel.kind === 'deploy') {
    title = 'The live Desk was rebuilt';
    top = <div className="mt-1 text-xs font-medium uppercase tracking-wide text-indigo-700">Deploy</div>;
    body = <><p className="text-sm text-gray-700">The time of the live web build (read from the file below), so a page change reached the owner then.</p>
      <div className="mt-3"><Row k="When"><T t={sel.at} tz={tz} now={now} /></Row><Row k="Read from"><code className="text-[11px] break-all">{sel.detail}</code></Row></div></>;
  }
  return (
    <aside role="dialog" aria-label={title} data-testid="plan-panel"
      className="fixed z-40 bg-white shadow-xl border-gray-200 overflow-y-auto inset-x-0 bottom-0 max-h-[75vh] rounded-t-2xl border-t md:inset-x-auto md:right-4 md:top-20 md:bottom-4 md:w-[400px] md:max-h-none md:rounded-2xl md:border"
      onClick={e => e.stopPropagation()}>
      <div className="sticky top-0 bg-white px-4 pt-3 pb-2 border-b border-gray-100">
        <div className="md:hidden mx-auto mb-2 h-1 w-10 rounded-full bg-gray-300" aria-hidden />
        <div className="flex items-start gap-2">
          <h2 className="text-base font-semibold text-gray-900 flex-1 leading-snug">{title}</h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100" aria-label="Close"><X className="w-4 h-4" /></button>
        </div>
        {top}
      </div>
      <div className="px-4 py-3">{body}</div>
    </aside>);
};
export default PlanPanel;

