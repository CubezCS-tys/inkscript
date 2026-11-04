"""Experiment 61: check a sample of the leaks on the page images (no model calls).

    verify61.py sample [--n 4] [--seed 61]   pick up to N leaks per (field, kind) row of out/audit.json, crop each
                                             line from its page scan (the line outlined in red, two lines of
                                             context), stack them six to a sheet: out/verify/sheet_NN.jpg and
                                             out/verify/sample.json (what each numbered crop claims)
    verify61.py score                        read the hand verdicts in verdicts61.json ({"<n>": "ok" | "false: why"})
                                             -> the false-alarm rate per kind, written to out/verify/score.json

The verdicts are a person's (or the agent's) reading of each crop against its claim: is the line printed text of
this article, is it what the audit says it is (the field), and is it really not in that field (checked against the
article's JATS by the audit; the crop shows the ink)."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"
VER = OUT / "verify"
PAGES = REPO / "experiments/43_rehearsal/out/pages"
VIEWS = REPO / "experiments/41_azure_structure/out/views"


def page_image(stem: str, run: str, page: int) -> Path | None:
    f = PAGES / f"{stem}_p{page:03d}.jpg"
    if f.exists():
        return f
    for r in (run, "v2_55"):
        f = VIEWS / r / "scans" / stem / f"p{page:03d}.jpg"
        if f.exists():
            return f
    return None


def crop(stem, run, page, box, page_size) -> Image.Image | None:
    f = page_image(stem, run, page)
    if f is None:
        return None
    im = Image.open(f).convert("RGB")
    pw, ph = page_size
    sx, sy = im.width / pw, im.height / ph
    x, y, w, h = box
    pad = max(h * 2.2, 40)
    y0, y1 = max(0, (y - pad) * sy), min(im.height, (y + h + pad) * sy)
    c = im.crop((0, int(y0), im.width, int(y1)))
    d = ImageDraw.Draw(c)
    d.rectangle([x * sx - 4, y * sy - y0 - 3, (x + w) * sx + 4, (y + h) * sy - y0 + 3], outline=(220, 30, 30), width=4)
    if c.width > 1400:
        c = c.resize((1400, round(c.height * 1400 / c.width)))
    return c


def cmd_sample(a):
    d = json.loads((OUT / "audit.json").read_text(encoding="utf-8"))
    rnd = random.Random(a.seed)
    VER.mkdir(parents=True, exist_ok=True)
    picks = []
    for row in d["leak_table"]:
        ex = list(row["examples"])
        rnd.shuffle(ex)
        for e in ex[:a.n]:
            picks.append(dict(field=row["field"], kind=row["kind"], **e))
    arts = {}
    crops = []
    for i, p in enumerate(picks, 1):
        if p["stem"] not in arts:
            arts[p["stem"]] = json.loads((OUT / "articles" / f"{p['stem']}.json").read_text(encoding="utf-8"))
        A = arts[p["stem"]]
        c = crop(p["stem"], A["run"], p["page"], p["box"], A["page_size"][str(p["page"])])
        p["n"] = i
        p["image"] = c is not None
        crops.append((i, c))
    sheets = []
    for k in range(0, len(crops), 6):
        part = [(i, c) for i, c in crops[k:k + 6] if c is not None]
        if not part:
            continue
        W = max(c.width for _, c in part)
        H = sum(c.height + 46 for _, c in part)
        sh = Image.new("RGB", (W, H), "white")
        dr = ImageDraw.Draw(sh)
        y = 0
        for i, c in part:
            dr.rectangle([0, y, W, y + 40], fill=(30, 60, 110))
            dr.text((12, y + 12), f"#{i}", fill="white")
            sh.paste(c, (0, y + 44))
            y += c.height + 46
        name = f"sheet_{k // 6 + 1:02d}.jpg"
        sh.save(VER / name, quality=82)
        sheets.append(name)
    (VER / "sample.json").write_text(json.dumps(dict(n=len(picks), sheets=sheets, picks=picks), ensure_ascii=False,
                                                indent=1), encoding="utf-8")
    print(f"{len(picks)} leaks on {len(sheets)} sheets -> {VER}")


def cmd_score(a):
    s = json.loads((VER / "sample.json").read_text(encoding="utf-8"))
    v = json.loads((HERE / "verdicts61.json").read_text(encoding="utf-8"))
    by = {}
    for p in s["picks"]:
        verdict = v.get(str(p["n"]))
        if verdict is None:
            continue
        k = p["kind"]
        b = by.setdefault(k, dict(checked=0, false=0, examples=[]))
        b["checked"] += 1
        if "wrong field" in verdict:
            b["wrong_field"] = b.get("wrong_field", 0) + 1
        if verdict.startswith("false"):
            b["false"] += 1
            b["examples"].append(dict(n=p["n"], stem=p["stem"], line=p["line"], field=p["field"], why=verdict))
    tot = dict(checked=sum(b["checked"] for b in by.values()), false=sum(b["false"] for b in by.values()),
               wrong_field=sum(b.get("wrong_field", 0) for b in by.values()))
    tot["false_alarm_rate"] = round(100 * tot["false"] / tot["checked"], 1) if tot["checked"] else None
    for b in by.values():
        b["false_alarm_rate"] = round(100 * b["false"] / b["checked"], 1) if b["checked"] else None
    out = dict(total=tot, by_kind=by)
    (VER / "score.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("sample")
    s.add_argument("--n", type=int, default=3)
    s.add_argument("--seed", type=int, default=61)
    sp.add_parser("score")
    a = ap.parse_args()
    {"sample": cmd_sample, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    main()
