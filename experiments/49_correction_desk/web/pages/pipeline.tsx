import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import { Play, Pause, SkipForward, SkipBack, RotateCcw, Maximize2, Minimize2, Search, Check, Workflow } from 'lucide-react';
import Layout from '../components/Layout';
import { ErrorBox } from '../components/Bits';
import PageCanvas from '../components/pipeline/PageCanvas';
import { STAGES, SPEEDS, DEFAULT_STEM } from '../components/pipeline/defs';
import { Tiles, tilesFor, ScanPanel, AzurePanel, GeminiPanel, RulesPanel, JudgePanel, PlatformPanel, IndexPanel, GhostLayer, Ghost } from '../components/pipeline/StagePanels';
import { api, enc, isArabic } from '../lib/api';

// How a page is read (/pipeline, 2026-10-30): one real page taken through the pipeline that reads Mandumah's archive,
// stage by stage, animated on the scan itself: the scan → Azure's words and numbered lines → Gemini's roles and
// reading order (line ids only) → the code rules and masters → the judge → the fields leaving the page with their
// ink and joining records with permanent ids → the article in the index. Everything comes from
// GET /desk/api/pipeline/{stem}?page= (desk/pipeline.py), read-only. Play / pause / step / speed / full screen;
// the stage and page are in the URL (?stem=&page=&stage=), so a view can be shared.

type V = React.CSSProperties & Record<string, any>;
const QUICK: [string, string][] = [['front', 'Front page'], ['footnotes', 'Footnotes'], ['table', 'A table'], ['references', 'References'], ['judged', 'Judged page']];

export default function PipelinePage() {
  const router = useRouter();
  const stem = typeof router.query.stem === 'string' ? router.query.stem : DEFAULT_STEM;
  const page = Math.max(1, parseInt(String(router.query.page || '1'), 10) || 1);
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState('');
  const [stage, setStage] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [done, setDone] = useState(false);          // the stage shown finished (stepped to while paused)
  const [speed, setSpeed] = useState(1);
  const [run, setRun] = useState(0);                // bumps to replay the current stage
  const [hover, setHover] = useState<string | null>(null);
  const [ghosts, setGhosts] = useState<Ghost[]>([]);
  const [full, setFull] = useState(false);
  const bar = useRef<HTMLDivElement>(null);
  const shell = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const elapsed = useRef(0);

  useEffect(() => {
    if (!router.isReady) return;
    setD(null); setErr('');
    api(`/pipeline/${enc(stem)}?page=${page}`).then(x => {
      setD(x);
      const st = parseInt(String(router.query.stage || ''), 10);
      const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      if (st >= 1 && st <= STAGES.length) { setStage(st - 1); setPlaying(false); setDone(true); }
      else { setStage(0); setPlaying(!reduce); setDone(!!reduce); }
      setRun(r => r + 1);
    }).catch(e => setErr(String(e.message || e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady, stem, page]);

  // the clock: runs only while playing; moves the progress bar directly (no re-render per frame)
  useEffect(() => { elapsed.current = done ? STAGES[stage].ms : 0; if (bar.current) bar.current.style.width = done ? '100%' : '0%'; }, [stage, run, done]);
  useEffect(() => {
    if (!playing || !d) return;
    let raf = 0, last = performance.now();
    const tick = (now: number) => {
      elapsed.current += (now - last) * speed; last = now;
      const p = Math.min(1, elapsed.current / STAGES[stage].ms);
      if (bar.current) bar.current.style.width = `${p * 100}%`;
      if (p >= 1) {
        if (stage < STAGES.length - 1) { setStage(stage + 1); setDone(false); }
        else setPlaying(false);
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, stage, speed, run, d]);

  const go = useCallback((s: number) => {
    const n = Math.max(0, Math.min(STAGES.length - 1, s));
    setHover(null); setStage(n);
    if (!playing) setDone(true); else { setDone(false); setRun(r => r + 1); }
  }, [playing]);
  const toggle = () => {
    if (playing) { setPlaying(false); return; }
    if (stage === STAGES.length - 1 && elapsed.current >= STAGES[stage].ms && !done) { setStage(0); setDone(false); setRun(r => r + 1); setPlaying(true); return; }
    if (done) { setDone(false); setRun(r => r + 1); }   // a stage shown finished: play it from its start
    setPlaying(true);
  };
  const restart = () => { setStage(0); setDone(false); setRun(r => r + 1); setPlaying(true); };
  const changeSpeed = (x: number) => { setSpeed(x); if (!done) setRun(r => r + 1); };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest('input, select, textarea')) return;
      if (e.key === ' ') { e.preventDefault(); toggle(); }
      else if (e.key === 'ArrowRight') go(stage + 1);
      else if (e.key === 'ArrowLeft') go(stage - 1);
      else if (e.key === 'f') toggleFull();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
  useEffect(() => {
    const f = () => setFull(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', f);
    return () => document.removeEventListener('fullscreenchange', f);
  }, []);
  const toggleFull = () => {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else shell.current?.requestFullscreen?.().catch(() => setFull(f => !f));
  };
  const setPage = (st: string, p: number) => router.replace({ pathname: '/pipeline', query: { stem: st, page: p } }, undefined, { shallow: true, scroll: false });

  const S = STAGES[stage];
  const height = full ? 'calc(100vh - 232px)' : 'clamp(520px, calc(100vh - 272px), 900px)';
  return (
    <Layout wide>
      <div ref={shell} className={`pl-root space-y-4 ${full ? 'pl-full' : ''}`} style={{ '--k': 1 / speed } as V}>
        <div className="flex flex-wrap lg:flex-nowrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2"><Workflow className="w-5 h-5 text-teal-700" aria-hidden />How a page is read</h1>
            <p className="text-sm text-gray-500 mt-0.5">One real page through the pipeline that reads Mandumah&apos;s archive, from the scan to the index. Every box and number below is live data.</p>
          </div>
          <Picker stem={stem} page={page} d={d} onPick={setPage} />
        </div>

        {/* the stepper: seven stages, the current one filling as it plays */}
        <div className="bg-white border border-gray-200 rounded-xl p-2.5 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1">
            <button onClick={() => go(stage - 1)} className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" aria-label="Previous stage" title="Previous stage (←)"><SkipBack className="w-4 h-4" /></button>
            <button onClick={toggle} className="h-9 px-3.5 rounded-lg bg-teal-700 hover:bg-teal-800 text-white text-sm font-medium inline-flex items-center gap-1.5" data-testid="pl-play"
              aria-label={playing ? 'Pause' : 'Play'} title="Play / pause (space)">{playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}{playing ? 'Pause' : 'Play'}</button>
            <button onClick={() => go(stage + 1)} className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" aria-label="Next stage" title="Next stage (→)" data-testid="pl-step"><SkipForward className="w-4 h-4" /></button>
            <button onClick={restart} className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" aria-label="From the start" title="From the start"><RotateCcw className="w-4 h-4" /></button>
          </div>
          <ol className="flex-1 min-w-[640px] grid grid-cols-7 gap-1.5" aria-label="Stages">
            {STAGES.map((x, i) => (
              <li key={x.key}>
                <button onClick={() => go(i)} aria-current={i === stage ? 'step' : undefined} data-testid={`pl-stage-${i + 1}`}
                  className={`w-full text-left rounded-lg px-2 pt-1.5 pb-2 transition-colors ${i === stage ? 'bg-teal-50' : 'hover:bg-gray-50'}`}>
                  <div className="flex items-center gap-1.5">
                    <span className={`w-5 h-5 rounded-full grid place-items-center text-[11px] font-semibold shrink-0 ${i < stage ? 'bg-teal-700 text-white' : i === stage ? 'bg-white text-teal-800 ring-2 ring-teal-600' : 'bg-gray-100 text-gray-500'}`}>
                      {i < stage ? <Check className="w-3 h-3" /> : x.n}</span>
                    <span className={`text-[12.5px] font-medium truncate ${i <= stage ? 'text-gray-900' : 'text-gray-500'}`}>{x.short}</span>
                  </div>
                  <div className="mt-1.5 h-1 rounded-full bg-gray-100 overflow-hidden">
                    <div ref={i === stage ? bar : undefined} className="h-full bg-teal-600 rounded-full" style={{ width: i < stage ? '100%' : '0%' }} />
                  </div>
                </button>
              </li>
            ))}
          </ol>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-gray-200 p-0.5 text-xs" role="group" aria-label="Speed">
              {SPEEDS.map(x => <button key={x} onClick={() => changeSpeed(x)} aria-pressed={speed === x}
                className={`px-2 py-1 rounded-md tabular-nums ${speed === x ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-50'}`}>{x}×</button>)}
            </div>
            <button onClick={toggleFull} className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" aria-label={full ? 'Leave full screen' : 'Full screen'} title="Full screen (f)" data-testid="pl-full">
              {full ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}</button>
          </div>
        </div>

        {err && <ErrorBox>{err}</ErrorBox>}
        {!d && !err && <p className="text-sm text-gray-500">Loading the page…</p>}
        {d && (
          <div ref={rootRef} key={`${d.stem}-${d.page}-${stage}-${run}`} data-testid="pl-stage" data-stage={S.key}
            className={`relative flex gap-6 items-start ${playing ? '' : 'pl-paused'} ${done ? 'pl-done' : ''}`}>
            <PageCanvas d={d} s={stage} done={done} hover={hover} setHover={setHover} height={height} canvasRef={canvasRef} />
            <div className="flex-1 min-w-0 flex flex-col gap-3" style={{ height }}>
              <div className="pl-anim pl-rise" style={{ '--t': 500 } as V}>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-teal-700">Stage {S.n} of 7 · {S.title}</div>
                <p className="text-[17px] leading-snug text-gray-900 mt-0.5" data-testid="pl-caption">{S.caption}</p>
                <p className="text-xs text-gray-500 mt-1 leading-relaxed">{S.detail}</p>
              </div>
              <Tiles items={tilesFor(S.key, d)} k={S.key} />
              <div className="flex-1 min-h-0 overflow-auto pr-1">
                {S.key === 'scan' && <ScanPanel d={d} />}
                {S.key === 'azure' && <AzurePanel d={d} />}
                {S.key === 'gemini' && <GeminiPanel d={d} />}
                {S.key === 'rules' && <RulesPanel d={d} />}
                {S.key === 'judge' && <JudgePanel d={d} />}
                {S.key === 'platform' && <PlatformPanel d={d} hover={hover} setHover={setHover} canvasRef={canvasRef} rootRef={rootRef} onGhosts={setGhosts} done={done} />}
                {S.key === 'index' && <IndexPanel d={d} />}
              </div>
            </div>
            {S.key === 'platform' && !done && <GhostLayer ghosts={ghosts} />}
          </div>
        )}
      </div>
    </Layout>
  );
}

function Picker({ stem, page, d, onPick }: { stem: string; page: number; d: any; onPick: (stem: string, page: number) => void }) {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [hits, setHits] = useState<any[]>([]);
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => {
      api(`/articles?limit=12${q.trim() ? `&q=${enc(q.trim())}` : ''}`).then(x => setHits(x.articles || [])).catch(() => setHits([]));
    }, 220);
    return () => clearTimeout(t);
  }, [q, open]);
  const sg = d?.suggest || {};
  return (
    <div className="flex flex-col items-end gap-1.5 shrink-0">
      <div className="flex items-center gap-2">
        <div className="relative">
          <label className="relative block">
            <span className="sr-only">Choose an article</span>
            <Search className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" aria-hidden />
            <input value={q} onChange={e => setQ(e.target.value)} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 180)}
              placeholder={stem} dir="auto" data-testid="pl-pick"
              className="pl-8 pr-2 py-1.5 w-72 rounded-lg border-gray-300 text-sm" />
          </label>
          {open && hits.length > 0 && (
            <ul className="absolute right-0 z-30 mt-1 w-[28rem] max-h-80 overflow-auto bg-white border border-gray-200 rounded-xl shadow-lg py-1">
              {hits.map(h => (
                <li key={h.stem}><button onMouseDown={e => e.preventDefault()} onClick={() => { setOpen(false); setQ(''); onPick(h.stem, 1); }}
                  className="w-full text-left px-3 py-1.5 hover:bg-gray-50">
                  <div className={`text-sm text-gray-900 truncate ${isArabic(h.title) ? 'ar' : ''}`}>{h.title || h.stem}</div>
                  <div className="text-[11px] text-gray-500 font-mono">{h.stem}{h.year ? ` · ${h.year}` : ''}</div>
                </button></li>
              ))}
            </ul>
          )}
        </div>
        <label className="text-sm text-gray-600 flex items-center gap-1">Page
          <select value={page} onChange={e => onPick(stem, parseInt(e.target.value, 10))} className="rounded-lg border-gray-300 text-sm py-1.5" data-testid="pl-page">
            {Array.from({ length: d?.pages || page }).map((_, i) => <option key={i} value={i + 1}>{i + 1}</option>)}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap justify-end gap-1 max-w-[30rem]">
        {QUICK.filter(([k]) => sg[k]).map(([k, l]) => (
          <button key={k} onClick={() => onPick(stem, sg[k])} data-testid={`pl-quick-${k}`}
            className={`text-xs rounded-full border px-2.5 py-0.5 ${page === sg[k] ? 'bg-teal-700 border-teal-700 text-white' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}>{l} <span className="opacity-70">p.{sg[k]}</span></button>
        ))}
      </div>
    </div>
  );
}
