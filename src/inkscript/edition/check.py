"""Automatic checks of the finished editions (experiment 35), run on the files a reader gets, not on the
generator's strings.

    tokens(text) -> [str]                          the comparison key of each word (see below)
    words_once(ed, text, layout=False) -> dict     does every ALTO word the edition must carry appear exactly once?
    reading_order(expected, extracted, blocks=None) -> dict
                                                   in-order share (LCS) and inversions of neighbouring blocks
    text_of_html / text_of_epub / text_of_pdf / text_of_md / text_of_jsonl (path) -> str (pdf: [str] per page)
    check_article(ed, files) -> dict               every check on the editions present

**Tokens.** NFKC (a PDF's presentation forms and lam-alef ligature back to letters), no bidi controls or other
format characters, no combining marks (harakat, Quranic signs) or tatweel, one form of alef / ya / ta marbuta /
Persian kaf and ya, Western digits, case folded; then the runs of letters and the runs of digits. So "عاصم(٢)."
is [عاصم, 2] whether the page printed it as one word or three, and punctuation never decides a match. The same
function reads the ALTO words and the edition, so both sides are cut alike.

**Words once.** Expected = the ALTO words of the blocks the master puts in the article (`ed.ink_words()`: body,
notes, references, title, authors, rubric, front-matter blocks; furniture and stray blocks are left out by the
master itself); for the layout-faithful print, every ALTO word on the page, furniture included. The words of an
inline formula (TAGREFS kind.formula) are not expected as words: they are rendered as mathematics, and the
formula is counted instead. Allowed extras = what the edition adds that is not ink: the catalogue's front matter
(title, authors, journal, dates, keywords, abstracts, subjects), verse texts and their references, note labels,
and the edition's own labels (`extra=`). For each token: e expected, g in the edition, a allowed;
missing = max(0, e - g), duplicated = max(0, g - e - a) where e > 0, extra = g - a where e = 0.
Missing words are charged to the front blocks first (title, author, rubric: the reading editions print the
catalogue's title and the printed author string, which may differ from the ink), then to the rest; the title's
misses are reported apart (`missing_front`).
"""
from __future__ import annotations

import json
import re
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree, html as lhtml

from .model import Edition, plain

_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ی": "ي", "ک": "ك",
                       "ـ": None})
_TOK = re.compile(r"[^\W\d_]+|\d+")
FRONT_KINDS = ("title", "author", "rubric", "front")


def tokens(text: str) -> list[str]:
    t = unicodedata.normalize("NFKC", text or "")
    t = "".join(ch for ch in t if unicodedata.category(ch) not in ("Mn", "Me", "Cf"))
    t = t.translate(_FOLD).translate(_DIG).casefold()
    return _TOK.findall(t)


# ---------------------------------------------------------------------------------------------- expected and allowed

def expected(ed: Edition, layout: bool = False) -> list[tuple[str, str, str]]:
    """(token, block kind, word id) for every word the edition must carry, in page order."""
    out = []
    for n in sorted(ed.pages):
        for b in ed.pages[n].blocks:
            if not layout and b.kind in ("furniture", "stray"):
                continue
            for w in b.words:
                if w.math and not layout:
                    continue
                for t in tokens(w.text):
                    out.append((t, b.kind, w.id))
    return out


def allowed_extra(ed: Edition, extra: str | list = "") -> Counter:
    """Tokens a reading edition may add that are not ink."""
    f = ed.front
    parts = [f["title"], f["subtitle"], f["alt_title"], f["journal"], f["journal_en"], f["publisher"],
             f["publisher_loc"], f["year"], f["date"], f["volume"], f["issue"], f["fpage"], f["lpage"],
             str(f["page_count"] or ""), f["doi"], f["record"], f["article_id"], f["journal_id"], " ".join(f["issn"])]
    parts += [t["title"] + " " + t["subtitle"] for t in f["trans_titles"]]
    for a in f["authors"]:
        parts += [a["display"], a["name_ar"], a["name_en"], a["prefix"], a["printed"], a["collab"], a["role"]]
        parts += a["aff"]
    parts += [s["text"] for s in f["subjects"]]
    parts += [k for g in f["keywords"] for k in g["kwds"]]
    parts += [p for ab in f["abstracts"] for p in ab["paras"]]
    for v in ed.verses:
        parts += [v["ref"], v["verse"], v["note"]]
    for n in ed.nodes():
        _quran_titles(n.inl, parts)
        if n.kind == "formula":
            parts += [n.extra.get("tex", ""), n.extra.get("ink", ""), n.extra.get("label", "")]
        for r in _runs(n.inl):
            if r["t"] == "math":
                parts += [r.get("tex", ""), r.get("ink", "")]
    for note in ed.notes:
        parts.append(note.label)
    if isinstance(extra, str):
        extra = [extra]
    parts += list(extra)
    c = Counter()
    for p in parts:
        c.update(tokens(p or ""))
    return c


def _runs(inl):
    for r in inl:
        yield r
        if "inl" in r:
            yield from _runs(r["inl"])


def _quran_titles(inl, parts):
    for r in _runs(inl):
        if r["t"] == "quran":
            parts += [r.get("title", ""), r.get("href", "")]


# ---------------------------------------------------------------------------------------------- words once

def words_once(ed: Edition, text: str, layout: bool = False, extra="", examples: int = 12,
               skip_numbers: bool = False) -> dict:
    """skip_numbers: leave tokens made only of digits out of both sides (the one-column print renumbers notes
    1..N and numbers its own pages, so the printed note numbers cannot match there; reported as such)."""
    exp = expected(ed, layout)
    if skip_numbers:
        exp = [x for x in exp if not x[0].isdigit()]
    E = Counter(t for t, _, _ in exp)
    G = Counter(t for t in tokens(text) if not (skip_numbers and t.isdigit()))
    if layout:                                   # the layout print adds nothing but its own labels
        A = Counter(tokens(extra if isinstance(extra, str) else " ".join(extra)))
    else:
        A = allowed_extra(ed, extra)
    missing = {t: E[t] - G[t] for t in E if G[t] < E[t]}
    dup = {t: G[t] - E[t] - A[t] for t in E if G[t] > E[t] + A[t]}
    extra_ = {t: G[t] - A[t] for t in G if t not in E and G[t] > A[t]}
    # charge the misses to word instances: front blocks first, then the rest, last instances first
    left = dict(missing)
    by_kind, miss_words = Counter(), []
    for pref in (True, False):
        for t, kind, wid in reversed(exp):
            if left.get(t, 0) > 0 and ((kind in FRONT_KINDS) == pref):
                left[t] -= 1
                by_kind[kind] += 1
                miss_words.append((wid, t, kind))
    n_exp = sum(E.values())
    n_miss = sum(missing.values())
    n_front = sum(v for k, v in by_kind.items() if k in FRONT_KINDS)
    n_body = sum(1 for _, k, _ in exp if k not in FRONT_KINDS)
    return dict(
        expected=n_exp, found=n_exp - n_miss, missing=n_miss, missing_front=n_front,
        missing_body=n_miss - n_front, duplicated=sum(dup.values()), extra=sum(extra_.values()),
        share=round((n_exp - n_miss) / n_exp, 5) if n_exp else 1.0,
        share_body=round(1 - (n_miss - n_front) / n_body, 5) if n_body else 1.0,
        missing_by_kind=dict(by_kind),
        examples_missing=[dict(word=w, token=t, kind=k) for w, t, k in miss_words[:examples]],
        examples_duplicated=sorted(dup.items(), key=lambda x: -x[1])[:examples],
        examples_extra=sorted(extra_.items(), key=lambda x: -x[1])[:examples],
        exactly_once=n_miss == 0 and not dup)


# ---------------------------------------------------------------------------------------------- reading order

def lcs_len(a: list, b: list) -> int:
    """Length of the longest common subsequence (bit-parallel, Hyyrö 2004): O(len(b)) big-integer steps."""
    if not a or not b:
        return 0
    masks = {}
    for i, x in enumerate(a):
        masks[x] = masks.get(x, 0) | (1 << i)
    full = (1 << len(a)) - 1
    V = full                                   # V: bits still "unmatched" (complement form)
    for y in b:
        M = masks.get(y, 0)
        U = V & M
        V = ((V + U) | (V - U)) & full
    return len(a) - bin(V).count("1")


def reading_order(exp_tokens: list, got_tokens: list, blocks: list | None = None) -> dict:
    """How much of the expected token sequence comes out of the edition in the same order (LCS / expected), and,
    given the expected blocks (lists of tokens, in reading order), how many neighbouring blocks come out swapped:
    each block is placed by its first trigram that occurs exactly once in the extracted text."""
    lcs = lcs_len(exp_tokens, got_tokens)
    out = dict(expected=len(exp_tokens), extracted=len(got_tokens), in_order=lcs,
               share=round(lcs / len(exp_tokens), 5) if exp_tokens else 1.0)
    if blocks is not None:
        tri = Counter(tuple(got_tokens[i:i + 3]) for i in range(len(got_tokens) - 2))
        where = {}
        for i in range(len(got_tokens) - 2):
            k = tuple(got_tokens[i:i + 3])
            if tri[k] == 1:
                where[k] = i
        pos = []
        for b in blocks:
            p = next((where[tuple(b[i:i + 3])] for i in range(len(b) - 2) if tuple(b[i:i + 3]) in where), None)
            if p is not None:
                pos.append(p)
        inv = sum(1 for x, y in zip(pos, pos[1:]) if y < x)
        out.update(blocks=len(blocks), blocks_placed=len(pos), block_inversions=inv)
    return out


def order_expected(ed: Edition, page: int | None = None, layout: bool = False) -> list[list[str]]:
    """The blocks' tokens in the master's reading order: front blocks (rubric, title, authors), then the body,
    the references and the notes as the JATS has them (a reading edition), or, for the layout-faithful print,
    the same order restricted to one page. Furniture and stray blocks are not ordered."""
    seen, order = set(), []

    def add(bids):
        for bid in bids:
            if bid not in seen and bid in ed.blocks:
                seen.add(bid)
                order.append(bid)
    for kind in ("rubric", "title", "author", "front"):
        add([b.id for n in sorted(ed.pages) for b in ed.pages[n].blocks if b.kind == kind])
    for n in ed.body:
        add(n.blocks)
    for n in ed.refs:
        add(n.blocks)
    for note in ed.notes:
        for p in note.paras:
            add(p.blocks)
    out = []
    for bid in order:
        b = ed.blocks[bid]
        if page is not None and b.page != page:
            continue
        toks = [t for w in b.words if not w.math for t in tokens(w.text)]
        if toks:
            out.append(toks)
    return out


# ---------------------------------------------------------------------------------------------- extractors

_SKIP_CLASSES = re.compile(r"\b(clip|orig|original|scan|ui|nav|toolbar|colophon|about|noink|meta|facts|"
                           r"trustline|qref|badge|sr-only|npage|fnpage)\b")


def text_of_html(path) -> str:
    """The visible text of an edition's HTML: no script/style/template, nothing hidden, no element marked as
    interface (data-noink, aria-hidden, or a class such as clip/scan/ui/nav/colophon/about/meta). When the page
    marks its article (data-ink, <article>, <main>), only that is read."""
    root = lhtml.fromstring(Path(path).read_bytes())
    return _visible(root)


def _drop(el):
    """Remove an element but keep the text that follows it (its tail is the paragraph's text)."""
    p = el.getparent()
    if p is None:
        return
    if el.tail:
        prev = el.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or "") + el.tail
        else:
            p.text = (p.text or "") + el.tail
    p.remove(el)


def _visible(root) -> str:
    for bad in root.xpath("//script|//style|//template|//noscript|//head|//*[@hidden]|//*[@aria-hidden='true']"
                          "|//*[@data-noink]"):
        _drop(bad)
    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        cls = el.get("class") or ""
        if _SKIP_CLASSES.search(cls):
            _drop(el)
    scope = root.xpath("//*[@data-ink]") or root.xpath("//article") or root.xpath("//main") or [root]
    return "\n".join(" ".join(s.itertext()) for s in scope)


def text_of_epub(path) -> str:
    """The spine's XHTML documents in order (navigation documents left out)."""
    with zipfile.ZipFile(path) as z:
        cont = etree.fromstring(z.read("META-INF/container.xml"))
        opf_path = cont.xpath("//*[local-name()='rootfile']/@full-path")[0]
        opf = etree.fromstring(z.read(opf_path))
        base = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""
        items = {i.get("id"): i for i in opf.xpath("//*[local-name()='item']")}
        out = []
        for ref in opf.xpath("//*[local-name()='itemref']"):
            it = items.get(ref.get("idref"))
            if it is None or "nav" in (it.get("properties") or "") or ref.get("linear") == "no":
                continue
            data = z.read(base + it.get("href"))
            root = lhtml.document_fromstring(data)
            out.append(_visible(root))
        return "\n".join(out)


def text_of_pdf(path) -> list[str]:
    """Each page's text as Chrome's engine gives it back (pypdfium2, pinned 5.12.1): NFKC, no bidi controls."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(path))
    try:
        out = []
        for i in range(len(doc)):
            t = doc[i].get_textpage().get_text_range()
            out.append(re.sub(r"[‎‏‪-‮⁦-⁩]", "",
                              unicodedata.normalize("NFKC", t)))
        return out
    finally:
        doc.close()


def text_of_md(path) -> str:
    """Markdown as read: no YAML header, no footnote keys, link text without its address, no HTML tags."""
    s = Path(path).read_text(encoding="utf-8")
    if s.startswith("---\n"):
        end = s.find("\n---\n", 4)
        if end >= 0:
            s = s[end + 5:]
    s = re.sub(r"\[\^[^\]]+\]:?", " ", s)
    s = re.sub(r"\]\([^)]*\)", "] ", s)
    s = re.sub(r"(?<!\\)</?[A-Za-z][^<>]*>", " ", s)      # HTML tags, not an escaped \< in the text
    s = s.replace("\\", "")
    return s


def text_of_jsonl(path_or_line, field: str = "reading") -> str:
    """A record's text. field="reading" (default): what a dataset user reads of the article — the title, the
    authors as printed, the front matter kept as printed, then `text`; any other name reads that field alone."""
    p = Path(path_or_line) if not str(path_or_line).lstrip().startswith("{") else None
    lines = p.read_text(encoding="utf-8").splitlines() if p else [path_or_line]
    out = []
    for x in lines:
        if not x.strip():
            continue
        r = json.loads(x)
        if field != "reading":
            out.append(r.get(field) or "")
            continue
        out += [r.get("title") or "", r.get("subtitle") or ""]
        for a in r.get("authors", []):
            out += [a.get("printed") or a.get("name") or ""] + list(a.get("affiliation") or [])
        out += [f.get("text") or "" for f in r.get("front_printed", [])]
        out.append(r.get("text") or "")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------- one article

def check_article(ed: Edition, files: dict, extra=None) -> dict:
    """files: {"html": path, "epub": path, "layout_pdf": path, "onecol_pdf": path, "md": path, "jsonl": path}
    (any subset). extra: the edition's own label words — one string for all, or {edition key: string}; the
    Markdown's labels are added here. Returns per edition: words_once, and for the PDFs reading_order (per page
    for the layout-faithful one, whole article for the one-column one)."""
    from .data import labels_text
    out = {}
    for k, p in files.items():
        if not p or not Path(p).exists():
            continue
        ex = (extra.get(k, "") if isinstance(extra, dict) else extra) or ""
        if k in ("md", "html", "epub", "onecol_pdf"):           # the usual Arabic labels (المجلد، العدد...)
            ex = ex + " " + labels_text(ed)
        try:
            extra_ = ex
            if k == "html":
                out[k] = dict(words=words_once(ed, text_of_html(p), extra=extra_))
            elif k == "epub":
                out[k] = dict(words=words_once(ed, text_of_epub(p), extra=extra_))
            elif k == "md":
                out[k] = dict(words=words_once(ed, text_of_md(p), extra=extra_))
            elif k == "jsonl":
                out[k] = dict(words=words_once(ed, text_of_jsonl(p), extra=extra_))
            elif k == "layout_pdf":
                pages = text_of_pdf(p)
                r = dict(words=words_once(ed, "\n".join(pages), layout=True, extra=extra_))
                tot = dict(expected=0, in_order=0, blocks=0, blocks_placed=0, block_inversions=0)
                per = []
                for i, pn in enumerate(sorted(ed.pages)):
                    blocks = order_expected(ed, page=pn)
                    got = tokens(pages[i]) if i < len(pages) else []
                    o = reading_order([t for b in blocks for t in b], got, blocks)
                    per.append(dict(page=pn, **o))
                    for kk in tot:
                        tot[kk] += o.get(kk, 0)
                tot["share"] = round(tot["in_order"] / tot["expected"], 5) if tot["expected"] else 1.0
                r["order"] = tot
                r["order_pages"] = per
                out[k] = r
            elif k == "onecol_pdf":
                pages = text_of_pdf(p)
                text = "\n".join(pages)
                blocks = order_expected(ed)
                from .printpdf import ONECOL_LABELS
                run_head = (" " + ed.front.get("journal", "")) * len(pages) + " " + ONECOL_LABELS
                out[k] = dict(words=words_once(ed, text, extra=extra_ + run_head, skip_numbers=True),
                              numbers_skipped=True,
                              order=reading_order([t for b in blocks for t in b], tokens(text), blocks))
            n_f = formulas_expected(ed)
            if n_f and k in ("html", "epub", "md"):
                out[k]["formulas"] = dict(expected=n_f, found=formulas_found(p, k))
        except Exception as e:                       # a broken file is a finding, not a crash of the check
            out[k] = dict(error=f"{type(e).__name__}: {e}")
    return out


def formulas_expected(ed: Edition) -> int:
    n = 0
    for node in ed.nodes():
        n += node.kind == "formula"
        n += sum(1 for r in _runs(node.inl) if r["t"] == "math")
    return n


def formulas_found(path, kind: str) -> int:
    """MathML <math> elements in HTML/EPUB; $$…$$ and $…$ formulas in Markdown."""
    if kind == "html":
        return len(re.findall(r"<math[\s>]", Path(path).read_text(encoding="utf-8", errors="replace")))
    if kind == "epub":
        with zipfile.ZipFile(path) as z:
            return sum(len(re.findall(r"<math[\s>]", z.read(n).decode("utf-8", "replace")))
                       for n in z.namelist() if n.endswith((".xhtml", ".html")) and "nav" not in n)
    s = text_of_md_raw(path)
    disp = len(re.findall(r"\$\$.+?\$\$", s, re.S))
    s = re.sub(r"\$\$.+?\$\$", " ", s, flags=re.S)
    return disp + len(re.findall(r"(?<!\\)\$[^$\n]+?(?<!\\)\$", s))


def text_of_md_raw(path) -> str:
    s = Path(path).read_text(encoding="utf-8")
    if s.startswith("---\n"):
        end = s.find("\n---\n", 4)
        if end >= 0:
            s = s[end + 5:]
    return s
