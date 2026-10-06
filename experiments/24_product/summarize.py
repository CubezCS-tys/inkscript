"""The product set's numbers, per document and in total.   python summarize.py [SET_DIR]  -> SET_DIR/summary.json

Reads every worker's native_pdf_report.json (the build's own --verify, --xml, --trust results), measures letter
coverage of each vector PDF with experiments/09_pen_path/coverage.py, and collects peak memory and wall time
from the workers' logs (/usr/bin/time lines)."""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SET = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out" / "set"
META = REPO / "experiments/19_azure_map/out/meta.json"


def coverage(pdf: Path):
    r = subprocess.run([str(REPO / ".venv/bin/python"), str(REPO / "experiments/09_pen_path/coverage.py"), str(pdf)],
                       capture_output=True, text=True)
    m = re.search(r"(\d+) of (\d+)", r.stdout)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def main():
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    runs = {}
    for log in sorted(SET.glob("w*.log")):
        for m in re.finditer(r"^(\S+) peak_kb=(\d+) wall=([\d.]+)", log.read_text(errors="replace"), re.M):
            r = dict(peak_mb=int(m.group(2)) // 1024, wall_s=float(m.group(3)))
            if r["wall_s"] > runs.get(m.group(1), {}).get("wall_s", -1):      # a --resume skip is a second, short line
                runs[m.group(1)] = r
    docs = []
    for rp in sorted(SET.glob("w*/native_pdf_report.json")):
        for r in json.loads(rp.read_text(encoding="utf-8")):
            stem = r["doc"]
            e = r.get("enrich", {})
            v, lines = r.get("verify", []), r.get("lines", [])
            cut, tot = coverage(rp.parent / f"{stem}_vector.pdf")
            tp = e.get("trust_pdf", {})
            year = (meta.get(stem) or {}).get("year")
            docs.append(dict(
                doc=stem, dir=rp.parent.name, pages=len(r["pages"]), year=int(year[:4]) if year and year[:4].isdigit() else None,
                born_digital_pages=sum(1 for p in r["pages"] if str(p.get("text", "")).startswith("native-")),
                words=sum(x["words"] for x in v), intact=sum(x["intact"] for x in v),
                lines=sum(x["lines"] for x in lines), in_order=sum(x["in_order"] for x in lines),
                inversions=r.get("order", {}).get("inversions"),
                letters_cut=cut, letters_words=tot,
                assessed=e.get("trust", {}).get("words"), flagged=e.get("trust", {}).get("flagged"),
                verified=e.get("trust", {}).get("verified"), why=e.get("trust", {}).get("why"),
                quotes=e.get("quotes", {}).get("found"), quotes_equal=e.get("quotes", {}).get("equal"),
                quotes_differ=e.get("quotes", {}).get("differ"),
                jats_valid=e.get("jats", {}).get("valid"), alto_valid=e.get("alto", {}).get("valid"),
                jats=e.get("jats"), alto=e.get("alto"),
                trust_pdfs_ok=all(t.get("check", {}).get("ok") for t in tp.values()) if tp else None,
                trust_marks=sum(t.get("annotations", 0) for t in tp.values()) // max(1, len(tp)),
                words_linked_to_glyphs=e.get("words_linked_to_glyphs"), azure_words=e.get("words"),
                **runs.get(stem, {})))
    S = lambda k: sum(d[k] or 0 for d in docs)
    tot = dict(documents=len(docs), pages=S("pages"), words=S("words"), intact=S("intact"), lines=S("lines"),
               in_order=S("in_order"), inversions=S("inversions"), letters_cut=S("letters_cut"),
               letters_words=S("letters_words"), assessed=S("assessed"), flagged=S("flagged"), verified=S("verified"),
               quotes=S("quotes"), quotes_equal=S("quotes_equal"), quotes_differ=S("quotes_differ"),
               jats_valid=sum(d["jats_valid"] is True for d in docs), alto_valid=sum(d["alto_valid"] is True for d in docs),
               trust_pdfs_ok=sum(d["trust_pdfs_ok"] is True for d in docs),
               peak_mb_max=max((d.get("peak_mb", 0) for d in docs), default=0),
               wall_s=round(sum(d.get("wall_s", 0) for d in docs)))
    (SET / "summary.json").write_text(json.dumps(dict(total=tot, docs=docs), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'doc':<24}{'year':>5}{'pg':>4}{'words':>14}{'lines':>10}{'letters':>8}{'flag':>7}{'quotes':>9}  xml  trust  peakMB")
    for d in docs:
        print(f"{d['doc']:<24}{d['year'] or '':>5}{d['pages']:>4}{d['intact']:>7}/{d['words']:<6}{d['in_order']:>5}/{d['lines']:<4}"
              f"{100 * d['letters_cut'] / max(1, d['letters_words']):>7.1f}%{100 * (d['flagged'] or 0) / max(1, d['assessed'] or 0):>6.1f}%"
              f"{d['quotes_equal'] or 0:>4}/{d['quotes'] or 0:<4}  {'ok ' if d['jats_valid'] and d['alto_valid'] else 'BAD'}  "
              f"{'ok ' if d['trust_pdfs_ok'] else 'BAD'}  {d.get('peak_mb', '')}")
    t = tot
    print(f"\n{t['documents']} documents, {t['pages']} pages: words intact {t['intact']}/{t['words']}, lines in order "
          f"{t['in_order']}/{t['lines']}, letter coverage {100 * t['letters_cut'] / max(1, t['letters_words']):.1f}%, "
          f"flagged {100 * t['flagged'] / max(1, t['assessed']):.1f}% of {t['assessed']} words, verified {t['verified']}, "
          f"quotations {t['quotes']} ({t['quotes_equal']} equal to the verse, {t['quotes_differ']} differ), "
          f"XML valid {t['jats_valid']}+{t['alto_valid']} of {t['documents']}, trust PDFs ok {t['trust_pdfs_ok']}, "
          f"peak memory {t['peak_mb_max']} MB")


if __name__ == "__main__":
    main()
