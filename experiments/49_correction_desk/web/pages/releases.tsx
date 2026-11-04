import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Package, ArrowUp, ArrowDown, Minus, Sparkles } from 'lucide-react';
import Layout from '../components/Layout';
import { Btn, Card, Chip, Empty, ErrorBox, StatusPill, T, n, when } from '../components/Bits';
import { api } from '../lib/api';
import { useApi, useMe } from '../lib/me';
import { S, f } from '../lib/strings';

const Move: React.FC<{ a?: number | null; b?: number | null }> = ({ a, b }) => {
  if (a == null) return <span className="inline-flex items-center text-indigo-700 text-xs gap-0.5"><Sparkles className="w-3.5 h-3.5" />new</span>;
  if (b == null) return <span className="text-xs text-gray-400">out</span>;
  if (a === b) return <Minus className="w-3.5 h-3.5 text-gray-300 inline" />;
  return a > b ? <span className="inline-flex items-center text-green-700 text-xs"><ArrowUp className="w-3.5 h-3.5" />{a - b}</span>
    : <span className="inline-flex items-center text-red-700 text-xs"><ArrowDown className="w-3.5 h-3.5" />{b - a}</span>;
};

const Diff: React.FC<{ id: string; vs: string }> = ({ id, vs }) => {
  const { data: d, err } = useApi<any>(`/releases/${id}/diff${vs ? `?vs=${vs}` : ''}`);
  if (err) return <ErrorBox>{err}</ErrorBox>;
  if (!d) return <Empty>{S.common.loading}</Empty>;
  const label = (x: string) => (x === 'reading' ? S.common.reading : x);
  return (
    <div className="space-y-4" data-testid="diff">
      <p className="text-sm text-gray-600"><span className="font-medium text-gray-900">{label(d.after)}</span> {S.releases.vs} <span className="font-medium text-gray-900">{label(d.before)}</span>
        {' · '}cards {n(d.counts.cards_before)} → {n(d.counts.cards_after)} · persons {n(d.counts.persons_before)} → {n(d.counts.persons_after)}</p>
      <div className="grid lg:grid-cols-2 gap-4">
        {[['before', S.releases.topBefore, d.top_before], ['after', S.releases.topAfter, d.top]].map(([k, title, rows]: any) => (
          <Card key={k} pad={false} title={`${title}: ${label(k === 'before' ? d.before : d.after)}`}>
            <table className="w-full text-sm" data-testid={`top-${k}`}>
              <thead className="bg-gray-50 text-xs text-gray-500"><tr><th className="px-3 py-1.5 text-right font-medium w-10">#</th><th className="px-2 py-1.5 text-right font-medium">{S.top.work}</th>
                <th className="px-2 py-1.5 text-right font-medium">{S.top.citing}</th><th className="px-2 py-1.5 font-medium w-16" /></tr></thead>
              <tbody>{rows.map((w: any) => {
                const changed = w.n_before !== w.n_after || w.rank_before == null || w.rank_after == null;   // its count moved, or it entered / left the list
                return (
                  <tr key={w.id} className={`border-t border-gray-100 ${changed ? 'bg-amber-50/60' : ''}`} data-work={w.id} data-changed={changed ? '1' : '0'}>
                    <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">{k === 'after' ? w.rank_after : w.rank_before}</td>
                    <td className="px-2 py-1.5 text-right"><Link href={`/works/${w.id}`} className="hover:text-indigo-700"><T text={w.title} /></Link> <span className="text-[10px] text-gray-400 font-mono">{w.id}</span></td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{k === 'after'
                      ? <>{w.n_before != null && w.n_before !== w.n_after && <span className="text-gray-400 line-through mr-1">{w.n_before}</span>}<span className="font-medium">{w.n_after}</span></>
                      : <>{w.n_before}{w.n_after != null && w.n_after !== w.n_before && <span className="text-gray-500"> → {w.n_after}</span>}</>}</td>
                    <td className="px-2 py-1.5 text-center">{k === 'after' ? <Move a={w.rank_before} b={w.rank_after} /> : <Move a={w.rank_before} b={w.rank_after} />}</td>
                  </tr>);
              })}</tbody>
            </table>
          </Card>))}
      </div>
      <Card title={`${S.releases.cards} (${d.cards.length})`}>
        {d.cards.length === 0 ? <Empty>{S.releases.noCards}</Empty> : (
          <ul className="space-y-3" data-testid="diff-cards">{d.cards.map((c: any, i: number) => (
            <li key={i} className="text-sm">
              <div className="flex flex-wrap items-center gap-2"><Chip tone={c.kind === 'merged' ? 'indigo' : c.kind === 'split' ? 'amber' : 'gray'}>{(S.releases as any)[c.kind === 'members moved' ? 'moved' : c.kind] || c.kind}</Chip>
                <Link href={`/works/${c.card}`} className="font-medium hover:text-indigo-700"><T text={c.title} /></Link><span className="text-xs text-gray-400 font-mono">{c.card}</span>
                <span className="text-xs text-gray-500">{c.n_before != null ? `${c.n_before} citing before` : ''}{c.n_after != null ? `${c.n_after} citing after` : ''}</span></div>
              <ul className="ms-6 mt-1 text-xs text-gray-600 space-y-0.5">{(c.to || c.frm || []).map((x: any) => (
                <li key={x.card}>{c.to ? S.releases.into : S.releases.from} <Link href={`/works/${x.card}`} className="font-mono text-indigo-700 hover:underline">{x.card}</Link> <span className="ar-inline">{x.title}</span> · {x.members} citation(s){x.n_after != null ? ` · cited by ${x.n_after}` : x.n_before != null ? ` · was cited by ${x.n_before}` : ''}</li>))}
              </ul>
            </li>))}
          </ul>)}
      </Card>
      <Card title={S.releases.persons}>
        {d.persons.length === 0 && d.bylines_moved.length === 0 ? <Empty>{S.releases.noPersons}</Empty> : (
          <ul className="space-y-1 text-sm" data-testid="diff-persons">{d.persons.map((p: any) => (
            <li key={p.person}><Chip tone={p.kind === 'merged' ? 'indigo' : 'gray'}>{p.kind === 'merged' ? S.releases.merged : S.releases.newPerson}</Chip> <T text={p.name} /> <span className="font-mono text-xs text-gray-400">{p.person}</span>
              {p.into && <> {S.releases.into} <Link href={`/persons/${p.into}`} className="text-indigo-700 hover:underline"><T text={p.into_name} /></Link> <span className="font-mono text-xs text-gray-400">{p.into}</span></>}</li>))}
            {d.bylines_moved.map((b: any) => <li key={b.authorship}><Chip>byline</Chip> <T text={b.before_name} /> → <Link href={`/persons/${b.after}`} className="text-indigo-700 hover:underline"><T text={b.after_name} /></Link></li>)}
          </ul>)}
        {d.authorships_joined > 0 && <p className="text-xs text-gray-500 mt-2">{f(S.releases.joined, { n: d.authorships_joined })}</p>}
      </Card>
    </div>
  );
};

export default function Releases() {
  const router = useRouter();
  const { me } = useMe();
  const rel = useApi<any[]>('/releases');
  const [build, setBuild] = useState<any>(null);
  const [note, setNote] = useState('');
  const [err, setErr] = useState('');
  const sel = typeof router.query.id === 'string' ? router.query.id : null;
  const vs = typeof router.query.vs === 'string' ? router.query.vs : '';
  const built = (rel.data || []).filter((r: any) => r.status === 'built');
  const current = sel || built[0]?.release_id;
  const poll = async () => { try { setBuild(await api('/build')); } catch { /* ignore */ } };
  useEffect(() => { poll(); }, []);
  useEffect(() => {
    if (!build?.running) return;
    const t = setInterval(async () => { const b = await api('/build'); setBuild(b); if (!b.running) { rel.reload(); if (b.release_id) router.replace(`/releases?id=${b.release_id}`); } }, 1500);
    return () => clearInterval(t);
  }, [build?.running]);
  const start = async () => {
    setErr('');
    try { setBuild(await api('/releases', { json: { note: note || null, run_detectors: true } })); } catch (e: any) { setErr(e.message); }
  };
  return (
    <Layout wide>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-semibold text-gray-900">{S.releases.title}</h1><p className="text-sm text-gray-500">{S.releases.lead}</p></div>
        {me?.role === 'admin' ? (
          <div className="flex items-center gap-2">
            <input value={note} onChange={e => setNote(e.target.value)} placeholder={S.releases.notePh} className="rounded-lg border-gray-300 text-sm w-56" />
            <Btn kind="primary" onClick={start} disabled={build?.running} data-testid="build"><Package className="w-4 h-4" />{S.releases.build}</Btn>
          </div>
        ) : <span className="text-xs text-gray-500">{S.releases.adminOnly}</span>}
      </div>
      {err && <ErrorBox>{err}</ErrorBox>}
      {build?.running && <p className="text-sm text-indigo-700" role="status" data-testid="build-status">{f(S.releases.building, { phase: build.phase || '' })}</p>}
      {build && !build.running && build.finished_at && (build.error
        ? <ErrorBox>{f(S.releases.failed, { e: build.error })}</ErrorBox>
        : <p className="text-sm text-green-700" role="status" data-testid="build-status">{f(S.releases.built, { id: build.release_id, s: build.seconds })} · applied {build.n_applied} of {build.n_decisions}{build.detectors ? ` · detectors: ${Object.entries(build.detectors).map(([k, v]: any) => `${k} ${v.tasks}`).join(', ')}` : ''}</p>)}
      <Card pad={false} className="overflow-x-auto">
        {!rel.data ? <div className="p-4"><Empty>{S.common.loading}</Empty></div> : (
          <table className="w-full text-sm" data-testid="releases">
            <thead className="bg-gray-50 text-xs text-gray-500"><tr>
              {['id', 'when', 'applied', 'orphaned', 'conflict', 'copy', 'note'].map(k => <th key={k} className="px-3 py-2 text-left font-medium">{(S.releases.cols as any)[k]}</th>)}<th /></tr></thead>
            <tbody>{rel.data.map((r: any) => (
              <tr key={r.release_id} className={`border-t border-gray-100 ${r.release_id === current ? 'bg-indigo-50/50' : 'hover:bg-gray-50'}`}>
                <td className="px-3 py-2 font-mono text-xs">{r.release_id} {r.status !== 'built' && <Chip tone={r.status === 'failed' ? 'red' : 'amber'}>{r.status}</Chip>}</td>
                <td className="px-3 py-2 whitespace-nowrap text-gray-600">{when(r.finished_at || r.started_at)}</td>
                <td className="px-3 py-2 tabular-nums">{r.n_applied ?? '—'} / {r.n_decisions ?? '—'}</td>
                <td className="px-3 py-2"><StatusPill light={r.n_orphaned ? 'warning' : 'good'} label={String(r.n_orphaned ?? '—')} /></td>
                <td className="px-3 py-2"><StatusPill light={r.n_conflict ? 'warning' : 'good'} label={String(r.n_conflict ?? '—')} /></td>
                <td className="px-3 py-2 text-xs text-gray-500">{r.copy_deleted_at ? S.common.no : S.common.yes}</td>
                <td className="px-3 py-2 text-xs text-gray-600 max-w-md truncate" title={r.note}>{r.note}</td>
                <td className="px-3 py-2 text-right">{r.status === 'built' && <Link href={`/releases?id=${r.release_id}`} className="text-indigo-700 hover:underline text-xs whitespace-nowrap">{S.releases.compare}</Link>}</td>
              </tr>))}
            </tbody>
          </table>)}
      </Card>
      {current && (
        <Card title={`${S.releases.compare}: ${current}`} right={
          <label className="text-xs text-gray-500 flex items-center gap-2">{S.releases.vs}
            <select value={vs} onChange={e => router.replace(`/releases?id=${current}${e.target.value ? `&vs=${e.target.value}` : ''}`)} className="rounded-lg border-gray-300 text-xs py-1">
              <option value="">the one before (default)</option><option value="reading">{S.common.reading}</option>
              {built.filter((r: any) => r.release_id !== current).map((r: any) => <option key={r.release_id} value={r.release_id}>{r.release_id}</option>)}
            </select></label>}>
          <Diff key={`${current}-${vs}`} id={current} vs={vs} />
        </Card>
      )}
    </Layout>
  );
}
