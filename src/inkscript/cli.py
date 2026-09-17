"""inkscript command line: the two halves of the project and where they meet.

  inkscript frontpage   Azure searchable PDF with Gemini's page-1 text      (ocr)
  inkscript native      PDF whose text layer is the page's own ink          (ocr + geometry)
  inkscript compare     static review bundle for front pages                (viewer)
  inkscript trace       one page -> outlines, fidelity, geometry JSON       (geometry)
  inkscript alphabet    shape dictionary across pages: does it saturate?    (geometry)
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

from . import config  # noqa: F401  (loads .env)


def cmd_frontpage(a) -> int:
    from .ocr.azure import load_azure  # noqa
    from .ocr.gemini import client, gemini_page1, GEMINI_MODEL, GEMINI_IN_PER_M, GEMINI_OUT_PER_M
    from .ocr.frontpage import build, verify, FONT
    from .text import fold_digits, strip_markdown
    ad, out = Path(a.azure_dir).expanduser(), Path(a.out).expanduser()
    sd = Path(a.scan_dir).expanduser() if a.scan_dir else None
    stems = sorted(d.name for d in ad.iterdir() if (d / f"{d.name}.json").exists() and (d / f"{d.name}.pdf").exists())
    if a.docs: stems = stems[:a.docs]
    if not stems:
        print(f"no <stem>/<stem>.json + .pdf pairs in {ad}", file=sys.stderr); return 2
    out.mkdir(parents=True, exist_ok=True)
    gc = client()
    print(f"{'doc':<24}{'p1 wds':>7}{'exact':>7}  {'page 1':<15}{'verify'}")
    tin = tout = 0; rows = []
    for stem in stems:
        aj, apdf = ad / stem / f"{stem}.json", ad / stem / f"{stem}.pdf"
        scan = sd / f"{stem}.pdf" if sd and (sd / f"{stem}.pdf").exists() else apdf
        gtext, usage = gemini_page1(gc, scan, out / f"{stem}.gemini.p1.md", a.gemini_model)
        gtext = fold_digits(strip_markdown(gtext)) if gtext is not None else None
        tin += usage.get("in", 0); tout += usage.get("out", 0)
        st, placed = build(stem, aj, apdf, gtext, out / f"{stem}.pdf", a.min_exact, a.font)
        vs = ""
        if a.verify:
            st["verify"] = v = verify(out / f"{stem}.pdf", apdf, placed)
            vs = (f"words {v['p1_recall']:.0%}  phrases {v['p1_phrase']:.0%}  " if "p1_recall" in v else "") + \
                 f"rest {'ok' if v['rest_identical'] else 'CHANGED'}  scan {'ok' if v['scan_identical'] else 'CHANGED'}"
        (out / f"{stem}.frontpage.json").write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append(st)
        ex = f"{st['exact_of_azure']:.0%}" if "exact_of_azure" in st else "-"
        print(f"{stem:<24}{st['azure_p1_words']:>7}{ex:>7}  {st['page1']:<15}{vs}")
    n = {k: sum(r["page1"] == k for r in rows) for k in ("gemini", "gemini-title", "azure-fallback")}
    print(f"\n{n['gemini']}/{len(rows)} front pages rebuilt with Gemini text, {n['gemini-title']} with a Gemini title only, {n['azure-fallback']} left as Azure")
    cost = tin / 1e6 * GEMINI_IN_PER_M + tout / 1e6 * GEMINI_OUT_PER_M
    print(f"gemini this run: {tin:,} in / {tout:,} out tokens = ${cost:.3f} (cached pages cost nothing)")
    return 0 if not a.verify or all(r["verify"]["rest_identical"] and r["verify"]["scan_identical"] for r in rows) else 1


def cmd_native(a) -> int:
    from .pdf.native import build_document
    from .verify.engines import pdfium_words, pdfium_order
    ad, out = Path(a.azure_dir).expanduser(), Path(a.out).expanduser()
    sd = Path(a.scan_dir).expanduser() if a.scan_dir else None
    fd = Path(a.frontpage_dir).expanduser() if a.frontpage_dir else None
    scan = lambda stem: (sd / f"{stem}.pdf") if sd and (sd / f"{stem}.pdf").exists() else ad / stem / f"{stem}.pdf"
    stems = sorted(d.name for d in ad.iterdir() if (d / f"{d.name}.json").exists() and scan(d.name).exists())
    if a.docs: stems = stems[:a.docs]
    reports = []
    for stem in stems:
        r = build_document(stem, ad, scan(stem), fd / f"{stem}.gemini.p1.md" if fd else None, out, a.vector, a.min_exact)
        nd = sum(1 for p in r["pages"] if p["text"] == "native-digital")
        line = f"{stem:<24} {len(r['pages'])} pages  {sum(p.get('glyphs', 0) for p in r['pages']):>5} glyphs  p1 {r['pages'][0]['text']}" + (f"  ({nd} born-digital pages left as they are)" if nd else "")
        if a.verify:
            r["verify"] = v = pdfium_words(out / f"{stem}.pdf", r, ad)
            rotated = {p["page"] for p in r["pages"] if p.get("rotated")}
            inv, nl = pdfium_order(out / f"{stem}.pdf", skip=rotated); r["order"] = dict(inversions=inv, lines=nl, sideways_pages=len(rotated))
            tw, ti = sum(x["words"] for x in v), sum(x["intact"] for x in v)
            line += f"  | pdfium: {ti}/{tw} words intact ({ti / max(1, tw):.0%}), {inv} order inversions" + (f", {len(rotated)} sideways pages" if rotated else "")
        print(line, flush=True); reports.append(r)
    out.mkdir(parents=True, exist_ok=True)
    (out / "native_pdf_report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.verify:
        tw = sum(x["words"] for r in reports for x in r["verify"]); ti = sum(x["intact"] for r in reports for x in r["verify"])
        inv = sum(r["order"]["inversions"] for r in reports)
        print(f"\nall documents: {ti}/{tw} words intact in pdfium ({ti / max(1, tw):.1%}), {inv} reading-order inversions")
    print(f"wrote {len(reports)} documents to {out}")
    return 0


def cmd_compare(a) -> int:
    from .viewer.frontpage_compare import build
    return build(a)


def cmd_trace(a) -> int:
    import fitz, cv2
    from .geometry.trace import render_gray, page_blobs, render_from_outlines, fidelity
    out = Path(a.out).expanduser(); out.mkdir(parents=True, exist_ok=True)
    page = fitz.open(a.pdf)[a.page - 1]
    gray = render_gray(page, a.dpi); blobs = page_blobs(gray); img = render_from_outlines(blobs, gray.shape)
    stem = Path(a.pdf).stem
    cv2.imwrite(str(out / f"{stem}_p{a.page}_scan.png"), gray); cv2.imwrite(str(out / f"{stem}_p{a.page}_outlines.png"), img)
    geo = dict(dpi=a.dpi, page=[gray.shape[1], gray.shape[0]],
               shapes=[dict(x=b["x"], y=b["y"], w=b["w"], h=b["h"], paths=[p.tolist() for p in b["paths"]], holes=b["holes"]) for b in blobs])
    (out / f"{stem}_p{a.page}_geometry.json").write_text(json.dumps(geo, separators=(",", ":")))
    pts = sum(len(p) for b in blobs for p in b["paths"])
    print(f"{stem} page {a.page}: {len(blobs)} ink shapes, {pts:,} outline points, {fidelity(gray, img):.1%} of ink reproduced from outlines")
    print(f"wrote {out / f'{stem}_p{a.page}_outlines.png'} and _geometry.json")
    return 0


def cmd_alphabet(a) -> int:
    import fitz
    from .geometry.trace import render_gray, page_blobs
    from .geometry.alphabet import Alphabet, prepare
    A = Alphabet(); tot = 0; rows = []
    for pdf in a.pdfs:
        doc = fitz.open(pdf)
        for pno in range(doc.page_count if not a.pages else min(doc.page_count, a.pages)):
            blobs = page_blobs(render_gray(doc[pno], a.dpi)); unit = prepare(blobs); before = len(A)
            for b in blobs: b["cid"] = A.assign(b)
            tot += len(blobs); rows.append(dict(doc=Path(pdf).stem, page=pno + 1, blobs=len(blobs), new=len(A) - before, cumulative_blobs=tot, shapes=len(A), unit_px=unit))
            print(f"{Path(pdf).stem} p{pno + 1}: unit {unit:4.1f}px {len(blobs):>5} blobs, {len(A) - before:>5} new shapes -> {tot:>6} blobs / {len(A):>5} shapes", flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1))
    print(f"\n{len(A)} distinct shapes for {tot} blobs; last page added {rows[-1]['new'] / max(1, rows[-1]['blobs']):.0%} new")
    return 0


def cmd_fetch(a) -> int:
    """Pull <id>/<id>.pdf + .json from the corpus bucket into --out/<id>/ (the --azure-dir layout)."""
    import subprocess
    from concurrent.futures import ThreadPoolExecutor
    out = Path(a.out).expanduser(); out.mkdir(parents=True, exist_ok=True)
    ids = list(a.ids)
    for f in a.id_file or []:
        ids += [l.strip() for l in Path(f).read_text().splitlines() if l.strip()]
    def one(i):
        d = out / i; d.mkdir(exist_ok=True); got = []
        for ext in ("pdf", "json"):
            if (d / f"{i}.{ext}").exists(): got.append(ext); continue
            r = subprocess.run(["aws", "s3", "cp", f"s3://{a.bucket}/{i}/{i}.{ext}", str(d / f"{i}.{ext}"), "--quiet"], capture_output=True, text=True)
            if r.returncode == 0: got.append(ext)
        return i, got
    with ThreadPoolExecutor(a.workers) as ex:
        for i, got in ex.map(one, ids):
            print(f"{i}: {' '.join(got) or 'MISSING'}", flush=True)
    return 0


def cmd_check(a) -> int:
    from .verify.consistency import review
    out = Path(a.out).expanduser() if a.out else None
    tot = dict(words=0, repeated=0, conflicts=0, suspects=0, numbers=0)
    for sj in sorted(Path(a.dir).expanduser().glob("*.shapes.json")):
        r = review(sj); stem = sj.name.replace(".shapes.json", "")
        ns = sum(len(c["suspects"]) for c in r["conflicts"])
        print(f"{stem:<24} {r['words']:>6} words, {r['repeated_ink']:>5} with ink seen elsewhere in the document, "
              f"{len(r['conflicts']):>3} contradictions ({ns} words to review), {len(r['numbers']):>4} numbers", flush=True)
        for c in r["conflicts"][:a.show]:
            print(f"    {c['readings']}  -> pages {sorted({s['page'] for s in c['suspects']})}")
        tot["words"] += r["words"]; tot["repeated"] += r["repeated_ink"]; tot["conflicts"] += len(r["conflicts"]); tot["suspects"] += ns; tot["numbers"] += len(r["numbers"])
        if out:
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{stem}.review.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nall: {tot['words']} words; {tot['repeated']} share ink with another word ({tot['repeated'] / max(1, tot['words']):.0%}); "
          f"{tot['conflicts']} contradictions, {tot['suspects']} words to review; {tot['numbers']} numbers")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="inkscript", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("frontpage", help="Azure searchable PDF with Gemini's page-1 text")
    p.add_argument("--azure-dir", required=True, help="dir of <stem>/<stem>.json + <stem>/<stem>.pdf (Azure prebuilt-read)")
    p.add_argument("--scan-dir", help="original scans <stem>.pdf (what Gemini reads); defaults to Azure's PDF")
    p.add_argument("--out", required=True); p.add_argument("--docs", type=int, default=0)
    p.add_argument("--min-exact", type=float, default=0.6); p.add_argument("--gemini-model", default=None)
    p.add_argument("--font", default=None); p.add_argument("--verify", action="store_true")
    p.set_defaults(fn=cmd_frontpage)

    p = sub.add_parser("native", help="PDF whose text layer is the page's own ink")
    p.add_argument("--azure-dir", required=True); p.add_argument("--scan-dir", help="source PDFs <stem>.pdf; defaults to the PDF beside each Azure JSON (its text layer is stripped)")
    p.add_argument("--frontpage-dir", help="frontpage output: <stem>.gemini.p1.md gives page 1 Gemini's text")
    p.add_argument("--out", required=True); p.add_argument("--docs", type=int, default=0); p.add_argument("--min-exact", type=float, default=0.6)
    p.add_argument("--vector", action="store_true", help="also write <stem>_vector.pdf: no image, glyphs only")
    p.add_argument("--verify", action="store_true", help="check the result in pdfium (Chrome's engine)")
    p.set_defaults(fn=cmd_native)

    p = sub.add_parser("compare", help="static review bundle: front page three ways")
    p.add_argument("--frontpage-dir", required=True); p.add_argument("--azure-dir", required=True); p.add_argument("--out", required=True)
    p.add_argument("--min-exact", type=float, default=0.6); p.add_argument("--zip", action="store_true")
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("trace", help="one page -> outlines, fidelity, geometry JSON")
    p.add_argument("--pdf", required=True); p.add_argument("--page", type=int, default=1); p.add_argument("--dpi", type=int, default=300)
    p.add_argument("--out", required=True); p.set_defaults(fn=cmd_trace)

    p = sub.add_parser("fetch", help="pull documents from the corpus bucket into the --azure-dir layout")
    p.add_argument("ids", nargs="*"); p.add_argument("--id-file", action="append", help="file of ids, one per line")
    p.add_argument("--bucket", default="mandumah-source-docs"); p.add_argument("--out", required=True); p.add_argument("--workers", type=int, default=8)
    p.set_defaults(fn=cmd_fetch)

    p = sub.add_parser("check", help="review list: same ink, different text; and every number")
    p.add_argument("dir", help="a native output dir (reads <stem>.shapes.json)"); p.add_argument("--out", help="write <stem>.review.json here")
    p.add_argument("--show", type=int, default=3, help="contradictions to print per document")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("alphabet", help="shape dictionary across pages: does it saturate?")
    p.add_argument("pdfs", nargs="+"); p.add_argument("--pages", type=int, default=0, help="first N pages of each")
    p.add_argument("--dpi", type=int, default=300); p.add_argument("--out", help="write the per-page curve as JSON")
    p.set_defaults(fn=cmd_alphabet)

    a = ap.parse_args(argv)
    if a.cmd == "frontpage":
        from .ocr.gemini import GEMINI_MODEL
        from .ocr.frontpage import FONT
        a.gemini_model = a.gemini_model or GEMINI_MODEL; a.font = a.font or FONT
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
