"""Experiment 38, step 6: the numbers, per page -> out/pages/<pid>/measures.json, and out/measures.json.

    /home/yassine/inkscript/.venv/bin/python measure.py [--force]

Text, with `inkscript score`'s own score_page, three readings of the same page:
  azure      Azure as it is (the draft: Azure's lines in the current pipeline's order)
  joined     Azure's words poured into dots.mocr's blocks, in dots' reading order (plus the text kept from dots:
             table cells and blocks Azure has no words for) = the new document's text, uncorrected
  corrected  the same after the correction step
  dots       dots.mocr alone (experiment 36's converted prediction), for reference
On gold pages (status done) against the truth; on every other page against Azure's draft (agreement, not
accuracy: there "order" says how often the new order keeps the current pipeline's).

Corrections on gold pages: each applied edit is scored on its own line against the truth (the gold line has the
draft line's id): right (the line gets closer to the truth), wrong (further), neutral; errors missed = word
differences left between the corrected line and the truth, against those before.
"""
from __future__ import annotations

import json
import sys
from html import escape

from common import B36, OUT, azure_draft, gold, pages
from inkscript.gold.score import draft_pred, score_page
from inkscript.gold.text import distance, faithful


def table_html(b, rep, cw):
    rows = []
    for r in b["rows"]:
        cs = []
        for c in r["cells"]:
            t = " ".join(w["text"] for w in cw(c.get("words") or [], rep)) if c.get("words") else c.get("text", "")
            tag = "th" if c.get("th") else "td"
            sp = (f' colspan="{c["colspan"]}"' if c["colspan"] > 1 else "") + \
                 (f' rowspan="{c["rowspan"]}"' if c["rowspan"] > 1 else "")
            cs.append(f"<{tag}{sp}>{escape(t)}</{tag}>")
        rows.append("<tr>" + "".join(cs) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def pred_from_layout(L, F, rep):
    from master import corrected_words as cw
    from parse import order_lines
    lines, tables, eqs = [], [], []
    for b in L["blocks"]:
        if b["role"] == "table":
            for r in b["rows"]:
                for c in r["cells"]:
                    if c.get("words"):
                        for ln in order_lines(c["words"]):
                            ws = cw(ln, rep)
                            if ws:
                                lines.append(dict(text=" ".join(w["text"] for w in ws), box=_ub(ws)))
                    elif c.get("text"):
                        lines.append(dict(text=c["text"], box=c["box"]))
            tables.append(dict(html=table_html(b, rep, cw), box=b["box"]))
            continue
        if b["role"] == "formula":
            f = F.get(b["id"]) or {}
            eqs.append(dict(latex=f.get("tex") or b.get("tex_dots") or "", box=b["box"]))
        if b["source"] == "dots":
            lines.append(dict(text=b.get("text") or b["dots_text"], box=b["box"]))
            continue
        for ln in b.get("lines") or []:
            ws = cw(ln, rep)
            if ws:
                lines.append(dict(text=" ".join(w["text"] for w in ws), box=_ub(ws)))
    return dict(lines=lines, tables=tables, equations=eqs)


def _ub(ws):
    return [min(w["box"][0] for w in ws), min(w["box"][1] for w in ws), max(w["box"][2] for w in ws),
            max(w["box"][3] for w in ws)]


def bag(g, pred):
    """Order-free word error: words missing from the reading plus words it has that the truth does not, over the
    truth's words (faithful normalisation; equations left out on both sides as score_page does by kind)."""
    from collections import Counter
    from inkscript.gold.format import gold_lines
    G = Counter(w for ln in gold_lines(g) if ln.get("kind") != "equation" for w in faithful(ln.get("text", "")).split())
    P = Counter(w for x in pred.get("lines", []) for w in faithful(x.get("text", "")).split())
    miss = sum((G - P).values())
    extra = sum((P - G).values())
    return {"bag.words": sum(G.values()), "bag.missing": miss, "bag.extra": extra}


def keep(s):
    return {k: v for k, v in s.items() if k not in ("by_line_kind",)}


def correction_truth(pid, L, C, rep):
    """Per applied edit: right / wrong / neutral on its line against the gold line; errors before and after."""
    from master import corrected_words as cw
    g = gold(pid)
    gl = {ln["id"]: ln for ln in g["lines"] if ln.get("status") != "deleted"}
    words = {}
    for b in L["blocks"]:
        for w in b["words"]:
            words[w["id"]] = w
        for r in b.get("rows") or []:
            for c in r["cells"]:
                for w in c.get("words") or []:
                    words[w["id"]] = w
    byline = {}
    for w in words.values():
        byline.setdefault(w["line"], []).append(w)
    d0 = azure_draft(pid)
    order = {ln["id"]: [x["text"] for x in ln.get("words") or []] for ln in d0["lines"]}

    def line_text(li, edits):
        ws = sorted(byline.get(li, []), key=lambda w: int(w["id"].split("w")[-1]))
        return " ".join(w["text"] for w in cw(ws, edits))
    rows = []
    from master import apply_corrections
    for e in C["edits"]:
        if e.get("status") != "applied" or not e.get("word_ids"):
            continue
        li = words[e["word_ids"][0]]["line"]
        truth = gl.get(li, {}).get("text")
        if truth is None:
            rows.append(dict(e, verdict="no-truth"))
            continue
        one = apply_corrections(L, dict(edits=[e]))
        b0, a0 = faithful(line_text(li, {})), faithful(line_text(li, one))
        t = faithful(truth)
        db, da = distance(t, b0), distance(t, a0)
        rows.append(dict(unit=e["unit"], before=e["before"], after=e["after"], kind=e["kind"], reason=e["reason"],
                         confidence=e["confidence"], line=li, truth=truth, azure_line=b0,
                         verdict="right" if da < db else ("wrong" if da > db else "neutral"), dist_before=db,
                         dist_after=da))
    err_before = err_after = 0
    for li, ln in gl.items():
        if li not in byline:
            continue
        t = faithful(ln["text"]).split()
        err_before += distance(t, faithful(line_text(li, {})).split())
        err_after += distance(t, faithful(line_text(li, rep)).split())
    return dict(edits=rows, word_errors_before=err_before, word_errors_after=err_after)


def main(argv):
    from master import apply_corrections
    force = "--force" in argv
    allrows = []
    for meta in pages():
        pid = meta["page_id"]
        pdir = OUT / "pages" / pid
        mf = pdir / "measures.json"
        if mf.exists() and not force:
            allrows.append(json.loads(mf.read_text(encoding="utf-8")))
            continue
        if not (pdir / "layout.json").exists():
            continue
        L = json.loads((pdir / "layout.json").read_text(encoding="utf-8"))
        F = {f["id"]: f for f in json.loads((pdir / "formulas.json").read_text())} \
            if (pdir / "formulas.json").exists() else {}
        C = json.loads((pdir / "corrections.json").read_text(encoding="utf-8")) \
            if (pdir / "corrections.json").exists() else None
        rep = apply_corrections(L, C)
        g = gold(pid)
        done = g.get("status") == "done"
        truth = g if done else azure_draft(pid)
        preds = dict(azure=draft_pred(azure_draft(pid), "azure"), joined=pred_from_layout(L, F, {}),
                     corrected=pred_from_layout(L, F, rep))
        dp = B36 / "pred/dots_mocr" / f"{pid}.json"
        if dp.exists():
            preds["dots"] = json.loads(dp.read_text(encoding="utf-8"))
        sc = {k: dict(keep(score_page(truth, v, drafts=not done)), **bag(truth, v)) for k, v in preds.items()}
        m = dict(page_id=pid, gold_done=done, kinds=g["kinds"], primary=g["primary"], decade=g["decade"],
                 split=g["split"], stats=L["stats"], scores=sc,
                 corrections=dict(proposed=len(C["edits"]) if C else 0,
                                  applied=sum(e.get("status") == "applied" for e in C["edits"]) if C else 0,
                                  by_status={}) if C else None)
        if C:
            for e in C["edits"]:
                m["corrections"]["by_status"][e.get("status", "failed")] = \
                    m["corrections"]["by_status"].get(e.get("status", "failed"), 0) + 1
            if done:
                m["correction_truth"] = correction_truth(pid, L, C, rep)
        for kind in ("", "_raw"):
            bj = pdir / f"edition{kind}" / "build.json"
            if bj.exists():
                b = json.loads(bj.read_text(encoding="utf-8"))
                m["edition" + kind] = dict(errors=b.get("errors"), stats=b.get("stats"),
                                           checks=_checks(b.get("checks")))
        mf.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        allrows.append(m)
        s = sc
        print(pid, "done" if done else "", " ".join(
            f"{k}:{s[k]['faithful.char_err'] / max(1, s[k]['faithful.chars']):.3f}/o{s[k]['order_ok'] / max(1, s[k]['order_pairs']):.2f}"
            for k in s), flush=True)
    (OUT / "measures.json").write_text(json.dumps(allrows, ensure_ascii=False, indent=0), encoding="utf-8")


def _checks(c):
    if not c:
        return None
    return {k: v for k, v in c.items() if not isinstance(v, (list, dict)) or k in ("editions",)} if isinstance(c, dict) \
        else None


if __name__ == "__main__":
    main(sys.argv[1:])
