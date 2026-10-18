"""Experiment 43: the gold set (hand-checked output that every change must keep) and the issues log. No model calls.

    gold43.py import FILE...        the owner's marks: an experiment 41 hand-check export (handcheck_<stem>_argon.json)
                                    or a review43 export (review_<run>.json). "yes" joins the gold set (the article
                                    or the spot's lines, snapshotted as today's code makes them); "no" becomes an open
                                    issue with its note (issues.json, issues.md)
    gold43.py add STEM... --run R --source TEXT   whole articles judged right by eye
    gold43.py check [--stems ...]   today's rules + masters on each gold article's saved answers, diffed against the
                                    snapshot: text, block kinds, order, lines, links. Plain report; exit 1 on any change
    gold43.py accept STEM --run R --why TEXT      a change on purpose: take today's output as the new snapshot
    gold43.py stale                 masters made with an older prompt or older code (from their version stamps)
    gold43.py issue ID --status S [--pattern NAME] [--rule TEXT]   S: open, code rule, prompt change, won't fix
    gold43.py issues                rewrite issues.md from issues.json

gold/<stem>__<run>.json: the run's answers (raw folder), what was checked (scope: "article" or line ids; source,
date, note), the version stamp and the snapshot. A gold run is a flags43 run name: "replay" = experiment 41's Argon
answers (which the owner checked in experiment 41) through today's rules.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import flags43 as F  # noqa: E402
import masters43 as M43  # noqa: E402
import rules43 as RU  # noqa: E402
from masters43 import ST, etree  # noqa: E402

GOLD = HERE / "gold"
ISSUES = HERE / "issues.json"
ISSUES_MD = HERE / "issues.md"
REPO = HERE.parent.parent
STATUSES = ["open", "code rule", "prompt change", "won't fix"]
RUN_OF_41 = {"argon": "replay"}            # experiment 41's hand-check run names -> flags43 runs


def jload(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def jdump(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def plain(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html or "").replace("&quot;", '"').replace("&amp;", "&")
                    .replace("&lt;", "<").replace("&gt;", ">").split())


# ------------------------------------------------------------------------------------------------ snapshot

def snapshot(a: dict, raw: Path) -> dict:
    """Today's rules and masters on the saved answers: blocks (page, kind, level, lines, text, links) and the JATS
    (text, links, notes), in a temporary folder."""
    F.use_pages_of(a)
    with tempfile.TemporaryDirectory() as td:
        rules, mast = Path(td) / "rules", Path(td) / "masters"
        rules.mkdir()
        for x, y in ST.chunks(a):
            f = raw / f"{a['stem']}_c{x:03d}-{y:03d}.json"
            if not f.exists():
                raise FileNotFoundError(f"{f} (gold needs every chunk answered)")
            rec = ST.jl(f)
            lines = {}
            for p in range(x, y + 1):
                for L in ST.page_lines(a, p)[0]:
                    lines[L["id"]] = dict(text=L["text"], b=L["b"], page=p)
            ans, _ = RU.normalize(rec["answer"], lines, M43.azure_words(a))
            (rules / f.name).write_text(json.dumps(dict(rec, answer=ans), ensure_ascii=False), encoding="utf-8")
        cap = M43.capture43(a, rules)
        blocks = []
        for b in cap["blocks"]:
            d = dict(n=b["n"], page=b["page"], type=b["type"], level=b.get("level"), ids=list(b["ids"]),
                     text=plain(b.get("html")), calls=[c.get("fn") for c in b.get("calls") or []])
            if b.get("fn_id"):
                d["fn_id"] = b["fn_id"]
            blocks.append(d)
        M43.build43(a, rules, mast, True, run="gold-check")
        root = etree.parse(str(mast / f"{a['stem']}.jats.xml")).getroot()
        for c in root.iter("custom-meta"):
            if (c.get("id") or "").startswith("stamp-"):
                c.getparent().remove(c)
        parts = [root.find(k) for k in ("front", "body", "back")]
        text = " ".join(" ".join(" ".join(e.itertext()).split()) for e in parts if e is not None)
        links = [f"{x.get('rid')}:{''.join(x.itertext()).strip()}" for x in root.iter("xref") if x.get("ref-type") == "fn"]
        fns = [x.get("id") for x in root.iter("fn")]
    return dict(blocks=blocks, jats=dict(text=text, links=links, fns=fns))


def scoped(blocks: list[dict], scope) -> list[dict]:
    if scope == "article":
        return blocks
    want = set(scope)
    return [b for b in blocks if want & set(b["ids"]) or want & {re.sub(r"[a-p]$", "", i) for i in b["ids"]}]


def word_diff(a: str, b: str, n=3) -> list[str]:
    wa, wb = a.split(), b.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=wa, b=wb, autojunk=False).get_opcodes():
        if op != "equal":
            out.append(f"{op}: «{' '.join(wa[i1:i2])[:80]}» → «{' '.join(wb[j1:j2])[:80]}»")
            if len(out) >= n:
                break
    return out


def diff(gold: dict, now: dict, scope) -> list[str]:
    """Plain-words differences, gold -> now, inside the checked scope."""
    out = []
    g, c = scoped(gold["blocks"], scope), scoped(now["blocks"], scope)
    key = lambda b: (b["page"], b["ids"][0] if b["ids"] else f"n{b['n']}")  # noqa: E731
    gi, ci = {key(b): b for b in g}, {key(b): b for b in c}
    for k, b in gi.items():
        x = ci.get(k)
        where = f"p{b['page']} block at {k[1]} ({b['type']})"
        if x is None:
            out.append(f"{where}: gone (its lines are now in another block or none)")
            continue
        if (b["type"], b.get("level")) != (x["type"], x.get("level")):
            out.append(f"{where}: kind {b['type']}{b.get('level') or ''} → {x['type']}{x.get('level') or ''}")
        if b["ids"] != x["ids"]:
            out.append(f"{where}: lines {' '.join(b['ids'][:6])}… → {' '.join(x['ids'][:6])}…")
        if b["text"] != x["text"]:
            out.append(f"{where}: text " + "; ".join(word_diff(b["text"], x["text"])))
        if b["calls"] != x["calls"] or b.get("fn_id") != x.get("fn_id"):
            out.append(f"{where}: links {b['calls']} {b.get('fn_id') or ''} → {x['calls']} {x.get('fn_id') or ''}")
    for k, x in ci.items():
        if k not in gi:
            out.append(f"p{x['page']} new block at {k[1]} ({x['type']}): «{x['text'][:60]}»")
    order_g = [key(b) for b in g if key(b) in ci]
    order_c = [key(b) for b in c if key(b) in gi]
    if order_g != order_c:
        sm = difflib.SequenceMatcher(a=order_g, b=order_c, autojunk=False)
        moved = [order_g[i1:i2] for op, i1, i2, _, _ in sm.get_opcodes() if op != "equal" and i2 > i1]
        out.append(f"reading order changed: {sum(len(m) for m in moved)} block(s) moved, first at "
                   f"p{moved[0][0][0]} {moved[0][0][1]}" if moved and moved[0] else "reading order changed")
    if scope == "article":
        gj, cj = gold["jats"], now["jats"]
        if gj["text"] != cj["text"]:
            out.append("JATS text: " + "; ".join(word_diff(gj["text"], cj["text"])))
        if gj["links"] != cj["links"]:
            out.append(f"JATS links: {len(gj['links'])} → {len(cj['links'])} "
                       + "; ".join(word_diff(" ".join(gj["links"]), " ".join(cj["links"]), 2)))
        if gj["fns"] != cj["fns"]:
            out.append(f"JATS notes: {len(gj['fns'])} → {len(cj['fns'])}")
    return out


# ------------------------------------------------------------------------------------------------ gold items

def gold_file(stem: str, run: str) -> Path:
    return GOLD / f"{stem}__{run}.json"


def merge_scope(old, new):
    if old == "article" or new == "article":
        return "article"
    return sorted(set(old or []) | set(new or []), key=lambda i: [int(v) if v.isdigit() else v
                                                               for v in re.split(r"[:a-p]", i) if v])


def add_gold(stem: str, run: str, scope, source: str, note: str = "", marks: dict | None = None) -> Path:
    a = F.all_articles()[stem]
    raw = F.run_dirs(run)["raw"]
    f = gold_file(stem, run)
    g = jload(f)
    if g is None:
        g = dict(stem=stem, run=run, raw=str(Path(raw).resolve().relative_to(REPO)), scope=None, checked=[],
                 stamp=M43.stamp_of(a, raw, run), snapshot=snapshot(a, raw), accepted=[])
    g["checked"].append(dict(date=time.strftime("%Y-%m-%d"), source=source, scope=scope, note=note,
                             **({"marks": marks} if marks else {})))
    g["scope"] = merge_scope(g["scope"], scope)
    jdump(f, g)
    return f


def new_issue(stem, run, page, lines, kind, note, source) -> dict:
    iss = jload(ISSUES, [])
    k = 1 + max([int(i["id"][1:]) for i in iss] or [0])
    it = dict(id=f"i{k}", date=time.strftime("%Y-%m-%d"), stem=stem, run=run, page=page, lines=lines, kind=kind,
              note=note, pattern=kind, status="open", rule="", source=source)
    iss.append(it)
    jdump(ISSUES, iss)
    return it


def cmd_import(files: list[str]):
    for fn in files:
        d = json.loads(Path(fn).read_text(encoding="utf-8"))
        src = Path(fn).name
        if "blocks" in d:                                  # experiment 41's hand-check export
            run = RUN_OF_41.get(d.get("run"), d.get("run"))
            stem = d["stem"]
            a = F.all_articles()[stem]
            F.use_pages_of(a)
            cap41 = M43.capture43(a, F.run_dirs(run)["raw"], rules=False)     # the numbering the owner saw
            ids_of = {str(b["n"]): list(b["ids"]) for b in cap41["blocks"]}
            yes = [b for b in d["blocks"] if b.get("ok") == "yes"]
            no = [b for b in d["blocks"] if b.get("ok") == "no"]
            marks = dict(yes=len(yes), no=len(no), blocks=len(d["blocks"]), exported=d.get("exported"))
            if yes:
                scope = "article" if len(yes) == len(d["blocks"]) else \
                    [i for b in yes for i in ids_of.get(str(b["block"]), [])]
                f = add_gold(stem, run, scope, f"owner's hand check, block by block ({src})",
                             f"{len(yes)}/{len(d['blocks'])} blocks marked right", marks)
                print(f"{stem}: {len(yes)} yes -> {f.name} (scope {'article' if scope == 'article' else len(scope)})")
            for b in no:
                it = new_issue(stem, run, b.get("page"), ids_of.get(str(b["block"]), []), b.get("type"),
                               b.get("note") or "", src)
                print(f"{stem}: no -> issue {it['id']}")
        elif "spots" in d:                                 # a review43 export
            run = d["run"]
            yes, no = {}, []
            for s in d["spots"]:
                if s.get("ok") == "yes":
                    yes.setdefault(s["stem"], []).append(s)
                elif s.get("ok") == "no":
                    no.append(s)
            for stem, ss in yes.items():
                f = add_gold(stem, run, [i for s in ss for i in s["lines"]], f"owner's review of flagged spots ({src})",
                             "; ".join(f"{s['kind']} p{s['page']}" + (f": {s['note']}" if s.get("note") else "")
                                       for s in ss)[:500], dict(yes=len(ss), spots=[s["id"] for s in ss]))
                print(f"{stem}: {len(ss)} spot(s) right -> {f.name}")
            for s in no:
                it = new_issue(s["stem"], run, s["page"], s["lines"], s["kind"], s.get("note") or "", src)
                print(f"{s['stem']}: {s['kind']} p{s['page']} wrong -> issue {it['id']}")
        else:
            print(f"{fn}: not a hand-check or review export")
    write_issues_md()


def cmd_check(stems=None) -> int:
    files = sorted(GOLD.glob("*.json"))
    arts = F.all_articles()
    changed = 0
    print(f"gold check: {len(files)} item(s); today's code {M43.versions()['rules_hash']}")
    for f in files:
        g = jload(f)
        if stems and g["stem"] not in stems:
            continue
        try:
            now = snapshot(arts[g["stem"]], REPO / g["raw"])
        except Exception as e:
            print(f"  {g['stem']} ({g['run']}): ERROR {type(e).__name__}: {e}")
            changed += 1
            continue
        d = diff(g["snapshot"], now, g["scope"])
        sc = "whole article" if g["scope"] == "article" else f"{len(g['scope'])} checked lines"
        if d:
            changed += 1
            print(f"  {g['stem']} ({g['run']}, {sc}): CHANGED, {len(d)} difference(s)")
            for x in d[:15]:
                print(f"      {x}")
            if len(d) > 15:
                print(f"      … {len(d) - 15} more")
        else:
            print(f"  {g['stem']} ({g['run']}, {sc}): same")
    print("gold check: " + ("all the same" if not changed else f"{changed} item(s) changed") + "")
    return 1 if changed else 0


def cmd_accept(stem, run, why):
    f = gold_file(stem, run)
    g = jload(f)
    a = F.all_articles()[stem]
    g["snapshot"] = snapshot(a, REPO / g["raw"])
    g["stamp"] = M43.stamp_of(a, REPO / g["raw"], run)
    g.setdefault("accepted", []).append(dict(date=time.strftime("%Y-%m-%d"), why=why,
                                             rules_hash=g["stamp"]["rules_hash"]))
    jdump(f, g)
    print(f"{f.name}: today's output is the new snapshot ({why})")


def cmd_stale():
    """Every masters folder under out/: which articles were made with another prompt text or other code."""
    cur = M43.versions()
    rows = []
    for st in sorted(F.OUT.glob("**/masters/*.stamp.json")) + sorted((F.OUT / "masters").glob("*.stamp.json")):
        s = jload(st)
        pv = M43.versions(s.get("prompt", "v2").split("+")[-1])
        why = []
        if s.get("rules_hash") != cur["rules_hash"]:
            why.append(f"code {s.get('rules_hash')} (now {cur['rules_hash']})")
        if pv.get("prompt_hash") and s.get("prompt_hash") != pv["prompt_hash"]:
            why.append(f"prompt {s.get('prompt')} text {s.get('prompt_hash')} (now {pv['prompt_hash']})")
        rows.append((st.parent.relative_to(F.OUT), st.name.replace(".stamp.json", ""), s.get("made"), why))
    unstamped = [j for j in sorted(F.OUT.glob("**/masters/*.jats.xml")) if not j.with_name(
        j.name.replace(".jats.xml", ".stamp.json")).exists()]
    seen = set()
    n = 0
    for folder, stem, made, why in rows:
        if (folder, stem) in seen:
            continue
        seen.add((folder, stem))
        if why:
            n += 1
            print(f"  stale  {folder}/{stem}  made {made}: {'; '.join(why)}")
    for j in unstamped:
        print(f"  no stamp  {j.parent.relative_to(F.OUT)}/{j.name.replace('.jats.xml', '')} (made before stamps)")
    print(f"stale: {n} of {len(seen)} stamped masters; {len(unstamped)} without a stamp; today's code "
          f"{cur['rules_hash']}, prompt {cur['prompt']} {cur['prompt_hash']}")


def cmd_issue(iid, status, pattern, rule):
    iss = jload(ISSUES, [])
    it = next(i for i in iss if i["id"] == iid)
    if status:
        assert status in STATUSES, f"status: one of {STATUSES}"
        it["status"] = status
    if pattern:
        it["pattern"] = pattern
    if rule:
        it["rule"] = rule
    jdump(ISSUES, iss)
    write_issues_md()
    print(it)


def write_issues_md():
    iss = jload(ISSUES, [])
    L = ["# Experiment 43 — issues from the owner's marks", "",
         "Written by `gold43.py` from `issues.json` (edit with `gold43.py issue ID --status ... --pattern ...`). Each "
         "\"no\" from a hand check or a review page, with its note, the pattern it belongs to, and what became of it: "
         "open / code rule (rules43, replayed free on saved answers) / prompt change (needs calls) / won't fix.", ""]
    for st in STATUSES:
        rows = [i for i in iss if i["status"] == st]
        L.append(f"## {st} ({len(rows)})")
        L.append("")
        if not rows:
            L.append("(none)")
        else:
            L.append("| id | date | article | run | page | lines | pattern | note | rule / change |")
            L.append("|---|---|---|---|---|---|---|---|---|")
            for i in rows:
                L.append(f"| {i['id']} | {i['date']} | {i['stem']} | {i['run']} | {i['page']} | "
                         f"{' '.join((i['lines'] or [])[:4])}{'…' if len(i['lines'] or []) > 4 else ''} | "
                         f"{i['pattern']} | {(i['note'] or '').replace('|', '/')} | {i.get('rule', '')} |")
        L.append("")
    ISSUES_MD.write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("import")
    p.add_argument("files", nargs="+")
    p = sp.add_parser("add")
    p.add_argument("stems", nargs="+")
    p.add_argument("--run", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--note", default="")
    p = sp.add_parser("check")
    p.add_argument("--stems", nargs="*")
    p = sp.add_parser("accept")
    p.add_argument("stem")
    p.add_argument("--run", required=True)
    p.add_argument("--why", required=True)
    sp.add_parser("stale")
    p = sp.add_parser("issue")
    p.add_argument("id")
    p.add_argument("--status")
    p.add_argument("--pattern")
    p.add_argument("--rule")
    sp.add_parser("issues")
    a = ap.parse_args()
    if a.cmd == "import":
        cmd_import(a.files)
    elif a.cmd == "add":
        for s in a.stems:
            print(add_gold(s, a.run, "article", a.source, a.note).name)
    elif a.cmd == "check":
        sys.exit(cmd_check(a.stems))
    elif a.cmd == "accept":
        cmd_accept(a.stem, a.run, a.why)
    elif a.cmd == "stale":
        cmd_stale()
    elif a.cmd == "issue":
        cmd_issue(a.id, a.status, a.pattern, a.rule)
    elif a.cmd == "issues":
        write_issues_md()


if __name__ == "__main__":
    main()
