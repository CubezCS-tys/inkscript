"""Experiment 101 (experiment 100's dev100.py, copied 2026-11-24; the decision rule changed as below): score the DEV
runs (the same 40 pages of 5 articles outside the exam) against Azure's lines, to choose prompt and image size BEFORE
the exam run.  No key exists for dev pages; Azure (~0.8% letters wrong on the exam) is good enough
to rank settings, as in experiment 99's OPTIONS.md.

    EXP101_MODEL=out/model/4B EXP101_DEVOUT=out/dev/4B nice -n 19 ionice -c3 /home/appuser/inkscript/.venv/bin/python dev101.py
    (every <model dir>/dev_<tag>/; tags p1_px20, p1_px41, p2_px20, p2_px41)

Per candidate: letters wrong against Azure's lines (folded, punctuation ignored; a line not found counts all its
letters), the same on found lines only, share of Azure text missing, share of the answer matching nothing on the
page, pages cut short by the token limit, pages with loops, output tokens, seconds.  Writes out/dev/dev_summary.json.

Decision rule (pre-registered in the README before any dev output was seen): a candidate with more than 10% of the dev
pages (more than 4 of 40) cut by the token limit (finish "length") is out.  Of the rest, the lowest "letters wrong
incl. missing" (folded, punctuation ignored, a line not found counts all its letters); every candidate within 0.3
points of it is tied, and among the tied the smaller image wins, then the shorter prompt (P1 before P2).
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import convert101 as V  # noqa: E402
sys.path.insert(0, V.P97)
import score97 as S  # noqa: E402
from common97 import lev  # noqa: E402
import score101 as Q  # noqa: E402  (loops)

FETCH = f"{V.X}/74_gate2_full/out/fetch"
PAGES = f"{V.X}/43_rehearsal/out/pages"
DEV = json.load(open(f"{HERE}/DEV_PAGES.json"))["pages"]


def jpeg_size(path):
    with open(path, "rb") as f:
        f.read(2)
        while True:
            m, = struct.unpack(">H", f.read(2))
            ln, = struct.unpack(">H", f.read(2))
            if m in (0xFFC0, 0xFFC1, 0xFFC2):
                f.read(1)
                h, w = struct.unpack(">HH", f.read(4))
                return w, h
            f.read(ln - 2)


_az = {}


def azure_lines(stem, page):
    if stem not in _az:
        _az[stem] = json.load(open(f"{FETCH}/{stem}/{stem}.json"))
    p = _az[stem]["pages"][page - 1]
    w, h = jpeg_size(f"{PAGES}/{stem}_p{page:03d}.jpg")
    k = w / p["width"]
    out = []
    for n, l in enumerate(p["lines"], 1):
        xs, ys = l["polygon"][0::2], l["polygon"][1::2]
        out.append(dict(line=n, text=l["content"], x=min(xs) * k, y=min(ys) * k, w=(max(xs) - min(xs)) * k,
                        h=(max(ys) - min(ys)) * k))
    return out


def f(s):
    return S.no_punct(S.r1_fold(s or ""))


def score(tag):
    d = f"{V.MODEL_DIR}/dev_{tag}"
    tot = wrong = miss = found_letters = found_wrong = 0
    out_letters = inv = 0
    rows = []
    for p in DEV:
        fn = f"{d}/{p['stem']}_p{p['page']:03d}.json"
        if not os.path.exists(fn):
            continue
        a = json.load(open(fn))
        az = azure_lines(p["stem"], p["page"])
        v = V.PageView(a["raw"], az)
        cover = [False] * len(v.NT)
        pw = pt = 0
        for l in az:
            t = f(l["text"])
            n = len(t)
            if not n:
                continue
            tot += n
            pt += n
            m = v.lines[l["line"]]
            if not m["found"]:
                wrong += n
                miss += n
                pw += n
                continue
            o = f(v.original(*m["span"]))
            e = min(n, lev(o, t))
            wrong += e
            pw += e
            found_letters += n
            found_wrong += e
            for k in range(*m["span"]):
                cover[k] = True
        for k_, b_ in enumerate(v.nblock):          # runs never span two blocks (separators count as covered)
            if b_ is None:
                cover[k_] = True
        az_norm = V.nrm(" ".join(l["text"] for l in az))
        run, ol = [], len(v.NT.replace(" ", ""))
        out_letters += ol
        pinv = 0
        for k, ch in enumerate(v.NT + "\0"):
            if k < len(v.NT) and not cover[k]:
                run.append(ch)
                continue
            s = "".join(run).strip()
            run = []
            if len(s.replace(" ", "")) >= 20 and V.fuzz.partial_ratio(s, az_norm) < 80:
                pinv += len(s.replace(" ", ""))
        inv += pinv
        lp = Q.loops(a["raw"], az_norm)
        u = a.get("usage") or {}
        rows.append(dict(page=f"{p['stem']}_p{p['page']:03d}", letters_wrong=round(pw / pt, 4) if pt else None,
                         invented=round(pinv / ol, 4) if ol else None, finish=a.get("finish_reason"), loop=lp["loop"],
                         out_tokens=u.get("completion_tokens"), prompt_tokens=u.get("prompt_tokens"),
                         seconds=a.get("seconds"), sent=a.get("image_sent")))
    if not rows:
        return None
    tk = [r["out_tokens"] or 0 for r in rows]
    return dict(pages=len(rows), letters_wrong_incl_missing=S.rate(wrong, tot), letters_wrong_found_lines=S.rate(found_wrong, found_letters),
                missing=S.rate(miss, tot), invented=S.rate(inv, out_letters),
                cut_short=sum(r["finish"] == "length" for r in rows), loops=sum(r["loop"] for r in rows),
                out_tokens_median=statistics.median(tk), out_tokens_max=max(tk),
                prompt_tokens_median=statistics.median(r["prompt_tokens"] or 0 for r in rows),
                seconds_median=statistics.median(r["seconds"] or 0 for r in rows), per_page=rows)


def px_rank(tag):          # p1_px20 -> 20 (smaller image first)
    return int(tag.split("_px")[1]) if "_px" in tag else 99


def prompt_rank(tag):      # P1 (short) before P2 (with the example)
    return int(tag[1]) if tag[:1] == "p" and tag[1:2].isdigit() else 9


def main():
    res = {}
    for d in sorted(x for x in glob.glob(f"{V.MODEL_DIR}/dev_*") if os.path.isdir(x)):
        tag = os.path.basename(d)[4:]
        r = score(tag)
        if r:
            res[tag] = r
            print(tag, {k: v for k, v in r.items() if k != "per_page"}, flush=True)
    if res:
        tags = [t for t in res if not t.startswith("_")]
        out_ = [t for t in tags if res[t]["cut_short"] > 0.10 * res[t]["pages"]]
        ok = [t for t in tags if t not in out_]
        if ok:
            best = min(ok, key=lambda t: res[t]["letters_wrong_incl_missing"])
            close = [t for t in ok if res[t]["letters_wrong_incl_missing"] - res[best]["letters_wrong_incl_missing"] <= 0.003]
            pick = min(close, key=lambda t: (px_rank(t), prompt_rank(t)))
        else:
            best, close, pick = None, [], None
        res["_decision"] = dict(out_for_loops=out_, lowest=best, within_0_3_points=close, chosen=pick,
                                complete=all(res[t]["pages"] == len(DEV) for t in tags))
        print("decision", res["_decision"])
    out = os.environ.get("EXP101_DEVOUT") or f"{V.E}/out/dev"
    os.makedirs(out, exist_ok=True)
    S.jdump(res, f"{out}/dev_summary.json")


if __name__ == "__main__":
    main()
