"""Experiment 85, step 2b: judge crops of the sampled held lines, cut here from S3 (presigned URLs) or experiment 80's
local pull, exactly as experiment 81's judge81.py cuts them (300-dpi pypdfium2 5.12.1 render, Azure's polygon,
common77.cut_line(H=96, test=True), PNG).

    nice -n 19 ionice -c3 .venv/bin/python experiments/85_disputes/cut85.py LINES.jsonl URLS.jsonl [WORKERS=2]

Each document is fetched to out/dl/, its needed pages rendered, its lines cut to out/judge/crops/<key>.png, then the
PDF and JSON are deleted.  A line is checked: Azure's line i of that page (nonempty_lines numbering) must have the same
cleaned text as the held line's Azure text; mismatches are logged and not cut.  Resumable (cut lines are skipped).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common85 import OUT, guard  # noqa: E402
from common77 import azure_pages, clean_label, cut_line, nonempty_lines, render_page  # noqa: E402

CROPS = OUT / "judge/crops"
DL = OUT / "dl"
LOCAL80 = HERE.parent / "80_old_print_pull/data/fetch"
LOG = OUT / "judge/cut85.log"


def fetch(url, dst, tries=4):
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


def download(job):
    doc, items, urls = job
    if (LOCAL80 / doc / f"{doc}.pdf").exists():
        return job
    tmp = DL / doc
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        fetch(urls["json"], tmp / f"{doc}.json")
        fetch(urls["pdf"], tmp / f"{doc}.pdf")
    except Exception as e:  # noqa: BLE001
        urls = dict(urls, error=f"download: {type(e).__name__}: {str(e)[:150]}")
    return doc, items, urls


def work(args):
    doc, items, urls = args
    import cv2
    import pypdfium2 as pdfium
    cv2.setNumThreads(1)
    res = dict(doc=doc, cut=0, mismatch=[], error=None)
    tmp = None
    try:
        if (LOCAL80 / doc / f"{doc}.pdf").exists():
            pdf, js = LOCAL80 / doc / f"{doc}.pdf", LOCAL80 / doc / f"{doc}.json"
        else:
            tmp = DL / doc                      # fetched beforehand by download() (threads, no CPU to speak of)
            pdf, js = tmp / f"{doc}.pdf", tmp / f"{doc}.json"
            if urls.get("error"):
                raise RuntimeError(urls["error"])
        pages = azure_pages(js)
        d = pdfium.PdfDocument(str(pdf))
        byp = defaultdict(list)
        for it in items:
            byp[it["page"]].append(it)
        for p, its in sorted(byp.items()):
            pg = pages[p - 1]
            img = render_page(d, p - 1, dpi=300)
            sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
            L = {ln["i"]: ln for ln in nonempty_lines(pg)}
            for it in its:
                ln = L.get(it["i"])
                if ln is None or clean_label(ln["text"]) != clean_label(it["azure"]):
                    res["mismatch"].append(it["key"])
                    continue
                c, _ = cut_line(img, ln["poly"], sx, sy, H=96, test=True)
                if c is not None:
                    cv2.imwrite(str(CROPS / f"{it['key']}.png"), c)
                    res["cut"] += 1
        d.close()
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        if tmp is not None:
            for f in tmp.glob("*"):
                f.unlink()
            tmp.rmdir()
    return res


def main():
    lines = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    urls = {d["id"]: d for d in map(json.loads, open(sys.argv[2], encoding="utf-8"))} if len(sys.argv) > 2 else {}
    W = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    assert W <= 2, "at most 2 cores on this shared machine"
    try:
        guard([d["key"] for d in lines], "crop")
    except RuntimeError as e:      # list not written yet: crops stay here, unseen; judge85 refuses until it passes
        print("WARNING:", e, flush=True)
    CROPS.mkdir(parents=True, exist_ok=True)
    by = defaultdict(list)
    for d in lines:
        if (CROPS / f"{d['key']}.png").exists():
            continue
        stem, rest = d["key"].split("_p")
        p, i = rest.split("_l")
        by[stem].append(dict(key=d["key"], page=int(p), i=int(i), azure=d["azure"]))
    jobs = [(doc, its, urls.get(doc, {})) for doc, its in sorted(by.items())]
    print(f"{len(jobs)} documents, {sum(len(j[1]) for j in jobs)} lines to cut", flush=True)
    n = 0
    from concurrent.futures import ThreadPoolExecutor
    with Pool(W) as pool, ThreadPoolExecutor(12) as tp, open(LOG, "a", encoding="utf-8") as log:
        # downloads run ahead in 12 threads, at most ~48 documents ahead of the two cutting processes
        def ahead():
            futs, it = [], iter(jobs)
            for j in it:
                futs.append(tp.submit(download, j))
                if len(futs) >= 48:
                    yield futs.pop(0).result()
            for f in futs:
                yield f.result()
        for r in pool.imap_unordered(work, ahead()):
            n += 1
            log.write(json.dumps(r) + "\n")
            log.flush()
            if n % 100 == 0:
                print(f"{n}/{len(jobs)} documents", time.strftime("%H:%M:%S"), flush=True)
    print("crops:", len(list(CROPS.glob("*.png"))))


if __name__ == "__main__":
    main()
