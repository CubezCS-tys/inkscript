"""Experiment 87: a quick local look at the fit (CPU): python tryfit87.py <lib> <iters> [era] [n]"""
import sys, json, time, cv2, numpy as np, torch
sys.path.insert(0, '.')
import fit87 as F
dev = F.device()
lib, iters = sys.argv[1], int(sys.argv[2])
era = sys.argv[3] if len(sys.argv) > 3 else '1950-1999'
n = int(sys.argv[4]) if len(sys.argv) > 4 else 2
R = [json.loads(l) for l in open('out/data/pool.jsonl')]
R = [r for r in R if r['era'] == era][:n]
items = [dict(grey=cv2.imread(f"out/data/crops/pool/{r['key']}.png", 0), text=r['text'], lib=lib) for r in R]
t0 = time.time()
bt = F.Batch(items, dev); P = F.Params(bt)
F.init_items(bt, P)
sc0 = F.scores(bt, P)
print('init', [round(s['iou'], 3) for s in sc0], round(time.time() - t0, 1))
F.fit(bt, P, iters=iters, log=True)
sc = F.scores(bt, P, need_maps=True)
print('fit iou', [round(s['iou'], 3) for s in sc], 'chamfer', [round(s['chamfer'], 2) for s in sc], round(time.time() - t0, 1))
rows = []
for it, s in zip(items, sc):
    t = F.target_of(it['grey'])
    rows += [cv2.cvtColor(it['grey'], cv2.COLOR_GRAY2BGR), cv2.cvtColor((255 * (1 - s['written'])).astype(np.uint8), cv2.COLOR_GRAY2BGR),
             F.overlay(it['grey'], s['written'], t), np.full((4, it['grey'].shape[1], 3), 200, np.uint8)]
Wm = max(r.shape[1] for r in rows)
img = np.vstack([np.hstack([np.full((r.shape[0], Wm - r.shape[1], 3), 255, np.uint8), r]) for r in rows])
cv2.imwrite(f'out/look/try_{lib.replace(":", "_")}_{era}.png', img)
print([F.params_of(P, bt, i) for i in range(bt.B)])
