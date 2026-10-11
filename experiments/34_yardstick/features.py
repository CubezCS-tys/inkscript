"""Per-page features of every pool document, to find pages of each kind (experiment 34).

    PYTHONPATH=src python features.py [--workers 2]   -> out/features.jsonl (one line per page), resumable

From Azure's reading (enrich.document.load, the build's paragraph kinds from enrich.structure.analyse, Quran
quotations from enrich.quran.check_document) and from a 60 dpi render of the scan (ruled lines for tables):
  words, lines, latin (share of words with Latin letters), digits (share of words that are numbers),
  vowelled (share of Arabic words carrying a short vowel, tanwin or sukun: shadda alone does not count),
  footnote_lines, heading_lines (title, author, rubric, section heading), furniture_lines,
  quran_words (words inside a matched quotation), hw (share of words in an Azure handwriting span),
  math (lines that look like a formula: = or an operator between Latin letters or digits, few Arabic letters),
  grid (short lines of numbers standing in columns), rules_h / rules_v (long ruled lines on the scan),
  columns (text columns found among the page's paragraphs), lowconf (share of words under 0.8), angle.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

import numpy as np

OUT = Path("/home/yassine/inkscript/experiments/34_yardstick/out")
AR = re.compile("[ء-ي]")
VOW = re.compile("[ً-ِْ]")
LAT = re.compile("[A-Za-z]")
NUM = re.compile(r"^[\d٠-٩۰-۹.,%/\-–()]+$")
MATH = re.compile(r"[=+×÷√∑∫±≤≥<>^∆Δαβγσμλπ]")
HEAD = ("title", "author", "rubric", "sectionHeading")
FURN = ("pageHeader", "pageFooter", "pageNumber")


def rules(scan, pages):
    """Long horizontal / vertical ruled lines per page at 60 dpi (table rules, frames, column rules)."""
    import cv2
    import fitz
    out = {}
    d = fitz.open(scan)
    for p in pages:
        try:
            pix = d[p - 1].get_pixmap(dpi=60, colorspace=fitz.csGRAY)
        except Exception:
            out[p] = (0, 0)
            continue
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
        bw = (img < 140).astype(np.uint8)
        h = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, pix.width // 6), 1)))
        v = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, pix.height // 14))))
        nh = cv2.connectedComponents(h)[0] - 1
        nv = cv2.connectedComponents(v)[0] - 1
        out[p] = (int(nh), int(nv))
    d.close()
    return out


def one(item):
    stem, azure, scan = item
    from inkscript.enrich import document, structure
    from inkscript.enrich.quran import check_document
    from inkscript.gold.draft import _columns
    try:
        doc = document.load(Path(azure))
        info = structure.analyse(doc)
        quotes = check_document(doc)
    except Exception as e:
        return [dict(stem=stem, error=f"{type(e).__name__}: {e}"[:200])]
    W = doc["words"]
    kinds = info["kinds"]
    qwords = {}
    for q in quotes:
        for k in q.get("doc_words", []):
            qwords[W[k]["page"]] = qwords.get(W[k]["page"], 0) + 1
    rr = rules(scan, sorted(doc["pages"]))
    rows = []
    for pn, pg in sorted(doc["pages"].items()):
        ws = [w for w in W if w["page"] == pn]
        lines = doc["lines"].get(pn, [])
        r = dict(stem=stem, page=pn, pages=len(doc["pages"]), words=len(ws), lines=len(lines),
                 angle=round(pg.get("angle") or 0.0, 2), w=round(pg["w"]), h=round(pg["h"]))
        if not ws:
            rows.append(r)
            continue
        arw = [w for w in ws if AR.search(w["text"])]
        r["latin"] = round(sum(1 for w in ws if LAT.search(w["text"])) / len(ws), 3)
        r["digits"] = round(sum(1 for w in ws if NUM.match(w["text"])) / len(ws), 3)
        r["vowelled"] = round(sum(1 for w in arw if VOW.search(w["text"])) / max(1, len(arw)), 3)
        r["lowconf"] = round(sum(1 for w in ws if (w["conf"] or 0) < 0.8) / len(ws), 3)
        r["hw"] = round(sum(1 for w in ws if w.get("hw", 0) >= 0.5) / len(ws), 3)
        r["quran_words"] = qwords.get(pn, 0)
        fl = hl = ul = math = grid = 0
        hs = [w["box"][3] - w["box"][1] for w in ws]
        for members in lines:
            lw = [W[k] for k in members]
            ks = [kinds[w["para"]] if w["para"] is not None and w["para"] < len(kinds) else None for w in lw]
            k = max(set(ks), key=ks.count)
            fl += k == "footnote"
            hl += k in HEAD
            ul += k in FURN
            t = " ".join(w["text"] for w in lw)
            ar = len(AR.findall(t))
            if len(MATH.findall(t)) >= 1 and ar <= 0.3 * len(t.replace(" ", "")) and len(t) >= 3:
                math += 1
            if len(lw) >= 3 and sum(1 for w in lw if NUM.match(w["text"])) >= 0.5 * len(lw):
                grid += 1
        r.update(footnote_lines=fl, heading_lines=hl, furniture_lines=ul, math=math, grid=grid)
        paras = {}
        for w in ws:
            if w["para"] is not None and (kinds[w["para"]] if w["para"] < len(kinds) else None) not in FURN:
                b = paras.setdefault(w["para"], list(w["box"]))
                b[0], b[1], b[2], b[3] = min(b[0], w["box"][0]), min(b[1], w["box"][1]), max(b[2], w["box"][2]), max(b[3], w["box"][3])
        cols = _columns(list(paras.values()), pg["w"]) if paras else []
        r["columns"] = max(cols) if cols else 0
        r["rules_h"], r["rules_v"] = rr.get(pn, (0, 0))
        r["body_h"] = round(statistics.median(hs), 1)
        rows.append(r)
    return rows


def main() -> int:
    """--shard K/N: this process does every N-th document from K (run two shards for two workers; a process
    pool hung here, so each shard is a plain loop). Appends to out/features.<K>.jsonl; resumable."""
    k, n = (int(x) for x in (sys.argv[sys.argv.index("--shard") + 1] if "--shard" in sys.argv else "0/1").split("/"))
    pool = json.loads((OUT / "pool.json").read_text())
    done = set()
    for f in OUT.glob("features*.jsonl"):
        done |= {json.loads(l)["stem"] for l in f.read_text().splitlines() if l.strip()}
    todo = [(s, p["azure"], p["scan"]) for i, (s, p) in enumerate(sorted(pool.items())) if i % n == k and s not in done]
    print(len(todo), "documents to do", flush=True)
    import time
    with open(OUT / f"features.{k}.jsonl", "a") as fh:
        for item in todo:
            t = time.time()
            rows = one(item)
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            print(item[0], len(rows), f"{time.time() - t:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
