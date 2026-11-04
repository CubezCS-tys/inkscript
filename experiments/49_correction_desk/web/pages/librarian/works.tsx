import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookMarked, Check, X, HelpCircle, Search, ChevronLeft, ChevronRight, AlertTriangle, ShieldCheck, ChevronDown } from 'lucide-react';
import Layout from '../../components/Layout';
import { Btn, Card, Chip, Empty, ErrorBox, Tile, T, actorName, n, when } from '../../components/Bits';
import { api } from '../../lib/api';
import { useApi } from '../../lib/me';
import { useShowMode } from '../../lib/showmode';
import { AppliedBanner, ProductionLibrarian } from '../../components/LibrarianBits';

// The cited-works librarian (experiment 62, 2026-11-02): the AI curator's pass over the cited-work cards of the 780
// articles. Its decisions are proposals (experiments/62_librarian_works/out/decisions62.jsonl); nothing is applied.
// Instead of an owner's sample, the check is automatic: a blind second judgement, every disagreement adjudicated,
// hard consistency checks, precision per kind and the APPLY rule. Only the few escalated cases take Yes / No / Unsure
// (append-only librarian_works_verdicts). API: desk/librarian_works.py.

type Verdict = { verdict_id: number; decision_id: string; verdict: 'yes' | 'no' | 'unsure'; comment: string | null;
  author: string; author_name: string; created_at: string; n_verdicts?: number };

const KIND: Record<string, string> = {
  same_work: 'Same work', edition_of: 'Edition of one work', part_of: 'Part of', different_work: 'Different works',
  unsure: 'Unsure', split_card: 'Card split', card_ok: 'Card is one work', not_a_work: 'Not a work',
  links_to_publication: 'Is a Mandumah publication', relation: 'Related Mandumah record', no_link: 'No link',
};
const LEVEL: Record<string, string> = { pair: 'two cards', card: 'one card', catalogue: 'card ↔ Mandumah' };
const BASIS: Record<string, string> = { rule: 'printed text (rule)', catalogue: 'catalogue record', world: 'knowledge of the work',
  context: 'the article’s own text', judgement: 'judgement' };
const CONF_TONE: Record<string, 'green' | 'amber' | 'red' | 'gray'> = { high: 'green', medium: 'amber', low: 'red' };
const pct = (x?: number | null, d = 1) => (x == null ? '—' : `${(100 * x).toFixed(d)}%`);
const DERIVED: Record<string, string> = {
  'pair:one work (same_work + edition_of)': 'Same work or edition, counted together',
  'card:not_a_work (the verdict only, not the action)': 'Not a work: the verdict alone',
  'card:not_a_work after the action fixes (round 2)': 'Not a work, after the action fixes',
  'catalogue:links passing K1c (venue fits)': 'Is a Mandumah publication: title, author, year and venue fit',
  'catalogue:links_to_publication passing K1c': 'Is a Mandumah publication: title, author, year and venue fit',
  'catalogue:links not passing K1c': 'Is a Mandumah publication: the rest',
  'catalogue:links_to_publication, the rest': 'Is a Mandumah publication: the rest',
  "catalogue:no_link read as 'not the cited work'": 'No link, read as “not the publication cited”',
  unsure: 'Unsure (any question)',
};
const kindLabel = (k: string) => {
  if (DERIVED[k]) return DERIVED[k];
  const [lvl, kd] = k.split(':'); return `${KIND[kd] || kd}${lvl && LEVEL[lvl] ? ` (${LEVEL[lvl]})` : ''}`;
};

function Says({ d }: { d: any }) {
  const dec = d.decision || {};
  const cs = (dec.cards || []).map((c: any) => c.title).filter(Boolean);
  const card = dec.card?.title;
  const line = (tag: string, t: React.ReactNode) => <div className="flex items-baseline gap-1.5"><span className="text-[11px] text-gray-400 w-10 shrink-0 text-right">{tag}</span><div className="min-w-0">{t}</div></div>;
  if (d.level === 'pair') return <div className="space-y-0.5">{line('A', <T text={cs[0]} />)}{line('B', <T text={cs[1]} />)}</div>;
  if (d.level === 'card') return <span><T text={card} />{dec.action ? <span className="text-xs text-gray-500"> · {String(dec.action).replace(/_/g, ' ')}</span> : null}
    {dec.groups ? <span className="text-xs text-gray-500"> · {dec.groups.length} groups</span> : null}</span>;
  return <div className="space-y-0.5">{line('cited', <T text={card} />)}{line('record', <span><T text={dec.target?.title || '—'} />
    {dec.target?.journal ? <span className="text-xs text-gray-500"> · <T text={dec.target.journal} />{dec.target.year ? ` ${dec.target.year}` : ''}</span> : null}</span>)}</div>;
}

function VerdictButtons({ id, verdict, onSaved }: { id: string; verdict: Verdict | null; onSaved: (v: Verdict) => void }) {
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const send = async (v: string) => {
    setBusy(true); setErr('');
    try { const r = await api<Verdict>('/librarian/works/verdicts', { json: { decision_id: id, verdict: v, comment } }); onSaved(r); setComment(''); }
    catch (e: any) { setErr(String(e.message || e)); } finally { setBusy(false); }
  };
  const cur = verdict?.verdict;
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
      {verdict && <p className="text-xs text-gray-500">Latest: <b>{verdict.verdict}</b> by {verdict.author_name || actorName(verdict.author)}, {when(verdict.created_at)}
        {verdict.comment ? <> — “{verdict.comment}”</> : null}{verdict.n_verdicts && verdict.n_verdicts > 1 ? <> ({verdict.n_verdicts} answers, all kept)</> : null}</p>}
      {err && <ErrorBox>{err}</ErrorBox>}
    </div>);
}

function BeforeAfter({ nb }: { nb: any }) {
  if (!nb) return null;
  const b = nb.before, a = nb.after, h = nb.held;
  const row = (label: string, x: React.ReactNode, y: React.ReactNode, note?: string) => (
    <tr className="border-t border-gray-100"><td className="py-1.5 pr-3 text-gray-700">{label}{note && <div className="text-[11px] text-gray-400">{note}</div>}</td>
      <td className="py-1.5 px-3 text-right tabular-nums text-gray-500 whitespace-nowrap">{x}</td><td className="py-1.5 pl-3 text-right tabular-nums font-semibold whitespace-nowrap">{y}</td></tr>);
  return (
    <div className="overflow-x-auto"><table className="w-full text-sm" data-testid="numbers">
      <thead><tr className="text-xs text-gray-500"><th className="text-left font-medium">On the {n(nb.articles)} articles ({n(nb.mentions)} citations, the Quran and hadith left out)</th>
        <th className="text-right font-medium px-3">machine today</th><th className="text-right font-medium pl-3">with the librarian</th></tr></thead>
      <tbody>
        {row('Cited works', n(b.cited_works), n(a.cited_works), `${n(nb.changes.pairs_joined)} pairs joined (${n(nb.changes.editions)} as editions), ${n(nb.changes.cards_split)} cards split, ${n(nb.changes.cards_dropped)} journal names dropped`)}
        {row('Works cited by 2 or more articles', n(b.cited_by_2plus), n(a.cited_by_2plus))}
        {row('Works cited by 3 or more articles', n(b.cited_by_3plus), n(a.cited_by_3plus))}
        {row('Gate 1 journal (0130): works cited by 2+ of its 126 articles', n(b.gate1.journal), n(a.gate1.journal))}
        {row('… random sets of 126 (mean of 20, seed 5250)', b.gate1.random_same_size, a.gate1.random_same_size, `ranges ${b.gate1.random_range.join('–')} → ${a.gate1.random_range.join('–')}; the journal ${b.gate1.ratio}× → ${a.gate1.ratio}× the random sets`)}
        {row('Citations to a work Mandumah holds', pct(h.before_link47.all.share, 2), pct(h.after.all.share, 2), `${n(h.before_link47.all.held)} → ${n(h.after.all.held)} citations`)}
        {row('… in the gate 1 journal', pct(h.before_link47.journal.share, 2), pct(h.after.journal.share, 2), `experiment 52's probe A: ${pct(h.before_probeA_exp52.journal.share, 2)}`)}
        {row('… in the 600 random articles', pct(h.before_link47.random600.share, 2), pct(h.after.random600.share, 2))}
      </tbody></table></div>);
}

function TopCited({ nb }: { nb: any }) {
  if (!nb) return null;
  const before: Record<string, number> = {};
  (nb.before.top || []).forEach((t: any) => { before[t.card] = t.articles; });
  const top = (nb.after.top || []).slice(0, 15);
  const max = Math.max(1, ...top.map((t: any) => t.articles));
  return (
    <div className="overflow-x-auto"><table className="w-full text-sm" data-testid="top-cited">
      <thead><tr className="text-xs text-gray-500"><th className="text-left font-medium py-1">Work</th><th className="text-right font-medium px-2">cards joined</th>
        <th className="text-left font-medium pl-3">articles citing it (grey: the machine’s biggest card)</th></tr></thead>
      <tbody>{top.map((t: any) => {
        const was = Math.max(0, ...t.cards.map((c: string) => before[c] || 0));
        return (
          <tr key={t.card} className="border-t border-gray-100">
            <td className="py-1.5 pr-2 text-gray-800 max-w-xs"><T text={t.title} /></td>
            <td className="py-1.5 px-2 text-right tabular-nums text-gray-500">{t.n_cards}</td>
            <td className="py-1.5 pl-3 min-w-[14rem]">
              <div className="flex items-center gap-2">
                <div className="relative h-3 flex-1 max-w-[16rem] bg-gray-100 rounded">
                  <div className="absolute inset-y-0 left-0 bg-indigo-300 rounded" style={{ width: `${(100 * t.articles) / max}%` }} />
                  {was > 0 && <div className="absolute inset-y-0 left-0 bg-gray-400/70 rounded" style={{ width: `${(100 * was) / max}%` }} />}
                </div>
                <span className="tabular-nums text-gray-700 whitespace-nowrap text-xs">{was && was !== t.articles ? `${was} → ` : ''}<b>{t.articles}</b></span>
              </div></td>
          </tr>);
      })}</tbody></table></div>);
}

function Precision({ pr }: { pr: any }) {
  if (!pr) return null;
  const apply: Record<string, any> = {};
  (pr.apply_rule || []).forEach((a: any) => { apply[a.kind] = a; });
  const shown = (pr.by_kind || []).filter((k: any) => k.n > 0);
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto"><table className="w-full text-sm" data-testid="precision">
        <thead><tr className="text-xs text-gray-500 text-left"><th className="font-medium py-1">Decision kind</th><th className="font-medium text-right px-2">checked</th>
          <th className="font-medium text-right px-2">right</th><th className="font-medium pl-3">precision (bar) and 95% range (line); the mark is 98%</th></tr></thead>
        <tbody>{shown.map((k: any) => (
          <tr key={k.kind} className="border-t border-gray-100">
            <td className={`py-1.5 pr-2 text-gray-700 ${DERIVED[k.kind] ? 'pl-4 text-gray-600' : ''}`}>{DERIVED[k.kind] ? '↳ ' : ''}{kindLabel(k.kind)}{k.note ? <div className="text-[11px] text-gray-400 max-w-md">{k.note}</div> : null}</td>
            <td className="py-1.5 px-2 text-right tabular-nums text-gray-500">{k.n}</td>
            <td className="py-1.5 px-2 text-right tabular-nums">{k.correct}</td>
            <td className="py-1.5 pl-3 min-w-[16rem]">
              <div className="flex items-center gap-2">
                <div className="relative h-3 flex-1 max-w-[18rem] bg-gray-100 rounded" title={`95% range ${pct(k.wilson95[0])}–${pct(k.wilson95[1])}`}>
                  <div className={`absolute inset-y-0 left-0 rounded ${k.precision >= pr.threshold ? 'bg-green-400' : 'bg-amber-300'}`} style={{ width: `${100 * k.precision}%` }} />
                  <div className="absolute top-1/2 h-0.5 bg-gray-700/60" style={{ left: `${100 * k.wilson95[0]}%`, width: `${100 * (k.wilson95[1] - k.wilson95[0])}%` }} />
                  <div className="absolute -top-0.5 -bottom-0.5 w-px bg-gray-800" style={{ left: `${100 * pr.threshold}%` }} />
                </div>
                <span className="tabular-nums text-xs text-gray-700 w-14 text-right">{pct(k.precision)}</span>
              </div></td>
          </tr>))}</tbody></table></div>
      <h3 className="text-sm font-semibold text-gray-800 pt-1">The apply rule: a kind is applied later only when it is right at least {pct(pr.threshold, 0)} of the time; unsure never</h3>
      <ul className="space-y-1.5" data-testid="apply-rule">
        {(pr.apply_rule || []).map((a: any) => (
          <li key={a.kind} className="flex items-start gap-2 text-sm">
            <span className="shrink-0 mt-0.5">{a.apply ? <Chip tone="green">apply</Chip> : <Chip tone="amber">hold</Chip>}</span>
            <span><span className="text-gray-800">{kindLabel(a.kind)}</span> <span className="text-gray-500 tabular-nums">· {a.measured}</span>
              <span className="block text-xs text-gray-500">{a.why}</span></span>
          </li>))}
      </ul>
      {pr.caveat && <p className="text-xs text-gray-500">{pr.caveat}.</p>}
    </div>);
}

function Disagreements({ blind }: { blind: any[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!blind?.length) return null;
  return (
    <div className="space-y-2" data-testid="disagreements">
      {blind.map((r: any, i: number) => (
        <div key={i} className="rounded-lg border border-gray-100">
          <button onClick={() => setOpen(open === i ? null : i)} className="w-full flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 text-left text-sm">
            <span className="font-medium text-gray-800">Round {r.round}</span>
            <span className="text-gray-600">{r.n} decisions drawn at random by kind, judged again blind</span>
            <span className="tabular-nums">agree <b>{r.agree}</b> ({pct(r.agree / r.n)})</span>
            <span className="text-gray-600">{r.disagreements} disagreements: the second judge was right in {r.right.blind}, the librarian in {r.right.librarian}, both defensible in {r.right.both}</span>
            <ChevronDown className={`w-4 h-4 ml-auto text-gray-400 transition-transform ${open === i ? 'rotate-180' : ''}`} aria-hidden />
          </button>
          {open === i && <div className="border-t border-gray-100 divide-y divide-gray-100">
            {r.cases.map((c: any) => (
              <div key={c.bid} className="px-3 py-2 text-sm space-y-0.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-gray-400">{c.bid}</span>
                  <span className="text-gray-700">librarian: <b>{(c.mine || '').replace(/_/g, ' ')}</b></span>
                  <span className="text-gray-700">second judge: <b>{(c.blind || '').replace(/_/g, ' ')}</b></span>
                  <Chip tone={c.right === 'blind' ? 'amber' : c.right === 'librarian' ? 'green' : 'gray'}>
                    {c.right === 'blind' ? 'second judge right: fixed' : c.right === 'librarian' ? 'librarian right' : 'both defensible'}</Chip>
                </div>
                <p className="text-gray-600" dir="ltr">{c.why}</p>
              </div>))}
          </div>}
        </div>))}
    </div>);
}

const CHECK_LABEL: Record<string, string> = {
  transitivity: 'Two cards joined through others although a decision keeps them apart',
  authors: 'One work whose cards print authors with nothing in common',
  'death dates': 'One work whose authors’ death years differ by more than 5',
  years: 'One work whose citations’ years are impossibly far apart',
  type: 'A thesis and a journal article in one work',
  catalogue: 'One work linked to two unlike Mandumah records, or one record from two works',
};

function Escalated({ cases, onSaved }: { cases: any[]; onSaved: (id: string, v: Verdict) => void }) {
  return (
    <div className="space-y-3" data-testid="escalated">
      {cases.map((c: any, i: number) => (
        <Card key={c.decision_id} id={`e-${c.decision_id}`}>
          <div className="space-y-2" data-testid="escalated-item">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-mono text-gray-400">{i + 1}</span>
              <h3 className="font-semibold text-gray-900">{c.title}</h3>
              <span className="ml-auto text-xs font-mono text-gray-400">{c.decision_id}</span>
            </div>
            <p className="text-sm text-gray-800">{c.question}</p>
            {(c.printed || []).length > 0 && <div className="rounded-lg bg-gray-50 border border-gray-100 px-3 py-2 space-y-1">
              {(c.printed || []).slice(0, 3).map((p: string, j: number) => <p key={j} className="text-sm text-gray-700"><T text={p} /></p>)}</div>}
            <div className="grid md:grid-cols-2 gap-2 text-sm">
              <div className="rounded-lg border border-green-100 bg-green-50/50 px-3 py-2"><span className="text-xs font-medium text-green-800">Yes means</span><p className="text-gray-700">{c.if_yes}</p></div>
              <div className="rounded-lg border border-red-100 bg-red-50/40 px-3 py-2"><span className="text-xs font-medium text-red-800">No means</span><p className="text-gray-700">{c.if_no}</p></div>
            </div>
            <p className="text-xs text-gray-500">Standing decision: <b>{KIND[c.kind] || c.kind}</b> ({c.confidence}). The librarian leans {c.lean} Why it is yours to decide: {c.why}.</p>
            <VerdictButtons id={c.decision_id} verdict={c.verdict} onSaved={v => onSaved(c.decision_id, v)} />
          </div>
        </Card>))}
    </div>);
}

function Decisions() {
  const [f, setF] = useState({ level: '', kind: '', confidence: '', basis: '', q: '' });
  const [qIn, setQIn] = useState('');
  const [off, setOff] = useState(0);
  const lim = 25;
  const qs = new URLSearchParams(Object.entries({ ...f, offset: String(off), limit: String(lim) }).filter(([, v]) => v !== '')).toString();
  const { data, err, loading } = useApi<any>(`/librarian/works/decisions?${qs}`, []);
  useEffect(() => { const t = setTimeout(() => { setF(x => ({ ...x, q: qIn })); setOff(0); }, 350); return () => clearTimeout(t); }, [qIn]);
  const sel = (k: keyof typeof f, opts: [string, string][]) => (
    <select value={f[k]} onChange={e => { setF({ ...f, [k]: e.target.value }); setOff(0); }} aria-label={k}
      className="rounded-lg border-gray-300 text-sm py-1.5">{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>);
  return (
    <Card title="Every decision" right={data ? <span className="text-xs text-gray-500">{n(data.total)} match</span> : null}>
      <div className="flex flex-wrap items-center gap-2 mb-3" data-testid="filters">
        {sel('level', [['', 'All questions'], ['pair', 'two cards: one work?'], ['card', 'one card: one work?'], ['catalogue', 'card ↔ Mandumah']])}
        {sel('kind', [['', 'All answers'], ...Object.entries(KIND)])}
        {sel('confidence', [['', 'Any confidence'], ['high', 'high'], ['medium', 'medium'], ['low', 'low']])}
        {sel('basis', [['', 'Any basis'], ...Object.entries(BASIS)])}
        <Btn kind="plain" small onClick={() => { setF({ ...f, kind: 'unsure' }); setOff(0); }}>Only unsure</Btn>
        <label className="relative flex-1 min-w-[12rem]"><Search className="w-4 h-4 absolute left-2 top-2 text-gray-400" aria-hidden />
          <input value={qIn} onChange={e => setQIn(e.target.value)} placeholder="Search titles, authors, reasons…" dir="auto" className="w-full pl-8 rounded-lg border-gray-300 text-sm py-1.5" /></label>
      </div>
      {err && <ErrorBox>{err}</ErrorBox>}
      {data && data.rows.length === 0 && <Empty>No decision matches.</Empty>}
      {data && data.rows.length > 0 && <div className="overflow-x-auto"><table className="w-full text-sm" data-testid="decisions">
        <thead className="text-xs text-gray-500 text-left"><tr><th className="py-1 pr-2 font-medium">Answer</th><th className="font-medium px-2">About</th>
          <th className="font-medium px-2">Why</th><th className="font-medium px-2">Conf.</th><th className="font-medium pl-2">Basis</th></tr></thead>
        <tbody>{data.rows.map((d: any) => (
          <tr key={d.decision_id} className="border-t border-gray-100 align-top">
            <td className="py-2 pr-2 whitespace-nowrap"><Chip>{KIND[d.kind] || d.kind}</Chip>
              <div className="text-[11px] text-gray-400 mt-0.5">{LEVEL[d.level]}{d.trivial ? ' · rule stood' : ''}{d.supersedes ? ' · revised' : ''}</div></td>
            <td className="py-2 px-2 min-w-[16rem] max-w-md"><Says d={d} /></td>
            <td className="py-2 px-2 text-xs text-gray-600 max-w-md" dir="ltr">{d.reason}</td>
            <td className="py-2 px-2"><Chip tone={CONF_TONE[d.confidence] || 'gray'}>{d.confidence || '—'}</Chip></td>
            <td className="py-2 pl-2 text-xs text-gray-500 whitespace-nowrap">{BASIS[d.basis] || d.basis}</td>
          </tr>))}</tbody></table></div>}
      {data && data.total > lim && <div className="flex items-center justify-end gap-2 mt-3 text-sm">
        <Btn kind="plain" small disabled={off === 0} onClick={() => setOff(Math.max(0, off - lim))}><ChevronLeft className="w-4 h-4" /> Previous</Btn>
        <span className="text-gray-500">{off + 1}–{Math.min(off + lim, data.total)} of {n(data.total)}</span>
        <Btn kind="plain" small disabled={off + lim >= data.total} onClick={() => setOff(off + lim)}>Next <ChevronRight className="w-4 h-4" /></Btn></div>}
      {loading && <p className="text-xs text-gray-400 mt-2">Loading…</p>}
    </Card>);
}

export default function LibrarianWorks() {
  const { data, err, setData } = useApi<any>('/librarian/works', []);
  const saved = (id: string, v: Verdict) => setData((d: any) => ({ ...d, escalated: d.escalated.map((c: any) =>
    c.decision_id === id ? { ...c, verdict: { ...v, n_verdicts: (c.verdict?.n_verdicts || 0) + 1 } } : c) }));
  const c = data?.counts, nb = data?.numbers, pr = data?.precision, sc = data?.scale, rc = data?.recall, bl = data?.blocking;
  const r1 = pr?.rounds?.round1, r2 = pr?.rounds?.round2;
  const est = sc?.estimates;
  const showMode = useShowMode();
  const hl = useApi<any>('/headlines');
  return (
    <Layout>
      <div className="space-y-5">
        <div className="flex flex-wrap items-start gap-3">
          <BookMarked className="w-7 h-7 text-indigo-600 mt-1" aria-hidden />
          <div className="flex-1 min-w-[16rem]">
            <h1 className="text-xl font-semibold text-gray-900">The librarian: cited works</h1>
            <p className="text-sm text-gray-600 max-w-3xl">An AI curator walked the card catalogue of everything the first 780 articles read cite: which cards are one work
              (a misprint, a short form, another edition), which cards hold several works, which are not works at all (a journal’s name, an issue),
              and which are publications Mandumah holds. Each answer was then checked without you: judged again blind, every disagreement read
              against the print, and the whole set tested for contradictions.{!showMode && <> What is left for you is below: {data ? data.escalated.length : 'a few'} questions.</>}</p>
            <p className="text-xs text-gray-500 mt-1"><Link href="/librarian" className="text-indigo-700 hover:underline">The institutions librarian →</Link></p>
          </div>
        </div>
        <AppliedBanner>Applied on 2 November: the kinds of decision measured right at least 98% of the time are in the index (the same work, another edition, a split card,
          not a work, and the links to Mandumah publications that pass the venue check). The rest stay proposals: other links, different works, and every unsure answer.
          {hl.data?.librarian?.cited_works && <> On the first 780 articles: {n(hl.data.librarian.cited_works[0])} cited-work cards before, {n(hl.data.librarian.cited_works[1])} works after.</>}
          {!showMode && data?.note && <span className="block text-xs text-green-800/80 mt-1">{data.note}</span>}</AppliedBanner>
        <ProductionLibrarian h={hl.data} />
        {err && <ErrorBox>{err}</ErrorBox>}
        {data && <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Tile label="Decisions" value={n(c.total)} sub={`${n(c.trivial)} by rule · ${n(c.total - c.trivial)} judged`} />
            <Tile label="Cited works" value={hl.data?.librarian?.cited_works ? n(hl.data.librarian.cited_works[1]) : nb ? n(nb.after.cited_works) : '—'} sub={hl.data?.librarian?.cited_works ? `from ${n(hl.data.librarian.cited_works[0])} cards, as applied` : nb ? `from ${n(nb.before.cited_works)} cards` : ''} />
            <Tile label="Cited by 2+ articles" value={nb ? n(nb.after.cited_by_2plus) : '—'} sub={nb ? (showMode ? `was ${n(nb.before.cited_by_2plus)}` : `was ${n(nb.before.cited_by_2plus)} · gate 1: ${nb.before.gate1.journal} → ${nb.after.gate1.journal}`) : ''} />
            <Tile label="Blind check agreed" value={r1 ? `${pct((r1.agree + (r2?.agree || 0)) / (r1.n + (r2?.n || 0)), 0)}` : '—'} sub={r1 ? `${r1.agree}/${r1.n} then ${r2?.agree || 0}/${r2?.n || 0}` : ''} />
            {!showMode && <Tile label="For you" value={n(data.escalated.length)} sub={`answered ${data.escalated.filter((x: any) => x.verdict).length}`} href="#for-you" />}
          </div>
          {!showMode && <Card title="Before and after (the librarian's own replay, before it was applied)"><BeforeAfter nb={nb} />
            <p className="text-xs text-gray-500 mt-2">The journal’s works shared by 2+ articles rise from {nb?.before.gate1.journal} to {nb?.after.gate1.journal}, and the random sets rise
              too ({nb?.before.gate1.random_same_size} → {nb?.after.gate1.random_same_size}): short forms such as <T text="«اللسان»" /> and misprinted titles now meet their full citation.
              The gap between a field’s own journal and random articles stays about seven to one.
              As applied and rebuilt (2 November) the counts are {hl.data?.librarian?.cited_works ? n(hl.data.librarian.cited_works[1]) : '—'} works and, for gate 1, {hl.data?.gate1?.shared_works ? `${hl.data.gate1.shared_works[0]} vs ${hl.data.gate1.shared_works[1]}` : '—'} on the current release.</p></Card>}
          <Card title="Most cited works after the librarian"><TopCited nb={nb} /></Card>
          <Card title={<span className="flex items-center gap-2"><ShieldCheck className="w-5 h-5 text-indigo-600" aria-hidden />How the answers were checked</span>}>
            <div className="space-y-4">
              <p className="text-sm text-gray-600 max-w-3xl">A random sample of each kind of answer was judged again by a second judge that saw only the evidence, not the first answer
                (round 1: {r1?.n} answers of every kind; round 2, after the fixes: {r2?.n} more of the kinds that decide what can be applied).
                Every disagreement was read against the printed citation, the article’s text and the catalogue record. The precision below counts
                an answer right when both judges agreed or the reading found the librarian right.</p>
              <Precision pr={pr} />
              <div><h3 className="text-sm font-semibold text-gray-800 mb-2">Every disagreement, and who was right</h3><Disagreements blind={data.blind} /></div>
              <div><h3 className="text-sm font-semibold text-gray-800 mb-1">Contradiction checks over all {n(c.total)} answers</h3>
                <ul className="text-sm space-y-1" data-testid="checks">
                  {Object.entries(data.checks?.by_check || {}).map(([k, v]: any) => (
                    <li key={k} className="flex items-baseline gap-2"><span className="tabular-nums w-8 text-right font-semibold">{v}</span><span className="text-gray-700">{CHECK_LABEL[k] || k}</span></li>))}
                </ul>
                <p className="text-xs text-gray-500 mt-1">The {data.checks?.by_check?.authors || 0} author cases are one person written two ways («ابن حنى» = ابن جني, «العسقلاني» = ابن حجر, yaagoubi = yaacobbi).
                  Earlier runs of these checks caught three real errors, all fixed: Sahih Muslim joined to al-Nawawi’s commentary through a third card,
                  an English title of an Arabic article linked to another record, and two review records linked as the book.</p></div>
              {(rc || bl) && <div><h3 className="text-sm font-semibold text-gray-800 mb-1">What the candidate search can miss</h3>
                <p className="text-sm text-gray-600 max-w-3xl">The librarian only reads pairs of cards that a search puts in front of it ({n(bl?.pairs_examined || 143810)} pairs looked at,
                  {' '}{n(bl?.candidate_pairs || 1015)} close enough to ask about). For {rc?.sample} random cards, the six nearest cards the search did not pair were read by hand
                  ({n(rc?.candidates_read)} in all): {rc?.missed_duplicates} duplicate was missed (a translated title, «Children’s Literature as Science and Art» = «أدب الأطفال علم وفن»),
                  against {rc?.found_by_blocking_for_sample} found for the same cards, about {pct(rc?.recall_estimate, 0)} found. Of the Desk’s own 290 “possibly the same work” pairs, 238 were in front of the librarian.</p></div>}
            </div>
          </Card>
          {!showMode && <>{data.rules && <Card title="Rules learned (what the librarian did again and again, written for code)">
            <div className="overflow-x-auto"><table className="w-full text-sm" data-testid="rules"><thead className="text-xs text-gray-500 text-left"><tr><th className="font-medium py-1">Rule</th>
              <th className="font-medium text-right px-2">fires</th><th className="font-medium text-right px-2">same answer as the librarian</th><th className="font-medium text-right pl-2">keep</th></tr></thead>
              <tbody>{data.rules.filter((r: any) => r.fires > 0).map((r: any) => <tr key={r.rule} className="border-t border-gray-100 align-top">
                <td className="py-1.5 pr-2 text-gray-700">{r.rule.replace(/^\w+ /, '')}<div className="text-[11px] text-gray-400">{r.test}</div></td>
                <td className="text-right px-2 tabular-nums">{n(r.fires)}</td>
                <td className="text-right px-2 tabular-nums whitespace-nowrap">{n(r.agrees)} ({pct(r.precision)})</td>
                <td className="text-right pl-2">{r.keep ? <Chip tone="green">yes</Chip> : <span className="text-xs text-gray-400">no</span>}</td></tr>)}</tbody></table></div>
            <p className="text-xs text-gray-500 mt-2">Kept: a rule that gives the librarian’s answer at least 98% of the time it fires. The others show where judgement is needed:
              same title and same author is not enough (a thesis and its article, «تقريب التهذيب» and «تهذيب التهذيب», two printings of one dictionary).</p></Card>}
          {sc && est && <Card title="At scale (estimate)">
            <div className="text-sm text-gray-700 space-y-1.5" data-testid="scale">
              <p>Here: {n(c.total)} questions on {n(sc.measured.cards)} cards; the rule stood in {pct(c.trivial / c.total, 0)}.
                A judged question reads about {n(sc.per_judged_question_tokens.pair.input)} tokens (two cards) or {n(sc.per_judged_question_tokens.catalogue.input)} (a card and a record) and writes about {n(sc.per_judged_question_tokens.pair.output)}
                {' '}(at {sc.assumptions.chars_per_token} characters a token, an assumption).</p>
              <p>Cards and distinct works grow with articles (≈ n^{sc.measured.fits.distinct_works[1]}: most works are cited once); candidate pairs grow faster (≈ n^{sc.measured.fits.candidate_pairs[1]}) until the search’s limits cap them.</p>
              <div className="overflow-x-auto"><table className="w-full text-sm mt-1"><thead className="text-xs text-gray-500"><tr><th className="text-left font-medium py-1">Batch list price, rules first, judgement to the model</th>
                <th className="text-right font-medium px-2">Opus 5.5</th><th className="text-right font-medium px-2">Sonnet 5.5</th><th className="text-right font-medium pl-2">Haiku 4.5</th></tr></thead>
                <tbody>{[['gate2_3460', 'Gate 2 (3,460 articles)'], ['edu_162816', 'Education (162,816)'], ['docs_1M', '1M documents']].map(([k, l]) => {
                  const lo = est[k].lower_bound_pairs_per_card.usd_batch_list_price, hi = est[k].rules_first_authority.usd_batch_list_price;
                  const cell = (m: string) => <td className="text-right px-2 tabular-nums whitespace-nowrap">${n(lo[m])}–{n(hi[m])}</td>;
                  return <tr key={k} className="border-t border-gray-100"><td className="py-1.5 text-gray-700">{l}</td>{cell('claude-opus-5-5')}{cell('claude-sonnet-5-5')}{cell('claude-haiku-4-5')}</tr>;
                })}</tbody></table></div>
              <p className="text-xs text-gray-500">Low: pair questions grow like cards; high: as fitted on the 780. Full report: experiments/62_librarian_works/README.md.</p>
            </div></Card>}
          <div id="for-you" className="scroll-mt-16">
            <h2 className="text-base font-semibold text-gray-900 mb-1">For you: {data.escalated.length} questions the checks cannot settle</h2>
            <p className="text-sm text-gray-500 mb-3">Each is a policy that moves many counts or a case where both readings hold. Yes keeps the librarian’s answer; every answer is kept, never overwritten.</p>
            <Escalated cases={data.escalated} onSaved={saved} />
          </div>
          <Decisions />
          </>}
        </>}
      </div>
    </Layout>);
}
