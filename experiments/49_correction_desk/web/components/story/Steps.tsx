import React from 'react';
import { cropOfAnchor } from '../../lib/api';
import { Journey } from '../ProjectMap';
import { Big, BeforeAfter, Bridge, Compare, Eyebrow, Headline, Legend, LiveButton, Panel, Shot, WordGrid, at, d, missing, num, pct, usd } from './Bits';

// The seven steps of the Story (experiment 73, AUDIT.md §4). Each: one plain headline, one to three visuals,
// one "open the live screen" button. h = GET /desk/api/headlines (may be null: every value then shows "—").
export type Ctx = { h: any; project: any; work: any; j: Record<string, any> };

export const STEPS: { key: string; short: string; render: (c: Ctx) => React.ReactNode }[] = [
  { key: 'problem', short: 'The problem', render: Problem },
  { key: 'read', short: 'How a page is read', render: HowRead },
  { key: 'ink', short: 'Every fact → the ink', render: Ink },
  { key: 'quality', short: 'Quality, measured', render: Quality },
  { key: 'index', short: 'The index forms', render: IndexForms },
  { key: 'reconcile', short: 'One work, one card', render: Reconcile },
  { key: 'next', short: 'Cost and what is next', render: Next },
];

// The scan articles the story opens (no Word-route article: those have no page images)
const STEM = '0165-008-029-001';
const PERSON = 'AH50PYZD9R';     // Mohamed Mahmoud Al-Attar: an author of both journals (gate 2's shared authors)
// لسان العرب (Ibn Manzur): every printed citation joined into one work. Chosen 2026-11-03 after checking all 39
// members against their print (35 crops looked at, 4 by text); CBDD9P2BCR, the audit's first choice, also held three
// citations of another book (al-Kaabi 2011), reported to the lead.
export const WORK = 'C7H83S6DX4';

function Problem() {
  // the outside facts and the archive counts are the deck's, each with its source (pitch slides 2–3)
  return (<>
    <Eyebrow n={1}>The problem and the asset</Eyebrow>
    <Headline action={<LiveButton href="/index-home" i={3}>Open the index</LiveButton>} sub="Universities, promotion committees and ministries need citation counts for Arabic research. Today they decide on a thin slice of the evidence. Mandumah holds the rest.">
      Arabic research is judged by indexes that barely see it.
    </Headline>
    <div className="grid grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-6 mt-7">
      <Panel title="What the world's indexes see" foot="Scopus: about 280 of 29,553 journals (Al-Fanar Media, May 2025). Clarivate's Arabic Citation Index: “over 400” selected journals, from 2015.">
        <Big size="xl" tone="gray" value="<1%" label="of the journals in Scopus come from Arab countries" />
        <div className="mt-6" aria-hidden>
          <div className="h-5 rounded-md bg-gray-200 overflow-hidden flex">
            <div className="st-bar h-full bg-indigo-500" style={{ width: '0.95%', minWidth: 4, ['--d' as any]: '700ms' }} />
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-1.5"><span>Arab countries ≈ 280</span><span>all Scopus journals 29,553</span></div>
        </div>
      </Panel>
      <Panel title="What Mandumah already holds" i={4} foot="Counted in the archive on 19 Oct 2026 and in the catalogue on 20 Oct 2026.">
        <div className="grid grid-cols-3 gap-6">
          <Big size="lg" tone="teal" value="1,013,912" label="documents with the scan and a full reading of every word" />
          <Big size="lg" tone="teal" value="308,593" label="more as PDFs, most with the publisher's Word file" />
          <Big size="lg" tone="indigo" value="1,558,415" label="catalogue records, with an author file that tells people apart" />
        </div>
        <p className="mt-6 text-base text-gray-700 leading-relaxed">Others index the reference lists of selected journals. We hold the <b>full text</b>, going back decades: the body, the footnotes, the tables. Arabic scholarship cites in its footnotes; only full text can count it, and only the scan can prove it.</p>
      </Panel>
    </div>
  </>);
}

const STAGES: [string, string][] = [
  ['The scan', 'the printed page as it is'], ['The words', 'every word and its box, read from the ink'],
  ['What each line is', 'title, author, footnote, reference…'], ['The article', 'code rules build it, safely'],
  ['A second look', 'a check before anything is kept'], ['The record', 'people, institutions, works, with ids'],
  ['The index', 'joined to everything else'],
];

function HowRead({ h }: Ctx) {
  const c = h?.costs || {};
  return (<>
    <Eyebrow n={2}>How a page is read</Eyebrow>
    <Headline action={<LiveButton href="/pipeline" i={3}>Open live: one page, step by step</LiveButton>}
      sub="Seven steps on a real page. Every word keeps its place on the scan, so every field can be traced back to the printed line.">
      The machine never types the text: it says what each printed line is.
    </Headline>
    <ol className="grid grid-cols-7 gap-2 mt-7">
      {STAGES.map(([t, s], k) => (
        <li key={t} className="st-in relative rounded-xl border border-gray-200 bg-white px-3 py-2.5" style={{ ['--d' as any]: `${380 + k * 130}ms` }}>
          <span className="flex items-center gap-2">
            <span className="w-5 h-5 shrink-0 rounded-full bg-teal-600 text-white grid place-items-center text-[11px] font-semibold">{k + 1}</span>
            <span className="text-[15px] font-medium text-gray-900 leading-tight">{t}</span>
          </span>
          <span className="block text-xs text-gray-500 mt-1 leading-snug">{s}</span>
        </li>))}
    </ol>
    <div className="grid grid-cols-[minmax(0,9fr)_minmax(0,3fr)] gap-6 mt-5 items-start">
      <Shot src="/story-shots/pipeline.png" href="/pipeline" alt="How a page is read: one page through the seven steps" caption="How a page is read — a real page at step 4" i={4} h={340} />
      <Panel title="What reading costs" i={5} foot="Measured on gate 2's pilot journal.">
        <div className="space-y-6">
          <Big tone="teal" value={usd(c.per_scan_page_usd, 4)} label="a scanned page" />
          <Big tone="indigo" value={usd(c.per_word_article_usd, 4)} label="an article from the publisher's Word file" />
        </div>
      </Panel>
    </div>
  </>);
}

function Ink({ h }: Ctx) {
  return (<>
    <Eyebrow n={3}>Every fact points at the ink</Eyebrow>
    <Headline action={<>
        <LiveButton href={`/articles/${STEM}?tab=text&view=beside`} i={3}>Open live: the article beside its scan</LiveButton>
        <LiveButton href={`/articles/${STEM}?tab=text&view=classic`} quiet i={4}>The classic page</LiveButton></>}
      sub="The rebuilt article sits beside its scan. Point at a heading, a name or a reference, and the printed lines light up on the page.">
      Click any fact, and you land on the printed lines.
    </Headline>
    <div className="grid grid-cols-[minmax(0,8fr)_minmax(0,4fr)] gap-6 mt-7 items-start">
      <Shot src="/story-shots/beside.png" href={`/articles/${STEM}?tab=text&view=beside`} alt="An article beside its scan" caption="An article beside its scan" i={3} h={440} />
      <div className="space-y-6">
        <Shot src="/story-shots/classic.png" href={`/articles/${STEM}?tab=text&view=classic`} alt="The classic page: the rebuilt edition beside the scan" caption="The classic page" i={4} />
        <Panel i={5}>
          <div className="grid grid-cols-2 gap-4">
            <Big tone="teal" value={num(h?.articles, 0)} label="articles rebuilt so far" />
            <Big tone="indigo" value={num(h?.references, 0)} label="references, each with its ink" />
          </div>
        </Panel>
      </div>
    </div>
  </>);
}

function Quality({ h }: Ctx) {
  const w = h?.words_wrong || {};
  return (<>
    <Eyebrow n={4}>Quality, measured</Eyebrow>
    <Headline action={<LiveButton href={`/audit?tab=article&stem=${STEM}`} i={3}>Open live: one article, line by line</LiveButton>}
      sub="Measured by a person beside the scan, not reported by the machine.">
      {missing(w.wrong) || missing(w.of) ? 'Every word checked against the scan.' : <>{num(w.wrong, 0)} wrong words in {num(w.of, 0)}.</>}
    </Headline>
    <div className="grid grid-cols-[minmax(0,7fr)_minmax(0,5fr)] gap-6 mt-7 items-stretch">
      <Panel title="Every checked word, one square each" i={3}
        foot={`${num(w.pages, 0)} random pages of articles the system had never seen; every word compared by eye with the printed page.`}>
        <WordGrid of={w.of} wrong={w.wrong} />
        <div className="mt-4"><Legend items={[['bg-teal-500', 'read right'], ['bg-red-600', 'read wrong (none)']]} /></div>
      </Panel>
      <Panel title="Nothing lost" i={4} foot={missing(h?.audit?.lines) ? 'Every printed line of every scanned article, followed into the article file.' : `${num(h.audit.lines, 0)} printed lines of ${num(h.audit.articles, 0)} scanned articles, each followed into the article file.`}>
        <Big size="xl" tone="green" value={pct(h?.audit_pct)} label="of the printed lines reach a proper field of the article" />
        <div className="mt-6 h-3 rounded-full bg-gray-100 overflow-hidden" aria-hidden>
          <div className="st-bar h-full rounded-full bg-green-500" style={{ width: `${missing(h?.audit_pct) ? 0 : h.audit_pct}%`, ['--d' as any]: '700ms' }} />
        </div>
        <p className="text-base text-gray-700 mt-6 leading-relaxed">Running heads and page numbers are set aside on purpose; everything else is a title, a name, a paragraph, a footnote or a reference.</p>
      </Panel>
    </div>
  </>);
}

function journalName(c: Ctx, id: string) {
  const fromH = (c.h?.journals_read_whole || []).find((x: any) => x.id === id);
  return fromH?.title || c.j[id]?.title || id.replace(/^J/, 'Journal ');
}

function IndexForms(c: Ctx) {
  const g = c.h?.gate2 || {};
  const [ida, idb] = Array.isArray(g.pair) ? g.pair : ['J0130', 'J0165'];
  // headlines carry the country's name; the journal record only its code
  const country = (id: string) => (c.h?.journals_read_whole || []).find((x: any) => x.id === id)?.country
    || ({ KW: 'Kuwait', EG: 'Egypt' } as any)[c.j[id]?.country] || '';
  const A = { name: journalName(c, ida), sub: country(ida) || ida.replace(/^J/, '') };
  const B = { name: journalName(c, idb), sub: country(idb) || idb.replace(/^J/, '') };
  return (<>
    <Eyebrow n={5}>The index forms</Eyebrow>
    <Headline action={<>
        <LiveButton href={`/journals/${idb}`} i={3}>Open live: the journal record</LiveButton>
        <div className="flex gap-2"><LiveButton href={`/journals/${ida}`} quiet i={4}>The other journal</LiveButton>
        <LiveButton href={`/persons/${PERSON}`} quiet i={5}>An author of both</LiveButton></div></>}
      sub="Read two education journals whole, and the bridges appear: they cite each other, share authors and cite the same works. Random articles of the same size show almost none of it.">
      Two journals read whole cite each other.
    </Headline>
    <div className="grid grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-6 mt-7 items-stretch">
      <Panel title="Citations between the two journals" i={3}>
        <Bridge a={A} b={B} ab={g.cites_a_to_b} ba={g.cites_b_to_a} />
      </Panel>
      <Panel title="What the two journals share" i={4}
        foot="Grey: the first journal against random sets of articles of the same size, drawn twenty times (the average).">
        <div className="mb-5"><Legend items={[['bg-teal-500', `${A.sub} and ${B.sub}, both read whole`], ['bg-gray-300', 'against random articles']]} /></div>
        <div className="space-y-6">
          <Compare i={0} label="Authors who wrote in both" a={at(g.shared_authors, 0)} b={at(g.shared_authors, 1)} aLabel="read whole" bLabel="random" />
          <Compare i={1} label="Works cited by both" a={at(g.shared_works, 0)} b={at(g.shared_works, 1)} aLabel="read whole" bLabel="random" />
          <Compare i={2} label="Article pairs citing the same work" a={at(g.coupled_pairs, 0)} b={at(g.coupled_pairs, 1)} aLabel="read whole" bLabel="random" />
        </div>
      </Panel>
    </div>
  </>);
}

function Reconcile(c: Ctx) {
  const l = c.h?.librarian || {};
  const w = c.work;
  // one printed citation per edition, as cut from the page
  const seen = new Set<any>();
  const key = (t: string) => (t || '').replace(/[ىي]/g, 'ي').replace(/[أإآا]/g, 'ا');
  const surname = key((w?.authors?.[0]?.printed || '').split(/\s+/).pop() || '').replace(/^ال/, '');
  const crops = (w?.members || []).filter((m: any) => {
    if (!m.anchor || seen.has(m.edition_pk)) return false;
    const t = key(m.printed);
    if (!t.includes(key(w.title || '')) || (surname && !t.includes(surname))) return false;
    seen.add(m.edition_pk); return true;
  }).slice(0, 4);
  return (<>
    <Eyebrow n={6}>Reconciliation</Eyebrow>
    <Headline action={<>
        <LiveButton href={`/works/${WORK}`} i={3}>Open live: the cited work</LiveButton>
        <LiveButton href="/librarian/works" quiet i={4}>The librarian, before and after</LiveButton></>}
      sub="Authors cite the same book in many ways. The AI librarian joins them into one work, and a wrong join is never applied: it is checked blind, and used only where it is measured precise.">
      The same book, cited many ways, becomes one work.
    </Headline>
    <div className="grid grid-cols-[minmax(0,7fr)_minmax(0,5fr)] gap-6 mt-7 items-stretch">
      <Panel title="One cited work, as it was printed" i={3}
        foot={`Each strip is cut from the printed page of a different article.${w ? ` In all: ${num(w.members?.length, 0)} printed citations in ${num(w.n_citing_pubs, 0)} articles, one card.` : ''}`}>
        <div className="flex items-baseline gap-3 mb-4">
          <span className="ar text-2xl font-semibold text-gray-900" style={{ textAlign: 'left' }}>{w?.title || '—'}</span>
          <span className="text-sm text-gray-500">{w?.authors?.[0]?.printed || ''}</span>
        </div>
        <div className="space-y-2.5">
          {crops.length ? crops.map((m: any, k: number) => (
            <div key={m.key} className="st-in rounded-lg border border-gray-200 bg-gray-50 p-2 flex justify-end" style={{ ['--d' as any]: `${500 + k * 180}ms` }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={cropOfAnchor(m.anchor) || ''} alt={m.printed} className="max-h-12 max-w-full object-contain mix-blend-multiply" />
            </div>)) : <div className="text-gray-400">—</div>}
        </div>
      </Panel>
      <div className="flex flex-col gap-6">
        <Panel title="The librarian's work so far" i={4}>
          <div className="space-y-5">
            <BeforeAfter i={0} label="Institutions" before={at(l.institutions, 0)} after={at(l.institutions, 1)} unit="records, before and after joining" />
            <BeforeAfter i={1} label="Cited works" before={at(l.cited_works, 0)} after={at(l.cited_works, 1)} unit="cards, before and after joining" />
          </div>
        </Panel>
        <Panel i={5}>
          <div className="grid grid-cols-2 gap-4">
            <Big tone="green" value={pct(l.precision_pct, 1)} label={missing(l.decisions_checked) ? 'of its joins right, checked blind' : `of its joins right, checked blind on ${num(l.decisions_checked, 0)} decisions`} />
            <Big tone="indigo" value={missing(l.usd_per_1000) ? '—' : `≈ ${usd(l.usd_per_1000, 0)}`} label="per 1,000 decisions" />
          </div>
        </Panel>
      </div>
    </div>
  </>);
}

function daysUntil(iso?: string) {
  if (!iso) return null;
  const t = Date.parse(iso + 'T00:00:00Z');
  if (!isFinite(t)) return null;
  return Math.ceil((t - Date.now()) / 86400000);
}

function Next({ h, project }: Ctx) {
  const g = h?.gate2 || {};
  const c = h?.costs || {};
  const days = daysUntil(c.price_doubles);
  const doubles = c.price_doubles ? new Date(c.price_doubles + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'long', timeZone: 'UTC' }) : '—';
  return (<>
    <Eyebrow n={7}>Cost and what is next</Eyebrow>
    <Headline action={<LiveButton href="/project" i={3}>Open live: the journey</LiveButton>} sub="Gate by gate: each step is paid for only after the one before has shown it works.">
      {missing(g.ten_journals_usd) ? 'Ten journals next, then all of education.' : <>Ten journals for about {usd(g.ten_journals_usd, 0)}, then all of education.</>}
    </Headline>
    <div className="mt-7 st-in" style={d(3)}>
      {project ? <Journey d={project} onPick={() => {}} /> : <div className="h-48 rounded-2xl border border-gray-200 bg-white grid place-items-center text-gray-400">—</div>}
    </div>
    <div className="grid grid-cols-3 gap-6 mt-6">
      <Panel i={4}><Big tone="green" value={usd(g.cost_usd)} label="gate 2's pilot: the second journal read whole, measured" /></Panel>
      <Panel i={5}><Big tone="teal" value={missing(g.ten_journals_usd) ? '—' : `≈ ${usd(g.ten_journals_usd, 0)}`} label={missing(g.ten_journals_usd) || missing(g.cost_usd) ? "for all ten journals of gate 2, at the pilot's measured rate"
        : <>for all ten journals of gate 2 at the pilot's measured rate: the nine still to read ≈ {usd(Number(g.ten_journals_usd) - Number(g.cost_usd), 0)}</>} /></Panel>
      <Panel i={6} className="border-amber-200 bg-amber-50/40">
        <Big tone="gray" value={doubles} label={<>the reading price doubles{days !== null && days > 0 ? <> — <b className="text-amber-800">{days} days</b> from today</> : null}. Gate 3 is cheaper decided before.</>} />
      </Panel>
    </div>
  </>);
}
