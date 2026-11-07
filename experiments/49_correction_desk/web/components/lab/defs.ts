// Shared bits of the OCR lab page (experiment 75): engine colours and short names, a word diff, number formats.

export type Engine = {
  run_id: string; engine: string; variant: string; label: string; kind: 'ours' | 'open' | 'earlier' | 'other';
  imported: boolean; state: string; attempts: number; facts: any; note?: string; failure?: { kind: string; message: string };
  blocks?: { id: string; type: string; raw_label?: string; box?: number[] | null; order?: number | null; text: string; flags?: string[] }[];
  text?: string; lines?: { id: string; text: string; box?: number[] | null; region?: string | null }[];
  elsewhere?: Record<string, { text: string | null; score: number; same?: boolean } | null>[];
  empty?: boolean; truncated?: boolean | null; repetition?: boolean; timing?: any; resources?: any; settings?: any;
  cost?: { usd: number; basis: string } | null; has_boxes?: boolean; has_text?: boolean; load_s?: number | null;
  health?: any; capabilities?: any; warning?: string;
};

const PALETTE: Record<string, string> = {
  'azure_read/existing': '#0f766e', 'paddle_vl/pipeline': '#4f46e5', 'paddle_vl/bare_ocr': '#0284c7',
  'paddle_vl/layout_stage': '#7c3aed', 'nuqta/as_written': '#c2410c', 'nuqta/markdown': '#d97706',
  'paddle_vl15_exp36/pipeline': '#6b7280', 'azure_argon/existing': '#065f46', 'nuqta/as_written_fast': '#9a3412',
  'nuqta/as_written_speedfix': '#ea580c', 'nuqta/markdown_speedfix': '#f59e0b', 'combo_paddle_nuqta/regions_speedfix': '#be185d', 'combo_paddle_nuqta/regions_speedfix_rtl': '#9d174d',
};
export const colorOf = (e: Engine) => PALETTE[`${e.engine}/${e.variant}`] || '#334155';
const SHORT: Record<string, string> = {
  'azure_read/existing': 'Ours (Azure)', 'paddle_vl/pipeline': 'Paddle 1.6', 'paddle_vl/bare_ocr': 'Paddle 1.6 alone',
  'paddle_vl/layout_stage': 'Paddle layout', 'nuqta/as_written': 'Nuqta', 'nuqta/markdown': 'Nuqta Markdown',
  'paddle_vl15_exp36/pipeline': 'Paddle 1.5 (exp 36)', 'azure_argon/existing': 'Ours (Azure + Argon)',
  'nuqta/as_written_fast': 'Nuqta, fast kernels', 'nuqta/as_written_speedfix': 'Nuqta, speed fix',
  'nuqta/markdown_speedfix': 'Nuqta Markdown, speed fix', 'combo_paddle_nuqta/regions_speedfix': 'Combination: Paddle regions + Nuqta text', 'combo_paddle_nuqta/regions_speedfix_rtl': 'Combination + RTL column rule',
};
export const shortOf = (e: Engine) => SHORT[`${e.engine}/${e.variant}`] || e.label;

export const TYPE_NICE: Record<string, string> = {
  paragraph: 'text', heading: 'heading', title: 'title', list: 'list', footnote: 'footnote', header: 'running head',
  footer: 'running foot', page_number: 'page number', table: 'table', equation: 'equation', figure: 'figure',
  caption: 'caption', bibliography: 'reference', abstract: 'abstract', text: 'text', unknown: 'unknown',
};

export const pct = (x?: number | null, d = 1) => (x == null ? '—' : `${(100 * x).toFixed(d)}%`);
export const secs = (x?: number | null) => (x == null ? '—' : x < 10 ? `${x.toFixed(1)} s` : `${Math.round(x)} s`);
export const usd = (x?: number | null) => (x == null ? '—' : x < 0.01 ? `$${x.toFixed(4)}` : `$${x.toFixed(3)}`);

export type Op = { op: 'equal' | 'replace' | 'delete' | 'insert'; a: string[]; b: string[] };

// word-level difference of two texts (LCS); a = left (or truth), b = right (or engine)
export function wordDiff(left: string, right: string): Op[] {
  const a = left.split(/\s+/).filter(Boolean), b = right.split(/\s+/).filter(Boolean);
  const n = a.length, m = b.length;
  if (n * m > 4_000_000) return [{ op: 'replace', a, b }];
  const L: Uint16Array[] = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const out: Op[] = [];
  const push = (op: Op['op'], x: string[], y: string[]) => {
    const last = out[out.length - 1];
    if (last && last.op === op) { last.a.push(...x); last.b.push(...y); } else out.push({ op, a: [...x], b: [...y] });
  };
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { push('equal', [a[i]], [b[j]]); i++; j++; }
    else if (L[i + 1][j] >= L[i][j + 1]) { push('delete', [a[i]], []); i++; }
    else { push('insert', [], [b[j]]); j++; }
  }
  while (i < n) push('delete', [a[i++]], []);
  while (j < m) push('insert', [], [b[j++]]);
  // a delete next to an insert reads better as one replacement
  const merged: Op[] = [];
  for (const o of out) {
    const last = merged[merged.length - 1];
    if (last && ((last.op === 'delete' && o.op === 'insert') || (last.op === 'insert' && o.op === 'delete') || (last.op === 'replace' && o.op !== 'equal'))) {
      last.op = 'replace'; last.a.push(...o.a); last.b.push(...o.b);
    } else merged.push({ ...o, a: [...o.a], b: [...o.b] });
  }
  return merged;
}

// readers the owner dropped (2026-11-04: "drop paddle its terrible"): their TEXT is hidden unless asked for; their
// regions stay available on the scan (the layout question is still open)
export const DROPPED_NOTE = 'dropped by the owner, 2026-11-04';
export const isDropped = (e: { engine: string; variant: string }) =>
  e.engine === 'paddle_vl15_exp36' || (e.engine === 'paddle_vl' && (e.variant === 'pipeline' || e.variant === 'bare_ocr'));
