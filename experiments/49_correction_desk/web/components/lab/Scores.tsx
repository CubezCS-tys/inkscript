import React, { useMemo, useState } from 'react';
import { AlertTriangle, Info } from 'lucide-react';
import { Card, Chip, Empty } from '../Bits';
import { DROPPED_NOTE, Engine, colorOf, isDropped, pct, shortOf, wordDiff } from './defs';

// Scores against the owner's saved correction, three tasks kept apart: recognition (the words), layout (the regions)
// and reading order. Lower is better for errors, higher for the rest. The engine the correction started from is
// marked: its words were the default, so it is flattered.

const POLICY_NICE: Record<string, string> = {
  raw: 'as printed (every letter form, mark, digit and punctuation counts)',
  faithful: 'as printed, Unicode tidied (NFC, no tatweel)',
  markup_stripped: '… with Markdown / LaTeX / HTML markup removed',
  no_punct: '… and punctuation removed',
  folded: 'folded for search (vowel marks, hamza forms, ى/ي, ة/ه, digits)',
};

export default function Scores({ d, scores, showDropped }: { d: any; scores: any; showDropped: boolean }) {
  const engines: Engine[] = d.engines;
  const byRun = useMemo(() => new Map(engines.map(e => [e.run_id, e])), [engines]);
  const [open, setOpen] = useState<string | null>(null);
  if (!scores || !scores.available) {
    return <Empty>{scores?.reason || 'No correction saved yet.'} Scores appear here once you save a correction in the Correct tab: until then there is no truth to score against (the Compare tab shows only where the readers disagree).</Empty>;
  }
  const rows: any[] = (scores.engines as any[]).filter(r => showDropped || !isDropped(r));
  const startedFrom = byRun.get(scores.started_from);
  return (
    <div className="space-y-4">
      <div className="text-sm text-gray-600 flex flex-wrap items-center gap-2">
        <span>Against revision <b>{scores.rev_no}</b>, saved by <b>{scores.actor}</b> on {new Date(scores.created_at).toLocaleString('en-GB')}: {scores.truth_lines} lines, {scores.truth_regions} regions{scores.unreadable_lines ? `, ${scores.unreadable_lines} unreadable line(s) left out` : ''}.</span>
        {startedFrom && <Chip tone="amber" title={scores.note}>started from {shortOf(startedFrom)}: flattered</Chip>}
      </div>
      <Card title="Each engine against your correction" pad={false}>
        <table className="w-full text-sm" data-testid="lab-scores">
          <thead>
            <tr className="text-xs text-gray-500 text-left border-b border-gray-100">
              <th className="px-4 py-2 font-medium">Engine</th>
              <th className="px-2 font-medium text-right" title="your text and the engine's as bags of words: order does not count; punctuation ignored; every letter form counts (1 − F1 of the word multisets)">Words wrong, any order</th>
              <th className="px-2 font-medium text-right" title="the same after folding vowel marks, hamza forms, ى/ي, ة/ه and digits">… folded</th>
              <th className="px-2 font-medium text-right" title="lines of your correction not found in the engine's text">Lines missing</th>
              <th className="px-2 font-medium text-right" title="your regions found by the engine (box overlap ≥ 50%), and with the right kind">Regions found / right kind</th>
              <th className="px-2 font-medium text-right text-gray-500" title="the order-sensitive figures, apart: letters wrong when the engine's text is read in its own order, and pairs of your lines in the same order">Reading order effect</th>
              <th className="px-4" />
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const e = byRun.get(r.run_id);
              const failed = r.status === 'failed';
              const rec = r.recognition;
              const lay = r.layout?.by_threshold?.['0.5'];
              const ro = r.reading_order?.text_position;
              return (
                <React.Fragment key={r.run_id}>
                  <tr className="border-t border-gray-100 align-top">
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full" style={{ background: e ? colorOf(e) : '#999' }} />
                        <span className="font-medium text-gray-900">{e ? shortOf(e) : r.label}</span>
                        {r.flattered && <Chip tone="amber">flattered</Chip>}
                        {isDropped(r) && <Chip tone="red">{DROPPED_NOTE}</Chip>}
                        {failed && <Chip tone="red">failed</Chip>}</div>
                    </td>
                    {failed ? <td colSpan={6} className="px-2 py-2 text-xs text-red-700"><AlertTriangle className="inline w-3.5 h-3.5 mr-1" />{r.error} — counted as 100% wrong (the page stays in the total)</td> : <>
                      <td className="px-2 py-2 text-right tabular-nums font-medium">{rec ? <>{pct(rec.no_punct.bag.rate, 1)} <span className="text-xs font-normal text-gray-500" title="unmatched words on both sides, halved: about how many words differ">≈ {Math.round(rec.no_punct.bag.errors / 2)} words</span></> : <span className="text-gray-400">no text</span>}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{rec ? pct(rec.folded.bag.rate, 1) : '—'}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{rec ? `${r.completeness.missing.length} of ${r.completeness.truth_lines}` : '—'}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{scores.truth_regions === 0 ? <span className="text-gray-400" title="the correction holds no regions yet">not corrected</span> : lay ? `${lay.matched} / ${lay.class_agree} of ${r.layout.truth_regions}` : <span className="text-gray-400" title={r.layout?.reason}>no boxes</span>}</td>
                      <td className="px-2 py-2 text-right tabular-nums text-gray-500 text-xs">{rec ? <>letters wrong in order {pct(rec.raw.cer.rate, 2)}{ro?.accuracy != null ? <><br />line pairs in order {pct(ro.accuracy, 1)}</> : null}</> : '—'}</td>
                    </>}
                    <td className="px-4 py-2 text-right">{!failed && <button className="text-xs text-indigo-700 hover:underline" onClick={() => setOpen(open === r.run_id ? null : r.run_id)}>{open === r.run_id ? 'hide' : 'details'}</button>}</td>
                  </tr>
                  {open === r.run_id && <tr><td colSpan={8} className="px-4 pb-4"><Details r={r} d={d} /></td></tr>}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </Card>
      <p className="text-xs text-gray-500 flex gap-1.5"><Info className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden />One page is a first look, not a ranking. Headline = words wrong in any order (1 − F1 of the word bags), so the text is judged apart from reading order; a word missing from the engine (a dropped column) still counts as wrong. The reading order effect, in grey, shows the order-sensitive figures: letters wrong when the engine&apos;s text is read in its own order (edit operations ÷ your text&apos;s length, can pass 100%) and the share of line pairs in your order. Regions are matched one to one by box overlap (intersection over union ≥ 0.5).</p>
    </div>
  );
}

function Details({ r, d }: { r: any; d: any }) {
  const rec = r.recognition;
  const truth = useMemo(() => (d.correction?.body?.lines || []).filter((l: any) => !l.unreadable).map((l: any) => l.text).join(' '), [d]);
  const eng = d.engines.find((e: Engine) => e.run_id === r.run_id) as Engine | undefined;
  const ops = useMemo(() => wordDiff(truth, eng?.text || ''), [truth, eng]);
  return (
    <div className="grid grid-cols-12 gap-4 bg-gray-50 rounded-lg p-3">
      <div className="col-span-5 space-y-3">
        {rec && <table className="w-full text-xs">
          <thead><tr className="text-gray-500 text-left"><th className="py-1 font-medium">Text compared</th><th className="font-medium text-right">letters wrong</th><th className="font-medium text-right">words wrong</th><th className="font-medium text-right">words, any order</th></tr></thead>
          <tbody>{Object.keys(POLICY_NICE).map(p => rec[p] && (
            <tr key={p} className="border-t border-gray-200"><td className="py-1 pr-2">{POLICY_NICE[p]}</td>
              <td className="text-right tabular-nums" title={`${rec[p].cer.sub} changed, ${rec[p].cer.dele} missing, ${rec[p].cer.ins} extra of ${rec[p].cer.ref_len}`}>{pct(rec[p].cer.rate, 2)}</td>
              <td className="text-right tabular-nums" title={`${rec[p].wer.sub} changed, ${rec[p].wer.dele} missing, ${rec[p].wer.ins} extra of ${rec[p].wer.ref_len}`}>{pct(rec[p].wer.rate, 1)}</td>
              <td className="text-right tabular-nums">{pct(rec[p].bag.rate, 1)}</td></tr>))}</tbody>
        </table>}
        {r.layout?.available && <div className="text-xs text-gray-700">
          <div className="font-medium mb-1">Regions (layout)</div>
          <p>At overlap ≥ 0.5: {r.layout.by_threshold['0.5'].matched} of your {r.layout.truth_regions} regions found, {r.layout.pred_regions} drawn by the engine; {r.layout.by_threshold['0.5'].class_agree} with the right kind (text / furniture / footnote). At ≥ 0.75: {r.layout.by_threshold['0.75'].matched}.</p>
          <p className="mt-1">Lines inside one of its regions: {r.layout.lines.covered} of {r.layout.lines.total}; in a region of the right kind: {r.layout.lines.coarse_agree}.</p>
          {r.reading_order?.block_order?.accuracy != null && <p className="mt-1">Reading order by its regions: {pct(r.reading_order.block_order.accuracy, 1)} of {r.reading_order.block_order.pairs} line pairs.</p>}
        </div>}
        {r.confusions?.length > 0 && <div className="text-xs"><div className="font-medium text-gray-700 mb-1">Most frequent letter changes (yours › engine&apos;s)</div>
          <div className="flex flex-wrap gap-1">{r.confusions.slice(0, 16).map(([k, n]: [string, number]) => { const [a, b] = k.split('>'); const show = (c: string) => (c === ' ' ? '␣' : c);
            return <span key={k} dir="ltr" className="bg-white border border-gray-200 rounded px-1.5 py-0.5"><bdi className="ar-inline">{show(a)}</bdi> → <bdi className="ar-inline">{show(b)}</bdi> ×{n}</span>; })}</div></div>}
        <div className="text-xs text-gray-600">Flags: {[r.completeness.truncated && 'cut off', r.completeness.repetition && 'repeats itself', r.completeness.empty && 'no text'].filter(Boolean).join(', ') || 'none'}</div>
      </div>
      <div className="col-span-7">
        <div className="text-xs text-gray-500 mb-1">Your text with the engine&apos;s differences: <span className="bg-red-100 text-red-800 px-1 rounded line-through">missing</span> <span className="bg-amber-100 text-amber-900 px-1 rounded">engine wrote</span></div>
        <div dir="rtl" className="ar text-[15px] leading-8 bg-white border border-gray-200 rounded-lg p-3 max-h-[50vh] overflow-auto">
          {ops.map((o, i) => o.op === 'equal' ? <span key={i}>{o.a.join(' ')} </span> : (
            <span key={i}>{o.a.length > 0 && <del className="bg-red-100 text-red-800 rounded px-0.5">{o.a.join(' ')}</del>}{o.b.length > 0 && <ins className="no-underline bg-amber-100 text-amber-900 rounded px-0.5 mx-0.5">{o.b.join(' ')}</ins>} </span>))}
        </div>
      </div>
    </div>
  );
}
