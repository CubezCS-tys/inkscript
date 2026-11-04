import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Image as ImageIcon, BookOpen, Link2, CornerDownLeft } from 'lucide-react';
import Layout from '../../components/Layout';
import { Card, Chip, Crop, Empty, ErrorBox, T, Tabs, n } from '../../components/Bits';
import { History, Notes } from '../../components/History';
import { cropOfAnchor, cropOfBlock, enc, hrefOf, isArabic } from '../../lib/api';
import { useApi } from '../../lib/me';
import { S, f } from '../../lib/strings';
import { FigNotes, ROLE, TableFig, Verses, withCalls } from '../../components/ArticleText';
import BesideScan, { ClassicPage, View, ViewSwitch } from '../../components/BesideScan';
import AllFields from '../../components/AllFields';
import { useShowMode } from '../../lib/showmode';

// ------------------------------------------------------------------ pieces of the full text
const InkToggle: React.FC<{ stem: string; b: any }> = ({ stem, b }) => {
  const [on, setOn] = useState(false);
  const srcs = b.parts?.length ? b.parts.map((p: any) => cropOfBlock(stem, p.page, b.block_id)) : [cropOfAnchor(b.anchor)];
  return (
    <>
      <button onClick={() => setOn(!on)} className="text-gray-300 hover:text-indigo-600 shrink-0 mt-1" aria-label={on ? S.common.hideInk : S.common.showInk} title={on ? S.common.hideInk : S.common.showInk} data-ink={b.block_id}>
        <ImageIcon className="w-4 h-4" />
      </button>
      {on && <div className="basis-full space-y-1 pt-1">{srcs.map((s: string, i: number) => <Crop key={i} src={s} maxH="max-h-[32rem]" rtl={b.script === 'ar'} />)}</div>}
    </>
  );
};

// v3.5b: the parts of a cited work the reader gave apart (each as printed)
const CitationParts: React.FC<{ c: any }> = ({ c }) => {
  const p = c.parts || {};
  const cal = (k?: string) => (k ? (S.article.calendar as any)[k] || k : '');
  const items: [string, string][] = [];
  if (c.editors?.length) items.push([S.article.editors, c.editors.join('؛ ')]);
  if (c.translators?.length) items.push([S.article.translators, c.translators.join('؛ ')]);
  if (p.edition) items.push([S.article.edition, p.edition]);
  (c.authors_died || []).forEach((x: any) => items.push([S.article.died, `${x.name}: ${x.died}`]));
  if (!c.authors_died?.length && p.died) items.push([S.article.died, p.died]);
  if (p.year_calendar || p.year2) items.push([S.article.year, [c.year && `${c.year}${p.year_calendar ? ` (${cal(p.year_calendar)})` : ''}`, p.year2 && `${p.year2}${p.year2_calendar ? ` (${cal(p.year2_calendar)})` : ''}`].filter(Boolean).join(' / ')]);
  if (p.cited_pages_source === 'cited-pages' && c.cited_pages) items.push([S.article.citedPage, c.cited_pages]);
  if (p.work_pages && p.cited_pages_source === 'cited-pages') items.push([S.article.workPages, p.work_pages]);
  if (p.access_date) items.push([S.article.accessed, p.access_date]);
  if (p.ms_library || p.ms_shelfmark || p.ms_folio) items.push([S.article.manuscript, [p.ms_library, p.ms_shelfmark, p.ms_folio].filter(Boolean).join(' · ')]);
  if (p.thesis_degree) items.push([S.article.degree, p.thesis_degree]);
  if (p.conf_name || p.conf_loc) items.push([S.article.conf, [p.conf_name, p.conf_loc].filter(Boolean).join(' · ')]);
  if (!items.length) return null;
  return (
    <p className="text-xs text-gray-600 flex flex-wrap gap-x-3 gap-y-0.5" data-testid="citation-parts">
      {items.map(([k, v], i) => <span key={i}><span className="text-gray-400">{k}</span> <T text={v} /></span>)}
    </p>
  );
};

const FullText: React.FC<{ a: any; noInk?: boolean }> = ({ a, noInk }) => {
  const callsByBlock = useMemo(() => {
    const m: Record<string, any[]> = {};
    a.calls.forEach((c: any) => { (m[c.block_id] ||= []).push(c); });
    return m;
  }, [a]);
  const figs = useMemo(() => Object.fromEntries(a.figures.map((x: any) => [x.figure_id, x])), [a]);
  const shown = new Set<string>();
  const out: React.ReactNode[] = [];
  a.blocks.forEach((b: any) => {
    if (b.role === 'footnote' || b.role === 'endnote') return;          // in the notes, beside their calls
    if (b.role === 'table-cell') {
      if (b.figure_id && figs[b.figure_id] && !shown.has(b.figure_id)) { shown.add(b.figure_id); out.push(<TableFig key={`t${b.figure_id}`} fig={figs[b.figure_id]} />); }
      return;
    }
    const ar = b.script === 'ar';
    let body: React.ReactNode;
    if (b.verses?.length) body = <Verses verses={b.verses} />;
    else body = <p dir={ar ? 'rtl' : 'ltr'} className={`${ar ? 'ar' : ''} ${ROLE[b.role] || 'text-[16px] leading-8'} whitespace-pre-wrap`}>{withCalls(b.text || '', callsByBlock[b.block_id])}</p>;
    const fig = b.role === 'caption' && b.figure_id ? figs[b.figure_id] : null;
    if (fig) shown.add(fig.figure_id);
    out.push(
      <div key={b.block_id} id={`b-${b.block_id}`} className="flex flex-wrap gap-2 items-start group" data-block={b.block_id} data-role={b.role}>
        <div className="flex-1 min-w-0">
          {fig && fig.kind !== 'table' && <p className="text-xs text-gray-500 flex items-center gap-1"><BookOpen className="w-3.5 h-3.5" />{S.article.figure} {fig.figure_id}{fig.fig_type && <Chip tone="indigo" title={S.article.figureKind}>{fig.fig_type}</Chip>}{fig.alt_en ? ` · ${fig.alt_en}` : ''}</p>}
          {body}
          {fig && fig.kind !== 'table' && <FigNotes fig={fig} />}
          {fig && fig.kind === 'table' && fig.cells?.length > 0 && !shown.has('t' + fig.figure_id) && <TableFig fig={fig} />}
        </div>
        <span className="text-[10px] text-gray-300 mt-1.5 w-14 text-right shrink-0" title={`${b.role} · ${b.block_id}`}>{b.role === 'paragraph' ? '' : b.role}</span>
        {!noInk && <InkToggle stem={a.stem} b={b} />}
      </div>);
  });
  a.figures.filter((x: any) => !shown.has(x.figure_id) && x.kind === 'table' && x.cells.length).forEach((x: any) => out.push(<TableFig key={`r${x.figure_id}`} fig={x} />));
  return <div className="space-y-3" data-testid="fulltext">{out}</div>;
};

const NotesList: React.FC<{ a: any; noInk?: boolean }> = ({ a, noInk }) => (
  <Card title={S.article.notesTitle} id="notes">
    {a.notes.length === 0 ? <Empty>{S.history.notesNone}</Empty> : (
      <ol className="space-y-2">{a.notes.map((nt: any) => (
        <li key={nt.note_id} id={`note-${nt.note_id}`} className="flex flex-wrap gap-2 items-start rounded" data-note={nt.note_id}>
          <div className="flex-1 min-w-0">
            <p dir={nt.script === 'ar' ? 'rtl' : 'ltr'} className={`${nt.script === 'ar' ? 'ar' : ''} text-sm leading-7 text-gray-800`}>{nt.text}</p>
            <p className="text-xs text-gray-400">{nt.kind === 'author-note' ? <Chip>{S.article.authorNote}</Chip> : nt.kind}{nt.written_by && <> <Chip tone="amber">{(S.article.noteBy as any)[nt.written_by] || nt.written_by}</Chip></>} · {S.common.page} {nt.page}
              {nt.calls.length > 0 && <> · {S.article.calledFrom} {nt.calls.map((c: number) => <a key={c} href={`#call-${c}`} className="text-indigo-600 hover:underline mx-0.5 inline-flex items-center"><CornerDownLeft className="w-3 h-3" />{c}</a>)}</>}
            </p>
          </div>
          {!noInk && <InkToggle stem={a.stem} b={{ block_id: nt.first_block_id, parts: [], anchor: nt.anchor }} />}
        </li>))}
      </ol>)}
  </Card>
);

const CitedBy: React.FC<{ a: any }> = ({ a }) => {
  const own = a.journal?.journal_id || a.journal?.id;
  const others = (a.cited_by || []).filter((c: any) => c.journal_id && c.journal_id !== own).length;
  return (
  <Card pad={false} title={`${S.article.citedBy} (${(a.cited_by || []).length})`} right={others > 0 ? <Chip tone="green">{others} from another journal</Chip> : undefined}>
    {!(a.cited_by || []).length ? <div className="px-5 pb-4"><Empty>{S.article.citedByNone}</Empty></div> : (
      <ol className="divide-y divide-gray-100" data-testid="cited-by">{a.cited_by.map((c: any) => (
        <li key={c.stem} className="px-5 py-3 flex flex-wrap items-baseline justify-between gap-2">
          <span className="min-w-0">
            <Link href={`/articles/${enc(c.stem)}`} className="font-medium text-gray-900 hover:text-indigo-700 hover:underline"><T text={c.title || c.stem} /></Link>
            {c.journal && <span className="block text-xs text-gray-500 mt-0.5">in <Link href={`/journals/${c.journal_id}`} className="hover:text-indigo-700"><T text={c.journal} /></Link>
              {c.journal_id !== own && <span className="ml-2"><Chip tone="green">another journal</Chip></span>}</span>}
          </span>
          <span className="text-xs text-gray-500 tabular-nums">{c.year || ''} · {f(S.article.citedByMentions, { n: c.n_mentions })}</span>
        </li>))}
      </ol>)}
  </Card>
  );
};

const Citations: React.FC<{ a: any; showMode?: boolean }> = ({ a, showMode }) => (
  <Card pad={false} title={`${S.article.citations} (${a.citations.length})`}>
    <ol className="divide-y divide-gray-100" data-testid="citations">{a.citations.map((c: any, i: number) => (
      <li key={c.mention_id} id={`m-${c.mention_id}`} className="px-5 py-3 grid md:grid-cols-[2.5rem_minmax(0,1fr)_16rem] gap-3" data-citation={c.mention_id}>
        <div className="text-xs text-gray-400 tabular-nums">{i + 1}<div><Chip tone={c.kind === 'full' ? 'indigo' : 'gray'}>{c.kind}</Chip></div></div>
        <div className="min-w-0 space-y-1">
          {!String(a.version?.run || "").startsWith("w") && <Crop src={cropOfAnchor(c.anchor)} maxH="max-h-24" rtl={c.script === "ar"} />}
          <T as="p" text={c.printed} className="text-[15px] leading-7" />
          <CitationParts c={c} />
          <p className="text-xs text-gray-400">{S.common.page} {c.page}{!showMode && <> · {c.container_kind} {c.container_id}</>}{c.cited_pages && c.parts?.cited_pages_source !== 'cited-pages' ? ` · p. ${c.cited_pages}` : ''}</p>
        </div>
        <div className="text-sm space-y-1">
          {c.card ? (
            <Link href={hrefOf(c.card.work)!} className="block hover:bg-indigo-50 rounded px-1 -mx-1" data-testid="card-link">
              <T text={c.card.title} className="text-indigo-700 font-medium" />
              <span className="block text-xs text-gray-500">{!showMode && <>{c.card.id} · </>}{f(S.article.timesCited, { n: c.card.n_citing_pubs })}</span>
            </Link>
          ) : c.kind === 'full' ? <span className="text-xs text-gray-400">{S.article.noCard}</span> : null}
          {c.link && (
            <div className="text-xs flex items-start gap-1"><Link2 className="w-3.5 h-3.5 text-green-700 shrink-0 mt-0.5" />
              {c.link.target_stem ? <Link href={`/articles/${enc(c.link.target_stem)}`} className="text-green-800 hover:underline"><T text={c.link.title_shown} /></Link>
                : <span className="text-green-800"><T text={c.link.title_shown || c.link.target_value} />{!showMode && <> ({S.article.catalogueLink} {c.link.target_pub_id})</>}</span>}
              {!showMode && <Chip tone={c.link.status === 'accepted' ? 'green' : 'amber'}>{c.link.status}</Chip>}
            </div>)}
          {c.target && <a href={`#m-${c.target.key.slice(8)}`} className="block text-xs text-gray-600 hover:text-indigo-700">{S.article.backref} <T text={(c.target.printed || '').slice(0, 90)} /></a>}
          {!showMode && c.resolve && !c.target && c.kind !== 'full' && <Chip tone="amber">{S.article.unresolved}{c.resolve.unresolved_why ? `: ${c.resolve.unresolved_why}` : ''}</Chip>}
        </div>
      </li>))}
    </ol>
  </Card>
);

const Quality: React.FC<{ a: any }> = ({ a }) => (
  <div className="space-y-4">
    <Card pad={false} title={`${S.article.pageProblems} (${(a.page_marks || []).length})`}>
      {!(a.page_marks || []).length ? <div className="px-5 pb-4"><Empty>{S.article.pageProblemsNone}</Empty></div> : (
        <table className="w-full text-sm" data-testid="page-problems"><tbody>{a.page_marks.map((x: any, i: number) => (
          <tr key={i} className="border-t border-gray-100"><td className="px-4 py-1.5 whitespace-nowrap"><Chip tone={x.kind === 'scan-problem' ? 'amber' : 'gray'}>{(S.article.pageProblemKinds as any)[x.kind] || x.kind}</Chip></td>
            <td className="px-2 py-1.5 text-gray-500 whitespace-nowrap">{S.common.page} {x.page}{x.line_id ? ` · ${x.line_id}` : ''}</td>
            <td className="px-2 py-1.5 text-gray-700">{x.problem ? x.problem.replace(/_/g, ' ') : <T text={x.text} />}</td></tr>))}
        </tbody></table>)}
    </Card>
    <Card pad={false} title={`${S.article.flags} (${a.flags.length})`}>
      <table className="w-full text-sm"><tbody>{a.flags.map((x: any) => (
        <tr key={x.flag_id} className="border-t border-gray-100"><td className="px-4 py-1.5 whitespace-nowrap"><Chip tone={x.severity === 'high' ? 'red' : 'amber'}>{x.kind}</Chip></td>
          <td className="px-2 py-1.5 text-gray-500 whitespace-nowrap">{S.common.page} {x.page}</td><td className="px-2 py-1.5 text-gray-700"><T text={x.reason} /></td></tr>))}
      </tbody></table>
    </Card>
    <Card pad={false} title={`${S.article.findings} (${a.judge_findings.length})`}>
      <table className="w-full text-sm"><tbody>{a.judge_findings.map((x: any) => (
        <tr key={x.finding_pk} className="border-t border-gray-100"><td className="px-4 py-1.5 whitespace-nowrap"><Chip>{x.type}</Chip></td>
          <td className="px-2 py-1.5 text-gray-500 whitespace-nowrap">{S.common.page} {x.page} · {x.route}</td><td className="px-2 py-1.5 text-gray-700"><T text={x.evidence} /></td></tr>))}
      </tbody></table>
    </Card>
    <Card pad={false} title={`${S.article.corrections} (${a.corrections.length})`}>
      <div className="max-h-[36rem] overflow-y-auto">
        <table className="w-full text-sm"><thead className="bg-gray-50 text-xs text-gray-500 sticky top-0"><tr>
          <th className="px-4 py-2 text-left font-medium">layer</th><th className="px-2 py-2 text-right font-medium">{S.article.azure}</th>
          <th className="px-2 py-2 text-right font-medium">{S.article.printedAs}</th><th className="px-2 py-2 text-right font-medium">{S.article.proposed}</th><th className="px-2 py-2 text-left font-medium">why</th></tr></thead>
          <tbody>{a.corrections.map((x: any) => (
            <tr key={x.xml_id} className="border-t border-gray-100"><td className="px-4 py-1.5 text-xs whitespace-nowrap">{x.layer}</td>
              <td className="px-2 py-1.5 ar text-red-700/80">{x.azure_reading}</td><td className="px-2 py-1.5 ar">{x.printed}</td><td className="px-2 py-1.5 ar text-gray-500">{x.proposed}</td>
              <td className="px-2 py-1.5 text-xs text-gray-500">{x.why}</td></tr>))}
          </tbody></table>
      </div>
    </Card>
  </div>
);

// ------------------------------------------------------------------ the page
export default function ArticlePage() {
  const router = useRouter();
  const stem = typeof router.query.stem === 'string' ? router.query.stem : null;
  const tab0 = typeof router.query.tab === 'string' ? router.query.tab : 'text';
  const { data: a, err } = useApi<any>(stem ? `/articles/${enc(stem)}` : null);
  const showMode = useShowMode();
  // experiment 73 (M8): built from the publisher's Word file (run w…): no scan, so no scan views; pages are estimates (D36)
  const isWord = !!a && String(a.version?.run || '').startsWith('w');
  const HIDDEN_IN_SHOW = ['quality', 'history', 'notes'];
  const tab = showMode && HIDDEN_IN_SHOW.includes(tab0) ? 'text' : tab0;
  const setTab = (t: string) => router.replace({ pathname: router.pathname, query: { stem, tab: t } }, undefined, { shallow: true, scroll: false });
  // the Text tab's three views: the text, the text beside the scan, the scan only (?view=beside|scan)
  const view: View = tab === 'text' && !isWord && (router.query.view === 'beside' || router.query.view === 'scan' || router.query.view === 'classic') ? router.query.view : 'text';
  const setView = (v: View) => {
    router.replace({ pathname: router.pathname, query: v === 'text' ? { stem, tab: 'text' } : { stem, tab: 'text', view: v } }, undefined, { shallow: true, scroll: false });
    if (v !== 'text') setTimeout(() => document.getElementById('article-views')?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 50);
  };
  const meta = (field: string) => (a?.metadata?.[field] || []).find((r: any) => r.is_chosen)?.value ?? (a?.metadata?.[field] || [])[0]?.value;
  return (
    <Layout wide={view !== 'text'}>
      {err && <ErrorBox>{err}</ErrorBox>}
      {!a ? !err && <Empty>{S.common.loading}</Empty> : (
        <>
          <Card>
            <div className="pt-4 space-y-3" data-testid="article-head">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-gray-500 flex flex-wrap items-center gap-x-1">Article{!showMode && <> · <span className="font-mono">{a.stem}</span> · {a.pub_id} · {S.common.readFrom} {a.release_id || S.common.reading}</>}
                  {isWord && <span className="ml-1"><Chip tone="indigo" title="Mandumah holds this article only as the publisher's Word file: the text and structure come from that file, not from a scan.">Built from the publisher's Word file</Chip></span>}</p>
                <div className="flex items-center gap-2">
                  {!isWord && <button onClick={() => setView('beside')} className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm text-indigo-700 hover:bg-indigo-100" data-testid="beside-scan-native"><ImageIcon className="w-4 h-4" />{S.article.besideScan}</button>}
                  {!showMode && a.version?.mirror && <a href={a.version.mirror} target="_blank" rel="noopener" className="text-xs text-gray-500 hover:text-indigo-700 hover:underline" data-testid="beside-scan" title="experiment 41's mirror page, in a new tab">mirror page ↗</a>}
                </div>
              </div>
              <div className="space-y-1">
                <T as="div" text={a.title.shown || a.title.printed} className="text-2xl font-semibold text-gray-900" />
                <dl className="grid sm:grid-cols-[8rem_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
                  {(['printed', 'corrected', 'catalogue'] as const).map(k => a.title[k] && !(showMode && a.title[k] === (a.title.shown || a.title.printed)) && !(showMode && k === 'corrected') ? (
                    <React.Fragment key={k}><dt className="text-gray-500">{S.article[k]}</dt><dd><T text={a.title[k]} className={a.title[k] === a.title.shown ? 'text-gray-900' : 'text-gray-600'} /></dd></React.Fragment>) : null)}
                  {a.title.translated && <><dt className="text-gray-500">{S.article.translated}</dt><dd><T text={a.title.translated} /></dd></>}
                </dl>
              </div>
              <dl className="grid grid-cols-2 md:grid-cols-6 gap-3 text-sm">
                <div><dt className="text-xs text-gray-500">{S.article.journal}</dt><dd><T text={a.journal?.title || meta('journal_title')} /></dd></div>
                <div><dt className="text-xs text-gray-500">{S.article.year}</dt><dd>{meta('year') || a.catalogue?.year_raw || '—'}</dd></div>
                <div><dt className="text-xs text-gray-500">{S.article.pages}</dt><dd>{meta('fpage') ? `${meta('fpage')}–${meta('lpage') || ''}` : a.catalogue?.pages_raw || '—'}</dd></div>
                <div><dt className="text-xs text-gray-500">{S.article.volIssue}</dt><dd>{[a.issue?.volume_raw || meta('volume'), a.issue?.issue_printed || a.issue?.issue_raw || meta('issue')].filter(Boolean).join(' / ') || '—'}</dd></div>
                <div><dt className="text-xs text-gray-500">{S.article.docType}</dt><dd data-testid="doc-type">
                  {a.doc_type?.shown ? <><Chip tone="indigo">{a.doc_type.shown.replace(/_/g, ' ')}</Chip> <span className="text-xs text-gray-400">{a.doc_type.shown_from === 'page' ? S.article.docPage : S.article.docCatalogue}</span></> : '—'}
                  <span className="block text-xs text-gray-500">{S.article.docPage}: {a.doc_type?.page ? a.doc_type.page.replace(/_/g, ' ') : <span className="text-gray-400">{S.article.docNotRead}</span>}</span>
                  {a.doc_type?.catalogue && <span className="block text-xs text-gray-500">{S.article.docCatalogue}: <span className="ar-inline">{a.doc_type.catalogue}</span></span>}
                  {a.doc_type?.disagreement?.length > 0 && <Chip tone="amber">{S.article.docDisagree}</Chip>}
                </dd></div>
                {showMode ? (a.catalogue?.doi ? <div><dt className="text-xs text-gray-500">DOI</dt><dd className="font-mono text-xs">{a.catalogue.doi}</dd></div> : null)
                  : <div><dt className="text-xs text-gray-500">{S.article.ids}</dt><dd className="font-mono text-xs">{a.catalogue?.c999 ? `999$c ${a.catalogue.c999}` : '—'}{a.catalogue?.doi ? ` · ${a.catalogue.doi}` : ''}<br />{S.article.version} {a.version.run}</dd></div>}
              </dl>
            </div>
          </Card>
          {a.about && Object.keys(a.about).length > 0 && (
            <Card title={S.article.about}>
              <dl className="grid md:grid-cols-2 gap-3 text-sm" data-testid="about">{Object.entries(a.about).map(([k, v]: [string, any]) => (
                <div key={k} className="rounded-lg border border-gray-100 p-3">
                  <dt className="text-xs text-gray-500 mb-1">{(S.article as any)[k] || k}</dt>
                  <dd className="space-y-0.5">{Object.entries(v).filter(([, x]) => x).map(([kk, x]: [string, any]) => (
                    <p key={kk}><span className="text-xs text-gray-400">{kk.replace(/_/g, ' ')}</span> <T text={String(x)} /></p>))}</dd>
                </div>))}
              </dl>
            </Card>)}
          <Card title={S.article.authors}>
            <ul className="grid md:grid-cols-2 gap-3" data-testid="authors">{a.authors.map((au: any) => (
              <li key={`${au.position}-${au.role_code}`} className="rounded-lg border border-gray-100 p-3 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  {au.person ? <Link href={hrefOf(au.person)!} className="text-indigo-700 font-medium hover:underline" data-testid="author-link"><T text={au.name} /></Link> : <T text={au.name} />}
                  <Chip>{au.role_name || au.role_code}</Chip>{!showMode && au.method && <Chip tone={au.method === 'provisional' ? 'amber' : 'gray'}>{au.method}</Chip>}
                  {!showMode && au.authority_id && <span className="text-xs text-gray-500">authority {au.authority_id}</span>}
                  {au.corresponding && <Chip tone="green">{S.article.corresponding}</Chip>}
                  {!showMode && (au.ids || []).map((x: any) => <span key={`${x.scheme}${x.value}`} className="text-xs font-mono text-gray-600" title={x.source}>{x.scheme} {x.value}</span>)}
                </div>
                {au.bylines.map((b: any) => (
                  <div key={b.key} className="space-y-1">
                    {!isWord && <Crop src={cropOfAnchor(b.anchor)} maxH="max-h-16" rtl={isArabic(b.printed)} />}
                    <p className="text-sm text-gray-700">{b.twin && <span className="text-xs text-gray-400">{S.article.alsoPrinted} </span>}<T text={b.printed} />
                      {b.role_phrase && <> <Chip>{b.role_phrase}</Chip></>}{b.contrib_type && b.contrib_type !== 'author' && !b.twin && <> <Chip tone="amber">{b.contrib_type}</Chip></>}
                      {!showMode && b.ids && Object.entries(b.ids).map(([k, v]: [string, any]) => <span key={k} className="ms-1 text-xs font-mono text-gray-500">{k} {v}</span>)}</p>
                    {b.affiliations.map((af: any) => (
                      <p key={af.aff_pk} className="text-xs text-gray-500"><T text={af.printed} />{af.assembled ? <> <Chip>{S.article.partsAsPrinted}</Chip></> : null}
                        {(af.faculty_printed || af.faculty_text) && <> · <span className="text-gray-400">{S.article.faculty}</span> <T text={af.faculty_printed || af.faculty_text} /></>}
                        {af.institutions.length > 0 && <> → {af.institutions.map((i: any) => <span key={i.inst_id} className="ar-inline text-gray-700">{i.name}{!showMode && <> <span className="font-mono">{i.inst_id}</span></>} </span>)}</>}</p>
                    ))}
                  </div>))}
              </li>))}
            </ul>
          </Card>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Tabs value={tab} onChange={setTab} tabs={([['text', S.article.text], ['citations', `${S.article.citations} (${a.citations.length})`], ['cited_by', `${S.article.citedBy} (${(a.cited_by || []).length})`], ['quality', S.article.quality], ['fields', 'All fields'],
              ['history', S.common.history], ['notes', S.common.notes]] as [string, string][]).filter(([k]) => !(showMode && HIDDEN_IN_SHOW.includes(k)))} />
            <span className="text-xs text-gray-500">{!showMode && <>{n(a.counts.blocks)} blocks · </>}{n(a.counts.notes)} notes · {n(a.counts.citations)} references · cited by {n((a.cited_by || []).length)} · {n(a.counts.figures)} figures</span>
          </div>
          {tab === 'text' && <div id="article-views" className="scroll-mt-14 space-y-4">
            {view === 'text' ? <><div className="flex justify-end"><ViewSwitch value={view} onChange={setView} noScan={isWord} /></div><Card><div className="pt-4"><FullText a={a} noInk={isWord} /></div></Card><NotesList a={a} noInk={isWord} /></>
              : view === 'classic' ? <ClassicPage a={a} onView={setView} />
              : <BesideScan a={a} view={view} onView={setView} />}
          </div>}
          {tab === 'fields' && <AllFields stem={a.stem} />}
          {tab === 'citations' && <Citations a={a} showMode={showMode} />}
          {tab === 'cited_by' && <CitedBy a={a} />}
          {tab === 'quality' && <Quality a={a} />}
          {tab === 'history' && <History subject={a.subject} path={`/articles/${enc(a.stem)}/history`} />}
          {tab === 'notes' && <Notes subject={a.subject} />}
        </>
      )}
    </Layout>
  );
}
