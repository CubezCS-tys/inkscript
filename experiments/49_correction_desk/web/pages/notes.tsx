import React, { useState } from 'react';
import Link from 'next/link';
import Layout from '../components/Layout';
import { Btn, Card, Chip, Empty, ErrorBox, actorName, when } from '../components/Bits';
import { api, hrefOf } from '../lib/api';
import { useApi, useMe } from '../lib/me';
import { S, opLabel } from '../lib/strings';

const List: React.FC<{ rows: any[] | null; reload: () => void; mineAre: 'inbox' | 'written' }> = ({ rows, reload, mineAre }) => {
  const [err, setErr] = useState('');
  const { reload: reloadMe } = useMe();
  if (!rows) return <Empty>{S.common.loading}</Empty>;
  if (!rows.length) return <Empty>{S.notes.none}</Empty>;
  const resolve = async (id: number) => { try { await api(`/notes/${id}/resolve`, { method: 'POST' }); reload(); reloadMe(); } catch (e: any) { setErr(e.message); } };
  return (
    <>
      {err && <ErrorBox>{err}</ErrorBox>}
      <ul className="divide-y divide-gray-100" data-testid={`notes-${mineAre}`}>{rows.map(n => (
        <li key={n.note_id} className="py-3 flex gap-3 items-start">
          <div className="flex-1 min-w-0 space-y-1">
            <p className="text-sm text-gray-900 whitespace-pre-wrap" dir="auto">{n.text}</p>
            <p className="text-xs text-gray-500">
              {mineAre === 'inbox' ? `from ${actorName(n.author)}` : n.decision_owner ? `to ${actorName(n.decision_owner)}` : ''} · {when(n.created_at)} · {S.notes.on}{' '}
              {hrefOf(n.subject_key) ? <Link href={hrefOf(n.subject_key)!} className="font-mono text-indigo-700 hover:underline">{n.subject_key}</Link> : <span className="font-mono">{n.subject_key}</span>}
              {n.op && <> · {opLabel(n.op)}</>}
            </p>
          </div>
          {n.resolved_at ? <Chip tone="green">{S.notes.resolved}</Chip> : <Btn small onClick={() => resolve(n.note_id)}>{S.notes.resolve}</Btn>}
        </li>))}
      </ul>
    </>
  );
};

export default function Notes() {
  const [all, setAll] = useState(false);
  const inbox = useApi<any[]>(`/me/notes?include_resolved=${all}`, [all]);
  const written = useApi<any[]>(`/me/notes/written?include_resolved=${all}`, [all]);
  return (
    <Layout>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold text-gray-900">{S.notes.title}</h1>
        <label className="text-sm text-gray-600 flex items-center gap-2"><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} className="rounded border-gray-300" />{S.notes.showResolved}</label>
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Card title={S.notes.inbox}>{inbox.err ? <ErrorBox>{inbox.err}</ErrorBox> : <List rows={inbox.data} reload={inbox.reload} mineAre="inbox" />}</Card>
        <Card title={S.notes.written}>{written.err ? <ErrorBox>{written.err}</ErrorBox> : <List rows={written.data} reload={written.reload} mineAre="written" />}</Card>
      </div>
    </Layout>
  );
}
