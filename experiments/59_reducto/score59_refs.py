"""Experiment 59: Reducto Extract's citation fields against the proof pack's citation gold (same items, same fields).

    /home/appuser/inkscript/.venv/bin/python score59_refs.py [--dump]   -> out/refs_scores.json

Gold = the proof pack's 20 sampled citations on the 15 pages sent (experiment 43 out/proof/cites_draw.json: the
printed citation; cites_score.json: the evaluator's field list and verdicts on our masters).  The fields scored are
exactly the evaluator's fields for that citation (authors, title, source, year, pages, volume, issue, publisher,
place, link, other = editor / translator / edition / a second locus).  The truth value of a field is our value where
the evaluator found it right, else the printed text (judge59_refs.json holds the truth values I set by reading the
print, and my verdict on each Reducto value that is not an exact folded match).
Reducto's entry for a citation = the extracted entry whose raw_text best overlaps the printed citation.
Field map: authors -> authors; title -> title when the work has a container (article / chapter), source -> the
container, or the title for a whole book; year -> year_as_printed (or year_gregorian); pages; volume; issue; publisher;
place; link -> url; other -> editors / translators / edition.
Verdicts as the proof pack: right / loose / missing / wrong; a citation is fully right when every field is right.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
from collections import Counter
from pathlib import Path

from inkscript.gold.text import folded

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
PROOF = E / "43_rehearsal/out/proof"
JUDGE = HERE / "judge59_refs.json"
DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def val(x):
    if isinstance(x, dict) and "value" in x and "citations" in x:
        return val(x["value"])
    if isinstance(x, dict):
        return {k: val(v) for k, v in x.items()}
    if isinstance(x, list):
        return [val(v) for v in x]
    return x


def cites_of(x):
    """the citations (boxes) Reducto gave for each field of one entry"""
    out = {}
    for k, v in x.items():
        if isinstance(v, dict) and "citations" in v:
            out[k] = v["citations"]
    return out


def norm(s):
    if s is None:
        return ""
    if isinstance(s, list):
        s = " ; ".join(str(v) for v in s if v)
    s = str(s).translate(DIG)
    s = folded(s)
    s = re.sub(r"[\"'«»“”‘’()\[\].,:;،؛\-–—_/]", " ", s)
    return " ".join(s.split())


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b), autojunk=False).ratio()


def entries(mode, pid):
    f = OUT / "extract" / f"refs_{mode}" / f"{pid}.json"
    if not f.exists():
        return None
    r = json.loads(f.read_text())["result"]
    r = r[0] if isinstance(r, list) else r
    raw = r.get("references")
    raw = raw.get("value") if isinstance(raw, dict) and "value" in raw else raw
    return [(val(e), cites_of(e)) for e in (raw or [])]


def best_entry(ents, printed, key):
    """the entry for this work: its title / authors closest to the gold work's (key), then its text to the print
    (a footnote can cite several works; the proof pack sampled one of them)"""
    best, bs = None, -1.0
    for e, c in ents:
        names = " ".join(str((a or {}).get("name_as_printed") or "") for a in (e.get("authors") or []) if isinstance(a, dict))
        s = 0.6 * sim(" ".join(str(e.get(k) or "") for k in ("title", "container_title")) + " " + names, key) + \
            0.4 * sim(e.get("raw_text"), printed)
        if s > bs:
            best, bs = (e, c), s
    return best, bs


LABEL = re.compile(r"^(pp|p|vol|no|n[°º]|ص|ج|جـ|مج|ع|العدد|ط)(?=[\s.:]|[0-9٠-٩])\.?\s*:?\s*", re.I)


def strip_label(v):
    return LABEL.sub("", str(v).strip()) if v is not None else v


def reducto_field(e, field, gold_has_title):
    if field == "authors":
        names = []
        for a in e.get("authors") or []:
            if isinstance(a, dict):
                names.append(" ".join(x for x in (a.get("surname"), a.get("given_names")) if x) or a.get("name_as_printed"))
        return " ; ".join(n for n in names if n) or None
    if field == "title":
        return e.get("title")
    if field == "source":
        return e.get("container_title") if gold_has_title else (e.get("title") or e.get("container_title"))
    if field == "year":
        return e.get("year_gregorian") or e.get("year_as_printed") or e.get("year_hijri")
    if field == "pages":
        return e.get("pages")
    if field in ("volume", "issue", "publisher", "place"):
        return e.get(field)
    if field == "link":
        return e.get("url")
    if field == "other":
        parts = []
        for k in ("editors", "translators"):
            parts += [f"{k}: {v}" for v in (e.get(k) or []) if v]
        if e.get("edition"):
            parts.append(f"edition: {e['edition']}")
        return " ; ".join(parts) or None
    return None


OUR = {"authors": ["authors"], "title": ["article-title", "chapter-title"], "source": ["source"], "year": ["year"],
       "pages": ["page-range", "fpage"], "volume": ["volume"], "issue": ["issue"], "publisher": ["publisher-name"],
       "place": ["publisher-loc"], "link": ["uri", "ext-link"], "other": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true", help="print every field for hand judging")
    a = ap.parse_args()
    units = [u for u in json.loads((OUT / "units59.json").read_text()) if "cites" in u["sets"]]
    draw = {x["i"]: x for x in json.loads((PROOF / "cites_draw.json").read_text())["sample"]}
    score = {x["i"]: x for x in json.loads((PROOF / "cites_score.json").read_text())["items"]}
    judge = json.loads(JUDGE.read_text()) if JUDGE.exists() else {}
    res = {"ours": Counter(), "std": Counter(), "deep": Counter()}
    full = Counter()
    rows = []
    for u in units:
        for i in u["cites"]:
            d, s = draw[i], score[i]
            ours = dict((k, v) for k, v in d["fields"])
            gold_has_title = "title" in s["verdicts"]
            row = dict(i=i, page=u["id"], printed=d["printed"], ours=s["verdicts"], ours_all_right=s["all_right"])
            full["ours"] += s["all_right"]
            for k, v in s["verdicts"].items():
                if k != "citation":
                    res["ours"][(k, v)] += 1
            for mode in ("std", "deep"):
                ents = entries(mode, u["id"])
                if ents is None:
                    continue
                key = " ".join(str(ours.get(x) or "") for x in ("article-title", "chapter-title", "source", "authors"))
                key += " " + " ".join(s["notes"].get(x, "") for x in ("source", "title"))
                be, bs = best_entry(ents, d["printed"], key)
                e, cit = be if be else ({}, {})
                fv = {}
                allr = True
                for k in s["verdicts"]:
                    if k == "citation":
                        continue
                    rv = reducto_field(e, k, gold_has_title)
                    ov = next((ours[x] for x in OUR.get(k, []) if x in ours), None)
                    key = f"{i}/{k}/{mode}"
                    if key in judge:
                        v = judge[key]["verdict"]
                    elif rv in (None, "", []):
                        v = "missing"
                    elif s["verdicts"][k] == "right" and ov is not None and norm(strip_label(rv)) == norm(ov):
                        v = "right"   # a label printed before the value (pp. ص ج Vol. No.) is not counted
                    else:
                        v = "?"
                    fv[k] = dict(reducto=rv, ours=ov, verdict=v, boxes=len(cit.get(
                        {"source": "container_title" if gold_has_title else "title", "link": "url", "year": "year_as_printed",
                         "other": "editors"}.get(k, k), []) or []))
                    res[mode][(k, v)] += 1
                    allr &= v == "right"
                full[mode] += allr
                row[mode] = dict(match=round(bs, 2), raw=e.get("raw_text"), fields=fv, all_right=allr,
                                 entries_on_page=len(ents))
            rows.append(row)
            if a.dump:
                print(f"\n#{i} {u['id']}  ours all right: {s['all_right']}\n  printed: {d['printed']}")
                for k, v in s["verdicts"].items():
                    print(f"  {k:9s} ours[{v}] {next((ours[x] for x in OUR.get(k, []) if x in ours), None)!r}  notes: {s['notes'].get(k, '')}")
                    for mode in ("std", "deep"):
                        if mode in row and k in row[mode]["fields"]:
                            f_ = row[mode]["fields"][k]
                            print(f"      {mode:4s} [{f_['verdict']}] {f_['reducto']!r}")
    n = len(rows)
    summ = {}
    for who in ("ours", "std", "deep"):
        c = res[who]
        fields = Counter()
        for (k, v), m in c.items():
            fields[v] += m
        summ[who] = dict(citations=n, fully_right=full[who], fields=dict(fields),
                         per_field={k: {v: c[(k, v)] for (kk, v) in c if kk == k} for k in sorted({k for k, _ in c})})
    (OUT / "refs_scores.json").write_text(json.dumps(dict(summary=summ, rows=rows), ensure_ascii=False, indent=1))
    for who, x in summ.items():
        print(who, "fully right", x["fully_right"], "/", x["citations"], "fields", x["fields"])


if __name__ == "__main__":
    main()
