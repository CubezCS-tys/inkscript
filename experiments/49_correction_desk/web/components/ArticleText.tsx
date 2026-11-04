import React from 'react';
import { Chip, T } from './Bits';
import { isArabic } from '../lib/api';
import { S } from '../lib/strings';

// The pieces of an article's full text, shared by the Article page's Text view and the beside-the-scan view
// (moved out of pages/articles/[stem].tsx on 2026-10-23, unchanged).
export function withCalls(text: string, calls: any[]): React.ReactNode[] {
  // put each note call at its char_offset as a link to its note; a call not found there is appended
  if (!calls?.length) return [text];
  const out: React.ReactNode[] = [];
  let pos = 0;
  const tail: any[] = [];
  [...calls].sort((a, b) => a.char_offset - b.char_offset).forEach(c => {
    const t = c.call_text || '';
    const at = text.slice(c.char_offset, c.char_offset + t.length) === t ? c.char_offset
      : text.indexOf(t, Math.max(pos, c.char_offset - 3));
    if (at >= pos && t) {
      out.push(text.slice(pos, at));
      out.push(<a key={`c${c.call_seq}`} id={`call-${c.call_seq}`} href={c.targets?.[0] ? `#note-${c.targets[0]}` : undefined} className="notecall">{t}</a>);
      pos = at + t.length;
    } else tail.push(c);
  });
  out.push(text.slice(pos));
  tail.forEach(c => out.push(<a key={`t${c.call_seq}`} id={`call-${c.call_seq}`} href={c.targets?.[0] ? `#note-${c.targets[0]}` : undefined} className="notecall">{c.call_text}</a>));
  return out;
}

export const TableFig: React.FC<{ fig: any }> = ({ fig }) => {
  const rows: Record<number, any[]> = {};
  fig.cells.forEach((c: any) => { (rows[c.row] ||= []).push(c); });
  const ar = fig.cells.some((c: any) => isArabic(c.text));
  return (
    <figure className="my-3" id={`fig-${fig.figure_id}`}>
      {(fig.label || fig.caption) && <figcaption className="text-sm text-gray-600 mb-1"><T text={[fig.label, fig.caption].filter(Boolean).join(' ')} /></figcaption>}
      <div className="overflow-x-auto">
        <table dir={ar ? 'rtl' : 'ltr'} className={`text-sm border border-gray-200 ${ar ? 'ar' : ''}`} data-testid="table">
          <tbody>{Object.keys(rows).map(Number).sort((a, b) => a - b).map(r => (
            <tr key={r}>{rows[r].map((c: any) => {
              const Tag = c.is_header ? 'th' : 'td';
              return <Tag key={c.col} rowSpan={c.rowspan || 1} colSpan={c.colspan || 1} className={`border border-gray-200 px-2 py-1 align-top ${c.is_header ? 'bg-gray-50 font-semibold' : ''}`}>{c.text}</Tag>;
            })}</tr>))}
          </tbody>
        </table>
      </div>
      <FigNotes fig={fig} />
    </figure>
  );
};

// v3.5b: the notes and «المصدر:» lines printed under a table or a figure, tied to it
export const FigNotes: React.FC<{ fig: any }> = ({ fig }) => !fig.notes?.length ? null : (
  <div className="mt-1 space-y-0.5 text-xs text-gray-600" data-testid="figure-notes" aria-label={fig.kind === 'table' ? S.article.tableNotes : S.article.figureNotes}>
    {fig.notes.map((x: any) => (
      <p key={x.seq} dir={isArabic(x.text) ? 'rtl' : 'ltr'} className={isArabic(x.text) ? 'ar' : ''}>
        <Chip tone={x.kind === 'source' ? 'indigo' : 'gray'}>{x.kind}</Chip> <T text={x.text} />
      </p>))}
  </div>
);

export const Verses: React.FC<{ verses: any[] }> = ({ verses }) => {
  const rows: any[][] = [];
  verses.forEach(v => {
    const last = rows[rows.length - 1];
    if (v.part === 'ajuz' && last && last.length === 1 && last[0].part === 'sadr') last.push(v); else rows.push([v]);
  });
  return (
    <div className="ar space-y-1 py-1" data-testid="verse">
      {verses[0]?.poet_hint && <p className="text-xs text-gray-500">{verses[0].poet_hint}</p>}
      {rows.map((r, i) => r.length === 2
        ? <div key={i} className="grid grid-cols-2 gap-8 text-[17px] leading-8"><span>{r[0].text}</span><span>{r[1].text}</span></div>
        : <div key={i} className="text-center text-[17px] leading-8">{r[0].text}</div>)}
    </div>
  );
};

export const ROLE: Record<string, string> = {
  title: 'text-2xl font-semibold text-gray-900', 'title-translated': 'text-lg text-gray-700', heading: 'text-lg font-semibold text-gray-900 pt-2',
  paragraph: 'text-[16px] leading-8 text-gray-900', abstract: 'text-[15px] leading-7 text-gray-800 bg-gray-50 rounded-lg px-3 py-2',
  keywords: 'text-sm text-gray-700 italic', 'list-item': 'text-[16px] leading-8 text-gray-900 ps-4', quote: 'text-[16px] leading-8 text-gray-800 border-s-4 border-gray-200 ps-3',
  caption: 'text-sm text-gray-600 italic', ref: 'text-sm leading-7 text-gray-800', byline: 'text-base text-gray-800 font-medium', affiliation: 'text-sm text-gray-600',
  'front-matter': 'text-sm text-gray-500', 'back-matter': 'text-sm text-gray-500',
};

