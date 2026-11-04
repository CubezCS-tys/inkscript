import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { BookOpen, Building2, Compass, Library, ListChecks, Search, Trophy } from 'lucide-react';
import Layout from '../components/Layout';
import { Card, Empty, ErrorBox, T, n } from '../components/Bits';
import { Def, Metric, Ranked, SmallNote, WHOLE, countryName, pct } from '../components/IndexBits';
import { Gate1Card, Gate2Card } from '../components/GateCards';
import { useShowMode } from '../lib/showmode';
import { useApi } from '../lib/me';

// The Index overview (2026-10-23): what the citation index holds today, each number defined on hover, gate 1
// against random articles, and the ways in. The corrector's Overview stays at /.

const show = (v: any, fmt: string) => {
  if (v == null) return '—';
  if (fmt === 'pct') return pct(v);
  if (typeof v === 'number') return n(v >= 100 ? Math.round(v) : Math.round(v * 100) / 100);
  if (v.citing != null) return <>{n(v.n)} <span className="text-xs text-gray-500 font-normal">({v.citing} citing → {v.cited} cited)</span></>;
  if (v.of != null) return <>{n(v.n)} <span className="text-xs text-gray-500 font-normal">of {n(v.of)}</span></>;
  return String(v);
};
const num = (v: any) => (v == null ? null : typeof v === 'number' ? v : v.n);

function Ratio({ j, r }: { j: any; r: any }) {
  const a = num(j), b = num(r);
  if (a == null || b == null) return null;
  if (b === 0) return a > 0 ? <span className="text-xs text-indigo-700 font-medium">vs 0</span> : null;
  const x = a / b;
  return <span className={`text-xs font-medium ${x >= 1.5 ? 'text-indigo-700' : 'text-gray-500'}`}>{x >= 10 ? Math.round(x) : x.toFixed(1)}×</span>;
}

export default function IndexHome() {
  const o = useApi<any>('/index/overview');
  const g = useApi<any>('/index/gate1');
  const hl = useApi<any>('/headlines');
  const showMode = useShowMode();
  const h = hl.data;
  const { push } = useRouter();
  const [q, setQ] = useState('');
  const d = o.data;
  const go = (e: React.FormEvent) => { e.preventDefault(); if (q.trim()) push(`/search?q=${encodeURIComponent(q.trim())}`); };
  const entries: [string, string, string, any][] = [
    ['/search', 'Search', 'Articles, people and cited works, Arabic folded (hamza, alef and ya forms).', Search],
    ['/explore', 'Explorer', 'Walk the bridges: who cites whom, shared works, people and places.', Compass],
    ['/journals', 'Journals', 'Journal records: issues, authors, institutions, citations, h-index.', BookOpen],
    ['/most-cited', 'Most cited', 'Cited works, and Mandumah publications cited by the articles read.', Trophy],
    ['/institutions', 'Institutions', 'Universities and ministries by articles, authors and citations.', Building2],
    ['/', 'Correction desk', 'Where correctors confirm or fix every bridge; each decision is kept and owned.', ListChecks],
  ];
  return (
    <Layout>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-indigo-700 font-semibold flex items-center gap-1.5"><Library className="w-4 h-4" aria-hidden /> Arabic citation index · pilot</p>
          <h1 className="text-2xl font-semibold text-gray-900 mt-1">The index so far</h1>
          <p className="text-sm text-gray-500 max-w-3xl">Built from Mandumah's scanned archive: every word read from the scan, every reference parsed and
            grouped into cited works, every author, institution and journal tied to an id.
            {d && <> So far {n(d.n_articles)} articles: two education journals read whole{h?.journals_read_whole?.length === 2 ? <> ({n(h.journals_read_whole[0].articles)} and {n(h.journals_read_whole[1].articles)} articles)</> : null} and about 600 drawn at random from the whole archive.</>}
            {!showMode && <>{' '}Read from {d?.release_id ? `release ${d.release_id}` : "the machine's reading"}.</>}</p>
        </div>
        <form onSubmit={go} role="search" className="flex items-center gap-2">
          <label className="relative">
            <span className="sr-only">Search the index</span>
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-3" aria-hidden />
            <input value={q} onChange={e => setQ(e.target.value)} dir="auto" placeholder="Search a title, author or cited work…"
              className="pl-9 pr-3 py-2 w-72 md:w-96 rounded-lg border-gray-300 text-sm" data-testid="index-search" />
          </label>
          <button className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700">Search</button>
        </form>
      </div>
      {o.err && <ErrorBox>{o.err}</ErrorBox>}
      {!d ? !o.err && <Empty>Loading…</Empty> : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="index-numbers">
          {d.numbers.map((m: any) => <Metric key={m.key} label={m.label} value={m.value} unit={m.unit} sub={m.sub} define={m.define} href={m.href} testid={`num-${m.key}`} />)}
        </div>
      )}

      {hl.err && <ErrorBox>{hl.err}</ErrorBox>}
      <Gate1Card h={h}>
        {!showMode && (
          <details className="mt-2">
            <summary className="text-xs text-indigo-700 cursor-pointer">All the measures, as measured now with experiment 52's code</summary>
            {g.err && <ErrorBox>{g.err}</ErrorBox>}
            {!g.data ? !g.err && <Empty>Measuring (a few seconds the first time)…</Empty> : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" data-testid="gate1-table">
                    <thead className="bg-gray-50 text-xs text-gray-500"><tr>
                      <th className="px-3 py-2 text-left font-medium">Bridge</th>
                      <th className="px-3 py-2 text-right font-medium">The journal ({g.data.n_journal})</th>
                      <th className="px-3 py-2 text-right font-medium">Random {g.data.n_journal} (mean of {g.data.draws})</th>
                      <th className="px-3 py-2 text-right font-medium">vs random {g.data.n_journal}</th>
                      <th className="px-3 py-2 text-right font-medium">Random {g.data.n_random}</th>
                    </tr></thead>
                    <tbody>{g.data.rows.map((r: any) => (
                      <tr key={r.key} className="border-t border-gray-100">
                        <td className="px-3 py-2 text-gray-800"><Def text={r.define}>{r.label}</Def></td>
                        <td className="px-3 py-2 text-right tabular-nums font-semibold text-gray-900">{show(r.journal, r.fmt)}</td>
                        <td className="px-3 py-2 text-right tabular-nums text-gray-600">{show(r.random_same_size, r.fmt)}</td>
                        <td className="px-3 py-2 text-right">{r.random_same_size != null && <Ratio j={r.journal} r={r.random_same_size} />}</td>
                        <td className="px-3 py-2 text-right tabular-nums text-gray-600">{show(r.random, r.fmt)}</td>
                      </tr>))}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-gray-500 mt-2">Not yet dense: repeat co-authorship, and citations between the journal's read years (the archive's gaps cut out the years in between).</p>
              </>
            )}
          </details>
        )}
      </Gate1Card>
      <Gate2Card h={h} />

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
        {entries.map(([href, title, sub, Icon]) => (
          <Link key={href} href={href} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 hover:border-indigo-300 flex gap-3">
            <Icon className="w-5 h-5 text-indigo-600 shrink-0 mt-0.5" aria-hidden />
            <span><span className="font-medium text-gray-900">{title}</span><span className="block text-sm text-gray-500">{sub}</span></span>
          </Link>
        ))}
      </div>

      {d && (
        <div className="grid lg:grid-cols-3 gap-4">
          <Card title={<Def text={d.defs.times_cited_work}>Most cited works</Def>} right={<Link href="/most-cited" className="text-xs text-indigo-700 hover:underline">All →</Link>}>
            <Ranked rows={d.top_works.map((w: any) => ({ key: w.id, href: `/works/${w.id}`, label: w.title, sub: (w.authors || []).join('، ') || w.pub_type, value: w.times_cited }))} />
          </Card>
          <Card title={<Def text={d.defs.institutions + ' Counted by articles read.'}>Top institutions</Def>} right={<Link href="/institutions" className="text-xs text-indigo-700 hover:underline">All →</Link>}>
            <Ranked rows={d.top_institutions.map((i: any) => ({ key: i.inst_id, href: `/institutions/${i.inst_id}`, label: i.name, sub: countryName(i.country), value: i.articles }))} />
          </Card>
          <Card title={<Def text={d.defs.journals + ' Counted by articles read.'}>Journals</Def>} right={<Link href="/journals" className="text-xs text-indigo-700 hover:underline">All →</Link>}>
            <Ranked rows={d.top_journals.map((j: any) => ({ key: j.journal_id, href: `/journals/${j.journal_id}`, label: j.title, sub: WHOLE[j.journal_id] || 'random sample', value: j.articles }))} />
          </Card>
        </div>
      )}
      <SmallNote>Every count here is computed from the release on each visit and is only as large as what has been read: {d ? n(d.n_articles) : '…'} articles
        of Mandumah's ~1 million. "Times cited" means cited by the articles read so far, not by the whole archive.</SmallNote>
    </Layout>
  );
}
