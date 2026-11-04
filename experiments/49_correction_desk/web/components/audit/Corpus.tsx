import React, { useMemo, useState } from 'react';
import { ArrowRight, Wrench, MessageSquarePlus } from 'lucide-react';
import { Card } from '../Bits';
import { KIND, KIND_ORDER, STORED, fieldLabel } from './defs';

// The corpus: how many printed lines landed in a field, the leaks by field and kind (bars: stored vs fell through),
// the fixes ranked, what Gemini returned that did not reach a field, bilingual pairs, platform gaps.

const VERSIONS = ['all', 'v2', 'v3.3', 'v3.5b'];
const pct = (x: number, d = 2) => `${x.toFixed(d)}%`;
const SOFT = new Set(['other', 'unclassified', 'date']);   // body text with no front field to expect: listed last

// simple (show mode, experiment 73): the four headline cards and what fell through, nothing of the workbench below
export default function Corpus({ d, openArticle, simple }: { d: any; openArticle: (stem: string, line?: string) => void; simple?: boolean }) {
  const [journal, setJournal] = useState('all');
  const [ver, setVer] = useState('all');
  const rows = useMemo(() => (d.index as any[]).filter(r => (journal === 'all' || r.journal === journal) && (ver === 'all' || r.prompt === ver)), [d, journal, ver]);
  const journals = useMemo(() => {
    const c: Record<string, number> = {};
    (d.index as any[]).forEach(r => { c[r.journal] = (c[r.journal] || 0) + 1; });
    return Object.entries(c).sort((a, b) => b[1] - a[1]);
  }, [d]);
  const agg = useMemo(() => {
    const b: Record<string, number> = { a: 0, b: 0, c: 0, d: 0 };
    const leak: Record<string, Record<string, number>> = {}, arts: Record<string, Set<string>> = {}, stored: Record<string, number> = {};
    rows.forEach(r => {
      Object.entries(r.buckets || {}).forEach(([k, v]) => { b[k] = (b[k] || 0) + (v as number); });
      Object.entries(r.leaks || {}).forEach(([k, v]) => {
        const [f, kind] = k.split('|');
        (leak[f] ||= {})[kind] = ((leak[f] || {})[kind] || 0) + (v as number);
        (arts[f] ||= new Set()).add(r.stem);
      });
      Object.entries(r.stored || {}).forEach(([f, v]) => { stored[f] = (stored[f] || 0) + (v as number); });
    });
    const total = b.a + b.b + b.c + b.d;
    const fields = Object.keys(leak).map(f => ({ f, leak: leak[f], leaked: Object.values(leak[f]).reduce((s, x) => s + x, 0), stored: stored[f] || 0, articles: arts[f].size }))
      .sort((p, q) => Number(SOFT.has(p.f)) - Number(SOFT.has(q.f)) || q.articles - p.articles || q.leaked - p.leaked);
    return { b, total, fields };
  }, [rows]);
  const acc = agg.total ? (100 * (agg.b.a + agg.b.c)) / agg.total : 0;
  const v = d.verify;
  return (
    <div className="space-y-4">
      {!simple && <div className="flex flex-wrap items-center gap-2 text-sm">
        <label className="flex items-center gap-1.5 text-gray-600">Journal
          <select value={journal} onChange={e => setJournal(e.target.value)} className="rounded-lg border-gray-300 text-sm py-1" data-testid="au-journal">
            <option value="all">All journals ({d.index.length} articles)</option>
            {journals.map(([j, n]) => <option key={j} value={j}>{j} ({n})</option>)}
          </select>
        </label>
        <div className="flex rounded-lg border border-gray-200 p-0.5 bg-white" role="group" aria-label="Prompt version">
          {VERSIONS.map(x => <button key={x} onClick={() => setVer(x)} aria-pressed={ver === x} data-testid={`au-ver-${x}`}
            className={`px-2.5 py-1 rounded-md text-xs ${ver === x ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-50'}`}>{x === 'all' ? 'All prompts' : `prompt ${x}`}</button>)}
        </div>
        <span className="text-xs text-gray-500 ml-auto">Release {d.release} · audit of {d.made}</span>
      </div>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Big label="Printed lines accounted for" value={pct(acc)} sub={`${(agg.b.a + agg.b.c).toLocaleString()} of ${agg.total.toLocaleString()} lines in a field or set aside as not article text`} tone="teal" />
        <Big label="Lines that fell through" value={(agg.b.b + agg.b.d).toLocaleString()} sub={`${agg.b.b.toLocaleString()} only as generic text · ${agg.b.d.toLocaleString()} nowhere`} tone="red" />
        <Big label="Articles audited" value={rows.length.toLocaleString()} sub={`${rows.filter(r => r.leak_lines).length} with at least one line that fell through`} tone="gray" />
        {!(simple && !v) && <Big label="False alarms (checked on the scans)" value={v ? pct(v.false_alarm_rate, 1) : '—'} sub={v ? `${v.false} of ${v.checked} leaks looked at on the page images` : 'not checked yet'} tone="gray" />}
      </div>

      <Card title="What fell through, field by field" right={<Legend />}>
        <p className="text-xs text-gray-500 -mt-1 mb-3">Each bar is one kind of printed text: the teal part is lines stored in that field, the rest is lines that only reached generic text (or nowhere), coloured by why. Sorted by the number of articles touched; body text with no field to expect comes last.</p>
        <div className="space-y-1.5" data-testid="au-bars">
          {agg.fields.slice(0, 24).map((r, i) => {
            const tot = r.stored + r.leaked;
            return (
              <div key={r.f} className="grid grid-cols-[minmax(10rem,15rem)_1fr_14rem] items-center gap-3 au-rise" style={{ animationDelay: `${i * 35}ms` }}>
                <div className="text-sm text-gray-800 truncate" title={fieldLabel(r.f)}>{fieldLabel(r.f)}</div>
                <div className="h-5 rounded-md bg-gray-100 overflow-hidden flex au-bar" title={`${r.stored} stored · ${r.leaked} fell through`}>
                  {r.stored > 0 && <div style={{ width: `${(100 * r.stored) / tot}%`, background: STORED, opacity: 0.85 }} />}
                  {KIND_ORDER.filter(k => r.leak[k]).map(k => <div key={k} style={{ width: `${(100 * r.leak[k]) / tot}%`, background: KIND[k].color }} title={`${KIND[k].label}: ${r.leak[k]} lines`} />)}
                </div>
                <div className="text-xs text-gray-600 tabular-nums whitespace-nowrap"><b className="text-red-700">{r.leaked}</b> lost · {r.articles} articles{r.stored ? <span className="text-gray-400"> · {r.stored} kept</span> : null}</div>
              </div>
            );
          })}
        </div>
      </Card>

      {!simple && <>
      <Card title="The fixes, ranked" right={<span className="text-xs text-gray-500">Code fixes are free (rebuild from the saved answers); prompt additions go in before the next journals are read</span>}>
        <ol className="grid md:grid-cols-2 gap-3">
          {(d.fixes as any[]).map((f, i) => <FixCard key={f.id} f={f} i={i} />)}
        </ol>
      </Card>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Gemini returned it, our code did not keep it">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-gray-500"><th className="font-medium pb-1">Answer key</th><th className="font-medium text-right">returned</th><th className="font-medium text-right">not in its field</th><th className="font-medium text-right">articles</th></tr></thead>
            <tbody>
              {(d.answers as any[]).filter(a => a.lost > 0).slice(0, 12).map(a => {
                const art = Math.max(a.flattened?.articles || 0, a.dropped?.articles || 0);
                return (
                  <tr key={a.key} className="border-t border-gray-100">
                    <td className="py-1.5 font-mono text-[12px] text-gray-800">{a.key}</td>
                    <td className="text-right tabular-nums text-gray-600">{a.total}</td>
                    <td className="text-right tabular-nums text-red-700 font-medium">{a.lost}</td>
                    <td className="text-right tabular-nums text-gray-600">{art}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="text-xs text-gray-500 mt-2">«not in its field» = only inside a generic front-matter block (flattened) or nowhere (dropped).</p>
        </Card>
        <Card title="Printed in two scripts: are both kept, and linked?">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-gray-500"><th className="font-medium pb-1">Pair</th><th className="font-medium text-right">printed both</th><th className="font-medium text-right">both in JATS</th><th className="font-medium text-right">linked</th><th className="font-medium text-right">both in platform</th></tr></thead>
            <tbody>
              {['title', 'names', 'affiliations', 'positions', 'abstracts', 'keywords'].map(k => {
                const x = (d.bilingual[k] || {})[ver === 'all' ? 'all' : ver] || {};
                const p = x.printed_both || 0;
                const cell = (n?: number) => <td className={`text-right tabular-nums ${p && (n || 0) < p ? 'text-red-700 font-medium' : 'text-gray-700'}`}>{n || 0}</td>;
                return (
                  <tr key={k} className="border-t border-gray-100">
                    <td className="py-1.5 text-gray-800 capitalize">{k}</td>
                    <td className="text-right tabular-nums text-gray-700">{p}</td>{cell(x.jats_both)}{cell(x.linked)}{cell(x.platform_both)}
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="text-xs text-gray-500 mt-2">Articles where both an Arabic and a Latin form are printed (from the answer and the lines). Red: some of them lost one form.</p>
        </Card>
      </div>

      <Card title="From JATS to the platform">
        <div className="grid md:grid-cols-2 gap-x-8 text-sm">
          {(d.platform as any[]).filter(p => p.jats).map(p => (
            <div key={p.element} className="flex items-center justify-between border-t border-gray-100 py-1">
              <span className="text-gray-700 truncate">{p.element}</span>
              <span className="tabular-nums text-gray-600">{p.jats.toLocaleString()} <ArrowRight className="inline w-3 h-3 text-gray-400" /> {p.platform.toLocaleString()}
                {p.articles_short ? <b className="text-red-700 ml-2">{p.articles_short} articles short</b> : null}</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-2">JATS elements of the current masters against the rows the platform holds for them. Platform columns no current article fills: {(d.columns as any[]).filter(c => !c.filled).length} (listed in the experiment's README).</p>
      </Card>

      <Card title="Articles with the most lines that fell through">
        <div className="flex flex-wrap gap-1.5">
          {[...rows].sort((a, b) => b.leak_lines - a.leak_lines).slice(0, 24).filter(r => r.leak_lines).map(r => (
            <button key={r.stem} onClick={() => openArticle(r.stem)} className="text-xs rounded-full border border-gray-200 bg-white px-2.5 py-1 hover:bg-gray-50 font-mono text-gray-700">
              {r.stem} <span className="text-red-700 font-sans font-medium">{r.leak_lines}</span></button>
          ))}
        </div>
      </Card>
      </>}
    </div>
  );
}

function Big({ label, value, sub, tone }: { label: string; value: React.ReactNode; sub: string; tone: 'teal' | 'red' | 'gray' }) {
  const c = tone === 'teal' ? 'text-teal-800' : tone === 'red' ? 'text-red-700' : 'text-gray-900';
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm px-4 py-3 au-rise">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-3xl font-semibold tabular-nums mt-0.5 ${c}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1 leading-snug">{sub}</div>
    </div>
  );
}

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-600">
      <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm" style={{ background: STORED }} />stored in its field</span>
      {KIND_ORDER.map(k => <span key={k} className="flex items-center gap-1" title={KIND[k].note}><i className="w-3 h-3 rounded-sm" style={{ background: KIND[k].color }} />{KIND[k].label}</span>)}
    </div>
  );
}

function evidenceText(ev: any): string[] {
  const out: string[] = [];
  Object.entries(ev || {}).forEach(([k, v]: [string, any]) => {
    if (v && typeof v === 'object' && 'lines' in v && typeof v.lines === 'number') out.push(`${k === 'lines' ? '' : k + ': '}${v.lines} lines in ${v.articles} articles`);
    else if (v && typeof v === 'object' && 'values' in v) out.push(`${v.values} answer values in ${v.articles} articles`);
    else if (k === 'lines' && typeof v === 'number') out.push(`${v} lines in ${ev.articles} articles`);
  });
  return out;
}

function FixCard({ f, i }: { f: any; i: number }) {
  const prompt = f.kind === 'prompt';
  return (
    <li className={`rounded-xl border p-3.5 au-rise ${prompt ? 'border-amber-300 bg-amber-50/40' : 'border-gray-200 bg-white'}`} style={{ animationDelay: `${i * 40}ms` }}>
      <div className="flex items-start gap-2">
        <span className={`shrink-0 mt-0.5 inline-flex items-center gap-1 text-[11px] font-semibold rounded-full px-2 py-0.5 ${prompt ? 'bg-amber-100 text-amber-900' : 'bg-teal-50 text-teal-800'}`}>
          {prompt ? <MessageSquarePlus className="w-3 h-3" /> : <Wrench className="w-3 h-3" />}{f.id} · {prompt ? 'prompt, before gate 2' : 'code, free'}</span>
        <h3 className="text-sm font-semibold text-gray-900 leading-snug">{f.title}</h3>
      </div>
      <p className="text-[13px] text-gray-700 mt-1.5 leading-relaxed">{f.what}</p>
      <div className="flex flex-wrap gap-1 mt-2">
        {evidenceText(f.evidence).map(t => <span key={t} className="text-[11px] rounded-full bg-gray-100 text-gray-700 px-2 py-0.5">{t}</span>)}
      </div>
      <p className="text-[11px] text-gray-500 font-mono mt-2 leading-snug break-words">{f.where}</p>
    </li>
  );
}
