"""Experiment 102, step 1: the pool of candidate training lines that exists ON THIS SERVER today, with t91's labels.

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python pool102.py     -> out/pool/pool102.jsonl.gz + pool102_summary.json

What is on disk (checked 2026-11-25): experiment 77's manifests (one line per cut line, Azure's clean label) for
  - r77: experiment 77's train + dev pages, 2,169 documents (PDF + Azure JSON all still on disk, pages77.jsonl);
  - o80: experiment 80's old-print pull, 572 documents (PDF + JSON on disk, pages80.jsonl).
Experiment 83's 2.17 M new lines (7,763 documents) were cut on rented hosts only (83, 89, 91 each re-cut them from S3)
and are NOT here: neither crops nor per-line labels (only the 444,265 held-aside disputes' keys, held_v3).
So this pool is r77 + o80, and every crop must be re-cut from the local PDFs (cut102.py).

Labels, as t91 was trained (experiments 83 -> 85 -> 89 -> 91):
  - o80 lines: v1 and Azure agree (consensus, experiment 83) -> Azure's clean label   [azure_consensus];
    a held dispute -> v6r's judged label [v6r_judged] or rule85's bare alif [v6r_rule85], or dropped (393,973 in all);
  - r77 lines: Azure's clean label, NO consensus filter (v1/v3/v7/t91 all trained on them so)  [azure_r77];
  - page-1 title lines matched to the catalogue (experiment 91's overrides91; v6r's judged label wins)  [t91_title];
  - every real line whose label has (( or )) is dropped (experiment 84/89's rule: Azure writes (( )) for printed «»).
Every key passes guard102.assert_trainable before it is written; forbidden ones are counted and left out.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(HERE))
import guard102 as G  # noqa: E402

S77 = E / "77_scratch_reader/out/shards"
OUT = HERE / "out/pool"
DR = re.compile(r"\(\(|\)\)")
AR = re.compile("[ؠ-يٱ-ۓۺ-ۿ]")
LAT = re.compile("[A-Za-z]")


def era_of(y) -> str:
    try:
        y = int(str(y)[:4])
    except (TypeError, ValueError):
        return "unknown"
    return "pre-1950" if y < 1950 else "1950-1979" if y < 1980 else "1980-1999" if y < 2000 else "2000+"


def jl(p):
    op = gzip.open if str(p).endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as f:
        for l in f:
            if l.strip():
                yield json.loads(l)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    v6r = {d["key"]: d["label"] for d in jl(E / "85_disputes/out/labels/labels_v6r.jsonl")}
    v6j = {d["key"] for d in jl(E / "85_disputes/out/labels/labels_v6j.jsonl") if d["label"] is not None}
    held = {d["key"] for d in jl(E / "83_reader_scale/out/held/held_v3.jsonl.gz")}
    ov = {d["key"]: d["label"] for d in jl(E / "91_titles/out/host/overrides91.jsonl")}
    rel = {d["key"][:-4]: d.get("rel") for d in jl(E / "91_titles/out/host/manifest91_host.jsonl") if d["key"].endswith("_t91")}
    pages = {}
    for f in ("pages77.jsonl", "pages80.jsonl"):
        for d in jl(E / "77_scratch_reader/out" / f):
            pages[(d["stem"], int(d["page"]))] = (d["pdf"], d["azure"])
    c = Counter()
    by = defaultdict(Counter)
    tmp = OUT / "pool102.jsonl.gz.tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as out:
        for mf in sorted(S77.glob("manifest-*.jsonl")):
            part = mf.name.split("-")[1]                      # train | dev | old80
            src = "o80" if part == "old80" else "r77"
            for d in jl(mf):
                k = d["key"]
                c["manifest_lines"] += 1
                w = G.why_forbidden(k)
                if w:
                    c[f"left out: {w}"] += 1
                    continue
                lab, ls = d["label"], ("azure_r77" if src == "r77" else "azure_consensus")
                if k in v6r:                                   # a held dispute (o80 only): v6r decides
                    if v6r[k] is None:
                        c["left out: held dispute, no settled label"] += 1
                        continue
                    lab, ls = v6r[k], ("v6r_judged" if k in v6j else "v6r_rule85")
                elif src == "o80" and k in held:
                    c["left out: held, not in v6r"] += 1
                    continue
                title = False
                if k in ov:
                    if ov[k] is None:
                        if ls not in ("v6r_judged",):
                            c["left out: title line, catalogue and readers disagree (exp 91)"] += 1
                            continue
                    else:
                        title = True
                        if ls != "v6r_judged":
                            lab, ls = ov[k], "t91_title"
                if DR.search(lab or ""):
                    c["left out: (( )) in Azure's label (exp 84 rule)"] += 1
                    continue
                if not (lab or "").strip():
                    c["left out: empty label"] += 1
                    continue
                pdf, az = pages.get((d["stem"], int(d["page"])), (None, None))
                if pdf is None:
                    c["left out: page not in pages77/80"] += 1
                    continue
                era = era_of(d.get("year"))
                kind = "arabic" if AR.search(lab) else ("latin" if LAT.search(lab) else "other")
                r = dict(key=k, stem=d["stem"], page=int(d["page"]), i=int(d["i"]), jcode=d["jcode"], year=d.get("year"),
                         era=era, src=src, part=part, label=lab, label_source=ls, title=title,
                         display=bool(title and (rel.get(k) or 0) >= 1.2), kind=kind, W48=d.get("W"), pdf=pdf, azure=az)
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                c["kept"] += 1
                by["era"][era] += 1
                by["label_source"][ls] += 1
                by["kind"][kind] += 1
                by["src"][src] += 1
                by["titles"]["title"] += title
                by["titles"]["display_title"] += r["display"]
                by["journals"][d["jcode"]] += 1
                by["docs"][d["stem"]] += 1
    tmp.rename(OUT / "pool102.jsonl.gz")
    docs_by_era = Counter()
    summ = dict(counts=dict(c), by_era=dict(by["era"]), by_label_source=dict(by["label_source"]), by_kind=dict(by["kind"]),
                by_src=dict(by["src"]), titles=dict(by["titles"]), journals=len(by["journals"]), documents=len(by["docs"]),
                top_journals=by["journals"].most_common(15))
    (OUT / "pool102_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
