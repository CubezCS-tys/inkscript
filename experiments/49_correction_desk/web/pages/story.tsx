import React, { useCallback, useEffect, useRef, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { ChevronLeft, ChevronRight, Maximize2, Minimize2 } from 'lucide-react';
import Layout from '../components/Layout';
import { STEPS, Ctx, WORK } from '../components/story/Steps';
import { STORY_CSS } from '../components/story/Bits';
import { useApi } from '../lib/me';

// The Story (experiment 73, 2026-11-03): the Desk told in seven steps for the shareholders, in the order of
// AUDIT.md §4. → / space / PageDown next, ← / PageUp back, 1–7 jump, F presents full screen. The step is kept in
// the URL (?step=3), so "open live" and the browser's back button return to the same step.
// Every number comes from GET /desk/api/headlines (desk/headlines.py); a missing value shows "—".

export default function Story() {
  const router = useRouter();
  const n = STEPS.length;
  const qs = Number(router.query.step);
  const step = Number.isInteger(qs) && qs >= 1 && qs <= n ? qs - 1 : 0;
  const dir = useRef(1);
  const box = useRef<HTMLDivElement>(null);
  const [full, setFull] = useState(false);

  const head = useApi<any>('/headlines');
  const project = useApi<any>('/project');
  const work = useApi<any>(`/works/${WORK}`);
  const ja = useApi<any>('/index/journals/J0130');
  const jb = useApi<any>('/index/journals/J0165');
  const ctx: Ctx = { h: head.data, project: project.data, work: work.data, j: { J0130: ja.data, J0165: jb.data } };

  const go = useCallback((i: number) => {
    const k = Math.max(0, Math.min(n - 1, i));
    if (k === step) return;
    dir.current = k > step ? 1 : -1;
    router.replace({ pathname: '/story', query: { ...router.query, step: k + 1 } }, undefined, { shallow: true, scroll: false });
  }, [n, step, router]);

  const toggleFull = useCallback(() => {
    try {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen();
    } catch { /* not allowed here */ }
  }, []);

  useEffect(() => {
    const f = () => setFull(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', f);
    return () => document.removeEventListener('fullscreenchange', f);
  }, []);

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      if (t && t.closest && t.closest('[role="menu"]')) return;
      if (e.key === 'ArrowRight' || e.key === 'PageDown' || (e.key === ' ' && !(t && t.tagName === 'BUTTON'))) { e.preventDefault(); go(step + 1); }
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); go(step - 1); }
      else if (e.key === 'Home') { e.preventDefault(); go(0); }
      else if (e.key === 'End') { e.preventDefault(); go(n - 1); }
      else if (/^[1-9]$/.test(e.key) && Number(e.key) <= n) go(Number(e.key) - 1);
      else if (e.key === 'f' || e.key === 'F') toggleFull();
    };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [go, step, n, toggleFull]);

  useEffect(() => { box.current?.scrollTo?.({ top: 0 }); window.scrollTo({ top: 0 }); }, [step]);

  const cur = STEPS[step];
  return (
    <Layout wide bare={full}>
      <Head><title>{`The story · ${step + 1} of ${n} · Mandumah Citation Index`}</title></Head>
      <div ref={box} className={`flex flex-col ${full ? 'min-h-[calc(100vh-3rem)] px-6 pt-2' : 'min-h-[calc(100vh-3.5rem-3rem)]'}`} data-testid="story">
        <style>{STORY_CSS}</style>
        {/* the seven steps: a progress bar that is also the way to jump */}
        <nav aria-label="Steps of the story" className="flex items-stretch gap-1.5">
          {STEPS.map((s, i) => (
            <button key={s.key} type="button" onClick={() => go(i)} aria-current={i === step ? 'step' : undefined} data-testid={`step-${i + 1}`}
              className="group flex-1 min-w-0 text-left pt-1 focus:outline-none">
              <span className="block h-1.5 rounded-full bg-gray-200 overflow-hidden">
                <span className={`block h-full rounded-full transition-all duration-500 ease-out ${i <= step ? 'bg-teal-500' : 'bg-transparent'}`} style={{ width: i <= step ? '100%' : '0%' }} />
              </span>
              <span className={`block mt-1.5 text-xs truncate transition-colors ${i === step ? 'text-gray-900 font-semibold' : 'text-gray-500 group-hover:text-gray-800'}`}>
                <span className="tabular-nums">{i + 1}</span> · {s.short}
              </span>
            </button>))}
        </nav>

        <article key={cur.key} className="st-stage flex-1 pt-8 pb-6" style={{ ['--dx' as any]: `${dir.current * 28}px` }} aria-live="polite">
          {cur.render(ctx)}
        </article>

        <div className="flex items-center justify-between border-t border-gray-200 pt-4 pb-1 text-sm text-gray-500">
          <button type="button" onClick={() => go(step - 1)} disabled={step === 0} data-testid="prev"
            className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 hover:bg-white hover:text-gray-900 disabled:opacity-30 disabled:hover:bg-transparent">
            <ChevronLeft className="w-4 h-4" aria-hidden /> {step > 0 ? STEPS[step - 1].short : 'Back'}
          </button>
          <div className="flex items-center gap-4">
            <span className="hidden xl:inline">Keys: <kbd>←</kbd> <kbd>→</kbd> or <kbd>space</kbd> · <kbd>F</kbd> full screen</span>
            <button type="button" onClick={toggleFull} data-testid="present"
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-gray-700 hover:bg-gray-50">
              {full ? <Minimize2 className="w-4 h-4" aria-hidden /> : <Maximize2 className="w-4 h-4" aria-hidden />}{full ? 'Leave full screen' : 'Present'}
            </button>
          </div>
          <button type="button" onClick={() => go(step + 1)} disabled={step === n - 1} data-testid="next"
            className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 font-medium text-indigo-700 hover:bg-white disabled:opacity-30 disabled:hover:bg-transparent">
            {step < n - 1 ? STEPS[step + 1].short : 'The end'} <ChevronRight className="w-4 h-4" aria-hidden />
          </button>
        </div>
      </div>
    </Layout>
  );
}
