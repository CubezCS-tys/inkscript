import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import { Card, Chip, Empty, ErrorBox, T, n } from '../../components/Bits';
import { Def, Metric, Ranked, YearBars, countryName, pubHref } from '../../components/IndexBits';
import { useShowMode } from '../../lib/showmode';
import { enc } from '../../lib/api';
import { useApi } from '../../lib/me';

// An institution record (2026-10-23): its names, units, articles, authors, journals, times cited, h-index.
export default function InstitutionPage() {
  const router = useRouter();
  const id = typeof router.query.id === 'string' ? router.query.id : null;
  const r = useApi<any>(id ? `/index/institutions/${enc(id)}` : null);
  const d = r.data;
  const showMode = useShowMode();
  const c = d?.counts;
  return (
    <Layout>
      {r.err && <ErrorBox>{r.err}</ErrorBox>}
      {!d ? !r.err && <Empty>Loading…</Empty> : (
        <>
          <div>
            <p className="text-xs text-gray-500"><Link href="/institutions" className="hover:text-indigo-700">Institutions</Link>{!showMode && <> · <span className="font-mono">{d.inst_id}</span></>} · {d.kind}{d.country && <> · {countryName(d.country)}</>}{d.city && <> · {d.city}</>}{!showMode && <> · read from {d.release_id || "the machine's reading"}</>}</p>
            <h1 className="text-2xl font-semibold text-gray-900 mt-1" data-testid="inst-name"><T text={d.name} /></h1>
            {d.parent && <p className="text-sm text-gray-500">Part of <Link href={`/institutions/${d.parent.inst_id}`} className="text-indigo-700 hover:underline"><T text={d.parent.name} /></Link></p>}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <Metric label="Articles read" value={c.articles} define={d.defs.inst_articles} />
            <Metric label="Authors" value={c.authors} define="Distinct persons whose printed affiliation on an article read was matched to this institution." />
            <Metric label="Journals" value={c.journals} define="Journals of those articles." />
            <Metric label="References made" value={c.references} define={d.defs.references} />
            <Metric label="Times cited" value={c.times_cited} sub={`${c.cited_articles} articles cited`} define={d.defs.times_cited_pub + ' Summed over its articles.'} />
            <Metric label="h-index" value={c.h_index} sub="within the articles read" define={d.defs.h_index} />
          </div>
          <div className="grid lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 space-y-4">
              <Card pad={false} title={`Articles (${d.articles.length})`}>
                <ul className="divide-y divide-gray-100">{d.articles.map((a: any) => (
                  <li key={a.pub_id} className="px-5 py-2.5">
                    <div className="flex items-start gap-2 justify-between">
                      <Link href={pubHref(a) || '#'} className="text-gray-900 hover:text-indigo-700 flex-1"><T text={a.title} /></Link>
                      {a.times_cited > 0 && <Chip tone="indigo">cited {a.times_cited}</Chip>}
                    </div>
                    <p className="text-xs text-gray-500">{a.year} · <Link href={`/journals/${a.journal_id}`} className="hover:text-indigo-700"><span className="ar-inline">{a.journal}</span></Link> · {a.references} references ·{' '}
                      {a.authors.map((p: any, i: number) => <span key={p.person_id}>{i > 0 && '، '}<Link href={`/persons/${p.person_id}`} className="hover:text-indigo-700"><span className="ar-inline">{p.name}</span></Link></span>)}</p>
                  </li>))}</ul>
              </Card>
              {d.years.length > 0 && <Card title="Articles per year"><YearBars data={d.years.map((y: any) => ({ year: y.year, value: y.articles }))} label="Articles read, by year" /></Card>}
            </div>
            <aside className="space-y-4">
              <Card title="Authors"><Ranked rows={d.authors.map((p: any) => ({ key: p.person_id, href: `/persons/${p.person_id}`, label: p.name, value: p.articles }))} /></Card>
              <Card title={<Def text="Faculties and departments printed on the same affiliations.">Units seen</Def>}>
                <Ranked rows={d.units.map((u: any) => ({ key: u.inst_id, href: `/institutions/${u.inst_id}`, label: u.name, sub: u.kind, value: u.articles }))} /></Card>
              <Card title="Journals"><Ranked rows={d.journals.map((j: any) => ({ key: j.journal_id, href: `/journals/${j.journal_id}`, label: j.title || j.journal_id, value: j.articles }))} /></Card>
              <Card title={<Def text="Every way this institution's name was printed or catalogued, with how often it was seen.">Names</Def>}>
                <ul className="space-y-1 text-sm">{d.names.map((x: any, i: number) => <li key={i} className="flex justify-between gap-2"><T text={x.name} /><span className="text-xs text-gray-400 shrink-0">{x.type} · {x.n_seen ?? ''}</span></li>)}</ul>
                {d.printed.length > 0 && <><h3 className="text-xs font-medium text-gray-500 mt-3 mb-1">As printed in affiliations</h3>
                  <ul className="space-y-1 text-xs text-gray-600">{d.printed.map((p: any, i: number) => <li key={i}><T text={p.text} /> <span className="text-gray-400">×{p.n}</span></li>)}</ul></>}
              </Card>
              {d.children.length > 0 && <Card title="Sub-units in the authority"><ul className="space-y-1 text-sm">{d.children.map((u: any) => <li key={u.inst_id}><Link href={`/institutions/${u.inst_id}`} className="hover:text-indigo-700"><T text={u.name} /></Link> <span className="text-xs text-gray-400">{u.kind}</span></li>)}</ul></Card>}
            </aside>
          </div>
        </>
      )}
    </Layout>
  );
}
