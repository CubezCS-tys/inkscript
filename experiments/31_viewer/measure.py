"""Experiment 31: how much of each article links back to the page, and how fast the viewer's data is made.

    python experiments/31_viewer/measure.py OUT_DIR [--json experiments/31_viewer/out/measure.json]

For every document under OUT_DIR (any depth): the share of the article's words that link to their ALTO word
(the JATS has no word ids; the viewer matches each block's words in reading order), the share of the page's
non-furniture blocks that have a place in the article, and the time to read the ALTO file and render the article.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from lxml import etree

from inkscript.viewer.outputs import FURNITURE, Outputs

ap = argparse.ArgumentParser()
ap.add_argument("out_dir")
ap.add_argument("--json")
a = ap.parse_args()
o = Outputs(a.out_dir)
rows = []
for stem in o.docs():
    d = o.doc(stem)
    t = time.perf_counter()
    d.summary()
    t_alto = time.perf_counter() - t
    t = time.perf_counter()
    art = d.article()
    t_art = time.perf_counter() - t
    h = etree.HTML(art["html"])
    placed = {b for e in h.xpath("//*[@data-b]") for b in e.get("data-b").split()}
    body = [b["id"] for n in d.page_numbers() for b in d.page(n)["blocks"] if b["role"] not in FURNITURE]
    words = sum(len(ln["w"]) for n in d.page_numbers() for b in d.page(n)["blocks"] if b["role"] not in FURNITURE
                for ln in b["lines"])
    rows.append(dict(id=stem, pages=len(d.page_numbers()), article_words=art["words"], linked=art["linked"],
                     page_words=words, blocks=len(body), blocks_placed=sum(b in placed for b in body),
                     alto_s=round(t_alto, 3), article_s=round(t_art, 3), html_kb=len(art["html"]) // 1024))
    o._open.clear()
tot = lambda k: sum(r[k] for r in rows)
worst = sorted(rows, key=lambda r: r["linked"] / max(1, r["article_words"]))[:5]
print(f"{len(rows)} documents, {tot('pages')} pages")
print(f"article words linked to their page word: {tot('linked'):,} / {tot('article_words'):,} "
      f"({tot('linked') / tot('article_words'):.2%})")
print(f"non-furniture blocks with a place in the article: {tot('blocks_placed'):,} / {tot('blocks'):,} "
      f"({tot('blocks_placed') / tot('blocks'):.2%})")
big = max(rows, key=lambda r: r["pages"])
print(f"longest: {big['id']} {big['pages']} pages: ALTO read {big['alto_s']} s, article {big['article_s']} s, "
      f"{big['html_kb']} KB of HTML")
print("lowest link rates:", ", ".join(f"{r['id']} {r['linked']}/{r['article_words']}" for r in worst))
if a.json:
    Path(a.json).parent.mkdir(parents=True, exist_ok=True)
    Path(a.json).write_text(json.dumps(rows, indent=1), encoding="utf-8")
sys.exit(0)
