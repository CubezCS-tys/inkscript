import React from 'react';
import { CheckCircle2 } from 'lucide-react';
import { Card } from './Bits';
import { Def } from './IndexBits';

// The librarian pages' shared parts (experiment 73): the decisions WERE applied on 2 November (M4), and the
// production librarian's measured numbers (experiment 71), from /desk/api/headlines.

export const AppliedBanner: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900 flex items-start gap-2" data-testid="applied-banner">
    <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" aria-hidden /><span>{children}</span></div>
);

const fmt = (v: any, unit = '') => (v == null ? '—' : `${v}${unit}`);

export const ProductionLibrarian: React.FC<{ h: any }> = ({ h }) => {
  const l = h?.librarian, D = h?.defs || {};
  return (
    <Card title={<Def text={D.librarian}>The librarian from now on: checked on a hand-made answer key</Def>}>
      <div className="grid sm:grid-cols-3 gap-3" data-testid="production-librarian">
        <div className="rounded-lg bg-gray-50 px-3 py-2"><Def text={D.librarian_precision}><span className="text-xs text-gray-500">Decisions right</span></Def>
          <span className="block text-2xl font-semibold text-gray-900 tabular-nums">{fmt(l?.precision_pct, '%')}</span>
          <span className="text-xs text-gray-500">{l?.decisions_checked ? `on ${l.decisions_checked} decisions checked by hand` : ''}</span></div>
        <div className="rounded-lg bg-gray-50 px-3 py-2"><Def text={D.librarian_to_person}><span className="text-xs text-gray-500">Left to a person</span></Def>
          <span className="block text-2xl font-semibold text-gray-900 tabular-nums">{fmt(l?.to_person_pct, '%')}</span>
          <span className="text-xs text-gray-500">the cases the models are unsure of</span></div>
        <div className="rounded-lg bg-gray-50 px-3 py-2"><Def text={D.librarian_cost}><span className="text-xs text-gray-500">Cost</span></Def>
          <span className="block text-2xl font-semibold text-gray-900 tabular-nums">{l?.usd_per_1000 != null ? `≈ $${l.usd_per_1000}` : '—'}</span>
          <span className="text-xs text-gray-500">per 1,000 decisions</span></div>
      </div>
      <p className="text-xs text-gray-500 mt-2">A wrong bridge corrupts every count, so the librarian is judged by how often it is right. A cheap model answers the kinds of question it is reliable on,
        a strong model the rest, and what both are unsure of goes to a person.</p>
    </Card>
  );
};
