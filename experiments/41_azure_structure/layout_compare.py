"""Experiment 41: the Layout view built from the masters against the one built from Argon's raw output (no model calls).

    .venv/bin/python layout_compare.py [--stems ...] [--old mirror_argon] [--new mirror] [--kind mirror|print]

Parses both HTML files of each article (out/views/<old>/<stem>.html and <new>/<stem>.html, or the print pages
print_argon/ and print/ <stem>.layout.html with --kind print) and compares page by page every block box (div.pc):
its kind (classes), box (left/top/width/height, tolerance 0.1 % of the page), font size and line pitch (2 % or 0.03), verse
column widths, text, and inline markup (fixes, flags, calls, maths, added text, continuation marks; link targets and
ids ignored, since the masters number footnotes their own way). Writes out/layout_compare/<kind>.json: per article
the differences, each with its class, page and block; prints the totals by class.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import lxml.html

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from structure import OUT, sample  # noqa: E402

V = OUT / "views"
TOL_BOX = 0.1            # % of the page width / height: the ALTO boxes are whole pixels (1 px = 0.04 %)
TOL_F = 0.02


def style(s: str) -> dict:
    out = {}
    for part in (s or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            m = re.match(r"-?[\d.]+", v.strip())
            out[k.strip()] = float(m.group(0)) if m else v.strip()
    return out


def norm_html(el) -> str:
    """Inner markup with link targets, ids and boxes left out, whitespace collapsed."""
    h = lxml.html.tostring(el, encoding="unicode")
    h = re.sub(r' (href|data-fn|id|data-bbox|loading|src|style)="[^"]*"', "", h)
    h = re.sub(r"\s+", " ", h)
    h = re.sub(r"> <", "><", h)
    return h.strip()


def blocks_of(path: Path, kind: str) -> tuple[dict, dict]:
    doc = lxml.html.fromstring(path.read_text(encoding="utf-8"))
    pages = {}
    if kind == "mirror":
        for sec in doc.xpath('//section[contains(@class,"mrow")]'):
            lp = sec.xpath('.//div[contains(@class,"lpage")]')[0]
            pages[sec.get("data-p")] = lp
    else:
        for lp in doc.xpath('//div[contains(@class,"lpage")]'):
            pages[lp.get("data-p")] = lp
    out = {}
    for p, lp in pages.items():
        bl = []
        for pc in lp.xpath('./div[contains(concat(" ",@class," ")," pc ")]'):
            cls = set(pc.get("class").split()) - {"pc"}
            st = style(pc.get("style"))
            inner = [c for c in pc if not (c.tag == "span" and "ob" in (c.get("class") or ""))]
            badges = [c.text_content() for c in pc if c.tag == "span" and "ob" in (c.get("class") or "")]
            tx = inner[0] if inner else None
            bl.append(dict(cls=" ".join(sorted(cls)), st=st, badges=badges,
                           text=re.sub(r"\s+", " ", tx.text_content()).strip() if tx is not None else "",
                           html=norm_html(tx) if tx is not None else "",
                           txst=style(tx.get("style")) if tx is not None else {},
                           txcls=tx.get("class") if tx is not None else None))
        out[p] = bl
    head = {}
    if kind == "mirror":
        h1 = doc.xpath("//header//h1")
        kk = doc.xpath('//header//p[@class="kicker"]')
        pv = doc.xpath('//header//p[@class="provenance"]')
        head = dict(title=h1[0].text_content() if h1 else "", kicker=kk[0].text_content() if kk else "",
                    provenance=re.sub(r"\s+", " ", pv[0].text_content()) if pv else "")
    return out, head


def compare(old, new) -> list[dict]:
    diffs = []
    for p in sorted(set(old) | set(new), key=lambda x: int(x)):
        A, B = old.get(p, []), new.get(p, [])
        if len(A) != len(B):
            diffs.append(dict(cls="block count", page=p, old=len(A), new=len(B),
                              old_kinds=[b["cls"] for b in A], new_kinds=[b["cls"] for b in B]))
        # align by order; when counts differ, align on (cls, text) with difflib
        import difflib
        ka = [(b["cls"], b["text"][:40]) for b in A]
        kb = [(b["cls"], b["text"][:40]) for b in B]
        sm = difflib.SequenceMatcher(a=ka, b=kb, autojunk=False)
        for op, i0, i1, j0, j1 in sm.get_opcodes():
            if op == "equal" or (op == "replace" and i1 - i0 == j1 - j0):
                for x, y in zip(range(i0, i1), range(j0, j1)):
                    diffs += block_diff(p, x, A[x], B[y])
            else:
                for x in range(i0, i1):
                    diffs.append(dict(cls="block only in old", page=p, i=x, kind=A[x]["cls"], text=A[x]["text"][:120]))
                for y in range(j0, j1):
                    diffs.append(dict(cls="block only in new", page=p, i=y, kind=B[y]["cls"], text=B[y]["text"][:120]))
    return diffs


def block_diff(p, i, a, b) -> list[dict]:
    out = []
    base = dict(page=p, i=i, kind=a["cls"])
    if a["cls"] != b["cls"]:
        out.append(dict(base, cls="kind", old=a["cls"], new=b["cls"]))
    bx = [k for k in ("left", "top", "width", "height") if abs(a["st"].get(k, 0) - b["st"].get(k, 0)) > TOL_BOX]
    if bx:
        out.append(dict(base, cls="box", keys=bx, old=[a["st"].get(k) for k in bx], new=[b["st"].get(k) for k in bx],
                        text=a["text"][:60]))
    for k in ("--f", "--lh"):
        x, y = a["st"].get(k), b["st"].get(k)
        if isinstance(x, float) and isinstance(y, float) and abs(x - y) > max(TOL_F * abs(x), 0.03):
            out.append(dict(base, cls=f"size {k}", old=x, new=y, text=a["text"][:60]))
        elif (x is None) != (y is None):
            out.append(dict(base, cls=f"size {k}", old=x, new=y))
    for k in ("--c1", "--c2", "--cg"):
        x, y = a["txst"].get(k), b["txst"].get(k)
        if (x is None) != (y is None) or (x is not None and abs(x - y) > 0.25):
            out.append(dict(base, cls="verse columns", key=k, old=x, new=y))
    if a["badges"] != b["badges"]:
        out.append(dict(base, cls="badges (order / continues)", old=a["badges"], new=b["badges"]))
    if a["text"] != b["text"]:
        x, y = a["text"], b["text"]
        k = next((j for j in range(min(len(x), len(y))) if x[j] != y[j]), min(len(x), len(y)))
        out.append(dict(base, cls="text", at=k, old=x[max(0, k - 80):k + 220], new=y[max(0, k - 80):k + 220]))
    elif a["html"] != b["html"]:
        out.append(dict(base, cls="markup", old=a["html"][:600], new=b["html"][:600]))
    if a["txcls"] != b["txcls"]:
        out.append(dict(base, cls="text box class", old=a["txcls"], new=b["txcls"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--kind", default="mirror", choices=["mirror", "print"])
    ap.add_argument("--old")
    ap.add_argument("--new")
    a = ap.parse_args()
    old_d = V / (a.old or f"{a.kind}_argon")
    new_d = V / (a.new or a.kind)
    suf = ".html" if a.kind == "mirror" else ".layout.html"
    res, tot, arts = {}, Counter(), Counter()
    for art in sample():
        s = art["stem"]
        if a.stems and s not in a.stems:
            continue
        o, oh = blocks_of(old_d / f"{s}{suf}", a.kind)
        n, nh = blocks_of(new_d / f"{s}{suf}", a.kind)
        d = compare(o, n)
        for k in oh:
            if oh[k] != nh.get(k):
                d.append(dict(cls=f"header {k}", old=oh[k], new=nh.get(k)))
        res[s] = dict(blocks_old=sum(len(v) for v in o.values()), blocks_new=sum(len(v) for v in n.values()),
                      diffs=d)
        c = Counter(x["cls"] for x in d)
        tot.update(c)
        arts.update(set(c))
        print(f"  {s:24} {res[s]['blocks_old']:>5} {res[s]['blocks_new']:>5}  " +
              ", ".join(f"{k} {v}" for k, v in sorted(c.items())), flush=True)
    od = OUT / "layout_compare"
    od.mkdir(parents=True, exist_ok=True)
    (od / f"{a.kind}.json").write_text(json.dumps(dict(total=tot, articles_with=arts, articles=res),
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print("total:", dict(tot))
    print("articles with:", dict(arts))


if __name__ == "__main__":
    main()
