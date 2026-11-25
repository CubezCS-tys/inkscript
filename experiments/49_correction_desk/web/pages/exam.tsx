import React, { useEffect, useMemo, useState } from 'react';
import { BookOpen, ChevronLeft, ChevronRight, ClipboardCheck, Droplets, FileText, LayoutTemplate, Scale, ScanText, Sparkles, Table2 } from 'lucide-react';
import Layout from '../components/Layout';
import { Card, ErrorBox } from '../components/Bits';
import { api, isArabic } from '../lib/api';
import { Marked, More, Pic, Pills, ROLE_COLOUR, TRIAGE_CLASS, TriageChip, Viewer, pageName, pc } from '../components/exam/bits';

// The extraction exam (/exam, 2026-11-10): experiment 97's scorecard drawn as bars, and for every group of measures
// real examples from the 214 exam pages: the printed region beside what was stored. Everything comes from
// /desk/api/exam (desk/exam.py), which serves experiments/97_extraction_evals/out/page/exam.json, built by page97.py
// from the scorer's files, the answer keys, the ink ledger and the reading checks; the triage section is read from
// out/triage/TRIAGE.md when the page opens. Nothing here is typed in by hand except the plain sentences around it.

const SECTIONS: [string, string][] = [
  ['scorecard', 'Scorecard'], ['ink', 'Nothing lost'], ['reading', 'Reading'], ['structure', 'Page structure'],
  ['tables', 'Tables'], ['front', 'Front matter'], ['refs', 'References'], ['errors', 'Real errors'], ['beyond', 'Beyond the exam'],
  ['triage', 'What the misses really are'], ['limits', 'Limits of this exam'],
];

export default function ExamPage() {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState('');
  const [view, setView] = useState<{ src: string | null; caption?: React.ReactNode }>({ src: null });
  useEffect(() => { api('/exam').then(setD).catch(e => setErr(String(e.message || e))); }, []);
  const open = (src: string | null, caption?: React.ReactNode) => setView({ src, caption });
  return (
    <Layout wide>
      <div className="max-w-[84rem] mx-auto pb-16">
        <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2"><ClipboardCheck className="w-5 h-5 text-indigo-600" aria-hidden />The extraction exam</h1>
        {err && <div className="mt-4"><ErrorBox>{err}</ErrorBox></div>}
        {!d && !err && <p className="text-sm text-gray-500 mt-4">Loading…</p>}
        {d && (
          <>
            <Intro d={d} />
            <nav className="flex flex-wrap gap-x-4 gap-y-1 mt-5 text-sm" aria-label="Sections">
              {SECTIONS.map(([id, l]) => <a key={id} href={`#${id}`} className="text-indigo-700 hover:underline">{l}</a>)}
            </nav>
            <div className="mt-6 space-y-8">
              <Scorecard rows={d.scorecard} />
              <Ink ink={d.ink} open={open} />
              <Reading cards={d.reading} rewrites={d.rewrites} r1={d.r1} />
              <Structure s={d.structure} />
              <Tables tables={d.tables} open={open} />
              <Fields id="front" title="Front matter: each miss, printed and stored" icon={FileText} cards={d.front}
                intro="For each article the key typed the title, authors, affiliations, abstract, keywords, dates and page numbers from the page. Here is every field the pipeline stored differently, even after ignoring vowel marks, punctuation and digit style. Left: where it is printed. Right: the key, then what the pipeline stored, with the differing letters marked." />
              <Fields id="refs" title="References: each miss, printed and stored" icon={BookOpen} cards={d.refs}
                intro="On 38 reference pages the key split every reference into authors, year, title, source, volume, issue and pages, as printed. Here is every field the pipeline stored differently after folding. Left: the printed reference. Right: the key, then what the pipeline stored." />
              <Errors kinds={d.errors} />
              <Beyond items={d.beyond} open={open} />
              <Triage t={d.triage} />
              <Limits limits={d.limits} />
            </div>
          </>)}
      </div>
      <Viewer src={view.src} caption={view.caption} onClose={() => setView({ src: null })} />
    </Layout>
  );
}

// ---------------------------------------------------------------- top

const PART_PLAIN: Record<string, string> = { SECT: 'section headings', PAGE: 'page structure', FRONT: 'front matter', TAB: 'tables', REFS: 'references' };

function Intro({ d }: { d: any }) {
  const st = d.status, ex = d.exam, rev = d.revision;
  const missing = (st.parts_without_keys || []).map((k: string) => PART_PLAIN[k] || k);
  return (
    <>
      <div className="text-[17px] text-gray-800 mt-2 max-w-4xl leading-relaxed space-y-1" data-testid="exam-intro">
        <p><b>{ex.articles} locked articles</b> from {ex.journals} journals, <b>{ex.pages} exam pages</b>: {ex.by_kind.front} first pages, {ex.by_kind.body} body pages, {ex.by_kind.table} table pages, {ex.by_kind.refs} reference pages, {ex.by_kind.notes} footnote pages.</p>
        <p>The answer keys were written <b>twice, from the page image</b>, by readers who could not see our output.</p>
        <p>Where the two keys differed, <b>a third reader settled it</b> by looking at the page.</p>
      </div>
      <div className={`mt-4 rounded-xl border px-5 py-4 max-w-5xl ${st.final ? 'bg-green-50 border-green-200' : 'bg-amber-50 border-amber-200'}`} data-testid="exam-status">
        <div className="flex items-center gap-3">
          <span className={`text-xs font-bold tracking-wide px-2 py-0.5 rounded ${st.final ? 'bg-green-600 text-white' : 'bg-amber-500 text-white'}`}>{st.word}</span>
          <span className="text-sm text-gray-900 font-medium">{st.final ? <>These scores are final: <b>{st.banner || 'the baseline'}</b>.</> : 'These scores are not final yet.'}</span>
        </div>
        <p className="text-sm text-gray-700 mt-2 leading-relaxed">
          {st.final
            ? <>Every answer key used is final{missing.length ? <> (not yet keyed: {missing.join(', ')}, so it has no score)</> : null}. </>
            : <>The answer keys are not all final; read every number as a development run. </>}
          {rev?.counts && <>After the triage, the keys were checked once more against the page images: {rev.counts['items checked']} items looked at, {rev.counts.changed} corrected{rev.scored_after ? ', and the scores include that revision' : ', not yet re-scored'}. </>}
          {d.triage ? <>The <a href="#triage" className="text-indigo-700 underline">triage</a> says, for every miss, whether it is a real pipeline error, the scorer&apos;s or the key&apos;s.</> : <>A triage of the misses is running now.</>}
        </p>
        {st.scorer_says && <p className="text-xs text-gray-500 mt-1">The scorer says: {st.scorer_says}</p>}
        <p className="text-xs text-gray-500 mt-2">Scored {st.made}; this page built {d.built}. The <a href="#limits" className="underline">limits of this exam</a> are at the bottom.</p>
      </div>
    </>
  );
}

// ---------------------------------------------------------------- scorecard

const GROUPS: [string, string, string][] = [
  ['ink', 'Nothing lost', 'ink'], ['reading', 'Reading', 'reading'], ['structure', 'Page structure: labels, grouping, order, footnotes', 'structure'],
  ['front', 'Front matter', 'front'], ['tables', 'Tables', 'tables'], ['refs', 'References', 'refs'],
];

function verdict(r: any): ['pass' | 'miss' | 'mixed' | 'info' | 'none', string] {
  const p = (r.passed || '').trim();
  if (r.code === 'P5') return ['none', 'Not keyed yet'];
  if (p === 'pass') return ['pass', 'Pass'];
  if (p === 'miss') return ['miss', 'Miss'];
  if (p) return [p.includes('pass') ? 'mixed' : 'miss', p[0].toUpperCase() + p.slice(1)];
  return ['info', 'For information'];
}
const V_STYLE: Record<string, [string, string]> = {
  pass: ['#0d9488', 'text-teal-700'], miss: ['#f43f5e', 'text-rose-700'], mixed: ['#f59e0b', 'text-amber-700'],
  info: ['#94a3b8', 'text-gray-500'], none: ['#e5e7eb', 'text-gray-400'],
};

function Scorecard({ rows }: { rows: any[] }) {
  return (
    <Card id="scorecard" title={<span className="flex items-center gap-2"><Scale className="w-4 h-4 text-indigo-600" aria-hidden />The scorecard</span>}>
      <p className="text-sm text-gray-600 -mt-1 max-w-4xl">One row per measure. The bar is the pipeline&apos;s score. The <b>black tick</b> is the pass mark, fixed before anything was scored. The <b>thin violet line</b> is how closely the two blind keyers agreed with each other: a score cannot be trusted beyond it. Under each bar, in grey: what a miss on that row means. Where a field has three scores, the bar is the one that ignores vowel marks, punctuation and digit style; the exact scores are written beside it.</p>
      <div className="flex flex-wrap items-center gap-5 text-xs text-gray-600 mt-3" aria-hidden>
        <span className="inline-flex items-center gap-1.5"><span className="w-6 h-3 rounded-sm" style={{ background: V_STYLE.pass[0] }} />pass</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-6 h-3 rounded-sm" style={{ background: V_STYLE.miss[0] }} />miss</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-6 h-3 rounded-sm" style={{ background: V_STYLE.mixed[0] }} />miss when exact, pass when folded</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-6 h-3 rounded-sm" style={{ background: V_STYLE.info[0] }} />no pass mark</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-[3px] h-4 bg-gray-900" />pass mark</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-[2px] h-4 bg-violet-500" />the keyers&apos; agreement</span>
      </div>
      <div className="mt-4 space-y-7" data-testid="scorecard">
        {GROUPS.map(([g, title, anchor]) => {
          const rs = rows.filter(r => r.group === g && r.main);
          if (!rs.length) return null;
          return (
            <div key={g}>
              <div className="flex items-baseline justify-between border-b border-gray-100 pb-1 mb-3">
                <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
                <a href={`#${anchor}`} className="text-xs text-indigo-700 hover:underline">see the examples ↓</a>
              </div>
              <div className="space-y-3.5">{rs.map(r => <ScoreRow key={r.id} r={r} />)}</div>
            </div>);
        })}
      </div>
      <details className="mt-6">
        <summary className="text-sm text-indigo-700 cursor-pointer select-none">Every row of the scorecard, as the scorer wrote it ({rows.filter(r => r.idx >= 0).length} rows)</summary>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-xs" data-testid="scorecard-all">
            <thead><tr className="text-gray-500 border-b border-gray-200 text-left">
              <th className="font-medium py-1.5 pr-3">Measure</th><th className="font-medium pr-3">Pipeline</th><th className="font-medium pr-3">Key A vs key B</th>
              <th className="font-medium pr-3">Pass mark</th><th className="font-medium pr-3">Result</th><th className="font-medium">What a miss means</th></tr></thead>
            <tbody>
              {rows.filter(r => r.idx >= 0 && !r.id.endsWith('w')).map(r => (
                <tr key={r.id} className="border-t border-gray-100 align-top">
                  <td className="py-1.5 pr-3"><div className="text-gray-900">{r.name.replace(/^Letters wrong: t/, 'T').replace(/^Letters wrong: /, '')}</div><div className="text-gray-400">{r.code_plain ? `${r.code_plain} (${r.code}) · ` : ''}{r.raw}</div></td>
                  <td className="pr-3 tabular-nums whitespace-nowrap">{r.pipeline_text}</td>
                  <td className="pr-3 tabular-nums whitespace-nowrap text-violet-700">{r.a_vs_b_text}</td>
                  <td className="pr-3 text-gray-600">{r.pass_text}</td>
                  <td className={`pr-3 ${V_STYLE[verdict(r)[0]][1]}`}>{r.passed || '—'}</td>
                  <td className="text-gray-600">{r.miss_means}</td>
                </tr>))}
            </tbody>
          </table>
        </div>
      </details>
    </Card>
  );
}

function ScoreRow({ r }: { r: any }) {
  const [v, word] = verdict(r);
  const [colour, tcls] = V_STYLE[v];
  const low = r.better === 'low';
  const has = r.value != null;
  const max = low ? Math.max((r.mark || 0) * 2, (r.value || 0) * 1.15, (r.ceiling || 0) * 1.15, 1e-6) : 1;
  const at = (x: number) => `${Math.min(100, (x / max) * 100)}%`;
  return (
    <div className="grid grid-cols-[19rem_minmax(0,1fr)_7rem_9.5rem] gap-4 items-start" data-testid="score-row" data-verdict={v}>
      <div>
        <div className="text-sm text-gray-900 leading-snug">{r.name}</div>
        <div className="text-[11px] text-gray-400">{r.code_plain ? `${r.code_plain} (${r.code})` : ''}{r.n != null ? ` · ${Number(r.n).toLocaleString('en')} items` : ''}</div>
      </div>
      <div className="pt-1">
        {has ? (
          <>
            <div className="relative h-4 bg-gray-100 rounded" title={`${r.name}: ${pc(r.value)}${r.mark != null ? `, pass mark ${low ? '≤' : '≥'} ${pc(r.mark)}` : ''}${r.ceiling != null ? `, keyers agreed ${pc(r.ceiling)}` : ''}`}>
              <div className="absolute left-0 top-0 h-4 rounded" style={{ width: r.value === 0 ? 2 : at(r.value), minWidth: 2, background: colour }} />
              {r.mark != null && <div className="absolute -top-1 h-6 w-[3px] bg-gray-900 rounded-sm" style={{ left: `calc(${at(r.mark)} - 1px)` }} />}
              {r.ceiling != null && <div className="absolute -top-1.5 h-7 w-[2px] bg-violet-500" style={{ left: `calc(${at(r.ceiling)} - 1px)` }} />}
            </div>
            <div className="flex justify-between text-[10px] text-gray-400 mt-0.5"><span>0</span><span>{low ? `${pc(max)} · lower is better` : '100%'}</span></div>
          </>) : <div className="text-sm text-gray-600">{r.code === 'P5' ? 'no answer key yet' : r.pipeline_text}</div>}
        {r.values && <div className="text-xs text-gray-600 mt-0.5">{r.values.map(([k, x]: [string, number]) => `${k} ${pc(x)}`).join(' · ')} · ignoring marks, punctuation and digit style {pc(r.value)}</div>}
        {r.miss_means && <div className="text-xs text-gray-500 mt-0.5 leading-snug">{r.mark != null || r.passed ? <>A miss here means: {r.miss_means}.</> : <>{r.miss_means[0].toUpperCase() + r.miss_means.slice(1)}.</>}</div>}
      </div>
      <div className="text-right pt-0.5">
        <div className="text-base font-semibold tabular-nums text-gray-900">{has ? pc(r.value) : '—'}</div>
        <div className="text-[11px] text-gray-500">{r.mark != null ? <>pass {low ? '≤' : '≥'} {pc(r.mark)}</> : 'no pass mark'}</div>
        {r.ceiling != null && <div className="text-[11px] text-violet-600">keyers {pc(r.ceiling)}</div>}
      </div>
      <div className={`pt-0.5 text-sm font-semibold ${tcls}`}>{word}</div>
    </div>
  );
}

// ---------------------------------------------------------------- ink

const GUESS_PLAIN: Record<string, string> = {
  'text-like row of glyph-sized blobs': 'looks like a row of letters',
  'small mark (1-3 glyph-sized blobs)': 'a small mark (1 to 3 blobs)',
  'long thin rule': 'a rule', 'frame / border ornament': 'a frame or ornament',
};

function Ink({ ink, open }: { ink: any; open: (s: string | null, c?: React.ReactNode) => void }) {
  const [kind, setKind] = useState('all');
  const [journal, setJournal] = useState('all');
  const [sort, setSort] = useState('unseen');
  const [n, setN] = useState(24);
  const journals = useMemo(() => Array.from(new Set((ink.pages as any[]).map(p => p.journal))).sort(), [ink]);
  const pages = useMemo(() => {
    const ps = (ink.pages as any[]).filter(p => (kind === 'all' || p.kind === kind) && (journal === 'all' || p.journal === journal));
    return sort === 'unseen' ? [...ps].sort((a, b) => (b.unseen + b.setaside + b.twice) - (a.unseen + a.setaside + a.twice) || b.all_unseen - a.all_unseen) : ps;
  }, [ink, kind, journal, sort]);
  const byId = (s: string, p: number) => (ink.pages as any[]).find(x => x.stem === s && x.page === p);
  const h = ink.headline || {};
  return (
    <Card id="ink" title={<span className="flex items-center gap-2"><Droplets className="w-4 h-4 text-indigo-600" aria-hidden />Nothing lost: every blob of ink on the 214 pages</span>}>
      <p className="text-sm text-gray-600 -mt-1 max-w-4xl">Every blob of printed ink was given to the stored piece that holds it. Text ink claimed once: <b>{pc(h.text_once)}</b>. Text ink nobody saw: <b>{pc(h.text_unseen)}</b>. Text ink the parser dropped: <b>{pc(h.text_dropped)}</b>. This says whether ink was <i>claimed</i>, not whether it was <i>read</i> right: the reading section does that.</p>
      <div className="grid grid-cols-4 gap-x-6 gap-y-2 mt-3 text-xs text-gray-700" data-testid="ink-legend">
        {(ink.legend as any[]).map(l => (
          <div key={l.name} className="flex gap-2 items-start">
            <span className="w-4 h-4 rounded-sm shrink-0 mt-0.5" style={l.box ? { border: `2px solid rgb(${l.rgb.join(',')})` } : { background: `rgb(${l.rgb.join(',')})` }} />
            <span><b className="font-medium">{l.name}</b>: {l.what}</span>
          </div>))}
      </div>

      <div className="grid grid-cols-2 gap-6 mt-5" data-testid="ink-featured">
        {(ink.featured as any[]).map(f => {
          const p = byId(f.stem, f.page);
          return (
            <figure key={`${f.stem}-${f.page}`} className="rounded-lg border border-gray-200 p-3">
              <figcaption className="mb-2"><div className="font-medium text-gray-900">{f.title}</div>
                <div className="text-sm text-gray-600 mt-0.5">{f.text}</div>
                <div className="text-xs text-gray-400 mt-1">{pageName(f.stem, f.page)}{p ? ` · ${p.kind} page · text claimed once ${pc(p.once)}` : ''}</div></figcaption>
              {p && <div className="max-h-[560px] overflow-hidden rounded-md"><Pic src={p.img} alt={`ink overlay of ${pageName(f.stem, f.page)}`} className="w-full h-auto" onClick={() => open(p.img, pageName(f.stem, f.page))} /></div>}
            </figure>);
        })}
      </div>

      <h3 className="text-sm font-semibold text-gray-800 mt-7">All 214 pages</h3>
      <div className="flex flex-wrap items-center gap-3 mt-2">
        <Pills label="Page kind" value={kind} onChange={k => { setKind(k); setN(24); }}
          items={[['all', 'All', ink.pages.length], ...Object.entries(ink.kinds as Record<string, string>).map(([k, l]) => [k, `${l}s`, (ink.pages as any[]).filter(p => p.kind === k).length] as [string, string, number])]} />
        <label className="text-sm text-gray-600 flex items-center gap-2">Journal
          <select value={journal} onChange={e => { setJournal(e.target.value); setN(24); }} className="rounded-lg border-gray-300 text-sm py-1">
            <option value="all">all</option>{journals.map(j => <option key={j} value={j}>{j}</option>)}</select></label>
        <label className="text-sm text-gray-600 flex items-center gap-2">Order
          <select value={sort} onChange={e => setSort(e.target.value)} className="rounded-lg border-gray-300 text-sm py-1">
            <option value="unseen">least claimed first</option><option value="exam">exam order</option></select></label>
      </div>
      <div className="grid grid-cols-6 gap-3 mt-3" data-testid="ink-gallery">
        {pages.slice(0, n).map(p => (
          <figure key={`${p.stem}-${p.page}`} className="min-w-0">
            <Pic src={p.thumb} alt={`ink overlay, ${pageName(p.stem, p.page)}`} className="w-full h-auto" onClick={() => open(p.img, `${pageName(p.stem, p.page)} · ${ink.kinds[p.kind]}`)} />
            <figcaption className="text-[11px] text-gray-600 mt-1 leading-tight">{p.stem} p{p.page}<br />
              <span className="text-gray-400">{ink.kinds[p.kind]} · text claimed {pc(p.once)}</span></figcaption>
          </figure>))}
      </div>
      {!pages.length && <p className="text-sm text-gray-500 mt-2">No page of this kind in this journal.</p>}
      <More shown={Math.min(n, pages.length)} total={pages.length} onMore={() => setN(n + 36)} />

      <h3 className="text-sm font-semibold text-gray-800 mt-7">The ink no piece claimed that could be text</h3>
      <p className="text-sm text-gray-600 mt-1 max-w-4xl">Rules, frames and specks left aside, these are all the unclaimed regions shaped like letters or marks, and the regions the parser set aside. By eye, none of the &lsquo;seen by nobody&rsquo; ones is printed text: rules, ornaments, punch holes, a © sign, the edge of the facing page.</p>
      <div className="grid grid-cols-4 gap-4 mt-3" data-testid="ink-regions">
        {(ink.regions as any[]).map(r => (
          <figure key={r.id} className="rounded-lg border border-gray-200 p-2 min-w-0">
            <div className="h-28 flex items-center justify-center bg-gray-50 rounded overflow-hidden">
              <Pic src={r.img} alt={`unclaimed region ${r.id}`} className="max-h-28 w-auto max-w-full border-0" onClick={() => open(r.img, r.id)} />
            </div>
            <figcaption className="text-[11px] mt-1.5 leading-snug">
              <span className={`font-medium ${r.group === 'set_aside' ? 'text-emerald-700' : 'text-purple-700'}`}>{r.group === 'set_aside' ? `set aside${r.setaside_role === 'otherArticle' ? ' as another article' : r.setaside_role ? ` as ${r.setaside_role}` : ''}` : 'seen by nobody'}</span>
              <span className="text-gray-600"> · {GUESS_PLAIN[r.guess] || r.guess}</span><br />
              <span className="text-gray-400">{r.stem} p{r.page} · {ink.kinds[r.kind]}</span>
            </figcaption>
          </figure>))}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- reading

const TAGS: [string, string][] = [
  ['letters', 'Real letter differences'], ['marks', 'Vowel marks'], ['hamza', 'Hamza added or dropped'],
  ['spacing', 'Spacing'], ['punctuation', 'Punctuation'], ['order', 'Order only'],
];
const TAG_PLAIN: Record<string, string> = { letters: 'letters differ', marks: 'vowel marks only', hamza: 'hamza only', spacing: 'spacing only', punctuation: 'punctuation only', order: 'word order only' };
const WITNESS: [string, string][] = [['azure', 'Azure (raw reading)'], ['t91', 'Our own reader (t91)'], ['shown', 'Text we show']];

function Reading({ cards, rewrites, r1 }: { cards: any[]; rewrites: any[]; r1: any }) {
  const [tag, setTag] = useState('letters');
  const [n, setN] = useState(10);
  const shown = useMemo(() => cards.filter(c => (tag === 'all' ? true : tag === 'unsettled' ? !c.settled : c.tags.includes(tag))), [cards, tag]);
  return (
    <Card id="reading" title={<span className="flex items-center gap-2"><ScanText className="w-4 h-4 text-indigo-600" aria-hidden />Reading: the lines where the readings disagree</span>}>
      <p className="text-sm text-gray-600 -mt-1 max-w-4xl">600 printed lines were read three ways: by Azure, by our own reader, and as the Desk shows them. On {cards.length} lines they did not all agree. Two readers who could not see whose reading was whose then typed what is printed; where they differed, a third settled it. Under each printed line: the three readings, with the letters that differ from the settled reading <mark className="bg-rose-100 text-rose-900 rounded-sm px-0.5">marked</mark> and a <span className="inline-block w-[3px] h-[0.9em] bg-rose-500 align-middle mx-0.5 rounded-sm" /> where something is missing.</p>
      <div className="mt-3">
        <Pills label="Kind of difference" value={tag} onChange={k => { setTag(k); setN(10); }}
          items={[['all', 'All', cards.length], ...TAGS.map(([k, l]) => [k, l, cards.filter(c => c.tags.includes(k)).length] as [string, string, number]),
            ['unsettled', 'Not settled yet', cards.filter(c => !c.settled).length]]} />
        <p className="text-xs text-gray-500 mt-2">A line is listed under every kind of difference one of its readings has (the smallest kind that explains each reading).</p>
      </div>
      <div className="mt-2 divide-y divide-gray-100" data-testid="reading-cards">
        {shown.slice(0, n).map(c => <LineCard key={c.id} c={c} />)}
      </div>
      <More shown={Math.min(n, shown.length)} total={shown.length} onMore={() => setN(n + 10)} />

      <h3 className="text-sm font-semibold text-gray-800 mt-8" id="rewrites">Deliberate rewrites: where the text we show differs from the print on purpose</h3>
      <p className="text-sm text-gray-600 mt-1 max-w-4xl">These are not misreadings. When the pipeline stores a keyword block it drops the printed label «الكلمات المفتاحية:» and turns the printed «،» into «؛»; in a verse or a list it inserts a separator. That is {r1?.rewrite_letters ?? 'some'} letters on the settled lines, which is why the scorecard shows the text we show twice: as stored, and with these rewrites set aside.</p>
      <div className="mt-2 divide-y divide-gray-100" data-testid="rewrite-cards">
        {(rewrites || []).map((c: any) => (
          <div key={c.id} className="py-4" data-testid="rewrite-card">
            <div className="text-xs text-gray-500 mb-2">{pageName(c.stem, c.page)}, line {c.line} · <span className="text-amber-800">{c.what}</span></div>
            <div className="flex justify-end"><Pic src={c.img} alt="the printed line" className="max-w-full h-auto max-h-24" /></div>
            <div className="mt-2 space-y-1">
              <div className="grid grid-cols-[11rem_minmax(0,1fr)] gap-3 items-baseline"><div className="text-xs text-gray-600">As printed</div><Marked text={c.settled || c.azure} /></div>
              <div className="grid grid-cols-[11rem_minmax(0,1fr)] gap-3 items-baseline"><div className="text-xs text-gray-600">Text we show</div><Marked segs={c.shown} /></div>
            </div>
          </div>))}
      </div>
    </Card>
  );
}

function LineCard({ c }: { c: any }) {
  return (
    <div className="py-5" data-testid="reading-card">
      <div className="text-xs text-gray-500 mb-2">{pageName(c.stem, c.page)}, line {c.line} · {c.kind} page</div>
      <div className="flex justify-end"><Pic src={c.img} alt="the printed line" className="max-w-full h-auto max-h-24" /></div>
      <div className="mt-3 space-y-1">
        {WITNESS.map(([k, label]) => {
          const w = c.witnesses[k] || {};
          return (
            <div key={k} className="grid grid-cols-[11rem_minmax(0,1fr)_9rem] gap-3 items-baseline">
              <div className="text-xs text-gray-600">{label}</div>
              <Marked segs={w.segs} text={w.segs ? undefined : w.text} />
              <div className="text-[11px] text-right">{!c.settled ? <span className="text-gray-400">—</span> : w.right ? <span className="text-teal-700">matches</span> : <span className="text-rose-700">{TAG_PLAIN[w.kind] || 'differs'}</span>}</div>
            </div>);
        })}
        <div className="grid grid-cols-[11rem_minmax(0,1fr)_9rem] gap-3 items-baseline border-t border-gray-100 pt-1.5 mt-1.5">
          <div className="text-xs font-semibold text-gray-900">Settled reading</div>
          {c.settled ? <Marked text={c.settled} className="font-semibold" /> : <div className="text-sm text-gray-400">not settled yet</div>}
          <div className="text-[11px] text-right text-gray-500">{c.how}</div>
        </div>
      </div>
      <details className="mt-1.5">
        <summary className="text-xs text-indigo-700 cursor-pointer select-none">How it was settled</summary>
        <div className="mt-1.5 space-y-1 pl-2 border-l-2 border-gray-100">
          {[['A', 'Reader A'], ['B', 'Reader B'], ['C', 'Third reader']].map(([k, l]) => c[k] && (
            <div key={k} className="grid grid-cols-[11rem_minmax(0,1fr)] gap-3 items-baseline">
              <div className="text-xs text-gray-600">{l}{c[k].unsure ? <span className="text-amber-700"> (unsure)</span> : null}{k === 'C' && c.C.who ? <span className="text-gray-400"> · sided with {c.C.who === 'neither' ? 'neither' : `reader ${c.C.who}`}</span> : null}</div>
              <div><Marked text={c[k].text} />{c[k].why && <div className="text-[11px] text-gray-500">{c[k].why}</div>}</div>
            </div>))}
        </div>
      </details>
    </div>
  );
}

// ---------------------------------------------------------------- page structure

function Structure({ s }: { s: any }) {
  const pages = s.pages as any[];
  const [i, setI] = useState(0);
  const [doc, setDoc] = useState<any>(null);
  const [err, setErr] = useState('');
  const cur = pages[i];
  useEffect(() => {
    if (!cur) return;
    setDoc(null); setErr('');
    api(`/exam/structure/${encodeURIComponent(cur.file)}`).then(setDoc).catch(e => setErr(String(e.message || e)));
  }, [cur]);
  const total = (p: any) => Object.values(p.counts || {}).reduce((a: number, b: any) => a + Number(b), 0);
  return (
    <Card id="structure" title={<span className="flex items-center gap-2"><LayoutTemplate className="w-4 h-4 text-indigo-600" aria-hidden />Page structure: the key&apos;s pieces beside the pipeline&apos;s</span>}>
      <p className="text-sm text-gray-600 -mt-1 max-w-4xl">Each reader line is coloured by its role; a thin frame of the same colour goes round the lines that form one piece (a paragraph, a list item, a reference, a whole table). Left: the answer key. Right: what the pipeline stored. Lines where they differ are <span className="text-red-600 font-medium">outlined in red</span> on both sides; point at a line to read it. The pages with the most differences come first.</p>
      <div className="flex flex-wrap items-center gap-3 mt-3">
        <button className="p-1.5 rounded-lg border border-gray-200 bg-white disabled:opacity-40" disabled={i === 0} onClick={() => setI(i - 1)} aria-label="previous page"><ChevronLeft className="w-4 h-4" /></button>
        <select value={i} onChange={e => setI(Number(e.target.value))} className="rounded-lg border-gray-300 text-sm py-1.5 max-w-xl" data-testid="structure-select">
          {pages.map((p, k) => <option key={p.file} value={k}>{pageName(p.stem, p.page)} · {p.kind} · {total(p)} difference{total(p) === 1 ? '' : 's'}</option>)}
        </select>
        <button className="p-1.5 rounded-lg border border-gray-200 bg-white disabled:opacity-40" disabled={i >= pages.length - 1} onClick={() => setI(i + 1)} aria-label="next page"><ChevronRight className="w-4 h-4" /></button>
        <span className="text-xs text-gray-500">{i + 1} of {pages.length}</span>
      </div>
      {err && <div className="mt-3"><ErrorBox>{err}</ErrorBox></div>}
      {doc && <StructurePage doc={doc} roles={s.roles} />}
      {!doc && !err && <p className="text-sm text-gray-500 mt-3">Loading the page…</p>}
    </Card>
  );
}

function clusters(lines: number[], box: Record<number, number[]>) {
  // consecutive lines of one piece that overlap across the page form one frame (a piece may turn a column)
  const out: number[][][] = [];
  let cur: number[][] = [];
  for (const n of lines) {
    const b = box[n];
    if (!b) continue;
    const last = cur[cur.length - 1];
    if (last && !(b[0] < last[0] + last[2] && last[0] < b[0] + b[2] && b[1] < last[1] + last[3] + 0.05)) { out.push(cur); cur = []; }
    cur.push(b);
  }
  if (cur.length) out.push(cur);
  return out.map(c => {
    const x0 = Math.min(...c.map(b => b[0])), y0 = Math.min(...c.map(b => b[1]));
    const x1 = Math.max(...c.map(b => b[0] + b[2])), y1 = Math.max(...c.map(b => b[1] + b[3]));
    return [x0, y0, x1 - x0, y1 - y0];
  });
}

function StructurePage({ doc, roles }: { doc: any; roles: Record<string, string> }) {
  const [hover, setHover] = useState<number | null>(null);
  const box: Record<number, number[]> = useMemo(() => Object.fromEntries((doc.lines as any[]).map(l => [l.n, l.b])), [doc]);
  const text: Record<number, string> = useMemo(() => Object.fromEntries((doc.lines as any[]).map(l => [l.n, l.t])), [doc]);
  const used = new Set<string>([...doc.key, ...doc.pipe].map((p: any) => p.role));
  const diffLines = Object.keys(doc.diff).map(Number).sort((a, b) => a - b);
  const flags = doc.key_flags || {};
  return (
    <div className="mt-4">
      {(flags.image_defect || flags.cover_sheet || flags.unsure) && <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">{flags.cover_sheet ? 'The keyers marked this page as a repository cover sheet. ' : ''}{flags.image_defect ? 'The keyers marked this page as a damaged image and left it out of the scores. ' : flags.unsure ? 'The keyers were unsure about part of this page; those pieces are left out of the scores. ' : ''}{flags.why}</p>}
      <div className="grid grid-cols-2 gap-6" data-testid="structure-pair">
        {[['key', 'The answer key', doc.key, doc.key_not_text], ['pipe', 'The pipeline', doc.pipe, doc.pipe_not_text]].map(([side, title, pieces, notText]: any) => (
          <figure key={side} className="min-w-0">
            <figcaption className="text-sm font-medium text-gray-800 mb-1.5">{title} <span className="text-xs text-gray-400 font-normal">· {pieces.length} pieces</span></figcaption>
            <div className="relative" data-testid={`structure-${side}`}>
              <Pic src={doc.img} alt={`${pageName(doc.stem, doc.page)}, ${title}`} className="w-full h-auto rounded-none" />
              <svg className="absolute inset-0 w-full h-full" viewBox={`0 0 1 ${doc.aspect}`} preserveAspectRatio="none">
                {(pieces as any[]).map((p, k) => {
                  const c = ROLE_COLOUR[p.role] || '#a8a29e';
                  return (
                    <g key={k}>
                      {p.lines.map((n: number) => box[n] && (
                        <rect key={n} x={box[n][0]} y={box[n][1] * doc.aspect} width={box[n][2]} height={box[n][3] * doc.aspect} fill={c} fillOpacity={hover === n ? 0.45 : 0.22}
                          onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(null)}>
                          <title>{`line ${n} · ${roles[p.role] || p.role}${doc.diff[n] ? ` · ${doc.diff[n].join('; ')}` : ''}\n${text[n] || ''}`}</title>
                        </rect>))}
                      {clusters(p.lines, box).map((b, j) => (
                        <rect key={`c${j}`} x={b[0] - 0.004} y={(b[1] - 0.002) * doc.aspect} width={b[2] + 0.008} height={(b[3] + 0.004) * doc.aspect}
                          fill="none" stroke={c} strokeWidth={1.4} vectorEffect="non-scaling-stroke" pointerEvents="none" />))}
                    </g>);
                })}
                {(notText as number[]).map(n => box[n] && <rect key={`n${n}`} x={box[n][0]} y={box[n][1] * doc.aspect} width={box[n][2]} height={box[n][3] * doc.aspect} fill="#d6d3d1" fillOpacity={0.5}><title>{`line ${n} · not text`}</title></rect>)}
                {diffLines.map(n => box[n] && <rect key={`d${n}`} x={box[n][0] - 0.003} y={(box[n][1] - 0.001) * doc.aspect} width={box[n][2] + 0.006} height={(box[n][3] + 0.002) * doc.aspect}
                  fill="none" stroke="#dc2626" strokeWidth={2.2} strokeDasharray="5 3" vectorEffect="non-scaling-stroke" pointerEvents="none" />)}
              </svg>
            </div>
          </figure>))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs text-gray-700" data-testid="role-legend">
        {Array.from(used).map(r => <span key={r} className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: ROLE_COLOUR[r] || '#a8a29e' }} />{roles[r] || r}</span>)}
        <span className="inline-flex items-center gap-1.5"><span className="w-4 h-3 border-2 border-dashed border-red-600 rounded-sm" />differs</span>
      </div>
      {diffLines.length > 0 && (
        <details className="mt-3" open={diffLines.length <= 12}>
          <summary className="text-sm text-indigo-700 cursor-pointer select-none">The {diffLines.length} line{diffLines.length === 1 ? '' : 's'} that differ</summary>
          <div className="mt-2 divide-y divide-gray-100">
            {diffLines.slice(0, 80).map(n => (
              <div key={n} className="grid grid-cols-[4rem_minmax(0,1fr)_minmax(0,22rem)] gap-3 py-1.5 items-baseline" onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(null)}>
                <div className="text-xs text-gray-500 tabular-nums">line {n}</div>
                <Marked text={text[n]} />
                <div className="text-xs text-gray-700">{doc.diff[n].join('; ')}{doc.triage?.[n] && <div className="mt-0.5"><TriageChip t={doc.triage[n]} full /></div>}</div>
              </div>))}
            {diffLines.length > 80 && <p className="text-xs text-gray-500 py-1.5">… and {diffLines.length - 80} more (one piece, such as a whole table, grouped differently).</p>}
          </div>
        </details>)}
    </div>
  );
}

// ---------------------------------------------------------------- tables

const CELL_STYLE: Record<string, string> = {
  format: 'bg-sky-50 text-sky-900', misplaced: 'bg-amber-100 text-amber-900', different: 'bg-rose-100 text-rose-900',
};

function Tables({ tables, open }: { tables: any[]; open: (s: string | null, c?: React.ReactNode) => void }) {
  return (
    <Card id="tables" title={<span className="flex items-center gap-2"><Table2 className="w-4 h-4 text-indigo-600" aria-hidden />Tables: every table with a wrong cell</span>}>
      <p className="text-sm text-gray-600 -mt-1 max-w-4xl">The key typed every cell of the first table on each table page. These are the tables where at least one cell is wrong even after ignoring digit style and spacing, with the shifted-row table first. Above: the printed table. Below: the key&apos;s grid and the pipeline&apos;s grid, cell by cell.</p>
      <div className="flex flex-wrap gap-4 text-xs text-gray-700 mt-3">
        <span className="inline-flex items-center gap-1.5"><span className={`w-4 h-3 rounded-sm ${CELL_STYLE.format}`} style={{ outline: '1px solid #bae6fd' }} />formatting only (digit style, spacing, sign position)</span>
        <span className="inline-flex items-center gap-1.5"><span className={`w-4 h-3 rounded-sm ${CELL_STYLE.misplaced}`} />right text in the wrong cell (a row or column shifted, a cell left empty)</span>
        <span className="inline-flex items-center gap-1.5"><span className={`w-4 h-3 rounded-sm ${CELL_STYLE.different}`} />different text</span>
      </div>
      <div className="mt-4 space-y-10" data-testid="tables">
        {tables.map(t => (
          <div key={`${t.stem}-${t.page}-${t.table}`} data-testid="table-card">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <h3 className="font-medium text-gray-900">{pageName(t.stem, t.page)}</h3>
              <span className="text-sm text-gray-600">{t.scorer_lists ? <>{t.n_wrong} wrong cell{t.n_wrong === 1 ? '' : 's'}{t.n_different ? `, ${t.n_different} of them different text` : ', all of them in the wrong place'}</> : <>{t.n_marked} cells differ when compared as stored</>} · key {t.key_shape[0]} rows × {t.key_shape[1]} columns, pipeline {t.pipe_shape[0]} × {t.pipe_shape[1]}</span>
            </div>
            {t.featured && <p className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-1.5 max-w-4xl"><b>Featured.</b> {t.featured}</p>}
            {t.triage_note && <p className="text-xs text-gray-500 mt-1">Triage: {t.triage_note}</p>}
            {t.caption && <Marked text={t.caption} className="mt-1 text-gray-700" />}
            <div className="mt-2 max-h-[520px] overflow-auto rounded-md border border-gray-200">
              <Pic src={t.img} alt={`the printed table, ${pageName(t.stem, t.page)}`} className="w-full h-auto border-0 rounded-none" onClick={() => open(t.img, `${pageName(t.stem, t.page)}: the printed table`)} />
            </div>
            <div className="grid grid-cols-2 gap-5 mt-3">
              <Grid title="The answer key" rows={t.key} dir={t.direction} />
              {t.pipe ? <Grid title="The pipeline" rows={t.pipe} dir={t.direction} /> : <p className="text-sm text-gray-500">The pipeline has no grid for this table.</p>}
            </div>
          </div>))}
      </div>
    </Card>
  );
}

function Grid({ title, rows, dir }: { title: string; rows: any[][]; dir: string }) {
  return (
    <div className="min-w-0">
      <div className="text-sm font-medium text-gray-800 mb-1">{title}</div>
      <div className="overflow-x-auto">
        <table dir={dir} className="border-collapse text-[13px]" data-testid="grid">
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="text-[10px] text-gray-400 pr-1.5 pl-1 align-top tabular-nums">{i + 1}</td>
                {r.map((c, j) => (
                  <td key={j} title={c.why ? `${c.why}${c.tri ? ` · triage: ${TRIAGE_CLASS[c.tri.cls]?.[0] || c.tri.cls}${c.tri.sub ? ` (${c.tri.sub})` : ''}` : ''}` : undefined}
                    className={`border border-gray-200 px-1.5 py-0.5 align-top max-w-[14rem] ${c.k ? CELL_STYLE[c.k] : ''}`}>
                    <span dir="auto" className={isArabic(c.t) ? 'ar-inline' : ''}>{c.t || <span className="text-gray-300">·</span>}</span>
                  </td>))}
              </tr>))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- front matter and references

function Fields({ id, title, icon: Icon, cards, intro }: { id: string; title: string; icon: any; cards: any[]; intro: string }) {
  const [f, setF] = useState('all');
  const [n, setN] = useState(8);
  const fields = useMemo(() => {
    const c = new Map<string, number>();
    cards.forEach(x => c.set(x.field, (c.get(x.field) || 0) + 1));
    return Array.from(c.entries()).sort((a, b) => b[1] - a[1]);
  }, [cards]);
  const shown = cards.filter(x => f === 'all' || x.field === f);
  return (
    <Card id={id} title={<span className="flex items-center gap-2"><Icon className="w-4 h-4 text-indigo-600" aria-hidden />{title}</span>}>
      <p className="text-sm text-gray-600 -mt-1 max-w-4xl">{intro} Where the triage looked at a miss, its verdict is shown: <i>real pipeline error</i>, <i>scoring artefact</i> or <i>answer key issue</i>.</p>
      <div className="mt-3">
        <Pills label="Field" value={f} onChange={k => { setF(k); setN(8); }} items={[['all', 'All', cards.length], ...fields.map(([k, c]) => [k, k, c] as [string, string, number])]} />
      </div>
      <div className="mt-2 divide-y divide-gray-100" data-testid={`${id}-cards`}>
        {shown.slice(0, n).map((c, i) => <FieldCard key={i} c={c} />)}
      </div>
      <More shown={Math.min(n, shown.length)} total={shown.length} onMore={() => setN(n + 8)} />
    </Card>
  );
}

function FieldCard({ c }: { c: any }) {
  return (
    <div className="grid grid-cols-2 gap-6 py-5" data-testid="field-card">
      <div className="min-w-0 space-y-2">
        {c.crops.length ? c.crops.map((k: any, i: number) => (
          <div key={i}>
            <div className="flex justify-end"><Pic src={k.img} alt="where it is printed" className="max-w-full h-auto max-h-64" /></div>
            <div className="text-[11px] text-gray-400 text-right mt-0.5">page {k.page}, line{k.lines.length > 1 ? 's' : ''} {k.lines.length > 1 ? `${k.lines[0]}–${k.lines[k.lines.length - 1]}` : k.lines[0]}</div>
          </div>))
          : <div className="text-xs text-gray-400 bg-gray-50 rounded-md border border-dashed border-gray-200 px-3 py-4">The printed place of this value was not found on the article&apos;s first and last pages.</div>}
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <span className="font-medium text-gray-900">{c.field}{c.lang ? <span className="text-gray-400 font-normal"> ({c.lang === 'ar' ? 'Arabic' : c.lang === 'en' ? 'English' : c.lang})</span> : null}</span>
          <span className="text-xs px-1.5 py-0.5 rounded border border-gray-200 bg-gray-50 text-gray-700">{c.kind_plain}</span>
          <span className="text-xs text-gray-400">{c.stem}{c.page ? `, page ${c.page}, reference ${c.ref + 1}` : ''}</span>
        </div>
        {c.author && <div className="text-xs text-gray-500 mb-1">for <span dir="auto" className={isArabic(c.author) ? 'ar-inline' : ''}>{c.author}</span></div>}
        <div className="space-y-2">
          <div><div className="text-xs text-gray-500">The key (as printed)</div><Marked segs={c.key_segs} text={c.key_segs ? undefined : c.key} /></div>
          <div><div className="text-xs text-gray-500">What the pipeline stored</div><Marked segs={c.pipe_segs} text={c.pipe_segs ? undefined : c.pipe} /></div>
        </div>
        {c.triage && <div className="mt-2.5"><TriageChip t={c.triage} full /></div>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- real pipeline errors (triage section 4)

function Errors({ kinds }: { kinds: any[] }) {
  if (!kinds?.length) return null;
  return (
    <Card id="errors" title={<span className="flex items-center gap-2"><Sparkles className="w-4 h-4 text-indigo-600" aria-hidden />The real pipeline errors, seen on the page</span>}>
      <p className="text-sm text-gray-600 -mt-1 max-w-4xl">The triage looked at every miss and kept the ones that are the pipeline&apos;s own fault. These are the four kinds that cost the most, three examples each from different journals.</p>
      <div className="mt-4 space-y-8" data-testid="errors">
        {kinds.map(k => (
          <div key={k.kind}>
            <h3 className="font-medium text-gray-900">{k.title}</h3>
            <p className="text-sm text-gray-600">{k.text}</p>
            <div className="grid grid-cols-3 gap-5 mt-3">
              {k.cards.map((c: any, i: number) => (
                <div key={i} className="rounded-lg border border-gray-200 p-3 min-w-0" data-testid="error-card">
                  <div className="text-[11px] text-gray-400 mb-1.5">{pageName(c.stem, c.page)}{c.lines?.length ? `, line${c.lines.length > 1 ? 's' : ''} ${c.lines[0]}${c.lines.length > 1 ? `–${c.lines[c.lines.length - 1]}` : ''}` : ''}</div>
                  <div className="flex justify-end"><Pic src={c.img} alt="where it is printed" className="max-w-full h-auto max-h-44" /></div>
                  <div className="mt-2 space-y-1.5">
                    {c.text && <Marked text={c.text} className="!text-[15px] !leading-7 text-gray-700" />}
                    <div><div className="text-[11px] text-gray-500">{c.key_label}</div><Marked segs={c.key_segs} text={c.key_segs ? undefined : c.key} className="!text-[15px] !leading-7" /></div>
                    <div><div className="text-[11px] text-gray-500">{c.pipe_label}</div><Marked segs={c.pipe_segs} text={c.pipe_segs ? undefined : c.pipe} className="!text-[15px] !leading-7" /></div>
                  </div>
                  {c.why && <p className="text-[11px] text-gray-500 mt-2 leading-snug">{c.why}</p>}
                </div>))}
            </div>
          </div>))}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- limits

// "P7.found" -> "P7.found (Tables)": every internal code gets its plain name beside it
function withPlain(t: string) {
  const name: Record<string, string> = { R0: 'Nothing lost', R1: 'Reading', R2: 'Nothing lost', P1: 'Labels', P2: 'Grouping', P3: 'Reading order', P4: 'Front matter', P5: 'Sections', P6: 'Footnotes', P7: 'Tables', P8: 'Figures', P9: 'References' };
  return t.replace(/\b([RP]\d)((?:\.[a-z_]+)?)(?![\w(])/g, (m, c) => (name[c] ? `${m} (${name[c]})` : m));
}

function Limits({ limits }: { limits: string[] }) {
  if (!limits?.length) return null;
  return (
    <Card id="limits" title="Limits of this exam">
      <p className="text-sm text-gray-600 -mt-1">What these numbers cannot tell, as the scorer states it.</p>
      <ul className="mt-2 space-y-1.5 text-sm text-gray-800 list-disc pl-5 max-w-5xl" data-testid="limits">
        {limits.map((l, i) => <li key={i}>{withPlain(l)}</li>)}
      </ul>
    </Card>
  );
}

// ---------------------------------------------------------------- beyond the exam

function Beyond({ items, open }: { items: any[]; open: (s: string | null, c?: React.ReactNode) => void }) {
  return (
    <Card id="beyond" title={<span className="flex items-center gap-2"><Sparkles className="w-4 h-4 text-indigo-600" aria-hidden />What the keyers found beyond the exam</span>}>
      <p className="text-sm text-gray-600 -mt-1 max-w-4xl">Looking at every page by eye, the keyers found things no score measures.</p>
      <div className="grid grid-cols-3 gap-6 mt-3" data-testid="beyond">
        {items.map(x => (
          <figure key={`${x.stem}-${x.page}`} className="min-w-0">
            <div className="max-h-[560px] overflow-hidden rounded-md border border-gray-200">
              <Pic src={x.img} alt={`${pageName(x.stem, x.page)}`} className="w-full h-auto border-0 rounded-none" onClick={() => open(x.img, pageName(x.stem, x.page))} />
            </div>
            <figcaption className="mt-2">
              <div className="font-medium text-gray-900">{x.title}</div>
              <div className="text-xs text-gray-400">{pageName(x.stem, x.page)}</div>
              <p className="text-sm text-gray-700 mt-1 leading-relaxed">{x.text}</p>
            </figcaption>
          </figure>))}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- triage

const CODE_PLAIN: [RegExp, string][] = [
  [/^P1\b/, 'Labels'], [/^P2\b/, 'Grouping'], [/^P3\b/, 'Reading order'], [/^P4\b/, 'Front matter'], [/^P6\b/, 'Footnotes'],
  [/^P7\b/, 'Tables'], [/^P9\b/, 'References'], [/^R1\b/, 'Reading'], [/^R2\b/, 'Nothing lost'],
];
const HEAD_PLAIN: Record<string, string> = { PIPELINE: 'Real pipeline error', SCORER: 'Scoring artefact', KEY: 'Answer key issue', UNCLEAR: 'Unclear' };
const CLASS_COLOUR: Record<string, string> = { PIPELINE: '#f43f5e', SCORER: '#6366f1', KEY: '#f59e0b', UNCLEAR: '#9ca3af' };

function plainMeasure(s: string) {
  const hit = CODE_PLAIN.find(([re]) => re.test(s));
  if (!hit) return <>{s}</>;
  const code = s.match(/^\S+/)![0];
  return <>{hit[1]}: {s.slice(code.length).trim()} <span className="text-gray-400">({code})</span></>;
}
const bold = (s: string) => s.split(/\*\*/).map((x, i) => (i % 2 ? <b key={i}>{x}</b> : <React.Fragment key={i}>{x.replace(/`/g, '')}</React.Fragment>));

function shares(cells: string[], misses: string): number[] | null {
  const total = parseFloat((misses.match(/[\d.]+/) || ['NaN'])[0]);
  const v = cells.map(c => {
    const t = c.trim();
    if (/^\d+(\.\d+)?%/.test(t)) return parseFloat(t) / 100;
    if (/^\d+$/.test(t) || /^\d+ \(/.test(t)) return parseFloat(t) / total;
    return NaN;
  });
  if (v.some(x => isNaN(x))) return null;
  const sum = v.reduce((a, b) => a + b, 0);
  return sum > 0.9 && sum < 1.1 ? v : null;
}

function Triage({ t }: { t: any }) {
  if (!t) return (
    <Card id="triage" title="What the misses really are">
      <p className="text-sm text-gray-600" data-testid="triage-pending">A triage of every miss is running now. When it writes its report (experiment 97, <code>out/triage/TRIAGE.md</code>) this section fills itself: for each measure, how much of the shortfall is a real pipeline error, a scoring artefact, or an answer key issue.</p>
    </Card>);
  const tab = t.table;
  const ci = (name: string) => tab.head.findIndex((h: string) => h.trim().toUpperCase() === name);
  const cls = ['PIPELINE', 'SCORER', 'KEY', 'UNCLEAR'];
  const idx = cls.map(ci);
  const iMiss = tab.head.findIndex((h: string) => /^miss/i.test(h.trim()));
  return (
    <Card id="triage" title={<span className="flex items-center gap-2"><Scale className="w-4 h-4 text-indigo-600" aria-hidden />What the misses really are (the triage)</span>}>
      <p className="text-sm text-gray-600 -mt-1 max-w-4xl">Every miss of every measure below was looked at, against the stored data and, where needed, the page. Each was put in one of four classes:</p>
      <div className="flex flex-wrap gap-x-5 gap-y-1 mt-2 text-xs text-gray-700">
        {cls.map(k => <span key={k} className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: CLASS_COLOUR[k] }} /><b className="font-medium">{HEAD_PLAIN[k]}</b>{k === 'PIPELINE' ? ': the pipeline is wrong' : k === 'SCORER' ? ': the pipeline holds the right thing, the scorer read it wrong' : k === 'KEY' ? ': the key is wrong, or the rule is debatable' : ': could not be settled'}</span>)}
      </div>
      {t.scored_after && <p className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-3 max-w-4xl">This table was made on the earlier scores. The scorer has since been fixed for the scoring artefacts it found, and the keys for the key issues, so the scorecard at the top already includes them: read the &lsquo;raw&rsquo; column here as the old number.</p>}
      {t.estimate_note && <p className="text-xs text-gray-500 mt-2 max-w-4xl">{bold(t.estimate_note)}</p>}
      {tab && (
        <div className="overflow-x-auto mt-3">
          <table className="w-full text-sm" data-testid="triage-table">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-200">
                {tab.head.map((h: string, i: number) => <th key={i} className={`font-medium py-1.5 px-2 ${i === 0 ? 'text-left' : 'text-right'}`}>{HEAD_PLAIN[h.trim().toUpperCase()] || h.replace(/\(pipeline only\)/, '')}</th>)}
                <th className="font-medium py-1.5 px-2 text-left w-40">Shares</th>
              </tr>
            </thead>
            <tbody>
              {tab.rows.map((r: string[], k: number) => {
                const sh = iMiss >= 0 && idx.every(x => x >= 0) ? shares(idx.map(x => r[x] || ''), r[iMiss] || '') : null;
                return (
                  <tr key={k} className="border-t border-gray-100 align-top">
                    {r.map((c, i) => <td key={i} className={`py-1.5 px-2 ${i === 0 ? 'text-gray-900' : 'text-right tabular-nums text-gray-700'}`}>{i === 0 ? plainMeasure(c) : bold(c)}</td>)}
                    <td className="py-2 px-2">{sh ? (
                      <div className="flex h-3 w-36 rounded overflow-hidden bg-gray-100" title={cls.map((c, j) => `${HEAD_PLAIN[c]} ${Math.round(sh[j] * 100)}%`).join(' · ')}>
                        {sh.map((v, j) => <div key={j} style={{ width: `${v * 100}%`, background: CLASS_COLOUR[cls[j]] }} />)}
                      </div>) : null}</td>
                  </tr>);
              })}
            </tbody>
          </table>
        </div>)}
      {t.errors?.length > 0 && (
        <>
          <h3 className="text-sm font-semibold text-gray-800 mt-6">The real pipeline errors, largest first</h3>
          <ol className="mt-2 space-y-1.5 text-sm text-gray-800 list-decimal pl-5" data-testid="triage-errors">
            {t.errors.map((e: any) => <li key={e.n}><b className="font-medium">{e.title}.</b> <span className="text-gray-600">{bold(e.rest)}</span></li>)}
          </ol>
        </>)}
      <p className="text-xs text-gray-500 mt-4">From experiment 97&apos;s <code>out/triage/TRIAGE.md</code>, read as the page opens{t.done ? ` (${t.done})` : ''}.{t.scored_after ? '' : ' The scorer changes it proposes are not applied yet.'}</p>
    </Card>
  );
}
