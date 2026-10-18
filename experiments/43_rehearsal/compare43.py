"""Experiment 43: a run of prompt v2 (out/<run>/rules + out/<run>/masters) against experiment 41 (its Argon answers +
masters) and the replay of 41's answers through the v2 code rules (out/replay/raw + out/masters). No model calls.

    compare43.py --run v2_55        -> out/<run>/compare.json (per article, three sources) + compare.txt (table)

Per article and source: words in the JATS body, blocks by type, reading order (lines moved against 41: lines minus
the longest common subsequence of the non-noise line order, and pages whose order changed), footnotes / endnotes,
calls (in the answer) and calls linked (masters stats), verse cuts, ornaments accepted, other_article blocks,
misprint flags (sic) and fixes (all; only hamza / alif / ya / ta marbuta; only diacritics), noise lines with words,
and the body words gone / new against 41 (examples).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import masters43 as M43  # noqa: E402
from masters43 import ST, etree  # noqa: E402

OUT = HERE / "out"
E41OUT = M43.E41 / "out"
HAND = ["0747-001-003-001", "2382-005-003-001", "0877-007-027-003", "0924-012-005-007", "1140-000-021-003"]
DIAC = re.compile("[ً-ْٰـ]")
ORTHO = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه", "ء": None})


def src_dirs(run):
    return {"41": (E41OUT / "argon" / "raw", E41OUT / "masters"),
            "replay": (OUT / "replay" / "raw", OUT / "masters"),
            "v2": (OUT / run / "rules", OUT / run / "masters")}


def body_words(p: Path) -> Counter:
    root = etree.parse(str(p), etree.XMLParser(load_dtd=False, no_network=True)).getroot()
    b = root.find("body")
    return Counter(" ".join(b.itertext()).split()) if b is not None else Counter()


def lcs(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def fix_kind(f):
    a, b = str(f.get("from") or ""), str(f.get("to") or "")
    if a.translate(ORTHO) == b.translate(ORTHO):
        return "ortho"
    if DIAC.sub("", a) == DIAC.sub("", b):
        return "diac"
    if DIAC.sub("", a).translate(ORTHO) == DIAC.sub("", b).translate(ORTHO):
        return "ortho"
    return "other"


def one(stem, raw: Path, mast: Path):
    files = sorted(raw.glob(f"{stem}_c*.json"))
    files = [f for f in files if not f.name.endswith(".failed.json")]
    if not files or not (mast / f"{stem}.jats.xml").exists():
        return None
    types, order, fixes, sic, calls, cuts, orn, endn = Counter(), {}, [], [], 0, 0, 0, 0
    for f in files:
        a = json.loads(f.read_text(encoding="utf-8"))["answer"]
        noise = set(map(str, a.get("noise") or []))
        for pg in a.get("pages") or []:
            for b in pg.get("blocks") or []:
                t = b.get("type")
                types[t] += 1
                calls += len(b.get("calls") or [])
                cuts += len(b.get("cut") or {})
                if t == "footnote" and b.get("note_kind") == "endnote":
                    endn += 1
                for lid in b.get("lines") or []:
                    lid = str(lid)
                    if lid not in noise and t not in ("header", "footer"):
                        order.setdefault(lid.split(":")[0], []).append(lid)
                for h in b.get("hemistichs") or []:
                    for lid in h:
                        order.setdefault(str(lid).split(":")[0], []).append(str(lid).rstrip("ab"))
        fixes += a.get("fixes") or []
        sic += a.get("sic") or []
        orn += len(a.get("ornaments") or [])
    st = mast / "stats" / f"{stem}.json"
    st = json.loads(st.read_text()) if st.exists() else {}
    fk = Counter(fix_kind(f) for f in fixes)
    text_words = len(M43.M.jats_text(mast / f"{stem}.jats.xml").split())
    return dict(body_words=body_words(mast / f"{stem}.jats.xml"), text_words=text_words, types=dict(types), order=order,
                fixes=len(fixes), fixes_ortho=fk["ortho"], fixes_diac=fk["diac"], fix_list=fixes, sic=len(sic),
                sic_list=sic, calls=calls, linked=st.get("calls_linked", 0), footnotes=st.get("footnotes", 0),
                endnotes=endn, cuts=cuts, ornaments_answer=orn, ornaments=st.get("ornaments", 0),
                other_article=types.get("other_article", 0), noise_with_words=st.get("noise_lines_with_words", 0),
                blocks=st.get("blocks", 0))


def moved(o41, o):
    lines, pages = 0, []
    for p in sorted(set(o41) | set(o), key=int):
        a, b = o41.get(p, []), o.get(p, [])
        common = set(a) & set(b)
        a2, b2 = [x for x in a if x in common], [x for x in b if x in common]
        m = len(a2) - lcs(a2, b2)
        if m:
            lines += m
            pages.append(int(p))
    return lines, pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="v2_55")
    args = ap.parse_args()
    D = src_dirs(args.run)
    rows, txt = {}, []
    tot = Counter()
    for a in ST.sample():
        s = a["stem"]
        r = {k: one(s, *D[k]) for k in D}
        if r["v2"] is None or r["41"] is None:
            continue
        w41, w2, wr = r["41"]["body_words"], r["v2"]["body_words"], r["replay"]["body_words"]
        mv, mp = moved(r["41"]["order"], r["v2"]["order"])
        row = dict(year=a.get("year"), pages=a.get("pages"))
        for k in D:
            x = r[k]
            row[k] = {kk: vv for kk, vv in x.items() if kk not in ("body_words", "order", "fix_list", "sic_list")}
            row[k]["body_words"] = sum(x["body_words"].values())
        row["order_moved_lines_vs_41"], row["order_pages_vs_41"] = mv, mp
        row["words_gone_vs_41"] = dict((w41 - w2).most_common(25))
        row["words_new_vs_41"] = dict((w2 - w41).most_common(25))
        row["words_gone_vs_replay"] = dict((wr - w2).most_common(25))
        row["words_new_vs_replay"] = dict((w2 - wr).most_common(25))
        row["sic_v2"] = r["v2"]["sic_list"][:20]
        row["fixes_v2_examples"] = r["v2"]["fix_list"][:12]
        rows[s] = row
        for k in D:
            for kk in ("body_words", "text_words", "fixes", "fixes_ortho", "fixes_diac", "sic", "calls", "linked", "footnotes",
                       "endnotes", "cuts", "ornaments", "other_article", "noise_with_words", "blocks"):
                tot[f"{k}.{kk}"] += row[k][kk]
        tot["order_moved_lines"] += mv
        tot["articles_order_changed"] += bool(mv)
        tot["articles"] += 1
    (OUT / args.run / "compare.json").write_text(json.dumps(dict(totals=tot, articles=rows), ensure_ascii=False,
                                                            indent=1), encoding="utf-8")
    hdr = (f"{'stem':22} {'body words 41/rp/v2':>17} {'all 41/v2':>11} {'blocks 41/v2':>12} {'moved':>5} {'linked/calls 41|v2':>19} "
           f"{'fn/en':>6} {'cut':>3} {'orn':>3} {'oth':>3} {'sic 41/v2':>9} {'fix 41/v2(ortho)':>17}")
    txt.append(hdr)
    for s, x in rows.items():
        o, p, v = x["41"], x["replay"], x["v2"]
        mark = "*" if s in HAND else " "
        txt.append(f"{s:21}{mark} {o['body_words']:>5}/{p['body_words']:>5}/{v['body_words']:>5} {o['text_words']:>5}/{v['text_words']:<5} "
                   f"{o['blocks']:>5}/{v['blocks']:<5}  {x['order_moved_lines_vs_41']:>5} "
                   f"{o['linked']:>4}/{o['calls']:<4}|{v['linked']:>4}/{v['calls']:<4} "
                   f"{v['footnotes'] - v['endnotes']:>3}/{v['endnotes']:<2} {v['cuts']:>3} {v['ornaments']:>3} "
                   f"{v['other_article']:>3} {o['sic']:>4}/{v['sic']:<4} {o['fixes']:>5}/{v['fixes']:>4}({v['fixes_ortho']})")
    txt.append(json.dumps(tot, indent=1))
    (OUT / args.run / "compare.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
