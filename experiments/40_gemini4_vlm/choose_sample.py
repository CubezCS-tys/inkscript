"""Experiment 40: the sample (25 pages + 3 short whole documents) -> out/sample.json, out/pages/, out/docs/.

    /home/yassine/inkscript/.venv/bin/python choose_sample.py

Pages are stratified over the archive's kinds of page; 21 of them are experiment 39's layout test pages (Azure lines
labelled by the Gemini Pro referee: exp 39 out/score_test), 5 of those are the owner's hand-corrected gold pages
(34_yardstick, status done), and 4 are born-digital pages whose PDF text is the truth (36's bd set). Every page has
Azure's lines (36 out/ref/azure). Page images: a colour 300 dpi render of the source PDF, checked to have exactly the
size of the reference image every box was measured on (else the reference's own grey JPEG is copied).
Resumable: what exists is not fetched or rendered again.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from common import B36, B39, DOCS, GOLD, MAIN, OUT, PAGES

AWS = str(MAIN / ".venv/bin/aws")
SRC = OUT / "src"            # <stem>/<stem>.pdf + .json (Azure) for the sample's documents
E19 = MAIN / "experiments/19_azure_map/out/docs"
E33 = MAIN / "experiments/33_kraken/out/docs"

PICK = [  # (page_id, kind, why)
    ("0005-055-003-004_p008", "gold", "owner-corrected gold, 2000s, a numbered list page"),
    ("0018-010-003-002_p003", "gold", "owner-corrected gold, pre-1960 print"),
    ("0058-023-003-005_p003", "gold", "owner-corrected gold, 1990s, headings + list + body"),
    ("0197-002-001-003_p003", "gold", "owner-corrected gold, 1960s"),
    ("0355-000-002-006_p017", "gold", "owner-corrected gold, 1970s, two columns"),
    ("bd_0767-010-002-007_p001", "born_digital", "born-digital front page (title, authors, abstract), mixed Latin"),
    ("bd_0198-012-003-001_p015", "born_digital", "born-digital table page"),
    ("bd_0493-000-029-001_p002", "born_digital", "born-digital three-column magazine page"),
    ("bd_2502-000-041-029_p021", "born_digital", "born-digital table with Latin"),
    ("0474-008-013-001_p036", "equation", "1980s equations inside a numbered list"),
    ("0682-000-092-014_p027", "equation", "2010s equations + footnotes + Latin"),
    ("0478-007-002-005_p006", "equation", "2000s equations on a three-column magazine page"),
    ("0200-000-140-006_p022", "table", "2020s table with Latin"),
    ("0924-012-005-007_p002", "table", "pre-1960 table, two columns, old print"),
    ("0732-019-222,224-040_p001", "poetry", "1980s decorative page of verse (28 verse lines by the referee)"),
    ("0747-001-003-001_p006", "poetry", "pre-1960 vowelled verse with footnotes"),
    ("0266-006-002-001_p042", "footnotes", "1990s page with nine footnote lines"),
    ("1000-000-020-028_p019", "quran", "2020s vowelled Quran quotation + verse + footnotes"),
    ("0877-007-027-003_p004", "two_column", "1960s two columns with footnotes"),
    ("0737-001-020-003_p009", "two_column", "pre-1960 three-column magazine"),
    ("0513-001-001-011_p003", "degraded", "pre-1960 old print, Latin"),
    ("0692-000-009-023_p003", "degraded", "pre-1960 old print, Quran, two columns"),
    ("0870-017-001-003_p007", "latin", "1970s mixed Arabic / Latin with footnotes"),
    ("0694-000-023-013_p027", "latin", "2000s Latin reference list"),
    ("0690-037-002-014_p001", "front_page", "1960s first page: title, author, Quran"),
]
DOC_CANDIDATES = {   # first one with <= 12 pages wins
    "equations_tables": ["2382-005-003-001", "1147-000-007-006", "0460-009-003-012", "0478-007-002-005"],
    "poetry_footnotes": ["0747-001-003-001", "0732-019-222,224-040", "0870-017-001-003"],
    "plain": ["0197-002-001-003", "0005-055-003-004", "0058-023-003-005"],
}


def fetch(stem: str) -> Path:
    d = SRC / stem
    d.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "json"):
        f = d / f"{stem}.{ext}"
        if not f.exists():
            subprocess.run([AWS, "s3", "cp", f"s3://mandumah-source-docs/{stem}/{stem}.{ext}", str(f), "--quiet"],
                           check=True)
    return d


def bd_pdf(stem: str) -> Path | None:
    for p in (E19 / stem / f"{stem}.pdf", E33 / stem / f"{stem}.pdf"):
        if p.exists():
            return p
    return None


def render(pdf: Path, page: int, out: Path, ref_jpg: Path) -> str:
    import cv2
    import numpy as np
    import pymupdf
    ref = cv2.imread(str(ref_jpg), cv2.IMREAD_GRAYSCALE)
    H, W = ref.shape
    with pymupdf.open(str(pdf)) as d:
        pg = d[page - 1]
        pix = pg.get_pixmap(dpi=300, alpha=False)
        if abs(pix.width - W) <= 1 and abs(pix.height - H) <= 1:
            a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3]
            a = cv2.resize(np.ascontiguousarray(a), (W, H)) if (pix.width, pix.height) != (W, H) else a
            cv2.imwrite(str(out), cv2.cvtColor(np.ascontiguousarray(a), cv2.COLOR_RGB2BGR),
                        [cv2.IMWRITE_JPEG_QUALITY, 92])
            return "colour render of the source PDF at 300 dpi"
    shutil.copy(ref_jpg, out)
    return f"copy of the reference grey JPEG (render was {pix.width}x{pix.height}, reference {W}x{H})"


def main():
    import pymupdf
    PAGES.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    man = {p["page_id"]: p for p in json.load(open(B36 / "pack/manifest.json"))["pages"]}
    old = {}
    if (OUT / "sample.json").exists():
        old = {p["page_id"]: p for p in json.load(open(OUT / "sample.json"))["pages"]}
    pages = []
    for pid, kind, why in PICK:
        m = man[pid]
        bd = pid.startswith("bd_")
        stem, page = m["stem"], m["page"]
        ref_jpg = (B36 / "pack/bd" / Path(m["file"]).name) if bd else GOLD / f"{pid}.jpg"
        pdf = bd_pdf(stem) if bd else fetch(stem) / f"{stem}.pdf"
        out = PAGES / f"{pid}.jpg"
        how = old.get(pid, {}).get("image_source")
        if not out.exists() or not how:
            how = render(pdf, page, out, ref_jpg) if pdf else "copy of the reference grey JPEG (no PDF)"
            if not out.exists():
                shutil.copy(ref_jpg, out)
        labels = B39 / "score_test" / f"{pid}.json"
        truth = "gold" if kind == "gold" else ("born_digital" if bd else None)
        pages.append(dict(page_id=pid, stem=stem, page=page, kind=kind, why=why, truth=truth,
                          truth_file=str(GOLD / f"{pid}.json") if truth == "gold" else
                          (str(B36 / "ref/bdtruth" / f"{pid}.json") if bd else None),
                          azure_file=str(B36 / "ref/azure" / f"{pid}.json"),
                          referee_labels=str(labels) if labels.exists() else None,
                          tags=m.get("tags", []), decade=m.get("decade"), ncols=m.get("ncols"),
                          journal=m.get("journal"), width=m["width"], height=m["height"],
                          image=str(out), image_source=how, source_pdf=str(pdf) if pdf else None))
        print(pid, kind, "|", how[:40], flush=True)
    docs = []
    for want, cands in DOC_CANDIDATES.items():
        for stem in cands:
            d = fetch(stem)
            with pymupdf.open(str(d / f"{stem}.pdf")) as x:
                n = len(x)
            print(" doc candidate", want, stem, n, "pages")
            if n <= 12:
                for ext in ("pdf", "json"):
                    if not (DOCS / f"{stem}.{ext}").exists():
                        shutil.copy(d / f"{stem}.{ext}", DOCS / f"{stem}.{ext}")
                sp = [p["page_id"] for p in pages if p["stem"] == stem]
                docs.append(dict(stem=stem, kind=want, pages=n, pdf=str(DOCS / f"{stem}.pdf"),
                                 azure_json=str(DOCS / f"{stem}.json"), sample_pages_inside=sp,
                                 bytes=(DOCS / f"{stem}.pdf").stat().st_size))
                break
    from collections import Counter
    counts = dict(Counter(p["kind"] for p in pages))
    json.dump(dict(made="2026-10-15", counts=counts, with_referee_labels=sum(bool(p["referee_labels"]) for p in pages),
                   with_truth=sum(bool(p["truth"]) for p in pages), pages=pages, docs=docs),
              open(OUT / "sample.json", "w"), ensure_ascii=False, indent=1)
    print(counts, [(d["stem"], d["pages"]) for d in docs])


if __name__ == "__main__":
    main()
