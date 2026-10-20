"""Experiment 43: doubtful spots of a run, found by code from the saved answers (no model calls).

    flags43.py --run replay        experiment 41's 55 answers through today's rules (out/replay/flags.json)
    flags43.py --run batch_test    the 4-article Batch test (out/batch_test/flags.json)
    flags43.py --run v2_55 | v2_fresh [--stems ...]   any run of run43.py, on whatever answers exist so far

Every article whose chunks are all answered is put through today's rules43 and experiment 41's assembly (in a
temporary folder: the run's own folders are only read), then checked. Each flag has the page, the Azure line ids,
a severity (high / medium / low) and a one-line reason in plain words. Kinds:

  call_failed       a chunk's call failed, was cut off (MAX_TOKENS) or did not end normally          high
  cost_high         a chunk cost far more per page than the run's median (input or output)            low
  noise_rescued     lines with words that the answer called noise or left out; rules43 put them back:
                    a run of >= 3 lines as its own block (another article? a missed block?)            high
                    one or two lines joined to the block beside them                                   low
  noise_left        a line with letters still left as noise (rules43 judged it a speck)               low
  line_twice        an Azure line placed in two blocks (or whole and as a half)                        high
  call_no_note      a footnote / endnote call whose note was not found                                medium
  call_not_in_line  a call whose marker is not in its line's text                                     low
  note_no_call      a note that no call points at                                                     low
  verse_cut         a verse cut that does not fit Azure's words, or a split rebuilt / undone          medium
  ornament_rejected an ornament the model listed that the code could not take out                     low
  other_middle      "another article" in the middle of a page (not a run at its top or bottom)         high
  other_inner       "another article" on a page that is neither the article's first nor last          medium
  other_most        "another article" covers most of the article's lines                              high
  type_mix          a page whose mix of block types is far from its neighbours' (list vs body...)     low
  heading_jump      a heading level jumps by two or more (h1 -> h3)                                   low
  table_ragged      a table whose rows have different numbers of cells                                medium
  math_failed       an equation whose LaTeX does not convert to MathML                                medium
  fixes_many        many more reader fixes on a page than the article's norm                          medium
  fixes_orth        several fixes on a page that only change hamza / ya / ta marbuta (D30: is it the
                    ink or a silent repair of the print?)                                             low
  long_heading      a heading of more than 3 printed rows: split by rules43 (low) or kept whole (medium)
  header_running_text  a line of running text rules43 took out of a header / footer block           medium
  overlap           two text boxes of the Layout view (after its box cutting) overlapping > 25% of the
                    smaller one by area (2026-10-18; 0478 p4)                                         medium
  inline_picture_over_text  a picture inside a printed line still over > 25% of the text           medium
  (2026-10-20, the fixes from the 300)
  show_through      lines of pale ink (the reverse side showing through, a watermark) kept as noise     low
  table_spans_columns  a table printed in two columns, drawn as one part per column                   medium
  letters_lost_vowelled  words in vocalised lines that are not words (lost letters?)                low
  inline_math_junk  Latin / formula tokens read unsure inside Arabic sentences, not taken as maths  medium
  guillemets_unsure (( )) whose ink is neither clearly guillemets nor clearly double brackets          low

Output: out/<run>/flags.json (versions used, thresholds, per article: counts + flags) and out/<run>/flags.txt.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import masters43 as M43  # noqa: E402
import rules43 as RU  # noqa: E402
from masters43 import ST, M, etree  # noqa: E402

OUT = HERE / "out"
SEV = {"high": 3, "medium": 2, "low": 1}
FURNITURE = {"header", "footer"}
T = dict(                                   # thresholds (tuned on experiment 41's 55 + the Batch test, 2026-10-18)
    cost_x=2.5,                             # chunk $/page or output tokens/page above this many times the run median
    noise_run=3,                            # rescued lines in one cluster from which it is "high"
    noise_left_letters=3,                   # a speck left as noise is listed from this many letters
    other_most=0.4,                         # share of the article's lines labelled another article
    mix_tv=0.55, mix_min_lines=10,          # total-variation distance of a page's type mix from its neighbours'
    notes_min=5, notes_share=0.5,          # an article-wide flag when this many and this share of calls/notes are unlinked
    heading_jump=2,
    fixes_min=8, fixes_x=3.0,               # a page's fixes >= max(fixes_min, fixes_x * article's median per page)
    orth_min=3,                             # hamza / ya / ta-marbuta-only fixes on one page
)


# ------------------------------------------------------------------------------------------------ runs and inputs

def run_dirs(run: str) -> dict:
    if run == "replay":                     # experiment 41's Argon answers, replayed through today's rules
        return dict(raw=M43.RAW41, masters=OUT / "masters", out=OUT / "replay")
    return dict(raw=OUT / run / "raw", masters=OUT / run / "masters", out=OUT / run)


def all_articles() -> dict:
    arts = {a["stem"]: dict(a, set="a") for a in ST.sample()}
    f = HERE / "sample43.json"
    if f.exists():
        for a in ST.jl(f)["articles"]:
            arts.setdefault(a["stem"], dict(a, set="b"))
    return arts


def use_pages_of(a: dict):
    """Page renders of the fresh sample live in this experiment (as in run43.py)."""
    ST.PAGES = OUT / "pages" if a.get("set") == "b" else M43.E41 / "out" / "pages"


def chunk_files(a: dict, raw: Path) -> list[dict]:
    out = []
    for x, y in ST.chunks(a):
        f = raw / f"{a['stem']}_c{x:03d}-{y:03d}.json"
        ff = raw / f"{a['stem']}_c{x:03d}-{y:03d}.failed.json"
        out.append(dict(x=x, y=y, f=f if f.exists() else None, failed=ff if ff.exists() else None))
    return out


def run_articles(run: str, stems=None) -> list[dict]:
    raw = run_dirs(run)["raw"]
    names = {p.name.split("_c")[0] for p in raw.glob("*_c*.json")} if raw.exists() else set()
    arts = all_articles()
    return [arts[s] for s in sorted(names) if s in arts and (not stems or s in stems)]


def load(a: dict, raw: Path, tmp: Path) -> dict:
    """Rules43 on every answered chunk (into tmp), then experiment 41's assembly: everything the checks read."""
    use_pages_of(a)
    ch = chunk_files(a, raw)
    B = dict(a=a, chunks=ch, recs=[], answers=[], logs=[], lines={}, cap=None)
    for c in ch:
        if not c["f"]:
            continue
        rec = ST.jl(c["f"])
        lines = {}
        for p in range(c["x"], c["y"] + 1):
            for L in ST.page_lines(a, p)[0]:
                lines[L["id"]] = dict(text=L["text"], b=L["b"], page=p)
        ans, log = RU.normalize(rec["answer"], lines, M43.azure_words(a))
        B["recs"].append(dict(rec, x=c["x"], y=c["y"], answer=None))
        B["answers"].append(ans)
        B["logs"].append(log)
        B["lines"].update(lines)
        (tmp / c["f"].name).write_text(json.dumps(dict(rec, answer=ans), ensure_ascii=False), encoding="utf-8")
    if all(c["f"] for c in ch):
        B["cap"] = M43.capture43(a, tmp)
    return B


# ------------------------------------------------------------------------------------------------ the checks

def flag(B, kind, sev, page, lines, reason, **extra) -> dict:
    lines = [str(i) for i in lines]
    box = None
    bs = [B["lines"][RU.base_of(i, B["lines"]) or i]["b"] for i in lines
          if (RU.base_of(i, B["lines"]) or i) in B["lines"]]
    if bs:
        box = RU.union(bs)
    return dict(id=f"{B['a']['stem']}|{kind}|p{page}|{lines[0] if lines else ''}", stem=B["a"]["stem"], kind=kind,
                severity=sev, page=page, lines=lines, box=box, reason=reason, **extra)


def run_norms(run: str) -> dict:
    per_usd, per_out = [], []
    for f in run_dirs(run)["raw"].glob("*_c*.json"):
        if f.name.endswith(".failed.json"):
            continue
        r = ST.jl(f)
        n = max(1, int(r.get("pages") or (r.get("last", 1) - r.get("first", 1) + 1)))
        if r.get("usd"):
            per_usd.append(r["usd"] / n)
        if r.get("tout"):
            per_out.append(r["tout"] / n)
    med = lambda v: statistics.median(v) if v else None  # noqa: E731
    return dict(usd_per_page=med(per_usd), out_per_page=med(per_out), chunks=len(per_usd))


def check_calls(B, norms):
    out = []
    for c in B["chunks"]:
        if c["failed"]:
            r = ST.jl(c["failed"])
            out.append(flag(B, "call_failed", "high", c["x"], [],
                            f"pages {c['x']}-{c['y']}: the call failed ({r.get('finish') or r.get('error') or '?'}); "
                            f"nothing of these pages is in the article"))
    for r in B["recs"]:
        fin = str(r.get("finish") or "")
        n = max(1, r["y"] - r["x"] + 1)
        if fin and "STOP" not in fin:
            out.append(flag(B, "call_failed", "high", r["x"], [], f"pages {r['x']}-{r['y']}: the answer ended with "
                                                                  f"{fin}, not a normal stop"))
        if r.get("error"):
            out.append(flag(B, "call_failed", "medium", r["x"], [], f"pages {r['x']}-{r['y']}: the call was retried "
                                                                    f"after an error ({str(r['error'])[:80]})"))
        why = []
        if norms.get("usd_per_page") and r.get("usd") and r["usd"] / n > T["cost_x"] * norms["usd_per_page"]:
            why.append(f"${r['usd'] / n:.3f} a page vs the run's median ${norms['usd_per_page']:.3f}")
        if norms.get("out_per_page") and r.get("tout") and r["tout"] / n > T["cost_x"] * norms["out_per_page"]:
            why.append(f"{r['tout'] / n:.0f} output tokens a page vs median {norms['out_per_page']:.0f}")
        if why:
            out.append(flag(B, "cost_high", "low", r["x"], [], f"pages {r['x']}-{r['y']} cost far above the norm "
                                                              f"({'; '.join(why)}): a long or looping answer?"))
    return out


def check_noise(B):
    out = []
    for log in B["logs"]:
        groups = {}
        for e in log["never_noise"]:
            groups.setdefault((e["page"], e["action"], e["kind"]), []).append(e)
        for (p, action, kind), es in sorted(groups.items()):
            ids = [e["line"] for e in es]
            said = "called noise" if kind == "noise" else "left out of every block"
            if action == "new other block":
                sev = "high" if len(ids) >= T["noise_run"] else "medium"
                out.append(flag(B, "noise_rescued", sev, p, ids,
                                f"{len(ids)} line(s) with words were {said}; the code kept them as an extra block "
                                f"(another article? a block the model missed?): «{es[0]['text'][:50]}»"))
            else:
                out.append(flag(B, "noise_rescued", "low", p, ids,
                                f"{len(ids)} line(s) with words were {said}; the code {action}: "
                                f"«{es[0]['text'][:50]}»"))
    for ans in B["answers"]:
        ghost = set(ans.get("_show_through") or [])
        for x in ans.get("noise") or []:
            i = RU.base_of(x, B["lines"])
            if i and i not in ghost and RU.letters(B["lines"][i]["text"]) >= T["noise_left_letters"]:
                L = B["lines"][i]
                out.append(flag(B, "noise_left", "low", L["page"], [i],
                                f"left as noise, judged a speck by the code: «{L['text'][:40]}»"))
    return out


def check_lines(B):
    out = []
    seen = Counter()
    for ans in B["answers"]:
        for pg in ans.get("pages") or []:
            for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
                for i in RU.block_ids(b):
                    seen[str(i)] += 1
    for i, n in seen.items():
        if n > 1 and i in B["lines"]:
            out.append(flag(B, "line_twice", "high", B["lines"][i]["page"], [i],
                            f"this line is placed in {n} blocks (its text may appear twice): "
                            f"«{B['lines'][i]['text'][:40]}»"))
    for i in seen:
        b = RU.base_of(i, B["lines"])
        if b and b != i and seen.get(b):
            out.append(flag(B, "line_twice", "high", B["lines"][b]["page"], [b],
                            f"this line is placed whole and also as a half ({i})"))
    return out


def check_notes(B):
    """Per page: calls without a note, calls whose marker is not in the line, notes without a call; per article:
    most calls (or notes) unlinked."""
    out = []
    blocks = B["cap"]["blocks"]
    notes = {b.get("fn_id"): b for b in blocks if b["type"] == "footnote" and b.get("fn_id")}
    called, no_note, not_in, n_calls = set(), {}, {}, 0
    for b in blocks:
        for c in b.get("calls") or []:
            n_calls += 1
            fn = c.get("fn")
            if fn:
                called.add(fn)
            p = c.get("page") or b["page"]
            if not fn or fn not in notes:
                no_note.setdefault(p, []).append(c)
            elif not c.get("_placed", True):
                not_in.setdefault(p, []).append(c)
    mk = lambda cs: " ".join(str(c.get("marker") or "?") for c in cs[:8]) + (" …" if len(cs) > 8 else "")  # noqa: E731
    for p, cs in sorted(no_note.items()):
        out.append(flag(B, "call_no_note", "medium", p, [c.get("line") for c in cs],
                        f"{len(cs)} call(s) on this page have no note ({mk(cs)}): note missing, misread, or an "
                        f"endnote not recognised?"))
    for p, cs in sorted(not_in.items()):
        out.append(flag(B, "call_not_in_line", "low", p, [c.get("line") for c in cs],
                        f"{len(cs)} call(s) whose marker is not in the line's text ({mk(cs)}): not linked where printed"))
    orphan = {}
    for fid, b in notes.items():
        if fid not in called:
            orphan.setdefault(b["page"], []).append(b)
    for p, bs in sorted(orphan.items()):
        out.append(flag(B, "note_no_call", "low", p, [b["ids"][0] for b in bs],
                        f"{len(bs)} note(s) on this page that no call points at "
                        f"({' '.join(str(b.get('marker') or b.get('fn_id')) for b in bs[:8])})"))
    nn = sum(len(v) for v in no_note.values())
    if nn >= T["notes_min"] and nn / n_calls >= T["notes_share"]:
        p0 = min(no_note)
        out.append(flag(B, "call_no_note", "high", p0, [c.get("line") for c in no_note[p0]][:3],
                        f"{nn} of the article's {n_calls} calls have no note: its notes (or endnotes) were not "
                        f"recognised", article=True))
    no = sum(len(v) for v in orphan.values())
    if notes and no >= T["notes_min"] and no / len(notes) >= T["notes_share"]:
        p0 = min(orphan)
        out.append(flag(B, "note_no_call", "medium", p0, [b["ids"][0] for b in orphan[p0]][:3],
                        f"{no} of the article's {len(notes)} notes have no call: calls not recognised in the text?",
                        article=True))
    return out


def check_verse(B):
    out = []
    for log in B["logs"]:
        for e in log["bad_cuts"]:
            i = RU.base_of(e["line"], B["lines"]) or e["line"]
            p = B["lines"].get(i, {}).get("page", 0)
            out.append(flag(B, "verse_cut", "medium", p, [i], f"verse cut {e['cut']} does not fit Azure's words of "
                                                              f"this line; the line stays uncut"))
        for e in log["bad_splits"]:
            i = str(e.get("line"))
            p = B["lines"].get(i, {}).get("page", 0)
            out.append(flag(B, "verse_cut", "medium", p, [i], f"the model's split of this line was not Azure's text "
                                                              f"({e.get('action', 'repaired')})"))
        by_page = {}
        for e in log["ornaments_rejected"]:
            i = RU.base_of(e.get("line"), B["lines"])
            if i:
                by_page.setdefault(B["lines"][i]["page"], []).append((i, e))
        for p, es in sorted(by_page.items()):
            out.append(flag(B, "ornament_rejected", "low", p, [i for i, _ in es],
                            f"{len(es)} ornament(s) the model listed could not be taken out (glued to a word?): "
                            + " ".join(f"«{e.get('text')}»" for _, e in es[:4])))
    return out


def check_other(B):
    out = []
    blocks = B["cap"]["blocks"]
    a = B["a"]
    tot = sum(len(b["ids"]) for b in blocks if b["type"] not in FURNITURE)
    oth = sum(len(b["ids"]) for b in blocks if b["type"] == "other_article")
    pages = sorted({b["page"] for b in blocks})
    for p in pages:
        seq = [b for b in blocks if b["page"] == p and b["type"] not in FURNITURE]
        flags = [b["type"] == "other_article" for b in seq]
        if not any(flags):
            continue
        ids = [i for b in seq if b["type"] == "other_article" for i in b["ids"]]
        k0 = 0
        while k0 < len(flags) and flags[k0]:                       # a run at the top
            k0 += 1
        k1 = len(flags)
        while k1 > k0 and flags[k1 - 1]:                            # a run at the bottom
            k1 -= 1
        if any(flags[k0:k1]):
            out.append(flag(B, "other_middle", "high", p, ids, "text labelled «another article» sits between this "
                                                                "article's blocks on the page, not at its top or bottom"))
        if p not in (a["first"], a["last"]) and p not in (pages[0], pages[-1]):
            out.append(flag(B, "other_inner", "medium", p, ids, f"«another article» on page {p}, which is neither the "
                                                                f"first nor the last page of this article"))
    if tot and oth / tot > T["other_most"]:
        ids = [i for b in blocks if b["type"] == "other_article" for i in b["ids"]]
        out.append(flag(B, "other_most", "high", next(b["page"] for b in blocks if b["type"] == "other_article"),
                        ids[:5], f"{oth / tot:.0%} of the article's lines are labelled «another article»"))
    return out


MIX = {"body", "list", "verse"}            # running text only: tables, notes, references legitimately vary by page


def page_mix(blocks) -> dict:
    mix = {}
    for b in blocks:
        k = ST.COARSE.get(b["type"], "other")
        if k in MIX:
            mix.setdefault(b["page"], Counter())[k] += len(b["ids"])
    return mix


def tv(c1: Counter, c2: Counter) -> float:
    n1, n2 = sum(c1.values()), sum(c2.values())
    return 0.5 * sum(abs(c1[k] / n1 - c2[k] / n2) for k in set(c1) | set(c2))


def check_mix(B):
    out = []
    mix = page_mix(B["cap"]["blocks"])
    for p, c in sorted(mix.items()):
        nb = Counter()
        for q in (p - 1, p + 1):
            nb.update(mix.get(q, Counter()))
        if p - 1 not in mix or p + 1 not in mix:                  # both neighbours: first / last pages differ anyway
            continue
        if sum(c.values()) < T["mix_min_lines"] or sum(nb.values()) < T["mix_min_lines"]:
            continue
        d = tv(c, nb)
        if d >= T["mix_tv"]:
            top = lambda x: ", ".join(f"{k} {v / sum(x.values()):.0%}" for k, v in x.most_common(2))  # noqa: E731
            ids = [i for b in B["cap"]["blocks"] if b["page"] == p and b["type"] not in FURNITURE for i in b["ids"]]
            out.append(flag(B, "type_mix", "low", p, ids, f"this page is {top(c)}; the pages beside it are {top(nb)} "
                                                          f"(list vs body? verse vs prose?)", distance=round(d, 2)))
    return out


def check_headings(B):
    out = []
    prev = None
    for b in B["cap"]["blocks"]:
        if b["type"] != "heading" or not b.get("level"):
            continue
        lv = int(b["level"])
        if prev is not None and lv - prev >= T["heading_jump"]:
            out.append(flag(B, "heading_jump", "low", b["page"], b["ids"],
                            f"heading level jumps from {prev} to {lv}: «{re.sub('<[^>]+>', '', b['html'])[:40]}»"))
        prev = lv
    return out


def table_widths(rows) -> list[int]:
    carry = {}                                  # column -> rows still covered by a rowspan from above
    widths = []
    for r in rows:
        w, col = 0, 0
        for c in r if isinstance(r, list) else []:
            while carry.get(col, 0) > 0:
                col += 1
                w += 1
            cs = int((c or {}).get("colspan") or 1) if isinstance(c, dict) else 1
            rs = int((c or {}).get("rowspan") or 1) if isinstance(c, dict) else 1
            for k in range(cs):
                if rs > 1:
                    carry[col + k] = rs
            col += cs
            w += cs
        while carry.get(col, 0) > 0:
            col += 1
            w += 1
        widths.append(w)
        carry = {k: v - 1 for k, v in carry.items() if v - 1 > 0}
    return widths


def check_tables(B):
    out = []
    for b in B["cap"]["blocks"]:
        if b["type"] != "table" or not b.get("rows"):
            continue
        ws = table_widths(b["rows"])
        if len(set(ws)) > 1:
            out.append(flag(B, "table_ragged", "medium", b["page"], b["ids"][:40],
                            f"table rows have different numbers of cells ({', '.join(map(str, ws[:12]))}"
                            f"{'…' if len(ws) > 12 else ''}): a cell merged, split or lost?"))
    return out


def mml_ok(latex: str) -> bool:
    return M.mathml(etree.Element("x"), latex, "block") is not None


def check_math(B):
    out = []
    for b in B["cap"]["blocks"]:
        if b["type"] == "equation" and b.get("latex") and not mml_ok(b["latex"]):
            out.append(flag(B, "math_failed", "medium", b["page"], b["ids"],
                            f"equation does not convert to MathML: {b['latex'][:60]}"))
    for lid, ms in (getattr(B["cap"]["S"], "math", None) or {}).items():
        for m in ms:
            if m.get("latex") and not mml_ok(m["latex"]):
                p = B["lines"].get(RU.base_of(lid, B["lines"]) or lid, {}).get("page", 0)
                out.append(flag(B, "math_failed", "medium", p, [lid],
                                f"inline formula does not convert to MathML: {m['latex'][:60]}"))
    return out


def check_fixes(B):
    out = []
    a = B["a"]
    S = B["cap"]["S"]
    per = Counter(f.get("page") for f in S.applied)
    n = a["last"] - a["first"] + 1
    med = statistics.median([per.get(p, 0) for p in range(a["first"], a["last"] + 1)]) if n else 0
    lim = max(T["fixes_min"], T["fixes_x"] * med)
    for p, k in sorted(per.items()):
        if k >= lim:
            ids = [f.get("line") for f in S.applied if f.get("page") == p]
            ex = "; ".join([f"{f.get('from')} → {f.get('to')}" for f in S.applied if f.get("page") == p][:3])
            out.append(flag(B, "fixes_many", "medium", p, ids,
                            f"{k} reader fixes on this page (article's median {med:g} a page): {ex}…", fixes=k))
    orth = {}
    for log in B["logs"]:
        for f in log["fixes_orthographic"]:
            i = RU.base_of(f.get("line"), B["lines"])
            if i:
                orth.setdefault(B["lines"][i]["page"], []).append((i, f))
    for p, fs in sorted(orth.items()):
        if len(fs) >= T["orth_min"]:
            out.append(flag(B, "fixes_orth", "low", p, [i for i, _ in fs],
                            f"{len(fs)} fixes only change hamza / ya / ta marbuta (ink or silent repair?): "
                            + "; ".join(f"{f['from']} → {f['to']}" for _, f in fs[:3])))
    return out


def check_layout_rules(B):
    """What the layout rules of 2026-10-18 did (0478 p4): a heading of more than 3 printed rows split or kept,
    a line of running text taken out of a header / footer block."""
    out = []
    for log in B["logs"]:
        for e in log.get("long_headings") or []:
            split = e["action"].startswith("split")
            out.append(flag(B, "long_heading", "low" if split else "medium", e["page"], e["lines"],
                            f"heading of {e['rows']} printed rows, {e['words']} words ({e['action']}): «{e['text'][:50]}»"))
        for e in log.get("header_text") or []:
            out.append(flag(B, "header_running_text", "medium", e["page"], [e["line"]],
                            f"a line of running text was in a {e['was']} block, now a {e['now']}: «{e['text'][:50]}»"))
    return out


def check_overlaps(B):
    """The Layout view's boxes (after its box cutting) on top of each other: two text boxes overlapping > 25% of
    the smaller one by area, or an inline picture > 25% over text. Built from the masters in a temporary folder."""
    if B.get("layout") is None:
        return []
    out = []
    for o in B["layout"]["overlaps"]:
        kind = "overlap" if o["kind"] == "text_text" else "inline_picture_over_text"
        out.append(dict(flag(B, kind, "medium", o["page"], [],
                             f"{o['a']} and {o['b']} drawn on top of each other ({o['share']:.0%} of the smaller box)"),
                        box_px=[o["box_a"], o["box_b"]]))
    return out


def check_fixes2(B):
    """What the rules of 2026-10-20 (the fixes from the 300) found."""
    out = []
    for log in B["logs"]:
        by = {}
        for e in log.get("show_through") or []:
            by.setdefault(e["page"], []).append(e)
        for p, es in sorted(by.items()):
            out.append(flag(B, "show_through", "low", p, [e["line"] for e in es],
                            f"{len(es)} line(s) of pale ink (show-through, watermark) kept out of the text: "
                            f"«{es[0]['text'][:40]}»"))
        for e in log.get("table_columns") or []:
            out.append(flag(B, "table_spans_columns", "medium", e["page"], [],
                            f"a table printed in {len(e['parts'])} columns ({' + '.join(map(str, e['parts']))} rows): "
                            f"drawn as {len(e['parts'])} parts, one table in the JATS", boxes=e["boxes"]))
        by = {}
        for e in log.get("vowelled_doubtful") or []:
            by.setdefault(e["page"], []).append(e)
        for p, es in sorted(by.items()):
            ws = [w["word"] for e in es for w in e["words"]]
            out.append(flag(B, "letters_lost_vowelled", "low", p, [e["line"] for e in es],
                            f"{len(ws)} word(s) in vocalised lines that are not words (letters Azure lost? a close-up "
                            f"re-read would tell): {' '.join(ws[:6])}"))
        by = {}
        for e in log.get("inline_math_junk") or []:
            by.setdefault(e["page"], []).append(e)
        for p, es in sorted(by.items()):
            ws = [w for e in es for w in e["words"]]
            out.append(flag(B, "inline_math_junk", "medium", p, [e["line"] for e in es],
                            f"{len(ws)} Latin / formula token(s) Azure read unsure inside Arabic sentences, not "
                            f"taken as maths (a formula left as junk?): {' '.join(ws[:6])}"))
        for e in log.get("guillemets") or []:
            if e["decision"] == "unsure":
                out.append(flag(B, "guillemets_unsure", "low", e["pages"][0], [],
                                f"(( )) on {e['lines']} line(s): the ink does not tell guillemets from double "
                                f"brackets ((: {e['double']} of the word height, single (: {e['single']}); kept as read"))
    return out


CHECKS = [check_fixes2, check_noise, check_lines, check_notes, check_verse, check_other, check_mix, check_headings, check_tables,
          check_math, check_fixes, check_layout_rules, check_overlaps]


def flags_of(B, norms) -> list[dict]:
    fl = check_calls(B, norms)
    if B["cap"] is not None:
        for c in CHECKS:
            fl += c(B)
    seen, out = set(), []
    for f in fl:
        if f["id"] in seen:
            k = 2
            while f"{f['id']}#{k}" in seen:
                k += 1
            f["id"] = f"{f['id']}#{k}"
        seen.add(f["id"])
        out.append(f)
    return sorted(out, key=lambda f: (-SEV[f["severity"]], f["page"]))


# ------------------------------------------------------------------------------------------------ the run

def run_flags(run: str, stems=None) -> dict:
    d = run_dirs(run)
    norms = run_norms(run)
    arts, pending, total = {}, [], Counter()
    for a in run_articles(run, stems):
        with tempfile.TemporaryDirectory() as td:
            try:
                B = load(a, d["raw"], Path(td))
                B["layout"] = None
                if B["cap"] is not None:
                    import views43
                    M43.build43(a, Path(td), Path(td) / "m", True, run="flags")
                    B["layout"] = views43.measure(a, Path(td) / "m", Path(td) / "v")
            except Exception as e:                       # one article's bug must not stop the rest
                arts[a["stem"]] = dict(error=f"{type(e).__name__}: {e}")
                continue
        answered = sum(1 for c in B["chunks"] if c["f"])
        failed = sum(1 for c in B["chunks"] if c["failed"])
        if B["cap"] is None and not failed:
            pending.append(dict(stem=a["stem"], answered=answered, chunks=len(B["chunks"])))
            continue
        fl = flags_of(B, norms)
        st = M43.stamp_of(a, d["raw"], run)
        cnt = Counter(f["severity"] for f in fl)
        kinds = Counter(f"{f['kind']}/{f['severity']}" for f in fl)
        total.update(kinds)
        arts[a["stem"]] = dict(pages=a["last"] - a["first"] + 1, prompt=st["prompt"], model=st["model"],
                               high=cnt["high"], medium=cnt["medium"], low=cnt["low"], kinds=dict(kinds), flags=fl)
    res = dict(run=run, made=time.strftime("%Y-%m-%d %H:%M"), versions=M43.versions(), thresholds=T, norms=norms,
               articles=arts, pending=pending,
               totals=dict(sorted(total.items(), key=lambda kv: (-SEV[kv[0].split("/")[1]], kv[0]))))
    d["out"].mkdir(parents=True, exist_ok=True)
    (d["out"] / "flags.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (d["out"] / "flags.txt").write_text(report(res), encoding="utf-8")
    return res


def report(res) -> str:
    L = [f"flags of run {res['run']} ({res['made']}; rules {res['versions']['rules_hash']})", ""]
    by_sev = Counter()
    for k, v in res["totals"].items():
        by_sev[k.split("/")[1]] += v
    L.append(f"articles {len(res['articles'])}, pending {len(res['pending'])}; flags: high {by_sev['high']}, "
             f"medium {by_sev['medium']}, low {by_sev['low']}")
    L.append("")
    for k, v in res["totals"].items():
        L.append(f"  {k:28} {v}")
    L.append("")
    L.append(f"  {'article':24} {'pages':>5} {'high':>5} {'med':>5} {'low':>5}  first high/medium reason")
    rows = sorted(res["articles"].items(), key=lambda kv: (-kv[1].get("high", 0), -kv[1].get("medium", 0), kv[0]))
    for s, r in rows:
        if r.get("error"):
            L.append(f"  {s:24} ERROR {r['error']}")
            continue
        top = next((f for f in r["flags"] if f["severity"] != "low"), None)
        L.append(f"  {s:24} {r['pages']:5} {r['high']:5} {r['medium']:5} {r['low']:5}  "
                 f"{('p' + str(top['page']) + ' ' + top['kind'] + ': ' + top['reason'][:70]) if top else ''}")
    for p in res["pending"]:
        L.append(f"  {p['stem']:24} pending: {p['answered']} of {p['chunks']} chunks answered")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--stems", nargs="*")
    a = ap.parse_args()
    res = run_flags(a.run, a.stems)
    print(report(res))


if __name__ == "__main__":
    main()
