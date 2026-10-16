"""Experiment 41: the print PDFs read back by Chrome's engine (pypdfium2 5.12.1), before and after prints.py.

    .venv/bin/python textcheck.py [--stems ...] [--new-dir out/prints] [--old-dir out/formats_lualatex] [--out NAME]

For each article and each print PDF: inkscript.edition.check.check_article (every ALTO word the master places,
found / lost / twice; reading order) on the LuaLaTeX original and on the Chromium print. One JSON per article in
out/textcheck/<NAME>/ (written as it goes), totals in out/textcheck/<NAME>.json.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from structure import OUT, sample  # noqa: E402


def one(stem, paths):
    from inkscript.edition.check import check_article
    from inkscript.edition.model import load
    ed = load(str(OUT / "masters" / f"{stem}.jats.xml"))
    res = {}
    for tag, files in paths.items():
        files = {k: p for k, p in files.items() if p.exists()}
        c = check_article(ed, files)
        for k, v in c.items():
            if "words" not in v:
                res[f"{tag}:{k}"] = dict(error=v.get("error"))
                continue
            w, o = v["words"], v.get("order") or {}
            res[f"{tag}:{k}"] = dict(expected=w["expected"], found=w["found"], missing=w["missing"],
                                     duplicated=w["duplicated"], order_expected=o.get("expected", 0),
                                     order_in_order=o.get("in_order", 0), missing_by_kind=w.get("missing_by_kind"),
                                     examples_missing=[x["token"] for x in w.get("examples_missing", [])][:12])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--new-dir", default=str(OUT / "prints"))
    ap.add_argument("--old-dir", default=str(OUT / "formats_lualatex"))
    ap.add_argument("--out", default="run")
    a = ap.parse_args()
    od = OUT / "textcheck" / a.out
    od.mkdir(parents=True, exist_ok=True)
    tot = Counter()
    rows = []
    for art in sample():
        s = art["stem"]
        if a.stems and s not in a.stems:
            continue
        old = Path(a.old_dir) / s
        if not (old / f"{s}.layout.pdf").exists():           # before the swap the originals are still in formats/
            old = OUT / "views" / "formats" / s
        new = Path(a.new_dir)
        r = one(s, dict(old=dict(layout_pdf=old / f"{s}.layout.pdf", onecol_pdf=old / f"{s}.onecol.pdf"),
                        new=dict(layout_pdf=new / f"{s}.layout.pdf", onecol_pdf=new / f"{s}.onecol.pdf")))
        (od / f"{s}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
        rows.append(dict(stem=s, **r))
        for k, v in r.items():
            for f in ("expected", "found", "missing", "duplicated", "order_expected", "order_in_order"):
                tot[f"{k}:{f}"] += v.get(f, 0)
        print(f"  {s:24} " + "  ".join(f"{k} {v.get('missing')}/{v.get('expected')}" for k, v in r.items()),
              flush=True)
    summ = {}
    for k in sorted({k.rsplit(":", 1)[0] for k in tot}):
        e, f = tot[f"{k}:expected"], tot[f"{k}:found"]
        oe, oi = tot[f"{k}:order_expected"], tot[f"{k}:order_in_order"]
        summ[k] = dict(expected=e, found=f, missing=tot[f"{k}:missing"], duplicated=tot[f"{k}:duplicated"],
                       share=round(f / e, 5) if e else None, order=round(oi / oe, 4) if oe else None)
    (OUT / "textcheck" / f"{a.out}.json").write_text(json.dumps(dict(total=summ, articles=rows), ensure_ascii=False,
                                                                indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
