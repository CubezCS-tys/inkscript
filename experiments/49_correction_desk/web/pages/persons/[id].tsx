import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { AlertTriangle } from 'lucide-react';
import Layout from '../../components/Layout';
import { Btn, Card, Chip, Crop, Empty, ErrorBox, T, Tabs, n } from '../../components/Bits';
import { History, Notes, Standing } from '../../components/History';
import { PersonRecord } from '../../components/PersonRecord';
import { WrongPanel, useDecide } from '../../components/Decide';
import { cropOfAnchor, enc } from '../../lib/api';
import { useApi } from '../../lib/me';
import { useShowMode } from '../../lib/showmode';
import { S, f } from '../../lib/strings';

export default function PersonPage() {
  const router = useRouter();
  const id = typeof router.query.id === 'string' ? router.query.id : null;
  const [tab, setTab] = useState('current');
  const p = useApi<any>(id ? `/persons/${enc(id)}` : null);
  const showMode = useShowMode();
  const d = p.data;
  const subject = d?.subject || (id ? `person:${id}` : '');
  const { decide, busy, status } = useDecide(p.reload);
  const [other, setOther] = useState('');
  const [byline, setByline] = useState('');
  const otherKey = other.trim() ? `person:${other.trim().replace(/^person:/, '').toUpperCase()}` : '';
  const bylines = (d?.works || []).flatMap((w: any) => w.bylines.map((b: any) => ({ ...b, stem: w.stem })));
  return (
    <Layout>
      {p.err && <ErrorBox>{p.err}</ErrorBox>}
      {!d ? !p.err && <Empty>{S.common.loading}</Empty> : (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs text-gray-500">{S.person.title}{!showMode && <> · <span className="font-mono">{d.id}</span> · {d.status} · {d.source}
                {d.resolved_from && <> · <Chip tone="amber">{d.resolved_from} → {d.id}</Chip></>} · {S.common.readFrom} {d.release_id || S.common.reading}</>}</p>
              <h1 className="text-2xl font-semibold text-gray-900 mt-1" data-testid="person-name"><T text={d.name_ar || d.name_lat} /> {d.name_ar && d.name_lat && <span className="text-gray-500 font-normal text-lg">{d.name_lat}</span>}</h1>
              <p className="text-sm text-gray-500">{f(S.person.citationsReceived, { pubs: n(d.citations_received.citing_pubs), m: n(d.citations_received.mentions), w: n(d.citations_received.works) })}
                {!showMode && d.merged_from?.length > 0 && ` · ${f(S.person.merged, { ids: d.merged_from.join(', ') })}`}</p>
            </div>
            {!showMode && <Tabs value={tab} onChange={setTab} tabs={[['current', S.common.current], ['history', S.common.history], ['notes', S.common.notes]]} />}
          </div>
          {tab === 'current' && (
            <>
              <Standing desk={d.desk} subject={subject} onDone={p.reload} />
              <PersonRecord id={d.id} />
              <div className="grid lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2 space-y-4">
                  <Card pad={false} title={`${S.person.works} (${d.works.length})`}>
                    <ul className="divide-y divide-gray-100">{d.works.map((w: any) => (
                      <li key={w.authorship_pk} className="px-5 py-3 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          {w.stem ? <Link href={`/articles/${enc(w.stem)}`} className="text-indigo-700 hover:underline"><T text={w.title_shown || w.pub_id} /></Link> : <T text={w.title_shown || w.pub_id} />}
                          <Chip>{w.role_name || w.role_code}</Chip><Chip tone={w.method === 'provisional' ? 'amber' : 'gray'}>{w.method}</Chip>
                        </div>
                        <p className="text-xs text-gray-500">{w.year_shown || ''} · <span className="ar-inline">{w.journal || ''}</span> · {w.pub_id}</p>
                        {w.bylines.map((b: any) => <div key={b.key} className="space-y-0.5"><Crop src={cropOfAnchor(b.anchor)} maxH="max-h-16" rtl={b.script !== 'Latn' && /[\u0600-\u06FF]/.test(b.printed || '')} /><T as="p" text={b.printed} className="text-sm text-gray-700" /></div>)}
                        {w.affiliations.filter((a: any) => a.printed).map((a: any, i: number) => <p key={i} className="text-xs text-gray-500"><T text={a.printed} />{a.inst_name && <> → <span className="ar-inline">{a.inst_name}</span></>}</p>)}
                      </li>))}
                    </ul>
                  </Card>
                  <Card title={`${S.person.cited} (${d.cited_works.length})`}>
                    {d.cited_works.length === 0 ? <Empty>—</Empty> : <ul className="space-y-1 text-sm">{d.cited_works.slice(0, 50).map((c: any) => (
                      <li key={c.id}><Link href={`/works/${c.id}`} className="hover:text-indigo-700"><T text={c.title} /></Link> <span className="text-xs text-gray-400">{f(S.article.timesCited, { n: c.n_citing_pubs })}</span></li>))}</ul>}
                  </Card>
                </div>
                <aside className="space-y-4">
                  <Card title={S.person.names}><ul className="space-y-1 text-sm">{d.names.map((x: any, i: number) => (
                    <li key={i} className="flex justify-between gap-2"><T text={x.full_form} /><span className="text-xs text-gray-400 shrink-0">{x.form_type}</span></li>))}</ul>
                    {d.authorities.length > 0 && <p className="text-xs text-gray-500 mt-2">{S.person.authorities}: {d.authorities.map((a: any) => `${a.authority_id} (${a.n_records ?? '?'} records)`).join(', ')}</p>}
                  </Card>
                  <Card title={S.person.coauthors}>{d.coauthors.length === 0 ? <Empty>—</Empty> : <ul className="space-y-1 text-sm">{d.coauthors.map((c: any) => (
                    <li key={c.person_id}><Link href={`/persons/${c.person_id}`} className="hover:text-indigo-700"><T text={c.name} /></Link> <span className="text-xs text-gray-400">{c.n}</span></li>))}</ul>}</Card>
                  <Card title={S.person.institutions}>{d.institutions.length === 0 ? <Empty>—</Empty> : <ul className="space-y-1 text-sm">{d.institutions.map((i: any) => (
                    <li key={i.inst_id}><Link href={`/institutions/${i.inst_id}`} className="hover:text-indigo-700"><T text={i.name} /></Link> <span className="text-xs text-gray-400 font-mono">{i.inst_id}</span></li>))}</ul>}</Card>
                  <Card title={<span className="flex items-center gap-1.5"><AlertTriangle className="w-4 h-4 text-amber-500" />{S.person.wrong}</span>}>
                    <WrongPanel title={S.person.wrong} ops={[['same', S.person.sameAs], ['not', S.person.notSameAs], ['unlink', S.person.unlink]]}>
                      {(op, note) => (
                        <div className="space-y-2 text-sm">
                          {(op === 'same' || op === 'not') && <>
                            <input value={other} onChange={e => setOther(e.target.value)} placeholder={S.person.otherId} className="w-full rounded-lg border-gray-300 text-sm font-mono" />
                            <Btn kind="primary" disabled={busy || !otherKey} onClick={() => decide(op === 'same' ? 'same_person' : 'not_same_person', [subject, otherKey], {}, note)}>{op === 'same' ? S.work.samePerson : 'Not the same person'}</Btn>
                          </>}
                          {op === 'unlink' && <>
                            <select value={byline} onChange={e => setByline(e.target.value)} className="w-full rounded-lg border-gray-300 text-sm"><option value="">{S.person.bylineToUnlink}…</option>
                              {bylines.map((b: any) => <option key={b.key} value={b.key}>{b.stem}: {b.printed}</option>)}</select>
                            <Btn kind="primary" disabled={busy || !byline} onClick={() => decide('unlink_byline', [byline], {}, note)}>{S.person.unlink}</Btn>
                          </>}
                          {status}
                        </div>
                      )}
                    </WrongPanel>
                  </Card>
                </aside>
              </div>
            </>
          )}
          {tab === 'history' && <History subject={subject} />}
          {tab === 'notes' && <Notes subject={subject} />}
        </>
      )}
    </Layout>
  );
}
