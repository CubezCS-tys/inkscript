"""Score the VLM smoke test (vlm_out.jsonl) and Kraken on the same items -> out/vlm/score.json.

    out/env/bin/python vlm_score.py [KRAKEN_TAGS=ftB,ppB]
Lines: characters different from Azure's line (silver), and the judged word right or wrong against the ink, the same
way evaluate.py scores Kraken. Pages: word bags against Azure's page (silver): Azure words the reader left out
("skipped"), reader words Azure never read ("invented", which includes the reader's own misreadings), and loops (the
most times any 4-word run repeats). Kraken's pages are its whole-page runs with its own line finder (fullpage.py).
"""
import json, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textnorm import faithful, search, is_arabic_line
from evaluate import align_span, word_in, letters
from rapidfuzz.distance import Levenshtein

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
tags = (sys.argv[1] if len(sys.argv) > 1 else "ftB,ppB").split(",")
vlm = {(r["kind"], r["id"]): r for r in map(json.loads, open(OUT / "vlm" / "vlm_out.jsonl"))}
scan = {json.loads(l)["id"]: json.loads(l) for l in open(OUT / "scan" / "scan.jsonl")}
kr = {t: {Path(j["img"]).stem: j["text"] for j in map(json.loads, open(OUT / "preds" / f"scan_{t}.jsonl"))} for t in tags}


def loops(text):
    w = text.split(); c = Counter(tuple(w[i:i + 4]) for i in range(len(w) - 3))
    return max(c.values()) if c else 0


res = {"lines": {}, "pages": {}, "examples": []}
readers = {"vlm": lambda i: re.sub(r"\s+", " ", vlm[("line", i)]["text"]).strip()} | {t: (lambda t: lambda i: kr[t].get(i, ""))(t) for t in tags}
for name, get in readers.items():
    ce = cn = wrong = n = lat = 0
    for (kind, i), r in vlm.items():
        if kind != "line":
            continue
        s = scan[i]; p = get(i)
        g = faithful(s["line"]); q = faithful(p)
        ce += Levenshtein.distance(g, q); cn += len(g)
        lo, hi = s["pos"]; plo, phi = align_span(s["line"], p, lo, hi)
        wrong += letters(word_in(p, plo, phi)) != letters(s["truth"]); n += 1
        lat += bool(re.search(r"[A-Za-z]", p)) and not re.search(r"[A-Za-z]", s["line"])
    res["lines"][name] = dict(cer_vs_azure=ce / cn, judged_word_wrong=wrong / n, n=n, latin_drift=lat)
res["lines"]["azure"] = dict(judged_word_wrong=sum(letters(scan[i]["word"]) != letters(scan[i]["truth"]) for k, i in vlm if k == "line") / res["lines"]["vlm"]["n"])
for (kind, i), r in vlm.items():
    if kind == "line":
        s = scan[i]
        res["examples"].append(dict(id=i, azure=s["line"], vlm=r["text"], **{t: kr[t].get(i, "") for t in tags},
                                    word=s["word"], truth=s["truth"], stratum=s["stratum"]))
# pages
pages = {}
for t in tags:
    pj = OUT / "pages" / f"{t}_scan.jsonl"
    if pj.exists():
        for r in map(json.loads, open(pj)):
            pages.setdefault(t, {})[f"{r['doc']}_p{r['page']}"] = " ".join(l["text"] for l in r["lines"])
for name in ["vlm"] + [t for t in tags if t in pages]:
    sk = inv = tot_a = tot_r = 0; lp = []
    for (kind, i), r in vlm.items():
        if kind != "page":
            continue
        doc, pn = i.rsplit("_p", 1)
        az = json.load(open(E19 / "docs" / doc / f"{doc}.json")); az = az.get("analyzeResult", az)
        pg = next(p for p in az["pages"] if p["pageNumber"] == int(pn))
        a = Counter(search(w["content"]) for w in pg["words"]); a.pop("", None)
        text = r["text"] if name == "vlm" else pages[name].get(i, "")
        b = Counter(w for w in search(text).split()); lp.append(loops(search(text)))
        sk += sum((a - b).values()); inv += sum((b - a).values()); tot_a += sum(a.values()); tot_r += sum(b.values())
    res["pages"][name] = dict(skipped=sk / tot_a, invented=inv / max(tot_r, 1), azure_words=tot_a, reader_words=tot_r,
                              max_loop=max(lp), pages_with_loop=sum(x >= 3 for x in lp),
                              seconds=sum(r["seconds"] for (k, i), r in vlm.items() if k == "page") if name == "vlm" else None)
json.dump(res, open(OUT / "vlm" / "score.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ("lines", "pages")}, indent=1))
