"""Experiment 43: how often rules43.pictures fires, and what it takes (no model calls).

    pictures43.py --run v3_test --build out/v31_test/v3_now [--stems ...]
                                                the run's answers through today's rules (DIR/rules) and masters
                                                (DIR/masters), JATS DTD + ALTO XSD checked
    pictures43.py --run v2_55 [--stems ...]     out/<run>/pictures.json (every firing) + out/<run>/pictures/*.jpg
                                                (one contact sheet per page that fired: the page with the new
                                                figure boxes in red, the junk lines in orange, the answer's own
                                                figures in blue, pictures of another article dashed)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import masters43 as M43  # noqa: E402
import replay43 as RP  # noqa: E402
import run43  # noqa: E402
from masters43 import ST  # noqa: E402

OUT = HERE / "out"


def sheet(a, p, figs, junk, lines, dst: Path):
    import cv2
    img = cv2.imread(str(ST.page_image(a, p)), cv2.IMREAD_COLOR)
    H, W = img.shape[:2]
    s = 1100 / H
    img = cv2.resize(img, (int(W * s), 1100), interpolation=cv2.INTER_AREA)
    h, w = img.shape[:2]
    P = lambda b: ((int(b[0] * w / 1000), int(b[1] * h / 1000)), (int(b[2] * w / 1000), int(b[3] * h / 1000)))  # noqa
    for i in junk:
        a0, a1 = P(lines[i]["b"])
        cv2.rectangle(img, a0, a1, (0, 140, 255), 2)
    for f in figs:
        a0, a1 = P(f["box"])
        col = (0, 0, 230) if "ink" in str(f.get("level") or "") else (220, 90, 0)
        if "other" in str(f.get("level") or ""):
            for x in range(a0[0], a1[0], 14):
                cv2.line(img, (x, a0[1]), (min(x + 7, a1[0]), a0[1]), col, 3)
                cv2.line(img, (x, a1[1]), (min(x + 7, a1[0]), a1[1]), col, 3)
            for y in range(a0[1], a1[1], 14):
                cv2.line(img, (a0[0], y), (a0[0], min(y + 7, a1[1])), col, 3)
                cv2.line(img, (a1[0], y), (a1[0], min(y + 7, a1[1])), col, 3)
        else:
            cv2.rectangle(img, a0, a1, col, 3)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), img, [cv2.IMWRITE_JPEG_QUALITY, 80])


def build(run: str, raw: str, dst: Path, stems):
    from inkscript.enrich.schemas import validate_alto, validate_jats
    arts = [a for a in run43.articles("a") if not stems or a["stem"] in stems]
    src, rules = OUT / run / raw, dst / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    bad = []
    for a in arts:
        fs = [src / f"{a['stem']}_c{x:03d}-{y:03d}.json" for x, y in ST.chunks(a)]
        if not all(f.exists() for f in fs):
            continue
        for f in fs:
            rec = ST.jl(f)
            ans, log = RP.apply_rules(a, rec)
            RP.jdump(rules / f.name, dict(rec, answer=ans, rules43=log))
        r = M43.build43(a, rules, dst / "masters", True, run=run)
        j = validate_jats(dst / "masters" / f"{a['stem']}.jats.xml")
        al = validate_alto(dst / "masters" / f"{a['stem']}.alto.xml")
        if j or al or r.get("error"):
            bad.append(dict(stem=a["stem"], error=r.get("error"), jats=j[:3], alto=al[:3]))
        print(f"  {a['stem']:24} {'ERROR ' + r['error'] if r.get('error') else 'ok'}"
              f"{' INVALID' if j or al else ''}", flush=True)
    print(f"invalid: {bad}" if bad else "all JATS DTD + ALTO XSD valid")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", help="folder: rules + masters of the run's answers with today's code")
    ap.add_argument("--run", required=True)
    ap.add_argument("--raw", default="raw", help="folder under out/<run>/ holding the answers")
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--no-sheets", action="store_true")
    args = ap.parse_args()
    if args.build:
        return build(args.run, args.raw, Path(args.build).resolve(), args.stems)
    src = OUT / args.run / args.raw
    arts = [a for a in run43.articles("a") if not args.stems or a["stem"] in args.stems]
    rep, tot = {}, Counter()
    for a in arts:
        for x, y in ST.chunks(a):
            f = src / f"{a['stem']}_c{x:03d}-{y:03d}.json"
            if not f.exists():
                continue
            rec = ST.jl(f)
            lines = RP.chunk_lines(a, x, y)
            ans, log = RP.apply_rules(a, rec)
            fired = log["pictures"]
            n_other = log["pictures_other_article"]
            for e in log["pictures_skipped"]:
                tot[f"skipped ({e['why']})"] += 1
            if not fired and not n_other:
                continue
            new = [e for e in fired if e["action"] == "new figure from ink"]
            tot["chunks"] += 1
            tot["new_figures"] += len(new)
            tot["junk_lines"] += log["picture_junk"]
            tot["figures_other_article"] += n_other
            tot["junk_out_of_figure_text"] += sum(len(e["lines"]) for e in fired if e["action"] != "new figure from ink")
            rep[f.stem] = dict(fired=fired, other_article=n_other)
            if args.no_sheets:
                continue
            junk = set(ans.get("_picture_junk") or [])
            for pg in ans["pages"]:
                p = pg.get("page")
                figs = [b for b in pg.get("blocks") or [] if isinstance(b, dict) and b.get("type") == "figure"
                        and b.get("box")]
                if any(e["page"] == p for e in fired) or any("other" in str(b.get("level") or "") for b in figs):
                    sheet(a, p, figs, [i for i in junk if lines[i]["page"] == p], lines,
                          OUT / args.run / "pictures" / f"{a['stem']}_p{p:03d}.jpg")
    tot["articles"] = len({k.split("_c")[0] for k in rep})
    out = OUT / args.run / "pictures.json"
    out.write_text(json.dumps(dict(totals=dict(tot), chunks=rep), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(tot)), "->", out)
    for k, v in rep.items():
        for e in v["fired"]:
            print(f"  {k:32} p{e['page']:<3} {e['action']:30} {e.get('box', '')} {e.get('fill', '')} {e['text'][:50]}")
        if v["other_article"]:
            print(f"  {k:32} {v['other_article']} figure(s) in another article's region")


if __name__ == "__main__":
    main()
