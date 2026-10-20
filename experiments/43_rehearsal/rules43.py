"""Experiment 43: rules applied in code to a Gemini answer (prompt v1 or v2) before assembly. No model calls.

normalize(ans, lines, words=None) -> (answer in experiment 41's shape, log)
  lines   {line id "P:N": {"text", "b" (0-1000 box), "page"}} for every Azure line of the chunk's pages
  words   optional callable(line id) -> Azure's words of that line [{"text", "box"}] (any box frame; used only to
          see gaps between words), or None

The rules, in order (each counted in the log):
  endnotes      an "endnote" block becomes a footnote with note_kind "endnote" (experiment 41's assembly and
                masters link footnotes by id across pages, so endnotes link the same way)
  verse cut     a verse block's "cut": {"3:4": K} becomes experiment 41's "splits" (Azure's words 1..K | K+1..),
                and a hemistich written as the uncut line becomes its two halves
  ornaments     the model's "ornaments" (line, word index) are checked against Azure's text; then, on verse lines,
                a lone ornament mark standing at the inner edge of a half (٥ ه * ※ = ° ...; « » . : - only where
                it sits in the gap between the halves) is added in code. Result in ans["_ornaments"]: the masters
                take them out of the text and keep their ink in the ALTO as role.ornament
  never noise   a line with words (>= MIN_LETTERS letters at a plausible width, not a sliver at the page edge) that
                the answer called noise or left out is put back: one or two lines next to a block of running text
                (paragraph, footnote, list item, other_article, ...) join it at their place; anything else becomes a
                block of type "other" flagged "from_noise", one per column, placed in reading order by position
  bad splits    a split whose parts are not Azure's text (experiment 41's assembly then left the line out of every
                block: 0355 21:63, where Argon retyped أن as ان inside the parts): when the parts hold as many words
                as the line, they are rebuilt from Azure's own words at the same cut; otherwise the split is undone
                (the first reference to a part becomes the whole line, the other references go)
  empty rows    a table row with no cells (every column covered by a rowspan from above: 1148 p6 in the 55) is
                dropped and the rowspans over it shortened by one (the JATS DTD wants th or td in every tr)
  exclamation   a "(!)" Azure read (the author's parenthetical exclamation) is never turned into a call: a fix that
                writes it as a digit "(١)" / "(1)" is refused and a footnote call whose marker is that "(!)" (or the
                digit the fix wrote) on that line is dropped (0197 p2: the owner's judgement on the scan)
  text in fig.  a block of running text (paragraph, abstract, quote, other, list item, keywords, verse, boxed) whose every
                line lies inside a figure's box on its page (>= 80% of each line's area) is the figure's own text
                (0493 p1: a paragraph printed on a drawn TV screen), unless the figure also holds a title, heading
                or byline line (then it is a background picture under the page's own text: 0881 p1): its lines become the figure's "lines" (the
                masters keep them as the figure's text, the view shows the picture only); its calls are dropped
  figure trim   a figure box that runs over a line of a title / heading / byline / caption (less than half of the
                line inside the box; a caption line also when wholly inside but in the box's top or bottom fifth) is
                cut back to that line's edge (+ the crop's 4/1000 margin), when the cut is under 30% of the box's
                height (0493 p1: the TV drawing's box began inside the title's second line; 1769: the label
                «شكل رقم (N)» above a picture inside its box, drawn twice)
  v3 types      (prompt v3) a title block with "translated": true becomes type "trans_title" (the masters write it as
                JATS trans-title-group); a "boxed" block keeps its type and its "box" number rides in "level" (the
                assembly keeps level, not unknown keys): the masters group one box's blocks into one boxed-text;
                a figure's description {"ar", "en"} becomes its JSON text (experiment 41's assembly escapes the
                description as a string), which masters43 reads back into one alt-text per language
  fixes counted fixes that only add or remove spaces, and fixes that only change hamza / ya / ta marbuta forms,
                are counted, not changed (mostly Azure gluing words: right to fix)
"""
from __future__ import annotations

import copy
import json
import re
from collections import Counter

MIN_LETTERS = 4                 # fewer letters than this: a speck read as letters (exp 41: "ins", "هـ", "x", "mi")
MIN_W_PER_LETTER = 1.5          # box width (0-1000) per letter; a 7-wide box with 8 letters is vertical junk
EDGE = 15                       # a line wholly within 1.5% of the left or right page edge is a sliver
MERGE = {"paragraph", "quote", "list_item", "reference", "footnote", "abstract", "keywords", "other",
         "other_article", "caption", "boxed"}
AR_LET = re.compile(r"[ء-غف-يٮ-ۓۺ-ۼݐ-ݿﭐ-﷿ﹰ-ﻼ]")
LA_LET = re.compile(r"[A-Za-zÀ-ɏ]")
ORN_STRONG = re.compile(r"^[٥ه\*※✡☆★✶✦✧❊❋°﴿﴾=⁂✿❀]{1,2}$")
ORN_WEAK = re.compile(r"^[\.·•:؛،«»\-–—]{1,2}$")
TASHKEEL = re.compile(r"[ً-ْٰ]")


def letters(t: str) -> int:
    return len(AR_LET.findall(t or "")) + len(LA_LET.findall(t or ""))


def has_words(L: dict) -> bool:
    """A line with words (never noise) vs a speck, ornament or rule read as letters."""
    n = letters(L["text"])
    if n < MIN_LETTERS:
        return False
    x0, _, x1, _ = L["b"]
    if x1 - x0 < MIN_W_PER_LETTER * n:
        return False
    if x1 <= EDGE or x0 >= 1000 - EDGE:
        return False
    return True


def base_of(i: str, lines: dict) -> str | None:
    i = str(i).strip()
    if i in lines:
        return i
    m = re.match(r"^(\d+:\d+)[a-p]$", i)
    return m.group(1) if m and m.group(1) in lines else None


def block_ids(b: dict) -> list[str]:
    if not isinstance(b, dict):
        return []
    if b.get("type") == "table":
        out = []
        for r in b.get("rows") or []:
            for c in (r if isinstance(r, list) else []):
                c = c if isinstance(c, dict) else {"lines": [c]}
                out += [str(i) for i in c.get("lines") or []]
        return out + [str(i) for i in b.get("lines") or []]
    if b.get("type") == "verse" and b.get("hemistichs"):
        return [str(i) for h in b["hemistichs"] for i in (h if isinstance(h, list) else [h])]
    return [str(i) for i in b.get("lines") or []]


def union(bs):
    bs = [b for b in bs if b]
    if not bs:
        return None
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def xoverlap(a, b) -> float:
    """Horizontal overlap as a share of the narrower box."""
    o = min(a[2], b[2]) - max(a[0], b[0])
    w = min(a[2] - a[0], b[2] - b[0]) or 1
    return max(0.0, o) / w


def is_rtl(t: str) -> bool:
    return len(AR_LET.findall(t)) >= len(LA_LET.findall(t))


# ------------------------------------------------------------------------------------------------ layout rules
# (2026-10-18, owner's marks on 0478 p4: blocks drawn on top of each other in the Layout view)

TEXT_TYPES = {"paragraph", "list_item", "quote", "reference", "abstract", "keywords", "other", "boxed", "footnote"}
HEAD_MAX_ROWS = 3
NUM_MARK = re.compile(r"^\s*[\(\[]?[0-9٠-٩]{1,3}\s*[-–\.)\]]|^\s*[•\-–▪■●]|^\s*[أبجدهـو]\s*[-–\.)]")
JOURNALISH = re.compile(r"مجلة|المجلد|العدد|السنة|ISSN|Vol\.?|No\.?|Journal|Revue|تاريخ|الترقيم|جامعة|كلية",
                        re.I)


def printed_rows(ids, lines) -> list[list[str]]:
    """Azure lines grouped into printed rows (Azure cuts one printed row at a wide gap), top to bottom."""
    rows = []
    for i in sorted(ids, key=lambda i: (lines[i]["b"][1] + lines[i]["b"][3]) / 2):
        b = lines[i]["b"]
        c, h = (b[1] + b[3]) / 2, b[3] - b[1]
        if rows:
            rb = union([lines[j]["b"] for j in rows[-1]])
            if abs(c - (rb[1] + rb[3]) / 2) < 0.45 * max(h, rb[3] - rb[1]):
                rows[-1].append(i)
                continue
        rows.append([i])
    return rows


def long_headings(ans, lines, log):
    """A heading of more than 3 printed rows (or 3 rows and far more words than the article's other headings)
    that runs into the text under it (0478 p4, owner: «١ -قيود الأسبقيه / Precedence Requirements» typed as one
    heading with the paragraph below): its short top rows stay the heading, the rest becomes a paragraph after it.
    Kept whole (flagged only) when the rows after the top do not look like running text (a display title in big
    type: 0447 p1, 4 rows, 5 words)."""
    heads = [b for pg in ans.get("pages") or [] if isinstance(pg, dict) for b in pg.get("blocks") or []
             if isinstance(b, dict) and b.get("type") == "heading"]
    nw = sorted(len(" ".join(lines[i]["text"] for i in block_ids(b) if i in lines).split()) for b in heads)
    med = nw[len(nw) // 2] if nw else 0
    for pg in ans.get("pages") or []:
        if not isinstance(pg, dict):
            continue
        bl = pg.get("blocks") or []
        k = 0
        while k < len(bl):
            b = bl[k]
            k += 1
            if not isinstance(b, dict) or b.get("type") != "heading":
                continue
            ids = [i for i in block_ids(b) if i in lines]
            if not ids:
                continue
            rows = printed_rows(ids, lines)
            words = len(" ".join(lines[i]["text"] for i in ids).split())
            if not (len(rows) > HEAD_MAX_ROWS or (len(rows) == HEAD_MAX_ROWS and med and words > 4 * med)):
                continue
            wid = [union([lines[i]["b"] for i in r]) for r in rows]
            maxw = max(w[2] - w[0] for w in wid)
            rw = [len(" ".join(lines[i]["text"] for i in r).split()) for r in rows]
            cut = next((j for j in range(1, min(HEAD_MAX_ROWS, len(rows) - 1) + 1)
                        if wid[j][2] - wid[j][0] >= 0.7 * maxw and rw[j] >= 5), None)
            tail = sum(rw[cut:]) if cut else 0
            ent = dict(page=pg.get("page"), lines=ids, rows=len(rows), words=words, text=" ".join(
                lines[i]["text"] for i in ids)[:80])
            if not cut or tail < 12 or len(rows) - cut < 2:
                log["long_headings"].append(dict(ent, action="kept (flag only)"))
                continue
            top = {i for r in rows[:cut] for i in r}
            b["lines"] = [i for i in ids if i in top]
            rest = dict(type="paragraph", lines=[i for i in ids if i not in top], from_heading=True)
            bl.insert(k, rest)
            k += 1
            log["long_headings"].append(dict(ent, action=f"split: {cut} row(s) heading, {len(rows) - cut} rows "
                                                         f"paragraph"))


def header_text(ans, lines, log):
    """A header / footer block holding a line of running text (0478 p4, owner: the page number «٥٩» and the first
    list item «١-تقليل الوقت غير المستغل …» in one header block): a line of >= 5 words, not like the running head
    or footer of the chunk's other pages, not journal / date furniture, that sits in the text column next to the
    page's running text, goes back into the article: a list item when it opens with a number and the block below is
    a list item, else a paragraph; at the top of the page's flow (header) or its end (footer)."""
    pages = [pg for pg in ans.get("pages") or [] if isinstance(pg, dict)]
    furn = {}
    for pg in pages:
        for b in pg.get("blocks") or []:
            if isinstance(b, dict) and b.get("type") in ("header", "footer"):
                for i in block_ids(b):
                    if i in lines:
                        furn.setdefault(pg.get("page"), []).append(set(re.findall(r"\w+", lines[i]["text"])))
    for pg in pages:
        bl = pg.get("blocks") or []
        body = [i for b in bl if isinstance(b, dict) and b.get("type") in TEXT_TYPES | {"heading"}
                for i in block_ids(b) if i in lines]
        if not body:
            continue
        col = union([lines[i]["b"] for i in body])
        for b in list(bl):
            if not isinstance(b, dict) or b.get("type") not in ("header", "footer"):
                continue
            for i in [i for i in block_ids(b) if i in lines]:
                L = lines[i]
                t, lb = L["text"], L["b"]
                ws = set(re.findall(r"\w+", t))
                if len(t.split()) < 5 or JOURNALISH.search(t) or letters(t) < 15:
                    continue
                if any(len(ws & o) >= 0.5 * max(1, min(len(ws), len(o))) for p2, os_ in furn.items()
                       if p2 != pg.get("page") for o in os_):
                    continue                                   # the running head of the other pages
                h = lb[3] - lb[1]
                near = [lines[j]["b"] for j in body if xoverlap(lines[j]["b"], lb) > 0.3]
                if not near or min(abs(nb[1] - lb[3]) if nb[1] >= lb[1] else abs(lb[1] - nb[3]) for nb in near) > 1.5 * h:
                    continue
                if lb[0] < col[0] - 0.02 * 1000 or lb[2] > col[2] + 0.02 * 1000:
                    continue
                b["lines"] = [x for x in b.get("lines") or [] if str(x) != i]
                top = b["type"] == "header"
                flow = [x for x in bl if isinstance(x, dict) and x.get("type") not in ("header", "footer")]
                nb = flow[0] if top and flow else (flow[-1] if flow else None)
                typ = "list_item" if NUM_MARK.match(t) and nb is not None and nb.get("type") == "list_item" \
                    else "paragraph"
                nbk = dict(type=typ, lines=[i], from_furniture=True)
                if typ == "list_item" and nb.get("list"):
                    nbk["list"] = nb["list"]
                at = bl.index(nb) if (top and nb is not None) else (bl.index(nb) + 1 if nb is not None else len(bl))
                bl.insert(at, nbk)
                log["header_text"].append(dict(page=pg.get("page"), line=i, was=b["type"], now=typ, text=t[:80]))
            if not b.get("lines"):
                bl.remove(b)


# ------------------------------------------------------------------------------------------------ the rules

def endnotes(ans, log):
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if isinstance(b, dict) and b.get("type") == "endnote":
                b["type"] = "footnote"
                b["note_kind"] = "endnote"
                if not b.get("id"):
                    b["id"] = f"en-{b.get('marker')}"
                log["endnotes"] += 1


def v3_types(ans, log):
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "title" and b.get("translated") in (True, "true", 1):
                b["type"] = "trans_title"
                log["trans_titles"] += 1
            elif b.get("type") == "figure" and isinstance(b.get("description"), dict):
                d = {str(k): v for k, v in b["description"].items() if isinstance(v, str) and v.strip()}
                b["description"] = json.dumps(d, ensure_ascii=False) if d else None
                log["descriptions_two_languages"] += len(d) > 1
            elif b.get("type") == "boxed":
                k = b.get("box")
                b["level"] = str(k) if k is not None else None
                log["boxed_blocks"] += 1


def nows(s):
    return re.sub(r"\s+", "", s or "")


def bad_splits(ans, lines, log):
    keep, bad = [], {}
    seen = set()
    for s in ans.get("splits") or []:
        if not isinstance(s, dict):
            continue
        lid = str(s.get("line"))
        parts = [p for p in (s.get("parts") or []) if isinstance(p, str)]
        t = (lines.get(lid) or {}).get("text", "")
        same = lid in lines and len(parts) >= 2 and lid not in seen and (
            nows("".join(parts)) == nows(t) or sorted(" ".join(parts).split()) == sorted(t.split()))
        toks = t.split()
        if same:
            keep.append(s)
            seen.add(lid)
        elif lid in lines and lid not in seen and len(parts) >= 2 and \
                sum(len(p.split()) for p in parts) == len(toks) and all(p.split() for p in parts):
            # the parts hold as many words as Azure's line, a letter or two retyped (exp 41: أن -> ان): the
            # same cut, made of Azure's own words
            new, k = [], 0
            for p in parts:
                n = len(p.split())
                new.append(" ".join(toks[k:k + n]))
                k += n
            keep.append(dict(s, parts=new, _rebuilt_from=parts))
            seen.add(lid)
            log["bad_splits"].append(dict(line=lid, parts=parts, azure=t, action="parts rebuilt from Azure's words"))
        elif lid in lines:
            bad[lid] = s
        else:
            keep.append(s)
    if isinstance(ans.get("splits"), list):
        ans["splits"] = keep
    if not bad:
        return
    placed = set()

    def fix_list(ids):
        out = []
        for i in ids:
            m = re.match(r"^(\d+:\d+)[a-p]$", str(i))
            if m and m.group(1) in bad:
                if m.group(1) not in placed:
                    placed.add(m.group(1))
                    out.append(m.group(1))
                continue
            out.append(i)
        return out
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if not isinstance(b, dict):
                continue
            if isinstance(b.get("lines"), list):
                b["lines"] = fix_list(b["lines"])
            if isinstance(b.get("hemistichs"), list):
                b["hemistichs"] = [fix_list(h if isinstance(h, list) else [h]) for h in b["hemistichs"]]
            for r in b.get("rows") or []:
                for c in (r if isinstance(r, list) else []):
                    if isinstance(c, dict) and isinstance(c.get("lines"), list):
                        c["lines"] = fix_list(c["lines"])
    for lid, s in bad.items():
        log["bad_splits"].append(dict(line=lid, parts=s.get("parts"), azure=lines[lid]["text"],
                                      action="undone: the whole line in the first part's place" if lid in placed
                                      else "undone: no block held it"))


def verse_cuts(ans, lines, log):
    if not isinstance(ans.get("splits"), list):
        ans["splits"] = []
    splits = ans["splits"]
    done = {str(s.get("line")) for s in splits if isinstance(s, dict)}
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if not isinstance(b, dict) or b.get("type") != "verse" or not isinstance(b.get("cut"), dict):
                continue
            for lid, k in b["cut"].items():
                lid = str(lid)
                toks = (lines.get(lid) or {}).get("text", "").split()
                try:
                    k = int(k)
                except (TypeError, ValueError):
                    k = 0
                if lid not in lines or not 0 < k < len(toks) or lid in done:
                    log["bad_cuts"].append(dict(line=lid, cut=b["cut"].get(lid)))
                    continue
                splits.append({"line": lid, "parts": [" ".join(toks[:k]), " ".join(toks[k:])], "_cut": k})
                done.add(lid)
                log["cuts"] += 1
                hs = b.get("hemistichs") or []
                flat = [str(i) for h in hs for i in (h if isinstance(h, list) else [h])]
                if lid in flat and f"{lid}a" not in flat:          # the uncut line given as a hemistich: cut it
                    new = []
                    for h in hs:
                        h = h if isinstance(h, list) else [h]
                        if [str(i) for i in h] == [lid]:
                            new += [[f"{lid}a"], [f"{lid}b"]]
                        else:
                            new.append([x if str(x) != lid else f"{lid}a" for x in h])
                    b["hemistichs"] = new


def split_parts(ans, lines) -> dict:
    """line id -> token counts of its split parts (only when the parts are Azure's words, in order)."""
    out = {}
    for s in ans.get("splits") or []:
        if not isinstance(s, dict):
            continue
        lid = str(s.get("line"))
        parts = [p for p in (s.get("parts") or []) if isinstance(p, str)]
        if lid in lines and len(parts) >= 2 and " ".join(" ".join(parts).split()) == " ".join(lines[lid]["text"].split()):
            out[lid] = [len(p.split()) for p in parts]
    return out


def ornaments(ans, lines, words, log):
    found = {}
    for o in ans.get("ornaments") or []:
        if not isinstance(o, dict):
            continue
        lid = base_of(o.get("line"), lines)
        toks = lines[lid]["text"].split() if lid else []
        try:
            w = int(o.get("word"))
        except (TypeError, ValueError):
            w = 0
        t = (o.get("text") or "").strip()
        if lid and not (1 <= w <= len(toks) and (not t or toks[w - 1] == t)):
            near = [k + 1 for k, x in enumerate(toks) if x == t]            # word number off: the nearest same mark
            w = min(near, key=lambda k: abs(k - w)) if near else 0
        pic = bool(o.get("picture"))
        if pic and lid and 1 <= w <= len(toks) and words is not None:       # v3.1: junk read from a sign in a line
            ws = words(lid)
            if len(ws) == len(toks) and real_word(ws[w - 1]["text"], ws[w - 1].get("conf")):
                pic = None                     # Azure read a real word there: kept (the model's word is not enough)
        if not lid or not 1 <= w <= len(toks) or (letters(toks[w - 1]) > 1 and not pic):
            log["ornaments_rejected"].append(o)
            continue
        found[(lid, w)] = dict(line=lid, word=w, text=toks[w - 1], source="model", **({"picture": True} if pic else {}))
    # code: lone marks at the inner edge of a verse half
    parts = split_parts(ans, lines)
    calls = {}
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            for c in (b.get("calls") or []) if isinstance(b, dict) else []:
                if isinstance(c, dict):
                    calls.setdefault(base_of(c.get("line"), lines), set()).add(str(c.get("marker") or ""))
    fixed = {}
    for f in ans.get("fixes") or []:
        if isinstance(f, dict):
            fixed.setdefault(base_of(f.get("line"), lines), []).append(str(f.get("from") or ""))
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if not isinstance(b, dict) or b.get("type") != "verse":
                continue
            hs = [h if isinstance(h, list) else [h] for h in (b.get("hemistichs") or [])]
            if len(hs) != 2:
                continue
            for side, h in enumerate(hs):
                if not h:
                    continue
                # the half's inner edge: the right half's last word, the left half's first word
                lid_part = str(h[-1] if side == 0 else h[0])
                lid = base_of(lid_part, lines)
                if not lid:
                    continue
                toks = lines[lid]["text"].split()
                if lid_part != lid:                                  # a part of a split line
                    cnt = parts.get(lid)
                    k = "abcdefghijklmnop".index(lid_part[-1])
                    if not cnt or k >= len(cnt):
                        continue
                    start = sum(cnt[:k])
                    w = start + cnt[k] if side == 0 else start + 1
                else:
                    w = len(toks) if side == 0 else 1
                if not 1 <= w <= len(toks) or (lid, w) in found:
                    continue
                t = toks[w - 1]
                if t in calls.get(lid, set()) or covered(lines[lid]["text"], w, fixed.get(lid, [])):
                    continue                    # a call marker, or a mark a fix reads as something else
                ok = bool(ORN_STRONG.match(t))
                if not ok and ORN_WEAK.match(t) and words is not None:
                    ok = in_gap(words(lid), toks, w)
                if ok:
                    found[(lid, w)] = dict(line=lid, word=w, text=t, source="code")
    ans["_ornaments"] = sorted(found.values(), key=lambda o: (o["line"], o["word"]))
    log["ornaments_model"] += sum(1 for o in found.values() if o["source"] == "model")
    log["ornaments_code"] += sum(1 for o in found.values() if o["source"] == "code")


def covered(text: str, w: int, froms: list[str]) -> bool:
    """Word w (1-based) of text lies inside the first occurrence of one of the fixes' "from" strings."""
    pos, start = 0, None
    for k, t in enumerate(text.split(), 1):
        i = text.find(t, pos)
        if k == w:
            start = i
            break
        pos = i + len(t)
    if start is None:
        return False
    end = start + len(text.split()[w - 1])
    for f in froms:
        i = text.find(f) if f else -1
        if i >= 0 and i < end and i + len(f) > start:
            return True
    return False


def in_gap(ws, toks, w) -> bool:
    """Word w (1-based) is separated from its neighbour by a gap at least 3x the line's median word gap."""
    if not ws or len(ws) != len(toks) or len(ws) < 3:
        return False
    xs = sorted(range(len(ws)), key=lambda k: -(ws[k]["box"][0] + ws[k]["box"][2]))     # right to left on the page
    pos = xs.index(w - 1)
    gaps = [ws[xs[j]]["box"][0] - ws[xs[j + 1]]["box"][2] for j in range(len(xs) - 1)]
    med = sorted(gaps)[len(gaps) // 2] if gaps else 0
    near = [g for j, g in enumerate(gaps) if j in (pos - 1, pos)]
    return bool(near) and max(near) >= max(3 * med, 8)


# ------------------------------------------------------------------------------------------------ show-through
# (2026-10-20, 0744 p1 in the 300: the reverse side's text shows through mirrored and pale; Azure reads it as garbled
# words, the model rightly calls it noise and the never-noise rule put ~40 lines a page back)
PALE = 0.3                  # a line whose ink share is under this part of the page's text median is not print
PALE_MIN_MEDIAN = 0.04      # ... judged only when the page's own text has at least this much ink (dark_share)
GHOST_CONF = 0.5            # or: Azure's mean word confidence under this ...
GHOST_KNOWN = 0.5           # ... and under this share of its words in the word list (wordlist43), >= 3 judged
GHOST_FAINT = 0.5           # or: ink under half the page's text median ...
GHOST_FAINT_CONF = 0.4      # ... and Azure's mean confidence under this


def show_through(cand, used, lines, words, log) -> set:
    """Lines that are not real print: pale against the page's text (show-through, a stain), or read with low
    confidence and mostly non-words. They stay noise (ALTO role.showThrough, flagged). Needs words.dark (the page
    image); without it nothing is judged."""
    dark = getattr(words, "dark", None)
    if dark is None:
        return set()
    try:
        import wordlist43 as WL
        W = WL.load()
    except Exception:                                        # noqa: BLE001
        WL, W = None, frozenset()
    med = {}
    for p in sorted({lines[i]["page"] for i in cand}):
        txt = [i for i in used if lines[i]["page"] == p and has_words(lines[i])]
        txt = sorted(txt, key=lambda i: -letters(lines[i]["text"]))[:25]
        ds = sorted(dark(p, lines[i]["b"]) for i in txt)
        med[p] = ds[len(ds) // 2] if ds else None
    out = set()
    for i in cand:
        L, p = lines[i], lines[i]["page"]
        d = dark(p, L["b"])
        ws = words(i) or []
        cs = [w.get("conf") for w in ws if w.get("conf") is not None]
        conf = sum(cs) / len(cs) if cs else None
        k, n = WL.known_share(L["text"], W) if WL and W else (0, 0)
        why = None
        if med[p] is not None and med[p] >= PALE_MIN_MEDIAN and d < PALE * med[p]:
            why = "pale"
        elif conf is not None and conf < GHOST_CONF and n >= 3 and k / n < GHOST_KNOWN:
            why = "non-words"
        elif med[p] is not None and med[p] >= PALE_MIN_MEDIAN and d < GHOST_FAINT * med[p] and \
                conf is not None and conf < GHOST_FAINT_CONF:
            why = "faint and unsure"                         # 0744 p1 1:27 / 1:28: ink 0.46 / 0.32 of the page's, conf 0.3
        if why:
            out.add(i)
            log["show_through"].append(dict(line=i, page=p, why=why, ink=round(d, 3),
                                            page_ink=None if med[p] is None else round(med[p], 3),
                                            conf=None if conf is None else round(conf, 2), known=f"{k}/{n}",
                                            text=L["text"][:80]))
    return out


def never_noise(ans, lines, log, words=None):
    """Put back every line with words that the answer called noise or dropped (see the module doc)."""
    pages = ans.get("pages") or []
    used = set()
    for pg in pages:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            for i in block_ids(b):
                bi = base_of(i, lines)
                if bi:
                    used.add(bi)
    noise = [str(x) for x in (ans.get("noise") or [])]
    noise_set = {base_of(x, lines) for x in noise} - {None}
    cand = [i for i in lines if i not in used and has_words(lines[i])]
    if not cand:
        return
    ghost = show_through(cand, used, lines, words, log)
    if ghost:
        cand = [i for i in cand if i not in ghost]
        ans.setdefault("_show_through", []).extend(sorted(ghost))
        if not cand:
            return
    page_of = {}
    for pg in pages:
        if isinstance(pg, dict):
            try:
                page_of[int(pg.get("page"))] = pg
            except (TypeError, ValueError):
                pass
    by_page = {}
    for i in cand:
        by_page.setdefault(lines[i]["page"], []).append(i)
    taken = set()
    for p, ids in sorted(by_page.items()):
        pg = page_of.get(p)
        if pg is None:
            pg = {"page": p, "blocks": []}
            pages.append(pg)
            page_of[p] = pg
        blocks = pg.setdefault("blocks", [])
        # clusters: lines one above the other (gap < 1.5 line heights) in the same column
        ids.sort(key=lambda i: lines[i]["b"][1])
        par = {i: i for i in ids}

        def find(i):
            while par[i] != i:
                i = par[i]
            return i
        for u in ids:
            for v in ids:
                if u < v:
                    bu, bv = lines[u]["b"], lines[v]["b"]
                    h = max(bu[3] - bu[1], bv[3] - bv[1], 1)
                    gap = max(bu[1], bv[1]) - min(bu[3], bv[3])
                    if gap < 1.5 * h and xoverlap(bu, bv) > 0.2:
                        par[find(u)] = find(v)
        clusters = {}
        for i in ids:
            clusters.setdefault(find(i), []).append(i)
        rtl = is_rtl(" ".join(lines[i]["text"] for i in ids))
        cl = sorted(clusters.values(), key=lambda c: (-(union([lines[i]["b"] for i in c])[0]) if rtl else
                                                     union([lines[i]["b"] for i in c])[0]))
        for c in cl:
            c.sort(key=lambda i: lines[i]["b"][1])
            cb = union([lines[i]["b"] for i in c])
            kind = "noise" if c[0] in noise_set else "dropped"
            if len(c) <= 2 and merge_into(blocks, c, lines, log, kind):
                taken.update(c)
                continue
            nb = {"type": "other", "lines": list(c), "from_noise": True}
            k = place(blocks, cb, lines)
            blocks.insert(k, nb)
            taken.update(c)
            for i in c:
                log["never_noise"].append(dict(line=i, page=p, kind=kind, action="new other block",
                                               text=lines[i]["text"][:80]))
    if taken:
        ans["noise"] = [x for x in noise if base_of(x, lines) not in taken]


# ------------------------------------------------------------------------------------------------ table over two columns
# (2026-10-20, 0368-013 p11 in the 300: a table printed at the foot of the right column and continued at the head of
# the left one was one table whose box covered the whole page, over both columns of text)
def table_parts(row_boxes) -> list[list[int]]:
    """Rows (each its box, 0-1000 or px, None for an empty row) -> runs of rows printed in one place. A new run starts
    where a row jumps back up the page by more than the table's own height so far and does not share the run's
    columns (horizontal overlap < 30%): the table continues in another column. One run: the table is whole."""
    parts, cur, cb = [], [], None
    for k, rb in enumerate(row_boxes):
        if rb is None:
            cur.append(k)
            continue
        if cb is not None and rb[3] < cb[1] + 0.25 * (cb[3] - cb[1]) and xoverlap(rb, cb) < 0.3:
            parts.append(cur)
            cur, cb = [], None
        cur.append(k)
        cb = rb if cb is None else union([cb, rb])
    if cur:
        parts.append(cur)
    return parts


def table_columns(ans, lines, log):
    """Count (and log) tables printed in two columns; the masters draw each part as its own ALTO block (one JATS
    table), the flags mark them table_spans_columns."""
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if not isinstance(b, dict) or b.get("type") != "table" or not isinstance(b.get("rows"), list):
                continue
            rbs = []
            for r in b["rows"]:
                ids = [base_of(i, lines) for c in (r if isinstance(r, list) else [])
                       for i in ((c.get("lines") or []) if isinstance(c, dict) else [c])]
                rbs.append(union([lines[x]["b"] for x in ids if x]))
            parts = table_parts(rbs)
            if len(parts) > 1:
                log["table_columns"].append(dict(page=pg.get("page"), rows=len(rbs), parts=[len(x) for x in parts],
                                                 boxes=[union([rbs[k] for k in x if rbs[k]]) for x in parts]))


# ------------------------------------------------------------------------------------------------ guillemets
# (2026-10-20, the 300: Azure reads printed «…» as ((…)) in many articles; some prints do use (( )), so the ink
# decides. A parenthesis is nearly as tall as the line's words; a guillemet is a small chevron at mid-height.)
DD_MIN = 2                  # at least this many (( / )) measured in the chunk
SP_MIN = 3                  # single ( measured: the article's own parenthesis height, the yardstick
DD_REL = 0.8                # (( this much shorter than a single ( ...
DD_ABS = 0.5                # ... and under this share of the word height: guillemets
DD_ALONE = 0.33             # no single ( to compare with: under this share (0701: printed (( at 0.38)
DD_SURE = 0.36              # under this share whatever the single ( (1010-001 pp7-10: 0.32 against 0.40)


def bracket_height(img, box, side, lh) -> float | None:
    """Height of the outermost ink piece at one end of a word (side "R" / "L"), as a share of the line's word
    height lh (300 dpi px)."""
    import cv2
    x0, y0, x1, y1 = (int(v) for v in box)
    w = int(lh)
    xa, xb = (x1 - w, x1) if side == "R" else (x0, x0 + w)
    crop = img[max(0, int(y0 - 0.3 * lh)):max(0, int(y1 + 0.3 * lh)), max(0, xa):max(0, xb)]
    if crop.size == 0:
        return None
    _, bw = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, _, st, _ = cv2.connectedComponentsWithStats(bw)
    c = [(st[k, 0], st[k, 2], st[k, 3]) for k in range(1, n) if st[k, 4] > 4]
    if not c:
        return None
    c = sorted(c, key=lambda z: -(z[0] + z[1]) if side == "R" else z[0])[:2]
    return max(h for _, _, h in c) / lh


def guillemets(ans, lines, words, log):
    """(( … )) Azure read where the print has « … »: decided per chunk from the ink (bracket_height of the (( / ))
    against the article's single parentheses); when they are guillemets every (( / )) of the chunk's lines becomes
    « / » through a fix (why "code: guillemets in the ink"); when unsure nothing changes and the chunk is logged
    (flag guillemets_unsure). D30 holds: the text is what is printed."""
    image = getattr(words, "image", None)
    hits = [i for i, L in lines.items() if "((" in L["text"] or "))" in L["text"]]
    if image is None or not hits:
        return
    import cv2
    import statistics
    dd, sp, imgs = [], [], {}
    for i in sorted(lines, key=lambda i: (lines[i]["page"], i in hits)):
        L = lines[i]
        if not re.search(r"\(", L["text"]) or (len(dd) >= 12 and len(sp) >= 12):
            continue
        ws = words(i) or []
        if not ws:
            continue
        p = L["page"]
        if p not in imgs:
            imgs[p] = cv2.imread(str(image(p)), cv2.IMREAD_GRAYSCALE)
        if imgs[p] is None:
            continue
        lh = statistics.median(w["box"][3] - w["box"][1] for w in ws) or 1
        rtl = is_rtl(L["text"])
        for w in ws:
            t = w["text"]
            o, c = ("R", "L") if rtl else ("L", "R")
            if (t == "((" or re.match(r"^\(\([^\W\d_]", t)) and len(dd) < 12:      # an opening (( before letters
                r = bracket_height(imgs[p], w["box"], o, lh)
                if r:
                    dd.append(r)
            elif re.match(r"^\([^\W\d_]{3}", t) and len(sp) < 12:              # a single ( before a word
                r = bracket_height(imgs[p], w["box"], o, lh)
                if r:
                    sp.append(r)
    if len(dd) < DD_MIN:
        return
    md = statistics.median(dd)
    ms = statistics.median(sp) if len(sp) >= SP_MIN else None
    if ms is not None:
        ok = md < DD_SURE or (md < DD_REL * ms and md < DD_ABS)
        sure = ok or md >= 0.9 * ms
    else:
        ok = md < DD_ALONE
        sure = ok or md >= 0.6
    rec = dict(pages=sorted({lines[i]["page"] for i in hits}), lines=len(hits), double=round(md, 2), n_double=len(dd),
               single=None if ms is None else round(ms, 2), n_single=len(sp))
    if not ok:
        log["guillemets"].append(dict(rec, decision="brackets as printed" if sure else "unsure"))
        return
    n = 0
    fx = ans.setdefault("fixes", [])
    for i in hits:
        t = lines[i]["text"]
        for frm, to in (("((", "«"), ("))", "»")):
            for _ in range(t.count(frm)):
                fx.append({"line": i, "from": frm, "to": to, "why": "code: guillemets in the ink (rules43.guillemets)"})
                n += 1
    log["guillemets"].append(dict(rec, decision="guillemets", fixes=n))


# ------------------------------------------------------------------------------------------------ vocalised lines
# (2026-10-20, 1875 p17 in the 300: in densely vowelled verse Azure loses letters: «الزَّاد» -> «الْادُ», «الْكَرِيمِ»
# -> «الْكَرِ»; the model did not restore them. Flag only: the fix route is a close-up re-read of the line.)
VOWELLED = 0.3              # diacritics per letter from which a line is "vocalised"
BAD_TASHKEEL = re.compile(r"^[وفبكل]?الْا[^ِ]|^[وفبكل]?الْا$|[ًٌٍَُِْ]{2,}|^[ًٌٍَُِّْ]|ّ{2}")   # «الْا»: the article's
                                                       # lam with sukun before a bare alef (a lost letter); stacked vowels


def vowelled_words(ans, lines, log):
    """Words in a vocalised line (verse, a quotation) that are not words: an impossible mark (sukun before alef, two
    vowels on a letter) or never seen once the marks are taken off, even without its clitics (wordlist43). Logged; flagged by flags43
    (letters_lost_vowelled); nothing changes."""
    try:
        import wordlist43 as WL
        W = WL.load()
    except Exception:                                        # noqa: BLE001
        return
    if not W:
        return
    used = {base_of(i, lines) for pg in ans.get("pages") or [] if isinstance(pg, dict)
            for b in pg.get("blocks") or [] if isinstance(b, dict) and b.get("type") not in ("header", "footer")
            for i in block_ids(b)} - {None}
    for i in sorted(used, key=lambda x: (lines[x]["page"], int(x.split(":")[1]))):
        t = lines[i]["text"]
        n = letters(t)
        if n < 8 or len(TASHKEEL.findall(t)) < VOWELLED * n:
            continue
        bad = []
        for w in t.split():
            core = re.sub(r"^[^\w]+|[^\w]+$", "", w)
            if len(AR_LET.findall(core)) < 3:
                continue
            if BAD_TASHKEEL.search(core):
                bad.append(dict(word=w, why="impossible marks"))
            elif not WL.known(core, W) and not (WL.fold(core).endswith("ا") and WL.known(WL.fold(core)[:-1], W)):
                bad.append(dict(word=w, why="not a word"))
        if bad:
            log["vowelled_doubtful"].append(dict(line=i, page=lines[i]["page"], words=bad, text=t[:80]))


# ------------------------------------------------------------------------------------------------ Latin line-end hyphens
# (2026-10-20, 2483 and 0310 in the 300: «classificat- ion», «tradition- nel»: a word cut at the line end kept its
# hyphen and got a space in the JATS)
LA_END = re.compile(r"([A-Za-zÀ-ɏ]{2,})[-‐‑]$")
LA_START = re.compile(r"^([a-zà-ÿœæ][A-Za-zÀ-ɏ]*)")


def latin_join(prev: str, nxt: str) -> str | None:
    """A Latin line ending in a hyphen after letters, the next line starting with a lower-case word: "join" (the
    word was cut: no hyphen, no space), "hyphen" (a compound cut at its own hyphen, «well-» «known»: hyphen kept, no
    space), None (not a cut word). Decided with wordlist43 when it exists: the hyphenated form known -> hyphen; the
    joined word known -> join; else the second part a word of its own -> hyphen («hispano-maghrébine»); else join."""
    a, b = LA_END.search((prev or "").rstrip()), LA_START.match((nxt or "").lstrip())
    if not a or not b or is_rtl(prev):
        return None
    try:
        import wordlist43 as WL
        W = WL.load()
    except Exception:                                        # noqa: BLE001
        return "join"
    if not W:
        return "join"
    x, y = a.group(1).split()[-1], b.group(1)
    if WL.freq(f"{x}-{y}", W):
        return "hyphen"
    if WL.freq(x + y, W):
        return "join"
    if len(y) >= 3 and WL.freq(y, W):
        return "hyphen"                    # the second part is a word of its own: «hispano-» «maghrébine» (1140)
    return "join"


# ------------------------------------------------------------------------------------------------ inline maths junk
# (2026-10-20, 0168 p5 in the 300: «μT = max ||x|| بحيث أن» became «… tostST- max …»: Azure's reading of a formula
# inside an Arabic sentence left in the text; math_failed fired elsewhere, not there. Flag only; prompt v3.4 asks
# for such formulas as LaTeX.)
MATHISH = re.compile(r"[=<>≤≥|∑∫√±×÷∞≠≈^_{}]|[A-Za-z]")
JUNK_CONF = 0.6


OPS = re.compile(r"[=<>≤≥|∑∫√±^{}]")
MIXED = re.compile(r"[a-z][A-Z]|^[A-Z]{2,4}$")


def formula_junk(t: str, conf) -> bool:
    """A token that looks like Azure's reading of a formula: Latin letters with an operator in the same token
    («||HT=maxx», «sup|hi(t)|»), or mixed-case / short capital soup («tostST», «DJO») read unsure (< JUNK_CONF);
    not a name or a word (wordlist43), not a lone dash or bar."""
    c = 1.0 if conf is None else conf
    if AR_LET.search(t) or c >= JUNK_CONF or not LA_LET.search(t) or len(t) < 2:
        return False
    if OPS.search(t):
        return True
    core = re.sub(r"[^A-Za-z]", "", t)
    if not MIXED.search(core):
        return False
    try:
        import wordlist43 as WL
        return not WL.freq(core)
    except Exception:                                        # noqa: BLE001
        return True


def math_parts(ans, lines, log):
    """A "math" entry with an empty LaTeX whose "from" holds no Arabic letter, on a line that has (or follows a line
    that has) a math entry with LaTeX: the model's way of saying "this junk is part of that formula" (0168 p5:
    «-tostST», the subscript of μ_T = max_{-t_0 ≤ t ≤ T} on the line above). Assembly rejects a math entry without
    LaTeX, so the junk stayed in the text; it becomes a fix that takes it out (the ALTO keeps Azure's reading)."""
    ms = [m for m in ans.get("math") or [] if isinstance(m, dict) and m.get("line") and m.get("from")]
    with_tex = {base_of(m["line"], lines) for m in ms if (m.get("latex") or "").strip()}
    keep = []
    for m in ans.get("math") or []:
        x = base_of(m.get("line"), lines) if isinstance(m, dict) and m.get("line") else None
        if x and m.get("from") and not (m.get("latex") or "").strip() and not AR_LET.search(m["from"]) and \
                m["from"] in lines[x]["text"]:
            p, k = x.split(":")
            prev = f"{p}:{int(k) - 1}"
            if x in with_tex or prev in with_tex:
                ans.setdefault("fixes", []).append({"line": m["line"], "from": m["from"], "to": "",
                                                    "why": "code: part of the formula given as LaTeX on this or the "
                                                           "line before (math with empty LaTeX; rules43.math_parts)"})
                log["math_parts"].append(dict(line=x, page=lines[x]["page"], text=m["from"]))
                continue
        keep.append(m)
    if "math" in ans:
        ans["math"] = keep


def inline_math_junk(ans, lines, words, log):
    """Latin / formula tokens Azure read with low confidence (< JUNK_CONF) in the Arabic lines of running text, not
    taken by the answer's "math" (or a fix): a formula left as junk. Also a short Latin-only line of such tokens
    between Arabic lines of the same block. Logged; flags43 inline_math_junk."""
    if words is None:
        return
    taken = {}
    for m in list(ans.get("math") or []) + list(ans.get("fixes") or []):
        if isinstance(m, dict) and m.get("line") and m.get("from"):
            taken.setdefault(base_of(m["line"], lines), []).append(m["from"])
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if not isinstance(b, dict) or b.get("type") not in TEXT_TYPES | {"paragraph"}:
                continue
            ids = [x for x in (base_of(i, lines) for i in b.get("lines") or []) if x]
            if not ids or not is_rtl(" ".join(lines[x]["text"] for x in ids)):
                continue
            for x in ids:
                t = lines[x]["text"]
                ws = words(x) or []
                rtl = is_rtl(t)
                if not rtl and len(ws) > 3:
                    continue                      # a Latin line of its own (a quotation, a reference)
                bad = [w["text"] for w in ws if formula_junk(w["text"], w.get("conf"))
                       and not any(w["text"] in f or f in w["text"] for f in taken.get(x, []))]
                if bad:
                    log["inline_math_junk"].append(dict(line=x, page=lines[x]["page"], words=bad, text=t[:80]))


# ------------------------------------------------------------------------------------------------ an advert in pieces
# (2026-10-20, 1010-006 p2 in the 300: an advertisement for «الجلادون», rightly "another article", drawn as picture
# pieces with its own words as small faint text between them)
ADVERT_PICTURE = 0.4        # pictures covering this share of an other_article block's box: one picture


def advert_whole(ans, lines, log):
    """An other_article block that is mostly pictures (the pictures inside its box cover >= ADVERT_PICTURE of it)
    becomes ONE figure of another article (level "other"): its box the union of the block and those pictures, its
    lines the figure's words (ALTO pictureText; not in this article's JATS); the pieces go."""
    for pg in ans.get("pages") or []:
        blocks = pg.get("blocks") if isinstance(pg, dict) else None
        if not isinstance(blocks, list):
            continue
        for b in list(blocks):
            if not isinstance(b, dict) or b.get("type") != "other_article" or b not in blocks:
                continue
            bb = block_box(b, lines)
            if not bb:
                continue
            area = max(1.0, (bb[2] - bb[0]) * (bb[3] - bb[1]))
            figs = [f for f in blocks if isinstance(f, dict) and f.get("type") == "figure" and fig_box(f)
                    and inside(fig_box(f), grow(bb, 10, 10)) >= 0.8]
            cover = sum((fig_box(f)[2] - fig_box(f)[0]) * (fig_box(f)[3] - fig_box(f)[1]) for f in figs) / area
            if not figs or cover < ADVERT_PICTURE:
                continue
            box = union([bb] + [fig_box(f) for f in figs])
            ids = list(b.get("lines") or []) + [i for f in figs for i in f.get("lines") or []]
            nf = {"type": "figure", "box": [round(float(v), 1) for v in box], "lines": ids, "level": "other",
                  "advert": True}
            k = blocks.index(b)
            blocks[k] = nf
            blocks[:] = [x for x in blocks if not any(x is f for f in figs)]
            log["advert_whole"].append(dict(page=pg.get("page"), box=nf["box"], pieces=len(figs), lines=len(ids),
                                            cover=round(cover, 2)))


# ------------------------------------------------------------------------------------------------ page numbers
# (2026-10-20, 1010-006 p2 in the 300: print ٤٥, Azure ٣٥, kept)
AR_DIG = "٠١٢٣٤٥٦٧٨٩"
PAGE_NO = re.compile(r"^[\s\-–—_.]*([0-9٠-٩]{1,4})[\s\-–—_.]*$")


def page_numbers(ans, lines, log):
    """A page number Azure misread: the chunk's other page numbers (lone numbers in header / footer blocks, one a
    page) agree on one offset from the page index (>= 2 pages, >= 2/3 of them), so do the pages either side of this one,
    and this one does not, with as many
    digits as the expected number -> a fix to the expected number in the same digits (why "code: page number in
    sequence"). Logged."""
    found = {}
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if not isinstance(b, dict) or b.get("type") not in ("header", "footer"):
                continue
            for i in b.get("lines") or []:
                x = base_of(i, lines)
                m = PAGE_NO.match(lines[x]["text"]) if x and x == str(i) else None
                if m:
                    found.setdefault(lines[x]["page"], []).append((x, m.group(1)))
    vals = {}
    for p, xs in found.items():
        if len(xs) == 1:
            t = xs[0][1]
            vals[p] = (xs[0][0], t, int(t.translate(str.maketrans(AR_DIG, "0123456789"))))
    if len(vals) < 3:
        return
    offs = Counter(v[2] - p for p, v in vals.items())
    o, n = offs.most_common(1)[0]
    if n < 2 or n < 2 / 3 * len(vals):
        return
    for p, (x, t, v) in sorted(vals.items()):
        e = p + o
        if v == e or len(str(e)) != len(t) or e <= 0:
            continue
        nb = [vals.get(p - 1), vals.get(p + 1)]
        if not all(q is not None and q[2] - (p + d) == o for q, d in zip(nb, (-1, 1))):
            continue                       # only a lone misreading between two pages in sequence (not a jump)
        to = str(e).translate(str.maketrans("0123456789", AR_DIG)) if t[0] in AR_DIG else str(e)
        ans.setdefault("fixes", []).append({"line": x, "from": t, "to": to,
                                            "why": "code: page number in sequence (rules43.page_numbers)"})
        log["page_numbers"].append(dict(line=x, page=p, printed_read=t, now=to, pages_agreeing=n))


# ------------------------------------------------------------------------------------------------ a rubric as the title
# (2026-10-20, coordinator / experiment 46: 0344-002-002-002 «II. - JURISPRUDENCE», 0814-007-020-008 «REVUE DES
# LIVRES»: the journal's section label became the article's title; the catalogue has the heading that follows)
RUBRICS = re.compile(r"^(jurisprudence|revue des livres|comptes? rendus?|bibliographie|chroniques?|documents?|"
                     r"notes? de lecture|notes?|l[ée]gislation|doctrine|[ée]tudes|articles|informations|"
                     r"book reviews?|reviews?|documents? et informations|varia|"
                     r"عرض كتاب|عرض الكتب|مراجعة كتاب|مراجعات|قراءات|قراءة في كتاب|ملف العدد|دراسات|بحوث|وثائق|"
                     r"تقارير|أخبار|اصدارات جديدة|إصدارات جديدة|تعريف بكتاب|ندوات|متابعات)$", re.I)
NUMBERING = re.compile(r"^\s*([IVXLC]+|[0-9٠-٩]+|[A-Z])\s*[\.\)\-–—:]+\s*[\-–—]?\s*")


def is_rubric(text: str) -> bool:
    t = " ".join(NUMBERING.sub("", text or "").replace("-", " ").split()).strip(" .:-–—")
    return bool(t) and bool(RUBRICS.match(t))


def rubric_title(ans, lines, log):
    """A title block that is a journal's section label (a rubric: «JURISPRUDENCE», «REVUE DES LIVRES», «عرض كتاب»,
    numbered or not) becomes a heading (level 1) and the first heading after it on the first three pages becomes
    the title (Gemini's metadata title too, when it was the rubric). Without such a heading nothing changes."""
    pages = [pg for pg in ans.get("pages") or [] if isinstance(pg, dict)]
    if not pages:
        return
    p0 = min(int(pg.get("page") or 0) for pg in pages)
    seq = [(int(pg.get("page") or 0), b) for pg in sorted(pages, key=lambda g: int(g.get("page") or 0))
           for b in pg.get("blocks") or [] if isinstance(b, dict)]
    txt = lambda b: " ".join(lines[x]["text"] for x in (base_of(i, lines) for i in b.get("lines") or []) if x)  # noqa
    for k, (p, b) in enumerate(seq):
        if b.get("type") != "title" or p > p0 + 1 or not is_rubric(txt(b)):
            continue
        nxt = next((c for q, c in seq[k + 1:] if q <= p0 + 2 and c.get("type") == "heading"), None)
        if nxt is None:
            log["rubric_title"].append(dict(page=p, rubric=txt(b), action="kept (no heading after it)"))
            continue
        b["type"], b["level"] = "heading", 1
        nxt["type"] = "title"
        nxt.pop("level", None)
        md = ans.get("metadata") if isinstance(ans.get("metadata"), dict) else None
        if md is not None and is_rubric(str(md.get("title") or "")):
            md["title"] = txt(nxt)
        log["rubric_title"].append(dict(page=p, rubric=txt(b), title=txt(nxt)[:100], action="rubric -> heading"))


def block_box(b, lines):
    return union([lines[x]["b"] for x in (base_of(i, lines) for i in block_ids(b)) if x])


def merge_into(blocks, c, lines, log, kind) -> bool:
    best = None
    for bi, b in enumerate(blocks):
        if not isinstance(b, dict) or b.get("type") not in MERGE or not b.get("lines"):
            continue
        for k, i in enumerate(b["lines"]):
            x = base_of(i, lines)
            if not x:
                continue
            bx, lb = lines[x]["b"], lines[c[0]]["b"]
            h = max(bx[3] - bx[1], lb[3] - lb[1], 1)
            cbx = union([lines[j]["b"] for j in c])
            gap = max(bx[1], cbx[1]) - min(bx[3], cbx[3])
            if gap < 1.5 * h and xoverlap(bx, cbx) >= 0.5:
                d = max(0, gap)
                after = cbx[1] >= bx[1]
                if best is None or d < best[0]:
                    best = (d, bi, k + 1 if after else k)
    if best is None:
        return False
    _, bi, k = best
    blocks[bi]["lines"][k:k] = list(c)
    blocks[bi].setdefault("from_noise", []).extend(c)
    for i in c:
        log["never_noise"].append(dict(line=i, page=lines[i]["page"], kind=kind,
                                       action=f"joined its {blocks[bi]['type']} block", text=lines[i]["text"][:80]))
    return True


def place(blocks, cb, lines) -> int:
    """Where a new block goes in the page's reading order: before the first block that starts lower in the same
    column; else before the page's closing furniture."""
    for k, b in enumerate(blocks):
        if not isinstance(b, dict) or b.get("type") in ("header",):
            continue
        bb = block_box(b, lines) if b.get("type") != "figure" else b.get("box")
        if bb and bb[1] > cb[1] and xoverlap(bb, cb) > 0:
            return k
    k = len(blocks)
    while k > 0 and isinstance(blocks[k - 1], dict) and blocks[k - 1].get("type") == "footer":
        k -= 1
    return k


def orth(s: str) -> str:
    s = TASHKEEL.sub("", s)
    return s.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي",
                                      "ء": None}))


def fixes(ans, log):
    keep = []
    for f in ans.get("fixes") or []:
        if isinstance(f, dict) and f.get("from") and f.get("to") is not None and f["from"] != f["to"] and \
                re.sub(r"\s+", "", f["from"]) == re.sub(r"\s+", "", f["to"]):
            log["fixes_spacing"].append(f)
        if isinstance(f, dict) and f.get("from") and f.get("to") and f["from"] != f["to"] and \
                orth(f["from"]) == orth(f["to"]) and TASHKEEL.sub("", f["from"]) != TASHKEEL.sub("", f["to"]):
            log["fixes_orthographic"].append(f)
        keep.append(f)
    ans["fixes"] = keep


def empty_rows(ans, log):
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            rows = b.get("rows") if isinstance(b, dict) and b.get("type") == "table" else None
            if not isinstance(rows, list):
                continue
            i = 0
            while i < len(rows):
                if isinstance(rows[i], list) and not rows[i] and i > 0:
                    for j in range(i):
                        for c in rows[j] if isinstance(rows[j], list) else []:
                            if isinstance(c, dict) and int(c.get("rowspan") or 1) > i - j:
                                c["rowspan"] = int(c["rowspan"]) - 1
                                if c["rowspan"] <= 1:
                                    c.pop("rowspan")
                    del rows[i]
                    log["empty_rows"] += 1
                    continue
                i += 1


EXCL = re.compile(r"\(\s*!\s*\)")
EXCL_DIGIT = re.compile(r"\(\s*[١1]\s*\)")


def exclamation(ans, log):
    """A "(!)" in Azure's text stays "(!)": a fix writing it as "(١)" is refused, calls on it dropped."""
    keep, lines_hit = [], set()
    for f in ans.get("fixes") or []:
        if isinstance(f, dict) and isinstance(f.get("from"), str) and isinstance(f.get("to"), str) and \
                EXCL.search(f["from"]) and EXCL_DIGIT.search(f["to"]) and \
                len(EXCL.findall(f["from"])) == len(EXCL_DIGIT.findall(f["to"])):
            orig = iter(EXCL.findall(f["from"]))
            to_ex = EXCL_DIGIT.sub(lambda m: next(orig), f["to"])
            from_n = f["from"]
            lines_hit.add(str(f.get("line")))
            log["exclamation_kept"].append(dict(line=f.get("line"), fix_from=f["from"], fix_to=f["to"]))
            if to_ex == from_n:
                continue                                     # the fix was only the exclamation: refused
            f = dict(f, to=to_ex)
        keep.append(f)
    if "fixes" in ans:
        ans["fixes"] = keep
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if not isinstance(b, dict) or not b.get("calls"):
                continue
            cs = []
            for c in b["calls"]:
                m = str(c.get("marker") or "") if isinstance(c, dict) else ""
                if isinstance(c, dict) and (EXCL.fullmatch(m.strip()) or
                                            (str(c.get("line")) in lines_hit and EXCL_DIGIT.fullmatch(m.strip()))):
                    log["exclamation_calls_dropped"].append(dict(line=c.get("line"), marker=m, fn=c.get("fn")))
                    continue
                cs.append(c)
            b["calls"] = cs


FIG_TEXT = {"boxed", "paragraph", "abstract", "quote", "other", "list_item", "keywords", "verse"}
HEAD = {"title", "heading", "byline"}


def fig_box(b):
    bx = b.get("box") if isinstance(b, dict) else None
    if not (isinstance(bx, list) and len(bx) == 4 and all(isinstance(v, (int, float)) for v in bx)):
        return None
    return [min(bx[0], bx[2]), min(bx[1], bx[3]), max(bx[0], bx[2]), max(bx[1], bx[3])]


def inside(lb, fb) -> float:
    """Share of the line box's area inside the figure box."""
    w = min(lb[2], fb[2]) - max(lb[0], fb[0])
    h = min(lb[3], fb[3]) - max(lb[1], fb[1])
    a = max(1e-9, (lb[2] - lb[0]) * (lb[3] - lb[1]))
    return max(0.0, w) * max(0.0, h) / a


def text_in_figure(ans, lines, log):
    for pg in ans.get("pages") or []:
        blocks = pg.get("blocks") if isinstance(pg, dict) else None
        if not isinstance(blocks, list):
            continue
        figs = [b for b in blocks if isinstance(b, dict) and b.get("type") == "figure" and fig_box(b)]
        # a picture that also holds the title / a heading / the byline is a background (0881 p1: a banner photo
        # under the title, byline and abstract): its text is the page's own, not the picture's
        heads = [base_of(i, lines) for b in blocks if isinstance(b, dict) and b.get("type") in HEAD
                 for i in block_ids(b)]
        figs = [f for f in figs if not any(x and inside(lines[x]["b"], fig_box(f)) >= 0.8 for x in heads)]
        if not figs:
            continue
        keep = []
        for b in blocks:
            moved = False
            if isinstance(b, dict) and b.get("type") in FIG_TEXT and b.get("lines"):
                ids = [base_of(i, lines) for i in block_ids(b)]
                if ids and all(ids):
                    for f in figs:
                        fb = fig_box(f)
                        if all(inside(lines[x]["b"], fb) >= 0.8 for x in ids):
                            f.setdefault("lines", [])
                            f["lines"] = list(f["lines"] or []) + list(b["lines"])
                            f.setdefault("text_from", []).append(b["type"])
                            log["text_in_figure"].append(dict(page=pg.get("page"), type=b["type"],
                                                              lines=list(b["lines"]), calls=len(b.get("calls") or []),
                                                              text=" ".join(lines[x]["text"] for x in ids)[:80]))
                            moved = True
                            break
            if not moved:
                keep.append(b)
        pg["blocks"] = keep


def figure_trim(ans, lines, log):
    for pg in ans.get("pages") or []:
        blocks = pg.get("blocks") if isinstance(pg, dict) else None
        if not isinstance(blocks, list):
            continue
        for f in blocks:
            fb = fig_box(f) if isinstance(f, dict) and f.get("type") == "figure" else None
            if not fb:
                continue
            for b in blocks:
                if not isinstance(b, dict) or b.get("type") not in HEAD | {"caption"}:
                    continue
                for x in (base_of(i, lines) for i in block_ids(b)):
                    if not x:
                        continue
                    lb = lines[x]["b"]
                    share = inside(lb, fb)
                    h = fb[3] - fb[1]
                    cy = (lb[1] + lb[3]) / 2
                    edge = cy < fb[1] + 0.2 * h or cy > fb[3] - 0.2 * h        # in the box's top or bottom band
                    if share <= 0 or (share >= 0.5 and not (b.get("type") == "caption" and edge)):
                        continue
                    old = list(fb)
                    if (lb[1] + lb[3]) / 2 < (fb[1] + fb[3]) / 2:
                        y = lb[3] + 4
                        if y - fb[1] < 0.3 * h:
                            fb[1] = y
                    else:
                        y = lb[1] - 4
                        if fb[3] - y < 0.3 * h:
                            fb[3] = y
                    if fb != old:
                        f["box"] = [round(v, 1) for v in fb]
                        log["figure_trim"].append(dict(page=pg.get("page"), line=x, old=old, new=f["box"]))


# ------------------------------------------------------------------------------------------------ pictures

PIC_KEEP = {"title", "trans_title", "heading", "byline", "header", "footer", "caption", "table", "equation",
            "footnote", "reference"}                       # a line of these is never taken as a picture's junk
PIC_MASK = {"figure", "table", "equation"}                 # their boxes are pictures / ink already accounted for
BRIDGE = 120                                               # 0-1000: widest run of words between two halves
NARROW = 60                                                # 0-1000: a junk line narrower than this is not masked
FRAME_AREA = 400000                                        # 0-1000 squared: a "picture" over 40% of the page ...
FRAME_LINES = 10                                           # ... holding this many lines of text is a frame / border
SMALL = 150                                                # 0-1000: a found picture smaller both ways, with no
                                                           # words read from it, is a decoration (0493 p1's cartoon)


def real_word(t: str, c) -> bool:
    """A word Azure read with some confidence: Arabic (>= 2 letters, confidence >= 0.5) or Latin with lower case
    (>= 3 letters, >= 2 lower case, >= 0.6: transliteration such as «nbt», «hk3t»). Capital soup («FRES», «DOA»,
    «DoC»), digits and lone marks are not."""
    c = 1.0 if c is None else c
    if len(AR_LET.findall(t)) >= 2 and c >= 0.5:
        return True
    return len(LA_LET.findall(t)) >= 3 and sum(ch.islower() for ch in t) >= 2 and c >= 0.6


def junk_line(lid, lines, words, max_conf=None) -> bool:
    """A line without one real word (see real_word): what Azure reads from a hieroglyph, a symbol or a drawing.
    max_conf: also require Azure's mean word confidence below it (inside a figure the model drew: «EGR» «POV» «END»
    are a diagram's real labels, read at 0.9+; «FRES safd.» at 0.3)."""
    ws = words(lid) if words is not None else None
    if ws and len(ws) == len(lines[lid]["text"].split()):
        if max_conf is not None:
            cs = [w.get("conf") for w in ws if w.get("conf") is not None]
            if not cs or sum(cs) / len(cs) >= max_conf:
                return False
        return not any(real_word(w["text"], w.get("conf")) for w in ws)
    if max_conf is not None:
        return False
    return not any(real_word(t, None) for t in lines[lid]["text"].split())


def junk_in_figure(lid, lines, words) -> bool:
    """Inside a picture the bar is higher: no word with two Arabic letters, no real word, and Azure unsure (mean
    confidence < 0.6: «FRES safd.»; < 0.4 when a word holds a digit). Single letters read at high confidence («D A»
    from a hieroglyph, «K» «j» of a diagram) cannot be told apart: they stay the figure's text."""
    toks = lines[lid]["text"].split()
    if any(len(AR_LET.findall(t)) >= 2 for t in toks) or not junk_line(lid, lines, words):
        return False
    digits = any(re.search(r"\d", t) for t in toks)      # a chart's scale (1147 p6, 0041 p10): its own text
    ws = words(lid) if words is not None else None
    cs = [w.get("conf") for w in ws or [] if w.get("conf") is not None]
    return bool(cs) and sum(cs) / len(cs) < (0.4 if digits else 0.6)


def swapped_box(f, blocks, lines) -> bool:
    """A figure box given as [y0, x0, y1, x1] (v3, 0355 p1: the photo's box lay over the text column): swap it when
    it covers >= 3 lines of the page's text and the swapped box covers none."""
    fb = fig_box(f)
    if not fb:
        return False
    sw = [fb[1], fb[0], fb[3], fb[2]]
    own = {base_of(i, lines) for i in block_ids(f)}
    txt = [base_of(i, lines) for b in blocks if isinstance(b, dict) and b.get("type") not in ("figure", "header",
                                                                                              "footer")
           for i in block_ids(b)]
    txt = [x for x in txt if x and x not in own]
    n = sum(1 for x in txt if inside(lines[x]["b"], fb) >= 0.8)
    m = sum(1 for x in txt if inside(lines[x]["b"], sw) >= 0.3)
    if n >= 3 and m == 0:
        f["box"] = sw
        return True
    return False


def grow(b, dx, dy):
    return [b[0] - dx, b[1] - dy, b[2] + dx, b[3] + dy]


def other_region(box, blocks, lines) -> bool:
    """A picture belongs to another article when the running text nearest to it is that article's."""
    best = None
    for b in blocks:
        if not isinstance(b, dict) or b.get("type") in ("header", "footer", "figure") or not b.get("lines"):
            continue
        bb = block_box(b, lines)
        if not bb:
            continue
        dx = max(0, bb[0] - box[2], box[0] - bb[2])
        dy = max(0, bb[1] - box[3], box[1] - bb[3])
        d = (dx * dx + dy * dy) ** .5
        if best is None or d < best[0]:
            best = (d, b.get("type"))
    return bool(best) and best[1] == "other_article"


def same_place(a, b, tol=15) -> bool:
    """Two boxes at the same place of their pages, or mirrored (odd / even pages)."""
    m = [1000 - b[2], b[1], 1000 - b[0], b[3]]
    return all(abs(u - v) <= tol for u, v in zip(a, b)) or all(abs(u - v) <= tol for u, v in zip(a, m))


def bridged(cands, line_boxes):
    """Two pieces of one picture side by side with printed words between them (0493 p4: a booklet cover whose
    title Azure read; the mask cut the cover in two): one picture. Two photos side by side have bare paper between
    them and stay two."""
    changed = True
    while changed:
        changed = False
        for i in range(len(cands)):
            for j in range(len(cands)):
                if i == j:
                    continue
                a, b = cands[i]["box"], cands[j]["box"]
                if a[0] > b[0]:
                    continue
                ha, hb = a[3] - a[1], b[3] - b[1]
                vo = min(a[3], b[3]) - max(a[1], b[1])
                gap = b[0] - a[2]
                if not (0 <= gap <= BRIDGE and vo >= 0.8 * min(ha, hb) and min(ha, hb) > 50):
                    continue
                g = [a[2], max(a[1], b[1]), b[0], min(a[3], b[3])]
                if not any(inside(lb, g) >= 0.5 for lb in line_boxes):
                    continue
                u = union([a, b])
                cands[i] = dict(cands[i], box=u, hit=cands[i].get("hit", []) + cands[j].get("hit", []),
                                fill=round(min(cands[i]["fill"], cands[j]["fill"]), 3))
                del cands[j]
                changed = True
                break
            if changed:
                break
    return cands


def figure_swap(ans, lines, log):
    """A figure box with x and y swapped (before text_in_figure, which would take the text under the wrong box)."""
    for pg in ans.get("pages") or []:
        blocks = pg.get("blocks") if isinstance(pg, dict) else None
        if not isinstance(blocks, list):
            continue
        for f in [b for b in blocks if isinstance(b, dict) and b.get("type") == "figure" and fig_box(b)]:
            old = fig_box(f)
            if swapped_box(f, blocks, lines):
                log["pictures"].append(dict(page=pg.get("page"), action="figure box x/y swapped back", box=f["box"],
                                            old=old, lines=[], text=""))


def pictures(ans, lines, words, log):
    """A picture is never lost (see the module doc). Needs words.ink and words.dark (masters43.azure_words);
    without them only the swapped-box check and the other-article tag of the answer's own figures run."""
    ink, dark = getattr(words, "ink", None), getattr(words, "dark", None)
    junk_all = set(ans.get("_picture_junk") or [])
    pages = []
    for pg in ans.get("pages") or []:
        blocks = pg.get("blocks") if isinstance(pg, dict) else None
        if not isinstance(blocks, list):
            continue
        try:
            p = int(pg.get("page"))
        except (TypeError, ValueError):
            continue
        pages.append((p, pg))
    found = {}
    for p, pg in pages:
        blocks = pg["blocks"]
        ids_p = [i for i, L in lines.items() if L["page"] == p]
        figs = [b for b in blocks if isinstance(b, dict) and b.get("type") == "figure" and fig_box(b)]
        keep_ids = {base_of(i, lines) for b in blocks if isinstance(b, dict) and b.get("type") in PIC_KEEP
                    for i in block_ids(b)} - {None}
        # (0) Azure's junk read from the answer's own pictures (v3.1 puts it in the figure's lines): out of the
        # figure's text (ALTO only), but never a diagram's labels (2382 p5 «EGR» «POV» at 0.9+, 0041's Arabic)
        for f in figs:
            fb = fig_box(f)
            out = [i for i in f.get("lines") or [] if str(i) in lines and inside(lines[str(i)]["b"], fb) >= 0.5
                   and junk_in_figure(str(i), lines, words)]
            if out:
                f["lines"] = [i for i in f["lines"] if i not in out]
                junk_all.update(str(i) for i in out)
                log["picture_junk"] += len(out)
                log["pictures"].append(dict(page=p, action="junk out of the figure's text", lines=out,
                                            text=" | ".join(lines[str(i)]["text"] for i in out)[:80]))
        if ink is None or not ids_p:
            continue
        # (1) ink that no line, picture, table or equation accounts for
        mask = []
        for i in ids_p:
            b = lines[i]["b"]
            h = b[3] - b[1]
            if b[2] - b[0] < NARROW and i not in keep_ids and junk_line(i, lines, words):
                continue                       # a sign Azure read as «DoC» or «#»: its ink is the picture's
            mask.append(grow(b, 0.3 * h, 0.3 * h))
        for b in blocks:
            if isinstance(b, dict) and b.get("type") in PIC_MASK:
                bb = fig_box(b) if b.get("type") == "figure" else block_box(b, lines)
                if bb:
                    mask.append(grow(bb, 8, 8))
        heads = [base_of(i, lines) for b in blocks if isinstance(b, dict) and b.get("type") in HEAD | {"trans_title"}
                 for i in block_ids(b)]
        heads = [x for x in heads if x]
        inverted = [x for x in heads if dark is not None and dark(p, lines[x]["b"]) >= 0.5]
        foot = [base_of(i, lines) for b in blocks if isinstance(b, dict) and b.get("type") == "footer"
                for i in block_ids(b)]
        foot = [x for x in foot if x]
        cands = []
        for bl in ink(p, mask):
            box = list(bl["box"])
            bw, bh = box[2] - box[0], box[3] - box[1]
            if any(inside(lines[x]["b"], box) >= 0.8 for x in heads):
                log["pictures_skipped"].append(dict(page=p, box=box, why="holds the title / a heading / byline"))
                continue                           # a banner under the page's own title: background
            if any(inside(lines[x]["b"], grow(box, 15, 15)) > 0 for x in inverted):
                log["pictures_skipped"].append(dict(page=p, box=box, why="the dark ground of a title"))
                continue                           # white title on black (0355 pp1-2): the ground round its lines
            if any(inside(lines[x]["b"], grow(box, 0.5 * (lines[x]["b"][3] - lines[x]["b"][1]), 8)) > 0 for x in heads):
                log["pictures_skipped"].append(dict(page=p, box=box, why="touches the title / a heading / byline"))
                continue                           # a stroke of a hand-lettered title outside Azure's box (0331 p1)
            if box[1] >= 920 and any(inside(lines[x]["b"], grow(box, 10, 10)) > 0 for x in foot):
                log["pictures_skipped"].append(dict(page=p, box=box, why="the page number's ornament"))
                continue                           # 0498 p5: the dark box round the page number
            if bw * bh >= FRAME_AREA and sum(1 for i in ids_p if i not in junk_all and
                                             inside(lines[i]["b"], box) >= 0.8 and has_words(lines[i])) >= FRAME_LINES:
                log["pictures_skipped"].append(dict(page=p, box=box, why="the page's frame or border round its text"))
                continue                           # 2026-10-20: 0368-003 pp11-12, 1080 ×2, 0751: whole-page "figure"
            if max(bw, bh) >= 10 * min(bw, bh) and bl["fill"] >= 0.35:
                log["pictures_skipped"].append(dict(page=p, box=box, why="a bar"))
                continue
            hit = []
            for i in ids_p:
                if i in keep_ids or i in junk_all:
                    continue
                lb = lines[i]["b"]
                h = lb[3] - lb[1]
                if inside(lb, grow(box, 2.0 * h, 0.5 * h)) > 0 and junk_line(i, lines, words):
                    hit.append(i)
            if hit:
                box = union([box] + [lines[i]["b"] for i in hit])
            cands.append(dict(bl, box=box, hit=hit))
        if cands:
            from ink43 import rows                 # a strip cut in two by the junk lines between: one
            cands = rows(cands)
            cands = bridged(cands, [lines[i]["b"] for i in ids_p])
        found[p] = cands
    # (2) a picture at the same place on two pages of the chunk is page furniture (a running head's logo, a page
    # number's ornament): not the article's picture
    for p, cands in found.items():
        for c in cands:
            c["furniture"] = any(same_place(c["box"], d["box"]) for q, ds in found.items() if q != p for d in ds)
    for p, pg in pages:
        blocks = pg["blocks"]
        figs = [b for b in blocks if isinstance(b, dict) and b.get("type") == "figure" and fig_box(b)]
        for c in found.get(p, []):
            box, hit = c["box"], sorted(set(c.get("hit") or []))
            if c["furniture"] and not hit:
                log["pictures_skipped"].append(dict(page=p, box=box, why="the same place on another page"))
                continue
            bw, bh = box[2] - box[0], box[3] - box[1]
            gone = []
            for b in blocks:                                  # the junk leaves the blocks that held it
                if not isinstance(b, dict) or b.get("type") == "table" or not hit:
                    continue
                had = block_ids(b)
                if b.get("lines"):
                    b["lines"] = [i for i in b["lines"] if base_of(i, lines) not in hit]
                if b.get("type") == "verse" and b.get("hemistichs"):
                    b["hemistichs"] = [[i for i in (h if isinstance(h, list) else [h])
                                        if base_of(i, lines) not in hit] for h in b["hemistichs"]]
                    b["hemistichs"] = [h for h in b["hemistichs"] if h]
                if had and not block_ids(b) and b.get("type") != "figure":
                    gone.append(id(b))
            if gone:
                blocks[:] = [b for b in blocks if id(b) not in gone]
            junk_all.update(hit)
            small = not hit and bw < SMALL and bh < SMALL
            nf = {"type": "figure", "box": [round(float(v), 1) for v in box], "lines": [],
                  "level": "ink decoration" if small else "ink", "from_ink": dict(fill=c["fill"], junk=hit)}
            blocks.insert(place(blocks, box, lines), nf)
            figs.append(nf)
            log["picture_junk"] += len(hit)
            log["pictures"].append(dict(page=p, action="new figure from ink", box=nf["box"], fill=c["fill"],
                                        lines=hit, small=small, text=" | ".join(lines[i]["text"] for i in hit)[:80]))
        # (3) a picture among another article's text is that article's
        for f in figs:
            if other_region(fig_box(f), blocks, lines):
                lv = str(f.get("level") or "")
                f["level"] = (lv + " other") if lv.startswith("ink") else "other"
                log["pictures_other_article"] += 1
    if junk_all:
        ans["_picture_junk"] = sorted(junk_all)
        noise = [str(x) for x in ans.get("noise") or []]
        ans["noise"] = noise + [i for i in sorted(junk_all) if i not in noise]


def new_log() -> dict:
    return dict(endnotes=0, cuts=0, bad_cuts=[], ornaments_model=0, ornaments_code=0, ornaments_rejected=[],
                never_noise=[], fixes_spacing=[], bad_splits=[], fixes_orthographic=[], other_article_blocks=0,
                other_article_lines=0, empty_rows=0, exclamation_kept=[], exclamation_calls_dropped=[],
                text_in_figure=[], figure_trim=[], trans_titles=0, boxed_blocks=0, descriptions_two_languages=0,
                pictures=[], pictures_skipped=[], picture_junk=0, pictures_other_article=0, picture_words=0,
                long_headings=[], header_text=[], inline_pictures=[], show_through=[], table_columns=[], guillemets=[], vowelled_doubtful=[], inline_math_junk=[], math_parts=[], advert_whole=[], page_numbers=[], rubric_title=[])


def normalize(ans: dict, lines: dict, words=None) -> tuple[dict, dict]:
    ans = copy.deepcopy(ans or {})
    log = new_log()
    if isinstance(ans.get("pages"), list):
        for pg in ans["pages"]:
            for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
                if isinstance(b, dict) and b.get("type") == "other_article":
                    log["other_article_blocks"] += 1
                    log["other_article_lines"] += len(b.get("lines") or [])
    endnotes(ans, log)
    v3_types(ans, log)
    rubric_title(ans, lines, log)
    bad_splits(ans, lines, log)
    verse_cuts(ans, lines, log)
    ornaments(ans, lines, words, log)
    never_noise(ans, lines, log, words)
    long_headings(ans, lines, log)
    header_text(ans, lines, log)
    exclamation(ans, log)
    figure_swap(ans, lines, log)
    text_in_figure(ans, lines, log)
    figure_trim(ans, lines, log)
    pictures(ans, lines, words, log)
    advert_whole(ans, lines, log)
    text_in_figure(ans, lines, log)            # again: words printed inside a picture the ink rule found
    empty_rows(ans, log)
    table_columns(ans, lines, log)
    guillemets(ans, lines, words, log)
    vowelled_words(ans, lines, log)
    page_numbers(ans, lines, log)
    math_parts(ans, lines, log)
    inline_math_junk(ans, lines, words, log)
    fixes(ans, log)
    return ans, log


def summary(log: dict) -> dict:
    return {k: (len(v) if isinstance(v, list) else v) for k, v in log.items()}


def merge_logs(logs) -> dict:
    tot = Counter()
    for lg in logs:
        tot.update(summary(lg))
    return dict(tot)
