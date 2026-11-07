"""Experiment 83: time-limited, read-only GET URLs for the chosen documents (made here; only the URLs go to the host).

    python3 presign83.py HOURS SET [N=all]       (system python3: it has boto3; the credentials never leave here)

SET new:      out/data/plan83.jsonl (the new documents)             -> out/data/urls_new.jsonl
SET r77train: experiment 77's training pages (select77.json train)  -> out/data/urls_r77train.jsonl  (with "pages")
SET r77dev:   experiment 77's dev pages (select77.json dev)         -> out/data/urls_r77dev.jsonl
SET o80:      experiment 80's pull as experiment 77 used it (pages80.jsonl) -> out/data/urls_o80.jsonl
Each line (file mode 600): {id, year, era, jcode, max_pages | pages, pdf, json}.  A presigned
GET URL can only read that one object until it expires (at most 12 hours here); nothing is written to S3 and no
request is sent to AWS while signing (it is a local computation).
"""
import json
import os
import sys
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
DATA = HERE / "out/data"
BUCKET = "mandumah-source-docs"


def main():
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 10
    assert 0 < hours <= 12, "expiry must be at most 12 hours"
    which = sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else None
    s3 = boto3.client("s3", region_name="eu-north-1")
    if which == "new":
        plan = [json.loads(l) for l in open(DATA / "plan83.jsonl", encoding="utf-8")]
    else:
        e77 = HERE.parent / "77_scratch_reader/out"
        meta = {}
        for f in ("pages77.jsonl", "pages80.jsonl"):
            for l in open(e77 / f, encoding="utf-8"):
                p = json.loads(l)
                meta[p["stem"]] = p
        if which == "o80":
            rows = [json.loads(l) for l in open(e77 / "pages80.jsonl", encoding="utf-8")]
        else:
            rows = json.loads((e77 / "select77.json").read_text())[which[3:]]
        pages = {}
        for r in rows:
            pages.setdefault(r["stem"], []).append(r["page"])
        plan = [dict(id=st, year=meta[st]["year"], era=None, jcode=meta[st]["jcode"], pages=sorted(pg))
                for st, pg in sorted(pages.items())]
    plan = plan[:n]
    out = DATA / f"urls_{which}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        os.chmod(out, 0o600)
        for d in plan:
            u = {ext: s3.generate_presigned_url("get_object", Params=dict(Bucket=BUCKET, Key=f"{d['id']}/{d['id']}.{ext}"),
                                                ExpiresIn=int(hours * 3600)) for ext in ("pdf", "json")}
            sel = dict(pages=d["pages"]) if "pages" in d else dict(max_pages=d["max_pages"])
            f.write(json.dumps(dict(id=d["id"], year=d["year"], era=d["era"], jcode=d["jcode"], **sel, **u)) + "\n")
    print(len(plan), "documents signed for", hours, "hours ->", out)


if __name__ == "__main__":
    main()
