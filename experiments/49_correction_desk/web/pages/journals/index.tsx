import React, { useState } from 'react';
import Link from 'next/link';
import Layout from '../../components/Layout';
import { Card, Chip, Empty, ErrorBox, T, n } from '../../components/Bits';
import { Def, SmallNote, WHOLE } from '../../components/IndexBits';
import { useShowMode } from '../../lib/showmode';
import { useApi } from '../../lib/me';

// Journals with articles read (2026-10-23): two read whole (gate 1, gate 2's pilot), the rest from the random sample.
export default function Journals() {
  const { data, err } = useApi<any>('/index/journals');
  const [all, setAll] = useState(false);
  const showMode = useShowMode();
  const rows = data ? (all ? data.journals : data.journals.slice(0, 60)) : [];
  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">Journals</h1>
      <p className="text-sm text-gray-500">{data ? `${n(data.journals.length)} journals with articles read${showMode ? '' : ` · read from ${data.release_id || "the machine's reading"}`}` : '…'}</p>
      <SmallNote>Two education journals are read whole for 2010–2025: مجلة الطفولة العربية (gate 1) and مجلة الطفولة والتنمية (gate 2's pilot). The others come from a random sample of 600 articles, so most show one or two articles: their records fill in as gates 2 and 3 read whole journals.</SmallNote>
      {err && <ErrorBox>{err}</ErrorBox>}
      {!data ? <Empty>Loading…</Empty> : (
        <Card pad={false} className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="journals">
            <thead className="bg-gray-50 text-xs text-gray-500"><tr>
              <th className="px-3 py-2 text-right font-medium">Journal</th><th className="px-3 py-2 text-left font-medium">{showMode ? '' : 'Id'}</th>
              <th className="px-3 py-2 text-right font-medium"><Def text={data.defs.articles}>Articles read</Def></th>
              <th className="px-3 py-2 text-right font-medium">Years</th>
              <th className="px-3 py-2 text-right font-medium"><Def text={data.defs.references}>References</Def></th>
              <th className="px-3 py-2 text-right font-medium"><Def text={data.defs.times_cited_pub + ' Summed over the journal\'s publications.'}>Times cited</Def></th></tr></thead>
            <tbody>{rows.map((j: any) => (
              <tr key={j.journal_id} className="border-t border-gray-100 hover:bg-indigo-50/40">
                <td className="px-3 py-2 text-right"><Link href={`/journals/${j.journal_id}`} className="text-gray-900 hover:text-indigo-700 font-medium"><T text={j.title || j.journal_id} /></Link>
                  {j.title_en && <span className="block text-xs text-gray-400">{j.title_en}</span>}</td>
                <td className="px-3 py-2 font-mono text-xs text-gray-500">{!showMode && j.journal_id} {WHOLE[j.journal_id] && <Chip tone="indigo">{WHOLE[j.journal_id]}</Chip>}</td>
                <td className="px-3 py-2 text-right tabular-nums font-medium">{j.articles}</td>
                <td className="px-3 py-2 text-right tabular-nums text-gray-500">{j.first}{j.last !== j.first && `–${j.last}`}</td>
                <td className="px-3 py-2 text-right tabular-nums">{n(j.references)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{j.times_cited || ''}</td>
              </tr>))}</tbody>
          </table>
          {!all && data.journals.length > 60 && <div className="p-3 text-center"><button onClick={() => setAll(true)} className="text-sm text-indigo-700 hover:underline">Show all {data.journals.length}</button></div>}
        </Card>
      )}
    </Layout>
  );
}
