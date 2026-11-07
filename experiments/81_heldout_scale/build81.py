"""Experiment 81, step 1: the large held-out test set (read only on every other experiment's files).

    nice -n 19 ionice -c3 out/venv/bin/python build81.py select
    nice -n 19 ionice -c3 out/venv/bin/python build81.py build [WORKERS=4]
    out/venv/bin/python build81.py merge

Source: experiment 76's inventory, held-out journals only (split76.json "test", 27 codes; 26 of them have articles on
disk: the 27th, 2399, is lab document 1, which is not in the inventory).  Checked first: no line of these journals is
in experiment 77's training/dev manifests, experiment 79's real-training jobs or experiment 77's select77.json (the
synthetic text of experiment 78 asserts the same in text78.py / common78.py).

Selection (unit = a whole page, so a page is rendered once): every page of every held-out article, except that a
journal is capped at JCAP lines (pages at random, seed 81); journal 0097 (107k of the 126k held-out lines, all
2000+) at J97 lines.  The owner's 20 yardstick pages (experiment 34) are always in, for calibration.

Per page (250 dpi pypdfium2 5.12.1 render, experiment 77's DPI): every non-empty Azure line is cut
  - at 48 px by experiment 77's cut_line(test=True) -> out/crops48/test81-<page>.tar (+ manifest), for the image readers;
  - at 96 px from the same render (as experiment 79's realtest79.py) -> its pen signal by sig79.line_signal
    (skeleton, start 'top', no flags: what p3t was trained on) -> out/sig/<page>.npz.
Per line: journal, year, era, Azure text, Argon text (where experiment 41's Argon labels exist), arabic_share.
Saved page by page (a stopped build resumes).
"""
from __future__ import annotations

import io
import json
import random
import re
import sys
import tarfile
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "79_signal_reader"))

from common77 import azure_pages, clean_label, cut_line, encode, fixpath, nonempty_lines, render_page, test_codes  # noqa: E402

INV = E / "76_finetune_pilot/out/inventory76.jsonl"
ARGON = E / "41_azure_structure/out/argon/labels"
JCAP, J97 = 2000, 3000
AR = re.compile("[ؠ-يٱ-ۓۺ-ۿ]")
LAT = re.compile("[A-Za-zÀ-ɏ]")


def era(y) -> str:
    y = int(str(y)[:4])
    return "2000+" if y >= 2000 else "1950-1999" if y >= 1950 else "pre-1950"


def arabic_share(s: str) -> float | None:
    a, l = len(AR.findall(s)), len(LAT.findall(s))
    return round(a / (a + l), 3) if a + l else None


def verify_heldout():
    held = test_codes()
    import glob
    n = bad = 0
    for f in glob.glob(str(E / "77_scratch_reader/out/shards/manifest-*.jsonl")):
        for l in open(f, encoding="utf-8"):
            d = json.loads(l)
            n += 1
            bad += d["key"][:4] in held
    S = json.loads((E / "77_scratch_reader/out/select77.json").read_text())
    sel = [x if isinstance(x, str) else x.get("stem", "") for k in ("train", "dev") for x in S[k]]
    jobs = [json.loads(l)["stem"] for f in ("jobs_train", "jobs_dev")
            for l in open(E / f"79_signal_reader/out/up_real/{f}.jsonl", encoding="utf-8")]
    res = dict(exp77_manifest_lines=n, exp77_heldout_lines=bad, exp77_select_articles=len(sel),
               exp77_select_heldout=sum(s[:4] in held for s in sel), exp79_real_jobs=len(jobs),
               exp79_real_heldout=sum(s[:4] in held for s in jobs),
               exp78="text78.py / bg78.py / common78.pages80 assert every source page against split76.json")
    assert res["exp77_heldout_lines"] == res["exp77_select_heldout"] == res["exp79_real_heldout"] == 0, res
    return res


def select():
    held = test_codes()
    inv = [json.loads(l) for l in open(INV, encoding="utf-8")]
    H = [r for r in inv if r["jcode"] in held and r.get("azure_ok") and r.get("pdf_ok") and not r.get("dup")]
    yard = {(g["stem"], g["page"]) for g in (json.loads(f.read_text(encoding="utf-8"))
                                             for f in (E / "34_yardstick/out/gold").glob("*.json")) if g.get("status") == "done"}
    rng = random.Random(81)
    pages = []
    for r in H:
        pg = azure_pages(fixpath(r["azure"]))
        for p, P in enumerate(pg, 1):
            n = len(nonempty_lines(P))
            if n:
                pages.append(dict(stem=r["stem"], page=p, jcode=r["jcode"], year=str(r["year"])[:4], era=era(r["year"]),
                                  journal=r["journal"], azure=str(fixpath(r["azure"])), pdf=str(fixpath(r["pdf"])),
                                  lines=n, yard=(r["stem"], p) in yard))
    rng.shuffle(pages)
    pages.sort(key=lambda p: not p["yard"])            # yardstick pages first (always in), the rest in random order
    per_j, chosen = Counter(), []
    for p in pages:
        cap = J97 if p["jcode"] == "0097" else JCAP
        if not p["yard"] and per_j[p["jcode"]] + p["lines"] > cap:
            continue
        per_j[p["jcode"]] += p["lines"]
        chosen.append(p)
    chosen.sort(key=lambda p: (p["stem"], p["page"]))
    by_era = Counter()
    for p in chosen:
        by_era[p["era"]] += p["lines"]
    st = dict(held_codes=len(held), articles_on_disk=len(H), journals_on_disk=len({r["jcode"] for r in H}),
              pages_on_disk=len(pages), lines_on_disk=sum(p["lines"] for p in pages),
              chosen_pages=len(chosen), chosen_lines=sum(p["lines"] for p in chosen),
              chosen_articles=len({p["stem"] for p in chosen}), lines_by_era=dict(by_era),
              lines_by_journal=dict(per_j.most_common()), yard_pages=sum(p["yard"] for p in chosen),
              verify=verify_heldout())
    OUT.mkdir(exist_ok=True)
    with open(OUT / "pages81.jsonl", "w", encoding="utf-8") as f:
        for p in chosen:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    (OUT / "select81.json").write_text(json.dumps(st, ensure_ascii=False, indent=1))
    print(json.dumps(st, ensure_ascii=False, indent=1))


def argon_lines(stem: str, page: int) -> dict[int, str]:
    f = ARGON / f"{stem}.json"
    if not f.exists():
        return {}
    d = json.loads(f.read_text(encoding="utf-8"))
    out: dict[int, list[str]] = {}
    for ln in sorted((x for x in d["lines"] if x["page"] == page), key=lambda x: x["id"]):
        k = int(re.match(r"\d+", ln["id"].split(":")[1]).group())
        out.setdefault(k, []).append(ln["text"])
    return {k: " ".join(v) for k, v in out.items()}


def work(p: dict):
    import cv2
    import numpy as np
    import pypdfium2 as pdfium
    from sig79 import features, line_signal
    cv2.setNumThreads(1)
    pid = f"{p['stem']}_p{p['page']:03d}"
    done = OUT / "meta" / f"{pid}.jsonl"
    if done.exists():
        return pid, 0
    pg = azure_pages(p["azure"])[p["page"] - 1]
    doc = pdfium.PdfDocument(p["pdf"])
    img = render_page(doc, p["page"] - 1)
    doc.close()
    sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
    arg = argon_lines(p["stem"], p["page"])
    rows, feats = [], {}
    tmp = OUT / "crops48" / f"test81-{pid}.tar.part"
    tar = tarfile.open(tmp, "w")
    for ln in nonempty_lines(pg):
        key = f"{pid}_l{ln['i']:03d}"
        lab = clean_label(ln["text"])
        row = dict(key=key, stem=p["stem"], page=p["page"], i=ln["i"], jcode=p["jcode"], year=p["year"], era=p["era"],
                   yard=p["yard"], azure=lab, argon=clean_label(arg[ln["i"]]) if ln["i"] in arg else None,
                   argon_page=bool(arg), arabic_share=arabic_share(lab), cut=False)
        crop, info = cut_line(img, ln["poly"], sx, sy, test=True)
        if crop is not None:
            row.update(cut=True, W=info["W"], ang=info["ang"], h=info["h"])
            for name, data in ((key + ".jpg", encode(crop)), (key + ".txt", lab.encode())):
                ti = tarfile.TarInfo(name)
                ti.size = len(data)
                tar.addfile(ti, io.BytesIO(data))
            c96, _ = cut_line(img, ln["poly"], sx, sy, H=96, test=True)
            try:
                F = features(line_signal(c96, start_rule="top", centre="skeleton", flags=False))
            except Exception:  # noqa: BLE001
                F = np.zeros((0, 13), np.float32)
            feats[key] = F.astype(np.float16)
            row["points"] = int(len(F))
        rows.append(row)
    tar.close()
    tmp.rename(OUT / "crops48" / f"test81-{pid}.tar")
    np.savez_compressed(OUT / "sig" / f"{pid}.npz", **feats)
    with open(str(done) + ".part", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    Path(str(done) + ".part").rename(done)
    return pid, len(rows)


def build(nw: int):
    from multiprocessing import Pool
    for d in ("crops48", "sig", "meta"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    P = [json.loads(l) for l in open(OUT / "pages81.jsonl", encoding="utf-8")]
    todo = [p for p in P if not (OUT / "meta" / f"{p['stem']}_p{p['page']:03d}.jsonl").exists()]
    print(f"{len(todo)} of {len(P)} pages to build, {nw} workers", flush=True)
    t0, n = time.time(), 0
    with Pool(nw, maxtasksperchild=50) as pool:
        for k, (pid, m) in enumerate(pool.imap_unordered(work, todo), 1):
            n += m
            if k % 20 == 0:
                print(f"{k}/{len(todo)} pages, {n} lines, {time.time() - t0:.0f}s", flush=True)
    print("built", n, "lines", flush=True)


def merge():
    P = [json.loads(l) for l in open(OUT / "pages81.jsonl", encoding="utf-8")]
    rows = []
    for p in P:
        f = OUT / "meta" / f"{p['stem']}_p{p['page']:03d}.jsonl"
        rows += [json.loads(l) for l in open(f, encoding="utf-8")]
    with open(OUT / "lines81.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    c = Counter()
    for r in rows:
        c["lines"] += 1
        c["cut"] += r["cut"]
        s = r["arabic_share"]
        c["no_letters" if s is None else "mostly_latin" if s < 0.5 else "arabic"] += 1
        c["argon_line"] += r["argon"] is not None
        c["yard"] += r["yard"]
    print(dict(c))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "select":
        select()
    elif cmd == "build":
        build(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    elif cmd == "merge":
        merge()
