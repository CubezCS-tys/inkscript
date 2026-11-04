"""Experiment 53: the Word file against the print, on the 23 documents that have both (no model calls).

Exp 44 found 23 documents in both S3 areas (a scan with Azure's reading in the main bucket, a legacy PDF made from the
Word file); all 23 have a Word original. For each (out/ground/<stem>.{docx,json,legacy.pdf}):
  text      does the Word text say what the print says? bag-of-words overlap of folded words (Azure's lines vs the
            Word file's paragraphs, tables and notes): share of printed words found in the Word file and the reverse
  numbering the Word file's first page number (pgNumType) against the catalogue's first page and the page numbers
            printed on the scan (Azure lines that are only a number at a page's top or bottom)
  pages     for each scan page, its first long line found in the Word text: the printed page estimated from the
            line's place in the text (catalogue range x character share) and from the legacy PDF page it falls on
            (scaled by page counts), against the true page -> exact / within one page
-> out/compare.json, a table on stdout.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import docx53 as D  # noqa: E402
from build53 import fold, ptext, norm_ar, Legacy  # noqa: E402
from inkscript.enrich import catalogue as CAT  # noqa: E402

G = HERE / "out" / "ground"


def words(s):
    return [w for w in re.findall(r"\w+", fold(s)) if not w.isdigit() and len(w) > 1]


def word_text(doc):
    out = []
    for b in doc["blocks"]:
        out.append(ptext(b))
    for ps in doc["footnotes"].values():
        out += [ptext(p) for p in ps]
    return out


def main():
    cat = CAT.open_catalogue()
    res = []
    for js in sorted(G.glob("*.json")):
        stem = js.stem
        doc = D.read_docx(G / f"{stem}.docx")
        az = json.loads(js.read_text())
        ar = az.get("analyzeResult", az)
        pages = ar["pages"]
        wt = word_text(doc)
        W = Counter(w for t in wt for w in words(t))
        P = Counter(w for p in pages for l in p["lines"] for w in words(l["content"]))
        inter = sum((W & P).values())
        rec = cat.get(stem) or {}
        rng = CAT.page_range(rec.get("pages", ""))
        # printed page numbers on the scan
        nums = []
        for k, p in enumerate(pages):
            ls = p["lines"]
            cand = [l["content"] for l in ls[:2] + ls[-2:]]
            n = next((int(c.strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
                      for c in cand if re.fullmatch(r"\s*[0-9٠-٩]{1,4}\s*", c)), None)
            nums.append(n)
        first_printed = next((n - k for k, n in enumerate(nums) if n is not None), None)
        # the place of each scan page in the Word text
        stream = norm_ar(" ".join(wt))
        L = Legacy(G / f"{stem}.legacy.pdf") if (G / f"{stem}.legacy.pdf").exists() else None
        npg = len(pages)
        ok_share = ok_share1 = ok_leg = ok_leg1 = tried = 0
        cursor = 0
        for k, p in enumerate(pages):
            line = next((l["content"] for l in p["lines"][1:] if len(l["content"].split()) >= 6), None)
            if not line:
                continue
            s = norm_ar(line)[:30]
            if len(s) < 15:
                continue
            pos = stream.find(s, cursor)
            if pos < 0:
                pos = stream.find(s)
            if pos < 0:
                continue
            cursor = pos
            tried += 1
            est = int(pos / max(1, len(stream)) * npg)
            ok_share += est == k
            ok_share1 += abs(est - k) <= 1
            if L is not None:
                f = L.find(line)
                if f and f["pages"]:
                    lp = f["pages"][0]["page"] - 1
                    e2 = int(lp / L.n * npg)
                    ok_leg += e2 == k
                    ok_leg1 += abs(e2 - k) <= 1
        r = dict(stem=stem, scan_pages=npg, legacy_pages=L.n if L else None, catalogue=rec.get("pages"),
                 word_start=doc["page_start"], printed_first=first_printed,
                 print_in_word=round(inter / max(1, sum(P.values())), 3),
                 word_in_print=round(inter / max(1, sum(W.values())), 3),
                 words_print=sum(P.values()), words_word=sum(W.values()),
                 pages_tried=tried, est_share_exact=ok_share, est_share_pm1=ok_share1,
                 est_legacy_exact=ok_leg, est_legacy_pm1=ok_leg1)
        res.append(r)
        print(f"{stem} scan {npg:>3} legacy {r['legacy_pages']!s:>4} cat {r['catalogue']!s:<10} word-start "
              f"{r['word_start']!s:>5} printed-first {first_printed!s:>5} | print-in-word {r['print_in_word']:.3f} "
              f"word-in-print {r['word_in_print']:.3f} | pages {tried}: share exact {ok_share} +-1 {ok_share1}; "
              f"legacy exact {ok_leg} +-1 {ok_leg1}", flush=True)
    (HERE / "out" / "compare.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__" and "--breaks" not in sys.argv:
    main()


# ------------------------------------------------------------------------------------------------ Word's own breaks

def word_pages(docx: Path):
    """(normalised Arabic stream, page index of each character) from Word's lastRenderedPageBreak marks (a native
    .docx saved by Word keeps where its pages broke; a .doc converted by LibreOffice has none)."""
    import zipfile
    from lxml import etree
    Wn = D.W
    x = etree.fromstring(zipfile.ZipFile(docx).read("word/document.xml"))
    for fb in list(x.iter(f"{{{D.MC}}}Fallback")):
        fb.getparent().remove(fb)
    chars, pg = [], []
    page = 0
    nbreaks = 0
    for el in x.iter(f"{{{Wn}}}t", f"{{{Wn}}}lastRenderedPageBreak", f"{{{Wn}}}br"):
        tag = el.tag.split("}")[1]
        if tag == "lastRenderedPageBreak":
            page += 1
            nbreaks += 1
        elif tag == "br":
            if el.get(f"{{{Wn}}}type") == "page":
                pass                       # Word also writes a lastRenderedPageBreak after a manual break
        else:
            s = norm_ar(el.text or "")
            chars.append(s)
            pg += [page] * len(s)
    return "".join(chars), pg, nbreaks


def breaks_main():
    out = []
    for js in sorted(G.glob("*.json")):
        stem = js.stem
        az = json.loads(js.read_text())
        pages = az.get("analyzeResult", az)["pages"]
        stream, pg, nb = word_pages(G / f"{stem}.docx")
        tried = exact = pm1 = 0
        cur = 0
        for k, p in enumerate(pages):
            line = next((l["content"] for l in p["lines"][1:] if len(l["content"].split()) >= 6), None)
            if not line:
                continue
            s = norm_ar(line)[:30]
            if len(s) < 15:
                continue
            pos = stream.find(s, cur)
            if pos < 0:
                pos = stream.find(s)
            if pos < 0:
                continue
            cur = pos
            tried += 1
            exact += pg[pos] == k
            pm1 += abs(pg[pos] - k) <= 1
        out.append(dict(stem=stem, scan_pages=len(pages), word_pages=nb + 1, tried=tried, exact=exact, pm1=pm1))
        print(f"{stem} scan {len(pages):>3} word pages {nb + 1:>3} | lines found {tried:>3}: same page {exact:>3}, "
              f"within one {pm1:>3}")
    (HERE / "out" / "compare_breaks.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__" and "--breaks" in sys.argv:
    breaks_main()
