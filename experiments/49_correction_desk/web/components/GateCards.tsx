import React from 'react';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react';
import { Card, Empty, T, n } from './Bits';
import { Def } from './IndexBits';

// Gate 1 and gate 2 as two calm cards for the Index home (experiment 73, M2). Every number comes from
// /desk/api/headlines, so the Index home, the Story page and the deck say the same thing; a missing value is "—".

const fmt = (v: any) => (v == null ? '—' : typeof v === 'number' ? (Number.isInteger(v) ? n(v) : String(Math.round(v * 10) / 10)) : String(v));
const usd = (v: any) => (v == null ? '—' : `$${Number(v).toLocaleString('en', { maximumFractionDigits: 2, minimumFractionDigits: Number.isInteger(v) ? 0 : 2 })}`);

function times(a: any, b: any) {
  if (a == null || b == null) return null;
  if (b === 0) return a > 0 ? 'vs none' : null;
  const x = a / b;
  return x >= 1.5 ? `${x >= 10 ? Math.round(x) : x.toFixed(1)}×` : 'about the same';
}

// One comparison: the read journal(s) against random articles of the same size, as two bars on one scale; the values
// sit in their own column so labels never overlap the bars.
export const PairRow: React.FC<{ label: string; define?: string; pair?: any[] | null; who: string; muted?: boolean; note?: string }> =
  ({ label, define, pair, who, muted, note }) => {
    const a = pair?.[0], b = pair?.[1];
    const max = Math.max(1, Number(a) || 0, Number(b) || 0);
    const w = (v: any) => `${v == null ? 0 : Math.max(v > 0 ? 1.5 : 0, (100 * Number(v)) / max)}%`;
    const x = times(a, b);
    return (
      <div className="py-2.5" data-testid="pair-row">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-sm font-medium text-gray-800"><Def text={define}>{label}</Def></span>
          {x && <span className={`text-xs font-semibold ${muted ? 'text-gray-500' : 'text-indigo-700'}`}>{x}</span>}
        </div>
        <div className="grid grid-cols-[9.5rem_1fr_3.5rem] items-center gap-x-3 gap-y-1 mt-1.5 text-xs">
          <span className="text-gray-600 truncate">{who}</span>
          <span className="h-3 rounded bg-gray-100 overflow-hidden"><span className="block h-3 rounded" style={{ width: w(a), background: muted ? '#94a3b8' : '#4f46e5' }} /></span>
          <span className="text-right tabular-nums font-semibold text-gray-900">{fmt(a)}</span>
          <span className="text-gray-500 truncate">random, same size</span>
          <span className="h-3 rounded bg-gray-100 overflow-hidden"><span className="block h-3 rounded" style={{ width: w(b), background: '#cbd5e1' }} /></span>
          <span className="text-right tabular-nums text-gray-600">{fmt(b)}</span>
        </div>
        {note && <p className="text-xs text-gray-500 mt-1">{note}</p>}
      </div>
    );
  };

const Done = ({ children }: { children: React.ReactNode }) => (
  <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-50 border border-green-200 rounded-full px-2 py-0.5">
    <CheckCircle2 className="w-3.5 h-3.5" aria-hidden />{children}</span>
);

export const Gate1Card: React.FC<{ h: any; children?: React.ReactNode }> = ({ h, children }) => {
  const g = h?.gate1, D = h?.defs || {};
  const j = (h?.journals_read_whole || []).find((x: any) => x.id === (g?.journal || 'J0130'));
  return (
    <Card title={<span className="flex items-center gap-2 flex-wrap">Gate 1: one journal read whole, against random articles <Done>done</Done></span>}
      right={<Link href={`/journals/${g?.journal || 'J0130'}`} className="text-sm text-indigo-700 hover:underline">Open the journal →</Link>}>
      {!h ? <Empty>Loading…</Empty> : (
        <div data-testid="gate1-card">
          <p className="text-sm text-gray-600 mb-1">Every article of <T text={g?.title || j?.title} />{j?.country && <> ({j.country})</>} was read: {fmt(g?.articles)} articles.
            Inside one journal the links a citation index lives on are far denser than in random articles of the same size.</p>
          <div className="divide-y divide-gray-100">
            <PairRow label="Authors who wrote 2 or more articles" define={D.gate1_authors_2plus} pair={g?.authors_2plus} who="the journal" />
            <PairRow label="Institutions seen in 2 or more articles" define={D.gate1_institutions_2plus} pair={g?.institutions_2plus} who="the journal" />
            <PairRow label="Cited works shared by 2 or more articles" define={D.gate1_shared_works} pair={g?.shared_works} who="the journal" />
          </div>
          {children}
        </div>
      )}
    </Card>
  );
};

export const Gate2Card: React.FC<{ h: any }> = ({ h }) => {
  const g = h?.gate2, D = h?.defs || {};
  const J = (id: string) => (h?.journals_read_whole || []).find((x: any) => x.id === id) || {};
  const [a, b] = g?.pair || ['J0130', 'J0165'];
  const A = J(a), B = J(b);
  const pc = g?.pages_checked;
  const Box = ({ x, id }: { x: any; id: string }) => (
    <Link href={`/journals/${id}`} className="block rounded-xl border border-indigo-200 bg-indigo-50/60 px-4 py-3 hover:border-indigo-400 min-w-0">
      <span className="block text-base font-semibold text-gray-900 truncate"><T text={x.title} /></span>
      <span className="block text-xs text-gray-600 truncate">{x.title_en}</span>
      <span className="block text-xs text-gray-500 mt-1">{x.country || '—'} · {fmt(x.articles)} articles{x.word ? ` (${fmt(x.scan)} scanned, ${fmt(x.word)} from Word files)` : ''}</span>
    </Link>
  );
  return (
    <Card title={<span className="flex items-center gap-2 flex-wrap">Gate 2's pilot: the two education journals cite each other <Done>done</Done></span>}
      right={<Link href={`/journals/${b}`} className="text-sm text-indigo-700 hover:underline">Open the second journal →</Link>}>
      {!h ? <Empty>Loading…</Empty> : !g ? <Empty>—</Empty> : (
        <div data-testid="gate2-card">
          <p className="text-sm text-gray-600 mb-3">A second education journal was read whole. Put side by side, the two journals cite each other and share
            authors and sources; random sets of articles of the same sizes share almost nothing.</p>
          <div className="grid md:grid-cols-[1fr_auto_1fr] items-center gap-3">
            <Box x={A} id={a} />
            <div className="flex flex-col items-center gap-2 text-sm px-2" aria-label={`${A.title} cites ${B.title} ${g.cites_a_to_b} times; ${B.title} cites ${A.title} ${g.cites_b_to_a} times`}>
              <Def text={D.gate2_cites}>
                <span className="flex items-center gap-1.5 whitespace-nowrap"><span className="tabular-nums text-xl font-semibold text-indigo-700">{fmt(g.cites_a_to_b)}</span>
                  <span className="text-xs text-gray-500">references</span><ArrowRight className="w-4 h-4 text-indigo-500" aria-hidden /></span>
              </Def>
              <span className="flex items-center gap-1.5 whitespace-nowrap"><ArrowLeft className="w-4 h-4 text-teal-600" aria-hidden />
                <span className="tabular-nums text-xl font-semibold text-teal-700">{fmt(g.cites_b_to_a)}</span><span className="text-xs text-gray-500">references</span></span>
            </div>
            <Box x={B} id={b} />
          </div>
          <div className="divide-y divide-gray-100 mt-3">
            <PairRow label="Authors who wrote in both journals" define={D.gate2_shared_authors} pair={g.shared_authors} who="the two journals" />
            <PairRow label="Cited works cited in both journals" define={D.gate2_shared_works} pair={g.shared_works} who="the two journals" />
            <PairRow label="Article pairs citing a common work" define={D.gate2_coupled_pairs} pair={g.coupled_pairs} who="the two journals" />
            <PairRow label="Institutions seen in both journals" define={D.gate2_shared_institutions} pair={g.shared_institutions} who="the two journals" muted
              note="No more than chance: the large Egyptian and Saudi universities appear everywhere." />
          </div>
          <div className="grid sm:grid-cols-3 gap-3 mt-3 text-sm">
            <div className="rounded-lg bg-gray-50 px-3 py-2"><Def text={D.gate2_cost}><span className="text-xs text-gray-500">What the pilot cost</span></Def>
              <span className="block text-lg font-semibold text-gray-900 tabular-nums">{usd(g.cost_usd)}</span>
              <span className="text-xs text-gray-500">{fmt(g.articles)} articles read whole</span></div>
            <div className="rounded-lg bg-gray-50 px-3 py-2"><Def text={D.gate2_ten}><span className="text-xs text-gray-500">The ten journals at this rate</span></Def>
              <span className="block text-lg font-semibold text-gray-900 tabular-nums">≈ {usd(g.ten_journals_usd)}</span>
              <span className="text-xs text-gray-500">so the other nine can follow</span></div>
            <div className="rounded-lg bg-gray-50 px-3 py-2"><span className="text-xs text-gray-500">Pages checked beside the scan</span>
              <span className="block text-lg font-semibold text-gray-900 tabular-nums">{pc ? `${pc.right} right · ${pc.minor} minor · ${pc.serious} serious` : '—'}</span>
              <span className="text-xs text-gray-500">{pc ? `of ${pc.of} random pages, ${pc.words_wrong} words wrong` : ''}</span></div>
          </div>
        </div>
      )}
    </Card>
  );
};
