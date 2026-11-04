import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookMarked, Check, X, HelpCircle, Search, ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react';
import Layout from '../components/Layout';
import { Btn, Card, Chip, Crop, Empty, ErrorBox, Tile, T, actorName, n, when } from '../components/Bits';
import { api, cropOfAnchor, enc } from '../lib/api';
import { useApi } from '../lib/me';
import { useShowMode } from '../lib/showmode';
import { AppliedBanner, ProductionLibrarian } from '../components/LibrarianBits';

// The librarian (experiment 56, 2026-10-23): the AI curator's first pass over institutions. Its decisions are
// proposals (experiments/56_librarian_institutions/out/decisions56.jsonl); nothing is applied. The owner checks a
// stratified random sample of 30 here (Yes / No / Unsure, stored append-only in librarian_verdicts) and can browse
// every decision with filters. API: desk/librarian.py.

type Verdict = { verdict_id: number; decision_id: string; verdict: 'yes' | 'no' | 'unsure'; comment: string | null;
  author: string; author_name: string; created_at: string; n_verdicts?: number };
type Ev = { key: string; stem: string; journal: string; year: number; author: string; printed: string; parts: any;
  byline_anchor?: string | null; page?: number | null; lines: string[]; machine: Record<string, { inst_id: string; names: string[]; country: string | null }>;
  catalogue: { univ: string; countries: Record<string, number> }[]; same_article: string[] };
type Item = { stratum: string; decision_id: string; kind: string; level: string; question: string | null; decision: any;
  reason: string | null; confidence: string; basis: string; trivial: boolean; printed?: string; evidence: Ev[]; verdict: Verdict | null };

const KIND_LABEL: Record<string, string> = {
  affiliation_institution: 'Affiliation → institution', unit_kept_apart: 'Faculty kept apart', not_an_institution: 'Not an institution',
  unsure: 'Unsure', same_institution: 'Same institution (merge)', not_same_institution: 'Not the same (split)',
  set_country: 'Country', set_parent: 'Parent', set_type: 'Type',
};
const CONF_TONE: Record<string, 'green' | 'amber' | 'red' | 'gray'> = { high: 'green', medium: 'amber', low: 'red' };
const BASIS_LABEL: Record<string, string> = { rule: 'printed name (rule)', catalogue: 'catalogue', world: 'world knowledge',
  context: 'same article / journal', judgement: 'judgement' };

const cropOfLines = (stem: string, page?: number | null, lines?: string[]) =>
  page && lines && lines.length ? `/desk/api/evidence/crop?stem=${enc(stem)}&page=${page}&lines=${enc(lines.join(','))}` : null;

// what the decision says, in one line
function Says({ d, kind }: { d: any; kind: string }) {
  const inst = (d.institutions || []).map((i: any) => i.name_ar + (i.name_en ? ` (${i.name_en})` : '')).join(' + ');
  if (kind === 'affiliation_institution') return <span><T text={inst} />{d.country ? <> · <Chip>{d.country}</Chip></> : null}
    {d.machine_agrees === false && <> <span className="text-xs text-gray-500">machine linked «<T text={(d.machine_org_names || [])[0] || 'nothing'} />»</span></>}</span>;
  if (kind === 'same_institution') return <span>One body: <T text={d.name_ar} /> ({d.name_en}) ← {Object.values(d.machine_rows || {}).map((ns: any, i) =>
    <span key={i} className="inline-block mx-1 px-1.5 rounded bg-gray-100"><T text={(ns && ns[0]) || '(no name)'} /></span>)}{d.bilingual_twin && <Chip tone="indigo">two scripts</Chip>}</span>;
  if (kind === 'not_same_institution') return <span>«<T text={(d.names || [])[0]} />» holds {Object.keys(d.groups || {}).length} different bodies:{' '}
    {Object.entries(d.groups || {}).map(([g, ks]: any) => <span key={g} className="inline-block mx-1 px-1.5 rounded bg-gray-100 text-xs"><T text={(d.group_names || {})[g] || g} /> ×{ks.length}</span>)}</span>;
  if (kind === 'set_country') return <span>«<T text={(d.names || [])[0]} />» is in <b>{d.country}</b>{d.was ? <> (machine: {d.was})</> : <> (machine: none)</>}</span>;
  if (kind === 'set_parent') return <span>«<T text={(d.names || [])[0]} />» is part of <T text={d.parent_name} /></span>;
  if (kind === 'set_type') return <span>«<T text={(d.names || [])[0]} />» is a <b>{d.type}</b> (machine: {d.was})</span>;
  if (kind === 'unit_kept_apart') return <span>Faculty «<T text={d.faculty} />» kept as its own unit (university not printed)</span>;
  if (kind === 'not_an_institution') return <span>No institution printed</span>;
  return <span>Left as the machine has it, marked unsure</span>;
}

function VerdictButtons({ item, onSaved }: { item: { decision_id: string; verdict: Verdict | null }; onSaved: (v: Verdict) => void }) {
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const send = async (verdict: string) => {
    setBusy(true); setErr('');
    try { const v = await api<Verdict>('/librarian/verdicts', { json: { decision_id: item.decision_id, verdict, comment } }); onSaved(v); setComment(''); }
    catch (e: any) { setErr(String(e.message || e)); } finally { setBusy(false); }
  };
  const cur = item.verdict?.verdict;
  const b = (v: string, label: string, Icon: any, tone: string) => (
    <button disabled={busy} onClick={() => send(v)} data-testid={`verdict-${v}`}
      className={`px-3 py-1.5 rounded-lg text-sm font-medium border flex items-center gap-1.5 disabled:opacity-50 ${cur === v ? tone : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'}`}>
      <Icon className="w-4 h-4" aria-hidden />{label}</button>);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {b('yes', 'Yes', Check, 'bg-green-600 border-green-600 text-white')}
        {b('no', 'No', X, 'bg-red-600 border-red-600 text-white')}
        {b('unsure', 'Unsure', HelpCircle, 'bg-amber-500 border-amber-500 text-white')}
        <input value={comment} onChange={e => setComment(e.target.value)} placeholder="Comment (optional)" maxLength={4000}
          className="flex-1 min-w-[12rem] rounded-lg border-gray-300 text-sm py-1.5" />
      </div>
      {item.verdict && <p className="text-xs text-gray-500">Your latest: <b>{item.verdict.verdict}</b> by {item.verdict.author_name || actorName(item.verdict.author)}, {when(item.verdict.created_at)}
        {item.verdict.comment ? <> — “{item.verdict.comment}”</> : null}{item.verdict.n_verdicts && item.verdict.n_verdicts > 1 ? <> ({item.verdict.n_verdicts} verdicts, all kept)</> : null}</p>}
      {err && <ErrorBox>{err}</ErrorBox>}
    </div>);
}

function Evidence({ e }: { e: Ev }) {
  const lines = cropOfLines(e.stem, e.page, e.lines);
  const m = e.machine?.org;
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50/60 p-3 space-y-1.5" data-testid="evidence">
      <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
        <Link href={`/articles/${enc(e.stem)}`} className="font-mono text-indigo-700 hover:underline">{e.stem}</Link>
        <span><T text={e.journal} /></span>{e.year ? <span>{e.year}</span> : null}
        <span>· <T text={e.author} /></span>
      </div>
      {lines ? <Crop src={lines} maxH="max-h-28" rtl /> : e.byline_anchor ? <Crop src={cropOfAnchor(e.byline_anchor)} maxH="max-h-16" rtl /> : null}
      <p className="text-sm text-gray-800"><T text={e.printed} /></p>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500">
        {m && <span>machine: <T text={m.names?.[0] || '(no name)'} /> <span className="font-mono">{m.inst_id}</span>{m.country ? ` ${m.country}` : ' (no country)'}</span>}
        {e.machine?.faculty && <span>faculty row: <T text={e.machine.faculty.names?.[0]} /></span>}
        {(e.catalogue || []).map((c, i) => <span key={i}>catalogue 502: <T text={c.univ} /> {Object.entries(c.countries).map(([k, v]) => `${k} ${v}`).join(', ')}</span>)}
        {(e.same_article || []).length > 0 && <span>same author here: {(e.same_article || []).map((s, i) => <T key={i} text={s} className="mx-1" />)}</span>}
      </div>
    </div>);
}

function SampleCard({ it, i, onSaved }: { it: Item; i: number; onSaved: (v: Verdict) => void }) {
  return (
    <Card id={`s-${it.decision_id}`} className="scroll-mt-16">
      <div className="space-y-3" data-testid="sample-item">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-mono text-gray-400">{String(i + 1).padStart(2, '0')}</span>
          <Chip tone="indigo">{it.stratum}</Chip><Chip>{KIND_LABEL[it.kind] || it.kind}</Chip>
          <Chip tone={CONF_TONE[it.confidence] || 'gray'}>{it.confidence || '—'}</Chip>
          <Chip>{BASIS_LABEL[it.basis] || it.basis}</Chip>
          <span className="text-xs font-mono text-gray-400 ml-auto">{it.decision_id}</span>
        </div>
        <p className="text-base text-gray-900"><Says d={it.decision} kind={it.kind} /></p>
        {it.reason && <p className="text-sm text-gray-600"><span className="text-gray-400">Why: </span><T text={it.reason} /></p>}
        <div className="grid md:grid-cols-2 gap-2">{it.evidence.map(e => <Evidence key={e.key} e={e} />)}</div>
        {it.evidence.length === 0 && <p className="text-xs text-gray-400">No printed affiliation attached (an institution-level fact).</p>}
        <VerdictButtons item={it} onSaved={onSaved} />
      </div>
    </Card>);
}

function Numbers({ nb }: { nb: any }) {
  if (!nb) return null;
  const b = nb.before, a = nb.after;
  const row = (label: string, x: React.ReactNode, y: React.ReactNode, note?: string) => (
    <tr className="border-t border-gray-100"><td className="py-1.5 pr-3 text-gray-700">{label}{note && <div className="text-[11px] text-gray-400">{note}</div>}</td>
      <td className="py-1.5 px-3 text-right tabular-nums text-gray-500">{x}</td><td className="py-1.5 pl-3 text-right tabular-nums font-semibold">{y}</td></tr>);
  return (
    <table className="w-full text-sm" data-testid="numbers">
      <thead><tr className="text-xs text-gray-500"><th className="text-left font-medium">On the {n(nb.articles)} articles ({n(nb.affiliations)} printed affiliations)</th>
        <th className="text-right font-medium px-3">machine today</th><th className="text-right font-medium pl-3">with the librarian</th></tr></thead>
      <tbody>
        {row('Institutions (organisation level, linked)', n(b.institutions_linked), n(a.institutions), `machine rows in all: ${n(b.institution_rows)}, of them ${n(b.faculty_department_rows)} faculties/departments`)}
        {row('Institutions in 2+ articles', n(b.institutions_2plus_articles), n(a.institutions_2plus_articles))}
        {row('Affiliations linked to an institution', n(b.affiliations_with_institution), n(a.affiliations_with_institution))}
        {row('Share of institutions with a country', `${Math.round(100 * b.share_institutions_with_country)}%`, `${Math.round(100 * a.share_institutions_with_country)}%`,
          `machine rows without a country: ${n(b.rows_without_country)} of ${n(b.institution_rows)}`)}
        {row('Affiliations with a country', n(b.affiliations_with_country), n(a.affiliations_with_country))}
        {row('Gate 1 journal (0130): institutions in 2+ articles', n(b.gate1.journal), n(a.gate1.journal))}
        {row('… random sets of 126 (mean of 20, seed 5250)', b.gate1.random_same_size, a.gate1.random_same_size, `ranges ${b.gate1.random_range.join('–')} → ${a.gate1.random_range.join('–')}`)}
        {row('Lumped «org:?» faculty/department rows', `${n(nb.lumped.machine_rows)} rows, ${n(nb.lumped.affiliations)} affiliations`,
          `${n(nb.lumped.resolved_to_university)} placed, ${n(nb.lumped.kept_apart)} kept apart`, `the rest: not an institution ${nb.lumped.other?.not_institution || 0}, unsure ${nb.lumped.other?.unsure || 0}`)}
        {row('Bilingual twins joined (one body, two scripts)', '—', n(nb.bilingual_twins_joined))}
      </tbody>
    </table>);
}

function Decisions() {
  const [f, setF] = useState({ kind: '', confidence: '', level: '', basis: '', q: '' });
  const [qIn, setQIn] = useState('');
  const [off, setOff] = useState(0);
  const lim = 25;
  const qs = new URLSearchParams(Object.entries({ ...f, offset: String(off), limit: String(lim) }).filter(([, v]) => v !== '')).toString();
  const { data, err, loading, setData } = useApi<any>(`/librarian/decisions?${qs}`, []);
  useEffect(() => { const t = setTimeout(() => { setF(x => ({ ...x, q: qIn })); setOff(0); }, 350); return () => clearTimeout(t); }, [qIn]);
  const sel = (k: keyof typeof f, opts: [string, string][]) => (
    <select value={f[k]} onChange={e => { setF({ ...f, [k]: e.target.value }); setOff(0); }} aria-label={k}
      className="rounded-lg border-gray-300 text-sm py-1.5">{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>);
  return (
    <Card title="Every decision" right={data ? <span className="text-xs text-gray-500">{n(data.total)} match</span> : null}>
      <div className="flex flex-wrap items-center gap-2 mb-3" data-testid="filters">
        {sel('kind', [['', 'All kinds'], ...Object.entries(KIND_LABEL)])}
        {sel('confidence', [['', 'Any confidence'], ['high', 'high'], ['medium', 'medium'], ['low', 'low']])}
        {sel('level', [['', 'Both levels'], ['affiliation', 'per affiliation'], ['institution', 'per institution']])}
        {sel('basis', [['', 'Any basis'], ...Object.entries(BASIS_LABEL)])}
        <Btn kind="plain" small onClick={() => { setF({ ...f, kind: 'unsure' }); setOff(0); }}>Only unsure</Btn>
        <label className="relative flex-1 min-w-[12rem]"><Search className="w-4 h-4 absolute left-2 top-2 text-gray-400" aria-hidden />
          <input value={qIn} onChange={e => setQIn(e.target.value)} placeholder="Search printed text, names, reasons…" className="w-full pl-8 rounded-lg border-gray-300 text-sm py-1.5" /></label>
      </div>
      {err && <ErrorBox>{err}</ErrorBox>}
      {data && data.rows.length === 0 && <Empty>No decision matches.</Empty>}
      {data && data.rows.length > 0 && <div className="overflow-x-auto"><table className="w-full text-sm" data-testid="decisions">
        <thead className="text-xs text-gray-500 text-left"><tr><th className="py-1 pr-2 font-medium">Kind</th><th className="font-medium px-2">Decision</th>
          <th className="font-medium px-2">Printed / reason</th><th className="font-medium px-2">Conf.</th><th className="font-medium px-2">Basis</th><th className="font-medium pl-2">Owner</th></tr></thead>
        <tbody>{data.rows.map((d: any) => (
          <tr key={d.decision_id} className="border-t border-gray-100 align-top">
            <td className="py-2 pr-2 whitespace-nowrap"><Chip>{KIND_LABEL[d.kind] || d.kind}</Chip>{d.trivial && <div className="text-[11px] text-gray-400 mt-0.5">rule-able</div>}</td>
            <td className="py-2 px-2 min-w-[14rem]"><Says d={d.decision} kind={d.kind} /></td>
            <td className="py-2 px-2 text-xs text-gray-600 max-w-md">{d.printed && <div className="text-gray-800"><T text={d.printed} /></div>}<T text={d.reason} /></td>
            <td className="py-2 px-2"><Chip tone={CONF_TONE[d.confidence] || 'gray'}>{d.confidence || '—'}</Chip></td>
            <td className="py-2 px-2 text-xs text-gray-500 whitespace-nowrap">{BASIS_LABEL[d.basis] || d.basis}</td>
            <td className="py-2 pl-2 text-xs whitespace-nowrap">{d.verdict ? <Chip tone={d.verdict.verdict === 'yes' ? 'green' : d.verdict.verdict === 'no' ? 'red' : 'amber'}>{d.verdict.verdict}</Chip>
              : <span className="text-gray-300">—</span>}</td>
          </tr>))}</tbody></table></div>}
      {data && data.total > lim && <div className="flex items-center justify-end gap-2 mt-3 text-sm">
        <Btn kind="plain" small disabled={off === 0} onClick={() => setOff(Math.max(0, off - lim))}><ChevronLeft className="w-4 h-4" /> Previous</Btn>
        <span className="text-gray-500">{off + 1}–{Math.min(off + lim, data.total)} of {n(data.total)}</span>
        <Btn kind="plain" small disabled={off + lim >= data.total} onClick={() => setOff(off + lim)}>Next <ChevronRight className="w-4 h-4" /></Btn></div>}
      {loading && <p className="text-xs text-gray-400 mt-2">Loading…</p>}
    </Card>);
}

export default function Librarian() {
  const { data, err, setData } = useApi<any>('/librarian', []);
  const saved = (id: string) => (v: Verdict) => setData((d: any) => {
    const items = d.sample.items.map((x: Item) => x.decision_id === id ? { ...x, verdict: { ...v, n_verdicts: (x.verdict?.n_verdicts || 0) + 1 } } : x);
    const vc: Record<string, number> = {};
    items.forEach((x: Item) => { const k = x.verdict ? x.verdict.verdict : 'not_reviewed'; vc[k] = (vc[k] || 0) + 1; });
    return { ...d, sample: { ...d.sample, items, verdicts: vc } };
  });
  const c = data?.counts;
  const sc = data?.scale;
  const showMode = useShowMode();
  const hl = useApi<any>('/headlines');
  return (
    <Layout>
      <div className="space-y-5">
        <div className="flex flex-wrap items-start gap-3">
          <BookMarked className="w-7 h-7 text-indigo-600 mt-1" aria-hidden />
          <div className="flex-1 min-w-[16rem]">
            <h1 className="text-xl font-semibold text-gray-900">The librarian: institutions</h1>
            <p className="text-sm text-gray-600 max-w-3xl">An AI curator read every printed affiliation of the first 780 articles read, the way a librarian walks a card catalogue,
              and decided which institution each one names, which machine rows are one body or several, and each body's country and parent.
              {!showMode && <> The sample below shows each decision with the print it rests on. Your Yes / No / Unsure is kept, never overwritten.</>}</p>
          </div>
        </div>
        <AppliedBanner>Applied on 2 November: the decisions are in the index. The same university printed in Arabic and in English is now one record, and
          {hl.data?.institutions_with_country_pct != null ? ` ${hl.data.institutions_with_country_pct}%` : ' most'} of the institutions have their country.
          {hl.data?.librarian?.institutions && <> On the first 780 articles: {n(hl.data.librarian.institutions[0])} institutions before, {n(hl.data.librarian.institutions[1])} after.</>}</AppliedBanner>
        <ProductionLibrarian h={hl.data} />
        {err && <ErrorBox>{err}</ErrorBox>}
        {data && <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Tile label="Decisions" value={n(c.total)} sub={`${n(c.trivial)} rule-able, ${n(c.total - c.trivial)} needed judgement`} />
            <Tile label="High confidence" value={n(c.by_confidence.high || 0)} sub={`medium ${n(c.by_confidence.medium || 0)} · low ${n(c.by_confidence.low || 0)}`} />
            <Tile label="Unsure" value={n(c.by_kind.unsure || 0)} sub="left as the machine has it" />
            <Tile label="Institutions" value={hl.data?.librarian?.institutions ? `${n(hl.data.librarian.institutions[0])} → ${n(hl.data.librarian.institutions[1])}` : `${n(data.numbers?.before?.institutions_linked)} → ${n(data.numbers?.after?.institutions)}`} sub={hl.data?.librarian?.institutions ? 'organisation level, as applied' : 'organisation level'} />
            {!showMode && <Tile label="Sample checked" value={`${n(30 - (data.sample.verdicts.not_reviewed || 0))} / ${n(data.sample.items.length)}`}
              sub={`yes ${data.sample.verdicts.yes || 0} · no ${data.sample.verdicts.no || 0} · unsure ${data.sample.verdicts.unsure || 0}`} />}
          </div>
          {!showMode && <Card title="Before and after (the librarian's own count, before it was applied)"><Numbers nb={data.numbers} />
            <p className="text-xs text-gray-500 mt-2">The journal's own count drops by one and the random sets rise: the machine's false bridges
              (one «وزارة التربية» row for four countries, one CRMEF for every Moroccan city) are gone, and true ones it missed (Arabic and English
              names of one university, «جامعة فاس» = Sidi Mohamed Ben Abdellah) are made. As applied on 2 November the count is {hl.data?.librarian?.institutions ? n(hl.data.librarian.institutions[1]) : '—'}: the unsure statements keep the machine's rows, and a few bodies were added or moved to a former post.</p></Card>}
          {!showMode && <><div>
            <h2 className="text-base font-semibold text-gray-900 mb-1">Review sample: 30 decisions drawn at random</h2>
            <p className="text-sm text-gray-500 mb-3">Stratified (seed {data.sample.seed}): {(data.sample.strata || []).map((s: any) => `${s[0]} ${s[1]}`).join(' · ')}.
              The crop is cut from the scan where the statement's words were found; where none was found, the byline.</p>
            <div className="space-y-3">{data.sample.items.map((it: Item, i: number) => <SampleCard key={it.decision_id} it={it} i={i} onSaved={saved(it.decision_id)} />)}</div>
          </div>
          <Decisions />
          {data.rules && <Card title="Rules learned (calls made again and again, written for code)">
            <table className="w-full text-sm" data-testid="rules"><thead className="text-xs text-gray-500 text-left"><tr><th className="font-medium">Rule</th>
              <th className="font-medium text-right px-2">fires</th><th className="font-medium text-right px-2">reproduces</th><th className="font-medium text-right pl-2">differs</th></tr></thead>
              <tbody>{data.rules.map((r: any) => <tr key={r.rule} className="border-t border-gray-100 align-top"><td className="py-1.5 text-gray-700">{r.what}</td>
                <td className="text-right px-2 tabular-nums">{r.fires}</td><td className="text-right px-2 tabular-nums text-green-700">{r.agrees}</td>
                <td className="text-right pl-2 tabular-nums text-red-700">{r.disagrees}</td></tr>)}</tbody></table></Card>}
          {sc && <Card title="At scale (estimate)">
            <div className="text-sm text-gray-700 space-y-1.5">
              <p>Here: {n(sc.measured.packets)} affiliation packets ({sc.measured.affiliations_per_article} per article), {n(sc.measured.decisions)} decisions;
                {' '}{n(sc.measured.trivial.affiliation)} of {n(sc.measured.affiliation_decisions)} affiliation calls a rule reproduces. A packet is about {n(sc.measured.evidence_chars_per_packet.mean)} characters
                of evidence in and {n(sc.measured.decision_chars_per_affiliation)} out: ≈ {n(sc.per_packet_tokens.input)} tokens in, {n(sc.per_packet_tokens.output)} out
                (at {sc.assumptions.chars_per_token} characters a token, an assumption).</p>
              <p>Distinct institutions grow slower than articles (≈ {sc.measured.heaps_fit.a}·n^{sc.measured.heaps_fit.b} on the 780).
                Rules first, judgement only to the model: 162,816 education articles ≈ {n(sc.estimates.edu_162816_rules_first.input_tokens / 1e6)}M tokens in,
                {' '}{n(sc.estimates.edu_162816_rules_first.output_tokens / 1e6)}M out; 1M documents ≈ {n(sc.estimates.docs_1M_rules_first.input_tokens / 1e6)}M in,
                {' '}{n(sc.estimates.docs_1M_rules_first.output_tokens / 1e6)}M out. Batch list price (Opus 5.5): about ${n(sc.estimates.edu_162816_rules_first.usd_batch_list_price['claude-opus-5-5'])} and
                {' '}${n(sc.estimates.docs_1M_rules_first.usd_batch_list_price['claude-opus-5-5'])}.</p>
              <p className="text-xs text-gray-500">Full report: experiments/56_librarian_institutions/README.md.</p>
            </div></Card>}
          </>}
        </>}
      </div>
    </Layout>);
}
