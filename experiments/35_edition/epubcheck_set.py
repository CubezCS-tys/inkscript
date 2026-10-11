"""Experiment 35: epubcheck (W3C, 5.2.1, in ~/.cache/inkscript/epubcheck/) on every Nth EPUB of a build.

    python experiments/35_edition/epubcheck_set.py OUT/editions [--every 10]   -> OUT/../epubcheck_set.json
"""
import argparse
import json
import subprocess
from pathlib import Path

JAR = Path.home() / ".cache/inkscript/epubcheck/epubcheck-5.2.1/epubcheck.jar"

ap = argparse.ArgumentParser()
ap.add_argument("editions")
ap.add_argument("--every", type=int, default=10)
a = ap.parse_args()
eps = sorted(Path(a.editions).glob("*/*.epub"))[::a.every]
rows = []
for f in eps:
    r = subprocess.run(["nice", "java", "-Xmx512m", "-jar", str(JAR), str(f)], capture_output=True, text=True,
                       timeout=300)
    out = r.stdout + r.stderr
    msgs = [x for x in out.splitlines() if x.startswith(("ERROR", "WARNING", "FATAL"))]
    rows.append(dict(epub=f.name, ok="No errors or warnings" in out, messages=msgs[:5]))
    print(f.name, "ok" if rows[-1]["ok"] else msgs[:2])
res = dict(checked=len(rows), clean=sum(r["ok"] for r in rows), rows=rows)
(Path(a.editions).parent / "epubcheck_set.json").write_text(json.dumps(res, indent=1))
print(f"{res['clean']}/{res['checked']} without errors or warnings")
