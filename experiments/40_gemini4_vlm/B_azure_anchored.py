"""Experiment 40, approach B: "Azure's text, Gemini's structure".

gemini-4-argon gets the page image and Azure's lines (numbered, with boxes in 0-1000 page coordinates and Azure's own
role guess) and returns the page's STRUCTURE as line ids: blocks in reading order, each naming the Azure lines it is
made of (verse as two half-lines, tables as rows of cells, equations as LaTeX, footnotes with their markers). The
HTML is then assembled here, deterministically, from Azure's own text: no word comes from Gemini except
  * `fixes`: a clear misreading of one Azure line, {line, from, to, why}, applied as a substring replacement and
    reported (fixes.jsonl), never silent;
  * `math`: a garbled formula inside a line, {line, from, latex}, rendered as inline LaTeX;
  * `missed`: text printed on the page that Azure has no line for, inserted as a flagged block (data-added).
Every line must be used exactly once (or listed as `noise`), so drops and duplicates are counted exactly.

Variants (out/B_azure_anchored/variants/<v>/, tag B_azure_anchored_<v>_<pid>):
  v1   JSON line ids, thinking low, page image (3000 px)
  v2   as v1, thinking medium
  v3   Gemini writes the HTML itself (each block with data-lines="L001 L002"), text copied by the model
  v4   as v1 without the image (text and boxes only): what does the picture add?
  v5   as v1 with a strict fix policy (restore the ink letter by letter; never correct the print's own spelling)
  v6   as v1 with thinking high
Each variant also writes <v>_nofix/ (the same structure with no fix / missed / math applied) so the fixes are scored
on their own.

    /home/yassine/inkscript/.venv/bin/python B_azure_anchored.py --variant v1 [--pages pid ...|--sample|--docs]
    /home/yassine/inkscript/.venv/bin/python B_azure_anchored.py --variant v1 --assemble-only     (no calls)
    /home/yassine/inkscript/.venv/bin/python B_azure_anchored.py --evaluate v1                    (fix verdicts)
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import OUT, gemini, jpeg, page_image_path, sample, spent, strip_fences  # noqa: E402
from score import azure_doc_lines, units  # noqa: E402

TAG = "B_azure_anchored"
SUBCAP = (TAG, 3.5)
BASE = OUT / TAG
VARIANTS = {
    "v1": dict(mode="json", thinking="low", image=True),
    "v2": dict(mode="json", thinking="medium", image=True),
    "v3": dict(mode="html", thinking="low", image=True),
    "v4": dict(mode="json", thinking="low", image=False),
    "v5": dict(mode="json", thinking="low", image=True, strict=True),
    "v6": dict(mode="json", thinking="high", image=True),
}
STRICT = """
- STRICT FIX POLICY (this edition is a faithful transcription, not a corrected one): a fix must restore what the INK
  shows, letter by letter. Never correct the author's or printer's spelling, typos, grammar, missing hamza, alif
  maqsura vs ya, ta marbuta vs ha, or word spacing - if the print itself has a misspelt word or two words run together, keep them. Never
  normalise punctuation or quotation marks. Fix only where Azure's letters are not the printed letters (a dot read
  as a speck or missed, a letter shape mistaken for another, a digit misread, a word Azure cut short) and you can
  see it plainly at this resolution. Most pages need no fix at all.
"""
AR = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LA = re.compile(r"[A-Za-zÀ-ɏ]")


# ------------------------------------------------------------------------------------------------ inputs

def unit_of(pid: str) -> dict:
    return next(u for u in units("all") if u["page_id"] == pid)


def page_lines(u: dict) -> list[dict]:
    """Azure's non-empty lines with ids L001.. in Azure's order, boxes in pixels and in 0-1000."""
    if u["unit"] == "sample":
        raw = json.loads(Path(u["azure_file"]).read_text(encoding="utf-8"))["lines"]
    else:
        raw, _, _ = azure_doc_lines(u["stem"], u["page"])
    W, H = u["width"], u["height"]
    out = []
    for ln in raw:
        t = (ln.get("text") or "").strip()
        if not t:
            continue
        b = ln.get("box")
        k = dict(id=f"L{len(out) + 1:03d}", text=t, kind=ln.get("kind") or "text", px=b,
                 b=[round(b[0] * 1000 / W), round(b[1] * 1000 / H), round(b[2] * 1000 / W), round(b[3] * 1000 / H)]
                 if b else None)
        out.append(k)
    return out


def line_table(lines) -> str:
    return "\n".join(f"{l['id']} [{','.join(map(str, l['b'])) if l['b'] else '?'}] ({l['kind']}) {l['text']}"
                     for l in lines)


# ------------------------------------------------------------------------------------------------ prompts

COMMON = """You are restructuring one scanned page of an Arabic journal article (it may contain French or English) into
a clean digital edition. A trusted OCR engine (Azure) has already read the page; its lines are listed below, one per
row: line id, box [x0,y0,x1,y1] in 0-1000 page coordinates (x from the LEFT edge, y from the top), Azure's own role
guess in parentheses (often wrong: "text" is anything), then the text exactly as Azure read it.
{image_note}
AZURE'S LINES (in Azure's order, which is not always the reading order):
{lines}
"""

JSON_TASK = """
YOUR JOB: give the page's structure, built ONLY from these line ids. Azure's text is the text of the edition; you do
not retype it. Return one JSON object:

{{
 "blocks": [ ... in true reading order: right-hand column before left-hand column for Arabic, top to bottom ... ],
 "splits": [ {{"line": "L012", "parts": ["first part", "second part"]}} ],
 "noise": ["L040"],
 "fixes": [ {{"line": "L007", "from": "exact substring of Azure's text", "to": "what is printed", "why": "short"}} ],
 "math": [ {{"line": "L009", "from": "exact substring of Azure's text", "latex": "LaTeX of that formula"}} ],
 "missed": [ {{"after": "L015", "type": "paragraph", "text": "printed text Azure has no line for"}} ]
}}

Each block: {{"type": T, "lines": ["L001", "L002", ...]}} with the lines in reading order, where T is one of
  title, heading, subheading   (article title; section headings; sub-headings)
  paragraph                    (body text; one block per paragraph, so start a new block where a paragraph starts)
  list_item                    (add "list": "ol" or "ul"; one block per item)
  reference                    (one bibliography / reference-list entry per block)
  footnote                     (one footnote per block; add "marker": the footnote's number as printed, e.g. "(1)")
  verse                        (one line of poetry: instead of "lines" give "hemistichs": [["L010"], ["L011"]] - the
                                right half-line first; if one Azure line holds both halves, split it with "splits")
  quote                        (a Quran verse or quotation set apart from the paragraph)
  table                        (instead of "lines" give "rows": [[{{"lines": ["L020"], "th": true, "colspan": 1,
                                "rowspan": 1}}, ...], ...], cells right to left as printed for an Arabic table,
                                an empty cell is {{"lines": []}}; the table caption is its own "caption" block)
  equation                     (a displayed formula: "lines" as usual plus "latex": the formula in LaTeX)
  caption                      (caption of a table or figure)
  figure                       (a picture/chart; "lines" = any text printed inside it)
  header, footer               (running head, page number, journal name: page furniture)
  other
Optional on any block: "lang": "ar" | "fr" | "en". On a paragraph, "calls": [{{"line": "L005", "marker": "(1)"}}] marks
footnote call numbers printed inside the text.

RULES
- Use EVERY line id exactly once across blocks (a line in "noise" is not used): never drop a line, never repeat one.
  "noise" is only for things that are not printed text at all (scanner specks, a stamp read as letters).
- "splits" only when one Azure line contains text that belongs to two different blocks (two columns run together,
  both half-lines of a verse, a heading glued to a paragraph). The parts must be Azure's text cut in two, unchanged;
  then use "L012a", "L012b" instead of "L012".
- "fixes": only where the image shows beyond doubt that Azure misread the printed text (a wrong or missing letter,
  dot, digit or word, a missing vowel mark that is clearly printed). Keep spelling as printed even if it is
  old-fashioned or a typo in the original. "from" must be an exact substring of that line. When in doubt, no fix.
- "math": formulas Azure turned into garbage inside a line (not displayed equations - those are equation blocks).
- "missed": only printed text that no Azure line covers.
- Return only the JSON object.
"""

HTML_TASK = """
YOUR JOB: write the page as semantic HTML (a fragment, no <html>/<head>), built from Azure's lines in true reading
order (right-hand column first for Arabic). Every block element carries data-lines="L001 L002" naming the Azure lines
it uses, in order; every line id must appear exactly once in the whole HTML. Copy Azure's text exactly; change it only
where the image shows beyond doubt that Azure misread it, and list each such change in a final
<!-- FIXES: [{{"line": "L007", "from": "...", "to": "...", "why": "..."}}] --> comment.

Elements: <h1> title, <h2>/<h3> headings, <p> paragraph, <ol>/<ul><li> lists, <ol class="references"><li>
bibliography, <aside class="footnote" id="fn1"> footnote (calls in the text as <sup><a href="#fn1">(1)</a></sup>),
<div class="verse"><span class="hemistich">right half</span><span class="hemistich">left half</span></div> per verse
line, <blockquote> Quran or quotation, <table> with <tr><th>/<td> (rowspan/colspan) and <caption>, displayed formula
<div class="equation"><span class="math">\\[LaTeX\\]</span></div>, inline formula <span class="math">\\(LaTeX\\)</span>,
<figure> picture, <p class="caption"> caption, <header class="furniture"> / <footer class="furniture"> running heads and
page numbers, <div class="other">. Use dir="rtl" lang="ar" or dir="ltr" lang="fr"/"en" on blocks.
Return only the HTML.
"""


def make_prompt(lines, var) -> str:
    note = ("The page image is attached: use it to see columns, reading order, verse, tables, footnotes and to check "
            "Azure's text.") if var["image"] else "(No image is given: judge from the boxes and the text.)"
    task = JSON_TASK if var["mode"] == "json" else HTML_TASK
    if var.get("strict"):
        task = task.replace("- Return only the JSON object.", STRICT.strip("\n") + "\n- Return only the JSON object.")
    return COMMON.format(image_note=note, lines=line_table(lines)) + task


# ------------------------------------------------------------------------------------------------ assembly

def is_rtl(t: str) -> bool:
    return len(AR.findall(t)) >= len(LA.findall(t))


def union(bs):
    bs = [b for b in bs if b]
    if not bs:
        return None
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def norm_ws(s):
    return re.sub(r"\s+", "", s)


class Page:
    """The line store of one page after splits (and, when apply=True, fixes / math)."""

    def __init__(self, lines, ans, apply=True):
        self.lines = {l["id"]: dict(l) for l in lines}
        self.order = [l["id"] for l in lines]
        self.issues = []
        self.applied, self.rejected = [], []
        for s in ans.get("splits") or []:
            lid, parts = s.get("line"), s.get("parts") or []
            if lid in self.lines and len(parts) >= 2 and norm_ws("".join(parts)) == norm_ws(self.lines[lid]["text"]):
                base = self.lines[lid]
                b, n, acc = base["b"], sum(len(norm_ws(p)) for p in parts) or 1, 0
                rtl = is_rtl(base["text"])
                for k, p in enumerate(parts):
                    # the part's box: the line's box cut in proportion to its letters (right to left for Arabic)
                    f0, f1 = acc / n, (acc + len(norm_ws(p))) / n
                    acc += len(norm_ws(p))
                    pb = None
                    if b:
                        w = b[2] - b[0]
                        pb = ([round(b[2] - f1 * w), b[1], round(b[2] - f0 * w), b[3]] if rtl else
                              [round(b[0] + f0 * w), b[1], round(b[0] + f1 * w), b[3]])
                    self.lines[f"{lid}{'abcdefgh'[k]}"] = dict(base, id=f"{lid}{'abcdefgh'[k]}", text=p.strip(),
                                                                split_of=lid, b=pb)
                self.lines[lid]["split"] = True
            else:
                self.issues.append(dict(kind="bad_split", item=s))
        self.math = {}
        if apply:
            for f in ans.get("fixes") or []:
                lid = f.get("line")
                L = self.get(lid, f.get("from"))
                if L is None or not f.get("from") or f["from"] not in L["text"] or f.get("from") == f.get("to"):
                    self.rejected.append(f)
                    continue
                L["text"] = L["text"].replace(f["from"], f.get("to") or "", 1)
                self.applied.append(dict(f, base=lid))
            for m in ans.get("math") or []:
                L = self.get(m.get("line"), m.get("from"))
                if L is None or not m.get("from") or m["from"] not in L["text"] or not m.get("latex"):
                    self.rejected.append(dict(m, kind="math"))
                    continue
                self.math.setdefault(L["id"], []).append(m)

    def get(self, lid, sub=None):
        """The line a fix aims at; when that line was split, the part holding the fix's text."""
        L = self.lines.get(lid)
        if L is not None and L.get("split") and sub:
            parts = [x for x in self.lines.values() if x.get("split_of") == lid and sub in x["text"]]
            return parts[0] if parts else None
        return L

    def text_html(self, lid, calls=()):
        L = self.lines[lid]
        t = L["text"]
        ms = self.math.get(lid, [])
        if not ms and not calls:
            return html.escape(t)
        # placeholders so escaping does not touch them
        reps = {}
        for k, m in enumerate(ms):
            ph = f"{k}"
            t = t.replace(m["from"], ph, 1)
            reps[ph] = f'<span class="math">\\({html.escape(m["latex"])}\\)</span>'
        for k, (marker, fn) in enumerate(calls):
            ph = f"{k}"
            if marker and marker in t:
                t = t.replace(marker, ph, 1)
                reps[ph] = f'<sup><a href="#fn{fn}">{html.escape(marker)}</a></sup>'
        t = html.escape(t)
        for ph, r in reps.items():
            t = t.replace(html.escape(ph), r)
        return t


def bbox_attr(b):
    return f' data-bbox="{b[0]},{b[1]},{b[2]},{b[3]}"' if b else ""


def fn_key(marker):
    d = re.sub(r"\D", "", (marker or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")))
    return d or re.sub(r"\W", "", marker or "") or "x"


def assemble(lines, ans, apply=True) -> tuple[str, dict]:
    """HTML of the page from Gemini's structure and Azure's text; and the bookkeeping (used, dropped, duplicated)."""
    P = Page(lines, ans, apply)
    used = []
    out = []
    open_list = None                                     # "ol" / "ul" / "references"

    def take(ids):
        res = []
        for i in ids or []:
            i = str(i).strip()
            if i in P.lines and not P.lines[i].get("split"):
                used.append(i)
                res.append(i)
            elif i in P.lines and P.lines[i].get("split"):  # the whole line named after it was split: its parts
                parts = [k for k in P.lines if P.lines[k].get("split_of") == i]
                used.extend(parts)
                res.extend(parts)
            else:
                P.issues.append(dict(kind="unknown_id", id=i))
        return res

    def attrs(ids, blk, extra=""):
        t = " ".join(P.lines[i]["text"] for i in ids)
        lang = blk.get("lang") or ("ar" if is_rtl(t) else ("fr" if re.search(r"[éèàçêù]", t) else "en"))
        d = "rtl" if lang == "ar" else "ltr"
        return f'{extra}{bbox_attr(union([P.lines[i]["b"] for i in ids]))} dir="{d}" lang="{lang}"' \
               f' data-lines="{" ".join(ids)}"'

    def join(ids, calls=()):
        cs = {}
        for c in calls:
            cs.setdefault(c.get("line"), []).append((c.get("marker"), fn_key(c.get("marker"))))
        return " ".join(P.text_html(i, cs.get(i, []) + cs.get(P.lines[i].get("split_of"), [])) for i in ids)

    def close_list():
        nonlocal open_list
        if open_list:
            out.append("</ol>" if open_list != "ul" else "</ul>")
            open_list = None

    missed_after = {}
    if apply:
        for m in ans.get("missed") or []:
            if (m.get("text") or "").strip():
                missed_after.setdefault(m.get("after"), []).append(m)

    def emit_missed(ids):
        for i in ids:
            for m in missed_after.pop(i, []) + missed_after.pop(P.lines[i].get("split_of"), []):
                t = m["text"].strip()
                d = "rtl" if is_rtl(t) else "ltr"
                tag = {"heading": "h2", "title": "h1", "footnote": "aside"}.get(m.get("type"), "p")
                cls = ' class="footnote"' if tag == "aside" else ""
                out.append(f'<{tag}{cls} dir="{d}" data-added="gemini">{html.escape(t)}</{tag}>')

    for blk in ans.get("blocks") or []:
        if not isinstance(blk, dict):
            continue
        T = (blk.get("type") or "paragraph").lower()
        want = {"list_item": blk.get("list") if blk.get("list") in ("ol", "ul") else "ol",
                "reference": "references"}.get(T)
        if want != open_list:
            close_list()
            if want:
                out.append('<ol class="references">' if want == "references" else f"<{want}>")
                open_list = want
        if T == "verse":
            hs = blk.get("hemistichs") or ([blk["lines"]] if blk.get("lines") else [])
            hids = [take(h if isinstance(h, list) else [h]) for h in hs]
            allids = [i for h in hids for i in h]
            if not allids:
                continue
            spans = "".join(f'<span class="hemistich"{bbox_attr(union([P.lines[i]["b"] for i in h]))}>{join(h)}</span>'
                            for h in hids if h)
            out.append(f'<div class="verse"{attrs(allids, blk)}>{spans}</div>')
            emit_missed(allids)
            continue
        if T == "table":
            rows = blk.get("rows") or []
            allids, trs = [], []
            for r in rows:
                cells = []
                for c in r if isinstance(r, list) else []:
                    c = c if isinstance(c, dict) else {"lines": [c]}
                    ids = take(c.get("lines"))
                    allids += ids
                    tg = "th" if c.get("th") else "td"
                    sp = "".join(f' {k}="{int(c[k])}"' for k in ("colspan", "rowspan")
                                 if str(c.get(k, 1)).isdigit() and int(c.get(k, 1)) > 1)
                    cells.append(f"<{tg}{sp}{bbox_attr(union([P.lines[i]['b'] for i in ids]))}>{join(ids)}</{tg}>")
                trs.append("<tr>" + "".join(cells) + "</tr>")
            extra = take(blk.get("lines"))                 # lines given loosely for a table: one row each
            for i in extra:
                trs.append(f"<tr><td{bbox_attr(P.lines[i]['b'])}>{join([i])}</td></tr>")
            allids += extra
            if not allids:
                continue
            d = "rtl" if is_rtl(" ".join(P.lines[i]["text"] for i in allids)) else "ltr"
            out.append(f'<table{bbox_attr(union([P.lines[i]["b"] for i in allids]))} dir="{d}" '
                       f'data-lines="{" ".join(allids)}">' + "".join(trs) + "</table>")
            emit_missed(allids)
            continue
        ids = take(blk.get("lines"))
        if not ids and not (T == "equation" and blk.get("latex")):
            continue
        calls = blk.get("calls") or []
        if T == "equation":
            lx = (blk.get("latex") or "").strip()
            if lx:
                out.append(f'<div class="equation"{attrs(ids, blk) if ids else ""}><span class="math">'
                           f'\\[{html.escape(lx)}\\]</span></div>')
            else:
                out.append(f'<div class="equation"{attrs(ids, blk)}>{join(ids)}</div>')
        else:
            tag, cls = {"title": ("h1", ""), "heading": ("h2", ""), "subheading": ("h3", ""),
                        "list_item": ("li", ""), "reference": ("li", ""),
                        "footnote": ("aside", ' class="footnote"'), "quote": ("blockquote", ""),
                        "caption": ("p", ' class="caption"'), "figure": ("figure", ""),
                        "header": ("header", ' class="furniture"'), "footer": ("footer", ' class="furniture"'),
                        "other": ("div", ' class="other"')}.get(T, ("p", ""))
            if T == "footnote":
                cls += f' id="fn{fn_key(blk.get("marker"))}"'
            inner = join(ids, calls)
            if T == "figure":
                inner = f'<figcaption>{inner}</figcaption>' if ids else ""
            out.append(f"<{tag}{cls}{attrs(ids, blk)}>{inner}</{tag}>")
        emit_missed(ids)
    close_list()
    for k, ms in missed_after.items():                  # anchors that never came up: at the end
        for m in ms:
            out.append(f'<p dir="{"rtl" if is_rtl(m["text"]) else "ltr"}" data-added="gemini">{html.escape(m["text"])}</p>')

    # bookkeeping on Azure's ORIGINAL lines (a split line is used when all its parts are)
    noise = {str(x) for x in (ans.get("noise") or [])}
    from collections import Counter
    cnt = Counter(used)
    base_used = Counter()
    for i, n in cnt.items():
        base_used[P.lines[i].get("split_of") or i] += n
    nparts = Counter(P.lines[i]["split_of"] for i in P.lines if P.lines[i].get("split_of"))
    dropped = [l["id"] for l in lines if base_used[l["id"]] == 0 and l["id"] not in noise]
    dup = [l["id"] for l in lines if base_used[l["id"]] > max(1, nparts.get(l["id"], 1))]
    partial = [l["id"] for l in lines if 0 < base_used[l["id"]] < nparts.get(l["id"], 1)]
    book = dict(lines=len(lines), used=sum(1 for l in lines if base_used[l["id"]] > 0),
                dropped=dropped, duplicated=dup, partial=partial, noise=sorted(noise),
                dropped_chars=sum(len(l["text"]) for l in lines if l["id"] in dropped),
                chars=sum(len(l["text"]) for l in lines),
                splits=sum(1 for l in lines if P.lines[l["id"]].get("split")),
                fixes_applied=P.applied, fixes_rejected=P.rejected, math=sum(len(v) for v in P.math.values()),
                missed=[m for m in (ans.get("missed") or []) if (m.get("text") or "").strip()] if apply else [],
                issues=P.issues[:20], blocks=len(ans.get("blocks") or []))
    return "\n".join(out) + "\n", book


# ------------------------------------------------------------------------------------------------ v3 (HTML) bookkeeping

def html_book(lines, h) -> dict:
    """Which line ids an HTML answer used (data-lines), and how far its text moved from Azure's."""
    from collections import Counter
    ids = re.findall(r'data-lines="([^"]*)"', h)
    cnt = Counter(i for s in ids for i in s.split())
    base = Counter()
    for i, n in cnt.items():
        base[re.sub(r"[a-h]$", "", i)] += n
    fx = []
    m = re.search(r"<!--\s*FIXES:\s*(\[.*?\])\s*-->", h, re.S)
    if m:
        try:
            fx = json.loads(m.group(1))
        except Exception:
            fx = []
    return dict(lines=len(lines), used=sum(1 for l in lines if base[l["id"]] > 0),
                dropped=[l["id"] for l in lines if base[l["id"]] == 0],
                duplicated=[l["id"] for l in lines if base[l["id"]] > 1],
                dropped_chars=sum(len(l["text"]) for l in lines if base[l["id"]] == 0),
                chars=sum(len(l["text"]) for l in lines), fixes_applied=fx, fixes_rejected=[], missed=[], math=0)


def add_bboxes(lines, h) -> str:
    """v3: give every block with data-lines the union of its lines' boxes (the model's own boxes are not asked)."""
    L = {l["id"]: l for l in lines}

    def rep(m):
        tag = m.group(0)
        if "data-bbox" in tag:
            return tag
        ids = [re.sub(r"[a-h]$", "", i) for i in m.group(1).split()]
        b = union([L[i]["b"] for i in ids if i in L])
        return tag[:-1] + bbox_attr(b) + ">" if b else tag
    return re.sub(r'<[a-z0-9]+\b[^>]*data-lines="([^"]*)"[^>]*>', rep, h)


# ------------------------------------------------------------------------------------------------ run

def vdir(v, nofix=False) -> Path:
    return BASE / "variants" / (v + ("_nofix" if nofix else ""))


def run_page(pid, v, call=True) -> dict | None:
    var = VARIANTS[v]
    u = unit_of(pid)
    lines = page_lines(u)
    d = vdir(v)
    raw = d / "raw" / f"{pid}.json"
    ans = None
    if raw.exists():
        ans = json.loads(raw.read_text(encoding="utf-8"))["answer"]
    elif call:
        prompt = make_prompt(lines, var)
        imgs = [jpeg(__import__("cv2").imread(str(page_image_path(pid))), 3000, 90)] if var["image"] else []
        info = {}
        n_out = 4000 + 60 * len(lines) + (6000 if var["thinking"] == "medium" else 3000)
        if var["mode"] == "html":
            n_out += sum(len(l["text"]) for l in lines) // 1          # the model retypes every character
        ans, usd = gemini(prompt, images=imgs, tag=f"{TAG}_{v}_{pid}", json_out=var["mode"] == "json",
                          max_out=min(n_out, 32000), thinking=var["thinking"], subcap=SUBCAP, info=info)
        if ans is None:
            print(f"  {pid}: no answer ({info.get('finish') or info.get('error') or 'refused'})", flush=True)
            return None
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(json.dumps(dict(answer=ans, info=info), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {pid}: ${usd:.4f} {info.get('tin')} in / {info.get('tout')} out ({info.get('think')} thinking) "
              f"{info.get('secs', 0):.0f}s", flush=True)
    if ans is None:
        return None
    if var["mode"] == "json":
        if isinstance(ans, list):
            ans = {"blocks": ans}
        h, book = assemble(lines, ans, apply=True)
        h0, _ = assemble(lines, ans, apply=False)
    else:
        h = add_bboxes(lines, strip_fences(ans))
        book = html_book(lines, h)
        h0 = h
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pid}.html").write_text(h, encoding="utf-8")
    vdir(v, True).mkdir(parents=True, exist_ok=True)
    (vdir(v, True) / f"{pid}.html").write_text(h0, encoding="utf-8")
    (d / "book").mkdir(exist_ok=True)
    (d / "book" / f"{pid}.json").write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
    return book


# ------------------------------------------------------------------------------------------------ evaluation

def _truth_lines(u) -> list[str] | None:
    import evaluate as e36  # noqa: F401  (on sys.path through score)
    from score import e36, gold_load, GOLD, DIG, jload
    if u.get("truth") == "gold":
        return [l["text"] for l in e36.gold_lines(gold_load(GOLD / f"{u['page_id']}.json"))]
    if u.get("truth") == "born_digital":
        return [l["text"].translate(DIG) for l in jload(u["truth_file"])["lines"]]
    return None


def semiglobal(a: str, b: str) -> int:
    """Edit distance of a against the best-matching substring of b."""
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ai != b[j - 1]))
        prev = cur
    return min(prev)


def _tri(s):
    from collections import Counter
    s = s.replace(" ", "")
    return Counter(s[i:i + 3] for i in range(len(s) - 2))


def fix_verdicts(v: str, pids=None) -> list[dict]:
    """Each applied fix on a truth page: right (closer to the truth), wrong (further), neutral; faithful text and
    folded (no vowel marks / letter variants)."""
    from score import DIG
    from inkscript.gold.text import folded
    d = vdir(v)
    out = []
    for f in sorted((d / "book").glob("*.json")):
        pid = f.stem
        if pids and pid not in pids:
            continue
        u = unit_of(pid)
        T = _truth_lines(u)
        if T is None:
            continue
        bd = u.get("truth") == "born_digital"
        lines = {l["id"]: l["text"] for l in page_lines(u)}
        book = json.loads(f.read_text(encoding="utf-8"))
        items = [("fix", x) for x in book["fixes_applied"]] + [("missed", x) for x in book.get("missed", [])]
        for kind, x in items:
            if kind == "fix":
                o = lines.get(x.get("base") or x["line"]) or lines.get(re.sub(r"[a-h]$", "", x["line"]), "")
                if x["from"] not in o:
                    continue
                n = o.replace(x["from"], x.get("to") or "", 1)
            else:
                o, n = "", x["text"]
            if bd:
                o, n = o.translate(DIG), n.translate(DIG)
            key = n if kind == "missed" else o
            tk = _tri(key)
            sc = [sum((tk & _tri(t)).values()) for t in T]
            k = max(range(len(T)), key=lambda i: sc[i]) if T else 0
            win = " ".join(T[max(0, k - 1):k + 2])
            row = dict(page=pid, kind=kind, line=x.get("line") or x.get("after"), frm=x.get("from"), to=x.get("to"),
                       text=x.get("text"), why=x.get("why"))
            for lab, fn in (("faithful", lambda s: s), ("folded", folded)):
                if kind == "fix":
                    do, dn = semiglobal(fn(o), fn(win)), semiglobal(fn(n), fn(win))
                    row[lab] = "right" if dn < do else "wrong" if dn > do else "neutral"
                else:
                    dn = semiglobal(fn(n), fn(win))
                    row[lab] = "right" if dn <= 0.2 * max(1, len(fn(n))) else "wrong"
            out.append(row)
    return out


def report(v: str, pids=None) -> dict:
    """Score the variant's pages (only those it has) with score.py's own page_eval, plus the line bookkeeping and the
    fix verdicts; writes variants/<v>/report.json."""
    from score import page_eval, summarise, costs
    d = vdir(v)
    have = [f.stem for f in d.glob("*.html")]
    if pids:
        have = [p for p in have if p in pids]
    us = [u for u in units("all") if u["page_id"] in have]
    res = {}
    for name, dd in (("with_fixes", d), ("no_fixes", vdir(v, True))):
        cs = costs(dd, f"{TAG}_{v}_", us)
        rows = []
        for u in us:
            r = page_eval(u, dd)
            r["usd"], r["secs"] = cs["per_page"].get(u["page_id"], [0.0, 0.0])
            rows.append(r)
        res[name] = summarise(rows)
        res[name + "_rows"] = rows
    # order-free text error vs the truth: words in one and not the other (multiset), over truth words. The gold
    # pages keep Azure's line breaks, so a two-column line Azure ran across both columns stays merged in the gold:
    # the scorer's character error rate then charges a correct column split as a reading-order error.
    from collections import Counter
    from score import blocks_of, DIG
    bag = {}
    for name, dd in (("with_fixes", d), ("no_fixes", vdir(v, True)), ("azure", OUT / "a0_azure")):
        e = n = 0
        per = {}
        for u in us:
            T = _truth_lines(u)
            if T is None:
                continue
            bl = blocks_of((dd / f"{u['page_id']}.html").read_text(encoding="utf-8"))
            P = " ".join(b["text"] for b in bl)
            if u.get("truth") == "born_digital":
                P = P.translate(DIG)
            G = Counter(" ".join(T).split())
            Pc = Counter(P.split())
            ee = sum((G - Pc).values()) + sum((Pc - G).values())
            per[u["page_id"]] = round(ee / max(1, sum(G.values())), 4)
            e += ee
            n += sum(G.values())
        bag[name] = dict(word_bag_err=round(e / n, 4) if n else None, per_page=per)
    res["truth_word_bag"] = bag
    books = {p: json.loads((d / "book" / f"{p}.json").read_text(encoding="utf-8")) for p in have}
    L = sum(b["lines"] for b in books.values())
    res["lines"] = dict(pages=len(books), lines=L,
                        dropped=sum(len(b["dropped"]) for b in books.values()),
                        duplicated=sum(len(b["duplicated"]) for b in books.values()),
                        partial=sum(len(b.get("partial", [])) for b in books.values()),
                        noise=sum(len(b.get("noise", [])) for b in books.values()),
                        dropped_chars=sum(b["dropped_chars"] for b in books.values()),
                        chars=sum(b["chars"] for b in books.values()),
                        splits=sum(b.get("splits", 0) for b in books.values()),
                        fixes=sum(len(b["fixes_applied"]) for b in books.values()),
                        fixes_rejected=sum(len(b["fixes_rejected"]) for b in books.values()),
                        missed=sum(len(b.get("missed", [])) for b in books.values()),
                        math=sum(b.get("math", 0) for b in books.values()),
                        pages_with_drop=sum(1 for b in books.values() if b["dropped"]),
                        pages_with_dup=sum(1 for b in books.values() if b["duplicated"]))
    fv = fix_verdicts(v, have)
    from collections import Counter
    res["fix_verdicts"] = {lab: dict(Counter(r[lab] for r in fv)) for lab in ("faithful", "folded")}
    res["fix_verdicts_by_kind"] = {k: {lab: dict(Counter(r[lab] for r in fv if r["kind"] == k))
                                       for lab in ("faithful", "folded")} for k in ("fix", "missed")}
    res["fix_rows"] = fv
    (d / "report.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def show(v, pids=None):
    r = report(v, pids)
    keys = ("pages", "cer_gold", "cer_bd", "cer_az", "invented_per_1000w", "dropped_per_1000w", "layout_text_acc",
            "layout_box_acc", "box_hit", "word_order", "teds_vs_pro_draft", "eq_sim_vs_pro_draft", "usd_per_page")
    for name in ("with_fixes", "no_fixes"):
        for grp in ("all", "truth_gold", "truth_bd", "multicolumn", "doc_pages"):
            s = r[name].get(grp)
            if s:
                print(f"  {v} {name:10} {grp:11} " + " ".join(f"{k}={s[k]}" for k in keys if s.get(k) is not None))
    print("  lines", r["lines"])
    print("  truth word-bag error", {k: x["word_bag_err"] for k, x in r["truth_word_bag"].items()})
    print("  fix verdicts", r["fix_verdicts"], r["fix_verdicts_by_kind"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="v1", choices=list(VARIANTS))
    ap.add_argument("--pages", nargs="*")
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--docs", action="store_true")
    ap.add_argument("--assemble-only", action="store_true")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--report", action="store_true", help="score / bookkeeping / fix verdicts only, no calls")
    a = ap.parse_args()
    if a.report:
        show(a.variant, a.pages or None)
        return
    pids = list(a.pages or [])
    if a.sample:
        pids += [p["page_id"] for p in sample()["pages"]]
    if a.docs:
        pids += [u["page_id"] for u in units("docs") if u["unit"] == "doc"]
    print(f"variant {a.variant}: {len(pids)} pages; {TAG} spent so far ${spent(TAG):.4f} (sub-cap ${SUBCAP[1]})")
    with ThreadPoolExecutor(min(4, a.threads)) as ex:
        books = list(ex.map(lambda p: (p, run_page(p, a.variant, call=not a.assemble_only)), pids))
    for p, b in books:
        if b:
            print(f"  {p:28} used {b['used']}/{b['lines']} dropped {len(b['dropped'])} dup {len(b['duplicated'])} "
                  f"fixes {len(b['fixes_applied'])} (+{len(b['fixes_rejected'])} rejected) missed {len(b['missed'])}")
    print(f"{TAG} spent ${spent(TAG):.4f}")


if __name__ == "__main__":
    main()
