"""Experiment 58: Surya 2.5 (CPU, llama.cpp) on six truth pages, scored like Indra and Azure on the same pages.

    ./out/run_surya.sh  (writes out/surya_out/surya_in/results.json)
    /home/appuser/inkscript/.venv/bin/python surya58.py   -> out/indra/surya/<id>.json, out/surya_scores.json
"""
import html as H
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score58_text as T  # noqa: E402

OUT = HERE / "out"


def block_lines(h):
    h = re.sub(r"<br\s*/?>|</p>|</li>|</tr>|</h\d>|</div>|</caption>", "\n", h or "")
    h = re.sub(r"</t[dh]>", " ", h)
    t = H.unescape(re.sub(r"<[^>]+>", "", h))
    return [x.strip() for x in t.split("\n") if x.strip()]


def main():
    res = json.loads((OUT / "surya_out/surya_in/results.json").read_text())
    dst = OUT / "indra/surya"
    dst.mkdir(parents=True, exist_ok=True)
    ids = []
    for name, pages in res.items():
        pg = pages[0] if isinstance(pages, list) else pages
        lines, labels = [], []
        for b in pg.get("blocks", []):
            labels.append(b.get("label"))
            if b.get("skipped"):
                continue
            lines += [dict(text=t) for t in block_lines(b.get("html", ""))]
        (dst / f"{name}.json").write_text(json.dumps(dict(id=name, lines=lines, labels=labels), ensure_ascii=False))
        ids.append(name)
    # score the six pages: Azure, Indra, Surya
    s41 = json.loads((T.E / "41_azure_structure/out/scores.json").read_text())
    arts = {a["stem"]: a for a in T.S.sample()}
    tot = {}
    rows = []
    for r in s41["truth_pages"]:
        pid = f"{r['stem']}_p{r['page']:03d}"
        if pid not in ids:
            continue
        kind, doc, tl = T.S.truth_of(r["stem"], r["page"])
        dig = kind == "bd"
        c = {"azure": [l["text"] for l in T.page_lines(arts[r["stem"]], r["page"])[0]],
             "indra": T.indra_lines("img300", pid), "surya": T.indra_lines("surya", pid)}
        row = dict(id=pid, kind=kind)
        for k, pl in c.items():
            e, n = T.S.bag(T.S.words(pl, dig), T.S.words(tl, dig))
            row[k] = round(e / n, 4)
            tot.setdefault(k, [0, 0])
            tot[k][0] += e
            tot[k][1] += n
        rows.append(row)
        print(row)
    out = dict(rows=rows, totals={k: round(e / n, 4) for k, (e, n) in tot.items()})
    print(out["totals"])
    (OUT / "surya_scores.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
