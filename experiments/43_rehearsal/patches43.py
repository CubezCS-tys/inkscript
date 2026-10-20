"""Experiment 43: the patch layer — edits to a run's answers, keyed to Azure line ids and blocks, applied when the
masters are built; logged in every master and reversible (switched off, the rebuild is the master before). No
model calls. Owner-approved design: docs/ideas.md "A judge with authority, through patches".

A patch (one JSON object):
  id          "j-<stem4>-p<page>-<n>" (judge), "h-..." (person), "r-..." (gemini-retry)
  run         the run whose answers it edits (v33_300)        article  stem        page  int
  action      mark_noise | set_kind | reorder | split_block | merge_blocks | relink_call | mark_other_article |
              unmark_other_article | fix_picture_box          (no action changes a word)
  targets     {"lines": [...]} and/or {"blocks": [{"id": "p1b3", "lines": [...], "type", "box"}]} — a block is found
              again by its lines (or, without lines, by type + box), never by its position alone
  payload     action's data: kind (noise kind show-through|bleed|scanner-junk, or a block kind), level, order
              (block ids), at_line, line / marker / fn, box (0-1000)
  source      person | judge | gemini-retry   (precedence in that order: a patch whose lines or blocks a
              higher-ranked patch already touched is skipped, logged "overridden")
  confidence, evidence, reason, created; apply (true = applied when the masters are built; judge proposals that
  did not pass both keys are kept with apply false, for the review page)

Where: out/<judged run>/patches/<stem>.json (a list). Build:
    python3 patches43.py build --run v33_300 --out out/v33_300_judged [--stems ...] [--off]
copies out/<run>/rules/<stem>_c*.json, applies the patches (--off: none), and builds the masters with
masters43.build43 into <out>/masters. Every master built with patches gets <stem>.patches.json (applied, skipped, with
why) and a JATS custom-meta "pipeline-patches" listing the applied ids; with no patch applied the master is exactly
what build43 makes without this layer (test_patches43.py).
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE / "out"

ACTIONS = ("mark_noise", "set_kind", "reorder", "split_block", "merge_blocks", "relink_call", "mark_other_article",
           "unmark_other_article", "fix_picture_box", "replace_page_blocks")
# replace_page_blocks: only from a bespoke retry (retry43.py) or a person — the page's blocks and noise as the retry
# answered them (line ids only: the words stay Azure's and the first answer's fixes; checked there that every line
# of the page is used once and every call's note exists)
RANK = {"person": 0, "judge": 1, "gemini-retry": 2}
NOISE_KINDS = ("show-through", "bleed", "scanner-junk")


def block_lines(b: dict) -> list[str]:
    if b.get("lines"):
        return [str(x) for x in b["lines"]]
    if b.get("hemistichs"):
        return [str(x) for h in b["hemistichs"] for x in (h or [])]
    if b.get("rows"):
        return [str(x) for r in b["rows"] for c in r if isinstance(c, dict) for x in (c.get("lines") or [])]
    return []


def fingerprint(b: dict) -> dict:
    return dict(lines=block_lines(b), type=b.get("type"), box=b.get("box"))


def page_of(answers: dict, page: int):
    """(chunk record, page dict) of `page` in a stem's chunk records {file name: record}."""
    for name, rec in answers.items():
        if rec["first"] <= page <= rec["last"]:
            for pg in rec["answer"].get("pages") or []:
                if isinstance(pg, dict) and pg.get("page") == page:
                    return rec, pg
    return None, None


def find_block(pg: dict, t: dict) -> int | None:
    bl = [b for b in pg.get("blocks") or [] if isinstance(b, dict)]
    want = [str(x) for x in t.get("lines") or []]
    if want:
        for i, b in enumerate(bl):
            if block_lines(b) == want:
                return i
        for i, b in enumerate(bl):
            if want[0] in block_lines(b):
                return i
        return None
    for i, b in enumerate(bl):
        if b.get("type") == t.get("type") and b.get("box") == t.get("box"):
            return i
    return None


def touched(p: dict) -> set:
    t = p.get("targets") or {}
    s = {f"L{x}" for x in t.get("lines") or []}
    for b in t.get("blocks") or []:
        s |= {f"L{x}" for x in b.get("lines") or []} or {f"B{b.get('type')}{b.get('box')}"}
    if p["action"] == "reorder":
        s.add(f"O{p['page']}")
    return s


def _drop_lines(b: dict, ids: set):
    if b.get("lines"):
        b["lines"] = [x for x in b["lines"] if str(x) not in ids]
    if b.get("hemistichs"):
        b["hemistichs"] = [[x for x in h if str(x) not in ids] for h in b["hemistichs"]]
        b["hemistichs"] = [h for h in b["hemistichs"] if h]
    if b.get("rows"):
        for r in b["rows"]:
            for c in r:
                if isinstance(c, dict) and c.get("lines"):
                    c["lines"] = [x for x in c["lines"] if str(x) not in ids]
    if b.get("calls"):
        b["calls"] = [c for c in b["calls"] if str(c.get("line")) not in ids]


def apply_one(answers: dict, p: dict) -> str | None:
    """Apply patch p to the chunk records in place. None when applied, else why not (stale target, unknown action)."""
    a, pay, t = p["action"], p.get("payload") or {}, p.get("targets") or {}
    rec, pg = page_of(answers, p["page"])
    if pg is None:
        return "page not in the answers"
    ans = rec["answer"]
    blocks = pg.setdefault("blocks", [])
    if a == "mark_noise":
        ids = {str(x) for x in t.get("lines") or []}
        present = {x for b in blocks if isinstance(b, dict) for x in block_lines(b)}
        if not ids or not ids & present:
            return "lines not in any block"
        for b in blocks:
            if isinstance(b, dict):
                _drop_lines(b, ids)
        pg["blocks"] = [b for b in blocks if not isinstance(b, dict) or block_lines(b) or b.get("box")]
        noise = ans.setdefault("noise", [])
        noise.extend(sorted(ids & present - set(map(str, noise))))
        ans.setdefault("_noise_kinds", {}).update({i: pay.get("kind", "noise") for i in ids & present})
        return None
    if a == "replace_page_blocks":
        if p.get("source") not in ("gemini-retry", "person"):
            return "replace_page_blocks is for a retry or a person only"
        old = {x for b in blocks if isinstance(b, dict) for x in block_lines(b)}
        if old != {str(x) for x in pay.get("was_lines") or []}:
            return "page changed since the retry (lines differ)"
        pg["blocks"] = copy.deepcopy(pay["blocks"])
        pre = f"{p['page']}:"
        ans["noise"] = [x for x in ans.get("noise") or [] if not str(x).startswith(pre)] + list(pay.get("noise") or [])
        return None
    tb = t.get("blocks") or []
    idx = [find_block(pg, b) for b in tb]
    if any(i is None for i in idx):
        return "target block not found (answers changed since the patch was made)"
    bl = [b for b in blocks if isinstance(b, dict)]
    if a == "set_kind":
        b = bl[idx[0]]
        b["_was"] = b.get("_was") or b.get("type")
        b["type"] = pay["kind"]
        if pay["kind"] == "heading":
            b["level"] = pay.get("level") or b.get("level") or 2
        return None
    if a == "mark_other_article":
        for i in idx:
            bl[i]["_was"] = bl[i].get("type")
            bl[i]["type"] = "other_article"
        return None
    if a == "unmark_other_article":
        for i in idx:
            if bl[i].get("type") != "other_article":
                return "block is not marked another article"
            bl[i]["type"] = pay.get("kind") or bl[i].pop("_was", None) or "paragraph"
        return None
    if a == "fix_picture_box":
        b = bl[idx[0]]
        if not b.get("box"):
            return "block has no box"
        b["_box_was"] = b["box"]
        b["box"] = [int(round(v)) for v in pay["box"]]
        return None
    if a == "split_block":
        b, at = bl[idx[0]], str(pay.get("at_line"))
        ls = [str(x) for x in b.get("lines") or []]
        if at not in ls or ls.index(at) == 0:
            return "split line not inside a lines block"
        k = ls.index(at)
        nb = copy.deepcopy(b)
        b["lines"], nb["lines"] = b["lines"][:k], b["lines"][k:]
        if b.get("calls"):
            b["calls"] = [c for c in b["calls"] if str(c.get("line")) in ls[:k]]
            nb["calls"] = [c for c in nb["calls"] if str(c.get("line")) in ls[k:]]
        if pay.get("kind"):
            nb["type"] = pay["kind"]
        blocks.insert(blocks.index(b) + 1, nb)
        return None
    if a == "merge_blocks":
        if len(idx) < 2:
            return "fewer than two blocks"
        first, rest = bl[idx[0]], [bl[i] for i in idx[1:]]
        if not first.get("lines") or any(not r.get("lines") for r in rest):
            return "only blocks of lines merge"
        for r in rest:
            first["lines"] = first["lines"] + r["lines"]
            if r.get("calls"):
                first["calls"] = (first.get("calls") or []) + r["calls"]
            blocks.remove(r)
        return None
    if a == "relink_call":
        b = bl[idx[0]]
        line, mk, fn = str(pay.get("line")), pay.get("marker"), pay.get("fn")
        if line not in block_lines(b):
            return "call's line not in the block"
        calls = b.setdefault("calls", [])
        for c in calls:
            if str(c.get("line")) == line and (c.get("marker") == mk or not mk):
                c["_fn_was"] = c.get("fn")
                c["fn"] = fn
                return None
        calls.append(dict(line=line, marker=mk, fn=fn))
        return None
    if a == "reorder":
        order = pay.get("order") or []
        fps = pay.get("fp") or {}
        cur = []
        for bid in order:
            i = find_block(pg, fps.get(bid) or {})
            if i is None:
                return f"block {bid} not found"
            cur.append(bl[i])
        if len({id(x) for x in cur}) != len(bl):
            return "order is not a permutation of the page's blocks"
        others = [b for b in blocks if not isinstance(b, dict)]
        pg["blocks"] = cur + others
        return None
    return f"unknown action {a}"


def apply_all(answers: dict, patches: list[dict]) -> tuple[dict, list[dict]]:
    """Deep copy of answers with every patch marked apply=true applied, by precedence; a log entry per patch."""
    out = copy.deepcopy(answers)
    claimed, log = {}, []
    todo = sorted((p for p in patches if p.get("apply")),
                  key=lambda p: (RANK.get(p.get("source"), 9), p.get("created", ""), p["id"]))
    for p in todo:
        tch = touched(p)
        hit = sorted({claimed[x] for x in tch if x in claimed})
        if hit:
            log.append(dict(id=p["id"], action=p["action"], applied=False, why=f"overridden by {', '.join(hit)}"))
            continue
        if p["action"] not in ACTIONS:
            why = f"unknown action {p['action']}"
        else:
            why = apply_one(out, p)
        log.append(dict(id=p["id"], action=p["action"], source=p.get("source"), page=p["page"], applied=why is None,
                        **({"why": why} if why else {})))
        if why is None:
            for x in tch:
                claimed[x] = p["id"]
    return out, log


# ------------------------------------------------------------------------------------------------ files

def load_patches(pdir: Path, stem: str) -> list[dict]:
    f = Path(pdir) / f"{stem}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def save_patches(pdir: Path, stem: str, patches: list[dict]):
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / f"{stem}.json").write_text(json.dumps(patches, ensure_ascii=False, indent=1), encoding="utf-8")


def mark_master(mast: Path, stem: str, log: list[dict]):
    """JATS custom-meta "pipeline-patches" (ids of the applied patches) + sidecar <stem>.patches.json."""
    from lxml import etree
    import masters43 as M43
    applied = [e for e in log if e.get("applied")]
    (mast / f"{stem}.patches.json").write_text(json.dumps(dict(stem=stem, made=time.strftime("%Y-%m-%d %H:%M"),
                                                               applied=applied, skipped=[e for e in log if not e.get("applied")]),
                                                          ensure_ascii=False, indent=1), encoding="utf-8")
    if not applied:
        return
    jf = mast / f"{stem}.jats.xml"
    raw = jf.read_bytes()
    doctype = raw[raw.index(b"<!DOCTYPE"):raw.index(b">", raw.index(b"<!DOCTYPE")) + 1].decode()
    tree = etree.fromstring(raw, etree.XMLParser(remove_blank_text=False, resolve_entities=False, load_dtd=False))
    cmg = tree.find(".//article-meta/custom-meta-group")
    if cmg is None:
        return
    c = etree.SubElement(cmg, "custom-meta", {"id": "stamp-patches"})
    etree.SubElement(c, "meta-name").text = "pipeline-patches"
    etree.SubElement(c, "meta-value").text = "; ".join(f"{e['id']} {e['action']} ({e.get('source')})" for e in applied)
    jf.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True, doctype=doctype))
    del M43


def build(run: str, out: Path, stems: list[str] | None = None, off: bool = False, which: str = "b") -> dict:
    """Patched answers out/<out>/rules/ and masters out/<out>/masters/ for the run's articles that have patches
    (or `stems`). Never writes under out/<run>/."""
    import masters43 as M43
    import run43
    if which == "b":
        M43.ST.PAGES = OUT / "pages"
    out = Path(out).resolve()
    assert out != (OUT / run).resolve()
    src, rules, mast, pdir = OUT / run / "rules", out / "rules", out / "masters", out / "patches"
    arts = {a["stem"]: a for a in run43.articles(which)}
    stems = stems or sorted(f.stem for f in pdir.glob("*.json"))
    res = {}
    for s in stems:
        a = arts[s]
        files = [src / f"{s}_c{x:03d}-{y:03d}.json" for x, y in M43.ST.chunks(a)]
        if not all(f.exists() for f in files):
            res[s] = dict(error="answers missing")
            continue
        answers = {f.name: json.loads(f.read_text(encoding="utf-8")) for f in files}
        patched, log = (answers, []) if off else apply_all(answers, load_patches(pdir, s))
        rules.mkdir(parents=True, exist_ok=True)
        for name, rec in patched.items():
            (rules / name).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        r = M43.build43(a, rules, mast, True, run=out.name)
        if not off:
            mark_master(mast, s, log)
        res[s] = dict(applied=sum(e["applied"] for e in log), skipped=sum(not e["applied"] for e in log),
                      error=r.get("error"))
        print(f"  {s:24} applied {res[s]['applied']} skipped {res[s]['skipped']}"
              f"{' ERROR ' + r['error'] if r.get('error') else ''}", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--run", default="v33_300")
    ap.add_argument("--out", default=str(OUT / "v33_300_judged"))
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--off", action="store_true", help="build without any patch (the reversibility check)")
    a = ap.parse_args()
    build(a.run, Path(a.out), a.stems, a.off)


if __name__ == "__main__":
    main()
