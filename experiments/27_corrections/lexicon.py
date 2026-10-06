"""A corpus lexicon for the noise experiment: how often each word (Quran matching key) was read by Azure with
confidence >= 0.95, per document, over every Azure reading on disk (experiment 19's 240 random documents and
experiment 16's 160 books). Stored as {key: {doc: count}} so a word's own document can be left out.

    python lexicon.py          -> out/lexicon.json.gz
    python lexicon.py ship     -> src/inkscript/data/lexicon/confident-words.tsv.gz: key <TAB> documents, for every
                                  key read confidently in >= 5 documents (what trust.refine needs; ~22k keys)
"""
import gzip
import json
from collections import defaultdict
from pathlib import Path

from inkscript.enrich.quran import norm

HERE = Path(__file__).resolve().parent
ROOTS = [Path("/home/yassine/inkscript/experiments/19_azure_map/out/docs"),
         Path("/home/yassine/inkscript/experiments/16_feel/out/books/raw")]

def ship(min_docs=5):
    lex = json.load(gzip.open(HERE / "out/lexicon.json.gz", "rt", encoding="utf-8"))
    dst = HERE.parents[1] / "src/inkscript/data/lexicon"
    dst.mkdir(parents=True, exist_ok=True)
    rows = sorted((k, len(v)) for k, v in lex.items() if len(v) >= min_docs)
    body = "# key (Quran matching key, enrich.quran.norm) <TAB> documents in which Azure read it with confidence >= 0.95\n" \
           f"# {len(rows)} keys from 400 documents (experiments 19 and 16), built by experiments/27_corrections/lexicon.py\n" + \
           "".join(f"{k}\t{n}\n" for k, n in rows)
    with gzip.GzipFile(dst / "confident-words.tsv.gz", "wb", mtime=0) as f:
        f.write(body.encode("utf-8"))
    print(len(rows), "keys ->", dst / "confident-words.tsv.gz")


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["ship"]:
        ship()
        sys.exit()
    lex = defaultdict(lambda: defaultdict(int))
    n = 0
    for root in ROOTS:
        for d in sorted(root.iterdir()):
            f = d / f"{d.name}.json"
            if not f.exists():
                continue
            ar = json.loads(f.read_text(encoding="utf-8"))
            ar = ar.get("analyzeResult", ar)
            for p in ar.get("pages", []):
                for w in p.get("words", []):
                    if (w.get("confidence") or 0) >= 0.95:
                        k = norm(w.get("content", ""))
                        if k:
                            lex[k][d.name] += 1
            n += 1
    (HERE / "out").mkdir(exist_ok=True)
    with gzip.open(HERE / "out/lexicon.json.gz", "wt", encoding="utf-8") as f:
        json.dump(lex, f, ensure_ascii=False)
    print(n, "documents,", len(lex), "keys")
