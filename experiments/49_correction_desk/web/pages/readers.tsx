import React, { useEffect, useMemo, useState } from 'react';
import { BarChart3, Coins, Images, Info, Lightbulb, ScanText } from 'lucide-react';
import Layout from '../components/Layout';
import { Card, Chip, ErrorBox, Tabs } from '../components/Bits';
import { LineCrop, Look, Reading, pc } from '../components/readers/bits';
import { api } from '../lib/api';

// Our own readers (/readers, 2026-11-05): the overnight results of the from-scratch Arabic line readers, experiments
// 77 (real lines, Gemini as judge), 78 (synthetic lines) and 79 (the signal reader). Every number and every line comes
// from the experiments' out/ files through /desk/api/readers (desk/readers.py); nothing here is typed in by hand
// except the plain sentences around them.

const TEAL = '#0d9488', INDIGO = '#6366f1';
const V1_SESSION = 59168770;   // experiment 77's rental that trained v1 (16 epochs, 42 min)

export default function ReadersPage() {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState('');
  useEffect(() => { api('/readers').then(setD).catch(e => setErr(String(e.message || e))); }, []);
  return (
    <Layout wide>
      <div className="max-w-[84rem] mx-auto">
        <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2"><ScanText className="w-5 h-5 text-teal-700" aria-hidden />Our own readers</h1>
        {d && <Headline d={d} />}
        {err && <div className="mt-4"><ErrorBox>{err}</ErrorBox></div>}
        {!d && !err && <p className="text-sm text-gray-500 mt-4">Loading…</p>}
        {d && (
          <div className="mt-5 space-y-6">
            <Scoreboard sb={d.scoreboard} />
            <Gallery lines={d.gallery} />
            <Learned l={d.learned} sb={d.scoreboard} />
            <Spend s={d.spend} />
          </div>)}
      </div>
    </Layout>
  );
}

const row = (sb: any, id: string) => sb.rows.find((r: any) => r.id === id);

function Headline({ d }: { d: any }) {
  const sb = d.scoreboard;
  const ours = row(sb, 'real_only'), az = row(sb, 'azure');
  const y = (r: any) => r?.sets?.yardstick, l = (r: any) => r?.sets?.lab_docs12;
  const v1 = d.spend.gpu.find((e: any) => e.exp === '77')?.instances?.find((i: any) => i.instance === V1_SESSION);
  return (
    <>
      <p className="text-[17px] text-gray-800 mt-2 max-w-4xl leading-relaxed" data-testid="readers-headline">
        Our <b>8-million-parameter reader</b>, trained from scratch on our own pages for <b>about {v1 ? `$${v1.usd.toFixed(2)}` : 'a dollar'}</b> of rented GPU, reads pages it never saw <b>almost as well as Azure</b>.
      </p>
      <p className="text-sm text-gray-500 mt-1 max-w-4xl">Overnight, 4–5 November 2026 (experiments 77, 78 and 79). Every reader is given the same lines, cut where Azure found them, so this compares <i>reading</i>, not finding lines on the page. Held out: none of these journals was in training.</p>
      <div className="grid grid-cols-4 gap-3 mt-4" data-testid="readers-tiles">
        <Stat label="Letters wrong, your 20 corrected pages" ours={y(ours)?.letters} azure={y(az)?.letters} />
        <Stat label="Words wrong, your 20 corrected pages" ours={y(ours)?.words} azure={y(az)?.words} />
        <Stat label="Letters wrong, lab documents 1–2" ours={l(ours)?.letters} azure={l(az)?.letters} />
        <Stat label="Whole lines exactly right (your 20 pages)" ours={sb.line_exact?.v1} azure={sb.line_exact?.azure} d={1} higher />
      </div>
    </>
  );
}

const Stat: React.FC<{ label: string; ours?: number; azure?: number; d?: number; higher?: boolean }> = ({ label, ours, azure, d = 2, higher }) => {
  const better = ours != null && azure != null && (higher ? ours > azure : ours < azure);
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="flex items-baseline gap-4 mt-1.5">
        <div><div className="text-2xl font-semibold tabular-nums" style={{ color: TEAL }}>{pc(ours, d)}</div><div className="text-[11px] text-gray-500">ours</div></div>
        <div><div className="text-2xl font-semibold tabular-nums text-gray-700">{pc(azure, d)}</div><div className="text-[11px] text-gray-500">Azure</div></div>
        {better && <Chip tone="green">ours ahead</Chip>}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- scoreboard

function Scoreboard({ sb }: { sb: any }) {
  const [set, setSet] = useState('yardstick');
  const s = sb.sets.find((x: any) => x.id === set);
  const rows = (sb.rows as any[]).filter(r => r.sets[set]).sort((a, b) => a.sets[set].words - b.sets[set].words);
  return (
    <Card title={<span className="flex items-center gap-2"><BarChart3 className="w-4 h-4 text-teal-700" aria-hidden />Scoreboard</span>}
      right={<Tabs value={set} onChange={setSet} tabs={sb.sets.map((x: any) => [x.id, x.label])} />}>
      <p className="text-sm text-gray-600 -mt-1 mb-3">{s.label}: {s.note}. Lower is better. Punctuation is left out of these two numbers; vowel marks, hamza forms and <bdi className="ar-inline">ى</bdi> against <bdi className="ar-inline">ي</bdi> still count.</p>
      <div className="flex items-center gap-4 text-xs text-gray-600 mb-2" aria-hidden>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: TEAL }} />ours: the same 8.3 M-parameter model, trained different ways</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: INDIGO }} />other readers</span>
      </div>
      <div className="grid grid-cols-2 gap-8" data-testid="readers-bars">
        <Bars rows={rows} set={set} field="letters" title="Letters wrong" />
        <Bars rows={rows} set={set} field="words" title="Words wrong" hideLabels />
      </div>
      <details className="mt-4">
        <summary className="text-sm text-indigo-700 cursor-pointer select-none">All three tests in one table</summary>
        <table className="w-full text-sm mt-2" data-testid="readers-table">
          <thead>
            <tr className="text-xs text-gray-500 border-b border-gray-100">
              <th className="text-left font-medium py-1.5">Reader</th>
              {sb.sets.map((x: any) => <th key={x.id} colSpan={2} className="font-medium text-center">{x.label}</th>)}
            </tr>
            <tr className="text-[11px] text-gray-400"><th />{sb.sets.map((x: any) => <React.Fragment key={x.id}><th className="font-normal text-right pr-2">letters</th><th className="font-normal text-right pr-4">words</th></React.Fragment>)}</tr>
          </thead>
          <tbody>
            {(sb.rows as any[]).map(r => (
              <tr key={r.id} className="border-t border-gray-100">
                <td className="py-1.5 flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: r.family === 'ours' ? TEAL : INDIGO }} />{r.label}</td>
                {sb.sets.map((x: any) => { const v = r.sets[x.id]; return (
                  <React.Fragment key={x.id}>
                    <td className="text-right tabular-nums pr-2">{v ? pc(v.letters) : <span className="text-gray-300">—</span>}</td>
                    <td className="text-right tabular-nums pr-4">{v ? pc(v.words) : <span className="text-gray-300">—</span>}</td>
                  </React.Fragment>); })}
              </tr>))}
          </tbody>
        </table>
        <p className="text-xs text-gray-500 mt-2">Nuqta (a page reader, run in the OCR lab) exists for the lab documents only; on document 3 it is far off because its text follows its own reading order. Argon is the reference for document 3, so it has no score there. A dash: not run on that test.</p>
      </details>
    </Card>
  );
}

function Bars({ rows, set, field, title, hideLabels }: { rows: any[]; set: string; field: 'letters' | 'words'; title: string; hideLabels?: boolean }) {
  const vals = rows.map(r => r.sets[set][field] as number);
  const sane = vals.filter(v => v <= 12);
  const max = Math.max(...(sane.length ? sane : vals), 0.01);
  return (
    <div>
      <div className="text-sm font-medium text-gray-700 mb-2">{title}</div>
      <div className="space-y-1.5">
        {rows.map(r => {
          const v = r.sets[set][field] as number;
          const off = v > max * 1.001;
          const w = Math.max(0.5, (Math.min(v, max) / max) * 100);
          return (
            <div key={r.id} className={`grid ${hideLabels ? 'grid-cols-[1fr]' : 'grid-cols-[14rem_1fr]'} items-center gap-3`} title={`${r.label}: ${v.toFixed(2)}% ${field} wrong`}>
              {!hideLabels && <div className={`text-xs truncate ${r.family === 'ours' ? 'text-gray-800' : 'text-gray-600'}`}>{r.label}</div>}
              <div className="flex items-center gap-2 h-5">
                <div className="flex-1 h-3.5"><div className="h-3.5 rounded-r" style={{ width: `${w}%`, minWidth: 3, background: r.family === 'ours' ? TEAL : INDIGO }} /></div>
                <span className="w-24 text-xs tabular-nums text-gray-700 whitespace-nowrap">{v.toFixed(2)}%{off ? ' ≫ scale' : ''}</span>
              </div>
            </div>);
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- gallery

const GROUPS: [string, string, string][] = [
  ['all', 'All', ''],
  ['ours_beat_azure', 'We are right, Azure is not', 'Our reader matches your correction; Azure does not.'],
  ['azure_beat_ours', 'Azure is right, we are not', 'Azure matches your correction; ours does not.'],
  ['old_print', 'Old print', 'Pages from before 1970.'],
  ['loops', 'Loop letters \u2066و / ر\u2069', 'Lines where a reader takes و for ر (or back): mostly the signal reader, which sees no shape, only the pen’s path.'],
];

function Gallery({ lines }: { lines: any[] }) {
  const [g, setG] = useState('all');
  const shown = useMemo(() => lines.filter(x => g === 'all' || x.group === g), [lines, g]);
  const count = (k: string) => (k === 'all' ? lines.length : lines.filter(x => x.group === k).length);
  return (
    <Card title={<span className="flex items-center gap-2"><Images className="w-4 h-4 text-teal-700" aria-hidden />Real lines our readers never saw</span>}>
      <p className="text-sm text-gray-600 -mt-1">From your 20 corrected pages. Under each printed line: your correction, then what each reader wrote. Words a reader got wrong are <span className="bg-rose-100 text-rose-900 rounded px-1">marked</span>, words it left out are <span className="text-rose-400 line-through">struck</span>. Punctuation and spacing are not marked.</p>
      <div className="flex flex-wrap gap-2 mt-3" role="tablist" aria-label="Which lines" data-testid="gallery-filter">
        {GROUPS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={g === k} onClick={() => setG(k)}
            className={`rounded-full border px-3 py-1 text-sm ${g === k ? 'border-teal-600 bg-teal-50 text-teal-900' : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'}`}>
            {label} <span className="text-xs text-gray-500">{count(k)}</span></button>))}
      </div>
      {g !== 'all' && <p className="text-xs text-gray-500 mt-2">{GROUPS.find(x => x[0] === g)?.[2]}</p>}
      <div className="mt-3 divide-y divide-gray-100" data-testid="gallery">
        {shown.map(x => <LineCard key={x.key} x={x} />)}
      </div>
    </Card>
  );
}

const GROUP_CHIP: Record<string, [string, 'green' | 'indigo' | 'gray']> = {
  ours_beat_azure: ['we are right, Azure is not', 'green'], azure_beat_ours: ['Azure is right, we are not', 'indigo'],
  old_print: ['old print', 'gray'], loops: ['loop letters \u2066و / ر\u2069', 'gray'],
};

function LineCard({ x }: { x: any }) {
  const [label, tone] = GROUP_CHIP[x.group] || [x.group, 'gray'];
  const [doc, pg] = x.page_id.split('_p');
  return (
    <div className="py-4" data-testid="gallery-line">
      <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
        <Chip tone={tone}>{label}</Chip>
        <span>{x.decade === 'pre-1960' ? 'before 1960' : x.decade}</span>
        <span className="text-gray-400">· document {doc}, page {Number(pg)}, line {x.i}</span>
        {x.group === 'loops' && <span className="text-gray-600">· <bdi className="ar-inline">و</bdi> and <bdi className="ar-inline">ر</bdi> swapped here: signal reader {x.loops.signal}×, ours {x.loops.ours}×, Azure {x.loops.azure}×</span>}
      </div>
      <LineCrop k={x.key} width={x.width} />
      <div className="mt-2">
        <Reading label={<b className="text-gray-800">Your correction</b>} truth={x.truth} text={x.truth} plain />
        <Reading label={<span style={{ color: TEAL }} className="font-medium">Ours (real lines, v1)</span>} truth={x.truth} text={x.ours} />
        <Reading label={<span style={{ color: INDIGO }} className="font-medium">Azure</span>} truth={x.truth} text={x.azure} />
        <Reading label={<span className="text-gray-600 font-medium">Signal reader <span className="font-normal text-gray-400">(movement only)</span></span>} truth={x.truth} text={x.signal} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- what we learned

function Learned({ l, sb }: { l: any; sb: any }) {
  const y = (id: string) => row(sb, id)?.sets?.yardstick;
  const lab = (id: string) => row(sb, id)?.sets?.lab_docs12;
  const f = l.fuse || {};
  const w = f.warning?.scores || {};
  const eras = Object.entries(f.era || {}) as [string, any][];
  const waw = l.waw || {};
  const wawPct = (m: string) => (waw[m] ? `${(100 * waw[m].err).toFixed(1)}%` : '—');
  const wawR = (m: string) => (waw[m]?.top || []).find((t: any) => t[0] === 'ر')?.[1];
  return (
    <section>
      <h2 className="font-semibold text-gray-800 flex items-center gap-2 mb-3"><Lightbulb className="w-4 h-4 text-teal-700" aria-hidden />What we learned</h2>
      <div className="grid grid-cols-2 gap-4 items-start" data-testid="learned">
        <Lesson n={1} title="Stretched joins were read as an extra س. Drawing them in our synthetic lines fixed it."
          body={<>A reader taught only on lines we render ourselves had never seen a kashida (a join stretched by the printer), so it read one as a <span className="ar-inline">س</span>: its most frequent error, 195 times on your 20 pages. Version 2 draws kashida in 30% of its lines. Letters wrong fell from {pc(y('syn_only')?.letters)} to {pc(y('syn2_only')?.letters)}, words from {pc(y('syn_only')?.words)} to {pc(y('syn2_only')?.words)} (experiment 78).</>}>
          <Look name="kashida" maxH={230} alt="the synthetic-only reader's most frequent error: an extra س on stretched joins" caption="Top of the error sheet: the printed line, your correction, and the synthetic-only reading." />
          {l.kashida && <div className="mt-3">
            <LineCrop k={l.kashida.key} width={l.kashida.width} h={52} />
            <Reading compact label="Your correction" truth={l.kashida.truth} text={l.kashida.truth} plain />
            <Reading compact label="Synthetic only, v1" truth={l.kashida.truth} text={l.kashida.syn1} />
            <Reading compact label="Synthetic only, v2 (kashida drawn)" truth={l.kashida.truth} text={l.kashida.syn2} />
          </div>}
        </Lesson>

        <Lesson n={2} title="Synthetic lines matter when real labels are scarce."
          body={<>With all 520,000 real lines, starting from synthetic lines changes nothing that can be measured ({pc(y('syn_then_real')?.words)} against {pc(y('real_only')?.words)} words wrong). With only 10% of the real lines, it cuts word errors from <b>{pc(y('real10')?.words)}</b> to <b>{pc(y('syn_then_real10')?.words)}</b>, a 40% cut. So synthetic lines are for the rare cases: old print, rare journals, new layouts.</>}>
          <MiniBars items={[
            ['10% of the real lines', y('real10')?.words, INDIGO],
            ['synthetic, then 10% real', y('syn_then_real10')?.words, TEAL],
            ['all real lines', y('real_only')?.words, '#94a3b8'],
          ]} unit="words wrong, your 20 pages" />
          <div className="mt-3"><Look name="synthetic" maxH={170} alt="lines we rendered ourselves" caption="Lines we rendered ourselves: free fonts, typefaces traced from our old scans, real paper and scan damage." /></div>
        </Lesson>

        <Lesson n={3} title="Gemini as the judge of our labels did not help."
          body={<>Where our first reader and Azure disagreed, Gemini looked at 5,226 lines and picked a reading; the second reader (v2) learned from those labels. On your pages it is no better: letters wrong {pc(y('v2')?.letters)} against v1&apos;s {pc(y('real_only')?.letters)}, words {pc(y('v2')?.words)} against {pc(y('real_only')?.words)}; lab documents 1–2 {pc(lab('v2')?.letters)} against {pc(lab('real_only')?.letters)}. So the extra $40 for Gemini was not spent.</>}>
          <Look name="judge" maxH={300} alt="lines where v1 and Azure disagreed, with Gemini's verdict" caption="From the judging sheet: training lines (never test lines) with both readings." />
        </Lesson>

        <Lesson n={4} title="«» against (( )) is a convention, not a misreading."
          body={<>Azure writes printed «» as (( )), and our readers learned that from Azure&apos;s labels. Your corrections write «» on some lines and (( )) on others, sometimes on the same page, so part of what looks like an error is which convention the truth used. The marks below ignore punctuation for this reason.</>}>
          {(l.quotes || []).map((q: any) => (
            <div key={q.key} className="mt-2 first:mt-0">
              <LineCrop k={q.key} width={q.width} h={50} />
              <Reading compact label="Your correction" truth={q.truth} text={q.truth} plain />
              <Reading compact label="Ours" truth={q.truth} text={q.ours} plain />
              <Reading compact label="Azure" truth={q.truth} text={q.azure} plain />
            </div>))}
        </Lesson>

        <Lesson n={5} title="The filled loop of و: fixed by giving the signal reader the ink's thickness."
          body={<>In heavy old print the loop of a <span className="ar-inline">و</span> fills with ink, and its path looks like a <span className="ar-inline">ر</span>. Telling the signal reader how thick the ink is at each point cut real <span className="ar-inline">و</span> errors from <b>{wawPct('p3n')}</b> to <b>{wawPct('p3t')}</b>{wawR('p3n') ? <> (read as <span className="ar-inline">ر</span>: {wawR('p3n')} → {wawR('p3t')} times of {waw.p3t?.n?.toLocaleString('en')})</> : null} (experiment 79).</>}>
          <Look name="loop" maxH={320} alt="a filled و in a 1937 line, with the pen path traced round it" caption="A 1937 line: the path traced round the filled loop (left: skeleton, right: minimum covering runs). Rings mark the blob." />
        </Lesson>

        <Lesson n={6} title="The signal reader reads from movement alone, does no harm, but warns less than a second image reader."
          body={<>Never trained on a real line, it gets <b>{f.all ? `${f.all.signal.toFixed(1)}%` : '—'}</b> of letters wrong from the pen&apos;s path alone. Combined with our image reader, letters wrong go from {pc(f.all?.image77)} to {pc(f.all?.fused_signal)}, and {eras.length && eras.every(([, v]) => v.fused_signal_do_no_harm) ? 'in no era does it make things worse' : 'it is not harmless in every era'}{eras.length ? ` (${eras.map(([k, v]) => `${k}: ${pc(v.image77)} → ${pc(v.fused_signal)}`).join('; ')})` : ''}. As a warning it is weaker than simply asking a second image reader: flagging 10% of lines, it catches {w.sig_ll ? `${Math.round(100 * w.sig_ll.recall)}%` : '—'} of the image reader&apos;s wrong lines, the second image reader {w.ctl_dis ? `${Math.round(100 * w.ctl_dis.recall)}%` : '—'}.</>}>
          <Look name="signal" maxH={220} alt="a 1937 line followed as a pen: pieces numbered, and the signal over time" caption="A line followed as a pen: the numbered pieces in reading order, and below, the signal over time." />
        </Lesson>
      </div>
    </section>
  );
}

const Lesson: React.FC<{ n: number; title: string; body: React.ReactNode; children?: React.ReactNode }> = ({ n, title, body, children }) => (
  <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col" data-testid={`lesson-${n}`}>
    <h3 className="font-semibold text-gray-900 flex gap-2"><span className="text-teal-700 tabular-nums">{n}</span>{title}</h3>
    <p className="text-sm text-gray-700 mt-1.5 mb-3 leading-relaxed">{body}</p>
    <div>{children}</div>
  </div>
);

const MiniBars: React.FC<{ items: [string, number | undefined, string][]; unit: string }> = ({ items, unit }) => {
  const max = Math.max(...items.map(i => i[1] || 0), 0.01);
  return (
    <div className="space-y-1.5">
      {items.map(([label, v, c]) => (
        <div key={label} className="grid grid-cols-[12rem_1fr] items-center gap-3">
          <div className="text-xs text-gray-700">{label}</div>
          <div className="flex items-center gap-2"><div className="h-3.5 rounded-r" style={{ width: `${((v || 0) / max) * 75}%`, background: c }} /><span className="text-xs tabular-nums">{pc(v)}</span></div>
        </div>))}
      <div className="text-[11px] text-gray-500">{unit}</div>
    </div>
  );
};

// ---------------------------------------------------------------- spend

const EXP_NAME: Record<string, string> = { '77': '77 · real lines + Gemini judge', '78': '78 · synthetic lines', '79': '79 · signal reader' };

function Spend({ s }: { s: any }) {
  const gpu = s.gpu as any[];
  const total = gpu.reduce((a, e) => a + e.usd, 0) + (s.gemini?.usd || 0);
  const t = (iso: string) => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  return (
    <Card title={<span className="flex items-center gap-2"><Coins className="w-4 h-4 text-teal-700" aria-hidden />What it cost</span>}
      right={<span className="text-sm text-gray-600">all three experiments: <b className="tabular-nums">${total.toFixed(2)}</b></span>}>
      <div className="grid grid-cols-4 gap-3" data-testid="spend">
        {gpu.map(e => (
          <div key={e.exp} className="rounded-lg border border-gray-200 p-3">
            <div className="text-xs text-gray-500">GPU, experiment {EXP_NAME[e.exp] || e.exp}</div>
            <div className="text-xl font-semibold tabular-nums mt-1">${e.usd.toFixed(2)} <span className="text-xs font-normal text-gray-500">of ${e.cap.toFixed(0)}</span></div>
            <ul className="mt-2 space-y-0.5 text-[11px] text-gray-600">
              {e.instances.map((i: any) => (
                <li key={i.instance} className="flex justify-between gap-2">
                  <span>{i.gpu}, {t(i.started)}, {Math.round(i.minutes)} min</span>
                  <span className="tabular-nums">${i.usd.toFixed(2)}{i.running && <> <Chip tone="indigo" title="this session was still logging minutes when the page was opened">running</Chip></>}</span>
                </li>))}
            </ul>
          </div>))}
        <div className="rounded-lg border border-gray-200 p-3">
          <div className="text-xs text-gray-500">Gemini, experiment 77 (the judge)</div>
          <div className="text-xl font-semibold tabular-nums mt-1">${s.gemini.usd.toFixed(2)} <span className="text-xs font-normal text-gray-500">of ${s.gemini.cap.toFixed(0)}</span></div>
          <p className="mt-2 text-[11px] text-gray-600">{s.gemini.answers.toLocaleString('en')} lines judged ({s.gemini.calls.toLocaleString('en')} paid calls, with the first costing tests), {s.gemini.model}. The conditional ${s.gemini.extra_cap_unused.toFixed(0)} more was not used: v2 did not beat v1.</p>
        </div>
      </div>
      <p className="text-xs text-gray-500 mt-3 flex gap-1.5"><Info className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden />Read from each experiment&apos;s minute-by-minute rental log and the judge&apos;s log as the page opens ({t(s.at)}). One RTX 5090 at about $1 an hour; every finished host was destroyed. Our first reader&apos;s whole training run is the ${gpu.find(e => e.exp === '77')?.instances?.find((i: any) => i.instance === V1_SESSION)?.usd?.toFixed(2)} session of experiment 77 (42 minutes).</p>
    </Card>
  );
}
