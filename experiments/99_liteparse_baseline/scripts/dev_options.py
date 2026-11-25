"""Choose LiteParse OCR options on 5 DEV articles outside the exam (DEV_STEMS.json), never on the exam.

For 2 pages per dev article (page 1 and the middle page) runs each candidate option set on the 300-dpi page image and
compares the words LiteParse returns with Azure's words on that page (order-free word F1 and a letter-level score on
the page's words; Azure is ~1% wrong, enough to rank options).  Writes out/dev/options/<cand>/<stem>_pNNN.json and
out/dev/options_summary.json.  Run with the system python (no third-party imports).
"""
import collections as C
import json
import os
import subprocess
import sys
import time

X = "/home/appuser/inkscript/experiments"
E = f"{X}/99_liteparse_baseline"
PAGES = f"{X}/43_rehearsal/out/pages"
DEV = json.load(open(f"{E}/DEV_STEMS.json"))["stems"]
CANDS = {
    "tess_ara_150": ["--ocr-backend", "tesseract", "--ocr-language", "ara"],
    "tess_ara_300": ["--ocr-backend", "tesseract", "--ocr-language", "ara", "--dpi", "300"],
    "tess_araeng_300": ["--ocr-backend", "tesseract", "--ocr-language", "ara+eng", "--dpi", "300"],
    "nano_250": ["--ocr-backend", "ocria-nano"],
    "nano_300": ["--ocr-backend", "ocria-nano", "--dpi", "300"],
    "tess_araeng_150": ["--ocr-backend", "tesseract", "--ocr-language", "ara+eng"],
    "tess_ara_200": ["--ocr-backend", "tesseract", "--ocr-language", "ara", "--dpi", "200"],
    "nano_200": ["--ocr-backend", "ocria-nano", "--dpi", "200"],
}


def azure_words(stem, page):
    d = json.load(open(f"{X}/74_gate2_full/out/fetch/{stem}/{stem}.json"))
    p = d["pages"][page - 1]
    return [w for l in p["lines"] for w in l["content"].split()]


def lit_words(path):
    d = json.load(open(path))
    return [w for p in d["pages"] for t in p["text_items"] for w in t["text"].split()]


def f1(a, b):
    ca, cb = C.Counter(a), C.Counter(b)
    tp = sum((ca & cb).values())
    return 0.0 if not tp else 2 * tp / (sum(ca.values()) + sum(cb.values()))


def main():
    out = {}
    jobs = []
    for s in DEV:
        n = len([f for f in os.listdir(PAGES) if f.startswith(s + "_p")])
        for pg in sorted({1, max(2, n // 2)}):
            jobs.append((s, pg))
    for cand, args in CANDS.items():
        os.makedirs(f"{E}/out/dev/options/{cand}", exist_ok=True)
        f1s, secs = [], []
        for s, pg in jobs:
            img = f"{PAGES}/{s}_p{pg:03d}.jpg"
            dst = f"{E}/out/dev/options/{cand}/{s}_p{pg:03d}.json"
            if not os.path.exists(dst):
                t0 = time.time()
                subprocess.run([f"{E}/scripts/litrun.sh", f"dev_{cand}", "parse", img, "--format", "json",
                                "--extract-blocks", "--num-workers", "4", "-q", "-o", dst] + args, check=True)
                secs.append(time.time() - t0)
            f1s.append(f1(lit_words(dst), azure_words(s, pg)))
        out[cand] = dict(word_f1_vs_azure=round(sum(f1s) / len(f1s), 4), per_page=[round(x, 3) for x in f1s],
                         sec_per_page=round(sum(secs) / len(secs), 2) if secs else None)
        print(cand, out[cand], flush=True)
    json.dump(dict(pages=jobs, results=out), open(f"{E}/out/dev/options_summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
