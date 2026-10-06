"""A first "document as data" file: TEI P5 beside the PDF, with a trust mark on every word.

(Copied from experiment 20; experiment 22 adds: every word gets #trust.verified / #trust.agreed / #trust.flagged, a
flagged word also points at its reasons, #why.*, from flag.py; punctuation alone is not assessed; and the build
returns out/trust/<stem>.json for the report and the _trust.pdf.)

    python tei.py STEM [STEM ...]          -> out/tei/<stem>.tei.xml

What goes in (see README for what is still empty):
  teiHeader   title/authors from Gemini's title file (<id>.gemini.title.json,
              out/titles/), the Mandumah id, journal name guessed from the
              running heads, who did what (Azure, Gemini, inkscript, Tanzil),
              the trust taxonomy, and the two link prefixes (glyph:, quran:).
  facsimile   one <surface> per page and one <zone> per Azure word: its
              polygon in 1/300 inch (= pixels of the 300-dpi scan).
  text/body   Azure's paragraphs in reading order, given roles: Azure's own
              role when it has one (prebuilt-read gives almost none), otherwise
              position rules (resp="#rules"): page number, running head/foot,
              footnote, section heading. Every word is a <w> with its zone,
              Azure's confidence, the glyph(s) it is drawn with in our PDF
              (corresp="glyph:N" = shapes.json placements[N]) and a trust mark.
  standOff    one <annotation> per Quran quotation (part 1): the words it
              covers, sura:verse, the verse, each word that differs.
"""
from __future__ import annotations
import difflib
import json
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from docs import list_docs, load_doc, shapes_for  # noqa: E402
from quran import norm  # noqa: E402
from signals import doc_signals  # noqa: E402
from flag import flag_reasons  # noqa: E402

# the reasons flag.py gives, as ids of the "why" taxonomy
REASON_ID = {"low confidence": "conf", "speck or stray mark": "speck", "ornament, stamp or display type": "ornament",
             "Persian letter the build does not fold": "persian", "differs from the Quran verse": "quran",
             "Latin word on an Arabic page": "latin", "low confidence (old print)": "conf_old",
             "hamza in a print that omits it": "hamza", "ﷺ ligature": "salla", "superscript note number?": "supnum"}
TRUST_CATS = [
    ("verified", "A second, independent source agrees with the reading: the word is part of a Quran quotation "
     "and equals the verse after normalisation, or Gemini's page-1 reading (which the PDF carries) is the same."),
    ("agreed", "No free signal raised a doubt. Not checked by a second source; on the measured sample such "
     "words are wrong 0.43% of the time."),
    ("flagged", "At least one signal says the reading may be wrong; check it on the ink. The reasons follow as "
     "#why.* pointers. On the measured sample about 1 flagged word in 7 is wrong.")]
WHY_CATS = [
    ("conf", "Azure's own confidence for the word is below 0.8."),
    ("speck", "A speck or stray mark: the box is small and alone (or nearly) on its line, or far too narrow for "
     "the letters Azure gives it."),
    ("ornament", "Display type, calligraphy, a stamp or white-on-black: a very large or very dense box, nearly "
     "alone on its line, with confidence below 0.95."),
    ("latin", "A Latin word on an Arabic page with confidence below 0.95 (transliteration marks, formulas, "
     "specks read as Latin)."),
    ("persian", "A Persian/Urdu code point the build does not fold to Arabic (breaks search)."),
    ("quran", "Part of a Quran quotation and differs from the verse by dots or letters (an Azure misreading "
     "20 times in 24 on the ink, experiment 20; otherwise the author's wording)."),
    ("gemini", "On page 1, Gemini's reading (which the PDF carries) differs from Azure's."),
    ("conf_old", "Pre-2000 print with confidence below 0.9 (strict option)."),
    ("hamza", "A hamza on an alef in a print that omits the hamza (strict option)."),
    ("salla", "The ﷺ ligature or Azure's reading of it."),
    ("supnum", "Where a superscript note number may have been read as a mark.")]

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("", TEI)
DPI = 300


def T(tag, parent=None, text=None, **attrs):
    attrs = {(f"{{{XML}}}{k[4:]}" if k.startswith("xml_") else k): str(v)
             for k, v in attrs.items() if v is not None and v != ""}
    e = ET.Element(f"{{{TEI}}}{tag}", attrs) if parent is None else \
        ET.SubElement(parent, f"{{{TEI}}}{tag}", attrs)
    if text is not None:
        e.text = text
    return e


# ---------------------------------------------------------------- roles

_NUM = re.compile(r"^[\s\d٠-٩۰-۹\-–—()\[\].]+$")
_FOOT = re.compile(r"^\s*[\(\[]?[\d٠-٩۰-۹]{1,3}[\)\]]?\s*[-–.)]?")


def roles(doc: dict) -> list[str | None]:
    """A role per paragraph: Azure's when present, else by position.

    The rules are deliberately plain and are marked resp="#rules" in the XML:
      pageNumber   only digits/dashes, in the top or bottom 12% of the page
      pageHeader   in the top 8%, at most 12 words
      pageFooter   in the bottom 6%, at most 12 words
      footnote     lower half, letters ≤ 85% of the page's median word height,
                   and either opening with a note number or following one
      sectionHeading  ≤ 10 words, letters ≥ 125% of the median, not page 1's top
    """
    words = doc["words"]
    by_page = {}
    for w in words:
        by_page.setdefault(w["page"], []).append(w["box"][3] - w["box"][1])
    med = {p: statistics.median(v) for p, v in by_page.items() if v}
    offs = [w["off"] for w in words]
    out, prev_foot = [], {}
    import bisect
    for p in doc["paras"]:
        if p["role"]:
            out.append(p["role"])
            continue
        if not p["box"] or not p["page"]:
            out.append(None)
            continue
        H = doc["pages"][p["page"]]["h"]
        x0, y0, x1, y1 = p["box"]
        i0 = bisect.bisect_left(offs, p["off"])
        i1 = bisect.bisect_left(offs, p["off"] + p["len"])
        ws = words[i0:i1]
        hs = [w["box"][3] - w["box"][1] for w in ws] or [0]
        h = statistics.median(hs)
        m = med.get(p["page"], h) or 1
        txt = p["content"].strip()
        r = None
        if _NUM.match(txt) and len(txt) <= 9 and (y1 < 0.12 * H or y0 > 0.88 * H):
            r = "pageNumber"
        elif y1 < 0.08 * H and len(ws) <= 12:
            r = "pageHeader"
        elif y0 > 0.94 * H and len(ws) <= 12:
            r = "pageFooter"
        elif y0 > 0.5 * H and h <= 0.85 * m and (_FOOT.match(txt) or prev_foot.get(p["page"])):
            r = "footnote"
        elif len(ws) <= 10 and h >= 1.25 * m and not txt.endswith((".", "،")):
            r = "sectionHeading"
        prev_foot[p["page"]] = r == "footnote" or (prev_foot.get(p["page"]) and r is None and y0 > 0.5 * H and h <= 0.85 * m)
        if prev_foot[p["page"]] and r is None:
            r = "footnote"
        out.append(r)
    return out


# ---------------------------------------------------------------- glyph links

def glyph_links(doc: dict, shapes: Path | None) -> dict[int, list[int]]:
    """Azure word index -> indices of the shapes.json placements drawn inside it.

    A placement belongs to the word on its page that covers most of its box
    (at least half of it). Placement boxes are pixels of the 300-dpi scan;
    Azure's are inches."""
    if not shapes:
        return {}, []
    pl = json.loads(shapes.read_text(encoding="utf-8"))["placements"]
    by_page = {}
    for w in doc["words"]:
        by_page.setdefault(w["page"], []).append(w)
    links = {}
    for n, p in enumerate(pl):
        bx = p["box"]
        area = max(1, (bx[2] - bx[0]) * (bx[3] - bx[1]))
        best, bi = 0.0, None
        for w in by_page.get(p["page"], []):
            a = [v * DPI for v in w["box"]]
            ix = min(a[2], bx[2]) - max(a[0], bx[0])
            iy = min(a[3], bx[3]) - max(a[1], bx[1])
            if ix > 0 and iy > 0 and ix * iy / area > best:
                best, bi = ix * iy / area, w["idx"]
        if bi is not None and best >= 0.5:
            links.setdefault(bi, []).append(n)
    return links, pl


def second_reading_pages(shapes: Path | None) -> set[int]:
    """Pages whose glyph text came from another reader than Azure (Gemini's
    page 1), from the build report next to shapes.json. Only a report of a
    single document can be attributed."""
    if not shapes:
        return set()
    rp = shapes.parent / "native_pdf_report.json"
    if not rp.exists():
        return set()
    r = json.loads(rp.read_text())
    r = r if isinstance(r, list) else [r]
    if len(r) != 1:
        return set()
    return {p["page"] for p in r[0]["pages"] if p.get("text") == "gemini"}


# ---------------------------------------------------------------- build

def wid(w: dict, per_page: dict) -> str:
    return w.setdefault("_id", f"p{w['page']}w{per_page[w['idx']]:04d}")


def build(stem: str, info: dict, quotes: list[dict], title: dict | None) -> tuple[ET.Element, dict]:
    doc = load_doc(info["json"])
    words = doc["words"]
    per_page, cnt = {}, Counter()
    for w in words:                   # ids number the words of each page in reading order
        cnt[w["page"]] += 1
        per_page[w["idx"]] = cnt[w["page"]]
    for w in words:
        wid(w, per_page)
    rl = roles(doc)
    shapes = shapes_for(stem)
    links, placements = glyph_links(doc, shapes)
    second = second_reading_pages(shapes)

    # trust (experiment 22): every word gets one mark.
    #   verified  a second source agrees (the verse of a Quran quotation; Gemini's page-1 reading in the PDF)
    #   agreed    no free signal raised a doubt (flag.py's default rule)
    #   flagged   at least one signal did; each reason is a category of the "why" taxonomy
    verified, why = set(), {}
    for qt in quotes:
        for o in qt["ops"]:
            for i in o["doc"]:
                if o["kind"] in ("exact", "spelling", "split", "joined"):
                    verified.add(i)
    alt = {}
    for w in words:
        if w["page"] in second and w["idx"] in links and w["n"]:
            g = "".join(placements[n]["text"] for n in links[w["idx"]])
            if norm(g) == w["n"]:
                verified.add(w["idx"])
            else:
                why.setdefault(w["idx"], []).append("gemini")
                alt[w["idx"]] = g
    idx = {w["idx"]: (w["page"], w["pi"]) for w in words}
    sig, hp = doc_signals(info["json"], info["pdf"], quotes, None, words_idx=idx)
    for w in words:
        s_ = sig.get((w["page"], w["pi"]))
        if s_ is None:
            continue
        w["sig"] = s_
        for r in flag_reasons(s_):
            why.setdefault(w["idx"], []).append(REASON_ID[r])
    trust = {}
    for w in words:
        i = w["idx"]
        if i in verified:                 # a second source agrees on the letters: that outweighs a low confidence
            why.pop(i, None)
        if not (w["n"] or any(c.isalnum() for c in w["text"])):
            continue                      # punctuation alone (<pc>): not assessed
        trust[i] = ("flagged", sorted(set(why[i]))) if i in why else (("verified", []) if i in verified else ("agreed", []))

    root = T("TEI", xml_lang="ar")
    hdr = T("teiHeader", root)
    fd = T("fileDesc", hdr)
    ts = T("titleStmt", fd)
    ttl = (title or {}).get("title") or ""
    T("title", ts, ttl or None, type="main", resp="#gemini" if ttl else None)
    for a in (title or {}).get("authors", []):
        T("author", ts, a, resp="#gemini")
    for xid, resp, name in [
            ("azure", f"text recognition, word boxes, paragraphs ({doc['model']}, API {doc['api']})",
             "Azure Document Intelligence"),
            ("gemini", "reading of page 1: title and authors", "Google Gemini"),
            ("inkscript", "faithful PDF (each word drawn with its own ink), glyph links, this file",
             "inkscript"),
            ("rules", "paragraph roles inferred from position and letter size (tei.py)", "inkscript"),
            ("tanzil", "canonical Quran text (Simple Clean / Simple, v1.1), CC BY 3.0, tanzil.net",
             "Tanzil Project")]:
        rs = T("respStmt", ts, xml_id=xid)
        T("resp", rs, resp)
        T("orgName", rs, name)
    ps = T("publicationStmt", fd)
    T("publisher", ps, "Dar Almandumah")
    T("idno", ps, stem, type="mandumah")
    av = T("availability", ps)
    T("p", av, "Rights as held by the publisher; not stated in this file yet.")
    T("date", ps, None, when=date.today().isoformat())
    sd = T("sourceDesc", fd)
    bs = T("biblStruct", sd)
    an = T("analytic", bs)
    T("title", an, ttl or None, level="a")
    for a in (title or {}).get("authors", []):
        au = T("author", an)
        T("persName", au, a)
    T("idno", an, stem, type="mandumah")
    mo = T("monogr", bs)
    journal = running_head(doc, rl, ttl)
    T("title", mo, journal or None, level="j", cert="low" if journal else None, resp="#rules" if journal else None)
    im = T("imprint", mo)
    parts = stem.split("-")
    T("biblScope", im, None, unit="volume", n=parts[1] if len(parts) > 1 else None)
    T("biblScope", im, None, unit="issue", n=parts[2] if len(parts) > 2 else None)
    T("biblScope", im, None, unit="page", n=str(len(doc["pages"])))
    T("date", im)
    T("note", bs, "The id's four parts are read here as journal-volume-issue-article; "
      "not confirmed. Journal title guessed from running heads (cert=low) where present.")

    ed = T("encodingDesc", hdr)
    pd = T("projectDesc", ed)
    T("p", pd, "Scanned Arabic journal page made into a PDF whose text is its own printed ink "
      "(inkscript). This file describes the document as data: structure, every word with its "
      "page and box, links to the glyphs of the PDF and to the Quran, and trust marks.")
    lp = T("listPrefixDef", ed)
    pdef = T("prefixDef", lp, ident="glyph", matchPattern="([0-9]+)",
             replacementPattern=f"{stem}.shapes.json#/placements/$1")
    T("p", pdef, "glyph:N is placement N of the document's shapes.json: one glyph of the "
      "faithful PDF, with its page, box, text and the shapes its ink is made of.")
    qdef = T("prefixDef", lp, ident="quran", matchPattern="([0-9]+):([0-9]+)",
             replacementPattern="https://tanzil.net/#$1:$2")
    T("p", qdef, "quran:S:A is sura S, verse A.")
    cd = T("classDecl", ed)
    tx = T("taxonomy", cd, xml_id="trust")
    T("desc", tx, "Per-word trust marks (experiment 22). Every word has exactly one. Measured on 2,971 words "
      "judged in experiment 19 (139 random scanned documents): the default rule flags 7.6% of words and "
      "leaves 0.43% of the unflagged words wrong (95% interval 0.05-0.98%).")
    for cid, d in TRUST_CATS:
        c = T("category", tx, xml_id=f"trust.{cid}")
        T("catDesc", c, d)
    tx2 = T("taxonomy", cd, xml_id="why")
    T("desc", tx2, "Why a word is flagged; a flagged word points at one or more of these.")
    for cid, d in WHY_CATS:
        c = T("category", tx2, xml_id=f"why.{cid}")
        T("catDesc", c, d)
    prof = T("profileDesc", hdr)
    lu = T("langUsage", prof)
    T("language", lu, "Arabic", ident="ar")
    rd = T("revisionDesc", hdr)
    T("change", rd, "Written by experiments/22_trust/tei.py (experiment 20's prototype with per-word trust marks).",
      when=date.today().isoformat(), who="#inkscript")

    # facsimile
    fac = T("facsimile", root)
    zones_by_page = {}
    for n, pgd in sorted(doc["pages"].items()):
        s = T("surface", fac, xml_id=f"p{n}", n=n, ulx=0, uly=0,
              lrx=round(pgd["w"] * DPI), lry=round(pgd["h"] * DPI))
        T("graphic", s, url=f"{stem}.pdf#page={n}", width=f"{pgd['w']}in", height=f"{pgd['h']}in")
        zones_by_page[n] = s
    for w in words:
        pts = " ".join(f"{round(w['poly'][i] * DPI)},{round(w['poly'][i + 1] * DPI)}"
                       for i in range(0, len(w["poly"]), 2))
        T("zone", zones_by_page[w["page"]], xml_id=f"z.{w['_id']}", points=pts)

    # body
    text = T("text", root)
    body = T("body", text)
    art = T("div", body, type="article")
    cur = art
    has_div_child = False
    offs = [w["off"] for w in words]
    import bisect
    line_starts = line_start_offsets(info["json"])
    page_seen = set()
    flow = []
    for p, r in zip(doc["paras"], rl):
        i0 = bisect.bisect_left(offs, p["off"])
        i1 = bisect.bisect_left(offs, p["off"] + p["len"])
        flow.append((p, r, words[i0:i1]))
    gem_title = [norm(x) for x in ttl.split()] if ttl else []
    gem_auth = (title or {}).get("authors", [])
    seen_title = False
    body_started = False
    for p, r, ws in flow:
        if not ws:
            continue
        pg = ws[0]["page"]
        resp = None if p["role"] else "#rules"
        joined = "".join(w["n"] for w in ws)
        if not seen_title and pg == 1 and gem_title and len(ws) <= len(ttl.split()) + 3 and \
                difflib.SequenceMatcher(None, joined, "".join(gem_title)).ratio() >= 0.6:
            r, resp, seen_title = "title", "#gemini", True
        elif pg == 1 and gem_auth and len(ws) <= 8 and any(
                difflib.SequenceMatcher(None, joined, norm(a)).ratio() >= 0.7
                for a in (title or {}).get("authors", [])):
            r, resp = "author", "#gemini"
        if pg not in page_seen:
            page_seen.add(pg)
            T("pb", cur, n=pg, facs=f"#p{pg}")
        if r == "title" and not body_started:
            el = T("head", cur, type="title", resp=resp)
        elif r == "author" and not body_started:
            el = T("byline", cur, resp=resp)
            el = T("docAuthor", el)
        elif r == "sectionHeading" and not body_started:
            el = T("head", cur, type="rubric", resp=resp)     # a kicker above the title
        elif r == "sectionHeading":
            cur = T("div", art, type="section")
            has_div_child = True
            el = T("head", cur, resp=resp)
        elif r in ("pageHeader", "pageFooter", "pageNumber"):
            el = T("fw", cur, type={"pageHeader": "header", "pageFooter": "footer",
                                   "pageNumber": "pageNum"}[r], place={"pageHeader": "top",
                                   "pageFooter": "bottom"}.get(r), resp=resp)
        elif r == "footnote":
            el = T("note", cur, place="foot", type="footnote", resp=resp)
        else:
            body_started = True
            el = T("p", cur, type=r if r and r not in ("title", "author") else None, resp=resp if r else None)
        put_words(el, ws, links, trust, line_starts, doc["content"])
    so = T("standOff", root) if (quotes or alt) else None
    if alt:
        la2 = T("listAnnotation", so, type="second-reading")
        for n, (i, g) in enumerate(sorted(alt.items()), 1):
            a = T("annotation", la2, xml_id=f"read{n}", target=f"#{words[i]['_id']}",
                  motivation="assessing", resp="#gemini")
            T("note", a, f"Azure reads «{words[i]['text']}», Gemini «{g}» (the faithful PDF carries Gemini's)",
              type="second-reading")
    # standOff: Quran
    if quotes:
        la = T("listAnnotation", so, type="quran")
        for n, qt in enumerate(quotes, 1):
            tgt = " ".join(f"#{words[i]['_id']}" for i in qt["doc_words"])
            a = T("annotation", la, xml_id=f"quran{n}", target=tgt, motivation="identifying",
                  resp="#inkscript")
            ref = f"quran:{qt['sura']}:{qt['aya']}"
            label = f"{qt['sura_name']} {qt['sura']}:{qt['aya']}" + (
                f"–{qt['aya_end']}" if qt["aya_end"] != qt["aya"] else "")
            T("ref", a, label, target=ref, type="verse")
            status = "exact after normalisation" if qt["differs"] == 0 else \
                f"{qt['differs']} word(s) differ from the verse"
            T("note", a, status, type="status")
            T("note", a, qt["verse"], type="verse", resp="#tanzil")
            for o in qt["ops"]:
                if not o.get("verdict"):
                    continue
                rd_ = " ".join(words[i]["text"] for i in o["doc"]) or "—"
                vs = " ".join(x["v"] for x in o["q"]) or "—"
                T("note", a, f"reading «{rd_}» · verse «{vs}» · {o['verdict']}", type="difference",
                  target=" ".join(f"#{words[i]['_id']}" for i in o["doc"]) or None)
            if qt.get("also"):
                T("note", a, "Same words also in " + ", ".join(qt["also"]), type="alternatives")
            if qt.get("citation"):
                T("note", a, f"Cited in the text as «{qt['citation']['text']}»"
                  + ("" if qt["citation_agrees"] else " — a different sura"), type="citation")
    stats = {"words": len(words), "linked_words": len(links),
             "placements_linked": sum(len(v) for v in links.values()),
             "roles": Counter(r for r in rl if r), "paragraphs": len(doc["paras"]),
             "quotes": len(quotes), "verified": sum(v[0] == "verified" for v in trust.values()),
             "agreed": sum(v[0] == "agreed" for v in trust.values()),
             "flagged": sum(v[0] == "flagged" for v in trust.values()), "second_reading_differs": len(alt),
             "why": dict(Counter(r for v in trust.values() for r in v[1])), "hamza_print": hp,
             "shapes": str(shapes) if shapes else None, "journal_guess": journal}
    trust_json = [dict(id=w["_id"], page=w["page"], pi=w["pi"], text=w["text"], conf=w["conf"],
                       box=w.get("sig", {}).get("box"), mark=trust.get(w["idx"], ("punctuation", []))[0], why=trust.get(w["idx"], (None, []))[1],
                       gemini=alt.get(w["idx"])) for w in words]
    return root, stats, trust_json


def line_start_offsets(js: Path) -> set[int]:
    from docs import text_elements
    j = json.loads(js.read_text(encoding="utf-8"))
    ar = j.get("analyzeResult", j)
    te = text_elements(ar.get("content", "")) if ar.get("stringIndexType") == "textElements" else None
    s = set()
    for pg in ar.get("pages", []):
        for ln in pg.get("lines", []):
            sp = (ln.get("spans") or [{}])[0]
            o = sp.get("offset", -1)
            if o >= 0:
                s.add(te[min(o, len(te) - 1)] if te else o)
    return s


def put_words(el, ws, links, trust, line_starts, content):
    last = None
    for k, w in enumerate(ws):
        if k and w["off"] in line_starts:
            last = T("lb", el)
            last.tail = ""
        attrs = {"xml_id": w["_id"], "facs": f"#z.{w['_id']}"}
        if w["conf"] is not None:
            attrs.update(cert=f"{w['conf']:.3f}", resp="#azure")
        if w["idx"] in links:
            attrs["corresp"] = " ".join(f"glyph:{n}" for n in links[w["idx"]])
        if w["idx"] in trust:
            mark, rs = trust[w["idx"]]
            attrs["ana"] = " ".join([f"#trust.{mark}"] + [f"#why.{r}" for r in rs])
        tag = "w" if w["n"] or any(c.isalnum() for c in w["text"]) else "pc"
        e = T(tag, el, w["text"], **attrs)
        e.tail = " " if k < len(ws) - 1 else None
        last = e


def running_head(doc, rl, title) -> str | None:
    """The most repeated running head, if it repeats on 3+ pages and is not the title."""
    c = Counter()
    for p, r in zip(doc["paras"], rl):
        if r == "pageHeader":
            t = re.sub(r"[\d٠-٩۰-۹\-–—()|]", "", p["content"]).strip()
            if len(t) > 3 and norm(t) != norm(title or ""):
                c[t] += 1
    if c:
        t, n = c.most_common(1)[0]
        if n >= 3:
            return t
    return None


def main():
    stems = sys.argv[1:]
    docs = list_docs()
    qall = json.loads((HERE / "out/quotes.json").read_text(encoding="utf-8"))
    out = HERE / "out/tei"
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for stem in stems:
        tf = HERE.parent / "20_document_data/out/titles" / f"{stem}.gemini.title.json"
        title = json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else None
        root, st, tj = build(stem, docs[stem], qall.get(stem, {}).get("quotes", []), title)
        (HERE / "out/trust").mkdir(exist_ok=True)
        (HERE / "out/trust" / f"{stem}.json").write_text(json.dumps(tj, ensure_ascii=False), encoding="utf-8")
        ET.indent(root, space=" ")
        p = out / f"{stem}.tei.xml"
        head = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<?xml-model href="https://tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng" '
                'type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>\n')
        p.write_text(head + ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
        st["roles"] = dict(st["roles"])
        st["title"] = bool(title)
        summary[stem] = st
        print(stem, st, flush=True)
    sp = out / "summary.json"
    old = json.loads(sp.read_text()) if sp.exists() else {}
    old.update(summary)
    sp.write_text(json.dumps(old, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
