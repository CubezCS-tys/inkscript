import React, { useMemo, useState } from 'react';
import { Box, roleColor, FIELD_KIND } from './defs';

// The scan with what each stage adds on top of it, drawn in the page's own frame (the ALTO pixel frame), so every
// box sits on its ink whatever the size on screen. Stage index s: 0 scan, 1 Azure, 2 Gemini, 3 rules, 4 judge,
// 5 platform, 6 index. Times are ms at 1x (the CSS multiplies them by 1 / speed).

type V = React.CSSProperties & Record<string, any>;
const css = (o: Record<string, any>): V => o as V;
const union = (bs: Box[]): Box | null => {
  if (!bs || !bs.length) return null;
  const x0 = Math.min(...bs.map(b => b.x)), y0 = Math.min(...bs.map(b => b.y));
  const x1 = Math.max(...bs.map(b => b.x + b.w)), y1 = Math.max(...bs.map(b => b.y + b.h));
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
};
export { union };

export function fieldTimes(n: number) {
  const per = Math.min(950, 8200 / Math.max(1, n));
  return { per, start: 500, fly: Math.min(1100, Math.max(700, per * 1.2)) };
}

export default function PageCanvas({ d, s, done, hover, setHover, height, canvasRef }: {
  d: any; s: number; done: boolean; hover: string | null; setHover: (h: string | null) => void; height: string;
  canvasRef: React.RefObject<HTMLDivElement>;
}) {
  const W = d.frame.w, H = d.frame.h;
  const u = W / 500;                                 // one "unit": ~1/500 of the page width
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const lines: any[] = d.lines;
  const words: any[] = d.words;
  const gb: any[] = d.answer.blocks;
  const lineBy = useMemo(() => Object.fromEntries(lines.map(l => [l.n, l])), [lines]);

  // reading order: the centre of each block's lines, page furniture left out
  const path = useMemo(() => {
    const pts = gb.filter(b => !['running', 'page_number', 'noise', 'other_article'].includes(b.role) && b.lines.length)
      .map(b => union(b.lines.map((n: number) => lineBy[n]).filter(Boolean)))
      .filter(Boolean).map((b: any) => [b.x + b.w / 2, b.y + b.h / 2]);
    let len = 0;
    for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    return { pts, len: Math.ceil(len) + 1, d: pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(0)},${p[1].toFixed(0)}`).join(' ') };
  }, [gb, lineBy]);

  // line labels "page:line", placed at the right of each line, never on top of each other
  const labels = useMemo(() => {
    const fs = 9.5 * u, out: any[] = [], placed: Box[] = [];
    for (const l of lines) {
      const text = `${d.page}:${l.n}`;
      const w = text.length * fs * 0.62 + 6 * u, h = fs * 1.35;
      let x = l.x + l.w + 3 * u;
      if (x + w > W - 2 * u) x = Math.max(2 * u, l.x - w - 3 * u);
      const y = l.y + l.h / 2 - h / 2;
      const b = { x, y, w, h };
      if (placed.some(p => !(b.x + b.w < p.x || p.x + p.w < b.x || b.y + b.h < p.y || p.y + p.h < b.y))) continue;
      placed.push(b);
      out.push({ ...b, text, fs, n: l.n });
    }
    return out;
  }, [lines, u, W, d.page]);

  const N = words.length || 1;
  const nb = gb.length || 1;
  const blockDelay = (i: number) => 300 + i * (5800 / nb);
  const fields: any[] = d.fields;
  const ft = fieldTimes(fields.length);
  const hovered = fields.find(f => f.id === hover);
  const showTip = (e: React.MouseEvent, text: string) => {
    const r = canvasRef.current?.getBoundingClientRect();
    if (r) setTip({ x: e.clientX - r.left, y: e.clientY - r.top, text });
  };

  return (
    <div ref={canvasRef} className="relative rounded-xl overflow-hidden bg-white border border-gray-200 shadow-sm shrink-0"
      style={{ height, aspectRatio: `${W} / ${H}` }} onMouseLeave={() => { setTip(null); }} data-testid="pl-canvas">
      {d.image ? (
        <img src={d.image_url} alt={`Page ${d.page} of ${d.stem}, as scanned`} draggable={false}
          className={`absolute inset-0 w-full h-full select-none ${s === 0 ? 'pl-anim pl-fade' : ''}`} style={css({ '--t': 1500 })} />
      ) : (
        <div className="absolute inset-0 grid place-items-center text-sm text-gray-500 crop-empty">The page image is not on this server</div>
      )}
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 w-full h-full" aria-hidden>
        <defs>
          <pattern id="pl-hatch" width={8 * u} height={8 * u} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width={8 * u} height={8 * u} fill="#f1f5f9" fillOpacity={0.55} />
            <line x1="0" y1="0" x2="0" y2={8 * u} stroke="#94a3b8" strokeWidth={2.2 * u} strokeOpacity={0.45} />
          </pattern>
          <marker id="pl-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#a21caf" />
          </marker>
          <linearGradient id="pl-scanlight" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#14b8a6" stopOpacity="0" />
            <stop offset="0.85" stopColor="#14b8a6" stopOpacity="0.16" />
            <stop offset="1" stopColor="#0f766e" stopOpacity="0.55" />
          </linearGradient>
        </defs>

        {/* 1 · the scan: a light passes down the page once */}
        {s === 0 && !done && (
          <rect className="pl-anim pl-sweep" x={0} y={-H * 0.12} width={W} height={H * 0.12} fill="url(#pl-scanlight)"
            style={css({ '--t': 2600, '--d': 300, '--dist': `${H * 1.12}px`, opacity: 0 })} />
        )}

        {/* 2 · Azure: every word's box, then the line numbers */}
        {(s === 1 || s === 2) && (
          <g style={{ opacity: s === 2 ? 0.1 : 1, transition: 'opacity .8s' }}>
            {words.map((w, i) => (
              <rect key={w.n} className={s === 1 ? 'pl-anim pl-pop' : ''} x={w.x} y={w.y} width={w.w} height={w.h} rx={u}
                fill="#0f766e" fillOpacity={0.07} stroke="#0f766e" strokeWidth={1} vectorEffect="non-scaling-stroke"
                style={css({ '--d': 200 + (i / N) * 4000, '--t': 450 })} />
            ))}
          </g>
        )}
        {(s === 1 || s === 2) && (
          <g className={s === 2 ? 'pl-anim pl-dim' : ''} style={css({ '--d': 6300, '--t': 900, opacity: s === 2 && done ? 0.28 : undefined })}>
            {labels.map((b, i) => (
              <g key={b.n} className={s === 1 ? 'pl-anim pl-fade' : ''} style={css({ '--d': 4600 + i * (2000 / labels.length), '--t': 400 })}>
                <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={b.h / 2} fill="#ffffff" fillOpacity={0.94} stroke="#99f6e4" strokeWidth={1} vectorEffect="non-scaling-stroke" />
                <text x={b.x + b.w / 2} y={b.y + b.h * 0.72} fontSize={b.fs} textAnchor="middle" fill="#0f766e"
                  style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontWeight: 600 }}>{b.text}</text>
              </g>
            ))}
          </g>
        )}

        {/* 3 · Gemini: each line coloured by its role, block by block in reading order; then the reading path */}
        {s === 2 && (
          <g>
            {gb.map((b, i) => b.lines.map((n: number, j: number) => {
              const l = lineBy[n];
              if (!l) return null;
              const c = roleColor(b.role);
              const rtl = (b.lang || 'ar') === 'ar' && /[؀-ۿ]/.test(l.text || '');
              return (
                <rect key={`${i}-${n}`} className={`pl-anim ${rtl ? 'pl-grow-r' : 'pl-grow-l'}`} x={l.x} y={l.y} width={l.w} height={l.h} rx={1.5 * u}
                  fill={c} fillOpacity={0.3} stroke={c} strokeOpacity={0.9} strokeWidth={1.3} vectorEffect="non-scaling-stroke"
                  style={css({ '--d': blockDelay(i) + j * 70, '--t': 520 })}
                  onMouseMove={e => showTip(e, `${d.page}:${n} · ${d.role_labels[b.role] || b.role}`)} onMouseLeave={() => setTip(null)} />
              );
            }))}
            {path.pts.length > 1 && (
              <g>
                <path d={path.d} fill="none" stroke="#4338ca" strokeWidth={2.4 * u} strokeLinecap="round" strokeLinejoin="round" strokeOpacity={0.85}
                  className="pl-anim pl-draw" strokeDasharray={path.len}
                  style={css({ '--d': 6600, '--t': 3000, '--len': path.len, strokeDashoffset: 0 })} />
                {path.pts.map((p, i) => (
                  <g key={i} className="pl-anim pl-pop" style={css({ '--d': 6600 + (i / Math.max(1, path.pts.length - 1)) * 3000, '--t': 350 })}>
                    <circle cx={p[0]} cy={p[1]} r={9 * u} fill="#4338ca" stroke="#fff" strokeWidth={2} vectorEffect="non-scaling-stroke" />
                    <text x={p[0]} y={p[1] + 3.6 * u} fontSize={10 * u} textAnchor="middle" fill="#fff" fontWeight={600}>{i + 1}</text>
                  </g>
                ))}
              </g>
            )}
          </g>
        )}

        {/* 4 · code: blocks built, page furniture kept out, fixes, misprints, flags */}
        {(s === 3 || s === 4) && (
          <g style={{ opacity: s === 4 ? 0.55 : 1, transition: 'opacity .8s' }}>
            {d.blocks.map((b: any, i: number) => b.boxes.map((x: Box, j: number) => (
              <rect key={`${b.id}-${j}`} className={s === 3 ? 'pl-anim pl-pop' : ''} x={x.x - 3 * u} y={x.y - 3 * u} width={x.w + 6 * u} height={x.h + 6 * u} rx={3 * u}
                fill={roleColor(b.shown)} fillOpacity={0.1} stroke={roleColor(b.shown)} strokeWidth={1.6} vectorEffect="non-scaling-stroke"
                style={css({ '--d': 200 + i * (3200 / Math.max(1, d.blocks.length)), '--t': 600 })}
                onMouseMove={e => showTip(e, `${b.id} · ${b.role}`)} onMouseLeave={() => setTip(null)} />
            )))}
            {d.regions.map((r: any, i: number) => (
              <g key={r.id} className={s === 3 ? 'pl-anim pl-fade' : ''} style={css({ '--d': 3700 + i * 250, '--t': 600 })}
                onMouseMove={e => showTip(e, `Kept out of the text: ${d.role_labels[r.shown] || r.role}${r.text ? ` «${r.text}»` : ''}`)} onMouseLeave={() => setTip(null)}>
                <rect x={r.box.x - 3 * u} y={r.box.y - 3 * u} width={r.box.w + 6 * u} height={r.box.h + 6 * u} rx={3 * u} fill="url(#pl-hatch)" stroke="#94a3b8"
                  strokeDasharray="4 3" strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
              </g>
            ))}
            {d.fixes.map((f: any, i: number) => (
              <g key={`fx${i}`} className={s === 3 ? 'pl-anim pl-pop' : ''} style={css({ '--d': 4800 + i * (1500 / Math.max(1, d.fixes.length)), '--t': 450 })}
                onMouseMove={e => showTip(e, `Azure read «${f.azure}», the print says «${f.printed}»${f.why ? ` · ${f.why.replace(/^code: /, '')}` : ''}`)} onMouseLeave={() => setTip(null)}>
                <rect x={f.box.x - 2 * u} y={f.box.y - 2 * u} width={f.box.w + 4 * u} height={f.box.h + 4 * u} rx={2 * u} fill="#16a34a" fillOpacity={0.16}
                  stroke="#15803d" strokeWidth={1.6} vectorEffect="non-scaling-stroke" />
              </g>
            ))}
            {d.misprints.map((f: any, i: number) => (
              <g key={`mp${i}`} className={s === 3 ? 'pl-anim pl-pop' : ''} style={css({ '--d': 5600 + i * 200, '--t': 450 })}
                onMouseMove={e => showTip(e, `Printed «${f.printed}», kept as printed; proposed «${f.proposed}»`)} onMouseLeave={() => setTip(null)}>
                <rect x={f.box.x - 2 * u} y={f.box.y - 2 * u} width={f.box.w + 4 * u} height={f.box.h + 4 * u} rx={2 * u} fill="#4338ca" fillOpacity={0.1}
                  stroke="#4338ca" strokeDasharray="3 2" strokeWidth={1.6} vectorEffect="non-scaling-stroke" />
              </g>
            ))}
            {d.flags.map((f: any, i: number) => f.boxes.map((x: Box, j: number) => (
              <rect key={`fl${i}-${j}`} className={s === 3 ? 'pl-anim pl-fade' : ''} x={x.x - 5 * u} y={x.y - 5 * u} width={x.w + 10 * u} height={x.h + 10 * u} rx={4 * u}
                fill="none" stroke="#dc2626" strokeWidth={2} strokeDasharray="6 4" vectorEffect="non-scaling-stroke"
                style={css({ '--d': 6400 + i * 200, '--t': 500 })} onMouseMove={e => showTip(e, `Flag (${f.severity}): ${f.reason}`)} onMouseLeave={() => setTip(null)} />
            )))}
          </g>
        )}

        {/* 5 · the judge: a second look passes over a page it was asked to check */}
        {s === 4 && !done && d.counts.judge.this_page && (
          <rect className="pl-anim pl-sweep" x={0} y={-H * 0.1} width={W} height={H * 0.1} fill="url(#pl-scanlight)"
            style={css({ '--t': 3000, '--d': 400, '--dist': `${H * 1.1}px`, opacity: 0 })} />
        )}
        {s === 4 && d.judge.findings.map((f: any, i: number) => f.boxes.map((x: Box, j: number) => (
          <rect key={`jf${i}-${j}`} className="pl-anim pl-pop" x={x.x - 5 * u} y={x.y - 5 * u} width={x.w + 10 * u} height={x.h + 10 * u} rx={4 * u}
            fill="#4338ca" fillOpacity={0.08} stroke="#4338ca" strokeWidth={2} vectorEffect="non-scaling-stroke" style={css({ '--d': 2600 + i * 300, '--t': 500 })} />
        )))}

        {/* 6 · each field lights up as it leaves the page; 7 · every field stays traceable to its ink */}
        {(s === 5 || s === 6) && fields.map((f, i) => {
          const c = (FIELD_KIND[f.kind] || {}).color || '#475569';
          return f.boxes.map((x: Box, j: number) => (
            <rect key={`${f.id}-${j}`} className={s === 5 ? 'pl-anim pl-flash' : ''} x={x.x - 3 * u} y={x.y - 3 * u} width={x.w + 6 * u} height={x.h + 6 * u} rx={3 * u}
              fill={c} fillOpacity={0.07} stroke={c} strokeOpacity={0.55} strokeWidth={1.2} vectorEffect="non-scaling-stroke"
              style={css({ '--d': ft.start + i * ft.per, '--t': ft.fly + 900, cursor: 'pointer' })}
              onMouseEnter={() => setHover(f.id)} onMouseLeave={() => setHover(null)} />
          ));
        })}
        {(s === 5 || s === 6) && fields.filter(f => f.kind === 'footnote' && f.call && f.boxes.length).map((f) => {
          const i = fields.indexOf(f);
          const a = f.call, b = union(f.boxes)!;
          const x1 = a.x + a.w / 2, y1 = a.y + a.h, x2 = Math.min(Math.max(x1, b.x + 20 * u), b.x + b.w - 20 * u), y2 = b.y - 4 * u;
          const len = Math.ceil(Math.hypot(x2 - x1, y2 - y1) * 1.25);
          const mx = (x1 + x2) / 2 + (x1 > W / 2 ? 40 : -40) * u;
          return (
            <g key={`call-${f.id}`}>
              <rect x={a.x - 3 * u} y={a.y - 3 * u} width={a.w + 6 * u} height={a.h + 6 * u} rx={4 * u} fill="#a21caf" fillOpacity={0.15} stroke="#a21caf" strokeWidth={1.6} vectorEffect="non-scaling-stroke"
                className={s === 5 ? 'pl-anim pl-pop' : ''} style={css({ '--d': ft.start + i * ft.per, '--t': 500 })} />
              <path d={`M${x1},${y1} Q${mx},${(y1 + y2) / 2} ${x2},${y2}`} fill="none" stroke="#a21caf" strokeWidth={2 * u} strokeLinecap="round" markerEnd="url(#pl-arrow)"
                className={s === 5 ? 'pl-anim pl-draw' : ''} strokeDasharray={len} style={css({ '--d': ft.start + i * ft.per + 300, '--t': 1200, '--len': len, strokeDashoffset: 0 })} />
            </g>
          );
        })}
        {hovered && hovered.boxes.map((x: Box, j: number) => (
          <rect key={`hv${j}`} x={x.x - 5 * u} y={x.y - 5 * u} width={x.w + 10 * u} height={x.h + 10 * u} rx={4 * u}
            fill={(FIELD_KIND[hovered.kind] || {}).color || '#4338ca'} fillOpacity={0.18} stroke={(FIELD_KIND[hovered.kind] || {}).color || '#4338ca'}
            strokeWidth={2.5} vectorEffect="non-scaling-stroke" pointerEvents="none" />
        ))}
      </svg>
      {s === 4 && !d.counts.judge.this_page && (
        <div className="absolute left-1/2 -translate-x-1/2 bottom-5 pl-anim pl-rise bg-white/95 border border-gray-200 shadow-sm rounded-full px-4 py-1.5 text-xs text-gray-700 whitespace-nowrap"
          style={css({ '--d': 500, '--t': 600 })}>
          {d.counts.rules.flags ? 'This page has flags' : 'No flags on this page, so the judge did not need to look'}
        </div>
      )}
      {tip && (
        <div className="absolute z-10 pointer-events-none max-w-[18rem] text-xs bg-gray-900/90 text-white rounded-md px-2 py-1 shadow"
          style={{ left: Math.min(tip.x + 12, (canvasRef.current?.clientWidth || 400) - 200), top: tip.y + 14 }} dir="auto">{tip.text}</div>
      )}
    </div>
  );
}
