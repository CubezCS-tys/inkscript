#!/usr/bin/env python3
"""Experiment 97 scorer: the pipeline's current output (release R20261104T151029, via out/cache) against the keys.

    nice -n 19 python3 score97.py [--keys final|A|B]        (default: final, falling back to A where final is missing)

Every part is scored by ONE comparison function compare_<part>(gold, pred) that takes two documents in the key
format of KEYER_RULES.md.  The pipeline is first turned into that format (pipeline_<part>), so the same function
gives  pipeline vs key  and  key A vs key B  (the agreement ceiling).  Every A/B difference is listed in
out/scores/disagreements_<PART>.jsonl for the adjudicator.

Writes out/scores/scorecard.json and out/scores/scorecard.md.  Missing key folders / files are skipped and counted.
NOT FINAL: until out/keys/<part>/final exists the keys are not adjudicated, and the scorecard says so.
"""
from __future__ import annotations

import argparse
import collections as C
import glob
import json
import os
import re
import sys
import unicodedata

from common97 import (ARTS, BY_STEM, NO_BLOCK, OUT, article_index, cache, digits, exam_pages, fold, jdump,
                      line_targets, map_block_role, map_region_role, offset_to_line, pipeline_line_view, ws,
                      BLOCK_ROLE_TO_KEY, REGION_ROLE_TO_KEY)

KEYS = os.environ.get("EXP97_KEYS") or f"{OUT}/keys"          # EXP97_KEYS: self-test keys only
NOT_TEXT = "(not-text)"
SCORES = os.environ.get("EXP97_SCORES") or f"{OUT}/scores"
SKIP_ORDER_ROLES = {"running-head", "page-number"}
FRONT_ORDER_ROLES = {"title", "title-translated", "byline", "affiliation", "abstract", "keywords", "front-matter",
                     "footnote", "endnote"}
PASS = {
    "R1.letters": "<= 0.5% wrong letters", "R1.words": "<= 2% wrong words",
    "R2.lost": "<= 0.5%", "R2.doubled": "<= 0.2%",
    "P1.overall": ">= 97%", "P1.per_role": ">= 90% for every role with >= 30 lines",
    "P2.f1": ">= 95%",
    "P3.one_column": ">= 98%", "P3.two_column": ">= 95%",
    "P4.title": ">= 98%", "P4.authors": ">= 97%", "P4.other": ">= 95%",
    "P5.found": ">= 97%", "P5.invented": "<= 3%", "P5.level": ">= 90%",
    "P6.notes": ">= 97%", "P6.calls": ">= 95%",
    "P7.found": ">= 98%", "P7.shape": ">= 95%", "P7.continuation": ">= 90%", "P7.cells": ">= 99.5%",
    "P8.found": ">= 95%",
    "P9.boundaries": ">= 98%", "P9.fields": ">= 95% each",
}


def rate(a, b):
    return None if not b else round(a / b, 4)


_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def label_norm(s):
    s = ws(s)
    d = digits(s)
    return d if d else re.sub(r"[\s()\[\]{}]", "", s)


# ================================================================================================ key files
def part_dir(part: str) -> str | None:
    for d in glob.glob(f"{KEYS}/*"):
        if os.path.basename(d).upper() == part.upper():
            return d
    return None


def load_keys(part: str, which: str) -> dict:
    """{file name: key dict} from out/keys/<part>/<which>/ (unreadable files are reported, not fatal)."""
    d = part_dir(part)
    out, bad = {}, []
    if not d or not os.path.isdir(f"{d}/{which}"):
        return dict(files=out, bad=bad, dir=None)
    for f in sorted(glob.glob(f"{d}/{which}/*.json")):           # (sub-folders such as _v1/ are not read)
        if os.path.basename(f).startswith("_"):
            continue
        try:
            out[os.path.basename(f)] = json.load(open(f))
        except (ValueError, OSError) as e:
            bad.append(dict(file=f, error=str(e)[:200]))
    return dict(files=out, bad=bad, dir=f"{d}/{which}")


def gold_set(part: str, which: str) -> tuple[dict, str]:
    """The key to score against: `which`; for 'final', missing files fall back to A (marked as such)."""
    if which != "final":
        k = load_keys(part, which)
        return k, which
    fin, a = load_keys(part, "final"), load_keys(part, "A")
    ev = lambda d: {k: v for k, v in d.items() if _is_eval_file(part, v)}
    fe, ae = ev(fin["files"]), ev(a["files"])
    files = dict(ae)
    files.update(fe)
    n_fin, n_a = len(fe), len(set(ae) - set(fe))
    if n_fin and not n_a:
        src = f"final ({n_fin} files, adjudicated)"
    elif n_fin:
        src = f"MIXED: final {n_fin} files + UNADJUDICATED A {n_a} files"
    else:
        src = f"UNADJUDICATED key A only ({n_a} files; no final yet)"
    return dict(files=files, bad=fin["bad"] + a["bad"], dir=fin["dir"] or a["dir"], n_final=n_fin, n_A_fallback=n_a), src


# ================================================================================================ pipeline as keys
def page_lines(stem, page):
    return [l for l in cache(stem)["azure_lines"] if l["page"] == page]


def pipeline_page(stem: str, page: int) -> dict:
    """The pipeline's page in the PAGE key format.  Pieces are blocks (a table's cell blocks together are one piece,
    as the key asks), in blocks.ord order; page regions (running heads, page numbers, picture text ...) are pieces
    without a reading position (`unordered`).  Lines in noise-like regions go to azure_lines_that_are_not_text."""
    ix = article_index(stem)
    pieces, not_text, unmapped = {}, [], []
    for l in page_lines(stem, page):
        v = pipeline_line_view(stem, page, l["line_no"])
        if v["role"] == NO_BLOCK:
            unmapped.append(l["line_no"])
            continue
        if v["role"] == NOT_TEXT:
            not_text.append(l["line_no"])
            continue
        p = pieces.setdefault(v["piece"], dict(role=v["role"], lines=[], _ord=v["ord"], _raw=v["raw_role"],
                                               unordered=v["ord"] is None))
        p["lines"].append(l["line_no"])
        if v["ord"] is not None and (p["_ord"] is None or v["ord"] < p["_ord"]):
            p["_ord"] = v["ord"]
        if v.get("block_id"):
            b = ix["blocks"][v["block_id"]]
            p["continues_from_previous_page"] = b["page"] < page
            p["continues_on_next_page"] = (b["last_page"] or b["page"]) > page
            # blocks.note_id is mostly empty: a note is found by notes.first_block_id as well
            n = next((n for n in cache(stem)["notes"] if (b["note_id"] and n["note_id"] == b["note_id"])
                      or n["first_block_id"] == b["block_id"]), None)
            if n:
                p["note_label"] = n["label"]
    plist = sorted(pieces.values(), key=lambda p: (p["_ord"] is None, p["_ord"] or 0, min(p["lines"])))
    # note calls printed on this page: their block's stretch of text tells the Azure line
    notes = {n["note_id"]: n for n in cache(stem)["notes"]}
    tgt = C.defaultdict(list)
    for t in cache(stem)["note_call_targets"]:
        tgt[t["call_seq"]].append(t["note_id"])
    calls = []
    for c in cache(stem)["note_calls"]:
        b = ix["blocks"].get(c["block_id"])
        if not b or not (b["page"] <= page <= (b["last_page"] or b["page"])):
            continue
        k = offset_to_line(stem, c["block_id"], c["char_offset"] or 0)
        if not k or k[0] != page:
            continue
        tl = [notes[n]["label"] for n in tgt.get(c["call_seq"], []) if n in notes]
        tlines = None
        for nid in tgt.get(c["call_seq"], []):
            if nid in notes:
                bids = {b2["block_id"] for b2 in cache(stem)["blocks"] if b2["note_id"] == nid} | {notes[nid]["first_block_id"]}
                tlines = sorted({r["azure_line_no"] for bid in bids for r in ix["block_lines"].get(bid, []) if r["page"] == page}) or None
                break
        calls.append(dict(label=c["call_text"], in_line=k[1], target_label=tl[0] if tl else None, status=c["status"],
                          target_lines=tlines))
    return dict(stem=stem, page=page, columns=None, pieces=plist, note_calls=calls,
                azure_lines_that_are_not_text=not_text, _unmapped=unmapped, unsure=False)


def _chosen(d, field, lang=None):
    vals = [m for m in d["metadata"] if m["field"] == field and m["is_chosen"]]
    if lang is not None:
        vals = [m for m in vals if (m["lang"] or "") == lang] or vals
    return vals[0]["value"] if vals else None


LANG2 = {"ara": "ar", "eng": "en", "fre": "fr", "fra": "fr", "ar": "ar", "en": "en", "fr": "fr"}


def text_lang(text, lang=None):
    """Language of a title from its own letters (TRIAGE 2.1): Arabic letters -> 'ar'; Latin -> the stored lang when it
    is en / fr, else 'en'.  metadata.lang is NULL for some English titles and says 'en' for one Arabic one."""
    t = text or ""
    ar = len(re.findall(r"[\u0600-\u06ff]", t))
    la = len(re.findall(r"[A-Za-z\u00c0-\u024f]", t))
    if ar >= la and ar:
        return "ar"
    l2 = LANG2.get(lang or "", lang)
    return l2 if l2 in ("en", "fr") else "en"


def pipeline_front(stem: str) -> dict:
    d = cache(stem)
    titles = []
    for m in d["metadata"]:
        if m["is_chosen"] and m["field"] in ("title", "title_translated"):
            t = m["value"]
            sub = [s for s in d["metadata"] if s["is_chosen"] and s["field"] == "subtitle" and (s["lang"] == m["lang"] or m["field"] == "title")]
            if sub and m["field"] == "title" and fold(sub[0]["value"]) not in fold(t):     # the title often holds it already
                t = f"{t} : {sub[0]['value']}"
            titles.append(dict(lang=text_lang(t, m["lang"]), text=t, _field=m["field"]))
    rows = C.defaultdict(list)
    for a in sorted(d["affiliations"], key=lambda a: (a["mention_pk"], a["seq"] or 0)):
        if a["printed"]:
            rows[a["mention_pk"]].append(a["printed"])
    authors = []
    for b in sorted(d["bylines"], key=lambda b: b["byline_pos"]):
        rs = rows.get(b["mention_pk"], [])
        pos = [x.strip() for x in (b.get("position") or "").split(" | ") if x.strip()]
        # TRIAGE 2.3: the job title is kept in bylines.position (one part per script, ' | ' between), sometimes a
        # second affiliation row: the key's affiliation may be any of these
        cands = list(rs) + [p + j + r for p in pos for r in rs for j in (" ", "، ", ", ")]
        if len(rs) > 1:
            cands.append(" ; ".join(rs))
        if b.get("position"):
            cands += [b["position"]] + pos
        same_script = [p for p in pos if (text_lang(p) == "ar") == (b["script"] == "Arab")]
        authors.append(dict(printed=b["printed"], name_text=b["name_text"], titles=b["titles"], script=b["script"],
                            affiliation_printed=rs[0] if rs else None,
                            _aff_candidates=cands, _aff_parts=dict(position=pos, rows=rs),
                            _affiliation_with_position=" ".join(x for x in (" ".join(same_script), " ; ".join(rs)) if x) or None))
    by_lang = C.defaultdict(list)
    for a in d["abstracts"]:
        by_lang[LANG2.get(a["lang"], a["lang"])].append(a)
    abstracts = []
    for lang, rs in by_lang.items():
        # TRIAGE 2.4: every printed row of a language, in seq order; the catalogue row only when none is printed
        pr = sorted([a for a in rs if a["form"] == "printed"], key=lambda a: a["seq"] or 0)
        use = pr or sorted(rs, key=lambda a: a["seq"] or 0)[:1]
        text = ws(" ".join(a["text"] or "" for a in use))
        w = text.split(" ")
        abstracts.append(dict(lang=lang, first_words=" ".join(w[:8]), last_words=" ".join(w[-8:]),
                              _form="printed" if pr else use[0]["form"], _text=text, _n_rows=len(use)))
    kws = C.defaultdict(list)
    src = "masters" if any(k["source"] == "masters" for k in d["keywords"]) else "catalogue"
    for k in sorted([k for k in d["keywords"] if k["source"] == src], key=lambda k: k["seq"] or 0):
        kws[LANG2.get(k["lang"] or "", k["lang"])].append(k["printed"] or k["display"])
    dates = {}
    for t in ("received", "accepted", "published"):
        x = [r for r in d["dates"] if r["date_type"] == t and r["derivation"] != "catalogue"]
        # TRIAGE 2.5: the most precise row (a day and month) rather than the first
        x.sort(key=lambda r: (r.get("precision") == "year", r.get("day") is None, r.get("month") is None))
        dates[t] = x[0]["printed"] if x else None
    doi = _chosen(d, "doi")
    return dict(stem=stem, titles=titles, authors=authors, abstracts=abstracts,
                keywords=[dict(lang=l, list=v) for l, v in kws.items()], dates=dates, doi=doi,
                first_printed_page_number=_chosen(d, "fpage"), last_printed_page_number=_chosen(d, "lpage"),
                article_language=_chosen(d, "language"), _keyword_source=src, unsure=False)


def table_number(cap):
    """The first printed number of a caption, whole: '3-3' and '2.1' survive (TRIAGE 2.7)."""
    m = re.search(r"\d+(?:\s*[-.]\s*\d+)*", (cap or "").translate(_DIG))
    return m.group(0) if m else None


def _table_dir(stem, cells):
    bp = {b["block_id"]: b for b in cache(stem)["block_parts"]}
    r0 = [c for c in cells if c["block_id"] in bp]
    if len(r0) < 2:
        return "rtl"
    a, b = min(r0, key=lambda c: c["col"]), max(r0, key=lambda c: c["col"])
    return "rtl" if bp[a["block_id"]]["x"] >= bp[b["block_id"]]["x"] else "ltr"


def pipeline_tab(stem: str, page: int) -> dict:
    d = cache(stem)
    ix = article_index(stem)
    lines_of = C.defaultdict(set)
    for l in page_lines(stem, page):
        for k, i in line_targets(stem, page, l["line_no"]):
            fig = ix["blocks"][i]["figure_id"] or ix["cell_fig"].get(i) if k == "block" else None
            if fig:
                lines_of[fig].add(l["line_no"])
    cells_of = C.defaultdict(list)
    for c in d["table_cells"]:
        cells_of[c["figure_id"]].append(c)
    tables, figures = [], []
    for f in d["figures"]:
        pages_of = {ix["blocks"][c["block_id"]]["page"] for c in cells_of.get(f["figure_id"], []) if c["block_id"] in ix["blocks"]}
        on_page = f["page"] == page or page in pages_of
        if not on_page:
            continue
        if f["kind"] == "table":
            cs = [c for c in cells_of.get(f["figure_id"], [])
                  if c["block_id"] not in ix["blocks"] or ix["blocks"][c["block_id"]]["page"] == page] or cells_of.get(f["figure_id"], [])
            nr = max((c["row"] + (c["rowspan"] or 1) for c in cs), default=0)
            nc = max((c["col"] + (c["colspan"] or 1) for c in cs), default=0)
            r0 = min((c["row"] for c in cs), default=0)
            grid = [["" for _ in range(nc)] for _ in range(nr - r0)] if cs else None
            hdr = set()
            for c in cs:
                if grid is not None:
                    grid[c["row"] - r0][c["col"]] = c["text"] or ""
                if c["is_header"]:
                    hdr.add(c["row"])
            nh = 0
            while r0 + nh in hdr:
                nh += 1
            ln = sorted(lines_of.get(f["figure_id"], []))
            cap = f["caption"] or ""
            tables.append(dict(lines_first_last=[ln[0], ln[-1]] if ln else None, lines=ln, caption=cap or None,
                               number_printed=table_number(cap),
                               n_rows=nr - r0, n_cols=nc, n_header_rows=nh,
                               is_continuation_of_previous_page=bool(pages_of) and min(pages_of) < page,
                               continues_on_next_page=bool(pages_of) and max(pages_of) > page,
                               cells=grid, direction=_table_dir(stem, cs), _figure_id=f["figure_id"]))
        elif f["page"] == page:
            kind = {"figure": "figure", "equation": "equation", "inline-equation": "equation",
                    "inline-picture": "picture"}.get(f["kind"], f["kind"])
            cap = f["caption"] or ""
            figures.append(dict(kind=kind, caption=cap or None, number_printed=(re.findall(r"\d+", cap.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))[:1] or [None])[0],
                                _fig_type=f["fig_type"], _figure_id=f["figure_id"]))
    tables.sort(key=lambda t: (t["lines_first_last"] or [10 ** 6])[0])
    return dict(stem=stem, page=page, tables=tables, figures=figures, unsure=False)


def _ref_fields(parsed: dict, mention: dict | None = None) -> dict:
    """Pipeline reference fields in the key's terms (TRIAGE 2.8): source by type (conference: conf_name; journal:
    source_title, never moved into the title; thesis: the publisher, whose tail after a comma may be the university);
    authors fall back to editors; pages fall back to cited_pages."""
    pt = parsed.get("pub_type")
    at = parsed.get("article_title") or parsed.get("chapter_title")
    st, pub = parsed.get("source_title"), parsed.get("publisher")
    alts = {}
    if pt == "confproc" and parsed.get("conf_name"):
        title, source = at or st, parsed.get("conf_name")
        alts["source"] = [x for x in (st,) if x]
    elif pt == "journal":
        title, source = at, st
    elif pt == "thesis":
        title = at or st
        source = pub or (st if at else None)
        if pub:
            alts["source"] = [pub.split(",", k)[-1] for k in range(1, pub.count(",") + 1)] + \
                             [pub.split("\u060c", k)[-1] for k in range(1, pub.count("\u060c") + 1)]
    elif at:
        title, source = at, st
    else:
        title, source = st, pub
    pages = parsed.get("page_range") or ("-".join(x for x in (parsed.get("fpage"), parsed.get("lpage")) if x) or None)
    if not pages:
        pages = parsed.get("cited_pages") or ((mention or {}).get("cited_pages"))
    authors = []
    for a in (parsed.get("authors") or parsed.get("editors") or []):
        if isinstance(a, list):
            authors.append([x for x in a if x])
        else:
            authors.append([str(a)])
    return dict(type=pt, authors=authors, year=parsed.get("year"), title=title, source=source,
                volume=parsed.get("volume"), issue=parsed.get("issue"), pages=pages, _alts=alts,
                _publisher=pub, _place=parsed.get("place"), _series=parsed.get("series"))


def pipeline_refs(stem: str, page: int) -> dict:
    d = cache(stem)
    ix = article_index(stem)
    lines_of = C.defaultdict(list)
    for l in page_lines(stem, page):
        for k, i in line_targets(stem, page, l["line_no"]):
            if k == "block" and ix["blocks"][i]["role"] == "ref":
                lines_of[i].append(l["line_no"])
    cm = {}
    for m in d["citation_mentions"]:
        if m["container_kind"] == "ref-list" and m["block_id"] and m["block_id"] not in cm:
            cm[m["block_id"]] = m
    refs = []
    for bid in sorted(lines_of, key=lambda b: ix["blocks"][b]["ord"]):
        b = ix["blocks"][bid]
        m = cm.get(bid)
        f = _ref_fields(json.loads(m["parsed"]) if m and m["parsed"] else {}, m)
        refs.append(dict(lines=sorted(lines_of[bid]), starts_on_previous_page=b["page"] < page,
                         continues_on_next_page=(b["last_page"] or b["page"]) > page, lang=b["lang"], _block=bid, **f))
    return dict(stem=stem, page=page, references=refs, unsure=False)


def pipeline_sect(stem: str) -> dict:
    d = cache(stem)
    ix = article_index(stem)
    lv = {s["heading_block_id"]: s["level"] for s in d["sections"] if s["heading_block_id"]}
    hs = []
    for b in d["blocks"]:
        if b["role"] != "heading":
            continue
        ls = ix["block_lines"].get(b["block_id"], [])
        for pg in sorted({r["page"] for r in ls}) or [b["page"]]:
            hs.append(dict(page=pg, lines=sorted(r["azure_line_no"] for r in ls if r["page"] == pg), text=b["text"],
                           level=lv.get(b["block_id"])))
    return dict(stem=stem, headings=hs, unsure=False)


# ================================================================================================ comparisons
LEAVE_OUT_FLAGS = ("unsure", "image_defect", "other_article")      # other_article: a piece of another work (keys rev 2)


def left_out(x) -> bool:
    """A page / piece / table / reference marked unsure, image_defect or multiple_works is left out (conventions)."""
    return isinstance(x, dict) and any(x.get(k) for k in LEAVE_OUT_FLAGS)


def file_left_out(d) -> bool:
    """A whole key file is left out when it is marked image_defect or multiple_works, or marked unsure while none of
    its items is: keyer A set the page-level `unsure` whenever one piece was unsure (34 of its 44 unsure pages), and
    then the unsure pieces alone are left out, not the page."""
    if not isinstance(d, dict):
        return False
    if d.get("image_defect"):                    # (multiple_works no longer leaves a file out: keys rev 2 key the article's own work)
        return True
    if d.get("unsure"):
        items = [x for k in ("pieces", "tables", "references", "figures", "authors", "headings") for x in d.get(k) or []
                 if isinstance(x, dict)]
        return not any(left_out(x) or x.get("unsure_cells") or x.get("unsure_fields") for x in items) and not d.get("unsure_fields")
    return False


AUTHOR_BLOCK = {"byline", "affiliation"}


def accepted_roles(p: dict) -> set:
    """The roles a key piece accepts (KEYER_RULES, conventions for Part PAGE, 2026-11-10)."""
    r = p.get("role")
    acc = {r}
    if p.get("label_of"):                       # «الملخص» / "Keywords" on its own line
        acc |= {"heading", p["label_of"]}
    if p.get("carries"):                        # a foot note carrying an affiliation, dates or a contact
        acc |= {"footnote", "affiliation", "front-matter"}
    if p.get("tabular_list"):                   # a borderless list set in columns inside a note
        acc |= {"footnote", "table"}
    if p.get("table_note"):                     # a note under a table, outside its frame
        acc |= {"other", "caption", "paragraph", "footnote"}
    acc |= set(p.get("either_ok") or [])
    if r in AUTHOR_BLOCK:                       # the pipeline keeps author lines in front-matter blocks
        acc |= {"byline", "front-matter"}
    return acc


def _line_index(doc):
    role, piece = {}, {}
    for n, p in enumerate(doc.get("pieces") or []):
        for l in p.get("lines") or []:
            role[l] = p.get("role")
            piece[l] = n
    for l in doc.get("azure_lines_that_are_not_text") or []:
        role.setdefault(l, NOT_TEXT)
    return role, piece


def compare_page(gold: dict, pred: dict, acc: dict, diffs: list, tag: dict):
    """P1 roles, P2 grouping, P3 order, P6 notes + calls, keyed R2, on one page."""
    gr, gp = _line_index(gold)
    pr, pp = _line_index(pred)
    gold_unsure = {l for p in gold.get("pieces") or [] if left_out(p) for l in p.get("lines") or []}
    text_lines = [l for l in gr if gr[l] != NOT_TEXT and l not in gold_unsure]
    # ---- P1: right when the other side's role is one the key piece accepts, or (key vs key) the other way round
    gpcs, ppcs = gold.get("pieces") or [], pred.get("pieces") or []
    for l in text_lines:
        g, p = gr[l], pr.get(l, NO_BLOCK)
        ga = accepted_roles(gpcs[gp[l]])
        pa = accepted_roles(ppcs[pp[l]]) if l in pp else {p}
        ok = p in ga or g in pa
        acc["P1_conf"][(g, p)] += 1
        acc["P1_ok"][(g, p)] += ok
        if g in AUTHOR_BLOCK:
            acc["P1_author_block"]["n"] += 1
            acc["P1_author_block"]["ok"] += ok
        if not ok:
            diffs.append(dict(tag, measure="P1 role", line=l, gold=g, pred=p, gold_accepts=sorted(ga)))
    for l in gold.get("azure_lines_that_are_not_text") or []:
        acc["P1_not_text"][pr.get(l, NO_BLOCK)] += 1
        if pr.get(l, NO_BLOCK) != NOT_TEXT:
            diffs.append(dict(tag, measure="P1 not-text", line=l, gold=NOT_TEXT, pred=pr.get(l, NO_BLOCK)))
    # ---- keyed R2: printed text lines the pipeline put in no block or in a noise region
    for l in text_lines:
        acc["R2k"]["text_lines"] += 1
        if pr.get(l, NO_BLOCK) in (NO_BLOCK, NOT_TEXT) and pr.get(l, NO_BLOCK) not in accepted_roles(gpcs[gp[l]]):
            acc["R2k"]["lost"] += 1
    # ---- P2 (pairs of the key's text lines)
    for excl_tables in (False, True):
        L = [l for l in text_lines if not (excl_tables and gr[l] == "table")]
        tp = fp = fn = 0
        for i in range(len(L)):
            for j in range(i + 1, len(L)):
                a, b = L[i], L[j]
                gs = gp[a] == gp[b]
                ps = a in pp and b in pp and pp[a] == pp[b]
                tp += gs and ps
                fp += ps and not gs
                fn += gs and not ps
        k = "P2_no_tables" if excl_tables else "P2"
        acc[k]["tp"] += tp; acc[k]["fp"] += fp; acc[k]["fn"] += fn
    gpieces = [set(p.get("lines") or []) for p in gold.get("pieces") or []]
    ppieces = [set(p.get("lines") or []) for p in pred.get("pieces") or []]
    for n, s in enumerate(gpieces):
        s2 = s & set(text_lines)
        if s2 and s2 not in [q & set(text_lines) for q in ppieces]:
            diffs.append(dict(tag, measure="P2 piece", gold_lines=sorted(s), gold_role=gold["pieces"][n].get("role"),
                              pred_pieces=sorted({pp.get(l) for l in s if l in pp} - {None})))
    # ---- P3: adjacent key pieces, their position in the other order.  First pages are reported apart, twice: over
    # all pieces ('first', a diagnostic: blocks.ord stores front matter in a logical order by design) and over body
    # pieces only ('first_body': title, bylines, affiliations, abstract, keywords, front matter, notes and label
    # headings left out)
    cols = gold.get("columns")
    first = (BY_STEM.get(gold.get("stem")) or {}).get("pages", {}).get("front") == gold.get("page")
    ck0 = "first" if first else ("two" if cols == 2 else ("mixed" if cols == "mixed" else "one"))
    pred_pieces = pred.get("pieces") or []
    def body(p):
        return not (p.get("role") in FRONT_ORDER_ROLES or p.get("label_of") or p.get("carries"))
    for ck, keep in ([(ck0, lambda p: True)] + ([("first_body", body)] if first else [])):
        pos = []
        for p in gold.get("pieces") or []:
            if p.get("role") in SKIP_ORDER_ROLES or not p.get("lines") or not keep(p) or p.get("other_article"):
                continue
            votes = C.Counter(pp[l] for l in p["lines"] if l in pp)
            if not votes:
                pos.append(None)
                continue
            idx = votes.most_common(1)[0][0]
            pos.append(None if pred_pieces[idx].get("unordered") or pred_pieces[idx].get("role") in SKIP_ORDER_ROLES else idx)
        for a, b in zip(pos, pos[1:]):
            if a is None or b is None:
                acc["P3"][ck + "_skipped"] += 1
                continue
            acc["P3"][ck + "_pairs"] += 1
            if a <= b:
                acc["P3"][ck + "_ok"] += 1
                acc["P3"][ck + "_tied"] += a == b
            else:
                diffs.append(dict(tag, measure="P3 order" + (" (first page, body)" if ck == "first_body" else ""),
                                  columns=cols, pred_positions=[a, b]))
    # ---- P6 notes (line set and label) and calls.  A note is a footnote / endnote piece, or a piece that carries an
    # affiliation / dates / contact, or (first pages) an affiliation piece with a note label: the same rule on both
    # sides, so key A vs key B is not split by the footnote / affiliation ruling.
    def is_note(p):
        return (p.get("role") in ("footnote", "endnote") or bool(p.get("carries"))
                or (first and p.get("role") == "affiliation" and bool(p.get("note_label"))))
    gnotes = [p for p in gold.get("pieces") or [] if is_note(p) and not left_out(p)]
    pn = [p for p in pred_pieces if is_note(p)]
    pnotes = {frozenset(p.get("lines") or []): p for p in pn}
    for p in gnotes:
        acc["P6"]["notes"] += 1
        m = pnotes.get(frozenset(p.get("lines") or []))
        if m:
            acc["P6"]["notes_lines_ok"] += 1
            # a note continued from the previous page prints no label: nothing to compare
            no_label = p.get("continues_from_previous_page") and not p.get("note_label")
            ok_labels = {label_norm(p.get("note_label"))} | {label_norm(y) for y in p.get("note_label_also_ok") or []}
            if no_label or label_norm(m.get("note_label")) in ok_labels:
                acc["P6"]["notes_ok"] += 1
                acc["P6"]["notes_ok_no_label_to_compare"] += bool(no_label)
                continue
        diffs.append(dict(tag, measure="P6 note", gold_lines=p.get("lines"), gold_label=p.get("note_label"),
                          pred=dict(lines=sorted(m["lines"]), label=m.get("note_label")) if m else None))
    pcalls = C.defaultdict(list)
    for c in pred.get("note_calls") or []:
        pcalls[c.get("in_line")].append(c)
    glines = [frozenset(p.get("lines") or []) for p in gnotes]
    labs = lambda x, k="label": ({label_norm(x.get(k))} | {label_norm(y) for y in x.get("label_also_ok") or []}
                                 | {label_norm(y) for y in x.get("note_label_also_ok") or []})
    for c in gold.get("note_calls") or []:
        acc["P6"]["calls"] += 1
        cl = labs(c)
        m = [x for x in pcalls.get(c.get("in_line"), []) if label_norm(x.get("label")) in cl]
        if m:
            acc["P6"]["calls_found"] += 1
            # the link is judged by the target note's lines on this page (two pages print call ١ against note «5-» /
            # «(٨)»); a target note on another page (an endnote) is judged by its label
            tl = m[0].get("target_lines")
            lab = m[0].get("target_label", m[0].get("label"))
            if tl is None:
                tn = next((q for q in pn if label_norm(q.get("note_label")) == label_norm(lab)), None)
                tl = tn.get("lines") if tn else None
            gt = next((q for q in gnotes if labs(q, "note_label") & cl), None)
            if gt is not None:
                ok = tl is not None and frozenset(tl) == frozenset(gt.get("lines") or [])
            elif tl is not None:
                ok = frozenset(tl) in glines
            else:
                ok = label_norm(lab) in cl
            if ok:
                acc["P6"]["calls_linked"] += 1
                continue
        diffs.append(dict(tag, measure="P6 call", gold=c, pred=m[0] if m else None))
    acc["P6"]["pred_calls"] += len(pred.get("note_calls") or [])


_TYPO = str.maketrans({"\u2019": "'", "\u2018": "'", "`": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-",
                       "\u203a": ">"})


def ex_norm(s, colon=False, ci=False):
    """The 'exact' form: whitespace collapsed, trailing separators stripped (FRONT/REFS convention); for titles the
    key's ' : ' subtitle joiner ignored; lower-cased for references printed in small caps."""
    x = re.sub(r"[\s.,\u060c;:]+$", "", ws(s))
    if colon:
        x = re.sub(r"\s*:\s*", " ", x)
    return x.lower() if ci else x


def typo_norm(s, colon=False, ci=False):
    """'Typography-folded exact': exact plus curly / straight quotes and apostrophes, hyphen / en and em dash, › / >."""
    return ex_norm((s or "").translate(_TYPO), colon, ci)


def _eq(a, b, colon=False, ci=False):
    return ex_norm(a, colon, ci) == ex_norm(b, colon, ci), fold(a) == fold(b)


def _eq3(a, b, colon=False, ci=False, partial=None):
    """(exact, typography-folded exact, folded); partial = 'edge' accepts the key's value as a prefix or suffix of the
    other (a reference cut by the page edge)."""
    if a is None or b is None:
        return False, False, False
    out = []
    for f in (lambda x: ex_norm(x, colon, ci), lambda x: typo_norm(x, colon, ci), fold):
        g, p = f(a), f(b)
        ok = g == p or (partial == "edge" and bool(g) and (p.startswith(g) or p.endswith(g)))
        out.append(ok)
    out[1] = out[1] or out[0]
    out[2] = out[2] or out[1]
    return tuple(out)


def content_kind(g, p, gold_other=(), pred_other=()):
    """What is still wrong after folding: 'other side empty', 'part extra' / 'part missing' (one contains the other),
    'different field boundary' (the extra or missing part sits in another field of the same item, e.g. title text
    that ran into source), 'letters differ' (similar strings) or 'different text'."""
    from common97 import similarity
    G, P = fold(g), fold(p)
    if not P:
        return "other side empty"
    go = [fold(x) for x in gold_other if isinstance(x, str) and x]
    po = [fold(x) for x in pred_other if isinstance(x, str) and x]
    if G in P:
        extra = P.replace(G, " ", 1).strip()
        return "different field boundary" if len(extra) >= 3 and any(e and e in o for o in go for e in extra.split("  ")) else "part extra"
    if P in G:
        miss = G.replace(P, " ", 1).strip()
        return "different field boundary" if len(miss) >= 3 and any(m and m in o for o in po for m in miss.split("  ")) else "part missing"
    if any(P in o for o in go if len(P) >= 3) or any(G in o for o in po if len(G) >= 3):
        return "different field boundary"
    return "letters differ" if similarity(G, P) >= 0.6 else "different text"


def _field(acc, diffs, tag, name, g, p, kind="text", ctx=((), ()), cands=None, colon=False, ci=False, partial=None,
           extra_folded=None):
    """One field, scored where the KEY has a value (n).  A value the pipeline gives where the key says nothing is
    printed is counted apart (pred_where_key_null) and listed, not scored as wrong: several pipeline fields (DOI,
    'published' date, fpage/lpage) can come from the catalogue rather than from the page.  Three scores: exact,
    typography-folded exact ('typo'), folded.  `cands` are other forms the pipeline holds (any one may match);
    `extra_folded(g, cand)` may accept a folded match.  What is still wrong after folding gets a content kind
    (content_kind), counted in acc[name + ' kinds'] and listed."""
    if g is None or (isinstance(g, str) and not g.strip()):
        if p is not None and str(p).strip():
            acc[name]["pred_where_key_null"] += 1
            diffs.append(dict(tag, measure=name + " (key: not printed)", gold=g, pred=p))
        return
    if kind == "digits":
        e = t = f = p is not None and digits(g) == digits(p)
    else:
        e = t = f = False
        for c in [p] + [c for c in (cands or []) if c is not None and c != p]:
            e2, t2, f2 = _eq3(g, c, colon, ci, partial)
            if not f2 and extra_folded is not None and c is not None:
                f2 = bool(extra_folded(g, c))
            e, t, f = e or e2, t or t2, f or f2
    acc[name]["n"] += 1
    acc[name]["exact"] += e
    acc[name]["typo"] += t
    acc[name]["folded"] += f
    if not e:
        d = dict(tag, measure=name, gold=g, pred=p, folded_equal=f, typography_equal=t)
        if not f:
            d["content_wrong"] = True
            d["kind"] = content_kind(g, p, *ctx) if kind != "digits" else ("other side empty" if p is None else "digits differ")
            acc[name + " kinds"][d["kind"]] += 1
        diffs.append(d)


HONORIFIC = re.compile(r"^(?:\s*(?:أ\.?\s?م\.?\s?د\.?|[أا]\.?\s?د\.?|م\.?\s?د\.?|د\s?\.|د\s|الدكتور[ةه]?|الأستاذ[ةه]?|الاستاذ[ةه]?"
                       r"|الأستاذ الدكتور|Prof\.?|Professor|Dr\.?|Mr\.?|Mrs\.?|Ms\.?|Assoc\.?\s?Prof\.?)\s*)+", re.I)


def no_honorific(s):
    return HONORIFIC.sub("", ws(s)).strip() if s else s


def compare_front(gold, pred, acc, diffs, tag):
    skip = set(gold.get("unsure_fields") or []) | set(pred.get("unsure_fields") or [])
    def sk(*names):
        return any(n in skip or n.split(".")[0] in skip for n in names)
    if not sk("titles", "title"):
        for t in gold.get("titles") or []:
            p = [x for x in pred.get("titles") or [] if x.get("lang") == t.get("lang")]
            if not p and t.get("lang") not in ("ar", None):            # en / fr told apart only by a stored tag
                p = [x for x in pred.get("titles") or [] if x.get("lang") not in ("ar", None)
                     and not any(y.get("lang") == x.get("lang") for y in gold.get("titles") or [])]
            pt = p[0]["text"] if p else None
            # accepted: the full title with its subtitle, or `title_main` alone (keys rev 2); a part number printed on
            # the title line («( ٤ )») may be in or out (lead's ruling)
            main = t.get("title_main") or (gold.get("title_main") if fold(t.get("text") or "").startswith(fold(gold.get("title_main") or "\x00")) else None)
            cands = [re.sub(r"\s*[(\[]\s*[\d\u0660-\u0669]+\s*[)\]]\s*$", "", pt)] if pt else []
            before = acc["P4.title"]["folded"]
            _field(acc, diffs, dict(tag, lang=t.get("lang")), "P4.title", t.get("text"), pt, colon=True, cands=cands)
            if main and pt and acc["P4.title"]["folded"] == before and _eq3(main, pt, colon=True)[2]:
                # the pipeline holds the main title only: right under the rev-2 key; undo the miss just counted
                for k_, v_ in zip(("exact", "typo", "folded"), _eq3(main, pt, colon=True)):
                    acc["P4.title"][k_] += v_
                acc["P4.title kinds"][diffs[-1].get("kind")] -= 1 if diffs and diffs[-1].get("kind") else 0
                diffs.pop()
                acc["P4.title"]["matched_title_main"] += 1
            elif pt and acc["P4.title"]["folded"] > before:
                acc["P4.title"]["matched_full_title"] += 1
    # authors: in printed order, matched one-to-one within a script.  The pipeline's `printed`, `name_text` or
    # `titles + name_text` may be the printed form; a pipeline author whose fold is >= 0.75 similar counts as found
    # (then exact / folded tell whether it is right), otherwise the key's author is missing.  Names are also scored
    # with honorifics (د. / أ.د. / Dr. ...) taken off both sides (P4.authors_no_honorific).
    from common97 import similarity
    forms = lambda x: [v for v in (x.get("printed"), x.get("name_text"),
                                   " ".join(y for y in (x.get("titles"), x.get("name_text")) if y)) if v]
    pa = list(pred.get("authors") or [])
    for i, a in ([] if sk("authors") else enumerate(gold.get("authors") or [])):
        gp = a.get("printed")
        cand = [x for x in pa if (x.get("script") or a.get("script")) == a.get("script")]
        scored = sorted(((max(similarity(fold(no_honorific(v)), fold(no_honorific(gp))) for v in forms(x)) if forms(x) else 0, n)
                         for n, x in enumerate(cand)), reverse=True)
        best = cand[scored[0][1]] if scored and scored[0][0] >= 0.75 else None
        acc["P4.authors"]["n"] += 1
        acc["P4.authors_no_honorific"]["n"] += 1
        if best is None:
            diffs.append(dict(tag, measure="P4.authors", gold=gp, pred=None, content_wrong=True, kind="other side empty"))
            acc["P4.authors kinds"]["other side empty"] += 1
            if a.get("affiliation_printed") and not sk("authors.affiliation_printed", "affiliation"):
                _field(acc, diffs, dict(tag, author=gp), "P4.affiliation", a.get("affiliation_printed"), None)
            continue
        t_ = any(typo_norm(v) == typo_norm(gp) for v in forms(best))
        e = any(ex_norm(v) == ex_norm(gp) for v in forms(best))
        f = any(fold(v) == fold(gp) for v in forms(best))
        e2 = any(ex_norm(no_honorific(v)) == ex_norm(no_honorific(gp)) for v in forms(best))
        acc["P4.authors_no_honorific"]["typo"] += e2 or any(typo_norm(no_honorific(v)) == typo_norm(no_honorific(gp)) for v in forms(best))
        f2 = any(fold(no_honorific(v)) == fold(no_honorific(gp)) for v in forms(best))
        acc["P4.authors"]["found"] += 1
        acc["P4.authors"]["exact"] += e
        acc["P4.authors"]["typo"] += e or t_
        acc["P4.authors"]["folded"] += f
        acc["P4.authors_no_honorific"]["found"] += 1
        acc["P4.authors_no_honorific"]["exact"] += e2
        acc["P4.authors_no_honorific"]["folded"] += f2
        pa.remove(best)
        if not e:
            d = dict(tag, measure="P4.authors", gold=gp, pred=best.get("printed"), folded_equal=f,
                     equal_without_honorifics=f2)
            if not f:
                d["content_wrong"] = True
                d["kind"] = "honorific only" if f2 else content_kind(no_honorific(gp), no_honorific(best.get("printed")))
                acc["P4.authors kinds"][d["kind"]] += 1
            diffs.append(d)
        if not sk("authors.affiliation_printed", "affiliation"):
            # TRIAGE 2.3: any stored form may match (row, position + row, all rows, position); folded also when the
            # key ends with a stored row and what comes before it is >= 0.6 like a stored position (في / ب between)
            parts = best.get("_aff_parts") or {}
            def pos_plus_row(gk, cand, parts=parts):
                from common97 import similarity
                G = fold(gk)
                for r in parts.get("rows") or []:
                    R = fold(r)
                    if R and G.endswith(R):
                        rest = G[: len(G) - len(R)].strip()
                        if not rest:
                            return True
                        if any(similarity(rest, fold(p_)) >= 0.6 for p_ in parts.get("position") or []):
                            return True
                return False
            _field(acc, diffs, dict(tag, author=gp), "P4.affiliation", a.get("affiliation_printed"), best.get("affiliation_printed"),
                   cands=best.get("_aff_candidates"), extra_folded=pos_plus_row if parts else None)
            if "_affiliation_with_position" in best:      # pipeline only: position + printed
                _field(acc, [], tag, "P4.affiliation_with_position", a.get("affiliation_printed"), best.get("_affiliation_with_position"))
    acc["P4.authors"]["pred_extra"] += len(pa)
    for x in pa:
        diffs.append(dict(tag, measure="P4.authors extra", gold=None, pred=x.get("printed")))
    for a in ([] if sk("abstracts", "abstract") else gold.get("abstracts") or []):
        p = next((x for x in pred.get("abstracts") or [] if x.get("lang") == a.get("lang")), None)
        acc["P4.abstract"]["n"] += 1
        # the key gives ~8 words at each end; keyers do not always count 8: one end is right when the shorter of the
        # two is a prefix (first words) / suffix (last words) of the other, or of the pipeline's whole abstract
        def end_ok(k, f):
            if not p:
                return False
            g = f(a.get(k))
            x = f(p.get("_text")) if p.get("_text") else f(p.get(k))
            if not g or not x:
                return g == x
            if p.get("_text"):
                return x.startswith(g) if k == "first_words" else x.endswith(g)
            return (x.startswith(g) or g.startswith(x)) if k == "first_words" else (x.endswith(g) or g.endswith(x))
        ef = [(end_ok(k, ex_norm), end_ok(k, fold)) for k in ("first_words", "last_words")]
        acc["P4.abstract"]["typo"] += all(end_ok(k, typo_norm) for k in ("first_words", "last_words"))
        acc["P4.abstract"]["exact"] += all(e for e, _ in ef)
        acc["P4.abstract"]["folded"] += all(f for _, f in ef)
        if not all(e for e, _ in ef):
            d = dict(tag, measure="P4.abstract", lang=a.get("lang"), gold=[a.get("first_words"), a.get("last_words")],
                     pred=[p.get("first_words"), p.get("last_words")] if p else None)
            if not all(f for _, f in ef):
                d["content_wrong"] = True
                d["kind"] = "other side empty" if not p else ("abstract boundary: " + ", ".join(
                    k for (k, (_, f)) in zip(("start", "end"), ef) if not f))
                acc["P4.abstract kinds"][d["kind"]] += 1
            diffs.append(d)
    for k in ([] if sk("keywords") else gold.get("keywords") or []):
        p = next((x for x in pred.get("keywords") or [] if x.get("lang") == k.get("lang")), None)
        gl, pl = k.get("list") or [], (p or {}).get("list") or []
        acc["P4.keywords"]["n"] += 1
        acc["P4.keywords"]["exact"] += [ex_norm(x) for x in gl] == [ex_norm(x) for x in pl]
        acc["P4.keywords"]["typo"] += [typo_norm(x) for x in gl] == [typo_norm(x) for x in pl]
        acc["P4.keywords"]["folded"] += [fold(x) for x in gl] == [fold(x) for x in pl]
        acc["P4.keyword_items"]["n"] += len(gl)
        acc["P4.keyword_items"]["exact"] += len({ex_norm(x) for x in gl} & {ex_norm(x) for x in pl})
        acc["P4.keyword_items"]["typo"] += len({typo_norm(x) for x in gl} & {typo_norm(x) for x in pl})
        acc["P4.keyword_items"]["folded"] += len({fold(x) for x in gl} & {fold(x) for x in pl})
        if [ex_norm(x) for x in gl] != [ex_norm(x) for x in pl]:
            d = dict(tag, measure="P4.keywords", lang=k.get("lang"), gold=gl, pred=pl)
            if [fold(x) for x in gl] != [fold(x) for x in pl]:
                G, P = {fold(x) for x in gl}, {fold(x) for x in pl}
                d["content_wrong"] = True
                d["kind"] = ("other side empty" if not P else "same items, other order" if G == P else
                             "items missing" if P < G else "items extra" if G < P else "items differ")
                acc["P4.keywords kinds"][d["kind"]] += 1
            diffs.append(d)
    gd, pd = gold.get("dates") or {}, pred.get("dates") or {}
    dn = gold.get("date_numbers") or {}
    for t in ("received", "accepted", "published"):
        if (gd.get(t) is not None or pd.get(t) is not None) and not sk("dates", f"dates.{t}", f"date_{t}"):
            nums = dn.get(t)
            # keys rev 2: `date_numbers` = the date's numbers; compared as a set, so the order they were typed in
            # (reading order of the Arabic line vs glyph order) does not matter
            xf = (lambda g, c, nums=nums: {int(x) for x in nums} == {int(x) for x in re.findall(r"\d+", (c or "").translate(_DIG))}) if nums else None
            _field(acc, diffs, tag, f"P4.date_{t}", gd.get(t), pd.get(t),
                   cands=None, extra_folded=xf)
    if (gold.get("doi") is not None or pred.get("doi") is not None) and not sk("doi"):
        nd = lambda s: re.sub(r"^(https?://)?(dx\.)?doi\.org/|^doi:\s*", "", ws(s).lower()) if s else None
        _field(acc, diffs, tag, "P4.doi", nd(gold.get("doi")), nd(pred.get("doi")))
    for k in ("first_printed_page_number", "last_printed_page_number"):
        if gold.get(k) is not None and not sk(k):
            _field(acc, diffs, tag, f"P4.{k}", gold.get(k), pred.get(k), kind="digits")
    if gold.get("article_language") and not sk("article_language"):
        _field(acc, diffs, tag, "P4.article_language", LANG2.get(gold["article_language"], gold["article_language"]),
               LANG2.get(pred.get("article_language") or "", pred.get("article_language")))


def _range(t):
    lf = t.get("lines_first_last")
    return set(t.get("_lines") or (range(lf[0], lf[1] + 1) if lf and len(lf) == 2 and None not in lf else []))


def _mirror(grid):
    return [list(reversed(r)) for r in grid]


_SIGNS = r"[-+*%()\[\]±<>]"


def cell_fold(s):
    """Folded cell (2026-11-10 round 2): digit sets alike; ٫ ٬ , ، . between digits alike; spaces, tashkeel and tatweel
    removed; minus variants and ٪ unified; for a numeric cell (digits plus signs, stars, percent, brackets) the
    position of signs / stars / percent / brackets is ignored (the key types numbers in visual order)."""
    s = (s or "").translate(_DIG).replace("\u0640", "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"[\u2212\u2013\u2014\u2010\u2011]", "-", s).replace("\u066a", "%").replace("\u066d", "*")
    s = re.sub(r"[\u25a1\u25aa\u25a0\u2022\u25e6\u25cf]", "", s)          # □ ▪ ■ • ◦ ● bullets
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(?<=\d)[\u066b\u066c,\u060c.](?=\d)", ".", s)
    if s and re.search(r"\d", s) and re.fullmatch(r"[\d.\-+*%()\[\]±<>/]+", s):
        return "#" + re.sub(_SIGNS, "", s) + "|" + "".join(sorted(re.findall(_SIGNS, s)))
    return s


def compact_grid(grid, table_note=None):
    """(rows kept, their original indices): rows with no text dropped; a trailing row whose only non-empty cell folds
    equal to (or inside) the key's table note dropped too."""
    if not grid:
        return grid, []
    keep = [(i, r) for i, r in enumerate(grid) if any((x or "").strip() for x in r)]
    if table_note and keep:
        i, r = keep[-1]
        filled = [x for x in r if (x or "").strip()]
        if len(filled) == 1 and fold(filled[0]) and (fold(filled[0]) == fold(table_note) or fold(filled[0]) in fold(table_note)):
            keep = keep[:-1]
    return [r for _, r in keep], [i for i, _ in keep]


def _lines_of(t):
    if t.get("lines"):
        return set(t["lines"])
    lf = t.get("lines_first_last")
    return set(range(lf[0], lf[1] + 1)) if lf and len(lf) == 2 and None not in lf else set()


def compare_cells(gc, pc, unsure, acc, diffs, tt, P="P7.cells"):
    """Four-way cell report: (a) exact, (b) folded (cell_fold), (c) content wrong after folding, split into
    misplaced / structure (text found in a neighbouring cell of the same row or column, a cell outside the other
    grid, or a cell empty on one side only) and different text, (d) per table: no content-wrong cells."""
    pf = [[cell_fold(x) for x in row] for row in pc] if pc else []
    gf = [[cell_fold(x) for x in row] for row in gc]
    # for finding a cell's text in a neighbour, a looser fold (also no punctuation or symbols such as □ bullets)
    pl = [[fold(x) for x in row] for row in pc] if pc else []
    gl = [[fold(x) for x in row] for row in gc]
    def shifted(G, Pp, by_row):
        """Rows (or columns) of the key whose non-empty cells mostly sit one row (column) away on the other side."""
        out = set()
        nr = len(G)
        nc = max((len(x) for x in G), default=0)
        for i in range(nr if by_row else nc):
            cells = [(i, j) if by_row else (j, i) for j in range(nc if by_row else nr)]
            vals = [(r, c, G[r][c]) for r, c in cells if r < nr and c < len(G[r]) and G[r][c]]
            for d in (-1, 1):
                hit = sum(1 for r, c, v in vals if at(Pp, r + d, c) == v) if by_row else \
                      sum(1 for r, c, v in vals if at(Pp, r, c + d) == v)
                if vals and hit * 2 > len(vals):
                    out.add(i)
        return out
    def at(F, r, c):
        return F[r][c] if 0 <= r < len(F) and 0 <= c < len(F[r]) else None
    n_wrong = n_diff = 0
    srows, scols = (shifted(gl, pl, True), shifted(gl, pl, False)) if pc else (set(), set())
    for r, row in enumerate(gc):
        for c, cell in enumerate(row):
            if (r, c) in unsure:
                acc[P]["unsure_left_out"] += 1
                continue
            pv = pc[r][c] if pc and r < len(pc) and c < len(pc[r]) else None
            g, p = gf[r][c], at(pf, r, c)
            e = pv is not None and ws(cell) == ws(pv)
            f = pv is not None and g == p
            acc[P]["n"] += 1; acc[P]["exact"] += e; acc[P]["folded"] += f
            if e:
                continue
            if f:
                diffs.append(dict(tt, measure="P7.cell", row=r, col=c, gold=cell, pred=pv, folded_equal=True))
                continue
            if p is None:
                kind = "misplaced: outside the other grid"
            else:
                gL, pL = gl[r][c], at(pl, r, c)
                row_n = [at(pl, r, c - 1), at(pl, r, c + 1)]
                col_n = [at(pl, r - 1, c), at(pl, r + 1, c)]
                g_row = [at(gl, r, c - 1), at(gl, r, c + 1)]
                g_col = [at(gl, r - 1, c), at(gl, r + 1, c)]
                if r in srows or c in scols:
                    kind = "misplaced: row or column shifted by one"
                elif gL and (gL in row_n or gL in col_n):
                    kind = "misplaced: key text in a neighbouring cell"
                elif pL and (pL in g_row or pL in g_col):
                    kind = "misplaced: other text belongs to a neighbouring cell"
                elif not g or not p:
                    kind = "misplaced: empty on one side (" + ("key" if not g else "other") + " empty)"
                elif gL == pL:
                    kind = "different text: punctuation / symbols only"
                else:
                    kind = "different text: letters or digits"
            n_wrong += 1
            acc[P]["content_wrong"] += 1
            if kind.startswith("different text"):
                n_diff += 1
                acc[P]["different_text"] += 1
            else:
                acc[P]["misplaced"] += 1
            acc["P7.cell_kinds"][kind] += 1
            diffs.append(dict(tt, measure="P7.cell", content_wrong=True, kind=kind, row=r, col=c, gold=cell, pred=pv,
                              folded_equal=False))
    acc["P7.cell_tables"]["n"] += 1
    acc["P7.cell_tables"]["zero_content_wrong"] += n_wrong == 0
    acc["P7.cell_tables"]["zero_different_text"] += n_diff == 0
    if n_wrong:
        acc["P7.cell_tables_list"][f"{tt.get('stem')} p{tt.get('page')} t{tt.get('table')}"] = (n_wrong, n_diff)


def compare_tab(gold, pred, acc, diffs, tag):
    gts = [(n, t) for n, t in enumerate(gold.get("tables") or []) if not left_out(t)]
    pts = list(pred.get("tables") or [])
    # one-to-one matching on the tables' Azure lines (the full list where both have it, else the [first, last]
    # interval), plus 1 when the printed numbers agree (two tables in one stretch of lines), best first
    def iou(a, b):
        A, B = _lines_of(a), _lines_of(b)
        if not A or not B:
            return 0.0
        if a.get("lines") and b.get("lines"):
            return len(A & B) / len(A | B)
        return max(0, min(max(A), max(B)) - max(min(A), min(B)) + 1) / (max(max(A), max(B)) - min(min(A), min(B)) + 1)
    def num_bonus(a, b):
        x, y = digits(a.get("number_printed")), digits(b.get("number_printed"))
        return 1.0 if x and x == y else 0.0
    pairs = sorted(((iou(t, p) + (num_bonus(t, p) if iou(t, p) > 0 else 0), n, i) for n, t in gts for i, p in enumerate(pts)), reverse=True)
    match, used = {}, set()
    for v, n, i in pairs:
        if v > 0 and n not in match and i not in used:
            match[n] = i
            used.add(i)
    for n, t in gts:
        best = match.get(n)
        acc["P7.found"]["n"] += 1
        tt = dict(tag, table=n, gold_lines=t.get("lines_first_last"))
        if best is None:
            diffs.append(dict(tt, measure="P7.found", gold="table", pred=None))
            continue
        p = pts[best]
        acc["P7.found"]["ok"] += 1
        # TRIAGE 2.7: rows empty on a side (a printed spacer row) are dropped before shape and cells, and a trailing
        # other-side row holding only the key's table note is not a row
        gk, gidx = compact_grid(t.get("cells"))
        pk, pidx = compact_grid(p.get("cells"), table_note=t.get("table_note") if isinstance(t.get("table_note"), str) else None)
        g_rows = t.get("n_rows") - (len(t["cells"]) - len(gk)) if t.get("cells") and t.get("n_rows") is not None else t.get("n_rows")
        p_rows = p.get("n_rows") - (len(p["cells"]) - len(pk)) if p.get("cells") and p.get("n_rows") is not None else p.get("n_rows")
        sh = g_rows == p_rows and t.get("n_cols") == p.get("n_cols")
        acc["P7.shape"]["n"] += 1; acc["P7.shape"]["ok"] += sh
        if not sh:
            diffs.append(dict(tt, measure="P7.shape", gold=[t.get("n_rows"), t.get("n_cols")], pred=[p.get("n_rows"), p.get("n_cols")],
                              rows_after_dropping_empty=[g_rows, p_rows]))
        hr = t.get("n_header_rows") == p.get("n_header_rows")
        acc["P7.header_rows"]["n"] += 1; acc["P7.header_rows"]["ok"] += hr
        if not hr:
            diffs.append(dict(tt, measure="P7.header_rows", gold=t.get("n_header_rows"), pred=p.get("n_header_rows")))
        # (caption_on_previous_page says nothing about continuation: the key's flag is taken as it is)
        for k, m in (("is_continuation_of_previous_page", "P7.continuation"), ("continues_on_next_page", "P7.continues_next")):
            ok = bool(t.get(k)) == bool(p.get(k))
            acc[m]["n"] += 1; acc[m]["ok"] += ok
            if not ok:
                diffs.append(dict(tt, measure=m, gold=t.get(k), pred=p.get(k)))
        if t.get("caption") is not None or p.get("caption") is not None:
            _field(acc, diffs, tt, "P7.caption", t.get("caption"), p.get("caption"))
        if t.get("number_printed") is not None or p.get("number_printed") is not None:
            _field(acc, diffs, tt, "P7.number", t.get("number_printed"), p.get("number_printed"), kind="digits")
        gc, pc = (gk if t.get("cells") else None), (pk if p.get("cells") else None)
        if gc:
            acc["P7.cells_tables"]["n"] += 1
            if pc and (t.get("direction") or "rtl") != (p.get("direction") or "rtl"):
                pc = _mirror(pc)
            same_shape = pc is not None and len(pc) == len(gc) and all(len(a) == len(b) for a, b in zip(gc, pc))
            acc["P7.cells_tables"]["ok"] += same_shape
            g_new = {o: n_ for n_, o in enumerate(gidx)}
            p_new = {o: n_ for n_, o in enumerate(pidx)}
            uc = lambda x: list(x.get("unsure_cells") or []) + list(x.get("unreadable_cells") or [])
            unsure = ({(g_new[r], c) for r, c in map(tuple, uc(t)) if r in g_new} |
                      {(p_new[r], c) for r, c in map(tuple, uc(p)) if r in p_new})
            acc["P7.rows_dropped"]["empty_key_rows"] += len(t["cells"]) - len(gk)
            acc["P7.rows_dropped"]["empty_or_note_other_rows"] += (len(p["cells"]) - len(pk)) if p.get("cells") else 0
            compare_cells(gc, pc, unsure, acc, diffs, tt)
    # borderless lists set in columns are not tables (scored apart): a table the other side made of one is not "extra"
    tl = [_lines_of(x) for x in gold.get("tabular_lists") or []]
    for x in tl:
        acc["P7.tabular_lists"]["n"] += 1
        acc["P7.tabular_lists"]["other_made_a_table"] += any(_lines_of(p) & x for p in pts)
    used |= {i for i, p in enumerate(pts) if any(_lines_of(p) & x for x in tl)}
    acc["P7.found"]["pred_extra"] += len(pts) - len(used)
    for i, p in enumerate(pts):
        if i not in used:
            diffs.append(dict(tag, measure="P7.extra", pred_lines=p.get("lines_first_last"), caption=p.get("caption")))
    # ---- P8 figures and equations: matched by printed number within the kind group, then in order
    grp = lambda k: "equation" if k == "equation" else "figure"
    pf = list(pred.get("figures") or [])
    for n, f in enumerate([f for f in gold.get("figures") or [] if not left_out(f)]):
        cand = [x for x in pf if grp(x.get("kind")) == grp(f.get("kind"))]
        m = next((x for x in cand if f.get("number_printed") and digits(x.get("number_printed")) == digits(f.get("number_printed"))), None) \
            or (cand[0] if cand else None)
        acc["P8.found"]["n"] += 1
        if not m:
            diffs.append(dict(tag, measure="P8.found", figure=n, gold=f, pred=None))
            continue
        pf.remove(m)
        acc["P8.found"]["ok"] += 1
        if f.get("caption") is not None or m.get("caption") is not None:
            _field(acc, diffs, dict(tag, figure=n), "P8.caption", f.get("caption"), m.get("caption"))
    acc["P8.found"]["pred_extra"] += len(pf)


ETAL = re.compile(r"\s*(?:et\s+al\.?|\u0648?\u0622\u062e\u0631\u0648\u0646|\u0648?\u0627\u062e\u0631\u0648\u0646)\s*[.,\u060c]?\s*$", re.I)


def _author_clean(s):
    """Honorifics off (also one glued to a name inside the string, «زرزور د.عدنان»), et-al markers off."""
    x = ETAL.sub("", no_honorific(s) or "").strip()
    return ws(" ".join(no_honorific(t) or "" for t in x.split(" ")))


def _authors_exact(gold_list, pred_list, ci=False):
    """Key authors are printed strings; the pipeline keeps [family, given] parts.  Honorifics and et-al markers
    (et al. / وآخرون) are taken off both sides.  Exact: one of the obvious printed joins equals the key; typography:
    the same after the typography fold; folded: the parts joined by spaces fold to the key's fold.
    -> (exact, typography, folded)"""
    gl = [_author_clean(g) for g in (gold_list or [])]
    gl = [g for g in gl if g]
    if pred_list and isinstance(pred_list[0], str):
        pred_list = [[x] for x in pred_list]
    pl = [[_author_clean(x) for x in p if _author_clean(x)] for p in (pred_list or [])]
    pl = [p for p in pl if p]
    if len(gl) != len(pl):
        return False, False, False
    e = t = f = True
    for g, p in zip(gl, pl):
        joins = {j.join(p) for j in (" ", "، ", ", ", ",", "،")} | {" ".join(reversed(p))}
        e &= ex_norm(g, ci=ci) in {ex_norm(j, ci=ci) for j in joins}
        t &= typo_norm(g, ci=ci) in {typo_norm(j, ci=ci) for j in joins}
        f &= fold(g) in {fold(j) for j in joins}
    return e, e or t, f


def page_set(s):
    """The printed numbers of a page field as a set (digit sets folded), NOT expanded or reordered: '٢٦٤-٢٢٣' equals
    itself and '223-264'.  (TRIAGE 2.8: the key writes ranges in reading order.)"""
    if not s:
        return None
    return frozenset(int(x) for x in re.findall(r"\d+", str(s).translate(_DIG)))


REF_FIELDS = ("year", "title", "source", "volume", "issue", "pages")


def compare_refs(gold, pred, acc, diffs, tag):
    gr = [(n, r) for n, r in enumerate(gold.get("references") or []) if not left_out(r)]
    pr = [r for r in pred.get("references") or [] if not left_out(r)]
    skip_file = set(gold.get("unsure_fields") or []) | set(pred.get("unsure_fields") or [])
    pmap = {frozenset(r.get("lines") or []): r for r in pr}
    for n, r in gr:
        tt = dict(tag, ref=n, gold_lines=r.get("lines"))
        merged = bool(r.get("merged_in_print"))
        if merged:                                   # two works printed as one entry: no boundary, no fields
            acc["P9.left_out"]["merged_in_print"] += 1
            continue
        skip = skip_file | set(r.get("unsure_fields") or [])
        m = pmap.get(frozenset(r.get("lines") or []))
        if "lines" not in skip:
            acc["P9.boundaries"]["n"] += 1
            if m:
                acc["P9.boundaries"]["ok"] += 1
        if not m:
            over = max(pr, key=lambda x: len(set(x.get("lines") or []) & set(r.get("lines") or [])), default=None)
            if over and set(over.get("lines") or []) & set(r.get("lines") or []):
                m = over
            if "lines" not in skip:
                diffs.append(dict(tt, measure="P9.boundaries", gold=r.get("lines"), pred=m.get("lines") if m else None))
            if m is None:
                continue
        skip |= set(m.get("unsure_fields") or [])
        ci = bool(r.get("small_caps"))                                   # printed in small caps: case is not text
        edge = "edge" if (r.get("starts_on_previous_page") or r.get("continues_on_next_page")) else None
        others = {digits(x) for x in r.get("other_numbers") or [] if digits(x)}
        alts = m.get("_alts") or {}
        # fields: scored on every key reference that has a pipeline reference over it (exact boundaries or not)
        ga, pa = r.get("authors"), m.get("authors")
        if (ga or pa) and "authors" not in skip:
            if pa and isinstance(pa[0], str):
                pa2 = [[x] for x in pa]
            else:
                pa2 = pa
            e, t, f = _authors_exact(ga, pa2, ci=ci)
            acc["P9.authors"]["n"] += 1; acc["P9.authors"]["exact"] += e; acc["P9.authors"]["typo"] += t
            acc["P9.authors"]["folded"] += f
            if not e:
                d = dict(tt, measure="P9.authors", gold=ga, pred=pa, folded_equal=f, typography_equal=t)
                if not f:
                    pj = [" ".join(x) if isinstance(x, list) else x for x in pa or []]
                    gl = [g for g in (_author_clean(x) for x in ga or []) if g]
                    d["content_wrong"] = True
                    d["kind"] = ("other side empty" if not pa else
                                 f"author count {len(gl)} vs {len(pj)}" if len(gl) != len(pj) else
                                 content_kind(" | ".join(gl), " | ".join(pj),
                                              [r.get(k) for k in REF_FIELDS], [m.get(k) for k in REF_FIELDS]))
                    acc["P9.authors kinds"][d["kind"] if not d["kind"].startswith("author count") else "author count differs"] += 1
                diffs.append(d)
        gv_source = None
        for k in REF_FIELDS:
            if k in skip or (r.get(k) is None and m.get(k) is None):
                continue
            pv = m.get(k)
            if k in ("pages", "volume") and pv is not None and digits(pv) and digits(pv) in others:
                acc["P9." + k]["pred_is_other_number"] += 1           # a printed number the key files elsewhere
                continue
            if k == "source" and pv and r.get("source"):
                # keys rev 2: the key's source is the bare journal / publisher / university; the pipeline's source is
                # right when it equals that or the key's source_as_printed, or when what it holds beyond the source
                # is only the key's place / series / publisher (not an error)
                extras = [x for x in list(r.get("place") or []) + [r.get("series"), r.get("publisher")] if x]
                F, G = fold(pv), fold(r.get("source"))
                if extras and G and G in F:
                    rest = F.replace(G, " ", 1)
                    for x in sorted(extras, key=lambda x: -len(fold(x))):
                        rest = rest.replace(fold(x), " ", 1)
                    if not rest.strip():
                        acc["P9.source"]["right_with_place_series_publisher"] += 1
                        pv = r.get("source")
                elif r.get("source_as_printed") and _eq3(r["source_as_printed"], pv)[2] and not _eq3(r["source"], pv)[2]:
                    acc["P9.source"]["right_as_source_as_printed"] += 1
                    gv_source = r["source_as_printed"]          # score against the printed form
            if k == "title" and pv:                                    # the key keeps «ط2», '(in Arabic)' ... apart
                for np_ in r.get("notes_printed") or []:
                    pv = ws(pv.replace(np_, " ")) if np_ else pv
            ctx = ([r.get(x) for x in REF_FIELDS if x != k] + list(r.get("authors") or []),
                   [m.get(x) for x in REF_FIELDS if x != k])
            xf = None
            if k == "year":
                xf = lambda g, c: digits(g) != "" and digits(g) == digits(c)          # '1994a' = '1994'
            gv = gv_source if k == "source" and gv_source is not None else r.get(k)
            _field(acc, diffs, tt, f"P9.{k}", gv, pv, kind="text", ctx=ctx, cands=alts.get(k), ci=ci,
                   partial=edge, extra_folded=xf)
        # diagnostics (keys rev 2): publisher and place, where the key has them and the pipeline holds such a field
        if r.get("publisher") and "_publisher" in m:
            _field(acc, diffs, tt, "P9.publisher", r.get("publisher"), m.get("_publisher"), ctx=([r.get("source")], [m.get("source")]))
        if r.get("place") and "_place" in m:
            acc["P9.place"]["n"] += 1
            pf = fold(m.get("_place") or "")
            acc["P9.place"]["ok"] += bool(pf) and all(fold(x) in pf for x in r["place"])
        if r.get("pages") and "pages" not in skip and not (m.get("pages") and digits(m.get("pages")) in others):
            ok = page_set(r.get("pages")) == page_set(m.get("pages"))
            acc["P9.pages_as_numbers"]["n"] += 1; acc["P9.pages_as_numbers"]["ok"] += ok
            if not ok:
                diffs.append(dict(tt, measure="P9.pages_as_numbers", gold=r.get("pages"), pred=m.get("pages"),
                                  content_wrong=True, kind="other side empty" if not m.get("pages") else "numbers differ"))
        if r.get("type") is not None and "type" not in skip:
            ok = r.get("type") == {"confproc": "conference"}.get(m.get("type"), m.get("type"))
            acc["P9.type"]["n"] += 1; acc["P9.type"]["ok"] += ok
    acc["P9.boundaries"]["pred_refs"] += len(pr)


def compare_sect(gold, pred, acc, diffs, tag):
    ph = list(pred.get("headings") or [])
    for h in gold.get("headings") or []:
        m = next((x for x in ph if x.get("page") == h.get("page") and set(x.get("lines") or []) & set(h.get("lines") or [])), None)
        acc["P5"]["gold"] += 1
        if not m:
            diffs.append(dict(tag, measure="P5.found", gold=h, pred=None))
            continue
        ph.remove(m)
        acc["P5"]["found"] += 1
        acc["P5"]["level_ok"] += h.get("level") == m.get("level")
        if h.get("level") != m.get("level"):
            diffs.append(dict(tag, measure="P5.level", page=h.get("page"), lines=h.get("lines"), gold=h.get("level"), pred=m.get("level")))
    acc["P5"]["invented"] += len(ph)
    for x in ph:
        diffs.append(dict(tag, measure="P5.invented", gold=None, pred=x))


# ================================================================================================ running a part
def new_acc():
    return C.defaultdict(C.Counter, P1_conf=C.Counter(), P1_ok=C.Counter(), P1_not_text=C.Counter())


PARTS = {
    "PAGE": (compare_page, lambda k: pipeline_page(k["stem"], int(k["page"]))),
    "FRONT": (compare_front, lambda k: pipeline_front(k["stem"])),
    "TAB": (compare_tab, lambda k: pipeline_tab(k["stem"], int(k["page"]))),
    "REFS": (compare_refs, lambda k: pipeline_refs(k["stem"], int(k["page"]))),
    "SECT": (compare_sect, lambda k: pipeline_sect(k["stem"])),
}


def _is_eval_file(part, k):
    if not isinstance(k, dict) or k.get("stem") not in BY_STEM:
        return False
    if part in ("PAGE", "TAB", "REFS"):
        return "page" in k
    return True


def run_part(part, gold_files, pred_files=None):
    """Compare every gold file with its pred (the pipeline, or the other key).  -> (acc, diffs, counts)"""
    cmp, pipe = PARTS[part]
    acc, diffs = new_acc(), []
    cnt = C.Counter()
    for name, g in sorted(gold_files.items()):
        if not _is_eval_file(part, g):
            cnt["not_an_exam_file"] += 1
            continue
        if file_left_out(g):
            cnt["file_left_out_unsure_or_defect"] += 1
            continue
        if pred_files is None:
            try:
                p = pipe(g)
            except Exception as e:                        # noqa: BLE001
                cnt["pipeline_conversion_error"] += 1
                diffs.append(dict(file=name, measure="error", error=f"{type(e).__name__}: {e}"))
                continue
        else:
            p = pred_files.get(name)
            if p is None:
                cnt["missing_in_other_key"] += 1
                continue
            if file_left_out(p):
                cnt["other_key_left_out"] += 1
                continue
        tag = dict(file=name, stem=g["stem"], **({"page": g["page"]} if "page" in g else {}))
        try:
            cmp(g, p, acc, diffs, tag)
            cnt["scored"] += 1
        except Exception as e:                            # noqa: BLE001
            cnt["compare_error"] += 1
            diffs.append(dict(tag, measure="error", error=f"{type(e).__name__}: {e}"))
    return acc, diffs, cnt


# ================================================================================================ summaries
def summarise(part, acc, cols_of=None):
    S = {}
    if part == "PAGE":
        conf, okc = acc["P1_conf"], acc["P1_ok"]
        n = sum(conf.values())
        ok = sum(okc.values())
        per = C.defaultdict(lambda: [0, 0])
        for (g, p), v in conf.items():
            per[g][0] += v
            per[g][1] += okc[(g, p)]
        ab = acc["P1_author_block"]
        if ab["n"]:
            per["author block (byline + affiliation)"] = [ab["n"], ab["ok"]]
        S["P1"] = dict(lines=n, accuracy=rate(ok, n),
                       per_role={r: dict(n=a, accuracy=rate(b, a), meets_90=(None if a < 30 else rate(b, a) >= 0.9)) for r, (a, b) in sorted(per.items(), key=lambda kv: -kv[1][0])},
                       confusion={f"{g} -> {p}": v - okc[(g, p)] for (g, p), v in sorted(conf.items(), key=lambda kv: -(kv[1] - okc[kv[0]])) if v - okc[(g, p)] > 0},
                       accepted_as_either={f"{g} -> {p}": okc[(g, p)] for (g, p) in conf if g != p and okc[(g, p)]},
                       key_not_text_lines_pipeline_put_in=dict(acc["P1_not_text"]))
        for k in ("P2", "P2_no_tables"):
            tp, fp, fn = acc[k]["tp"], acc[k]["fp"], acc[k]["fn"]
            pr, rc = rate(tp, tp + fp), rate(tp, tp + fn)
            S[k] = dict(tp=tp, fp=fp, fn=fn, precision=pr, recall=rc,
                        f1=None if not pr or not rc else round(2 * pr * rc / (pr + rc), 4))
        p3 = acc["P3"]
        S["P3"] = {ck: dict(pairs=p3[ck + "_pairs"], ok=p3[ck + "_ok"], share=rate(p3[ck + "_ok"], p3[ck + "_pairs"]),
                            tied_same_pipeline_piece=p3[ck + "_tied"], skipped=p3[ck + "_skipped"])
                   for ck in ("first", "first_body", "one", "two", "mixed")}
        p6 = acc["P6"]
        S["P6"] = dict(notes=p6["notes"], notes_right=rate(p6["notes_ok"], p6["notes"]),
                       notes_lines_right=rate(p6["notes_lines_ok"], p6["notes"]),
                       calls=p6["calls"], calls_found=rate(p6["calls_found"], p6["calls"]),
                       calls_linked_right=rate(p6["calls_linked"], p6["calls"]), pred_calls=p6["pred_calls"],
                       notes_right_without_label_to_compare=p6["notes_ok_no_label_to_compare"])
        S["R2_keyed"] = dict(text_lines=acc["R2k"]["text_lines"], lost=acc["R2k"]["lost"],
                             lost_share=rate(acc["R2k"]["lost"], acc["R2k"]["text_lines"]))
        return S
    if part == "SECT":
        p = acc["P5"]
        pred_total = p["found"] + p["invented"]
        return dict(P5=dict(gold_headings=p["gold"], found=rate(p["found"], p["gold"]),
                            invented=rate(p["invented"], pred_total), level=rate(p["level_ok"], p["found"])))
    for k, v in sorted(acc.items()):
        if k in ("P1_conf", "P1_ok", "P1_not_text") or not isinstance(v, C.Counter) or not v:
            continue
        if k.endswith(" kinds") or k == "P7.cell_kinds":
            S[k] = dict(v.most_common())
            continue
        if k == "P7.cell_tables_list":
            S[k] = {t: dict(content_wrong=a, different_text=b) for t, (a, b) in sorted(v.items(), key=lambda kv: -kv[1][0])}
            continue
        if k == "P7.cell_tables":
            S[k] = dict(n=v["n"], zero_content_wrong=rate(v["zero_content_wrong"], v["n"]),
                        zero_different_text=rate(v["zero_different_text"], v["n"]))
            continue
        if k in ("P7.rows_dropped", "P9.left_out"):
            S[k] = dict(v)
            continue
        if k == "P7.tabular_lists":
            S[k] = dict(n=v["n"], other_side_made_a_table=v["other_made_a_table"])
            continue
        if "exact" in v:
            S[k] = dict(n=v["n"], exact=rate(v["exact"], v["n"]), folded=rate(v["folded"], v["n"]))
            if "typo" in v:
                S[k]["exact_typography"] = rate(v["typo"], v["n"])
            if k == "P7.cells":
                S[k].update(content_wrong=rate(v["content_wrong"], v["n"]), misplaced=rate(v["misplaced"], v["n"]),
                            different_text=rate(v["different_text"], v["n"]),
                            counts=dict(exact=v["exact"], folded_only=v["folded"] - v["exact"], misplaced=v["misplaced"],
                                        different_text=v["different_text"], unsure_left_out=v["unsure_left_out"]))
        else:
            S[k] = dict(n=v["n"], share=rate(v["ok"], v["n"]))
        if "found" in v:
            S[k]["found"] = rate(v["found"], v["n"])
        for extra in ("pred_extra", "pred_refs", "pred_where_key_null", "pred_is_other_number", "matched_title_main",
                      "matched_full_title", "right_with_place_series_publisher", "right_as_source_as_printed"):
            if extra in v:
                S[k][extra] = v[extra]
    return S

# ================================================================================================ R1, settled
SETTLE = os.environ.get("EXP97_SETTLE") or f"{OUT}/reading/settle"
READING = os.environ.get("EXP97_READING") or f"{OUT}/reading"


def r1_fold(s):
    """R1 folded reading: digit sets alike, ٫ ٬ , ، . between digits alike, tashkeel and tatweel removed, whitespace
    collapsed (words are kept apart: word error needs them)."""
    s = (s or "").translate(_DIG).replace("\u0640", "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"(?<=\d)\s*[\u066b\u066c,\u060c.]\s*(?=\d)", ".", s)
    return ws(s)


def no_punct(s):
    return ws("".join(" " if unicodedata.category(ch)[0] in "PS" else ch for ch in s or ""))


def _errs(w, t):
    from common97 import lev
    return lev(w, t), len(t), lev(w.split(), t.split()), len(t.split())


def unrewrite(shown, truth, source):
    """The shown text with the pipeline's deliberate block rewrites undone, so what is left is reading: the dropped
    keyword label put back, «؛» back to «،», inserted '/ ' and '• ' taken out (TRIAGE 2.9)."""
    x = shown or ""
    t = truth or ""
    if source == "keywords":
        m = re.match(r"^\s*([^:]{2,40}:)\s*", t)
        if m and fold(m.group(1)) not in fold(x[: len(m.group(1)) + 5]):
            x = m.group(1) + " " + x
        if "\u061b" not in t:
            x = x.replace("\u061b", "\u060c")
    for mark in ("/", "\u2022"):
        if mark not in t:
            x = re.sub(r"\s*" + re.escape(mark) + r"\s*", " ", x)
    return ws(x)


def _shown_now(r):
    """The line's shown text under the current tiling (common97.tile_block, hyphen fix included)."""
    from common97 import shown_segment
    t = r.get("targets") or []
    if len(t) != 1:
        return r.get("shown")
    k, i = t[0].split(":", 1)
    try:
        return shown_segment(r["stem"], r["page"], r["line"], i if k == "block" else f"region:{i}")[0]
    except Exception:                                        # noqa: BLE001
        return r.get("shown")


def score_r1():
    """R1 letter / word error per witness from the blind readers' settlements: out/reading/settle/{A,B} and, where A
    and B disagreed, the third reader C.  C rows marked unreadable or unsure are left out; glyph_only rows count as
    settled; order_only rows (the stored order of mixed-direction text) are reported apart, not as wrong letters."""
    pa, pb = f"{SETTLE}/A/readings.jsonl", f"{SETTLE}/B/readings.jsonl"
    if not (os.path.exists(pa) and os.path.exists(pb) and os.path.exists(f"{READING}/lines.jsonl")):
        return None
    def load(p):
        out = {}
        if not os.path.exists(p):
            return out
        for x in open(p):
            x = x.strip()
            if x:
                try:
                    d = json.loads(x)
                    out[d["id"]] = d                         # the last line for an id wins (a resumed reader)
                except (ValueError, KeyError):
                    pass
        return out
    RA, RB, RC = load(pa), load(pb), load(f"{SETTLE}/C/readings.jsonl")
    disp = {d["id"]: d for d in map(json.loads, open(f"{READING}/disputes.jsonl"))}
    lines = {}
    for r in map(json.loads, open(f"{READING}/lines.jsonl")):
        lines[f"{r['stem']}_p{r['page']:03d}_l{r['line']:03d}"] = r
    use = {k: r for k, r in lines.items() if r.get("all_three_agree") is not None}       # the 598 three-witness lines
    for r in use.values():
        r["shown"] = _shown_now(r)
    W = ("azure", "shown", "t91")
    wit = lambda r, w: (r.get(w) or "").strip()
    truth, dis, pending, order_only, left_out_c = {}, [], C.Counter(), set(), C.Counter()
    for i, d in disp.items():
        a, b, c3 = RA.get(i), RB.get(i), RC.get(i)
        ok = lambda x: x and not x.get("unsure") and isinstance(x.get("printed"), str)
        ab_agree = ok(a) and ok(b) and ws(a["printed"]) == ws(b["printed"])
        if ab_agree:
            truth[i] = dict(exact=ws(a["printed"]), folded=r1_fold(ws(a["printed"])), by="A=B")
            continue
        rec = dict(id=i, stem=d["stem"], page=d["page"], line=d["line"], crop=d["crop"], control=d["control"],
                   candidates=d["candidates"], reader_A=(a or {}).get("printed"), reader_B=(b or {}).get("printed"),
                   A_unsure=bool(a and a.get("unsure")), B_unsure=bool(b and b.get("unsure")))
        if ok(a) and ok(b):
            fa, fb = r1_fold(ws(a["printed"])), r1_fold(ws(b["printed"]))
            rec.update(agree_after_folding=fa == fb, punctuation_only=no_punct(fa) == no_punct(fb), reason="readers differ")
        else:
            rec.update(reason="unsure or read by one reader only")
        if c3:
            rec.update(reader_C=c3.get("printed"), C_flags=[k for k in ("unreadable", "unsure", "glyph_only", "order_only") if c3.get(k)],
                       C_why=c3.get("why"))
            if c3.get("unreadable") or c3.get("unsure"):
                left_out_c["unreadable" if c3.get("unreadable") else "unsure"] += 1
                rec["settled"] = "left out (third reader: " + ("unreadable" if c3.get("unreadable") else "unsure") + ")"
            elif c3.get("order_only"):
                order_only.add(i)
                rec["settled"] = "order only: stored order of mixed-direction text"
            elif isinstance(c3.get("printed"), str):
                truth[i] = dict(exact=ws(c3["printed"]), folded=r1_fold(ws(c3["printed"])),
                                by="C (glyph only)" if c3.get("glyph_only") else "C")
                rec["settled"] = truth[i]["by"]
        elif ok(a) and ok(b) and rec.get("agree_after_folding"):
            truth[i] = dict(folded=r1_fold(ws(a["printed"])), by="A~B folded")
            rec["settled"] = "folded only"
        else:
            pending["unsure" if rec["A_unsure"] or rec["B_unsure"] else "not read by both"] += 1
            rec["settled"] = None
        dis.append(rec)
    os.makedirs(SETTLE, exist_ok=True)
    with open(f"{SETTLE}/disagreements.jsonl", "w") as f:
        for d in dis:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    disputed = [k for k in use if k in disp and not disp[k]["control"] and k not in order_only]
    controls = [k for k in use if k in disp and disp[k]["control"] and k not in order_only]
    agree = [k for k in use if use[k]["all_three_agree"]]
    out = dict(readers=dict(A=len(RA), B=len(RB), C=len(RC)), dispute_lines=len(disp), pending=dict(pending),
               readers_disagree=sum(1 for d in dis if d["reason"] == "readers differ"),
               readers_disagree_punctuation_only=sum(1 for d in dis if d.get("punctuation_only") and d["reason"] == "readers differ"),
               settled_by_third_reader=sum(1 for v in truth.values() if v["by"].startswith("C")),
               left_out_by_third_reader=dict(left_out_c),
               order_only_lines=len(order_only),
               order_only_note="stored order of mixed-direction text (a sign or Latin run on the other side): reported apart, not wrong letters",
               lines_598=len(use), disputed_in_598=len(disputed), controls_in_598=len(controls), all_agree_in_598=len(agree))
    for mode in ("exact", "folded", "folded_no_punct"):
        get_t = lambda i: (truth.get(i) or {}).get("exact" if mode == "exact" else "folded")
        tf = (lambda x: x) if mode == "exact" else (r1_fold if mode == "folded" else (lambda x: no_punct(r1_fold(x))))
        tt = (lambda x: x) if mode != "folded_no_punct" else no_punct
        ce = cl = cwe = cwl = 0
        n_ctrl = n_ctrl_wrong = 0
        for k in controls:
            t = get_t(k)
            if t is None:
                continue
            le, ll, we, wl = _errs(tf(wit(use[k], "azure")), tt(t))
            ce += le; cl += ll; cwe += we; cwl += wl
            n_ctrl += 1; n_ctrl_wrong += le > 0
        rc, rcw = (ce / cl if cl else 0.0), (cwe / cwl if cwl else 0.0)
        L_agree = sum(len(tf(wit(use[k], "azure"))) for k in agree)
        Wd_agree = sum(len(tf(wit(use[k], "azure")).split()) for k in agree)
        M = dict(control_lines_settled=n_ctrl, control_lines_wrong=n_ctrl_wrong, control_letter_error=round(rc, 5),
                 control_word_error=round(rcw, 5))
        texts = {}
        for k in disputed:
            t = get_t(k)
            r = use[k]
            texts[k] = dict(azure=wit(r, "azure"), shown=wit(r, "shown"), t91=wit(r, "t91"),
                            shown_no_rewrites=unrewrite(wit(r, "shown"), t if t is not None else "", r.get("shown_source")))
        rewrite_letters = 0
        for w in W + ("shown_no_rewrites",):
            le = ll = we = wl = 0
            n = nw = 0
            Lproxy = Wproxy = 0
            for k in disputed:
                Lproxy += len(tf(wit(use[k], "azure")))
                Wproxy += len(tf(wit(use[k], "azure")).split())
                t = get_t(k)
                if t is None:
                    continue
                a_, b_, c_, d_ = _errs(tf(texts[k][w]), tt(t))
                le += a_; ll += b_; we += c_; wl += d_
                n += 1; nw += a_ > 0
            rl, rw = (le / ll if ll else None), (we / wl if wl else None)
            est_l = None if rl is None else (rl * Lproxy + rc * L_agree) / max(1, Lproxy + L_agree)
            est_w = None if rw is None else (rw * Wproxy + rcw * Wd_agree) / max(1, Wproxy + Wd_agree)
            M[w] = dict(settled_disputed_lines=n, of_disputed=len(disputed), lines_wrong=nw, letters_wrong=le,
                        letter_error_on_settled=None if rl is None else round(rl, 5),
                        word_error_on_settled=None if rw is None else round(rw, 5),
                        letter_error_598_est=None if est_l is None else round(est_l, 5),
                        word_error_598_est=None if est_w is None else round(est_w, 5))
        M["rewrite_letters"] = M["shown"]["letters_wrong"] - M["shown_no_rewrites"]["letters_wrong"]
        M["rewrite_note"] = "deliberate rewrites of the print (letters): keyword label dropped, «،»→«؛», '/ ' and '• ' inserted"
        # what the pipeline's fixes are worth: the shown text against Azure's raw line, line by line
        for key, w in (("shown_vs_azure", "shown"), ("shown_vs_azure_no_rewrites", "shown_no_rewrites")):
            cmpc = C.Counter()
            for k in disputed:
                t = get_t(k)
                if t is None or not texts[k]["shown"]:
                    continue
                ea = _errs(tf(texts[k]["azure"]), tt(t))[0]
                es = _errs(tf(texts[k][w]), tt(t))[0]
                cmpc["shown better" if es < ea else "shown worse" if es > ea else "same"] += 1
            M[key] = dict(cmpc)
        out[mode] = M
    return out


# ================================================================================================ scorecard text
def pct(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def lab_extra(v):
    v = v or {}
    x = [f"found {pct(v['found'])}" for _ in [0] if v.get("found") is not None]
    x += [f"+{v['pred_where_key_null']} where key has none" for _ in [0] if v.get("pred_where_key_null")]
    x += [f"+{v['pred_extra']} extra" for _ in [0] if v.get("pred_extra")]
    return ("; " + "; ".join(x)) if x else ""


def _g(d, *ks):
    for k in ks:
        d = (d or {}).get(k) if isinstance(d, dict) else None
    return d


def _val(d):
    if not d:
        return "–"
    if "share" in d:
        return pct(d.get("share"))
    if d.get("exact_typography") is not None:
        return f"{pct(d.get('exact'))} / {pct(d.get('exact_typography'))} / {pct(d.get('folded'))}"
    return f"{pct(d.get('exact'))} / {pct(d.get('folded'))}"


# what a miss of each measure means, in plain words (from the triage, out/triage/TRIAGE.md)
MISS_MEANS = [
    ("R1 three witnesses", "nothing by itself: lines where the three readings differ go to the blind readers"),
    ("R1 shown, block rewrites removed", "a reading error (letters printed otherwise than stored)"),
    ("R1 deliberate rewrites", "deliberate rewrite of the print (keyword label dropped, ، → ؛, inserted / and •)"),
    ("R1 shown vs Azure", "where the pipeline's own corrections help or hurt"),
    ("R1 stored order", "formatting only: the stored order of mixed-direction text, not wrong letters"),
    ("R1 readers", "work left for a reader, not a pipeline error"),
    ("R1", "a reading error (for 'shown' as stored: reading errors plus deliberate rewrites)"),
    ("R2", "text lost or stored twice (wrong join)"),
    ("P1 author block", "wrong label"),
    ("P1", "wrong label (mostly list items stored as paragraphs, page numbers inside the running head)"),
    ("P2", "wrong join: lines of one piece split, or of two pieces merged"),
    ("P3 order, first pages (all", "nothing about reading: front matter is stored in a logical order by design (diagnostic)"),
    ("P3", "wrong order of pieces"),
    ("P6 notes", "wrong join (note lines) or wrong label (note number)"),
    ("P6 calls", "wrong link between a call mark and its note"),
    ("P4.authors_no_honorific", "reading error or wrong field boundary in a name"),
    ("P4.affiliation", "dropped (affiliation stored for one script only) or wrong field boundary"),
    ("P4.abstract", "wrong join: abstract cut short or run on (often dash items left out)"),
    ("P4.keywords", "wrong join (list not split on printed separators) or reading error"),
    ("P4.date", "dropped (date line at the end of the article not extracted)"),
    ("P4.last_printed", "deliberate rule (lpage counts a trailing English page)"),
    ("P4", "exact miss = formatting only or deliberate rewrite; folded miss = reading error or wrong field boundary"),
    ("P5", "wrong label (heading not found / invented) or wrong level"),
    ("P7.found", "table missed (cannot fail here: table pages were picked where the pipeline found tables)"),
    ("P7.shape", "wrong join: rows or columns merged / split"),
    ("P7.continuation", "continuation not marked (barely can fail: the pipeline never links tables across pages)"),
    ("P7.continues_next", "the pipeline never links a table to the next page"),
    ("P7.cells (a)", "formatting only (digit set, decimal mark, sign position) unless (b) misses too"),
    ("P7.cells (c1)", "wrong join: a cell's text in another cell (shifted row, lost merge span)"),
    ("P7.cells (c2)", "reading error (or a dropped symbol)"),
    ("P7.cells", "see (a)-(d): formatting / wrong join / reading error"),
    ("P7.tabular", "a borderless list made into a table (wrong label)"),
    ("P7", "wrong label or wrong join of a table's caption / number / header"),
    ("P8", "figure missed or caption not attached"),
    ("P9.boundaries", "wrong join: one reference split or two merged"),
    ("P9.pages", "exact miss = formatting only (en dash → hyphen); numbers miss = wrong field or parse"),
    ("P9.type", "wrong label (reference type)"),
    ("P9.publisher", "diagnostic: publisher not stored, or stored inside the source"),
    ("P9.place", "diagnostic: place not stored, or stored inside the source"),
    ("P9", "exact miss = formatting only (typography, small caps); folded miss = wrong field boundary or reading error"),
]


def miss_means(label):
    for k, v in MISS_MEANS:
        if label.startswith(k):
            return v
    return ""


def _pass(value_cell, mark):
    """'pass' / 'miss' / '' from the pipeline cell and the pass mark (the first number of each)."""
    m = re.match(r"\s*(>=|<=)\s*([\d.]+)%", mark or "")
    v = re.match(r"\s*([\d.]+)%", value_cell or "")
    if not m or not v:
        return ""
    x, y = float(v.group(1)), float(m.group(2))
    ok = x >= y if m.group(1) == ">=" else x <= y
    res = "pass" if ok else "miss"
    if not ok and value_cell.count("%") >= 2:              # x / (y /) z: say whether the folded score passes
        z = float(re.findall(r"([\d.]+)%", value_cell)[-1])
        if (z >= y if m.group(1) == ">=" else z <= y):
            res = "miss (folded: pass)"
    return res


def md_rows(sc):
    """(measure, pipeline, A vs B, pass mark, key state, what a miss means, pass?)"""
    P, Pc = sc["parts"], sc["ceiling"]
    ks = lambda part: (sc["inputs"].get(part) or {}).get("key_source", "–")
    rows = []
    r1, r2, r1s = sc.get("R1") or {}, sc.get("R2") or {}, sc.get("R1_settled") or {}
    rows.append(("R1 three witnesses agree (598 lines)", pct(r1.get("all_three_agree_rate")), "–", "(no mark: sorting only)", "no key needed"))
    for mode, lab in (("exact", "exact"), ("folded", "folded"), ("folded_no_punct", "folded, punctuation ignored")):
        M = r1s.get(mode) or {}
        for w, wl in (("shown_no_rewrites", "shown, block rewrites removed"), ("shown", "shown as stored"),
                      ("azure", "Azure raw line"), ("t91", "t91 reader")):
            m = M.get(w) or {}
            if m:
                lbl = (f"R1 {wl}: letters / words wrong, {lab}" if w != "shown_no_rewrites" else
                       f"R1 shown, block rewrites removed: letters / words wrong, {lab}")
                rows.append((f"{lbl} (598 est.; settled {m['settled_disputed_lines']}/{m['of_disputed']} disputed)",
                             f"{pct(m['letter_error_598_est'])} / {pct(m['word_error_598_est'])}", "–",
                             f"{PASS['R1.letters']}, {PASS['R1.words']}" if w.startswith("shown") else "(witness)",
                             "blind readers A, B, third reader C" + ("" if m['settled_disputed_lines'] == m['of_disputed'] else "; PARTIAL")))
        if M.get("rewrite_letters") is not None:
            rows.append((f"R1 deliberate rewrites of the print (letters), {lab}, settled disputed lines", str(M["rewrite_letters"]), "–",
                         "(reported apart)", "blind readers"))
        for key, lb in (("shown_vs_azure", "as stored"), ("shown_vs_azure_no_rewrites", "rewrites removed")):
            if M.get(key):
                sv = M[key]
                rows.append((f"R1 shown vs Azure raw ({lb}), {lab}, settled disputed lines",
                             f"better {sv.get('shown better', 0)}, worse {sv.get('shown worse', 0)}, same {sv.get('same', 0)}",
                             "–", "(what the pipeline's fixes are worth)", "blind readers"))
    if r1s:
        rows.append(("R1 stored order of mixed-direction text (lines, reported apart)", str(r1s.get("order_only_lines")), "–", "(not wrong letters)", "third reader C"))
        rows.append(("R1 readers: lines left out (unreadable / unsure)", str(r1s.get("left_out_by_third_reader")), "–",
                     f"pending {r1s.get('pending')}", "third reader C"))
    rows.append(("R2 lines lost (mechanical)", pct(r2.get("lost_share")), "–", PASS["R2.lost"], "no key needed"))
    rows.append(("R2 lines doubled (mechanical)", pct(r2.get("doubled_share")), "–", PASS["R2.doubled"], "no key needed"))
    PG = lambda *k: (pct(_g(P, "PAGE", *k)), pct(_g(Pc, "PAGE", *k)))
    for lab, k, mark in [
        ("R2 key text lines lost (keyed)", ("R2_keyed", "lost_share"), PASS["R2.lost"]),
        ("P1 role per line (accept-either rulings applied)", ("P1", "accuracy"), PASS["P1.overall"]),
        ("P1 author block (byline + affiliation)", ("P1", "per_role", "author block (byline + affiliation)", "accuracy"), "(reported apart)"),
        ("P2 same-piece F1", ("P2", "f1"), PASS["P2.f1"]),
        ("P2 same-piece F1, tables left out", ("P2_no_tables", "f1"), "(diagnostic)"),
        ("P3 order, one column (not first pages)", ("P3", "one", "share"), PASS["P3.one_column"]),
        ("P3 order, two columns (not first pages)", ("P3", "two", "share"), PASS["P3.two_column"]),
        ("P3 order, mixed pages", ("P3", "mixed", "share"), "(reported apart)"),
        ("P3 order, first pages, body pieces", ("P3", "first_body", "share"), "(reported apart)"),
        ("P3 order, first pages (all pieces)", ("P3", "first", "share"), "(diagnostic: front matter stored in logical order)"),
        ("P6 notes right (lines + label)", ("P6", "notes_right"), PASS["P6.notes"]),
        ("P6 calls linked right", ("P6", "calls_linked_right"), PASS["P6.calls"]),
    ]:
        rows.append((lab, *PG(*k), mark, ks("PAGE")))
    ab_fail = [r for r, v in (_g(P, "PAGE", "P1", "per_role") or {}).items() if v.get("meets_90") is False]
    rows.append(("P1 roles with >= 30 lines under 90%", ", ".join(ab_fail) or "none", "–", PASS["P1.per_role"], ks("PAGE")))
    for k, mark in [("P4.title", PASS["P4.title"]), ("P4.authors", PASS["P4.authors"]), ("P4.authors_no_honorific", PASS["P4.authors"]),
                    ("P4.affiliation", PASS["P4.other"]), ("P4.affiliation_with_position", "(diagnostic)"),
                    ("P4.abstract", PASS["P4.other"]), ("P4.keywords", PASS["P4.other"]), ("P4.keyword_items", "(diagnostic)"),
                    ("P4.date_received", PASS["P4.other"]), ("P4.date_accepted", PASS["P4.other"]), ("P4.date_published", PASS["P4.other"]),
                    ("P4.doi", PASS["P4.other"]), ("P4.first_printed_page_number", PASS["P4.other"]),
                    ("P4.last_printed_page_number", PASS["P4.other"]), ("P4.article_language", "(diagnostic)")]:
        v, c = _g(P, "FRONT", k), _g(Pc, "FRONT", k)
        if v or c:
            kinds = _g(P, "FRONT", k + " kinds")
            rows.append((f"{k} exact / typography / folded (n={(v or {}).get('n')}{lab_extra(v)})" + (f"; still wrong after folding: {kinds}" if kinds else ""),
                         _val(v), _val(c), mark, ks("FRONT")))
    for lab, k, mark in [("P5 headings found", "found", PASS["P5.found"]), ("P5 headings invented", "invented", PASS["P5.invented"]),
                         ("P5 level right", "level", PASS["P5.level"])]:
        rows.append((lab, pct(_g(P, "SECT", "P5", k)), pct(_g(Pc, "SECT", "P5", k)), mark, ks("SECT")))
    for k, mark in [("P7.found", PASS["P7.found"]), ("P7.shape", PASS["P7.shape"]), ("P7.header_rows", "(no mark)"),
                    ("P7.caption", "(no mark)"), ("P7.number", "(no mark)"), ("P7.continuation", PASS["P7.continuation"]),
                    ("P7.continues_next", "(diagnostic)")]:
        v, c = _g(P, "TAB", k) or {}, _g(Pc, "TAB", k) or {}
        if v or c:
            rows.append((f"{k} (n={v.get('n')}{lab_extra(v)})", _val(v), _val(c), mark, ks("TAB")))
    v, c = _g(P, "TAB", "P7.cells") or {}, _g(Pc, "TAB", "P7.cells") or {}
    if v or c:
        cn = lambda d, k: pct(d.get(k)) if d else "–"
        rows += [
            (f"P7.cells (a) exact (n={v.get('n')}; unsure cells left out: {(v.get('counts') or {}).get('unsure_left_out')}; empty rows dropped: {_g(P, 'TAB', 'P7.rows_dropped')})", cn(v, "exact"), cn(c, "exact"), PASS["P7.cells"], ks("TAB")),
            ("P7.cells (b) folded (digit sets, decimal marks, spaces, tashkeel, sign position, bullets)", cn(v, "folded"), cn(c, "folded"), PASS["P7.cells"], ks("TAB")),
            ("P7.cells (c) content wrong after folding", cn(v, "content_wrong"), cn(c, "content_wrong"), "(lower is better)", ks("TAB")),
            ("P7.cells (c1) of which misplaced / structure", cn(v, "misplaced"), cn(c, "misplaced"), "(structure, not reading)", ks("TAB")),
            ("P7.cells (c2) of which different text", cn(v, "different_text"), cn(c, "different_text"), "(reading)", ks("TAB")),
        ]
        vt, ct = _g(P, "TAB", "P7.cell_tables") or {}, _g(Pc, "TAB", "P7.cell_tables") or {}
        rows.append((f"P7.cells (d) tables with no content-wrong cell (n={vt.get('n')})", pct(vt.get("zero_content_wrong")),
                     pct(ct.get("zero_content_wrong")), "(per table)", ks("TAB")))
        rows.append(("P7.cells (d) tables with no different-text cell", pct(vt.get("zero_different_text")),
                     pct(ct.get("zero_different_text")), "(per table)", ks("TAB")))
    for k, mark in [("P7.tabular_lists", "(borderless lists: not tables)"), ("P8.found", PASS["P8.found"]), ("P8.caption", "(no mark)")]:
        v, c = _g(P, "TAB", k) or {}, _g(Pc, "TAB", k) or {}
        if k == "P7.tabular_lists" and (v or c):
            rows.append((f"P7.tabular lists the other side made a table of (n={v.get('n')})", str(v.get("other_side_made_a_table")),
                         str(c.get("other_side_made_a_table")), mark, ks("TAB")))
        elif v or c:
            rows.append((f"{k} (n={v.get('n')}{lab_extra(v)})", _val(v), _val(c), mark, ks("TAB")))
    for k in ("P9.boundaries", "P9.authors", "P9.year", "P9.title", "P9.source", "P9.volume", "P9.issue",
              "P9.pages_as_numbers", "P9.pages", "P9.type", "P9.publisher", "P9.place"):
        v, c = _g(P, "REFS", k) or {}, _g(Pc, "REFS", k) or {}
        if v or c:
            kinds = _g(P, "REFS", k + " kinds")
            mark = PASS["P9.boundaries"] if k == "P9.boundaries" else ("(diagnostic)" if k in ("P9.type", "P9.publisher", "P9.place") else PASS["P9.fields"])
            name = {"P9.pages_as_numbers": "P9.pages as printed numbers (headline pages measure)",
                    "P9.pages": "P9.pages text exact / typography / folded (diagnostic)"}.get(k, k + (" exact / typography / folded" if "exact" in v else ""))
            if k == "P9.pages":
                mark = "(diagnostic)"
            rows.append((f"{name} (n={v.get('n')}{lab_extra(v)})" + (f"; still wrong after folding: {kinds}" if kinds else ""),
                         _val(v), _val(c), mark, ks("REFS")))
    return [r + (miss_means(r[0]), _pass(r[1], r[3])) for r in rows]


def write_md(sc, path):
    head = (f"**{sc['banner']}**" if sc.get("all_final") else f"**NOT FINAL.** {sc['status']}")
    L = ["# Experiment 97 scorecard", "", head, "",
         f"Scored {sc['made']}. Key state per part:", ""]
    for p, v in sc["inputs"].items():
        L.append(f"- **{p}**: {v['key_source']}; {v['counts'].get('scored', 0)} files scored"
                 + (f", {v['counts'].get('file_left_out_unsure_or_defect')} left out (unsure / image_defect / multiple_works)"
                    if v['counts'].get('file_left_out_unsure_or_defect') else ""))
    L += ["",
          "Pipeline = release R20261104T151029 (out/cache, copied read-only by extract97.py). "
          "A vs B = key A scored against key B with the same measure (the agreement ceiling; files both have). "
          "Three numbers `x / y / z` = exact (trimmed, trailing separators stripped) / typography-folded exact (quotes, "
          "apostrophes, dashes alike) / folded (no diacritics, tatweel, punctuation; digits to ASCII). "
          "Table cells use their own four-way report (P7.cells a-d). 'Pass?' judges the first number against the mark.", "",
          "| Measure | Pipeline | Key A vs key B | Pass mark | Pass? | What a miss means | Key state used |",
          "|---|---|---|---|---|---|---|"]
    for r in md_rows(sc):
        m, pv, cv, mark, key, means, ok = r
        L.append("| " + " | ".join(str(x).replace("|", "/") for x in (m, pv, cv, mark, ok, means, key)) + " |")
    L += ["", "## Limits of this exam", ""] + [f"- {x}" for x in sc.get("limits") or []]
    page = sc["parts"].get("PAGE") or {}
    if page.get("P1"):
        L += ["", "## P1 per key role", "", "| Key role | Lines | Pipeline right | ≥ 90% (roles with ≥ 30 lines) |", "|---|---|---|---|"]
        for r, v in page["P1"]["per_role"].items():
            L.append(f"| {r} | {v['n']} | {pct(v['accuracy'])} | {'–' if v['meets_90'] is None else ('yes' if v['meets_90'] else 'no')} |")
        L += ["", "## P1 confusion (key role -> pipeline role, wrong lines only)", "", "| Key -> pipeline | Lines |", "|---|---|"]
        for k, v in list(page["P1"]["confusion"].items())[:40]:
            L.append(f"| {k} | {v} |")
        if page["P1"].get("accepted_as_either"):
            L += ["", "Accepted under the rulings (key role -> pipeline role, lines): " +
                  ", ".join(f"{k} {v}" for k, v in page["P1"]["accepted_as_either"].items())]
    tab = sc["parts"].get("TAB") or {}
    if tab.get("P7.cell_tables_list"):
        L += ["", "## P7 tables carrying content-wrong cells (pipeline)", "", "| Table | Content wrong | Of which different text |", "|---|---|---|"]
        for t, v in tab["P7.cell_tables_list"].items():
            L.append(f"| {t} | {v['content_wrong']} | {v['different_text']} |")
        L += ["", "Cell kinds: " + ", ".join(f"{k} {v}" for k, v in (tab.get("P7.cell_kinds") or {}).items())]
    L += ["", "## Role mapping used (pipeline -> key role)", "", "| Pipeline | Key role |", "|---|---|"]
    for k, v in BLOCK_ROLE_TO_KEY.items():
        L.append(f"| block `{k}` | {v} |")
    for k, v in REGION_ROLE_TO_KEY.items():
        L.append(f"| page region `{k}` | {v} |")
    L.append(f"| no line_map row | {NO_BLOCK} |")
    L += ["", "## Notes on interpretation", ""] + [f"- {x}" for x in sc["interpretation"]]
    L += ["", "Files: A/B disagreements for the adjudicator `out/scores/disagreements_<PART>.jsonl`; every pipeline miss "
          "`pipeline_misses_<PART>.jsonl`; cells wrong after folding `cells_content_wrong.jsonl` (A vs B: `_AvsB`); fields "
          "wrong after folding `fields_content_wrong_<PART>.jsonl`; R1 reader disagreements `out/reading/settle/disagreements.jsonl`."]
    open(path, "w").write("\n".join(L) + "\n")


LIMITS = [
    "Table, reference and note pages were picked where the pipeline had found a table, a reference or a note (sample97.py): "
    "P7.found cannot fail, and P9 boundaries and P6 are biased upward. The random body page is the unbiased sample.",
    "P7.continuation can barely fail: the pipeline never marks or links a continued table, and an always-'no' answer scores "
    "the share of tables that are not continued.",
    "P3 on first pages over all pieces compares blocks.ord, a logical order by design; only the body-piece number is a reading-order test.",
    "The keyers saw Azure's lines: where Azure 'corrects' the print and a keyer accepted it, key and pipeline share the error unseen "
    "(R1's all-agree lines carry the same risk).",
    "Six articles each come from seven journals: one journal's habit moves a measure (0246 gives most date and lpage misses; two "
    "articles give most wrong cells and 49 P1 ref lines). The effective sample is nearer the number of journals than 60 articles.",
    "Exact scores mostly measure typography policy (’/–, small caps, trailing separators); typography-folded and folded scores are "
    "the ones that measure reading and joining.",
    "The per-role P1 mark (>= 90% on roles with >= 30 lines) is driven by two or three articles for verse, quote and front matter.",
]


INTERPRETATION = [
    "Round 3 (TRIAGE.md section 2, 2026-11-10): title language from the title's own letters; affiliation right when the key equals any stored form (a row, position + row with ' ', '، ' or ', ', all rows joined, the position) or, folded, ends with a stored row after a prefix >= 0.6 like a stored position; abstracts join every printed row of a language in seq order; dates take the most precise non-catalogue row.",
    "Round 3: exact = whitespace collapsed and trailing separators stripped (titles also ignore the key's ' : ' joiner); a third 'typography-folded exact' maps ’ ‘ ` → ', “ ” → \", – — → -, › → >.",
    "Round 3 P6: a note continued from the previous page with no printed label is not compared on its label; a call's link is judged by the lines of its target note on the page, or by the target's label when the note is on another page; notes are footnote / endnote pieces, pieces with `carries`, and first-page affiliation pieces with a note label, on both sides (so the A vs B ceiling follows the rulings too); a call's `label_also_ok` labels are accepted.",
    "Round 3 P7: rows with no text are dropped on each side before shape and cells (a printed spacer row); a trailing other-side row holding only the key's table note is dropped; table numbers are read whole ('3-3'); cell folding drops □ ▪ ■ • ◦ ● bullets.",
    "Round 3 P9: conference source = conf_name; a journal's source_title is never moved into the title; a thesis' source = publisher (its tail after a comma also accepted); authors fall back to editors, honorifics and et al. / وآخرون are taken off both sides, and joins without the space after the comma are tried; year folded = its digits; pages fall back to cited_pages, and the headline pages measure compares the printed numbers as a set without reordering; the key's notes_printed are removed from the pipeline title; merged_in_print references are left out (boundary and fields); a pipeline pages / volume value listed in the key's other_numbers is not counted (pred_is_other_number); small_caps references compare case-insensitively; a reference cut by the page edge accepts the key's value as a prefix or suffix; 'lines' in unsure_fields leaves the boundary out.",
    "Round 3 P3: first pages are scored over body pieces only (first_body); the old all-pieces number stays as 'first', a diagnostic.",
    "Round 3 R1: the third reader C settles lines where A and B differ (unreadable / unsure rows left out, glyph_only counts as settled, order_only reported apart as the stored order of mixed-direction text); the shown text is scored as stored and with the block rewrites undone (keyword label put back, ؛ → ،, inserted '/ ' and '• ' removed), and the difference is reported as deliberate rewrites; the shown text is re-cut with the hyphen fix (common97.tile_block cuts after a stored end-of-line hyphen, else keeps the joined word with its first line).",
    "A table's cell blocks (blocks.role = table-cell, one block per cell; their table comes from table_cells.block_id) are one pipeline piece per table, since the key keeps a whole table as one piece.",
    "An Azure line with several line_map rows (a table row spread over cells, a merged line) takes its first row's target for P1-P3; R2 counts it as doubled.",
    "P1 rulings (KEYER_RULES, 2026-11-10): a piece with label_of accepts heading or the labelled role; a footnote with carries accepts footnote / affiliation / front-matter; table_note accepts other / caption / paragraph / footnote; either_ok lists accepted roles; key byline and affiliation accept the pipeline's front-matter or byline (reported together as 'author block'). Key vs key, a line is also right when the key's role is one the other key's piece accepts.",
    "P3: running heads and page numbers are left out; first pages are reported apart; page regions (no reading position) are skipped.",
    "Lines in noise / showThrough / pictureJunk / ornament regions count as the pipeline saying 'not text'.",
    "Left out: pieces, tables, references marked unsure, image_defect or multiple_works; whole files marked image_defect or multiple_works, or marked unsure while none of their items is (a page-level unsure that only says 'some piece is unsure' leaves out those pieces, not the page); fields in unsure_fields (file or reference); cells in unsure_cells.",
    "P6: a note is right when the pipeline has a footnote/endnote piece with exactly the key's lines on the page AND the same label (digit sets folded, brackets ignored). A call is found when the pipeline has a call with the same label on the same Azure line (the call's char_offset is placed on a line through common97.tile_block); linked when its note_call_targets note has that label.",
    "P4: titles from metadata_assertions (is_chosen = 1; + ' : ' + subtitle only when the title does not already hold it); authors from byline_mentions, matched to the key's `printed` by `printed`, `name_text` or `titles name_text`, and scored again with honorifics off both sides; affiliations from affiliation_mentions.printed (job title is in byline_mentions.position, so P4.affiliation_with_position adds it); abstracts: first/last words as prefix/suffix of the pipeline's whole abstract; keywords from publication_keywords (source 'masters' when present); dates from publication_dates.printed, derivation not 'catalogue'; page numbers from the chosen fpage / lpage (digits compared).",
    "P7: tables matched one-to-one by their Azure line sets (the key's `lines`), +1 when the printed numbers agree. figures.label is empty for every table, so the pipeline's number is the first number in its caption; the pipeline has no 'continued' flag, so a table counts as a continuation on a page when its cell blocks start on an earlier page. caption_on_previous_page does not change the key's continuation flag. Pipeline column order is read from the cell blocks' x and mirrored when the key's direction differs. Header rows = leading rows with an is_header cell. A pipeline table over a key `tabular_lists` entry is not counted as extra.",
    "P7 cells: (a) exact after trimming; (b) folded: digit sets, ٫ ٬ , ، . between digits, spaces, tashkeel, tatweel, minus variants, and for numeric cells the position of signs / stars / percent / brackets; (c) still different: misplaced / structure when the cell's row or column is shifted by one (most of the row's non-empty cells sit one row / column away on the other side), or the key's text is in the adjacent cell of the same row or column, or the other text belongs to such an adjacent cell, or one side is empty or outside the grid; otherwise different text, split into punctuation / symbols only and letters or digits; (d) per table.",
    "P9: pipeline fields from the first ref-list citation_mention of the ref block: title = article_title or chapter_title, else source_title (book / thesis) with source = publisher; pages = page_range or fpage-lpage; pages also compared as sets of numbers. Authors are stored as [family, given] parts, not as printed: an author is exact when one of the obvious joins equals the key's string.",
    "Fields (P4, P7 caption/number, P9) are scored where the key has a value; a pipeline value where the key says nothing is printed is counted apart (pred_where_key_null). What is still wrong after folding gets a kind: other side empty, part missing, part extra, different field boundary (the extra / missing text sits in another field of the same item), letters differ, different text.",
    "R1: truth = the two blind readers' transcription where they agree (exact; and, for the folded scores, where they agree after folding). Error rates on the settled disputed lines are extrapolated to the 598 three-witness lines: disputed lines weighted by their letters (Azure's text as the size of unsettled ones), all-agree lines at the error rate of the settled control lines.",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default="final", choices=["final", "A", "B"])
    a = ap.parse_args()
    import time
    sc = dict(made=time.strftime("%Y-%m-%d %H:%M"), keys=a.keys, parts={}, ceiling={}, inputs={}, interpretation=INTERPRETATION,
              limits=LIMITS,
              status="The keys are not adjudicated yet (or only partly): these pipeline numbers are a development run of the scorer, not the baseline.")
    os.makedirs(SCORES, exist_ok=True)
    for part in PARTS:
        gold, src = gold_set(part, a.keys)
        acc, diffs, cnt = run_part(part, gold["files"])
        sc["parts"][part] = summarise(part, acc)
        with open(f"{SCORES}/pipeline_misses_{part}.jsonl", "w") as f:
            for d in diffs:
                f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
        A, B = load_keys(part, "A"), load_keys(part, "B")
        cacc, cdiffs, ccnt = run_part(part, A["files"], B["files"]) if A["files"] and B["files"] else (new_acc(), [], C.Counter())
        sc["ceiling"][part] = summarise(part, cacc) if ccnt.get("scored") else None
        with open(f"{SCORES}/disagreements_{part}.jsonl", "w") as f:
            for d in cdiffs:
                f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
        # what is still wrong after folding, by kind: table cells, and front-matter / reference fields
        for suffix, D in (("", diffs), ("_AvsB", cdiffs)):
            cw = [d for d in D if d.get("content_wrong")]
            if part == "TAB":
                with open(f"{SCORES}/cells_content_wrong{suffix}.jsonl", "w") as f:
                    for d in cw:
                        if d.get("measure") == "P7.cell":
                            f.write(json.dumps(dict(stem=d["stem"], page=d["page"], table=d["table"], row=d["row"], col=d["col"],
                                                    key_text=d["gold"], other_text=d["pred"], kind=d["kind"]), ensure_ascii=False) + "\n")
            if part in ("FRONT", "REFS", "TAB"):
                with open(f"{SCORES}/fields_content_wrong_{part}{suffix}.jsonl", "w") as f:
                    for d in cw:
                        if d.get("measure") != "P7.cell":
                            f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
        print(f"{part:6s} scored against: {src}", file=sys.stderr)
        sc["inputs"][part] = dict(key_source=src, n_final=gold.get("n_final"), n_A_fallback=gold.get("n_A_fallback"), key_dir=gold["dir"], files=len(gold["files"]), unreadable=gold["bad"],
                                  counts=dict(cnt), ceiling_counts=dict(ccnt), A_files=len(A["files"]), B_files=len(B["files"]),
                                  pipeline_misses=len(diffs), disagreements=len(cdiffs))
    for name, p in (("R2", f"{OUT}/scores/r2_lines.json"), ("R1", f"{OUT}/reading/summary.json")):
        if os.path.exists(p):
            sc[name] = json.load(open(p))
    sc["R1_settled"] = score_r1()
    scored_parts = [p for p, v in sc["inputs"].items() if v.get("files")]
    sc["all_final"] = bool(scored_parts) and all(not v.get("n_A_fallback") and v.get("n_final") for p, v in sc["inputs"].items()
                                                 if p in scored_parts)
    sc["parts_without_keys"] = [p for p in sc["inputs"] if p not in scored_parts]
    rev = any(os.path.isdir(f"{d}/final/_v1") for d in glob.glob(f"{KEYS}/*"))
    sc["keys_revision"] = "rev 2" if rev else "rev 1"
    sc["banner"] = (f"Baseline v1{' (keys rev 2)' if rev else ''}, {time.strftime('%Y-%m-%d')}") if sc["all_final"] else "NOT FINAL"
    sc["rows"] = [dict(measure=r[0], pipeline=r[1], a_vs_b=r[2], pass_mark=r[3], key_state=r[4], miss_means=r[5], passed=r[6])
                  for r in md_rows(sc)]
    jdump(sc, f"{SCORES}/scorecard.json")
    write_md(sc, f"{SCORES}/scorecard.md")
    print(json.dumps(sc["inputs"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
