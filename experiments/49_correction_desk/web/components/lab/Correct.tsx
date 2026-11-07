import React, { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, Ban, Plus, Save, SquareDashedMousePointer, Trash2, Undo2 } from 'lucide-react';
import { Btn, Card, Chip, ErrorBox } from '../Bits';
import ScanOverlay, { Layer } from './ScanOverlay';
import { Engine, TYPE_NICE, colorOf, shortOf } from './defs';
import { api, enc } from '../../lib/api';

// Correct (brief §11): the owner writes the page's truth. Start from the reading you pick (its text, editable) and
// the regions of the engine you pick (boxes, kinds, order, editable); mark unreadable lines and regions; save. Every
// save is a NEW revision with your name and the time; the engines' outputs are never changed. The other engines'
// reading of each line is shown under it where it differs, to adopt with one click.

type Line = { line_id: string; text: string; box?: number[] | null; region?: string | null; unreadable?: boolean; reason?: string | null; source?: string | null };
type Region = { region_id: string; type: string; box: number[]; unreadable?: boolean; reason?: string | null; source?: string | null };
type Draft = { lines: Line[]; regions: Region[]; started_from: string | null; layout_from: string | null; note: string; reviewed: boolean; parent: string | null };

const overlap = (a: number[], b: number[]) => {
  const ix = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])), iy = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  return (ix * iy) / Math.max(1, (a[2] - a[0]) * (a[3] - a[1]));
};

function fromCandidates(text: Engine, layout: Engine | null, types: string[]): Draft {
  const regions: Region[] = (layout?.blocks || []).filter(b => b.box).sort((x, y) => (x.order ?? 999) - (y.order ?? 999)).map((b, i) => ({
    region_id: `r${i + 1}`, type: types.includes(b.type) ? b.type : b.type === 'text' ? 'paragraph' : 'unknown', box: b.box!.map(v => Math.round(v)),
    source: `${layout!.run_id}#${b.id}`,
  }));
  const lines: Line[] = (text.lines || []).map((l, i) => {
    let region: string | null = null;
    if (layout && layout.run_id === text.run_id && l.region) {
      const idx = (layout.blocks || []).filter(b => b.box).findIndex(b => b.id === l.region);
      region = idx >= 0 ? regions.find(r => r.source === `${layout.run_id}#${l.region}`)?.region_id || null : null;
    } else if (l.box && regions.length) {
      const best = regions.map(r => [overlap(l.box!, r.box), r.region_id] as [number, string]).sort((a, b) => b[0] - a[0])[0];
      region = best && best[0] >= 0.5 ? best[1] : null;
    }
    return { line_id: `l${i + 1}`, text: l.text, box: l.box ? l.box.map(v => Math.round(v)) : null, region, source: `${text.run_id}#${l.id}` };
  });
  return { lines, regions, started_from: text.run_id, layout_from: layout?.run_id || null, note: '', reviewed: false, parent: null };
}

export default function Correct({ d, scan, dataset, pageId, onSaved }: { d: any; scan: string; dataset: string; pageId: string; onSaved: (x: any) => void }) {
  const engines: Engine[] = d.engines.filter((e: Engine) => e.state === 'succeeded');
  const texted = engines.filter(e => e.has_text && (e.lines || []).length);
  const boxed = engines.filter(e => e.has_boxes);
  const byRun = useMemo(() => new Map(engines.map(e => [e.run_id, e])), [engines]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [textFrom, setTextFrom] = useState<string>('');
  const [layoutFrom, setLayoutFrom] = useState<string>(boxed.find(e => e.engine === 'paddle_vl' && e.variant === 'pipeline')?.run_id || boxed[0]?.run_id || '');
  const [focus, setFocus] = useState<string | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [dirty, setDirty] = useState(false);

  // a saved correction is the starting point when there is one
  useEffect(() => {
    if (d.correction) {
      const b = d.correction.body;
      setDraft({ lines: b.lines, regions: b.regions, started_from: b.started_from, layout_from: b.layout_from, note: '', reviewed: !!b.reviewed, parent: d.correction.revision_id });
    }
  }, [d.correction]);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  const set = (f: (x: Draft) => Draft) => { setDraft(x => (x ? f(x) : x)); setDirty(true); };
  const setLine = (i: number, p: Partial<Line>) => set(x => ({ ...x, lines: x.lines.map((l, k) => (k === i ? { ...l, ...p } : l)) }));
  const move = <T,>(arr: T[], i: number, j: number) => { const a = [...arr]; if (j < 0 || j >= a.length) return a; const [v] = a.splice(i, 1); a.splice(j, 0, v); return a; };
  const nextId = (pre: string, ids: string[]) => { let k = ids.length + 1; while (ids.includes(`${pre}${k}`)) k++; return `${pre}${k}`; };
  // a line with typed line breaks becomes several lines (same region, no box)
  const splitLine = (i: number) => set(x => {
    const l = x.lines[i];
    if (!l.text.includes('\n')) return x;
    const parts = l.text.split('\n').map(s => s.trim()).filter(Boolean);
    const ids = x.lines.map(z => z.line_id);
    const extra = parts.slice(1).map(t => { const id = nextId('l', ids); ids.push(id); return { line_id: id, text: t, region: l.region, box: null, source: l.source }; });
    return { ...x, lines: [...x.lines.slice(0, i), { ...l, text: parts[0] || '' }, ...extra, ...x.lines.slice(i + 1)] };
  });

  const start = () => {
    const t = byRun.get(textFrom);
    if (!t) return;
    setDraft(fromCandidates(t, byRun.get(layoutFrom) || null, d.region_types));
    setDirty(true);
  };

  const save = async () => {
    if (!draft) return;
    setBusy(true); setErr('');
    try {
      const body = { ...draft, lines: draft.lines.map(l => ({ ...l, text: l.text.trim() })) };
      const r = await api(`/lab/${enc(dataset)}/${enc(pageId)}/annotations`, { json: body });
      setDirty(false);
      setDraft(x => (x ? { ...x, parent: r.saved.revision_id, note: '' } : x));
      onSaved(r);
    } catch (e: any) { setErr(String(e.message || e)); } finally { setBusy(false); }
  };

  // the other engines' readings of a line that came from the starting engine
  const elsewhere = (l: Line) => {
    if (!l.source) return [];
    const [run, lid] = l.source.split('#');
    const e = byRun.get(run);
    const idx = (e?.lines || []).findIndex(x => x.id === lid);
    if (!e || idx < 0 || !e.elsewhere) return [];
    return Object.entries(e.elsewhere[idx] || {}).filter(([, v]) => v && v.text && v.text.trim() !== l.text.trim())
      .map(([rid, v]) => ({ run: rid, text: v!.text as string, eng: byRun.get(rid) })).filter(x => x.eng);
  };

  if (!draft) {
    return (
      <Card title="Start a correction" pad>
        <p className="text-sm text-gray-600 max-w-3xl">Pick the reading you want to start from: its text becomes your draft, line by line, and you correct it against the scan. Pick whose regions (boxes, kinds, order) to start from. Whichever you pick gets an easier score later (its words are the default), and the scores say so.</p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="text-sm">Text from<br />
            <select value={textFrom} onChange={e => setTextFrom(e.target.value)} className="mt-1 text-sm rounded-md border-gray-300" data-testid="lab-start-text">
              <option value="">choose a reading…</option>
              {texted.map(e => <option key={e.run_id} value={e.run_id}>{e.label} ({(e.lines || []).length} lines{(e.lines || []).some(l => l.box) ? ', with line boxes' : ''})</option>)}
            </select></label>
          <label className="text-sm">Regions from<br />
            <select value={layoutFrom} onChange={e => setLayoutFrom(e.target.value)} className="mt-1 text-sm rounded-md border-gray-300" data-testid="lab-start-layout">
              <option value="">no regions (draw your own)</option>
              {boxed.map(e => <option key={e.run_id} value={e.run_id}>{e.label} ({(e.blocks || []).filter(b => b.box).length} regions)</option>)}
            </select></label>
          <Btn kind="primary" disabled={!textFrom} onClick={start} data-testid="lab-start">Start correcting</Btn>
        </div>
      </Card>
    );
  }

  const rIndex = new Map(draft.regions.map((r, i) => [r.region_id, i]));
  const layers: Layer[] = [
    { key: 'region', color: '#e11d48', boxes: draft.regions.map((r, i) => ({ id: r.region_id, box: r.box, order: i, label: (TYPE_NICE[r.type] || r.type) + (r.unreadable ? ' · unreadable' : '') })) },
    { key: 'line', color: '#0284c7', dashed: true, boxes: draft.lines.filter(l => l.box).map(l => ({ id: l.line_id, box: l.box!, muted: true })) },
  ];
  const linesFoot = draft.lines.length;
  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-5 space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Btn small kind={drawing ? 'primary' : 'plain'} onClick={() => setDrawing(!drawing)} data-testid="lab-draw">
            <SquareDashedMousePointer className="w-3.5 h-3.5" aria-hidden />{drawing ? 'Drag on the page to add a region…' : 'Add a region'}</Btn>
          <span className="text-gray-500">Red: your regions, numbered in reading order. Blue dashes: line boxes. Click a box to find it in the list.</span>
        </div>
        <ScanOverlay src={scan} width={d.page.width} height={d.page.height} layers={layers} focus={focus} showOrder
          onPick={(k, id) => { setFocus(`${k}:${id}`); document.getElementById(`lab-${k}-${id}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' }); }}
          draw={drawing} onDraw={b => { set(x => ({ ...x, regions: [...x.regions, { region_id: nextId('r', x.regions.map(r => r.region_id)), type: 'paragraph', box: b, source: 'drawn' }] })); setDrawing(false); }}
          maxH="max-h-[80vh]" />
      </div>
      <div className="col-span-7 space-y-3">
        <Card title={<>Your correction {d.correction ? <span className="text-xs font-normal text-gray-500">continuing from revision {d.correction.rev_no}</span> : null}</>}
          right={<div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">started from {shortOf(byRun.get(draft.started_from || '') || ({ label: draft.started_from } as any))}</span>
            <Btn small onClick={() => { if (!dirty || confirm('Drop your unsaved changes and start again?')) { setDraft(null); setDirty(false); } }}><Undo2 className="w-3.5 h-3.5" aria-hidden />Start again</Btn>
          </div>} pad>
          <p className="text-xs text-gray-500 mb-2">Write each line exactly as printed: hamza forms, ى/ي, ة/ه, digits and vowel marks as on the page. Press Enter inside a line to split it into two. The ↑ ↓ arrows set the reading order.</p>
          <ol className="space-y-1.5 max-h-[62vh] overflow-auto pr-1" data-testid="lab-lines">
            {draft.lines.map((l, i) => {
              const others = elsewhere(l);
              const on = focus === `line:${l.line_id}`;
              return (
                <li key={l.line_id} id={`lab-line-${l.line_id}`} className={`rounded-lg border p-2 ${on ? 'border-sky-400 bg-sky-50/40' : l.unreadable ? 'border-gray-300 bg-gray-50' : 'border-gray-200'}`}
                  onFocus={() => setFocus(l.box ? `line:${l.line_id}` : l.region ? `region:${l.region}` : null)}>
                  <div className="flex items-start gap-2">
                    <span className="text-[11px] text-gray-400 tabular-nums w-6 pt-2 text-right">{i + 1}</span>
                    <textarea dir="rtl" value={l.text} rows={Math.max(1, Math.ceil(l.text.length / 80))} data-testid="lab-line-text"
                      onChange={e => setLine(i, { text: e.target.value })} onBlur={() => splitLine(i)}
                      className={`flex-1 ar text-[16px] leading-7 rounded-md border-gray-200 focus:border-sky-400 focus:ring-sky-200 ${l.unreadable ? 'line-through text-gray-400' : ''}`} />
                    <div className="flex flex-col gap-1">
                      <div className="flex gap-1">
                        <button title="earlier in the reading order" onClick={() => set(x => ({ ...x, lines: move(x.lines, i, i - 1) }))} className="p-1 rounded hover:bg-gray-100"><ArrowUp className="w-3.5 h-3.5" /></button>
                        <button title="later in the reading order" onClick={() => set(x => ({ ...x, lines: move(x.lines, i, i + 1) }))} className="p-1 rounded hover:bg-gray-100"><ArrowDown className="w-3.5 h-3.5" /></button>
                        <button title="add a line after this one" onClick={() => set(x => ({ ...x, lines: [...x.lines.slice(0, i + 1), { line_id: nextId('l', x.lines.map(z => z.line_id)), text: '', region: l.region, box: null, source: 'added' }, ...x.lines.slice(i + 1)] }))} className="p-1 rounded hover:bg-gray-100"><Plus className="w-3.5 h-3.5" /></button>
                        <button title="remove this line (it is not on the page)" onClick={() => set(x => ({ ...x, lines: x.lines.filter((_, k) => k !== i) }))} className="p-1 rounded hover:bg-red-50 text-red-600"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                      <select value={l.region || ''} onChange={e => setLine(i, { region: e.target.value || null })} className="text-[11px] py-0.5 rounded border-gray-200" title="the region this line belongs to">
                        <option value="">no region</option>
                        {draft.regions.map(r => <option key={r.region_id} value={r.region_id}>{(rIndex.get(r.region_id) ?? 0) + 1}. {TYPE_NICE[r.type] || r.type}</option>)}
                      </select>
                      <label className="text-[11px] text-gray-600 flex items-center gap-1"><input type="checkbox" checked={!!l.unreadable} onChange={e => setLine(i, { unreadable: e.target.checked, reason: e.target.checked ? l.reason || '' : null })} className="rounded border-gray-300 w-3 h-3" />unreadable</label>
                    </div>
                  </div>
                  {l.unreadable && <input value={l.reason || ''} onChange={e => setLine(i, { reason: e.target.value })} placeholder="why (stain, cut off, faded…)" className="mt-1 ml-8 w-1/2 text-xs rounded border-gray-200" />}
                  {others.length > 0 && (
                    <div className="mt-1 ml-8 space-y-0.5">
                      {others.map(o => (
                        <button key={o.run} onClick={() => setLine(i, { text: o.text })} title="use this reading" className="flex items-baseline gap-2 text-left w-full hover:bg-amber-50 rounded px-1">
                          <span className="text-[10px] shrink-0 font-medium" style={{ color: colorOf(o.eng!) }}>{shortOf(o.eng!)}</span>
                          <span dir="rtl" className="ar text-[13px] text-gray-600 flex-1">{o.text}</span>
                        </button>))}
                    </div>)}
                </li>
              );
            })}
          </ol>
          <div className="mt-2 text-xs text-gray-500">{linesFoot} lines · {draft.lines.filter(l => l.unreadable).length} unreadable</div>
        </Card>
        <Card title="Regions" pad>
          {draft.regions.length === 0 ? <p className="text-sm text-gray-500">No regions. Use “Add a region” and drag on the page.</p> : (
            <ol className="space-y-1" data-testid="lab-regions">
              {draft.regions.map((r, i) => (
                <li key={r.region_id} id={`lab-region-${r.region_id}`} className={`flex flex-wrap items-center gap-2 text-sm rounded-md px-2 py-1 ${focus === `region:${r.region_id}` ? 'bg-rose-50' : ''}`}
                  onMouseEnter={() => setFocus(`region:${r.region_id}`)}>
                  <span className="w-6 text-right text-xs text-gray-400 tabular-nums">{i + 1}</span>
                  <select value={r.type} onChange={e => set(x => ({ ...x, regions: x.regions.map(z => (z.region_id === r.region_id ? { ...z, type: e.target.value } : z)) }))} className="text-xs py-0.5 rounded border-gray-200">
                    {d.region_types.map((t: string) => <option key={t} value={t}>{TYPE_NICE[t] || t}</option>)}
                  </select>
                  <span className="text-xs text-gray-500 flex-1 truncate" dir="rtl">{draft.lines.filter(l => l.region === r.region_id).map(l => l.text).join(' ').slice(0, 90) || '(no lines)'}</span>
                  <button title="earlier" onClick={() => set(x => ({ ...x, regions: move(x.regions, i, i - 1) }))} className="p-1 rounded hover:bg-gray-100"><ArrowUp className="w-3.5 h-3.5" /></button>
                  <button title="later" onClick={() => set(x => ({ ...x, regions: move(x.regions, i, i + 1) }))} className="p-1 rounded hover:bg-gray-100"><ArrowDown className="w-3.5 h-3.5" /></button>
                  <button title="mark unreadable" onClick={() => set(x => ({ ...x, regions: x.regions.map(z => (z.region_id === r.region_id ? { ...z, unreadable: !z.unreadable } : z)) }))} className={`p-1 rounded hover:bg-gray-100 ${r.unreadable ? 'text-amber-700' : ''}`}><Ban className="w-3.5 h-3.5" /></button>
                  <button title="remove the region (its lines keep their text)" onClick={() => set(x => ({ ...x, regions: x.regions.filter(z => z.region_id !== r.region_id), lines: x.lines.map(l => (l.region === r.region_id ? { ...l, region: null } : l)) }))} className="p-1 rounded hover:bg-red-50 text-red-600"><Trash2 className="w-3.5 h-3.5" /></button>
                </li>))}
            </ol>)}
        </Card>
        <Card pad>
          {err && <div className="mb-2"><ErrorBox>{err}</ErrorBox></div>}
          <div className="flex flex-wrap items-center gap-3">
            <input value={draft.note} onChange={e => set(x => ({ ...x, note: e.target.value }))} placeholder="a note with this revision (optional)" className="flex-1 min-w-[16rem] text-sm rounded-md border-gray-300" />
            <label className="text-sm text-gray-700 flex items-center gap-1.5"><input type="checkbox" checked={draft.reviewed} onChange={e => set(x => ({ ...x, reviewed: e.target.checked }))} className="rounded border-gray-300" />the whole page is checked</label>
            <Btn kind="primary" onClick={save} disabled={busy} data-testid="lab-save"><Save className="w-4 h-4" aria-hidden />{busy ? 'Saving and scoring…' : `Save as revision ${(d.history?.length || 0) + 1}`}</Btn>
          </div>
          <p className="text-xs text-gray-500 mt-2">Saving keeps every earlier revision and never touches the engines&apos; outputs. The scores are then worked out against what you saved.</p>
          {dirty && <Chip tone="amber">unsaved changes</Chip>}
        </Card>
      </div>
    </div>
  );
}
