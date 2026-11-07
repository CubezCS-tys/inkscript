import React, { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { AlertTriangle, FlaskConical } from 'lucide-react';
import Layout from '../components/Layout';
import { ErrorBox, Tabs } from '../components/Bits';
import Compare from '../components/lab/Compare';
import Correct from '../components/lab/Correct';
import Scores from '../components/lab/Scores';
import { api, enc } from '../lib/api';

const CATEGORY: Record<string, string> = {
  clean_modern_arabic: 'clean modern Arabic', older_print: 'older print', two_columns_footnotes: 'two columns + footnotes',
  tables: 'tables', arabic_maths: 'Arabic maths', mixed_latin: 'Arabic with English / French', western: 'Western control',
};

// The OCR lab (/lab, experiment 75, 2026-11-04): how much of the reading can we do with software we run ourselves?
// One document at a time: the scan with every engine's regions, their texts side by side (where they disagree), the
// owner's fresh correction (saved as revisions), and the scores against it. Reads /desk/api/lab/* (desk/lab.py).

export default function LabPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<any[] | null>(null);
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState('');
  const [showDropped, setShowDropped] = useState(false);
  const tab = (router.query.tab as string) || 'compare';
  const sel = docs && (docs.find(x => `${x.dataset}/${x.page_id}` === router.query.doc) || docs[0]);
  useEffect(() => { api('/lab').then(setDocs).catch(e => setErr(String(e.message || e))); }, []);
  const load = useCallback(() => {
    if (!sel) return;
    setD(null);
    api(`/lab/${enc(sel.dataset)}/${enc(sel.page_id)}`).then(setD).catch(e => setErr(String(e.message || e)));
  }, [sel?.dataset, sel?.page_id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load]);
  const go = (q: Record<string, string>) => router.replace({ pathname: '/lab', query: { ...router.query, ...q } }, undefined, { shallow: true, scroll: false });
  const scan = sel ? `/desk/api/lab/${enc(sel.dataset)}/${enc(sel.page_id)}/scan` : '';
  return (
    <Layout wide>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2"><FlaskConical className="w-5 h-5 text-teal-700" aria-hidden />OCR lab</h1>
          <p className="text-sm text-gray-500 mt-0.5 max-w-3xl">How much of the reading can we do with software we run ourselves? Open readers on a rented GPU beside ours (Azure), one document at a time. Recognition, regions and reading order are scored separately, and only against your own correction.</p>
        </div>
        <div className="flex items-center gap-3">
          <Tabs value={tab} onChange={t => go({ tab: t })} tabs={[['compare', 'Compare'], ['correct', 'Correct'], ['scores', d?.correction ? `Scores (rev ${d.correction.rev_no})` : 'Scores']]} />
        </div>
      </div>
      {docs && docs.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2" role="tablist" aria-label="Document" data-testid="lab-docs">
          {docs.map((x, i) => {
            const on = sel && x.dataset === sel.dataset && x.page_id === sel.page_id;
            return (
              <button key={`${x.dataset}/${x.page_id}`} role="tab" aria-selected={!!on} onClick={() => go({ doc: `${x.dataset}/${x.page_id}` })}
                data-testid={`lab-doc-${x.dataset}`}
                className={`text-left rounded-lg border px-3 py-1.5 text-sm ${on ? 'border-teal-600 bg-teal-50 text-teal-900' : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'}`}>
                <div className="font-medium">Document {x.dataset.replace(/^doc/, '') || i + 1} · {CATEGORY[x.category] || x.category}</div>
                <div className="text-[11px] text-gray-500">{x.page_id.replace(/_p0*/, ', page ')} · {x.corrected ? `corrected (rev ${x.rev_no})` : 'not corrected yet'}</div>
              </button>);
          })}
        </div>)}
      {err && <ErrorBox>{err}</ErrorBox>}
      {docs && docs.length === 0 && <p className="text-sm text-gray-500 mt-4">No document in the lab yet (python -m labocr compare …).</p>}
      {sel && d && (
        <div className="mt-4 space-y-4">
          <DocHead d={d} sel={sel} />
          <label className="inline-flex items-center gap-2 text-xs text-gray-600" data-testid="lab-show-dropped">
            <input type="checkbox" checked={showDropped} onChange={e => setShowDropped(e.target.checked)} className="rounded border-gray-300" />
            show dropped readers (PaddleOCR-VL text, dropped by the owner, 2026-11-04)</label>
          {tab === 'compare' && <Compare d={d} scan={scan} showDropped={showDropped} />}
          {tab === 'correct' && <Correct d={d} scan={scan} dataset={sel.dataset} pageId={sel.page_id}
            onSaved={r => { setD({ ...d, history: r.history, scores: r.scores, correction: { ...(d.correction || {}), rev_no: r.saved.rev_no, revision_id: r.saved.revision_id } }); load(); go({ tab: 'scores' }); }} />}
          {tab === 'scores' && <Scores d={d} scores={d.scores} showDropped={showDropped} />}
        </div>)}
      {sel && !d && !err && <p className="text-sm text-gray-500 mt-4">Loading the page…</p>}
    </Layout>
  );
}

function DocHead({ d, sel }: { d: any; sel: any }) {
  const p = d.page;
  const fails = (d.failures || []) as any[];
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-700">
        <span><b>Document {sel.dataset.replace(/^doc/, '')}</b> · {p.document_id}, page {p.page_number}</span>
        <span className="text-gray-500">{CATEGORY[p.category] || p.category} · {p.width}×{p.height} px at {p.dpi} dpi ({p.renderer})</span>
        {d.sessions?.length > 0 && <span className="text-gray-500">GPU sessions: {d.sessions.map((x: any) => `${x.gpu} $${Number(x.dph).toFixed(3)}/h`).join(' · ')}</span>}
        <span className="text-gray-500">{d.history?.length ? `${d.history.length} correction revision(s), last by ${d.history[d.history.length - 1].actor}` : 'not corrected yet'}</span>
      </div>
      {fails.length > 0 && (
        <div className="text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 flex gap-2" data-testid="lab-failures">
          <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden />
          <div>{fails.map((f, i) => <div key={i}><b>{f.label}</b>, attempt {f.n} ({new Date(f.started_at).toLocaleString('en-GB')}): failed ({f.error_kind}). {f.note || f.error_message}</div>)}</div>
        </div>)}
    </div>
  );
}
