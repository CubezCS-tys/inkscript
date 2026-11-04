import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import { Card, Empty, ErrorBox, T, n } from '../components/Bits';
import { enc } from '../lib/api';
import { useApi } from '../lib/me';
import { S, f } from '../lib/strings';

export default function Search() {
  const router = useRouter();
  const q = typeof router.query.q === 'string' ? router.query.q : '';
  const { data, err } = useApi<any>(q ? `/search?q=${enc(q)}&limit=30` : null);
  const sec = (title: string, rows: any[], render: (x: any) => React.ReactNode) => (
    <Card title={`${title} (${rows.length})`} pad={false}>
      {rows.length === 0 ? <div className="px-5 pb-4"><Empty>{S.search.none}</Empty></div> : <ul className="divide-y divide-gray-100">{rows.map(render)}</ul>}
    </Card>
  );
  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">{S.search.title}: <T text={q} /></h1>
      {data && <p className="text-xs text-gray-500">{S.search.folded} <span className="ar-inline">«{data.folded}»</span> · {S.common.readFrom} {data.release_id || S.common.reading}</p>}
      {err && <ErrorBox>{err}</ErrorBox>}
      {!data ? q && <Empty>{S.common.loading}</Empty> : (
        <div className="grid lg:grid-cols-3 gap-4" data-testid="search-results">
          {sec(S.search.articles, data.articles, (a: any) => (
            <li key={a.stem} className="px-5 py-2"><Link href={`/articles/${enc(a.stem)}`} className="hover:text-indigo-700"><T as="p" text={a.title} className="text-sm" /></Link>
              <p className="text-xs text-gray-500 font-mono">{a.stem}{a.year ? ` · ${a.year}` : ''}</p></li>))}
          {sec(S.search.persons, data.persons, (p: any) => (
            <li key={p.id} className="px-5 py-2"><Link href={`/persons/${p.id}`} className="hover:text-indigo-700"><T as="p" text={p.name} className="text-sm" /></Link>
              <p className="text-xs text-gray-500">{p.name_lat && p.name_lat !== p.name ? `${p.name_lat} · ` : ''}<span className="font-mono">{p.id}</span> · {p.status} · {f(S.work.works, { n: p.n_works })}</p></li>))}
          {sec(S.search.works, data.works, (w: any) => (
            <li key={w.id} className="px-5 py-2"><Link href={`/works/${w.id}`} className="hover:text-indigo-700"><T as="p" text={w.title} className="text-sm" /></Link>
              <p className="text-xs text-gray-500"><span className="ar-inline">{(w.authors || []).slice(0, 2).join('، ')}</span> · <span className="font-mono">{w.id}</span> · {f(S.article.timesCited, { n: n(w.n_citing_pubs) })}</p></li>))}
        </div>
      )}
    </Layout>
  );
}
