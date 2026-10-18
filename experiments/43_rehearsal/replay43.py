"""Experiment 43: replay experiment 41's saved Argon answers (prompt v1, out/argon/raw of experiment 41) through the
v2 code rules and the masters. No model calls.

    replay43.py rules     out/replay/raw/<stem>_cAAA-BBB.json   answers after rules43 (+ the log per chunk)
                          out/replay/rules_log.json            every rule firing, per article, and totals
    replay43.py harness   out/masters_id/   experiment 41's code on experiment 41's answers through this harness:
                          must equal experiment 41's out/masters byte for byte (proves the harness changes nothing)
    replay43.py masters   out/masters/      the v2 rules' masters of all 55
    replay43.py compare   out/replay/compare.json: per article, v2 masters vs experiment 41's (JATS words, ALTO roles,
                          words per role), with the five hand-checked articles in detail
    replay43.py simulate  out/simulated/raw + out/masters_sim/: 0656 with its page-4 top half labelled other_article
                          and 0747 with its verse splits given as v2 "cut"s (what a v2 answer would say), through the
                          same code (labelled "simulated" wherever shown)
"""
from __future__ import annotations

import argparse
import copy
import filecmp
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import masters43 as M43  # noqa: E402
import rules43 as RU  # noqa: E402
from masters43 import ST, M, etree  # noqa: E402

OUT = HERE / "out"
E41OUT = M43.E41 / "out"
RAW41 = E41OUT / "argon" / "raw"
HAND = ["0747-001-003-001", "2382-005-003-001", "0877-007-027-003", "0924-012-005-007", "1140-000-021-003"]


def jdump(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def chunk_lines(a, x, y) -> dict:
    out = {}
    for p in range(x, y + 1):
        for L in ST.page_lines(a, p)[0]:
            out[L["id"]] = dict(text=L["text"], b=L["b"], page=p)
    return out


def apply_rules(a, rec) -> tuple[dict, dict]:
    lines = chunk_lines(a, rec["first"], rec["last"])
    words = M43.azure_words(a)
    ans, log = RU.normalize(rec["answer"], lines, words)
    return ans, log


def cmd_rules(stems):
    dst = OUT / "replay" / "raw"
    dst.mkdir(parents=True, exist_ok=True)
    per = {}
    for a in ST.sample():
        if stems and a["stem"] not in stems:
            continue
        logs = []
        for x, y in ST.chunks(a):
            f = RAW41 / f"{a['stem']}_c{x:03d}-{y:03d}.json"
            if not f.exists():
                continue
            rec = ST.jl(f)
            ans, log = apply_rules(a, rec)
            rec = dict(rec, answer=ans, rules43=log)
            jdump(dst / f.name, rec)
            logs.append(log)
        per[a["stem"]] = dict(summary=RU.merge_logs(logs), never_noise=[e for lg in logs for e in lg["never_noise"]],
                              fixes_spacing=[e for lg in logs for e in lg["fixes_spacing"]],
                              bad_splits=[e for lg in logs for e in lg["bad_splits"]],
                              fixes_orthographic=[e for lg in logs for e in lg["fixes_orthographic"]])
    tot = Counter()
    for v in per.values():
        tot.update(v["summary"])
    jdump(OUT / "replay" / "rules_log.json", dict(totals=dict(tot), articles=per))
    print(json.dumps(dict(tot), indent=1))


def cmd_build(raw_dir: Path, mast: Path, rules: bool, stems):
    rows = []
    for a in ST.sample():
        if stems and a["stem"] not in stems:
            continue
        try:
            r = M43.build43(a, raw_dir, mast, rules)
        except Exception as e:                                    # one article's bug must not stop the rest
            import traceback
            traceback.print_exc()
            r = dict(stem=a["stem"], error=f"{type(e).__name__}: {e}")
        rows.append(r)
        print(f"  {a['stem']:24} {'ERROR ' + r['error'] if r.get('error') else 'ok'}", flush=True)
    jdump(mast / "build.json", rows)


def cmd_harness(stems):
    cmd_build(RAW41, OUT / "masters_id", False, stems)
    same, diff = [], []
    for a in ST.sample():
        if stems and a["stem"] not in stems:
            continue
        ok = all(filecmp.cmp(E41OUT / "masters" / f"{a['stem']}.{k}.xml", OUT / "masters_id" / f"{a['stem']}.{k}.xml",
                             shallow=False) for k in ("jats", "alto"))
        (same if ok else diff).append(a["stem"])
    jdump(OUT / "replay" / "harness.json", dict(same=len(same), differ=diff))
    print(f"harness: {len(same)} identical to experiment 41's masters, differ: {diff}")


# ------------------------------------------------------------------------------------------------ compare

ALTO = "{http://www.loc.gov/standards/alto/ns-v4#}"


TAGS43 = None


def jats_words(p: Path) -> Counter:
    t = etree.parse(str(p)).getroot()
    body = [t.find("body"), t.find("back"), t.find("front")]
    txt = " ".join(" ".join(e.itertext()) for e in body if e is not None)
    return Counter(txt.split())


def alto_roles(p: Path) -> dict:
    t = etree.parse(str(p)).getroot()
    out = Counter()
    words = Counter()
    for b in t.iter(f"{ALTO}TextBlock"):
        role = [x for x in (b.get("TAGREFS") or "").split() if x.startswith("role.")]
        role = role[0][5:] if role else "?"
        out[role] += 1
        words[role] += sum(1 for _ in b.iter(f"{ALTO}String"))
    return dict(blocks=dict(out), words=dict(words))


def string_boxes(p: Path) -> int:
    t = etree.parse(str(p)).getroot()
    return sum(1 for _ in t.iter(f"{ALTO}String"))


def cmd_compare(mast: Path, name: str):
    global TAGS43
    t = next(f for f in (mast / f"{x['stem']}.alto.xml" for x in ST.sample()) if f.exists()).read_bytes()  # any article
    i, j = t.find(b'<StructureTag ID="role.otherArticle"'), t.find(b'<OtherTag ID="kind.formula"')
    TAGS43 = t[i:j]                     # the two role tags v2 adds (and their indentation), ignored when comparing
    rows = {}
    for a in ST.sample():
        s = a["stem"]
        f41, f43 = E41OUT / "masters", mast
        if not (f43 / f"{s}.jats.xml").exists():
            continue
        w41, w43 = jats_words(f41 / f"{s}.jats.xml"), jats_words(f43 / f"{s}.jats.xml")
        r41, r43 = alto_roles(f41 / f"{s}.alto.xml"), alto_roles(f43 / f"{s}.alto.xml")
        same_j = (f41 / f"{s}.jats.xml").read_bytes() == M43.strip_stamp((f43 / f"{s}.jats.xml").read_bytes())
        same_a = (f41 / f"{s}.alto.xml").read_bytes() == (f43 / f"{s}.alto.xml").read_bytes().replace(
            b"experiments/43_rehearsal/masters43.py (on experiments/41_azure_structure/masters.py)",
            b"experiments/41_azure_structure/masters.py").replace(TAGS43, b"")
        rows[s] = dict(jats_identical=same_j, alto_identical=same_a,
                       jats_words_41=sum(w41.values()), jats_words_43=sum(w43.values()),
                       jats_words_gone=dict((w41 - w43).most_common(30)), jats_words_new=dict((w43 - w41).most_common(30)),
                       alto_41=r41, alto_43=r43,
                       stats=json.loads((f43 / "stats" / f"{s}.json").read_text()) if (f43 / "stats" / f"{s}.json").exists() else {})
    tot = dict(articles=len(rows), jats_identical=sum(r["jats_identical"] for r in rows.values()),
               alto_identical=sum(r["alto_identical"] for r in rows.values()),
               jats_words_41=sum(r["jats_words_41"] for r in rows.values()),
               jats_words_43=sum(r["jats_words_43"] for r in rows.values()),
               changed=[s for s, r in rows.items() if not r["jats_identical"]])
    jdump(OUT / "replay" / f"{name}.json", dict(totals=tot, hand_checked={s: rows.get(s) for s in HAND}, articles=rows))
    print(json.dumps(tot, ensure_ascii=False, indent=1))
    for s in HAND:
        r = rows.get(s)
        if r:
            print(s, "jats same" if r["jats_identical"] else f"jats {r['jats_words_41']}->{r['jats_words_43']} gone "
                  f"{r['jats_words_gone']} new {r['jats_words_new']}", "| alto same" if r["alto_identical"] else
                  f"| alto {r['alto_41']['blocks']} -> {r['alto_43']['blocks']}")


# ------------------------------------------------------------------------------------------------ simulate

def cmd_simulate():
    """What a v2 answer would say on two known cases, built from experiment 41's answers by hand-written rules
    (labelled simulated): 0656 p4 lines 1-26 = other_article (two columns, the right one first); 0747's verse
    splits given as word-index cuts."""
    dst = OUT / "simulated" / "raw"
    dst.mkdir(parents=True, exist_ok=True)
    # 0656
    a = ST.art_of("0656-016-001-011")
    rec = ST.jl(RAW41 / "0656-016-001-011_c001-004.json")
    ans = copy.deepcopy(rec["answer"])
    lines = chunk_lines(a, 1, 4)
    top = [f"4:{k}" for k in range(1, 27)]
    ans["noise"] = [x for x in ans["noise"] if x not in top]
    right = sorted([i for i in top if lines[i]["b"][0] >= 480], key=lambda i: lines[i]["b"][1])
    left = sorted([i for i in top if lines[i]["b"][0] < 480], key=lambda i: lines[i]["b"][1])
    p4 = next(pg for pg in ans["pages"] if pg["page"] == 4)
    p4["blocks"][0:0] = [{"type": "other_article", "lines": right, "continued": True},
                         {"type": "other_article", "lines": left, "continued": True}]
    rec2 = dict(rec, answer=ans, simulated="0656 p4 lines 1-26 labelled other_article by hand (what prompt v2 asks)")
    lw = M43.azure_words(a)
    rec2["answer"], rec2["rules43"] = RU.normalize(ans, lines, lw)
    jdump(dst / "0656-016-001-011_c001-004.json", rec2)
    # 0747
    a = ST.art_of("0747-001-003-001")
    rec = ST.jl(RAW41 / "0747-001-003-001_c001-008.json")
    ans = copy.deepcopy(rec["answer"])
    lines = chunk_lines(a, 1, 8)
    cuts = {}
    keep = []
    for s in ans.get("splits") or []:
        lid = str(s.get("line"))
        parts = s.get("parts") or []
        if lid in lines and len(parts) == 2:
            cuts[lid] = len(parts[0].split())
        else:
            keep.append(s)
    ans["splits"] = keep
    for pg in ans["pages"]:
        for b in pg["blocks"]:
            if b.get("type") == "verse":
                ids = [str(i) for h in b.get("hemistichs") or [] for i in h]
                c = {i[:-1]: cuts[i[:-1]] for i in ids if i.endswith("a") and i[:-1] in cuts}
                if c:
                    b["cut"] = c
    # the other splits (non-verse) stay as splits
    vs = {k for pg in ans["pages"] for b in pg["blocks"] if b.get("cut") for k in b["cut"]}
    ans["splits"] += [s for s in rec["answer"].get("splits") or [] if str(s.get("line")) not in vs and s not in keep]
    rec2 = dict(rec, answer=None, simulated="0747 verse splits given as v2 word-index cuts")
    lw = M43.azure_words(a)
    rec2["answer"], rec2["rules43"] = RU.normalize(ans, lines, lw)
    jdump(dst / "0747-001-003-001_c001-008.json", rec2)
    for s in ("0656-016-001-011", "0747-001-003-001"):
        r = M43.build43(ST.art_of(s), dst, OUT / "masters_sim", True)
        print(s, {k: v for k, v in r.items() if k in ("other_article_lines", "ornaments", "ornaments_alto",
                                                       "split_lines_word_boxed", "noise_lines_with_words")})


def assemble_run(run: str, arts: list[dict]):
    """A run of run43.py: rules43 on its raw answers (out/<run>/rules/), then the masters (out/<run>/masters/)."""
    src, dst = OUT / run / "raw", OUT / run / "rules"
    dst.mkdir(parents=True, exist_ok=True)
    for a in arts:
        for x, y in ST.chunks(a):
            f = src / f"{a['stem']}_c{x:03d}-{y:03d}.json"
            if f.exists():
                rec = ST.jl(f)
                ans, log = apply_rules(a, rec)
                jdump(dst / f.name, dict(rec, answer=ans, rules43=log))
        r = M43.build43(a, dst, OUT / run / "masters", True, run=run)
        print(f"  {a['stem']:24} {'ERROR ' + r['error'] if r.get('error') else 'ok'}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["rules", "harness", "masters", "compare", "simulate", "all"])
    ap.add_argument("--stems", nargs="*")
    a = ap.parse_args()
    if a.cmd in ("rules", "all"):
        cmd_rules(a.stems)
    if a.cmd in ("harness", "all"):
        cmd_harness(a.stems)
    if a.cmd in ("masters", "all"):
        cmd_build(OUT / "replay" / "raw", OUT / "masters", True, a.stems)
    if a.cmd in ("compare", "all"):
        cmd_compare(OUT / "masters", "compare")
    if a.cmd in ("simulate", "all"):
        cmd_simulate()


if __name__ == "__main__":
    main()
