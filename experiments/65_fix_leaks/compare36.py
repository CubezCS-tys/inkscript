"""Experiment 65: prompt v3.6's answers on the check pages against the saved answers of the same pages (v3.5b for the
0130 pages, v3.3 for the three others). No calls. -> out/<run>_compare.json + .md (run: v36_check2 (default) or v36_check)

Structure: per page, the blocks (type and lines) of each answer; lines placed in blocks; the same lines in blocks of
the same type. New keys: authors' position, DOI, licence, section, printings, ORCID, corresponding mark.
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E43 = HERE.parent / "43_rehearsal" / "out"
SAVED = {"0130": "j0130", "1152": "v33_300", "0201": "v33_300", "2461": "v33_300b_fix3", "1080": "v33_300b_fix3",
         "1010": "v33_300"}


def page_blocks(ans: dict, p: int) -> list[dict]:
    for pg in ans.get("pages") or []:
        if isinstance(pg, dict) and int(pg.get("page") or 0) == p:
            return [b for b in pg.get("blocks") or [] if isinstance(b, dict)]
    return []


def lines_of(b) -> list[str]:
    out = []
    for k in ("lines",):
        out += [str(x) for x in b.get(k) or [] if isinstance(x, (str, int))]
    for h in b.get("hemistichs") or []:
        out += [str(x) for x in h or []]
    for r in b.get("rows") or []:
        for c in r if isinstance(r, list) else []:
            if isinstance(c, dict):
                out += [str(x) for x in c.get("lines") or []]
    return out


def typemap(blocks) -> dict:
    return {lid: str(b.get("type")) for b in blocks for lid in lines_of(b)}


def main():
    rows, md = [], ["| page | blocks v3.6 / saved | lines placed v3.6 / saved | same type | new keys (v3.6) | saved had |",
                    "|---|---|---|---|---|---|"]
    run = sys.argv[1] if len(sys.argv) > 1 else "v36_check2"
    for f in sorted(glob.glob(str(E43 / run / "raw" / "*.json"))):
        j = json.loads(Path(f).read_text(encoding="utf-8"))
        stem, x, y = j["stem"], j["first"], j["last"]
        new = j["answer"]
        saved_run = SAVED[stem[:4]]
        old_f = None
        for g in sorted(glob.glob(str(E43 / saved_run / "raw" / f"{stem}_c*.json"))):
            if g.endswith(".failed.json"):
                continue
            a, b = (int(t) for t in Path(g).stem.split("_c")[1].split("-"))
            if a <= x and y <= b:
                old_f = g
        old = json.loads(Path(old_f).read_text(encoding="utf-8"))["answer"] if old_f else {}
        oldp = json.loads(Path(old_f).read_text(encoding="utf-8")).get("prompt") if old_f else None
        for p in range(x, y + 1):
            bn, bo = page_blocks(new, p), page_blocks(old, p)
            tn, to = typemap(bn), typemap(bo)
            same = sum(1 for k in tn if to.get(k) == tn[k])
            r = dict(stem=stem, page=p, saved=f"{saved_run} ({oldp})", blocks_new=len(bn), blocks_old=len(bo),
                     lines_new=len(tn), lines_old=len(to), same_type=same,
                     types_new=dict(Counter(tn.values())), types_old=dict(Counter(to.values())))
            rows.append(r)
        mn, mo = new.get("metadata") or {}, old.get("metadata") or {}
        En, Eo = new.get("enrich") or {}, old.get("enrich") or {}
        keys = []
        for au in mn.get("authors") or []:
            if au.get("position"):
                keys.append(f"position «{au['position']}»")
        for k in ("doi", "license", "section"):
            if En.get(k):
                keys.append(f"{k} {json.dumps(En[k], ensure_ascii=False)}")
        for pr in En.get("printings") or []:
            keys.append("printing a{} «{}»{}{}{}".format(pr.get("a"), pr.get("name"),
                        " orcid " + pr["orcid"] if pr.get("orcid") else "", " email" if pr.get("email") else "",
                        " corresp" if pr.get("corresp") else ""))
        for au in En.get("authors") or []:
            if au.get("orcid") or au.get("corresp"):
                keys.append(f"authors a{au.get('a')}{' orcid ' + au['orcid'] if au.get('orcid') else ''}"
                            f"{' corresp' if au.get('corresp') else ''}")
        had = []
        for au in mo.get("authors") or []:
            if au.get("role"):
                had.append(f"role «{au['role']}»")
        for au in Eo.get("authors") or []:
            if au.get("orcid") or au.get("corresp"):
                had.append(f"authors a{au.get('a')}{' orcid' if au.get('orcid') else ''}"
                           f"{' corresp' if au.get('corresp') else ''}")
        if not mo and x > 1:
            had.append("(page inside a later chunk: no metadata)")
        tr = [r for r in rows if r["stem"] == stem]
        md.append(f"| {stem} p{x}-{y} | {sum(r['blocks_new'] for r in tr)} / {sum(r['blocks_old'] for r in tr)} | "
                  f"{sum(r['lines_new'] for r in tr)} / {sum(r['lines_old'] for r in tr)} | "
                  f"{sum(r['same_type'] for r in tr)} | {'; '.join(keys) or '-'} | {'; '.join(had) or '-'} |")
        rows[-1]["keys_new"], rows[-1]["keys_saved"] = keys, had
    (HERE / "out" / f"{run}_compare.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "out" / f"{run}_compare.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
