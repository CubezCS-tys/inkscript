import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import { Card, Chip, Empty, ErrorBox, T, n } from '../../components/Bits';
import { WHOLE } from '../../components/IndexBits';
import { useShowMode } from '../../lib/showmode';
import { enc } from '../../lib/api';
import { useApi } from '../../lib/me';
import { S } from '../../lib/strings';

export default function Articles() {
  const router = useRouter();
  const q0 = typeof router.query.q === 'string' ? router.query.q : '';
  const [q, setQ] = useState(q0);
  useEffect(() => setQ(q0), [q0]);
  const showMode = useShowMode();
  const { data, err } = useApi<any>(router.isReady ? `/articles?limit=5000${q0 ? `&q=${enc(q0)}` : ''}` : null);
  return (
    <Layout>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-semibold text-gray-900">{S.nav.articles}</h1>
          <p className="text-sm text-gray-500">{data ? <>{q0 ? `${n(data.articles.length)} of ${n(data.total)} articles match` : `${n(data.total ?? data.articles.length)} articles`}{q0 && data.articles.length >= 5000 && ' (first 5,000 shown)'}
            {' '}· by journal, newest first{!showMode && <> · {S.common.readFrom} {data.release_id || S.common.reading}</>}</> : ''}</p></div>
        <form onSubmit={e => { e.preventDefault(); router.push(q ? `/articles?q=${enc(q)}` : '/articles'); }}>
          <input value={q} onChange={e => setQ(e.target.value)} dir="auto" placeholder="title or author" className="rounded-lg border-gray-300 text-sm w-72" />
        </form>
      </div>
      {err && <ErrorBox>{err}</ErrorBox>}
      {!data ? <Empty>{S.common.loading}</Empty> : (
        <Card pad={false} className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500"><tr>{!showMode && <th className="px-4 py-2 text-left font-medium">Article</th>}<th className="px-2 py-2 text-left font-medium">Title</th><th className="px-2 py-2 text-left font-medium">Journal</th><th className="px-2 py-2 text-left font-medium">Authors</th><th className="px-2 py-2 text-right font-medium">Year</th></tr></thead>
            <tbody>{sorted(data.articles, !!q0).map((a: any) => (
              <tr key={a.stem} className="border-t border-gray-100 hover:bg-indigo-50/40">
                {!showMode && <td className="px-4 py-2 font-mono text-xs whitespace-nowrap"><Link href={`/articles/${enc(a.stem)}`} className="text-indigo-700 hover:underline">{a.stem}</Link></td>}
                <td className="px-2 py-2 max-w-xl"><Link href={`/articles/${enc(a.stem)}`} className="hover:text-indigo-700"><T text={a.title} /></Link>
                  {a.word_route && <span className="ml-2"><Chip tone="gray">Word file</Chip></span>}</td>
                <td className="px-2 py-2 text-xs text-gray-600 max-w-[16rem]"><T text={a.journal} />{WHOLE[a.journal_id] && <span className="block text-[11px] text-indigo-700">{WHOLE[a.journal_id]}</span>}</td>
                <td className="px-2 py-2 text-gray-600"><T text={(a.authors || []).join('، ')} /></td>
                <td className="px-2 py-2 text-right tabular-nums text-gray-600">{a.year || ''}</td>
              </tr>))}
            </tbody>
          </table>
        </Card>
      )}
    </Layout>
  );
}

// No search: the journals read whole first, then the others, each journal's articles newest first. A search keeps
// the API's order (best matches first).
function sorted(rows: any[], searching: boolean) {
  if (searching) return rows;
  const rank = (a: any) => (WHOLE[a.journal_id] ? (a.journal_id === 'J0130' ? 0 : 1) : 2);
  return [...rows].sort((a, b) => rank(a) - rank(b) || String(a.journal || '').localeCompare(String(b.journal || ''), 'ar')
    || (b.year || 0) - (a.year || 0) || String(a.stem).localeCompare(String(b.stem)));
}
