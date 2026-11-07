"""Experiment 85: time-limited GET URLs for the documents a line list needs (system python3: it has boto3).

    python3 presign85.py HOURS LINES.jsonl OUT_URLS.jsonl

One line per document not already on this machine (experiment 80's pull is read from its own data/fetch):
{id, pdf, json}, file mode 600.  Signing is a local computation; nothing is written to S3; the URLs read one object
each until they expire (at most 12 hours).
"""
import json
import os
import sys
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
LOCAL80 = HERE.parent / "80_old_print_pull/data/fetch"
BUCKET = "mandumah-source-docs"


def main():
    hours = float(sys.argv[1])
    assert 0 < hours <= 12
    lines, out = Path(sys.argv[2]), Path(sys.argv[3])
    docs = sorted({json.loads(l)["key"].split("_p")[0] for l in open(lines, encoding="utf-8") if l.strip()})
    need = [d for d in docs if not (LOCAL80 / d / f"{d}.pdf").exists()]
    s3 = boto3.client("s3", region_name="eu-north-1")
    with open(out, "w", encoding="utf-8") as f:
        os.chmod(out, 0o600)
        for d in need:
            u = {ext: s3.generate_presigned_url("get_object", Params=dict(Bucket=BUCKET, Key=f"{d}/{d}.{ext}"),
                                                ExpiresIn=int(hours * 3600)) for ext in ("pdf", "json")}
            f.write(json.dumps(dict(id=d, **u)) + "\n")
    print(f"{len(docs)} documents, {len(docs) - len(need)} on disk (exp 80), {len(need)} signed for {hours} h -> {out}")


if __name__ == "__main__":
    main()
