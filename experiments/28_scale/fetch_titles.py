"""Fetch each document's Gemini title file where the bucket has one (free: no Gemini call), for the structure step
(`--frontpage-dir out/gemini`; enrich/structure.read_meta looks there).
    .venv/bin/python experiments/28_scale/fetch_titles.py [AZURE_DIR]   -> out/gemini/<id>.gemini.title.json, out/titles.tsv
"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent
AZ = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out" / "azure"
AWS = str(HERE.parents[1] / ".venv/bin/aws"); OUT = HERE / "out" / "gemini"; OUT.mkdir(parents=True, exist_ok=True)
def get(d):
    f = OUT / f"{d}.gemini.title.json"
    if f.exists(): return d, "ok"
    r = subprocess.run([AWS, "s3", "cp", f"s3://mandumah-source-docs/{d}/{d}.gemini.title.json", str(f)], capture_output=True, text=True)
    return d, "ok" if r.returncode == 0 else "none"
with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(get, sorted(os.listdir(AZ))))
(HERE / "out" / "titles.tsv").write_text("".join(f"{d}\t{s}\n" for d, s in res))
print(sum(s == "ok" for _, s in res), "of", len(res), "have a title file")
