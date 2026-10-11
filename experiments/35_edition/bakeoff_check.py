"""The bake-off's PDFs read again by the edition checker (src/inkscript/edition/check.py, fork C's words-once and
reading-order measure), as a second opinion on bakeoff.py's numbers. Adds "check" to each entry of
out/bakeoff.json and prints a table.

    PYTHONPATH=src .venv/bin/python experiments/35_edition/bakeoff_check.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from bakeoff import OUT, jats_of  # noqa: E402

from inkscript.edition.check import check_article  # noqa: E402
from inkscript.edition.model import load  # noqa: E402


def main():
    res_path = OUT / "bakeoff.json"
    res = json.loads(res_path.read_text())
    eds = {}
    for key, v in sorted(res.items()):
        doc, eng, var, *mode = key.split("|")
        if not v.get("ok"):
            continue
        pdf = OUT / "bakeoff" / (f"{doc}.{eng}.{var}" + (f".{mode[0]}" if mode else "") + ".pdf")
        if not pdf.exists():
            continue
        ed = eds.setdefault(doc, load(jats_of(doc)))
        k = "layout_pdf" if var == "layout" else "onecol_pdf"
        c = check_article(ed, {k: pdf}).get(k, {})
        w, o = c.get("words", {}), c.get("order", {})
        v["check"] = dict(words=w, order=o)
        print(f"{key:44s} missing {w.get('missing')} dup {w.get('duplicated')} of {w.get('expected')}  "
              f"order {o.get('share')}", flush=True)
    res_path.write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
