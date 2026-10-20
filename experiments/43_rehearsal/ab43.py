"""Experiment 43, step G0 (2026-10-20): the quality A/B that chooses the exam configuration (no model calls here).

    ab43.py numbers  ARM=DIR ...      per arm: pages, cost / output tokens a page, flags per 100 pages (by severity and
                                      kind), the model's fixes and misprints (sic), fixes in fully vowelled lines,
                                      letters_lost_vowelled; writes out/stepEF/g0/numbers.json
    ab43.py gold     ARM=RAWDIR ...   the 5 gold articles (the owner's checked set, experiment 41 answers) against
                                      each arm's answers: differences of kind / lines / text / links (gold43.diff)
    ab43.py changed  A=DIR B=DIR      pages whose blocks (kinds + lines) or text fixes differ between two arms
                                      (the pages to look at beside the scan)

An arm DIR holds rules/ (rules43 applied), masters/ and flags.json (flags43 --out DIR), and raw answers given by
--raw ARM=PATH (default DIR/raw).
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
OUT = HERE / "out"
G0 = OUT / "stepEF" / "g0"
MARKS = re.compile(r"[ً-ْ]")
LETTERS = re.compile(r"[ء-ي]")


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def vowelled(text: str) -> bool:
    n = len(LETTERS.findall(text or ""))
    return n >= 6 and len(MARKS.findall(text)) / n >= 0.3


def arm_numbers(d: Path, raw: Path, stems: list[str]) -> dict:
    from masters43 import ST
    import flags43 as F
    arts = F.all_articles()
    fl = jl(d / "flags.json")["articles"]
    n = Counter()
    kinds = Counter()
    per = {}
    for s in stems:
        a = arts[s]
        F.use_pages_of(a)
        pages = a["last"] - a["first"] + 1
        r = Counter(pages=pages)
        lines = {}
        for f in sorted(raw.glob(f"{s}_c*.json")):
            if f.name.endswith(".failed.json"):
                continue
            rec = jl(f)
            r["usd"] += rec.get("usd") or 0
            r["tout"] += rec.get("tout") or 0
            r["think"] += rec.get("think") or 0
            r["tin"] += rec.get("tin") or 0
            r["chunks"] += 1
            r["max_tokens"] += "MAX_TOKENS" in str(rec.get("finish"))
        for f in sorted((d / "rules").glob(f"{s}_c*.json")):
            rec = jl(f)
            x, y = rec["first"], rec["last"]
            try:
                for p in range(x, y + 1):
                    for L in ST.page_lines(a, p)[0]:
                        lines[str(L["id"])] = L["text"]
            except Exception:
                pass
            ans = rec["answer"]
            for fx in ans.get("fixes") or []:
                if str(fx.get("why") or "").startswith("code:"):
                    r["code_fixes"] += 1
                    continue
                r["fixes"] += 1
                if vowelled(lines.get(str(fx.get("line")), "")):
                    r["fixes_vowelled"] += 1
            r["sic"] += len(ans.get("sic") or [])
            r["math"] += len(ans.get("math") or [])
        r["vowelled_lines"] = sum(1 for t in lines.values() if vowelled(t))
        fa = fl.get(s) or {}
        for sev in ("high", "medium", "low"):
            r[sev] = fa.get(sev, 0)
        for k, v in (fa.get("kinds") or {}).items():
            kinds[k] += v
            r["k:" + k] = v
        per[s] = dict(r)
        n.update(r)
    pg = n["pages"] or 1
    tot = dict(pages=n["pages"], usd=round(n["usd"], 4), usd_page=round(n["usd"] / pg, 5),
               out_tokens_page=round(n["tout"] / pg), think_tokens_page=round(n["think"] / pg),
               in_tokens_page=round(n["tin"] / pg), max_tokens=n["max_tokens"],
               high_100=round(100 * n["high"] / pg, 2), medium_100=round(100 * n["medium"] / pg, 2),
               low_100=round(100 * n["low"] / pg, 2), fixes=n["fixes"], fixes_page=round(n["fixes"] / pg, 2),
               fixes_vowelled=n["fixes_vowelled"], vowelled_lines=n["vowelled_lines"], sic=n["sic"], math=n["math"],
               code_fixes=n["code_fixes"],
               kinds_100={k: round(100 * v / pg, 2) for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])})
    return dict(total=tot, articles=per)


def cmd_numbers(arms: list[str], raws: dict, stems: list[str]):
    G0.mkdir(parents=True, exist_ok=True)
    res = {}
    for spec in arms:
        name, d = spec.split("=", 1)
        d = Path(d).resolve()
        res[name] = arm_numbers(d, Path(raws.get(name) or d / "raw").resolve(), stems)
        t = res[name]["total"]
        print(f"{name:14} pp {t['pages']:4} ${t['usd_page']:.4f}/p out {t['out_tokens_page']}/p think "
              f"{t['think_tokens_page']}/p MAX {t['max_tokens']} | h {t['high_100']} m {t['medium_100']} l {t['low_100']} "
              f"| fixes {t['fixes']} (vowelled {t['fixes_vowelled']}) sic {t['sic']} math {t['math']}")
    out = G0 / "numbers.json"
    prev = jl(out) if out.exists() else {}
    prev.update(res)
    out.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_gold(arms: list[str]):
    import flags43 as F
    import gold43 as GD
    arts = F.all_articles()
    res = {}
    for spec in arms:
        name, raw = spec.split("=", 1)
        res[name] = {}
        for g in sorted(GD.GOLD.glob("*.json")):
            g = jl(g)
            now = GD.snapshot(arts[g["stem"]], Path(raw).resolve())
            d = GD.diff(g["snapshot"], now, g["scope"])
            c = Counter()
            for x in d:
                c["kind" if ": kind " in x else "lines" if ": lines " in x else "text" if ": text " in x
                  else "links" if ": links " in x or x.startswith("JATS links") else "gone" if ": gone" in x
                  else "new" if " new block " in x else "order" if x.startswith("reading order") else
                  "jats_text" if x.startswith("JATS text") else "other"] += 1
            gw, nw = g["snapshot"]["jats"]["text"].split(), now["jats"]["text"].split()
            import difflib
            sm = difflib.SequenceMatcher(a=gw, b=nw, autojunk=False)
            words_off = sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal")
            res[name][g["stem"]] = dict(differences=len(d), by=dict(c), words=len(gw), words_off=words_off,
                                        all=d)
            print(f"{name:14} {g['stem']}: {len(d):3} differences {dict(c)}; JATS words off {words_off} of {len(gw)}")
    out = G0 / "gold.json"
    G0.mkdir(parents=True, exist_ok=True)
    prev = jl(out) if out.exists() else {}
    prev.update(res)
    out.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")


def page_sig(d: Path, stem: str) -> dict:
    sig = {}
    for f in sorted((d / "rules").glob(f"{stem}_c*.json")):
        ans = jl(f)["answer"]
        fx = Counter()
        for x in ans.get("fixes") or []:
            fx[str(x.get("line", "")).split(":")[0]] += 1
        for pg in ans.get("pages") or []:
            if not isinstance(pg, dict):
                continue
            bl = [(b.get("type"), tuple(str(i) for i in (b.get("lines") or []))) for b in pg.get("blocks") or []
                  if isinstance(b, dict)]
            sig[pg["page"]] = dict(blocks=bl, fixes=fx.get(str(pg["page"]), 0))
    return sig


def cmd_changed(a: str, b: str, stems: list[str]):
    na, da = a.split("=", 1)
    nb, db = b.split("=", 1)
    rows = []
    for s in stems:
        A, B = page_sig(Path(da), s), page_sig(Path(db), s)
        for p in sorted(set(A) | set(B)):
            x, y = A.get(p) or dict(blocks=[], fixes=0), B.get(p) or dict(blocks=[], fixes=0)
            kinds = sum(1 for u, v in zip(x["blocks"], y["blocks"]) if u != v) + abs(len(x["blocks"]) - len(y["blocks"]))
            if kinds or x["fixes"] != y["fixes"]:
                rows.append(dict(stem=s, page=p, blocks_changed=kinds, n_a=len(x["blocks"]), n_b=len(y["blocks"]),
                                 fixes_a=x["fixes"], fixes_b=y["fixes"]))
    rows.sort(key=lambda r: -(r["blocks_changed"] * 3 + abs(r["fixes_a"] - r["fixes_b"])))
    G0.mkdir(parents=True, exist_ok=True)
    (G0 / f"changed_{na}_{nb}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for r in rows[:40]:
        print(r)
    print(f"{len(rows)} pages differ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["numbers", "gold", "changed"])
    ap.add_argument("arms", nargs="+")
    ap.add_argument("--stems", nargs="*", default=[])
    ap.add_argument("--raw", nargs="*", default=[], help="ARM=PATH raw answers of an arm")
    a = ap.parse_args()
    if a.cmd == "numbers":
        cmd_numbers(a.arms, dict(x.split("=", 1) for x in a.raw), a.stems)
    elif a.cmd == "gold":
        cmd_gold(a.arms)
    else:
        cmd_changed(a.arms[0], a.arms[1], a.stems)


if __name__ == "__main__":
    main()
