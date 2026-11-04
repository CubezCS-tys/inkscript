"""Experiment 51: count what the v3.3 Gemini answers of the 600 hold (metadata keys, block types, parsed-work fields).
Read-only; no calls. Writes out/answer_counts.json."""
import json, glob, collections
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "43_rehearsal" / "out"
C = collections.Counter(); arts = collections.defaultdict(set); ex = {}
def note(k, stem, v=None):
    C[k] += 1; arts[k].add(stem)
    if v is not None and k not in ex: ex[k] = (stem, str(v)[:150])
for d in ('v33_300_final/raw', 'v33_300b_fix3/raw'):
    for f in sorted(glob.glob(str(R / d / '*.json'))):
        j = json.load(open(f)); a = j.get('answer')
        if isinstance(a, str):
            try: a = json.loads(a)
            except Exception: a = None
        if not isinstance(a, dict): C['no-answer'] += 1; continue
        stem = j['stem']; arts['_all'].add(stem)
        m = a.get('metadata') or {}
        if isinstance(m, dict):
            for k, v in m.items():
                if v not in (None, '', [], {}): note('meta.' + k, stem, v)
            for au in m.get('authors') or []:
                if not isinstance(au, dict): continue
                for k, v in au.items():
                    if v not in (None, '', [], {}): note('au.' + k, stem, v)
                for k, v in (au.get('aff_parts') or {}).items():
                    if v: note('aff.' + k, stem, v)
            for h in m.get('history') or []:
                if isinstance(h, dict): note('hist.' + str(h.get('type')), stem, h.get('text'))
            for k, v in (m.get('abstract') or {}).items() if isinstance(m.get('abstract'), dict) else []:
                if v: note('abs.' + k, stem)
            for k, v in (m.get('keywords') or {}).items() if isinstance(m.get('keywords'), dict) else []:
                if v: note('kw.' + k, stem, v)
        for p in a.get('pages', []):
            for b in p.get('blocks', []):
                t = b.get('type'); note('blk.' + str(t), stem)
                for k in b:
                    if k not in ('type', 'lines'): note('bk.' + k, stem)
                if b.get('lang'): note('lang.' + str(b['lang']), stem)
                for w in (b.get('parsed') or []) + (b.get('cites') or []):
                    if isinstance(w, dict):
                        note('W.type.' + str(w.get('type')), stem)
                        for k, v in w.items():
                            if v: note('W.' + k, stem, v)
        for k in ('splits', 'noise', 'ornaments', 'fixes', 'sic', 'math', 'missed'):
            if a.get(k): C['top.' + k] += len(a[k]) - 1; note('top.' + k, stem)
out = {k: {"articles": len(arts.get(k, ())), "n": C[k], "example": ex.get(k)} for k in sorted(C)}
out['_articles'] = len(arts['_all'])
Path(__file__).resolve().parent.joinpath('out').mkdir(exist_ok=True)
json.dump(out, open(Path(__file__).resolve().parent / 'out' / 'answer_counts.json', 'w'), ensure_ascii=False, indent=1)
for k, v in out.items(): print(k, v)
