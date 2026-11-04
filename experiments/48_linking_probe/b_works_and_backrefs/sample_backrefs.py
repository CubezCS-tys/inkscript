"""B2 back-reference sample, seed 4813, stratified by link47's category; for each: the marker's note and the 5 notes
before it, read from the JATS master (fn elements), plus the resolved target's printed citation and note."""
import json, random, re
from collections import defaultdict
import xml.etree.ElementTree as ET
from db import con, OUT
c = con()
MASTERS = {"v33_300_final": "/home/appuser/inkscript/experiments/43_rehearsal/out/v33_300_final/masters",
           "v33_300b_fix3": "/home/appuser/inkscript/experiments/43_rehearsal/out/v33_300b_fix3/masters"}
rows = [dict(r) for r in c.execute("""select m.*, v.stem, v.run from citation_mentions m join versions v using(version_id)
         where v.is_current=1 and v.run in ('v33_300_final','v33_300b_fix3') and m.kind in ('ibid','op_cit','loc_cit')""")]
def cat(r):
    if r["resolve_method"]: return r["resolve_method"]
    return "unresolved:" + (r["unresolved_why"] or "").split(":")[0]
by = defaultdict(list)
for r in rows: by[cat(r)].append(r)
json.dump({k: len(v) for k, v in by.items()}, open(f"{OUT}/backref_categories.json", "w"), indent=1)
ALLOC = {"previous-mention": 10, "previous-mention (chain collapsed)": 10, "same-author-earliest": 9,
         "same-author+title-words": 5, "same-author+page-continuity": 3, "same-author+title-words+page": 2,
         "same-author+year": 2, "title-words": 2, "same-author-latest": 2, "unresolved:no-earlier-full": 8,
         "unresolved:chain-broken": 3, "unresolved:previous-not-parsed": 3, "part-of-citation": 2}
rng = random.Random(4813)
fn_cache = {}
def fns(run, stem):
    k = (run, stem)
    if k not in fn_cache:
        t = ET.parse(f"{MASTERS[run]}/{stem}.jats.xml")
        out = []
        for e in t.iter():
            if e.tag.endswith("fn") and e.get("id"):
                out.append((e.get("id"), " ".join("".join(e.itertext()).split())))
        for e in t.iter():
            if e.tag.endswith("ref") and e.get("id"):
                out.append((e.get("id"), " ".join("".join(e.itertext()).split())))
        fn_cache[k] = out
    return fn_cache[k]
sample = []
for k, n in ALLOC.items():
    pool = sorted(by[k], key=lambda r: r["mention_id"])
    for r in rng.sample(pool, min(n, len(pool))):
        f = fns(r["run"], r["stem"]); ids = [x[0] for x in f]
        i = ids.index(r["container_id"]) if r["container_id"] in ids else None
        before = f[max(0, i - 5):i] if i is not None else []
        tgt = None
        if r["full_mention_pk"]:
            t = c.execute("select mention_id, kind, container_id, printed from citation_mentions where mention_pk=?",
                          (r["full_mention_pk"],)).fetchone()
            tgt = dict(t)
        sample.append(dict(category=k, stem=r["stem"], run=r["run"], mention_id=r["mention_id"], note=r["container_id"],
                           marker=r["marker"], printed=r["printed"], note_text=f[i][1] if i is not None else None,
                           before=before, target=tgt, evidence=r["resolve_evidence"], why=r["unresolved_why"]))
json.dump(sample, open(f"{OUT}/backref_sample.json", "w"), ensure_ascii=False, indent=1)
for j, s in enumerate(sample):
    print(f"\n##{j} [{s['category']}] {s['stem']} {s['note']} marker={s['marker']!r}")
    print("   NOTE:", (s["note_text"] or "")[:260])
    for nid, t in s["before"]: print("      <", nid, t[:200])
    if s["target"]: print("   -> TARGET", s["target"]["container_id"], s["target"]["kind"], (s["target"]["printed"] or "")[:200])
    if s["why"]: print("   WHY:", s["why"])
