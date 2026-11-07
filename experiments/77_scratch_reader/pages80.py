"""Experiment 77, extra old print: experiment 80's 580 pre-2000 documents (S3 pull) -> out/pages80.jsonl.

The 8 documents that are mostly Latin script (arabic_share < 0.5) are left out; held-out journal codes are checked
(none).  Same row format as pages77.jsonl; build77.py builds them as split "old80".
"""
import json

from common77 import E, OUT, azure_pages, nonempty_lines, test_codes

D = E / "80_old_print_pull/data"
test = test_codes()
n = 0
with open(OUT / "pages80.jsonl", "w", encoding="utf-8") as fh:
    for r in map(json.loads, open(D / "manifest80.jsonl", encoding="utf-8")):
        if r["arabic_share"] < 0.5 or r["jcode"] in test or not (r["pdf"] and r["json"]):
            continue
        az, pdf = D / "fetch" / r["id"] / f"{r['id']}.json", D / "fetch" / r["id"] / f"{r['id']}.pdf"
        for k, pg in enumerate(azure_pages(az)):
            L = len(nonempty_lines(pg))
            if L:
                fh.write(json.dumps(dict(stem=r["id"], jcode=r["jcode"], year=r["year"], set="exp80", page=k + 1, lines=L,
                                         azure=str(az), pdf=str(pdf)), ensure_ascii=False) + "\n")
                n += 1
print(n, "pages")
