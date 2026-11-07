import React, { useRef, useState } from 'react';

// The page scan with boxes drawn over it (experiment 75, /lab). Boxes are in the canonical render's pixels
// ([x0, y0, x1, y1), top-left origin) and are drawn as fractions of the page, so the display image's size is free.
// Layers can be switched on and off; a box can be clicked; in draw mode a drag on the page returns a new box.

export type OBox = { id: string; box: number[]; label?: string; order?: number | null; muted?: boolean };
export type Layer = { key: string; color: string; boxes: OBox[]; dashed?: boolean };

export default function ScanOverlay({ src, width, height, layers, focus, onPick, draw, onDraw, showOrder, maxH }: {
  src: string; width: number; height: number; layers: Layer[]; focus?: string | null;
  onPick?: (layer: string, id: string) => void; draw?: boolean; onDraw?: (box: number[]) => void; showOrder?: boolean;
  maxH?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<null | { x0: number; y0: number; x1: number; y1: number }>(null);
  const at = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)) };
  };
  const pct = (b: number[]) => ({ left: `${(100 * b[0]) / width}%`, top: `${(100 * b[1]) / height}%`,
    width: `${(100 * (b[2] - b[0])) / width}%`, height: `${(100 * (b[3] - b[1])) / height}%` });
  return (
    <div className={`relative overflow-auto rounded-lg border border-gray-200 bg-white ${maxH || ''}`} data-testid="lab-scan">
      <div ref={ref} className={`relative select-none ${draw ? 'cursor-crosshair' : ''}`}
        onMouseDown={e => { if (!draw) return; const p = at(e); setDrag({ x0: p.x, y0: p.y, x1: p.x, y1: p.y }); e.preventDefault(); }}
        onMouseMove={e => { if (!drag) return; const p = at(e); setDrag({ ...drag, x1: p.x, y1: p.y }); }}
        onMouseUp={() => {
          if (!drag) return;
          const b = [Math.min(drag.x0, drag.x1) * width, Math.min(drag.y0, drag.y1) * height, Math.max(drag.x0, drag.x1) * width, Math.max(drag.y0, drag.y1) * height].map(v => Math.round(v));
          setDrag(null);
          if (b[2] - b[0] > 8 && b[3] - b[1] > 8) onDraw?.(b);
        }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt="the page scan" className="block w-full h-auto" draggable={false} />
        {layers.map(L => L.boxes.map(b => {
          const on = focus === `${L.key}:${b.id}`;
          return (
            <button key={`${L.key}:${b.id}`} type="button" data-box={`${L.key}:${b.id}`}
              onClick={e => { e.stopPropagation(); if (!draw) onPick?.(L.key, b.id); }}
              title={b.label || b.id}
              className="absolute rounded-[2px] transition-colors"
              style={{ ...pct(b.box), border: `${on ? 2.5 : 1.5}px ${L.dashed ? 'dashed' : 'solid'} ${L.color}`,
                background: on ? `${L.color}33` : b.muted ? 'transparent' : `${L.color}10`, pointerEvents: draw ? 'none' : 'auto' }}>
              {(showOrder || on) && (b.order != null || b.label) && (
                <span className="absolute -top-2 -left-2 text-[10px] leading-none px-1 py-0.5 rounded text-white whitespace-nowrap"
                  style={{ background: L.color }}>{b.order != null ? b.order + 1 : ''}{b.label ? ` ${b.label}` : ''}</span>)}
            </button>
          );
        }))}
        {drag && <div className="absolute border-2 border-dashed border-rose-500 bg-rose-500/10"
          style={{ left: `${100 * Math.min(drag.x0, drag.x1)}%`, top: `${100 * Math.min(drag.y0, drag.y1)}%`,
            width: `${100 * Math.abs(drag.x1 - drag.x0)}%`, height: `${100 * Math.abs(drag.y1 - drag.y0)}%` }} />}
      </div>
    </div>
  );
}
