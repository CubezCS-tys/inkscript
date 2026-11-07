"""Experiment 91: experiment 83's cut83.py (copied 2026-11-06) with ONE addition: when a document's URL row carries
its catalogue title (urls lists of presign91host.py), its page 1 also goes through experiment 91's title matcher
(title91.title_doc, with the PDF and JSON already fetched, so no extra download) and its usable title lines are
written as ttl91-<PREFIX>-<worker>-NNN.tar / manifest- / docs-ttl91-<PREFIX>-<worker>.jsonl next to the ordinary
shards.  The ordinary cut is unchanged.

Experiment 83, step 2 (runs on the GPU host): fetch each new document with its presigned URLs and cut its lines
exactly as experiment 77's build77.py does (its common77.py, unchanged: 250 dpi pypdfium2 render, Azure's polygon,
upright, padded, 48 px, grey JPEG q80, label = clean_label(Azure's text); lines over 8 degrees, tiny or too wide are
left out, as in build77).

    python cut83.py URLS.jsonl OUTDIR WORKERS [PREFIX=train-n83]

URLS.jsonl: one line per document {id, year, era, jcode, max_pages, pdf, json} (pdf/json: time-limited GET URLs).
Pages: those with Azure lines; at most max_pages of them, chosen at random (seed = the document id).
Pages: a document's "pages" list when it has one (experiment 77's own pages, re-cut from S3 so nothing large is
uploaded from here; checked bit-identical to experiment 77's shards on one article).
OUTDIR gets PREFIX-<worker>-<NNN>.tar shards (members <key>.jpg, <key>.txt), manifest-PREFIX-<worker>.jsonl (one
line per cut line, build77's fields + era) and docs-PREFIX-<worker>.jsonl (one line per document, also errors).
The trainer reads every train-*.tar as training data and dev-*.tar as dev, so PREFIX is train-n83 (new documents),
train-r77 / dev-r77 (experiment 77's train / dev pages) or train-o80 (experiment 80's pull).
A document's crops are written only once all of its pages are cut, so a stopped run resumes cleanly (documents in
docs-PREFIX-*.jsonl are skipped).  The PDF and JSON are deleted as soon as the document is cut.
"""
from __future__ import annotations

import glob
import io
import json
import os
import random
import re
import sys
import tarfile
import time
import urllib.request
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "x/e77"))
from common77 import azure_pages, clean_label, cut_line, encode, nonempty_lines, render_page  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from title91 import TitleOut, title_doc  # noqa: E402

SHARD = 5000
ARABIC = re.compile("[ؠ-يٱ-ۓۺ-ۿ]")
LATIN = re.compile("[A-Za-z]")


def fetch(url: str, dst: str, tries: int = 4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(dst, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            return
        except Exception:  # noqa: BLE001
            if k == tries - 1:
                raise
            time.sleep(3 * (k + 1))


def work(args):
    wid, docs, outdir, prefix = args
    import cv2
    import pypdfium2 as pdfium
    cv2.setNumThreads(1)
    done = set()
    for f in glob.glob(os.path.join(outdir, f"docs-{prefix}-*.jsonl")):
        done |= {json.loads(l)["id"] for l in open(f, encoding="utf-8") if l.strip()}
    shard_no = len(glob.glob(os.path.join(outdir, f"{prefix}-{wid}-*.tar")))
    tmp = os.path.join(outdir, "tmp", str(wid))
    os.makedirs(tmp, exist_ok=True)
    mf = open(os.path.join(outdir, f"manifest-{prefix}-{wid}.jsonl"), "a", encoding="utf-8")
    df = open(os.path.join(outdir, f"docs-{prefix}-{wid}.jsonl"), "a", encoding="utf-8")
    tar, n_in, t0, nd = None, SHARD, time.time(), 0
    tout = TitleOut(outdir, f"{prefix}-{wid}")
    for d in docs:
        if d["id"] in done:
            continue
        stem = d["id"]
        pdf_f, js_f = os.path.join(tmp, stem + ".pdf"), os.path.join(tmp, stem + ".json")
        rec = dict(id=stem, year=d["year"], era=d.get("era"), jcode=d["jcode"])
        skipped = Counter()
        crops = []
        try:
            fetch(d["json"], js_f)
            fetch(d["pdf"], pdf_f)
            rec["bytes"] = os.path.getsize(pdf_f) + os.path.getsize(js_f)
            pgs = azure_pages(js_f)
            pdf = pdfium.PdfDocument(pdf_f)
            if d.get("title"):                    # exp 91: the title hook (page 1, the files already here)
                try:
                    tres = title_doc(d, pgs, lambda: pdf)
                except Exception as e:  # noqa: BLE001
                    tres = (dict(id=stem, set=d.get("set"), era=d.get("tera", d.get("era")), jcode=d["jcode"], year=d["year"],
                                 error=f"{type(e).__name__}: {e}"[:300]), [], [])
                tout.add(d, *tres)
            ar = la = 0
            todo = [k + 1 for k, pg in enumerate(pgs) if nonempty_lines(pg)]
            if d.get("pages"):
                todo = [p for p in d["pages"] if p - 1 < len(pgs)]
            elif d.get("max_pages") and len(todo) > d["max_pages"]:
                todo = sorted(random.Random(stem).sample(todo, d["max_pages"]))
            for page in todo:
                if page - 1 >= len(pdf):
                    skipped["page_missing"] += 1
                    continue
                pg = pgs[page - 1]
                lines = nonempty_lines(pg)
                if not lines:
                    continue
                img = render_page(pdf, page - 1)
                sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
                for ln in lines:
                    lab = clean_label(ln["text"])
                    if not lab or not ln["poly"]:
                        skipped["empty"] += 1
                        continue
                    ar += len(ARABIC.findall(lab))
                    la += len(LATIN.findall(lab))
                    crop, info = cut_line(img, ln["poly"], sx, sy)
                    if crop is None:
                        skipped[info["reason"]] += 1
                        continue
                    key = f"{stem}_p{page:03d}_l{ln['i']:03d}"
                    crops.append((key, encode(crop), lab, page, ln["i"], info["W"]))
            pdf.close()
            rec.update(pages=len(pgs), pages_cut=len(todo), lines=len(crops), arabic_share=round(ar / max(1, ar + la), 3))
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
            crops = []
        finally:
            for f in (pdf_f, js_f):
                if os.path.exists(f):
                    os.remove(f)
        for key, jpg, lab, page, i, W in crops:
            if tar is None or n_in >= SHARD:
                if tar:
                    tar.close()
                tar = tarfile.open(os.path.join(outdir, f"{prefix}-{wid}-{shard_no:03d}.tar"), "w")
                shard_no += 1
                n_in = 0
            for name, data in ((key + ".jpg", jpg), (key + ".txt", lab.encode("utf-8"))):
                ti = tarfile.TarInfo(name)
                ti.size = len(data)
                tar.addfile(ti, io.BytesIO(data))
            n_in += 1
            mf.write(json.dumps(dict(key=key, stem=stem, page=page, i=i, jcode=d["jcode"], year=d["year"], era=d.get("era"),
                                     W=W, label=lab, shard=f"{prefix}-{wid}-{shard_no - 1:03d}.tar"),
                                ensure_ascii=False) + "\n")
        if tar:
            tar.fileobj.flush()
        mf.flush()
        rec["skipped"] = dict(skipped)
        df.write(json.dumps(rec, ensure_ascii=False) + "\n")
        df.flush()
        nd += 1
        if nd % 25 == 0:
            print(f"w{wid}: {nd} docs, {time.time() - t0:.0f}s", flush=True)
    if tar:
        tar.close()
    mf.close()
    df.close()
    tout.close()
    return dict(wid=wid, docs=nd)


def main():
    urls, outdir, nw = sys.argv[1], sys.argv[2], int(sys.argv[3])
    prefix = sys.argv[4] if len(sys.argv) > 4 else "train-n83"
    os.makedirs(outdir, exist_ok=True)
    docs = [json.loads(l) for l in open(urls, encoding="utf-8") if l.strip()]
    jobs = [(w, docs[w::nw], outdir, prefix) for w in range(nw)]
    with Pool(nw, maxtasksperchild=1) as pool:
        r = pool.map(work, jobs)
    print("CUT_DONE", r, flush=True)


if __name__ == "__main__":
    main()
