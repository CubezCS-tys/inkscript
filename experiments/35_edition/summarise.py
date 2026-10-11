"""Experiment 35: the set's numbers from OUT/summary.json (the checks of every edition of every article).

    PYTHONPATH=src .venv/bin/python experiments/35_edition/summarise.py [OUT]   -> OUT/../numbers.json
"""
import collections
import json
import statistics
import sys
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/yassine/inkscript/experiments/35_edition/out/editions")


def main():
    docs = json.loads((OUT / "summary.json").read_text())["docs"]
    res = dict(documents=len(docs), errors={}, editions={}, order={}, seconds={}, sizes={})
    for r in docs:
        for k, v in (r.get("errors") or {}).items():
            res["errors"].setdefault(k, []).append(r["id"])
    agg = collections.defaultdict(collections.Counter)
    order = collections.defaultdict(collections.Counter)
    order_doc = collections.defaultdict(list)
    for r in docs:
        for k, v in (r.get("checks") or {}).items():
            if "error" in v:
                agg[k]["check_errors"] += 1
                continue
            w = v.get("words", {})
            for f in ("expected", "found", "missing", "missing_front", "missing_body", "duplicated", "extra"):
                agg[k][f] += w.get(f, 0)
            agg[k]["exactly_once_docs"] += bool(w.get("exactly_once"))
            agg[k]["docs"] += 1
            agg[k]["docs_no_body_missing_no_dup"] += (w.get("missing_body", 0) == 0 and w.get("duplicated", 0) == 0)
            o = v.get("order")
            if o:
                for f in ("expected", "in_order", "blocks", "block_inversions"):
                    order[k][f] += o.get(f, 0)
                order_doc[k].append(o.get("share", 0))
            fm = v.get("formulas")
            if fm:
                agg[k]["formulas_expected"] += fm["expected"]
                agg[k]["formulas_found"] += fm["found"]
    for k, c in agg.items():
        d = dict(c)
        d["found_pct"] = round(100 * c["found"] / c["expected"], 3) if c["expected"] else None
        res["editions"][k] = d
    for k, c in order.items():
        res["order"][k] = dict(c, share_pct=round(100 * c["in_order"] / c["expected"], 3) if c["expected"] else None,
                               median_doc=round(statistics.median(order_doc[k]), 4),
                               docs_under_95=sum(x < 0.95 for x in order_doc[k]))
    for kind in ("html", "epub", "layout", "onecol", "data", "checks"):
        xs = [r["stats"][kind]["seconds"] for r in docs if kind in r.get("stats", {})]
        if xs:
            res["seconds"][kind] = dict(median=statistics.median(xs), max=max(xs), total=round(sum(xs)))
    sizes = collections.defaultdict(int)
    for p in OUT.rglob("*"):
        if p.is_file():
            sizes[p.suffix or p.name] += p.stat().st_size
    res["sizes"] = {k: round(v / 1e6, 1) for k, v in sorted(sizes.items(), key=lambda x: -x[1])[:12]}
    res["pages"] = sum(r.get("pages", 0) for r in docs)
    (OUT.parent / "numbers.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
