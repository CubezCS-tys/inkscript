"""Experiment 41: the two print PDFs of each article, printed by headless Chromium from the pages the owner reads
on screen (no model calls). Replaces the LuaLaTeX line-by-line editions `inkscript edition` made (D27) for these
55 articles, whose tables broke (every line sized from its own height; README, "Formats to download").

  <stem>.layout.pdf   out/views/print/<stem>.layout.html (views.py): the Layout view's pages alone, each block at its
                      printed box, text flowing and justified, one size per kind of block per page, fitted by the
                      view's own script; each PDF page the printed page's size (scan pixels / 300 dpi)
  <stem>.onecol.pdf   out/views/formats/<stem>/<stem>.html (inkscript edition, the Web page format) with its print
                      stylesheet: A4, one column, tables fitted to the text width (smaller type, then fixed columns
                      that wrap), header row repeated on each page a table runs to, notes at the end as on screen;
                      page number at the foot

Then each PDF is finished for Chrome's engine: ligatures' ToUnicode reversed where their letters are Arabic (the
lam-alef glyph otherwise copies as ال; pdftext._fix_tounicode, D27), /Direction /R2L unless the document is
mostly Latin (D18, D27), /Lang, title and author.

    .venv/bin/python prints.py [--stems ...] [--kinds layout onecol] [--no-swap]

Writes out/prints/<stem>.{layout,onecol}.pdf and out/prints/prints.json (per job: seconds, the boxes the layout
fitting left overflowing, the tables of the web page that needed squeezing); unless --no-swap, moves the
previous PDFs to out/formats_lualatex/<stem>/ (once: the LuaLaTeX originals are kept for comparison) and copies
the new ones into out/views/formats/<stem>/.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from structure import OUT, sample  # noqa: E402

PW = HERE.parents[0] / "40_gemini4_vlm" / "out" / "venv" / "bin" / "python"
PRINT = OUT / "views" / "print"
FMT = OUT / "views" / "formats"
STAGE = OUT / "prints"
OLD = OUT / "formats_lualatex"
MAST = OUT / "masters"
ONECOL_WIDTH = 665            # CSS px of A4's text width under the web page's @page margins (210 - 2 x 17 mm)
ONECOL_LEFT_PT = 17 / 25.4 * 72   # its left margin
ONECOL_TOP_PT = 18 / 25.4 * 72    # and top margin


def page_width_px(stem: str) -> int:
    """CSS px width of the first page of the layout print (its @page size)."""
    import re
    s = (PRINT / f"{stem}.layout.html").read_text(encoding="utf-8")
    m = re.search(r"width:([\d.]+)in", s)
    return int(round(float(m.group(1)) * 96)) if m else 800


def finish(pdf: Path, stem: str, kind: str, words: Path) -> dict:
    import pymupdf
    import textlayer as TL
    from inkscript.edition.model import load
    from inkscript.edition.printpdf import latin_document
    ed = load(str(MAST / f"{stem}.jats.xml"))
    rtl = not latin_document(ed)
    d = pymupdf.open(str(pdf))
    dom = json.loads(words.read_text())
    st = {}
    if kind == "layout":
        by_page = TL.page_lines_layout(dom, len(d))
    else:
        by_page, st = TL.page_lines_onecol(dom, d, ONECOL_LEFT_PT, ONECOL_TOP_PT)
    st["deglyph"] = TL.deglyph(d)
    st["layer"] = TL.add_layer(d, by_page, rtl)
    cat = d.pdf_catalog()
    d.xref_set_key(cat, "ViewerPreferences", "<</Direction /%s /DisplayDocTitle true>>" % ("R2L" if rtl else "L2R"))
    d.xref_set_key(cat, "Lang", pymupdf.get_pdf_str("ar" if rtl else (ed.front.get("lang") or "en")))
    authors = "; ".join(a.get("display") or a.get("name_ar") or a.get("name_en") or ""
                        for a in ed.front.get("authors", []))
    meta = d.metadata or {}
    d.set_metadata(dict(title=ed.front.get("title") or stem, author=authors, subject=ed.front.get("journal") or "",
                        creator="inkscript experiment 41 (prints.py)",
                        producer=(meta.get("producer") or "Skia/PDF") + "; inkscript"))
    tmp = pdf.with_suffix(".tmp.pdf")
    d.save(str(tmp), garbage=1, deflate=True)
    d.close()
    tmp.replace(pdf)
    return dict(st, rtl=rtl)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--kinds", nargs="*", default=["layout", "onecol"])
    ap.add_argument("--no-swap", action="store_true")
    args = ap.parse_args()
    stems = [a["stem"] for a in sample() if not args.stems or a["stem"] in set(args.stems)]
    (STAGE / "words").mkdir(parents=True, exist_ok=True)
    jobs = []
    for s in stems:
        if "layout" in args.kinds:
            jobs.append(dict(html=str(PRINT / f"{s}.layout.html"), pdf=str(STAGE / f"{s}.layout.pdf"), kind="layout",
                             width=page_width_px(s), stem=s, words=str(STAGE / "words" / f"{s}.layout.json")))
        if "onecol" in args.kinds:
            jobs.append(dict(html=str(FMT / s / f"{s}.html"), pdf=str(STAGE / f"{s}.onecol.pdf"), kind="onecol",
                             width=ONECOL_WIDTH, stem=s, words=str(STAGE / "words" / f"{s}.onecol.json")))
    jf = STAGE / "jobs.json"
    jf.write_text(json.dumps(jobs, ensure_ascii=False))
    rf = STAGE / "prints.json"
    rows = {(r["stem"], r["kind"]): r for r in json.loads(rf.read_text())} if rf.exists() else {}
    t0 = time.time()
    p = subprocess.Popen(["nice", "-n", "10", str(PW), str(HERE / "print_worker.py"), str(jf)], stdout=subprocess.PIPE,
                         text=True)
    by_pdf = {j["pdf"]: j for j in jobs}
    chromium = None
    for line in p.stdout:
        r = json.loads(line)
        if "chromium" in r:
            chromium = r["chromium"]
            print(f"Chromium {chromium}", flush=True)
            continue
        j = by_pdf[r["pdf"]]
        r.update(stem=j["stem"], chromium=chromium)
        if r.get("ok"):
            r.update(finish(Path(r["pdf"]), j["stem"], j["kind"], Path(j["words"])))
        rows[(j["stem"], j["kind"])] = r
        fit = r.get("fit") or {}
        note = (f"over {len(fit.get('over', []))}" if j["kind"] == "layout" else
                f"tables {fit.get('tables')} smaller/squeezed {fit.get('squeezed')} wider {fit.get('wider')}")
        print(f"  {j['stem']:24} {j['kind']:6} {'ok' if r.get('ok') else 'FAILED ' + r.get('error', '')} "
              f"{r['seconds']} s {note}", flush=True)
        rf.write_text(json.dumps(list(rows.values()), ensure_ascii=False, indent=0))   # after each job
    p.wait()
    print(f"{len(jobs)} jobs in {time.time() - t0:.0f} s")
    if args.no_swap:
        return
    for (s, k), r in rows.items():
        if s not in stems or k not in args.kinds or not r.get("ok"):
            continue
        dst = FMT / s / f"{s}.{k}.pdf"
        old = OLD / s / f"{s}.{k}.pdf"
        if dst.exists() and not old.exists():
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(old))
        shutil.copy2(r["pdf"], dst)
    print(f"swapped into {FMT}; LuaLaTeX originals in {OLD}")


if __name__ == "__main__":
    main()
