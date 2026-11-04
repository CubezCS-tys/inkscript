import React, { useState } from 'react';
import Link from 'next/link';
import Layout from '../../components/Layout';
import { Card, Empty, ErrorBox, T, n } from '../../components/Bits';
import { Def, SmallNote, countryName } from '../../components/IndexBits';
import { useShowMode } from '../../lib/showmode';
import { useApi } from '../../lib/me';

// Institutions (organisation level) by articles read (2026-10-23).
export default function Institutions() {
  const { data, err } = useApi<any>('/index/institutions?limit=1000');
  const [all, setAll] = useState(false);
  const showMode = useShowMode();
  const hl = useApi<any>('/headlines');
  const rows = data ? (all ? data.institutions : data.institutions.slice(0, 50)) : [];
  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">Institutions</h1>
      <p className="text-sm text-gray-500">{data ? `${n(data.institutions.length)} institutions matched from printed affiliations${showMode ? '' : ` · read from ${data.release_id || "the machine's reading"}`}` : '…'}</p>
      <SmallNote>Matched from the affiliations printed under the authors' names. The same university printed in Arabic and in English is one record: the AI librarian joined the two spellings on 2 November (for example جامعة الإسكندرية and Alexandria University), so each university is counted once.
        {hl.data?.institutions_with_country_pct != null && <> {hl.data.institutions_with_country_pct}% of the institutions have their country recorded.</>}</SmallNote>
      {err && <ErrorBox>{err}</ErrorBox>}
      {!data ? <Empty>Loading…</Empty> : (
        <Card pad={false} className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="institutions">
            <thead className="bg-gray-50 text-xs text-gray-500"><tr>
              <th className="px-3 py-2 text-left font-medium w-10">#</th>
              <th className="px-3 py-2 text-right font-medium">Institution</th><th className="px-3 py-2 text-left font-medium">Kind</th>
              <th className="px-3 py-2 text-left font-medium">Country</th>
              <th className="px-3 py-2 text-right font-medium"><Def text="Articles read with at least one author whose printed affiliation was matched to this institution.">Articles</Def></th>
              <th className="px-3 py-2 text-right font-medium">Authors</th><th className="px-3 py-2 text-right font-medium">Journals</th>
              <th className="px-3 py-2 text-right font-medium"><Def text={data.defs.times_cited_pub + ' Summed over its articles.'}>Times cited</Def></th></tr></thead>
            <tbody>{rows.map((i: any, k: number) => (
              <tr key={i.inst_id} className="border-t border-gray-100 hover:bg-indigo-50/40">
                <td className="px-3 py-2 text-gray-400 tabular-nums">{k + 1}</td>
                <td className="px-3 py-2 text-right"><Link href={`/institutions/${i.inst_id}`} className="text-gray-900 hover:text-indigo-700 font-medium"><T text={i.name} /></Link></td>
                <td className="px-3 py-2 text-xs text-gray-500">{i.kind}</td><td className="px-3 py-2 text-xs text-gray-500">{i.country ? countryName(i.country) : '—'}</td>
                <td className="px-3 py-2 text-right tabular-nums font-medium">{i.articles}</td>
                <td className="px-3 py-2 text-right tabular-nums">{i.authors}</td><td className="px-3 py-2 text-right tabular-nums">{i.journals}</td>
                <td className="px-3 py-2 text-right tabular-nums">{i.times_cited || ''}</td>
              </tr>))}</tbody>
          </table>
          {!all && data.institutions.length > 50 && <div className="p-3 text-center"><button onClick={() => setAll(true)} className="text-sm text-indigo-700 hover:underline">Show all {data.institutions.length}</button></div>}
        </Card>
      )}
    </Layout>
  );
}
