import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { enc } from '../../lib/api';
import { fieldLabel, RED, STORED } from './defs';

// The selected lines on the scan: the page image (/desk/api/evidence/page) with each line outlined, red for a line
// that fell through, teal for one that landed in a field, grey for ink that is not article text.

export type Line = { id: string; page: number; n: number; text: string; box: number[]; bucket: string; field: string | null; gemini: string };

export default function ScanView({ stem, pageSize, lines, focus }: {
  stem: string; pageSize: Record<string, number[]>; lines: Line[]; focus?: string | null;
}) {
  const pages = useMemo(() => Array.from(new Set(lines.map(l => l.page))).sort((a, b) => a - b), [lines]);
  const focusLine = lines.find(l => l.id === focus);
  const [page, setPage] = useState<number>(focusLine?.page || pages[0] || 1);
  const [loaded, setLoaded] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { setPage(focusLine?.page || pages[0] || 1); }, [focus, pages.join(',')]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setLoaded(false); }, [page, stem]);
  const here = lines.filter(l => l.page === page);
  const [pw, ph] = pageSize[String(page)] || [2480, 3508];
  // scroll the first (or focused) box into view once the image has its size
  useEffect(() => {
    if (!loaded || !box.current) return;
    const t = (focusLine && focusLine.page === page ? focusLine : here[0]);
    if (!t) return;
    const el = box.current;
    const img = el.querySelector('img');
    if (!img) return;
    const y = (t.box[1] / ph) * img.clientHeight;
    el.scrollTo({ top: Math.max(0, y - el.clientHeight / 3), behavior: 'smooth' });
  }, [loaded, page, focus]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!lines.length) return <p className="text-sm text-gray-500 p-4">Click a stream or a box of the flow to see its lines on the scan.</p>;
  const i = pages.indexOf(page);
  return (
    <div className="flex flex-col gap-2 min-h-0">
      <div className="flex items-center justify-between gap-2 text-sm">
        <div className="flex items-center gap-1">
          <button disabled={i <= 0} onClick={() => setPage(pages[i - 1])} className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30" aria-label="Previous page with selected lines"><ChevronLeft className="w-4 h-4" /></button>
          <span className="tabular-nums text-gray-700">Page {page}</span>
          <button disabled={i >= pages.length - 1} onClick={() => setPage(pages[i + 1])} className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30" aria-label="Next page with selected lines"><ChevronRight className="w-4 h-4" /></button>
          <span className="text-xs text-gray-500 ml-1">{here.length} line{here.length === 1 ? '' : 's'} here · {pages.length} page{pages.length === 1 ? '' : 's'}</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm border-2" style={{ borderColor: STORED }} />in a field</span>
          <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm border-2" style={{ borderColor: RED }} />fell through</span>
          <span className="flex items-center gap-1"><i className="w-3 h-3 rounded-sm border-2 border-gray-400" />not article text</span>
        </div>
      </div>
      <div ref={box} className="relative overflow-auto rounded-lg border border-gray-200 bg-gray-100" style={{ height: 'clamp(420px, calc(100vh - 330px), 760px)' }} data-testid="au-scan">
        <div className="relative">
          <img src={`/desk/api/evidence/page?stem=${enc(stem)}&page=${page}&w=1000`} alt={`Page ${page} of ${stem}`}
            className="w-full block select-none" onLoad={() => setLoaded(true)} />
          {loaded && here.map(l => {
            const leak = l.bucket === 'b' || l.bucket === 'd';
            const c = leak ? RED : l.bucket === 'c' ? '#9ca3af' : STORED;
            const f = focus === l.id;
            return (
              <div key={l.id} className={`absolute rounded-sm au-box ${f ? 'au-box-focus' : ''}`} title={`${l.id} · ${fieldLabel(l.field)}`}
                style={{ left: `${(l.box[0] / pw) * 100 - 0.4}%`, top: `${(l.box[1] / ph) * 100 - 0.25}%`,
                  width: `${(l.box[2] / pw) * 100 + 0.8}%`, height: `${(l.box[3] / ph) * 100 + 0.5}%`,
                  border: `2px solid ${c}`, background: leak ? 'rgba(220,38,38,.10)' : 'rgba(15,118,110,.06)' }} />
            );
          })}
        </div>
      </div>
    </div>
  );
}
