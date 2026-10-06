"""The article's structure, read from the page as a reader reads it (experiment 26): what is page furniture,
what is the title, who wrote it, where the sections start, which notes sit at the foot of a page and which
marker in the text points at each.

    meta = read_meta(stem, dirs)            # Gemini's title file (if one exists) and the Mandumah id's parts
    st = analyse(doc, meta, scan_pdf)       # doc from document.load; scan_pdf optional (stroke widths)

Nothing here is a single position rule. Each decision looks at several things a reader sees:

  furniture   page numbers (digits alone at the top or bottom), running heads and footers (short text at the
              top or bottom that repeats on other pages, the journal's masthead), text turned on its side in the
              outer margin (a side tab), and short text in the top 8% / bottom 6%.
  notes       the block of small lines at the foot of a page (letters at most 86% of the body's height, read from
              the bottom up until a body-size line), accepted only when one of its lines opens with a bracketed
              number "(3)", "3)", "[3]"; each line that opens with a number starts a note, the others continue it.
  markers     for each note, the place in that page's text that points at it: the number in brackets glued to a
              word ("عاصم(٢)."), alone ("(٢)", "٢)"), or a bare number raised above its line; when several, the
              one in order after the previous note's marker, never a verse or page number ("الآية (١٣)").
  title       Gemini's title (the title file already in the bucket), aligned to Azure's words on the first pages
              so the title points at its ink; without it, the largest letters on page 1 before the text begins,
              adjacent lines of nearly the same size joined (a title set over two lines).
  authors     Gemini's names aligned the same way; without them, the line after the title that opens with a
              byline word (بقلم, إعداد, الدكتور, الأستاذ, الشيخ, د.) or is a short line of its own; the honorific
              is kept apart (JATS <prefix>), the next lines of the byline paragraph are the affiliation.
  headings    a short paragraph (at most 2 lines, 14 words, narrower than the column) that stands out by size
              (>= 1.2x the body), by bold-looking ink (stroke width >= 1.2x the body's, from the scan), or that is
              numbered / opens with a section word / ends with a colon and is set apart by bold or space;
              lists (3+ short numbered lines in a row), quotations, the title repeated, separators are not.

Every measurement is relative to the document's body text: the letter height and stroke width of lines of 6
words or more in the top 60% of pages.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import statistics
from collections import Counter
from pathlib import Path

import numpy as np

from .quran import norm

_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
NUMONLY = re.compile(r"^[\s\d٠-٩۰-۹\-–—()\[\].,،/•●■|*]+$")
MAST = re.compile(r"مجلة|العدد|السنة|المجلد|عدد")
DIGIT = re.compile(r"[\d٠-٩۰-۹]")
NUM = r"[0-9٠-٩۰-۹]{1,3}"
# a note's label at the start of its line: "(3)", "3)", "[3]", "(3" (a lost bracket); a bare "3 -" only counts
# once the block has a bracketed one
NOTE_LABEL = re.compile(rf"^\s*(?:[(\[]\s*({NUM})\s*[)\]]?|({NUM})\s*[)\]])\s*[-–.:]?$")
NOTE_LABEL_HEAD = re.compile(rf"^\s*(?:[(\[]\s*({NUM})\s*[)\]]?|({NUM})\s*[)\]])")
BARE_LABEL = re.compile(rf"^\s*({NUM})\s*[-–.]?$")
BYLINE = ("بقلم", "اعداد", "تاليف", "كتبه", "للدكتور", "للاستاذ", "للشيخ", "الدكتور", "الدكتوره", "دكتور",
          "الاستاذ", "الشيخ", "د", "ا", "اد", "ذ", "المستشار", "الامام", "السيد", "الباحث", "الباحثه")
HONORIFIC = ("للدكتور", "للاستاذ", "للشيخ", "الدكتور", "الدكتوره", "دكتور", "الاستاذ", "الشيخ", "د", "ا", "اد",
             "ذ", "المستشار", "الامام", "السيد", "الباحث", "الباحثه", "بقلم", "اعداد", "تاليف", "كتبه")
AFF_WORDS = ("جامعه", "كليه", "قسم", "معهد", "مركز", "استاذ", "الاستاذ", "المدرس", "مدرس", "باحث", "عضو", "رئيس")
SECTION_WORDS = ("اولا", "ثانيا", "ثالثا", "رابعا", "خامسا", "سادسا", "سابعا", "ثامنا", "تاسعا", "عاشرا",
                 "المبحث", "الفصل", "المطلب", "الفرع", "المساله", "تمهيد", "التمهيد", "مقدمه", "المقدمه", "تقديم",
                 "خاتمه", "الخاتمه", "النتائج", "التوصيات", "الباب", "القسم", "المحور", "الزمره", "توطئه", "مدخل")
ROMAN = re.compile(r"^(?=[IVXLC]+$)M{0,3}(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$")
NUMBERED = re.compile(r"^\s*[(\[]?[0-9٠-٩۰-۹]{1,2}(?:\s*[.\-]\s*[0-9٠-٩۰-۹]{1,2})*\s*[)\]]?\s*[°'ʼ]?\s*[-–ـ.)]")
NOT_AUTHOR = ("اولا", "ثانيا", "مقدمه", "المقدمه", "تمهيد", "المبحث", "الفصل", "المطلب", "ملخص", "الملخص",
              "مستخلص", "تقديم", "بسماللهالرحمن", "الحمدلله", "abstract")
ABSTRACT = {"ملخص", "الملخص", "مستخلص", "المستخلص", "ملخصالبحث", "abstract", "résumé", "resume", "summary"}
BASMALA = "بسماللهالرحمن"
DEBUG = bool(os.environ.get("INKSCRIPT_STRUCTURE_DEBUG"))
NOT_MARKER_BEFORE = {"الايه", "ايه", "الايات", "رقم", "ص", "ج", "صفحه", "العدد", "المجلد", "سنه", "عام", "بتاريخ"}


# ---------------------------------------------------------------- metadata outside the page

def id_parts(stem: str) -> dict:
    """What the Mandumah id spells: journal-volume-issue-article (checked on 240 documents of experiment 19:
    the printed issue equals the id's on 62 of 70 that print one by a naive reading, the others being the
    reading's own mistakes or a misprint; the printed volume / year-of-journal on 33 of 37). 000 = none (books
    and journals without volumes), "41,042" = a double issue, 999 = a special issue."""
    parts = stem.split("-")
    out = dict(journal=parts[0] if parts else stem)
    if len(parts) != 4:
        return out
    vol, iss, seq = parts[1], parts[2], parts[3]
    if vol.isdigit() and int(vol) > 0:
        out["volume"] = str(int(vol))
    if "," in iss:
        out["issue"] = "-".join(str(int(x)) for x in iss.split(",") if x.isdigit())
    elif iss == "999":
        out["issue_special"] = True
    elif iss.isdigit() and int(iss) > 0:
        out["issue"] = str(int(iss))
    if seq.isdigit():
        out["seq"] = str(int(seq))
    return out


def read_meta(stem: str, dirs=()) -> dict:
    """Gemini's title file (<stem>.gemini.title.json: {"title", "authors"}), looked for in each dir and in
    dir/<stem>/, plus the id's parts. Never calls Gemini."""
    meta = dict(id=id_parts(stem))
    for d in dirs:
        if not d:
            continue
        for f in (Path(d) / f"{stem}.gemini.title.json", Path(d) / stem / f"{stem}.gemini.title.json"):
            if f.exists():
                try:
                    g = json.loads(f.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                if isinstance(g, dict) and (g.get("title") or g.get("authors")):
                    meta["gemini"] = dict(title=(g.get("title") or "").strip(),
                                          authors=[a.strip() for a in g.get("authors") or [] if a and a.strip()],
                                          file=f.name)
                    return meta
    return meta


# ---------------------------------------------------------------- helpers

def key(s: str) -> str:
    k = norm((s or "").translate(_DIG)).replace(" ", "")
    return k or re.sub(r"\W", "", (s or "").translate(_DIG)).lower()


def sim(a: str, b: str) -> float:
    ka, kb = key(a), key(b)
    if not ka or not kb:
        return 0.0
    return difflib.SequenceMatcher(None, ka, kb, autojunk=False).ratio()


def _box(ws):
    return [min(w["box"][0] for w in ws), min(w["box"][1] for w in ws),
            max(w["box"][2] for w in ws), max(w["box"][3] for w in ws)]


def _h(ws):
    return statistics.median([w["box"][3] - w["box"][1] for w in ws]) if ws else 0.0


PEN = {"بقلم", "اعداد", "تاليف", "كتبه"}


def _split_honorific(text: str) -> tuple[str, str]:
    """('الدكتور', 'محمود ناظم نسيمي') from 'الدكتور محمود ناظم نسيمي'; 'د/ عبد العزيز' -> ('د/', 'عبد العزيز')."""
    text = re.sub(r"\(\s*\*\s*\)|\*|\(\s*[0-9٠-٩]{1,2}\s*\)", " ", text)     # the author's note marker
    toks = re.sub(r"([./])", r"\1 ", text).split()
    pre = []
    while toks and (norm(toks[0].strip("./:،")) in HONORIFIC or toks[0] in ("/", ".", ":", "-", "_")):
        pre.append(toks.pop(0))
    pre = [t for t in pre if norm(t.strip("./:،")) not in PEN and t.strip("./:،-")]    # "بقلم" is not a title
    pref = " ".join(pre).replace(" /", "/").replace(" .", ".").strip()
    return pref, " ".join(toks).strip(" :،-")


# ---------------------------------------------------------------- measurements from the scan

def stroke_widths(scan_pdf, doc, lines: dict) -> dict:
    """Mean stroke width (px at 300 dpi) of the ink of each line: 2 x ink area / ink outline length, on the
    page's Otsu split. Pages are rendered one at a time (the trust step does the same)."""
    import cv2
    import pymupdf
    out = {}
    src = pymupdf.open(str(scan_pdf))
    try:
        for pn in sorted(lines):
            if pn > src.page_count or not lines[pn]:
                continue
            pix = src[pn - 1].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
            g = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
            t, _ = cv2.threshold(np.ascontiguousarray(g[::4, ::4]), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            H, W = g.shape
            for li, ws in lines[pn].items():
                x0, y0, x1, y1 = (int(round(v)) for v in _box(ws))
                x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
                if x1 - x0 < 4 or y1 - y0 < 4:
                    continue
                m = (g[y0:y1, x0:x1] <= t).astype(np.uint8)
                ink = int(m.sum())
                if ink < 30:
                    continue
                er = cv2.erode(m, np.ones((3, 3), np.uint8))
                edge = ink - int(er.sum())
                if edge > 0:
                    out[(pn, li)] = 2.0 * ink / edge
            del g, pix
    finally:
        src.close()
    return out


# ---------------------------------------------------------------- the analysis

def analyse(doc: dict, meta: dict | None = None, scan_pdf=None) -> dict:
    meta = meta or {}
    W = doc["words"]
    paras = doc["paras"]
    npar = len(paras)
    pages = doc["pages"]
    kinds: list[str | None] = [None] * npar
    why: list[str] = [""] * npar

    # lines: (page, line index) -> word idx, in reading order
    line_words = {}
    for w in W:
        line_words.setdefault((w["page"], w["line"]), []).append(w["idx"])
    lines_by_page = {}
    for (pg, li), ks in line_words.items():
        lines_by_page.setdefault(pg, {})[li] = [W[k] for k in ks]

    # body letter height: lines of 6+ words in the top 60% of their page
    hs = []
    for (pg, li), ks in line_words.items():
        ws = [W[k] for k in ks]
        if len(ws) >= 6 and _box(ws)[3] < 0.6 * pages[pg]["h"]:
            hs.append(_h(ws))
    if not hs:
        hs = [_h([W[k] for k in ks]) for ks in line_words.values() if ks]
    body_h = statistics.median(hs) if hs else 1.0

    strokes = {}
    if scan_pdf and Path(scan_pdf).exists():
        try:
            strokes = stroke_widths(scan_pdf, doc, lines_by_page)
        except Exception:                      # a scan pdfium/mupdf cannot open: no stroke cue
            strokes = {}
    bs = [strokes[(pg, li)] for (pg, li), ks in line_words.items()
          if (pg, li) in strokes and len(ks) >= 6 and _box([W[k] for k in ks])[3] < 0.6 * pages[pg]["h"]]
    body_stroke = statistics.median(bs) if bs else None

    def pstroke(p):
        """Stroke width of a paragraph relative to the body's (None: unknown)."""
        if not body_stroke:
            return None
        v = [strokes[(W[k]["page"], W[k]["line"])] for k in p["words"] if (W[k]["page"], W[k]["line"]) in strokes]
        return statistics.median(v) / body_stroke if v else None

    def pinfo(p):
        pg = W[p["words"][0]]["page"]
        ws = [W[k] for k in p["words"] if W[k]["page"] == pg]
        b = _box(ws)
        H, Wd = pages[pg]["h"], pages[pg]["w"]
        txt = " ".join(w["out"] for w in ws).strip()
        return pg, ws, b, H, Wd, txt

    info = [pinfo(p) for p in paras]

    # ------------------------------------------------ furniture
    def fkey(t):
        return key(re.sub(r"[\d٠-٩۰-۹]", "", t))

    zone_keys = {}                              # short paragraphs in the top / bottom 16% of the page
    for i, (pg, ws, b, H, Wd, txt) in enumerate(info):
        if len(ws) <= 15 and (b[3] < 0.16 * H or b[1] > 0.84 * H):
            k = fkey(txt)
            if len(k) >= 3 and not NUMBERED.match(txt):     # "3 - ..." at the top is a heading, not a running head
                edge = b[3] < 0.13 * H or b[1] > 0.87 * H
                zone_keys[i] = (pg, "top" if b[3] < 0.16 * H else "bottom", k, edge)
    repeats = set()
    for i, (pg, z, k, edge) in zone_keys.items():
        others = {pg2 for j, (pg2, z2, k2, e2) in zone_keys.items()
                  if j != i and pg2 != pg and z2 == z
                  and (k2 == k or difflib.SequenceMatcher(None, k, k2, autojunk=False).ratio() >= 0.8)}
        if len(others) >= (1 if edge else 2):   # at the very edge, once more elsewhere; a little inside, twice
            repeats.add(i)
    first_page = min(pages) if pages else 1
    for i, (pg, ws, b, H, Wd, txt) in enumerate(info):
        if paras[i].get("role") in ("pageHeader", "pageFooter", "pageNumber"):
            kinds[i], why[i] = paras[i]["role"], "azure"
        elif NUMONLY.match(txt) and len(txt) <= 9 and (b[3] < 0.13 * H or b[1] > 0.87 * H):
            kinds[i], why[i] = "pageNumber", "digits alone at the top or bottom"
        elif i in repeats:
            kinds[i] = "pageHeader" if b[3] < 0.5 * H else "pageFooter"
            why[i] = "repeats at the same place on other pages"
        elif (b[3] < 0.2 * H or (b[3] < 0.25 * H and "مجلة" in txt)) and len(ws) <= 20 and MAST.search(txt) \
                and DIGIT.search(txt):
            kinds[i], why[i] = "pageHeader", "the journal's masthead"
        elif b[3] < 0.08 * H and len(ws) <= 12 and pg != first_page:   # on page 1 it may be the rubric
            kinds[i], why[i] = "pageHeader", "short text in the top 8%"
        elif b[1] > 0.94 * H and len(ws) <= 12:
            kinds[i], why[i] = "pageFooter", "short text in the bottom 6%"
        elif len(ws) <= 8 and (b[3] - b[1]) > 2.5 * (b[2] - b[0]) and (b[2] < 0.16 * Wd or b[0] > 0.84 * Wd):
            kinds[i], why[i] = "pageHeader", "text on its side in the outer margin"
        elif NUMONLY.match(txt) and len(txt) <= 3 and _h(ws) < 0.5 * body_h:
            kinds[i], why[i] = "pageFooter", "a speck read as a digit"   # stray mark, not article text
    furniture = {i for i in range(npar) if kinds[i] in ("pageHeader", "pageFooter", "pageNumber")}
    furn_words = {k for i in furniture for k in paras[i]["words"]}

    # ------------------------------------------------ notes at the foot of each page
    notes = []                                  # dict(page, label, words, lines, weak)
    note_word = {}                              # word idx -> note index
    for pg in sorted(lines_by_page):
        ls = []
        for li, ws in lines_by_page[pg].items():
            ws = [w for w in ws if w["idx"] not in furn_words]
            if ws:
                ls.append((_box(ws), li, ws))
        ls = _fold_numbers(ls, body_h)
        ls.sort(key=lambda x: x[0][1])
        zone = []
        for b, li, ws in reversed(ls):
            h = _h(ws)
            if h <= 0.86 * body_h or (_label(ws, strong=True) and h <= 0.93 * body_h):
                zone.append((b, li, ws))
            else:
                break
        zone.reverse()
        if not zone:
            continue
        H = pages[pg]["h"]
        strong = sum(1 for b, li, ws in zone if _label(ws, strong=True))
        bare = sum(1 for b, li, ws in zone if _label(ws))
        if not bare or zone[-1][0][3] < 0.5 * H:
            continue
        weak = strong == 0 and bare < 2          # one bare "1 -": a note only if a marker points at it
        # lines above the first labelled line are not notes (a table, a diagram), unless they continue a note
        # from the previous page
        while zone and not _label(zone[0][2]):
            if notes and notes[-1]["page"] == pg - 1 and len(zone[0][2]) >= 4:
                break
            zone.pop(0)
        cur = None
        for b, li, ws in zone:
            lab = _label(ws)
            if lab:
                cur = dict(page=pg, label=lab[0], words=[], lines=[], label_word=lab[1], weak=weak)
                notes.append(cur)
            elif cur is None:
                if notes and notes[-1]["page"] == pg - 1:
                    cur = notes[-1]             # continues the last note of the previous page
                else:
                    cur = dict(page=pg, label=None, words=[], lines=[], label_word=None, weak=weak)
                    notes.append(cur)
            cur["words"] += [w["idx"] for w in ws]
            cur["lines"].append(li)
    for n, nt in enumerate(notes):
        nt["words"].sort()
        for k in nt["words"]:
            note_word[k] = n
    for i, p in enumerate(paras):
        if i in furniture:
            continue
        inz = sum(1 for k in p["words"] if k in note_word)
        if inz and inz >= 0.5 * len(p["words"]):
            kinds[i], why[i] = "footnote", "small lines at the foot of the page, opening with a note number"

    # ------------------------------------------------ front matter
    front = _front(doc, info, kinds, furniture, note_word, body_h, meta)
    front_words = set(front.get("title_words", [])) | set(front.get("rubric_words", []))
    for a in front.get("authors", []):
        front_words |= set(a["words"]) | set(a.get("aff_words", [])) | set(a.get("prefix_words", []))

    # ------------------------------------------------ markers in the text pointing at each note
    markers = _markers(doc, notes, kinds, furniture, note_word, front_words)
    linked = {m["note"] for m in markers.values()}
    bad = {n for n, nt in enumerate(notes) if nt.get("weak") and n not in linked}
    if bad:                                    # a lone bare "1 -" that nothing points at: not a note
        keep = [n for n in range(len(notes)) if n not in bad]
        remap = {old: new for new, old in enumerate(keep)}
        notes = [notes[n] for n in keep]
        markers = {k: dict(m, note=remap[m["note"]]) for k, m in markers.items()}
        note_word = {k: remap[n] for k, n in note_word.items() if n in remap}
        for i, p in enumerate(paras):
            if kinds[i] == "footnote" and why[i].startswith("small lines") and not any(k in note_word for k in p["words"]):
                kinds[i], why[i] = None, ""
    markers.update(_endnote_markers(doc, notes, markers, kinds, furniture, note_word, front_words))

    # ------------------------------------------------ headings
    title_text = front.get("title", "")
    author_texts = [a["name"] for a in front.get("authors", [])]
    tkey = key(title_text)
    cand = []
    for i, (pg, ws, b, H, Wd, txt) in enumerate(info):
        if kinds[i] or i in furniture:
            continue
        if all(k in front_words for k in paras[i]["words"]):
            continue
        cand.append(i)
    col = _columns(info, kinds, body_h)
    heads = []
    head_words = {}                            # heading paragraph -> its heading words (a name before it is not)
    for i in cand:
        pg = info[i][0]
        H, Wd = info[i][3], info[i][4]
        ws = [w for w in info[i][1] if w["idx"] not in front_words]   # what is left once the byline is taken
        for t_ in [title_text] + author_texts:   # the title or a name repeated over the text of a later page
            run = _align(ws, t_, 0.8) if t_ and len(ws) > 1 else None
            if run:
                ws = [w for w in ws if w["idx"] not in set(run)]
        if not ws:
            continue
        b = _box(ws)
        txt = " ".join(w["out"] for w in ws).strip()
        nl = len({w["line"] for w in ws})
        letters = norm(re.sub(r"[\W\d_]", "", txt))
        roman = bool(ROMAN.match(txt.strip(" .-")))
        if nl > 2 or len(ws) > 16 or (len(letters) < 3 and not roman):
            continue
        if txt.startswith(("(", "«", "\"", "{", "[", "﴿", "»")):
            continue                               # a quotation
        if txt.rstrip().endswith(("،", "؛", ",")) or (txt.rstrip().endswith(".") and len(ws) > 6):
            continue
        k = key(txt)
        if k.startswith(("الحمدلله", BASMALA, "والصلاه", "اما بعد".replace(" ", ""))):
            continue                               # the invocation, not a section
        if tkey and (sim(txt, title_text) >= 0.8 or (len(tkey) >= 6 and difflib.SequenceMatcher(
                None, tkey, k, autojunk=False).find_longest_match(0, len(tkey), 0, len(k)).size >= 0.8 * len(tkey))):
            continue                               # the title repeated at the top of a page (perhaps with the name)
        if any(sim(txt, a) >= 0.8 for a in author_texts):
            continue
        size = _h(ws) / body_h
        if size < (0.45 if roman else 0.6):
            continue                               # a speck or a stray mark
        if roman or len(ws) <= 2:                  # a short cell of a table has neighbours on its row
            row = [w for w in doc["words"] if w["page"] == pg and w["para"] != i
                   and min(w["box"][3], b[3]) - max(w["box"][1], b[1]) > 0.5 * (b[3] - b[1])
                   and min(abs(w["box"][0] - b[2]), abs(b[0] - w["box"][2])) < 0.25 * Wd]
            if row:
                continue
        c0, c1 = col.get(pg, (0, Wd))
        cw = max(1.0, c1 - c0)
        width = (b[2] - b[0]) / cw
        stroke = pstroke(dict(words=[w["idx"] for w in ws]))
        bold = stroke is not None and stroke >= 1.2
        boldish = stroke is not None and stroke >= 1.1
        k0 = norm(ws[0]["out"])
        mnum = re.match(r"^\s*[(\[]?([0-9٠-٩۰-۹]{1,3})", txt)
        if mnum and NUMBERED.match(txt) and int(mnum.group(1).translate(_DIG)) > 40:
            continue                               # "٨٩- سورة الأحزاب": a note, not a heading
        numbered = bool(NUMBERED.match(txt)) or k0 in SECTION_WORDS or roman \
            or any(k.startswith(s) for s in SECTION_WORDS)
        colon = txt.rstrip(" .").endswith(":")
        centred = abs((b[0] + b[2]) / 2 - (c0 + c1) / 2) < 0.08 * cw and width < 0.7
        gap = _gap_above(info, i, kinds, body_h)
        short = width < 0.8
        reason = None
        if short and size >= 1.2 and len(ws) <= 12:
            reason = f"letters {size:.2f}x the body"
        elif short and bold and (len(ws) <= 12 or (numbered and len(ws) <= 16)):
            reason = f"bold ink (stroke {stroke:.2f}x the body)"
        elif short and numbered and (boldish or colon or gap >= 0.6 or centred) and len(ws) <= 10:
            reason = "numbered / section word" + (", bold" if boldish else "") + (", colon" if colon else "") \
                     + (", space above" if gap >= 0.6 else "") + (", centred" if centred else "")
        elif roman and len(ws) == 1:
            reason = "a Roman numeral alone"
        elif short and colon and len(ws) <= 8 and (boldish or (gap >= 0.8 and centred)):
            reason = "ends with a colon, set apart" + (", bold" if boldish else "")
        if DEBUG:
            print(f"  head? p{pg} {txt[:40]!r} size={size:.2f} stroke={stroke if stroke is None else round(stroke, 2)} "
                  f"num={numbered} colon={colon} gap={gap:.2f} centred={centred} width={width:.2f} -> {reason}")
        if reason:
            heads.append((i, reason, numbered))
            head_words[i] = [w["idx"] for w in ws]
    # a run of 3+ short numbered paragraphs one after another, none of them standing out by size or ink, is a list
    drop = set()
    run = []
    for i in cand + [None]:
        pg, ws, b, H, Wd, txt = info[i] if i is not None else (None,) * 6
        is_short_num = i is not None and len(ws) <= 10 and bool(NUMBERED.match(txt))
        if is_short_num:
            run.append(i)
            continue
        if len(run) >= 3:
            for j in run:
                r = next((r for x, r, n in heads if x == j), "")
                if not (r.startswith("letters") or r.startswith("bold")):
                    drop.add(j)
        run = []
    for i, r, n in heads:
        if i in drop:
            continue
        kinds[i], why[i] = "sectionHeading", r

    # ------------------------------------------------ journal title and date from the furniture
    journal, year = _journal_and_year(doc, info, kinds, furniture, title_text, author_texts)

    return dict(kinds=kinds, why=why, body_h=body_h, body_stroke=body_stroke, front=front, notes=notes,
                note_word=note_word, markers=markers, journal=journal, year=year, furniture=furniture,
                head_words={i: v for i, v in head_words.items() if kinds[i] == "sectionHeading"},
                front_words=front_words, id=meta.get("id") or {}, gemini=bool(meta.get("gemini")))


def _fold_numbers(ls, body_h):
    """A note's number printed raised comes back from Azure as a line of its own beside its note's first line;
    put it back at the start of that line (the build folds superscript markers the same way)."""
    out = list(ls)
    for item in sorted(ls, key=lambda x: x[0][1]):
        b, li, ws = item
        if len(ws) != 1 or not re.fullmatch(rf"[(\[]?\s*{NUM}\s*[)\]]?", ws[0]["out"].strip()):
            continue
        h = b[3] - b[1]
        best = None
        for other in out:
            if other is item or len(other[2]) < 1:
                continue
            ob = other[0]
            ov = min(b[3], ob[3]) - max(b[1], ob[1])
            gap = min(abs(b[0] - ob[2]), abs(ob[0] - b[2]))
            if ov > 0.3 * h and gap < 1.5 * body_h and (best is None or gap < best[0]):
                best = (gap, other)
        if best:
            ob, oli, ows = best[1]
            merged = ([min(b[0], ob[0]), min(b[1], ob[1]), max(b[2], ob[2]), max(b[3], ob[3])], oli, ws + ows)
            out = [x for x in out if x is not item and x is not best[1]] + [merged]
    return out


def _label(ws, strong=False):
    """(label, word idx) when a line opens with a note number: the line's first word in reading order, or its
    rightmost word (Azure sometimes reads a number at the start of a right-to-left line last). strong: in
    brackets "(3)", "3)", "[3]"; otherwise a bare "3 -", "3." or "3" followed by text also counts."""
    if not ws:
        return None
    firsts = [ws[0]]
    r = max(ws, key=lambda w: w["box"][2])
    if r is not ws[0]:
        firsts.append(r)
    for w in firsts:
        t = w["out"]
        if w is ws[0] and re.match(r"^\s*(\(\s*\*\s*\)|\*)", t):
            return ("*", w["idx"])               # the author's note: "* الجامعة الأسمرية."
        m = NOTE_LABEL_HEAD.match(t)
        if m:
            return ((m.group(1) or m.group(2)).translate(_DIG), w["idx"])
        if strong:
            continue
        m = re.match(rf"^\s*({NUM})\s*[-–.]", t) or (re.fullmatch(NUM, t.strip()) and len(ws) >= 2 and
                                                       re.match(rf"^\s*({NUM})", t))
        if m:
            nxt = ws[1]["out"] if w is ws[0] and len(ws) > 1 else ""
            if re.fullmatch(r"\d{4}", m.group(1).translate(_DIG)) or re.fullmatch(r"[\d٠-٩/.]+", nxt or "x"):
                continue                       # a year, or a number followed by more numbers
            return (m.group(1).translate(_DIG), w["idx"])
    return None


def _columns(info, kinds, body_h) -> dict:
    """Per page, the horizontal extent of the text column(s): the span of body lines of 6+ words."""
    out = {}
    for i, (pg, ws, b, H, Wd, txt) in enumerate(info):
        if kinds[i] or len(ws) < 12:
            continue
        x0, x1 = out.get(pg, (b[0], b[2]))
        out[pg] = (min(x0, b[0]), max(x1, b[2]))
    # a two-column page: the paragraph's own column is narrower than the page's text; use the median body width
    return out


def _gap_above(info, i, kinds, body_h) -> float:
    """White space above a paragraph, in body line heights (to the nearest text above it that overlaps it
    horizontally on the same page)."""
    pg, ws, b, H, Wd, txt = info[i]
    best = None
    for j, (pg2, ws2, b2, *_r) in enumerate(info):
        if j == i or pg2 != pg or b2[3] > b[1] + 0.3 * body_h:
            continue
        if min(b[2], b2[2]) - max(b[0], b2[0]) <= 0:
            continue
        g = b[1] - b2[3]
        if best is None or g < best:
            best = g
    if best is None:
        return 2.0
    return max(0.0, best) / body_h


def _front(doc, info, kinds, furniture, note_word, body_h, meta) -> dict:
    W = doc["words"]
    paras = doc["paras"]
    gem = meta.get("gemini") or {}
    out = {}
    # the first pages' words in reading order, outside furniture and notes: where a title can be
    early = [w for w in W if w["page"] <= 3 and w["idx"] not in note_word
             and w["para"] not in furniture][:260]
    if gem.get("title"):
        run = _align(early, gem["title"])
        if run:
            out.update(title=gem["title"], title_words=run, title_source="gemini-title-file")
    if "title" not in out:
        out.update(_front_by_layout(doc, info, kinds, furniture, note_word, body_h))
    if not out.get("title_words"):
        return out
    tw = set(out["title_words"])
    if gem.get("authors"):
        authors = []
        rest = [w for w in early if w["idx"] not in tw]
        for a in gem["authors"]:
            pref, name = _split_honorific(a)
            run = _align(rest, name or a)
            pw = []
            if run:                                 # the honorific / byline words just before the name
                pos = next(j for j, w in enumerate(rest) if w["idx"] == run[0])
                while pos > 0 and rest[pos - 1]["para"] == rest[pos]["para"] \
                        and (_honorific_word(rest[pos - 1]["out"])
                                   or not re.sub(r"[\W_]", "", rest[pos - 1]["out"])) and len(pw) < 4:
                    pos -= 1
                    pw.insert(0, rest[pos]["idx"])
            authors.append(dict(name=name or a, prefix=pref, words=run or [], prefix_words=pw,
                                source="gemini-title-file"))
            if run:
                rest = [w for w in rest if w["idx"] not in set(run) | set(pw)]
        out["authors"] = authors
    elif "authors" not in out:
        out["authors"] = []
    # rubric: short lines above the title on its page (layout pass sets it; with Gemini, look again)
    if "rubric_words" not in out:
        tpage = W[out["title_words"][0]]["page"]
        first_tp = min(out["title_words"])
        rub = []
        for i, (pg, ws, b, H, Wd, txt) in enumerate(info):
            if pg != tpage or i in furniture or kinds[i] == "footnote":
                continue
            ks = [k for k in paras[i]["words"] if k < first_tp and k not in tw]
            if not ks or len(ks) > 6 or ks[-1] >= first_tp:
                continue
            t = " ".join(W[k]["out"] for k in ks)
            if key(t).startswith(BASMALA) or len(norm(t).replace(" ", "")) < 3 or _is_byline(t):
                continue
            if any(set(ks) & set(a["words"]) for a in out.get("authors", [])):
                continue
            rub += ks
        if rub:
            out["rubric_words"] = rub
            out["rubric"] = " ".join(W[k]["out"] for k in rub)
    return out


def _align(words, text, least: float = 0.6) -> list[int] | None:
    """The run of words (contiguous in reading order, at most 3 strays inside) whose letters best match text;
    None below 0.6 similarity."""
    target = key(text)
    if not target or not words:
        return None
    nt = max(1, len(text.split()))
    best, arg = 0.0, None
    keys = [key(w["out"]) for w in words]
    for i in range(len(words)):
        if not keys[i] or keys[i][:1] not in target:
            continue
        acc = ""
        for j in range(i, min(len(words), i + 2 * nt + 4)):
            acc += keys[j]
            if len(acc) > 1.6 * len(target) + 6:
                break
            r = difflib.SequenceMatcher(None, acc, target, autojunk=False).ratio()
            if r > best:
                best, arg = r, (i, j)
    if best < least or arg is None:
        return None
    i, j = arg
    return [w["idx"] for w in words[i:j + 1]]


def _front_by_layout(doc, info, kinds, furniture, note_word, body_h) -> dict:
    """Title, rubric and byline from page 1's layout alone (no Gemini title file)."""
    W = doc["words"]
    paras = doc["paras"]
    p1 = [i for i, inf in enumerate(info) if inf[0] == min(doc["pages"])]
    cand = []
    for i in p1:
        if i in furniture or kinds[i] == "footnote":
            continue
        pg, ws, b, H, Wd, txt = info[i]
        k = key(txt)
        if len(ws) > 12 and _h(ws) < 1.15 * body_h or k in ABSTRACT or txt.strip().lower().rstrip(":") in ABSTRACT:
            break                                   # the text, or the abstract, has begun
        if k.startswith(BASMALA) or len(re.sub(r"[\W\d_]", "", txt)) < 3:
            continue
        cand.append(i)
    if not cand:
        return {}
    size = {i: _h(info[i][1]) for i in cand}
    t = max(cand, key=lambda i: size[i])
    nxt = cand[cand.index(t) + 1] if cand.index(t) + 1 < len(cand) else None
    bylined = nxt is not None and _is_byline(info[nxt][5])
    if size[t] < (0.95 if bylined else 1.2) * body_h or len(info[t][1]) > 25:
        return {}                                   # nothing stands out (a byline under it lowers the bar)
    # a title set over two lines: neighbours in reading order of nearly the same size
    pos = cand.index(t)
    group = [t]
    for d in (-1, 1):
        j = pos + d
        while 0 <= j < len(cand) and size[cand[j]] >= 0.75 * size[t] and size[cand[j]] >= 1.25 * body_h \
                and len(info[cand[j]][1]) <= 12 and not _is_byline(info[cand[j]][5]):
            group.append(cand[j])
            j += d
    group.sort(key=lambda i: cand.index(i))
    tw = [k for i in group for k in paras[i]["words"]]
    glued = None                                    # "السلفية وأثرها ... أ. محمد القاسي": the byline set on the title line
    for j in range(2, len(tw)):
        if _honorific_word(W[tw[j]]["out"]) and len(norm(W[tw[j]]["out"])) <= 2 and j < len(tw) - 1:
            glued = tw[j:]
            tw = tw[:j]
            break
    out = dict(title=" ".join(W[k]["out"] for k in tw), title_words=tw, title_source="layout: largest letters on page 1")
    first = cand.index(group[0])
    rub = [k for i in cand[:first] if len(info[i][1]) <= 6 and not _is_byline(info[i][5])
           and len(norm(info[i][5]).replace(" ", "")) >= 3 for k in paras[i]["words"]]
    if rub:
        out.update(rubric_words=rub, rubric=" ".join(W[k]["out"] for k in rub))
    # the byline: the next one or two candidates
    authors = []
    after = cand[cand.index(group[-1]) + 1:cand.index(group[-1]) + 3]
    lone_byline = []
    if after and key(info[after[0]][5]) in BYLINE and len(after) > 1:
        lone_byline = list(paras[after[0]]["words"])
        after = after[1:]                           # "بقلم :" alone on its line: the name is the next paragraph
    for i in after[:1]:
        pg, ws, b, H, Wd, txt = info[i]
        lines = []
        for w in ws:
            if not lines or lines[-1][-1]["line"] != w["line"]:
                lines.append([])
            lines[-1].append(w)
        while len(lines) > 1 and not re.sub(r"[\W\d_]", "", " ".join(w["out"] for w in lines[0])):
            lines = [lines[0] + lines[1]] + lines[2:]   # a raised "*" read as a line of its own
        first_line = lines[0]
        if _is_byline(" ".join(w["out"] for w in first_line)) and len(first_line) <= 3 and len(lines) > 1:
            first_line = first_line + lines[1]      # "بقلم الدكتور" on one line, the name on the next
            lines = [first_line] + lines[2:]
        ft = " ".join(w["out"] for w in first_line)
        k = key(ft)
        if any(k.startswith(key(h)) for h in NOT_AUTHOR) or len(first_line) > 8:
            break
        if len(ws) > 6 and not _is_byline(ft) and len(lines) == 1:
            break
        pref, name = _split_honorific(ft)
        if not name or len(re.sub(r"[\W\d_]", "", name)) < 4:
            break
        # the words of the name: drop the honorific words from the start
        nw = [w["idx"] for w in first_line]
        npre = 0
        while npre < len(first_line) - 1 and (_honorific_word(first_line[npre]["out"])
                                              or not re.sub(r"[\W\d_]", "", first_line[npre]["out"])):
            npre += 1
        a = dict(name=name, prefix=pref, words=nw[npre:] if npre < len(nw) else nw,
                 prefix_words=lone_byline + nw[:npre], source="layout: the line after the title")
        _split_aff(a, W)

        aff = [w["idx"] for ln in lines[1:] for w in ln]
        if aff:
            a["aff_words"] = aff
            a["aff"] = " ".join(W[k]["out"] for k in aff)
        authors.append(a)
    if not authors and glued:
        k0 = 0
        while k0 < len(glued) - 1 and (_honorific_word(W[glued[k0]]["out"]) or not re.sub(r"[\W\d_]", "", W[glued[k0]]["out"])):
            k0 += 1
        a = dict(name=" ".join(W[k]["out"] for k in glued[k0:]), prefix=" ".join(W[k]["out"] for k in glued[:k0]),
                 words=glued[k0:], prefix_words=glued[:k0], source="layout: the byline on the title's line")
        _split_aff(a, W)
        authors.append(a)
    out["authors"] = authors
    return out


def _split_aff(a: dict, W) -> None:
    """'كمال فضل السيد جامعة الخرطوم' -> name 'كمال فضل السيد', affiliation 'جامعة الخرطوم'."""
    ws = a["words"]
    for j in range(1, len(ws)):
        t = W[ws[j]]["out"]
        if norm(t.strip("،,-")) in AFF_WORDS or t.startswith("(") or any(norm(t).startswith(x) for x in AFF_WORDS[:4]):
            a["aff_words"] = ws[j:] + a.get("aff_words", [])
            a["aff"] = " ".join(W[k]["out"] for k in a["aff_words"])
            a["words"] = ws[:j]
            a["name"] = " ".join(W[k]["out"] for k in ws[:j]).strip(" ،,-")
            return


def _honorific_word(t: str) -> bool:
    """A byline or honorific word, also when misread by a letter or two ("لَدكتُورُ" for "للدكتور")."""
    k = norm(t.strip("./:،-"))
    return k in BYLINE or (len(k) >= 5 and any(len(b) >= 5 and difflib.SequenceMatcher(None, k, b).ratio() >= 0.8
                                               for b in BYLINE))


def _is_byline(txt: str) -> bool:
    toks = re.sub(r"([./:*()])", r" ", txt).split()
    return bool(toks) and norm(toks[0]) in BYLINE


def _num(label) -> int:
    return int(label) if label and label.isdigit() else 0


def _body_words(doc, kinds, furniture, note_word, front_words, page=None):
    return [w for w in doc["words"] if (page is None or w["page"] == page) and w["idx"] not in note_word
            and w["idx"] not in front_words and w["para"] not in furniture and kinds[w["para"]] != "footnote"]


def _marker_cands(doc, body) -> list[tuple]:
    """Possible note markers among body words, in reading order: (label, priority, idx, head, mark, tail);
    priority 0 glued to a word, 1 in brackets alone, 2 with one bracket, 3 a bare number raised above its line."""
    out = []
    line_of = {}
    for w in doc["words"]:
        line_of.setdefault((w["page"], w["line"]), []).append(w)
    for pos, w in enumerate(body):
        t = w["out"]
        prev = norm(body[pos - 1]["out"]) if pos else ""
        if prev in NOT_MARKER_BEFORE:
            continue
        ms = re.match(r"^(.*?)(\(\s*\*\s*\)|\*)([.,،:؛]*)$", t)
        if ms and (ms.group(1) or ms.group(2).startswith("(")):
            out.append(("*", 1, w["idx"], ms.group(1), ms.group(2), ms.group(3)))
            continue
        for pri, rx in ((0, rf"^(.*?[^\s(\[0-9٠-٩])([(\[]\s*({NUM})\s*[)\]])([.,،:؛»\"”)!?؟]*)$"),
                        (1, rf"^([.,،:؛»\"”]?)([(\[]\s*({NUM})\s*[)\]])([.,،:؛»\"”!?؟]*)$"),
                        (2, rf"^([.,،:؛»\"”]?)(({NUM})\s*[)\]])([.,،:؛»\"”!?؟]*)$")):
            m = re.match(rx, t)
            if m:
                out.append((m.group(3).translate(_DIG), pri, w["idx"], m.group(1), m.group(2), m.group(4)))
                break
        else:
            m = re.match(rf"^(.*?[^\W\d_][.،:؛»\"”)\]﴾﴿]+)({NUM})([.,،:؛]*)$", t)
            mb = re.match(rf"^({NUM})([.,،:؛]*)$", t)
            if m:                                # a raised number printed after the full stop: "الأدب.٣"
                out.append((m.group(2).translate(_DIG), 1, w["idx"], m.group(1), m.group(2), m.group(3)))
            elif mb:                             # a bare number: raised, alone on its line, or after a full stop
                L = line_of[(w["page"], w["line"])]
                lh = statistics.median([x["box"][3] - x["box"][1] for x in L])
                lb = statistics.median([x["box"][3] for x in L])
                h = w["box"][3] - w["box"][1]
                raised = len(L) >= 3 and h <= 0.75 * lh and w["box"][3] < lb - 0.25 * lh
                alone = len(L) == 1
                after_stop = pos > 0 and re.search(r"[.»\"”)\]﴾﴿]$", body[pos - 1]["out"]) is not None
                if raised or alone or after_stop:
                    out.append((mb.group(1).translate(_DIG), 3, w["idx"], "", mb.group(1), mb.group(2)))
    return out


def _markers(doc, notes, kinds, furniture, note_word, front_words) -> dict:
    """word idx -> dict(note=index into notes, head=text before the marker, mark=the marker, tail=after)."""
    by_page = {}
    for n, nt in enumerate(notes):
        if nt["label"] is not None:
            by_page.setdefault(nt["page"], []).append(n)
    out = {}
    for pg, ns in by_page.items():
        cands = {}
        for c in _marker_cands(doc, _body_words(doc, kinds, furniture, note_word, front_words, pg)):
            cands.setdefault(c[0], []).append(c[1:])
        last = -1
        for n in sorted(ns, key=lambda n: (_num(notes[n]["label"]), n)):
            c = [x for x in cands.get(notes[n]["label"], []) if x[1] not in out]
            if not c:
                continue
            after = [x for x in c if x[1] > last]
            pick = min(after or c, key=lambda x: (x[0], x[1]))
            out[pick[1]] = dict(note=n, head=pick[2], mark=pick[3], tail=pick[4])
            last = max(last, pick[1])
    return out


def _endnote_markers(doc, notes, markers, kinds, furniture, note_word, front_words) -> dict:
    """Notes gathered at the end of the article (endnotes): when 3+ numbered notes have no marker on their own
    page and their numbers do not repeat, each is linked to the first marker with its number after the previous
    one, anywhere in the text before it."""
    linked = {m["note"] for m in markers.values()}
    un = [n for n, nt in enumerate(notes) if n not in linked and nt["label"] and nt["label"] != "*"
          and not nt.get("weak")]
    per_page = Counter(notes[n]["page"] for n in un)
    pages_ = []
    for pg in sorted(per_page, reverse=True):  # the last pages that hold 3+ such notes each: the endnotes
        if per_page[pg] < 3 or (pages_ and pg < pages_[-1] - 1):
            break
        pages_.append(pg)
    un = [n for n in un if notes[n]["page"] in pages_]
    seen, uniq = set(), []
    for n in un:
        if notes[n]["label"] not in seen:
            seen.add(notes[n]["label"])
            uniq.append(n)
    if len(uniq) < 3 or len(uniq) < 0.9 * len(un):
        return {}
    un = uniq
    first_page = min(notes[n]["page"] for n in un)
    body = [w for w in _body_words(doc, kinds, furniture, note_word, front_words) if w["page"] <= first_page
            and w["idx"] not in markers]
    cands = {}
    for c in _marker_cands(doc, body):
        if c[1] <= 2:                            # bracketed only: a raised bare digit far from its note is too weak
            cands.setdefault(c[0], []).append(c[1:])
    out, last = {}, -1
    for n in sorted(un, key=lambda n: _num(notes[n]["label"])):
        c = [x for x in cands.get(notes[n]["label"], []) if x[1] > last and x[1] not in out]
        if not c:
            continue
        pick = min(c, key=lambda x: x[1])
        out[pick[1]] = dict(note=n, head=pick[2], mark=pick[3], tail=pick[4], endnote=True)
        last = pick[1]
    return out if len(out) >= 0.5 * len(un) else {}


def _journal_and_year(doc, info, kinds, furniture, title, authors):
    c = Counter()
    years = Counter()
    for i in furniture:
        txt = info[i][5]
        for m in re.finditer(r"(?<!\d)(1[3-4]\d\d|19\d\d|20[0-3]\d)(?!\d)", txt.translate(_DIG)):
            y = int(m.group(1))
            years[("hijri" if y < 1500 else "gregorian", y)] += 1
        t = re.sub(r"[\d٠-٩۰-۹\-–—()|•●■:/]", " ", txt)
        t = re.sub(r"\b(العدد|عدد|المجلد|السنة|الجزء|ج|ص)\b", " ", t)
        t = " ".join(t.split())
        if len(key(t)) >= 4 and not (title and sim(t, title) >= 0.7) and not any(sim(t, a) >= 0.7 for a in authors):
            c[t] += 2 if "مجلة" in t else 1
    journal = None
    if c:
        t, n = c.most_common(1)[0]
        if n >= 3:
            journal = t
    year = None
    if years:
        g = [k for k in years if k[0] == "gregorian"]
        year = max(g, key=lambda k: years[k]) if g else max(years, key=lambda k: years[k])
    return journal, year
