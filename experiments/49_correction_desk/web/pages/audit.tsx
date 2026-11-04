import React, { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { Search, ShieldCheck } from 'lucide-react';
import Layout from '../components/Layout';
import { ErrorBox } from '../components/Bits';
import Corpus from '../components/audit/Corpus';
import Flow, { FlowRow } from '../components/audit/Flow';
import ScanView, { Line } from '../components/audit/ScanView';
import { KIND, fieldLabel, geminiLabel } from '../components/audit/defs';
import { api, enc, isArabic } from '../lib/api';
import { useShowMode } from '../lib/showmode';

// Nothing lost (/audit, 2026-11-02, experiment 61): does everything printed, and everything Gemini returned, end up
// in a proper field? The corpus view (leaks by field and kind, the fixes ranked) and one article's flow (Azure lines
// → Gemini's roles → JATS fields → platform records), each stream clickable down to its lines on the scan.
// Read-only: GET /desk/api/audit and /desk/api/audit/articles/{stem} (desk/audit.py; precomputed by experiment 61).

const DEFAULT_STEM = '0130-018-072-003';

export default function AuditPage() {
  const router = useRouter();
  const tab = router.query.tab === 'article' ? 'article' : router.query.tab === 'corpus' ? 'corpus' : (router.query.stem ? 'article' : 'corpus');
  const stem = typeof router.query.stem === 'string' ? router.query.stem : DEFAULT_STEM;
  const [sum, setSum] = useState<any>(null);
  const [err, setErr] = useState('');
  const showMode = useShowMode();
  useEffect(() => { api('/audit').then(setSum).catch(e => setErr(String(e.message || e))); }, []);
  const go = (q: Record<string, string>) => router.replace({ pathname: '/audit', query: q }, undefined, { shallow: true, scroll: false });
  const openArticle = (s: string) => { go({ tab: 'article', stem: s }); window.scrollTo({ top: 0 }); };
  return (
    <Layout wide>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2"><ShieldCheck className="w-5 h-5 text-teal-700" aria-hidden />Nothing lost</h1>
          <p className="text-sm text-gray-500 mt-0.5 max-w-3xl">{showMode
            ? <>Every line printed on the scanned articles{sum ? <> ({sum.n_articles?.toLocaleString?.('en') ?? sum.n_articles} of them)</> : null}, followed from the scan to the article file and the index: did it land in a proper field? Red is what fell through.</>
            : <>Every line printed on all the scanned articles of the current release{sum ? <> ({sum.n_articles?.toLocaleString?.('en') ?? sum.n_articles})</> : null}, followed from Azure&apos;s reading through Gemini&apos;s answer and the JATS master to the platform: did it land in a proper field? Red is what fell through; orange is what the prompt does not yet ask for.
              {' '}Articles built from the publisher&apos;s Word file have no scan lines and are not in this audit.</>}</p>
        </div>
        <div className="flex rounded-lg border border-gray-200 p-0.5 bg-white" role="tablist">
          {(['corpus', 'article'] as const).map(t => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => go(t === 'article' ? { tab: t, stem } : { tab: t })} data-testid={`au-tab-${t}`}
              className={`px-3.5 py-1.5 rounded-md text-sm font-medium ${tab === t ? 'bg-teal-700 text-white' : 'text-gray-600 hover:bg-gray-50'}`}>
              {t === 'corpus' ? (sum?.n_articles ? `All ${Number(sum.n_articles).toLocaleString('en')} articles` : 'All articles') : 'One article'}</button>
          ))}
        </div>
      </div>
      {err && <ErrorBox>{err}</ErrorBox>}
      {!sum && !err && <p className="text-sm text-gray-500">Loading the audit…</p>}
      {sum && tab === 'corpus' && <Corpus d={sum} openArticle={openArticle} simple={showMode} />}
      {sum && tab === 'article' && <Article stem={stem} sum={sum} onPick={s => go({ tab: 'article', stem: s })} />}
    </Layout>
  );
}

function Article({ stem, sum, onPick }: { stem: string; sum: any; onPick: (s: string) => void }) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState('');
  const [metric, setMetric] = useState<'lines' | 'words'>('lines');
  const [sel, setSel] = useState<{ key: string; flows: number[]; label: string } | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const showMode = useShowMode();
  useEffect(() => {
    setD(null); setErr(''); setSel(null); setFocus(null);
    api(`/audit/articles/${enc(stem)}`).then(x => {
      setD(x);
      const leakIdx = (x.flows as FlowRow[]).map((f, i) => (f.bucket === 'b' || f.bucket === 'd' ? i : -1)).filter(i => i >= 0);
      if (leakIdx.length) setSel({ key: 'leaks', flows: leakIdx, label: 'Everything that fell through' });
      const first = (x.leaks as any[]).find(l => l.field === 'affiliation' && l.kind === 'mapping') || x.leaks[0];
      setFocus(first ? first.id : null);
    }).catch(e => setErr(String(e.message || e)));
  }, [stem]);
  const byId = useMemo(() => new Map<string, Line>((d?.lines || []).map((l: Line) => [l.id, l])), [d]);
  const selLines: Line[] = useMemo(() => {
    if (!d || !sel) return [];
    const ids = new Set<string>();
    sel.flows.forEach(i => (d.flows[i].refs as string[]).forEach(r => ids.add(r)));
    return Array.from(ids).map(i => byId.get(i)).filter(Boolean).sort((a: any, b: any) => a.page - b.page || a.n - b.n) as Line[];
  }, [d, sel, byId]);
  const leakOf = useMemo(() => new Map<string, any>((d?.leaks || []).map((l: any) => [l.id, l])), [d]);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-gray-600">
          {!showMode && <span className="font-mono text-gray-900">{stem}</span>}
          {d && <>{!showMode && <> · prompt {d.prompt} · </>}{d.totals.lines_all.toLocaleString()} lines on {d.pages.length} pages · <b className={d.leaks.length ? 'text-red-700' : 'text-teal-800'}>{d.leaks.length} fell through</b></>}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-gray-200 p-0.5 text-xs bg-white" role="group" aria-label="Stream width">
            {(['lines', 'words'] as const).map(m => <button key={m} onClick={() => setMetric(m)} aria-pressed={metric === m}
              className={`px-2.5 py-1 rounded-md ${metric === m ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-50'}`}>by {m}</button>)}
          </div>
          <Picker stem={stem} sum={sum} onPick={onPick} />
        </div>
      </div>
      {err && <ErrorBox>{err}</ErrorBox>}
      {!d && !err && <p className="text-sm text-gray-500">Loading the article…</p>}
      {d && (
        <>
          <section className="bg-white rounded-xl border border-gray-200 shadow-sm px-5 pt-4 pb-3" data-testid="au-flow">
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
              <h2 className="font-semibold text-gray-800">Where this article&apos;s lines went</h2>
              <p className="text-xs text-gray-500">Stream width = {metric}. Click a stream or a box to see its lines on the scan.{sel && <> Showing: <b className="text-gray-700">{sel.label}</b> <button className="underline ml-1" onClick={() => { setSel(null); setFocus(null); }}>clear</button></>}</p>
            </div>
            <Flow key={stem} flows={d.flows} metric={metric} selected={sel?.key || null}
              onSelect={(key, flows, label) => { setSel({ key, flows, label }); setFocus(null); }} />
          </section>
          <div className="grid xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-4 items-start">
            <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 space-y-2" data-testid="au-leaks">
              <h2 className="font-semibold text-gray-800">{sel ? sel.label : 'Lines that fell through'} <span className="text-gray-500 font-normal text-sm">· {sel ? selLines.length : d.leaks.length} lines</span></h2>
              <div className="space-y-2 overflow-auto pr-1" style={{ maxHeight: 'clamp(420px, calc(100vh - 300px), 760px)' }}>
                {(sel ? selLines : (d.leaks as any[]).map((l: any) => byId.get(l.id)).filter(Boolean) as Line[]).slice(0, 250).map(l => {
                  const lk = leakOf.get(l.id);
                  return <LineCard key={l.id} l={l} lk={lk} on={focus === l.id} onClick={() => setFocus(l.id)} />;
                })}
                {!d.leaks.length && !sel && <p className="text-sm text-teal-800">Every printed line of this article is in a field or set aside as not article text.</p>}
              </div>
            </section>
            <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <ScanView stem={stem} pageSize={d.page_size} lines={sel ? selLines : []} focus={focus} />
            </section>
          </div>
          {!showMode && d.answer.values.length > 0 && (
            <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <h2 className="font-semibold text-gray-800 mb-2">Values Gemini returned that are not in their field</h2>
              <table className="w-full text-sm">
                <tbody>
                  {(d.answer.values as any[]).slice(0, 40).map((v, i) => (
                    <tr key={i} className="border-t border-gray-100 align-top">
                      <td className="py-1.5 pr-3 font-mono text-[12px] text-gray-700 whitespace-nowrap">{v.key}</td>
                      <td className={`py-1.5 pr-3 ${isArabic(v.value) ? 'ar' : ''}`}>{v.value}</td>
                      <td className="py-1.5 pr-3 whitespace-nowrap"><span className={`text-xs font-medium ${v.status === 'dropped' || v.status === 'flattened' ? 'text-red-700' : 'text-gray-600'}`}>{v.status === 'flattened' ? 'generic text only' : v.status === 'elsewhere' ? `in ${fieldLabel(v.where)}` : v.status}</span></td>
                      <td className="py-1.5 text-xs text-gray-500">{v.reason || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function LineCard({ l, lk, on, onClick }: { l: Line; lk: any; on: boolean; onClick: () => void }) {
  const leak = l.bucket === 'b' || l.bucket === 'd';
  const k = lk ? KIND[lk.kind] : null;
  return (
    <button onClick={onClick} data-testid={`au-line-${l.id}`}
      className={`w-full text-left rounded-lg border px-3 py-2 transition-colors ${on ? 'border-gray-900 bg-gray-50' : 'border-gray-200 hover:bg-gray-50'}`}>
      <div className="flex items-center justify-between gap-2 text-[11px] text-gray-500">
        <span className="font-mono">p{l.page} · line {l.n}</span>
        <span>Gemini: {geminiLabel(l.gemini)}</span>
      </div>
      <div className={`text-[14px] text-gray-900 mt-0.5 ${isArabic(l.text) ? 'ar' : ''}`} dir="auto">{l.text}</div>
      {leak && lk ? (
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="rounded-full px-2 py-0.5 font-medium text-white" style={{ background: k?.color }}>{k?.label}</span>
          <span className="text-gray-700">should be: <b>{fieldLabel(lk.field)}</b></span>
          <span className="text-gray-500">· {lk.why}</span>
        </div>
      ) : (
        <div className="mt-1 text-xs text-gray-600">{l.bucket === 'c' ? 'not article text' : `in field: ${fieldLabel(l.field)}`}</div>
      )}
    </button>
  );
}

function Picker({ stem, sum, onPick }: { stem: string; sum: any; onPick: (s: string) => void }) {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [hits, setHits] = useState<any[]>([]);
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => {
      api(`/articles?limit=12${q.trim() ? `&q=${enc(q.trim())}` : ''}`).then(x => setHits(x.articles || [])).catch(() => setHits([]));
    }, 220);
    return () => clearTimeout(t);
  }, [q, open]);
  const leaks = new Map<string, number>((sum.index as any[]).map(r => [r.stem, r.leak_lines]));
  return (
    <div className="relative">
      <label className="relative block">
        <span className="sr-only">Choose an article</span>
        <Search className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" aria-hidden />
        <input value={q} onChange={e => setQ(e.target.value)} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 180)}
          placeholder={stem} dir="auto" data-testid="au-pick" className="pl-8 pr-2 py-1.5 w-72 rounded-lg border-gray-300 text-sm" />
      </label>
      {open && hits.length > 0 && (
        <ul className="absolute right-0 z-30 mt-1 w-[28rem] max-h-80 overflow-auto bg-white border border-gray-200 rounded-xl shadow-lg py-1">
          {hits.map(h => (
            <li key={h.stem}><button onMouseDown={e => e.preventDefault()} onClick={() => { setOpen(false); setQ(''); onPick(h.stem); }} className="w-full text-left px-3 py-1.5 hover:bg-gray-50">
              <div className={`text-sm text-gray-900 truncate ${isArabic(h.title) ? 'ar' : ''}`}>{h.title || h.stem}</div>
              <div className="text-[11px] text-gray-500 font-mono">{h.stem}{leaks.has(h.stem) ? <span className={leaks.get(h.stem) ? 'text-red-700' : 'text-teal-700'}> · {leaks.get(h.stem)} fell through</span> : ''}</div>
            </button></li>
          ))}
        </ul>
      )}
    </div>
  );
}
