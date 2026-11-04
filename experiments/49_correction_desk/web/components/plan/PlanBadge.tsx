import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { GanttChartSquare } from 'lucide-react';
import { api } from '../../lib/api';

// A small link to the plan with its live counts, for other pages' headers (the project page): "Plan: 3 running ·
// 12 need you". Says nothing if the plan cannot be read.
const PlanBadge: React.FC = () => {
  const [c, setC] = useState<{ running: number; needs_you: number; stale: number } | null>(null);
  useEffect(() => { api<any>('/plan').then(d => setC(d.counts)).catch(() => setC(null)); }, []);
  if (!c) return null;
  return (
    <Link href="/plan" data-testid="plan-badge" className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50">
      <GanttChartSquare className="w-4 h-4 text-teal-600" aria-hidden />Plan:
      <b className="text-teal-700">{c.running} running</b>{c.stale ? <span className="text-amber-700">({c.stale} quiet)</span> : null}·
      <b className="text-orange-600">{c.needs_you} need you</b>
    </Link>);
};
export default PlanBadge;
