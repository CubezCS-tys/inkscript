"""What the structure step set aside as page furniture (ALTO roles pageHeader / pageFooter / pageNumber; kept out of
the JATS text), sorted into: page numbers; running heads (the same text on 3+ pages, or the journal/author/title);
and LONE blocks — text with letters set aside only once or twice in the document, which the furniture rule took for
its place alone ("short text in the top 8% / bottom 6%"). Lone blocks are mostly content (a heading opening a page,
a table's header row, a last line of a footnote); out/furniture.json lists them for looking.
    .venv/bin/python experiments/28_scale/furniture.py
"""
import glob, json, re
from collections import Counter
from pathlib import Path
from lxml import etree
HERE = Path(__file__).resolve().parent; SET = HERE / "out" / "set"
A = "{http://www.loc.gov/standards/alto/ns-v4#}"
norm = lambda s: re.sub(r"[^ء-يa-zA-Z]", "", s or "")
res = {}; tot = Counter()
for f in sorted(SET.glob("w*/*.alto.xml")):
    stem = f.name[:-9]; t = etree.parse(str(f)); blocks = []
    for pg in t.iter(A + "Page"):
        for b in pg.iter(A + "TextBlock"):
            r = b.get("TAGREFS") or ""
            role = next((x[5:] for x in r.split() if x.startswith("role.")), "")
            if role in ("pageHeader", "pageFooter", "pageNumber"):
                txt = " ".join(s.get("CONTENT") for s in b.iter(A + "String"))
                blocks.append((int(pg.get("PHYSICAL_IMG_NR")), role, txt, len(list(b.iter(A + "String")))))
    c = Counter(norm(x[2]) for x in blocks)
    lone = [(p, r, x, n) for p, r, x, n in blocks if len(norm(x)) >= 3 and c[norm(x)] <= 2]
    rep = [b for b in blocks if len(norm(b[2])) >= 3 and c[norm(b[2])] > 2]
    num = [b for b in blocks if len(norm(b[2])) < 3]
    res[stem] = dict(blocks=len(blocks), numbers=len(num), running=len(rep), lone=len(lone), lone_words=sum(x[3] for x in lone),
                     lone_examples=[(p, r, x[:80]) for p, r, x, n in lone[:12]],
                     running_texts=Counter(x[2][:60] for p, r, x, n in rep).most_common(6))
    tot.update(blocks=len(blocks), numbers=len(num), running=len(rep), lone=len(lone), lone_words=res[stem]["lone_words"],
               docs_with_lone=bool(lone))
(HERE / "out" / "furniture.json").write_text(json.dumps(dict(total=dict(tot), docs=res), ensure_ascii=False, indent=1))
print(dict(tot))
