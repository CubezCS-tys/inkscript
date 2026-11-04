"""Experiment 60, test 1: page verdicts side by side (no calls). Argon's first answer = the proof pack's verdict
after fix round 3, except where today's master of Argon's answers differs from the judged one (only 1539 p2: the
advert the judge marked other_article later); Claude's = Argon's where the two masters show the page alike, else the
hand verdict in out/t1/page_verdicts_claude.jsonl.     -> out/t1/page_scores.json"""
import json
from collections import Counter
from common60 import OUT, jdump
T1 = OUT / "t1"
pages = json.loads((T1 / "pages.json").read_text())
hand = {(r["stem"], r["page"]): r for r in map(json.loads, (T1 / "page_verdicts_claude.jsonl").read_text().splitlines())}
ARGON_PLAIN = {("1539-000-007-005", 2): ("minor", ["wrong_kind:advert"], "the advert stays picture text in the article until the judge's edit")}
rows = []
for p in pages:
    k = (p["stem"], p["page"])
    a = ARGON_PLAIN.get(k, (p["after_fix3"], p["kinds"] if p["after_fix3"] != "right" else [], "proof pack"))
    if p["claude_same_as_argon_plain"]:
        c = (a[0], a[1], "same page as Argon's")
    else:
        h = hand[k]
        c = (h["verdict"], h["kinds"], h["why"])
    rows.append(dict(stem=k[0], page=k[1], judged=p["after_fix3"], argon_first=a[0], argon_kinds=a[1], claude=c[0],
                     claude_kinds=c[1], claude_why=c[2]))
missing = [k for k in [(p["stem"], p["page"]) for p in pages if not p["claude_same_as_argon_plain"]] if k not in hand]
assert not missing, missing
tot = {w: dict(Counter(r[w] for r in rows)) for w in ("judged", "argon_first", "claude")}
def wc(kinds):
    return sum(int(k.split(":")[1]) for k in kinds if k.startswith("word_errors:"))
tot["claude_word_errors"] = sum(wc(r["claude_kinds"]) for r in rows)
tot["argon_word_errors"] = sum(wc(r["argon_kinds"]) for r in rows)
tot["claude_pages_with_word_errors"] = sum(wc(r["claude_kinds"]) > 0 for r in rows)
tot["argon_pages_with_word_errors"] = sum(wc(r["argon_kinds"]) > 0 for r in rows)
tot["claude_kinds"] = dict(Counter(k.split(":")[0] for r in rows for k in r["claude_kinds"]))
tot["argon_kinds"] = dict(Counter(k.split(":")[0] for r in rows for k in r["argon_kinds"]))
jdump(T1 / "page_scores.json", dict(totals=tot, pages=rows))
print(json.dumps(tot, ensure_ascii=False, indent=1))
