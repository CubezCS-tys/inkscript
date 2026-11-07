import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Check, ClipboardCopy, ImageUp, Info, PenLine, ScanText, ShieldCheck } from 'lucide-react';
import Layout from '../components/Layout';
import { Card, Chip, ErrorBox } from '../components/Bits';
import { api } from '../lib/api';

// Try our reader (/try-reader, 2026-11-06): drop, pick or paste an image of printed Arabic; the final reader (v7-28M,
// experiment 89) reads it through /desk/api/try-reader (desk/try_reader.py -> experiment 89's serve_reader.py on
// 127.0.0.1:8171). Nothing is stored: the image goes to the reader in memory and is dropped after the answer.

const TEAL = '13,148,136';
const MAX = 5 * 1024 * 1024;
const OK_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/bmp'];

type Ch = { c: string; p: number };
type Alt = { text: string; logp: number };
type Line = { box: number[]; crop: string; crop_w: number; text: string; chars: Ch[]; alternatives: Alt[] };
type Res = { text: string; chars: Ch[] | null; alternatives: Alt[]; inverted: boolean; lines: Line[]; ms: number; ms_read: number; size: number[]; model: string; params: number };

export default function TryReaderPage() {
  const [img, setImg] = useState<{ url: string; name: string; kb: number } | null>(null);
  const [res, setRes] = useState<Res | null>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const send = useCallback(async (f: File | Blob, name: string) => {
    setErr(''); setRes(null);
    if (f.size > MAX) { setErr(`This image is ${(f.size / 1e6).toFixed(1)} MB; the limit is 5 MB. A crop of the lines works best.`); return; }
    if (f.type && !OK_TYPES.includes(f.type)) { setErr('Please use a PNG, JPEG, WebP or BMP image.'); return; }
    setImg(prev => { if (prev) URL.revokeObjectURL(prev.url); return { url: URL.createObjectURL(f), name, kb: Math.round(f.size / 1024) }; });
    setBusy(true);
    try {
      const r = await api<Res>('/try-reader', { method: 'POST', body: f, headers: { 'Content-Type': f.type || 'application/octet-stream' } });
      setRes(r);
    } catch (e: any) { setErr(String(e?.message || e)); }
    finally { setBusy(false); }
  }, []);

  useEffect(() => {                                    // Ctrl+V of a screenshot anywhere on the page
    const onPaste = (e: ClipboardEvent) => {
      const it = Array.from(e.clipboardData?.items || []).find(i => i.kind === 'file' && i.type.startsWith('image/'));
      const f = it?.getAsFile();
      if (f) { e.preventDefault(); send(f, 'pasted image'); }
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [send]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) send(f, f.name);
  };

  return (
    <Layout wide>
      <div className="max-w-[84rem] mx-auto">
        <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2"><ScanText className="w-5 h-5 text-teal-700" aria-hidden />Try our reader</h1>
        <p className="text-[15px] text-gray-700 mt-1.5 max-w-4xl leading-relaxed">
          Our own reader (v7-28M, 28M parameters, trained from scratch on Mandumah lines). Best on printed Arabic lines; titles in decorative fonts and calligraphy are its weak spots.
        </p>

        <div className="grid grid-cols-[26rem_1fr] gap-6 mt-5 items-start">
          <div className="space-y-4">
            <div data-testid="drop"
              onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}
              onClick={() => input.current?.click()} role="button" tabIndex={0}
              onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') input.current?.click(); }}
              className={`cursor-pointer rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors ${over ? 'border-teal-500 bg-teal-50' : 'border-gray-300 bg-white hover:border-teal-400 hover:bg-teal-50/40'}`}>
              <ImageUp className="w-8 h-8 mx-auto text-teal-600" aria-hidden />
              <div className="mt-2 text-[15px] font-medium text-gray-800">Drop an image of Arabic print here</div>
              <div className="mt-1 text-sm text-gray-500">or click to choose a file, or paste a screenshot with <span className="font-medium text-gray-700">Ctrl+V</span></div>
              <div className="mt-2 text-xs text-gray-400">PNG, JPEG, WebP or BMP · up to 5 MB · one line or a few lines</div>
              <input ref={input} type="file" accept="image/png,image/jpeg,image/webp,image/bmp" className="hidden" data-testid="file"
                onChange={e => { const f = e.target.files?.[0]; if (f) send(f, f.name); e.target.value = ''; }} />
            </div>
            <div className="flex gap-2 text-xs text-gray-500 items-start">
              <ShieldCheck className="w-4 h-4 text-teal-600 shrink-0 mt-px" aria-hidden />
              <span>Nothing is stored. Your image goes to the reader on this machine, is read in memory and dropped as soon as the reading comes back; it is not saved or logged.</span>
            </div>
            {img && (
              <Card title={<span className="text-sm">Your image</span>} right={<span className="text-xs text-gray-400">{img.name} · {img.kb} KB{res ? ` · ${res.size[0]} × ${res.size[1]} px` : ''}</span>}>
                <img src={img.url} alt="the image you gave" className="max-h-80 w-full object-contain object-right rounded border border-gray-100 bg-gray-50" data-testid="preview" />
              </Card>
            )}
          </div>

          <div className="min-w-0">
            {err && <ErrorBox>{err}</ErrorBox>}
            {busy && <Card><p className="text-sm text-gray-500 py-6 text-center">Reading…</p></Card>}
            {!busy && !res && !err && <Placeholder />}
            {res && !busy && <Result r={res} />}
          </div>
        </div>
      </div>
    </Layout>
  );
}

function Placeholder() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white px-8 py-12 text-center text-gray-500">
      <p className="text-[15px]">The reading appears here, in large right-to-left text.</p>
      <p className="text-sm mt-2 max-w-xl mx-auto">Each letter is underlined: a <span style={{ color: `rgb(${TEAL})` }} className="font-medium">strong line</span> where the reader is sure, a <span style={{ color: `rgba(${TEAL},0.45)` }} className="font-medium">pale line</span> where it hesitates.</p>
    </div>
  );
}

function Result({ r }: { r: Res }) {
  const multi = r.lines.length > 1;
  return (
    <div className="space-y-4" data-testid="result">
      <Card title={<span>What our reader reads</span>} right={
        <div className="flex items-center gap-2">
          {r.inverted && <Chip tone="indigo" title="The image had light letters on a dark ground; it was flipped to dark on light before reading">flipped white-on-dark</Chip>}
          {multi && <Chip tone="gray">{r.lines.length} lines</Chip>}
          <span className="text-xs text-gray-400 tabular-nums">{(r.ms / 1000).toFixed(r.ms < 10000 ? 2 : 1)} s</span>
          <CopyBtn text={r.text} />
        </div>}>
        {!multi && <Reading chars={r.lines[0].chars} text={r.lines[0].text} big />}
        {!multi && <Alternatives alts={r.alternatives} base={r.lines[0].text} />}
        {multi && (
          <div className="divide-y divide-gray-100" data-testid="lines">
            <div className="grid grid-cols-[1fr_minmax(0,22rem)_1.5rem] gap-4 text-xs text-gray-400 pb-1"><span className="text-right">Reading</span><span className="text-right">The line as the reader saw it</span><span /></div>
            {r.lines.map((l, i) => (
              <div key={i} className="grid grid-cols-[1fr_minmax(0,22rem)_1.5rem] gap-4 items-start py-3 first:pt-1">
                <div className="min-w-0">
                  <Reading chars={l.chars} text={l.text} />
                  <Alternatives alts={l.alternatives} base={l.text} small />
                  <Writer crop={l.crop} text={l.text} />
                </div>
                <div className="flex justify-end pt-2">
                  <img src={l.crop} alt={`line ${i + 1} as the reader saw it`} className="h-8 max-w-full object-contain object-right rounded border border-gray-100" />
                </div>
                <span className="text-[11px] text-gray-400 tabular-nums pt-3 text-right">{i + 1}</span>
              </div>))}
          </div>)}
      </Card>
      {!multi && (
        <Card title={<span className="text-sm">The line as the reader saw it</span>}>
          <div className="flex justify-end"><img src={r.lines[0].crop} alt="the line, grey, 48 pixels high, as the reader saw it" className="h-12 max-w-full object-contain object-right rounded border border-gray-100" data-testid="crop" /></div>
          <Writer crop={r.lines[0].crop} text={r.lines[0].text} />
          <p className="text-xs text-gray-500 mt-2">Grey, 48 pixels high, with a margin round the ink: the same cut the reader was trained on{r.inverted ? ', after flipping light letters to dark' : ''}.</p>
        </Card>)}
      <div className="flex gap-2 text-xs text-gray-500 items-start px-1">
        <Info className="w-4 h-4 text-gray-400 shrink-0 mt-px" aria-hidden />
        <span>The reading is the reader&apos;s first choice (greedy). The other readings come from a small search over its next-best letters; they are often one letter apart. Reading time on this machine&apos;s CPU (two threads, low priority): {r.ms_read} ms for {r.lines.length === 1 ? 'the line' : `${r.lines.length} lines`}.</span>
      </div>
    </div>
  );
}

// "Show the writer" (experiment 87): the reading written back by our stroke writer in the style fitted to this crop
type Stroke = { letter: number; pts: number[][] };
type Wr = { written: string; overlay: string; crop: string; lib: string; iou: number; chamfer: number; ms: number; strokes?: Stroke[] };

function Writer({ crop, text }: { crop: string; text: string }) {
  const [w, setW] = useState<Wr | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  if (!text.trim()) return null;
  const go = async () => {
    setBusy(true); setErr('');
    try {
      setW(await api<Wr>('/try-reader/write', { method: 'POST', body: JSON.stringify({ crop, text }), headers: { 'Content-Type': 'application/json' } }));
    } catch (e: any) { setErr(String(e?.message || e)); } finally { setBusy(false); }
  };
  return (
    <div className="mt-2" data-testid="writer">
      {!w && <button type="button" onClick={go} disabled={busy} data-testid="show-writer"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-60">
        <PenLine className="w-3.5 h-3.5" aria-hidden />{busy ? 'Writing… (about 20 s)' : 'Show the writer'}</button>}
      {err && <p className="text-xs text-red-600 mt-1">{err}</p>}
      {w && (
        <div className="space-y-1 mt-1">
          {[['the image', w.crop], ['written by our writer', w.written], ['overlay', w.overlay]].map(([lab, src]) => (
            <div key={lab} className="flex items-center justify-end gap-3">
              <span className="text-[11px] text-gray-400 w-32 text-right">{lab}</span>
              <img src={src} alt={lab} className="h-12 max-w-full object-contain object-right rounded border border-gray-100" />
            </div>))}
          {w.strokes && w.strokes.length > 0 && <WriteAnim crop={w.crop} strokes={w.strokes} />}
          <p className="text-[11px] text-gray-500 text-right">Black: ink explained · red: ink not written · blue: written where there is no ink · letters: {w.lib} · overlap {w.iou.toFixed(2)} · {(w.ms / 1000).toFixed(1)} s</p>
        </div>)}
    </div>
  );
}

// "Watch it write": the fitted strokes drawn on a canvas over a faint copy of the line, in reading order, each
// segment a round-capped line of the fitted width (coordinates: the 96-px crop's pixels). Client-side only.
function WriteAnim({ crop, strokes }: { crop: string; strokes: Stroke[] }) {
  const [on, setOn] = useState(false);
  const [speed, setSpeed] = useState(40);
  const [run, setRun] = useState(0);
  const cv = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!on || !cv.current) return;
    const c = cv.current, ctx = c.getContext('2d');
    if (!ctx) return;
    const img = new Image();
    let raf = 0, stop = false;
    const segs: [number[], number[]][] = [];
    for (const s of strokes) for (let i = 1; i < s.pts.length; i++) segs.push([s.pts[i - 1], s.pts[i]]);
    img.onload = () => {
      const sc = img.height ? 96 / img.height : 1;
      c.width = Math.round(img.width * sc); c.height = 96;
      const bg = () => { ctx.clearRect(0, 0, c.width, c.height); ctx.globalAlpha = 0.25; ctx.drawImage(img, 0, 0, c.width, c.height); ctx.globalAlpha = 1; };
      bg();
      let n = 0; const t0 = performance.now();
      ctx.lineCap = 'round'; ctx.strokeStyle = 'rgb(17,94,89)';
      const step = (t: number) => {
        if (stop) return;
        const want = Math.min(segs.length, Math.floor(((t - t0) / 1000) * speed));
        for (; n < want; n++) {
          const [a, b] = segs[n];
          ctx.lineWidth = Math.max(1, a[2] + b[2]);
          ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
        }
        if (n < segs.length) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    };
    img.src = crop;
    return () => { stop = true; cancelAnimationFrame(raf); };
  }, [on, run, speed, crop, strokes]);
  return (
    <div className="mt-1" data-testid="write-anim">
      <div className="flex items-center justify-end gap-3 text-[11px] text-gray-500">
        <label className="inline-flex items-center gap-1.5"><input type="checkbox" checked={on} onChange={e => setOn(e.target.checked)} data-testid="watch" />Watch it write</label>
        {on && <>
          <button type="button" onClick={() => setRun(r => r + 1)} className="px-2 py-0.5 rounded border border-gray-200 bg-white hover:bg-gray-50">Replay</button>
          <label className="inline-flex items-center gap-1">speed<input type="range" min={5} max={200} value={speed} onChange={e => setSpeed(Number(e.target.value))} /></label>
          <span className="tabular-nums w-16">{speed} seg/s</span>
        </>}
      </div>
      {on && <div className="flex justify-end mt-1"><canvas ref={cv} className="h-12 max-w-full rounded border border-gray-100" data-testid="anim-canvas" /></div>}
    </div>
  );
}

// combining marks (harakat, shadda, superscript alif …) join the letter before them, so the underline follows letters
const MARK = /\p{M}/u;

function Reading({ chars, text, big }: { chars: Ch[]; text: string; big?: boolean }) {
  const groups: { s: string; p: number }[] = [];
  for (const ch of chars) {
    if (MARK.test(ch.c) && groups.length) { const g = groups[groups.length - 1]; g.s += ch.c; g.p = Math.min(g.p, ch.p); }
    else groups.push({ s: ch.c, p: ch.p });
  }
  if (!text.trim()) return <p className="text-sm text-gray-400 py-2">The reader found no text.</p>;
  return (
    <p dir="rtl" lang="ar" data-testid="reading"
      className={`font-naskh text-gray-900 ${big ? 'text-[34px] leading-[2.1] py-2' : 'text-[24px] leading-[2]'}`}>
      {groups.map((g, i) => {
        const a = g.s.trim() ? 0.18 + 0.82 * Math.pow(Math.max(0, Math.min(1, (g.p - 0.3) / 0.7)), 1.5) : 0;
        return (
          <span key={i} title={g.s.trim() ? `${Math.round(g.p * 100)}% sure` : undefined}
            style={{ textDecorationLine: g.s.trim() ? 'underline' : 'none', textDecorationColor: `rgba(${TEAL},${a.toFixed(2)})`,
              textDecorationThickness: big ? 3 : 2, textUnderlineOffset: big ? 12 : 9, textDecorationSkipInk: 'none' }}>{g.s}</span>);
      })}
    </p>
  );
}

// the words of an alternative that the first reading does not have (longest common run of words), shown in indigo
function diffWords(base: string, alt: string): { w: string; diff: boolean }[] {
  const A = base.split(/\s+/).filter(Boolean), B = alt.split(/\s+/).filter(Boolean);
  const L: number[][] = Array.from({ length: A.length + 1 }, () => new Array(B.length + 1).fill(0));
  for (let i = A.length - 1; i >= 0; i--) for (let j = B.length - 1; j >= 0; j--)
    L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const out: { w: string; diff: boolean }[] = [];
  let i = 0, j = 0;
  while (j < B.length) {
    if (i < A.length && A[i] === B[j]) { out.push({ w: B[j], diff: false }); i++; j++; }
    else if (i < A.length && L[i + 1][j] >= L[i][j + 1]) i++;
    else { out.push({ w: B[j], diff: true }); j++; }
  }
  return out;
}

function Alternatives({ alts, base, small }: { alts: Alt[]; base: string; small?: boolean }) {
  if (!alts.length) return small ? null : <p className="text-xs text-gray-400 mt-1">No other reading came close.</p>;
  return (
    <div className={small ? 'mt-0.5' : 'mt-3 border-t border-gray-100 pt-3'}>
      {!small && <div className="text-xs text-gray-500 mb-1">Other readings it considered <span className="text-gray-400">(the words that differ in <span className="text-indigo-600">indigo</span>)</span></div>}
      <ul className="space-y-0.5">
        {alts.map((a, i) => (
          <li key={i} dir="rtl" lang="ar" className={`font-naskh text-gray-400 ${small ? 'text-[15px]' : 'text-[19px]'} flex items-baseline gap-2`}>
            <span className="text-[11px] text-gray-300 font-sans tabular-nums" dir="ltr">{i + 2}</span>
            <span>{diffWords(base, a.text).map((t, k) => <React.Fragment key={k}>{k ? ' ' : ''}<span className={t.diff ? 'text-indigo-600' : ''}>{t.w}</span></React.Fragment>)}</span>
          </li>))}
      </ul>
    </div>
  );
}

function CopyBtn({ text }: { text: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button type="button" data-testid="copy"
      onClick={async () => { try { await navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 1500); } catch { /* clipboard refused */ } }}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50">
      {ok ? <Check className="w-3.5 h-3.5 text-teal-600" aria-hidden /> : <ClipboardCopy className="w-3.5 h-3.5" aria-hidden />}{ok ? 'Copied' : 'Copy text'}
    </button>
  );
}
