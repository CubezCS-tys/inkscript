"""Experiment 77, step 1a: every page we may train on (read only).  One JSON line per page -> out/pages77.jsonl.

Source: experiment 76's inventory (2,315 articles with Azure JSON + scan PDF on disk).  Excluded: the 27 held-out
journal codes of out/split76.json (and therefore every test article), and the 2 duplicate rows.
"""
from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor

from common77 import INV, OUT, azure_pages, fixpath, nonempty_lines, test_codes


def one(row):
    pgs = azure_pages(fixpath(row["azure"]))
    out = []
    for k, pg in enumerate(pgs):
        n = len(nonempty_lines(pg))
        if n:
            out.append(dict(stem=row["stem"], jcode=row["jcode"], year=row.get("year"), set=row["set"], page=k + 1,
                            lines=n, azure=str(fixpath(row["azure"])), pdf=str(fixpath(row["pdf"]))))
    return out


def main():
    test = test_codes()
    rows = [json.loads(l) for l in open(INV, encoding="utf-8")]
    keep = [r for r in rows if not r["dup"] and r["azure_ok"] and r["pdf_ok"] and r["jcode"] not in test]
    print(f"{len(rows)} articles; {len(keep)} kept (test journals and duplicates out)", flush=True)
    n = 0
    with ProcessPoolExecutor(4) as ex, open(OUT / "pages77.jsonl", "w", encoding="utf-8") as fh:
        for res in ex.map(one, keep, chunksize=8):
            for p in res:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
                n += 1
    print(n, "pages")


if __name__ == "__main__":
    main()
