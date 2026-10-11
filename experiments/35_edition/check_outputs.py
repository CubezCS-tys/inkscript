"""Run the automatic checks (src/inkscript/edition/check.py) on whatever editions exist under an output folder
(experiment 35).

    PYTHONPATH=src .venv/bin/python experiments/35_edition/check_outputs.py [OUT] [--json FILE] [--pdf]

OUT (default experiments/35_edition/out/editions) holds <id>/<id>.{html,epub,layout.pdf,onecol.pdf,md,jsonl};
the master files are looked for in tests/fixtures/edition (test-*) or experiment 29's merged set. --pdf also reads
the PDFs back (pdfium; slower).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from inkscript.edition.check import check_article
from inkscript.edition.model import load

ROOT = Path(__file__).resolve().parents[2]
MERGED = Path("/home/yassine/inkscript/experiments/29_catalogue/out/merged")
FIXTURES = ROOT / "tests" / "fixtures" / "edition"
OUT = Path("/home/yassine/inkscript/experiments/35_edition/out/editions")
SUFFIX = dict(html=".html", epub=".epub", layout_pdf=".layout.pdf", onecol_pdf=".onecol.pdf", md=".md",
              jsonl=".jsonl")


def master(stem: str) -> Path | None:
    for d in (FIXTURES, MERGED):
        p = d / f"{stem}.jats.xml"
        if p.exists():
            return p
    return None


def html_labels() -> str:
    """The reading HTML's own words (labels, headings, the 'about' panel), allowed as extras."""
    try:
        from inkscript.edition import html as h
        words = []
        for name in dir(h):
            v = getattr(h, name)
            if name.isupper() and isinstance(v, dict):
                words += [x for x in v.values() if isinstance(x, str)]
        return " ".join(words) + " الهوامش الآيات المقتبسة ص المراجع الأصل"
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=str(OUT))
    ap.add_argument("--json")
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    lab = html_labels()
    rows = []
    for d in sorted(p for p in Path(a.out).iterdir() if p.is_dir()):
        m = master(d.name)
        if m is None:
            continue
        files = {k: d / f"{d.name}{s}" for k, s in SUFFIX.items()
                 if (d / f"{d.name}{s}").exists() and (a.pdf or not k.endswith("pdf"))}
        if not files:
            continue
        t = time.time()
        ed = load(m)
        r = check_article(ed, files, extra=dict(html=lab, epub=lab))
        rows.append(dict(id=d.name, seconds=round(time.time() - t, 2), **r))
        parts = []
        for k, v in r.items():
            if "error" in v:
                parts.append(f"{k}: ERROR {v['error']}")
                continue
            w = v["words"]
            s = f"{k}: {w['found']}/{w['expected']} miss {w['missing']} ({w['missing_front']} front) dup {w['duplicated']} extra {w['extra']}"
            if "order" in v:
                o = v["order"]
                s += f" order {o['share']:.3f} inv {o.get('block_inversions', '-')}/{o.get('blocks_placed', '-')}"
            if "formulas" in v:
                s += f" maths {v['formulas']['found']}/{v['formulas']['expected']}"
            parts.append(s)
        print(d.name, " | ".join(parts), flush=True)
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
