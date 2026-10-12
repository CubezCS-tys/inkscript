"""Score readers on experiment 33's test material -> out/results.json.

    out/env/bin/python evaluate.py MODEL_TAG [MODEL_TAG ...]
For every model tag T it reads (when present):
  out/preds/test_clean_T.jsonl, out/preds/test_deg_T.jsonl   gold line crops of the born-digital test split
  out/preds/scan_T.jsonl                                      the lines of experiment 19's judged words (real scans)
  out/pages/T.jsonl, out/pages/T_scan.jsonl                   whole pages, kraken's own line finder
Azure is scored on the same lines from its own JSON (its words that fall on each gold line).
Rates are pooled (sum of edits / sum of reference length); 95% intervals bootstrap the documents (1000 draws).
"""
import json, random, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textnorm import NORMS, faithful, search, HARAKAT, PUNCT, is_arabic_line
from rapidfuzz.distance import Levenshtein
import re

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
B = 1000


def boot(per_doc: dict, num: str, den: str) -> dict:
    """per_doc: doc -> dict of sums. Pooled rate and a 95% interval over documents."""
    docs = list(per_doc); n = sum(per_doc[d][num] for d in docs); dn = sum(per_doc[d][den] for d in docs)
    if not dn:
        return dict(rate=None, lo=None, hi=None, n=0, docs=0)
    r = random.Random(33); vals = []
    for _ in range(B):
        s = [docs[r.randrange(len(docs))] for _ in docs]
        a = sum(per_doc[d][num] for d in s); b = sum(per_doc[d][den] for d in s)
        if b: vals.append(a / b)
    vals.sort()
    return dict(rate=n / dn, lo=vals[int(0.025 * len(vals))], hi=vals[int(0.975 * len(vals)) - 1], n=dn, docs=len(docs))


def line_scores(rows, get_pred):
    """rows: records with doc, gold. Returns {norm: {cer, wer}} plus empty-line counts."""
    out = {}
    for norm, f in NORMS.items():
        pd = defaultdict(lambda: defaultdict(int))
        for r in rows:
            g = f(r["gold"]); p = f(get_pred(r) or "")
            d = pd[r["doc"]]
            d["ce"] += Levenshtein.distance(g, p); d["cn"] += len(g)
            d["we"] += Levenshtein.distance(g.split(), p.split()); d["wn"] += len(g.split())
            d["lines"] += 1; d["empty"] += (not p.strip()) and bool(g.strip())
            d["exact"] += g == p
        out[norm] = dict(cer=boot(pd, "ce", "cn"), wer=boot(pd, "we", "wn"),
                         empty=sum(d["empty"] for d in pd.values()), lines=sum(d["lines"] for d in pd.values()),
                         exact=sum(d["exact"] for d in pd.values()))
    return out


def load_preds(path):
    if not Path(path).exists():
        return None
    return {Path(r["img"]).name: r for r in map(json.loads, open(path))}


def decade(y):
    return f"{(y // 10) * 10}s" if y else "?"


def born_digital(tags):
    data = [json.loads(l) for l in open(OUT / "data.jsonl")]
    meta = json.load(open(OUT / "meta.json"))
    test = [r for r in data if r["split"] == "test" and not r.get("suspect")]
    for r in test:
        r["decade"] = decade(meta.get(r["doc"], {}).get("year")); r["arabic"] = is_arabic_line(r["gold"])
    res = {"n_lines": len(test), "n_docs": len({r["doc"] for r in test}), "n_journals": len({r["journal"] for r in test}),
           "n_suspect": sum(r["split"] == "test" and bool(r.get("suspect")) for r in data)}
    readers = {"azure": {"clean": lambda r: r["azure"], "deg": None}}
    for t in tags:
        readers[t] = {}
        for v in ("clean", "deg"):
            p = load_preds(OUT / "preds" / f"test_{v}_{t}.jsonl")
            if p is not None:
                suf = ".png" if v == "clean" else "_d.jpg"
                readers[t][v] = (lambda p, suf: (lambda r: (p.get(r["id"] + suf) or {}).get("text")))(p, suf)
    subsets = {"all": lambda r: True, "arabic": lambda r: r["arabic"]}
    for k in sorted({r["kind"] for r in test}):
        subsets[f"kind:{k}"] = (lambda k: lambda r: r["kind"] == k)(k)
    for dc in sorted({r["decade"] for r in test}):
        subsets[f"decade:{dc}"] = (lambda dc: lambda r: r["decade"] == dc and r["arabic"])(dc)
    for name, rd in readers.items():
        for v, fn in rd.items():
            if fn is None:
                continue
            res[f"{name}/{v}"] = {s: line_scores([r for r in test if sel(r)], fn) for s, sel in subsets.items()}
    return res


def align_span(a: str, b: str, lo: int, hi: int) -> tuple[int, int]:
    """Map the span [lo, hi) of string a onto string b through a character alignment."""
    m = [0] * (len(a) + 1); m[len(a)] = len(b)
    for tag, i1, i2, j1, j2 in Levenshtein.opcodes(a, b):
        for k in range(i2 - i1):
            if tag == "equal":
                m[i1 + k] = j1 + k
            elif tag == "replace":
                m[i1 + k] = j1 + min(int(k * (j2 - j1) / (i2 - i1)), j2 - j1 - 1)
            else:                                                       # delete
                m[i1 + k] = j1
    if hi <= lo:
        return m[lo], m[lo]
    return m[lo], m[hi - 1] + 1


def word_in(pred: str, lo: int, hi: int) -> str:
    """The whitespace tokens of pred that the span [lo, hi) touches."""
    toks = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", pred)]
    got = [t for s, e, t in toks if s < max(hi, lo + 1) and e > lo]
    return " ".join(got)


def letters(s):
    """The judge's criterion in experiment 19: letters and hamza forms count; short vowels, kashida, punctuation don't.
    ى and ي are folded too: the judge cannot tell them apart (19's calibration: its only misses were ى/ي, and it read
    the owner's فى as في), so its truth leans to Azure's choice there."""
    return re.sub(r"\s+", "", PUNCT.sub("", HARAKAT.sub("", faithful(s)))).replace("\u0649", "\u064a")


def scans(tags):
    rows = [json.loads(l) for l in open(OUT / "scan" / "scan.jsonl")]
    res = {}
    for t in tags:
        p = load_preds(OUT / "preds" / f"scan_{t}.jsonl")
        if p is None:
            continue
        words = defaultdict(lambda: defaultdict(float)); wordsw = defaultdict(lambda: defaultdict(float))
        lines = {}
        strata = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        examples = []
        for r in rows:
            pred = (p.get(r["id"] + ".png") or {}).get("text") or ""
            lines.setdefault(r["id"].rsplit("_w", 1)[0] + str(r["px"]), (r, pred))
            if r["truth"] is None or r["pos"] is None:
                continue
            # where the judged word sits in kraken's line: align Azure's line to kraken's reading (search-folded
            # alignment is too lossy for positions, so the faithful strings are aligned)
            a = r["line"]; lo, hi = r["pos"]
            plo, phi = align_span(a, pred, lo, hi)
            kw = word_in(pred, plo, phi)
            ok_k = letters(kw) == letters(r["truth"]); ok_a = letters(r["word"]) == letters(r["truth"])        # Azure's word under the same rule
            okf_k = search(kw).replace(" ", "") == search(r["truth"]).replace(" ", "")
            key = ("pre2000" if (r["year"] or 0) < 2000 else "2000+") if r["year"] else "?"
            for grp in ("all", key, f"stratum:{r['stratum']}"):
                for dct, wt in ((words, 1.0), (wordsw, r["w"])):
                    d = dct[(grp, r["doc"])]
                    d["n"] += wt; d["k_err"] += wt * (not ok_k); d["a_err"] += wt * (not ok_a); d["k_err_search"] += wt * (not okf_k)
            examples.append(dict(id=r["id"], truth=r["truth"], azure=r["word"], kraken=kw, ok_k=ok_k, ok_a=ok_a, stratum=r["stratum"],
                                 year=r["year"], line=a, pred=pred))
        out = {}
        for nm, dct in (("unweighted", words), ("weighted", wordsw)):
            groups = sorted({g for g, _ in dct})
            out[nm] = {}
            for g in groups:
                pd = {d: v for (gg, d), v in dct.items() if gg == g}
                out[nm][g] = {"kraken": boot(pd, "k_err", "n"), "kraken_search": boot(pd, "k_err_search", "n"), "azure": boot(pd, "a_err", "n")}
        # silver line CER: kraken against Azure's line, by period
        sil = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        for r, pred in lines.values():
            key = ("pre2000" if (r["year"] or 0) < 2000 else "2000+") if r["year"] else "?"
            if not is_arabic_line(r["line"]):
                continue
            for norm, f in NORMS.items():
                for grp in ("all", key):
                    g = f(r["line"]); q = f(pred); d = sil[norm][(grp, r["doc"])]
                    d["ce"] += Levenshtein.distance(g, q); d["cn"] += len(g)
                    d["we"] += Levenshtein.distance(g.split(), q.split()); d["wn"] += len(g.split())
        out["silver_lines"] = {norm: {g: {"cer": boot({d: v for (gg, d), v in sil[norm].items() if gg == g}, "ce", "cn"),
                                          "wer": boot({d: v for (gg, d), v in sil[norm].items() if gg == g}, "we", "wn")}
                                      for g in sorted({g for g, _ in sil[norm]})} for norm in NORMS}
        out["n_lines"] = len(lines)
        res[t] = out
        json.dump(examples, open(OUT / f"scan_words_{t}.json", "w"), ensure_ascii=False, indent=0)
    return res


def match_pages(gold_lines, pred_lines, scale=1.0):
    """Gold line boxes (points) vs predicted line boxes (px). A predicted line goes to the gold line it overlaps most
    (at least half its height and a third of its width inside); several predictions on one gold line are joined right
    to left. Returns (pairs [(gold, pred_text)], inserted [pred])."""
    gl = [dict(g, px=[v * scale for v in g["bbox"]]) for g in gold_lines]
    got = defaultdict(list); inserted = []
    for p in pred_lines:
        x0, y0, x1, y1 = p["bbox"]; best, bo = None, 0
        for k, g in enumerate(gl):
            gx0, gy0, gx1, gy1 = g["px"]
            ov_y = min(y1, gy1) - max(y0, gy0); ov_x = min(x1, gx1) - max(x0, gx0)
            if ov_y <= 0 or ov_x <= 0:
                continue
            if ov_y < 0.5 * min(y1 - y0, gy1 - gy0) or ov_x < 0.33 * (x1 - x0):
                continue
            sc = ov_x * ov_y
            if sc > bo:
                best, bo = k, sc
        if best is None:
            inserted.append(p)
        else:
            got[best].append(p)
    pairs = [(g, " ".join(q["text"] for q in sorted(got[k], key=lambda q: -q["bbox"][2]))) for k, g in enumerate(gl)]
    return pairs, inserted


def pages(tags):
    res = {}
    sp = json.load(open(OUT / "splits.json"))
    meta = json.load(open(OUT / "meta.json"))
    gold_cache = {}
    test_docs = {json.loads(l)["doc"] for l in open(OUT / "data.jsonl") if '"split": "test"' in l}

    def gold(doc, page):
        if doc not in gold_cache:
            gold_cache[doc] = {p["page"]: p["lines"] for p in json.load(open(OUT / "lines" / f"{doc}.json"))["pages"]}
        return gold_cache[doc].get(page, [])

    def azure_lines(doc, page):
        d = E19 / "docs" / doc if (E19 / "docs" / doc).exists() else OUT / "docs" / doc
        import pymupdf
        az = json.load(open(d / f"{doc}.json")); az = az.get("analyzeResult", az)
        pg = next(p for p in az["pages"] if p["pageNumber"] == page)
        pdf = pymupdf.open(str(d / f"{doc}.pdf")); s = 300 / 72 * pdf[page - 1].rect.width / pg["width"]
        return [dict(bbox=[min(l["polygon"][0::2]) * s, min(l["polygon"][1::2]) * s, max(l["polygon"][0::2]) * s, max(l["polygon"][1::2]) * s],
                     text=l["content"]) for l in pg["lines"]]

    def score(rows_by_doc):
        out = {}
        for norm, f in NORMS.items():
            pd = defaultdict(lambda: defaultdict(int))
            for doc, (pairs, ins) in rows_by_doc.items():
                d = pd[doc]
                for g, ptxt in pairs:
                    gt = f(g["gold"]); pt = f(ptxt)
                    d["ce"] += Levenshtein.distance(gt, pt); d["cn"] += len(gt)
                    d["we"] += Levenshtein.distance(gt.split(), pt.split()); d["wn"] += len(gt.split())
                    d["gold_lines"] += 1; d["dropped"] += not pt.strip()
                for p in ins:
                    pt = f(p["text"]); d["ce_ins"] += len(pt); d["we_ins"] += len(pt.split()); d["inserted"] += bool(pt.strip())
                d["ce_all"] = d["ce"] + d["ce_ins"]; d["we_all"] = d["we"] + d["we_ins"]
            out[norm] = dict(cer=boot(pd, "ce_all", "cn"), wer=boot(pd, "we_all", "wn"), cer_matched=boot(pd, "ce", "cn"),
                             gold_lines=sum(d["gold_lines"] for d in pd.values()), dropped=sum(d["dropped"] for d in pd.values()),
                             inserted=sum(d["inserted"] for d in pd.values()))
        return out

    # born-digital pages: kraken (clean, deg) and Azure (its own lines on the clean render)
    az_rows = {}
    for t in tags + ["__azure__"]:
        path = OUT / "pages" / f"{t}.jsonl"
        if t != "__azure__" and not path.exists():
            continue
        by_var = defaultdict(dict)
        recs = list(map(json.loads, open(path))) if t != "__azure__" else [
            dict(doc=d, page=i["drawn"][0], variant="clean", lines=None) for d, i in sp["docs"].items()
            if i.get("status") == "ok" and i.get("split") == "test" and i.get("drawn") and d in test_docs]
        for r in recs:
            if r["doc"] not in test_docs:
                continue
            gl = [g for g in gold(r["doc"], r["page"]) if g["gold"]]
            pl = r["lines"] if r["lines"] is not None else azure_lines(r["doc"], r["page"])
            by_var[r["variant"]][r["doc"]] = match_pages(gl, pl, 300 / 72)
        name = "azure" if t == "__azure__" else t
        res[name] = {v: score(rows) for v, rows in by_var.items()}
    # real scans, silver: kraken's page against Azure's lines (Azure's lines play gold)
    for t in tags:
        path = OUT / "pages" / f"{t}_scan.jsonl"
        if not path.exists():
            continue
        rows = {}; rows_pre = {}; rows_post = {}
        for r in map(json.loads, open(path)):
            al = azure_lines(r["doc"], r["page"])
            gl = [dict(bbox=[v * 72 / 300 for v in a["bbox"]], gold=a["text"]) for a in al]   # every Azure line (Latin too)
            m = match_pages(gl, r["lines"], 300 / 72)
            rows[r["doc"]] = m
            y = meta.get(r["doc"], {}).get("year")
            (rows_pre if (y or 0) < 2000 else rows_post)[r["doc"]] = m
        res[f"{t}/scan_silver"] = {"all": score(rows), "pre2000": score(rows_pre), "2000+": score(rows_post)}
    return res


if __name__ == "__main__":
    tags = sys.argv[1:]
    res = {"born_digital_lines": born_digital(tags), "scan_words": scans(tags), "pages": pages(tags)}
    json.dump(res, open(OUT / "results.json", "w"), ensure_ascii=False, indent=1)
    bd = res["born_digital_lines"]
    for k, v in bd.items():
        if isinstance(v, dict) and "arabic" in v:
            a = v["arabic"]
            print(f"{k:28} arabic lines CER faithful {a['faithful']['cer']['rate']:.4f} [{a['faithful']['cer']['lo']:.4f}-{a['faithful']['cer']['hi']:.4f}]"
                  f"  search {a['search']['cer']['rate']:.4f}  WER faithful {a['faithful']['wer']['rate']:.4f} search {a['search']['wer']['rate']:.4f}")
    for t, v in res["scan_words"].items():
        for nm in ("unweighted", "weighted"):
            a = v[nm]["all"]
            print(f"scan words {t} {nm}: kraken wrong {a['kraken']['rate']:.4f} [{a['kraken']['lo']:.4f}-{a['kraken']['hi']:.4f}]  azure wrong {a['azure']['rate']:.4f}")
