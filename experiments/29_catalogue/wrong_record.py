"""Would the check notice a wrong record? Each of the 205 documents is given its neighbour's record (the next id in
order, another article) and the front matter is read again; the verdicts are counted. Also the right record, for the
false alarms. Structure only (no XML, no scan: stroke widths are not needed for the front matter).

    PYTHONPATH=src .venv/bin/python experiments/29_catalogue/wrong_record.py   -> out/wrong_record.json
"""
import json
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SET28 = Path("/home/yassine/inkscript/experiments/28_scale/out")


def one(args):
    stem, other = args
    from inkscript.enrich.catalogue import open_catalogue
    from inkscript.enrich.document import load
    from inkscript.enrich.structure import analyse, read_meta
    cat = open_catalogue()
    doc = load(SET28 / "azure" / stem / f"{stem}.json")
    res = {}
    for kind, s in (("right", stem), ("wrong", other)):
        rec = cat.get(s)
        if not rec:
            continue
        meta = read_meta(stem, [SET28 / "azure" / stem, SET28 / "gemini"])
        meta["catalogue"] = rec
        d = dict(doc)
        d.pop("structure", None)
        fr = analyse(d, meta, None)["front"]
        res[kind] = fr["catalogue_check"]
    return stem, res


def main():
    stems = sorted(p.name for p in (SET28 / "azure").iterdir())
    pairs = [(s, stems[(i + 1) % len(stems)]) for i, s in enumerate(stems)]
    with Pool(3) as pool:
        rows = dict(pool.imap_unordered(one, pairs))
    count = {k: Counter(r[k]["verdict"].split(":")[0].split(";")[0] for r in rows.values() if k in r) for k in ("right", "wrong")}
    (OUT / "wrong_record.json").write_text(json.dumps(dict(count=count, docs=rows), ensure_ascii=False, indent=1))
    print(json.dumps(count, indent=1))
    for s, r in sorted(rows.items()):
        if "wrong" in r and r["wrong"]["verdict"].startswith("agrees"):
            print("wrong record accepted:", s, r["wrong"])


if __name__ == "__main__":
    main()
