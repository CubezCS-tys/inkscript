"""Experiment 77, step 5a: the held-out test pages, cut exactly like the training lines (read only).

Segmentation = Azure's line polygons (this tests READING, not layout).  Pages:
  - yardstick: the owner's 20 checked pages of experiment 34 (status done), truth = the owner's lines;
  - lab doc1 2399-003-008-002 p21 and doc2 0018-010-003-002 p3, truth = the lab's rev1 (lab.sqlite, read only);
  - lab doc3 0877-007-027-003 p4, no truth yet (compared with Argon only).
Writes out/test/test-0-000.tar (+ manifest) and out/test/pages.json (Azure / Argon line texts, truth, gold map).
"""
from __future__ import annotations

import io
import re
import json
import sqlite3
import tarfile
from pathlib import Path

import pypdfium2 as pdfium

from common77 import E, OUT, azure_pages, clean_label, cut_line, encode, fixpath, nonempty_lines, render_page, test_codes

GOLD = E / "34_yardstick/out/gold"
LAB = E / "75_ocr_lab/out/data/lab.sqlite"
LABELS = E / "41_azure_structure/out/argon/labels"


def find_sources(stem: str):
    for d in (E / "28_scale/out/azure" / stem, E / "34_yardstick/out/extra" / stem):
        if (d / f"{stem}.json").exists() and (d / f"{stem}.pdf").exists():
            return d / f"{stem}.json", d / f"{stem}.pdf"
    for l in open(E / "76_finetune_pilot/out/inventory76.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r["stem"] == stem:
            return fixpath(r["azure"]), fixpath(r["pdf"])
    raise FileNotFoundError(stem)


def argon_lines(stem: str, page: int) -> dict[int, str]:
    f = LABELS / f"{stem}.json"
    if not f.exists():
        return {}
    d = json.loads(f.read_text(encoding="utf-8"))
    out: dict[int, list[str]] = {}
    for ln in sorted((x for x in d["lines"] if x["page"] == page), key=lambda x: x["id"]):
        k = int(re.match(r"\d+", ln["id"].split(":")[1]).group())     # "3:7a", "3:7b": Argon split line 7
        out.setdefault(k, []).append(ln["text"])
    return {k: " ".join(v) for k, v in out.items()}


def lab_truth(page_id: str) -> str | None:
    c = sqlite3.connect(f"file:{LAB}?mode=ro", uri=True)
    r = c.execute("select body_json from annotations where page_id=? order by rev_no desc limit 1", (page_id,)).fetchone()
    if not r:
        return None
    b = json.loads(r[0])
    return "\n".join(ln["text"] for ln in b["lines"] if not ln.get("unreadable"))


def main():
    assert all(s[:4] in test_codes() for s in ("2399", "0018", "0877"))
    pages = []
    for f in sorted(GOLD.glob("*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        if g.get("status") == "done":
            pages.append(dict(set="yardstick", stem=g["stem"], page=g["page"], gold=g))
    for pid, st, pg in (("doc1", "2399-003-008-002", 21), ("doc2", "0018-010-003-002", 3), ("doc3", "0877-007-027-003", 4)):
        pages.append(dict(set="lab", lab=pid, stem=st, page=pg))
    td = OUT / "test"
    td.mkdir(exist_ok=True)
    tar = tarfile.open(td / "test-0-000.tar", "w")
    mf = open(td / "manifest-test.jsonl", "w", encoding="utf-8")
    out = []
    for P in pages:
        assert P["stem"][:4] in test_codes(), P["stem"]
        az, pdf = find_sources(P["stem"])
        pgs = azure_pages(az)
        doc = pdfium.PdfDocument(str(pdf))
        img = render_page(doc, P["page"] - 1)
        pg = pgs[P["page"] - 1]
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        lines = nonempty_lines(pg)
        arg = argon_lines(P["stem"], P["page"])
        rec = dict(set=P["set"], lab=P.get("lab"), stem=P["stem"], page=P["page"],
                   page_id=f"{P['stem']}_p{P['page']:03d}", lines=[], argon_available=bool(arg))
        for ln in lines:
            key = f"{P['stem']}_p{P['page']:03d}_l{ln['i']:03d}"
            crop, info = cut_line(img, ln["poly"], sx, sy, test=True)
            row = dict(i=ln["i"], key=key, azure=ln["text"], argon=arg.get(ln["i"]), cut=crop is not None,
                       cut_info=info)
            if crop is not None:
                for name, data in ((key + ".jpg", encode(crop)), (key + ".txt", clean_label(ln["text"]).encode())):
                    ti = tarfile.TarInfo(name)
                    ti.size = len(data)
                    tar.addfile(ti, io.BytesIO(data))
                mf.write(json.dumps(dict(key=key, W=info["W"], label=clean_label(ln["text"])), ensure_ascii=False) + "\n")
            rec["lines"].append(row)
        if P["set"] == "yardstick":
            g = P["gold"]
            by = {l["id"]: l for l in g["lines"]}
            truth = [by[i] for i in g["order"] if by[i]["status"] != "deleted"]
            rec["truth"] = [l["text"] for l in truth]
            rec["decade"] = g.get("decade")
            # gold line -> Azure line (the gold was drafted from Azure's lines: exact text, in order)
            used = set()
            gmap = {}
            for pos, l in enumerate(truth):
                a = (l.get("draft") or {}).get("azure", "").strip()
                for ln in lines:
                    if ln["i"] not in used and ln["text"] == a:
                        used.add(ln["i"])
                        gmap[ln["i"]] = pos
                        break
            rec["gold_pos"] = gmap
            rec["truth_source"] = "experiment 34 yardstick, checked by the owner (October 2026)"
        else:
            t = lab_truth(rec["page_id"])
            rec["truth"] = t.split("\n") if t else None
            rec["truth_source"] = "lab rev1 (owner, 2026-11-04)" if t else "none yet (document 3)"
        out.append(rec)
        print(rec["page_id"], rec["set"], len(lines), "lines;", sum(not r["cut"] for r in rec["lines"]), "not cut;",
              "argon" if arg else "no argon", flush=True)
    tar.close()
    mf.close()
    (td / "pages.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")


if __name__ == "__main__":
    main()
