"""Experiment 28's numbers: per document, per page, per decade and journal, and the set's totals.

    .venv/bin/python experiments/28_scale/summarize.py [SET_DIR]      -> SET_DIR/summary.json, SET_DIR/pages.json

Reads each worker's native_pdf_report.json (the build's --verify/--xml/--trust results), each document's exit status
and /usr/bin/time line (run_set.sh), its stderr (tracebacks), the JATS (title, authors, journal, sections, notes,
links), the ALTO (flags per page), <stem>.corrections.json (inkscript fix), and letter coverage per page measured on
the vector PDF exactly as experiments/09_pen_path/coverage.py does. Per-document measurements are cached in
SET_DIR/metrics/<stem>.json (deleted when the document's files change), so it can run while the set builds.
Front matter is scored against the MARC catalogue (out/catalogue_titles.json): letters-only similarity >= 0.6.
"""
import difflib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import pypdfium2 as pdfium

HERE = Path(__file__).resolve().parent
SET = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out" / "set"
OUT = HERE / "out"
CAT = json.loads((OUT / "catalogue_titles.json").read_text()) if (OUT / "catalogue_titles.json").exists() else {}
FRESH = set((OUT / "ids_fresh.txt").read_text().split()) if (OUT / "ids_fresh.txt").exists() else set()
TITLED = {l.split("\t")[0] for l in (OUT / "titles.tsv").read_text().splitlines() if l.endswith("\tok")} \
    if (OUT / "titles.tsv").exists() else set()
JNS = "{http://www.loc.gov/standards/alto/ns-v4#}"


def letters(s):
    s = re.sub(r"[ًٌٍَُِّْـٰ]", "", s or "")
    s = re.sub("[أإآٱ]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"[^ء-ي0-9a-zA-Z]", "", s)


def sim(a, b):
    a, b = letters(a), letters(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


HONOR = r"^(?:أ\.?\s*د\.?|د\.|الدكتورة?|الأستاذة?|الاستاذة?|الشيخ|السيد|المهندس|ا\.?\s*د\.?|بقلم\s*:?|إعداد\s*:?|اعداد\s*:?)\s*"


def name_sim(cat, found):
    """A catalogue name ("Surname، Given") against a name found on the page, either order, honorifics dropped."""
    f = re.sub(r"\(\*+\)|\*", "", found or "").strip()
    for _ in range(3): f = re.sub(HONOR, "", f).strip()
    parts = [x.strip() for x in re.split(r"[،,]", cat or "") if x.strip()]
    variants = {cat or "", " ".join(reversed(parts)), " ".join(parts)}
    return max(sim(v, f) for v in variants)


def coverage_pages(pdf):
    """Per page (cut, whole): Arabic words of 2+ letters with every letter its own box (coverage.py's rule)."""
    res = []
    a = pdfium.PdfDocument(str(pdf))
    try:
        for pi in range(len(a)):
            pg = a[pi]; tp = pg.get_textpage(); t = tp.get_text_range(); k = 0; cut = whole = 0
            for w in re.split(r"(\s+)", t):
                if re.fullmatch(r"[ء-ي]{2,}", w):
                    boxes = {tuple(round(v, 1) for v in tp.get_charbox(k + m)) for m in range(len(w))}
                    lig = len(re.findall("لا|لأ|لإ|لآ", w))
                    if len(boxes) >= len(w) - lig: cut += 1
                    else: whole += 1
                k += len(w)
            res.append((cut, whole)); tp.close(); pg.close()
    finally:
        a.close()
    return res


def alto_pages(path):
    """Per page: words, flagged, reasons; and Quran-corrected words."""
    pages = []
    for ev, el in ET.iterparse(str(path), events=("start", "end")):
        if ev == "start" and el.tag == JNS + "Page":
            pages.append(dict(words=0, flagged=0, corrected=0, why=defaultdict(int)))
        elif ev == "end" and el.tag == JNS + "String":
            tr = (el.get("TAGREFS") or "").split(); p = pages[-1]; p["words"] += 1
            if "trust.flagged" in tr:
                p["flagged"] += 1
                for t in tr:
                    if t.startswith("why."): p["why"][t[4:]] += 1
            if "trust.corrected" in tr: p["corrected"] += 1
            el.clear()
    for p in pages: p["why"] = dict(p["why"])
    return pages


def jats_info(path):
    t = path.read_text(encoding="utf-8")
    root = ET.fromstring(t.encode())
    title = "".join(root.find(".//article-meta/title-group/article-title").itertext()).strip() \
        if root.find(".//article-meta/title-group/article-title") is not None else ""
    names = []
    for c in root.iter("contrib"):
        n = c.find(".//name")
        sn = c.find(".//string-name")
        nm = " ".join(x for x in (n.findtext("given-names") if n is not None else "", n.findtext("surname") if n is not None else "") if x) \
            if n is not None else ("".join(sn.itertext()).strip() if sn is not None else "".join(c.itertext()).strip())
        names.append(re.sub(r"\s+", " ", nm))
    jt = root.findtext(".//journal-title") or ""
    return dict(title=title, authors=names, journal_title=jt,
                secs=sum(1 for _ in root.iter("sec")), fns=sum(1 for _ in root.iter("fn")),
                xref_fn=sum(1 for x in root.iter("xref") if x.get("ref-type") == "fn"),
                refs=sum(1 for _ in root.iter("ref")), quotes=sum(1 for x in root.iter("disp-quote")) +
                sum(1 for x in root.iter("named-content") if "quran" in (x.get("content-type") or "")),
                fpage=root.findtext(".//article-meta/fpage") or "", lpage=root.findtext(".//article-meta/lpage") or "",
                title_source=next((cm.findtext("meta-value") for cm in root.iter("custom-meta")
                                   if cm.findtext("meta-name") == "title-source"), ""))


def doc_metrics(stem, wdir, report):
    """Everything per document that needs reading files (cached)."""
    m = dict()
    vec = wdir / f"{stem}_vector.pdf"
    if vec.exists():
        m["coverage_pages"] = coverage_pages(vec)
    a = wdir / f"{stem}.alto.xml"
    if a.exists():
        try: m["alto_pages"] = alto_pages(a)
        except Exception as e: m["alto_error"] = str(e)[:200]
    j = wdir / f"{stem}.jats.xml"
    if j.exists():
        try: m["jats"] = jats_info(j)
        except Exception as e: m["jats_error"] = str(e)[:200]
    c = wdir / f"{stem}.corrections.json"
    if c.exists():
        d = json.loads(c.read_text(encoding="utf-8"))
        st = defaultdict(int); kinds = defaultdict(int); notp = defaultdict(int); declined = defaultdict(int)
        for e in d["corrections"]:
            st[e["status"]] += 1
            if e["status"] == "applied": kinds[e["kind"]] += 1
            if e["status"] == "declined":
                declined[str(e.get("declined") or e.get("why_declined") or "")[:60]] += 1
        for r in d["runs"][-1:]:
            for k, v in (r.get("not_proposed") or {}).items(): notp[k] += v
        last = d["runs"][-1] if d["runs"] else {}
        m["fix"] = dict(proposed=len(d["corrections"]), statuses=dict(st), applied_kinds=dict(kinds), not_proposed=dict(notp),
                        ink=last.get("ink"), enrich_problems=last.get("enrich_problems"), declined=dict(declined),
                        spend=sum(r.get("spend", 0) or 0 for r in d["runs"]))
    return m


def stamp(wdir, stem):
    fs = [wdir / f"{stem}{s}" for s in ("_vector.pdf", ".alto.xml", ".jats.xml", ".corrections.json", ".pdf")]
    return [f.stat().st_mtime if f.exists() else 0 for f in fs]


def main():
    (SET / "metrics").mkdir(exist_ok=True)
    order = (SET / "order.txt").read_text().split()
    reports = {}
    for rp in sorted(SET.glob("w*/native_pdf_report.json")):
        for r in json.loads(rp.read_text(encoding="utf-8")):
            reports[r["doc"]] = (rp.parent, r)
    docs, pages = [], []
    for stem in order:
        st = (SET / "status" / stem).read_text().strip() if (SET / "status" / stem).exists() else None
        tm = (SET / "logs" / f"{stem}.time")
        peak = wall = None
        if tm.exists():
            mm = re.search(r"peak_kb=(\d+) wall=([\d.]+)", tm.read_text())
            if mm: peak, wall = int(mm.group(1)) // 1024, float(mm.group(2))
        err = (SET / "logs" / f"{stem}.err")
        tb = None
        if err.exists():
            et = err.read_text(errors="replace")
            if "Traceback" in et:
                tb = et[et.rfind("Traceback"):][-1500:]
        cat = CAT.get(stem, {})
        y = re.search(r"(1[89]\d\d|20[0-2]\d)", cat.get("year", "") or "")
        year = int(y.group(1)) if y else None
        d = dict(doc=stem, status=st, peak_mb=peak, wall_s=wall, traceback=tb, year=year,
                 decade=("<1960" if year and year < 1960 else f"{year // 10 * 10}s") if year else "?",
                 journal=cat.get("journal", ""), country=cat.get("country", ""), fresh=stem in FRESH,
                 title_file=stem in TITLED, cat_title=cat.get("title", ""), cat_authors=cat.get("authors", []))
        if stem not in reports or st is None:
            d["built"] = False; docs.append(d); continue
        wdir, r = reports[stem]
        d["built"] = True; d["dir"] = wdir.name
        cf = SET / "metrics" / f"{stem}.json"
        s = stamp(wdir, stem)
        m = json.loads(cf.read_text()) if cf.exists() else None
        if not m or m.get("_stamp") != s:
            m = doc_metrics(stem, wdir, r); m["_stamp"] = s; cf.write_text(json.dumps(m, ensure_ascii=False))
        e = r.get("enrich", {}); v = r.get("verify", []); ln = r.get("lines", [])
        cov = m.get("coverage_pages", []); ap = m.get("alto_pages", [])
        bd = {p["page"] for p in r["pages"] if str(p.get("text", "")).startswith("native")}
        d.update(pages=len(r["pages"]), born_digital_pages=len(bd),
                 sideways_pages=sum(1 for p in r["pages"] if p.get("rotated")),
                 words=sum(x["words"] for x in v), intact=sum(x["intact"] for x in v),
                 lines=sum(x["lines"] for x in ln), in_order=sum(x["in_order"] for x in ln),
                 reversed=sum(x.get("reversed", 0) for x in ln),
                 inversions=(r.get("order") or {}).get("inversions"),
                 lines_layer=sum(x.get("lines_layer", 0) for x in v), lines_pdfium=sum(x.get("lines_pdfium", 0) for x in v),
                 lost_image=r.get("lost_image", []),
                 letters_cut=sum(c for c, w in cov), letters_words=sum(c + w for c, w in cov),
                 enrich_error=e.get("error"))
        d["joins_lines"] = bool(d["lines_layer"] and d["lines_pdfium"] < 0.8 * d["lines_layer"])
        t = e.get("trust", {}); q = e.get("quotes", {}); jt = e.get("jats", {}); al = e.get("alto", {})
        tp = e.get("trust_pdf", {})
        d.update(assessed=t.get("words"), flagged=t.get("flagged"), verified=t.get("verified"), why=t.get("why"),
                 corrected_in_trust=t.get("corrected"),
                 quotes=q.get("found"), quotes_equal=q.get("equal"), quotes_differ=q.get("differ"),
                 jats_valid=jt.get("valid"), alto_valid=al.get("valid"),
                 trust_pdfs_ok=all(x.get("check", {}).get("ok") for x in tp.values()) if tp else None,
                 words_linked=e.get("words_linked_to_glyphs"), azure_words=e.get("words"))
        ji = m.get("jats") or {}
        d["jats_info"] = ji
        d["title_found"] = bool(ji.get("title"))
        d["author_found"] = bool(ji.get("authors"))
        if cat:
            d["title_sim"] = round(sim(ji.get("title", ""), cat.get("title", "")), 3) if ji.get("title") else 0.0
            ca = cat.get("authors", [])
            ja = ji.get("authors", [])
            hit = sum(1 for x in ca if any(name_sim(x, y) >= 0.6 for y in ja))
            d["authors_cat"] = len(ca); d["authors_hit"] = hit; d["authors_jats"] = len(ja)
            d["authors_jats_right"] = sum(1 for y in ja if any(name_sim(x, y) >= 0.6 for x in ca))
        d["fix"] = m.get("fix")
        docs.append(d)
        # pages
        vp = {x["page"]: x for x in v}; lp = {x["page"]: x for x in ln}
        for i, p in enumerate(r["pages"]):
            n = p["page"] if "page" in p else i + 1
            pv, pl = vp.get(n, {}), lp.get(n, {})
            c = cov[i] if i < len(cov) else (0, 0); a = ap[i] if i < len(ap) else {}
            pages.append(dict(doc=stem, page=n, kind=p.get("text"), rotated=p.get("rotated"), words=pv.get("words", 0),
                              intact=pv.get("intact", 0), lines=pl.get("lines", 0), in_order=pl.get("in_order", 0),
                              reversed=pl.get("reversed", 0),
                              lines_layer=pv.get("lines_layer", 0), lines_pdfium=pv.get("lines_pdfium", 0),
                              cut=c[0], whole=c[1], alto_words=a.get("words", 0), flagged=a.get("flagged", 0),
                              why=a.get("why", {}), lost_image=n in (r.get("lost_image") or []),
                              decade=d["decade"], year=year))
    (SET / "pages.json").write_text(json.dumps(pages, ensure_ascii=False))
    B = [d for d in docs if d.get("built")]

    def agg(ds):
        S = lambda k: sum((d.get(k) or 0) for d in ds)
        fx = defaultdict(int); fk = defaultdict(int); prop = 0; spend = 0.0
        for d in ds:
            f = d.get("fix") or {}
            prop += f.get("proposed", 0); spend += f.get("spend", 0)
            for k, v in (f.get("statuses") or {}).items(): fx[k] += v
            for k, v in (f.get("applied_kinds") or {}).items(): fk[k] += v
        cat = [d for d in ds if d.get("cat_title")]
        return dict(documents=len(ds), pages=S("pages"), born_digital_pages=S("born_digital_pages"),
                    words=S("words"), intact=S("intact"), lines=S("lines"), in_order=S("in_order"), reversed=S("reversed"),
                    inversions=S("inversions"), letters_cut=S("letters_cut"), letters_words=S("letters_words"),
                    assessed=S("assessed"), flagged=S("flagged"), verified=S("verified"),
                    quotes=S("quotes"), quotes_equal=S("quotes_equal"), quotes_differ=S("quotes_differ"),
                    jats_valid=sum(d.get("jats_valid") is True for d in ds), alto_valid=sum(d.get("alto_valid") is True for d in ds),
                    trust_pdfs_ok=sum(d.get("trust_pdfs_ok") is True for d in ds),
                    title_found=sum(d.get("title_found", False) for d in ds), author_found=sum(d.get("author_found", False) for d in ds),
                    with_cat_title=len(cat), title_right=sum(d.get("title_sim", 0) >= 0.6 for d in cat),
                    authors_cat=S("authors_cat"), authors_hit=S("authors_hit"), authors_jats=S("authors_jats"),
                    authors_jats_right=S("authors_jats_right"),
                    joins_lines=sum(d.get("joins_lines", False) for d in ds), lost_image_pages=sum(len(d.get("lost_image") or []) for d in ds),
                    enrich_errors=sum(1 for d in ds if d.get("enrich_error")),
                    fix_proposed=prop, fix_statuses=dict(fx), fix_applied_kinds=dict(fk), fix_spend=round(spend, 3),
                    wall_s=round(S("wall_s")), peak_mb_max=max((d.get("peak_mb") or 0 for d in ds), default=0))
    tot = agg(B)
    tot.update(attempted=sum(1 for d in docs if d["status"] is not None), in_set=len(docs),
               crashed=[d["doc"] for d in docs if d["status"] not in (None, "0", "124")],
               timeouts=[d["doc"] for d in docs if d["status"] == "124"])
    by_decade = {k: agg([d for d in B if d["decade"] == k]) for k in sorted({d["decade"] for d in B})}
    by_journal = {k: agg([d for d in B if d["journal"] == k]) for k in sorted({d["journal"] for d in B})}
    by_origin = {"experiment 19 sample": agg([d for d in B if not d["fresh"]]), "fresh draw": agg([d for d in B if d["fresh"]])}
    (SET / "summary.json").write_text(json.dumps(dict(total=tot, by_decade=by_decade, by_origin=by_origin,
                                                      by_journal=by_journal, docs=docs), ensure_ascii=False, indent=1))
    t = tot; P = lambda a, b: f"{100 * a / max(1, b):.2f}%"
    print(f"{t['documents']} built of {t['attempted']} attempted ({t['in_set']} in the set), {t['pages']} pages; "
          f"crashed {len(t['crashed'])}, timeouts {len(t['timeouts'])}, enrich errors {t['enrich_errors']}")
    print(f"words intact {t['intact']}/{t['words']} ({P(t['intact'], t['words'])}), lines in order {t['in_order']}/{t['lines']} "
          f"({P(t['in_order'], t['lines'])}), reversed {t['reversed']}, inversions {t['inversions']}, joins-lines docs {t['joins_lines']}, "
          f"lost-image pages {t['lost_image_pages']}")
    print(f"letter coverage {P(t['letters_cut'], t['letters_words'])}, flagged {P(t['flagged'], t['assessed'])}, verified {t['verified']}, "
          f"quotations {t['quotes']} ({t['quotes_equal']} equal, {t['quotes_differ']} differ)")
    print(f"JATS valid {t['jats_valid']}, ALTO valid {t['alto_valid']}, trust PDFs ok {t['trust_pdfs_ok']}; title found {t['title_found']}, "
          f"right {t['title_right']}/{t['with_cat_title']}; authors: catalogue {t['authors_cat']}, found {t['authors_hit']}, "
          f"JATS names {t['authors_jats']} of which right {t['authors_jats_right']}")
    print(f"fix: proposed {t['fix_proposed']}, {t['fix_statuses']}, spend ${t['fix_spend']}; wall {t['wall_s'] / 3600:.1f} h of work, "
          f"peak {t['peak_mb_max']} MB")
    for k, a in by_decade.items():
        print(f"  {k:<6} {a['documents']:>3} docs {a['pages']:>5} pp  intact {P(a['intact'], a['words'])}  lines {P(a['in_order'], a['lines'])}  "
              f"letters {P(a['letters_cut'], a['letters_words'])}  flagged {P(a['flagged'], a['assessed'])}  title right "
              f"{a['title_right']}/{a['with_cat_title']}")


if __name__ == "__main__":
    main()
