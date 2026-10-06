"""Signals for every word experiment 19 judged (2,971 words, 139 scanned documents), joined to the judge's verdict.

    .venv/bin/python features.py      -> out/judged_signals.json

The truth is experiment 19's (out/judged.json there): the calibrated Gemini judge's final verdict and the agent's
by-eye cause. Nothing is re-judged here.
"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
E19 = HERE.parent / "19_azure_map/out"


def one(args):
    doc, pages, year = args
    from docs import load_doc
    from signals import doc_signals
    js = E19 / "docs" / doc / f"{doc}.json"; pdf = E19 / "docs" / doc / f"{doc}.pdf"
    q = json.load(open(HERE / "out/quotes.json")).get(doc, {}).get("quotes", [])
    D = load_doc(js)
    idx = {w["idx"]: (w["page"], w["pi"]) for w in D["words"]}
    sig, hp = doc_signals(js, pdf, q, year, pages=set(pages), words_idx=idx)
    return doc, {f"{doc}:{p}:{k}": v for (p, k), v in sig.items()}, hp


if __name__ == "__main__":
    judged = json.load(open(E19 / "judged.json")); docs = json.load(open(E19 / "docs.json"))
    pages = defaultdict(set)
    for r in judged: pages[r["doc"]].add(r["page"])
    jobs = [(d, sorted(p), docs[d].get("year")) for d, p in pages.items()]
    sig, hps = {}, {}
    with Pool(3) as pool:
        for n, (d, s, hp) in enumerate(pool.imap_unordered(one, jobs), 1):
            sig.update(s); hps[d] = hp
            print(n, d, len(s), hp, flush=True)
    rows = []
    for r in judged:
        s = sig.get(r["id"])
        if s is None: print("missing", r["id"]); continue
        rows.append(dict(id=r["id"], doc=r["doc"], stratum=r["stratum"], verdict=r["verdict"], err=r["err"], cause=r["cause"],
                         judge=r["judge"], w=r["w"], size=r["size"], **{k: v for k, v in s.items() if k not in ("page", "pi")},
                         page=r["page"]))
    json.dump(dict(rows=rows, hamza_docs=hps), open(HERE / "out/judged_signals.json", "w"), ensure_ascii=False)
    print(len(rows), "rows")
