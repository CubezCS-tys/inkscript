"""The JATS and ALTO files of experiment 28's 205 documents written again, without and with the catalogue, from the
builds already made (the Azure reading, the scan, the build's shapes.json and corrections; nothing is rebuilt and
experiment 28's files are only read). Each file is validated (JATS 1.4 Archiving DTD, ALTO 4.4 XSD) and its front
matter summarised.

    PYTHONPATH=src .venv/bin/python experiments/29_catalogue/run.py before|after [--workers 3] [stem ...]
    -> out/<mode>/<stem>.jats.xml, .alto.xml; out/<mode>.json (one row per document)

The data live in the main checkout (gitignored): $INK28 (default /home/yassine/inkscript/experiments/28_scale/out).
"""
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SET28 = Path(os.environ.get("INK28", "/home/yassine/inkscript/experiments/28_scale/out"))


def where(stem):
    for w in ("w0", "w1", "w2"):
        if (SET28 / "set" / w / f"{stem}.shapes.json").exists():
            return SET28 / "set" / w
    return None


def report_of(stem, d):
    for r in json.loads((d / "native_pdf_report.json").read_text(encoding="utf-8")):
        if r["doc"] == stem:
            return r
    return {}


def summarise(path: Path) -> dict:
    t = etree.parse(str(path))
    fm = t.find("front")
    am = fm.find("article-meta")
    jm = fm.find("journal-meta")
    cm = {c.findtext("meta-name"): c.findtext("meta-value") for c in am.iter("custom-meta")}
    title = "".join(am.find("title-group/article-title").itertext()).strip()
    contribs = am.findall("contrib-group/contrib")

    def cname(c):
        n = c.find(".//name")
        if n is not None:
            return " ".join(x for x in (n.findtext("given-names"), n.findtext("surname")) if x)
        s = c.find(".//string-name")
        if s is not None:
            return " ".join("".join(s.itertext()).split())
        return c.findtext("collab") or ""
    return dict(
        title=title, subtitle=am.findtext("title-group/subtitle") or "",
        title_words=bool(cm.get("title-words")),
        authors=[cname(c) for c in contribs],
        authors_ink=sum(1 for n in range(1, len(contribs) + 1) if cm.get(f"author-{n}-words")),
        prefixes=[c.findtext(".//prefix") or "" for c in contribs],
        affs=sum(1 for c in contribs if c.find("aff") is not None),
        journal=(jm.findtext("journal-title-group/journal-title") or ""),
        issn=jm.findtext("issn") or "",
        year=" / ".join(f"{p.findtext('year')} ({p.get('calendar')})" for p in am.findall("pub-date")),
        volume=am.findtext("volume") or "", issue=am.findtext("issue") or "",
        fpage=am.findtext("fpage") or "", lpage=am.findtext("lpage") or "",
        abstract=len(am.findall("abstract")) + len(am.findall("trans-abstract")),
        keywords=sum(len(g.findall("kwd")) for g in am.findall("kwd-group")),
        doi=next((a.text for a in am.findall("article-id") if a.get("pub-id-type") == "doi"), ""),
        check=cm.get("catalogue-check", ""), sources=cm.get("front-sources", ""),
        title_source=cm.get("title-source", ""))


def one(args):
    stem, mode = args
    from inkscript.enrich import alto, jats, schemas
    from inkscript.enrich.catalogue import open_catalogue
    from inkscript.enrich.corrections import applied_entries, overlay
    from inkscript.enrich.document import load
    from inkscript.enrich.quran import check_document
    from inkscript.enrich.structure import read_meta
    from inkscript.enrich.trust import assess
    t0 = time.time()
    d = where(stem)
    az = SET28 / "azure" / stem
    out = OUT / mode
    out.mkdir(parents=True, exist_ok=True)
    try:
        r = report_of(stem, d)
        pages = r.get("pages", [])
        gem = {p["page"] for p in pages if p.get("text") == "gemini"}
        born = {p["page"] for p in pages if str(p.get("text", "")).startswith("native-")}
        doc = load(az / f"{stem}.json", d / f"{stem}.shapes.json", gem)
        quotes = check_document(doc)
        scan = az / f"{stem}.pdf"
        marks = assess(doc, quotes, scan)
        overlay(doc, marks, applied_entries(d, stem), quotes)
        cat = open_catalogue() if mode == "after" else None
        meta = read_meta(stem, [az, SET28 / "gemini"], catalogue=cat)
        jats.structure_of(doc, meta, scan)
        jn, an = f"{stem}.jats.xml", f"{stem}.alto.xml"
        res = jats.write(doc, quotes, marks, stem, out / jn, an)
        ids = res.pop("_ids")
        alto.write(doc, quotes, marks, stem, out / an, jn, born, "exp29", ids)
        je, ae = schemas.validate_jats(out / jn), schemas.validate_alto(out / an)
        row = dict(stem=stem, jats_valid=not je, alto_valid=not ae, jats_errors=je[:5], alto_errors=ae[:5],
                   pages=len(doc["pages"]), catalogue=bool(meta.get("catalogue")), seconds=round(time.time() - t0, 1))
        row.update(summarise(out / jn))
        fr = doc["structure"]["front"]
        if fr.get("catalogue_check"):
            row["catalogue_check"] = fr["catalogue_check"]
            row["page_front"] = fr.get("page_front")
        row["title_word_ids"] = [doc["words"][k]["id"] for k in fr.get("title_words", [])]
        row["author_word_ids"] = [[doc["words"][k]["id"] for k in a.get("words", [])] for a in fr.get("authors", [])]
        return row
    except Exception as e:
        import traceback
        return dict(stem=stem, error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc())


def main():
    mode = sys.argv[1]
    args = sys.argv[2:]
    workers = 3
    if "--workers" in args:
        i = args.index("--workers")
        workers = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    stems = args or sorted(p.name for p in (SET28 / "azure").iterdir() if where(p.name))
    rows = []
    with Pool(workers, maxtasksperchild=1) as pool:
        for row in pool.imap_unordered(one, [(s, mode) for s in stems]):
            rows.append(row)
            print(row["stem"], row.get("error") or f"{row['seconds']}s jats {row['jats_valid']} alto {row['alto_valid']} "
                  f"title {row['title'][:40]!r} authors {len(row['authors'])}", flush=True)
    rows.sort(key=lambda r: r["stem"])
    name = OUT / f"{mode}.json"
    if args and name.exists():                     # a rerun of some documents: replace their rows
        old = {r["stem"]: r for r in json.loads(name.read_text(encoding="utf-8"))}
        old.update({r["stem"]: r for r in rows})
        rows = sorted(old.values(), key=lambda r: r["stem"])
    name.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", name)


if __name__ == "__main__":
    main()
