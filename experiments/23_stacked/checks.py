"""The build's own pdfium checks (cli native --verify: words intact, lines in order, order inversions) and letter
coverage (experiments/09_pen_path/coverage.py), on any copy of a built document, using the build's report.

    ../../.venv/bin/python checks.py PDF REPORT_JSON AZURE_DIR [VECTOR_PDF]
"""
import sys, json, re, subprocess
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from inkscript.verify.engines import pdfium_words, pdfium_order, pdfium_lines


def checks(pdf, report_json, azure_dir, vector=None):
    r = json.load(open(report_json))[0]
    v = pdfium_words(Path(pdf), r, Path(azure_dir)); tw, ti = sum(x["words"] for x in v), sum(x["intact"] for x in v)
    rotated = {p["page"] for p in r["pages"] if p.get("rotated")}; digital = {p["page"] for p in r["pages"] if p["text"] == "native-digital"}
    inv, nl = pdfium_order(Path(pdf), skip=rotated | digital)
    lv = pdfium_lines(Path(pdf), r); tl, tok = sum(x["lines"] for x in lv), sum(x["in_order"] for x in lv)
    out = dict(intact=f"{ti}/{tw}", lines=f"{tok}/{tl}", inversions=inv)
    if vector:
        cov = subprocess.run([str(REPO / ".venv/bin/python"), str(REPO / "experiments/09_pen_path/coverage.py"), str(vector)], capture_output=True, text=True).stdout
        c = re.search(r"own box: (\d+) of (\d+) \(([\d.]+)%\)", cov); out["coverage"] = f"{c.group(1)}/{c.group(2)} ({c.group(3)}%)"
    return out


if __name__ == "__main__":
    print(json.dumps(checks(*sys.argv[1:])))
