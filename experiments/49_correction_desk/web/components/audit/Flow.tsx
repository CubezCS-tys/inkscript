import React, { useEffect, useMemo, useRef, useState } from 'react';
import { fieldLabel, geminiLabel, platLabel, STORED, GREY, RED } from './defs';

// The article's flow, left to right: Azure's lines → the role Gemini gave each line → the JATS field it landed in →
// the platform record that holds it. Stream widths are lines (or words). Red streams fell through (generic text
// only, or nowhere); grey streams are ink that is not article text. A click on a stream or a box selects its lines.

export type FlowRow = { gemini: string; jats: string; bucket: string; plat: string; words: number; lines: number; refs: string[] };
type Node = { id: string; col: number; key: string; label: string; value: number; kind: 'src' | 'gem' | 'ok' | 'grey' | 'leak' | 'plat'; flows: number[]; y: number; h: number };
type Link = { a: Node; b: Node; value: number; flows: number[]; leak: boolean; grey: boolean; sa: number; sb: number; ta: number; tb: number };

const COLS = ['The printed lines', 'What each line is', 'The article file', 'The index'];
const H = 500, GAP = 7, MIN = 16, NODE_W = 11;

function jKey(f: FlowRow) { return f.bucket === 'a' ? f.jats : f.bucket === 'c' ? 'not article text' : f.bucket === 'd' ? 'nowhere' : 'generic text'; }

export default function Flow({ flows, metric, selected, onSelect }: {
  flows: FlowRow[]; metric: 'lines' | 'words'; selected: string | null; onSelect: (key: string, flowIdx: number[], label: string) => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(980);
  const [hover, setHover] = useState<string | null>(null);
  useEffect(() => {
    const el = wrap.current; if (!el) return;
    const ro = new ResizeObserver(() => setW(Math.max(720, el.clientWidth)));
    ro.observe(el); return () => ro.disconnect();
  }, []);

  const { nodes, links } = useMemo(() => layout(flows, metric, W), [flows, metric, W]);
  const xs = colX(W);
  const isSel = (k: string) => selected === k;
  return (
    <div ref={wrap} className="w-full overflow-x-auto">
      <svg width={W} height={H + 34} role="img" aria-label="Where the article's lines went" className="au-flow block">
        <defs>
          <clipPath id="au-reveal"><rect className="au-reveal" x={0} y={0} width={W} height={H + 34} /></clipPath>
        </defs>
        {COLS.map((c, i) => (
          <text key={c} x={xs[i] + (i === 3 ? 0 : 0)} y={12} className="fill-gray-500" fontSize={11} fontWeight={600} letterSpacing=".04em">{c.toUpperCase()}</text>
        ))}
        <g transform="translate(0,26)">
          <g clipPath="url(#au-reveal)">
            {links.map((l, i) => {
              const k = `L:${l.a.id}>${l.b.id}`;
              const color = l.leak ? RED : l.grey ? '#9aa1a9' : l.a.col === 0 ? '#6366f1' : STORED;
              const on = isSel(k) || hover === k || (selected === 'leaks' && l.leak);
              const dim = (selected || hover) && !on && !(selected && (isSel(l.a.id) || isSel(l.b.id)));
              const t0 = l.leak ? Math.max(4, l.ta) : l.ta, t1 = l.leak ? Math.max(4, l.tb) : l.tb;
              return (
                <path key={k} d={ribbon(xs[l.a.col] + NODE_W, l.a.y + l.sa, t0, xs[l.b.col], l.b.y + l.sb, t1)}
                  fill={color} fillOpacity={on ? 0.62 : dim ? 0.08 : l.leak ? 0.42 : l.grey ? 0.22 : 0.17}
                  stroke={l.leak ? RED : 'none'} strokeOpacity={l.leak ? 0.5 : 0} strokeWidth={0.6}
                  className="cursor-pointer transition-[fill-opacity] duration-200"
                  onMouseEnter={() => setHover(k)} onMouseLeave={() => setHover(null)}
                  onClick={() => onSelect(k, l.flows, `${nodeName(l.a)} → ${nodeName(l.b)}`)}>
                  <title>{`${nodeName(l.a)} → ${nodeName(l.b)}: ${l.value.toLocaleString()} ${metric}`}</title>
                </path>
              );
            })}
          </g>
          {nodes.map(n => {
            const fill = n.kind === 'leak' ? RED : n.kind === 'grey' ? GREY : n.kind === 'src' ? '#475569' : n.kind === 'gem' ? '#4f46e5' : n.kind === 'plat' ? '#15803d' : STORED;
            const right = n.col < 3;
            const tx = right ? xs[n.col] + NODE_W + 6 : xs[n.col] + NODE_W + 6;
            return (
              <g key={n.id} className="cursor-pointer au-node" onClick={() => onSelect(n.id, n.flows, nodeName(n))}
                onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}>
                <rect x={xs[n.col]} y={n.y} width={NODE_W} height={n.h} rx={2.5} fill={fill}
                  stroke={isSel(n.id) ? '#111827' : 'none'} strokeWidth={1.5} />
                {n.col < 3 && <rect x={tx - 3} y={n.y + n.h / 2 - 8} width={labelW(n)} height={16} rx={3} fill="#fff" fillOpacity={0.88} className="pointer-events-none" />}
                <text x={tx} y={n.y + n.h / 2} dominantBaseline="middle" fontSize={12} className="au-label"
                  fill={n.kind === 'leak' ? '#b91c1c' : '#1f2937'} fontWeight={n.kind === 'leak' ? 600 : 500}>
                  {nodeName(n)}<tspan fill="#6b7280" fontWeight={400}>{` · ${n.value.toLocaleString()}`}</tspan>
                </text>
                <title>{`${nodeName(n)}: ${n.value.toLocaleString()} ${metric}`}</title>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

function labelW(n: Node) {
  const t = `${nodeName(n)} · ${n.value.toLocaleString()}`;
  return t.length * (n.kind === 'leak' ? 7 : 6.6) + 6;
}

function nodeName(n: Node) {
  if (n.col === 0) return 'All lines';
  if (n.key === '__other') return n.label;
  if (n.col === 1) return geminiLabel(n.key);
  if (n.col === 2) return fieldLabel(n.key);
  return platLabel(n.key);
}

function colX(W: number) {
  const right = 210;                 // room for the last column's labels
  const span = W - right - NODE_W;
  return [0, span * 0.31, span * 0.66, span];
}

function ribbon(x0: number, y0: number, t0: number, x1: number, y1: number, t1: number) {
  const mx = (x0 + x1) / 2;
  return `M${x0},${y0} C${mx},${y0} ${mx},${y1} ${x1},${y1} L${x1},${y1 + t1} C${mx},${y1 + t1} ${mx},${y0 + t0} ${x0},${y0 + t0} Z`;
}

function layout(flows: FlowRow[], metric: 'lines' | 'words', W: number) {
  const val = (f: FlowRow) => (metric === 'lines' ? f.lines : f.words);
  const total = flows.reduce((s, f) => s + val(f), 0) || 1;
  const leakFlow = (f: FlowRow) => f.bucket === 'b' || f.bucket === 'd';
  // small kinds are folded into one «smaller kinds» box per column (never a leak, never a selected kind)
  const keyOf = (col: number, f: FlowRow) => (col === 1 ? f.gemini : col === 2 ? jKey(f) : f.plat);
  const sums = [1, 2, 3].map(col => {
    const m = new Map<string, number>(), leak = new Set<string>();
    flows.forEach(f => { const k = keyOf(col, f); m.set(k, (m.get(k) || 0) + val(f)); if (leakFlow(f) || f.bucket === 'c') leak.add(k); });
    return { m, leak };
  });
  const fold = (col: number, k: string) => {
    const { m, leak } = sums[col - 1];
    return (m.get(k) || 0) < total * 0.012 && !leak.has(k) ? '__other' : k;
  };
  const nodes = new Map<string, Node>();
  const get = (col: number, key: string, kind: Node['kind']) => {
    const id = `${col}:${key}`;
    if (!nodes.has(id)) nodes.set(id, { id, col, key, label: '', value: 0, kind, flows: [], y: 0, h: 0 });
    return nodes.get(id)!;
  };
  const linkMap = new Map<string, Link>();
  flows.forEach((f, i) => {
    const v = val(f);
    if (!v) return;
    const leak = leakFlow(f), grey = f.bucket === 'c';
    const k1 = fold(1, f.gemini), k2 = fold(2, jKey(f)), k3 = fold(3, f.plat);
    const chain = [get(0, 'all', 'src'), get(1, k1, 'gem'), get(2, k2, leak ? 'leak' : grey ? 'grey' : 'ok'), get(3, k3, leak ? 'leak' : grey ? 'grey' : 'plat')];
    chain.forEach(n => { n.flows.push(i); });
    chain[0].value += v; chain[1].value += v; chain[2].value += v; chain[3].value += v;
    for (let c = 0; c < 3; c++) {
      const a = chain[c], b = chain[c + 1];
      const lk = `${a.id}>${b.id}`;
      if (!linkMap.has(lk)) linkMap.set(lk, { a, b, value: 0, flows: [], leak: false, grey: false, sa: 0, sb: 0, ta: 0, tb: 0 });
      const L = linkMap.get(lk)!;
      L.value += v; L.flows.push(i); L.leak = L.leak || (leak && c >= 0 && (b.kind === 'leak' || a.kind === 'leak')); L.grey = L.grey || (grey && (b.kind === 'grey' || a.kind === 'grey'));
    }
  });
  // a stream whose next box is a leak is red from the start, so the eye follows it back to Gemini's role
  linkMap.forEach(L => { if (L.a.col <= 1 && !L.leak) { const leakShare = L.flows.every(i => leakFlow(flows[i])); if (leakShare) L.leak = true; } });
  for (const col of [1, 2, 3]) {
    const other = nodes.get(`${col}:__other`);
    if (other) {
      const n = new Set(flows.filter(f => fold(col, keyOf(col, f)) === '__other').map(f => keyOf(col, f))).size;
      other.label = `${n} smaller kind${n === 1 ? '' : 's'}`;
    }
  }
  // vertical layout per column: ok/plat boxes by size, grey after them, leaks last (bottom)
  const rank = (n: Node) => (n.kind === 'leak' ? 2 : n.kind === 'grey' ? 1 : n.key === '__other' ? 0.5 : 0);
  for (const col of [0, 1, 2, 3]) {
    const ns = Array.from(nodes.values()).filter(n => n.col === col).sort((a, b) => rank(a) - rank(b) || b.value - a.value);
    const avail = H - GAP * (ns.length - 1);
    let k = avail / ns.reduce((s, n) => s + n.value, 0);
    for (let it = 0; it < 4; it++) {
      const small = ns.filter(n => n.value * k < MIN);
      const big = ns.filter(n => n.value * k >= MIN);
      k = Math.max(0.0001, (avail - small.length * MIN) / (big.reduce((s, n) => s + n.value, 0) || 1));
    }
    let y = 0;
    ns.forEach(n => { n.h = Math.max(MIN, n.value * k); n.y = y; y += n.h + GAP; });
  }
  // stack the streams inside each box in the order of the boxes they come from / go to
  const links = Array.from(linkMap.values());
  const outOff = new Map<string, number>(), inOff = new Map<string, number>();
  links.sort((p, q) => p.b.y - q.b.y).forEach(L => {
    const o = outOff.get(L.a.id) || 0; L.ta = (L.value / L.a.value) * L.a.h; L.sa = o; outOff.set(L.a.id, o + L.ta);
  });
  links.sort((p, q) => p.a.y - q.a.y).forEach(L => {
    const o = inOff.get(L.b.id) || 0; L.tb = (L.value / L.b.value) * L.b.h; L.sb = o; inOff.set(L.b.id, o + L.tb);
  });
  return { nodes: Array.from(nodes.values()), links: links.sort((p, q) => Number(p.leak) - Number(q.leak)) };
}
