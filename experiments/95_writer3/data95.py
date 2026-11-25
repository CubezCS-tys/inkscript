"""Experiment 95: data.

    python data95.py journals      idea 2's lines: four training-pool journals, split by DOCUMENT into learn and test
                                   documents; consensus lines only (v1's reading == Azure's under no_punct, every Azure
                                   word confidence >= 0.9, Arabic letters only, 12-90 characters, tilt < 1.5 deg);
                                   exp 87's crop recipe (300 dpi, Azure's polygon, cut_line H=96 test=True)
                                   -> out/data/journals.jsonl + out/data/crops/jl/<key>.png
    python data95.py guards        out/data/guards.json (the split76 test codes, for the GPU host's asserts)

Journals (chosen 2026-11-09 by page count, none held-out or locked; asserted): 0013 and 0523 (2010s-2020s), 0924
(1920s) and 0739 (1930s).  Consensus readings: exp 77's v1 predictions on its training pages (pred/train_v1.jsonl)
and on exp 80's old-print pull (pred/old80_v1.jsonl, never trained on).
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict

import cv2

from common95 import D95, E, TEST76, assert_pool, is_locked_any

sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "87_writer"))

JOURNALS = {"0013": ("2010", "2030"), "0523": ("2010", "2030"), "0924": ("1920", "1930"), "0739": ("1930", "1940"),
            "0690": ("1920", "1930")}          # 0690 added after 0739 gave only 427 learn lines (7 documents)
ONLY = sys.argv[2].split(",") if len(sys.argv) > 2 else None
N_LEARN, N_TEST = 1700, 260
OK_CH = re.compile(r"^[ء-ْٰ\s\.\:\(\)،؛؟!\-«»]+$")
ARABIC = re.compile("[ء-ي]")


def guards():
    D95.mkdir(parents=True, exist_ok=True)
    (D95 / "guards.json").write_text(json.dumps({"test": sorted(TEST76)}))


def journals(seed: int = 95):
    from common77 import POLICIES_NP, azure_pages, clean_label, cut_line, fixpath, nonempty_lines, render_page
    from data87 import _line_conf
    import pypdfium2 as pdfium
    NP = POLICIES_NP["no_punct"]
    if ONLY:
        for j in list(JOURNALS):
            if j not in ONLY:
                JOURNALS.pop(j)
    for j in JOURNALS:
        assert j not in TEST76 and not is_locked_any(j), j
    P = [json.loads(l) for f in ("pages77.jsonl", "pages80.jsonl") for l in open(E / "77_scratch_reader/out" / f)]
    P = [p for p in P if p["jcode"] in JOURNALS and JOURNALS[p["jcode"]][0] <= str(p["year"])[:4] < JOURNALS[p["jcode"]][1]
         and not is_locked_any(p["stem"])]
    assert_pool([p["stem"] for p in P], "journal pages")
    want = {p["stem"] for p in P}
    pred = {}
    for f in ("train_v1.jsonl", "old80_v1.jsonl"):
        for l in open(E / "77_scratch_reader/out/pred" / f, encoding="utf-8"):
            if l[9:25] in want:
                d = json.loads(l)
                pred[d["key"]] = d["pred"]
    print("v1 readings on the journals' lines", len(pred), flush=True)
    rng = random.Random(seed)
    (D95 / "crops/jl").mkdir(parents=True, exist_ok=True)
    out = open(D95 / "journals.jsonl", "a" if ONLY else "w", encoding="utf-8")
    stats = {}
    for j in JOURNALS:
        pages = [p for p in P if p["jcode"] == j]
        docs = sorted({p["stem"] for p in pages})
        rng.shuffle(docs)
        nt = max(3, int(round(0.15 * len(docs))))
        test_docs = set(docs[:nt])
        rng.shuffle(pages)
        got = {"learn": 0, "test": 0}
        quota = {"learn": N_LEARN, "test": N_TEST}
        per_doc = defaultdict(int)
        for p in pages:
            role = "test" if p["stem"] in test_docs else "learn"
            if got[role] >= quota[role]:
                if all(got[r] >= quota[r] for r in got):
                    break
                continue
            try:
                pg = azure_pages(fixpath(p["azure"]))[p["page"] - 1]
            except Exception as e:  # noqa: BLE001
                print("skip", p["stem"], e)
                continue
            conf = _line_conf(pg)
            good = []
            for ln in nonempty_lines(pg):
                key = f"{p['stem']}_p{p['page']:03d}_l{ln['i']:03d}"
                t = clean_label(ln["text"])
                if key not in pred or NP(pred[key]) != NP(t):
                    continue
                if not (12 <= len(t) <= 90) or not OK_CH.match(t) or conf.get(ln["i"], 0) < 0.9 or len(ARABIC.findall(t)) < 8:
                    continue
                good.append((key, ln, t))
            if not good:
                continue
            cap = 12 if role == "learn" else 6          # spread over many pages and documents
            good = good[:max(1, min(cap, quota[role] - got[role]))] if len(good) <= cap else rng.sample(good, cap)
            try:
                pdf = pdfium.PdfDocument(str(fixpath(p["pdf"])))
                img = render_page(pdf, p["page"] - 1, dpi=300)
            except Exception as e:  # noqa: BLE001
                print("skip", p["stem"], e)
                continue
            sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
            for key, ln, t in good:
                if got[role] >= quota[role]:
                    break
                c, info = cut_line(img, ln["poly"], sx, sy, H=96, test=True)
                if c is None or abs(info["ang"]) > 1.5:
                    continue
                cv2.imwrite(str(D95 / "crops/jl" / f"{key}.png"), c)
                out.write(json.dumps(dict(key=key, stem=p["stem"], page=p["page"], jcode=j, year=p["year"], role=role,
                                          text=t, W=c.shape[1]), ensure_ascii=False) + "\n")
                got[role] += 1
                per_doc[p["stem"]] += 1
            out.flush()
        stats[j] = dict(docs=len(docs), test_docs=len(test_docs), **got, docs_used=len(per_doc))
        print(j, stats[j], flush=True)
    out.close()
    sf = D95 / "journals_stats.json"
    old = json.loads(sf.read_text()) if sf.exists() else {}
    sf.write_text(json.dumps({**old, **stats}, indent=1))


if __name__ == "__main__":
    D95.mkdir(parents=True, exist_ok=True)
    {"journals": journals, "guards": guards}[sys.argv[1]]()
