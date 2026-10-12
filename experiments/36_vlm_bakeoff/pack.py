"""The page pack for the rented GPU, the yardstick's Azure reference, and the Kraken job list (experiment 36).

    PYTHONPATH=<worktree>/src /home/yassine/inkscript/.venv/bin/python pack.py     (after bd.py build)
Reads the gold set READ ONLY (experiments/34_yardstick/out/gold; the owner is correcting it live) and bd.py's output.
Writes, under experiments/36_vlm_bakeoff/out/:
  ref/azure/<page_id>.json   Azure's draft of every yardstick page: the lines' `draft.azure` text and draft boxes, in
                             the draft's order, taken from the page's oldest saved version (.history/<id>/ first file:
                             the untouched draft) when the owner has saved it, else the current file
  pack/manifest.json         one row per page (yardstick + born-digital)
  pack/pages.tar             pages/<page_id>.jpg (yardstick JPEGs byte for byte: 300 dpi grey, quality 88; born-digital
                             rendered the same way by bd.py) + manifest.json; no compression (JPEG)
  kraken_jobs.tsv            page_id <TAB> image path, for kraken_check.py
  gold_done.json             the gold pages whose status is "done" right now
"""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

GOLD = Path("/home/yassine/inkscript/experiments/34_yardstick/out/gold")
OUT = Path("/home/yassine/inkscript/experiments/36_vlm_bakeoff/out")


def draft_version(pid: str) -> tuple[dict, str]:
    h = GOLD / ".history" / pid
    if h.is_dir():
        fs = sorted(h.glob("*.json"))
        if fs:
            return json.loads(fs[0].read_text(encoding="utf-8")), f".history/{pid}/{fs[0].name}"
    return json.loads((GOLD / f"{pid}.json").read_text(encoding="utf-8")), f"{pid}.json"


def columns(g: dict) -> int:
    return max([r.get("column") or 0 for r in g.get("regions", [])] + [1])


def main():
    (OUT / "ref" / "azure").mkdir(parents=True, exist_ok=True)
    (OUT / "pack").mkdir(parents=True, exist_ok=True)
    rows, done, jobs = [], [], []
    for f in sorted(GOLD.glob("*.json")):
        cur = json.loads(f.read_text(encoding="utf-8"))
        pid = cur["page_id"]
        if cur.get("status") == "done":
            done.append(dict(page_id=pid, split=cur.get("split"), lines=len(cur["lines"]), seconds=cur.get("seconds"),
                             checked=cur.get("checked")))
        g, src = draft_version(pid)
        by = {ln["id"]: ln for ln in g["lines"]}
        lines = []
        for i in g["order"]:
            ln = by[i]
            t = (ln.get("draft") or {}).get("azure")
            if t:
                ws = ln.get("words") or []
                lines.append(dict(text=t, box=ln["box"], kind=ln.get("kind"),
                                  conf=min((w.get("conf") or 0) for w in ws) if ws else None))
        im = g["image"]
        json.dump(dict(page_id=pid, source=f"Azure's draft from gold/{src}", image=dict(width=im["width"], height=im["height"],
                       dpi=im.get("dpi", 300)), lines=lines), open(OUT / "ref" / "azure" / f"{pid}.json", "w"),
                  ensure_ascii=False, indent=1)
        tags = list(cur.get("kinds", []))
        if columns(cur) >= 2 and "columns" not in tags:
            tags.append("columns")
        if cur.get("tables") and "table" not in tags:
            tags.append("table")
        if cur.get("equations") and "equation" not in tags:
            tags.append("equation")
        rows.append(dict(page_id=pid, kind="yardstick", split=cur.get("split"), stem=cur.get("stem"), page=cur.get("page"),
                         journal=cur.get("journal", ""), journal_code=pid[:4], year=cur.get("year", ""),
                         decade=cur.get("decade", ""), field=cur.get("field", ""), primary=cur.get("primary", ""), tags=tags,
                         width=im["width"], height=im["height"], dpi=im.get("dpi", 300), file=f"pages/{pid}.jpg",
                         lines=len(lines), ncols=columns(cur), angle=im.get("angle", 0.0)))
        jobs.append((pid, str(GOLD / f"{pid}.jpg")))
    bd = json.load(open(OUT / "bd_pages.json"))
    for r in bd:
        rows.append(r)
        jobs.append((r["page_id"], str(OUT / "pack" / "bd" / f"{r['page_id']}.jpg")))
    for r in rows:
        r["bytes"] = Path(dict(jobs)[r["page_id"]]).stat().st_size
    man = OUT / "pack" / "manifest.json"
    man.write_text(json.dumps(dict(
        about="Experiment 36 page pack. yardstick: experiment 34's gold pages (truth = the owner's corrections, only pages "
              "with status done; score with `inkscript score`). born-digital: experiment 33's held-out (test) and dev "
              "documents with the exact text layer as truth (out/ref/bdtruth). Images: 300 dpi grey JPEG, quality 88; "
              "boxes everywhere in these pixels. split: test = held out (report), dev = may be used for prompt tuning.",
        pages=rows), ensure_ascii=False, indent=1), encoding="utf-8")
    with tarfile.open(OUT / "pack" / "pages.tar", "w") as tf:
        tf.add(man, arcname="manifest.json")
        for pid, p in jobs:
            tf.add(p, arcname=f"pages/{pid}.jpg")
    (OUT / "kraken_jobs.tsv").write_text("".join(f"{a}\t{b}\n" for a, b in jobs))
    json.dump(done, open(OUT / "gold_done.json", "w"), indent=1)
    from collections import Counter
    print(len(rows), "pages", Counter((r["kind"], r["split"]) for r in rows))
    print("tar", round((OUT / "pack" / "pages.tar").stat().st_size / 1e6, 1), "MB;",
          "yardstick", round(sum(r["bytes"] for r in rows if r["kind"] == "yardstick") / 1e6, 1), "MB;",
          "born-digital", round(sum(r["bytes"] for r in rows if r["kind"] == "born-digital") / 1e6, 1), "MB")
    print("gold done:", [d["page_id"] for d in done])


if __name__ == "__main__":
    main()
