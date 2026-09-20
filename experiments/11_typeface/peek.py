"""Show the printings behind a letter-form: peek.py <azure.json> <scan.pdf> <letter> <form> <out.png>"""
import sys, numpy as np, cv2
sys.argv_backup = sys.argv[:]; import importlib.util, os
spec = importlib.util.spec_from_file_location("mf", os.path.join(os.path.dirname(__file__), "make_font.py")); mf = importlib.util.module_from_spec(spec); spec.loader.exec_module(mf)
azure, scan, letter, form, out = sys.argv[1:6]
plans, iso = mf.collect(azure, scan); P = mf.P; P.solve([p for p, _, _ in plans]); ex = []
if form == "iso": ex = [dict(e, cell=(min(q[:, 0].min() for q in e["paths"]), max(q[:, 0].max() for q in e["paths"]) + 1), score=0) for e in iso.get(letter, [])]
else:
    for p, pc, lg in plans:
        lb = P.letter_blobs(p, pc["blobs"])
        if len(lb) != p["n"]: continue
        for k, s in enumerate(p["scores"]):
            if P.key(p, k) == (letter, form) and s is not None: b = lb[k][0]; ex.append(dict(score=s, paths=b["paths"], holes=b["holes"], base=lg["baseline"], rise=lg["rise"], cell=b["cell"], ok=P.accepted(p)))
ex = sorted(ex, key=lambda e: -e["score"]); print(len(ex), "printings; widths/rise:", [round((e["cell"][1] - e["cell"][0]) / e["rise"], 2) for e in ex[:24]], "scores", [round(e["score"], 2) for e in ex[:24]])
tiles = [255 - 255 * mf.render(e, (e["cell"][1] - e["cell"][0]) / e["rise"])[:, mf.XR - 3 * mf.HI:mf.XR + 20] for e in ex[:24]]
rows = [np.hstack(tiles[i:i + 8] + [np.full_like(tiles[0], 255)] * (8 - len(tiles[i:i + 8]))) for i in range(0, len(tiles), 8)]; cv2.imwrite(out, np.vstack(rows))
