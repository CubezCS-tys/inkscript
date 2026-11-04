import React from 'react';
import Link from 'next/link';
import Layout from '../../components/Layout';
import { Card, Empty, ErrorBox, T, n } from '../../components/Bits';
import { useApi } from '../../lib/me';
import { useShowMode } from '../../lib/showmode';
import { S, f } from '../../lib/strings';

export default function TopWorks() {
  const { data, err } = useApi<any>('/top/works?limit=60');
  const showMode = useShowMode();
  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">{S.top.title}</h1>
      <p className="text-sm text-gray-500">{showMode ? 'The works the articles read cite most.' : f(S.top.lead, { src: data ? (data.release_id ? `release ${data.release_id}` : S.common.reading) : '…' })}</p>
      <div className="rounded-lg border border-indigo-100 bg-indigo-50 px-4 py-2 text-sm text-indigo-900 flex flex-wrap items-center gap-3">
        <span>The full view, with the list of Mandumah's own publications cited, is <b>Most cited</b>:</span>
        <Link href="/most-cited" className="underline hover:text-indigo-700">All cited works →</Link>
        <Link href="/most-cited?kind=pubs" className="underline hover:text-indigo-700">Mandumah publications cited →</Link>
      </div>
      {err && <ErrorBox>{err}</ErrorBox>}
      {!data ? <Empty>{S.common.loading}</Empty> : (
        <Card pad={false} className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="top-works">
            <thead className="bg-gray-50 text-xs text-gray-500"><tr>
              <th className="px-4 py-2 text-right font-medium w-12">{S.top.rank}</th><th className="px-2 py-2 text-right font-medium">{S.top.work}</th>
              <th className="px-2 py-2 text-right font-medium">{S.top.authors}</th><th className="px-2 py-2 text-left font-medium">type</th>
              <th className="px-2 py-2 text-right font-medium">{S.top.citing}</th><th className="px-2 py-2 text-right font-medium">{S.top.mentions}</th></tr></thead>
            <tbody>{data.works.map((w: any) => (
              <tr key={w.id} className="border-t border-gray-100 hover:bg-indigo-50/40" data-work={w.id}>
                <td className="px-4 py-2 text-right tabular-nums text-gray-500">{w.rank}</td>
                <td className="px-2 py-2 text-right"><Link href={`/works/${w.id}`} className="text-gray-900 hover:text-indigo-700 font-medium"><T text={w.title} /></Link> {!showMode && <span className="text-xs text-gray-400 font-mono">{w.id}</span>}</td>
                <td className="px-2 py-2 text-right text-gray-600"><T text={(w.authors || []).join('، ')} /></td>
                <td className="px-2 py-2 text-gray-500 text-xs">{w.pub_type}</td>
                <td className="px-2 py-2 text-right tabular-nums font-medium">{n(w.n_citing_pubs)}</td>
                <td className="px-2 py-2 text-right tabular-nums text-gray-600">{n(w.n_mentions)}</td>
              </tr>))}
            </tbody>
          </table>
        </Card>
      )}
    </Layout>
  );
}
