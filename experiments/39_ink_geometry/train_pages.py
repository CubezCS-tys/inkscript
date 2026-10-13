"""Training pages for a layout model: ~2,700 pages from the documents of experiment 34's pool, leaving out every
document behind the 44 pilot (test) pages. Each page is drafted like a gold page (image at 300 dpi + Azure's lines,
src/inkscript/gold/draft.write_pages) into out/train/pages/, then every line is labelled by the Flash referee
(score_layout's prompt and label set) into out/train/labels/<pid>.json, one file per page, skipped if present.
Gemini is capped at $15 for the whole experiment (out/gemini_spend.jsonl)."""
import json, random, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2, fitz
HERE = Path(__file__).parent; MAIN = HERE.parents[1]
PAGES = HERE / "out/train/pages"; LAB = HERE / "out/train/labels"; PAGES.mkdir(parents=True, exist_ok=True); LAB.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(MAIN / "src")); sys.path.insert(0, str(HERE))
import os; os.environ.setdefault("REFEREE", "gemini-3.8-flash")
import score_layout as S, common
from inkscript.gold.draft import write_pages, page_id

N, PER_DOC = 2700, 40


def plan():
    f = HERE / "out/train/plan.json"
    if f.exists(): return json.loads(f.read_text())
    pool = json.load(open(MAIN / "experiments/34_yardstick/out/pool.json"))
    test = {p["stem"] for p in json.load(open(MAIN / "experiments/38_parser/out/pages.json"))["pages"]}
    rnd = random.Random(39); jobs = []
    for stem, v in sorted(pool.items()):
        if stem in test: continue
        n = fitz.open(v["scan"]).page_count
        pages = sorted(rnd.sample(range(1, n + 1), min(n, PER_DOC)))
        jobs += [dict(stem=stem, page=p, azure=v["azure"], scan=v["scan"], decade=v["decade"], journal=v["journal"]) for p in pages]
    rnd.shuffle(jobs); jobs = jobs[:N]
    f.write_text(json.dumps(jobs, ensure_ascii=False, indent=0)); return jobs


def draft(stem, rows):
    r0 = rows[0]
    try:
        write_pages(r0["azure"], r0["scan"], [r["page"] for r in rows], PAGES, dict(stem=stem, decade=r0["decade"], journal=r0["journal"]))
    except Exception as e:
        print("draft failed", stem, type(e).__name__, str(e)[:120], flush=True)


def referee(pid):
    out = LAB / f"{pid}.json"
    if out.exists() or not (PAGES / f"{pid}.json").exists(): return None
    g = json.loads((PAGES / f"{pid}.json").read_text()); by = {l["id"]: l for l in g["lines"]}
    L = [dict(id=i, text=by[i]["text"], box=by[i]["box"]) for i in g["order"] if i in by]
    if not L: out.write_text(json.dumps(dict(pid=pid, lines=[], note="no Azure lines"))); return 0
    gray = cv2.imread(str(PAGES / f"{pid}.jpg"), cv2.IMREAD_GRAYSCALE)
    img = S.numbered(gray, L)
    ans, usd = common.gemini(S.PROMPT % len(L), [common.jpeg(img, max_side=2600, quality=88)], f"train {pid}",
                             model=S.MODEL, max_out=12000, schema=S.SCHEMA, thinking="low", est_in=3000)
    if not ans: return None                                              # not saved: a rerun retries it
    ref = {a["n"]: a["label"] for a in ans["lines"]}
    out.write_text(json.dumps(dict(pid=pid, size=gray.shape[::-1], lines=[dict(n=n, id=l["id"], box=l["box"], text=l["text"], label=ref.get(n))
                                                                          for n, l in enumerate(L, 1)]), ensure_ascii=False))
    return usd


if __name__ == "__main__":
    jobs = plan(); by = {}
    for j in jobs: by.setdefault(j["stem"], []).append(j)
    print(len(jobs), "pages from", len(by), "documents", flush=True)
    with ThreadPoolExecutor(3) as ex:                                     # drafting: CPU, at most 3 workers
        list(ex.map(lambda kv: draft(*kv), by.items()))
    pids = [page_id(j["stem"], j["page"]) for j in jobs]
    print("drafted", sum((PAGES / f"{p}.json").exists() for p in pids), flush=True)
    done = 0
    with ThreadPoolExecutor(6) as ex:
        for k, r in enumerate(ex.map(referee, pids)):
            done += r is not None
            if k % 100 == 0: print(k, "labelled; spent", round(common.spent(), 2), flush=True)
    print("labelled", sum((LAB / f"{p}.json").exists() for p in pids), "of", len(pids), "; spent", round(common.spent(), 2), flush=True)
