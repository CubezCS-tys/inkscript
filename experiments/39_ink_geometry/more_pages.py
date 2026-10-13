"""Step 1 of round 2: find pages with equations and tables the layout model has not seen.

Journals with equation pages in experiment 34, but none of the 44 test pages' journals (so the test stays clean):
list each journal's documents on S3, draw some at random (seed 39), fetch only Azure's JSON, and count per page
the lines that look like maths (features.py's MATH rule) and like table rows (mostly numbers). Writes
out/more/kinds.json; the JSONs go to out/more/azure/<stem>/<stem>.json (the PDF is fetched later, for chosen pages)."""
import json, random, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).parent; MAIN = HERE.parents[1]; OUT = HERE / "out/more"; AZ = OUT / "azure"
sys.path.insert(0, str(MAIN / "src")); sys.path.insert(0, str(MAIN / "experiments/34_yardstick"))
from features import MATH, AR, NUM
from inkscript.enrich import document
AWS = str(MAIN / ".venv/bin/aws"); B = "s3://mandumah-source-docs"
JOURNALS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["1541", "0527", "0700", "1016", "2483"]
PER = int(sys.argv[2]) if len(sys.argv) > 2 else 30
test = {p["stem"].split("-")[0] for p in json.load(open(MAIN / "experiments/38_parser/out/pages.json"))["pages"]}
seen = set(json.load(open(MAIN / "experiments/34_yardstick/out/pool.json")))


def ls(j):
    r = subprocess.run([AWS, "s3", "ls", f"{B}/{j}-"], capture_output=True, text=True, timeout=300).stdout
    return sorted(l.split()[-1].rstrip("/") for l in r.splitlines() if l.strip().startswith("PRE"))


def fetch(stem):
    f = AZ / stem / f"{stem}.json"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([AWS, "s3", "cp", "--quiet", f"{B}/{stem}/{stem}.json", str(f)], timeout=600)
    return f if f.exists() else None


def kinds(stem):
    f = fetch(stem)
    if not f: return []
    try: d = document.load(f)
    except Exception as e: print("load failed", stem, e, flush=True); return []
    W, rows = d["words"], []
    for pn, lines in d["lines"].items():
        m = g = 0
        for mem in lines:
            lw = [W[k] for k in mem]; t = " ".join(w["text"] for w in lw)
            m += len(MATH.findall(t)) >= 1 and len(AR.findall(t)) <= 0.3 * len(t.replace(" ", "")) and len(t) >= 3
            g += len(lw) >= 3 and sum(1 for w in lw if NUM.match(w["text"])) >= 0.5 * len(lw)
        rows.append(dict(stem=stem, page=pn, lines=len(lines), math=m, grid=g))
    return rows


if __name__ == "__main__":
    rnd = random.Random(39); stems = []
    for j in JOURNALS:
        assert j not in test, j
        s = [x for x in ls(j) if x not in seen]; stems += rnd.sample(s, min(PER, len(s))); print(j, len(s), flush=True)
    kf = OUT / "kinds.json"; have = json.loads(kf.read_text()) if kf.exists() else []
    done = {r["stem"] for r in have}
    with ThreadPoolExecutor(4) as ex:
        for rows in ex.map(kinds, [s for s in stems if s not in done]): have += rows
    kf.write_text(json.dumps(have))
    for th in (2, 4): print(f"math>={th}", sum(r["math"] >= th for r in have), f"grid>={th}", sum(r["grid"] >= th for r in have))
    print("pages", len(have), "docs", len({r["stem"] for r in have}))
