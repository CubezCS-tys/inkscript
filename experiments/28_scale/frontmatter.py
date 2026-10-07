"""Title and authors on all 205 documents, scored against the MARC catalogue, without the build (only the Azure
reading and the scan are needed). Runs the product's structure.analyse as it is, and optionally a candidate rule
from front_fix.py monkeypatched in (src/ is never written).

    PYTHONPATH=src .venv/bin/python experiments/28_scale/frontmatter.py MODE [--fix]
      MODE: product  (title files where the bucket has one, as the build does)
            layout   (no title file anywhere: the layout rule on every document)
    -> out/front_<MODE>[_fix].json
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from inkscript.enrich import structure  # noqa: E402
from inkscript.enrich.document import load  # noqa: E402
from summarize import name_sim, sim  # noqa: E402

mode = sys.argv[1]
fix = "--fix" in sys.argv
if fix:
    import front_fix
    front_fix.install(structure)
cat = json.loads((OUT / "catalogue_titles.json").read_text())
stems = sorted(p.name for p in (OUT / "azure").iterdir())
if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
    stems = [s for s in stems if s in sys.argv[2].split(",")]
res = {}
for stem in stems:
    t0 = time.time()
    az = OUT / "azure" / stem
    try:
        doc = load(az / f"{stem}.json")
        meta = structure.read_meta(stem, [OUT / "gemini"] if mode == "product" else [])
        a = structure.analyse(doc, meta, az / f"{stem}.pdf")
    except Exception as e:
        res[stem] = dict(error=f"{type(e).__name__}: {e}")
        print(stem, "ERROR", e, flush=True)
        continue
    fr = a["front"]
    title = fr.get("title", "")
    authors = [x.get("name", "") for x in fr.get("authors", []) if x.get("name")]
    c = cat.get(stem, {})
    ts = sim(title, c.get("title", "")) if title else 0.0
    hit = sum(1 for x in c.get("authors", []) if any(name_sim(x, y) >= 0.6 for y in authors))
    right = sum(1 for y in authors if any(name_sim(x, y) >= 0.6 for x in c.get("authors", [])))
    res[stem] = dict(title=title, title_source=fr.get("title_source", ""), cat_title=c.get("title", ""), title_sim=round(ts, 3),
                     authors=authors, cat_authors=c.get("authors", []), authors_hit=hit, authors_right=right,
                     rubric=fr.get("rubric", ""), journal=(a.get("journal") or {}).get("text") if isinstance(a.get("journal"), dict) else a.get("journal"),
                     cat_journal=c.get("journal", ""), heads=len(a["head_words"]), notes=len(a["notes"]) if a.get("notes") else 0)
    print(f"{stem} {time.time() - t0:.1f}s title {ts:.2f} authors {hit}/{len(c.get('authors', []))} ({right}/{len(authors)} right)", flush=True)
ok = [r for r in res.values() if "error" not in r and r["cat_title"]]
summary = dict(mode=mode, fix=fix, documents=len(res), errors=sum("error" in r for r in res.values()),
               title_found=sum(bool(r["title"]) for r in ok), title_right=sum(r["title_sim"] >= 0.6 for r in ok), with_cat=len(ok),
               authors_cat=sum(len(r["cat_authors"]) for r in ok), authors_hit=sum(r["authors_hit"] for r in ok),
               authors_found=sum(len(r["authors"]) for r in ok), authors_right=sum(r["authors_right"] for r in ok))
print(summary)
(OUT / f"front_{mode}{'_fix' if fix else ''}.json").write_text(json.dumps(dict(summary=summary, docs=res), ensure_ascii=False, indent=1))
