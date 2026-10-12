"""The VLM smoke test's material: 60 real-scan lines of experiment 19's judged words (scoring only; no prompt or
setting was tuned on them) and 10 of the line finder's test pages.

    out/env/bin/python vlm_prep.py   -> out/vlm/vlm.tar (lines/*.png, pages/*.jpg, items.json)
Lines: 7 per stratum at random (seed 33) among Arabic lines whose judged word has a truth, up to 60.
"""
import json, random, shutil, tarfile
from pathlib import Path
from textnorm import is_arabic_line

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); V = OUT / "vlm"
if V.exists():
    shutil.rmtree(V)
(V / "lines").mkdir(parents=True); (V / "pages").mkdir()
rows = [json.loads(l) for l in open(OUT / "scan" / "scan.jsonl")]
rows = [r for r in rows if r["truth"] and r["pos"] and is_arabic_line(r["line"])]
r = random.Random(33); r.shuffle(rows)
pick, per = [], {}
for x in rows:
    if per.get(x["stratum"], 0) < 7 and len(pick) < 60:
        pick.append(x); per[x["stratum"]] = per.get(x["stratum"], 0) + 1
for x in pick:
    shutil.copy(OUT / "scan" / "img" / f"{x['id']}.png", V / "lines" / f"{x['id']}.png")
pages = sorted((OUT / "seg" / "test").glob("*.jpg")); r.shuffle(pages); pages = pages[:10]
for p in pages:
    shutil.copy(p, V / "pages" / p.name)
json.dump(dict(lines=[x["id"] for x in pick], pages=[p.stem for p in pages]), open(V / "items.json", "w"), indent=1)
with tarfile.open(V / "vlm.tar", "w") as tf:
    tf.add(V / "lines", arcname="lines"); tf.add(V / "pages", arcname="pages"); tf.add(V / "items.json", arcname="items.json")
print(len(pick), "lines", per, len(pages), "pages", (V / "vlm.tar").stat().st_size // 1024, "KB")
