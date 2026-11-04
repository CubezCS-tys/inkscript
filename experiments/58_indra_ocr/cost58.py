"""Experiment 58: where Gemini's tokens go per page (exp 43 v33_300b_fix3 chunks, from out/layout_scores.json).

    /home/appuser/inkscript/.venv/bin/python cost58.py  -> prints the input model (least squares) and the output split
"""
import json
from pathlib import Path
import numpy as np
OUT = Path(__file__).resolve().parent / "out"
r = json.loads((OUT / "layout_scores.json").read_text())
T = r["tokens"]
X = np.array([[1, t["pages"], t["az_chars"]] for t in T], float)
y = np.array([t["tin"] for t in T], float)
co = np.linalg.lstsq(X, y, rcond=None)[0]
pred = X @ co
print("tin = %.0f per chunk + %.0f per page + %.3f per Azure character" % tuple(co),
      " R2 %.3f" % (1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()))
P = sum(t["pages"] for t in T)
tout = sum(t["tout"] for t in T)
print("pages", P, "chunks", len(T), "tin/page %.0f" % (y.sum() / P), "tout/page %.0f" % (tout / P),
      "Azure chars/page %.0f" % (X[:, 2].sum() / P))
print("input per page: prompt %.0f, page image %.0f, Azure lines %.0f" % (co[0] * len(T) / P, co[1], co[2] * X[:, 2].sum() / P))
parts, b = {}, {}
for t in T:
    for k, v in t["parts"].items():
        parts[k] = parts.get(k, 0) + v
    for k, v in t["blocks"].items():
        b[k] = b.get(k, 0) + v
tot = sum(parts.values())
print("answer characters by part:", {k: round(v / tot, 3) for k, v in sorted(parts.items(), key=lambda x: -x[1])})
print("  inside pages (share of whole answer):", {k: round(v / tot, 3) for k, v in b.items()})
usd = sum(t["usd"] for t in T)
print("usd/page %.5f (v3.3 batch)" % (usd / P))
# price split at Argon batch prices implied: fit usd = a*tin + b*tout
A = np.array([[t["tin"], t["tout"]] for t in T], float)
u = np.array([t["usd"] for t in T])
pr = np.linalg.lstsq(A, u, rcond=None)[0]
print("implied $/M tokens in %.3f out %.3f" % (pr[0] * 1e6, pr[1] * 1e6))
print("share of $ that is input %.2f, output %.2f" % (pr[0] * y.sum() / usd, pr[1] * tout / usd))
