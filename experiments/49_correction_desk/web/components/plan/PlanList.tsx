import React, { useState } from 'react';
import { C, Item, LANE_COLOR, NEEDS_SHOWN, PlanData, Promise_, agoText, ep, needsInOrder, nextInOrder, whenUK } from './model';
import { StatusPill } from './PlanPanel';
import type { Sel } from './PlanChart';

// The plan as a stacked list (phones by default; "List" on a wide screen): running now, needs you, promises, next
// (in order), live, done (newest first) and parked or dropped. Tap a row for its card.

const Section: React.FC<{ title: string; n: number; tone?: string; children: React.ReactNode; testid: string }> = ({ title, n, tone, children, testid }) => (
  <section className="rounded-2xl border border-gray-200 bg-white p-4" data-testid={testid}>
    <h2 className="text-sm font-semibold mb-2" style={{ color: tone || '#111827' }}>{title} <span className="text-gray-400 font-normal">({n})</span></h2>
    {n === 0 ? <p className="text-sm text-gray-400">Nothing.</p> : <ul className="divide-y divide-gray-100">{children}</ul>}
  </section>);

const ItemRow: React.FC<{ it: Item; d: PlanData; now: number; onPick: (s: Sel) => void; line: React.ReactNode }> = ({ it, d, now, onPick, line }) => (
  <li>
    <button className="w-full text-left py-2.5 flex gap-3 items-start hover:bg-gray-50 rounded-lg px-1" onClick={() => onPick({ kind: 'item', id: it.id })} data-list-item={it.id}>
      <span className="mt-1.5 w-2.5 h-2.5 rounded-full shrink-0" style={{ background: it.lane === 'needs_you' ? C.owner : LANE_COLOR[it.lane] }} aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2"><span className="text-[14px] font-medium text-gray-900">{it.title}</span>
          {['running', 'live'].includes(it.status) && <StatusPill it={it} stale={d.live.stale.includes(it.id)} />}</span>
        <span className="block text-xs text-gray-500 mt-0.5">{line}</span>
      </span>
    </button>
  </li>);

const laneName = (d: PlanData, k: string) => d.plan.lanes.find(l => l.key === k)?.label || k;

const PlanList: React.FC<{ d: PlanData; now: number; onPick: (s: Sel) => void }> = ({ d, now, onPick }) => {
  const [allDone, setAllDone] = useState(false);
  const [allNeeds, setAllNeeds] = useState(false);
  const items = d.plan.items;
  const running = items.filter(i => i.status === 'running');
  const needs = needsInOrder(items);
  const needsShown = allNeeds ? needs : needs.slice(0, NEEDS_SHOWN);
  const next = nextInOrder(items);
  const live = items.filter(i => i.status === 'live');
  const done = items.filter(i => i.status === 'done').sort((a, b) => (ep(b.end) || 0) - (ep(a.end) || 0));
  const shelved = items.filter(i => i.status === 'parked' || i.status === 'dropped');
  const proms = d.plan.promises.filter(p => p.status === 'open');
  const byId = (id?: string) => items.find(i => i.id === id);
  const doneShown = allDone ? done : done.filter(i => (ep(i.end) || 0) > now - 7 * 86400);
  const promLine = (p: Promise_) => {
    const late = d.live.overdue.includes(p.id);
    return <span style={{ color: late ? C.alert : undefined }}>{p.due ? `${late ? 'overdue: was ' : ''}due ${whenUK(ep(p.due), now)} UK` : 'no time given'}{p.by ? ` · ${p.by}` : ''}</span>;
  };
  return (
    <div className="grid gap-3 md:grid-cols-2" data-testid="plan-list">
      <Section title="Running now" n={running.length} tone="#0f766e" testid="list-running">
        {running.map(it => { const a = d.live.activity[it.id]; return <ItemRow key={it.id} it={it} d={d} now={now} onPick={onPick}
          line={<>{laneName(d, it.lane)} · started {whenUK(ep(it.start), now)} UK{a ? ` · last seen ${agoText(now - a.at)}` : ''}</>} />; })}
      </Section>
      <Section title="Needs you, most urgent first" n={needs.length} tone={C.owner} testid="list-needs">
        {needsShown.map(it => <ItemRow key={it.id} it={it} d={d} now={now} onPick={onPick}
          line={<>{it.urgency ? `${it.urgency} · ` : ''}waiting since {whenUK(ep(it.start), now)} UK{it.planned_end ? ` · due ${whenUK(ep(it.planned_end), now)}` : ''}</>} />)}
        {needs.length > NEEDS_SHOWN && <li className="pt-2"><button className="text-sm text-orange-700 underline" data-testid="list-needs-more" onClick={() => setAllNeeds(x => !x)}>
          {allNeeds ? `Show only the ${NEEDS_SHOWN} most urgent` : `+${needs.length - NEEDS_SHOWN} more waiting on you`}</button></li>}
      </Section>
      <Section title="Promises" n={proms.length} tone="#3730a3" testid="list-promises">
        {proms.map(p => (
          <li key={p.id}><button className="w-full text-left py-2.5 px-1 hover:bg-gray-50 rounded-lg" onClick={() => onPick({ kind: 'promise', p })}>
            <span className="text-[14px] font-medium text-gray-900">{p.title}</span><span className="block text-xs text-gray-500 mt-0.5">{promLine(p)}</span></button></li>))}
      </Section>
      <Section title="Next, in order" n={next.length} tone="#3730a3" testid="list-next">
        {next.map((it, i) => <ItemRow key={it.id} it={it} d={d} now={now} onPick={onPick}
          line={<>{i + 1}. {laneName(d, it.lane)}{it.planned_start ? ` · planned ${whenUK(ep(it.planned_start), now)} UK` : byId(it.after) ? ` · after “${byId(it.after)!.title}”` : ' · no date yet'}
            {it.waits_on ? <span style={{ color: C.owner }}> · waits on you</span> : null}{it.cost ? ` · ${it.cost}` : ''}</>} />)}
      </Section>
      <Section title="Live" n={live.length} tone="#166534" testid="list-live">
        {live.map(it => <ItemRow key={it.id} it={it} d={d} now={now} onPick={onPick} line={<>{laneName(d, it.lane)} · since {whenUK(ep(it.start), now)} UK</>} />)}
      </Section>
      <Section title={allDone ? 'Done' : 'Done in the last 7 days'} n={doneShown.length} testid="list-done">
        {doneShown.map(it => <ItemRow key={it.id} it={it} d={d} now={now} onPick={onPick}
          line={<>{laneName(d, it.lane)} · finished {whenUK(ep(it.end), now)} UK{it.outcome ? ` · ${it.outcome}` : ''}</>} />)}
        {!allDone && done.length > doneShown.length && <li className="pt-2"><button className="text-sm text-indigo-700 underline" onClick={() => setAllDone(true)}>Show all {done.length}</button></li>}
      </Section>
      {shelved.length > 0 && <Section title="Parked or dropped" n={shelved.length} testid="list-shelved">
        {shelved.map(it => <ItemRow key={it.id} it={it} d={d} now={now} onPick={onPick} line={<>{laneName(d, it.lane)}{it.outcome ? ` · ${it.outcome}` : ''}</>} />)}
      </Section>}
    </div>);
};
export default PlanList;
