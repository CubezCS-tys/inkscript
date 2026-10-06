"""Over every stored plan of a document (the fixture: all its pieces): the joined final alef's box width before and
after, against the width of the alef's ink; and how many pieces the change touched. -> printed, and out/checks.json
gets the fixture build checks (from the build logs and coverage.py).

    ../../.venv/bin/python fixture_stats.py
"""
import sys, re, json, pickle, subprocess, collections
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(HERE)); import cells as C
from inkscript.geometry import penpath as P


def alef_widths(doc, variant):
    out = []
    for p in pickle.load(open(HERE / f"out/plans/{variant}_{doc}.pkl", "rb")):
        if P._base(p["units"][-1]) != "ا": continue
        p["cache"] = {}; c = C.cells_orig(p)
        if c is None: continue
        a, b = P.intervals(p)[-1]; ys, xs = np.where(P._mask(p, a, b, owner=p["n"] - 1))
        out.append((c[-1][1] - c[-1][0], xs.max() - xs.min() + 1 if len(xs) else 0))
    return np.array(out)


def build_checks(variant, doc="0582"):
    log = open(HERE / f"out/build_{variant}_{doc}.log").read()
    m = re.search(r"pdfium: (\d+/\d+) words intact.*?lines in order (\d+/\d+)", log)
    pdf = HERE / f"out/build_{variant}/{doc}/0582-004-009-012_vector.pdf"
    cov = subprocess.run([str(REPO / ".venv/bin/python"), str(REPO / "experiments/09_pen_path/coverage.py"), str(pdf)], capture_output=True, text=True).stdout
    c = re.search(r"own box: (\d+) of (\d+) \(([\d.]+)%\)", cov)
    return dict(intact=m.group(1), lines=m.group(2), coverage=f"{c.group(1)}/{c.group(2)} ({c.group(3)}%)")


if __name__ == "__main__":
    for v in ("orig", "new"):
        a = alef_widths("0582", v); print(v, "final alefs", len(a), "box width median", np.median(a[:, 0]), "ink width median", np.median(a[:, 1]),
                                         "box narrower than half the alef's ink:", int((a[:, 0] < 0.5 * a[:, 1]).sum()))
    ck = dict(before=build_checks("orig"), after=build_checks("new"))
    p = HERE / "out/checks.json"; old = json.load(open(p)) if p.exists() else {}
    old.update(ck); json.dump(old, open(p, "w"), indent=1); print(old)
