"""Markdown + JSONL for a sample of the master files, and the word checks on them (experiment 35, fork C).

    PYTHONPATH=src .venv/bin/python experiments/35_edition/data_sample.py [N] [--out DIR] [ids or jats paths...]

Writes <out>/<id>.md and <out>/<id>.jsonl, prints one line per article (words expected / missing / duplicated /
extra in each, and the time), and <out>/data_check.json.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from inkscript.edition.check import check_article
from inkscript.edition.data import jsonl_line, markdown
from inkscript.edition.model import load

MERGED = Path("/home/yassine/inkscript/experiments/29_catalogue/out/merged")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", nargs="?", type=int, default=15)
    ap.add_argument("docs", nargs="*")
    ap.add_argument("--out", default="/home/yassine/inkscript/experiments/35_edition/out/data_sample")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.docs:
        paths = [Path(d) if d.endswith(".jats.xml") else MERGED / f"{d}.jats.xml" for d in a.docs]
    else:
        allp = sorted(MERGED.glob("*.jats.xml"))
        step = max(1, len(allp) // a.n)
        paths = allp[::step][:a.n]
    rows = []
    for p in paths:
        t = time.time()
        ed = load(p)
        md, line = markdown(ed), jsonl_line(ed)
        (out / f"{ed.stem}.md").write_text(md, encoding="utf-8")
        (out / f"{ed.stem}.jsonl").write_text(line + "\n", encoding="utf-8")
        t_write = time.time() - t
        r = check_article(ed, dict(md=out / f"{ed.stem}.md", jsonl=out / f"{ed.stem}.jsonl"))
        dt = time.time() - t
        rows.append(dict(id=ed.stem, seconds=round(dt, 3), write=round(t_write, 3), **r))
        cells = "  ".join(f"{k}: {v['words']['expected']} exp, {v['words']['missing']} miss "
                          f"({v['words']['missing_front']} front), {v['words']['duplicated']} dup, "
                          f"{v['words']['extra']} extra" for k, v in r.items() if "words" in v)
        print(f"{ed.stem}  {dt:.2f}s  {cells}", flush=True)
    (out / "data_check.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
