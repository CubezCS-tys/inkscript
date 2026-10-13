"""Round 2 of the layout model's training data (steps 1 and 2): equation and table pages, then the pages the model
is least sure of. Stages (each resumable, each writes under out/round2/):
  candidates   every page with maths (>= 2 lines) or table rows (>= 2), 600 other pages of the new documents, and the
               pool pages round 1 left unused (none from the test pages' documents)        -> candidates.json
  draft        fetch each document's PDF and draft the pages like round 1 (300 dpi image + Azure's lines) -> pages/
  [predict]    out/venv/bin/python predict_local.py round2   (the round-1 model on every candidate)  -> pred.json
  select       all maths pages, then the least sure of the rest, up to N pages                -> chosen.json
  label        the Flash referee on the chosen pages, as round 1                               -> labels/
Gemini for experiment 39 capped at $19 (round 1 spent $11.92; the owner approved $7 more on 2026-10-13)."""
import json, random, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).parent; MAIN = HERE.parents[1]; OUT = HERE / "out/round2"
PAGES = OUT / "pages"; LAB = OUT / "labels"
for d in (PAGES, LAB): d.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(MAIN / "src")); sys.path.insert(0, str(HERE))
import os; os.environ.setdefault("REFEREE", "gemini-3.8-flash")
import train_pages as T, common
from inkscript.gold.draft import write_pages, page_id
common.CAP = 19.0
T.PAGES, T.LAB = PAGES, LAB                                               # T.referee reads and writes these
AWS = str(MAIN / ".venv/bin/aws"); MORE = HERE / "out/more/azure"
N = int(os.environ.get("N", 1450))


def candidates():
    f = OUT / "candidates.json"
    if f.exists(): return json.loads(f.read_text())
    rnd = random.Random(39); K = json.load(open(HERE / "out/more/kinds.json"))
    hot = [r for r in K if r["math"] >= 2 or r["grid"] >= 2]
    cold = [r for r in K if r not in hot and r["lines"] >= 5]
    pool = json.load(open(MAIN / "experiments/34_yardstick/out/pool.json"))
    left = [r for r in json.load(open(HERE / "out/train/pool_kinds.json")) if not r["used"]]
    jobs = [dict(stem=r["stem"], page=r["page"], math=r["math"], grid=r["grid"], src="more",
                 azure=str(MORE / r["stem"] / f"{r['stem']}.json"), scan=str(MORE / r["stem"] / f"{r['stem']}.pdf"))
            for r in hot + rnd.sample(cold, min(600, len(cold)))]
    jobs += [dict(stem=r["stem"], page=r["page"], math=r["math"], grid=r["grid"], src="pool", azure=pool[r["stem"]]["azure"],
                  scan=pool[r["stem"]]["scan"], decade=pool[r["stem"]]["decade"], journal=pool[r["stem"]]["journal"]) for r in left]
    f.write_text(json.dumps(jobs, ensure_ascii=False)); return jobs


def draft(stem, rows):
    r0 = rows[0]
    if r0["src"] == "more" and not Path(r0["scan"]).exists():
        subprocess.run([AWS, "s3", "cp", "--quiet", f"s3://mandumah-source-docs/{stem}/{stem}.pdf", r0["scan"]], timeout=600)
    todo = [r["page"] for r in rows if not (PAGES / f"{page_id(stem, r['page'])}.json").exists()]
    if not todo: return
    try:
        write_pages(r0["azure"], r0["scan"], todo, PAGES, dict(stem=stem, decade=r0.get("decade"), journal=r0.get("journal")))
    except Exception as e:
        print("draft failed", stem, type(e).__name__, str(e)[:120], flush=True)


def select():
    """All maths pages; then the rest ranked by how unsure the round-1 model is: the share of Azure lines that no
    predicted box covers with confidence >= 0.5, plus the share of its boxes that are equation/other/caption."""
    P = json.load(open(OUT / "pred.json")); C = {page_id(j["stem"], j["page"]): j for j in candidates()}
    sys.path.insert(0, str(MAIN / "experiments/38_parser")); from common import inter, area
    from score_layout import LABELS
    score = {}
    for pid, p in P.items():
        g = json.loads((PAGES / f"{pid}.json").read_text()); W, H = g["image"]["width"], g["image"]["height"]
        B = [([b[0] * W, b[1] * H, b[2] * W, b[3] * H], LABELS[c], s) for b, c, s in zip(p["boxes"], p["cls"], p["conf"])]
        L = g["lines"]
        if not L: continue
        unsure = sum(not any(s >= 0.5 and inter(b, l["box"]) / max(1, area(l["box"])) >= 0.4 for b, _, s in B) for l in L) / len(L)
        rare = sum(c in ("equation", "other", "caption") for _, c, s in B if s >= 0.3) / max(1, len(B))
        score[pid] = unsure + rare
    maths = [p for p in score if C[p]["math"] >= 2]
    rest = sorted((p for p in score if p not in maths), key=lambda p: -score[p])
    chosen = maths + rest[:max(0, N - len(maths))]
    (OUT / "chosen.json").write_text(json.dumps(dict(chosen=chosen, score=score)))
    print("maths", len(maths), "chosen", len(chosen), "of", len(score), "; least sure cut-off", round(score[chosen[-1]], 3), flush=True)
    return chosen


if __name__ == "__main__":
    step = sys.argv[1]
    if step == "draft":
        by = {}
        for j in candidates(): by.setdefault(j["stem"], []).append(j)
        print(len(candidates()), "candidates from", len(by), "documents", flush=True)
        with ThreadPoolExecutor(3) as ex: list(ex.map(lambda kv: draft(*kv), by.items()))
        print("drafted", sum((PAGES / f"{page_id(j['stem'], j['page'])}.json").exists() for j in candidates()), flush=True)
    elif step == "select":
        select()
    elif step == "label":
        chosen = json.loads((OUT / "chosen.json").read_text())["chosen"]
        with ThreadPoolExecutor(6) as ex:
            for k, r in enumerate(ex.map(T.referee, chosen)):
                if k % 100 == 0: print(k, "labelled; spent", round(common.spent(), 2), flush=True)
        print("labelled", sum((LAB / f"{p}.json").exists() for p in chosen), "of", len(chosen), "; spent", round(common.spent(), 2), flush=True)
