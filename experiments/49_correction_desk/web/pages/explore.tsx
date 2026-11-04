import React, { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  FileText, Quote, Users, Building2, Newspaper, Library, Columns3, Funnel, Group, Download, Link2, RotateCcw,
  ArrowUp, ArrowDown, ArrowUpDown, X, Plus, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, Search, Bookmark, Check,
} from 'lucide-react';
import Layout from '../components/Layout';
import { Card, Empty, ErrorBox, Btn, n as fmt } from '../components/Bits';
import { api, enc, hrefOf, isArabic } from '../lib/api';
import { SX } from '../lib/strings_explore';

// The Explorer (owner, 2026-10-23: "centralise everything … see and order all fields"). Server side: desk/explore.py.
// The whole view lives in the address: e (entity), c (columns), s/d (sort), q, f (filters, JSON), g/m (group by,
// sum), p (page), n (page size).

type Col = { name: string; type: string; group: string; label: string; src: string; ref: string | null };
type Ent = { label: string; one: string; key: string; default: string[]; sort: [string, string]; about: string; n: number | null; columns: Col[] };
type Filter = { c: string; op: string; v?: any };
type View = { e: string; c: string[] | null; s: string | null; d: boolean | null; q: string; f: Filter[]; g: string | null; m: string | null; p: number; n: number };

const ORDER = ['articles', 'references', 'persons', 'institutions', 'journals', 'works'];
const ICON: Record<string, any> = { articles: FileText, references: Quote, persons: Users, institutions: Building2, journals: Newspaper, works: Library };
const YEAR: Record<string, string> = { articles: 'year', references: 'citing_year', persons: 'first_year', institutions: 'first_year', journals: 'first_year', works: 'year_greg' };
const NUM = new Set(['int', 'real', 'year']);
const SIZES = [25, 50, 100, 250];

// ready-made views, one click each (they only set the address)
const PRESETS: Record<string, { label: string; v: Partial<View> }[]> = {
  articles: [
    { label: 'Most references', v: { s: 'n_full', d: true } },
    { label: 'No references found', v: { f: [{ c: 'n_mentions', op: 'eq', v: 0 }], s: 'n_blocks', d: true } },
    { label: 'Most cited by our articles', v: { s: 'times_cited', d: true, c: ['stem', 'title', 'authors', 'journal', 'year', 'times_cited', 'times_cited_mentions'] } },
    { label: 'Page and catalogue disagree on the type', v: { f: [{ c: 'doc_type_disagrees', op: 'eq', v: 1 }], c: ['stem', 'title', 'doc_type', 'doc_type_page', 'doc_type_catalogue', 'journal', 'year'] } },
    { label: 'Articles by journal', v: { g: 'journal', m: 'n_full' } },
    { label: 'Articles by year', v: { g: 'year' } },
    { label: 'Most flagged', v: { s: 'n_flags', d: true, c: ['stem', 'title', 'n_flags', 'n_flags_high', 'n_flags_medium', 'n_reader_fixes', 'n_misprints', 'wc_mean'] } },
  ],
  references: [
    { label: 'Full references not linked to a work', v: { f: [{ c: 'kind', op: 'eq', v: 'full' }, { c: 'cited_work_id', op: 'empty' }] } },
    { label: 'Ibid / op. cit. left unresolved', v: { f: [{ c: 'unresolved_why', op: 'not_empty' }], c: ['mention_id', 'stem', 'kind', 'printed', 'unresolved_why', 'resolve_method'] } },
    { label: 'Theses cited', v: { f: [{ c: 'pub_type', op: 'eq', v: 'thesis' }], c: ['mention_id', 'stem', 'printed', 'authors', 'source_title', 'thesis_degree', 'year_parsed', 'cited_work_id'] } },
    { label: 'Web references', v: { f: [{ c: 'url', op: 'not_empty' }], c: ['mention_id', 'stem', 'printed', 'url', 'access_date', 'cited_work_id'] } },
    { label: 'References by type', v: { g: 'pub_type' } },
    { label: 'References by citing journal', v: { g: 'citing_journal' } },
  ],
  persons: [
    { label: 'Most articles', v: { s: 'n_articles', d: true } },
    { label: 'Most cited', v: { s: 'times_cited', d: true, c: ['person_id', 'name', 'name_lat', 'n_works_cited', 'times_cited', 'mentions_received', 'death_year_h'] } },
    { label: 'Provisional (from a byline only)', v: { f: [{ c: 'status', op: 'eq', v: 'provisional' }] } },
    { label: 'Authors by country', v: { g: 'countries' } },
  ],
  institutions: [
    { label: 'Universities', v: { f: [{ c: 'kind', op: 'eq', v: 'university' }], s: 'n_authors', d: true } },
    { label: 'Institutions by country', v: { g: 'country', m: 'n_articles' } },
    { label: 'Institutions by kind', v: { g: 'kind' } },
  ],
  journals: [
    { label: 'Journals we have read', v: { f: [{ c: 'n_articles', op: 'gte', v: 1 }], s: 'n_articles', d: true } },
    { label: 'Most cited by our articles', v: { s: 'cited_by_articles', d: true, c: ['journal_id', 'title', 'country', 'cited_by_articles', 'cited_mentions', 'n_citing_journals', 'self_mentions'] } },
    { label: 'Journals by country', v: { g: 'country', m: 'n_articles' } },
  ],
  works: [
    { label: 'Most cited', v: { s: 'times_cited', d: true } },
    { label: 'Linked to the catalogue', v: { f: [{ c: 'catalogue_link', op: 'not_empty' }], c: ['cited_work_id', 'title', 'authors', 'times_cited', 'catalogue_link', 'catalogue_link_title', 'catalogue_link_stem', 'catalogue_link_status'] } },
    { label: 'Theses cited', v: { f: [{ c: 'pub_type', op: 'eq', v: 'thesis' }] } },
    { label: 'Works by type', v: { g: 'pub_type', m: 'times_cited' } },
    { label: 'Works by publisher', v: { g: 'publisher', m: 'times_cited' } },
  ],
};

function readView(q: Record<string, any>): View {
  const s = (k: string) => (typeof q[k] === 'string' ? (q[k] as string) : '');
  let f: Filter[] = [];
  try { const x = JSON.parse(s('f') || '[]'); if (Array.isArray(x)) f = x; } catch { f = []; }
  const e = ORDER.includes(s('e')) ? s('e') : 'articles';
  return {
    e, c: s('c') ? s('c').split(',').filter(Boolean) : null, s: s('s') || null, d: s('d') ? s('d') === 'desc' : null,
    q: s('q'), f, g: s('g') || null, m: s('m') || null, p: Math.max(1, parseInt(s('p') || '1', 10) || 1),
    n: SIZES.includes(parseInt(s('n'), 10)) ? parseInt(s('n'), 10) : 50,
  };
}

function toQuery(v: View): Record<string, string> {
  const o: Record<string, string> = { e: v.e };
  if (v.c) o.c = v.c.join(',');
  if (v.s) o.s = v.s;
  if (v.d !== null && v.s) o.d = v.d ? 'desc' : 'asc';
  if (v.q) o.q = v.q;
  if (v.f.length) o.f = JSON.stringify(v.f);
  if (v.g) o.g = v.g;
  if (v.m && v.g) o.m = v.m;
  if (v.p > 1) o.p = String(v.p);
  if (v.n !== 50) o.n = String(v.n);
  return o;
}

function apiParams(v: View, cols: string[]): string {
  const p = new URLSearchParams();
  p.set('cols', cols.join(','));
  if (v.s) p.set('sort', v.s);
  if (v.d !== null) p.set('desc', String(v.d));
  if (v.q) p.set('q', v.q);
  if (v.f.length) p.set('f', JSON.stringify(v.f));
  return p.toString();
}

// a link for an id the row holds (several ids, space-separated, give several links)
function refHref(ref: string | null, id: string): string | null {
  if (!ref || !id) return null;
  if (ref === 'article') return `/articles/${enc(id)}`;
  if (ref === 'work') return `/works/${enc(id)}`;
  if (ref === 'person') return `/persons/${enc(id)}`;
  if (ref === 'mention') return hrefOf(`mention:${id}`);
  if (ref === 'journal') return `/journals/${enc(id)}`;            // the journal and institution records (index pages)
  if (ref === 'institution') return `/institutions/${enc(id)}`;
  return null;
}

const Cell: React.FC<{ col: Col; v: any; rowKey?: string; keyHref?: string | null }> = ({ col, v, keyHref }) => {
  if (v === null || v === undefined || v === '') return <span className="text-gray-300">—</span>;
  if (col.type === 'int' || col.type === 'real') {
    return <span className="tabular-nums">{col.type === 'real' ? Number(v).toLocaleString('en', { maximumFractionDigits: 3 }) : fmt(v)}</span>;
  }
  if (col.type === 'year') return <span className="tabular-nums">{v}</span>;
  const s = String(v);
  if (col.type === 'id') {
    const ids = col.ref && /\s/.test(s) ? s.split(/\s+/) : [s];
    return (
      <span className="font-mono text-[11px] inline-flex flex-wrap gap-x-1.5">
        {ids.map(id => {
          const h = keyHref && ids.length === 1 ? keyHref : refHref(col.ref, id);
          return h ? <Link key={id} href={h} className="text-indigo-700 hover:underline whitespace-nowrap">{id}</Link> : <span key={id} className="whitespace-nowrap">{id}</span>;
        })}
      </span>
    );
  }
  // a date or number printed in Arabic digits («١٩٩٨», «1423هـ») stays a short left-aligned value
  if (s.length <= 14 && /^[\d\u0660-\u0669\s\-–/.,:؛،()هـمق]+$/.test(s)) return <span className="tabular-nums whitespace-nowrap">{s}</span>;
  const ar = isArabic(s);
  return (
    <div dir={ar ? 'rtl' : 'ltr'} title={s.length > 60 ? s : undefined}
      className={`${ar ? 'ar text-[15px] leading-6' : ''} line-clamp-2 break-words ${s.length > 40 ? 'min-w-[14rem]' : ''} max-w-[30rem]`}>
      {keyHref ? <Link href={keyHref} className="hover:text-indigo-700">{s}</Link> : s}
    </div>
  );
};

export default function Explore() {
  const router = useRouter();
  const view = useMemo(() => readView(router.query), [router.query]);
  const [meta, setMeta] = useState<any>(null);
  const [err, setErr] = useState('');
  const [data, setData] = useState<any>(null);
  const [groups, setGroups] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [panel, setPanel] = useState<'' | 'cols' | 'filter' | 'views'>('');
  const [q, setQ] = useState('');
  const [copied, setCopied] = useState(false);
  useEffect(() => setQ(view.q), [view.q]);

  useEffect(() => { api('/explore').then(setMeta).catch(e => setErr(String(e.message || e))); }, []);
  const ent: Ent | null = meta?.entities?.[view.e] || null;
  // the row counts arrive once the API has built the tables (in the background after a start or a new release)
  useEffect(() => {
    if (data && meta && Object.values(meta.entities as Record<string, Ent>).some(e => e.n == null)) api('/explore').then(setMeta).catch(() => {});
  }, [data]);  // eslint-disable-line react-hooks/exhaustive-deps
  const byName = useMemo(() => Object.fromEntries((ent?.columns || []).map(c => [c.name, c])) as Record<string, Col>, [ent]);
  const cols = useMemo(() => {
    if (!ent) return [];
    const c = (view.c || ent.default).filter(x => byName[x]);
    return c.includes(ent.key) ? c : [ent.key, ...c];
  }, [ent, view.c, byName]);

  const go = (patch: Partial<View>, keepPage = false) => {
    const v = { ...view, ...patch };
    if (!keepPage) v.p = patch.p || 1;
    router.replace({ pathname: '/explore', query: toQuery(v) }, undefined, { shallow: true, scroll: false });
  };

  // rows (or groups)
  const params = ent ? apiParams(view, cols) : '';
  useEffect(() => {
    if (!router.isReady || !ent) return;
    setLoading(true); setErr('');
    const done = () => setLoading(false);
    if (view.g) {
      const p = new URLSearchParams();
      p.set('by', view.g);
      if (view.m) p.set('measure', view.m);
      if (view.q) p.set('q', view.q);
      if (view.f.length) p.set('f', JSON.stringify(view.f));
      api(`/explore/${view.e}/groups?${p}`).then(d => { setGroups(d); }).catch(e => setErr(String(e.message || e))).finally(done);
    } else {
      api(`/explore/${view.e}?${params}&offset=${(view.p - 1) * view.n}&limit=${view.n}`)
        .then(d => setData(d)).catch(e => setErr(String(e.message || e))).finally(done);
    }
  }, [router.isReady, ent, params, view.p, view.n, view.g, view.m, view.e, view.q, view.f]);  // eslint-disable-line react-hooks/exhaustive-deps

  const sortBy = (c: string) => {
    const cur = view.s || ent?.sort[0];
    const curDesc = view.s ? view.d : ent?.sort[1] === 'desc';
    if (cur === c) go({ s: c, d: !curDesc });
    else go({ s: c, d: NUM.has(byName[c]?.type) });
  };
  const sortCol = view.s || ent?.sort[0];
  const sortDesc = view.s ? !!view.d : ent?.sort[1] === 'desc';

  const yearCol = YEAR[view.e];
  const yearF = view.f.find(f => f.c === yearCol && f.op === 'between');
  const setYear = (lo: string, hi: string) => {
    const rest = view.f.filter(f => !(f.c === yearCol && f.op === 'between'));
    go({ f: lo || hi ? [...rest, { c: yearCol, op: 'between', v: [lo || null, hi || null] }] : rest });
  };

  const copyLink = async () => {
    try { await navigator.clipboard.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch { /* no clipboard */ }
  };
  const csvHref = ent ? `/desk/api/explore/${view.e}/csv?${params}` : '#';
  const pages = data ? Math.max(1, Math.ceil(data.total / view.n)) : 1;

  return (
    <Layout wide>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{SX.title}</h1>
          <p className="text-sm text-gray-500">{SX.lead}{meta ? <> · {SX.readFrom} <span className="font-mono text-xs">{meta.release_id || 'the reading'}</span></> : null}</p>
        </div>
        <div className="flex items-center gap-2">
          <Btn small onClick={copyLink} title={SX.savedInUrl}>{copied ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Link2 className="w-3.5 h-3.5" />}{copied ? SX.copied : SX.copyLink}</Btn>
          <a href={csvHref} className="px-2 py-1 text-xs rounded-lg font-medium inline-flex items-center gap-1.5 bg-indigo-600 text-white hover:bg-indigo-700" download data-testid="csv">
            <Download className="w-3.5 h-3.5" />{SX.export}{data && !view.g ? ` (${fmt(data.total)})` : ''}</a>
        </div>
      </div>

      {/* what to explore */}
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="What to explore">
        {ORDER.map(k => {
          const e = meta?.entities?.[k]; const Icon = ICON[k]; const on = view.e === k;
          return (
            <button key={k} role="tab" aria-selected={on} onClick={() => router.replace({ pathname: '/explore', query: { e: k } }, undefined, { shallow: true })}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl border text-sm font-medium shadow-sm ${on ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-gray-200 text-gray-700 hover:border-indigo-300'}`}>
              <Icon className="w-4 h-4" aria-hidden />{e?.label || k}
              {e && <span className={`text-[11px] rounded-full px-1.5 tabular-nums ${on ? 'bg-indigo-500 text-indigo-50' : 'bg-gray-100 text-gray-500'}`}>{e.n != null ? fmt(e.n) : `${e.columns.length} fields`}</span>}
            </button>
          );
        })}
      </div>

      {err && <ErrorBox>{err}</ErrorBox>}
      {!ent ? <Empty>{meta ? SX.loading : SX.firstLoad}</Empty> : (
        <>
          {/* the toolbar */}
          <Card pad={false}>
            <div className="px-4 py-3 flex flex-wrap items-center gap-2">
              <form className="relative" onSubmit={e => { e.preventDefault(); go({ q: q.trim() }); }}>
                <Search className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" aria-hidden />
                <input value={q} onChange={e => setQ(e.target.value)} onBlur={() => q.trim() !== view.q && go({ q: q.trim() })} dir="auto"
                  placeholder={SX.search} aria-label={SX.search} className="pl-8 pr-2 py-1.5 w-72 rounded-lg border-gray-300 text-sm" />
              </form>
              <Btn small onClick={() => setPanel(panel === 'cols' ? '' : 'cols')} aria-expanded={panel === 'cols'} className={panel === 'cols' ? '!border-indigo-300 !bg-indigo-50' : ''}>
                <Columns3 className="w-3.5 h-3.5" />{SX.columns} <span className="text-gray-400 tabular-nums">{cols.length}/{ent.columns.length}</span></Btn>
              <Btn small onClick={() => setPanel(panel === 'filter' ? '' : 'filter')} aria-expanded={panel === 'filter'} className={panel === 'filter' ? '!border-indigo-300 !bg-indigo-50' : ''}>
                <Funnel className="w-3.5 h-3.5" />{SX.addFilter}</Btn>
              {yearCol && byName[yearCol] && (
                <YearRange label={`${byName[yearCol].label}`} lo={yearF?.v?.[0] ?? ''} hi={yearF?.v?.[1] ?? ''} onApply={setYear} />
              )}
              <label className="flex items-center gap-1.5 text-xs text-gray-600">
                <Group className="w-3.5 h-3.5" aria-hidden />
                <select value={view.g || ''} onChange={e => go({ g: e.target.value || null, m: e.target.value ? view.m : null })} className="py-1 pl-2 pr-7 rounded-lg border-gray-300 text-xs w-48" aria-label={SX.groupBy}>
                  <option value="">{SX.noGroup}</option>
                  {groupOptions(ent.columns)}
                </select>
                {view.g && (
                  <select value={view.m || ''} onChange={e => go({ m: e.target.value || null })} className="py-1 pl-2 pr-7 rounded-lg border-gray-300 text-xs w-48" aria-label={SX.measure}>
                    <option value="">{SX.noMeasure}</option>
                    {ent.columns.filter(c => c.type === 'int' || c.type === 'real').map(c => <option key={c.name} value={c.name}>{SX.measure} {c.label}</option>)}
                  </select>
                )}
              </label>
              <div className="relative">
                <Btn small onClick={() => setPanel(panel === 'views' ? '' : 'views')} aria-expanded={panel === 'views'}><Bookmark className="w-3.5 h-3.5" />{SX.views}<ChevronDown className="w-3 h-3" /></Btn>
                {panel === 'views' && (
                  <div className="absolute z-30 mt-1 w-80 bg-white border border-gray-200 rounded-xl shadow-lg py-1">
                    {(PRESETS[view.e] || []).map(p => (
                      <button key={p.label} className="block w-full text-left px-3 py-1.5 text-sm hover:bg-indigo-50"
                        onClick={() => { setPanel(''); go({ c: null, s: null, d: null, q: '', f: [], g: null, m: null, ...p.v }); }}>{p.label}</button>
                    ))}
                    <div className="px-3 pt-1.5 pb-1 text-[11px] text-gray-400 border-t border-gray-100 mt-1">{SX.savedInUrl}</div>
                  </div>
                )}
              </div>
              <button onClick={() => go({ c: null, s: null, d: null, q: '', f: [], g: null, m: null })} className="ml-auto text-xs text-gray-500 hover:text-gray-800 inline-flex items-center gap-1">
                <RotateCcw className="w-3.5 h-3.5" />{SX.reset}</button>
            </div>
            {/* the filters in force */}
            {(view.f.length > 0 || view.q) && (
              <div className="px-4 pb-3 flex flex-wrap gap-1.5" aria-label={SX.filters}>
                {view.q && <FilterChip label={<>“<span dir="auto">{view.q}</span>” anywhere</>} onX={() => go({ q: '' })} />}
                {view.f.map((f, i) => (
                  <FilterChip key={i} label={<><b className="font-medium">{byName[f.c]?.label || f.c}</b> {SX.ops[f.op] || f.op} {fval(f)}</>}
                    onX={() => go({ f: view.f.filter((_, j) => j !== i) })} />
                ))}
              </div>
            )}
            {panel === 'cols' && <ColumnPanel ent={ent} cols={cols} onChange={c => go({ c }, true)} onClose={() => setPanel('')} />}
            {panel === 'filter' && <FilterForm ent={ent} onAdd={f => { setPanel(''); go({ f: [...view.f, f] }); }} onClose={() => setPanel('')} />}
          </Card>

          {view.g ? (
            <GroupTable g={groups && groups.by === view.g && groups.entity === view.e ? groups : null} col={byName[view.g]} measure={view.m ? byName[view.m] : null}
              loading={loading} onPick={v => go({ g: null, m: null, f: [...view.f, v === null ? { c: view.g!, op: 'empty' } : { c: view.g!, op: 'eq', v }] })} />
          ) : (
            <Card pad={false} className="overflow-hidden">
              <div className="overflow-auto max-h-[calc(100vh-17rem)]">
                <table className="w-full text-sm" data-testid="explore-table">
                  <thead className="bg-gray-50 text-xs text-gray-500 sticky top-0 z-10 shadow-[0_1px_0_#e5e7eb]">
                    <tr>{cols.map(c => {
                      const col = byName[c]; const on = sortCol === c; const num = NUM.has(col.type);
                      return (
                        <th key={c} scope="col" className={`px-3 py-2 font-medium whitespace-nowrap ${num ? 'text-right' : 'text-left'}`} aria-sort={on ? (sortDesc ? 'descending' : 'ascending') : 'none'}>
                          <button onClick={() => sortBy(c)} title={`${col.label} · ${SX.where}: ${col.src}`}
                            className={`inline-flex items-center gap-1 hover:text-gray-900 ${on ? 'text-indigo-700' : ''}`}>
                            {col.label}
                            {on ? (sortDesc ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />) : <ArrowUpDown className="w-3 h-3 opacity-30" />}
                          </button>
                        </th>
                      );
                    })}</tr>
                  </thead>
                  <tbody className={loading ? 'opacity-60' : ''}>
                    {data && data.entity === view.e && data.rows.map((r: any[], i: number) => {
                      const idx = Object.fromEntries(data.columns.map((c: string, j: number) => [c, r[j]]));
                      const key = String(idx[ent.key]);
                      const keyHref = refHref(byName[ent.key].ref, key);
                      return (
                        <tr key={key + i} className="border-t border-gray-100 hover:bg-indigo-50/40 align-top">
                          {cols.map(c => (
                            <td key={c} className={`px-3 py-1.5 ${NUM.has(byName[c].type) ? 'text-right' : ''} ${c === ent.key ? 'whitespace-nowrap' : ''}`}>
                              <Cell col={byName[c]} v={idx[c]} keyHref={c === ent.key ? keyHref : null} />
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {data && data.entity === view.e && data.rows.length === 0 && <div className="p-4"><Empty>{SX.empty}</Empty></div>}
                {!data && <div className="p-4"><Empty>{SX.firstLoad}</Empty></div>}
              </div>
              {data && data.entity === view.e && (
                <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 border-t border-gray-100 text-xs text-gray-500">
                  <span className="tabular-nums">
                    {data.total ? `${fmt(data.offset + 1)}–${fmt(Math.min(data.total, data.offset + data.rows.length))}` : '0'} {SX.of} <b className="text-gray-800">{fmt(data.total)}</b> {ent.label.toLowerCase()}
                    {data.total !== data.n_all ? <> (of {fmt(data.n_all)})</> : null} · {data.ms} ms
                  </span>
                  <span className="flex items-center gap-2">
                    <select value={view.n} onChange={e => go({ n: parseInt(e.target.value, 10) })} className="py-0.5 pl-2 pr-7 rounded-md border-gray-300 text-xs" aria-label={SX.perPage}>
                      {SIZES.map(s => <option key={s} value={s}>{s} {SX.perPage}</option>)}
                    </select>
                    <button disabled={view.p <= 1} onClick={() => go({ p: view.p - 1 }, true)} className="p-1 rounded hover:bg-gray-100 disabled:opacity-30" aria-label={SX.prev}><ChevronLeft className="w-4 h-4" /></button>
                    <span className="tabular-nums">{SX.page} <PageBox p={view.p} max={pages} onGo={p => go({ p }, true)} /> {SX.of} {fmt(pages)}</span>
                    <button disabled={view.p >= pages} onClick={() => go({ p: view.p + 1 }, true)} className="p-1 rounded hover:bg-gray-100 disabled:opacity-30" aria-label={SX.next}><ChevronRight className="w-4 h-4" /></button>
                  </span>
                </div>
              )}
            </Card>
          )}
          <p className="text-xs text-gray-400">{ent.about} {SX.savedInUrl}</p>
        </>
      )}
    </Layout>
  );
}

function fval(f: Filter): React.ReactNode {
  if (f.op === 'empty' || f.op === 'not_empty') return null;
  if (f.op === 'between') return <span className="tabular-nums">{f.v?.[0] ?? '…'} – {f.v?.[1] ?? '…'}</span>;
  return <span dir="auto" className="font-medium">{String(f.v ?? '')}</span>;
}

function groupOptions(columns: Col[]) {
  const by: Record<string, Col[]> = {};
  columns.forEach(c => { (by[c.group] = by[c.group] || []).push(c); });
  return Object.entries(by).map(([g, cs]) => (
    <optgroup key={g} label={g}>{cs.map(c => <option key={c.name} value={c.name}>{SX.groupBy} {c.label}</option>)}</optgroup>
  ));
}

const FilterChip: React.FC<{ label: React.ReactNode; onX: () => void }> = ({ label, onX }) => (
  <span className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-full bg-indigo-50 border border-indigo-200 text-xs text-indigo-800">
    {label}<button onClick={onX} className="p-0.5 rounded-full hover:bg-indigo-100" aria-label="Remove this filter"><X className="w-3 h-3" /></button>
  </span>
);

const PageBox: React.FC<{ p: number; max: number; onGo: (p: number) => void }> = ({ p, max, onGo }) => {
  const [v, setV] = useState(String(p));
  useEffect(() => setV(String(p)), [p]);
  return (
    <form className="inline" onSubmit={e => { e.preventDefault(); const x = Math.min(max, Math.max(1, parseInt(v, 10) || 1)); onGo(x); }}>
      <input value={v} onChange={e => setV(e.target.value)} className="w-12 py-0 px-1 text-xs text-center rounded border-gray-300 tabular-nums" aria-label="Page number" />
    </form>
  );
};

const YearRange: React.FC<{ label: string; lo: string; hi: string; onApply: (lo: string, hi: string) => void }> = ({ label, lo, hi, onApply }) => {
  const [a, setA] = useState(String(lo ?? '')); const [b, setB] = useState(String(hi ?? ''));
  useEffect(() => { setA(String(lo ?? '')); setB(String(hi ?? '')); }, [lo, hi]);
  return (
    <form className="flex items-center gap-1 text-xs text-gray-600" onSubmit={e => { e.preventDefault(); onApply(a.trim(), b.trim()); }}>
      <span>{label}</span>
      <input value={a} onChange={e => setA(e.target.value)} placeholder={SX.from} inputMode="numeric" className="w-16 py-1 px-1.5 rounded-lg border-gray-300 text-xs tabular-nums" aria-label={`${label} ${SX.from}`} />
      <span>–</span>
      <input value={b} onChange={e => setB(e.target.value)} placeholder={SX.to} inputMode="numeric" className="w-16 py-1 px-1.5 rounded-lg border-gray-300 text-xs tabular-nums" aria-label={`${label} ${SX.to}`} />
      <button className="px-1.5 py-1 rounded-md border border-gray-200 hover:bg-gray-50">{SX.apply}</button>
    </form>
  );
};

const ColumnPanel: React.FC<{ ent: Ent; cols: string[]; onChange: (c: string[]) => void; onClose: () => void }> = ({ ent, cols, onChange, onClose }) => {
  const [find, setFind] = useState('');
  const by = Object.fromEntries(ent.columns.map(c => [c.name, c])) as Record<string, Col>;
  const groups: Record<string, Col[]> = {};
  const f = find.trim().toLowerCase();
  ent.columns.filter(c => !f || c.label.toLowerCase().includes(f) || c.name.includes(f) || c.src.toLowerCase().includes(f))
    .forEach(c => { (groups[c.group] = groups[c.group] || []).push(c); });
  const toggle = (c: string) => onChange(cols.includes(c) ? cols.filter(x => x !== c || c === ent.key) : [...cols, c]);
  const move = (i: number, d: number) => { const c = [...cols]; const j = i + d; if (j < 0 || j >= c.length) return; [c[i], c[j]] = [c[j], c[i]]; onChange(c); };
  return (
    <div className="border-t border-gray-100 px-4 py-3 grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]" data-testid="column-panel">
      <div>
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <span className="text-xs font-semibold text-gray-700">{SX.allFields} ({ent.columns.length})</span>
          <input value={find} onChange={e => setFind(e.target.value)} placeholder={SX.findField} className="py-1 px-2 rounded-lg border-gray-300 text-xs w-52" />
          <button className="text-xs text-indigo-700 hover:underline" onClick={() => onChange(ent.default)}>{SX.defaults}</button>
          <button className="text-xs text-indigo-700 hover:underline" onClick={() => onChange(ent.columns.map(c => c.name))}>{SX.all}</button>
          <button className="text-xs text-indigo-700 hover:underline" onClick={() => onChange([ent.key])}>{SX.none}</button>
          <button className="ml-auto p-1 rounded hover:bg-gray-100" onClick={onClose} aria-label="Close"><X className="w-4 h-4" /></button>
        </div>
        <div className="columns-1 sm:columns-2 xl:columns-3 gap-6 max-h-[24rem] overflow-auto pr-1">
          {Object.entries(groups).map(([g, cs]) => (
            <div key={g} className="break-inside-avoid mb-3">
              <div className="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-1">{g}</div>
              {cs.map(c => (
                <label key={c.name} className="flex items-start gap-2 py-0.5 text-sm cursor-pointer group" title={`${SX.where}: ${c.src}`}>
                  <input type="checkbox" checked={cols.includes(c.name)} disabled={c.name === ent.key} onChange={() => toggle(c.name)} className="mt-0.5 rounded border-gray-300 text-indigo-600" />
                  <span className="min-w-0"><span className="text-gray-800">{c.label}</span>
                    <span className="block text-[10px] font-mono text-gray-400 truncate group-hover:text-gray-500">{c.src}</span></span>
                </label>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="lg:border-l lg:border-gray-100 lg:pl-4">
        <div className="text-xs font-semibold text-gray-700 mb-2">{SX.shown} ({cols.length})</div>
        <ol className="space-y-0.5 max-h-[24rem] overflow-auto">
          {cols.map((c, i) => (
            <li key={c} className="flex items-center gap-1 text-sm bg-gray-50 border border-gray-100 rounded-md px-2 py-0.5">
              <span className="text-[10px] text-gray-400 w-5 tabular-nums">{i + 1}</span>
              <span className="flex-1 min-w-0 truncate">{by[c]?.label || c}</span>
              <button onClick={() => move(i, -1)} disabled={i === 0} className="p-0.5 rounded hover:bg-gray-200 disabled:opacity-20" aria-label="Move left"><ChevronUp className="w-3.5 h-3.5" /></button>
              <button onClick={() => move(i, 1)} disabled={i === cols.length - 1} className="p-0.5 rounded hover:bg-gray-200 disabled:opacity-20" aria-label="Move right"><ChevronDown className="w-3.5 h-3.5" /></button>
              {c !== ent.key && <button onClick={() => toggle(c)} className="p-0.5 rounded hover:bg-gray-200" aria-label="Hide"><X className="w-3.5 h-3.5" /></button>}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
};

const FilterForm: React.FC<{ ent: Ent; onAdd: (f: Filter) => void; onClose: () => void }> = ({ ent, onAdd, onClose }) => {
  const [c, setC] = useState(ent.default[1] || ent.key);
  const col = ent.columns.find(x => x.name === c) || ent.columns[0];
  const num = NUM.has(col.type) || col.type === 'date';
  const opsFor = num ? ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'between', 'empty', 'not_empty'] : ['contains', 'not_contains', 'eq', 'neq', 'empty', 'not_empty'];
  const [op, setOp] = useState(opsFor[0]);
  const [v, setV] = useState(''); const [v2, setV2] = useState('');
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { if (!opsFor.includes(op)) setOp(opsFor[0]); }, [c]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (op === 'empty' || op === 'not_empty') onAdd({ c, op });
    else if (op === 'between') onAdd({ c, op, v: [v || null, v2 || null] });
    else onAdd({ c, op, v: NUM.has(col.type) && v !== '' ? Number(v) : v });
  };
  return (
    <form onSubmit={submit} className="border-t border-gray-100 px-4 py-3 flex flex-wrap items-center gap-2" data-testid="filter-form">
      <Funnel className="w-4 h-4 text-gray-400" aria-hidden />
      <select value={c} onChange={e => setC(e.target.value)} className="py-1 pl-2 pr-7 rounded-lg border-gray-300 text-sm" aria-label="Field">
        {groupFieldOptions(ent.columns)}
      </select>
      <select value={op} onChange={e => setOp(e.target.value)} className="py-1 pl-2 pr-7 rounded-lg border-gray-300 text-sm" aria-label="Condition">
        {opsFor.map(o => <option key={o} value={o}>{SX.ops[o]}</option>)}
      </select>
      {op !== 'empty' && op !== 'not_empty' && (
        <input ref={ref} value={v} onChange={e => setV(e.target.value)} dir="auto" autoFocus inputMode={num ? 'numeric' : undefined}
          placeholder={op === 'between' ? SX.from : 'value'} className="py-1 px-2 rounded-lg border-gray-300 text-sm w-56" aria-label="Value" />
      )}
      {op === 'between' && <input value={v2} onChange={e => setV2(e.target.value)} placeholder={SX.to} className="py-1 px-2 rounded-lg border-gray-300 text-sm w-28" aria-label="To" />}
      <Btn small kind="primary" type="submit"><Plus className="w-3.5 h-3.5" />{SX.addFilter}</Btn>
      <span className="text-[11px] text-gray-400 font-mono truncate max-w-[22rem]">{SX.where}: {col.src}</span>
      <button type="button" className="ml-auto p-1 rounded hover:bg-gray-100" onClick={onClose} aria-label="Close"><X className="w-4 h-4" /></button>
    </form>
  );
};

function groupFieldOptions(columns: Col[]) {
  const by: Record<string, Col[]> = {};
  columns.forEach(c => { (by[c.group] = by[c.group] || []).push(c); });
  return Object.entries(by).map(([g, cs]) => (
    <optgroup key={g} label={g}>{cs.map(c => <option key={c.name} value={c.name}>{c.label}</option>)}</optgroup>
  ));
}

const GroupTable: React.FC<{ g: any; col: Col; measure: Col | null; loading: boolean; onPick: (v: any) => void }> = ({ g, col, measure, loading, onPick }) => {
  if (!g) return <Empty>{SX.loading}</Empty>;
  const max = Math.max(1, ...g.groups.map((x: any) => x.n));
  return (
    <Card title={<>{SX.groupBy} {col?.label} <span className="text-sm font-normal text-gray-500">· {fmt(g.n_groups)} {SX.groups} · {fmt(g.total)} {SX.rows} · {g.ms} ms</span></>}
      right={<span className="text-xs text-gray-400">{SX.clickGroup}</span>} pad={false}>
      <div className={`overflow-auto max-h-[calc(100vh-19rem)] ${loading ? 'opacity-60' : ''}`}>
        <table className="w-full text-sm" data-testid="group-table">
          <thead className="bg-gray-50 text-xs text-gray-500 sticky top-0"><tr>
            <th className="px-4 py-2 text-left font-medium">{SX.value}</th>
            <th className="px-3 py-2 text-right font-medium w-24">{SX.count}</th>
            <th className="px-3 py-2 text-left font-medium w-[28%]">{SX.share}</th>
            {measure && <th className="px-3 py-2 text-right font-medium w-32">{SX.sum}: {measure.label}</th>}
          </tr></thead>
          <tbody>{g.groups.map((x: any, i: number) => {
            const s = x.value === null ? null : String(x.value); const ar = isArabic(s);
            return (
              <tr key={i} className="border-t border-gray-100 hover:bg-indigo-50/40 cursor-pointer" onClick={() => onPick(x.value)}>
                <td className="px-4 py-1.5">{s === null ? <span className="text-gray-400 italic">{SX.emptyValue}</span>
                  : <span dir={ar ? 'rtl' : 'ltr'} className={ar ? 'ar inline-block text-[15px]' : ''}>{s}</span>}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{fmt(x.n)}</td>
                <td className="px-3 py-1.5"><div className="h-2 rounded-full bg-gray-100 overflow-hidden"><div className="h-2 bg-indigo-500 rounded-full" style={{ width: `${(100 * x.n) / max}%` }} /></div></td>
                {measure && <td className="px-3 py-1.5 text-right tabular-nums">{fmt(x.sum)}</td>}
              </tr>
            );
          })}</tbody>
        </table>
      </div>
    </Card>
  );
};
