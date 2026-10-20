"""Seeded draw for the proof pack (independent evaluator). 30 articles, 2 pages each."""
import json, random
from pathlib import Path
H = Path(__file__).resolve().parents[2]
SEED = 20261020
stems = sorted(p.name for p in (H/'out/v33_300b_final/views/scans').iterdir())
rng = random.Random(SEED)
arts = sorted(rng.sample(stems, 30))
draw = []
for s in arts:
    pages = sorted(int(f.stem[1:]) for f in (H/'out/v33_300b_final/views/scans'/s).glob('p*.jpg'))
    pick = sorted(rng.sample(pages, 2)) if len(pages) >= 2 else pages
    draw.append(dict(stem=s, n_pages=len(pages), pages=pick))
short = 60 - sum(len(d['pages']) for d in draw)
rest = [s for s in stems if s not in arts]
for s in sorted(rng.sample(rest, short)):  # top-up: one page from each of `short` more articles
    pages = sorted(int(f.stem[1:]) for f in (H/'out/v33_300b_final/views/scans'/s).glob('p*.jpg'))
    draw.append(dict(stem=s, n_pages=len(pages), pages=[rng.choice(pages)], topup=True))
json.dump(dict(seed=SEED, method='random.Random(seed).sample(sorted stems,30) then sample(pages,2) per article in sorted order; 1-page articles leave a shortfall, topped up with 1 random page from each of that many further random articles', draw=draw), open(H/'out/proof/draw.json','w'), indent=1)
print(sum(len(d['pages']) for d in draw)); [print(d) for d in draw]
