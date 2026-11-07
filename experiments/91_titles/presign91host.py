"""Experiment 91: the presigned URL lists for the GPU host (system python3: it has boto3; the credentials never leave
this machine).  Written to out/gpu/up/, mode 600; they expire.

    nice -n 19 python3 presign91host.py HOURS

  urls_t91.jsonl                         the NEW documents of out/data/docs91.jsonl (select91.py), with their catalogue
                                         title / subtitle, for title91.py on the host (JSON first; the PDF only on a
                                         confident match);
  urls_new / r77train / r77dev / o80     experiment 83's training data, exactly as experiment 89's presign89host.py
                                         lists it (its plan_of, imported), re-cut on the host by cut91.py (= cut83.py +
                                         the title hook); the rows of documents in docs91.jsonl also carry set, title,
                                         subtitle and tera (the title era), so their page 1 is matched with no extra
                                         download.
Every id is checked against the locked guard (locked_old.assert_not_locked) and split76's held-out journals first.
"""
import json
import os
import sys
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "88_truth_and_lock"))
sys.path.insert(0, str(E / "89_final_reader"))
from locked_old import assert_not_locked  # noqa: E402
from presign89host import BUCKET, plan_of  # noqa: E402

OUTD = HERE / "out/gpu/up"


def main():
    hours = float(sys.argv[1])
    assert 0 < hours <= 12
    OUTD.mkdir(parents=True, exist_ok=True)
    held = set(json.loads((E / "76_finetune_pilot/out/split76.json").read_text())["test"])
    s3 = boto3.client("s3", region_name="eu-north-1")
    D91 = {d["id"]: d for d in map(json.loads, open(HERE / "out/data/docs91.jsonl", encoding="utf-8"))}
    t91 = [d for d in D91.values() if d["set"] == "new"]
    lists = {"t91": t91, **{w: plan_of(w) for w in ("new", "r77train", "r77dev", "o80")}}
    for which, plan in lists.items():
        ids = [d["id"] for d in plan]
        assert_not_locked(ids)
        assert not [i for i in ids if i[:4] in held], "held-out journal in " + which
        out = OUTD / f"urls_{which}.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            os.chmod(out, 0o600)
            for d in plan:
                u = {ext: s3.generate_presigned_url("get_object", Params=dict(Bucket=BUCKET, Key=f"{d['id']}/{d['id']}.{ext}"),
                                                    ExpiresIn=int(hours * 3600)) for ext in ("pdf", "json")}
                if which == "t91":
                    rec = {k: d[k] for k in ("id", "set", "year", "era", "jcode", "title", "subtitle")}
                else:
                    sel = dict(pages=d["pages"]) if "pages" in d else dict(max_pages=d["max_pages"])
                    rec = dict(id=d["id"], year=d["year"], era=d["era"], jcode=d["jcode"], **sel)
                    if d["id"] in D91:
                        t = D91[d["id"]]
                        rec.update(set=t["set"], tera=t["era"], title=t["title"], subtitle=t["subtitle"])
                f.write(json.dumps(dict(**rec, **u), ensure_ascii=False) + "\n")
        print(which, len(plan), "documents signed for", hours, "h; none locked, none held out ->", out.name)


if __name__ == "__main__":
    main()
