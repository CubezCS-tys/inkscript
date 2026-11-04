import React from 'react';
import Link from 'next/link';
import { cropOfAnchor, isArabic } from '../lib/api';
import { S, f } from '../lib/strings';
import { Crop, T } from './Bits';

export type Member = { key: string; stem: string; page?: number; printed: string; anchor?: string | null; authors?: string[]; article_title?: string };

// Each citation with its ink, and a picker: "Unclear" (0) or "Book i". Digits on a focused row pick its book.
export const SplitPicker: React.FC<{ members: Member[]; group: Record<string, number>; setGroup: (g: Record<string, number>) => void }> =
  ({ members, group, setGroup }) => {
    const max = Math.max(2, members.length);
    const set = (k: string, v: number) => setGroup({ ...group, [k]: v });
    return (
      <ol className="divide-y divide-gray-100" data-testid="members">
        {members.map((m, i) => {
          const letter = String.fromCharCode(65 + (i % 26));
          const page = m.page ?? (m.anchor ? Number((m.anchor.match(/\|p(\d+)\|/) || [])[1]) : undefined);
          return (
            <li key={m.key} tabIndex={0} data-member={m.key}
              onKeyDown={e => { if (/^[0-9]$/.test(e.key) && (e.target as HTMLElement).tagName !== 'SELECT') { e.preventDefault(); e.stopPropagation(); set(m.key, Number(e.key)); } }}
              className="px-5 py-3 grid sm:grid-cols-[2rem_minmax(0,1fr)_9rem] gap-3 items-start focus:bg-indigo-50/50 outline-none">
              <span className="w-7 h-7 rounded-lg bg-gray-100 text-gray-700 grid place-items-center text-sm font-medium">{letter}</span>
              <div className="min-w-0 space-y-1.5">
                <Crop src={cropOfAnchor(m.anchor)} maxH="max-h-28" rtl={isArabic(m.printed)} />
                <T as="p" text={m.printed} className="text-[15px] leading-7 text-gray-900" />
                <p className="text-xs text-gray-500">
                  <Link href={`/articles/${encodeURIComponent(m.stem)}`} className="hover:text-indigo-700 hover:underline">{m.stem}</Link>
                  {page ? ` · ${S.common.page} ${page}` : ''} · {m.authors?.length ? f(S.work.authorPrinted, { a: m.authors.join('; ') }) : S.work.noAuthor}
                </p>
              </div>
              <select value={group[m.key] ?? 0} onChange={e => set(m.key, Number(e.target.value))} aria-label={`Group for citation ${letter}`}
                className="rounded-lg border-gray-300 text-sm" data-testid="group-select">
                <option value={0}>{S.work.unclear}</option>
                {Array.from({ length: max }, (_, j) => <option key={j + 1} value={j + 1}>{f(S.work.book, { n: j + 1 })}</option>)}
              </select>
            </li>
          );
        })}
      </ol>
    );
  };

// the books, in order, for split_work: [[mention keys of book 1], [book 2], …]; unclear ones are left out
export function booksOf(members: Member[], group: Record<string, number>): { books: string[][]; unclear: string[]; labels: string[] } {
  const by: Record<number, Member[]> = {};
  members.forEach(m => { const g = group[m.key] ?? 0; (by[g] ||= []).push(m); });
  const nums = Object.keys(by).map(Number).filter(x => x > 0).sort((a, b) => a - b);
  return {
    books: nums.map(x => by[x].map(m => m.key)),
    unclear: (by[0] || []).map(m => m.key),
    labels: nums.map(x => Array.from(new Set(by[x].flatMap(m => m.authors || []))).join(' / ').slice(0, 80)),
  };
}

export const GroupsSummary: React.FC<{ members: Member[]; group: Record<string, number> }> = ({ members, group }) => {
  const by: Record<number, number[]> = {};
  members.forEach((m, i) => { (by[group[m.key] ?? 0] ||= []).push(i); });
  const keys = Object.keys(by).map(Number).sort((a, b) => (a === 0 ? 1 : 0) - (b === 0 ? 1 : 0) || a - b);
  const books = keys.filter(k => k > 0).length;
  return (
    <div className="space-y-2 text-sm" data-testid="groups">
      {keys.map(k => (
        <div key={k} className="flex items-start gap-2">
          <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-medium ${k === 0 ? 'bg-amber-50 text-amber-800 border border-amber-200' : 'bg-indigo-50 text-indigo-700'}`}>
            {k === 0 ? S.work.unclear : f(S.work.book, { n: k })}</span>
          <span className="text-gray-700">{by[k].map(i => String.fromCharCode(65 + (i % 26)) + (members[i].authors?.length ? ' ' + members[i].authors![0] : '')).join(', ')}</span>
        </div>
      ))}
      <p className="text-xs text-gray-500 pt-1">{f(S.work.groupsSummary, { books, unclear: (by[0] || []).length })}</p>
    </div>
  );
};
