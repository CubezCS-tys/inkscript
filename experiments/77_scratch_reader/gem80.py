"""Experiment 77, round 2 of judging (owner's conditional $40, 2026-11-04 18:40 CST): Gemini judges v1-vs-Azure
disputes on experiment 80's old print, for a v3 training.  Same prompt, model, settings and code path as gem77.py
(imported); its own files under out/judge80/ and its own spend log and cap.

    python gem80.py pick N        stratified sample: by decade (weight x2 before 1960), at most 6 lines a page,
                                  no journal over 3% of the sample
    python gem80.py crops         96-px judge crops from experiment 80's scans
    python gem80.py run [LIMIT] [THREADS]
    python gem80.py spent
"""
from __future__ import annotations

import glob
import json
import random
import sys
from collections import Counter, defaultdict

import gem77
from common77 import OUT, POLICIES_NP, azure_pages, cut_line, nonempty_lines, render_page, to_visual

J = OUT / "judge80"
J.mkdir(exist_ok=True)
gem77.J, gem77.SPEND, gem77.CACHE = J, J / "spend.jsonl", J / "answers.jsonl"
gem77.CAP, gem77.STOP_AT = 40.0, 39.0
NP = POLICIES_NP["no_punct"]


def pick(n: int):
    M = {}
    for f in glob.glob(str(OUT / "shards/manifest-old80-*.jsonl")):
        for l in open(f, encoding="utf-8"):
            d = json.loads(l)
            M[d["key"]] = d
    disp = []
    for d in map(json.loads, open(OUT / "pred/old80_v1.jsonl", encoding="utf-8")):
        m = M[d["key"]]
        if NP(d["pred"]) == NP(m["label"]) or to_visual(d["pred"]) == to_visual(m["label"]):
            continue
        disp.append(dict(key=d["key"], azure=m["label"], v1=d["pred"], cmin=d["cmin"], cmean=d["cmean"],
                         year=m["year"], jcode=m["jcode"]))
    rng = random.Random(80)
    rng.shuffle(disp)
    dec = lambda y: (int(y) // 10) * 10  # noqa: E731
    by_dec = defaultdict(list)
    for d in disp:
        by_dec[dec(d["year"])].append(d)
    w = {k: len(v) * (2 if k < 1960 else 1) for k, v in by_dec.items()}
    quota = {k: min(len(by_dec[k]), round(n * w[k] / sum(w.values()))) for k in by_dec}
    per_page, per_j, sample = Counter(), Counter(), []
    jcap = max(30, int(0.03 * n))
    for k, items in sorted(by_dec.items()):
        got = 0
        for d in items:
            if got >= quota[k]:
                break
            pg = d["key"].rsplit("_l", 1)[0]
            if per_page[pg] >= 6 or per_j[d["jcode"]] >= jcap:
                continue
            per_page[pg] += 1
            per_j[d["jcode"]] += 1
            d["A"] = "azure" if rng.random() < 0.5 else "v1"
            sample.append(d)
            got += 1
    rng.shuffle(sample)
    with open(J / "sample.jsonl", "w", encoding="utf-8") as f:
        for d in sample:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    st = dict(disputes=len(disp), sample=len(sample), pages=len(per_page), journals=len(per_j),
              by_decade_disputes={k: len(v) for k, v in sorted(by_dec.items())},
              by_decade_sample=dict(sorted(Counter(dec(d["year"]) for d in sample).items())))
    (J / "pick.json").write_text(json.dumps(st, indent=1))
    print(json.dumps(st, indent=1))


def crops():
    import cv2
    import pypdfium2 as pdfium
    cv2.setNumThreads(1)
    S = [json.loads(l) for l in open(J / "sample.jsonl", encoding="utf-8")]
    meta = {json.loads(l)["stem"]: json.loads(l) for l in open(OUT / "pages80.jsonl", encoding="utf-8")}
    by = defaultdict(list)
    for s in S:
        stem, rest = s["key"].rsplit("_p", 1)
        by[(stem, int(rest[:3]))].append((int(s["key"][-3:]), s["key"]))
    (J / "crops").mkdir(exist_ok=True)
    for (stem, p), items in sorted(by.items()):
        if all((J / "crops" / f"{k}.png").exists() for _, k in items):
            continue
        m = meta[stem]
        doc = pdfium.PdfDocument(m["pdf"])
        pg = azure_pages(m["azure"])[p - 1]
        img = render_page(doc, p - 1, dpi=300)
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        L = {ln["i"]: ln for ln in nonempty_lines(pg)}
        for i, k in items:
            c, _ = cut_line(img, L[i]["poly"], sx, sy, H=96, test=True)
            if c is not None:
                cv2.imwrite(str(J / "crops" / f"{k}.png"), c)
        doc.close()
    print("crops:", len(list((J / "crops").glob("*.png"))))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "pick":
        pick(int(sys.argv[2]))
    elif c == "crops":
        crops()
    elif c == "run":
        gem77.run(int(sys.argv[2]) if len(sys.argv) > 2 else None, int(sys.argv[3]) if len(sys.argv) > 3 else 12)
    elif c == "spent":
        print(f"${gem77.spent():.4f}")
