"""Write the XML and trust PDFs of some of experiment 28's documents again with the code on PYTHONPATH (the new
furniture rule and the block marks), into this experiment's out/reenrich/<stem>/, then check them as `--verify`
would (schemas, trust PDF against its faithful PDF). Experiment 28's own outputs are only read: the faithful PDFs
and shapes.json are copied first.

    PYTHONPATH=src .venv/bin/python experiments/30_furniture_flags/reenrich.py STEM [STEM...]  -> out/reenrich.json
"""
import json
import shutil
import sys
from pathlib import Path

from inkscript.enrich import enrich, verify

HERE = Path(__file__).resolve().parent
DATA = Path("/home/yassine/inkscript/experiments/28_scale/out")
OUT = HERE / "out" / "reenrich"
res = json.loads((HERE / "out" / "reenrich.json").read_text()) if (HERE / "out" / "reenrich.json").exists() else {}
reports = {}
for rp in DATA.glob("set/w*/native_pdf_report.json"):
    for r in json.loads(rp.read_text(encoding="utf-8")):
        reports[r["doc"]] = (rp.parent, r)
for stem in sys.argv[1:]:
    src, rep = reports[stem]
    d = OUT / stem
    d.mkdir(parents=True, exist_ok=True)
    for n in (f"{stem}.pdf", f"{stem}_vector.pdf", f"{stem}.shapes.json", f"{stem}.corrections.json"):
        if (src / n).exists():
            shutil.copyfile(src / n, d / n)
    az = DATA / "azure" / stem
    e = enrich(stem, az / f"{stem}.json", az / f"{stem}.pdf", d, dict(rep), xml=True, trust=True,
               meta_dirs=[DATA / "gemini"])
    probs = verify(stem, d, e)
    res[stem] = dict(trust=e["trust"], regions=e.get("regions"), jats={k: v for k, v in e["jats"].items() if k != "errors"},
                     alto=e["alto"], trust_pdf={k: dict(annotations=v["annotations"], ok=v.get("check", {}).get("ok"))
                                                for k, v in e.get("trust_pdf", {}).items()}, problems=probs)
    print(stem, e["trust"]["flagged"], "of", e["trust"]["words"], e.get("regions"), probs or "ok", flush=True)
(HERE / "out" / "reenrich.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
