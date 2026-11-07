import React, { useMemo, useState } from 'react';

// Shared bits of the /readers page (experiments 77, 78, 79): a word-level comparison against the truth that ignores
// punctuation (as the headline scores do), a reading row with its differences marked, a line crop.

const TATWEEL = /ـ/g;
const PUNCT = /[\p{P}«»*]/gu;
export const key = (w: string) => w.normalize('NFC').replace(TATWEEL, '').replace(PUNCT, '');

type Tok = { w: string; k: string; wrong?: boolean; missing?: boolean };

// The reader's words, each marked wrong when it is not in the longest common run with the truth. Between two words both
// share, the truth's left-over words and the reader's left-over words are one misread stretch: the reader's are marked
// wrong; truth words beyond them (nothing was written for them) are put back in place, struck as missing. A stretch
// counts as max(left-over truth words, left-over reader words). Punctuation-only tokens are never marked.
export function markReading(truth: string, reading: string): { toks: Tok[]; wrong: number; missing: number } {
  const T = truth.split(/\s+/).filter(Boolean).map(w => ({ w, k: key(w) })).filter(t => t.k);
  const R: Tok[] = reading.split(/\s+/).filter(Boolean).map(w => ({ w, k: key(w) }));
  const Rw = R.filter(t => t.k);
  const n = T.length, m = Rw.length;
  const L: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    L[i][j] = T[i].k === Rw[j].k ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const pairs: [number, number][] = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (T[i].k === Rw[j].k) { pairs.push([i, j]); i++; j++; }
    else if (L[i + 1][j] >= L[i][j + 1]) i++;
    else j++;
  }
  pairs.push([n, m]);                                     // sentinel: the end
  const matched = new Set(pairs.slice(0, -1).map(p => p[1]));
  const missAt = new Map<number, string[]>();             // reader-word index -> struck truth words to show before it
  let wrong = 0, missing = 0, pi = 0, pj = 0;
  for (const [ti, tj] of pairs) {
    const lostT = T.slice(pi, ti).map(t => t.w), extraR = tj - pj;
    wrong += Math.max(0, extraR - lostT.length) + Math.min(extraR, lostT.length);
    if (lostT.length > extraR) { missAt.set(tj, [...(missAt.get(tj) || []), ...lostT.slice(extraR)]); missing += lostT.length - extraR; }
    pi = ti + 1; pj = tj + 1;
  }
  const out: Tok[] = [];
  let wi = 0;
  for (const t of R) {
    if (!t.k) { out.push(t); continue; }
    (missAt.get(wi) || []).forEach(w => out.push({ w, k: key(w), missing: true }));
    out.push({ ...t, wrong: !matched.has(wi) });
    wi++;
  }
  (missAt.get(m) || []).forEach(w => out.push({ w, k: key(w), missing: true }));
  return { toks: out, wrong, missing };
}

export const Reading: React.FC<{ label: React.ReactNode; truth: string; text?: string | null; plain?: boolean; testid?: string; tone?: string; compact?: boolean }> =
  ({ label, truth, text, plain, testid, tone = 'text-gray-500', compact }) => {
    const r = useMemo(() => (text == null || plain ? null : markReading(truth, text)), [truth, text, plain]);
    const n = r ? r.wrong + r.missing : 0;
    return (
      <div className={compact ? 'grid grid-cols-[1fr_6.5rem] items-baseline gap-x-3 py-1' : 'grid grid-cols-[12rem_1fr_6.5rem] items-baseline gap-3 py-1'} data-testid={testid}>
        <div className={`text-xs ${tone} ${compact ? 'col-span-2' : ''}`}>{label}</div>
        {text == null ? <div className="text-xs text-gray-400">no reading</div> : (
          <div dir="rtl" className={`ar ${compact ? 'text-[15px] leading-7' : 'text-[17px] leading-8'} text-gray-900`}>
            {plain ? text : r!.toks.map((t, i) => (
              <React.Fragment key={i}>
                {t.missing ? <span className="text-rose-400 line-through decoration-rose-300 px-0.5" title="left out">{t.w}</span>
                  : t.wrong ? <span className="bg-rose-100 text-rose-900 rounded px-0.5" title="read differently">{t.w}</span>
                    : <span>{t.w}</span>}{' '}
              </React.Fragment>))}
          </div>)}
        <div className="text-[11px] text-right tabular-nums">
          {plain || text == null ? null : n === 0 ? <span className="text-green-700">every word right</span>
            : <span className="text-rose-700">{n} word{n > 1 ? 's' : ''} differ{n > 1 ? '' : 's'}</span>}
        </div>
      </div>
    );
  };

// a 48-px line crop shown a little larger, right-aligned like the line it is
export const LineCrop: React.FC<{ k: string; width?: number; h?: number }> = ({ k, width, h = 60 }) => {
  const [bad, setBad] = useState(false);
  const w = width ? Math.round((width * h) / 48) : undefined;
  if (bad) return <div className="crop-empty rounded-md border border-gray-200 h-10 text-[11px] text-gray-400 grid place-items-center">no image</div>;
  return (
    <div className="flex justify-end">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`/desk/api/readers/crop/${encodeURIComponent(k)}`} alt="the printed line (held-out scan)" loading="lazy" onError={() => setBad(true)}
        style={{ width: w ? `${w}px` : undefined }} className="block max-w-full h-auto rounded-md border border-gray-200 bg-white" />
    </div>
  );
};

// a picture from the experiments, cut to its top part (most are tall contact sheets)
export const Look: React.FC<{ name: string; maxH?: number; alt: string; caption?: React.ReactNode }> = ({ name, maxH = 260, alt, caption }) => (
  <figure>
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white" style={{ maxHeight: maxH }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`/desk/api/readers/look/${name}`} alt={alt} loading="lazy" className="block w-full h-auto" />
    </div>
    {caption && <figcaption className="text-[11px] text-gray-500 mt-1">{caption}</figcaption>}
  </figure>
);

export const pc = (x?: number | null, d = 2) => (x == null ? '—' : `${x.toFixed(d)}%`);
