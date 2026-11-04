"""Experiment 72, the lead's follow-up (2026-11-03): 0165 citations joined to a card by a shared title phrase where the
authors, years or places disagree (CBDD9P2BCR: al-Hiti's «ثقافة الأطفال» 1988 held three citations of al-Kaabi's
«تكنولوجيا الثقافة: دراسة في الأسس العلمية لثقافة الأطفال» 2011). Read-only on a release.

Every 0165 member of a card is compared with the card's core (the members whose title is the card's title: experiment
62's fuzzy title_sim, dice >= 0.6): a member is flagged when its own title is not the card's (dice < 0.6) AND at least
one of: its author contradicts every core author (exp 62's author_relation), its year is more than 2 years from all
core years, or it prints no author while every core member does.

    python scan72.py [RELEASE]  -> out/scan72.json, out/scan72.txt
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict

from common72 import E62, OUT, add_paths, ro, wjs

add_paths(E62)
from norm62 import author_relation, name_words, title_sim, tokens  # noqa: E402

YR = re.compile(r"(?<![0-9٠-٩])((?:19|20)[0-9]{2}|[١٢][٩٠][٠-٩]{2})(?![0-9٠-٩])")


def year(s):
    m = YR.findall(s or "")
    return {int(y.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))) for y in m}


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "/home/appuser/data/desk/releases/R20261103T055432.db"
    con = ro(db)
    rows = con.execute("""SELECT w.cited_work_id, w.title, m.mention_id, m.printed, m.parsed, cm.method, v.stem
                          FROM cited_works w JOIN cited_work_members cm ON cm.cited_work_pk = w.cited_work_pk
                          JOIN citation_mentions m ON m.mention_pk = cm.full_mention_pk
                          JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
                          WHERE w.status = 'active'""").fetchall()
    cards = defaultdict(list)
    for r in rows:
        cards[r["cited_work_id"]].append(dict(r))
    out = []
    for cid, ms in cards.items():
        if len(ms) < 2 or not any(m["stem"].startswith("0165-") for m in ms):
            continue
        feats = []
        for m in ms:
            p = json.loads(m["parsed"]) if m["parsed"] else {}
            t = p.get("article_title") or p.get("chapter_title") or p.get("source_title") or ""
            au, sur = set(), set()
            for x in p.get("authors") or []:
                if isinstance(x, list) and x:
                    au |= name_words(" ".join(y for y in x if y))
                    sur |= name_words(x[0])
            feats.append(dict(m=m, toks=tokens(t), title=t, au=au, sur=sur or au, years=year(str(p.get("year") or "")
                                                                                          or m["printed"])))
        ct = tokens(ms[0]["title"])
        core = [g for g in feats if g["toks"] and title_sim(g["toks"], ct)["dice"] >= 0.6]
        for i, f in enumerate(feats):
            if not f["m"]["stem"].startswith("0165-") or not f["toks"]:
                continue
            d = title_sim(f["toks"], ct)["dice"]
            if d >= 0.6 or len(core) < 1:
                continue
            others = [g for g in core if g is not f]
            if not others:
                continue
            why = []
            oa = [g for g in others if g["au"]]
            if f["au"] and oa and all(author_relation(f["au"], g["au"], f["sur"], g["sur"]) == "contradict" for g in oa):
                why.append("author contradicts the card's")
            oy = set().union(*[g["years"] for g in others])
            if f["years"] and oy and min(abs(a - b) for a in f["years"] for b in oy) > 2:
                why.append(f"year {sorted(f['years'])} vs {sorted(oy)[:4]}")
            if not f["au"] and oa and len(oa) == len(others):
                why.append("prints no author; the card's members do")
            if why:
                out.append(dict(card=cid, card_title=ms[0]["title"], n=len(ms), mention=f["m"]["mention_id"],
                                method=f["m"]["method"], title=f["title"], dice=round(d, 2), why=why,
                                printed=f["m"]["printed"][:300]))
    wjs(OUT / "scan72.json", out)
    with open(OUT / "scan72.txt", "w", encoding="utf-8") as fh:
        for x in out:
            fh.write(f"{x['card']} «{x['card_title']}» ({x['n']}) {x['method']} d{x['dice']} {x['why']}\n"
                     f"    {x['mention']}: {x['printed']}\n")
    print(len(out), "members flagged on", len({x["card"] for x in out}), "cards")


if __name__ == "__main__":
    main()
