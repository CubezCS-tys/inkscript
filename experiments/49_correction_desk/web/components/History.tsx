import React, { useState } from 'react';
import Link from 'next/link';
import { MessageSquarePlus, Undo2, Wrench, Pencil, CheckCircle2 } from 'lucide-react';
import { api, hrefOf } from '../lib/api';
import { rightsOn, useApi, useMe } from '../lib/me';
import { S, f, opLabel } from '../lib/strings';
import { Btn, Card, Chip, Empty, ErrorBox, actorName, when } from './Bits';

// One decision with its owner, and what *you* may do with it (DESIGN §7): the owner sees "Change", an admin
// "Fix" (logged), anyone else "Leave a note" (the owner finds it in their inbox).
export const DecisionRow: React.FC<{ d: any; subject: string; onDone?: () => void; compact?: boolean }> = ({ d, subject, onDone, compact }) => {
  const { me } = useMe();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const right = rightsOn(me, d);
  const standing = ['accepted', 'proposed'].includes(d.status) && !['revert', 'retire'].includes(d.op);
  const undo = async () => {
    setErr('');
    try {
      await api(`/decisions/${d.decision_id}/revert`, { json: { note: text || (right === 'admin' ? 'admin fix' : 'undone by its owner') } });
      setMsg(S.history.sent); setOpen(false); onDone?.();
    } catch (e: any) { setErr(e.message); }
  };
  const note = async () => {
    setErr('');
    const key = d.subject_keys.includes(subject) ? subject : d.subject_keys[0];
    try {
      await api(`/subjects/${encodeURIComponent(key)}/notes`, { json: { text, decision_id: d.decision_id } });
      setMsg(S.history.sent); setOpen(false); setText(''); onDone?.();
    } catch (e: any) { setErr(e.message); }
  };
  const tone = d.status === 'accepted' ? 'indigo' : d.status === 'superseded' ? 'gray' : 'amber';
  return (
    <li className="flex gap-3" data-decision={d.decision_id}>
      <span className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${d.status === 'accepted' ? 'bg-indigo-500' : 'bg-gray-300'}`} aria-hidden />
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-medium text-gray-900">{opLabel(d.op)}</span>
          <Chip tone={tone as any}>{d.status}</Chip>
          <span className="text-gray-500">{f(S.history.by, { who: actorName(d.actor_id) })}{d.role_at_time === 'admin' ? ' (admin)' : ''} · {when(d.created_at)}</span>
          {right === 'owner' && <Chip tone="green">{S.history.mine}</Chip>}
          {d.confidence && d.confidence !== 'sure' && <Chip tone="amber">{d.confidence}</Chip>}
        </div>
        {!compact && (
          <div className="text-xs text-gray-500 flex flex-wrap gap-x-2">
            {d.subject_keys.map((k: string) => hrefOf(k)
              ? <Link key={k} href={hrefOf(k)!} className="font-mono hover:text-indigo-700 hover:underline">{k}</Link>
              : <span key={k} className="font-mono">{k}</span>)}
          </div>
        )}
        {d.op === 'split_work' && d.payload?.groups && (
          <p className="text-xs text-gray-600">{d.payload.groups.length} groups: {d.payload.groups.map((g: any) => `${g.card_id} (${g.members.length})`).join(' · ')}</p>
        )}
        {d.note && <p className="text-sm text-gray-700">{d.note}</p>}
        {(d.applications || []).length > 0 && (
          <p className="text-xs text-gray-500">{d.applications.map((a: any) => f(S.history.applied, { r: a.release_id, s: a.status })).join(' · ')}</p>
        )}
        {msg && <p className="text-xs text-green-700 flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" />{msg}</p>}
        {standing && !open && (
          <div className="pt-0.5">
            {right === 'owner' && <Btn small onClick={() => setOpen(true)}><Pencil className="w-3.5 h-3.5" />{S.history.change}</Btn>}
            {right === 'admin' && <Btn small onClick={() => setOpen(true)}><Wrench className="w-3.5 h-3.5" />{S.history.fix}</Btn>}
            {right !== 'owner' && <Btn small className="ml-1" onClick={() => setOpen(true)} data-action="note"><MessageSquarePlus className="w-3.5 h-3.5" />{S.history.leaveNote}</Btn>}
          </div>
        )}
        {open && (
          <div className="mt-1 p-3 rounded-lg bg-gray-50 border border-gray-200 space-y-2 text-sm">
            {right === 'owner' && <p className="text-gray-600">{S.history.changeLead}</p>}
            {right === 'admin' && <p className="text-gray-600">{S.history.fixLead}</p>}
            <textarea rows={2} value={text} onChange={e => setText(e.target.value)} dir="auto" className="w-full rounded-lg border-gray-300 text-sm"
              placeholder={right === 'other' ? f(S.history.notePh, { owner: actorName(d.actor_id) }) : S.history.undoNotePh} />
            {err && <ErrorBox>{err}</ErrorBox>}
            <div className="flex flex-wrap gap-2">
              {right !== 'other' && <Btn small kind="danger" onClick={undo}><Undo2 className="w-3.5 h-3.5" />{S.history.undo}</Btn>}
              {right !== 'owner' && <Btn small kind="primary" disabled={!text.trim()} onClick={note}>{S.history.sendNote}</Btn>}
              <Btn small onClick={() => setOpen(false)}>{S.common.cancel}</Btn>
            </div>
          </div>
        )}
      </div>
    </li>
  );
};

export const History: React.FC<{ subject: string; path?: string }> = ({ subject, path }) => {
  const h = useApi<any>(path || `/subjects/${encodeURIComponent(subject)}/history`);
  if (h.err) return <ErrorBox>{h.err}</ErrorBox>;
  if (!h.data) return <Empty>{S.common.loading}</Empty>;
  const decs = [...h.data.decisions].reverse();
  return (
    <Card title={S.history.title} right={<span className="text-xs text-gray-500">{S.history.lead}</span>}>
      {decs.length === 0 ? <Empty>{S.history.none}</Empty> : (
        <ol className="space-y-4" data-testid="history">{decs.map((d: any) => <DecisionRow key={d.decision_id} d={d} subject={subject} onDone={h.reload} />)}</ol>
      )}
      {h.data.tasks?.length > 0 && (
        <div className="mt-4 text-xs text-gray-500">{S.history.tasks}: {h.data.tasks.map((t: any) => `${t.task_id} ${t.kind} (${t.state})`).join(' · ')}</div>
      )}
    </Card>
  );
};

export const Notes: React.FC<{ subject: string }> = ({ subject }) => {
  const { me } = useMe();
  const h = useApi<any[]>(`/subjects/${encodeURIComponent(subject)}/notes`);
  const [text, setText] = useState('');
  const [err, setErr] = useState('');
  const add = async () => {
    setErr('');
    try { await api(`/subjects/${encodeURIComponent(subject)}/notes`, { json: { text } }); setText(''); h.reload(); } catch (e: any) { setErr(e.message); }
  };
  const resolve = async (id: number) => { try { await api(`/notes/${id}/resolve`, { method: 'POST' }); h.reload(); } catch (e: any) { setErr(e.message); } };
  return (
    <Card title={S.history.notesTitle}>
      {!h.data ? <Empty>{S.common.loading}</Empty> : h.data.length === 0 ? <Empty>{S.history.notesNone}</Empty> : (
        <ul className="divide-y divide-gray-100">{h.data.map((n: any) => (
          <li key={n.note_id} className="py-2 text-sm flex gap-3 items-start">
            <div className="flex-1 min-w-0">
              <p className="text-gray-800 whitespace-pre-wrap" dir="auto">{n.text}</p>
              <p className="text-xs text-gray-500">{actorName(n.author)} · {when(n.created_at)}{n.decision_id ? ` · on decision ${String(n.decision_id).slice(0, 8)}` : ''}{n.resolved_at ? ` · ${S.history.resolved}` : ''}</p>
            </div>
            {!n.resolved_at && (me?.role === 'admin' || me?.actor_id === n.author) && <Btn small onClick={() => resolve(n.note_id)}>{S.history.resolve}</Btn>}
          </li>))}
        </ul>
      )}
      <div className="mt-3 space-y-2">
        <textarea rows={2} value={text} onChange={e => setText(e.target.value)} dir="auto" className="w-full rounded-lg border-gray-300 text-sm" placeholder={S.history.addNote} />
        {err && <ErrorBox>{err}</ErrorBox>}
        <Btn small kind="primary" disabled={!text.trim()} onClick={add}>{S.history.sendNote}</Btn>
      </div>
    </Card>
  );
};

// The standing decisions on an entity, with owners, at the top of its Current tab
export const Standing: React.FC<{ desk: any; subject: string; onDone?: () => void }> = ({ desk, subject, onDone }) => {
  if (!desk || !desk.standing?.length) return null;
  return (
    <Card title={S.history.standing} right={desk.open_notes ? <Chip tone="amber">{desk.open_notes} open notes</Chip> : null}>
      <ol className="space-y-3">{desk.standing.map((d: any) => <DecisionRow key={d.decision_id} d={d} subject={subject} onDone={onDone} />)}</ol>
    </Card>
  );
};
