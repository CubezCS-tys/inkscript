"""Experiment 43: the correction tool's end-to-end test, part 2 — the export of part 1 (correct_test43.py) imported,
the masters rebuilt, and each correction checked in the masters. No model calls; nothing under out/v33_300*.

    .venv/bin/python correct_check43.py [EXPORT]          (default out/correct/test/corrections_test.json)
In out/correct/test/: judged/ (the judge's patches of the three articles copied from out/v33_300_judged + the
person's, imported by correct43.import_corrections, masters rebuilt), off/ (patches43 --off), plain/ (build43 with no
patch layer), judge_only/; gold/ (gold43 import into a test folder, not the real gold set). Checks:
  * every person patch applied; the judge's patch on the same lines logged "overridden";
  * each correction did what the plan says (ALTO roles and blocks by Azure line, ALTO words, JATS sic / xref / order,
    the picture's box) and NOTHING else changed: every Azure line whose role, block or text differs between the
    patched master and the judge-only master is one the corrections touched;
  * JATS DTD + ALTO XSD valid; patches off = the master with no patch layer (stamps stripped), byte for byte;
  * the corrected article marked "now right" becomes a gold item whose check passes ("same").
Writes check.json and prints a report.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import correct43 as C  # noqa: E402
import masters43 as M43  # noqa: E402
import patches43 as PA  # noqa: E402
import run43  # noqa: E402
from lxml import etree  # noqa: E402

T = HERE / "out" / "correct" / "test"
RUN = "v33_300"
ALTO_NS = "{http://www.loc.gov/standards/alto/ns-v4#}"


def q(el):
    return etree.QName(el).localname


def lines_px(a):
    """Azure line id -> (page, px) as the masters' ALTO has them (Store43 on the run's answers)."""
    D = C.article_data(a, RUN, HERE / "out" / RUN / "masters")
    return {lid: (int(p), L["px"]) for p, P in D["pages"].items() for lid, L in P["lines"].items()}


def state(mast: Path, stem: str, lpx: dict, first: int) -> dict:
    """Per Azure line: ALTO block id, block role, the block's lines, the line's words (CONTENT, ALTERNATIVE); block
    order; illustration boxes; JATS: plain text, xrefs, sic flags."""
    al = C.alto_map(mast / f"{stem}.alto.xml", lpx, first)
    root = etree.parse(str(mast / f"{stem}.alto.xml")).getroot()
    role, order, words, ill = {}, [], {}, {}
    for el in root.iter():
        if q(el) in ("TextBlock", "ComposedBlock", "Illustration") and el.get("ID"):
            role[el.get("ID")] = " ".join(t for t in (el.get("TAGREFS") or "").split() if t.startswith("role."))
            order.append(el.get("ID"))
            if q(el) == "Illustration":
                ill[el.get("ID")] = al[el.get("ID")]["box"]
    for el in root.iter():
        if q(el) != "TextLine":
            continue
        ws = [(s.get("CONTENT"), (s.find(ALTO_NS + "ALTERNATIVE").text if s.find(ALTO_NS + "ALTERNATIVE") is not None
                                  else None)) for s in el if q(s) == "String"]
        words[el.get("ID")] = ws
    per = {}
    for bid, v in al.items():
        if q_of(root, bid) != "TextBlock":
            continue
        for k, lid in enumerate(v["lines"]):
            per[lid] = dict(block=bid, role=role.get(bid), with_=tuple(v["lines"]))
    for tl_id, ws in words.items():           # TextLine ID = <block>l<k>: the k-th line of that block
        bid = tl_id.rsplit("l", 1)[0]
        lids = al.get(bid, {}).get("lines", [])
        k = int(tl_id.rsplit("l", 1)[1]) - 1
        if 0 <= k < len(lids) and lids[k] in per:
            per[lids[k]]["words"] = ws
    J = etree.parse(str(mast / f"{stem}.jats.xml")).getroot()
    text = " ".join(" ".join(J.find("body").itertext()).split()) if J.find("body") is not None else ""
    xrefs = [(x.get("rid"), "".join(x.itertext()).strip()) for x in J.iter("xref") if x.get("ref-type") == "fn"]
    sic = [("".join(x.itertext()), x.get("{http://www.w3.org/1999/xlink}title")) for x in J.iter("named-content")
           if x.get("content-type") == "sic"]
    return dict(lines=per, order=order, ill=ill, text=text, xrefs=xrefs, sic=sic)


_QCACHE = {}


def q_of(root, bid):
    if id(root) not in _QCACHE:
        _QCACHE.clear()
        _QCACHE[id(root)] = {el.get("ID"): q(el) for el in root.iter() if el.get("ID")}
    return _QCACHE[id(root)].get(bid)


def valid(mast: Path, stem: str) -> list[str]:
    from inkscript.enrich.schemas import validate_alto, validate_jats
    return validate_jats(mast / f"{stem}.jats.xml") + validate_alto(mast / f"{stem}.alto.xml")


def main():
    export = Path(sys.argv[1]) if len(sys.argv) > 1 else T / "corrections_test.json"
    plan = json.loads((T / "plan.json").read_text(encoding="utf-8"))
    d = C.read_export(export)
    stems = sorted(d["articles"])
    arts = {a["stem"]: a for a in run43.articles("b")}
    M43.ST.PAGES = HERE / "out" / "pages"
    for sub in ("judged", "judge_only", "off", "plain", "gold"):
        shutil.rmtree(T / sub, ignore_errors=True)
    judge_src = HERE / "out" / f"{RUN}_judged" / "patches"
    for sub in ("judged", "judge_only"):
        (T / sub / "patches").mkdir(parents=True)
        for s in stems:
            if (judge_src / f"{s}.json").exists():
                shutil.copyfile(judge_src / f"{s}.json", T / sub / "patches" / f"{s}.json")
    print("== import (correct43.import_corrections)")
    C.import_corrections(export, RUN, T / "judged")
    print("== judge only / off / plain")
    PA.build(RUN, T / "judge_only", stems)
    PA.build(RUN, T / "off", stems, off=True)
    for s in stems:
        M43.build43(arts[s], HERE / "out" / RUN / "rules", T / "plain" / "masters", True, run=RUN)
    rep = dict(export=str(export.relative_to(HERE)), articles={}, ok=True)
    for s in stems:
        a = arts[s]
        log = json.loads((T / "judged" / "masters" / f"{s}.patches.json").read_text(encoding="utf-8"))
        mine = [p["id"] for p in d["articles"][s]["patches"]]
        applied = {e["id"] for e in log["applied"]}
        r = dict(person=len(mine), person_applied=sum(i in applied for i in mine),
                 judge_applied=sorted(i for i in applied if i.startswith("j-")),
                 overridden=[f"{e['id']}: {e['why']}" for e in log["skipped"] if "overridden" in (e.get("why") or "")] +
                 [f"{e['id']}: {e['note']}" for e in log["applied"] if e.get("note")],
                 skipped_other=[f"{e['id']}: {e.get('why')}" for e in log["skipped"]
                                if "overridden" not in (e.get("why") or "") and e["id"] not in mine])
        lpx = lines_px(a)
        on = state(T / "judged" / "masters", s, lpx, a.get("first", 1))
        base = state(T / "judge_only" / "masters", s, lpx, a.get("first", 1))   # "nothing else": the judge's own
        orig = state(T / "off" / "masters", s, lpx, a.get("first", 1))          # "what it was": no patch at all
        checks, touched = [], set()
        for it in (x for x in plan if x["stem"] == s):
            w = it["what"]
            if w == "noise":
                ok = all(on["lines"].get(x, {}).get("role") in (None, "role.noise", "role.showThrough") for x in it["lines"])
                was = sorted({orig["lines"].get(x, {}).get("role") for x in it["lines"]} - {None})
                checks.append((f"{len(it['lines'])} lines -> noise (were {was})", ok))
                touched |= set(it["lines"])
            elif w in ("misread", "misprint"):
                ws = on["lines"].get(it["line"], {}).get("words") or []
                if w == "misread":
                    ok = (it["to"], it["frm"]) in ws and it["to"] in on["text"]
                    checks.append((f"{it['line']}: ALTO word {it['frm']} -> {it['to']} (ALTERNATIVE keeps Azure's)", ok))
                else:
                    ok = (it["frm"], it["to"]) in on["sic"] and any(c == it["frm"] for c, _ in ws)
                    checks.append((f"{it['line']}: misprint {it['frm']} stays printed, JATS sic corr {it['to']}", ok))
                touched.add(it["line"])
            elif w == "relink":
                diff = [(x, y) for x, y in zip(orig["xrefs"], on["xrefs"]) if x != y]
                ok = len(orig["xrefs"]) == len(on["xrefs"]) and len(diff) == 1 and diff[0][0][1] == diff[0][1][1]
                checks.append((f"call {it['marker']} on {it['line']}: note {it['fn']} -> {it['to']}: one xref's rid "
                               f"changed {diff[:1]}", ok))
                touched.add(it["line"])
            elif w == "split":
                b0, b1 = on["lines"][it["before"][0]]["block"], on["lines"][it["after"][0]]["block"]
                ok = b0 != b1 and on["lines"][it["after"][-1]]["block"] == b1 and \
                    orig["lines"][it["before"][0]]["block"] == orig["lines"][it["after"][0]]["block"]
                checks.append((f"split: {it['before']} | {it['after']} in two ALTO blocks (one before)", ok))
                touched |= set(it["before"] + it["after"])
            elif w == "merge":
                ok = on["lines"][it["a"][0]]["block"] == on["lines"][it["b"][-1]]["block"] and \
                    orig["lines"][it["a"][0]]["block"] != orig["lines"][it["b"][0]]["block"]
                checks.append((f"merge p{it['page']}: {it['a'][0]}… + {it['b'][0]}… in one ALTO block", ok))
                touched |= set(it["a"] + it["b"])
            elif w == "move_up":
                pos = lambda st, x: st["order"].index(st["lines"][x]["block"])       # noqa: E731
                ok = pos(on, it["block"][0]) < pos(on, it["over"][0]) and pos(orig, it["block"][0]) > pos(orig, it["over"][0])
                checks.append((f"reading order p{it['page']}: {it['block'][0]} now before {it['over'][0]}", ok))
                touched |= set(it["block"] + it["over"])
            elif w == "kind":
                r0 = {orig["lines"][x]["role"] for x in it["lines"]}
                r1 = {on["lines"][x]["role"] for x in it["lines"]}
                ok = r0 != r1 and r1 == {"role.body"}
                checks.append((f"kind {it['lines']}: {sorted(r0)} -> {sorted(r1)}", ok))
                touched |= set(it["lines"])
            elif w == "box":
                P = C.article_data(a, RUN, HERE / "out" / RUN / "masters")["pages"][str(it["page"])]
                want = [it["box"][0] * P["W"] / 1000, it["box"][1] * P["H"] / 1000, it["box"][2] * P["W"] / 1000,
                        it["box"][3] * P["H"] / 1000]
                moved = [k for k in on["ill"] if on["ill"][k] != orig["ill"].get(k)]
                got = on["ill"][moved[0]] if moved else None
                ok = len(moved) == 1 and all(abs(x - y) <= 0.012 * P["W"] for x, y in zip(got, want))
                checks.append((f"picture box p{it['page']} {moved}: {[round(x) for x in got or []]} ~ {[round(x) for x in want]} "
                               f"(crop margin 4/1000)", ok))
        changed = sorted(x for x in set(on["lines"]) | set(base["lines"])
                         if (on["lines"].get(x, {}).get("role"), on["lines"].get(x, {}).get("with_"),
                             on["lines"].get(x, {}).get("words")) !=
                         (base["lines"].get(x, {}).get("role"), base["lines"].get(x, {}).get("with_"),
                          base["lines"].get(x, {}).get("words")))
        # a line that only shares a block with a touched line (split / merge / noise taken out of its block)
        near = {x for x in changed for y in (on["lines"].get(x, {}).get("with_") or ()) + (base["lines"].get(x, {}).get("with_") or ())
                if y in touched}
        extra = sorted(set(changed) - touched - near)
        checks.append((f"nothing else changed: {len(changed)} line(s) differ from the judge-only master, "
                       f"outside the corrections: {extra}", not extra))
        inv = valid(T / "judged" / "masters", s)
        checks.append((f"JATS DTD + ALTO XSD valid ({len(inv)} errors)", not inv))
        same = all(M43.strip_stamp((T / "off" / "masters" / f"{s}.{e}").read_bytes()) ==
                   M43.strip_stamp((T / "plain" / "masters" / f"{s}.{e}").read_bytes()) for e in ("jats.xml", "alto.xml"))
        checks.append(("patches off = the master without the patch layer (JATS + ALTO, stamps stripped)", same))
        checks.append((f"every person patch applied ({r['person_applied']}/{r['person']})", r["person_applied"] == r["person"]))
        r["checks"] = [dict(what=c, ok=bool(ok)) for c, ok in checks]
        r["invalid"] = inv[:5]
        rep["articles"][s] = r
        rep["ok"] &= all(ok for _, ok in checks)
        print(f"\n{s}: person {r['person_applied']}/{r['person']} applied; judge applied {r['judge_applied']}; "
              f"overridden {r['overridden']}")
        for c, ok in checks:
            print(f"   {'PASS' if ok else 'FAIL'}  {c}")
    print("\n== gold (gold43 import into a test folder)")
    import gold43 as G
    G.GOLD = T / "gold"
    G.ISSUES, G.ISSUES_MD = T / "gold" / "issues.json", T / "gold" / "issues.md"
    G.cmd_import([str(export)])
    gold_ok = G.cmd_check() == 0 if list((T / "gold").glob("*__*.json")) else False
    rep["gold"] = dict(items=[f.name for f in (T / "gold").glob("*__*.json")], check_same=gold_ok)
    rep["ok"] &= gold_ok
    (T / "check.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nALL {'PASS' if rep['ok'] else 'FAIL'} -> {T / 'check.json'}")
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
