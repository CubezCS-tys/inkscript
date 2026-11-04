"""Experiment 51 helper: print up to N real snippets for a regex from the 600 masters' printed blocks.
usage: snip.py REGEX [N] [context,context]"""
import sys, re
from lxml import etree
import count_masters as CM
rx = re.compile(sys.argv[1], re.M); N = int(sys.argv[2]) if len(sys.argv) > 2 else 4
cs = sys.argv[3].split(",") if len(sys.argv) > 3 else None
arts = set(); shown = 0
for f in CM.FILES:
    stem = f.rsplit("/", 1)[1].replace(".jats.xml", "")
    for page, ctx, t in CM.blocks(etree.parse(f)):
        if cs and ctx not in cs: continue
        m = rx.search(t)
        if not m: continue
        arts.add(stem)
        if shown < N:
            a = max(0, m.start() - 50); print(f"{stem} p{page} {ctx}: {t[a:a+170]}"); shown += 1
print("articles:", len(arts))
