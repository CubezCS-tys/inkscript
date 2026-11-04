"""Experiment 51: page furniture and other non-article ink in the 600 masters' ALTO (roles per TextBlock). Read-only.
Writes out/alto_counts.json: per role, articles / blocks / up to 3 examples (stem, page, text <= 120 chars)."""
import glob, json, re, collections
from pathlib import Path
from lxml import etree
HERE = Path(__file__).resolve().parent
R = HERE.parent / "43_rehearsal" / "out"
FILES = sorted(glob.glob(str(R / "v33_300_final/masters/*.alto.xml"))) + sorted(glob.glob(str(R / "v33_300b_fix3/masters/*.alto.xml")))
NS = "{http://www.loc.gov/standards/alto/ns-v4#}"
C = collections.Counter(); A = collections.defaultdict(set); EX = collections.defaultdict(list)
for f in FILES:
    stem = Path(f).name.replace(".alto.xml", "")
    for ev, pg in etree.iterparse(f, tag=NS + "Page"):
        pno = pg.get("PHYSICAL_IMG_NR") or pg.get("ID")
        printed = pg.get("PRINTED_IMG_NR")
        if printed: C["page.PRINTED_IMG_NR"] += 1; A["page.PRINTED_IMG_NR"].add(stem)
        for tb in pg.iter(NS + "TextBlock"):
            for r in (tb.get("TAGREFS") or "").split():
                if not r.startswith("role."): continue
                C[r] += 1; A[r].add(stem)
                if len(EX[r]) < 3 and (not EX[r] or EX[r][-1][0] != stem):
                    t = " ".join(s.get("CONTENT", "") for s in tb.iter(NS + "String"))[:120]
                    if t.strip(): EX[r].append((stem, pno, t))
        for s in pg.iter(NS + "String"):
            if s.get("STYLE") or s.get("STYLEREFS"): C["string.style"] += 1; A["string.style"].add(stem)
        pg.clear()
out = {k: {"articles": len(A[k]), "n": C[k], "examples": EX[k]} for k in sorted(C)}
json.dump(out, open(HERE / "out" / "alto_counts.json", "w"), ensure_ascii=False, indent=1)
for k, v in out.items(): print(k, v["articles"], v["n"], v["examples"][:1])
