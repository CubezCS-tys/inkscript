import React, { useState } from 'react';
import Link from 'next/link';
import { Card, Chip, Empty, T, n } from './Bits';
import { Def, Metric, pubHref } from './IndexBits';
import { enc } from '../lib/api';
import { useApi } from '../lib/me';

// The author record on the Person page (2026-10-23), Web of Science style: publications, times cited with and
// without self-citations, citing articles, h-index, years and journals, and the works with their counts.
export const PersonRecord: React.FC<{ id: string }> = ({ id }) => {
  const r = useApi<any>(`/index/persons/${enc(id)}`);
  const [all, setAll] = useState(false);
  const d = r.data;
  if (r.err) return null;
  if (!d) return <Empty>Loading the author record…</Empty>;
  const c = d.counts;
  const items = all ? d.items : d.items.slice(0, 12);
  return (
    <Card title={<Def text={d.defs.person_items}>Author record</Def>} right={<span className="text-xs text-gray-500">cited by the {''}articles read so far · {c.first_year ? `${c.first_year}–${c.last_year}` : ''}</span>}>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4" data-testid="person-record">
        <Metric label="Publications" value={c.publications_signed} sub={`${c.articles_read} read · ${c.catalogued_only} catalogue`} define="Publications this person signed: the articles read (bylines matched to the person) and catalogue records under their authority id." />
        <Metric label="Citing articles" value={c.citing_articles} sub={`${n(c.citing_articles_no_self)} without self-citations`} define={d.defs.citing_articles} />
        <Metric label="Sum of times cited" value={c.times_cited} sub={`${n(c.times_cited_no_self)} without self-citations`} define={`${d.defs.person_tc} ${d.defs.self_citations}`} testid="person-tc" />
        <Metric label="h-index" value={c.h_index} sub={`${c.h_index_no_self} without self-citations`} define={d.defs.h_index} testid="person-h" />
        <Metric label="Works cited" value={c.works_cited} define="Works of this person cited at least once by the articles read." />
        <Metric label="Journals" value={d.journals.length} sub={d.journals[0] ? <span className="ar-inline">{d.journals[0].title}</span> : undefined} define="Journals of the publications they signed." />
      </div>
      {d.items.length === 0 ? <Empty>No citations to this person's works among the articles read yet.</Empty> : (
        <table className="w-full text-sm">
          <thead className="text-xs text-gray-500 border-b border-gray-100"><tr>
            <th className="py-1.5 text-right font-medium">Work</th><th className="py-1.5 px-2 text-left font-medium">Kind</th>
            <th className="py-1.5 px-2 text-right font-medium">Year</th>
            <th className="py-1.5 px-2 text-right font-medium">Times cited</th><th className="py-1.5 text-right font-medium">of them self</th></tr></thead>
          <tbody>{items.map((it: any) => (
            <tr key={(it.pub_id || '') + (it.id || '')} className="border-t border-gray-50">
              <td className="py-1.5 text-right">{it.kind === 'cited work'
                ? <Link href={`/works/${it.id}`} className="hover:text-indigo-700"><T text={it.title} /></Link>
                : it.stem ? <Link href={pubHref(it)!} className="hover:text-indigo-700"><T text={it.title} /></Link> : <T text={it.title} />}
                {it.journal && <span className="block text-xs text-gray-400 ar-inline">{it.journal}</span>}</td>
              <td className="py-1.5 px-2">{it.kind === 'cited work' ? <Chip>cited work</Chip> : it.read ? <Chip tone="indigo">article read</Chip> : <Chip tone="green">in catalogue</Chip>}</td>
              <td className="py-1.5 px-2 text-right tabular-nums text-gray-500">{it.year || ''}</td>
              <td className="py-1.5 px-2 text-right tabular-nums font-semibold">{it.times_cited}</td>
              <td className="py-1.5 text-right tabular-nums text-gray-500">{it.self_citations || ''}</td>
            </tr>))}</tbody>
        </table>)}
      {!all && d.items.length > 12 && <button onClick={() => setAll(true)} className="mt-2 text-sm text-indigo-700 hover:underline">Show all {d.items.length}</button>}
    </Card>
  );
};
export default PersonRecord;
