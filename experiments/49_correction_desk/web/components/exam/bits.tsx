import React, { useEffect, useState } from 'react';
import { ImageOff, X } from 'lucide-react';
import { isArabic } from '../../lib/api';

// Shared bits of the /exam page (experiment 97): picture URLs, text with its differences marked, plain names for
// the triage classes, the role colours of the page-structure view, and a simple picture viewer.

export const img = (p?: string | null) => {
  if (!p) return null;
  const [kind, name] = p.split('/');
  return `/desk/api/exam/img/${kind}/${encodeURIComponent(name)}`;
};

// 0.00021 -> "0.021%", 0.0091 -> "0.91%", 0.947 -> "94.7%"
export const pc = (x?: number | null) => {
  if (x == null) return '—';
  const v = 100 * x;
  if (v === 0) return '0%';
  if (Math.abs(v) < 0.1) return `${v.toFixed(3)}%`;
  if (Math.abs(v) < 1) return `${v.toFixed(2)}%`;
  return `${v.toFixed(1)}%`;
};

export const pageName = (stem: string, page: number) => `${stem}, page ${page}`;

// A picture from out/page/img; a missing one shows the grey stripes, as elsewhere in the Desk.
export const Pic: React.FC<{ src?: string | null; alt: string; className?: string; style?: React.CSSProperties; onClick?: () => void }> =
  ({ src, alt, className = '', style, onClick }) => {
    const [bad, setBad] = useState(false);
    const u = img(src);
    if (!u || bad) return (
      <div className={`crop-empty rounded-md border border-gray-200 h-16 flex items-center justify-center text-[11px] text-gray-400 gap-1 ${className}`}>
        <ImageOff className="w-3.5 h-3.5" aria-hidden /> no picture</div>);
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={u} alt={alt} loading="lazy" onError={() => setBad(true)} onClick={onClick} style={style}
        className={`block rounded-md border border-gray-200 bg-white ${onClick ? 'cursor-zoom-in' : ''} ${className}`} />);
  };

// Text with the stretches that differ from the other side marked (segments from page97.py: [text, 0 same | 1 differs
// | 2 something of the other side is missing here]). Arabic is set right to left in the edition font.
export const Marked: React.FC<{ segs?: [string, number][] | null; text?: string | null; className?: string; big?: boolean }> =
  ({ segs, text, className = '', big }) => {
    const full = text ?? (segs ? segs.map(s => s[0]).join('') : '');
    if (!full && !(segs && segs.some(s => s[1] === 2))) return <span className="text-sm text-gray-400 italic">nothing stored</span>;
    const ar = isArabic(full);
    const body = segs ? segs.map((s, i) => s[1] === 0 ? <React.Fragment key={i}>{s[0]}</React.Fragment>
      : s[1] === 1 ? <mark key={i} className="bg-rose-100 text-rose-900 rounded-sm">{s[0]}</mark>
        : <span key={i} title="something is missing here" className="inline-block w-[3px] h-[0.9em] bg-rose-500 align-middle mx-[1px] rounded-sm" />) : full;
    return ar
      ? <div dir="rtl" className={`ar ${big ? 'text-[19px] leading-9' : 'text-[17px] leading-8'} text-gray-900 ${className}`}>{body}</div>
      : <div dir="ltr" className={`${big ? 'text-[15px]' : 'text-sm'} leading-6 text-gray-900 break-words ${className}`}>{body}</div>;
  };

export const TRIAGE_CLASS: Record<string, [string, string]> = {
  PIPELINE: ['Real pipeline error', 'bg-rose-50 text-rose-800 border-rose-200'],
  SCORER: ['Scoring artefact', 'bg-indigo-50 text-indigo-700 border-indigo-200'],
  KEY: ['Answer key issue', 'bg-amber-50 text-amber-800 border-amber-200'],
  UNCLEAR: ['Unclear', 'bg-gray-100 text-gray-600 border-gray-200'],
};

export const TriageChip: React.FC<{ t?: { cls?: string; sub?: string; why?: string } | null; full?: boolean }> = ({ t, full }) => {
  if (!t || !t.cls) return null;
  const [label, cls] = TRIAGE_CLASS[t.cls] || [t.cls, 'bg-gray-100 text-gray-600 border-gray-200'];
  return (
    <div className="text-xs">
      <span className={`inline-flex items-center px-1.5 py-0.5 rounded border font-medium ${cls}`} title="the triage's verdict on this miss">{label}</span>
      {full && (t.sub || t.why) && <span className="text-gray-500 ml-2">{t.sub}{t.sub && t.why ? ': ' : ''}{t.why}</span>}
    </div>);
};

// role colours for the page-structure view (the same on the key's side and the pipeline's)
export const ROLE_COLOUR: Record<string, string> = {
  'title': '#7c3aed', 'title-translated': '#a78bfa', 'byline': '#db2777', 'affiliation': '#f472b6',
  'author block (byline + affiliation)': '#db2777', 'abstract': '#0891b2', 'keywords': '#22d3ee',
  'front-matter': '#a16207', 'heading': '#4f46e5', 'paragraph': '#64748b', 'list-item': '#16a34a',
  'quote': '#ca8a04', 'verse': '#ea580c', 'footnote': '#0d9488', 'endnote': '#14b8a6', 'ref': '#2563eb',
  'caption': '#9333ea', 'table': '#c2410c', 'figure': '#65a30d', 'equation': '#4d7c0f',
  'running-head': '#94a3b8', 'page-number': '#334155', 'other': '#a8a29e', '(not-text)': '#d6d3d1', '(no-block)': '#dc2626',
};

// a picture viewer over the page: Esc or a click outside closes it
export const Viewer: React.FC<{ src: string | null; caption?: React.ReactNode; onClose: () => void }> = ({ src, caption, onClose }) => {
  useEffect(() => {
    if (!src) return;
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', k);
    return () => document.removeEventListener('keydown', k);
  }, [src, onClose]);
  if (!src) return null;
  return (
    <div className="fixed inset-0 z-50 bg-gray-900/70 flex items-start justify-center overflow-auto p-6" onClick={onClose} role="dialog" aria-modal="true">
      <div className="bg-white rounded-xl shadow-xl p-3 max-w-[1200px]" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-2 gap-4">
          <div className="text-sm text-gray-700">{caption}</div>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100" aria-label="close"><X className="w-5 h-5 text-gray-600" /></button>
        </div>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={img(src) || ''} alt="the page at full size" className="block max-w-full h-auto" />
      </div>
    </div>);
};

export const Pills: React.FC<{ items: [string, React.ReactNode, number?][]; value: string; onChange: (v: string) => void; label: string }> =
  ({ items, value, onChange, label }) => (
    <div className="flex flex-wrap gap-2" role="tablist" aria-label={label}>
      {items.map(([k, l, n]) => (
        <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)}
          className={`rounded-full border px-3 py-1 text-sm ${value === k ? 'border-indigo-500 bg-indigo-50 text-indigo-900' : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'}`}>
          {l}{n != null && <span className="text-xs text-gray-500 ml-1">{n}</span>}</button>))}
    </div>);

export const More: React.FC<{ shown: number; total: number; onMore: () => void }> = ({ shown, total, onMore }) =>
  shown >= total ? null : (
    <div className="mt-4 text-center">
      <button onClick={onMore} className="px-4 py-2 text-sm rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50">
        Show more <span className="text-gray-500">({shown} of {total} shown)</span></button>
    </div>);
