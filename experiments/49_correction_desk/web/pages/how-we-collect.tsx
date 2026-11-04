import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { BookOpen, Check, HelpCircle, Tag, Search, ExternalLink, ChevronRight, AlertTriangle } from 'lucide-react';
import Layout from '../components/Layout';
import { Btn, Card, Chip, Empty, ErrorBox, actorName, when } from '../components/Bits';
import { api, enc, hrefOf, isArabic } from '../lib/api';
import { useApi } from '../lib/me';

// The field guide (owner, 2026-10-23): how every Explorer field is collected, so the owner can read it, agree, or say a
// label is wrong. The entries are desk/field_guide/<tab>.json (traced by reading the code); reviews are stored in the
// Desk's PostgreSQL (field_reviews, append-only) by desk/field_guide.py.

type Example = { stem?: string; id?: string; value?: string; note?: string } | string;
type Entry = {
  key: string; label: string; group: string; meaning: string; source: string; how: string[]; exact: string[];
  examples: Example[]; fill: string; caveats: string[]; label_check: { ok: boolean; why: string; better?: string };
};
type Review = { review_id: number; field_key: string; verdict: 'agree' | 'wrong_label' | 'question'; comment: string | null;
  proposed_label: string | null; author: string; author_name: string; created_at: string; n_reviews?: number };
type Column = { key: string; field_key: string; label: string; group: string; type: string; src: string; entry: Entry | null; review: Review | null };
type TabT = { tab: string; label: string; about: string; explore_key: string; written: boolean; n_columns: number; n_entries: number; columns: Column[] };
type Guide = { tabs: TabT[]; sources: string[]; counts: Record<string, number>; n_columns: number; n_entries: number };

const SRC: Record<string, { short: string; chip: string; box: string; dot: string }> = {
  'printed page (Azure words)': { short: 'Printed page', chip: 'bg-sky-50 text-sky-800 border-sky-200', box: 'border-sky-400', dot: 'bg-sky-500' },
  'AI reading (Gemini)': { short: 'AI reading', chip: 'bg-violet-50 text-violet-800 border-violet-200', box: 'border-violet-400', dot: 'bg-violet-500' },
  'code rule': { short: 'Code rule', chip: 'bg-slate-100 text-slate-700 border-slate-300', box: 'border-slate-400', dot: 'bg-slate-500' },
  'catalogue (MARC)': { short: 'Catalogue', chip: 'bg-teal-50 text-teal-800 border-teal-200', box: 'border-teal-400', dot: 'bg-teal-500' },
  'linker': { short: 'Linker', chip: 'bg-indigo-50 text-indigo-700 border-indigo-200', box: 'border-indigo-400', dot: 'bg-indigo-500' },
  'corrector': { short: 'Corrector', chip: 'bg-green-50 text-green-800 border-green-200', box: 'border-green-500', dot: 'bg-green-600' },
  'counted': { short: 'Counted', chip: 'bg-stone-50 text-stone-700 border-stone-300', box: 'border-stone-400', dot: 'bg-stone-400' },
  'several': { short: 'Several', chip: 'bg-orange-50 text-orange-800 border-orange-200', box: 'border-orange-400', dot: 'bg-orange-500' },
};
const srcOf = (s: string) => SRC[s] || SRC['several'];

// the pipeline in plain words, one box per source of a value (the colours are the chips' colours)
const STEPS: [string, string, string][] = [
  ['printed page (Azure words)', 'The printed page', 'Azure reads every word on the scan, with its box and how sure it is. The text is always these words; nobody retypes it.'],
  ['AI reading (Gemini)', 'The AI reading', 'Gemini looks at the page images and Azure\'s numbered lines and says, by line number, what each line is (title, byline, paragraph, note, reference …). Names, affiliations and a few other strings it copies out itself.'],
  ['code rule', 'Code rules', 'Our code checks and repairs what can be decided safely, the same way every time (a value must be found in the print, page ranges, Hijri years, look-alike letters), and writes the article files.'],
  ['catalogue (MARC)', 'The catalogue', 'Mandumah\'s catalogue record of the article gives its own values: kept beside the printed ones, and used where the page gives none.'],
  ['linker', 'The linker', 'Joins things across articles: the same person, the same institution, the same cited work, and who cites whom.'],
  ['corrector', 'Correctors', 'People on the Desk confirm or correct those joins; every decision is kept and applied in the next release.'],
];

const T = {
  title: 'How we collect every field',
  lead: 'For each column of the Explorer: what the value is, where it comes from, step by step from the scan, real examples, its limits, and whether its label says exactly what the data is. Read a field, then say whether you agree.',
  search: 'Search labels, meanings, steps, caveats…',
  onlyWrong: 'Only fields whose label may be wrong',
  onlyUnreviewed: 'Not reviewed yet',
  allSources: 'All sources',
  writing: 'Being written: this tab\'s fields are being traced and will appear here.',
  noEntry: 'Being written.',
  meaning: 'What it is', how: 'How it is collected', examples: 'Real examples', limits: 'Limits', exact: 'Exact details (code, prompt, MARC, SQL)',
  inExplorer: 'See in the Explorer', fill: 'Filled', labelWrong: 'The label may be wrong', propose: 'Proposed label',
  agree: 'Agree', wrong: 'Wrong label', question: 'Question', comment: 'Comment (optional for Agree)', yourLabel: 'Your label (optional)',
  send: 'Save review', cancel: 'Cancel', latest: 'Latest review', history: 'All reviews', none: 'Not reviewed yet.',
  agreed: 'Agreed', wrongs: 'Wrong label', questions: 'Questions', notReviewed: 'Not reviewed', written: 'fields written',
  groups: 'Groups', shown: 'shown', counted: 'Counted', several: 'Several',
};
const VERDICT: Record<string, { label: string; tone: 'green' | 'red' | 'amber' }> = {
  agree: { label: T.agreed, tone: 'green' }, wrong_label: { label: T.wrongs, tone: 'red' }, question: { label: 'Question', tone: 'amber' },
};

const Txt: React.FC<{ s?: string | null; className?: string }> = ({ s, className = '' }) => {
  if (!s) return null;
  const ar = isArabic(s);
  if (ar) return <span dir="rtl" className={`ar text-[15px] ${className}`}>{s}</span>;
  // an English sentence quoting Arabic «…»: each quote isolated, so its digits and words keep their order
  const parts = s.split(/(«[^»]*»)/);
  return <span dir="auto" className={className}>{parts.map((p, i) => (p.startsWith('«') ? <bdi key={i}>{p}</bdi> : p))}</span>;
};

function exampleHref(tab: string, ex: Example): string | null {
  if (typeof ex === 'string') return null;
  if (ex.id) {
    if (tab === 'references') return hrefOf(`mention:${ex.id}`);
    if (tab === 'persons') return `/persons/${enc(ex.id)}`;
    if (tab === 'works') return `/works/${enc(ex.id)}`;
    if (tab === 'institutions') return `/institutions/${enc(ex.id)}`;
    if (tab === 'journals') return `/journals/${enc(ex.id)}`;
  }
  if (ex.stem) return `/articles/${enc(ex.stem)}`;
  return null;
}

const SourceChip: React.FC<{ s: string }> = ({ s }) => (
  <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium border whitespace-nowrap ${srcOf(s).chip}`} title={s}>
    <span className={`w-1.5 h-1.5 rounded-full ${srcOf(s).dot}`} aria-hidden />{srcOf(s).short}
  </span>
);

const Pipeline: React.FC = () => (
  <Card title="From the scan to a value, in plain words" right={<span className="text-xs text-gray-500">each box's colour is the colour of its chip on the fields below</span>}>
    <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6" aria-label="the pipeline">
      {STEPS.map(([s, title, text], i) => (
        <li key={s} className={`relative rounded-lg border border-gray-200 border-t-4 ${srcOf(s).box} bg-white p-3`}>
          <div className="flex items-center gap-1.5 text-sm font-semibold text-gray-800">
            <span className="text-xs text-gray-400 tabular-nums">{i + 1}</span>{title}
          </div>
          <p className="text-xs text-gray-600 mt-1 leading-5">{text}</p>
          {i < STEPS.length - 1 && <ChevronRight className="hidden lg:block absolute -right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-300 z-10" aria-hidden />}
        </li>
      ))}
    </ol>
    <p className="text-xs text-gray-600 mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="inline-flex items-center gap-1.5"><SourceChip s="counted" /> a number counted from other fields</span>
      <span className="inline-flex items-center gap-1.5"><SourceChip s="several" /> the shown value is chosen among several sources (the field says which wins)</span>
    </p>
  </Card>
);

const ReviewBox: React.FC<{ col: Column; onSaved: (r: Review) => void }> = ({ col, onSaved }) => {
  const [mode, setMode] = useState<null | 'agree' | 'wrong_label' | 'question'>(null);
  const [comment, setComment] = useState('');
  const [label, setLabel] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [hist, setHist] = useState<Review[] | null>(null);
  const r = col.review;
  const save = async () => {
    setBusy(true); setErr('');
    try {
      const out = await api<Review>('/field-guide/reviews', { json: { field_key: col.field_key, verdict: mode, comment, proposed_label: mode === 'wrong_label' ? label : null } });
      onSaved({ ...out, n_reviews: (r?.n_reviews || 0) + 1 });
      setMode(null); setComment(''); setLabel(''); setHist(null);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const loadHist = async () => { try { setHist(await api<Review[]>(`/field-guide/reviews?field=${enc(col.field_key)}`)); } catch (e: any) { setErr(e.message); } };
  const btn = (v: 'agree' | 'wrong_label' | 'question', Icon: any, text: string, on: string) => (
    <button type="button" onClick={() => setMode(mode === v ? null : v)} aria-pressed={mode === v} data-testid={`review-${v}`}
      className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border inline-flex items-center gap-1.5 ${mode === v ? on : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'}`}>
      <Icon className="w-3.5 h-3.5" aria-hidden />{text}
    </button>
  );
  return (
    <div className="border-t border-gray-100 pt-3 mt-1 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {btn('agree', Check, T.agree, 'bg-green-600 border-green-600 text-white')}
        {btn('wrong_label', Tag, T.wrong, 'bg-red-600 border-red-600 text-white')}
        {btn('question', HelpCircle, T.question, 'bg-amber-500 border-amber-500 text-white')}
        <div className="ml-auto text-xs text-gray-600 flex flex-wrap items-center gap-1.5" data-testid="latest-review">
          {r ? (<>
            <span className="text-gray-500">{T.latest}:</span>
            <Chip tone={VERDICT[r.verdict].tone}>{VERDICT[r.verdict].label}</Chip>
            <span>by {r.author_name || actorName(r.author)} · {when(r.created_at)}</span>
            {(r.n_reviews || 0) > 1 && <button className="text-indigo-700 hover:underline" onClick={loadHist}>{T.history} ({r.n_reviews})</button>}
          </>) : <span className="text-gray-400">{T.none}</span>}
        </div>
      </div>
      {r && (r.comment || r.proposed_label) && (
        <div className="text-xs text-gray-700 bg-gray-50 rounded-lg px-3 py-2 space-y-0.5">
          {r.proposed_label && <div><span className="text-gray-500">{T.propose}:</span> <Txt s={r.proposed_label} className="font-medium" /></div>}
          {r.comment && <div className="whitespace-pre-wrap" dir="auto">{r.comment}</div>}
        </div>
      )}
      {hist && (
        <ul className="text-xs text-gray-700 divide-y divide-gray-100 border border-gray-100 rounded-lg">
          {hist.map(h => (
            <li key={h.review_id} className="px-3 py-1.5 flex flex-wrap gap-x-2">
              <Chip tone={VERDICT[h.verdict].tone}>{VERDICT[h.verdict].label}</Chip>
              <span className="text-gray-500">{h.author_name || actorName(h.author)} · {when(h.created_at)}</span>
              {h.proposed_label && <span>→ <Txt s={h.proposed_label} /></span>}
              {h.comment && <span className="w-full whitespace-pre-wrap" dir="auto">{h.comment}</span>}
            </li>
          ))}
        </ul>
      )}
      {mode && (
        <div className="space-y-2">
          {mode === 'wrong_label' && (
            <input value={label} onChange={e => setLabel(e.target.value)} placeholder={col.entry?.label_check?.better ? `${T.yourLabel} — e.g. ${col.entry.label_check.better}` : T.yourLabel}
              dir="auto" className="w-full rounded-lg border-gray-300 text-sm" maxLength={200} aria-label={T.yourLabel} />
          )}
          <textarea value={comment} onChange={e => setComment(e.target.value)} rows={2} dir="auto" maxLength={4000}
            placeholder={mode === 'question' ? 'Your question' : T.comment} aria-label="comment"
            className="w-full rounded-lg border-gray-300 text-sm" />
          {err && <ErrorBox>{err}</ErrorBox>}
          <div className="flex gap-2">
            <Btn kind="primary" small disabled={busy || (mode === 'question' && !comment.trim())} onClick={save} data-testid="review-save">{T.send}</Btn>
            <Btn small onClick={() => { setMode(null); setErr(''); }}>{T.cancel}</Btn>
          </div>
        </div>
      )}
      {!mode && err && <ErrorBox>{err}</ErrorBox>}
    </div>
  );
};

const FieldCard: React.FC<{ tab: TabT; col: Column; onSaved: (fk: string, r: Review) => void }> = ({ tab, col, onSaved }) => {
  const e = col.entry;
  const exploreHref = `/explore?e=${enc(tab.tab)}&c=${enc(Array.from(new Set([tab.explore_key, col.key])).join(','))}&s=${enc(col.key)}&d=desc`;
  const flagged = e && e.label_check && e.label_check.ok === false;
  return (
    <article id={col.field_key} className={`bg-white rounded-xl border shadow-sm p-5 space-y-3 scroll-mt-20 ${flagged ? 'border-amber-300' : 'border-gray-200'}`} data-testid="field-card">
      <header className="flex flex-wrap items-start gap-x-3 gap-y-1">
        <h3 className="text-base font-semibold text-gray-900">{col.label}</h3>
        <code className="text-[11px] text-gray-400 mt-1">{col.key}</code>
        {e && <SourceChip s={e.source} />}
        {flagged && <Chip tone="amber" title={e!.label_check.why}><AlertTriangle className="w-3 h-3 mr-0.5" aria-hidden />{T.labelWrong}</Chip>}
        {col.review && <Chip tone={VERDICT[col.review.verdict].tone}>{VERDICT[col.review.verdict].label}</Chip>}
        <Link href={exploreHref} className="ml-auto text-xs text-indigo-700 hover:underline inline-flex items-center gap-1 whitespace-nowrap">
          {T.inExplorer}<ExternalLink className="w-3 h-3" aria-hidden /></Link>
      </header>
      {!e ? <Empty>{T.noEntry}</Empty> : (<>
        <p className="text-sm text-gray-800 leading-6 max-w-4xl"><Txt s={e.meaning} /></p>
        {flagged && (
          <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-900">
            <span className="font-medium">{T.labelWrong}: </span>{e.label_check.why}
            {e.label_check.better && <div className="mt-0.5"><span className="text-amber-700">{T.propose}:</span> <span className="font-medium">«<Txt s={e.label_check.better} />»</span></div>}
          </div>
        )}
        <div className="grid lg:grid-cols-5 gap-4">
          <div className="lg:col-span-3">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">{T.how}</h4>
            <ol className="list-decimal pl-5 space-y-1 text-sm text-gray-700 leading-6">
              {(e.how || []).map((h, i) => <li key={i}><Txt s={h} /></li>)}
            </ol>
          </div>
          <div className="lg:col-span-2 space-y-3">
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">{T.examples}</h4>
              <ul className="space-y-1.5">
                {(e.examples || []).map((x, i) => {
                  const v = typeof x === 'string' ? x : x.value;
                  const h = exampleHref(tab.tab, x);
                  const who = typeof x === 'string' ? '' : (x.stem || x.id || '');
                  return (
                    <li key={i} className="text-sm rounded-lg bg-gray-50 border border-gray-100 px-2.5 py-1.5">
                      <div className={isArabic(v) ? 'text-right' : ''}><Txt s={v || '—'} className="text-gray-900" /></div>
                      <div className="text-[11px] text-gray-500 flex flex-wrap gap-x-2">
                        {who && (h ? <Link href={h} className="font-mono text-indigo-700 hover:underline">{who}</Link> : <span className="font-mono">{who}</span>)}
                        {typeof x !== 'string' && x.note && <span className="italic">{x.note}</span>}
                      </div>
                    </li>
                  );
                })}
              </ul>
              {e.fill && <p className="text-xs text-gray-500 mt-1.5">{T.fill}: {e.fill}</p>}
            </div>
          </div>
        </div>
        {e.caveats && e.caveats.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">{T.limits}</h4>
            <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700 leading-6">{e.caveats.map((c, i) => <li key={i}><Txt s={c} /></li>)}</ul>
          </div>
        )}
        <details className="text-xs text-gray-600">
          <summary className="cursor-pointer text-gray-500 hover:text-gray-800 select-none">{T.exact}</summary>
          <ul className="mt-1.5 space-y-1 font-mono text-[11px] leading-5 bg-gray-50 rounded-lg p-3 overflow-x-auto">
            {(e.exact || []).map((x, i) => <li key={i} className="whitespace-pre-wrap break-words" dir="ltr">{x}</li>)}
          </ul>
        </details>
      </>)}
      <ReviewBox col={col} onSaved={r => onSaved(col.field_key, r)} />
    </article>
  );
};

export default function HowWeCollect() {
  const router = useRouter();
  const g = useApi<Guide>('/field-guide');
  const [q, setQ] = useState('');
  const [onlyWrong, setOnlyWrong] = useState(false);
  const [onlyNew, setOnlyNew] = useState(false);
  const [src, setSrc] = useState<string | null>(null);
  const tabs = g.data?.tabs || [];
  const tabKey = typeof router.query.tab === 'string' && tabs.some(t => t.tab === router.query.tab) ? router.query.tab : 'articles';
  const tab = tabs.find(t => t.tab === tabKey) || null;

  useEffect(() => {        // a link to one field (#articles.n_institutions) opens its tab and scrolls to it
    if (!g.data || typeof window === 'undefined') return;
    const h = decodeURIComponent(window.location.hash.slice(1));
    const t = h.split('.')[0];
    if (h && t !== tabKey && tabs.some(x => x.tab === t)) router.replace({ pathname: '/how-we-collect', query: { tab: t }, hash: h }, undefined, { shallow: true });
    else if (h) setTimeout(() => document.getElementById(h)?.scrollIntoView(), 50);
  }, [g.data]);            // eslint-disable-line react-hooks/exhaustive-deps

  const onSaved = (fk: string, r: Review) => {
    if (!g.data) return;
    const d = { ...g.data, counts: { ...g.data.counts } };
    d.tabs = d.tabs.map(t => ({ ...t, columns: t.columns.map(c => {
      if (c.field_key !== fk) return c;
      d.counts[c.review ? c.review.verdict : 'not_reviewed'] -= 1;
      d.counts[r.verdict] += 1;
      return { ...c, review: r };
    }) }));
    g.setData(d);
  };

  const cols = useMemo(() => {
    if (!tab) return [];
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return tab.columns.filter(c => {
      const e = c.entry;
      if (onlyWrong && !((e && e.label_check && e.label_check.ok === false) || c.review?.verdict === 'wrong_label')) return false;
      if (onlyNew && c.review) return false;
      if (src && e?.source !== src) return false;
      if (!words.length) return true;
      const hay = [c.label, c.key, c.group, e?.meaning, ...(e?.how || []), ...(e?.caveats || []), e?.label_check?.why, e?.label_check?.better].join(' ').toLowerCase();
      return words.every(w => hay.includes(w));
    });
  }, [tab, q, onlyWrong, onlyNew, src]);
  const groups = useMemo(() => {
    const m = new Map<string, Column[]>();
    cols.forEach(c => { const k = c.group || '—'; if (!m.has(k)) m.set(k, []); m.get(k)!.push(c); });
    return Array.from(m.entries());
  }, [cols]);
  const tabCounts = (t: TabT) => ({
    wrong: t.columns.filter(c => c.entry?.label_check?.ok === false).length,
    done: t.columns.filter(c => c.review).length,
  });
  const c = g.data?.counts;

  return (
    <Layout wide>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-4xl">
          <h1 className="text-2xl font-semibold text-gray-900 flex items-center gap-2"><BookOpen className="w-6 h-6 text-indigo-600" aria-hidden />{T.title}</h1>
          <p className="text-sm text-gray-600 mt-1 leading-6">{T.lead}</p>
        </div>
        {g.data && <p className="text-xs text-gray-500">{g.data.n_entries} of {g.data.n_columns} {T.written}</p>}
      </div>
      {g.err && <ErrorBox>{g.err}</ErrorBox>}
      {c && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="review-counts">
          {([['agree', T.agreed, 'text-green-700'], ['wrong_label', T.wrongs, 'text-red-700'], ['question', T.questions, 'text-amber-700'], ['not_reviewed', T.notReviewed, 'text-gray-700']] as const).map(([k, l, cls]) => (
            <div key={k} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <div className="text-xs text-gray-500">{l}</div>
              <div className={`text-2xl font-semibold tabular-nums mt-1 ${cls}`}>{c[k] ?? 0}</div>
            </div>
          ))}
        </div>
      )}
      <Pipeline />
      {!g.data && !g.err && <Empty>Loading…</Empty>}
      {g.data && (<>
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Explorer tabs">
          {tabs.map(t => {
            const tc = tabCounts(t);
            const on = t.tab === tabKey;
            return (
              <button key={t.tab} role="tab" aria-selected={on} onClick={() => router.replace({ pathname: '/how-we-collect', query: { tab: t.tab } }, undefined, { shallow: true })}
                className={`px-3 py-1.5 rounded-lg text-sm border flex items-center gap-2 ${on ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'}`}>
                {t.label}<span className={`text-[11px] tabular-nums ${on ? 'text-indigo-100' : 'text-gray-400'}`}>{t.n_columns}</span>
                {t.written && tc.wrong > 0 && <span className={`text-[11px] rounded-full px-1.5 ${on ? 'bg-amber-300 text-amber-950' : 'bg-amber-100 text-amber-800'}`} title="labels that may be wrong">{tc.wrong}</span>}
                {!t.written && <span className={`text-[11px] ${on ? 'text-indigo-100' : 'text-gray-400'}`}>being written</span>}
              </button>
            );
          })}
        </div>
        {tab && (
          <div className="flex flex-wrap items-center gap-3 bg-white rounded-xl border border-gray-200 shadow-sm px-4 py-3">
            <label className="relative flex-1 min-w-[16rem] max-w-xl">
              <span className="sr-only">{T.search}</span>
              <Search className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" aria-hidden />
              <input value={q} onChange={e => setQ(e.target.value)} placeholder={T.search} dir="auto" className="pl-8 pr-2 py-1.5 w-full rounded-lg border-gray-300 text-sm" />
            </label>
            <label className="text-sm text-gray-700 flex items-center gap-2"><input type="checkbox" checked={onlyWrong} onChange={e => setOnlyWrong(e.target.checked)} className="rounded border-gray-300" data-testid="only-wrong" />{T.onlyWrong}</label>
            <label className="text-sm text-gray-700 flex items-center gap-2"><input type="checkbox" checked={onlyNew} onChange={e => setOnlyNew(e.target.checked)} className="rounded border-gray-300" data-testid="only-new" />{T.onlyUnreviewed}</label>
            <div className="flex flex-wrap items-center gap-1">
              <button onClick={() => setSrc(null)} className={`px-2 py-0.5 rounded text-[11px] border ${src === null ? 'bg-gray-800 text-white border-gray-800' : 'bg-white text-gray-600 border-gray-200'}`}>{T.allSources}</button>
              {(g.data.sources || []).map(s => (
                <button key={s} onClick={() => setSrc(src === s ? null : s)} aria-pressed={src === s}
                  className={`rounded ${src === s ? 'ring-2 ring-offset-1 ring-gray-700' : ''}`}><SourceChip s={s} /></button>
              ))}
            </div>
            <span className="text-xs text-gray-500 ml-auto">{cols.length} of {tab.n_columns} {T.shown}</span>
          </div>
        )}
        {tab && !tab.written && <Empty>{T.writing}</Empty>}
        {tab && tab.written && (
          <div className="flex gap-6 items-start">
            <nav className="hidden xl:block w-52 shrink-0 sticky top-20 bg-white rounded-xl border border-gray-200 shadow-sm p-3 text-sm max-h-[75vh] overflow-y-auto" aria-label={T.groups}>
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1.5">{T.groups}</div>
              <ul className="space-y-0.5">
                {groups.map(([gname, cs]) => (
                  <li key={gname}><a href={`#g-${enc(gname)}`} className="flex justify-between gap-2 px-2 py-1 rounded hover:bg-gray-50 text-gray-700">
                    <span className="truncate">{gname}</span><span className="text-gray-400 tabular-nums text-xs">{cs.length}</span></a></li>
                ))}
              </ul>
            </nav>
            <div className="flex-1 min-w-0 space-y-6">
              {!cols.length && <Empty>No field matches.</Empty>}
              {groups.map(([gname, cs]) => (
                <section key={gname} id={`g-${enc(gname)}`} className="space-y-3 scroll-mt-20">
                  <h2 className="text-lg font-semibold text-gray-800 border-b border-gray-200 pb-1">{gname} <span className="text-sm font-normal text-gray-400">{cs.length}</span></h2>
                  {cs.map(col => <FieldCard key={col.field_key} tab={tab} col={col} onSaved={onSaved} />)}
                </section>
              ))}
            </div>
          </div>
        )}
      </>)}
    </Layout>
  );
}
