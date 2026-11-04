"""Experiment 60, test 2: Claude's and Argon's v3.5b answers on the same gate-1 articles, field by field (no calls).

Both readers answer in Azure's line ids, so a reference block is the same block in both answers when it starts on
the same line: its parsed works are compared key by key. Article-level fields come from the answers after rules43
(doc type, authors and roles, corresponding author, affiliation parts) and from the masters (note calls linked,
tables, cells).

    t2compare60.py   -> out/t2/compare.json, out/t2/disagreements.jsonl
"""
from __future__ import annotations

import glob
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from common60 import OUT, jdump, jl

T2 = OUT / "t2"
CL = T2 / "build"
AR = T2 / "argon_build"
REF_KEYS = ["type", "authors", "editors", "translators", "died", "title", "source", "edition", "place", "publisher",
            "year", "year2", "cal", "volume", "issue", "pages", "cited", "accessed", "url", "series"]


def answers(build: Path, stem: str) -> list[dict]:
    return [jl(f)["answer"] for f in sorted(glob.glob(str(build / "rules" / f"{glob.escape(stem)}_c*.json")))]


def refs(ans: list[dict]) -> dict:
    out = {}
    for a in ans:
        for pg in a.get("pages") or []:
            for b in pg.get("blocks") or []:
                if not isinstance(b, dict) or not b.get("parsed"):
                    continue
                key0 = (b.get("type"), (b.get("lines") or ["?"])[0])
                for k, w in enumerate(b["parsed"]):
                    if isinstance(w, dict):
                        out[f"{key0[0]} {key0[1]} #{k + 1}"] = w
    return out


def norm(v):
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, dict):
        return {k: norm(x) for k, x in sorted(v.items()) if x not in (None, "", [])}
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else None


def art_fields(ans: list[dict]) -> dict:
    m = (ans[0].get("metadata") or {}) if ans else {}
    e = (ans[0].get("enrich") or {}) if ans else {}
    auth = [dict(name=a.get("name"), role=a.get("role")) for a in m.get("authors") or [] if isinstance(a, dict)]
    ea = {str(x.get("a")): x for x in e.get("authors") or [] if isinstance(x, dict)}
    return dict(doc_type=e.get("doc_type"), authors=auth,
                corresp=sorted(k for k, x in ea.items() if x.get("corresp")),
                affs={k: norm(x.get("affs")) for k, x in ea.items()},
                same_as={k: x.get("same_as") for k, x in ea.items() if x.get("same_as")},
                note_kinds=norm({k: v for a in ans for k, v in (((a.get("enrich") or {}).get("note_kinds") or {}).items()
                                                            if isinstance((a.get("enrich") or {}).get("note_kinds"), dict) else [])}),
                table_notes=sum(len((a.get("enrich") or {}).get("table_notes") or []) if isinstance((a.get("enrich") or {}).get("table_notes"), list) else 0 for a in ans),
                figure_kinds=sum(len(v) if isinstance(v, list) else 1 for a in ans
                                 for v in (((a.get("enrich") or {}).get("figures") or {}).values()
                                           if isinstance((a.get("enrich") or {}).get("figures"), dict) else [])),
                fixes=sum(len(a.get("fixes") or []) for a in ans), sic=sum(len(a.get("sic") or []) for a in ans),
                missed=sum(len(a.get("missed") or []) for a in ans),
                noise=sum(len(a.get("noise") or []) for a in ans))


def master_counts(build: Path, stem: str) -> dict:
    f = build / "masters" / f"{stem}.jats.xml"
    if not f.exists():
        return {}
    r = ET.parse(f).getroot()
    return dict(fn=len(r.findall(".//fn")), xref_fn=len([x for x in r.iter("xref") if x.get("ref-type") == "fn"]),
                refs=len(r.findall(".//ref")), element_citations=len(list(r.iter("element-citation"))),
                tables=len(list(r.iter("table-wrap"))), cells=len(list(r.iter("td"))) + len(list(r.iter("th"))),
                figs=len(list(r.iter("fig"))), article_type=r.get("article-type"))


def main():
    stems = list(jl(OUT / "plan_t2.json"))
    rows, dis = [], []
    tot = Counter()
    for s in stems:
        A, C = answers(AR, s), answers(CL, s)
        if not C:
            continue
        fa, fc = art_fields(A), art_fields(C)
        ma, mc = master_counts(AR, s), master_counts(CL, s)
        ra, rc = refs(A), refs(C)
        for k in ("doc_type", "authors", "corresp", "affs", "same_as", "note_kinds"):
            if norm(fa[k]) != norm(fc[k]):
                dis.append(dict(stem=s, level="article", field=k, argon=fa[k], claude=fc[k]))
        both = sorted(set(ra) & set(rc))
        for key in sorted(set(ra) | set(rc)):
            if key not in both:
                dis.append(dict(stem=s, level="ref", where=key, field="(work only in one)",
                                argon=ra.get(key), claude=rc.get(key)))
                tot["ref_only_argon" if key in ra else "ref_only_claude"] += 1
                continue
            wa, wc = ra[key], rc[key]
            tot["refs_both"] += 1
            same = True
            for f in sorted(set(wa) | set(wc)):
                if norm(wa.get(f)) != norm(wc.get(f)):
                    same = False
                    tot[f"ref_field_differs:{f}"] += 1
                    dis.append(dict(stem=s, level="ref", where=key, field=f, argon=wa.get(f), claude=wc.get(f)))
                for who, w in (("argon", wa), ("claude", wc)):
                    if w.get(f) not in (None, "", []):
                        tot[f"has:{who}:{f}"] += 1
            tot["refs_identical"] += same
        rows.append(dict(stem=s, argon=fa, claude=fc, argon_master=ma, claude_master=mc,
                         refs_argon=len(ra), refs_claude=len(rc), refs_both=len(both)))
    jdump(T2 / "compare.json", dict(totals=dict(sorted(tot.items())), articles=rows))
    with open(T2 / "disagreements.jsonl", "w") as f:
        for d in dis:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(json.dumps(dict(sorted(tot.items())), ensure_ascii=False, indent=0))
    print(len(dis), "disagreements;", Counter(d["field"] for d in dis).most_common(25))


if __name__ == "__main__":
    main()
