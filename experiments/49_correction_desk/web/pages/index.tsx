import React, { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Play, RefreshCw } from 'lucide-react';
import Layout from '../components/Layout';
import { Card, Chip, Empty, ErrorBox, Tile, dur, n, when } from '../components/Bits';
import { useApi, useMe } from '../lib/me';
import { S, f, kindLabel } from '../lib/strings';
import { readShowMode, useShowMode } from '../lib/showmode';

export default function Overview() {
  // presentation mode (experiment 73): a visitor never lands on the correctors' queue; / leads to the Story
  const show = useShowMode();
  const router = useRouter();
  useEffect(() => { if (show || readShowMode() || router.query.show === '1') router.replace(router.query.show === '1' ? '/story?show=1' : '/story'); }, [show, router.query.show]);   // eslint-disable-line
  const { me } = useMe();
  const o = useApi<any>('/stats/overview');
  const k = useApi<any[]>('/stats/kinds');
  const st = useApi<any>('/state');
  const ov = o.data;
  const open = (ov?.open_tasks || []).reduce((s: number, r: any) => s + r.n, 0);
  const rel = ov?.last_release;
  const mine = me ? Object.values(me.decisions || {}).reduce((s: number, x: any) => s + x, 0) : null;
  const kinds = (k.data || []).filter((r: any) => r.open + r.claimed + r.answered > 0);
  return (
    <Layout>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{S.overview.title}</h1>
          <p className="text-sm text-gray-500">{rel ? f(S.overview.sub, { release: rel.release_id, articles: st.data?.n_articles ?? '…', when: when(rel.finished_at) }) : S.common.reading}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => { o.reload(); k.reload(); }} aria-label="Refresh" className="p-2 rounded-lg bg-white border border-gray-200 hover:bg-gray-100">
            <RefreshCw className={`w-4 h-4 ${o.loading ? 'animate-spin' : ''}`} /></button>
          <Link href="/work" className="text-sm px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 flex items-center gap-1.5" data-testid="start"><Play className="w-4 h-4" aria-hidden /> {S.overview.start}</Link>
        </div>
      </div>
      {o.err && <ErrorBox>{o.err}</ErrorBox>}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <Tile label={S.overview.openTasks} value={ov ? n(open) : '…'} sub={ov ? f(S.overview.openTasksSub, { n: ov.open_tasks.length }) : ''} href="/work" />
        <Tile label={S.overview.today} value={ov ? n(ov.decisions_today) : '…'} sub={S.overview.todaySub} />
        <Tile label={S.overview.mine} value={mine == null ? '…' : n(mine)} sub={me ? f(S.overview.mineSub, { n: me.decisions_last_24h }) : ''} />
        <Tile label={S.overview.notesOnMine} value={me ? n(me.open_notes_on_my_decisions) : '…'} sub={S.overview.notesOnMineSub} href="/notes"
          light={me ? (me.open_notes_on_my_decisions ? 'warning' : 'good') : undefined} />
        <Tile label={S.overview.orphaned} value={ov ? n(ov.orphaned_subjects) : '…'} sub={S.overview.orphanedSub}
          light={ov ? (ov.orphaned_subjects ? 'warning' : 'good') : undefined} />
        <Tile label={S.overview.lastRelease} value={rel ? rel.release_id.slice(1, 9) + ' ' + rel.release_id.slice(10, 14) : '—'}
          sub={rel ? f(S.overview.lastReleaseSub, { applied: rel.n_applied, n: rel.n_decisions }) : ''} href="/releases"
          light={rel ? (rel.fk_ok && rel.decisions_hold && !rel.n_orphaned && !rel.n_conflict ? 'good' : 'warning') : undefined} />
      </div>
      <Card pad={false} className="overflow-x-auto" title={S.overview.queue} right={<span className="text-xs text-gray-500">{S.overview.queueSub}</span>}>
        {k.err && <div className="px-5 pb-4"><ErrorBox>{k.err}</ErrorBox></div>}
        {!k.data ? <div className="px-5 pb-4"><Empty>{S.common.loading}</Empty></div> : (
          <table className="w-full text-sm" data-testid="queue">
            <thead className="bg-gray-50 text-xs text-gray-500"><tr>
              <th className="px-4 py-2 text-left font-medium">{S.overview.cols.kind}</th>
              <th className="px-2 py-2 text-right font-medium">{S.overview.cols.open}</th>
              <th className="px-2 py-2 text-right font-medium">{S.overview.cols.held}</th>
              <th className="px-2 py-2 text-right font-medium">{S.overview.cols.answered}</th>
              <th className="px-2 py-2 text-right font-medium">{S.overview.cols.mine}</th>
              <th className="px-2 py-2 text-right font-medium">{S.overview.cols.median}</th>
              <th className="px-2 py-2 text-left font-medium">{S.overview.cols.owner}</th>
              <th className="px-2 py-2" />
            </tr></thead>
            <tbody>{kinds.map((r: any) => (
              <tr key={r.kind} className="border-t border-gray-100 hover:bg-indigo-50/40">
                <td className="px-4 py-2 font-medium text-gray-900">{kindLabel(r.kind)}</td>
                <td className="px-2 py-2 text-right tabular-nums">{n(r.open)}</td>
                <td className="px-2 py-2 text-right tabular-nums text-gray-600">{n(r.claimed)}</td>
                <td className="px-2 py-2 text-right tabular-nums text-gray-600">{n(r.answered)}</td>
                <td className="px-2 py-2 text-right tabular-nums text-gray-600">{n(r.answered_by_me)}</td>
                <td className="px-2 py-2 text-right tabular-nums text-gray-600">{dur(r.median_s)}</td>
                <td className="px-2 py-2 text-gray-600"><span title={S.overview.ownerTitle}><Chip tone="indigo">{S.overview.ownerWording}</Chip></span></td>
                <td className="px-2 py-2 text-right">{r.open > 0 && <Link href={`/work?kind=${r.kind}`} className="text-indigo-700 hover:underline text-xs whitespace-nowrap">{S.overview.go} →</Link>}</td>
              </tr>))}
            </tbody>
          </table>
        )}
      </Card>
    </Layout>
  );
}
