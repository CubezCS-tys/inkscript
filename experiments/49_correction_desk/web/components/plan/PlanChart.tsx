import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  BAR_H, C, LANE_COLOR, Layout, Marker, PlanData, Promise_, UK, dayLabel, ep, hm, layout, textMeasurer, tickStep,
  ticks, whenTz, whenUK,
} from './model';

// The plan's timeline (pages/plan.tsx): one lane per workstream, "Needs you" on top in orange; under them four strips:
// releases and deploys (diamonds and triangles), results (dots; milestones as stars), promises (flags at their due
// time, red when overdue) and alerts (red ticks). Solid bar = what happened; faint dashed = what was planned;
// running = striped and moving up to "now", with a pulsing dot; a stalled running bar (no sign of life for 60 min)
// is amber; live = solid to now with a green dot. Every bar carries its title, inside it when it fits, else beside it;
// bars whose titles would touch go on separate rows (model.layout), so nothing overlaps. Tap a bar or a marker for
// its card (onSelect). Axis in UK time; the server's time is in each tooltip.

export type Sel = { kind: 'item'; id: string } | { kind: 'marker'; m: Marker } | { kind: 'promise'; p: Promise_ }
  | { kind: 'release'; id: string; at: number; live: boolean } | { kind: 'deploy'; at: number; detail: string }
  | { kind: 'stall'; id: string; at: number };
const FONT = '600 11.5px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

const useReducedMotion = () => {
  const [r, setR] = useState(false);
  useEffect(() => {
    try { const mq = window.matchMedia('(prefers-reduced-motion: reduce)'); setR(mq.matches); } catch { /* none */ }
  }, []);
  return r;
};

const PlanChart: React.FC<{ d: PlanData; now: number; win: { start: number; end: number }; minWidth: number;
  selected: string | null; onSelect: (s: Sel | null) => void; needsExpanded: boolean; onToggleNeeds: () => void }> = ({ d, now, win, minWidth, selected, onSelect, needsExpanded, onToggleNeeds }) => {
  const box = useRef<HTMLDivElement>(null);
  const [boxW, setBoxW] = useState(0);
  const reduced = useReducedMotion();
  useEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    const on = () => setBoxW(el.clientWidth);
    on();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(on);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const width = Math.max(minWidth, boxW || minWidth);
  const L: Layout = useMemo(() => layout(d, win, now, width, textMeasurer(FONT), needsExpanded), [d, win, now, width, needsExpanded]);
  // first draw on a narrow screen: scroll so "now" sits two-thirds in
  const scrolled = useRef(false);
  useEffect(() => {
    const el = box.current;
    if (!el || !boxW || scrolled.current) return;
    if (width > boxW) el.scrollLeft = Math.max(0, L.x(now) - boxW * 0.66);
    scrolled.current = true;
  }, [boxW, width, L, now]);

  const x = L.x;
  const inWin = (t: number | null) => t != null && t >= win.start && t <= win.end;
  const pxPerHour = (width - 8) / ((win.end - win.start) / 3600);
  const step = tickStep(pxPerHour);
  const tks = ticks(win, step);
  const days = ticks(win, 24);
  const stale = new Set(d.live.stale);
  const tz = d.server_tz;
  const tip = (t: number) => `${whenUK(t)} UK · ${whenTz(tz, t)} server`;
  const hit = (s: Sel, key: string, name: string) => ({
    role: 'button', tabIndex: 0, 'aria-label': name, 'data-plan-hit': key, style: { cursor: 'pointer' },
    onClick: (e: React.MouseEvent) => { e.stopPropagation(); onSelect(s); },
    onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(s); } },
  });
  const strip = (k: string) => L.strips.find(s => s.key === k)!;
  const sRel = strip('releases'), sRes = strip('results'), sPro = strip('promises'), sAl = strip('alerts');

  // marker labels right of their mark, only when they fit before the next mark of the same strip
  const labelled = <T,>(ms: { t: number; text: string; v: T }[]) => {
    const s = [...ms].filter(m => inWin(m.t)).sort((a, b) => a.t - b.t);
    const m = textMeasurer('500 10.5px ui-sans-serif, system-ui, sans-serif');
    return s.map((mk, i) => {
      const lx = x(mk.t) + 9;
      const next = i + 1 < s.length ? x(s[i + 1].t) - 10 : width - 4;
      return { ...mk, x: x(mk.t), lx, show: lx + m(mk.text) <= next };
    });
  };
  const rels = labelled(d.live.releases.map(r => ({ t: r.at, text: r.live ? `${r.id} (live)` : r.id, v: r })));
  const deps = d.live.deploys.filter(x0 => inWin(x0.at));
  const evals = labelled(d.plan.markers.filter(m => m.kind === 'eval' || m.kind === 'milestone' || m.kind === 'release' || m.kind === 'deploy')
    .map(m => ({ t: ep(m.at)!, text: m.label, v: m })));
  const proms = labelled(d.plan.promises.filter(p => p.due || p.closed_at).map(p => ({ t: ep(p.due || p.closed_at)!, text: p.title, v: p })));
  const alerts = d.plan.markers.filter(m => m.kind === 'alert');
  const stalls = d.plan.items.filter(i => stale.has(i.id)).map(i => ({ i, at: (d.live.activity[i.id]?.at || now) + d.live.stale_after_s }));
  const overdue = new Set(d.live.overdue);

  return (
    <div className="flex" data-testid="plan-chart" onClick={() => onSelect(null)}>
      <div className="shrink-0 w-[118px] sm:w-[168px] relative border-r border-gray-200 bg-white" style={{ height: L.height }}>
        {L.lanes.map(l => (
          <div key={l.lane.key} className="absolute inset-x-0 px-2.5 sm:px-3 flex flex-col justify-center border-b border-gray-200"
            style={{ top: l.y, height: l.h, background: l.owner ? C.ownerBg : undefined }}>
            <div className="text-[12px] sm:text-[13px] font-semibold leading-tight flex items-center gap-1.5" style={{ color: l.owner ? C.owner : C.ink }}>
              {!l.owner && <span className="w-2 h-2 rounded-full shrink-0" style={{ background: LANE_COLOR[l.lane.key] }} aria-hidden />}{l.lane.label}</div>
            {l.lane.sub && <div className="text-[11px] leading-tight mt-0.5 text-gray-500 hidden sm:block">{l.lane.sub}</div>}
          </div>))}
        {L.strips.map(s => (
          <div key={s.key} className="absolute inset-x-0 px-2.5 sm:px-3 flex items-center text-[10.5px] font-semibold uppercase tracking-wide border-b border-gray-100"
            style={{ top: s.y, height: s.h, color: s.key === 'alerts' ? C.alert : C.muted }}>{s.label}</div>))}
      </div>

      <div ref={box} className="overflow-x-auto overscroll-x-contain min-w-0 flex-1" data-testid="plan-scroll">
        <svg width={width} height={L.height} role="img" aria-label="Timeline of the project's work, UK time" style={{ display: 'block' }}>
          <defs>
            <pattern id="pl-stripes" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="10" fill="rgba(255,255,255,0.42)" />
              {!reduced && <animateTransform attributeName="patternTransform" type="translate" additive="sum" from="0 0" to="10 0" dur="0.9s" repeatCount="indefinite" />}
            </pattern>
            <pattern id="pl-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="2" height="6" fill={C.grey} opacity="0.55" />
            </pattern>
          </defs>
          {L.lanes.filter(l => l.owner).map(l => <rect key={`ob${l.lane.key}`} x={0} y={l.y} width={width} height={l.h} fill={C.ownerBg} pointerEvents="none" />)}
          {/* the future, faintly */}
          {inWin(now) && <rect x={x(now)} y={AXIS_TOP} width={Math.max(0, width - x(now))} height={L.lanesBottom - AXIS_TOP} fill="#f8fafc" pointerEvents="none" />}

          {/* grid and axis (UK) */}
          {tks.map(t => (
            <g key={`t${t.t}`}>
              <line x1={x(t.t)} x2={x(t.t)} y1={AXIS_TOP} y2={L.height - 22} stroke={C.rule} strokeWidth={t.midnight ? 1.4 : 1} />
              {step < 24 && x(t.t) > 20 && x(t.t) < width - 20 && <text x={x(t.t)} y={AXIS_TOP - 5} textAnchor="middle" fontSize={10.5} fill={C.muted}
                style={{ fontVariantNumeric: 'tabular-nums' }}>{hm(UK, t.t)}</text>}
            </g>))}
          {(step < 24 ? days : tks).map((t, i, arr) => {
            const nx = i + 1 < arr.length ? x(arr[i + 1].t) : width;
            const lab = dayLabel(UK, t.t);
            return nx - x(t.t) > 34 && x(t.t) < width - 30 ? <text key={`d${t.t}`} x={x(t.t) + 4} y={step < 24 ? 13 : AXIS_TOP - 7} fontSize={11.5} fontWeight={600} fill={C.ink}>
              {nx - x(t.t) > 70 ? lab : lab.split(' ').slice(1).join(' ')}</text> : null;
          })}
          {step < 24 && !(days.length && x(days[0].t) < 80) && <text x={6} y={13} fontSize={11.5} fontWeight={600} fill={C.ink}>{dayLabel(UK, win.start)}</text>}
          {[...L.lanes.map(l => l.y + l.h), ...L.strips.map(s => s.y + s.h)].map((yy, i) => (
            <line key={`r${i}`} x1={0} x2={width} y1={yy} y2={yy} stroke={C.rule} />))}

          {/* releases reach up through the lanes, faintly */}
          {rels.map(r => <line key={`rl${r.v.id}`} x1={r.x} x2={r.x} y1={AXIS_TOP} y2={sRel.y + 6} stroke="#0d9488" strokeDasharray="2 4" opacity={0.45} />)}

          {/* now (under the bars, so titles stay readable; the caption is at the bottom) */}
          {inWin(now) && <g data-testid="plan-now">
            <line x1={x(now)} x2={x(now)} y1={AXIS_TOP - 4} y2={L.height - 18} stroke={C.now} strokeWidth={2} />
            <text x={x(now) + (x(now) > width - 60 ? -4 : 4)} textAnchor={x(now) > width - 60 ? 'end' : 'start'} y={L.height - 6} fontSize={11} fontWeight={600} fill={C.now}>now {hm(UK, now)} UK</text>
          </g>}

          {/* bars */}
          {L.bars.map(b => {
            const it = b.item;
            if (it.synthetic) {
              const s0 = b.solid!;
              return (
                <g key={it.id} role="button" tabIndex={0} aria-expanded={needsExpanded} data-item="__more-needs" style={{ cursor: 'pointer' }}
                  onClick={e => { e.stopPropagation(); onToggleNeeds(); }} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggleNeeds(); } }}>
                  <title>{needsExpanded ? 'Fold the less urgent items into one row' : 'Show everything waiting on you'}</title>
                  <rect x={s0[0]} y={b.y + 2} width={Math.max(s0[1] - s0[0], 4)} height={BAR_H - 4} rx={9} fill="#fff" stroke={C.owner} strokeOpacity={0.6} strokeDasharray="4 3" />
                  <text x={b.labelX} y={b.y + BAR_H / 2 + 4} fontSize={11.5} fontWeight={600} fill="#9a3412" pointerEvents="none">{b.label}</text>
                </g>);
            }
            const owner = it.lane === 'needs_you';
            const isStale = it.status === 'running' && stale.has(it.id);
            const col = isStale ? C.stale : owner ? C.owner : ['parked', 'dropped'].includes(it.status) ? C.grey : LANE_COLOR[it.lane] || C.muted;
            const resolved = owner && it.status !== 'blocked-on-owner';
            const s = b.solid, f = b.faint;
            const running = it.status === 'running';
            const edge = running && s ? Math.max(s[0], s[1] - 34) : null;
            const sel = selected === `item:${it.id}`;
            const ext = [Math.min(s?.[0] ?? 1e9, f?.[0] ?? 1e9), Math.max(s?.[1] ?? -1e9, f?.[1] ?? -1e9)];
            const st = ep(it.start), en = ep(it.end);
            const tt = `${it.title}${st ? ` · from ${tip(st)}` : ''}${en ? ` · to ${tip(en)}` : ''}`;
            return (
              <g key={it.id} {...hit({ kind: 'item', id: it.id }, key(it), `${it.title}, ${it.status}`)} data-item={it.id} data-status={it.status}
                data-label-inside={b.labelInside ? '1' : '0'}>
                <title>{tt}</title>
                {f && <rect x={f[0]} y={b.y} width={Math.max(f[1] - f[0], 4)} height={BAR_H} rx={5} fill={col} fillOpacity={0.12}
                  stroke={col} strokeOpacity={0.75} strokeDasharray="4 3" />}
                {s && <rect x={s[0]} y={b.y} width={Math.max(s[1] - s[0], 4)} height={BAR_H} rx={5}
                  fill={it.status === 'parked' || it.status === 'dropped' ? 'url(#pl-hatch)' : owner ? (resolved ? '#f3f4f6' : '#fed7aa') : col}
                  stroke={it.status === 'parked' || it.status === 'dropped' ? C.grey : owner ? (resolved ? '#d1d5db' : C.owner) : 'none'} strokeWidth={owner ? 1.2 : 1} />}
                {s && edge != null && <>
                  <rect x={edge} y={b.y} width={Math.max(s[1] - edge, 2)} height={BAR_H} fill="url(#pl-stripes)" />
                  {inWin(now) && <circle cx={s[1]} cy={b.y + BAR_H / 2} r={4} fill={isStale ? C.stale : C.now}>
                    {!reduced && !isStale && <animate attributeName="r" values="3;5.5;3" dur="1.6s" repeatCount="indefinite" />}
                  </circle>}
                </>}
                {s && it.status === 'live' && inWin(now) && <circle cx={s[1] - 6} cy={b.y + BAR_H / 2} r={3.5} fill="#fff" stroke={C.live} strokeWidth={2} />}
                {b.dueX != null && <line x1={b.dueX} x2={b.dueX} y1={b.y - 3} y2={b.y + BAR_H + 3} stroke={C.owner} strokeWidth={2} />}
                {sel && <rect x={ext[0] - 2} y={b.y - 2} width={ext[1] - ext[0] + 4} height={BAR_H + 4} rx={7} fill="none" stroke={C.ink} strokeWidth={1.5} />}
                <text x={b.labelX} y={b.y + BAR_H / 2 + 4} fontSize={11.5} fontWeight={600} pointerEvents="none"
                  stroke={b.labelInside ? undefined : owner ? C.ownerBg : '#fff'} strokeWidth={b.labelInside ? undefined : 3.5} paintOrder="stroke" strokeLinejoin="round"
                  fill={owner ? (resolved ? C.muted : '#7c2d12') : b.labelInside && !['parked', 'dropped'].includes(it.status) ? '#fff' : C.ink}
                  textDecoration={it.status === 'dropped' ? 'line-through' : undefined}>{b.label}</text>
              </g>);
          })}

          {/* releases (diamonds; the live one filled teal with a ring) and deploys of the live web (triangles) */}
          {rels.map(r => {
            const cy = sRel.y + sRel.h / 2;
            return (
              <g key={`r${r.v.id}`} {...hit({ kind: 'release', id: r.v.id, at: r.v.at, live: r.v.live }, `release:${r.v.id}`, `Release ${r.v.id}`)} data-release={r.v.id}>
                <title>{`Desk release ${r.v.id}${r.v.live ? ' (live)' : ''} · ${tip(r.v.at)}`}</title>
                <path d={`M${r.x} ${cy - 6} L${r.x + 6} ${cy} L${r.x} ${cy + 6} L${r.x - 6} ${cy} Z`} fill={r.v.live ? '#0d9488' : '#fff'} stroke="#0d9488" strokeWidth={1.6} />
                {r.show && <text x={r.lx} y={cy + 3.5} fontSize={10} fill={C.muted} pointerEvents="none" style={{ fontFamily: 'ui-monospace, Menlo, monospace' }}>{r.text}</text>}
              </g>);
          })}
          {deps.map((dp, i) => {
            const cx = x(dp.at), cy = sRel.y + sRel.h / 2;
            return (
              <g key={`dp${i}`} {...hit({ kind: 'deploy', at: dp.at, detail: dp.detail }, `deploy:${i}`, 'Live Desk rebuilt')} data-deploy="1">
                <title>{`Live Desk rebuilt · ${tip(dp.at)}`}</title>
                <path d={`M${cx} ${cy - 7} L${cx + 6} ${cy + 5} L${cx - 6} ${cy + 5} Z`} fill="#4f46e5" opacity={0.85} />
              </g>);
          })}

          {/* results (dots) and milestones (stars) */}
          {evals.map(e => {
            const cy = sRes.y + sRes.h / 2;
            const ms = e.v.kind === 'milestone';
            return (
              <g key={`e${e.v.id}`} {...hit({ kind: 'marker', m: e.v }, `marker:${e.v.id}`, e.v.label)} data-marker={e.v.kind}>
                <title>{`${e.v.label} · ${tip(e.t)}`}</title>
                {ms ? <path d={star(e.x, cy, 6.5)} fill="#4f46e5" /> : <circle cx={e.x} cy={cy} r={4.5} fill="#059669" />}
                {e.show && <text x={e.lx} y={cy + 3.5} fontSize={10.5} fill={C.muted} pointerEvents="none">{e.text}</text>}
              </g>);
          })}

          {/* promises: a flag at the due time; red when overdue, green when kept */}
          {proms.map(p => {
            const cy = sPro.y + sPro.h / 2;
            const late = overdue.has(p.v.id);
            const c = late ? C.alert : p.v.status === 'kept' ? C.live : p.v.status === 'dropped' ? C.grey : '#4f46e5';
            return (
              <g key={`p${p.v.id}`} {...hit({ kind: 'promise', p: p.v }, `promise:${p.v.id}`, p.v.title)} data-promise={p.v.status}>
                <title>{`${p.v.title} · ${p.v.due ? `due ${tip(p.t)}` : `kept ${tip(p.t)}`}`}</title>
                <line x1={p.x} x2={p.x} y1={cy - 8} y2={cy + 8} stroke={c} strokeWidth={late ? 2.5 : 1.6} />
                <path d={`M${p.x} ${cy - 8} L${p.x + 8} ${cy - 5} L${p.x} ${cy - 2} Z`} fill={c} />
                {p.show && <text x={p.lx + 2} y={cy + 4} fontSize={10.5} fill={late ? C.alert : C.muted} pointerEvents="none">{p.text}</text>}
              </g>);
          })}

          {/* alerts: red ticks (from the plan's record), stalled running work, overdue promises */}
          {alerts.map(a => {
            const t0 = ep(a.at)!, t1 = ep(a.end) ?? t0;
            if (!inWin(t0) && !inWin(t1)) return null;
            const cy = sAl.y + sAl.h / 2;
            return (
              <g key={`a${a.id}`} {...hit({ kind: 'marker', m: a }, `marker:${a.id}`, `Alert: ${a.label}`)} data-alert="record">
                <title>{`${a.label} · ${tip(t0)}`}</title>
                <rect x={x(t0)} y={cy - 3} width={Math.max(x(t1) - x(t0), 2)} height={6} rx={2} fill={C.alert} opacity={0.35} />
                <line x1={x(t0)} x2={x(t0)} y1={cy - 9} y2={cy + 9} stroke={C.alert} strokeWidth={2} />
              </g>);
          })}
          {stalls.map(s => inWin(s.at) && (
            <g key={`st${s.i.id}`} {...hit({ kind: 'stall', id: s.i.id, at: s.at }, `stall:${s.i.id}`, `No sign of life: ${s.i.title}`)} data-alert="stall">
              <title>{`No sign of life from "${s.i.title}" for an hour · ${tip(s.at)}`}</title>
              <line x1={x(s.at)} x2={x(s.at)} y1={sAl.y + 6} y2={sAl.y + sAl.h - 6} stroke={C.stale} strokeWidth={2.5} />
            </g>))}
          {proms.filter(p => overdue.has(p.v.id)).map(p => (
            <line key={`od${p.v.id}`} x1={p.x} x2={p.x} y1={sAl.y + 6} y2={sAl.y + sAl.h - 6} stroke={C.alert} strokeWidth={2.5} />))}

        </svg>
      </div>
    </div>
  );
};

const AXIS_TOP = 30;
const key = (it: { id: string }) => `item:${it.id}`;
const star = (cx: number, cy: number, r: number) => {
  const pts: string[] = [];
  for (let i = 0; i < 10; i++) {
    const a = (Math.PI / 5) * i - Math.PI / 2, rr = i % 2 ? r * 0.45 : r;
    pts.push(`${(cx + rr * Math.cos(a)).toFixed(1)} ${(cy + rr * Math.sin(a)).toFixed(1)}`);
  }
  return `M${pts.join(' L')} Z`;
};
export default PlanChart;
