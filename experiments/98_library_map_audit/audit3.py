#!/usr/bin/env python3
"""Audit steps 4 (payloads actually sent), 7 (money), 8 (full inputs)."""
import json, re, glob, os, collections, random
L = "/home/appuser/ai-search-eval-archive/2026-11-23-library-map"
load = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
test = {r["doc_id"]: r for r in load(f"{L}/pilot/sets/test.jsonl")}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")
FOS = set()
for r in test.values():
    for k in ("fields_of_study_ar", "fields_of_study_en"):
        FOS.update(v for v in (r.get(k) or []) if len(v) > 14)
print("== 4b. request payloads of the frozen test run")
tot = collections.Counter()
for p in sorted(glob.glob(f"{L}/pilot/runs/test_frozen/*/batch/*_requests.jsonl")):
    txt = open(p, encoding="utf-8").read()
    tot["files"] += 1; tot["chars"] += len(txt)
    ids = set(re.findall(r"\d{4}-\d{3}-[\d,]{3,}-\d{3,}(?:-\d+)?", txt))
    tot["test ids seen"] += len(ids & set(test))
    for d in ids & set(test):
        jn = test[d].get("journal_name") or ""
        if len(jn) > 12 and jn in txt: tot["journal name of a test record present somewhere in the same file"] += 1
    tot["e-mails"] += len(EMAIL.findall(txt))
    tot["long field-of-study strings"] += sum(txt.count(v) for v in FOS)
    for key in ("journal_name", "journal_code", "fields_of_study", "strict_primary", "acceptable_l1", "proxy_field", "split_unit", '"group"'):
        tot["key " + key] += txt.count(key)
for k, v in tot.items(): print("  ", k, v)
print("== 7. money")
def sumusd(p):
    s = 0.0; n = 0
    for l in open(p, encoding="utf-8"):
        try: d = json.loads(l)
        except Exception: continue
        for k in ("usd", "cost_usd", "usd_total"):
            if isinstance(d.get(k), (int, float)): s += d[k]; n += 1; break
    return s, n
grand = 0
for p in [f"{L}/pilot/labeller/spend.jsonl", f"{L}/pilot/reference/spend.jsonl"] + sorted(glob.glob(f"{L}/runs/full-v0.1/**/spend*.jsonl", recursive=True)) + sorted(glob.glob(f"{L}/[0-9][0-9]-*/**/spend*.json*", recursive=True)) + sorted(glob.glob(f"{L}/pilot/runs/**/spend.jsonl", recursive=True))[:0]:
    if p.endswith(".lock"): continue
    try: s, n = sumusd(p)
    except Exception as e: print("   could not read", p, e); continue
    grand += s
    print(f"   {os.path.relpath(p, L)[:70]:70s} rows {n:6d}  ${s:8.2f}")
print("   sum of the above: $%.2f" % grand)
for p in sorted(glob.glob(f"{L}/runs/full-v0.1/*state*.json")) + sorted(glob.glob(f"{L}/runs/full-v0.1/**/state*.json", recursive=True))[:3]:
    try:
        d = json.load(open(p)); print("   driver state", os.path.relpath(p, L), {k: d[k] for k in d if "usd" in k.lower() or "spent" in k.lower() or "ceiling" in k.lower()})
    except Exception as e: print("   state unreadable", p, e)
print(open(f"{L}/BUDGET.md", encoding="utf-8").read()[-1500:])
print("== 8. inputs for the whole catalogue")
fp = f"{L}/runs/full-v0.1/inputs/full_inputs_v1.jsonl"
sz = os.path.getsize(fp); rnd = random.Random(98); rows = []
with open(fp, "rb") as f:
    for _ in range(4000):
        f.seek(rnd.randrange(0, sz - 20000)); f.readline()
        try: rows.append(json.loads(f.readline().decode("utf-8")))
        except Exception: pass
print("   sampled", len(rows), "of file GB %.2f" % (sz / 1e9), "| keys:", sorted(rows[0].keys()))
c = collections.Counter()
for r in rows:
    s = json.dumps(r, ensure_ascii=False)
    c["e-mail anywhere"] += bool(EMAIL.search(s))
    c["field-of-study string anywhere"] += any(v in s for v in FOS)
    for k in r:
        if re.search(r"journal|field|author|supervis|name|university|faculty|databas|collection", k, re.I): c["key:" + k] += 1
print("  ", dict(c))
ex = [r for r in rows if EMAIL.search(json.dumps(r, ensure_ascii=False))][:3]
for r in ex:
    s = json.dumps(r, ensure_ascii=False); m = EMAIL.search(s); print("   e-mail context:", s[max(0, m.start()-60):m.start()], "<EMAIL>", "| in key:", [k for k, v in r.items() if EMAIL.search(json.dumps(v, ensure_ascii=False))])
