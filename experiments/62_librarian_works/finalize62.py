"""Experiment 62, step 4: before / after on the 780 articles — what the librarian's decisions would change if applied
(nothing is applied; read-only on the release and on experiment 52's outputs).

The after-state is rebuilt from the standing decisions alone (replayable):
1. every full citation (or short form standing alone) starts on its machine card;
2. a card split (split_card) puts each citation in its group; a card that is not a work is dropped from the work
   counts (`drop`), or each of its citations becomes a work of its own (`one_per_citation`);
3. same_work and edition_of join two works (the group of a split card that matches the other card); a joins entry
   joins a split-off group to another card; part_of and different_work join nothing;
4. a work is held by Mandumah when one of its cards has a standing links_to_publication decision, or a link47
   accepted link that no standing decision contradicts.

Back references count for the work of the citation they point to (citation_mentions.full_mention_pk), as in the
platform's v_mention_work; the Quran and hadith stay out, as in experiment 52.

    python3 finalize62.py   -> out/numbers62.json
"""
from __future__ import annotations

import json
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from norm62 import release, title_sim, tokens  # noqa: E402

RELEASES = Path.home() / "data/desk/releases"
GATE1 = "J0130"
RANDOM_RUNS = ("v33_300_final_lettersfix", "v33_300b_fix3_lettersfix")
E52 = HERE.parent / "52_journal_gate1" / "out" / "catalogue"


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if str(ra) > str(rb):
                ra, rb = rb, ra
            self.p[rb] = ra


def standing() -> list:
    out = {}
    for l in open(OUT / "decisions62.jsonl", encoding="utf-8"):
        d = json.loads(l)
        out[d["qkey"]] = d
    return list(out.values())


def main():
    rel = release()
    con = sqlite3.connect(f"file:{rel}?mode=ro", uri=True)
    cards = {json.loads(l)["cited_work_id"]: json.loads(l) for l in open(OUT / "cards62.jsonl", encoding="utf-8")}
    arts = json.loads((OUT / "articles62.json").read_text(encoding="utf-8"))
    D = standing()
    member_card, member_id = {}, {}
    for cid, c in cards.items():
        for m in c["members"]:
            member_card[m["mention_pk"]] = cid
            member_id[m["mention_pk"]] = m["mention_id"]
    # every mention of the 780 (Quran and hadith out), the work it counts for
    vm = [dict(zip(("mention_pk", "version_id", "stem", "pub", "kind", "full", "cw"), r)) for r in con.execute(
        "SELECT mention_pk, version_id, stem, citing_pub_id, kind, full_mention_pk, cited_work_pk FROM v_mention_work")]
    pk2id = {c["cited_work_pk"]: cid for cid, c in cards.items()}

    # ---------------------------------------------------------------- units: split / not-a-work
    split = {}
    drop, per_cit, joins = set(), set(), []
    for d in D:
        if d["level"] != "card":
            continue
        cid = d["subject_keys"][0]
        if d["kind"] == "split_card" and d["decision"].get("groups"):
            split[cid] = d["decision"]["groups"]
            joins += [(cid, j["member"], j["card"]) for j in d["decision"].get("joins") or []]
        if d["kind"] == "not_a_work":
            a = d["decision"].get("action")
            if a == "drop":
                drop.add(cid)
            elif a == "one_per_citation":
                per_cit.add(cid)

    def group_of(cid, mid):
        for gi, g in enumerate(split.get(cid, [])):
            if any(piece in mid for piece in g):
                return gi
        return 0

    def unit_of_member(mpk):
        cid = member_card.get(mpk)
        if cid is None:
            return None
        if cid in drop and cid not in split:
            return None
        if cid in per_cit and cid not in split:
            return (cid, "m:" + member_id[mpk])
        return (cid, group_of(cid, member_id[mpk]))

    def pick_group(cid, other):
        if cid not in split:
            return (cid, 0)
        ot = tokens(cards[other]["title"])
        ostems = set(cards[other]["stems"])
        oau = {w for a in cards[other]["authors"] for w in tokens(a["printed"])}
        best, bi = -1, 0
        for gi, g in enumerate(split[cid]):
            ms = [m for m in cards[cid]["members"] if any(p in m["mention_id"] for p in g)]
            for m in ms:
                p = m["parsed"] or {}
                t = p.get("article_title") or p.get("chapter_title") or p.get("source_title") or ""
                # the group that shares the other card's article first, then its authors, then its title
                s = (2.0 * (m["stem"] in ostems) + 0.5 * bool(oau & set(tokens(m["printed"] or "")))
                     + title_sim(tokens(t), ot)["dice"])
                if s > best:
                    best, bi = s, gi
        return (cid, bi)

    uf = UF()
    pairs = [d for d in D if d["level"] == "pair"]
    for d in pairs:
        if d["kind"] in ("same_work", "edition_of"):
            a, b = d["subject_keys"]
            uf.union(pick_group(a, b), pick_group(b, a))
    for cid, piece, target in joins:
        mpk = next((m["mention_pk"] for m in cards[cid]["members"] if piece in m["mention_id"]), None)
        if mpk is None:
            continue
        tc, _, tg = target.partition("#")
        tu = (tc, int(tg) - 1) if tg else pick_group(tc, cid)
        uf.union(unit_of_member(mpk), tu)

    # ---------------------------------------------------------------- held by Mandumah
    l47 = {cid for cid, c in cards.items() if any(L["status"] == "accepted" and L["best"] for L in c["links"])}
    cat = {}
    for d in D:
        if d["level"] == "catalogue":
            cid = d["subject_keys"][0]
            k = d["kind"]
            prev = cat.get(cid)
            if prev == "links_to_publication":      # a read-article link and a catalogue link: either holds
                continue
            cat[cid] = k
    lib_links = {cid for cid, k in cat.items() if k == "links_to_publication"}
    contradicted = {cid for cid, k in cat.items() if k in ("no_link", "relation")}
    after_links = lib_links | (l47 - contradicted)
    # experiment 52's catalogue matcher (probe A) on the gate-1 cards, mapped to this release by mention ids
    e52 = set()
    if (E52 / "works.jsonl").exists():
        mid2card = {m["mention_id"]: cid for cid, c in cards.items() for m in c["members"]}
        dec = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(E52 / "decisions.jsonl", encoding="utf-8")}
        for l in open(E52 / "works.jsonl", encoding="utf-8"):
            w = json.loads(l)
            if dec.get(w["cited_work_pk"], {}).get("decision") == "accept":
                for m in w["members"]:
                    if m["mention_id"] in mid2card:
                        e52.add(mid2card[m["mention_id"]])
    rule_accept = set()
    for l in open(OUT / "catalogue" / "cat62.jsonl", encoding="utf-8"):
        x = json.loads(l)
        if x["decision"] == "accept":
            rule_accept.add(x["cited_work_id"])

    # ---------------------------------------------------------------- per mention: before and after work
    rows = []
    for r in vm:
        cid = pk2id.get(r["cw"]) if r["cw"] else None
        u = unit_of_member(r["full"]) if r["full"] in member_card else None
        if r["cw"] and r["full"] not in member_card:     # the mention's own card (a member we did not see)
            u = (cid, 0) if cid else None
        root = uf.find(u) if u else None
        rows.append(dict(r, before=cid, after=root, after_card=u[0] if u else None))
    stems_journal = {s for s, a in arts.items() if a["journal_id"] == GATE1}
    pool = sorted(s for s, a in arts.items() if a["run"] in RANDOM_RUNS)

    def measure(stem_set, which):
        pubs = defaultdict(set)
        ment = Counter()
        for r in rows:
            if r["stem"] not in stem_set:
                continue
            w = r[which]
            if w is None:
                continue
            pubs[w].add(r["pub"])
            ment[w] += 1
        return pubs, ment

    def held_share(stem_set, which, links):
        tot = held = 0
        for r in rows:
            if r["stem"] not in stem_set:
                continue
            tot += 1
            if which == "before":
                if r["before"] in links:
                    held += 1
            else:
                if r["after"] is not None and root_held.get(r["after"]):
                    held += 1
        return dict(mentions=tot, held=held, share=round(held / max(1, tot), 4))

    root_held = defaultdict(bool)
    for cid in after_links:
        for gi in ([0] if cid not in split else [0]):
            root_held[uf.find((cid, gi))] = True
        if cid in per_cit and cid not in split:
            for m in cards[cid]["members"]:
                root_held[uf.find((cid, "m:" + m["mention_id"]))] = True
    all_stems = set(arts)

    def summary(which):
        pubs, ment = measure(all_stems, which)
        names = {}
        for r in rows:
            w = r[which]
            if w is not None and w not in names:
                names[w] = r["before"] if which == "before" else r["after_card"]
        top = sorted(pubs, key=lambda w: (-len(pubs[w]), -ment[w], str(w)))[:30]

        def label(w):
            if which == "after":
                members = [k for k in uf.p if uf.find(k) == w] or [w]
                cids = sorted({k[0] for k in members}, key=lambda c: (-cards[c]["n_mentions"], c))
                cid = cids[0]
            else:
                cid, cids = w, [w]
            c = cards.get(cid) or {}
            return dict(card=cid, title=c.get("title"), cards=cids[:12], n_cards=len(cids), articles=len(pubs[w]),
                        mentions=ment[w])
        return dict(cited_works=len(pubs), cited_by_2plus=sum(1 for s in pubs.values() if len(s) >= 2),
                    cited_by_3plus=sum(1 for s in pubs.values() if len(s) >= 3), top=[label(w) for w in top])

    B, A = summary("before"), summary("after")

    def gate(which):
        j = sum(1 for s in measure(stems_journal, which)[0].values() if len(s) >= 2)
        rnd = random.Random(5250)
        rs = []
        for _ in range(20):
            st = set(rnd.sample(pool, len(stems_journal)))
            rs.append(sum(1 for s in measure(st, which)[0].values() if len(s) >= 2))
        r600 = sum(1 for s in measure(set(pool), which)[0].values() if len(s) >= 2)
        return dict(journal=j, random_same_size=round(sum(rs) / len(rs), 2), random_range=[min(rs), max(rs)],
                    random_600=r600, ratio=round(j / max(0.01, sum(rs) / len(rs)), 1))
    held = dict(
        before_link47=dict(all=held_share(all_stems, "before", l47), journal=held_share(stems_journal, "before", l47),
                           random600=held_share(set(pool), "before", l47)),
        before_probeA_exp52=dict(journal=held_share(stems_journal, "before", e52)),
        before_rule_catalogue=dict(all=held_share(all_stems, "before", rule_accept),
                                   journal=held_share(stems_journal, "before", rule_accept)),
        after=dict(all=held_share(all_stems, "after", None), journal=held_share(stems_journal, "after", None),
                   random600=held_share(set(pool), "after", None)))
    # links to the 780 articles read (citations between the articles of this release)
    read_links = [d for d in D if d["packet"].startswith("read:") and d["kind"] == "links_to_publication"]
    read_targets = {(d["subject_keys"][0], d["decision"]["target"].get("stem")) for d in read_links}
    # what the decisions are
    kinds = Counter((d["level"], d["kind"]) for d in D)
    conf = Counter(d["confidence"] for d in D)
    kind_conf = defaultdict(Counter)
    for d in D:
        kind_conf[f"{d['level']}:{d['kind']}"][d["confidence"]] += 1
    basis = Counter(d["basis"] for d in D)
    split_moved = sum(len(cards[c]["members"]) - max(1, len([m for m in cards[c]["members"] if group_of(c, m["mention_id"]) == 0]))
                      for c in split)
    # the Desk's «possible same work» tasks: how the librarian decided them
    det = json.loads((OUT / "desk_detectors62.json").read_text(encoding="utf-8"))
    dpairs = {tuple(sorted(k.split(":", 1)[1] for k in x["keys"])) for x in det["possible_same_work"]}
    pd = {tuple(d["subject_keys"]): d["kind"] for d in pairs}
    desk = Counter(pd.get(p, "not judged (outside the blocking)") for p in dpairs)
    # Lisan al-Arab and friends: the variants that joined
    def family(word):
        fam = []
        for root in {r["after"] for r in rows if r["after"] is not None}:
            pass
        return fam
    lisan = [x for x in A["top"] if (x["title"] or "").startswith(("لسان", "اللسان"))]
    N = dict(release=rel.name, articles=len(arts), journal_articles=len(stems_journal), random_pool=len(pool),
             mentions=len(rows), cards=len(cards),
             before=dict(cited_works=B["cited_works"], cited_by_2plus=B["cited_by_2plus"], cited_by_3plus=B["cited_by_3plus"],
                         gate1=gate("before"), top=B["top"]),
             after=dict(cited_works=A["cited_works"], cited_by_2plus=A["cited_by_2plus"], cited_by_3plus=A["cited_by_3plus"],
                        gate1=gate("after"), top=A["top"]),
             held=held,
             changes=dict(pairs_joined=sum(1 for d in pairs if d["kind"] in ("same_work", "edition_of")),
                          editions=sum(1 for d in pairs if d["kind"] == "edition_of"),
                          cards_split=len(split), citations_moved_by_splits=split_moved,
                          cards_dropped=len(drop - set(split)), cards_one_per_citation=len(per_cit - set(split)),
                          retitled=sum(1 for d in D if d["kind"] == "not_a_work" and d["decision"].get("action") == "retitle"),
                          librarian_links=len(lib_links), link47_links=len(l47), link47_contradicted=len(l47 & contradicted),
                          rule_accepts=len(rule_accept), links_to_articles_read=len(read_targets)),
             decisions=dict(total=len(D), by_kind={f"{a}:{b}": n for (a, b), n in sorted(kinds.items())},
                            by_confidence=dict(conf), by_basis=dict(basis),
                            kind_confidence={k: dict(v) for k, v in sorted(kind_conf.items())},
                            trivial=sum(1 for d in D if d["trivial"]),
                            found_while_judging=sum(1 for d in D if d.get("found_while_judging"))),
             desk_possible_same_work=dict(pairs=len(dpairs), decided=dict(desk)))
    (OUT / "numbers62.json").write_text(json.dumps(N, ensure_ascii=False, indent=1), encoding="utf-8")
    show = {k: v for k, v in N.items() if k not in ("before", "after")}
    print(json.dumps(dict(before={k: v for k, v in N["before"].items() if k != "top"},
                          after={k: v for k, v in N["after"].items() if k != "top"}, **show), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
