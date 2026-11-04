import React, { useMemo, useState } from 'react';
import { Check, Search } from 'lucide-react';
import { Card, Chip, Crop, Empty, ErrorBox, T, n } from './Bits';
import { cropOfAnchor, cropOfBlock, enc, isArabic } from '../lib/api';
import { useApi } from '../lib/me';

// The Article page's "All fields" tab (2026-10-23): every field the platform holds for the article, each with its
// value, where it came from (the page, the catalogue, a correction, or counted by our code) and its ink crop when
// the reading has one. Grouped by section or by source; ordered as in the inventory, A–Z, or by source.
const SOURCES: Record<string, { label: string; tone: 'indigo' | 'amber' | 'green' | 'gray'; hint: string }> = {
  page: { label: 'page', tone: 'indigo', hint: 'read from the scanned page' },
  catalogue: { label: 'catalogue', tone: 'amber', hint: "Mandumah's catalogue record" },
  corrected: { label: 'corrected', tone: 'green', hint: 'changed by a rule or a person' },
  derived: { label: 'derived', tone: 'gray', hint: 'counted or computed by our code' },
};
const SRC_ORDER = ['page', 'catalogue', 'corrected', 'derived'];

const InkCell: React.FC<{ f: any; stem: string }> = ({ f, stem }) => {
  const [big, setBig] = useState(false);
  const src = f.anchor ? cropOfAnchor(f.anchor) : f.block && f.page ? cropOfBlock(stem, f.page, f.block) : null;
  if (!src) return <span className="text-xs text-gray-300">—</span>;
  return (
    <button onClick={() => setBig(!big)} className="block text-left w-full" title={big ? 'Smaller' : 'Larger'} data-field-ink={f.id}>
      <Crop src={src} maxH={big ? 'max-h-[28rem]' : 'max-h-14'} rtl={isArabic(f.value)} />
    </button>
  );
};

const Value: React.FC<{ v: string }> = ({ v }) => {
  const [open, setOpen] = useState(false);
  const long = v.length > 260;
  return (
    <div>
      <T as="div" text={open || !long ? v : v.slice(0, 240) + '…'} className="text-sm text-gray-900 leading-6 break-words" />
      {long && <button onClick={() => setOpen(!open)} className="text-xs text-indigo-600 hover:underline">{open ? 'Less' : 'More'}</button>}
    </div>
  );
};

const AllFields: React.FC<{ stem: string }> = ({ stem }) => {
  const { data: d, err } = useApi<any>(`/articles/${enc(stem)}/fields`);
  const [groupBy, setGroupBy] = useState<'section' | 'source'>('section');
  const [order, setOrder] = useState<'inventory' | 'az' | 'source'>('inventory');
  const [q, setQ] = useState('');
  const [inkOnly, setInkOnly] = useState(false);
  const [srcs, setSrcs] = useState<Set<string>>(new Set(SRC_ORDER));

  const shown = useMemo(() => {
    if (!d) return [];
    const ql = q.trim().toLowerCase();
    let xs = d.fields.filter((f: any) => srcs.has(f.source) && (!inkOnly || f.anchor || f.block)
      && (!ql || `${f.label} ${f.value} ${f.wos || ''} ${f.by || ''}`.toLowerCase().includes(ql)));
    const by = order === 'az' ? (x: any, y: any) => x.label.localeCompare(y.label, 'en', { numeric: true }) || x.ord - y.ord
      : order === 'source' ? (x: any, y: any) => SRC_ORDER.indexOf(x.source) - SRC_ORDER.indexOf(y.source) || x.ord - y.ord
        : (x: any, y: any) => x.ord - y.ord;
    xs = [...xs].sort(by);
    return xs;
  }, [d, q, inkOnly, srcs, order]);

  if (err) return <ErrorBox>{err}</ErrorBox>;
  if (!d) return <Empty>Loading every field…</Empty>;
  const groups: [string, string, any[]][] = groupBy === 'section'
    ? d.groups.map((g: any) => [g.id, g.title, shown.filter((f: any) => f.group === g.id)])
    : SRC_ORDER.map(s => [s, `From the ${SOURCES[s].label === 'derived' ? 'code (derived)' : SOURCES[s].label}`, shown.filter((f: any) => f.source === s)]);
  const toggle = (s: string) => setSrcs(old => { const x = new Set(old); x.has(s) ? x.delete(s) : x.add(s); return x.size ? x : new Set(SRC_ORDER); });
  const seg = (val: string, cur: string, set: (v: any) => void, label: string) => (
    <button key={val} onClick={() => set(val)} aria-pressed={cur === val} className={`px-2.5 py-1 ${cur === val ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-50'}`}>{label}</button>);
  return (
    <div className="space-y-4" data-testid="all-fields">
      <Card>
        <div className="pt-4 space-y-3">
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <p className="text-2xl font-semibold text-gray-900 tabular-nums">{n(d.counts.fields)} <span className="text-sm font-normal text-gray-500">fields held for this article</span></p>
            <p className="text-sm text-gray-600 tabular-nums">{n(d.counts.with_ink)} with their ink on the page</p>
            <div className="flex flex-wrap gap-1.5 text-xs" aria-label="Sources">
              {SRC_ORDER.map(s => (
                <button key={s} onClick={() => toggle(s)} aria-pressed={srcs.has(s)} title={SOURCES[s].hint} className={`rounded-md border px-2 py-0.5 ${srcs.has(s) ? 'bg-white border-gray-300 text-gray-800' : 'bg-gray-50 border-gray-200 text-gray-400 line-through'}`}>
                  <Chip tone={SOURCES[s].tone}>{SOURCES[s].label}</Chip> <span className="tabular-nums">{n(d.counts[`source_${s}`] || 0)}</span>
                </button>))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label className="relative">
              <span className="sr-only">Filter fields</span>
              <Search className="w-4 h-4 text-gray-400 absolute left-2.5 top-2" aria-hidden />
              <input value={q} onChange={e => setQ(e.target.value)} placeholder="Filter: field, value, WoS tag…" dir="auto" className="pl-8 pr-2 py-1 w-64 rounded-lg border-gray-300 text-sm" data-testid="fields-filter" />
            </label>
            <span className="text-gray-500 text-xs">Group by</span>
            <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden text-xs">{seg('section', groupBy, setGroupBy, 'Section')}{seg('source', groupBy, setGroupBy, 'Source')}</div>
            <span className="text-gray-500 text-xs">Order</span>
            <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden text-xs">{seg('inventory', order, setOrder, 'As read')}{seg('az', order, setOrder, 'A–Z')}{seg('source', order, setOrder, 'By source')}</div>
            <label className="inline-flex items-center gap-1.5 text-xs text-gray-600"><input type="checkbox" checked={inkOnly} onChange={e => setInkOnly(e.target.checked)} className="rounded border-gray-300" />Only fields with ink</label>
            <span className="ms-auto text-xs text-gray-400">{n(shown.length)} shown</span>
          </div>
        </div>
      </Card>
      {groups.filter(([, , xs]) => xs.length).map(([id, title, xs]) => (
        <Card key={id} pad={false} title={<span>{title} <span className="text-sm font-normal text-gray-400 tabular-nums">{xs.length}</span></span>}>
          <table className="w-full text-sm table-fixed" data-group={id}>
            <colgroup><col className="w-[15rem]" /><col /><col className="w-[9.5rem]" /><col className="w-[18rem]" /></colgroup>
            <thead className="bg-gray-50 text-xs text-gray-500"><tr>
              <th className="px-4 py-1.5 text-left font-medium">Field</th><th className="px-2 py-1.5 text-left font-medium">Value</th>
              <th className="px-2 py-1.5 text-left font-medium">From</th><th className="px-2 py-1.5 text-left font-medium">Ink on the page</th></tr></thead>
            <tbody>{xs.map((f: any) => (
              <tr key={f.id} className={`border-t border-gray-100 align-top ${f.chosen === false ? 'text-gray-500' : ''}`} data-field={f.key} data-source={f.source}>
                <td className="px-4 py-2">
                  <div className="text-gray-800 font-medium leading-5">{f.label}</div>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {f.wos && <span className="text-[10px] font-mono text-gray-500 border border-gray-200 rounded px-1" title="Web of Science field tag">{f.wos}</span>}
                    {f.chosen && <span className="inline-flex items-center gap-0.5 text-[10px] text-green-700" title="the value the platform shows"><Check className="w-3 h-3" />shown</span>}
                    {f.chosen === false && <span className="text-[10px] text-gray-400">another reading</span>}
                  </div>
                </td>
                <td className="px-2 py-2 min-w-0"><Value v={f.value} />{f.note && <p className="text-xs text-gray-400 mt-0.5 break-words">{f.note}</p>}</td>
                <td className="px-2 py-2"><span title={SOURCES[f.source]?.hint}><Chip tone={SOURCES[f.source]?.tone || 'gray'}>{SOURCES[f.source]?.label || f.source}</Chip></span>
                  {f.by && <div className="text-[11px] text-gray-400 mt-0.5 break-all">{String(f.by).replace(/^(model|catalogue|rule|person|agent):/, '')}</div>}
                  {f.page && <div className="text-[11px] text-gray-400">page {f.page}</div>}</td>
                <td className="px-2 py-2"><InkCell f={f} stem={stem} /></td>
              </tr>))}
            </tbody>
          </table>
        </Card>))}
      {!shown.length && <Empty>No field matches.</Empty>}
    </div>
  );
};
export default AllFields;
