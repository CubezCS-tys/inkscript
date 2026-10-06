"""After `inkscript fix --apply` on the set: do the PDFs still read right in pdfium (the pinned engine)?

For every document, faithful and vector PDF:
  * words intact, before (experiment 24's PDF) and after (the corrected one), the "placed" words of the build
    report with each applied correction's printed reading replaced by the corrected one — so a correction that
    landed counts as intact, and one that broke its neighbours would show as a drop;
  * every applied correction's text found on its page in pdfium's reading;
  * nothing else moved: pdfium's words on each corrected page, before and after, aligned; every difference must be
    a correction's printed reading turned into its text (the words-intact and lines-in-order counts below match the
    build report's words by text, so a corrected common word such as ما can be credited to the wrong line);
  * lines in reading order (pdfium_lines), before and after;
  * the ink: from the fix run's own check (pages with a correction rendered before and after, pixel for pixel;
    the original bytes still the file's prefix);
  * the trust PDFs: enrich.verify's check (same bytes first, same text and character boxes as the faithful PDF).

    python verify_set.py   -> out/verify_set.json
"""
import copy
import difflib
import json
from pathlib import Path

from inkscript.verify.engines import pdfium_words, pdfium_lines
from inkscript.enrich.trustpdf import check

HERE = Path(__file__).resolve().parent
SET = HERE / "out" / "set"
ORIG = Path("/home/yassine/inkscript/experiments/24_product/out/set")
AZ = Path("/home/yassine/inkscript/experiments/24_product/out/azure")


def corrected_report(rep, fixes):
    r = copy.deepcopy(rep)
    for c in fixes:
        for p in r["pages"]:
            if p["page"] == c["page"] and p.get("placed"):
                if c["was"] in p["placed"]:
                    p["placed"][p["placed"].index(c["was"])] = c["text"]
                for i, run in enumerate(p.get("runs", [])):    # the line's text, for pdfium_lines
                    toks = run.split(" ")
                    if c["was"] in toks:
                        toks[toks.index(c["was"])] = c["text"]
                        p["runs"][i] = " ".join(toks)
                        break
    return r


if __name__ == "__main__":
    import pypdfium2 as pdfium
    out = {}
    for rp in sorted(SET.glob("w*/native_pdf_report.json")):
        for rep in json.loads(rp.read_text(encoding="utf-8")):
            stem = rep["doc"]
            log = rp.parent / f"{stem}.corrections.json"
            fixes = [c for c in json.loads(log.read_text(encoding="utf-8"))["corrections"]
                     if c.get("status") == "applied"] if log.exists() else []
            res = dict(applied=len(fixes))
            rep2 = corrected_report(rep, fixes)
            for name in (f"{stem}.pdf", f"{stem}_vector.pdf"):
                a, b = ORIG / rp.parent.name / name, rp.parent / name
                if not b.exists():
                    continue
                wa, wb = pdfium_words(a, rep, AZ), pdfium_words(b, rep2, AZ)
                la, lb = pdfium_lines(a, rep), pdfium_lines(b, rep2)
                d = pdfium.PdfDocument(str(b))
                found = 0
                for c in fixes:
                    t = d[c["page"] - 1].get_textpage().get_text_range()
                    found += c["text"] in t
                # nothing else moved: pdfium's words before and after, page by page; every difference must be an
                # applied correction's printed reading turned into its corrected text, in place
                da = pdfium.PdfDocument(str(a))
                explained = unexplained = 0
                odd = []
                for pn in sorted({c["page"] for c in fixes}):
                    ta = da[pn - 1].get_textpage().get_text_range().split()
                    tb = d[pn - 1].get_textpage().get_text_range().split()
                    want = [(c["was"].split(), c["text"].split()) for c in fixes if c["page"] == pn]
                    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
                        if tag == "equal":
                            continue
                        x, y = ta[i1:i2], tb[j1:j2]
                        was_tok = {u for w, _ in want for u in w}
                        new_tok = {u for _, t in want for u in t}
                        if set(x) <= was_tok and set(y) <= new_tok:          # one correction, or several side by side
                            explained += 1
                        else:
                            unexplained += 1
                            odd.append(dict(page=pn, before=" ".join(x), after=" ".join(y)))
                da.close()
                d.close()
                res[name] = dict(words=sum(x["words"] for x in wb), intact_before=sum(x["intact"] for x in wa),
                                 intact_after=sum(x["intact"] for x in wb),
                                 lines_in_order_before=sum(x["in_order"] for x in la),
                                 lines_in_order_after=sum(x["in_order"] for x in lb),
                                 lines=sum(x["lines"] for x in lb), corrections_found=found,
                                 changes_explained=explained, changes_unexplained=unexplained, odd=odd[:10])
                tp = rp.parent / name.replace(".pdf", "_trust.pdf")
                if tp.exists():
                    res[name]["trust_pdf_ok"] = check(b, tp)["ok"]
            if log.exists():
                runs = json.loads(log.read_text(encoding="utf-8"))["runs"]
                inks = [r["ink"] for r in runs if r.get("ink")]
                res["ink_identical"] = all(v["ink_identical"] and v["prefix_identical"] for ink in inks for v in ink.values())
                res["enrich_problems"] = [p for r in runs for p in r.get("enrich_problems", [])]
            out[stem] = res
            print(stem, json.dumps(res, ensure_ascii=False), flush=True)
    (HERE / "out" / "verify_set.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
