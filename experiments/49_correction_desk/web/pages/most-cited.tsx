import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../components/Layout';
import { Card, Chip, Empty, ErrorBox, T, Tabs, n } from '../components/Bits';
import { Def, SmallNote, pubHref } from '../components/IndexBits';
import { useApi } from '../lib/me';
import { useShowMode } from '../lib/showmode';

// Most cited (2026-10-23): cited works (any work, held or not) and Mandumah publications reached through a link.
export default function MostCited() {
  const router = useRouter();
  const [kind, setKind] = useState('works');
  useEffect(() => { if (router.query.kind === 'pubs' || router.query.kind === 'works') setKind(router.query.kind as string); }, [router.query.kind]);
  const [limit, setLimit] = useState(50);
  const r = useApi<any>(`/index/most-cited?kind=${kind}&limit=${limit}`);
  const showMode = useShowMode();
  const d = r.data && r.data.kind === kind ? r.data : null;
  return (
    <Layout>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Most cited</h1>
          <p className="text-sm text-gray-500">{d ? (kind === 'works' ? `${n(d.total)} cited works · ${n(d.cited_2plus)} cited by 2+ articles` : `${n(d.total)} Mandumah publications cited · ${d.total_read} of them read`) : '…'}{!showMode && <> · read from {r.data?.release_id || '…'}</>}</p>
        </div>
        <Tabs value={kind} onChange={setKind} tabs={[['works', 'Cited works'], ['pubs', 'Mandumah publications cited']]} />
      </div>
      <SmallNote>Times cited counts only the articles read so far (a pilot sample), so the counts are small and many works tie. {kind === 'pubs' ? 'A publication counts when the linker matched a reference to it (accepted links only).' : 'A cited work is any book, article or thesis cited, whether Mandumah holds it or not.'}</SmallNote>
      {r.err && <ErrorBox>{r.err}</ErrorBox>}
      {!d ? <Empty>Loading…</Empty> : (
        <Card pad={false} className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="most-cited">
            <thead className="bg-gray-50 text-xs text-gray-500"><tr>
              <th className="px-3 py-2 text-left font-medium w-10">#</th>
              <th className="px-3 py-2 text-right font-medium">{kind === 'works' ? 'Work' : 'Publication'}</th>
              <th className="px-3 py-2 text-right font-medium">Authors</th>
              <th className="px-3 py-2 text-left font-medium">{kind === 'works' ? 'Type' : 'Journal · year'}</th>
              <th className="px-3 py-2 text-left font-medium">{kind === 'works' ? 'In Mandumah' : 'Held as'}</th>
              <th className="px-3 py-2 text-right font-medium"><Def text={d.define}>Times cited</Def></th>
              <th className="px-3 py-2 text-right font-medium"><Def text="Every reference to it, back references («المرجع السابق», ibid.) included.">Mentions</Def></th></tr></thead>
            <tbody>{d.items.map((w: any) => (
              <tr key={w.id || w.pub_id} className="border-t border-gray-100 hover:bg-indigo-50/40">
                <td className="px-3 py-2 tabular-nums text-gray-400">{w.rank}</td>
                <td className="px-3 py-2 text-right">{kind === 'works'
                  ? <Link href={`/works/${w.id}`} className="text-gray-900 hover:text-indigo-700 font-medium"><T text={w.title} /></Link>
                  : w.stem ? <Link href={pubHref(w)!} className="text-gray-900 hover:text-indigo-700 font-medium"><T text={w.title} /></Link> : <T text={w.title} className="font-medium text-gray-900" />}</td>
                <td className="px-3 py-2 text-right text-gray-600"><T text={(w.authors || []).filter(Boolean).join('، ') || null} /></td>
                <td className="px-3 py-2 text-xs text-gray-500">{kind === 'works' ? w.pub_type : <><Link href={`/journals/${w.journal_id}`} className="hover:text-indigo-700"><span className="ar-inline">{w.journal}</span></Link> · {w.year}</>}</td>
                <td className="px-3 py-2">{kind === 'works' ? (w.held_pub_id ? (w.held_stem ? <Link href={`/articles/${w.held_stem}`}><Chip tone="indigo">read</Chip></Link> : <Chip tone="green">catalogue</Chip>) : '')
                  : w.read ? <Chip tone="indigo">read</Chip> : <Chip>catalogue</Chip>}</td>
                <td className="px-3 py-2 text-right tabular-nums font-semibold">{w.times_cited}</td>
                <td className="px-3 py-2 text-right tabular-nums text-gray-500">{w.mentions}</td>
              </tr>))}</tbody>
          </table>
          {d.items.length >= limit && <div className="p-3 text-center"><button onClick={() => setLimit(limit + 100)} className="text-sm text-indigo-700 hover:underline">Show 100 more</button></div>}
        </Card>
      )}
    </Layout>
  );
}
