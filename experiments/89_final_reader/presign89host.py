"""Experiment 89: experiment 85's presign85host.py (copied 2026-11-05), with experiment 88's guard (locked journals AND
locked old-print documents) in place of experiment 84's journal-only one; written to this folder's out/gpu/up/.

Experiment 85: the presigned URL lists for re-cutting experiment 83's training data on the rented host.

    python3 presign85host.py HOURS        (system python3: it has boto3; the credentials never leave here)

The same lists as experiment 83's presign83.py (its document choice and page lists, read from experiment 83 and 77's
files; the same fields), written here: out/gpu/urls_<set>.jsonl, mode 600, for the sets new, r77train, r77dev, o80.
Every document id is checked against experiment 84's locked journals and experiment 76's held-out journals first.
"""
import json
import os
import sys
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "88_truth_and_lock"))
sys.path.insert(0, str(E / "84_display_fonts"))
if (E / "88_truth_and_lock/LOCKED_OLD_DOCS.json").exists():
    from locked_old import assert_not_locked  # noqa: E402  (exp 84's journals + exp 88's documents)
else:   # exp 88's list not written yet: its selector excludes plan83 / exp 77-80's pools by construction, and
        # forbid89.py re-checks these URL lists against it before any training starts
    from locked import assert_not_locked  # noqa: E402
    print("note: LOCKED_OLD_DOCS.json not written yet; journal guard only here, forbid89.py re-checks later")

OUTD = HERE / "out/gpu/up"
BUCKET = "mandumah-source-docs"


def plan_of(which):
    if which == "new":
        return [json.loads(l) for l in open(E / "83_reader_scale/out/data/plan83.jsonl", encoding="utf-8")]
    e77 = E / "77_scratch_reader/out"
    meta = {}
    for f in ("pages77.jsonl", "pages80.jsonl"):
        for l in open(e77 / f, encoding="utf-8"):
            p = json.loads(l)
            meta[p["stem"]] = p
    rows = ([json.loads(l) for l in open(e77 / "pages80.jsonl", encoding="utf-8")] if which == "o80"
            else json.loads((e77 / "select77.json").read_text())[which[3:]])
    pages = {}
    for r in rows:
        pages.setdefault(r["stem"], []).append(r["page"])
    return [dict(id=st, year=meta[st]["year"], era=None, jcode=meta[st]["jcode"], pages=sorted(pg))
            for st, pg in sorted(pages.items())]


def main():
    hours = float(sys.argv[1])
    assert 0 < hours <= 12
    OUTD.mkdir(parents=True, exist_ok=True)
    held = set(json.loads((E / "76_finetune_pilot/out/split76.json").read_text())["test"])
    s3 = boto3.client("s3", region_name="eu-north-1")
    for which in ("new", "r77train", "r77dev", "o80"):
        plan = plan_of(which)
        ids = [d["id"] for d in plan]
        assert_not_locked(ids)
        assert not [i for i in ids if i[:4] in held], "held-out journal in " + which
        out = OUTD / f"urls_{which}.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            os.chmod(out, 0o600)
            for d in plan:
                u = {ext: s3.generate_presigned_url("get_object", Params=dict(Bucket=BUCKET, Key=f"{d['id']}/{d['id']}.{ext}"),
                                                    ExpiresIn=int(hours * 3600)) for ext in ("pdf", "json")}
                sel = dict(pages=d["pages"]) if "pages" in d else dict(max_pages=d["max_pages"])
                f.write(json.dumps(dict(id=d["id"], year=d["year"], era=d["era"], jcode=d["jcode"], **sel, **u)) + "\n")
        print(which, len(plan), "documents signed for", hours, "h; none locked, none held out ->", out)


if __name__ == "__main__":
    main()
