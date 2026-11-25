"""Run LiteParse over a list of articles in one mode; one JSON file per article (resumable: existing files are skipped).

Run ONLY through litrun.sh (LiteParse venv python -I, sandbox env, strace, /usr/bin/time):
    litrun.sh exam_text --py run_lit.py --mode text --set exam

Modes (options fixed in OPTIONS.md after the dev runs; nothing tuned on the exam):
  text      the PDF's own text layer: PDF in, OCR off, blocks on, word boxes on (the ocria-nano package's LayoutNet
            table model runs, since it is installed; LiteParse says it runs whenever the package is present)
  text_apache  as text, but with LITEPARSE_MODEL_DIR pointed at an empty folder: pure Apache-2.0 LiteParse
  tess      the 300-dpi page image (no text layer) through the bundled Tesseract, Arabic + English data
  nano      the 300-dpi page image through ocria-nano
Output: out/runs/<mode>/<stem>.json = {stem, mode, options, pages: {page: ParseResult page as dict}, seconds}
"""
import argparse
import dataclasses
import json
import os
import sys
import time

X = "/home/appuser/inkscript/experiments"
E = f"{X}/99_liteparse_baseline"
PAGES = f"{X}/43_rehearsal/out/pages"

from liteparse import LiteParse  # noqa: E402  (the LiteParse venv only)

LEGACY = False
COMMON = dict(extract_blocks=True, emit_word_boxes=True, num_workers=4, quiet=True, output_format="json")
OPTIONS = {
    "text": dict(ocr_enabled=False),
    "text_apache": dict(ocr_enabled=False),
    "tess": dict(ocr_enabled=True, ocr_backend="tesseract", ocr_language="ara+eng", dpi=150,
                 tessdata_path=f"{E}/out/tessdata"),
    "nano": dict(ocr_enabled=True, ocr_backend="ocria-nano", dpi=250),
}


def pdf_of(stem):
    for c in (f"{X}/53_word_route/out/legacy_pdf/{stem}.pdf" if LEGACY else "/nonexistent",f"{X}/96_layout3/out/gpu/pdflinks/{stem}.pdf", f"{X}/74_gate2_full/out/fetch/{stem}/{stem}.pdf",
              f"{X}/43_rehearsal/out/fetch/{stem}/{stem}.pdf"):
        if os.path.exists(c):
            return os.path.realpath(c)
    raise FileNotFoundError(stem)


def todo(which):
    if which == "exam":
        arts = json.load(open(f"{X}/97_extraction_evals/LOCKED_EVAL.json"))["articles"]
        return [(a["stem"], sorted(set(a["pages"].values()))) for a in arts]
    if which == "dev":
        dev = json.load(open(f"{E}/DEV_STEMS.json"))["stems"]
        out = []
        for s in dev:
            n = len([f for f in os.listdir(PAGES) if f.startswith(s + "_p")])
            out.append((s, sorted({1, max(2, n // 2)})))
        return out
    if which == "legacy":                      # Q5: 10 born-digital PDFs made from publishers' Word files (exp 53)
        d = f"{X}/53_word_route/out/legacy_pdf"
        import random
        stems = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".pdf"))
        pick = random.Random(99).sample(stems, 10)
        json.dump(dict(note="Q5: 10 legacy PDFs, seed 99, from experiments/53_word_route/out/legacy_pdf", stems=pick),
                  open(f"{E}/out/legacy_stems.json", "w"), indent=1)
        return [(s, None) for s in pick]
    raise ValueError(which)


def page_dict(p):
    d = dataclasses.asdict(p)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=sorted(OPTIONS))
    ap.add_argument("--set", default="exam", choices=["exam", "dev", "legacy"])
    a = ap.parse_args()
    global LEGACY
    LEGACY = a.set == "legacy"
    opts = dict(COMMON, **OPTIONS[a.mode])
    if a.mode == "text_apache":
        assert os.environ.get("LITEPARSE_MODEL_DIR", "").endswith("models_empty"), "point LITEPARSE_MODEL_DIR at out/models_empty"
    outdir = f"{E}/out/runs/{a.set}_{a.mode}"
    os.makedirs(outdir, exist_ok=True)
    jobs = todo(a.set)
    n_pages = 0
    t_all = time.time()
    for stem, pages in jobs:
        dst = f"{outdir}/{stem}.json"
        if os.path.exists(dst):
            continue
        t0 = time.time()
        res, errs = {}, {}
        if a.mode.startswith("text"):
            lp = LiteParse(target_pages=",".join(map(str, pages)), **opts) if pages else LiteParse(**opts)
            try:
                r = lp.parse(pdf_of(stem))
                for p in r.pages:
                    res[p.page_num] = page_dict(p)
            except Exception as e:  # noqa: BLE001
                errs["all"] = f"{type(e).__name__}: {e}"[:500]
        else:
            lp = LiteParse(**opts)
            for pg in pages:
                img = f"{PAGES}/{stem}_p{pg:03d}.jpg"
                try:
                    r = lp.parse(img)
                    res[pg] = page_dict(r.pages[0])
                except Exception as e:  # noqa: BLE001
                    errs[pg] = f"{type(e).__name__}: {e}"[:500]
        sec = time.time() - t0
        n_pages += len(pages) if pages else len(res)
        tmp = dst + ".tmp"
        with open(tmp, "w") as f:
            json.dump(dict(stem=stem, mode=a.mode, options={k: v for k, v in opts.items()}, exam_pages=pages,
                           pages=res, errors=errs, seconds=round(sec, 2)), f, ensure_ascii=False)
        os.replace(tmp, dst)
        print(f"{stem} {len(res)}p {sec:.1f}s errors={len(errs)}", flush=True)
    print(f"done {a.mode} {n_pages} pages in {time.time() - t_all:.1f}s", flush=True)


if __name__ == "__main__":
    main()
