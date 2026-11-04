import React from 'react';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

// Small visual pieces of the Story page (experiment 73, 2026-11-03). Every number arrives from
// GET /desk/api/headlines; a missing value is shown as "—", never invented.

export const missing = (v: any) => v === null || v === undefined || v === '' || (typeof v === 'number' && !isFinite(v));
export function num(v: any, digits = 1): string {
  if (missing(v)) return '—';
  const x = Number(v);
  if (!isFinite(x)) return String(v);
  return x.toLocaleString('en-US', { maximumFractionDigits: digits });
}
export const usd = (v: any, digits = 2) => (missing(v) ? '—' : `$${num(v, digits)}`);
export const pct = (v: any, digits = 2) => (missing(v) ? '—' : `${num(v, digits)}%`);
export const at = (a: any, i: number) => (Array.isArray(a) ? a[i] : undefined);

// the stagger of an element inside a step: style={d(2)} = the third thing to appear
export const d = (i: number): React.CSSProperties => ({ ['--d' as any]: `${120 + i * 140}ms` });

export const Eyebrow: React.FC<{ n: number; children: React.ReactNode }> = ({ n, children }) => (
  <div className="st-in flex items-center gap-2 text-sm font-semibold tracking-wide uppercase text-teal-700" style={d(0)}>
    <span className="w-6 h-6 rounded-full bg-teal-600 text-white grid place-items-center text-xs">{n}</span>{children}
  </div>);

export const Headline: React.FC<{ children: React.ReactNode; sub?: React.ReactNode; action?: React.ReactNode }> = ({ children, sub, action }) => (
  <div className="flex items-end justify-between gap-10">
    <div className="max-w-5xl min-w-0">
      <h2 className="st-in text-[2.35rem] leading-[1.15] font-semibold text-gray-900 tracking-tight mt-3 [text-wrap:balance]" style={d(1)}>{children}</h2>
      {sub && <p className="st-in text-lg text-gray-600 mt-2.5 max-w-4xl leading-relaxed [text-wrap:pretty]" style={d(2)}>{sub}</p>}
    </div>
    {action && <div className="shrink-0 flex flex-col items-end gap-2 pb-1">{action}</div>}
  </div>);

export const Panel: React.FC<{ title?: React.ReactNode; children: React.ReactNode; i?: number; className?: string; foot?: React.ReactNode }> = ({ title, children, i = 3, className = '', foot }) => (
  <section className={`st-in rounded-2xl border border-gray-200 bg-white shadow-sm shadow-gray-900/[0.03] p-6 flex flex-col ${className}`} style={d(i)}>
    {title && <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">{title}</h3>}
    <div className="flex-1">{children}</div>
    {foot && <p className="text-xs text-gray-400 mt-4 leading-relaxed">{foot}</p>}
  </section>);

export const Big: React.FC<{ value: React.ReactNode; label: React.ReactNode; tone?: 'teal' | 'indigo' | 'green' | 'gray'; size?: 'lg' | 'xl' }> = ({ value, label, tone = 'teal', size = 'lg' }) => {
  const c = { teal: 'text-teal-700', indigo: 'text-indigo-700', green: 'text-green-700', gray: 'text-gray-800' }[tone];
  return (
    <div>
      <div className={`${size === 'xl' ? 'text-6xl' : 'text-4xl'} font-semibold tabular-nums tracking-tight ${c}`}>{value}</div>
      <div className="text-sm text-gray-600 mt-1.5 leading-snug">{label}</div>
    </div>);
};

export const LiveButton: React.FC<{ href: string; children: React.ReactNode; quiet?: boolean; i?: number }> = ({ href, children, quiet, i = 6 }) => (
  <Link href={href} data-testid="live" style={d(i)}
    className={`st-in inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium transition-colors ${quiet ? 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50' : 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm'}`}>
    {children}<ArrowRight className="w-4 h-4" aria-hidden />
  </Link>);

// a picture of a live screen, linked to it (the Desk refuses to be framed, so the preview is a still taken from it)
export const Shot: React.FC<{ src: string; href: string; alt: string; caption?: string; i?: number; className?: string; h?: number }> = ({ src, href, alt, caption, i = 3, className = '', h }) => (
  <Link href={href} className={`st-in group block rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden hover:shadow-md hover:border-indigo-200 transition ${className}`} style={d(i)}>
    <div className="flex items-center gap-1.5 px-3 py-2 border-b border-gray-100 bg-gray-50">
      <span className="w-2.5 h-2.5 rounded-full bg-gray-200" /><span className="w-2.5 h-2.5 rounded-full bg-gray-200" /><span className="w-2.5 h-2.5 rounded-full bg-gray-200" />
      {caption && <span className="ml-2 text-xs text-gray-500 truncate">{caption}</span>}
      <span className="ml-auto text-xs text-indigo-700 opacity-0 group-hover:opacity-100 transition-opacity">open live →</span>
    </div>
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src={src} alt={alt} className="w-full object-cover object-top block" style={h ? { height: h } : undefined} />
  </Link>);

// two bars for one measure: what the two journals read whole show, against the same thing in random articles
export const Compare: React.FC<{ label: string; a: any; b: any; aLabel: string; bLabel: string; i?: number; note?: string }> = ({ label, a, b, aLabel, bLabel, i = 0, note }) => {
  const max = Math.max(Number(a) || 0, Number(b) || 0, 1);
  const w = (v: any) => (missing(v) ? 0 : Math.max(0.6, (Number(v) / max) * 100));
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 mb-2">
        <div className="text-base font-medium text-gray-900">{label}</div>
        {note && <div className="text-xs text-gray-400">{note}</div>}
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_4.5rem] items-center gap-x-3 gap-y-1.5">
        <div className="h-7 rounded-md bg-gray-50 overflow-hidden" title={aLabel}>
          <div className="st-bar h-full rounded-md bg-teal-500" style={{ width: `${w(a)}%`, ['--d' as any]: `${400 + i * 180}ms` }} />
        </div>
        <div className="text-xl font-semibold tabular-nums text-teal-700">{num(a)}</div>
        <div className="h-7 rounded-md bg-gray-50 overflow-hidden" title={bLabel}>
          <div className="st-bar h-full rounded-md bg-gray-300" style={{ width: `${w(b)}%`, ['--d' as any]: `${480 + i * 180}ms` }} />
        </div>
        <div className="text-xl font-semibold tabular-nums text-gray-500">{num(b)}</div>
      </div>
    </div>);
};

export const Legend: React.FC<{ items: [string, string][] }> = ({ items }) => (
  <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-600">
    {items.map(([c, l]) => <span key={l} className="inline-flex items-center gap-2"><span className={`w-3 h-3 rounded-sm ${c}`} />{l}</span>)}
  </div>);

// before → after, for the librarian: the same records, fewer cards once the duplicates are joined
export const BeforeAfter: React.FC<{ label: string; before: any; after: any; i?: number; unit: string }> = ({ label, before, after, i = 0, unit }) => {
  const max = Math.max(Number(before) || 0, Number(after) || 0, 1);
  const w = (v: any) => (missing(v) ? 0 : (Number(v) / max) * 100);
  const gone = !missing(before) && !missing(after) ? Number(before) - Number(after) : null;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-base font-medium text-gray-900">{label}</div>
        {gone !== null && <div className="text-sm text-teal-700 font-medium">{num(gone, 0)} duplicates joined</div>}
      </div>
      <div className="grid grid-cols-[4.5rem_minmax(0,1fr)_5rem] items-center gap-x-3 gap-y-1.5 text-sm">
        <div className="text-gray-500">before</div>
        <div className="h-6 rounded-md bg-gray-50 overflow-hidden"><div className="st-bar h-full rounded-md bg-gray-300" style={{ width: `${w(before)}%`, ['--d' as any]: `${400 + i * 200}ms` }} /></div>
        <div className="text-lg font-semibold tabular-nums text-gray-500">{num(before, 0)}</div>
        <div className="text-gray-700">after</div>
        <div className="h-6 rounded-md bg-gray-50 overflow-hidden"><div className="st-bar h-full rounded-md bg-teal-500" style={{ width: `${w(after)}%`, ['--d' as any]: `${520 + i * 200}ms` }} /></div>
        <div className="text-lg font-semibold tabular-nums text-teal-700">{num(after, 0)}</div>
      </div>
      <div className="text-xs text-gray-400 mt-1">{unit}</div>
    </div>);
};

// every checked word as one small square: all green when none was wrong
export const WordGrid: React.FC<{ of: any; wrong: any }> = ({ of, wrong }) => {
  const total = Number(of);
  if (!isFinite(total) || total <= 0) return <div className="h-40 grid place-items-center text-gray-400">—</div>;
  const bad = Math.max(0, Math.min(total, Number(wrong) || 0));
  const cols = 64, cell = 9, gap = 3;
  const rows = Math.ceil(total / cols);
  const W = cols * (cell + gap) - gap, H = rows * (cell + gap) - gap;
  const rects: React.ReactNode[] = [];
  for (let r = 0; r < rows; r++) {
    const cells: React.ReactNode[] = [];
    for (let c = 0; c < cols; c++) {
      const k = r * cols + c;
      if (k >= total) break;
      cells.push(<rect key={c} x={c * (cell + gap)} y={r * (cell + gap)} width={cell} height={cell} rx={2}
        fill={k >= total - bad ? '#dc2626' : '#14b8a6'} />);
    }
    rects.push(<g key={r} className="st-fade" style={{ ['--d' as any]: `${300 + r * 45}ms` }}>{cells}</g>);
  }
  return <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label={`${num(total, 0)} words checked, ${num(bad, 0)} wrong`}>{rects}</svg>;
};

// two journals and the citations that run between them, one arc each way; the country in the circle, the name below
export const Bridge: React.FC<{ a: { name: string; sub: string }; b: { name: string; sub: string }; ab: any; ba: any }> = ({ a, b, ab, ba }) => {
  const W = 640, H = 360, ax = 140, bx = 500, cy = 165, r = 50;
  const arc = (from: number, to: number, up: boolean) => {
    const y = up ? cy - 26 : cy + 26, ctrl = up ? cy - 150 : cy + 150;
    return `M ${from} ${y} C ${from + (to - from) * 0.3} ${ctrl}, ${from + (to - from) * 0.7} ${ctrl}, ${to} ${y}`;
  };
  const pill = (x: number, y: number, t: string, sub: string) => (
    <g>
      <rect x={x - 78} y={y - 22} width={156} height={44} rx={22} fill="white" stroke="#99f6e4" />
      <text x={x} y={y - 2} textAnchor="middle" fontSize="18" fontWeight={600} fill="#0f766e">{t}</text>
      <text x={x} y={y + 14} textAnchor="middle" fontSize="11" fill="#6b7280">{sub}</text>
    </g>);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label={`${a.sub} cites ${b.sub} ${num(ab)} times; ${b.sub} cites ${a.sub} ${num(ba)} times`}>
      <defs>
        <marker id="st-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="#14b8a6" />
        </marker>
      </defs>
      <path d={arc(ax + 30, bx - 30, true)} fill="none" stroke="#14b8a6" strokeWidth={3} markerEnd="url(#st-arrow)" className="st-draw" pathLength={1} style={{ ['--d' as any]: '500ms' }} />
      <path d={arc(bx - 30, ax + 30, false)} fill="none" stroke="#14b8a6" strokeWidth={3} markerEnd="url(#st-arrow)" className="st-draw" pathLength={1} style={{ ['--d' as any]: '900ms' }} />
      <g className="st-fade" style={{ ['--d' as any]: '1100ms' }}>{pill(W / 2, cy - 112, `${num(ab)} citations`, `${a.sub} → ${b.sub}`)}</g>
      <g className="st-fade" style={{ ['--d' as any]: '1400ms' }}>{pill(W / 2, cy + 112, `${num(ba)} citations`, `${b.sub} → ${a.sub}`)}</g>
      {[[ax, a], [bx, b]].map(([x, j]: any, k) => (
        <g key={k} className="st-fade" style={{ ['--d' as any]: `${200 + k * 120}ms` }}>
          <circle cx={x} cy={cy} r={r} fill={k ? '#eef2ff' : '#f0fdfa'} stroke={k ? '#818cf8' : '#2dd4bf'} strokeWidth={2} />
          <text x={x} y={cy + 6} textAnchor="middle" fontSize="17" fontWeight={600} fill={k ? '#3730a3' : '#115e59'}>{j.sub}</text>
          <text x={x} y={cy + r + 26} textAnchor="middle" fontSize="15" fill="#374151" className="ar-inline" direction="rtl">{j.name}</text>
        </g>))}
    </svg>);
};

export const STORY_CSS = `
.st-in, .st-fade, .st-bar, .st-draw { animation-duration: .7s; animation-delay: var(--d, 0ms); animation-fill-mode: both; animation-timing-function: cubic-bezier(.22,.7,.2,1); }
.st-in { animation-name: st-in; }
.st-fade { animation-name: st-fade; }
.st-bar { animation-name: st-bar; animation-duration: 1s; transform-origin: left center; }
.st-draw { stroke-dasharray: 1; animation-name: st-draw; animation-duration: 1.1s; }
.st-stage { animation: st-stage .5s cubic-bezier(.22,.7,.2,1) both; }
@keyframes st-in { from { opacity: 0; transform: translateY(14px); } }
@keyframes st-fade { from { opacity: 0; } }
@keyframes st-bar { from { transform: scaleX(0); } }
@keyframes st-draw { from { stroke-dashoffset: 1; } to { stroke-dashoffset: 0; } }
@keyframes st-stage { from { opacity: 0; transform: translateX(var(--dx, 0px)); } }
.st-pulse { animation: st-pulse 2.4s ease-in-out infinite; }
@keyframes st-pulse { 50% { opacity: .55; } }
@media (prefers-reduced-motion: reduce) { .st-in, .st-fade, .st-bar, .st-draw, .st-stage { animation: none !important; } }
`;
