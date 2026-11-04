import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { AlertTriangle } from 'lucide-react';
import Layout from '../../components/Layout';
import { Btn, Card, Chip, Crop, Empty, ErrorBox, T, Tabs, n } from '../../components/Bits';
import { History, Notes, Standing } from '../../components/History';
import { GroupsSummary, SplitPicker, booksOf } from '../../components/SplitPicker';
import { WrongPanel, useDecide } from '../../components/Decide';
import { cropOfAnchor, enc, hrefOf } from '../../lib/api';
import { useApi } from '../../lib/me';
import { useShowMode } from '../../lib/showmode';
import { S, f } from '../../lib/strings';

const TYPES = ['book', 'turath', 'diwan', 'serial', 'law', 'legal-decision', 'article', 'thesis', 'chapter', 'conference-paper', 'manuscript', 'web', 'hadith-collection', 'report', 'dictionary', 'not-a-work'];

export default function WorkPage() {
  const router = useRouter();
  const id = typeof router.query.id === 'string' ? router.query.id : null;
  const [tab, setTab] = useState('current');
  const w = useApi<any>(id ? `/works/${enc(id)}` : null);
  const showMode = useShowMode();
  const d = w.data;
  const subject = d?.subject || (id ? `work:${id}` : '');
  const { decide, busy, status } = useDecide(w.reload);
  const members = useMemo(() => (d?.members || []).map((m: any) => ({ ...m })), [d]);
  const [group, setGroup] = useState<Record<string, number>>({});
  useEffect(() => { const g: Record<string, number> = {}; members.forEach((m: any, i: number) => { g[m.key] = 1; }); setGroup(g); }, [members]);
  const [other, setOther] = useState('');
  const [member, setMember] = useState('');
  const [type, setType] = useState('book');
  const otherKey = other.trim() ? `work:${other.trim().replace(/^work:/, '').toUpperCase()}` : '';
  return (
    <Layout>
      {w.err && <ErrorBox>{w.err}</ErrorBox>}
      {!d ? !w.err && <Empty>{S.common.loading}</Empty> : (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs text-gray-500">{S.workPage.title}{!showMode && <> · <span className="font-mono">{d.id}</span></>} · {d.pub_type || '—'}{!showMode && <> · {d.status}
                {d.resolved_from && <> · <Chip tone="amber">{d.resolved_from} → {d.id}</Chip></>} · {S.common.readFrom} {d.release_id || S.common.reading}</>}</p>
              <h1 className="text-2xl font-semibold text-gray-900 mt-1" data-testid="work-title"><T text={d.title || d.id} /> <span className="text-gray-400 font-normal text-lg">({f(S.article.timesCited, { n: n(d.n_citing_pubs) })}, {n(d.n_mentions)} mentions)</span></h1>
              {d.merged_from?.length > 0 && <p className="text-xs text-gray-500">{f(S.workPage.merged, { ids: d.merged_from.join(', ') })}</p>}
            </div>
            {!showMode && <Tabs value={tab} onChange={setTab} tabs={[['current', S.common.current], ['history', S.common.history], ['notes', S.common.notes]]} />}
          </div>
          {d.pending && <ErrorBox>{S.workPage.pending}</ErrorBox>}
          {tab === 'current' && (
            <>
              <Standing desk={d.desk} subject={subject} onDone={w.reload} />
              {(d.editions || []).length > 0 && (
                <Card pad={false} title={`${S.workPage.editions} (${d.editions.length})`}>
                  <table className="w-full text-sm" data-testid="work-editions"><thead className="bg-gray-50 text-xs text-gray-500"><tr>
                    {(['edition', 'year', 'publisher', 'place', 'n'] as const).map(k => <th key={k} className="px-4 py-2 text-start font-medium">{S.workPage.editionCols[k]}</th>)}</tr></thead>
                    <tbody>{d.editions.map((e: any) => (
                      <tr key={e.edition_pk} className="border-t border-gray-100">
                        <td className="px-4 py-1.5"><T text={e.edition_printed || '—'} /></td>
                        <td className="px-4 py-1.5 tabular-nums">{e.year_printed || '—'}{e.year_calendar ? ` (${e.year_calendar})` : ''}{e.year2 ? ` / ${e.year2}` : ''}</td>
                        <td className="px-4 py-1.5"><T text={e.publisher || '—'} /></td><td className="px-4 py-1.5"><T text={e.place || '—'} /></td>
                        <td className="px-4 py-1.5 tabular-nums">{e.n_members}</td></tr>))}
                    </tbody></table>
                </Card>)}
              <div className="grid lg:grid-cols-3 gap-4">
                <Card pad={false} className="lg:col-span-2" title={`${S.workPage.members} (${members.length})`}>
                  <ol className="divide-y divide-gray-100" data-testid="work-members">{members.map((m: any) => (
                    <li key={m.key} className="px-5 py-3 space-y-1">
                      <Crop src={cropOfAnchor(m.anchor)} maxH="max-h-24" rtl={m.script === 'ar'} />
                      <T as="p" text={m.printed} className="text-[15px] leading-7" />
                      <p className="text-xs text-gray-500"><Link href={hrefOf(m.key)!} className="hover:text-indigo-700 hover:underline">{m.stem}</Link> · {S.common.page} {m.page}
                        {m.article_title && <> · <span className="ar-inline">{m.article_title}</span></>}
                        {m.edition_pk && (() => { const e = (d.editions || []).find((x: any) => x.edition_pk === m.edition_pk); return e ? <> · <span className="text-gray-400">{S.workPage.edition}</span> <T text={[e.edition_printed, e.year_printed, e.publisher].filter(Boolean).join(' · ')} /></> : null; })()}</p>
                    </li>))}
                  </ol>
                </Card>
                <aside className="space-y-4">
                  <Card title={S.workPage.authors}>{d.authors.length === 0 ? <Empty>—</Empty> : <ul className="space-y-1 text-sm">{d.authors.map((a: any) => (
                    <li key={a.seq}><T text={a.printed} /> {a.died && <span className="text-xs text-gray-500" title={[a.died_hijri && `${a.died_hijri} AH`, a.died_greg && `${a.died_greg} CE`].filter(Boolean).join(' / ')}>({S.workPage.died} <T text={a.died} />)</span>} {a.person_id && <Link href={`/persons/${a.person_id}`} className="text-xs text-indigo-700 hover:underline font-mono">{a.person_id}</Link>}</li>))}</ul>}
                  </Card>
                  {(d.contributors || []).length > 0 && <Card title={S.workPage.contributors}><ul className="space-y-1 text-sm" data-testid="work-contributors">{d.contributors.map((x: any) => (
                    <li key={`${x.role}${x.seq}`}><Chip>{x.role}</Chip> <T text={x.printed} /> <span className="text-xs text-gray-400">{x.n_mentions}×</span></li>))}</ul></Card>}
                  <Card title={`${S.workPage.citing} (${d.citing.length})`}><ul className="space-y-1 text-sm">{d.citing.map((c: any) => (
                    <li key={c.stem}><Link href={`/articles/${enc(c.stem)}`} className="hover:text-indigo-700"><T text={c.title || c.stem} /></Link> <span className="text-xs text-gray-400">{c.year} · {c.n_mentions}×</span></li>))}</ul>
                  </Card>
                  {(d.links.length > 0 || d.relations.length > 0) && <Card title={S.workPage.links}>
                    <ul className="space-y-1 text-sm">{d.links.map((l: any, i: number) => (
                      <li key={i}><Chip tone={l.status === 'accepted' ? 'green' : 'amber'}>{l.status}</Chip> {l.stem ? <Link href={`/articles/${enc(l.stem)}`} className="text-indigo-700 hover:underline"><T text={l.title} /></Link> : <T text={l.title || l.target_value} />} <span className="text-xs text-gray-400">{l.target_pub_id} · {l.method} {l.score?.toFixed?.(2)}</span></li>))}
                      {d.relations.map((r: any, i: number) => <li key={`r${i}`}><Chip>{r.relation}</Chip> <T text={r.object_title || r.object_work_title} /></li>)}
                    </ul></Card>}
                  <Card title={<span className="flex items-center gap-1.5"><AlertTriangle className="w-4 h-4 text-amber-500" />{S.workPage.wrong}</span>}>
                    <WrongPanel title={S.workPage.wrong} ops={[['split', S.workPage.split], ['same', S.workPage.sameAs], ['not', S.workPage.notSameAs], ['move', S.workPage.move], ['type', S.workPage.setType]]}>
                      {(op, note) => (
                        <div className="space-y-2 text-sm">
                          {op === 'split' && <>
                            <GroupsSummary members={members} group={group} />
                            <Btn kind="primary" disabled={busy || booksOf(members, group).books.length < 2}
                              onClick={() => { const b = booksOf(members, group); decide('split_work', [subject], { groups: b.books.map((x, i) => ({ members: x, label: b.labels[i] || null })) }, note); }}>{S.work.saveSplit}</Btn>
                            <p className="text-xs text-gray-500">Pick a book for each citation in the list below.</p>
                          </>}
                          {(op === 'same' || op === 'not') && <>
                            <input value={other} onChange={e => setOther(e.target.value)} placeholder={S.workPage.otherId} className="w-full rounded-lg border-gray-300 text-sm font-mono" />
                            <Btn kind="primary" disabled={busy || !otherKey} onClick={() => decide(op === 'same' ? 'same_work' : 'not_same_work', [subject, otherKey], {}, note)}>{op === 'same' ? S.work.same : S.work.notSame}</Btn>
                          </>}
                          {op === 'move' && <>
                            <select value={member} onChange={e => setMember(e.target.value)} className="w-full rounded-lg border-gray-300 text-sm"><option value="">{S.workPage.member}…</option>
                              {members.map((m: any) => <option key={m.key} value={m.key}>{m.stem} p{m.page}: {(m.printed || '').slice(0, 60)}</option>)}</select>
                            <input value={other} onChange={e => setOther(e.target.value)} placeholder={S.workPage.target} className="w-full rounded-lg border-gray-300 text-sm font-mono" />
                            <Btn kind="primary" disabled={busy || !member || !otherKey} onClick={() => decide('move_member', [member, otherKey], {}, note)}>{S.workPage.move}</Btn>
                          </>}
                          {op === 'type' && <>
                            <select value={type} onChange={e => setType(e.target.value)} className="w-full rounded-lg border-gray-300 text-sm">{TYPES.map(t => <option key={t}>{t}</option>)}</select>
                            <Btn kind="primary" disabled={busy} onClick={() => decide('set_work_type', [subject], { type }, note)}>{S.common.save}</Btn>
                          </>}
                          {status}
                        </div>
                      )}
                    </WrongPanel>
                  </Card>
                </aside>
              </div>
              <Card pad={false} title={`${S.workPage.split}: pick a book for each citation`}>
                <SplitPicker members={members} group={group} setGroup={setGroup} />
              </Card>
            </>
          )}
          {tab === 'history' && <History subject={subject} />}
          {tab === 'notes' && <Notes subject={subject} />}
        </>
      )}
    </Layout>
  );
}
