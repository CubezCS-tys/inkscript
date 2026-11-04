"""Experiment 62, step 6: the rules the librarian's decisions teach — each written as a plain test on the evidence a
packet already holds (title likeness, author agreement, years, types, the catalogue record), and measured against
the librarian's standing decisions: how often it fires, how often its answer is the librarian's, and how many
decisions it would take off a judge's desk (fires and agrees).

A rule is worth keeping when it agrees >= 98% of the time it fires; the others are listed with their misses so the
reason they fail is visible.

    python3 rules62.py   -> out/rules62.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))

ONE = {"same_work", "edition_of"}
JOURNAL_RE = re.compile(r"^(مجلة|مجله|جريدة|صحيفة|journal|revue|the journal|magazine|newspaper)\b", re.I)


def _years(c):
    ys = []
    for y in c.get("years") or []:
        ys += [int(x) for x in re.findall(r"(?<!\d)(1[3-9]\d{2}|20\d{2})(?!\d)", str(y))]
        ys += [int(x.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
               for x in re.findall(r"[١٢][٠-٩]{3}", str(y))]
    return ys


def year_gap(d):
    a, b = (_years(c) for c in d["decision"]["cards"])
    if not a or not b:
        return None
    return min(abs(x - y) for x in a for y in b)


def pair_rules(cards):
    def f(d):
        return d["decision"]["features"]

    def same_article(d):
        a, b = d["subject_keys"]
        return bool(set(cards[a]["stems"]) & set(cards[b]["stems"]))

    def short_only(d):
        a, b = d["subject_keys"]
        return cards[a]["short_only"] or cards[b]["short_only"]

    def types(d):
        return {c["type"] for c in d["decision"]["cards"]}

    return [
        ("P1 same title, same author -> one work",
         "folded titles nearly identical (dice >= 0.85) and the authors agree",
         lambda d: f(d)["title"]["dice"] >= 0.85 and f(d)["author"] == "agree", "one"),
        ("P2 same title, same author, years within 2 -> same_work (not an edition)",
         "as P1 and the printed years at most 2 apart",
         lambda d: f(d)["title"]["dice"] >= 0.85 and f(d)["author"] == "agree" and (year_gap(d) or 0) <= 2,
         "same_work"),
        ("P3 short form in the same article as the long card -> one work",
         "one card is a short form alone, both cards are cited in the same article, authors do not contradict",
         lambda d: short_only(d) and same_article(d) and f(d)["author"] != "contradict"
         and (f(d)["title"]["prefix"] or f(d)["title"]["cover"] >= 0.99), "one"),
        ("P4 authors contradict -> different works",
         "the cards print authors with nothing in common (surnames, either script)",
         lambda d: f(d)["author"] == "contradict", "different_work"),
        ("P5 unlike titles -> different works",
         "folded titles share little (dice < 0.5) and the authors do not agree",
         lambda d: f(d)["title"]["dice"] < 0.5 and f(d)["author"] != "agree", "different_work"),
        ("P6 a thesis and a journal article -> different works (a relation, not one work)",
         "one card is a thesis, the other a journal article",
         lambda d: types(d) == {"thesis", "journal"}, "different_work"),
        ("P7 two journal articles years apart -> different works",
         "both cards are journal articles and their years are more than 2 apart",
         lambda d: types(d) == {"journal"} and (year_gap(d) or 0) > 2, "different_work"),
        ("P8 short generic title, author unknown -> do not join",
         "the shorter title has at most 2 words and an author is missing on one side",
         lambda d: f(d)["title"]["n_short"] <= 2 and f(d)["author"] == "unknown", "not_one"),
    ]


def card_rules():
    def title(d):
        return d["decision"]["card"]["title"] or ""
    return [
        ("C1 a card titled with a journal's name is not a work",
         "the card's title begins with مجلة / جريدة / Journal / Revue …",
         lambda d: d["packet"].startswith("notwork:") and bool(JOURNAL_RE.match(title(d).strip())), "not_a_work"),
    ]


def cat_rules():
    def t(d):
        return d["decision"].get("target") or {}
    return [
        ("K1 title, author and year all match -> the record is the work",
         "title score >= 0.9, author score >= 0.8, years within 1",
         lambda d: (t(d).get("s_title") or 0) >= 0.9 and (t(d).get("s_author") or 0) >= 0.8
         and (t(d).get("s_year") or 0) >= 0.5, "links_to_publication"),
        ("K2 a book-review or thesis-review record -> a relation",
         "the Mandumah record is of type عروض كتب / عروض رسائل",
         lambda d: (t(d).get("type") or "").startswith("عروض"), "relation"),
        ("K3 the cited work is a thesis, the record an article -> a relation",
         "card type thesis, record type بحوث ومقالات",
         lambda d: d["decision"]["card"]["type"] == "thesis" and t(d).get("type") == "بحوث ومقالات", "relation"),
        ("K1b as K1, and the record is not a review and not an article from a cited thesis -> the work",
         "K1, record type not عروض …, and not (card thesis, record article)",
         lambda d: (t(d).get("s_title") or 0) >= 0.9 and (t(d).get("s_author") or 0) >= 0.8
         and (t(d).get("s_year") or 0) >= 0.5 and not (t(d).get("type") or "").startswith("عروض")
         and not (d["decision"]["card"]["type"] == "thesis" and t(d).get("type") == "بحوث ومقالات"),
         "links_to_publication"),
        ("K1c as K1b, and the venue fits: a journal article's journal is printed, a book is not matched to an article",
         "K1b; card journal -> the record's journal words in the citation (>= 50%); card book/chapter -> record not "
         "an article",
         lambda d: _k1b(d) and _venue_fits(d), "links_to_publication"),
        ("K2b a review record, and the citation does not name the record's journal -> a relation",
         "record type عروض …, and the record's journal words are not in the printed citation",
         lambda d: (t(d).get("type") or "").startswith("عروض") and _jhit(d) < 0.5, "relation"),
        ("K4 author does not match -> no link",
         "author score < 0.3 on a record proposed only as a candidate",
         lambda d: (t(d).get("s_author") is not None) and (t(d).get("s_author") or 0) < 0.3
         and d["decision"].get("proposal") == "candidate", "no_link"),
    ]


def _k1b(d):
    return [r for r in cat_rules() if r[0].startswith("K1b")][0][2](d)


def _venue_fits(d):
    t = d["decision"].get("target") or {}
    ct = d["decision"]["card"]["type"]
    if ct == "journal" and t.get("journal"):
        return _jhit(d) >= 0.5
    if ct in ("book", "chapter"):
        return t.get("type") != "بحوث ومقالات"
    return True


def _jhit(d):
    from norm62 import tokens
    t = d["decision"].get("target") or {}
    jt = set(tokens(t.get("journal") or "")) - {"مجله", "مجلة"}
    return len(jt & set(tokens(" ".join(d.get("printed") or [])))) / max(1, len(jt))


def notwork_action(d, cards):
    """N1: a journal-name card: drop when no author and no item title is printed; one item per citation when the
    citations print different authors; else retitle (one item whose title was lost)."""
    c = cards[d["subject_keys"][0]]
    ms = c["members"]
    sur = set()
    for m in ms:
        au = ((m["parsed"] or {}).get("authors") or [[""]])[0]
        sur.add(((au[0] if isinstance(au, list) and au else "") or "").strip())
    sur.discard("")
    long_ = [m for m in ms if len(m["printed"] or "") > len(c["title"] or "") + 40]
    if not c["authors"] and not sur and not long_:
        return "drop"
    if len(ms) >= 2 and len(sur) >= 2:
        return "one_per_citation"
    return "retitle"


def agrees(kind, want):
    if want == "one":
        return kind in ONE
    if want == "not_one":
        return kind not in ONE
    return kind == want


def main():
    from finalize62 import standing
    cards = {json.loads(l)["cited_work_id"]: json.loads(l) for l in open(OUT / "cards62.jsonl", encoding="utf-8")}
    D = standing()
    sets = [("pair", pair_rules(cards)), ("card", card_rules() + [
        ("N1 journal-name card: no author and no item title -> drop; several authors -> one per citation; else retitle",
         "on the not-a-work cards of journal names: the action from the printed authors and length",
         lambda d: d["packet"].startswith("notwork:") and d["kind"] == "not_a_work"
         and d["decision"].get("action") in ("drop", "retitle", "one_per_citation"),
         lambda d: "not_a_work:" + notwork_action(d, cards))]), ("catalogue", cat_rules())]
    rows = []
    for lvl, rules in sets:
        pool = [d for d in D if d["level"] == lvl and d["kind"] != "unsure"
                and (lvl != "pair" or "title" in (d["decision"].get("features") or {}))]
        for name, test, fn, want in rules:
            fired = [d for d in pool if fn(d)]
            def ag(d):
                if callable(want):
                    return f"{d['kind']}:{d['decision'].get('action')}" == want(d)
                return agrees(d["kind"], want)
            ok = [d for d in fired if ag(d)]
            judged = [d for d in ok if not d.get("trivial")]
            miss = [dict(decision_id=d["decision_id"], subject=d["subject_keys"], librarian=d["kind"],
                         action=d["decision"].get("action"), reason=d["reason"][:160]) for d in fired if not ag(d)]
            prec = len(ok) / len(fired) if fired else None
            rows.append(dict(rule=name, test=test, level=lvl, answer=want if isinstance(want, str) else "computed", pool=len(pool), fires=len(fired),
                             agrees=len(ok), precision=round(prec, 4) if prec is not None else None,
                             reproduces_judged=len(judged), keep=bool(fired) and prec >= 0.98,
                             misses=miss[:8], n_misses=len(miss)))
    out = dict(rules=rows, note="fires = standing decisions (unsure left out) on which the test is true; agrees = "
               "those where the librarian's decision is the rule's answer; reproduces_judged = agreements on "
               "decisions the librarian made by judgement / world knowledge / context / reading the record rather "
               "than left as the proposing rule had them (not trivial); keep = precision >= 98%")
    (OUT / "rules62.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        print(f"{r['rule'][:70]:70s} fires {r['fires']:5d} agrees {r['agrees']:5d} p={r['precision']} "
              f"judged={r['reproduces_judged']} keep={r['keep']}")


if __name__ == "__main__":
    main()
