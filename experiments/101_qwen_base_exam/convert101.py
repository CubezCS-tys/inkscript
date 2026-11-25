"""Experiment 101 (experiment 100's convert100.py, copied 2026-11-24; only the folder and the default model directory
changed: EXP101_MODEL, default out/model/4B): a model's page Markdown -> blocks -> the exam's key formats, in Azure
line numbers.  Plain Qwen3.5 is asked (prompts/P1.txt, P2.txt) for exactly the output OCRia-1 was trained to give.

Run with the repo's .venv python (rapidfuzz).  Reads the model's raw answers (out/model/<set>/<stem>_pNNN.json); never
imports anything from the model.

The model gives no boxes, so Azure lines are found in its text, not on the page:

1. The answer is cut into blocks (strict Markdown reading: blank lines end a paragraph; `#` headings; `*`/`-`/`+`/
   `\\*` and `1.`/`1)` list items; `>` quotes; `[^n]:` notes; HTML `<table>`s; ``` fences (mermaid / code) and `$$`
   display maths; `![label: text]` images; the furniture tags <page_header>, <page_footer>, <page_number>,
   <watermark>).  Markup is stripped to plain text (bold / italic / underline / mark / sub / sup / escapes).
2. The plain texts are joined into one page text.  Both it and every Azure line are normalised the same way for
   matching only (diacritics and tatweel off, NFKC, digit sets to ASCII, lower case, whitespace collapsed), keeping an
   index back to the original characters.
3. Each Azure line is located by best fuzzy alignment (rapidfuzz partial_ratio_alignment, then both ends moved to the
   lowest Levenshtein distance).  Similarity = 1 - distance / line length.  A line is FOUND when similarity >= 0.65
   (lines of 4-11 normalised characters: >= 0.75; lines of <= 3: only an exact occurrence counts).  Lines under 12
   characters match exact occurrences only on word boundaries, and prefer an occurrence that is a whole block on its
   own (a page number in its tag).  Numeric lines (digits and signs only) also match 1-3 tokens with the same digits
   and the same signs wherever the signs stand.  Short lines and lines that occur more than once are placed next to
   the line before them (by Azure line number) or else the next confidently found line.
4. A found line belongs to the block holding most of its aligned span.  Pieces = blocks in the answer's order.
"""
from __future__ import annotations

import html
import html.parser
import json
import os
import re
import sys
import unicodedata

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

X = "/home/appuser/inkscript/experiments"
E = f"{X}/101_qwen_base_exam"
P97 = f"{X}/97_extraction_evals"
sys.path.insert(0, P97)
from common97 import NO_BLOCK  # noqa: E402

MODEL_DIR = os.environ.get("EXP101_MODEL") or f"{E}/out/model/4B"
NOT_TEXT = "(not-text)"
FOUND_SIM = 0.65          # chosen on the self-test (0.5 let 8% of deliberately dropped lines match other text)
SHORT = 12
SHORT_SIM = 0.75           # lines of 4-11 normalised characters

KIND_TO_KEY = {
    "heading": "heading", "paragraph": "paragraph", "list": "list-item", "quote": "quote", "table": "table",
    "figure": "figure", "equation": "equation", "page_header": "running-head", "page_footer": "running-head",
    "page_number": "page-number", "watermark": "other", "footnote": "footnote", "code": "other",
}
# key roles the Markdown format has a name for (P1 'restricted')
# (footnote is mapped when the answer uses `[^n]:`, but the card's prompt gives no footnote syntax: not counted here)
EXPRESSIBLE = {"heading", "paragraph", "list-item", "quote", "table", "figure", "equation", "running-head",
               "page-number"}
AR = re.compile(r"[؀-ۿ]")


# ================================================================================================ the answer
def strip_fence(text: str) -> str:
    """The outer ```markdown fence off.  The card's own regex (r"```markdown\n(.*?)(?:\n```|$)") stops at the first
    inner fence, so an answer holding a ```mermaid block lost everything after it; fixed 2026-11-24 after the first
    exam scoring (it cut 0840-000-014-006 p10 short): the body runs to a closing fence at the very end, or to the end."""
    t = text or ""
    m = re.search(r"```markdown\n", t)
    if not m:
        return t
    body = t[m.end():]
    return re.sub(r"\n```\s*$", "", body)


# Diagnostic only (added 2026-11-25 after the plain models' exam output was seen; disclosed in the README): the plain
# models do not keep the output contract.  The 4B never wrote an HTML table, but GFM pipe tables (| a | b | over a
# |---| row); the 9B wrote 79 of 214 pages as a whole HTML page in a ```html fence (<p>, <h2>, <table>), which the
# contract reading takes as one code block.  With EXP101_LENIENT=1 (a) such an HTML page is turned into Markdown
# (<h1>-<h6> -> # lines, <p>/<div> -> paragraphs, <li> -> list items, <table> kept, other tags dropped) and (b) pipe
# tables are turned into HTML tables (rows above the delimiter row = header rows), before parsing, so READING and
# STRUCTURE can be scored apart from FOLLOWING THE FORMAT.  Off by default: the main scorecard keeps the contract.
LENIENT = os.environ.get("EXP101_LENIENT") == "1"
PIPE_TABLES = LENIENT          # name kept for pictures101
_PIPE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_PIPE_DELIM = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def _pipe_cells(ln: str) -> list[str]:
    t = ln.strip()
    t = t[1:] if t.startswith("|") else t
    t = t[:-1] if t.endswith("|") else t
    return [c.strip() for c in re.split(r"(?<!\\)\|", t)]


def pipe_tables_to_html(md: str) -> str:
    lines, out, i = md.split("\n"), [], 0
    while i < len(lines):
        if _PIPE_ROW.match(lines[i]) or _PIPE_DELIM.match(lines[i]) and "|" in lines[i]:
            j = i
            while j < len(lines) and (_PIPE_ROW.match(lines[j]) or (_PIPE_DELIM.match(lines[j]) and "|" in lines[j])):
                j += 1
            run = lines[i:j]
            d = next((k for k, ln in enumerate(run) if _PIPE_DELIM.match(ln)), None)
            if d is not None and len(run) >= 2:
                head = run[:d]
                body = [ln for ln in run[d + 1:] if not _PIPE_DELIM.match(ln)]
                h = "".join("<tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in _pipe_cells(r)) + "</tr>" for r in head)
                b = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in _pipe_cells(r)) + "</tr>" for r in body)
                out.append("<table>" + (f"<thead>{h}</thead>" if h else "") + f"<tbody>{b}</tbody></table>")
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


_HTML_FENCE = re.compile(r"```html\s*\n(.*?)(?:\n```\s*$|$)", re.S)


def html_page_to_md(raw: str) -> str | None:
    """A whole-page HTML answer (```html fence, or <html>/<body> outside any ```markdown fence) -> Markdown; else None."""
    t = raw or ""
    if "```markdown" in t:
        return None
    m = _HTML_FENCE.search(t)
    body = m.group(1) if m else (t if re.search(r"<(html|body)\b", t, re.I) else None)
    if body is None:
        return None
    keep, k = [], 0

    def stash(mm):
        keep.append(mm.group(0))
        return f"\n\n@@TABLE{len(keep) - 1}@@\n\n"
    body = re.sub(r"<table\b.*?</table>", stash, body, flags=re.S | re.I)
    body = re.sub(r"<h([1-6])\b[^>]*>(.*?)</h\1>", lambda mm: "\n\n" + "#" * int(mm.group(1)) + " " + " ".join(mm.group(2).split()) + "\n\n", body, flags=re.S | re.I)
    body = re.sub(r"<li\b[^>]*>(.*?)</li>", lambda mm: "\n- " + " ".join(mm.group(1).split()) + "\n", body, flags=re.S | re.I)
    body = re.sub(r"<(p|div)\b[^>]*>(.*?)</\1>", lambda mm: "\n\n" + " ".join(mm.group(2).split()) + "\n\n", body, flags=re.S | re.I)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"</?(?!page_header|page_footer|page_number|watermark)[a-zA-Z][^>]*>", "", body)
    body = html.unescape(body)
    body = re.sub(r"@@TABLE(\d+)@@", lambda mm: keep[int(mm.group(1))], body)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def load_answer(set_: str, stem: str, page: int) -> dict | None:
    f = f"{MODEL_DIR}/{set_}/{stem}_p{page:03d}.json"
    return json.load(open(f)) if os.path.exists(f) else None


_TAG = re.compile(r"</?(?:u|mark|sub|sup|b|i|em|strong|span|small|big|font|s|del|ins)\b[^>]*>", re.I)


def plain(s: str, cell: bool = False) -> str:
    """Markup off, printed characters kept."""
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    s = _TAG.sub("", s)
    s = re.sub(r"<[^>]+>", " ", s) if cell else s
    if not cell:
        s = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"\2", s)
        s = re.sub(r"(?<![\*\w\\])\*(?=[^\s*])(.+?)(?<=[^\s*\\])\*(?![\*\w])", r"\1", s)
        s = re.sub(r"~~\s*(.+?)\s*~~", r"\1", s)
        s = re.sub(r"!\[(?:[a-z]+:\s*)?([^\]]*)\]", r"\1", s)
        s = re.sub(r"\$\$?(.+?)\$\$?", r"\1", s)
    else:
        s = re.sub(r"^\s*\*\*(.+)\*\*\s*$", r"\1", s) if not re.fullmatch(r"\s*\*+\s*", s) else s
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|<>~$])", r"\1", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


class _TableParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.cur, self.cell, self.in_thead = [], None, None, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "thead":
            self.in_thead = True
        elif tag == "tr":
            self.cur = dict(cells=[], thead=self.in_thead)
        elif tag in ("td", "th"):
            if self.cur is None:
                self.cur = dict(cells=[], thead=self.in_thead)
            self.cell = dict(th=tag == "th", text=[], cs=_int(a.get("colspan")), rs=_int(a.get("rowspan")))
        elif tag == "br" and self.cell is not None:
            self.cell["text"].append(" ")

    def handle_endtag(self, tag):
        if tag == "thead":
            self.in_thead = False
        elif tag in ("td", "th") and self.cell is not None:
            self.cur["cells"].append(self.cell)
            self.cell = None
        elif tag == "tr" and self.cur is not None:
            self.rows.append(self.cur)
            self.cur = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"].append(data)


def _int(x):
    try:
        return max(1, int(str(x).strip()))
    except (TypeError, ValueError):
        return 1


def parse_table(h: str) -> dict:
    """HTML table -> grid (rowspan / colspan filled: text in one position, '' in the rest; which position is decided
    later, once the column direction is known), header rows (thead rows, else leading all-<th> rows)."""
    p = _TableParser()
    try:
        p.feed(h)
        p.close()
    except Exception:  # noqa: BLE001
        pass
    if p.cur and p.cur["cells"]:
        p.rows.append(p.cur)
    grid, spans, taken = [], [], {}
    for r, row in enumerate(p.rows):
        c = 0
        line = {}
        for cell in row["cells"]:
            while (r, c) in taken:
                c += 1
            txt = plain("".join(cell["text"]), cell=True)
            spans.append(dict(r=r, c=c, rs=cell["rs"], cs=cell["cs"], text=txt))
            for dr in range(cell["rs"]):
                for dc in range(cell["cs"]):
                    taken[(r + dr, c + dc)] = len(spans) - 1
            c += cell["cs"]
    nr = max([k[0] for k in taken] + [-1]) + 1
    nc = max([k[1] for k in taken] + [-1]) + 1
    owner = [[taken.get((r, c)) for c in range(nc)] for r in range(nr)]
    thead = sum(1 for row in p.rows if row["thead"])
    if not thead:
        for row in p.rows:
            if row["cells"] and all(x["th"] for x in row["cells"]):
                thead += 1
            else:
                break
    return dict(owner=owner, spans=spans, n_rows=nr, n_cols=nc, n_header_rows=thead,
                text=" ".join(s["text"] for s in spans if s["text"]))


def fill_grid(t: dict, merged_at_end: bool) -> list[list[str]]:
    """Merged cells: text in the span's first row and its first column in the grid's own order, or its last column
    (merged_at_end: an Arabic table written left to right, so that after mirroring the text sits in the rightmost
    position, as the key types it)."""
    g = [["" for _ in range(t["n_cols"])] for _ in range(t["n_rows"])]
    for i, s in enumerate(t["spans"]):
        c = s["c"] + (s["cs"] - 1 if merged_at_end else 0)
        if s["r"] < t["n_rows"] and c < t["n_cols"]:
            g[s["r"]][c] = s["text"]
    return g


_FURN = re.compile(r"<(page_header|page_footer|page_number|watermark)>(.*?)</\1>", re.S)
_BLOCKY = re.compile(r"<table\b.*?</table>|```.*?(?:```|$)|\$\$.*?\$\$", re.S | re.I)


def parse_md(md: str) -> list[dict]:
    """-> blocks [{kind, text, raw, level?, table?}] in the answer's order."""
    out = []
    pos = 0
    tokens = []
    # furniture and block constructs first, in text order
    spans = []
    for m in _FURN.finditer(md):
        spans.append((m.start(), m.end(), "furn", m))
    for m in _BLOCKY.finditer(md):
        if not any(a <= m.start() < b for a, b, _, _ in spans):
            spans.append((m.start(), m.end(), "blocky", m))
    spans.sort()
    for a, b, kind, m in spans:
        if a < pos:
            continue
        tokens.append(("md", md[pos:a]))
        tokens.append((kind, m))
        pos = b
    tokens.append(("md", md[pos:]))
    for kind, x in tokens:
        if kind == "md":
            out += _md_blocks(x)
        elif kind == "furn":
            tag, inner = x.group(1), x.group(2)
            nums = list(re.finditer(r"<page_number>(.*?)</page_number>", inner, re.S))
            rest = re.sub(r"<page_number>.*?</page_number>", " ", inner, flags=re.S)
            if tag == "page_number":
                out.append(dict(kind="page_number", text=plain(inner), raw=x.group(0)))
                continue
            sub = []
            for b in _md_blocks(_BLOCKY.sub(lambda m: plain(m.group(0), cell=True), rest)):
                sub.append(b["text"])
            if any(sub):
                out.append(dict(kind=tag, text=" ".join(t for t in sub if t), raw=x.group(0)))
            for n in nums:
                out.append(dict(kind="page_number", text=plain(n.group(1)), raw=n.group(0)))
        else:
            s = x.group(0)
            if s.lower().startswith("<table"):
                t = parse_table(s)
                out.append(dict(kind="table", text=t["text"], raw=s, table=t))
            elif s.startswith("```"):
                body = re.sub(r"^```[^\n]*\n?|```$", "", s)
                lang = re.match(r"```(\w*)", s).group(1)
                txt = " ".join(re.findall(r"[\[\(\{\"]([^\]\)\}\"]+)[\]\)\}\"]", body)) if lang == "mermaid" else body
                out.append(dict(kind="figure" if lang == "mermaid" else "code", text=plain(txt, cell=True), raw=s))
            else:
                out.append(dict(kind="equation", text=plain(s.strip("$"), cell=True), raw=s))
    return [b for b in out if b["text"] or b["kind"] == "table"]


_LIST = re.compile(r"^\s{0,3}(?:\\\*|[*+\-]|\d{1,9}[.)])\s+")
_HEAD = re.compile(r"^\s{0,3}(#{1,6})\s+")


def _md_blocks(md: str) -> list[dict]:
    out, cur = [], None

    def flush():
        nonlocal cur
        if cur and cur["lines"]:
            raw = "\n".join(cur["lines"])
            txt = raw
            if cur["kind"] == "list":
                txt = _LIST.sub(lambda m: m.group(0) if re.match(r"\s*\d", m.group(0)) else "", txt, count=1)
                txt = re.sub(r"^\s*(\d{1,9}[.)])\s+", r"\1 ", txt)
            elif cur["kind"] == "quote":
                txt = re.sub(r"^\s*>\s?", "", txt, flags=re.M)
            elif cur["kind"] == "footnote":
                txt = re.sub(r"^\[\^([^\]]+)\]:\s*", r"\1 ", txt)
            out.append(dict(kind=cur["kind"], text=plain(txt), raw=raw, level=cur.get("level"),
                            note_label=cur.get("note_label")))
        cur = None

    for ln in md.split("\n"):
        if not ln.strip():
            flush()
            continue
        h = _HEAD.match(ln)
        if h:
            flush()
            out.append(dict(kind="heading", text=plain(ln[h.end():].rstrip("# ")), raw=ln, level=len(h.group(1))))
            continue
        if re.match(r"^\s*>", ln):
            if not cur or cur["kind"] != "quote":
                flush()
                cur = dict(kind="quote", lines=[])
            cur["lines"].append(ln)
            continue
        fn = re.match(r"^\[\^([^\]]+)\]:", ln)
        if fn:
            flush()
            cur = dict(kind="footnote", lines=[ln], note_label=fn.group(1))
            continue
        if _LIST.match(ln) and not re.match(r"^\s*([*\-_])(\s*\1){2,}\s*$", ln):
            flush()
            cur = dict(kind="list", lines=[ln])
            continue
        if re.match(r"^\s*([*\-_])(\s*\1){2,}\s*$", ln):        # thematic break
            flush()
            continue
        if cur is None:
            cur = dict(kind="paragraph", lines=[])
        cur["lines"].append(ln)
    flush()
    for b in out:                                                 # an image reference on its own is a figure
        if b["kind"] == "paragraph" and re.fullmatch(r"\s*!\[[^\]]*\]\s*", b["raw"]):
            b["kind"] = "figure"
    return out


# ================================================================================================ normalising
_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def norm_map(s: str):
    """-> (normalised string, index of each normalised char in s).  For matching only."""
    out, idx = [], []
    for i, ch in enumerate(s or ""):
        if ch == "ـ" or unicodedata.category(ch) == "Mn":
            continue
        for c in unicodedata.normalize("NFKC", ch):
            if unicodedata.category(c) == "Mn":
                continue
            c = c.translate(_DIG).lower()
            if c.isspace():
                if out and out[-1] == " ":
                    continue
                c = " "
            out.append(c)
            idx.append(i)
    return "".join(out), idx


def nrm(s: str) -> str:
    return norm_map(s)[0].strip()


# ================================================================================================ the page view
def _locate(q: str, T: str, lo: int = 0, hi: int | None = None):
    """Best approximate occurrence of q in T[lo:hi] -> (start, end, distance) in T coordinates."""
    hi = len(T) if hi is None else hi
    W = T[lo:hi]
    if not q or not W:
        return None
    if len(q) >= len(W):
        return (lo, hi, Levenshtein.distance(q, W))
    al = fuzz.partial_ratio_alignment(q, W)
    if al is None:
        return None
    s, e = al.dest_start, al.dest_end
    d = Levenshtein.distance(q, W[s:e])
    for _ in range(2):                       # move each end to the lowest distance (coordinate descent)
        best = (d, s)
        for s2 in range(max(0, s - 10), min(e, s + 11)):
            v = Levenshtein.distance(q, W[s2:e])
            if v < best[0] or (v == best[0] and abs(s2 - s) < abs(best[1] - s)):
                best = (v, s2)
        d, s = best
        best = (d, e)
        for e2 in range(max(s + 1, e - 10), min(len(W), e + 10) + 1):
            v = Levenshtein.distance(q, W[s:e2])
            if v < best[0] or (v == best[0] and abs(e2 - e) < abs(best[1] - e)):
                best = (v, e2)
        d, e = best
    while s < e and W[s] == " ":
        s += 1
    while e > s and W[e - 1] == " ":
        e -= 1
    return (lo + s, lo + e, Levenshtein.distance(q, W[s:e]))


def _occurrences(q, T, whole=False):
    """Exact occurrences of q in T; whole=True: only where q starts and ends on a word boundary."""
    out, k = [], T.find(q)
    while k >= 0 and len(out) < 200:
        e = k + len(q)
        if not whole or ((k == 0 or not T[k - 1].isalnum() or not q[0].isalnum())
                         and (e == len(T) or not T[e].isalnum() or not q[-1].isalnum())):
            out.append(k)
        k = T.find(q, k + 1)
    return out


_NUMLIKE = re.compile(r"[\d\s.,،٫٬\-−–+*%٪()\[\]±<>/]+")


def _canon_num(s):
    """A numeric line or cell: its digits (decimal marks unified) and its signs as a set, positions ignored
    (Azure, the keys and the model type signs and stars on different sides of the number)."""
    s = re.sub(r"(?<=\d)[,،٫٬.](?=\d)", ".", s.replace(" ", ""))
    return re.sub(r"[^\d.]", "", s) + "|" + "".join(sorted(re.findall(r"[\-−–+*%٪()\[\]±<>]", s)))


def _numeric_occurrences(q, T):
    """Windows of 1-3 whitespace tokens of T whose numeric canon equals q's -> [(start, end)]."""
    want = _canon_num(q)
    toks = [(m.start(), m.end()) for m in re.finditer(r"\S+", T)]
    out = []
    for i in range(len(toks)):
        for n in (1, 2, 3):
            if i + n > len(toks):
                break
            a, z = toks[i][0], toks[i + n - 1][1]
            w = T[a:z]
            if re.search(r"\d", w) and _NUMLIKE.fullmatch(w) and _canon_num(w) == want:
                out.append((a, z))
    return out


class PageView:
    """One page: the answer's blocks, its page text, and where every Azure line sits in it."""

    def __init__(self, raw: str, azure_lines: list[dict], texts: dict | None = None):
        self.md = strip_fence(raw)
        if PIPE_TABLES:
            self.md = pipe_tables_to_html(html_page_to_md(raw) or self.md)
        self.blocks = parse_md(self.md)
        parts, pos = [], 0
        for b in self.blocks:
            b["start"] = pos
            parts.append(b["text"])
            pos += len(b["text"])
            b["end"] = pos
            parts.append("\n\n")
            pos += 2
        self.T = "".join(parts)
        self.NT, self.idx = norm_map(self.T)
        self.nblock = self._nblock_index()
        self.az = {l["line"]: l for l in azure_lines}
        self.texts = {l["line"]: (texts or {}).get(l["line"], l["text"]) for l in azure_lines}
        self.lines = {}
        self._align_all()

    def _nblock_index(self):
        """block of every normalised character (None for separators)."""
        bl = [None] * len(self.NT)
        bi = 0
        for k, i in enumerate(self.idx):
            while bi < len(self.blocks) and i >= self.blocks[bi]["end"] + 2:
                bi += 1
            if bi < len(self.blocks) and self.blocks[bi]["start"] <= i < self.blocks[bi]["end"]:
                bl[k] = bi
        return bl

    def block_of(self, s, e):
        votes = {}
        for k in range(s, e):
            b = self.nblock[k]
            if b is not None:
                votes[b] = votes.get(b, 0) + 1
        return max(votes, key=votes.get) if votes else None

    def align(self, text: str, near: int | None = None) -> dict:
        q = nrm(text)
        if not q:
            return dict(q=q, found=False, sim=0.0, span=None, block=None)
        cands = []
        occ = _occurrences(q, self.NT, whole=len(q) < SHORT)
        for k in occ:
            cands.append((k, k + len(q), 0))
        if re.search(r"\d", q) and _NUMLIKE.fullmatch(q):
            num = _numeric_occurrences(q, self.NT)
            cands += [(a, z, 0) for a, z in num if (a, z) not in {(c[0], c[1]) for c in cands}]
            occ = occ or [a for a, _ in num]
        if len(q) > 3 and (not occ or len(occ) == 1 and len(q) >= SHORT):
            r = _locate(q, self.NT)
            if r:
                cands.append(r)
        if len(q) > 3 and not occ and near is not None:     # a short or repeated line: also look near its neighbours
            r = _locate(q, self.NT, max(0, near - 400), min(len(self.NT), near + 400))
            if r:
                cands.append(r)
        if not cands:
            return dict(q=q, found=False, sim=0.0, span=None, block=None)
        def whole_block(c):              # a short line that is a whole block on its own (a page number in its tag)
            b = self.block_of(c[0], c[1])
            return b is not None and nrm(self.blocks[b]["text"]) == self.NT[c[0]:c[1]].strip()

        def key(c):
            # similarity, less a distance penalty when the line has an anchor (0.5 x distance / page length), plus a
            # small bonus for a short line that is a whole block on its own
            sim = 1 - c[2] / len(q)
            pen = 0.5 * abs(c[0] - near) / max(1, len(self.NT)) if near is not None else 0.0
            bonus = 0.05 if len(q) < SHORT and whole_block(c) else 0.0
            return -(sim - pen + bonus)
        best = min(cands, key=key)
        sim = max(0.0, 1 - best[2] / len(q))
        found = (sim >= FOUND_SIM if len(q) >= SHORT else sim >= SHORT_SIM) if len(q) > 3 else best[2] == 0
        return dict(q=q, found=found, sim=round(sim, 4), span=(best[0], best[1]) if found else None,
                    block=self.block_of(best[0], best[1]) if found else None, n_occ=len(occ), _best=best)

    def _align_all(self):
        order = sorted(self.az)
        # pass 1: long lines that occur at most once
        for ln in order:
            q = nrm(self.texts[ln])
            if len(q) >= SHORT and len(_occurrences(q, self.NT)) <= 1:
                self.lines[ln] = self.align(self.texts[ln])
        conf = [ln for ln in order if ln in self.lines and self.lines[ln]["found"]]
        # pass 2: the rest, in line order, anchored on the line just before (if it was placed) or else on the next
        # confidently found line: a table's cells are numbered one after another, so they stay in their table
        last = None
        for ln in order:
            if ln in self.lines:
                if self.lines[ln]["found"]:
                    last = ln
                continue
            nxt = [x for x in conf if x > ln][:1]
            if last is not None:
                near = self.lines[last]["span"][1]
            elif nxt:
                near = self.lines[nxt[0]]["span"][0]
            else:
                near = None
            self.lines[ln] = self.align(self.texts[ln], near=near)
            if self.lines[ln]["found"]:
                last = ln

    # ---------------------------------------------------------------------------------------------- texts
    def original(self, s: int, e: int, snap: bool = True) -> str:
        """The answer's original text for normalised span [s, e), widened to whole words, not across blocks."""
        b = self.block_of(s, e)                          # keep to the block holding most of the span
        while s < e and self.nblock[s] != b:
            s += 1
        while e > s and self.nblock[e - 1] != b:
            e -= 1
        if s >= e:
            return ""
        a, z = self.idx[s], self.idx[e - 1] + 1
        if snap:
            b0 = self.nblock[s]
            lo = self.blocks[b0]["start"] if b0 is not None else 0
            b1 = self.nblock[e - 1]
            hi = self.blocks[b1]["end"] if b1 is not None else len(self.T)
            n = 0
            while a > lo and not self.T[a - 1].isspace() and n < 12:
                a -= 1
                n += 1
            n = 0
            while z < hi and not self.T[z].isspace() and n < 12:
                z += 1
                n += 1
        return re.sub(r"\s+", " ", self.T[a:z].replace("\n\n", " ")).strip()

    def line_text(self, text: str, near_line: int | None = None) -> dict:
        """Find a (truth) line in the answer -> {found, sim, text (original, word-snapped)}."""
        near = None
        if near_line is not None and near_line in self.lines and self.lines[near_line].get("span"):
            near = self.lines[near_line]["span"][0]
        r = self.align(text, near=near)
        return dict(found=r["found"], sim=r["sim"], text=self.original(*r["span"]) if r["found"] else "",
                    block=r["block"])

    def line_block(self):
        return {ln: v["block"] for ln, v in self.lines.items() if v["found"] and v["block"] is not None}


# ================================================================================================ key formats
def pred_page(stem: str, page: int, v: PageView) -> dict:
    lb = v.line_block()
    pieces = {}
    for ln in sorted(lb):
        b = lb[ln]
        role = KIND_TO_KEY.get(v.blocks[b]["kind"], "other")
        pieces.setdefault(b, dict(role=role, lines=[], _kind=v.blocks[b]["kind"], _block=b, unordered=False,
                                  note_label=v.blocks[b].get("note_label")))
        pieces[b]["lines"].append(ln)
    return dict(stem=stem, page=page, columns=None, pieces=[pieces[b] for b in sorted(pieces)], note_calls=[],
                azure_lines_that_are_not_text=[], unsure=False)


def _table_direction(v: PageView, b: int, t: dict, lines: list[int]):
    """'rtl' when the grid's first column is the rightmost on the page: each spanning-free cell is matched to the
    table's Azure line it equals best (normalised), and the x-centres along each row vote."""
    cand = [(ln, nrm(v.texts[ln]), v.az[ln]) for ln in lines]
    votes = [0, 0]
    for r in range(t["n_rows"]):
        xs = []
        for c in range(t["n_cols"]):
            o = t["owner"][r][c]
            if o is None:
                continue
            s = t["spans"][o]
            if s["cs"] != 1 or s["c"] != c or s["r"] != r:
                continue
            q = nrm(s["text"])
            if len(q) < 1:
                continue
            numeric = bool(re.search(r"\d", q) and _NUMLIKE.fullmatch(q))

            def fit(x):
                if numeric and _NUMLIKE.fullmatch(x[1] or "-") and _canon_num(x[1]) == _canon_num(q):
                    return 100.0
                r = fuzz.ratio(q, x[1])
                if len(x[1]) >= 6 and len(x[1]) < len(q):        # a cell printed over two Azure lines
                    r = max(r, fuzz.partial_ratio(x[1], q) - 5)
                return r
            best = max(cand, key=fit, default=None)
            if best and fit(best) >= 80:
                xs.append(best[2]["x"] + best[2]["w"] / 2)
        for a, z in zip(xs, xs[1:]):
            if a > z:
                votes[0] += 1
            elif z > a:
                votes[1] += 1
    if votes[0] == votes[1]:
        # no box votes (a whole printed row is one Azure line): the order in which the row's cells stand inside one
        # Azure line's text (reading order for an Arabic line) against the grid's order
        for r in range(t["n_rows"]):
            cells = [nrm(t["spans"][o]["text"]) for o in dict.fromkeys(x for x in t["owner"][r] if x is not None)]
            cells = [c for c in cells if len(c) >= 3 and not _NUMLIKE.fullmatch(c)]
            if len(cells) < 2:
                continue
            for ln, q in ((l, nrm(v.texts[l])) for l in v.az):
                pos = [q.find(c) for c in cells]
                pos = [p_ for p_ in pos if p_ >= 0]
                if len(pos) >= 2 and len(set(pos)) == len(pos):
                    inc = sum(1 for a, z in zip(pos, pos[1:]) if z > a)
                    dec = len(pos) - 1 - inc
                    rtl_line = len(AR.findall(q)) > len(re.findall(r"[a-z]", q))
                    if inc != dec:
                        reading = inc > dec
                        votes[0 if reading == rtl_line else 1] += 1
                    break
    if votes[0] == votes[1]:
        return "rtl" if len(AR.findall(t["text"])) > len(re.findall(r"[A-Za-z]", t["text"])) else "ltr", votes
    return ("rtl" if votes[0] > votes[1] else "ltr"), votes


_CAP = re.compile(r"^\s*(?:ال)?(?:جدول|شكل|table|figure|fig\.)\s*(?:رقم\s*)?[\(\[]?\s*([0-9٠-٩]+)", re.I)


def pred_tab(stem: str, page: int, v: PageView) -> dict:
    lb = v.line_block()
    tables = []
    for b, blk in enumerate(v.blocks):
        if blk["kind"] != "table":
            continue
        t = blk["table"]
        ln = sorted(l for l, bb in lb.items() if bb == b)
        direction, votes = _table_direction(v, b, t, ln)
        arabic = len(AR.findall(t["text"])) > len(re.findall(r"[A-Za-z]", t["text"]))
        grid = fill_grid(t, merged_at_end=(direction == "ltr" and arabic))
        cap = num = None
        for nb in (b - 1, b + 1):            # a caption written just before (or after) the table
            if 0 <= nb < len(v.blocks) and v.blocks[nb]["kind"] in ("paragraph", "heading"):
                m = _CAP.match(v.blocks[nb]["text"])
                if m and re.match(r"\s*(?:ال)?(?:جدول|table)", v.blocks[nb]["text"], re.I):
                    cap, num = v.blocks[nb]["text"], m.group(1)
                    break
        tables.append(dict(lines_first_last=[ln[0], ln[-1]] if ln else None, lines=ln, caption=cap, number_printed=num,
                           n_rows=t["n_rows"], n_cols=t["n_cols"], n_header_rows=t["n_header_rows"],
                           is_continuation_of_previous_page=False, continues_on_next_page=False, cells=grid,
                           direction=direction, _direction_votes=votes, _block=b))
    tables.sort(key=lambda t: (t["lines_first_last"] or [10 ** 6])[0])
    figs = [dict(kind="figure", caption=None, number_printed=None) for x in v.blocks if x["kind"] == "figure"]
    return dict(stem=stem, page=page, tables=tables, figures=figs, unsure=False)


def pred_refs(stem: str, page: int, v: PageView, kinds=("list", "paragraph")) -> dict:
    lb = v.line_block()
    refs = []
    for b, blk in enumerate(v.blocks):
        if blk["kind"] not in kinds:
            continue
        ln = sorted(l for l, bb in lb.items() if bb == b)
        if ln:
            refs.append(dict(lines=ln, starts_on_previous_page=False, continues_on_next_page=False, _kind=blk["kind"]))
    return dict(stem=stem, page=page, references=refs, unsure=False)
