#!/usr/bin/env python3
"""Audit steps 2, 4, 7, 8: the split, leakage into what the labeller saw, the money, the full inputs."""
import json, re, glob, os, collections, hashlib, random
L = "/home/appuser/ai-search-eval-archive/2026-11-23-library-map"
def load(p): return [json.loads(l) for l in open(p, encoding="utf-8")]
dev, test = load(f"{L}/pilot/sets/dev.jsonl"), load(f"{L}/pilot/sets/test.jsonl")
seen = load(f"{L}/pilot/sets/test_seen_journals.jsonl")
fold = lambda s: re.sub(r"[ً-ْـ\W_]+", "", (s or "").replace("أ","ا").replace("إ","ا").replace("آ","ا").replace("ى","ي").replace("ة","ه")).lower()
print("== 2. SPLIT")
print("ids: dev", len(dev), "test", len(test), "seen", len(seen), "| dev∩test", len({r['doc_id'] for r in dev} & {r['doc_id'] for r in test}), "| dev∩seen", len({r['doc_id'] for r in dev} & {r['doc_id'] for r in seen}))
for key in ("journal_code", "split_unit"):
    d = {r.get(key) for r in dev if r.get(key)}; t = {r.get(key) for r in test if r.get(key)}
    print(f"   {key}: dev {len(d)} test {len(t)} shared {len(d & t)}", sorted(d & t)[:8])
dn = collections.defaultdict(set); tn = collections.defaultdict(set)
for r in dev: dn[fold(r.get("journal_name"))].add(r.get("journal_code"))
for r in test: tn[fold(r.get("journal_name"))].add(r.get("journal_code"))
sh = [n for n in dn if n and n in tn]
print("   folded journal NAME on both sides:", len(sh), "| records in test with such a name:", sum(1 for r in test if fold(r.get("journal_name")) in sh), "| examples:", [(n[:25], sorted(dn[n])[:2], sorted(tn[n])[:2]) for n in sh[:4]])
def uni(r):
    t = r.get("thesis")
    if isinstance(t, dict): return fold(t.get("university") or t.get("c"))
    return None
du = {uni(r) for r in dev if uni(r)}; tu = {uni(r) for r in test if uni(r)}
print("   thesis universities: dev", len(du), "test", len(tu), "shared", len(du & tu), "| thesis field sample:", next((r.get("thesis") for r in test if r.get("thesis")), None))
print("   split_unit kinds test:", collections.Counter((r.get("split_unit") or "")[:2] for r in test).most_common(), "dev:", collections.Counter((r.get("split_unit") or "")[:2] for r in dev).most_common())
# sample_60k overlap
s60 = set()
for l in open(f"{L}/shared/sample_60k.jsonl", encoding="utf-8"):
    try: s60.add(json.loads(l).get("doc_id"))
    except Exception: pass
print("   sample_60k size", len(s60), "| test in sample_60k:", sum(1 for r in test if r["doc_id"] in s60), "| dev in sample_60k:", sum(1 for r in dev if r["doc_id"] in s60))
# near duplicates by folded title
dt = collections.defaultdict(list)
for r in dev: dt[fold(r.get("title"))].append(r["doc_id"])
nd = [(r["doc_id"], dt[fold(r.get("title"))][0], r.get("title")[:50]) for r in test if len(fold(r.get("title"))) > 12 and fold(r.get("title")) in dt]
print("   test titles identical (folded) to a dev title:", len(nd), nd[:4])
print("   held_out_journals.txt lines:", sum(1 for _ in open(f"{L}/pilot/sets/held_out_journals.txt")))
print("== 4. LEAKAGE into what the labeller saw")
inp = load(f"{L}/pilot/sets/test_inputs_for_labeller_v2.jsonl")
print("   input keys:", sorted(inp[0].keys()))
T = {r["doc_id"]: r for r in test}
bad = collections.Counter()
fos_vals = set()
for r in test:
    for k in ("fields_of_study_ar", "fields_of_study_en"):
        for v in (r.get(k) or []): fos_vals.add(v)
for x in inp:
    s = json.dumps(x, ensure_ascii=False)
    t = T.get(x.get("doc_id") or x.get("id"))
    if not t: bad["id not in test"] += 1; continue
    jn = t.get("journal_name") or ""
    if jn and len(jn) > 8 and jn in s: bad["journal name in input"] += 1
    if any(k in x for k in ("journal_name", "journal_code", "fields_of_study_ar", "group", "strata", "proxy_field", "strat_subject_proxy", "split_unit")): bad["a forbidden key present"] += 1
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", s): bad["e-mail in input"] += 1
print("   v2 inputs:", len(inp), dict(bad))
# prompts actually sent in the frozen test run
pfiles = glob.glob(f"{L}/pilot/runs/test_frozen/*/prompts/*") + glob.glob(f"{L}/pilot/runs/test_frozen/*/*/prompts/*")
print("   prompt files in test_frozen:", len(pfiles), [os.path.relpath(p, L)[:90] for p in pfiles[:3]])
jnames = sorted({t.get("journal_name") for t in test if t.get("journal_name") and len(t["journal_name"]) > 10})
hits = collections.Counter(); nbytes = 0
for p in pfiles:
    try: s = open(p, encoding="utf-8", errors="replace").read()
    except Exception: continue
    nbytes += len(s)
    for j in jnames:
        if j in s: hits["journal name"] += 1; break
    if any(v in s for v in ("العلوم الإنسانية ، متعددة التخصصات", "Humanities, Multidisciplinary", "fields_of_study", "strict_primary", "acceptable_l1")): hits["field-of-study value or reference key"] += 1
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", s): hits["e-mail"] += 1
print("   prompt text scanned (chars):", nbytes, dict(hits))
