import React, { useMemo, useState } from 'react';
import { AlertTriangle, Eye, EyeOff, ListOrdered } from 'lucide-react';
import { Card, Chip } from '../Bits';
import ScanOverlay, { Layer } from './ScanOverlay';
import { DROPPED_NOTE, Engine, TYPE_NICE, colorOf, isDropped, pct, secs, shortOf, usd, wordDiff } from './defs';

// Compare: the scan with each engine's regions as overlays you can switch on and off, a card per engine (state, time,
// memory, cost, what it gives), two engines' texts side by side with the words where they DISAGREE marked (no truth
// is involved here: a disagreement is not an error), and how much every pair of engines disagrees.

export default function Compare({ d, scan, showDropped }: { d: any; scan: string; showDropped: boolean }) {
  const allEngines: Engine[] = d.engines;
  const engines: Engine[] = showDropped ? allEngines : allEngines.filter(e => !isDropped(e));
  const boxed = allEngines.filter(e => e.has_boxes);
  // readings whose text is identical to an earlier one (the same model with a speed setting) are shown once
  const dupOf = useMemo(() => {
    const seen = new Map<string, string>(); const m = new Map<string, string>();
    engines.filter(e => e.has_text).forEach(e => { const k = e.text || ''; if (seen.has(k)) m.set(e.run_id, seen.get(k)!); else seen.set(k, e.run_id); });
    return m;
  }, [engines]);
  const texted = engines.filter(e => e.has_text && !dupOf.has(e.run_id));
  const [on, setOn] = useState<Record<string, boolean>>(() => Object.fromEntries(boxed.map((e, i) => [e.run_id, i === 0])));
  const [order, setOrder] = useState(true);
  const [focus, setFocus] = useState<string | null>(null);
  const [left, setLeft] = useState<string>(texted.find(e => e.engine === 'azure_argon')?.run_id || texted.find(e => e.kind === 'ours')?.run_id || texted[0]?.run_id || '');
  const [right, setRight] = useState<string>((d.default_right && texted.find(e => `${e.engine}/${e.variant}` === d.default_right)?.run_id)
    || texted.find(e => e.engine === 'nuqta')?.run_id || texted.find(e => e.run_id !== left)?.run_id || '');
  const byId = useMemo(() => new Map(allEngines.map(e => [e.run_id, e])), [allEngines]);
  const layers: Layer[] = boxed.filter(e => on[e.run_id]).map(e => ({
    key: e.run_id, color: colorOf(e),
    boxes: (e.blocks || []).filter(b => b.box).map(b => ({ id: b.id, box: b.box!, order: b.order, label: TYPE_NICE[b.type] || b.type })),
  }));
  const L = byId.get(left), R = byId.get(right);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-5 space-y-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-gray-500 mr-1">Regions on the scan:</span>
            {boxed.map(e => (
              <button key={e.run_id} onClick={() => setOn({ ...on, [e.run_id]: !on[e.run_id] })} data-testid={`lab-layer-${e.engine}-${e.variant}`}
                className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border text-xs ${on[e.run_id] ? 'bg-white' : 'bg-gray-50 text-gray-400'}`}
                style={{ borderColor: on[e.run_id] ? colorOf(e) : '#e5e7eb', color: on[e.run_id] ? colorOf(e) : undefined }}>
                {on[e.run_id] ? <Eye className="w-3.5 h-3.5" aria-hidden /> : <EyeOff className="w-3.5 h-3.5" aria-hidden />}{shortOf(e)}{isDropped(e) ? ' (regions only)' : ''}
              </button>))}
            <button onClick={() => setOrder(!order)} className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border text-xs ${order ? 'border-gray-400 text-gray-700' : 'text-gray-400'}`}>
              <ListOrdered className="w-3.5 h-3.5" aria-hidden />reading order</button>
          </div>
          <ScanOverlay src={scan} width={d.page.width} height={d.page.height} layers={layers} focus={focus} showOrder={order}
            onPick={(k, id) => setFocus(`${k}:${id}`)} maxH="max-h-[78vh]" />
          <p className="text-xs text-gray-500">Each box is a region as the engine found it, numbered in the engine&apos;s own reading order, with its kind. Nuqta gives text only, so it has no boxes. Azure&apos;s boxes are its paragraphs (our Read model gives no kinds).</p>
        </div>
        <div className="col-span-7 space-y-3">
          <Card title="Two readings side by side" right={<span className="text-xs text-gray-500">marked: where the two <b>disagree</b> (not errors: there is no truth here)</span>} pad>
            <div className="grid grid-cols-2 gap-3">
              <Pick engines={texted} value={left} onChange={setLeft} />
              <Pick engines={texted} value={right} onChange={setRight} />
            </div>
            {[L, R].filter(x => x?.warning).map(x => (
              <p key={x!.run_id} className="mt-2 text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded px-2 py-1" data-testid="lab-reader-warning">
                <b>{shortOf(x!)}</b>: {x!.warning}</p>))}
            {L && R && <SideBySide a={L} b={R} focus={focus} setFocus={setFocus} />}
          </Card>
          <Card title="How much the readers disagree" pad>
            <DisagreeTable d={d} byId={byId} hide={dupOf} keep={new Set(engines.map(e => e.run_id))} />
            {dupOf.size > 0 && <p className="text-xs text-gray-500 mt-1">Identical text, shown once: {Array.from(dupOf.entries()).map(([a, b]) => `${shortOf(byId.get(a)!)} = ${shortOf(byId.get(b)!)}`).join('; ')}.</p>}
          </Card>
        </div>
      </div>
      {(d.speed || []).length > 0 && <SpeedTable d={d} showDropped={showDropped} />}
      <h2 className="font-semibold text-gray-800 pt-2">The engines on this page</h2>
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3" data-testid="lab-engine-cards">
        {engines.map(e => <EngineCard key={e.run_id} e={e} />)}
      </div>
    </div>
  );
}

function Pick({ engines, value, onChange }: { engines: Engine[]; value: string; onChange: (v: string) => void }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} className="text-sm rounded-md border-gray-300 py-1.5">
      {engines.map(e => <option key={e.run_id} value={e.run_id}>{e.label}</option>)}
    </select>
  );
}

function EngineCard({ e }: { e: Engine }) {
  const failed = e.state !== 'succeeded';
  const r = e.resources || {}, t = e.timing || {};
  return (
    <div className={`rounded-xl border p-3 bg-white shadow-sm ${failed ? 'border-red-300' : 'border-gray-200'}`} data-testid="lab-engine-card">
      <div className="flex items-start gap-2">
        <span className="mt-1 w-2.5 h-2.5 rounded-full shrink-0" style={{ background: colorOf(e) }} />
        <div className="min-w-0">
          <div className="text-sm font-semibold text-gray-900 leading-snug">{e.label}</div>
          <div className="text-[11px] text-gray-500 truncate" title={e.facts?.model}>{e.facts?.model} · {e.facts?.licence}</div>
        </div>
      </div>
      {failed ? (
        <div className="mt-2 text-xs text-red-800 bg-red-50 border border-red-200 rounded p-2 flex gap-1.5">
          <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden /><span><b>Failed</b> ({e.failure?.kind}) after {e.attempts} attempt(s): {e.failure?.message}</span>
        </div>
      ) : (
        <dl className="mt-2 grid grid-cols-2 gap-x-2 gap-y-0.5 text-xs">
          <dt className="text-gray-500">Time on the page</dt><dd className="text-gray-900 tabular-nums">{e.imported ? (t.inference_s != null ? secs(t.inference_s) : 'not measured') : secs(t.inference_s)}</dd>
          <dt className="text-gray-500">GPU memory</dt><dd className="text-gray-900 tabular-nums">{r.peak_gpu_mem_mb != null ? `${(r.peak_gpu_mem_mb / 1024).toFixed(1)} GB` : '—'}</dd>
          <dt className="text-gray-500">Cost of the page</dt><dd className="text-gray-900 tabular-nums" title={e.cost?.basis}>{e.cost ? usd(e.cost.usd) : e.kind === 'ours' ? 'already paid' : '—'}</dd>
          <dt className="text-gray-500">Gives</dt><dd className="text-gray-900">{[e.has_text && 'text', e.has_boxes && 'regions', (e.blocks || []).some(b => b.order != null) && e.has_boxes && 'order'].filter(Boolean).join(' · ') || '—'}</dd>
        </dl>
      )}
      <div className="mt-2 flex flex-wrap gap-1">
        {isDropped(e) && <Chip tone="red">{DROPPED_NOTE}</Chip>}
        {e.warning && <Chip tone="amber" title={e.warning}>see note: {e.warning.slice(0, 40)}…</Chip>}
        {e.imported && <Chip tone="gray" title={e.note}>existing output</Chip>}
        {e.truncated && <Chip tone="red">cut off</Chip>}
        {e.repetition && <Chip tone="amber">repeats itself</Chip>}
        {e.empty && !failed && <Chip tone="amber">no text</Chip>}
        {e.facts?.caveat && <Chip tone="amber" title={e.facts.caveat}>benchmark caveat</Chip>}
      </div>
    </div>
  );
}

function SideBySide({ a, b, focus, setFocus }: { a: Engine; b: Engine; focus: string | null; setFocus: (f: string | null) => void }) {
  const NL = '\u00b6';
  const ops = useMemo(() => wordDiff((a.text || '').replace(/\n/g, ` ${NL} `), (b.text || '').replace(/\n/g, ` ${NL} `)), [a, b]);
  const cnt = (x: string[]) => x.filter(t => t !== NL).length;
  const differing = ops.filter(o => o.op !== 'equal').reduce((s, o) => s + Math.max(cnt(o.a), cnt(o.b)), 0);
  const words = ops.reduce((s, o) => s + Math.max(cnt(o.a), cnt(o.b)), 0);
  const side = (k: 'a' | 'b') => (
    <div dir="rtl" className="ar text-[15px] leading-8 text-gray-900 border border-gray-100 rounded-lg p-3 max-h-[60vh] overflow-auto" data-testid={`lab-side-${k}`}>
      {ops.map((o, i) => {
        const toks = k === 'a' ? o.a : o.b;
        if (o.op === 'equal' && toks.includes(NL)) {
          return <span key={i}>{toks.map((t, j) => t === NL ? <br key={j} /> : <span key={j}>{t} </span>)}</span>;
        }
        const w = toks.filter(t => t !== NL).join(' ');
        if (!w) {
          if (toks.includes(NL)) return <br key={i} />;
          const other = (k === 'a' ? o.b : o.a).filter(t => t !== NL);
          return other.length ? <span key={i} className="mx-0.5 text-gray-300" title="nothing here on this side">∅ </span> : null;
        }
        return o.op === 'equal' ? <span key={i}>{w} </span>
          : <mark key={i} className={`rounded px-0.5 ${k === 'a' ? 'bg-sky-100 text-sky-900' : 'bg-amber-100 text-amber-900'}`}
              title={`the other reading: ${(k === 'a' ? o.b : o.a).filter(t => t !== NL).join(' ') || '(nothing)'}`}>{w} </mark>;
      })}
    </div>
  );
  return (
    <div className="mt-2">
      <p className="text-xs text-gray-500 mb-2">Marked in each reader&apos;s order: {differing} of {words} words ({pct(words ? differing / words : null)}); this includes the reading order effect (the table below gives the order-free figure). Hover a marked word to see the other reading.</p>
      <div className="grid grid-cols-2 gap-3">{side('a')}{side('b')}</div>
    </div>
  );
}

function DisagreeTable({ d, byId, hide, keep }: { d: any; byId: Map<string, Engine>; hide: Map<string, string>; keep: Set<string> }) {
  const rows = ((d.disagreements || []) as { a: string; b: string; raw: number; folded: number; bag_raw?: number; bag_folded?: number }[])
    .filter(r => !hide.has(r.a) && !hide.has(r.b) && keep.has(r.a) && keep.has(r.b));
  if (!rows.length) return <p className="text-sm text-gray-500">Only one reading so far.</p>;
  return (
    <>
      <table className="w-full text-sm" data-testid="lab-disagree">
        <thead><tr className="text-left text-xs text-gray-500"><th className="py-1 font-medium">Reader</th><th className="font-medium">and reader</th>
          <th className="font-medium text-right" title="the two texts as bags of words: order does not count; punctuation ignored; every letter form counts">words differ, any order</th>
          <th className="font-medium text-right" title="the same after folding vowel marks, hamza forms, ى/ي, ة/ه and digits">… folded for search</th>
          <th className="font-medium text-right text-gray-400" title="characters that differ when each text is read in its own order: the gap to the column on the left is what reading order adds">reading order effect</th></tr></thead>
        <tbody>{rows.sort((x, y) => (x.bag_raw ?? x.raw) - (y.bag_raw ?? y.raw)).map((r, i) => {
          const A = byId.get(r.a), B = byId.get(r.b);
          return (
            <tr key={i} className="border-t border-gray-100">
              <td className="py-1.5">{A ? shortOf(A) : r.a}</td><td>{B ? shortOf(B) : r.b}</td>
              <td className="text-right tabular-nums font-medium">{pct(r.bag_raw)}</td><td className="text-right tabular-nums">{pct(r.bag_folded)}</td>
              <td className="text-right tabular-nums text-gray-400">{pct(r.raw)} characters in order</td>
            </tr>);
        })}</tbody>
      </table>
      <p className="text-xs text-gray-500 mt-2">Headline: the share of words that differ when both texts are taken as bags of words (1 − F1 of the word multisets), so a reader that only puts the columns in another order is not counted as reading different words. Apart, in grey: characters that differ in each reader&apos;s own order (edit distance / mean length), the reading order effect. Missing words still count: a word one reader has and the other lacks is a difference in any order. Readers that agree can both be wrong; accuracy comes only from a correction.</p>
    </>
  );
}

function SpeedTable({ d, showDropped }: { d: any; showDropped: boolean }) {
  const rows = ((d.speed || []) as any[]).filter(r => showDropped || !isDropped(r));
  return (
    <Card title="Speed by card" right={<span className="text-xs text-gray-500">every run on this page; the same text = the same fingerprint</span>} pad>
      <table className="w-full text-sm" data-testid="lab-speed">
        <thead><tr className="text-left text-xs text-gray-500"><th className="py-1 font-medium">Engine</th><th className="font-medium">Card</th>
          <th className="font-medium text-right">Seconds on the page</th><th className="font-medium text-right">Peak GPU memory</th>
          <th className="font-medium text-right">Cost of the page</th><th className="font-medium text-right" title="first 12 hex of the text's sha256: equal = identical text">Text fingerprint</th></tr></thead>
        <tbody>{rows.map(r => (
          <tr key={r.run_id} className="border-t border-gray-100">
            <td className="py-1.5">{r.label}</td><td>{r.gpu || '—'}</td>
            <td className="text-right tabular-nums">{secs(r.seconds)}</td>
            <td className="text-right tabular-nums">{r.peak_gpu_mem_mb != null ? `${(r.peak_gpu_mem_mb / 1024).toFixed(1)} GB` : '—'}</td>
            <td className="text-right tabular-nums">{usd(r.usd)}</td>
            <td className="text-right font-mono text-xs text-gray-500">{r.text_sha}</td>
          </tr>))}</tbody>
      </table>
      <p className="text-xs text-gray-500 mt-2">Seconds = the engine&apos;s own time on the page (no set-up, download or model load). &quot;Speed fix&quot;: the vision patch embedding computed as the matrix product it is, instead of PyTorch 2.9&apos;s very slow bf16 3-D convolution; same weights, same text.</p>
    </Card>
  );
}
