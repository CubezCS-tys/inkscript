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
  text in fig.  a block of running text (paragraph, abstract, quote, other, list item, keywords, verse) whose every
                line lies inside a figure's box on its page (>= 80% of each line's area) is the figure's own text
                (0493 p1: a paragraph printed on a drawn TV screen), unless the figure also holds a title, heading
                or byline line (then it is a background picture under the page's own text: 0881 p1): its lines become the figure's "lines" (the
                masters keep them as the figure's text, the view shows the picture only); its calls are dropped
  figure trim   a figure box that runs over a line of a title / heading / byline (less than half of the line inside
                the box) is cut back to that line's edge (+ the crop's 4/1000 margin), when the cut is under 30% of
                the box's height (0493 p1: the TV drawing's box began inside the title's second line)
  fixes counted fixes that only add or remove spaces, and fixes that only change hamza / ya / ta marbuta forms,
                are counted, not changed (mostly Azure gluing words: right to fix)
"""
from __future__ import annotations

import copy
import re
from collections import Counter

MIN_LETTERS = 4                 # fewer letters than this: a speck read as letters (exp 41: "ins", "هـ", "x", "mi")
MIN_W_PER_LETTER = 1.5          # box width (0-1000) per letter; a 7-wide box with 8 letters is vertical junk
EDGE = 15                       # a line wholly within 1.5% of the left or right page edge is a sliver
MERGE = {"paragraph", "quote", "list_item", "reference", "footnote", "abstract", "keywords", "other",
         "other_article", "caption"}
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
        if not lid or not 1 <= w <= len(toks) or letters(toks[w - 1]) > 1:
            log["ornaments_rejected"].append(o)
            continue
        found[(lid, w)] = dict(line=lid, word=w, text=toks[w - 1], source="model")
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


def never_noise(ans, lines, log):
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


FIG_TEXT = {"paragraph", "abstract", "quote", "other", "list_item", "keywords", "verse"}
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
                if not isinstance(b, dict) or b.get("type") not in HEAD:
                    continue
                for x in (base_of(i, lines) for i in block_ids(b)):
                    if not x:
                        continue
                    lb = lines[x]["b"]
                    share = inside(lb, fb)
                    if share <= 0 or share >= 0.5:
                        continue
                    h = fb[3] - fb[1]
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


def new_log() -> dict:
    return dict(endnotes=0, cuts=0, bad_cuts=[], ornaments_model=0, ornaments_code=0, ornaments_rejected=[],
                never_noise=[], fixes_spacing=[], bad_splits=[], fixes_orthographic=[], other_article_blocks=0,
                other_article_lines=0, empty_rows=0, exclamation_kept=[], exclamation_calls_dropped=[],
                text_in_figure=[], figure_trim=[])


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
    bad_splits(ans, lines, log)
    verse_cuts(ans, lines, log)
    ornaments(ans, lines, words, log)
    never_noise(ans, lines, log)
    exclamation(ans, log)
    text_in_figure(ans, lines, log)
    figure_trim(ans, lines, log)
    empty_rows(ans, log)
    fixes(ans, log)
    return ans, log


def summary(log: dict) -> dict:
    return {k: (len(v) if isinstance(v, list) else v) for k, v in log.items()}


def merge_logs(logs) -> dict:
    tot = Counter()
    for lg in logs:
        tot.update(summary(lg))
    return dict(tot)
