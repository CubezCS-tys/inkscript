"""Experiment 90, step 1: the LOCKED test sets, fetched from S3 (presigned, read-only) and cut exactly as experiment 81.

    python3 build90.py docs journals          # system python3 (boto3): eligible documents of the 20 locked journals
                                              #   (experiment 84's rule, marc.db read only), order seed 90, signed URLs
    python3 build90.py docs old               # experiment 88's LOCKED_OLD_DOCS.json, signed URLs
    python3 build90.py fetch SET json|pdf     # fetch with the signed URLs into out/src/ (private, mode 600)
    python3 build90.py select SET             # choose pages (unit = a whole page) -> out/pages90_SET.jsonl
    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python build90.py build SET [WORKERS=2]
    ../81_heldout_scale/out/venv/bin/python build90.py merge

Opened ONCE for the final claim, with the owner's OK of 2026-11-05.  Nothing here is trained or tuned on.

Size (fixed before any page was opened):
- journals: documents of each locked journal in random order (seed 90), at most PER_DOC pages of a document (pages at
  random, seed = stem), taken round-robin over the documents until the journal holds JCAP lines (about 1,000; 20
  journals -> about 20,000 lines).  A page is never split.
- old documents: every page of every locked old document, unless that exceeds OLDCAP lines; then pages are taken
  round-robin over the documents (random order within each, seed = stem) until OLDCAP.
Cutting = build81.work without the pen signal: a 250-dpi pypdfium2 5.12.1 render, Azure's polygon,
cut_line(test=True) at 48 px (the image readers' input) -> out/crops48/test90-<page>.tar; per line journal, year,
era, Azure's text, arabic_share, the polygon's place on the page (top / bottom band, for the masthead detector).
Argon: no Argon reading exists for locked material (Argon was run on experiment 41's documents only; checked below).
"""
from __future__ import annotations

import io
import json
import os
import random
import re
import sqlite3
import sys
import tarfile
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
SRC = OUT / "src"
DATA = OUT / "data"
sys.path.insert(0, str(E / "88_truth_and_lock"))
sys.path.insert(0, str(E / "84_display_fonts"))

MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
IDS_MAIN = E / "44_bucket_map/out/ids_main.txt"
LISTING = E / "44_bucket_map/out/listing"
TYPES = ("بحوث ومقالات", "نصوص أدبية", "بحوث المؤتمرات", "عروض كتب", "افتتاحيات", "عروض رسائل")
STEM = re.compile(r"^(\d{4}-\d{3}-\d{3}-\d{3})/\1\.(pdf|json)$")
BUCKET = "mandumah-source-docs"
JCAP, PER_DOC, MAXDOCS, OLDCAP = 1000, 5, 24, 8000
AR = re.compile("[ؠ-يٱ-ۓۺ-ۿ]")
LAT = re.compile("[A-Za-zÀ-ɏ]")


def era(y) -> str:
    y = int(str(y)[:4])
    return "2000+" if y >= 2000 else "1980-1999" if y >= 1980 else "1950-1979" if y >= 1950 else "pre-1950"


def arabic_share(s: str):
    a, l = len(AR.findall(s)), len(LAT.findall(s))
    return round(a / (a + l), 3) if a + l else None


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if Path(p).exists() else []


def npages(pages, pf, pl):
    if pf and pl and pl >= pf:
        return pl - pf + 1
    m = re.search(r"\d+", pages or "")
    return int(m.group()) if m else None


def eligible_journal_docs():
    """Experiment 84's eligible-document rule (select84.main), for the 20 locked codes only."""
    from locked import locked_codes
    codes = locked_codes()
    main_ids = set(IDS_MAIN.read_text().split())
    c = sqlite3.connect(MARC, uri=True)
    q = f"""select p.stem, r.year_int, r.journal_code, r.pages, r.page_first, r.page_last
            from records r join pdf_ids p on p.rec = r.rec
            where r.year_int >= 1900 and r.year_int <= 2025 and r.language = 'ara'
              and r.type in ({','.join('?' * len(TYPES))})"""
    docs = {}
    for stem, y, jc, pg, pf, pl in c.execute(q, TYPES):
        if not jc or jc not in codes or stem in docs or stem not in main_ids:
            continue
        n = npages(pg, pf, pl)
        if not n or not 2 <= n <= 40:
            continue
        docs[stem] = dict(id=stem, year=int(y), era=era(y), jcode=jc)
    sizes = defaultdict(set)
    for f in sorted(LISTING.glob("mandumah-source-docs__*.tsv")):
        for line in f.open(encoding="utf-8"):
            m = STEM.match(line.split("\t", 1)[0])
            if m and m.group(1) in docs:
                sizes[m.group(1)].add(m.group(2))
    return [d for s, d in sorted(docs.items()) if sizes.get(s) == {"pdf", "json"}]


def cmd_docs(which: str, hours: float = 12):
    import boto3
    from locked_old import locked_docs
    from locked import locked_codes
    if which == "journals":
        D = eligible_journal_docs()
        rng = random.Random(90)
        byj = defaultdict(list)
        for d in D:
            byj[d["jcode"]].append(d)
        plan = []
        for jc in sorted(byj):
            L = byj[jc]
            rng.shuffle(L)
            for k, d in enumerate(L[:MAXDOCS]):
                plan.append(dict(d, order=k))
        assert {d["jcode"] for d in plan} <= locked_codes()
        print(len(D), "eligible documents;", len(plan), "in the plan;", Counter(d["jcode"] for d in plan))
    else:
        L = json.loads((E / "88_truth_and_lock/LOCKED_OLD_DOCS.json").read_text(encoding="utf-8"))["documents"]
        plan = []
        for k, d in enumerate(L):
            y = d.get("year") or d.get("year_int")
            plan.append(dict(id=d["stem"], year=int(y), era=era(y), jcode=d["stem"][:4], order=k))
        assert {d["id"] for d in plan} <= locked_docs()
        print(len(plan), "locked old documents;", Counter(d["era"] for d in plan))
    s3 = boto3.client("s3", region_name="eu-north-1")
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / f"urls_{which}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        os.chmod(out, 0o600)
        for d in plan:
            u = {ext: s3.generate_presigned_url("get_object", Params=dict(Bucket=BUCKET, Key=f"{d['id']}/{d['id']}.{ext}"),
                                                ExpiresIn=int(hours * 3600)) for ext in ("pdf", "json")}
            f.write(json.dumps(dict(d, **u)) + "\n")
    print(len(plan), "documents signed for", hours, "hours ->", out)


def fetch(url: str, dst: Path, tries: int = 4):
    tmp = Path(str(dst) + ".part")
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                os.chmod(tmp, 0o600)
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            tmp.rename(dst)
            return
        except Exception:  # noqa: BLE001
            if k == tries - 1:
                raise
            time.sleep(3 * (k + 1))


def cmd_fetch(which: str, ext: str):
    SRC.mkdir(parents=True, exist_ok=True)
    os.chmod(SRC, 0o700)
    U = jl(DATA / f"urls_{which}.jsonl")
    if ext == "pdf":                                   # only documents with chosen pages
        need = {p["stem"] for p in jl(OUT / f"pages90_{which}.jsonl")}
        U = [u for u in U if u["id"] in need]
    n = err = 0
    for u in U:
        dst = SRC / f"{u['id']}.{ext}"
        if dst.exists():
            continue
        try:
            hold = os.environ.get("HOLD_DIR")            # the old documents' files live outside the repo (lead)
            if hold:
                fetch(u[ext], Path(hold) / dst.name)
                dst.symlink_to(Path(hold) / dst.name)
                n += 1
                continue
            fetch(u[ext], dst)
            n += 1
        except Exception as e:  # noqa: BLE001
            err += 1
            print("  failed", u["id"], ext, type(e).__name__, str(e)[:120], flush=True)
    print(which, ext, "fetched", n, "errors", err, flush=True)


def page_lines(stem: str):
    sys.path.insert(0, str(E / "77_scratch_reader"))
    from common77 import azure_pages, nonempty_lines
    return [len(nonempty_lines(pg)) for pg in azure_pages(SRC / f"{stem}.json")]


def cmd_select(which: str):
    U = [u for u in jl(DATA / f"urls_{which}.jsonl") if (SRC / f"{u['id']}.json").exists()]
    groups = defaultdict(list)
    for u in U:
        groups[u["jcode"] if which == "journals" else "old"].append(u)
    chosen, st = [], {}
    for g, docs in sorted(groups.items()):
        docs.sort(key=lambda u: u["order"])
        queues = []
        for u in docs:
            n = page_lines(u["id"])
            pg = [p for p in range(1, len(n) + 1) if n[p - 1]]
            random.Random(u["id"]).shuffle(pg)
            if which == "journals":
                pg = pg[:PER_DOC]
            queues.append([(u, p, n[p - 1]) for p in pg])
        cap = JCAP if which == "journals" else OLDCAP
        total = sum(x[2] for q in queues for x in q)
        tot = 0
        if total <= cap:
            picks = [x for q in queues for x in q]
            tot = total
        else:
            picks = []
            while any(queues) and tot < cap:
                for q in queues:
                    if q and tot < cap:
                        x = q.pop(0)
                        picks.append(x)
                        tot += x[2]
        for u, p, n in picks:
            chosen.append(dict(stem=u["id"], page=p, jcode=u["jcode"], year=str(u["year"]), era=u["era"], lines=n,
                               set=which))
        st[g] = dict(docs=len({u["id"] for u, _, _ in picks}), pages=len(picks), lines=tot, available_lines=total)
    chosen.sort(key=lambda p: (p["stem"], p["page"]))
    with open(OUT / f"pages90_{which}.jsonl", "w", encoding="utf-8") as f:
        for p in chosen:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    by_era = Counter()
    for p in chosen:
        by_era[p["era"]] += p["lines"]
    summ = dict(set=which, pages=len(chosen), docs=len({p["stem"] for p in chosen}), lines=sum(p["lines"] for p in chosen),
                lines_by_era=dict(by_era), groups=st)
    (OUT / f"select90_{which}.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    print(json.dumps({k: summ[k] for k in ("set", "pages", "docs", "lines", "lines_by_era")}))


def work(p: dict):
    sys.path.insert(0, str(E / "77_scratch_reader"))
    import cv2
    import pypdfium2 as pdfium
    from common77 import azure_pages, clean_label, cut_line, encode, nonempty_lines, render_page
    cv2.setNumThreads(1)
    pid = f"{p['stem']}_p{p['page']:03d}"
    done = OUT / "meta" / (f"{pid}.jsonl" if not p.get("only") else f"{pid}_titles.jsonl")
    if done.exists():
        return pid, 0
    pg = azure_pages(SRC / f"{p['stem']}.json")[p["page"] - 1]
    doc = pdfium.PdfDocument(str(SRC / f"{p['stem']}.pdf"))
    if p["page"] - 1 >= len(doc):
        doc.close()
        return pid, -1
    img = render_page(doc, p["page"] - 1)
    doc.close()
    sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
    rows = []
    tmp = OUT / "crops48" / f"test90-{pid}.tar.part"
    tar = tarfile.open(tmp, "w")
    only = set(p.get("only") or [])
    for ln in nonempty_lines(pg):
        if only and ln["i"] not in only:
            continue
        key = f"{pid}_l{ln['i']:03d}"
        lab = clean_label(ln["text"])
        ys = ln["poly"][1::2] if ln["poly"] else [0]
        row = dict(key=key, stem=p["stem"], page=p["page"], i=ln["i"], jcode=p["jcode"], year=p["year"], era=p["era"],
                   set=p["set"], azure=lab, argon=None, argon_page=False, arabic_share=arabic_share(lab), cut=False,
                   y0=round(min(ys) / pg["height"], 4), y1=round(max(ys) / pg["height"], 4))
        crop, info = cut_line(img, ln["poly"], sx, sy, test=True)
        if crop is not None:
            row.update(cut=True, W=info["W"], ang=info["ang"], h=info["h"])
            for name, data in ((key + ".jpg", encode(crop)), (key + ".txt", lab.encode())):
                ti = tarfile.TarInfo(name)
                ti.size = len(data)
                tar.addfile(ti, io.BytesIO(data))
        rows.append(row)
    tar.close()
    tmp.rename(OUT / "crops48" / f"test90-{pid}.tar")
    with open(str(done) + ".part", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    Path(str(done) + ".part").rename(done)
    return pid, len(rows)


def cmd_build(which: str, nw: int):
    from multiprocessing import Pool
    for d in ("crops48", "meta"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    P = jl(OUT / f"pages90_{which}.jsonl")
    sfx = "_titles" if which == "titles" else ""
    todo = [p for p in P if not (OUT / "meta" / f"{p['stem']}_p{p['page']:03d}{sfx}.jsonl").exists()
            and (SRC / f"{p['stem']}.pdf").exists()]
    print(f"{len(todo)} of {len(P)} pages to build, {nw} workers", flush=True)
    t0, n = time.time(), 0
    with Pool(nw, maxtasksperchild=50) as pool:
        for k, (pid, m) in enumerate(pool.imap_unordered(work, todo), 1):
            n += max(m, 0)
            if k % 25 == 0:
                print(f"{k}/{len(todo)} pages, {n} lines, {time.time() - t0:.0f}s", flush=True)
    print("built", n, "lines", flush=True)


def cmd_merge():
    from locked_old import is_locked_any
    rows = []
    for which in ("journals", "old", "titles"):
        sfx = "_titles" if which == "titles" else ""
        for p in jl(OUT / f"pages90_{which}.jsonl"):
            f = OUT / "meta" / f"{p['stem']}_p{p['page']:03d}{sfx}.jsonl"
            if f.exists():
                rows += jl(f)
    assert all(is_locked_any(r["key"]) for r in rows), "a line outside the locked sets"
    with open(OUT / "lines90.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    c = Counter()
    for r in rows:
        c[f"{r['set']}|lines"] += 1
        c[f"{r['set']}|cut"] += r["cut"]
        s = r["arabic_share"]
        c[f"{r['set']}|" + ("no_letters" if s is None else "mostly_latin" if s < 0.5 else "arabic")] += 1
        c[f"era|{r['era']}"] += 1
    argon = E / "41_azure_structure/out/argon/labels"
    c["argon_docs"] = sum((argon / f"{s}.json").exists() for s in {r["stem"] for r in rows})
    print(dict(sorted(c.items())))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "docs":
        cmd_docs(sys.argv[2])
    elif c == "fetch":
        cmd_fetch(sys.argv[2], sys.argv[3])
    elif c == "select":
        cmd_select(sys.argv[2])
    elif c == "build":
        cmd_build(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2)
    elif c == "merge":
        cmd_merge()
