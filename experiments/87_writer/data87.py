"""Experiment 87: the lines the writer is measured and the checker tested on.

    python data87.py pool      # training-pool pages (exp 77/80/83's pool; never a held-out or locked journal/doc)
                               #   -> out/data/pool.jsonl + out/data/crops/pool/<key>.png   (ceiling, verifier design)
    python data87.py held      # exp 81's judged held-out lines (their 96-px judge crops) + up to 6 agreed lines of
                               #   each judged page for the page's style -> out/data/held.jsonl + crops/held/

Crops: exactly exp 81's judge crops: 300-dpi pypdfium2 5.12.1 render, Azure's polygon, common77.cut_line(H=96,
test=True).  "Clean" pool lines: every Azure word confidence >= 0.95 (pre-1950: 0.85), Arabic letters only (spaces and the common
punctuation allowed, no digits or Latin), 12-90 characters, tilt under 1.5 degrees.

Rules (asserted in code): no split76 held-out journal in the pool; no locked journal (exp 84) or locked old-print
document (exp 88) anywhere, pool or held.
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
D = OUT / "data"
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "88_truth_and_lock"))
from common77 import azure_pages, cut_line, fixpath, nonempty_lines, render_page  # noqa: E402
from locked_old import assert_not_locked, is_locked_any  # noqa: E402

TEST = set(json.loads((E / "76_finetune_pilot/out/split76.json").read_text())["test"])
ARABIC = re.compile("[ء-ي]")
OK_CH = re.compile(r"^[ء-ْٰ\s\.\:\(\)،؛؟!\-«»]+$")


def era_of(y) -> str:
    y = int(str(y)[:4])
    return "pre-1950" if y < 1950 else ("1950-1999" if y < 2000 else "2000+")


def _line_conf(page: dict):
    """Azure line index (1..) -> min word confidence, from the words whose spans fall inside the line's spans."""
    words = page.get("words", [])
    offs = [(w["span"]["offset"], w.get("confidence", 1.0)) for w in words]
    out, k = {}, 0
    for ln in page.get("lines", []):
        t = (ln.get("content") or "").strip()
        if not t:
            continue
        k += 1
        cs = []
        for sp in ln.get("spans", []):
            a, b = sp["offset"], sp["offset"] + sp["length"]
            cs += [c for o, c in offs if a <= o < b]
        out[k] = min(cs) if cs else 0.0
    return out


def pool(n_pages_era: int = 30, max_lines: int = 10, seed: int = 87):
    P = [json.loads(l) for f in ("pages77.jsonl", "pages80.jsonl") for l in open(E / "77_scratch_reader/out" / f)]
    P = [p for p in P if p["jcode"] not in TEST and not is_locked_any(p["stem"])]
    assert not any(p["jcode"] in TEST for p in P)
    assert_not_locked([p["stem"] for p in P])
    rng = random.Random(seed)
    by = defaultdict(lambda: defaultdict(list))
    for p in P:
        by[era_of(p["year"])][p["jcode"]].append(p)
    (D / "crops/pool").mkdir(parents=True, exist_ok=True)
    rows = []
    import pypdfium2 as pdfium
    for era in ("2000+", "1950-1999", "pre-1950"):
        J = sorted(by[era])
        rng.shuffle(J)
        got, ji = 0, 0
        while got < n_pages_era and ji < 4 * len(J):
            j = J[ji % len(J)]
            ji += 1
            p = rng.choice(by[era][j])
            if any(r["stem"] == p["stem"] for r in rows):
                continue
            try:
                pg = azure_pages(fixpath(p["azure"]))[p["page"] - 1]
                pdf = pdfium.PdfDocument(str(fixpath(p["pdf"])))
            except Exception as e:  # noqa: BLE001
                print("skip", p["stem"], e)
                continue
            conf = _line_conf(pg)
            L = nonempty_lines(pg)
            good = []
            for ln in L:
                t = ln["text"]
                cmin = 0.95 if era != "pre-1950" else 0.85         # old print: Azure is less sure of itself
                if not (12 <= len(t) <= 90) or not OK_CH.match(t) or conf.get(ln["i"], 0) < cmin:
                    continue
                if len(ARABIC.findall(t)) < 8:
                    continue
                good.append(ln)
            if len(good) < (4 if era != "pre-1950" else 3):
                continue
            img = render_page(pdf, p["page"] - 1, dpi=300)
            sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
            rng.shuffle(good)
            n = 0
            for ln in good:
                c, info = cut_line(img, ln["poly"], sx, sy, H=96, test=True)
                if c is None or abs(info["ang"]) > 1.5:
                    continue
                key = f"{p['stem']}_p{p['page']:03d}_l{ln['i']:03d}"
                cv2.imwrite(str(D / "crops/pool" / f"{key}.png"), c)
                rows.append(dict(key=key, stem=p["stem"], page=p["page"], i=ln["i"], jcode=p["jcode"], year=p["year"],
                                 era=era, text=ln["text"], conf=round(conf.get(ln["i"], 0), 3), W=c.shape[1]))
                n += 1
                if n >= max_lines:
                    break
            got += 1
            print(era, got, p["stem"], n, flush=True)
    assert_not_locked([r["key"] for r in rows])
    with open(D / "pool.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("pool lines", len(rows))


def held(max_fit: int = 6, seed: int = 87):
    X = E / "81_heldout_scale/out"
    sys.path.insert(0, str(E / "81_heldout_scale"))
    from agree81 import form
    rows = {d["key"]: d for d in map(json.loads, open(X / "readings81.jsonl", encoding="utf-8"))}
    S = [json.loads(l) for l in open(X / "judge/sample.jsonl", encoding="utf-8")]
    S += [json.loads(l) for l in open(X / "judge/calib.jsonl", encoding="utf-8")]
    S = [s for s in S if not is_locked_any(s["key"])]
    assert_not_locked([s["key"] for s in S])
    pages = {json.loads(l)["stem"] + "_%d" % json.loads(l)["page"]: json.loads(l) for l in open(X / "pages81.jsonl")}
    judged = {s["key"] for s in S}
    bypage = defaultdict(list)
    for s in S:
        bypage[f"{s['stem']}_{s['page']}"].append(s)
    (D / "crops/held").mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    out = []
    import pypdfium2 as pdfium
    for pk, ss in sorted(bypage.items()):
        p = pages[pk]
        # agreed lines of the page: Azure, v1 and s2r read it the same (no judge, no truth: what the checker sees)
        cand = []
        for k, r in rows.items():
            if r["stem"] != p["stem"] or r["page"] != p["page"] or k in judged or r.get("kind") != "arabic":
                continue
            R = r["readings"]
            if not all(x in R for x in ("azure", "v1", "s2r")):
                continue
            if form(R["azure"]) == form(R["v1"]) == form(R["s2r"]) and 12 <= len(R["v1"]) <= 90:
                cand.append(k)
        rng.shuffle(cand)
        fit = cand[:max_fit]
        for s in ss:
            out.append(dict(key=s["key"], stem=s["stem"], page=s["page"], era=s["era"], role="judged",
                            stratum=s["stratum"], jcode=s["key"][:4], crop="judge"))
        if fit:
            pdf = pdfium.PdfDocument(str(fixpath(p["pdf"])))
            pg = azure_pages(fixpath(p["azure"]))[p["page"] - 1]
            img = render_page(pdf, p["page"] - 1, dpi=300)
            sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
            L = {ln["i"]: ln for ln in nonempty_lines(pg)}
            for k in fit:
                i = rows[k]["i"]
                c, info = cut_line(img, L[i]["poly"], sx, sy, H=96, test=True)
                if c is None:
                    continue
                cv2.imwrite(str(D / "crops/held" / f"{k}.png"), c)
                out.append(dict(key=k, stem=p["stem"], page=p["page"], era=rows[k]["era"], role="fit",
                                text=rows[k]["readings"]["v1"], jcode=k[:4], crop="held"))
        print(pk, len(ss), "judged,", len(fit), "fit", flush=True)
    assert_not_locked([r["key"] for r in out])
    with open(D / "held.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("held rows", len(out))


if __name__ == "__main__":
    D.mkdir(parents=True, exist_ok=True)
    {"pool": pool, "held": held}[sys.argv[1]]()
