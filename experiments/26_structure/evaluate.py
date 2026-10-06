"""Score JATS files against the hand-made truth: precision and recall per element.

    python evaluate.py [--truth heldout] JATS_DIR [JATS_DIR...]
        -> prints a table; writes JATS_DIR/scores.json (scores_heldout.json with --truth heldout)

Elements: title (one per document), authors (one per person), rubric, headings (section titles on the pages read),
footnote links (an <xref ref-type="fn"> in the text of a page read, pointing at that page's note with the right
label), and furniture leaks (article paragraphs that are a running head, footer or page number).

Matching is on the normalised letters (inkscript.enrich.quran.norm, spaces removed) with a similarity ratio of at
least 0.6 (difflib), so a misread letter does not count as a miss; honorifics (الدكتور, الأستاذ, الشيخ, بقلم …) are
removed from names first.
"""
import difflib
import json
import re
import sys
from pathlib import Path

from lxml import etree

from inkscript.enrich.document import load, para_box
from inkscript.enrich.jats import block_ids
from inkscript.enrich.quran import norm

HERE = Path(__file__).resolve().parent
TRUTH_NAME = "truth"
TRUTH = json.loads((HERE / "truth" / "truth.json").read_text(encoding="utf-8"))["docs"]
HONOR = re.compile(r"\b(بقلم|للدكتور|الدكتور|الدكتوره|دكتور|د|الاستاذ|الأستاذ|للاستاذ|استاذ|الشيخ|للشيخ|أ|ا)\b\.?")
_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def key(s: str, name=False) -> str:
    s = (s or "").translate(_DIG)
    if name:
        s = re.sub(r"[/.]", " ", s)
        s = " ".join(t for t in s.split() if norm(t) not in {norm(h) for h in (
            "بقلم", "للدكتور", "الدكتور", "دكتور", "د", "الاستاذ", "للاستاذ", "الشيخ", "للشيخ", "أ", "ا")})
    k = norm(s).replace(" ", "")
    if not k:                          # digits, Latin numerals
        k = re.sub(r"\W", "", s).lower()
    return k


def sim(a: str, b: str, name=False) -> float:
    ka, kb = key(a, name), key(b, name)
    if not ka or not kb:
        return 0.0
    return difflib.SequenceMatcher(None, ka, kb, autojunk=False).ratio()


AZ = Path("/home/yassine/inkscript/experiments/24_product/out/azure")


def page_of_id(i):
    m = re.match(r"p(\d+)b\d+", i or "")
    return int(m.group(1)) if m else None


def page_of(el) -> int | None:
    while el is not None:
        i = el.get("id") or ""
        m = re.match(r"p(\d+)b\d+", i)
        if m:
            return int(m.group(1))
        el = el.getparent()
    return None


def read_jats(path: Path) -> dict:
    t = etree.parse(str(path))
    txt = lambda e: "".join(e.itertext()).strip() if e is not None else ""
    fn_label = {}
    for fn in t.iter("fn"):
        lab = fn.findtext("label")
        fn_label[fn.get("id")] = (lab or "").translate(_DIG).strip()
    links, endlinks = [], []
    for x in t.xpath("//body//xref[@ref-type='fn']"):
        pg = page_of(x)
        m = re.match(r"fn-p(\d+)-", x.get("rid") or "")
        rec = dict(page=pg, note=fn_label.get(x.get("rid"), "?"))
        (links if m and int(m.group(1)) == pg else endlinks).append(rec)
    heads = [dict(page=page_of(s), text=txt(s)) for s in t.xpath("//body//sec/title")]
    body_ps = [(p.get("id"), txt(p)) for p in t.xpath("//body//p")]
    return dict(title=txt(t.find(".//article-title")),
                authors=[txt(c) for c in t.xpath("//contrib-group/contrib/string-name")],
                rubric=" ".join(txt(s) for s in t.xpath("//subj-group[@subj-group-type='heading']/subject")),
                headings=heads, links=links, endlinks=endlinks, body=body_ps)


def score(dirs):
    out = {}
    for d in dirs:
        d = Path(d)
        c = {k: dict(tp=0, fp=0, fn=0) for k in ("title", "authors", "rubric", "headings", "footnote_links",
                                                  "endnote_links")}
        leaks = 0
        per_doc = {}
        for stem, tr in TRUTH.items():
            f = d / f"{stem}.jats.xml"
            if not f.exists():
                continue
            j = read_jats(f)
            pages = set(tr["pages"])
            dd = per_doc[stem] = {}
            # title
            if j["title"]:
                ok = sim(j["title"], tr["title"]) >= 0.6
                c["title"]["tp" if ok else "fp"] += 1
                c["title"]["fn"] += 0 if ok else 1
            else:
                c["title"]["fn"] += 1
            dd["title"] = j["title"]
            # authors
            used = set()
            for a in j["authors"]:
                m = [i for i, t in enumerate(tr["authors"]) if i not in used and sim(a, t, True) >= 0.6]
                if m:
                    used.add(m[0])
                    c["authors"]["tp"] += 1
                else:
                    c["authors"]["fp"] += 1
            c["authors"]["fn"] += len(tr["authors"]) - len(used)
            dd["authors"] = j["authors"]
            # rubric
            if tr.get("rubric"):
                if j["rubric"] and sim(j["rubric"], tr["rubric"]) >= 0.6:
                    c["rubric"]["tp"] += 1
                else:
                    c["rubric"]["fn"] += 1
                    c["rubric"]["fp"] += 1 if j["rubric"] else 0
            elif j["rubric"]:
                c["rubric"]["fp"] += 1
            dd["rubric"] = j["rubric"]
            # headings on the pages read
            th = list(tr["headings"])
            opt = tr.get("headings_optional", [])
            used = set()
            dd["headings"] = []
            for h in j["headings"]:
                if h["page"] not in pages:
                    continue
                m = [i for i, t in enumerate(th) if i not in used and t["page"] == h["page"] and sim(h["text"], t["text"]) >= 0.6]
                if m:
                    used.add(m[0])
                    c["headings"]["tp"] += 1
                    dd["headings"].append(("ok", h["page"], h["text"]))
                elif any(t["page"] == h["page"] and sim(h["text"], t["text"]) >= 0.6 for t in opt):
                    dd["headings"].append(("optional", h["page"], h["text"]))
                else:
                    c["headings"]["fp"] += 1
                    dd["headings"].append(("wrong", h["page"], h["text"]))
            c["headings"]["fn"] += len(th) - len(used)
            dd["headings_missed"] = [t for i, t in enumerate(th) if i not in used]
            # footnote links
            tl = [(x["page"], x["note"]) for x in tr["footnote_links"]]
            got = [(x["page"], x["note"]) for x in j["links"] if x["page"] in pages]
            rem = list(tl)
            dd["links"] = []
            for g in got:
                if g in rem:
                    rem.remove(g)
                    c["footnote_links"]["tp"] += 1
                    dd["links"].append(("ok",) + g)
                else:
                    c["footnote_links"]["fp"] += 1
                    dd["links"].append(("wrong",) + g)
            c["footnote_links"]["fn"] += len(rem)
            dd["links_missed"] = rem
            # endnote links (a marker whose note is in a list on another page)
            epages = set(tr.get("endnote_pages", tr["pages"]))
            tl = [(x["page"], x["note"]) for x in tr.get("endnote_links", [])]
            rem = list(tl)
            dd["endlinks"] = []
            for g in [(x["page"], x["note"]) for x in j["endlinks"] if x["page"] in epages]:
                ok = g in rem
                if ok:
                    rem.remove(g)
                c["endnote_links"]["tp" if ok else "fp"] += 1
                dd["endlinks"].append(("ok" if ok else "wrong",) + g)
            c["endnote_links"]["fn"] += len(rem)
            dd["endlinks_missed"] = rem
            # furniture in the article text
            fk = [key(x) for x in tr.get("furniture", [])]
            doc = load(AZ / stem / f"{stem}.json")
            ypos = {}
            for p in doc["paras"]:
                for pg, bid in block_ids(doc)[p["idx"]]:
                    b = para_box(doc, p, pg)
                    ypos[bid] = (b[1] / doc["pages"][pg]["h"], b[3] / doc["pages"][pg]["h"])
            for bid, t in j["body"]:
                pg = page_of_id(bid)
                y0, y1 = ypos.get(bid, (0.5, 0.5))
                k = key(re.sub(r"[\d٠-٩•●■|\-–—]", " ", t))
                digits_only = re.fullmatch(r"[\s\d٠-٩\-–—.()]+", t or "") is not None and len(t.strip()) <= 9 \
                    and (y1 < 0.12 or y0 > 0.88)
                if digits_only or (k and len(k) <= 60 and any(f and difflib.SequenceMatcher(None, k, f).ratio() >= 0.7 for f in fk)):
                    leaks += 1
                    dd.setdefault("leaks", []).append((pg, t))
        res = {}
        for k, v in c.items():
            p = v["tp"] / (v["tp"] + v["fp"]) if v["tp"] + v["fp"] else None
            r = v["tp"] / (v["tp"] + v["fn"]) if v["tp"] + v["fn"] else None
            res[k] = dict(v, precision=p, recall=r)
        res["furniture_leaks"] = leaks
        out[str(d)] = dict(scores=res, docs=per_doc)
        (d / ("scores.json" if TRUTH_NAME == "truth" else f"scores_{TRUTH_NAME}.json")).write_text(json.dumps(out[str(d)], ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n{d}")
        for k, v in res.items():
            if isinstance(v, dict):
                fmt = lambda x: "  -  " if x is None else f"{x:5.2f}"
                print(f"  {k:15} P {fmt(v['precision'])}  R {fmt(v['recall'])}   tp {v['tp']:3} fp {v['fp']:3} fn {v['fn']:3}")
            else:
                print(f"  {k:15} {v}")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--truth"]:
        TRUTH_NAME = args[1]
        TRUTH = json.loads((HERE / "truth" / f"{TRUTH_NAME}.json").read_text(encoding="utf-8"))["docs"]
        args = args[2:]
    score(args)
