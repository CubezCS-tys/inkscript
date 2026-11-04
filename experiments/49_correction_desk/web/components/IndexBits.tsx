import React, { useState } from 'react';
import Link from 'next/link';
import { Info } from 'lucide-react';
import { T, n } from './Bits';

// The index pages' parts (2026-10-23): a number with its definition on hover, simple SVG bar charts, small tables.

// A definition that shows on hover or focus (and as the native title, for screen readers and touch).
export const Def: React.FC<{ text?: string; children?: React.ReactNode; className?: string }> = ({ text, children, className = '' }) => {
  const [open, setOpen] = useState(false);
  if (!text) return <>{children}</>;
  return (
    <span className={`relative inline-flex items-center gap-1 ${className}`} onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      {children}
      <button type="button" aria-label={`How this is defined: ${text}`} title={text} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        className="text-gray-400 hover:text-indigo-600 focus:text-indigo-600"><Info className="w-3.5 h-3.5" aria-hidden /></button>
      {open && (
        <span role="tooltip" className="absolute z-30 left-0 top-full mt-1 w-72 text-left text-xs font-normal leading-snug text-gray-700 bg-white border border-gray-200 rounded-lg shadow-lg p-2.5 normal-case tracking-normal whitespace-normal">
          {text}
        </span>
      )}
    </span>
  );
};

export const fmtNum = (v: any, unit?: string) => (v == null ? '—' : unit === '%' ? `${v}%` : typeof v === 'number' ? n(v) : String(v));
export const pct = (x?: number | null, d = 1) => (x == null ? '—' : `${(100 * x).toFixed(d)}%`);

// A headline number: label, value, a line under it, and its definition on hover.
export const Metric: React.FC<{ label: string; value: any; unit?: string; sub?: React.ReactNode; define?: string; href?: string; big?: boolean; testid?: string }> =
  ({ label, value, unit, sub, define, href, big, testid }) => {
    const inner = (
      <>
        <div className="text-xs text-gray-500"><Def text={define}>{label}</Def></div>
        <div className={`${big ? 'text-3xl' : 'text-2xl'} font-semibold text-gray-900 tabular-nums mt-1`} data-testid={testid}>{fmtNum(value, unit)}</div>
        {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
      </>
    );
    const cls = 'bg-white rounded-xl border border-gray-200 shadow-sm p-4 min-w-0';
    return href ? <div className={`${cls} hover:border-indigo-300`}>{inner}<Link href={href} className="text-xs text-indigo-700 hover:underline">Open →</Link></div>
      : <div className={cls}>{inner}</div>;
  };

// Vertical bars by year (one series), drawn in HTML so bars and labels keep their size at any width. Hover a bar
// for its value; years without data are left as gaps on the axis.
export const YearBars: React.FC<{ data: { year: number; value: number }[]; label: string; color?: string; height?: number; unit?: string }> =
  ({ data, label, color = '#4f46e5', height = 120, unit = '' }) => {
    const [hover, setHover] = useState<number | null>(null);
    if (!data.length) return <p className="text-sm text-gray-500">—</p>;
    const y0 = Math.min(...data.map(d => d.year)), y1 = Math.max(...data.map(d => d.year));
    const years = Array.from({ length: y1 - y0 + 1 }, (_, i) => y0 + i);
    const by = new Map(data.map(d => [d.year, d.value]));
    const max = Math.max(1, ...data.map(d => d.value));
    const every = years.length > 24 ? 5 : years.length > 12 ? 2 : 1;
    return (
      <figure className="w-full" role="img" aria-label={`${label}: ${data.map(d => `${d.year} ${d.value}${unit}`).join(', ')}`}>
        <div className="flex items-end gap-[2px] border-b border-gray-200" style={{ height }}>
          {years.map(yr => {
            const v = by.get(yr) || 0;
            return (
              <div key={yr} className="flex-1 h-full flex flex-col justify-end items-center min-w-0 max-w-[2.5rem] relative"
                onMouseEnter={() => setHover(yr)} onMouseLeave={() => setHover(null)} title={`${yr}: ${v}${unit}`}>
                {hover === yr && <span className="absolute -top-1 -translate-y-full text-[11px] font-semibold text-gray-900 bg-white border border-gray-200 rounded px-1 shadow-sm z-10 whitespace-nowrap">{yr}: {v}{unit}</span>}
                {v > 0 && <div className="w-full rounded-t" style={{ height: `${(100 * v) / max}%`, background: color, opacity: hover == null || hover === yr ? 1 : 0.5 }} />}
              </div>
            );
          })}
        </div>
        <div className="flex gap-[2px] mt-1">
          {years.map((yr, i) => <span key={yr} className="flex-1 min-w-0 max-w-[2.5rem] text-center text-[10px] text-gray-500 tabular-nums">{(i % every === 0 || (yr === y1 && i % every >= Math.ceil(every / 2))) ? yr : ''}</span>)}
        </div>
        <figcaption className="text-xs text-gray-500 mt-1">{label}</figcaption>
      </figure>
    );
  };

// One horizontal bar (for ranked lists), the value as text beside it.
export const Bar: React.FC<{ value: number; max: number; color?: string }> = ({ value, max, color = '#6366f1' }) => (
  <span className="inline-block align-middle h-2 rounded-full bg-gray-100 w-24 overflow-hidden" aria-hidden>
    <span className="block h-2 rounded-full" style={{ width: `${Math.max(2, (100 * value) / Math.max(1, max))}%`, background: color }} />
  </span>
);

// A ranked list: label (link), a bar and the count.
export const Ranked: React.FC<{ rows: { key: string; href?: string; label?: string | null; sub?: React.ReactNode; value: number }[]; unit?: string; empty?: string }> =
  ({ rows, unit = '', empty = '—' }) => {
    if (!rows.length) return <p className="text-sm text-gray-500">{empty}</p>;
    const max = Math.max(...rows.map(r => r.value));
    return (
      <ul className="divide-y divide-gray-100 text-sm">
        {rows.map(r => (
          <li key={r.key} className="py-1.5 flex items-center gap-3">
            <span className="flex-1 min-w-0">
              {r.href ? <Link href={r.href} className="text-gray-900 hover:text-indigo-700"><T text={r.label} /></Link> : <T text={r.label} />}
              {r.sub && <span className="block text-xs text-gray-400 truncate">{r.sub}</span>}
            </span>
            <Bar value={r.value} max={max} />
            <span className="w-14 text-right tabular-nums font-medium text-gray-800">{n(r.value)}{unit}</span>
          </li>
        ))}
      </ul>
    );
  };

export const SmallNote: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <p className="text-xs text-gray-500 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">{children}</p>
);

export const pubHref = (p: { stem?: string | null }) => (p.stem ? `/articles/${encodeURIComponent(p.stem)}` : undefined);
// A country code -> its English name ('EG' -> 'Egypt'); unknown codes are shown as they are.
let _regions: any = null;
export const countryName = (c?: string | null): string => {
  if (!c) return '—';
  if (c.length !== 2) return c;
  try {
    if (!_regions) _regions = new (Intl as any).DisplayNames(['en'], { type: 'region' });
    return _regions.of(c.toUpperCase()) || c;
  } catch { return c; }
};
export const country = (c?: string | null) => countryName(c);

// The journals read whole (gate 1, gate 2's pilot): never a random sample (experiment 73, M3).
export const WHOLE: Record<string, string> = { J0130: 'read whole · gate 1', J0165: 'read whole · gate 2 pilot' };
