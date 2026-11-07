"""Experiment 91, on the GPU host: catalogue-matched TITLE lines of page 1 (match91.py's rule), cut and labelled.

    python title91.py cut URLS.jsonl OUTDIR WORKERS     fetch each document's JSON (presigned), match its page 1 with
        the catalogue title (match91.match_page); when the match is confident and has a usable line (agree / differ),
        fetch the PDF, render page 1 (250 dpi, pypdfium2 5.12.1) and cut those lines exactly as the training lines are
        cut (common77.cut_line, train mode: 48 px, lines over 8 degrees or too wide left out).
        -> OUTDIR/ttl91-<w>-NNN.tar (<stem>_p001_lNNN_t91.jpg / .txt = Azure's line), manifest-ttl91-<w>.jsonl (one
           row per cut line: verdict, Azure text, the replaced words, size, set, era ...), docs-ttl91-<w>.jsonl (one
           row per document: match reason and similarity, also errors), look91/<key>.png (72 px crops of one document
           in 40, for looking at).  The PDF and JSON are deleted at once; resumable like cut83.py.
    python title91.py labels OUTDIR PRED.jsonl RESULTS   the label rule, with the current reader's reading (PRED =
        train89.py infer of v7-28M on the ttl91 crops) as the third vote:
          agree  -> Azure's line (it equals the catalogue in folded form; Azure's letters, marks and punctuation);
          differ -> if the reader's reading equals the catalogue-corrected line in folded form (spaces ignored), the
                    label is Azure's line with the differing words replaced by the READER's words there (the
                    catalogue's word as the ink shows it); if the reader equals Azure instead, or neither, the line
                    is dropped (Azure and the reader learn from the same labels, so their agreement against the
                    catalogue is not taken as proof).
        Documents with md5(stem) % 100 < 3 go to tdev91-000.tar (a title dev set, scored each epoch, never trained);
        the rest to train-t91-NNN.tar.  Also writes RESULTS/labels91_titles.jsonl (key -> label of every kept line)
        and RESULTS/overrides91.jsonl: the SAME line's ordinary training key (without _t91, if it was cut from page
        1 of an experiment 83 document) gets the title label (train documents) or is dropped (dev documents);
        and RESULTS/titles91_stats.json.
"""
from __future__ import annotations

import glob
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import time
from collections import Counter
from difflib import SequenceMatcher
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "x/e77"))
sys.path.insert(0, HERE)
from match91 import fw, match_page  # noqa: E402

SHARD = 5000
USE = ("agree", "differ")


def fetch(url: str, dst: str, tries: int = 4):
    import urllib.request
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


def look_doc(stem: str) -> bool:
    return int(hashlib.md5(stem.encode()).hexdigest(), 16) % 40 == 7


def dev_doc(stem: str) -> bool:
    return int(hashlib.md5(stem.encode()).hexdigest(), 16) % 100 < 3


def title_doc(d: dict, pages: list, open_pdf) -> tuple[dict, list, list]:
    """Match one document's page 1 and cut its usable title lines.  open_pdf() returns an open pdfium document (it
    is called only when a line is usable, so a PDF is fetched only for a confident match)."""
    import cv2
    from common77 import cut_line, encode, render_page
    stem = d["id"]
    rec = dict(id=stem, set=d["set"], era=d.get("tera", d["era"]), jcode=d["jcode"], year=d["year"])
    m = match_page(pages[0], d["title"], d.get("subtitle", "")) if pages else dict(ok=False, reason="no_pages")
    rec.update({k: m.get(k) for k in ("ok", "reason", "sim", "target", "n", "top", "t1_miss", "lines_on_page")})
    rec["verdicts"] = dict(Counter(l["verdict"] for l in m.get("lines", [])))
    use = [l for l in m.get("lines", []) if l["verdict"] in USE] if m.get("ok") else []
    rows, looks = [], []
    if use:
        pdf = open_pdf()
        img = render_page(pdf, 0)
        pg = pages[0]
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        skipped = Counter()
        for l in use:
            key = f"{stem}_p001_l{l['i']:03d}_t91"
            crop, info = cut_line(img, l["poly"], sx, sy)
            if crop is None:
                skipped[info["reason"]] += 1
                continue
            if look_doc(stem):
                lc, _ = cut_line(img, l["poly"], sx, sy, H=72, test=True)
                if lc is not None:
                    looks.append((key, lc))
            rows.append((key, encode(crop), l, info["W"]))
        rec["skipped"] = dict(skipped)
    rec["lines_cut"] = len(rows)
    return rec, rows, looks


class TitleOut:
    """One worker's title shards ttl91-<tag>-NNN.tar, manifest-ttl91-<tag>.jsonl, docs-ttl91-<tag>.jsonl, look91/."""

    def __init__(self, outdir: str, tag: str):
        import cv2  # noqa: F401
        self.outdir, self.tag = outdir, tag
        self.look = os.path.join(outdir, "look91")
        os.makedirs(self.look, exist_ok=True)
        self.shard_no = len(glob.glob(os.path.join(outdir, f"ttl91-{tag}-*.tar")))
        self.mf = open(os.path.join(outdir, f"manifest-ttl91-{tag}.jsonl"), "a", encoding="utf-8")
        self.df = open(os.path.join(outdir, f"docs-ttl91-{tag}.jsonl"), "a", encoding="utf-8")
        self.tar, self.n_in = None, SHARD

    def add(self, d, rec, rows, looks):
        import cv2
        for key, lc in looks:
            cv2.imwrite(os.path.join(self.look, key + ".png"), lc)
        for key, jpg, l, W in rows:
            if self.tar is None or self.n_in >= SHARD:
                if self.tar:
                    self.tar.close()
                self.tar = tarfile.open(os.path.join(self.outdir, f"ttl91-{self.tag}-{self.shard_no:03d}.tar"), "w")
                self.shard_no += 1
                self.n_in = 0
            for name, data in ((key + ".jpg", jpg), (key + ".txt", l["azure"].encode("utf-8"))):
                ti = tarfile.TarInfo(name)
                ti.size = len(data)
                self.tar.addfile(ti, io.BytesIO(data))
            self.n_in += 1
            self.mf.write(json.dumps(dict(key=key, stem=d["id"], set=d["set"], era=d.get("tera", d["era"]), jcode=d["jcode"],
                                          year=d["year"], i=l["i"], verdict=l["verdict"], azure=l["azure"], rep=l["rep"],
                                          rel=l["rel"], W=W, title=d["title"], subtitle=d.get("subtitle", ""),
                                          look=look_doc(d["id"])), ensure_ascii=False) + "\n")
        if self.tar:
            self.tar.fileobj.flush()
        self.mf.flush()
        self.df.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.df.flush()

    def close(self):
        if self.tar:
            self.tar.close()
        self.mf.close()
        self.df.close()


def work(args):
    wid, docs, outdir = args
    import cv2
    import pypdfium2 as pdfium
    from common77 import azure_pages
    cv2.setNumThreads(1)
    done = set()
    for f in glob.glob(os.path.join(outdir, "docs-ttl91-*.jsonl")):
        done |= {json.loads(l)["id"] for l in open(f, encoding="utf-8") if l.strip()}
    tmp = os.path.join(outdir, "tmp91", str(wid))
    os.makedirs(tmp, exist_ok=True)
    out = TitleOut(outdir, str(wid))
    nd, t0 = 0, time.time()
    for d in docs:
        stem = d["id"]
        if stem in done:
            continue
        js_f, pdf_f = os.path.join(tmp, stem + ".json"), os.path.join(tmp, stem + ".pdf")
        held = []

        def open_pdf():
            fetch(d["pdf"], pdf_f)
            held.append(pdfium.PdfDocument(pdf_f))
            return held[-1]
        try:
            fetch(d["json"], js_f)
            rec, rows, looks = title_doc(d, azure_pages(js_f), open_pdf)
            rec["bytes"] = sum(os.path.getsize(f) for f in (js_f, pdf_f) if os.path.exists(f))
        except Exception as e:  # noqa: BLE001
            rec = dict(id=stem, set=d["set"], era=d["era"], jcode=d["jcode"], year=d["year"],
                       error=f"{type(e).__name__}: {e}"[:300])
            rows, looks = [], []
        finally:
            for p in held:
                p.close()
            for f in (js_f, pdf_f):
                if os.path.exists(f):
                    os.remove(f)
        out.add(d, rec, rows, looks)
        nd += 1
        if nd % 100 == 0:
            print(f"w{wid}: {nd} docs, {time.time() - t0:.0f}s", flush=True)
    out.close()
    return nd


def cut(urls, outdir, nw):
    os.makedirs(outdir, exist_ok=True)
    docs = [json.loads(l) for l in open(urls, encoding="utf-8") if l.strip()]
    with Pool(nw, maxtasksperchild=1) as pool:
        r = pool.map(work, [(w, docs[w::nw], outdir) for w in range(nw)])
    print("TITLE_CUT_DONE", sum(r), flush=True)


# ------------------------------------------------------------------------------------------------ labels

def nospace(ws):
    return "".join(ws)


def corrected(azure: str, rep) -> list[str]:
    """Azure's folded words with the catalogue's words in place of the replaced ones."""
    w = fw(azure)
    out, k = [], 0
    reps = sorted(rep, key=lambda r: r[2])
    for a, b, pos in reps:
        n = len(a.split())
        out += w[k:pos] + b.split()
        k = pos + n
    return out + w[k:]


def merge_label(azure: str, reader: str) -> str:
    """Azure's tokens, with the reader's tokens where the two differ in folded form."""
    from common77 import clean_label
    A, R = clean_label(azure).split(), clean_label(reader).split()
    fa, fr = [" ".join(fw(t)) for t in A], [" ".join(fw(t)) for t in R]
    out = []
    for op, a0, a1, b0, b1 in SequenceMatcher(None, fa, fr, autojunk=False).get_opcodes():
        if op == "equal":
            out += A[a0:a1]
        elif op == "replace":
            out += R[b0:b1]
        elif op == "insert":
            out += [t for t in R[b0:b1] if fw(t)]
        else:                                   # delete: keep Azure's punctuation-only tokens, drop its extra words
            out += [t for t in A[a0:a1] if not fw(t)]
    return " ".join(out)


def labels(outdir, pred_f, res):
    os.makedirs(res, exist_ok=True)
    M = [json.loads(l) for f in sorted(glob.glob(os.path.join(outdir, "manifest-ttl91-*.jsonl")))
         for l in open(f, encoding="utf-8") if l.strip()]
    M = list({m["key"]: m for m in M}.values())                 # a resumed worker may repeat a document
    P = {json.loads(l)["key"]: json.loads(l)["pred"] for l in open(pred_f, encoding="utf-8")}
    lab, why = {}, {}
    st = Counter()
    for m in M:
        k = m["key"]
        if m["verdict"] == "agree":
            lab[k], why[k] = m["azure"], "agree"
        else:
            r = P.get(k, "")
            cat = corrected(m["azure"], m["rep"])
            if r and nospace(fw(r)) == nospace(cat):
                lab[k], why[k] = merge_label(m["azure"], r), "differ_reader_with_catalogue"
                if nospace(fw(lab[k])) != nospace(cat):
                    del lab[k]
                    why[k] = "differ_merge_failed"
            elif r and nospace(fw(r)) == nospace(fw(m["azure"])):
                why[k] = "differ_reader_with_azure"
            else:
                why[k] = "differ_three_way"
        st[f"{m['era']}|{why[k]}"] += 1
    # write the shards
    tr, dv = None, tarfile.open(os.path.join(outdir, "tdev91-000.tar"), "w")
    n_tr, sh = SHARD, 0
    kept, written = Counter(), set()
    with open(os.path.join(res, "labels91_titles.jsonl"), "w", encoding="utf-8") as fl, \
            open(os.path.join(res, "overrides91.jsonl"), "w", encoding="utf-8") as fo:
        for f in sorted(glob.glob(os.path.join(outdir, "ttl91-*.tar"))):
            with tarfile.open(f) as t:
                for mem in t:
                    k, ext = mem.name.rsplit(".", 1)
                    if ext != "jpg" or k not in lab or k in written:
                        continue
                    written.add(k)
                    data = t.extractfile(mem).read()
                    stem = k.rsplit("_p001_", 1)[0]
                    dev = dev_doc(stem)
                    if dev:
                        out = dv
                    else:
                        if tr is None or n_tr >= SHARD:
                            if tr:
                                tr.close()
                            tr = tarfile.open(os.path.join(outdir, f"train-t91-{sh:03d}.tar"), "w")
                            sh += 1
                            n_tr = 0
                        out = tr
                        n_tr += 1
                    for name, b in ((k + ".jpg", data), (k + ".txt", lab[k].encode("utf-8"))):
                        ti = tarfile.TarInfo(name)
                        ti.size = len(b)
                        out.addfile(ti, io.BytesIO(b))
                    kept["dev" if dev else "train"] += 1
                    fl.write(json.dumps(dict(key=k, label=lab[k], why=why[k], dev=dev), ensure_ascii=False) + "\n")
                    fo.write(json.dumps(dict(key=k[:-4], label=None if dev else lab[k]), ensure_ascii=False) + "\n")
    if tr:
        tr.close()
    dv.close()
    D = [json.loads(l) for f in sorted(glob.glob(os.path.join(outdir, "docs-ttl91-*.jsonl")))
         for l in open(f, encoding="utf-8") if l.strip()]
    D = list({d["id"]: d for d in D}.values())
    by = lambda f: dict(Counter(f(d) for d in D))  # noqa: E731
    stats = dict(docs=len(D), docs_error=sum("error" in d for d in D), docs_ok=sum(bool(d.get("ok")) for d in D),
                 docs_by_era_ok=by(lambda d: f"{d['era']}|{bool(d.get('ok'))}"),
                 docs_by_set_ok=by(lambda d: f"{d['set']}|{bool(d.get('ok'))}"),
                 reasons=by(lambda d: d.get("reason") or "error"),
                 line_verdicts_in_confident_runs=dict(sum((Counter(d.get("verdicts") or {}) for d in D if d.get("ok")),
                                                         Counter())),
                 lines_cut=len(M), label_decisions=dict(st), kept=dict(kept),
                 kept_by_era=dict(Counter(m["era"] for m in M if m["key"] in lab)),
                 kept_by_set=dict(Counter(m["set"] for m in M if m["key"] in lab)),
                 kept_journals=len({m["jcode"] for m in M if m["key"] in lab}),
                 kept_display_1p2=sum(1 for m in M if m["key"] in lab and m["rel"] >= 1.2),
                 azure_differs_from_catalogue_folded=sum(1 for m in M if m["verdict"] == "differ"),
                 label_differs_from_azure_strict=sum(1 for m in M if m["key"] in lab and lab[m["key"]] != m["azure"]))
    json.dump(stats, open(os.path.join(res, "titles91_stats.json"), "w"), ensure_ascii=False, indent=1)
    print("LABELS_DONE", json.dumps(stats, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "cut":
        cut(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif c == "labels":
        labels(sys.argv[2], sys.argv[3], sys.argv[4])
