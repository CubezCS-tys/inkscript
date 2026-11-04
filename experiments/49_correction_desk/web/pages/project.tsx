import React from 'react';
import { useRouter } from 'next/router';
import { LayoutDashboard, List, Network } from 'lucide-react';
import Layout from '../components/Layout';
import { ErrorBox } from '../components/Bits';
import ProjectDetails from '../components/ProjectDetails';
import ProjectMap, { Journey } from '../components/ProjectMap';
import PlanBadge from '../components/plan/PlanBadge';
import { useApi } from '../lib/me';
import { useShowMode } from '../lib/showmode';

// The project page (2026-10-26): the Web-of-Science project at a glance, the page the owner opens first when they
// come back. Two tabs over one file, desk/project/project.json (API desk/project.py), in which every item carries
// its source:
//   Map (the default): the journey line (gate 1 → gate 2 → gate 3 → the archive, "you are here") and a mind map of
//     the project, branches closed with counts, short labels, colour by status, a side panel with the full text;
//   Details (?tab=details): the page as first built, every section in full (components/ProjectDetails.tsx).

export default function ProjectPage() {
  const { data: d, err } = useApi<any>('/project');
  const router = useRouter();
  const show = useShowMode();
  const tab = router.query.tab === 'details' ? 'details' : 'map';
  const go = (t: string) => router.replace({ pathname: '/project', query: t === 'map' ? {} : { tab: t } }, undefined, { shallow: true, scroll: false });

  if (err) return <Layout><ErrorBox>{err}</ErrorBox></Layout>;
  if (!d) return <Layout><p className="text-sm text-gray-500">Loading the project…</p></Layout>;
  // presentation mode (experiment 73, M11): the journey strip and its headline only; no board, no sources, no to-dos
  if (show) return (
    <Layout wide>
      <div className="pt-2">
        <h1 className="text-2xl font-semibold text-gray-900">From one journal to the Arabic Web of Science</h1>
        <p className="text-sm text-gray-500 mt-1">Gate by gate: each step is paid for only after the one before has shown it works. As of {d.meta.as_of}.</p>
      </div>
      <Journey d={d} onPick={() => {}} />
    </Layout>);
  return (
    <Layout wide>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2"><LayoutDashboard className="w-5 h-5 text-indigo-600" aria-hidden />{d.meta.title}</h1>
          <p className="text-xs text-gray-500 mt-0.5">As of <b>{d.meta.as_of}</b>. Every item has a source: click it on the map, or see Details.</p>
        </div>
        <PlanBadge />
        <div className="flex rounded-xl border border-gray-200 bg-white p-1 text-sm" role="tablist" aria-label="How to see the project">
          {([['map', 'Map', Network], ['details', 'Details', List]] as const).map(([k, l, Icon]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => go(k)} data-testid={`tab-${k}`}
              className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg font-medium ${tab === k ? 'bg-indigo-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}>
              <Icon className="w-4 h-4" aria-hidden />{l}</button>))}
        </div>
      </div>
      {tab === 'map' ? <ProjectMap d={d} /> : <ProjectDetails d={d} />}
    </Layout>
  );
}
