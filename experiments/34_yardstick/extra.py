"""Draw extra documents for strata the random set is thin in, from the MARC catalogue index (experiment 29).

    python extra.py            -> out/extra_ids.txt (+ out/extra_draw.json: why each was drawn)
    inkscript fetch --id-file out/extra_ids.txt --out out/extra --workers 2
    python extra.py --classify -> out/extra_kinds.json; born-digital documents are moved aside to out/extra_bd/

Draws (seed 34, Arabic records with a year, journals already in the pool skipped, one document per journal
within a stratum):
  * experiment 28's 78 "fresh" scans (their files were no longer on disk): ids_fresh.txt, as drawn there;
  * pre-1970: 24 documents (16 before 1960, 8 in the 1960s);
  * magazines laid out like newspapers (Mandumah holds no newspapers: no record type, no journal named جريدة,
    and every S3 prefix is an article id): the cultural monthlies المعرفة, الموقف الأدبي, المجلة, الثقافة,
    الأديب, الآداب — 14 documents, 1960-1999;
  * equations: Economics, Management, Business, Sport Sciences, Psychology, Geography 1975-2009 (the archive has
    no science journals; formulas sit in these): 24 documents;
  * Quran and vowelled text: Islamic Studies, Quranic Studies, Hadith, Islamic Jurisprudence, Poetry before 2000:
    12 documents.
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import zlib
from collections import defaultdict
from pathlib import Path

MAIN = Path("/home/yassine/inkscript")
OUT = MAIN / "experiments/34_yardstick/out"
CAT = Path.home() / ".cache/inkscript/catalogue/catalogue.sqlite"
MAGAZINES = ("المعرفة", "الموقف الأدبي", "المجلة", "الثقافة", "الأديب", "الآداب")
EQ_FIELDS = ("Economics", "Management", "Business", "Sport Sciences", "Psychology, Applied", "Geography",
             "Demography", "Environmental Studies")
ISLAMIC = ("Islamic Studies", "Quranic Studies", "Hadith", "Islamic Jurisprudence", "Poetry", "Islamic Creed")


def year(r) -> int | None:
    y = "".join(c for c in r.get("year", "") if c.isdigit())[:4]
    return int(y) if len(y) == 4 else None


def records():
    c = sqlite3.connect(f"file:{CAT}?mode=ro", uri=True)
    stems = defaultdict(list)
    for s, b, p in c.execute("select stem,bid,pos from pdf"):
        stems[(b, p)].append(s)
    for bid, data in c.execute("select bid,data from blk"):
        for pos, r in enumerate(json.loads(zlib.decompress(data))):
            for s in stems.get((bid, pos), []):
                yield s, r


def draw() -> int:
    pool = json.loads((OUT / "pool.json").read_text()) if (OUT / "pool.json").exists() else {}
    fresh = [l.strip() for l in (MAIN / "experiments/28_scale/out/ids_fresh.txt").read_text().splitlines() if l.strip()]
    seen_j = {p["journal"] for p in pool.values()}
    buckets = defaultdict(list)
    for s, r in records():
        if "ara" not in r.get("lang", ["ara"]) or s in pool or s in fresh:
            continue
        if r.get("type", "") not in ("بحوث ومقالات", "نصوص أدبية", "افتتاحيات", "عروض كتب"):
            continue
        y = year(r)
        if not y:
            continue
        jt = r.get("journal", {}).get("title", "")
        f = (r.get("journal", {}).get("fields_en") or [""])[0]
        if jt in MAGAZINES and 1960 <= y <= 1999:
            buckets["magazine"].append((s, jt, y, f))
        if jt in seen_j:
            continue
        if y < 1960:
            buckets["pre1960"].append((s, jt, y, f))
        elif y < 1970:
            buckets["1960s"].append((s, jt, y, f))
        if f in EQ_FIELDS and 1975 <= y <= 2009:
            buckets["equations"].append((s, jt, y, f))
        if f in ISLAMIC and y < 2000:
            buckets["islamic"].append((s, jt, y, f))
    rnd = random.Random(34)
    want = dict(pre1960=16, **{"1960s": 8}, magazine=14, equations=24, islamic=12)
    picked, why = [], {}
    for k, n in want.items():
        items = buckets[k][:]
        rnd.shuffle(items)
        used_j = defaultdict(int)
        cap = 3 if k == "magazine" else 1
        for s, jt, y, f in items:
            if len([x for x in picked if why[x]["stratum"] == k]) >= n:
                break
            if s in why or used_j[jt] >= cap:
                continue
            used_j[jt] += 1
            picked.append(s)
            why[s] = dict(stratum=k, journal=jt, year=y, field=f)
        print(k, len(buckets[k]), "candidates,", sum(1 for x in why.values() if x["stratum"] == k), "drawn")
    for s in fresh:
        why.setdefault(s, dict(stratum="exp28-fresh"))
    ids = fresh + picked
    (OUT / "extra_ids.txt").write_text("\n".join(ids) + "\n")
    (OUT / "extra_draw.json").write_text(json.dumps(why, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(ids), "ids")
    return 0


def classify() -> int:
    """Experiment 19's rule: a document is born-digital when most pages are (real fonts carry at least half as many
    words as Azure's Dummy layer); those are moved to out/extra_bd/ and left out of the pool."""
    import pymupdf
    from inkscript.pdf.native import born_digital
    kinds = {}
    (OUT / "extra_bd").mkdir(exist_ok=True)
    for d in sorted((OUT / "extra").iterdir()):
        pdf, js = d / f"{d.name}.pdf", d / f"{d.name}.json"
        if not (pdf.exists() and js.exists()):
            kinds[d.name] = "missing"
            continue
        try:
            doc = pymupdf.open(str(pdf))
            nb = sum(born_digital(pg) for pg in doc)
            k = "born-digital" if nb > len(doc) / 2 else "scan"
            doc.close()
        except Exception as e:
            k = f"error: {e}"[:100]
        kinds[d.name] = k
        if k != "scan":
            d.rename(OUT / "extra_bd" / d.name)
    (OUT / "extra_kinds.json").write_text(json.dumps(kinds, indent=1))
    from collections import Counter
    print(Counter(v if not v.startswith("error") else "error" for v in kinds.values()))
    return 0


if __name__ == "__main__":
    sys.exit(classify() if "--classify" in sys.argv else draw())
