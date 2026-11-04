"""Experiment 62, step 2: candidate generation by code (cheap, recall first) — which cards MIGHT be one work, which
card MIGHT hold two, which card might not be a work at all, and which might be a Mandumah record.

Packets (out/packets62.jsonl), one per question a librarian would ask:
- `merge`   a small cluster of cards that might be one work (or editions / parts of one). Edges come from:
            fuzzy folded titles (one misprinted letter forgiven per word; hamza / alef / ya / taa marbuta, «ال» and
            clitics, edition and volume marks removed; the authors' own name words dropped from both titles, so
            «مقدمة ابن خلدون» meets «المقدمة»), short vs long titles (one is the start of / inside the other),
            letters alike, author names alike in either script (a rough consonant skeleton for «جاكندوف» ~
            Jackendoff), years in either calendar. Pairs whose authors contradict are kept only when the titles are
            near-identical (an author printed two ways). Components larger than 12 cards are cut at their weakest
            edges.
- `split`   a card cited by 2+ articles whose members print no author on one side or two author sets with nothing
            in common, or a short generic title («الديوان», «الكتاب») joined across articles; or members whose years
            are centuries apart.
- `notwork` a card that may not be a work: a journal / newspaper / series named alone, the Quran or a hadith
            collection as a card, «بيانات غير منشورة», a bare web site, a law named generically, a back reference
            parsed as a title («المرجع السابق»).
- `catalogue` a card the catalogue drawer (catindex62) proposed as a candidate / relation (accepts are taken by
            rule and sampled), plus a card whose title is one of the 780 articles read.

Also out/pairs62.jsonl (every candidate edge with its features) and out/blocking62.json (how many edges each
blocking rule made, and the overlap with the Desk's «possible same work» detector — an independent generator — as
a recall check).

    python3 experiments/62_librarian_works/cands62.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from norm62 import (AR, GENERIC, author_relation, fold, key, name_words, near, script_of, title_sim,  # noqa: E402
                    tokens, year_relation, years_of)

MAX_CLUSTER = 12


def member_title(m: dict) -> str:
    p = m["parsed"] or {}
    return p.get("article_title") or p.get("chapter_title") or p.get("source_title") or ""


def features(c: dict) -> dict:
    au, sur = set(), set()
    for a in c["authors"]:
        w = name_words(a["printed"]) | name_words(a.get("latin"))
        au |= w
    eds, esur = set(), set()
    for m in c["members"]:
        p = m["parsed"] or {}
        for x in (p.get("authors") or []):
            if isinstance(x, list) and x:
                au |= name_words(" ".join(y for y in x if y))
                sur |= name_words(x[0]) or name_words(" ".join(y for y in x if y))
        for x in (p.get("editors") or []):
            if isinstance(x, list) and x:
                eds |= name_words(" ".join(y for y in x if y))
                esur |= name_words(x[0])
    if not au:
        au, sur = set(eds), set(esur)
    if not sur:
        sur = set(au)
    ys = set()
    for m in c["members"]:
        ys |= years_of(str((m["parsed"] or {}).get("year") or ""))
    titles = list(dict.fromkeys([c["title"] or ""] + [member_title(m) for m in c["members"] if member_title(m)]))
    reps = [m for m in c["members"] if m["kind"] == "full"] or c["members"]
    p = (reps[0]["parsed"] if reps else None) or {}
    container = p.get("source_title") if (p.get("article_title") or p.get("chapter_title")) else None
    died = {a["died_hijri"] for a in c["authors"] if a.get("died_hijri")}
    tl = [tokens(t) for t in titles[:4]]
    return dict(id=c["cited_work_id"], title=c["title"] or "", titles=titles, tl=tl, au=au, sur=sur, ys=ys, type=c["pub_type"],
                script=script_of(c["title"]), container=container, n_articles=c["n_articles"],
                n_mentions=c["n_mentions"], stems=set(c["stems"]), short_only=c["short_only"], died=died,
                publisher=fold(c.get("publisher") or ""), toks=tokens(c["title"]))


def pair_features(A: dict, B: dict) -> dict:
    drop = A["au"] | B["au"]
    best = None
    for ia, xa in enumerate(A["tl"]):
        for ib, xb in enumerate(B["tl"]):
            s = title_sim(xa, xb)
            if drop:
                da = [w for w in xa if w not in drop and re.sub("^ل", "", w) not in drop]
                db = [w for w in xb if w not in drop and re.sub("^ل", "", w) not in drop]
                if (da, db) != (xa, xb) and da and db:
                    s1 = title_sim(da, db)
                    if s1["dice"] > s["dice"]:
                        s = s1
            if best is None or (s["dice"], s["cover"]) > (best["dice"], best["cover"]):
                best = dict(s, ta=A["titles"][ia], tb=B["titles"][ib])
    ar = author_relation(A["au"], B["au"], A["sur"], B["sur"])
    yr = year_relation(A["ys"], B["ys"])
    cont = None
    if A["container"] and B["container"]:
        cont = title_sim(tokens(A["container"]), tokens(B["container"]))["dice"]
    died = None
    if A["died"] and B["died"]:
        died = "same" if any(abs(x - y) <= 2 for x in A["died"] for y in B["died"]) else "differ"
    shared = len(A["stems"] & B["stems"])
    return dict(title=best, author=ar, year=yr, container=cont, died=died, same_article=shared,
                types=[A["type"], B["type"]], scripts=[A["script"], B["script"]])


def keep_pair(f: dict, A: dict, B: dict) -> str | None:
    """Which blocking rule lets this pair through (recall first), or None."""
    t = f["title"]
    if not t or t["n_short"] == 0:
        return None
    if f["author"] in ("contradict", "weak") and not (t["dice"] >= 0.95 and t["n_short"] >= 2):
        return None
    if f["died"] == "differ":
        return None
    if t["dice"] >= 0.6 and t["n_short"] >= 2:
        return "B1 fuzzy title"
    if (t["chars"] or 0) >= 0.85 and t["n_short"] >= 2:
        return "B2 letters alike"
    if t["cover"] >= 0.8 and t["n_short"] >= 2 and f["author"] in ("agree", "translit"):
        return "B3 short title inside long"
    if t["cover"] >= 0.8 and t["n_short"] >= 2 and f["author"] == "unknown" and (t["dice"] >= 0.5 or f["same_article"]):
        return "B3 short title inside long"
    if t["n_short"] == 1 and t["prefix"] and f["author"] in ("agree", "translit"):
        return "B4 one-word short form + author"
    if t["n_short"] == 1 and t["cover"] >= 0.99 and f["author"] in ("agree", "translit"):
        return "B4 one-word short form + author"
    if t["n_short"] <= 2 and t["cover"] >= 0.5 and f["author"] in ("agree", "translit"):
        return "B6 short title, same author"
    if t["n_short"] == 1 and t["prefix"] and (A["short_only"] or B["short_only"]) and f["author"] == "unknown":
        long_ = B if A["short_only"] and len(A["toks"]) <= len(B["toks"]) else A
        if f["same_article"] or long_["n_articles"] >= 2:
            return "B5 short form alone, no author"
    return None


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
            self.p[max(ra, rb)] = min(ra, rb)


def edge_strength(f: dict) -> float:
    t = f["title"]
    s = t["dice"] + 0.3 * t["cover"] + {"agree": 0.4, "translit": 0.2, "unknown": 0.0, "contradict": -0.5}[f["author"]]
    s += {"same": 0.1, "differ": -0.05, "unknown": 0}[f["year"]]
    return round(s, 3)


def components(nodes, edges):
    uf = UF()
    for n in nodes:
        uf.find(n)
    for a, b in edges:
        uf.union(a, b)
    comp = defaultdict(list)
    for n in nodes:
        comp[uf.find(n)].append(n)
    return list(comp.values())


def cut(nodes: list, E: dict) -> list:
    """A component too big for one look is cut at its weakest edges until every part is <= MAX_CLUSTER cards."""
    edges = sorted(((a, b) for (a, b) in E if a in nodes and b in nodes), key=lambda e: (-E[e]["strength"], e))
    parts = components(nodes, edges)
    while any(len(p) > MAX_CLUSTER for p in parts):
        edges = edges[:-max(1, len(edges) // 10)]
        parts = components(nodes, edges)
    return parts


NOTWORK = [
    ("quran", re.compile(r"^(ال)?قران( ال?كريم)?$|^(the )?(holy )?qur'?an|^مصحف")),
    ("hadith collection as a card", re.compile(r"^(صحيح|سنن|مسند)$")),
    ("unpublished data", re.compile(r"بيانات غير منشوره|unpublished|غير منشور$")),
    ("back reference parsed as a title", re.compile(r"^(ال)?(مرجع|مصدر) (ال)?(سابق|نفسه)|^نفسه$|^op\.? ?cit|^ibid|^المرجع$")),
    ("bare web site", re.compile(r"^(www\.|https?:|google|wikipedia|ويكيبيديا|جوجل|موقع)", re.I)),
    ("journal or newspaper named alone", None),
]


def notwork_reason(c: dict) -> str | None:
    t = key(c["title"] or "")
    for why, rx in NOTWORK:
        if rx is not None and rx.search(t):
            return why
    reps = [m for m in c["members"] if m["kind"] == "full"] or c["members"]
    if reps and all(not (m["parsed"] or {}).get("article_title") and (m["parsed"] or {}).get("pub_type") == "journal"
                    for m in reps):
        return "journal or newspaper named alone"
    if c["pub_type"] == "journal" and re.match(r"^(مجله|جريده|صحيفه|journal|revue|magazine)\b", t):
        return "journal or newspaper named alone"
    return None


def split_reason(c: dict, F: dict) -> dict | None:
    ms = c["members"]
    stems = {m["stem"] for m in ms}
    if len(ms) < 2:
        return None
    groups = []
    noauth = []
    for m in ms:
        au, sur = set(), set()
        for x in ((m["parsed"] or {}).get("authors") or (m["parsed"] or {}).get("editors") or []):
            if isinstance(x, list) and x:
                au |= name_words(" ".join(y for y in x if y))
                sur |= name_words(x[0])
        if not au:
            noauth.append(m["mention_id"])
            continue
        hit = [g for g in groups if author_relation(au, g["au"], sur or au, g["sur"]) in ("agree", "translit")]
        groups = [g for g in groups if g not in hit] + [dict(au=au.union(*[g["au"] for g in hit]),
                                                            sur=(sur or au).union(*[g["sur"] for g in hit]),
                                                            ms=[m["mention_id"]] + [x for g in hit for x in g["ms"]])]
    ys = []
    for m in ms:
        for cal, y in years_of(str((m["parsed"] or {}).get("year") or "")):
            if cal == "g":
                ys.append(y)
    why = []
    if len(groups) >= 2:
        why.append("two author sets with nothing in common")
    tl = [tokens(member_title(m)) for m in ms if m["kind"] == "full" and len(tokens(member_title(m))) >= 2]
    if any(title_sim(a, b)["cover"] < 0.5 for i, a in enumerate(tl) for b in tl[i + 1:]):
        why.append("members print different titles")
    if len(stems) < 2:
        return dict(why=why, author_groups=[g["ms"] for g in groups], no_author=noauth) if why else None
    if noauth and groups:
        why.append("joined through a citation that prints no author")
    if not groups and len(F["toks"]) <= 2:
        why.append("short title, no author on any member, cited by several articles")
    if F["toks"] and len(F["toks"]) == 1 and F["toks"][0] in GENERIC:
        why.append("generic short title")
    if ys and max(ys) - min(ys) >= 150 and c["pub_type"] not in ("book",):
        why.append("years centuries apart")
    if not why:
        return None
    return dict(why=why, author_groups=[g["ms"] for g in groups], no_author=noauth)


def main():
    cards = [json.loads(l) for l in open(OUT / "cards62.jsonl", encoding="utf-8")]
    C = {c["cited_work_id"]: c for c in cards}
    F = {c["cited_work_id"]: features(c) for c in cards}
    # ---------------------------------------------------------------- blocking: shared words, exact or one letter off
    df = Counter(w for f in F.values() for w in set(f["toks"]))
    idx = defaultdict(set)
    dele = defaultdict(set)
    for cid, f in F.items():
        for w in set(f["toks"]):
            idx[w].add(cid)
            if len(w) >= 5:
                for i in range(len(w)):
                    dele[w[:i] + w[i + 1:]].add(w)
        for w in f["au"]:
            idx["@" + w].add(cid)
    near_words = defaultdict(set)
    for d, ws in dele.items():
        for a, b in combinations(sorted(ws), 2):
            near_words[a].add(b)
            near_words[b].add(a)
    for w in list(df):
        if len(w) >= 5 and w[:-1] in df:            # a deleted last letter: «تحليل» / «تحليلي»
            near_words[w].add(w[:-1])
            near_words[w[:-1]].add(w)
    pairs = {}
    rule_n = Counter()
    seen = set()
    for cid, f in F.items():
        cand, acand = Counter(), Counter()
        for w in set(f["toks"]):
            if df[w] > 250:
                continue
            for x in idx[w]:
                cand[x] += 1
            for w2 in near_words.get(w, ()):
                if df[w2] <= 250:
                    for x in idx[w2]:
                        cand[x] += 1
        for w in f["au"]:
            if len(idx["@" + w]) <= 250:
                for x in idx["@" + w]:
                    if len(F[x]["toks"]) <= 2 or len(f["toks"]) <= 2 or cand.get(x):
                        acand[x] += 1               # an author word opens the door to a short-form check
        for x in sorted(set(cand) | set(acand)):
            n = cand.get(x, 0)
            if x == cid:
                continue
            a, b = sorted((cid, x))
            if (a, b) in seen:
                continue
            short = min(len(f["toks"]), len(F[x]["toks"]))
            if n < min(2, max(1, short)) and not (short <= 2 and acand.get(x)):
                continue                        # cheap prefilter: too few shared title words to be one title
            seen.add((a, b))
            pf = pair_features(F[a], F[b])
            why = keep_pair(pf, F[a], F[b])
            if why:
                pf["rule"] = why
                pf["strength"] = edge_strength(pf)
                pairs[(a, b)] = pf
                rule_n[why] += 1
    # ---------------------------------------------------------------- recall check: the Desk's independent detector
    det = json.loads((OUT / "desk_detectors62.json").read_text(encoding="utf-8"))
    dpairs = {tuple(sorted(k.split(":", 1)[1] for k in x["keys"])) for x in det["possible_same_work"]}
    covered = {p for p in dpairs if p in pairs}
    # ---------------------------------------------------------------- clusters
    nodes = sorted({x for p in pairs for x in p})
    comps = components(nodes, list(pairs))
    clusters = []
    for comp in comps:
        clusters.extend(cut(comp, pairs) if len(comp) > MAX_CLUSTER else [comp])
    clusters = [sorted(c) for c in clusters if len(c) >= 2]
    cl_of = {x: i for i, c in enumerate(clusters) for x in c}
    # ---------------------------------------------------------------- packets
    packets = []
    for i, cl in enumerate(sorted(clusters, key=lambda c: c[0])):
        es = [dict(a=a, b=b, **{k: v for k, v in pairs[(a, b)].items()}) for (a, b) in pairs
              if a in cl and b in cl]
        packets.append(dict(key=f"merge:{cl[0]}", kind="merge", cards=cl, edges=es))
    inside = {(e["a"], e["b"]) for p in packets for e in p["edges"]}
    for (a, b), pf in sorted(pairs.items()):
        if (a, b) not in inside:             # an edge cut out of a big component: judged as a pair of its own
            packets.append(dict(key=f"merge:{a}|{b}", kind="merge", cards=[a, b], edges=[dict(a=a, b=b, **pf)],
                                cut_edge=True))
    for c in cards:
        r = split_reason(c, F[c["cited_work_id"]])
        if r:
            packets.append(dict(key=f"split:{c['cited_work_id']}", kind="split", cards=[c["cited_work_id"]], **r))
        nw = notwork_reason(c)
        if nw:
            packets.append(dict(key=f"notwork:{c['cited_work_id']}", kind="notwork", cards=[c["cited_work_id"]], why=nw))
    catf = OUT / "catalogue" / "cat62.jsonl"
    ncat = Counter()
    if catf.exists():
        for l in open(catf, encoding="utf-8"):
            x = json.loads(l)
            ncat[x["decision"]] += 1
            if x["decision"] in ("accept", "candidate", "relation"):
                packets.append(dict(key=f"catalogue:{x['cited_work_id']}", kind="catalogue", cards=[x["cited_work_id"]],
                                    proposal=x["decision"], why=x["why"], best=x["best"], top=x["top"]))
    # a cited work that is one of the 780 articles read (title match against the articles' own titles)
    arts = json.loads((OUT / "articles62.json").read_text(encoding="utf-8"))
    at = {s: tokens(a["title"]) for s, a in arts.items() if a.get("title")}
    aidx = defaultdict(set)
    for s, ts in at.items():
        for w in set(ts):
            aidx[w].add(s)
    nread = 0
    for cid, f in F.items():
        if len(f["toks"]) < 3:
            continue
        cnt = Counter(s for w in set(f["toks"]) for s in aidx.get(w, ()))
        for s, n in cnt.most_common(3):
            if s in f["stems"]:
                continue
            ts = title_sim(f["toks"], at[s])
            if ts["dice"] >= 0.8:
                packets.append(dict(key=f"read:{cid}|{s}", kind="catalogue", cards=[cid], proposal="read-article",
                                    target_stem=s, target_title=arts[s]["title"], target_c999=arts[s]["c999"],
                                    target_pub_id=arts[s]["pub_id"], s_title=ts["dice"]))
                nread += 1
    with open(OUT / "packets62.jsonl", "w", encoding="utf-8") as f:
        for p in packets:
            f.write(json.dumps(p, ensure_ascii=False, default=list) + "\n")
    with open(OUT / "pairs62.jsonl", "w", encoding="utf-8") as f:
        for (a, b), pf in sorted(pairs.items()):
            f.write(json.dumps(dict(a=a, b=b, **pf), ensure_ascii=False, default=list) + "\n")
    B = dict(cards=len(cards), pairs_examined=len(seen), candidate_pairs=len(pairs), by_rule=dict(rule_n),
             clusters=len(clusters), cluster_sizes=dict(sorted(Counter(len(c) for c in clusters).items())),
             cards_in_clusters=len(cl_of),
             packets=dict(Counter(p["kind"] for p in packets)), catalogue_proposals=dict(ncat), read_article_hits=nread,
             desk_detector=dict(pairs=len(dpairs), covered=len(covered),
                                missed=sorted(map(list, dpairs - covered))))
    (OUT / "blocking62.json").write_text(json.dumps(B, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in B.items() if k != "desk_detector"} | dict(
        desk=dict(pairs=len(dpairs), covered=len(covered))), ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
