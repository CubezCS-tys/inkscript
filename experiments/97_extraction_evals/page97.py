#!/usr/bin/env python3
"""Experiment 97: the data and pictures behind the Desk page /exam ("The extraction exam", desk/exam.py).

    cd /home/appuser/inkscript/experiments/97_extraction_evals
    nice -n 19 ionice -c3 /home/appuser/inkscript/.venv/bin/python page97.py [--force]

Reads only files: out/scores (scorecard.json, pipeline_misses_PAGE, cells_content_wrong, fields_content_wrong_*),
out/keys/*/final, out/packets, out/cache (via score97's pipeline_<part> converters, read-only), out/ink, out/reading,
out/triage (verdicts per miss, when present), and the 300-dpi page images of experiment 43. Writes only under
out/page/:  exam.json (the page's data), structure/<stem>_pNNN.json (one per exam page, loaded on demand) and
img/<kind>/<name>.jpg (crops and downscaled pages; an existing picture is kept unless --force).

Run it again after the scorer is re-run; the page follows. TRIAGE.md is read by the Desk at request time, so the
triage section appears (and updates) without a rebuild.
"""
from __future__ import annotations

import argparse
import collections as C
import difflib
import glob
import json
import os
import re
import sys
import time
import unicodedata
from functools import lru_cache

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common97 import ARTS, BY_STEM, OUT, fold, ws  # noqa: E402
import score97 as S  # noqa: E402

PG = f"{OUT}/page"
IMG = f"{PG}/img"
FORCE = False
T0 = time.time()


def say(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def jl(p):
    return [json.loads(x) for x in open(p, encoding="utf-8") if x.strip()] if os.path.isfile(p) else []


def jload(p, default=None):
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else default


def safe(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z,_.\-]", "_", s)


# ------------------------------------------------------------------------------------------------ pictures
@lru_cache(maxsize=None)
def packet(stem):
    return jload(f"{OUT}/packets/{stem}/packet.json")


def ppage(stem, page):
    return next(p for p in packet(stem)["pages"] if p["page"] == page)


@lru_cache(maxsize=2)
def page_img(stem, page):
    im = cv2.imread(ppage(stem, page)["image"], cv2.IMREAD_COLOR)
    if im is None:
        raise FileNotFoundError(ppage(stem, page)["image"])
    return im


def save(kind, name, im, q=82):
    os.makedirs(f"{IMG}/{kind}", exist_ok=True)
    cv2.imwrite(f"{IMG}/{kind}/{name}", im, [cv2.IMWRITE_JPEG_QUALITY, q, cv2.IMWRITE_JPEG_OPTIMIZE, 1])
    time.sleep(0.05)        # shared disk with a live database: cut gently
    return f"{kind}/{name}"


def have(kind, name):
    return not FORCE and os.path.isfile(f"{IMG}/{kind}/{name}")


def resize_w(im, w):
    h0, w0 = im.shape[:2]
    if w0 <= w:
        return im
    return cv2.resize(im, (w, round(h0 * w / w0)), interpolation=cv2.INTER_AREA)


def page_picture(stem, page, w=1000):
    """The whole page, downscaled to w px wide (for the structure view and the 'beyond the exam' strip)."""
    name = f"{safe(stem)}_p{page:03d}.jpg"
    if not have("pages", name):
        save("pages", name, resize_w(page_img(stem, page), w), 80)
    return f"pages/{name}"


def line_boxes(stem, page):
    pp = ppage(stem, page)
    return {l["line"]: l for l in pp["azure_lines"]}, pp["width_px"], pp["height_px"]


def crop_lines(stem, page, lines, tag, pad=14, maxw=1500):
    """A crop of the printed page around the given Azure lines (boxes are in ALTO pixels; the JPEG differs by a
    few px, so the box is scaled by image / ALTO size)."""
    boxes, W, H = line_boxes(stem, page)
    bs = [boxes[n] for n in lines if n in boxes]
    if not bs:
        return None
    name = f"{safe(stem)}_p{page:03d}_{tag}.jpg"
    if have("cut", name):
        return f"cut/{name}"
    im = page_img(stem, page)
    ih, iw = im.shape[:2]
    sx, sy = iw / W, ih / H
    x0 = max(0, int(min(b["x"] for b in bs) * sx) - pad)
    y0 = max(0, int(min(b["y"] for b in bs) * sy) - pad)
    x1 = min(iw, int(max(b["x"] + b["w"] for b in bs) * sx) + pad)
    y1 = min(ih, int(max(b["y"] + b["h"] for b in bs) * sy) + pad)
    if x1 <= x0 or y1 <= y0:
        return None
    return save("cut", name, resize_w(im[y0:y1, x0:x1], maxw), 85)


# ------------------------------------------------------------------------------------------------ text diff
TASHKEEL = re.compile(r"[ً-ٰٟۖ-ۭ]")
HAMZA = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و", "ئ": "ى", "ء": "", "ي": "ى", "ة": "ه"})


def _nopunct(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0] not in "PS")


def diff_kind(a: str, b: str) -> str | None:
    """The smallest kind of difference that explains a != b (reading cards' filter)."""
    a, b = unicodedata.normalize("NFC", a or ""), unicodedata.normalize("NFC", b or "")
    if a == b:
        return None
    if a.replace(" ", "") == b.replace(" ", ""):
        return "spacing"
    pa, pb = _nopunct(a).replace(" ", ""), _nopunct(b).replace(" ", "")
    if pa == pb:
        return "punctuation"
    va, vb = TASHKEEL.sub("", pa).replace("ـ", ""), TASHKEEL.sub("", pb).replace("ـ", "")
    if va == vb:
        return "marks"
    if va.translate(HAMZA) == vb.translate(HAMZA):
        return "hamza"
    wa, wb = sorted(_nopunct(a).split()), sorted(_nopunct(b).split())
    if wa == wb:
        return "order"
    return "letters"


def segs(truth: str | None, text: str | None):
    """text cut into [[piece, 0 same | 1 differs | 2 something of the truth is missing here]] against truth."""
    if text is None:
        return None
    if truth is None:
        return [[text, 0]]
    sm = difflib.SequenceMatcher(None, truth, text, autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append([text[j1:j2], 0])
        elif op in ("replace", "insert"):
            out.append([text[j1:j2], 1])
        else:
            out.append(["", 2])
    merged = []
    for s in out:
        if merged and merged[-1][1] == s[1] and s[1] != 2:
            merged[-1][0] += s[0]
        else:
            merged.append(s)
    return merged


def as_text(v):
    if v is None:
        return None
    if isinstance(v, list):
        return " · ".join(str(x) for x in v)
    return str(v)


# ------------------------------------------------------------------------------------------------ scorecard
def _get(d, part, name):
    """parts[part]['P4']['title'] (pipeline) or ceiling[part]['P4.title'] (key A vs key B)."""
    x = (d or {}).get(part) or {}
    if name in x:
        return x[name]
    a, _, b = name.partition(".")
    return (x.get(a) or {}).get(b) if b else None


PLAIN = [  # (pattern on the scorer's measure name, group, plain name); first match wins
    (r"^R1 shown, block rewrites removed: letters / words", "reading", "Text we show, with deliberate rewrites set aside"),
    (r"^R1 shown as stored: letters / words", "reading", "Text we show, as stored"),
    (r"^R1 Azure raw line", "reading", "Azure's own reading (for comparison)"),
    (r"^R1 t91 reader", "reading", "Our own reader t91 (for comparison)"),
    (r"^R1 deliberate rewrites", "reading", "Letters deliberately rewritten (keyword label dropped, ، → ؛)"),
    (r"^R1 shown vs Azure raw \(as stored\)", "reading", "Our fixes against Azure's reading, as stored"),
    (r"^R1 shown vs Azure raw \(rewrites removed\)", "reading", "Our fixes against Azure's reading, rewrites set aside"),
    (r"^R1 three witnesses agree", "reading", "Lines where all three readings agree"),
    (r"^R1 stored order", "reading", "Mixed-direction lines stored in another order (not wrong letters)"),
    (r"^R1 readers: lines left out", "reading", "Lines the readers could not settle"),
    (r"^R2 lines lost", "ink", "Printed lines lost (counted by machine)"),
    (r"^R2 lines doubled", "ink", "Printed lines stored twice"),
    (r"^R2 key text lines lost", "ink", "Printed lines lost (checked against the answer key)"),
    (r"^P1 role per line", "structure", "Labels: each line has the right role"),
    (r"^P1 author block", "structure", "Labels: author block (name and affiliation)"),
    (r"^P1 roles with", "structure", "Labels: roles under 90%"),
    (r"^P2 same-piece F1, tables", "structure", "Grouping, tables left out"),
    (r"^P2 same-piece", "structure", "Grouping: lines joined into the right pieces"),
    (r"^P3 order, one column", "structure", "Reading order, one-column pages"),
    (r"^P3 order, two columns", "structure", "Reading order, two-column pages"),
    (r"^P3 order, mixed", "structure", "Reading order, mixed pages"),
    (r"^P3 order, first pages, body", "structure", "Reading order, first pages (body text)"),
    (r"^P3 order, first pages", "structure", "Reading order, first pages (all pieces)"),
    (r"^P6 notes", "structure", "Footnotes: note text and number right"),
    (r"^P6 calls", "structure", "Footnotes: the mark in the text points to its note"),
    (r"^P5 headings found", "structure", "Section headings found"),
    (r"^P5 headings invented", "structure", "Section headings invented"),
    (r"^P5 level", "structure", "Section heading level right"),
    (r"^P4\.title", "front", "Title"), (r"^P4\.authors_no", "front", "Author names without Dr. / Prof."),
    (r"^P4\.authors", "front", "Author names"), (r"^P4\.affiliation_with", "front", "Affiliation with job title"),
    (r"^P4\.affiliation", "front", "Affiliation"), (r"^P4\.abstract", "front", "Abstract (where it starts and ends)"),
    (r"^P4\.keyword_items", "front", "Keywords, item by item"), (r"^P4\.keywords", "front", "Keywords"),
    (r"^P4\.date_received", "front", "Date received"), (r"^P4\.date_accepted", "front", "Date accepted"),
    (r"^P4\.date_published", "front", "Date published"), (r"^P4\.doi", "front", "DOI"),
    (r"^P4\.first_printed", "front", "First page number"), (r"^P4\.last_printed", "front", "Last page number"),
    (r"^P4\.article_language", "front", "Article language"),
    (r"^P7\.found", "tables", "Tables found"), (r"^P7\.shape", "tables", "Tables with the right rows and columns"),
    (r"^P7\.header_rows", "tables", "Header rows"), (r"^P7\.caption", "tables", "Table caption"),
    (r"^P7\.number", "tables", "Table number"), (r"^P7\.continuation", "tables", "Table continued from the previous page, marked"),
    (r"^P7\.continues_next", "tables", "Table continuing on the next page, marked"),
    (r"^P7\.cells \(a\)", "tables", "Table cells exactly as printed"),
    (r"^P7\.cells \(b\)", "tables", "Table cells right, ignoring digit style and spacing"),
    (r"^P7\.cells \(c\)", "tables", "Cells with wrong content"),
    (r"^P7\.cells \(c1\)", "tables", "… of which the right text in the wrong cell"),
    (r"^P7\.cells \(c2\)", "tables", "… of which different text"),
    (r"^P7\.cells \(d\) tables with no content", "tables", "Tables with no wrong cell"),
    (r"^P7\.cells \(d\) tables with no different", "tables", "Tables with no cell of different text"),
    (r"^P7\.tabular", "tables", "Borderless lists made into tables"),
    (r"^P8\.found", "tables", "Figures found"), (r"^P8\.caption", "tables", "Figure caption"),
    (r"^P9\.boundaries", "refs", "Where each reference starts and ends"), (r"^P9\.authors", "refs", "Authors"),
    (r"^P9\.year", "refs", "Year"), (r"^P9\.title", "refs", "Title of the cited work"),
    (r"^P9\.source", "refs", "Source (journal, publisher, university)"), (r"^P9\.volume", "refs", "Volume"),
    (r"^P9\.issue", "refs", "Issue"), (r"^P9\.pages as printed numbers", "refs", "Pages (the printed numbers)"),
    (r"^P9\.pages text", "refs", "Pages, character by character"), (r"^P9\.type", "refs", "Kind of reference"),
]
FOLD_NAME = [(", folded, punctuation ignored", " (ignoring vowel marks, digit style and punctuation)"),
             (", folded", " (ignoring vowel marks and digit style)"), (", exact", "")]
CODE_PLAIN = {"R1": "Reading", "R2": "Nothing lost", "P1": "Labels", "P2": "Grouping", "P3": "Reading order",
              "P4": "Front matter", "P5": "Sections", "P6": "Footnotes", "P7": "Tables", "P8": "Figures", "P9": "References"}
# rows shown as bars in the picture (the rest are listed in full below it)
MAIN_EXTRA = (r"^R1 (Azure raw line|t91 reader): letters / words wrong, exact", r"^R1 deliberate rewrites.*exact",
              r"^R1 shown vs Azure raw \(rewrites removed\), exact", r"^P3 order, first pages, body", r"^P5 ",
              r"^R1 stored order")


def _nums(s):
    """'81.2% / 89.4% / 95.3%' -> [0.812, 0.894, 0.953]; anything else -> None"""
    s = (s or "").strip()
    if not re.fullmatch(r"-?[\d.]+%( / -?[\d.]+%)*", s):
        return None
    return [float(x) / 100 for x in re.findall(r"-?[\d.]+(?=%)", s)]


def _mark(s):
    m = re.match(r"^\s*(<=|>=)\s*([\d.]+)%", s or "")
    return (float(m.group(2)) / 100, "low" if m.group(1) == "<=" else "high") if m else (None, None)


def scorecard_rows(sc, ink):
    out = []
    for i, r in enumerate(sc.get("rows") or []):
        m = r.get("measure") or ""
        hit = next(((g, n) for pat, g, n in PLAIN if re.search(pat, m)), None)
        group, name = hit if hit else ("other", m)
        if m.startswith("R1"):
            name += next((v for k, v in FOLD_NAME if k in m), "")
        code = re.match(r"^([RP]\d)", m)
        code = code.group(1) if code else None
        nm = re.search(r"\(n=(\d+)", m)
        vals, ceil = _nums(r.get("pipeline")), _nums(r.get("a_vs_b"))
        pm = r.get("pass_mark") or ""
        passed = (r.get("passed") or "").strip()
        main = bool(passed) or any(re.search(p, m) for p in MAIN_EXTRA)
        if m.startswith("R1"):
            # one level up front (vowel marks, digit style and punctuation ignored: the level the two numbers the lead
            # quotes are on); the exact and middle levels are in the full list only (lead, 2026-11-10: 15 rows were too many)
            main = ("stored order" in m) or ("punctuation ignored" in m and ("letters / words" in m or "deliberate rewrites" in m
                                                                             or "(rewrites removed)" in m))
        base = dict(idx=i, group=group, code=code, code_plain=CODE_PLAIN.get(code), raw=m, n=int(nm.group(1)) if nm else None,
                    miss_means=r.get("miss_means"), key_state=r.get("key_state"), pass_text=pm, passed=passed, main=main,
                    pipeline_text=r.get("pipeline"), a_vs_b_text=r.get("a_vs_b"))
        if m.startswith("R1") and "letters / words" in m and vals and len(vals) == 2:
            marks = re.findall(r"<=\s*([\d.]+)%", pm)
            for j, (what, unit) in enumerate([("letters", "Letters wrong"), ("words", "Words wrong")]):
                mk = float(marks[j]) / 100 if len(marks) == 2 else None
                v = vals[j]
                pz = ("pass" if v <= mk else "miss") if mk is not None and passed else ""
                if what == "words" and re.search(r"Azure raw line|t91 reader", m):
                    base = dict(base, main=False)        # witnesses: letters up front, words in the full list
                out.append(dict(base, id=f"r{i}{what[0]}", name=f"{unit}: {name[0].lower() + name[1:] if name.startswith(('Text', 'Our')) else name}", value=v,
                                values=None, mark=mk, better="low", ceiling=None, passed=pz))
            continue
        mk, better = _mark(pm)
        if not mk and "lower is better" in pm:
            better = "low"
        value = vals[-1] if vals else None
        others = None
        if vals and len(vals) == 3:
            others = [("exact", vals[0]), ("typography-folded", vals[1])]
        out.append(dict(base, id=f"r{i}", name=name, value=value, values=others, mark=mk, better=better or "high",
                        ceiling=ceil[-1] if ceil else None))
    tl = ink.get("overall", {}).get("text_ledger", {})
    for id_, name, v, mk, note in [
            ("ink_unseen", "Text ink that nobody saw", tl.get("unseen"), 0.003, "printed letters no reader line and no stored piece covers"),
            ("ink_dropped", "Text ink the reader saw but the parser dropped", tl.get("dropped"), 0.002, "text lost between reading and storing"),
            ("ink_setaside", "Text ink set aside as 'not this article'", tl.get("set_aside_text_like"), None,
             "nothing lost: all of it is one neighbouring poem on two pages of 0738, set aside correctly")]:
        out.insert(0 if id_ == "ink_unseen" else 1 if id_ == "ink_dropped" else 2,
                   dict(idx=-1, id=id_, group="ink", code="R0", code_plain="Nothing lost (ink)", raw=f"R0 {name}", n=None,
                        miss_means=note, key_state="no key needed", pass_text=(f"<= {100 * mk:g}%" if mk else "(no mark)"),
                        passed=(("pass" if v <= mk else "miss") if mk is not None and v is not None else ""), main=True,
                        name=name, value=v, values=None, mark=mk, better="low", ceiling=None,
                        pipeline_text=pct(v, 3), a_vs_b_text="–"))
    return out


def pct(x, d=1):
    return "–" if x is None else f"{100 * x:.{d}f}%"


# ------------------------------------------------------------------------------------------------ ink
INK_LEGEND = [  # from ink97.py COL (BGR there; RGB here) and out/ink/SUMMARY.md
    dict(rgb=[120, 120, 120], name="Claimed once", what="ink that exactly one stored piece holds: the normal case"),
    dict(rgb=[255, 140, 0], name="Claimed twice", what="ink two pieces both hold (a rule where two line boxes overlap)"),
    dict(rgb=[230, 0, 0], name="Reader saw, parser dropped", what="inside a reader line but in no stored piece"),
    dict(rgb=[160, 40, 200], name="Seen by nobody", what="in no reader line and no piece: mostly rules, frames, page edges"),
    dict(rgb=[60, 170, 140], name="Set aside", what="in a region the parser set aside on purpose: noise, ornament, another article"),
    dict(rgb=[215, 215, 215], name="Specks", what="dust below the size cut, not counted"),
    dict(rgb=[150, 200, 235], name="Thin blue boxes", what="the reader's (Azure's) lines", box=True),
]
KIND_PLAIN = {"front": "First page", "body": "Body page", "table": "Table page", "refs": "Reference page",
              "notes": "Footnote page"}


def build_ink():
    out = dict(legend=INK_LEGEND, pages=[], regions=[], kinds=KIND_PLAIN)
    summ = jload(f"{OUT}/ink/summary.json", {}) or {}
    for f in sorted(glob.glob(f"{OUT}/ink/pages/*.json")):
        d = json.load(open(f))
        stem, page = d["stem"], d["page"]
        base = f"{safe(stem)}_p{page:03d}.jpg"
        src = f"{OUT}/ink/overlays/{stem}_p{page:03d}.png"
        if not os.path.isfile(src):
            continue
        if not (have("ink", base) and have("inkthumb", base)):
            im = cv2.imread(src, cv2.IMREAD_COLOR)
            save("ink", base, resize_w(im, 1100), 84)
            save("inkthumb", base, resize_w(im, 300), 78)
        t = d["tally"]["text"]
        out["pages"].append(dict(stem=stem, page=page, kind=d["kind"], journal=d["journal"], img=f"ink/{base}",
                                 thumb=f"inkthumb/{base}",
                                 once=t["once"]["area_share"], unseen=t["unseen"]["area_share"],
                                 twice=t["twice"]["area_share"], dropped=t["dropped"]["area_share"],
                                 setaside=(t.get("once_by_piece_kind_area") or {}).get("setaside", 0) / max(1, t["ink_px"]),
                                 all_unseen=d["tally"]["all"]["unseen"]["area_share"]))
    say("ink overlays", len(out["pages"]))
    regs = jl(f"{OUT}/ink/unclaimed_regions.jsonl")
    for r in regs:
        src = f"{OUT}/ink/{r['crop']}"
        if not os.path.isfile(src):
            continue
        name = safe(os.path.basename(src))
        if not have("inkcrop", name):
            save("inkcrop", name, resize_w(cv2.imread(src, cv2.IMREAD_COLOR), 900), 85)
        out["regions"].append(dict(id=r["region_id"], stem=r["stem"], page=int(re.search(r"_p(\d+)_", r["region_id"]).group(1)),
                                   kind=r["kind"], group=r["group"], guess=r.get("auto_guess"),
                                   setaside_role=r.get("setaside_role"), label=r.get("label"), box=r["box"],
                                   img=f"inkcrop/{name}"))
    out["regions"].sort(key=lambda r: (r["group"] != "set_aside", r["guess"] != "text-like row of glyph-sized blobs", r["id"]))
    tl = (summ.get("overall") or {}).get("text_ledger") or {}
    out["headline"] = dict(text_once=tl.get("once"), text_unseen=tl.get("unseen"), text_dropped=tl.get("dropped"),
                           set_aside=tl.get("set_aside_text_like"),
                           all_unseen=((summ.get("overall") or {}).get("all_ink") or {}).get("unseen", {}).get("area_share"))
    # featured: the neighbouring poem set aside, and the cleanest reference page of a read-whole journal
    refs = [p for p in out["pages"] if p["kind"] == "refs" and p["journal"] in ("0013", "0097", "0130", "0165", "0246", "0840", "1001")]
    clean = max(refs, key=lambda p: (round(p["once"], 5), -p["all_unseen"])) if refs else None
    out["featured"] = [dict(stem="0738-002-003-016", page=1,
                            title="A neighbouring poem, set aside correctly",
                            text="The top of this page is the end of another work: a poem by another author. The parser set it "
                                 "aside as 'another article' (green). That is the only text-like ink on the 214 pages the "
                                 "parser put aside, and it was right to.")]
    if clean:
        out["featured"].append(dict(stem=clean["stem"], page=clean["page"], title="A clean reference page",
                                    text="Every printed letter is grey: claimed once. Only the rules and the page edge are "
                                         "purple, which is what 'seen by nobody' usually is."))
    return out


# ------------------------------------------------------------------------------------------------ reading
def build_reading():
    lines = {f"{r['stem']}_p{r['page']:03d}_l{r['line']:03d}": r for r in jl(f"{OUT}/reading/lines.jsonl")}
    disputes = jl(f"{OUT}/reading/disputes.jsonl")
    A = {r["id"]: r for r in jl(f"{OUT}/reading/settle/A/readings.jsonl")}
    B = {r["id"]: r for r in jl(f"{OUT}/reading/settle/B/readings.jsonl")}
    Cr = {r["id"]: r for r in jl(f"{OUT}/reading/settle/C/readings.jsonl")}
    D = {r["id"]: r for r in jl(f"{OUT}/reading/settle/disagreements.jsonl")}
    cards = []
    for d in disputes:
        i = d["id"]
        L = lines.get(i)
        if not L:
            continue
        a, b, c = A.get(i), B.get(i), Cr.get(i)
        settled, how = None, "not settled yet"
        dz = D.get(i)
        if dz is not None:          # the scorer's own verdict (settle/disagreements.jsonl, 'settled')
            v = str(dz.get("settled") or "")
            if v.startswith("C") and c:
                settled, how = c["printed"], "third reader"
            elif v.startswith("order only"):
                settled, how = (c or {}).get("printed"), "third reader: same letters, stored in another order"
            else:
                how = "left out: " + (dz.get("C_why") or v)
        elif a and b and ws(a["printed"]) == ws(b["printed"]):
            settled, how = a["printed"], "both readers agree"
        src = L["crop"]
        name = safe(os.path.basename(src).rsplit(".", 1)[0]) + ".jpg"
        if os.path.isfile(src) and not have("line", name):
            save("line", name, resize_w(cv2.imread(src, cv2.IMREAD_COLOR), 1400), 88)
        wit = {}
        tags = set()
        for k in ("azure", "t91", "shown"):
            t = L.get(k)
            k_ = diff_kind(settled, t) if settled is not None and t is not None else None
            if k_:
                tags.add(k_)
            wit[k] = dict(text=t, right=(settled is not None and t is not None and ws(t) == ws(settled)),
                          kind=k_, segs=segs(settled, t))
        cards.append(dict(id=i, stem=L["stem"], page=L["page"], line=L["line"], kind=L["kind"],
                          img=f"line/{name}" if os.path.isfile(src) else None, control=d.get("control"),
                          witnesses=wit, settled=settled, how=how,
                          A=dict(text=a["printed"], unsure=a.get("unsure"), why=a.get("why")) if a else None,
                          B=dict(text=b["printed"], unsure=b.get("unsure"), why=b.get("why")) if b else None,
                          C=dict(text=c["printed"], why=c.get("why"), who=c.get("who"), unsure=c.get("unsure")) if c else None,
                          tags=sorted(tags)))
    say("reading cards", len(cards))
    return cards


def build_rewrites(cards):
    """Lines where the text we show deliberately differs from the print: a keyword block drops its printed label and
    turns ، into ؛; a verse or a bullet gets '/ ' or '• ' inserted (R1 'deliberate rewrites')."""
    by_id = {c["id"]: c for c in cards}
    out = []
    for L in jl(f"{OUT}/reading/lines.jsonl"):
        i = f"{L['stem']}_p{L['page']:03d}_l{L['line']:03d}"
        a, sh = L.get("azure") or "", L.get("shown") or ""
        if not sh or ws(a) == ws(sh):
            continue
        kw = L.get("shown_source") == "keywords"
        ins = ("• " in sh and "• " not in a) or (" / " in sh and "/" not in a)
        if not (kw or ins):
            continue
        c = by_id.get(i)
        src = L["crop"]
        name = safe(os.path.basename(src).rsplit(".", 1)[0]) + ".jpg"
        if os.path.isfile(src) and not have("line", name):
            save("line", name, resize_w(cv2.imread(src, cv2.IMREAD_COLOR), 1400), 88)
        truth = (c or {}).get("settled") or a
        out.append(dict(id=i, stem=L["stem"], page=L["page"], line=L["line"], img=f"line/{name}",
                        what="the printed keyword label dropped, and each Arabic comma turned into a semicolon" if kw else "a separator inserted (a bullet or a slash)",
                        azure=a, shown=segs(truth, sh), settled=(c or {}).get("settled"),
                        printed_from="the settled reading" if c and c.get("settled") else "Azure's reading (all three agree on the letters)"))
    say("rewrite cards", len(out))
    return out


# ------------------------------------------------------------------------------------------------ page structure
ROLE_PLAIN = {
    "title": "Title", "title-translated": "Title (other language)", "byline": "Author name", "affiliation": "Affiliation",
    "author block (byline + affiliation)": "Author block", "abstract": "Abstract", "keywords": "Keywords",
    "front-matter": "Front matter", "heading": "Heading", "paragraph": "Paragraph", "list-item": "List item",
    "quote": "Quotation", "verse": "Verse", "footnote": "Footnote", "endnote": "Endnote", "ref": "Reference",
    "caption": "Caption", "table": "Table", "figure": "Text in a picture", "equation": "Equation",
    "running-head": "Running head", "page-number": "Page number", "other": "Other", "(not-text)": "Not text",
    "(no-block)": "In no piece",
}


def build_structure():
    misses = jl(f"{S.SCORES}/pipeline_misses_PAGE.jsonl")
    trg = {}
    for f in glob.glob(f"{OUT}/triage/P1_*.jsonl"):
        for r in jl(f):
            for n in r.get("lines") or []:
                trg[(r["stem"], r["page"], n)] = dict(cls=r.get("cls"), sub=r.get("sub"), why=r.get("why"))
    by_page = C.defaultdict(list)
    for m in misses:
        by_page[(m["stem"], m["page"])].append(m)
    kinds = {(a["stem"], p): k for a in ARTS for k, p in a["pages"].items()}
    os.makedirs(f"{PG}/structure", exist_ok=True)
    index = []
    for (stem, page), kind in sorted(kinds.items()):
        keyf = f"{S.KEYS}/PAGE/final/{stem}_p{page:03d}.json"
        key = jload(keyf)
        if not key or not packet(stem):
            continue
        boxes, W, H = line_boxes(stem, page)
        try:
            pred = S.pipeline_page(stem, page)
        except Exception as e:  # noqa: BLE001
            say("pipeline_page failed", stem, page, e)
            continue
        diff = C.defaultdict(list)
        counts = C.Counter()
        for m in by_page.get((stem, page), []):
            counts[m["measure"]] += 1
            if m["measure"].startswith("P1"):
                diff[m["line"]].append(f"key: {ROLE_PLAIN.get(m['gold'], m['gold'])}; pipeline: {ROLE_PLAIN.get(m['pred'], m['pred'])}")
            elif m["measure"] == "P2 piece":
                for n in m.get("gold_lines") or []:
                    diff[n].append("joined to different lines")
            elif m["measure"] == "P6 note":
                for n in m.get("gold_lines") or []:
                    diff[n].append(f"footnote: key label {m.get('gold_label')}, pipeline {((m.get('pred') or {}).get('label'))}")
        lines = [dict(n=n, b=[round(l["x"] / W, 5), round(l["y"] / H, 5), round(l["w"] / W, 5), round(l["h"] / H, 5)],
                      t=l["text"]) for n, l in sorted(boxes.items())]
        kp = [dict(role=p["role"], lines=p["lines"]) for p in key.get("pieces") or []]
        pp = [dict(role=p["role"], lines=p["lines"]) for p in pred.get("pieces") or []]
        img = page_picture(stem, page)
        doc = dict(stem=stem, page=page, kind=kind, img=img, aspect=H / W, lines=lines, key=kp, pipe=pp,
                   key_not_text=key.get("azure_lines_that_are_not_text") or [],
                   pipe_not_text=pred.get("azure_lines_that_are_not_text") or [],
                   diff={str(k): v for k, v in diff.items()},
                   triage={str(n): t for (s, p, n), t in trg.items() if s == stem and p == page},
                   key_flags={k: key.get(k) for k in ("unsure", "image_defect", "cover_sheet", "why", "columns") if key.get(k) is not None},
                   counts=dict(counts))
        json.dump(doc, open(f"{PG}/structure/{safe(stem)}_p{page:03d}.json", "w"), ensure_ascii=False)
        index.append(dict(stem=stem, page=page, kind=kind, n_diff_lines=len(diff), counts=dict(counts),
                          file=f"{safe(stem)}_p{page:03d}"))
    index.sort(key=lambda r: (-sum(r["counts"].values()), r["stem"], r["page"]))
    say("structure pages", len(index))
    return dict(pages=index, roles=ROLE_PLAIN)


# ------------------------------------------------------------------------------------------------ tables
FEATURED_TABLES = {
    ("1001-018-001-008", 11, 0): "A whole row shifted. The table prints an empty row; the pipeline dropped it, so every row "
                                 "below moved up by one: the right text in the wrong row. Since 2026-11-10 the scorer sets "
                                 "the empty row aside before comparing, so these cells no longer count as wrong, but the "
                                 "stored grid is still one row short (marked here cell by cell).",
}
def build_tables():
    rows = jl(f"{S.SCORES}/cells_content_wrong.jsonl")
    trg = {(r["stem"], r["page"], tuple(r["cell"])): r for r in jl(f"{OUT}/triage/P7_cells.jsonl")}
    by_t = C.defaultdict(dict)
    for r in rows:
        by_t[(r["stem"], r["page"], r["table"])][(r["row"], r["col"])] = r
    for f in FEATURED_TABLES:
        by_t.setdefault(f, {})
    out = []
    for (stem, page, ti), wrong in sorted(by_t.items(), key=lambda kv: -len(kv[1])):
        key = jload(f"{S.KEYS}/TAB/final/{stem}_p{page:03d}.json")
        if not key:
            continue
        gts = [t for t in key.get("tables") or [] if not S.left_out(t)]
        if ti >= len(gts):
            continue
        g = gts[ti]
        pred = S.pipeline_tab(stem, page)
        best, bv = None, 0.0
        for p in pred.get("tables") or []:
            A_, B_ = S._lines_of(g), S._lines_of(p)
            v = len(A_ & B_) / len(A_ | B_) if A_ and B_ else 0
            if v > bv:
                best, bv = p, v
        gc = g.get("cells") or []
        pc = (best or {}).get("cells") or []
        if pc and (g.get("direction") or "rtl") != (best.get("direction") or "rtl"):
            pc = S._mirror(pc)

        own = (stem, page, ti) in FEATURED_TABLES and not wrong     # the scorer lists nothing: compare cell by cell here

        def at(G, r, c):
            return G[r][c] if 0 <= r < len(G) and 0 <= c < len(G[r]) else None

        def cls_at(r, c):
            w = wrong.get((r, c))
            if w:
                return ("misplaced" if w["kind"].startswith("misplaced") else "different"), w["kind"]
            gt, pt = at(gc, r, c), at(pc, r, c)
            if gt is not None and pt is not None and ws(gt) != ws(pt) and S.cell_fold(gt) == S.cell_fold(pt):
                return "format", "formatting only (digit style, spacing, sign position)"
            if own and S.cell_fold(gt or "") != S.cell_fold(pt or ""):
                near = {S.cell_fold(at(pc, r + d, c) or "") for d in (-1, 1)} | {S.cell_fold(at(gc, r + d, c) or "") for d in (-1, 1)}
                if S.cell_fold(gt or "") in near or S.cell_fold(pt or "") in near:
                    return "misplaced", "the right text, one row away"
                return "different", "different text"
            return None, None

        def grid(src, side):
            out_ = []
            for r, row in enumerate(src):
                cells = []
                for c, t in enumerate(row):
                    k, why = cls_at(r, c)
                    tr = trg.get((stem, page, (r, c))) if k in ("misplaced", "different") else None
                    cells.append(dict(t=t, k=k, why=why, tri=(dict(cls=tr["cls"], sub=tr.get("sub")) if tr else None)))
                out_.append(cells)
            return out_
        lines = sorted(S._lines_of(g))
        crop = crop_lines(stem, page, lines, f"t{ti}", pad=20, maxw=1600) if lines else None
        kg, kp = grid(gc, "key"), grid(pc, "pipe") if pc else None
        n_marked = sum(1 for row in kg for x in row if x["k"] in ("misplaced", "different"))
        out.append(dict(stem=stem, page=page, table=ti, caption=g.get("caption"), direction=g.get("direction") or "rtl",
                        featured=FEATURED_TABLES.get((stem, page, ti)), scorer_lists=len(wrong), n_marked=n_marked,
                        img=crop, key=kg, pipe=kp,
                        n_wrong=len(wrong), n_different=sum(1 for w in wrong.values() if w["kind"].startswith("different")),
                        key_shape=[len(gc), max((len(r) for r in gc), default=0)],
                        pipe_shape=[len(pc), max((len(r) for r in pc), default=0)],
                        triage_note=next((t.get("why") for (s, p, _), t in trg.items() if s == stem and p == page and t.get("why")), None)))
    out.sort(key=lambda t: (not t["featured"], -t["n_marked"]))
    say("tables", len(out))
    return out


# ------------------------------------------------------------------------------------------------ front matter
FRONT_PLAIN = {"P4.title": "Title", "P4.authors": "Author name", "P4.affiliation": "Affiliation",
               "P4.abstract": "Abstract", "P4.keywords": "Keywords", "P4.date_received": "Date received",
               "P4.date_accepted": "Date accepted", "P4.date_published": "Date published", "P4.doi": "DOI",
               "P4.first_printed_page_number": "First page number", "P4.last_printed_page_number": "Last page number"}
REFS_PLAIN = {"P9.authors": "Authors", "P9.year": "Year", "P9.title": "Title", "P9.source": "Source",
              "P9.volume": "Volume", "P9.issue": "Issue", "P9.pages": "Pages"}
KIND_PLAIN_FIELD = {"other side empty": "nothing stored", "part missing": "part missing", "part extra": "part extra",
                    "letters differ": "letters differ", "different text": "different text",
                    "different field boundary": "text sits in the next field", "items differ": "items differ",
                    "items missing": "items missing", "digits differ": "digits differ",
                    "abstract boundary: end": "ends in the wrong place", "abstract boundary: start": "starts in the wrong place",
                    "author count differs": "number of authors differs", "honorific only": "title (Dr., Prof.) only"}


def _toks(s):
    return set(fold(s).split())


def find_lines(stem, gold, pages):
    """Azure lines (page, [lines]) where a printed value sits: the line sharing most words with it, grown to
    neighbours that also share words (at most 6)."""
    g = _toks(gold)
    if not g:
        return None
    best = None
    for pg in pages:
        try:
            boxes, _, _ = line_boxes(stem, pg)
        except StopIteration:
            continue
        sc = {n: (len(_toks(l["text"]) & g) / max(1, len(_toks(l["text"])))) for n, l in boxes.items()}
        for n, v in sc.items():
            hit = len(_toks(boxes[n]["text"]) & g)
            if hit and (best is None or (v, hit) > best[0]):
                best = ((v, hit), pg, n, sc)
    if not best or best[0][0] < 0.5:
        return None
    _, pg, n, sc = best
    lines = [n]
    for step in (-1, 1):
        k = n + step
        while sc.get(k, 0) >= 0.5 and len(lines) < 6 and len(_toks(" ".join(line_boxes(stem, pg)[0][x]["text"] for x in lines)) & g) < len(g):
            lines.append(k)
            k += step
    return pg, sorted(lines)


def build_front():
    rows = [r for r in jl(f"{S.SCORES}/fields_content_wrong_FRONT.jsonl") if r["measure"] in FRONT_PLAIN]
    trg = C.defaultdict(list)
    for f in glob.glob(f"{OUT}/triage/P4_*.jsonl"):
        m = "P4." + os.path.basename(f)[3:-6]
        for t in jl(f):
            trg[(m, t["stem"])].append(t)
    out = []
    for i, r in enumerate(rows):
        stem = r["stem"]
        pk = packet(stem)
        allp = [p["page"] for p in pk["pages"]]
        cand = sorted(set(allp[:3] + allp[-3:]))
        gold = r.get("gold")
        crops = []
        targets = gold if isinstance(gold, list) and r["measure"] == "P4.abstract" else [as_text(gold)]
        for j, gt in enumerate(targets):
            if not gt:
                continue
            hit = find_lines(stem, gt, cand)
            if hit:
                c = crop_lines(stem, hit[0], hit[1], f"f{i}_{j}")
                if c:
                    crops.append(dict(img=c, page=hit[0], lines=hit[1]))
        g, p = as_text(gold), as_text(r.get("pred"))
        tri = None
        for t in trg.get((r["measure"], stem), []):
            if ws(as_text(t.get("key"))) == ws(g) or (r.get("author") and t.get("author") == r.get("author")):
                tri = dict(cls=t.get("cls"), sub=t.get("sub"), why=t.get("why"))
                break
        out.append(dict(stem=stem, measure=r["measure"], field=FRONT_PLAIN[r["measure"]], lang=r.get("lang"),
                        author=r.get("author"), kind=r.get("kind"), kind_plain=KIND_PLAIN_FIELD.get(r.get("kind"), r.get("kind")),
                        key=g, pipe=p, key_segs=segs(p, g) if g and p else None, pipe_segs=segs(g, p) if g and p else None,
                        crops=crops, triage=tri))
    say("front cards", len(out), "with a crop:", sum(1 for x in out if x["crops"]))
    return out


def build_refs():
    rows = [r for r in jl(f"{S.SCORES}/fields_content_wrong_REFS.jsonl") if r["measure"] in REFS_PLAIN]
    trg = {}
    for f in glob.glob(f"{OUT}/triage/P9_*.jsonl"):
        for t in jl(f):
            trg[(t.get("measure"), t["stem"], t.get("page"), t.get("ref"))] = t
    out = []
    for r in rows:
        stem, page = r["stem"], r["page"]
        lines = r.get("gold_lines") or []
        c = crop_lines(stem, page, lines, f"r{r['ref']}") if lines else None
        g, p = as_text(r.get("gold")), as_text(r.get("pred"))
        t = trg.get((r["measure"], stem, page, r["ref"]))
        out.append(dict(stem=stem, page=page, ref=r["ref"], measure=r["measure"], field=REFS_PLAIN[r["measure"]],
                        kind=r.get("kind"), kind_plain=KIND_PLAIN_FIELD.get(r.get("kind"), r.get("kind")),
                        key=g, pipe=p, key_segs=segs(p, g) if g and p else None, pipe_segs=segs(g, p) if g and p else None,
                        crops=[dict(img=c, page=page, lines=lines)] if c else [],
                        triage=dict(cls=t.get("cls"), sub=t.get("sub"), why=t.get("why")) if t else None))
    say("reference cards", len(out))
    return out


# ------------------------------------------------------------------------------------------------ beyond the exam
def build_beyond():
    items = []
    for stem, page, title, text in [
        ("0529-004-007-007", 1, "A page with no letters in the body text",
         "The scan shows the title, the author and the page number, but in the body only punctuation is printed: the body "
         "font did not render when the PDF was turned into an image. Azure still has text for those lines, from the PDF's "
         "own text layer. The keyers left this page out of the scores."),
        ("0529-004-007-007", 3, "The same font failure, two pages on",
         "The flow chart and its labels are printed; the six bullet items above it show only their bullets and full stops."),
        ("0246-021-003-004", 1, "A repository's cover sheet",
         "The page before the article is a cover sheet added by a repository (journal, issue, link). The keyers marked it "
         "as front matter of a cover sheet; it is not part of the article as printed."),
    ]:
        key = jload(f"{S.KEYS}/PAGE/final/{stem}_p{page:03d}.json") or {}
        if not packet(stem):
            continue
        items.append(dict(stem=stem, page=page, title=title, text=text, img=page_picture(stem, page),
                          keyer_note=key.get("why")))
    return items


# ------------------------------------------------------------------------------------------------ real errors
ERROR_KINDS = [
    ("list", "List items stored as paragraphs",
     "A printed numbered or dashed item is stored as its own piece, but labelled a paragraph."),
    ("refsplit", "References split in two, or a field left unparsed",
     "One printed reference is parsed as two pieces at a line end, or its title or pages are not taken out."),
    ("folio", "The page number merged into the running head",
     "The printed page number is joined to the header or footer line, so the page has no number of its own."),
    ("hamza", "A hamza added that the print does not have",
     "Azure writes «أ» or «إ» where the page prints a bare «ا»; the pipeline passes it on."),
]


def build_errors(data):
    """Example cards for the triage's ranked real pipeline errors (TRIAGE.md section 4): three per kind."""
    ref_lines = {(r["stem"], r["page"], r["ref"]): r.get("gold_lines") for r in jl(f"{S.SCORES}/fields_content_wrong_REFS.jsonl")}
    tri = {os.path.basename(f)[:-6]: jl(f) for f in glob.glob(f"{OUT}/triage/*.jsonl")}
    cards = {k: [] for k, _, _ in ERROR_KINDS}

    def pick(rows, n=3):
        seen, out = set(), []
        for r in rows:
            j = r["stem"][:4]
            if j in seen:
                continue
            seen.add(j)
            out.append(r)
            if len(out) == n:
                break
        return out

    def card(kind, r, lines, page, key, pipe, key_label="As printed", pipe_label="What the pipeline stored"):
        c = crop_lines(r["stem"], page, lines, f"e{kind}{'-'.join(map(str, lines[:2]))}") if lines else None
        cards[kind].append(dict(stem=r["stem"], page=page, lines=lines, img=c, key_label=key_label, pipe_label=pipe_label,
                                key=as_text(key), pipe=as_text(pipe),
                                key_segs=segs(as_text(pipe), as_text(key)) if key and pipe and kind != "list" else None,
                                pipe_segs=segs(as_text(key), as_text(pipe)) if key and pipe and kind != "list" else None,
                                why=r.get("why"), sub=r.get("sub")))

    for r in pick([r for r in tri.get("P1_list-item", []) if r.get("cls") == "PIPELINE" and "list-item -> paragraph" in (r.get("sub") or "")]):
        card("list", r, (r.get("lines") or [])[:5], r["page"], "List item", "Paragraph", "The answer key's label", "The pipeline's label")
        cards["list"][-1]["text"] = r.get("key_text")
    rs = [r for f in ("P9_authors", "P9_title", "P9_source", "P9_pages") for r in tri.get(f, [])
          if r.get("cls") == "PIPELINE" and re.search(r"split|not parsed|fragment|space or stray dot", r.get("sub") or "")]
    for r in pick(rs):
        card("refsplit", r, ref_lines.get((r["stem"], r["page"], r.get("ref"))) or [], r["page"], r.get("key"), r.get("pipeline"),
             f"{REFS_PLAIN.get(r.get('measure'), 'Field')}, as printed", "What the pipeline stored")
    for r in pick([r for r in tri.get("P1_page-number", []) if r.get("cls") == "PIPELINE"]):
        lines = r.get("lines") or []
        reg = None
        try:
            ix = S.article_index(r["stem"])
            for n in lines:
                for k, t in S.line_targets(r["stem"], r["page"], n):
                    if k == "region":
                        reg = ix["regions"][t]
        except Exception:  # noqa: BLE001
            reg = None
        # the crop also takes the running-head line the number was merged with
        allin = lines
        if reg:
            allin = sorted({n for n, l in line_boxes(r["stem"], r["page"])[0].items()
                            if any(t == ("region", reg["region_id"]) for t in S.line_targets(r["stem"], r["page"], n))} | set(lines))
        card("folio", r, allin[:4], r["page"], r.get("key_text"), (reg or {}).get("text"),
             "The page number, as printed", "The header / footer piece it was stored in")
    hz = [r for f, rows in tri.items() if f.startswith(("P4_", "P9_")) for r in rows
          if r.get("cls") == "PIPELINE" and "hamza" in (r.get("sub") or "")]
    for r in pick(hz):
        if r.get("ref") is not None:
            lines, page = ref_lines.get((r["stem"], r["page"], r["ref"])) or [], r["page"]
        else:
            pk = packet(r["stem"])
            hit = find_lines(r["stem"], as_text(r.get("key")), [p["page"] for p in pk["pages"]][:2]) if pk else None
            lines, page = (hit[1], hit[0]) if hit else ([], r.get("page") or 1)
        card("hamza", r, lines, page, r.get("key"), r.get("pipeline"))
    say("error cards", {k: len(v) for k, v in cards.items()})
    return [dict(kind=k, title=t, text=x, cards=cards[k]) for k, t, x in ERROR_KINDS]


# ------------------------------------------------------------------------------------------------ main
def status_of(sc):
    """Final when the scorer says all_final (scorecard.json from 2026-11-10 15:47 on); older scorecards only had a
    free-text status."""
    st = sc.get("status") or ""
    keys = {k: v.get("key_source") for k, v in (sc.get("inputs") or {}).items()}
    final = bool(sc["all_final"]) if "all_final" in sc else (not st or st.upper().startswith("FINAL"))
    return dict(final=final, word="FINAL" if final else "PROVISIONAL", banner=sc.get("banner"),
                scorer_says=None if "all_final" in sc else st, made=sc.get("made"), keys=keys,
                parts_without_keys=sc.get("parts_without_keys") or [])


def main():
    global FORCE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="re-cut every picture")
    FORCE = ap.parse_args().force
    os.makedirs(PG, exist_ok=True)
    sc = jload(f"{S.SCORES}/scorecard.json")
    ink_summary = jload(f"{OUT}/ink/summary.json", {}) or {}
    data = dict(built=time.strftime("%Y-%m-%d %H:%M"), status=status_of(sc),
                exam=dict(articles=len(ARTS), pages=sum(len(a["pages"]) for a in ARTS),
                          by_kind=dict(C.Counter(k for a in ARTS for k in a["pages"])),
                          journals=len({a["journal"] for a in ARTS})),
                scorecard=scorecard_rows(sc, ink_summary), limits=sc.get("limits") or [],
                r1=dict(rewrite_note=((sc.get("R1_settled") or {}).get("exact") or {}).get("rewrite_note"),
                        rewrite_letters=((sc.get("R1_settled") or {}).get("exact") or {}).get("rewrite_letters"),
                        order_only_lines=(sc.get("R1_settled") or {}).get("order_only_lines")))
    data["ink"] = build_ink()
    data["reading"] = build_reading()
    data["rewrites"] = build_rewrites(data["reading"])
    data["structure"] = build_structure()
    data["tables"] = build_tables()
    data["front"] = build_front()
    data["refs"] = build_refs()
    data["beyond"] = build_beyond()
    data["errors"] = build_errors(data)
    tmp = f"{PG}/exam.json.tmp"
    json.dump(data, open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, f"{PG}/exam.json")
    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(PG) for f in fs)
    say(f"wrote {PG}/exam.json; out/page holds {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
