"""Experiment 100: choose the dev pages (outside the exam) and stage the upload folder.  Standard library only.

    nice -n 19 ionice -c3 python3 prep100.py

Dev = experiment 99's 5 dev articles (DEV_STEMS.json, seed 99, outside the locked exam), 8 pages each, evenly spaced
from page 1 to the last page (the article's 9-page one gives 8 of its 9): 40 pages.  Exam = the 214 locked exam
pages.  out/up/exam and out/up/dev hold symlinks to the 300-dpi JPEGs (originals untouched).  Writes DEV_PAGES.json.
"""
import json
import os

X = "/home/appuser/inkscript/experiments"
E = f"{X}/100_ocria1_exam"
PAGES = f"{X}/43_rehearsal/out/pages"
LOCK = json.load(open(f"{X}/97_extraction_evals/LOCKED_EVAL.json"))
DEV = json.load(open(f"{X}/99_liteparse_baseline/DEV_STEMS.json"))["stems"]


def n_pages(stem):
    return len([f for f in os.listdir(PAGES) if f.startswith(stem + "_p") and f.endswith(".jpg")])


def main():
    exam_stems = {a["stem"] for a in LOCK["articles"]}
    assert not exam_stems & set(DEV), "a dev article is in the exam"
    dev = []
    for s in DEV:
        n = n_pages(s)
        k = min(8, n)
        pages = sorted({1 + round(i * (n - 1) / (k - 1)) for i in range(k)})
        dev += [dict(stem=s, page=p) for p in pages]
    json.dump(dict(note="experiment 100 dev pages: exp 99's 5 dev articles, 8 evenly spaced pages each (first..last)",
                   pages=dev), open(f"{E}/DEV_PAGES.json", "w"), indent=1)
    exam = [(a["stem"], p) for a in LOCK["articles"] for p in sorted(set(a["pages"].values()))]
    for name, items in (("dev", [(d["stem"], d["page"]) for d in dev]), ("exam", exam)):
        d = f"{E}/out/up/{name}"
        os.makedirs(d, exist_ok=True)
        size = 0
        for s, p in items:
            src = f"{PAGES}/{s}_p{p:03d}.jpg"
            assert os.path.exists(src), src
            dst = f"{d}/{s}_p{p:03d}.jpg"
            if not os.path.lexists(dst):
                os.symlink(src, dst)
            size += os.path.getsize(src)
        print(name, len(items), "pages", round(size / 1e6), "MB")


if __name__ == "__main__":
    main()
