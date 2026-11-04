import React, { useLayoutEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { User, Building2, BookOpen, Library, FileText, ArrowUpRight } from 'lucide-react';
import { roleColor, FIELD_KIND, KIND_ORDER, ENTITY_KIND, PART_LABEL, Box } from './defs';
import { fieldTimes, union } from './PageCanvas';
import { isArabic, enc } from '../../lib/api';

type V = React.CSSProperties & Record<string, any>;
const css = (o: Record<string, any>): V => o as V;
const fmt = (n: any) => (typeof n === 'number' ? n.toLocaleString('en-US') : n ?? '—');
const dirOf = (t?: string | null) => (isArabic(t) ? 'rtl' : 'ltr');
const Ar: React.FC<{ t?: string | null; className?: string }> = ({ t, className = '' }) =>
  <span dir="auto" className={`${isArabic(t) ? 'ar-inline font-naskh' : ''} ${className}`}>{t}</span>;

// line ids 12,13,14,17 → "1:12–1:14, 1:17"
export function spans(page: number, ns: number[]) {
  if (!ns.length) return '—';
  const s = [...ns].sort((a, b) => a - b), out: string[] = [];
  let a = s[0], b = s[0];
  for (const n of s.slice(1).concat([NaN])) {
    if (n === b + 1) { b = n; continue; }
    out.push(a === b ? `${page}:${a}` : `${page}:${a}–${page}:${b}`);
    a = b = n;
  }
  return out.join(', ');
}

export const Tiles: React.FC<{ items: { n: any; label: string }[]; k: string }> = ({ items, k }) => (
  <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.min(items.length, 4)}, minmax(0, 1fr))` }}>
    {items.map((x, i) => (
      <div key={`${k}-${i}`} className="pl-anim pl-rise bg-white border border-gray-200 rounded-xl px-3 py-2" style={css({ '--d': 150 + i * 120, '--t': 500 })}>
        <div className="text-xl font-semibold text-gray-900 tabular-nums leading-tight">{fmt(x.n)}</div>
        <div className="text-[11.5px] text-gray-500 leading-snug">{x.label}</div>
      </div>
    ))}
  </div>
);

export function tilesFor(key: string, d: any) {
  const c = d.counts;
  switch (key) {
    case 'scan': return [{ n: `${c.scan.page} / ${c.scan.pages}`, label: 'page of the article' },
      { n: `${c.scan.width} × ${c.scan.height}`, label: 'pixels in the scan' }, { n: `${c.scan.dpi} dpi`, label: 'scan resolution' },
      { n: d.folio || '—', label: 'printed page number' }];
    case 'azure': return [{ n: c.azure.words, label: 'words, each with its box' }, { n: c.azure.lines, label: 'numbered lines' },
      { n: c.azure.wc_mean != null ? `${(c.azure.wc_mean * 100).toFixed(1)}%` : '—', label: "Azure's mean word confidence" },
      { n: c.azure.low_wc, label: 'words below 80% confidence' }];
    case 'gemini': return [{ n: c.gemini.lines, label: 'lines given a role' }, { n: c.gemini.roles, label: 'different roles' },
      { n: c.gemini.blocks, label: 'blocks, in reading order' }, { n: c.gemini.fixes, label: 'Azure misreadings it named' }];
    case 'rules': return [{ n: c.rules.blocks, label: 'blocks in the article file' }, { n: c.rules.kept_out, label: 'kept out of the text' },
      { n: c.rules.fixes, label: 'misreadings repaired' }, { n: c.rules.flags, label: 'flags raised' }];
    case 'judge': return [{ n: c.judge.flags, label: 'flags on this page' }, { n: c.judge.judged_pages, label: 'pages of this article judged' },
      { n: c.judge.findings, label: 'problems found here' }, { n: c.judge.patches, label: 'patches on this page' }];
    case 'platform': return [{ n: c.platform.fields, label: 'fields read from this page' }, { n: c.platform.with_ink, label: 'with their ink anchor' },
      { n: c.platform.persons + c.platform.institutions + c.platform.works, label: 'people, institutions, works' },
      { n: c.platform.references || c.platform.footnotes || c.platform.headings, label: c.platform.references ? 'references' : c.platform.footnotes ? 'footnotes' : 'headings' }];
    default: return [{ n: c.index.references, label: 'references in the article' }, { n: c.index.on_cards, label: 'on a cited-work record' },
      { n: c.index.held, label: 'cited works Mandumah holds' }, { n: c.index.times_cited, label: 'times cited, in the index' }];
  }
}

const Section: React.FC<{ title: string; d?: number; children: React.ReactNode; right?: React.ReactNode }> = ({ title, d = 0, children, right }) => (
  <section className="pl-anim pl-rise bg-white border border-gray-200 rounded-xl p-3" style={css({ '--d': d, '--t': 500 })}>
    <div className="flex items-baseline justify-between gap-2 mb-1.5">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">{title}</h3>{right}
    </div>
    {children}
  </section>
);

// ------------------------------------------------------------------ 1 · scan
export function ScanPanel({ d }: { d: any }) {
  return (
    <div className="space-y-3">
      <Section title="The article" d={600}>
        <p className="text-base text-gray-900 leading-relaxed" dir={dirOf(d.title)}><Ar t={d.title} /></p>
        <p className="text-xs text-gray-500 mt-1"><Ar t={d.journal} /> · <span className="font-mono">{d.stem}</span> · {d.pages} pages</p>
      </Section>
      <Section title="What happens next" d={1100}>
        <ol className="text-sm text-gray-700 space-y-1 list-decimal ps-5">
          <li>Azure&apos;s OCR gives every word and its box.</li>
          <li>Gemini 4 Argon names each numbered line: title, byline, paragraph, footnote…</li>
          <li>Code builds the article and repairs only what is safe.</li>
          <li>A judge takes a second look where code raised a flag.</li>
          <li>Every field joins the index with its ink and a permanent id.</li>
        </ol>
      </Section>
    </div>
  );
}

// ------------------------------------------------------------------ 2 · Azure
export function AzurePanel({ d }: { d: any }) {
  const ls = d.lines.slice(0, 14);
  return (
    <Section title="Azure's numbered lines" d={300} right={<span className="text-[11px] text-gray-400">first {ls.length} of {d.lines.length}</span>}>
      <ul className="divide-y divide-gray-100">
        {ls.map((l: any, i: number) => (
          <li key={l.n} className="pl-anim pl-rise flex items-center gap-3 py-1" style={css({ '--d': 4600 + i * (2000 / Math.max(1, d.lines.length)), '--t': 450 })}>
            <span className="font-mono text-[11px] font-semibold text-teal-700 bg-teal-50 border border-teal-100 rounded-full px-2 py-0.5 shrink-0 w-14 text-center">{d.page}:{l.n}</span>
            <span className="text-sm text-gray-800 truncate flex-1 min-w-0" dir="auto"><Ar t={l.text} /></span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

// ------------------------------------------------------------------ 3 · Gemini
export function GeminiPanel({ d }: { d: any }) {
  const gb: any[] = d.answer.blocks;
  const nb = gb.length || 1;
  const counts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const b of gb) m[b.role] = (m[b.role] || 0) + b.lines.length;
    return m;
  }, [gb]);
  const sample = gb.find(b => !['running', 'page_number'].includes(b.role) && b.lines.length) || gb[0];
  const json = sample ? JSON.stringify(Object.fromEntries(Object.entries({ type: sample.type, level: sample.level ?? undefined, lang: sample.lang ?? undefined,
    lines: sample.lines.slice(0, 6).map((n: number) => `${d.page}:${n}`).concat(sample.lines.length > 6 ? ['…'] : []) }).filter(([, v]) => v !== undefined))) : '';
  return (
    <div className="space-y-3">
      <Section title="Legend" d={100}>
        <div className="flex flex-wrap gap-x-3 gap-y-1.5">
          {Object.entries(counts).map(([r, n]) => (
            <span key={r} className="inline-flex items-center gap-1.5 text-xs text-gray-700">
              <i className="w-3 h-3 rounded-[3px] border" style={{ background: `${roleColor(r)}33`, borderColor: roleColor(r) }} />{d.role_labels[r] || r}
              <span className="text-gray-400 tabular-nums">{n}</span>
            </span>
          ))}
        </div>
      </Section>
      <Section title={d.answer.source === 'masters' ? 'The roles the masters hold, in reading order' : "Gemini's answer for this page, in reading order"} d={200}>
        <ol className="space-y-0.5">
          {gb.map((b, i) => (
            <li key={i} className="pl-anim pl-rise flex items-center gap-2 text-sm py-0.5" style={css({ '--d': 300 + i * (5800 / nb), '--t': 450 })}>
              <span className="w-5 text-right text-[11px] text-gray-400 tabular-nums">{i + 1}</span>
              <i className="w-1.5 h-5 rounded-full shrink-0" style={{ background: roleColor(b.role) }} />
              <span className="w-36 shrink-0 text-gray-800 truncate">{d.role_labels[b.role] || b.role}{b.level ? <span className="text-gray-400"> · level {b.level}</span> : null}</span>
              <span className="font-mono text-[11.5px] text-gray-600 truncate flex-1 min-w-0">{spans(d.page, b.lines)}</span>
              {b.lang && b.lang !== 'ar' ? <span className="text-[10.5px] uppercase text-gray-400">{b.lang}</span> : null}
              {b.calls?.length ? <span className="text-[10.5px] text-fuchsia-700 bg-fuchsia-50 rounded px-1">{b.calls.length} note call{b.calls.length > 1 ? 's' : ''}</span> : null}
              {b.cells ? <span className="text-[10.5px] text-blue-700 bg-blue-50 rounded px-1">{b.cells} cells</span> : null}
              {b.parsed ? <span className="text-[10.5px] text-cyan-700 bg-cyan-50 rounded px-1">parsed</span> : null}
            </li>
          ))}
        </ol>
      </Section>
      {sample && (
        <Section title="What one answer looks like" d={6800}>
          <code className="block text-[12px] font-mono text-indigo-900 bg-indigo-50/60 border border-indigo-100 rounded-lg px-3 py-2 break-all">{json}</code>
          <p className="text-xs text-gray-500 mt-1.5">Line ids only: the words stay Azure&apos;s. It may name a plain misreading to repair, never the author&apos;s spelling.
            {d.answer.usd != null && d.answer.chunk ? <> This read covered pages {d.answer.chunk[0]}–{d.answer.chunk[1]} in one call (${d.answer.usd.toFixed(3)}, Batch API).</> : null}</p>
        </Section>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ 4 · code rules
const RULE_NAMES: Record<string, string> = {
  guillemets: 'guillemets «» made whole', guillemet_halves: 'guillemet halves joined', trans_titles: 'translated title kept apart',
  never_noise: 'lines with words put back (never noise)', letters: 'Persian look-alike letters fixed', ornaments_code: 'ornaments taken out of the text',
  pictures: 'pictures drawn from the ink', figure_trim: 'figure boxes trimmed', table_cells_added: 'table cells added (D35)',
  show_through: 'show-through kept out', other_article_blocks: 'another article kept out', text_in_figure: 'text inside a figure',
  page_numbers: 'page numbers', header_text: 'running heads', long_headings: 'long headings checked', cuts: 'verse halves cut',
  enrich: 'enrich part checked', boxed_blocks: 'boxed blocks', endnotes: 'endnotes linked', table_columns: 'table columns',
};
export function RulesPanel({ d }: { d: any }) {
  const roles = useMemo(() => {
    const m: Record<string, number> = {};
    for (const b of d.blocks) m[b.role] = (m[b.role] || 0) + 1;
    return Object.entries(m).sort((a, b) => b[1] - a[1]);
  }, [d.blocks]);
  return (
    <div className="space-y-3">
      <Section title="Blocks built from the lines" d={300} right={<span className="text-xs text-gray-500 tabular-nums">{d.blocks.length}</span>}>
        <div className="flex flex-wrap gap-1.5">
          {roles.map(([r, n]) => <span key={r} className="text-xs rounded-full border px-2 py-0.5 text-gray-700 bg-gray-50">{r.replace('-', ' ')} <b className="tabular-nums">{n}</b></span>)}
        </div>
      </Section>
      <Section title="Kept out of the article's text" d={3700}>
        {d.regions.length ? (
          <ul className="text-sm text-gray-700 space-y-0.5">
            {d.regions.map((r: any) => <li key={r.id} className="flex gap-2"><span className="text-gray-500 w-28 shrink-0">{d.role_labels[r.shown] || r.role}</span><Ar t={r.text} className="truncate" /></li>)}
          </ul>
        ) : <p className="text-sm text-gray-500">Nothing on this page.</p>}
      </Section>
      <Section title="Azure misreadings repaired" d={4800} right={<span className="text-xs text-gray-500 tabular-nums">{d.fixes.length}</span>}>
        {d.fixes.length ? (
          <ul className="text-sm space-y-1 max-h-48 overflow-auto">
            {d.fixes.slice(0, 30).map((f: any, i: number) => (
              <li key={i} className="flex flex-wrap items-center gap-x-2">
                <span className="line-through decoration-gray-400 text-gray-500"><Ar t={f.azure} /></span><span className="text-gray-400">→</span>
                <span className="text-green-800 font-medium"><Ar t={f.printed} /></span>
                <span className="text-xs text-gray-500">{(f.why || '').replace(/^code: /, '').replace(/ \(.*$/, '')}{f.by === 'code' ? ' · by code' : ' · named by Gemini'}</span>
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-gray-500">None needed on this page: the text is exactly Azure&apos;s.</p>}
        <p className="text-xs text-gray-500 mt-1.5">The letter fix: Azure writes Persian look-alike letters (ی ک ہ ھ ڪ) where the print shows Arabic ones; code writes the Arabic letter and keeps Azure&apos;s word beside it.</p>
      </Section>
      {d.misprints.length > 0 && (
        <Section title="Misprints kept as printed (flagged, never changed)" d={5600}>
          <ul className="text-sm space-y-1">
            {d.misprints.map((f: any, i: number) => <li key={i}><Ar t={f.printed} /> <span className="text-gray-400">· proposed</span> <Ar t={f.proposed} /> <span className="text-xs text-gray-500">{f.why}</span></li>)}
          </ul>
        </Section>
      )}
      <Section title="Flags raised" d={6400}>
        {d.flags.length ? (
          <ul className="text-sm space-y-1">{d.flags.map((f: any, i: number) => <li key={i}><span className="text-red-700 font-medium">{f.kind.replace(/_/g, ' ')}</span> <span className="text-xs text-gray-500">({f.severity})</span> <span className="text-gray-700">{f.reason}</span></li>)}</ul>
        ) : <p className="text-sm text-gray-500">None on this page.</p>}
      </Section>
      <Section title="Written as masters" d={6900}>
        <p className="text-sm text-gray-700">JATS 1.4 (the article) and ALTO 4.4 (every word on the page), checked against the official DTD and XSD on every build. Word ids such as <span className="font-mono text-xs">p{d.page}w0001</span> are shared by both files.</p>
        {d.rules_fired.length > 0 && <p className="text-xs text-gray-500 mt-1.5">Rules that acted on pages {d.answer.chunk ? `${d.answer.chunk[0]}–${d.answer.chunk[1]}` : 'of this part'}: {d.rules_fired.map((r: any) => RULE_NAMES[r.rule] || r.rule.replace(/_/g, ' ')).join(' · ')}.</p>}
      </Section>
    </div>
  );
}

// ------------------------------------------------------------------ 5 · judge
export function JudgePanel({ d }: { d: any }) {
  const j = d.judge;
  return (
    <div className="space-y-3">
      <Section title="This page" d={300}>
        <p className="text-sm text-gray-700">{d.counts.judge.this_page
          ? (((j.calls.find((c: any) => c.page === d.page) || {}).verdict === 'clean') ? 'The judge looked at this page and found it clean.' : 'The judge looked at this page and named a problem:')
          : d.flags.length ? 'This page carries flags.' : 'No flags here, so no second look was needed.'}</p>
        {j.findings.length > 0 && <ul className="mt-1 text-sm space-y-0.5">{j.findings.map((f: any, i: number) => <li key={i}>{f.type}{f.subtype ? ` · ${f.subtype}` : ''} <span className="text-xs text-gray-500">confidence {f.confidence ?? '—'} · route {f.route}</span></li>)}</ul>}
      </Section>
      <Section title="This article" d={900}>
        {j.calls.length ? (
          <div className="flex flex-wrap gap-1.5">{j.calls.map((c: any, i: number) => (
            <span key={i} className={`text-xs rounded-full border px-2 py-0.5 ${c.verdict === 'clean' ? 'bg-green-50 border-green-200 text-green-800' : 'bg-indigo-50 border-indigo-200 text-indigo-800'}`}>page {c.page} · {c.verdict}</span>))}</div>
        ) : <p className="text-sm text-gray-500">No page of this article needed a second look.</p>}
        <p className="text-sm text-gray-700 mt-2">{j.patches.length ? `${j.patches.length} patch${j.patches.length > 1 ? 'es' : ''} in this article: ${j.patches.map((p: any) => `page ${p.page}: ${p.op.replace(/_/g, ' ')} by the ${p.source}, ${({ applied: 'applied', proposed: 'proposed, not applied', skipped: 'skipped', overridden: 'overridden' } as any)[p.status] || p.status || 'kept'}`).join('; ')}.` : 'No patches: the masters stand as built.'}</p>
      </Section>
      <Section title="How a patch gets in" d={1500}>
        <ol className="text-sm text-gray-700 space-y-1 list-decimal ps-5">
          <li>The judge sees the scan, the scan with our blocks numbered, and our layout of the page.</li>
          <li>It answers with a problem type, its targets, its confidence and a proposed edit.</li>
          <li>The edit applies only with both keys: confidence ≥ 0.85 and a code check against the scan and Azure.</li>
          <li>It is stored as a patch beside the master, never written into it. A person&apos;s patch outranks the judge&apos;s.</li>
        </ol>
      </Section>
    </div>
  );
}

// ------------------------------------------------------------------ 6 · fields fly into cards, cards join entities
const EntIcon: Record<string, any> = { person: User, institution: Building2, work: BookOpen, journal: Library, publication: FileText };

export function FieldRows({ f, d }: { f: any; d: any }) {
  if (f.kind === 'author') return (
    <div dir={dirOf(f.value)}><div className="text-[15px] text-gray-900"><Ar t={f.value} /></div>
      <div className="text-xs text-gray-500" dir="ltr" style={{ textAlign: isArabic(f.value) ? 'right' : 'left' }}>{[f.titles, f.role, f.email, f.twin ? 'the same author, in English' : null].filter(Boolean).join(' · ')}</div></div>);
  if (f.kind === 'affiliation') return (
    <div dir={dirOf(f.value)}><div className="text-sm text-gray-800"><Ar t={f.value} /></div>
      <div className="flex flex-wrap gap-1 mt-1">{(f.parts || []).map((p: any, i: number) => (
        <span key={i} dir="ltr" className="text-[11.5px] rounded-md border border-teal-200 bg-teal-50/60 px-1.5 py-0.5"><span className="text-teal-700">{PART_LABEL[p.part] || p.part}</span> <Ar t={p.value} className="text-gray-800" /></span>))}</div></div>);
  if (f.kind === 'abstract') return <p className="text-sm text-gray-700 line-clamp-3 leading-relaxed" dir={dirOf(f.value)}><Ar t={f.value} /></p>;
  if (f.kind === 'heading') return <div className="text-sm text-gray-900" dir={dirOf(f.value)} style={{ paddingInlineStart: `${Math.max(0, (f.level || 2) - 2) * 14}px` }}><Ar t={f.value} /></div>;
  if (f.kind === 'footnote') return <p className="text-sm text-gray-700 line-clamp-2" dir={dirOf(f.value)}><Ar t={f.value} /></p>;
  if (f.kind === 'table') {
    const rows = Math.min(4, Math.max(0, ...f.cells.map((c: any) => c.r)) + 1), cols = Math.min(6, Math.max(0, ...f.cells.map((c: any) => c.c)) + 1);
    const at = (r: number, c: number) => f.cells.find((x: any) => x.r === r && x.c === c);
    return (
      <div><div className="grid gap-px bg-gray-200 border border-gray-200 rounded overflow-hidden text-[10.5px]" dir="rtl" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0,1fr))` }}>
        {Array.from({ length: rows * cols }).map((_, i) => { const x = at(Math.floor(i / cols), i % cols); return (
          <div key={i} className={`px-1 py-0.5 truncate ${x?.th ? 'bg-blue-50 text-blue-900 font-medium' : 'bg-white text-gray-700'}`} dir="auto"><Ar t={x?.t || ''} /></div>); })}
      </div><div className="text-[11px] text-gray-500 mt-0.5">{f.value}{f.caption ? <> · <Ar t={f.caption} /></> : null}</div></div>);
  }
  if (f.kind === 'reference') return (
    <div dir={dirOf(f.value)}><div className="text-[13px] text-gray-700 line-clamp-2"><Ar t={f.value} /></div>
      <div className="flex flex-wrap gap-1 mt-1">{(f.parts || []).map((p: any, i: number) => (
        <span key={i} dir="ltr" className="text-[11px] rounded-md border border-cyan-200 bg-cyan-50/60 px-1.5 py-0.5 max-w-full truncate"><span className="text-cyan-700">{PART_LABEL[p.part] || p.part}</span> <Ar t={p.value} className="text-gray-800" /></span>))}</div></div>);
  return <div className="text-[15px] text-gray-900 leading-snug" dir={dirOf(f.value)}><Ar t={f.value} /></div>;
}

export type Ghost = { id: string; left: number; top: number; w: number; h: number; fx: number; fy: number; s: number; bg: string; bs: string; bp: string; d: number; t: number; color: string };

export function PlatformPanel({ d, hover, setHover, canvasRef, rootRef, onGhosts, done }: {
  d: any; hover: string | null; setHover: (h: string | null) => void; canvasRef: React.RefObject<HTMLDivElement>;
  rootRef: React.RefObject<HTMLDivElement>; onGhosts: (g: Ghost[]) => void; done: boolean;
}) {
  const fields: any[] = d.fields;
  const ft = fieldTimes(fields.length);
  const ORDER = ['publication', 'person', 'institution', 'work', 'journal'];
  const ents: any[] = [...d.entities].sort((a: any, b: any) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind));
  const eStart = ft.start + fields.length * ft.per + ft.fly;
  const eper = Math.min(380, 2600 / Math.max(1, ents.length));
  const groups = KIND_ORDER.map(k => ({ k, fs: fields.filter(f => f.kind === k) })).filter(g => g.fs.length);
  const wrap = useRef<HTMLDivElement>(null);
  const [links, setLinks] = useState<{ d: string; key: string; delay: number; len: number; color: string; from: string }[]>([]);

  useLayoutEffect(() => {
    const root = rootRef.current, cv = canvasRef.current, w = wrap.current;
    if (!root || !cv || !w) return;
    const R = root.getBoundingClientRect(), C = cv.getBoundingClientRect(), Wr = w.getBoundingClientRect();
    const sc = C.width / d.frame.w;
    const gh: Ghost[] = [];
    fields.forEach((f, i) => {
      const el = w.querySelector(`[data-fid="${f.id}"]`) as HTMLElement | null;
      const b = union(f.boxes);
      if (!el || !b || !d.image) return;
      const E = el.getBoundingClientRect();
      const aspect = b.h / b.w;
      let dw = E.width, dh = dw * aspect;
      const maxH = Math.min(Math.max(E.height, 40), 96);
      if (dh > maxH) { dh = maxH; dw = dh / aspect; }
      let top = E.top - R.top;
      top = Math.min(Math.max(top, Wr.top - R.top), Wr.bottom - R.top - dh);      // a card below the fold: land at the panel's edge
      const left = (isArabic(f.value) ? E.right - dw : E.left) - R.left;   // Arabic lands at the right, where its text starts
      const srcL = C.left - R.left + b.x * sc, srcT = C.top - R.top + b.y * sc;
      const k = dw / b.w;
      gh.push({ id: f.id, left, top, w: dw, h: dh, fx: srcL - left, fy: srcT - top, s: (b.w * sc) / dw,
        bg: d.image_url, bs: `${d.frame.w * k}px ${d.frame.h * k}px`, bp: `${-b.x * k}px ${-b.y * k}px`,
        d: ft.start + i * ft.per, t: ft.fly, color: (FIELD_KIND[f.kind] || {}).color || '#475569' });
    });
    onGhosts(gh);
    // connectors: from each field row to the entity chips it resolves to
    const ls: any[] = [];
    ents.forEach((e, j) => {
      const chip = w.querySelector(`[data-eid="${e.id}"]`) as HTMLElement | null;
      if (!chip) return;
      const Ch = chip.getBoundingClientRect();
      const from = fields.filter(f => (f.entities || []).includes(e.id));
      for (const f of from) {
        const el = w.querySelector(`[data-fid="${f.id}"]`) as HTMLElement | null;
        if (!el) continue;
        const E = el.getBoundingClientRect();
        const x1 = E.right - Wr.left + 4, y1 = E.top + Math.min(E.height / 2, 18) - Wr.top + w.scrollTop;
        const x2 = Ch.left - Wr.left - 4, y2 = Ch.top + Ch.height / 2 - Wr.top + w.scrollTop;
        const mx = (x1 + x2) / 2;
        ls.push({ key: `${f.id}-${e.id}`, from: f.id, d: `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`, delay: eStart + j * eper,
          len: Math.ceil(Math.hypot(x2 - x1, y2 - y1) * 1.3), color: ENTITY_KIND[e.kind]?.color || '#64748b' });
      }
    });
    setLinks(ls);
    return () => onGhosts([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d]);

  const fi = (f: any) => fields.indexOf(f);
  return (
    <div ref={wrap} className="relative grid grid-cols-[minmax(0,1fr)_minmax(0,15rem)] gap-x-10 gap-y-3 items-start overflow-auto h-full pr-1" data-testid="pl-platform">
      <div className="space-y-3 min-w-0">
        {groups.length === 0 && <p className="text-sm text-gray-500">This page holds running text only: its paragraphs go to the article&apos;s body and its search chunks.</p>}
        {groups.map(g => (
          <section key={g.k} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider px-3 pt-2 pb-1 flex items-center gap-1.5" style={{ color: FIELD_KIND[g.k].color }}>
              <i className="w-2 h-2 rounded-full" style={{ background: FIELD_KIND[g.k].color }} />{FIELD_KIND[g.k].title}</h3>
            <div className="divide-y divide-gray-100">
              {g.fs.map(f => (
                <div key={f.id} data-fid={f.id} onMouseEnter={() => setHover(f.id)} onMouseLeave={() => setHover(null)}
                  className={`pl-anim pl-fade px-3 py-1.5 cursor-default transition-colors ${hover === f.id ? 'bg-indigo-50/70' : ''}`}
                  style={css({ '--d': ft.start + fi(f) * ft.per + ft.fly * 0.7, '--t': 500 })}>
                  {f.label !== FIELD_KIND[g.k].title && !['author', 'affiliation', 'reference', 'heading', 'footnote'].includes(f.kind) && <div className="text-[11px] text-gray-400">{f.label}</div>}
                  <FieldRows f={f} d={d} />
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
      <div className="space-y-2 min-w-0 sticky top-0">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 pl-anim pl-fade" style={css({ '--d': eStart - 300, '--t': 400 })}>Records with permanent ids</h3>
        {ents.length === 0 && <p className="text-xs text-gray-500">No person, institution or cited work is printed on this page.</p>}
        {ents.map((e, j) => {
          const Icon = EntIcon[e.kind] || FileText;
          const k = ENTITY_KIND[e.kind] || ENTITY_KIND.work;
          const on = hover && fields.some(f => f.id === hover && (f.entities || []).includes(e.id));
          return (
            <div key={e.id} data-eid={e.id} className={`pl-anim pl-pop rounded-xl border px-2.5 py-1.5 bg-white transition-shadow ${on ? 'ring-2 ring-indigo-300' : ''}`}
              style={css({ '--d': eStart + j * eper, '--t': 500, borderColor: `${k.color}55` })}>
              <div className="flex items-center gap-1.5 text-[11px]" style={{ color: k.color }}><Icon className="w-3.5 h-3.5" aria-hidden />{k.label}
                <span className="ml-auto font-mono font-semibold tracking-tight">{e.id}</span></div>
              <div className="text-[13px] text-gray-900 truncate" dir={dirOf(e.name || e.latin)}><Ar t={e.name || e.latin} /></div>
              <div className="text-[11px] text-gray-500">{e.kind === 'publication' ? 'this article, by its catalogue number' : e.kind === 'work' ? `cited by ${fmt(e.n_citing)} article${e.n_citing === 1 ? '' : 's'} in the index`
                : e.n_articles != null ? `${fmt(e.n_articles)} article${e.n_articles === 1 ? '' : 's'} in the index` : ''}</div>
            </div>
          );
        })}
      </div>
      <svg className="absolute inset-0 pointer-events-none overflow-visible" width="100%" height="100%" aria-hidden>
        {links.map(l => (
          <path key={l.key} d={l.d} fill="none" stroke={l.color} strokeOpacity={hover === l.from ? 0.95 : 0.45} strokeWidth={hover === l.from ? 2 : 1.3}
            className="pl-anim pl-draw" strokeDasharray={l.len} style={css({ '--d': l.delay, '--t': 700, '--len': l.len, strokeDashoffset: 0 })} />
        ))}
      </svg>
    </div>
  );
}

export function GhostLayer({ ghosts }: { ghosts: Ghost[] }) {
  return (
    <div className="absolute inset-0 pointer-events-none z-10" aria-hidden>
      {ghosts.map(g => (
        <div key={g.id} className="pl-anim pl-fly absolute rounded-md bg-white" style={css({
          left: g.left, top: g.top, width: g.w, height: g.h, '--fx': `${g.fx}px`, '--fy': `${g.fy}px`, '--s': g.s, '--d': g.d, '--t': g.t,
          backgroundImage: `url(${g.bg})`, backgroundSize: g.bs, backgroundPosition: g.bp, backgroundRepeat: 'no-repeat',
          outline: `2px solid ${g.color}`, outlineOffset: 0 })} />
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ 7 · the index record
export function IndexPanel({ d }: { d: any }) {
  const x = d.index;
  const maxC = Math.max(1, ...x.top_works.map((w: any) => w.n_citing || 0));
  return (
    <div className="space-y-3 overflow-auto h-full pr-1" data-testid="pl-index">
      <Section title="The record in the index" d={200} right={<span className="font-mono text-[11px] text-indigo-700">{x.pub_id}</span>}>
        <h2 className="text-lg text-gray-900 leading-relaxed" dir={dirOf(x.title)}><Ar t={x.title} /></h2>
        {x.translated && <p className="text-sm text-gray-500 mt-0.5" dir="auto">{x.translated}</p>}
        <div className="mt-2 space-y-1.5">
          {x.authors.map((a: any) => (
            <div key={a.id || a.name} className="flex flex-wrap items-center gap-1.5 text-sm">
              <User className="w-3.5 h-3.5 text-teal-700" aria-hidden />
              {a.id ? <Link href={`/persons/${enc(a.id)}`} className="text-gray-900 hover:underline"><Ar t={a.name} /></Link> : <Ar t={a.name} />}
              {a.latin && <span className="text-gray-500 text-xs">{a.latin}</span>}
              {a.id && <span className="font-mono text-[11px] text-teal-700 bg-teal-50 rounded px-1">{a.id}</span>}
              {a.institutions.map((i: any) => <span key={i.id} className="text-xs text-gray-600 inline-flex items-center gap-1"><Building2 className="w-3 h-3 text-teal-600" aria-hidden /><Ar t={i.name} /> <span className="font-mono text-[10.5px] text-teal-700">{i.id}</span></span>)}
            </div>
          ))}
        </div>
        <p className="text-sm text-gray-700 mt-2 flex flex-wrap items-center gap-1.5">
          <Library className="w-3.5 h-3.5 text-indigo-600" aria-hidden />
          {x.journal.id ? <Link href={`/journals/${enc(x.journal.id)}`} className="hover:underline"><Ar t={x.journal.title} /></Link> : <Ar t={x.journal.title} />}
          <span className="font-mono text-[11px] text-indigo-700 bg-indigo-50 rounded px-1">{x.journal.id}</span>
          <span className="text-gray-500">· <Ar t={x.issue} /> · {x.year}{x.fpage ? ` · pp. ${x.fpage}–${x.lpage}` : ''} · {(x.doc_type || '').replace(/_/g, ' ')}</span>
        </p>
      </Section>
      <Section title="What it cites, most-cited first" d={900} right={<span className="text-[11px] text-gray-400">times cited across the index</span>}>
        <ul className="space-y-1.5">
          {x.top_works.map((w: any, i: number) => (
            <li key={w.id} className="grid grid-cols-[minmax(0,1fr)_9rem] items-center gap-3">
              <Link href={`/works/${enc(w.id)}`} className="text-sm text-gray-800 truncate hover:underline" dir="auto"><Ar t={w.title} /> <span className="font-mono text-[10.5px] text-cyan-700">{w.id}</span></Link>
              <div className="flex items-center gap-2">
                <div className="h-2 rounded-full bg-cyan-600 pl-anim pl-bar" style={css({ width: `${Math.max(4, (w.n_citing / maxC) * 100)}%`, '--d': 1200 + i * 180, '--t': 900 })} />
                <span className="text-xs text-gray-600 tabular-nums">{w.n_citing}</span>
              </div>
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Who cites it" d={1700}>
        {x.cited_by.length ? (
          <ul className="text-sm space-y-0.5">{x.cited_by.map((c: any, i: number) => <li key={i}><Link href={`/articles/${enc(c.stem)}`} className="hover:underline"><Ar t={c.title || c.stem} /></Link></li>)}</ul>
        ) : <p className="text-sm text-gray-600">Not cited yet by the {fmt((d.entities.find((e: any) => e.kind === 'journal') || {}).n_articles || 0)} articles of its journal read so far; every new release counts again.</p>}
      </Section>
      <div className="pl-anim pl-rise flex flex-wrap gap-2" style={css({ '--d': 2200, '--t': 500 })}>
        <Link href={`/articles/${enc(d.stem)}`} className="inline-flex items-center gap-1 text-sm rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-indigo-700 hover:bg-indigo-50">Open the article in the Desk <ArrowUpRight className="w-3.5 h-3.5" /></Link>
        {x.journal.id && <Link href={`/journals/${enc(x.journal.id)}`} className="inline-flex items-center gap-1 text-sm rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-indigo-700 hover:bg-indigo-50">The journal&apos;s page <ArrowUpRight className="w-3.5 h-3.5" /></Link>}
      </div>
    </div>
  );
}
