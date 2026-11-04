import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import { Card, Chip, Empty, ErrorBox, T, Tabs, n } from '../../components/Bits';
import { Def, Metric, Ranked, SmallNote, WHOLE, YearBars, countryName, pct, pubHref } from '../../components/IndexBits';
import { useShowMode } from '../../lib/showmode';
import { enc } from '../../lib/api';
import { useApi } from '../../lib/me';

// A journal record (2026-10-23), Web of Science style: what is held and read, issues by year, authors, institutions,
// what it cites, who cites it, times cited per article and a journal h-index. Showcase: J0130 (gate 1).

export default function JournalPage() {
  const router = useRouter();
  const id = typeof router.query.id === 'string' ? router.query.id : null;
  const j = useApi<any>(id ? `/index/journals/${enc(id)}` : null);
  const [tab, setTab] = useState('articles');
  const [allArts, setAllArts] = useState(false);
  const [allAuthors, setAllAuthors] = useState(false);
  const showMode = useShowMode();
  const d = j.data;
  const c = d?.counts;
  return (
    <Layout>
      {j.err && <ErrorBox>{j.err}</ErrorBox>}
      {!d ? !j.err && <Empty>Loading…</Empty> : (
        <>
          <div>
            <p className="text-xs text-gray-500"><Link href="/journals" className="hover:text-indigo-700">Journals</Link>{!showMode && <> · <span className="font-mono">{d.journal_id}</span></>}
              {d.country && <> · {countryName(d.country)}</>}{!showMode && d.databases && <> · {d.databases}</>}{d.issns?.map((i: any) => <React.Fragment key={i.issn}> · ISSN {i.issn}</React.Fragment>)}
              {d.is_whole && <> · <Chip tone="indigo">{WHOLE[d.journal_id] || 'read whole'}</Chip></>}{!showMode && <> · read from {d.release_id || "the machine's reading"}</>}</p>
            <h1 className="text-2xl font-semibold text-gray-900 mt-1" data-testid="journal-title"><T text={d.title} /></h1>
            {d.title_en && <p className="text-gray-500">{d.title_en}</p>}
            {d.publishers?.length > 0 && <p className="text-sm text-gray-500">Published by <T text={d.publishers.map((p: any) => p.name).join('، ')} />{d.first_year && <> · catalogue years {d.first_year}–{d.last_year}</>}</p>}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3" data-testid="journal-numbers">
            <Metric label="Articles read" value={c.read} sub={`${n(c.pages)} pages · ${c.issues_read} issues`} define={`Articles of this journal the pipeline has read. Mandumah's platform holds ${c.in_platform} of its publications (the rest catalogued only, mostly ones cited by the articles read).`} />
            <Metric label="Authors" value={c.authors} sub={`${c.authors_2plus} with 2+ articles`} define="Distinct persons who signed the articles read (byline or catalogue record). " />
            <Metric label="Institutions" value={c.institutions} sub={`${c.institutions_2plus} in 2+ articles`} define={d.defs.institutions} />
            <Metric label="References" value={c.references} sub={`${(c.references / Math.max(1, c.read)).toFixed(1)} per article`} define={d.defs.references} />
            <Metric label="Held by Mandumah" value={pct(c.held_share)} sub={`${n(c.held)} references`} define={d.defs.held} />
            <Metric label="Times cited" value={c.times_cited} sub={`${c.cited_pubs} publications cited`} define={d.defs.times_cited_pub + ' Summed over the journal\'s publications.'} />
            <Metric label="Cited inside / outside" value={`${c.inside_refs} / ${c.outside_refs}`} sub={`${c.inside_citing} / ${c.outside_citing} citing articles`} define={`Inside: ${d.defs.inside} Outside: ${d.defs.outside}`} />
            <Metric label="Journal h-index" value={c.h_index} sub="within the articles read" define={d.defs.journal_h} />
          </div>
          {d.is_gate1 && <SmallNote>Read whole. Gate 1 read every article of this journal that the scanned archive holds for 2010–2025: {c.read} articles, all from 2017–2019 and 2023–2025.
            Citations to the journal can come only from the {n(c.platform_read)} articles read so far, so times cited and the h-index are small by construction; they grow with every journal read.</SmallNote>}
          {d.is_whole && !d.is_gate1 && <SmallNote>Read whole. Gate 2's pilot read every research article of this journal for 2010–2025: {n(c.read)} articles,
            {' '}{n(c.read - (c.word || 0))} from the scans and {n(c.word || 0)} from the publisher's Word files (no scan exists for those).
            Citations to the journal can come only from the {n(c.platform_read)} articles read so far, so times cited and the h-index grow with every journal read.</SmallNote>}
          <Bridges d={d} />

          <div className="grid lg:grid-cols-2 gap-4">
            <Card title={<Def text="Articles read, by the year shown on the article.">Articles read per year</Def>}>
              <YearBars data={d.chart.filter((r: any) => r.read).map((r: any) => ({ year: r.year, value: r.read }))} label="Articles read, by year of publication" />
            </Card>
            <Card title={<Def text="Times cited of the journal's publications (read or catalogued), by the cited publication's year: how far back the journal's own record is used.">Citations received, by year of the cited article</Def>}>
              <YearBars data={d.chart.filter((r: any) => r.cited).map((r: any) => ({ year: r.year, value: r.cited }))} label="Times cited, by year of the cited publication" color="#0e7490" />
            </Card>
          </div>

          <div className="grid lg:grid-cols-3 gap-4">
            <Card title={<Def text="Persons who signed two or more of the articles read.">Authors with several articles</Def>}>
              <Ranked rows={(allAuthors ? d.authors_2plus : d.authors_2plus.slice(0, 10)).map((p: any) => ({ key: p.person_id, href: `/persons/${p.person_id}`, label: p.name, value: p.articles }))} />
              {!allAuthors && d.authors_2plus.length > 10 && <button onClick={() => setAllAuthors(true)} className="text-sm text-indigo-700 hover:underline mt-2">Show all {d.authors_2plus.length}</button>}
            </Card>
            <Card title={<Def text={d.defs.institutions + ' Counted by articles read.'}>Institutions</Def>}>
              <Ranked rows={d.institutions.slice(0, 15).map((i: any) => ({ key: i.inst_id, href: `/institutions/${i.inst_id}`, label: i.name, sub: countryName(i.country), value: i.articles }))} />
            </Card>
            <Card title={<Def text="Countries of the institutions above (each institution once). Some institutions have no country recorded yet.">Countries</Def>}>
              <Ranked rows={[...d.countries.filter(([cc]: [string, number]) => cc !== 'not recorded'), ...d.countries.filter(([cc]: [string, number]) => cc === 'not recorded')]
                .map(([cc, k]: [string, number]) => ({ key: cc, label: cc === 'not recorded' ? 'Country not recorded yet' : countryName(cc), value: k }))} />
            </Card>
          </div>
          <div className="flex justify-between items-center flex-wrap gap-2">
            <Tabs value={tab} onChange={setTab} tabs={[['articles', `Articles (${c.read})`], ['issues', `Issues by year (${c.issues})`], ['cited', `Times cited (${d.received.length})`], ['refs', 'What it cites']]} />
          </div>

          {tab === 'articles' && (
            <Card pad={false} className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="journal-articles">
                <thead className="bg-gray-50 text-xs text-gray-500"><tr>
                  <th className="px-3 py-2 text-left font-medium w-16">Year</th><th className="px-3 py-2 text-right font-medium">Title</th>
                  <th className="px-3 py-2 text-right font-medium">Authors</th><th className="px-3 py-2 text-left font-medium">Type</th>
                  <th className="px-3 py-2 text-right font-medium"><Def text={d.defs.references}>Refs</Def></th>
                  <th className="px-3 py-2 text-right font-medium"><Def text={d.defs.times_cited_pub}>Cited</Def></th></tr></thead>
                <tbody>{(allArts ? d.articles : d.articles.slice(0, 20)).map((a: any) => (
                  <tr key={a.pub_id} className="border-t border-gray-100 hover:bg-indigo-50/40">
                    <td className="px-3 py-2 tabular-nums text-gray-500">{a.year}</td>
                    <td className="px-3 py-2 text-right"><Link href={pubHref(a) || '#'} className="text-gray-900 hover:text-indigo-700"><T text={a.title} /></Link></td>
                    <td className="px-3 py-2 text-right text-gray-600">{a.authors.map((p: any, i: number) => <span key={p.person_id}>{i > 0 && '، '}<Link href={`/persons/${p.person_id}`} className="hover:text-indigo-700"><T text={p.name} /></Link></span>)}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">{a.doc_type}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{a.references}</td>
                    <td className="px-3 py-2 text-right tabular-nums font-medium">{a.times_cited || ''}</td>
                  </tr>))}</tbody>
              </table>
              {!allArts && d.articles.length > 20 && <div className="p-3 text-center"><button onClick={() => setAllArts(true)} className="text-sm text-indigo-700 hover:underline">Show all {d.articles.length} articles</button></div>}
            </Card>
          )}
          {tab === 'issues' && (
            <Card title={<Def text="Every issue of the journal the platform knows of, with how many of its publications the platform holds and how many are read. Years before 2017 appear because the articles read cite them.">Issues by year</Def>}>
              <div className="space-y-2" data-testid="journal-issues">{d.years.map((y: any) => (
                <div key={y.year ?? 'none'} className="flex gap-3 items-start">
                  <span className="w-12 text-sm tabular-nums text-gray-500 pt-1">{y.year ?? '—'}</span>
                  <div className="flex flex-wrap gap-1.5">{y.issues.map((i: any) => (
                    <span key={i.issue_id} title={`${i.read} read · ${i.in_platform} in the platform`}
                      className={`text-xs rounded-lg border px-2 py-1 ar-inline ${i.read ? 'bg-indigo-50 border-indigo-200 text-indigo-800' : 'bg-gray-50 border-gray-200 text-gray-500'}`}>
                      {i.label} {i.read ? <b className="tabular-nums">· {i.read} read</b> : <span>· cited only</span>}</span>))}</div>
                </div>))}</div>
            </Card>
          )}
          {tab === 'cited' && (
            <Card pad={false} className="overflow-x-auto" title={<Def text={d.defs.times_cited_pub}>The journal's publications cited by the articles read</Def>}>
              {d.received.length === 0 ? <div className="px-5 pb-4"><Empty>None yet.</Empty></div> : (
                <table className="w-full text-sm" data-testid="journal-received">
                  <thead className="bg-gray-50 text-xs text-gray-500"><tr>
                    <th className="px-3 py-2 text-left font-medium w-16">Year</th><th className="px-3 py-2 text-right font-medium">Publication</th>
                    <th className="px-3 py-2 text-left font-medium">Held as</th>
                    <th className="px-3 py-2 text-right font-medium"><Def text={d.defs.inside}>Inside</Def></th>
                    <th className="px-3 py-2 text-right font-medium"><Def text={d.defs.outside}>Outside</Def></th>
                    <th className="px-3 py-2 text-right font-medium">Times cited</th></tr></thead>
                  <tbody>{d.received.map((a: any) => (
                    <tr key={a.pub_id} className="border-t border-gray-100">
                      <td className="px-3 py-2 tabular-nums text-gray-500">{a.year}</td>
                      <td className="px-3 py-2 text-right">{a.stem ? <Link href={pubHref(a)!} className="text-gray-900 hover:text-indigo-700"><T text={a.title} /></Link> : <T text={a.title} />}</td>
                      <td className="px-3 py-2">{a.read ? <Chip tone="indigo">read</Chip> : <Chip>catalogue</Chip>}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{a.inside}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{a.outside}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-semibold">{a.times_cited}</td>
                    </tr>))}</tbody>
                </table>)}
            </Card>
          )}
          {tab === 'refs' && (
            <div className="grid lg:grid-cols-2 gap-4">
              <Card title={<Def text="Cited works, by the number of this journal's articles citing them.">Most cited by this journal</Def>}>
                <Ranked rows={d.most_cited_works.map((w: any) => ({ key: w.id, href: `/works/${w.id}`, label: w.title, sub: [(w.authors || []).join('، '), w.held_pub_id ? 'held by Mandumah' : ''].filter(Boolean).join(' · '), value: w.times_cited }))} />
              </Card>
              <Card title={<Def text="References from this journal's articles landing on publications of each journal, through accepted links.">Journals it cites</Def>}>
                <Ranked rows={d.cites_journals.map((x: any) => ({ key: x.journal_id, href: `/journals/${x.journal_id}`, label: x.title || x.journal_id, sub: x.self ? 'self-citation' : undefined, value: x.references }))} />
                <h3 className="text-sm font-medium text-gray-700 mt-4 mb-1"><Def text="References from articles of each journal landing on this journal's publications.">Journals citing it</Def></h3>
                <Ranked rows={d.cited_by_journals.map((x: any) => ({ key: x.journal_id, href: `/journals/${x.journal_id}`, label: x.title || x.journal_id, sub: x.self ? 'self-citation' : undefined, value: x.references }))} />
              </Card>
            </div>
          )}

        </>
      )}
    </Layout>
  );
}

// Bridges with other journals (experiment 73, N1): the other journal read whole first (references each way), then
// the journals this one cites most and that cite it most, self-citation left out.
const WHOLE_IDS = Object.keys(WHOLE);
function Bridges({ d }: { d: any }) {
  const out = (d.cites_journals || []).filter((x: any) => !x.self);
  const inn = (d.cited_by_journals || []).filter((x: any) => !x.self);
  const others = WHOLE_IDS.filter(id => id !== d.journal_id);
  const ref = (rows: any[], id: string) => rows.find((x: any) => x.journal_id === id)?.references || 0;
  if (!out.length && !inn.length) return null;
  return (
    <Card title={<Def text="References between this journal's publications and other journals' publications, through accepted links (each reference once). Self-citation is left out.">Bridges with other journals</Def>}>
      {others.map(id => {
        const t = out.find((x: any) => x.journal_id === id)?.title || inn.find((x: any) => x.journal_id === id)?.title;
        const a = ref(out, id), b = ref(inn, id);
        if (!a && !b) return null;
        return (
          <div key={id} className="rounded-xl border border-teal-200 bg-teal-50/60 px-4 py-3 mb-3 flex flex-wrap items-center gap-x-6 gap-y-1" data-testid="bridge-whole">
            <span className="text-sm text-gray-700">With the other journal read whole, <Link href={`/journals/${id}`} className="font-medium text-gray-900 hover:text-indigo-700"><T text={t || id} /></Link>:</span>
            <span className="text-sm"><b className="text-lg tabular-nums text-indigo-700">{a}</b> references to it</span>
            <span className="text-sm"><b className="text-lg tabular-nums text-teal-700">{b}</b> references from it</span>
          </div>
        );
      })}
      <div className="grid md:grid-cols-2 gap-4">
        <div><h3 className="text-sm font-medium text-gray-700 mb-1">Journals it cites</h3>
          <Ranked rows={out.slice(0, 6).map((x: any) => ({ key: x.journal_id, href: `/journals/${x.journal_id}`, label: x.title || x.journal_id, sub: WHOLE[x.journal_id], value: x.references }))} /></div>
        <div><h3 className="text-sm font-medium text-gray-700 mb-1">Journals citing it</h3>
          <Ranked rows={inn.slice(0, 6).map((x: any) => ({ key: x.journal_id, href: `/journals/${x.journal_id}`, label: x.title || x.journal_id, sub: WHOLE[x.journal_id], value: x.references }))} empty="None of the articles read yet." /></div>
      </div>
    </Card>
  );
}
