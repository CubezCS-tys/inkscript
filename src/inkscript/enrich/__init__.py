"""What we know about a document beyond its ink, written beside the faithful PDF and never into it (D14, D20).

    enrich(stem, azure_json, scan_pdf, out_dir, report, xml=True, trust=True) -> summary for the build report

  document.py   Azure's reading: pages, paragraphs (with position roles), lines, words with ids and boxes
  structure.py  the article's structure: furniture, title / authors (Gemini's title file aligned to the ink, or
                the layout), headings (size, bold ink, numbering, space), notes and the markers that point at them
  quran.py      Quran quotations found, linked to sura:verse and checked word for word (Tanzil text, shipped)
  trust.py      one mark per word: verified / agreed / flagged with reasons (experiment 22's default rule)
  jats.py       <stem>.jats.xml   the article: front matter, body in reading order, footnotes, references,
                                  quotations linked (JATS 1.4 Archiving)
  alto.py       <stem>.alto.xml   every page, line and word with its box, confidence, trust mark, and ids that
                                  link it to the JATS and to the glyphs of the PDF (ALTO 4.4)
  trustpdf.py   <stem>_trust.pdf  the faithful PDF plus hideable highlights on flagged words, appended as an
                                  incremental update (the original bytes come first, unchanged)
  schemas.py    the official schemas, cached, and validation
  corrections.py  `inkscript fix` (experiment 27): corrections proposed from Quran verses, judged on the ink, applied
                to the text only; <stem>.corrections.json; applied ones are written in again and laid over the reading
  judge.py      the ink judge: Gemini, blind A/B on the scan's crop, cached, spend-capped
"""
from __future__ import annotations

import json
from pathlib import Path


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("inkscript")
    except Exception:
        return ""


def enrich(stem: str, azure_json: Path, scan_pdf: Path, out_dir: Path, report: dict,
           xml: bool = True, trust: bool = True, meta_dirs=()) -> dict:
    from . import alto, jats, trustpdf
    from .document import load
    from .quran import check_document
    from .trust import assess, summary
    from .corrections import applied_entries, overlay, reapply
    out_dir = Path(out_dir)
    pages = report.get("pages", [])
    gemini_pages = {p["page"] for p in pages if p.get("text") == "gemini"}
    born_digital = {p["page"] for p in pages if str(p.get("text", "")).startswith("native-")}
    shapes = out_dir / f"{stem}.shapes.json"
    doc = load(azure_json, shapes if shapes.exists() else None, gemini_pages)
    quotes = check_document(doc)
    marks = assess(doc, quotes, scan_pdf)
    # corrections accepted on the ink (`inkscript fix`, experiment 27): written into the faithful PDFs again (a
    # rebuild drops them; otherwise nothing changes), then into the reading the XML and trust PDFs are made from
    fixes = applied_entries(out_dir, stem)
    reapplied = reapply(out_dir, stem, fixes) if fixes else {}
    n_fixed = overlay(doc, marks, fixes, quotes)
    res = dict(trust=summary(marks), quotes=dict(found=len(quotes), equal=sum(q["differs"] == 0 for q in quotes),
                                                 differ=sum(q["differs"] > 0 for q in quotes),
                                                 refs=[q["ref"] for q in quotes]),
               words_linked_to_glyphs=sum(1 for w in doc["words"] if w["glyphs"]), words=len(doc["words"]))
    if fixes:
        res["corrections"] = dict(applied=n_fixed, pdfs=reapplied)
    res["trust"]["flagged_on_born_digital_pages"] = sum(
        1 for w in doc["words"] if w["page"] in born_digital and getattr(marks.get(w["idx"]), "mark", "") == "flagged")
    if xml:
        from .structure import read_meta
        # the article's structure (experiment 26): Gemini's title file if one sits beside the Azure reading or in
        # a frontpage dir (never a new Gemini call), stroke widths from the scan; both writers use it
        meta = read_meta(stem, [Path(azure_json).parent, *meta_dirs])
        jats.structure_of(doc, meta, scan_pdf)
        jn, an = f"{stem}.jats.xml", f"{stem}.alto.xml"
        res["jats"] = jats.write(doc, quotes, marks, stem, out_dir / jn, an)
        ids = res["jats"].pop("_ids")
        res["alto"] = alto.write(doc, quotes, marks, stem, out_dir / an, jn, born_digital, _version(), ids)
        if doc["placements"]:                 # the ALTO word id beside each glyph of the build's shapes.json
            ids = {}
            for w in doc["words"]:
                for g in w["glyphs"]:
                    ids[g] = w["id"]
            sj = json.loads(shapes.read_text(encoding="utf-8"))
            for g, pl in enumerate(sj["placements"]):
                if g in ids:
                    pl["word"] = ids[g]
            shapes.write_text(json.dumps(sj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if trust:
        res["trust_pdf"] = {}
        for name in (f"{stem}.pdf", f"{stem}_vector.pdf"):
            if (out_dir / name).exists():
                p, n = trustpdf.write(out_dir / name, doc, marks, quotes, born_digital)
                res["trust_pdf"][p.name] = dict(annotations=n)
    return res


def verify(stem: str, out_dir: Path, res: dict) -> list[str]:
    """After enrich: validate the XMLs against the official schemas and check each trust PDF against its
    faithful PDF. Returns problems ([] = all good); results are added to res."""
    from . import schemas, trustpdf
    out_dir = Path(out_dir)
    problems = []
    if "jats" in res:
        for kind, fn, name in (("jats", schemas.validate_jats, f"{stem}.jats.xml"),
                               ("alto", schemas.validate_alto, f"{stem}.alto.xml")):
            try:
                errs = fn(out_dir / name)
            except Exception as e:            # no network for the first schema fetch: say so, do not fail the build
                res[kind]["valid"] = None
                problems.append(f"{name}: not validated ({type(e).__name__}: {e})")
                continue
            res[kind]["valid"] = not errs
            if errs:
                res[kind]["errors"] = errs[:20]
                problems.append(f"{name}: {len(errs)} schema errors, first: {errs[0]}")
    for name, t in res.get("trust_pdf", {}).items():
        c = trustpdf.check(out_dir / name.replace("_trust.pdf", ".pdf"), out_dir / name)
        t["check"] = c
        if not c["ok"]:
            problems.append(f"{name}: differs from the faithful PDF in pdfium")
    return problems
