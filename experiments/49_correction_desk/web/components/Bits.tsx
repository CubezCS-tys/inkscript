import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle, ImageOff } from 'lucide-react';
import { isArabic } from '../lib/api';
import { S } from '../lib/strings';

// The parts of AI-Search's admin dashboard (OpsBits.tsx), redrawn for the Desk: Card, Tile, StatusPill, Empty, Chip.
export const C = { good: '#0ca30c', warning: '#fab219', critical: '#d03b3b', unknown: '#9ca3af' };
export type Light = 'good' | 'warning' | 'critical' | 'unknown';
const ICON = { good: CheckCircle2, warning: AlertTriangle, critical: XCircle, unknown: HelpCircle };

export const StatusPill: React.FC<{ light: Light; label?: React.ReactNode }> = ({ light, label }) => {
  const Icon = ICON[light];
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-700">
      <Icon className="w-4 h-4" style={{ color: C[light] }} aria-hidden />{label}
    </span>
  );
};

export const Card: React.FC<{ title?: React.ReactNode; right?: React.ReactNode; className?: string; pad?: boolean; children: React.ReactNode; id?: string }> =
  ({ title, right, className = '', pad = true, children, id }) => (
    <section id={id} className={`bg-white rounded-xl border border-gray-200 shadow-sm ${className}`}>
      {(title || right) && (
        <div className="flex flex-wrap items-center justify-between gap-2 px-5 pt-4 pb-2">
          {title && <h2 className="font-semibold text-gray-800">{title}</h2>}
          {right}
        </div>
      )}
      <div className={pad ? 'px-5 pb-4' : ''}>{children}</div>
    </section>
  );

export const Tile: React.FC<{ label: string; value: React.ReactNode; sub?: React.ReactNode; light?: Light; href?: string }> =
  ({ label, value, sub, light, href }) => {
    const inner = (
      <>
        <div className="text-xs text-gray-500 flex items-center justify-between gap-2">
          <span>{label}</span>{light && <StatusPill light={light} />}
        </div>
        <div className="text-2xl font-semibold text-gray-900 tabular-nums mt-1 truncate">{value}</div>
        {sub && <div className="text-xs text-gray-500 mt-0.5 truncate">{sub}</div>}
      </>
    );
    return href
      ? <a href={href} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 min-w-0 hover:border-indigo-300 block">{inner}</a>
      : <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 min-w-0">{inner}</div>;
  };

export const Empty: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="text-sm text-gray-500 bg-gray-50 border border-dashed border-gray-200 rounded-lg px-4 py-3">{children}</div>
);

export const ErrorBox: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div role="alert" className="text-sm text-red-800 bg-red-50 border border-red-200 rounded-lg px-4 py-3">{children}</div>
);

export const Chip: React.FC<{ tone?: 'amber' | 'gray' | 'indigo' | 'green' | 'red'; children: React.ReactNode; title?: string }> = ({ tone = 'gray', children, title }) => {
  const cls = {
    amber: 'bg-amber-50 text-amber-800 border-amber-200', gray: 'bg-gray-100 text-gray-600 border-gray-200',
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200', green: 'bg-green-50 text-green-800 border-green-200',
    red: 'bg-red-50 text-red-700 border-red-200',
  }[tone];
  return <span title={title} className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium border ${cls}`}>{children}</span>;
};

export const Btn: React.FC<React.ButtonHTMLAttributes<HTMLButtonElement> & { kind?: 'primary' | 'plain' | 'danger'; small?: boolean }> =
  ({ kind = 'plain', small, className = '', ...p }) => (
    <button {...p} className={`${small ? 'px-2 py-1 text-xs' : 'px-3 py-2 text-sm'} rounded-lg font-medium disabled:opacity-50 inline-flex items-center justify-center gap-1.5 ${
      kind === 'primary' ? 'bg-indigo-600 text-white hover:bg-indigo-700' : kind === 'danger' ? 'bg-white border border-red-200 text-red-700 hover:bg-red-50'
        : 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-50'} ${className}`} />
  );

export const Kbd: React.FC<{ children: React.ReactNode; dark?: boolean }> = ({ children, dark }) =>
  <kbd className={dark ? '!bg-indigo-500 !text-white !border-indigo-400' : ''}>{children}</kbd>;

// Text that may be Arabic: set right-to-left in its own block when it is
export const T: React.FC<{ text?: string | null; className?: string; as?: 'p' | 'span' | 'div' }> = ({ text, className = '', as = 'span' }) => {
  const Tag = as as any;
  if (!text) return <Tag className={className}>{S.common.none}</Tag>;
  return isArabic(text) ? <Tag dir="rtl" className={`ar ${className}`}>{text}</Tag> : <Tag dir="ltr" className={className}>{text}</Tag>;
};

// An ink crop from the scan (cached by the API). Lazy; a missing image shows the grey stripes.
export const Crop: React.FC<{ src: string | null; alt?: string; className?: string; maxH?: string; rtl?: boolean }> = ({ src, alt = 'ink crop from the scan', className = '', maxH = 'max-h-48', rtl }) => {
  const [bad, setBad] = useState(false);
  if (!src || bad) {
    return <div className={`crop-empty rounded-md border border-gray-200 h-10 flex items-center justify-center text-[11px] text-gray-400 gap-1 ${className}`}>
      <ImageOff className="w-3.5 h-3.5" aria-hidden /> {S.common.noImage}</div>;
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} loading="lazy" onError={() => setBad(true)} data-crop="1"
      className={`block rounded-md border border-gray-200 bg-white w-auto max-w-full ${maxH} object-contain ${rtl ? 'ml-auto' : ''} ${className}`} />
  );
};

export const Tabs: React.FC<{ tabs: [string, React.ReactNode][]; value: string; onChange: (v: string) => void }> = ({ tabs, value, onChange }) => (
  <div className="flex rounded-lg border border-gray-200 bg-white overflow-hidden text-sm" role="tablist">
    {tabs.map(([k, label]) => (
      <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)}
        className={`px-3 py-1.5 ${value === k ? 'bg-indigo-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}>{label}</button>
    ))}
  </div>
);

export const n = (x: number | null | undefined) => (x == null ? '—' : Number(x).toLocaleString('en'));
export const when = (iso?: string | null) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};
export const dur = (s?: number | null) => (s == null ? '—' : s < 60 ? `${Math.round(s)} s` : s < 3600 ? `${Math.floor(s / 60)} min ${Math.round(s % 60)} s` : `${(s / 3600).toFixed(1)} h`);
export const actorName = (a?: string | null) => (a ? a.replace(/^(person|agent|model|rule):/, '') : '—');
