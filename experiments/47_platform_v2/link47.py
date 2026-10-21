"""Experiment 47: citations. For every version (one run's reading of a document) loaded by load47:

1. **Back references resolve to the FIRST FULL citation of the work in the article.** The article's citation
   mentions are walked in reading order. Full citations and short forms of the same work inside the article are one
   in-article work; «المرجع نفسه»/«نفسه»/ibid. take the mention just before them, «المرجع السابق»/op. cit. the earlier
   work named by the author (and title words) written before the marker; either way the pointer goes to that work's
   first full citation, never to another back reference, so chains collapse to one step and every back reference
   counts as one more citation of the work. What cannot be resolved stays NULL with unresolved_why.
2. **Cited works**: the full citations (and short forms with no full one) of the shown versions are grouped across
   articles into one card per work (title key + a shared author word), books included.
3. **Real links only**: each cited work is matched to the catalogue (marc.db, experiment 46's link_catalogue) and to
   the archive's own publications (link_articles); a confirmed match is an accepted citation_link to a publication
   (catalogued-only records become publications W<c999>), a title-only one a candidate; a record that reviews,
   studies or is part of the cited book is a work_relation, not a link. No back reference, no in-article pointer and
   no link from an article to itself is ever a citation_link.
4. The 54 hand checks of experiment 46 are carried into `reviews`, re-attached to the v2 subjects (or marked stale).
5. Metrics: resolution, times cited, true self-citation (shared person id), journal pairs, Quran index.

    .venv/bin/python experiments/47_platform_v2/link47.py            # versions not linked yet, then all cards
    .venv/bin/python experiments/47_platform_v2/link47.py --all      # re-resolve every version
    .venv/bin/python experiments/47_platform_v2/link47.py --report   # metrics only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import biblio47  # noqa: E402
from common47 import (DATA, DB, E46, V46, akey, split_life, calendar_of, connect, fill_pk, fold, greg_to_hijri,  # noqa: E402
                      hijri_to_greg, insert, jdump, key, marc, name_key, heading_key, name_parts, now, ratio, sha_files, script,
                      to_int, tokset, year_of)

sys.path.insert(0, str(E46))
import link46  # noqa: E402

THRESHOLDS = dict(in_article_title_tokset=0.8, in_article_title_ratio=0.85, short_note_words=12,
                  catalogue="link46.link_catalogue (title ratio >= 0.85; confident: title >= 0.9 + author, or + year "
                            "with >= 3 words, or >= 0.8 + author + year)", article="link46.link_articles")
COMMON = set("محمد احمد علي عبد بن ابن ابو ابي ام ال الله حسن حسين محمود مصطفى ابراهيم عمر عثمان يوسف سعيد صالح "
             "خالد عبدالله عبدالرحمن جمال الدين al el ibn abu bin mohamed mohammed muhammad ahmed ali".split())
CACHE = DATA / "link_cache47.json"


# ------------------------------------------------------------------ keys
def title_of(p: dict) -> str | None:
    """The cited work's own title: a journal article's or a chapter's title, else the book's (fix round 1: a chapter
    «La preuve» in a book is the chapter, not the book; the book is its container)."""
    if not p:
        return None
    return p.get("article_title") or p.get("chapter_title") or p.get("source_title")


def container_of(p: dict) -> str | None:
    """The book a chapter sits in (journal names vary too much in print to tell articles apart by them)."""
    if not p or not p.get("chapter_title") or p.get("article_title"):
        return None
    return p.get("source_title")


def tnorm(t: str | None) -> str:
    k = link46.tkey(t or "")
    k = akey(k) if re.search("[A-Za-zÀ-ɏ]", k) else k
    ws = [re.sub(r"^(ال|و?بال|لل)(?=\S{2,})", "", w) for w in k.split()]
    ws = ["بن" if w in ("ابن", "بن") else w for w in ws]
    return " ".join(w for w in ws if w)


def _join_abd(s: str) -> str:
    """«عبد الحكيم» and «عبدالحكيم» are one name word"""
    return re.sub(r"(?:^|(?<=\s))(ابو|عبد)\s+(?=\S)", r"\1", s)


def _atoks(sn, gn) -> set:
    out = set()
    for w in _join_abd(akey(f"{gn or ''} {sn or ''}")).split():
        w2 = re.sub(r"^ال", "", w)
        if len(w2) >= 3 and w2 not in COMMON and w not in COMMON:
            out.add(w2)
    return out


def author_tokens(p: dict) -> set:
    out = set()
    for sn, gn in (p or {}).get("authors") or []:
        out |= _atoks(sn, gn)
    return out


def first_author_tokens(p: dict) -> set:
    a = (p or {}).get("authors") or []
    return _atoks(*a[0]) if a else set()


def compatible(a: set, b: set) -> bool:
    return not a or not b or bool(a & b)


def same_title(t1: str, t2: str) -> bool:
    if not t1 or not t2:
        return False
    if t1 == t2:
        return True
    a, b = t1.replace(" ", ""), t2.replace(" ", "")
    if min(len(a), len(b)) >= 6 and (a in b or b in a) and tokset(t1, t2) >= THRESHOLDS["in_article_title_tokset"]:
        return True
    return tokset(t1, t2) >= 0.8 and ratio(t1, t2) >= THRESHOLDS["in_article_title_ratio"]


def same_container(a: dict, b: dict) -> bool:
    return not a["ck"] or not b["ck"] or same_title(a["ck"], b["ck"])


def contains_title(text_norm: str, title_norm: str) -> bool:
    """The title's words, in order, inside a printed citation («Rafi-ud-Din, The Qur'ān and Modern Knowledge, p. 259»)."""
    if not title_norm or len(title_norm.split()) < 2 or len(title_norm) < 8:
        return False
    return f" {title_norm} " in f" {text_norm} "


def title_in_text(m: dict, cands: list) -> dict | None:
    """The full (else any) citation whose title is printed in m's text, by an author m shares (when m names one);
    when several titles are printed, the first one is m's own («Rafi-ud-Din, The Qur'ān …, pp. 148-150; The Ideology
    of the Future …»)."""
    best = None
    for w in cands:
        if not w["tk"] or (m["au"] and not (m["au"] & w["au"])) or not contains_title(m["pn"], w["tk"]):
            continue
        pos = f" {m['pn']} ".find(f" {w['tk']} ")
        k = (pos, w["kind"] != "full", w["reading_ord"])
        if best is None or k < best[0]:
            best = (k, w)
    return best[1] if best else None


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


# ------------------------------------------------------------------ 1. resolution inside one version
HINT_STOP = re.compile(r"\b(ص|ج|جـ|مج|ط|p|pp|vol|no|voir|voy|see|cf|انظر|ينظر|يراجع|راجع|السابق|et|al|in|وانظر|"
                       r"المرجع|المصدر|مرجع|مصدر|سابق|نفسه|ذاته|op|cit|loc|ibid|id|aussi|also|cite|par|dans)\b")
YEAR_RE = re.compile(r"(?<![0-9])(1[0-9]{3}|20[0-9]{2})(?![0-9])")
# a note in between that breaks «المرجع نفسه» only when it looks like a citation (a page, a back reference, a
# publisher); an explanatory note («* لم تتوفر احصاءات …») does not
CITE_LIKE = re.compile(r"(?:^|\s)(?:ص|ص\.|صفحة|ج|p|pp|s|vol)\s*\.?\s*[0-9٠-٩]|المرجع|المصدر|مرجع|مصدر|op\.?\s*cit|"
                       r"ibid|ibíd|loc\.?\s*cit|(?:^|\s)دار\s|مطبعة|مكتبة|منشورات|(?:^|\s)ط\s*[0-9٠-٩]|§|"
                       r"(?:^|\s)n[°º]\s*\S|affaire|arr[êe]t|jugement|judgment|(?:^|\s)case\s|décision", re.I)
OWN_WORK = re.compile(r"(?:مؤلف|كتاب|بحث|دراست|مقال|مرجع)نا|notre (?:ouvrage|article|étude)|our (?:book|study|article)",
                      re.I)
PAGE_NEAR = 30           # pages: a back reference continues the work last cited within this many pages


def hint_words(h: str) -> list:
    k = HINT_STOP.sub(" ", akey(h or ""))
    return [w for w in k.split() if len(w) >= 3 and w not in link46.STOP and not w.isdigit()]


QUOTED = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”")


def whole_names(p: dict | None) -> set:
    return {name_key(f"{gn or ''} {sn or ''}") for sn, gn in (p or {}).get("authors") or []} - {""}


def page_of(x) -> int | None:
    v = to_int(str(x)) if x not in (None, "") else None
    return v if v and v < 20000 else None


def resolve(con, vid: int) -> dict:
    ms = [dict(r) for r in con.execute("SELECT * FROM citation_mentions WHERE version_id = ? ORDER BY reading_ord, "
                                       "mention_id", (vid,))]
    for m in ms:
        m["p"] = json.loads(m["parsed"]) if m["parsed"] else None
        m["tk"] = tnorm(title_of(m["p"])) if m["p"] else ""
        m["ck"] = tnorm(container_of(m["p"])) if m["p"] else ""
        m["au"] = author_tokens(m["p"])
        m["au1"] = first_author_tokens(m["p"])
        m["pn"] = tnorm(m["printed"])
        m["yr"] = year_of((m["p"] or {}).get("year")) if m["p"] else None
        m["borrowed"] = None
    # a citation whose parsed form lost its title (the reader's element-citation has none) takes the title of the
    # full citation of the same author whose title is printed in it, or, failing that, the only one by that author
    # with the same year
    titled = [m for m in ms if m["kind"] in ("full", "short") and m["tk"]]
    for m in ms:
        if m["kind"] not in ("full", "short") or m["tk"] or not m["p"]:
            continue
        src = title_in_text(m, titled)
        if not src and m["au"] and m["yr"]:
            ys = [w for w in titled if w["kind"] == "full" and w["au"] & m["au"] and w["yr"] == m["yr"]]
            if len({w["tk"] for w in ys}) == 1:
                src = ys[0]
        if src:
            m["tk"], m["ck"], m["borrowed"] = src["tk"], src["ck"], src["mention_id"]
            if not m["au"]:
                m["au"], m["au1"] = set(src["au"]), set(src["au1"])
    works = [m for m in ms if m["kind"] in ("full", "short") and m["tk"]]
    uf = UF()
    for i, a in enumerate(works):
        uf.find(a["mention_pk"])
        for b in works[:i]:
            if not same_container(a, b):
                continue
            if compatible(a["au"], b["au"]) and same_title(a["tk"], b["tk"]):
                uf.union(a["mention_pk"], b["mention_pk"])
            elif "short" in (a["kind"], b["kind"]) and a["au"] & b["au"] and tokset(a["tk"], b["tk"]) >= 0.6 and \
                    min(len(a["tk"].split()), len(b["tk"].split())) >= 2:
                uf.union(a["mention_pk"], b["mention_pk"])       # same author, most title words (a misprinted title)
            elif a["au"] & b["au"] and min(len(a["tk"].split()), len(b["tk"].split())) >= 3 and \
                    ratio(a["tk"], b["tk"]) >= 0.85:
                uf.union(a["mention_pk"], b["mention_pk"])       # same author, misprinted letters («Trautè … drait»)
    # a short form left alone whose printed text carries the title of a full citation by a compatible author
    root_kinds = defaultdict(set)
    for m in works:
        root_kinds[uf.find(m["mention_pk"])].add(m["kind"])
    fulls = [w for w in works if w["kind"] == "full"]
    for m in works:
        if m["kind"] == "short" and "full" not in root_kinds[uf.find(m["mention_pk"])]:
            w = title_in_text(m, [w for w in fulls if w["mention_pk"] != m["mention_pk"]])
            if w:
                uf.union(m["mention_pk"], w["mention_pk"])
                m["borrowed"] = m["borrowed"] or w["mention_id"]
    clusters = defaultdict(list)
    for m in works:
        clusters[uf.find(m["mention_pk"])].append(m)
    canon = {}
    for root, mm in clusters.items():
        fl = [m for m in mm if m["kind"] == "full"]
        c = min(fl or mm, key=lambda m: (m["reading_ord"], m["mention_id"]))
        for m in mm:
            canon[m["mention_pk"]] = c["mention_pk"]
    by_pk = {m["mention_pk"]: m for m in ms}
    # what each in-article work is known by: author tokens, first author, title (+ container) words, year
    wk_au, wk_au1, wk_tw, wk_cw, wk_yr = defaultdict(set), defaultdict(set), defaultdict(set), defaultdict(set), {}
    wk_whole = defaultdict(set)   # follow-up 2026-10-21: whole folded author names («أحمد إبراهيم محمود»: all common)
    for m in works:
        c = canon[m["mention_pk"]]
        wk_whole[c] |= whole_names(m["p"])
        wk_au[c] |= m["au"]
        wk_au1[c] |= m["au1"]
        wk_tw[c] |= {w for w in m["tk"].split() if len(w) >= 3}
        wk_cw[c] |= {w for w in m["ck"].split() if len(w) >= 3}
        if m["yr"] and c not in wk_yr:
            wk_yr[c] = m["yr"]
    pages = defaultdict(list)     # canonical -> pages cited so far (reading order)
    notes = {r["note_id"]: dict(r) for r in con.execute("SELECT note_id, ord, text FROM notes WHERE version_id = ?", (vid,))}
    byline_toks = set()
    for (n,) in con.execute("SELECT name_text FROM byline_mentions WHERE version_id = ?", (vid,)):
        byline_toks |= _atoks(n, "")
    note_has = {m["container_id"] for m in ms if m["container_kind"] == "note"}
    upd = []
    stats = Counter()
    target = {}      # mention_pk -> canonical pk it counts for
    prev = None
    refs = [m for m in ms if m["container_kind"] == "ref-list" and m["kind"] in ("full", "short")]

    def by_page(cands, pg):
        """the candidate whose cited pages run on to this one («op. cit., p. 954» after p. 945, 946 …)"""
        if not pg:
            return None
        d = sorted((min(abs(pg - q) for q in pages[c]), k, c) for k, c in enumerate(cands) if pages.get(c))
        if d and d[0][0] <= PAGE_NEAR and (len(d) == 1 or d[1][0] > 2 * d[0][0] + 5):
            return d[0][2]
        return None

    for idx, m in enumerate(ms):
        pk = m["mention_pk"]
        u = dict(full_mention_pk=None, resolve_method=None, resolve_score=None, resolved_by=None, unresolved_why=None,
                 resolve_evidence=m["resolve_evidence"])
        k = m["kind"]
        pg = page_of(m["cited_pages"])
        if k == "full":
            u.update(full_mention_pk=pk, resolve_method="self", resolve_score=1.0, resolved_by="link47")
            target[pk] = canon.get(pk, pk)
        elif k == "short":
            c = canon.get(pk)
            if c and c != pk and by_pk[c]["kind"] == "full":
                how = "short-form+title-in-text" if m["borrowed"] else "short-form"
                u.update(full_mention_pk=c, resolve_method=how, resolve_score=0.9 if not m["borrowed"] else 0.85,
                         resolved_by="link47")
                if m["borrowed"]:
                    ev = json.loads(m["resolve_evidence"]) if m["resolve_evidence"] else {}
                    u["resolve_evidence"] = jdump(dict(ev, title_from=m["borrowed"]))
            else:
                u.update(unresolved_why="no-full-citation" if m["tk"] else "no-title")
            target[pk] = canon.get(pk, pk)
        elif k == "quran":
            target[pk] = pk
        elif k in ("ibid", "op_cit", "loc_cit"):
            ev = json.loads(m["resolve_evidence"]) if m["resolve_evidence"] else {}
            hint = ev.get("hint") or ""
            hw = hint_words(hint) if k != "ibid" else []
            if not hw and k != "ibid" and m["marker"] and m["printed"] and m["marker"] in m["printed"]:
                tail = m["printed"].split(m["marker"], 1)[1]       # «Op. cit Ziauddin Sardar.»: the name after it
                if not tail.strip(" .،,") and m["container_kind"] == "note":
                    nt = (notes.get(m["container_id"]) or {}).get("text") or ""
                    tail = nt.split(m["marker"], 1)[1] if m["marker"] in nt else ""
                if 0 < len(tail.split()) <= 6 and not re.search(r"[0-9٠-٩]", tail):
                    hw, hint = hint_words(tail), tail
            years = {int(y) for y in YEAR_RE.findall(fold(hint))} if k != "ibid" else set()
            tgt, how, sc, why = None, None, None, None
            if prev is not None and prev["container_kind"] == m["container_kind"] == "note" and \
                    prev["container_id"] == m["container_id"] and prev["kind"] in ("full", "short") and not hw:
                # «Pincus: Economic Aid, op. cit., 362»: the marker is part of the citation just parsed; that citation
                # place is counted once (as the parsed mention, resolved to its work's first full citation)
                u.update(resolve_method="part-of-citation", resolved_by="link47",
                         resolve_evidence=jdump(dict(ev, citation=prev["mention_id"])))
                stats["part-of-citation"] += 1
                target[pk] = target.get(prev["mention_pk"], prev["mention_pk"])
                upd.append((None, u["resolve_method"], None, u["resolved_by"], None, u["resolve_evidence"], pk))
                prev = m
                continue
            earlier = [x for x in ms[:idx] if x["kind"] in ("full", "short") and x["tk"]]
            if OWN_WORK.search(f"{m['marker'] or ''} {hint} {m['printed'] or ''}") and byline_toks:
                # «مؤلفنا السابق» («our earlier work»): the latest earlier work by the article's own author
                pool = list(reversed(earlier)) + [x for x in refs if x not in earlier]
                own = [canon.get(x["mention_pk"], x["mention_pk"]) for x in pool
                       if len(wk_au[canon.get(x["mention_pk"], x["mention_pk"])] & byline_toks) >= 2 or
                       (wk_au[canon.get(x["mention_pk"], x["mention_pk"])] and
                        wk_au[canon.get(x["mention_pk"], x["mention_pk"])] <= byline_toks)]
                if own:
                    tgt, how, sc = own[0], "own-earlier-work", 0.8
                    hw = []
            if tgt:
                pass
            elif hw:
                hs = set(hw) | {re.sub(r"^ال", "", h) for h in hw}
                # follow-up 2026-10-21: the author is looked for outside quoted titles («CHEN. «Le roman policier de
                # Fred Vargas…». Op.Cit.» names the thesis, not Vargas); the quoted words still count as title words
                hw_a = hint_words(QUOTED.sub(" ", hint)) if QUOTED.search(hint) else hw
                hs_a = set(hw_a) | {re.sub(r"^ال", "", h) for h in hw_a}
                hwhole = name_key(QUOTED.sub(" ", hint).strip(" .،,:؛;()"))
                pool = list(reversed(earlier)) + [x for x in refs if x not in earlier]
                cands = []                 # in-article works, most recently cited first
                for x in pool:
                    c = canon.get(x["mention_pk"], x["mention_pk"])
                    if c not in cands:
                        cands.append(c)
                A = [c for c in cands if wk_au[c] & hs_a]
                if not A and hwhole:
                    # a name made only of common words leaves no token: the whole folded name, as judge_link does
                    A = [c for c in cands if hwhole in wk_whole[c]]
                if A:
                    if years and [c for c in A if wk_yr.get(c) in years]:
                        A = [c for c in A if wk_yr.get(c) in years]       # «ROLDAN et al., 2006, op. cit.»
                    if len(A) > 1 and [c for c in A if wk_au1[c] & hs_a]:
                        A = [c for c in A if wk_au1[c] & hs_a]            # the name printed is the first author
                    left = {h for h in hs if h not in set().union(*(wk_au[c] for c in A))}
                    # words of the work's own title, then of the book it sits in («La preuve», in Commentaire …)
                    hits = [(len(wk_tw[c] & left) + len(wk_cw[c] & left),
                             round(len(wk_tw[c] & left) / max(1, len(wk_tw[c])), 3), c) for c in A]
                    top = max((h[:2] for h in hits), default=(0, 0))
                    T = [c for n, cv, c in hits if (n, cv) == top] if top[1] else A   # the book's words alone never pick
                    base = "same-author+title-words" if top[1] else ("same-author+year" if years and len(A) == 1 and
                                                                    wk_yr.get(A[0]) in years else "same-author-earliest")
                    unexplained = len(left) >= 3 and not top[1]
                    if len(T) > 1 and unexplained:
                        why = ("no-earlier-full: the title printed matches none of the author's earlier works "
                               f"({len(T)} by that author)")
                        T = []
                    if len(T) == 1:
                        tgt, how, sc = T[0], base, 0.95 if top[1] else (0.7 if unexplained else 0.9)
                        if unexplained:
                            why = "the author's only earlier work; words printed beside the name do not match it"
                    elif T:
                        bp = by_page(T, pg)
                        if bp:
                            tgt, how, sc = bp, ("same-author+title-words+page" if top[0] else
                                                "same-author+page-continuity"), 0.75
                        else:
                            tgt, how, sc = T[0], "same-author-latest", 0.5
                            why = (f"ambiguous: {len(T)} works by the author fit the words printed; the one cited "
                                   f"most recently is taken (citation-style rule)")
                if not tgt and not why and len(hw) <= THRESHOLDS["short_note_words"]:
                    hs2 = set(hw) | {re.sub(r"^ال", "", h) for h in hw}
                    hits = []
                    for c in cands:
                        tw = wk_tw[c]
                        n = len(tw & hs2)
                        if tw and n >= min(2, len(tw)) and (not QUOTED.search(hint) or n >= 0.5 * len(hs2)):
                            # a quoted title printed whole must be mostly the work's title, not two shared words
                            hits.append((n / len(tw), n, -cands.index(c), c))
                    if hits:
                        hits.sort(reverse=True)
                        T = [h[3] for h in hits if h[:2] == hits[0][:2]]
                        if len(T) == 1:
                            tgt, how, sc = T[0], "title-words", 0.8
                        else:
                            bp = by_page(T, pg)
                            tgt, how, sc = (bp, "title-words+page", 0.7) if bp else (T[0], "title-words-latest", 0.5)
                            if not bp:
                                why = f"ambiguous: {len(T)} works share the title words; the most recent taken"
                if not tgt and not why and hs_a:
                    # follow-up 2026-10-21: an earlier citation by that author whose title the masters did not parse
                    # («أدونيس العكرة. الإرهاب السياسي…», typed short with no title): the only one by that author
                    U = []
                    for x in ms[:idx]:
                        if x["kind"] in ("full", "short") and not x["tk"] and x["p"] and \
                                (x["container_kind"], x["container_id"]) != (m["container_kind"], m["container_id"]) and \
                                ((x["au"] & hs_a) or (hwhole and hwhole in whole_names(x["p"]))):
                            if not any(by_pk[u_]["au"] == x["au"] and whole_names(by_pk[u_]["p"]) ==
                                       whole_names(x["p"]) for u_ in U):
                                U.append(x["mention_pk"])
                    if len(U) == 1 and not [c for c in cands if wk_au[c] & hs_a]:
                        tgt, how, sc = U[0], "same-author-untitled", 0.7
                        why = "the author's only earlier citation; its title was not parsed"
                if not tgt and not why and (k != "ibid" and len(hw) >= 1):
                    why = "no-earlier-full: names a work not parsed earlier in the article"
            if not tgt and not why:
                # ibid (or a bare op. cit.): the mention just before; a citation-like note with no parsed citation
                # in between breaks it
                p = prev
                if p is None:
                    why = "no-earlier-mention"
                else:
                    gap = False
                    if m["container_kind"] == "note" and p["container_kind"] == "note":
                        lo, hi = notes.get(p["container_id"], {}).get("ord"), notes.get(m["container_id"], {}).get("ord")
                        if lo is not None and hi is not None:
                            for nid, n in notes.items():
                                t = (n["text"] or "").strip()
                                if lo < n["ord"] < hi and nid not in note_has and len(t.split()) <= 30 \
                                        and not t.startswith("*") and CITE_LIKE.search(t):
                                    gap = True
                    if gap:
                        why = "previous-not-parsed: a citation-like note without a parsed citation lies in between"
                    elif p["kind"] in ("ibid", "op_cit", "loc_cit"):
                        if target.get(p["mention_pk"]):
                            tgt, how, sc = target[p["mention_pk"]], "previous-mention (chain collapsed)", 0.85
                        else:
                            why = "chain-broken: the back reference before it is unresolved"
                    else:
                        tgt, how, sc = target.get(p["mention_pk"], p["mention_pk"]), "previous-mention", 0.9
            if tgt:
                u.update(full_mention_pk=tgt, resolve_method=how, resolve_score=sc, resolved_by="link47")
                if why:
                    ev["note"] = why
                    u["resolve_evidence"] = jdump(ev)
                target[pk] = tgt
                stats[f"resolved:{how}"] += 1
            else:
                u["unresolved_why"] = why
                stats[f"unresolved:{(why or '').split(':')[0]}"] += 1
        if target.get(pk) and pg:
            pages[target[pk]].append(pg)
        upd.append((u["full_mention_pk"], u["resolve_method"], u["resolve_score"], u["resolved_by"],
                    u["unresolved_why"], u["resolve_evidence"], pk))
        if k != "see_also":
            prev = m
    con.executemany("UPDATE citation_mentions SET full_mention_pk = ?, resolve_method = ?, resolve_score = ?, "
                    "resolved_by = ?, unresolved_why = ?, resolve_evidence = ? WHERE mention_pk = ?", upd)
    return dict(stats=stats, clusters={canon[mm[0]["mention_pk"]]: [m["mention_pk"] for m in mm]
                                       for mm in clusters.values()},
                mentions={m["mention_pk"]: m for m in works})


# ------------------------------------------------------------------ 2. cited works across articles
def build_cited_works(con, res: dict, load_id: int) -> dict:
    """One card per work across the shown versions (title key + container + a shared author word). The card's id
    comes from its content key; a card whose key moved (a new member changed its representative) keeps the id its
    members had, and an id no card keeps any more is retired into merged_ids — never re-minted silently."""
    vkey = {r[0]: r[1] for r in con.execute("SELECT version_id, version_key FROM versions")}
    old_of = {}          # (version_key, mention_id) -> old active cited_work_id
    for r in con.execute("""SELECT v.version_key, c.mention_id, w.cited_work_id FROM cited_work_members m
                            JOIN citation_mentions c ON c.mention_pk = m.full_mention_pk
                            JOIN versions v ON v.version_id = c.version_id
                            JOIN cited_works w ON w.cited_work_pk = m.cited_work_pk WHERE w.status = 'active'"""):
        old_of[(r[0], r[1])] = r[2]
    old_active = {r[0] for r in con.execute("SELECT cited_work_id FROM cited_works WHERE status = 'active'")}
    groups = []          # (canonical pk, mention dict, member pks, version id)
    for vid in sorted(res, key=lambda v: vkey[v]):
        r = res[vid]
        for c in sorted(r["clusters"], key=lambda c: r["mentions"][c]["mention_id"]):
            groups.append((c, r["mentions"][c], r["clusters"][c], vid))
    by_t = defaultdict(list)
    for i, g in enumerate(groups):
        by_t[g[1]["tk"]].append(i)
    uf = UF()
    for t, ix in by_t.items():
        for a in ix:
            uf.find(a)
            for b in ix:
                if b < a and compatible(groups[a][1]["au"], groups[b][1]["au"]) and \
                        same_container(groups[a][1], groups[b][1]):
                    uf.union(a, b)
    cw = defaultdict(list)
    for i in range(len(groups)):
        cw[uf.find(i)].append(i)
    cards = []
    for root, ix in cw.items():
        reps = [groups[i] for i in ix]
        allm = [res[g[3]]["mentions"][pk] for g in reps for pk in g[2] if pk in res[g[3]]["mentions"]]
        rep = max(reps, key=lambda g: (g[1]["kind"] == "full", bool((g[1]["p"] or {}).get("authors")),
                                       len(json.dumps(g[1]["p"] or {}, sort_keys=True)),
                                       [-ord(ch) for ch in f"{vkey[g[3]]}|{g[1]['mention_id']}"]))[1]
        au = Counter(w for g in reps for w in sorted(g[1]["au"]))
        akey_ = sorted(au.items(), key=lambda x: (-x[1], x[0]))[0][0] if au else ""
        nat = f"cw:{rep['tk']}|{rep['ck']}|{akey_}" if rep["ck"] else f"cw:{rep['tk']}|{akey_}"
        members = [(vkey[g[3]], res[g[3]]["mentions"][pk]["mention_id"]) for g in reps for pk in g[2]
                   if pk in res[g[3]]["mentions"] and (res[g[3]]["mentions"][pk]["kind"] == "full" or pk == g[0])]
        # the authors: the representative's, else the most common author list among all the members
        alist = (rep["p"] or {}).get("authors") or []
        if not alist:
            cnt = Counter(json.dumps(m["p"]["authors"], ensure_ascii=False) for m in allm
                          if m["p"] and m["p"].get("authors"))
            if cnt:
                alist = json.loads(sorted(cnt.items(), key=lambda x: (-x[1], x[0]))[0][0])
        cards.append(dict(nat=nat, rep=rep, reps=reps, members=members, akey=akey_, authors=alist))
    # ids: a known content key keeps its id; otherwise the old id most of the members had; otherwise a new one
    claimed = {}
    for cd in cards:
        r = con.execute("SELECT public_id FROM id_registry WHERE kind = 'cited_work' AND natural_key = ?",
                        (cd["nat"],)).fetchone()
        if r and r[0] not in claimed.values():
            cd["id"] = r[0]
            claimed[cd["nat"]] = r[0]
    rest = [cd for cd in cards if "id" not in cd]
    prefs = []
    for cd in rest:
        votes = Counter(old_of[m] for m in cd["members"] if m in old_of)
        for oid, n in votes.items():
            prefs.append((-n, cd["nat"], oid))
    for _, nat, oid in sorted(prefs):
        cd = next(c for c in rest if c["nat"] == nat)
        if "id" not in cd and oid not in claimed.values():
            cd["id"] = oid
            claimed[nat] = oid
    for cd in sorted(rest, key=lambda c: c["nat"]):
        if "id" not in cd:
            nat, n = cd["nat"], 1
            while True:
                pid = biblio47.public_id(con, "cited_work", nat, load_id)
                if pid not in claimed.values():
                    break
                n += 1
                nat = f"{cd['nat']}#{n}"         # two cards with one content key (authors told them apart)
            cd["id"] = pid
            claimed[nat] = pid
    con.execute("DELETE FROM cited_work_members")
    con.execute("DELETE FROM cited_work_authors")
    keep, out = set(), {}
    for cd in cards:
        rep, cid = cd["rep"], cd["id"]
        p = rep["p"] or {}
        yp = p.get("year")
        y = year_of(yp)
        cal = calendar_of(f"{yp or ''} {rep['printed'] or ''}" if y and re.search(r"%s\s*هـ" % y, fold(rep["printed"] or ""))
                          else yp, y) if y else None
        pt = p.get("pub_type") or ("article" if p.get("article_title") else "book")
        if p.get("chapter_title") and not p.get("article_title") and pt == "book":
            pt = "chapter"
        row = fill_pk("cited_works", [dict(cited_work_id=cid)])[0]
        cpk = row["cited_work_pk"]
        con.execute("""INSERT INTO cited_works (cited_work_pk, cited_work_id, pub_type, title, title_key, first_author_key,
                       year_printed, year_calendar, year_hijri, year_greg, edition_note, place, publisher, lang, status,
                       method, built_load) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'active', ?, ?)
                       ON CONFLICT(cited_work_id) DO UPDATE SET pub_type = excluded.pub_type, title = excluded.title,
                       title_key = excluded.title_key, first_author_key = excluded.first_author_key,
                       year_printed = excluded.year_printed, year_calendar = excluded.year_calendar,
                       year_hijri = excluded.year_hijri, year_greg = excluded.year_greg, place = excluded.place,
                       publisher = excluded.publisher, lang = excluded.lang, status = 'active',
                       built_load = excluded.built_load""",
                    (cpk, cid, pt, title_of(p), rep["tk"], cd["akey"] or None, yp, cal,
                     y if cal == "hijri" else (greg_to_hijri(y) if y else None),
                     hijri_to_greg(y) if cal == "hijri" else y, (p.get("extra") or {}).get("edition") if isinstance(
                         p.get("extra"), dict) else None, p.get("place"), p.get("publisher"),
                     "ara" if script(title_of(p)) == "Arab" else ("lat" if title_of(p) else None),
                     "title-key + container + shared author word", load_id))
        cpk = con.execute("SELECT cited_work_pk FROM cited_works WHERE cited_work_id = ?", (cid,)).fetchone()[0]
        keep.add(cid)
        for c, m, pks, vid in cd["reps"]:
            for pk in pks:
                mm = res[vid]["mentions"].get(pk)
                if mm and (mm["kind"] == "full" or pk == c):
                    con.execute("INSERT OR REPLACE INTO cited_work_members VALUES (?,?,?,?,?, 'link47', NULL)",
                                (pk, cpk, "in-article-first" if pk == c else "in-article-repeat",
                                 1.0 if pk == c else 0.9,
                                 jdump(dict(title_key=m["tk"], container_key=m["ck"] or None, authors=sorted(m["au"])))))
        for k, (sn, gn) in enumerate(cd["authors"]):
            printed = " ".join(x for x in (gn, sn) if x)
            pp = name_parts(printed)
            con.execute("INSERT OR REPLACE INTO cited_work_authors (cited_work_pk, seq, printed, honorific, kunya, ism, "
                        "nasab, nisba, laqab, shuhra, latin, name_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (cpk, k + 1, printed, pp["titles"], pp["kunya"], pp["ism"], pp["nasab"], pp["nisba"],
                         pp["laqab"], pp["shuhra"], printed if script(printed) == "Latn" else None,
                         name_key(printed)))
        out[cpk] = dict(rep=rep, citing=set(), authors=cd["authors"])
    # retired ids: written to merged_ids (old -> the card that holds most of its members now)
    new_of = {m: cd["id"] for cd in cards for m in cd["members"]}
    for oid in sorted(old_active - keep):
        votes = Counter(new_of[m] for m, o in old_of.items() if o == oid and m in new_of)
        con.execute("UPDATE cited_works SET status = 'merged' WHERE cited_work_id = ?", (oid,))
        if votes:
            nid = sorted(votes.items(), key=lambda x: (-x[1], x[0]))[0][0]
            con.execute("INSERT OR REPLACE INTO merged_ids VALUES (?,?, 'cited_work', 'merged-into', ?, ?, 'link47', "
                        "NULL)", (oid, nid, now(), f"{sum(votes.values())} of its members are now on {nid}"))
    return out


# ------------------------------------------------------------------ 3. real links
def name_tokens(name: str | None) -> set:
    out = set()
    for w in _join_abd(akey(split_life(name or "")[0])).split():
        w2 = re.sub(r"^ال", "", w)
        if len(w2) >= 3 and w2 not in COMMON and w not in COMMON:
            out.add(w2)
    return out


def near_token(a: str, b: str) -> bool:
    """the same name word, allowing one misread letter in a word of 4+ («العبلي» for «العيلي»)"""
    if a == b:
        return True
    if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    lo, hi = (a, b) if len(a) < len(b) else (b, a)
    return any(hi[:i] + hi[i + 1:] == lo for i in range(len(hi)))


def judge_link(confident: bool, authors: list, target_names: list, where: str):
    """(status, best, method, author evidence). A link is best only when the authors agree (a shared name word in
    either script, the record's Latin heading included); a match the record's own authors contradict is rejected;
    one with no author to compare stays a candidate, however good the title."""
    cited = set()
    for sn, gn in authors or []:
        cited |= _atoks(sn, gn)
        whole = akey(f"{gn or ''} {sn or ''}").replace(" ", "").replace("-", "")
        if script(whole) == "Latn" and len(whole) >= 6:
            cited.add(whole)                       # «Abdul Razzaq» = abdulrazzaq
    tgt = set()
    for n, lat in target_names:
        tgt |= name_tokens(n) | name_tokens(lat)
    for t in [t for t in tgt if script(t) == "Arab"]:
        # the catalogue's own Arabic→Latin name pairs (translit_pairs): «عبدالرزاق» -> abdulrazzaq, abdul razzaq …
        for lat in TRANSLIT.get(t, set()) | TRANSLIT.get("ال" + t, set()):
            tgt.add(lat.replace(" ", "").replace("-", ""))
            tgt |= {w for w in lat.split() if len(w) >= 3 and w not in COMMON}
    shared = sorted({a for a in cited for b in tgt if near_token(a, b)})
    # fix round 2: a name made only of common words («أحمد إبراهيم محمود») leaves no token to compare; then the
    # whole folded name is compared (equal = agree; a difference proves nothing, so it stays unknown)
    cfull = {name_key(f"{gn or ''} {sn or ''}") for sn, gn in authors or []} - {""}
    tfull = {heading_key(x) if re.search("[،,]", x) else name_key(x) for n, lat in target_names for x in (n, lat)
             if x} - {""}
    whole = sorted(cfull & tfull)
    if not cited or not tgt:
        agree = "agree" if whole else "unknown"
    else:
        agree = "agree" if shared or whole else "contradict"
    ev = dict(agreement=agree, cited=sorted(cited), target=sorted(tgt), shared=shared)
    if whole:
        ev["whole_name"] = whole
    base = "catalogue-fts" if where == "catalogue" else "article-fts"
    if agree == "contradict":
        return "rejected", 0, f"{base} (authors contradict)", ev
    if confident and agree == "agree":
        return "accepted", 1, f"{base}+validate", ev
    if confident:
        return "candidate", 0, f"{base}+validate (no author to compare)", ev
    return "candidate", 0, f"{base} (title only)" + (", authors agree" if agree == "agree" else ""), ev


TRANSLIT = {}


def link_cards(con, mcon, cards: dict, link_run_id: int, load_id=None) -> Counter:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    TRANSLIT.clear()
    for ar, lat in con.execute("SELECT arabic, latin FROM translit_pairs WHERE share >= 0.05 AND n >= 5"):
        TRANSLIT.setdefault(ar, set()).add(lat)
    chash = sha_files([HERE / "link47.py", E46 / "link46.py"])
    con.execute("DELETE FROM citation_links WHERE asserted_by = 'link47'")
    con.execute("DELETE FROM work_relations WHERE asserted_by = 'link47'")
    # citing publications of each card (an article never links to itself)
    for r in con.execute("""SELECT m.cited_work_pk, p.pub_id, p.c999 FROM cited_work_members m
                            JOIN citation_mentions c ON c.mention_pk = m.full_mention_pk
                            JOIN versions v ON v.version_id = c.version_id JOIN documents d ON d.stem = v.stem
                            JOIN publications p ON p.pub_id = d.pub_id"""):
        if r["cited_work_pk"] in cards:
            cards[r["cited_work_pk"]]["citing"].add(r["pub_id"])
    arts = []
    for r in con.execute("""SELECT d.stem, p.pub_id, p.year_shown AS pub_year,
                            (SELECT value FROM metadata_assertions a WHERE a.pub_id = p.pub_id AND a.field = 'title'
                             AND a.is_chosen = 1 LIMIT 1) AS title FROM documents d JOIN publications p ON p.pub_id = d.pub_id"""):
        x = dict(r)
        ts = [t[0] for t in con.execute("SELECT DISTINCT value FROM metadata_assertions WHERE pub_id = ? AND field IN "
                                        "('title', 'title_translated')", (r["pub_id"],))]
        x["_tk"] = [link46.tkey(t) for t in ts if t] or [""]
        x["_authors"] = [t[0] for t in con.execute(
            "SELECT b.name_text FROM authorships a JOIN authorship_mentions am USING (authorship_pk) JOIN byline_mentions "
            "b USING (mention_pk) WHERE a.pub_id = ? UNION SELECT c.name FROM authorships a JOIN catalogue_contributors c "
            "ON c.c999 = a.c999 AND c.seq = a.catalogue_seq WHERE a.pub_id = ?", (r["pub_id"], r["pub_id"]))]
        arts.append(x)
    S = Counter()
    REL = {"review": ("is_reviewed_in", "reviews"), "about": ("is_studied_in", "studies"),
           "part": ("is_part_of", "has_part")}
    t0 = time.time()
    for i, (cpk, c) in enumerate(cards.items()):
        rep = c["rep"]
        p = rep["p"] or {}
        w = dict(article_title=p.get("article_title"), pub_type=p.get("pub_type"), source_title=p.get("source_title"),
                 chapter_title=p.get("chapter_title"), authors=json.dumps(c["authors"] or [], ensure_ascii=False),
                 year_int=year_of(p.get("year")), stem=None)
        ck = hashlib.sha1(json.dumps([chash, w], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if ck not in cache:
            f = link46.link_catalogue(mcon, w, None)
            cache[ck] = f
        f = cache[ck]
        if f:
            ev = json.loads(f["evidence"])
            c999 = ev.get("c999")
            rel = ev.get("relation")
            tp = biblio47.ensure_catalogued_pub(con, mcon, c999, load_id) if c999 else None
            if tp and tp in c["citing"]:
                S["dropped: catalogue match is a citing article itself"] += 1
            elif tp and rel in REL:
                insert(con, "work_relations", [dict(subject_cited_work_pk=cpk, relation=REL[rel][0], inverse=REL[rel][1],
                                                    object_pub_id=tp, score=f["score"], method=f["method"],
                                                    evidence=f["evidence"], asserted_by="link47",
                                                    link_run_id=link_run_id)], "INSERT")
                S[f"relation:{REL[rel][0]}"] += 1
            elif tp:
                names = [(r["name"], r["latin"]) for r in con.execute(
                    "SELECT name, latin FROM catalogue_contributors WHERE c999 = ? ORDER BY seq", (c999,))]
                st, best, method, ag = judge_link(bool(f["best"]), c["authors"], names, "catalogue")
                f_ev = jdump(dict(json.loads(f["evidence"]), authors=ag))
                insert(con, "citation_links", [dict(
                    cited_work_pk=cpk, via_mention_pk=rep["mention_pk"], target_kind="publication", target_pub_id=tp,
                    status=st, best=best, score=f["score"], method=method, matched_on="printed", evidence=f_ev,
                    asserted_by="link47", link_run_id=link_run_id, created=now())], "INSERT OR IGNORE")
                S[f"link:catalogue:{st}"] += 1
        x = [a for a in arts if a["pub_id"] not in c["citing"]]
        fa = link46.link_articles(x, dict(w, stem="")) if len(link46.tkey(title_of(p)).split()) >= 2 else None
        if fa:
            tgt = next(a for a in x if a["stem"] == fa["target_id"])
            st, best, method, ag = judge_link(bool(fa["best"]), c["authors"], [(n, None) for n in tgt["_authors"]],
                                              "article")
            insert(con, "citation_links", [dict(
                cited_work_pk=cpk, via_mention_pk=rep["mention_pk"], target_kind="publication",
                target_pub_id=tgt["pub_id"], status=st, best=best, score=fa["score"], method=method,
                matched_on="printed", evidence=jdump(dict(json.loads(fa["evidence"]), authors=ag)),
                asserted_by="link47", link_run_id=link_run_id, created=now())], "INSERT OR IGNORE")
            S[f"link:article:{st}"] += 1
        if (i + 1) % 500 == 0:
            print(f"  linked {i + 1}/{len(cards)} cards ({time.time() - t0:.0f} s)", flush=True)
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    # best: one accepted link per card (the highest score; ties by target id)
    con.execute("""UPDATE citation_links SET best = 0 WHERE best = 1 AND link_pk NOT IN (SELECT link_pk FROM
                   (SELECT link_pk, row_number() OVER (PARTITION BY cited_work_pk ORDER BY score DESC, target_pub_id)
                   rn FROM citation_links WHERE best = 1) WHERE rn = 1)""")
    return S


# ------------------------------------------------------------------ 4. experiment 46's hand checks
def carry_checks(con, mcon) -> Counter:
    S = Counter()
    con.execute("DELETE FROM reviews WHERE source_file = 'link_checks'")
    rv = []
    v46 = connect(V46, ro=True)
    for c in v46.execute("SELECT * FROM link_checks ORDER BY rowid").fetchall():
        fk, fid = c["from_kind"], c["from_id"]
        stem = fid.split("|")[0]
        vid = con.execute("SELECT version_id FROM versions WHERE stem = ? AND is_current = 1", (stem,)).fetchone()
        subj, kind, fp, attach = None, None, None, "stale"
        if vid:
            vid = vid[0]
            if fk == "work":
                _, cont, seq = fid.split("|")
                ck, cid = cont.split(":", 1)
                ms = con.execute("SELECT * FROM citation_mentions WHERE version_id = ? AND container_id = ? AND kind IN "
                                 "('full', 'short') ORDER BY seq_in_container", (vid, cid)).fetchall()
                m = ms[int(seq)] if int(seq) < len(ms) else None
                if m:
                    rec = mcon.execute("SELECT c999, title FROM records WHERE rec = ?", (int(c["target_id"]),)).fetchone()
                    c999 = rec["c999"] if rec else None
                    cw = con.execute("SELECT cited_work_pk FROM cited_work_members WHERE full_mention_pk = ?",
                                     (m["full_mention_pk"] or m["mention_pk"],)).fetchone()
                    kind = "relation" if c["verdict"] == "withheld-ok" else "link"
                    subj = f"{m['mention_id']}->W{c999}"
                    fp = hashlib.sha1(f"{m['printed']}|{rec['title'] if rec else ''}".encode()).hexdigest()[:16]
                    if cw:
                        l = con.execute("SELECT status FROM citation_links WHERE cited_work_pk = ? AND target_pub_id = ?",
                                        (cw[0], f"W{c999}")).fetchone()
                        r = con.execute("SELECT relation FROM work_relations WHERE subject_cited_work_pk = ? AND "
                                        "object_pub_id = ?", (cw[0], f"W{c999}")).fetchone()
                        attach = f"v2 link {l[0]}" if l else (f"v2 relation {r[0]}" if r else "v2 has no such link")
            else:
                note = fid.split("|")[1]
                m = con.execute("SELECT * FROM citation_mentions WHERE version_id = ? AND container_id = ? AND kind IN "
                                "('ibid', 'op_cit', 'loc_cit') ORDER BY seq_in_container LIMIT 1", (vid, note)).fetchone()
                if m:
                    kind, subj = "resolution", m["mention_id"]
                    fp = hashlib.sha1((m["printed"] or "").encode()).hexdigest()[:16]
                    tw = c["target_id"].split("|")   # stem|note:fn-..|k  (the v46 target work)
                    _, cont, seq = tw
                    ck, cid = cont.split(":", 1)
                    ms = con.execute("SELECT mention_pk, full_mention_pk FROM citation_mentions WHERE version_id = ? AND "
                                     "container_id = ? AND kind IN ('full', 'short') ORDER BY seq_in_container",
                                     (vid, cid)).fetchall()
                    old = ms[int(seq)] if int(seq) < len(ms) else None
                    eff = m["full_mention_pk"]
                    if eff is None and m["resolve_method"] == "part-of-citation":
                        cm = con.execute("SELECT mention_pk, full_mention_pk FROM citation_mentions WHERE version_id = ? "
                                         "AND mention_id = ?", (vid, json.loads(m["resolve_evidence"])["citation"])
                                         ).fetchone()
                        eff = (cm["full_mention_pk"] or cm["mention_pk"]) if cm else None
                    if eff is None:
                        attach = f"v2 leaves it unresolved ({m['unresolved_why']})"
                    elif old:
                        oe = old["full_mention_pk"] or old["mention_pk"]
                        a = con.execute("SELECT cited_work_pk FROM cited_work_members WHERE full_mention_pk = ?",
                                        (eff,)).fetchone()
                        b = con.execute("SELECT cited_work_pk FROM cited_work_members WHERE full_mention_pk = ?",
                                        (oe,)).fetchone()
                        attach = "v2 resolves to the same work" if eff == oe or (a and b and a[0] == b[0]) else \
                            "v2 resolves to a different work"
                    else:
                        attach = "v46 target not found in v2"
        S[attach.split(" (")[0]] += 1
        rv.append((dict(subject_kind=kind or ("link" if fk == "work" else "resolution"),
                                     subject_key=subj or f"v46:{fk}:{fid}->{c['target_kind']}:{c['target_id']}",
                                     subject_fingerprint=fp,
                                     verdict={"near": "partly", "withheld-ok": "right"}.get(c["verdict"], c["verdict"]),
                                     note=f"{c['note']} | v46 {fk} {fid} -> {c['target_kind']} {c['target_id']} | "
                                          f"attached: {attach}",
                                     actor_id="agent:agent-46", checked=c["checked"], is_gold=0,
                                     source_file="link_checks")))
    insert(con, "reviews", rv, "INSERT")
    return S


# ------------------------------------------------------------------ 5. metrics
def metrics(con) -> dict:
    q = lambda s, *a: con.execute(s, a).fetchall()  # noqa: E731
    cur = "JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1"
    M = {}
    M["mentions (shown versions) by kind"] = dict(q(f"SELECT m.kind, count(*) FROM citation_mentions m {cur} GROUP BY 1"))
    M["back references resolved"] = dict(q(f"SELECT m.resolve_method, count(*) FROM citation_mentions m {cur} WHERE "
                                           "m.kind IN ('ibid','op_cit','loc_cit') AND m.full_mention_pk IS NOT NULL "
                                           "GROUP BY 1 ORDER BY 2 DESC"))
    M["back references unresolved"] = dict(q(f"SELECT substr(m.unresolved_why, 1, instr(m.unresolved_why || ':', ':') - 1), "
                                             f"count(*) FROM citation_mentions m {cur} WHERE m.kind IN "
                                             "('ibid','op_cit','loc_cit') AND m.full_mention_pk IS NULL AND "
                                             "coalesce(m.resolve_method, '') <> 'part-of-citation' GROUP BY 1"))
    M["back-reference markers inside a parsed citation (counted once, as that citation)"] = q(
        f"SELECT count(*) FROM citation_mentions m {cur} WHERE m.resolve_method = 'part-of-citation'")[0][0]
    M["short forms resolved to a first full citation"] = q(
        f"SELECT count(*) FROM citation_mentions m {cur} WHERE m.kind = 'short' AND m.full_mention_pk IS NOT NULL")[0][0]
    M["back references pointing at a non-full mention"] = q(
        "SELECT count(*) FROM citation_mentions m JOIN citation_mentions t ON t.mention_pk = m.full_mention_pk "
        "WHERE m.kind IN ('ibid','op_cit','loc_cit') AND t.kind IN ('ibid','op_cit','loc_cit')")[0][0]
    M["cited works (active)"] = q("SELECT count(*) FROM cited_works WHERE status = 'active'")[0][0]
    M["cited works by type"] = dict(q("SELECT pub_type, count(*) FROM cited_works WHERE status = 'active' GROUP BY 1 "
                                      "ORDER BY 2 DESC"))
    M["cited works cited by >1 article"] = q("SELECT count(*) FROM v_times_cited WHERE n_citing_pubs > 1")[0][0]
    M["citation_links"] = dict(q("SELECT method || ' / ' || status, count(*) FROM citation_links GROUP BY 1"))
    M["work_relations"] = dict(q("SELECT relation, count(*) FROM work_relations GROUP BY 1"))
    M["same-article links (must be 0)"] = q(
        """SELECT count(*) FROM citation_links l JOIN cited_work_members w ON w.cited_work_pk = l.cited_work_pk
           JOIN citation_mentions c ON c.mention_pk = w.full_mention_pk JOIN versions v ON v.version_id = c.version_id
           JOIN documents d ON d.stem = v.stem WHERE d.pub_id = l.target_pub_id""")[0][0]
    M["top cited works"] = [dict(r) for r in q(
        """SELECT w.cited_work_id, w.title, w.first_author_key, t.n_citing_pubs, t.n_mentions, t.n_full, t.n_backrefs
           FROM v_times_cited t JOIN cited_works w USING (cited_work_pk) ORDER BY t.n_citing_pubs DESC, t.n_mentions DESC
           LIMIT 12""")]
    M["true self-citations (shared person id)"] = [dict(r) for r in q(
        """SELECT s.citing_pub_id, s.person_id, w.title FROM v_author_self_citations s
           JOIN cited_works w USING (cited_work_pk) LIMIT 20""")]
    M["journal citation pairs"] = [dict(r) for r in q("SELECT * FROM v_journal_citation_pairs ORDER BY n_mentions DESC "
                                                      "LIMIT 10")]
    M["quran index (top)"] = [dict(r) for r in q("SELECT q.*, a.sura_name_ar FROM v_quran_index q JOIN quran_ayat a ON "
                                                 "a.sura = q.sura AND a.aya = q.aya_from ORDER BY n_places DESC LIMIT 10")]
    M["quran places"] = dict(q("SELECT q.method, count(*) FROM quran_citations q JOIN versions v USING (version_id) "
                               "WHERE v.is_current = 1 GROUP BY 1"))
    return M


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--work", help="folder for the link cache and metrics47.json (default: the data folder)")
    a = ap.parse_args(argv)
    global CACHE
    work = Path(a.work) if a.work else DATA
    work.mkdir(parents=True, exist_ok=True)
    CACHE = work / "link_cache47.json"
    con = connect(Path(a.db))
    t0 = time.time()
    if not a.report:
        mcon = marc()
        cur = con.execute("INSERT INTO load_events (started, tool, tool_hash, export_id, args) VALUES (?, 'link47', ?, "
                          "?, ?)", (now(), sha_files([HERE / "link47.py"]), biblio47.EXPORT, " ".join(sys.argv[1:])))
        load_id = cur.lastrowid
        lr = con.execute("INSERT INTO link_runs (linker, code_hash, thresholds, export_id, started) VALUES "
                         "('link47', ?, ?, ?, ?)", (sha_files([HERE / "link47.py", E46 / "link46.py"]),
                                                    json.dumps(THRESHOLDS, ensure_ascii=False), biblio47.EXPORT, now()))
        lrid = lr.lastrowid
        # resolution: every version not linked yet (or all); cards are rebuilt from every shown version
        done = {r[0] for r in con.execute("SELECT DISTINCT version_id FROM link_run_versions")}
        vids = [r[0] for r in con.execute("SELECT version_id FROM versions ORDER BY version_id")]
        res, stats = {}, Counter()
        for vid in vids:
            shown = con.execute("SELECT is_current FROM versions WHERE version_id = ?", (vid,)).fetchone()[0]
            if a.all or vid not in done or shown:
                r = resolve(con, vid)
                if shown:
                    res[vid] = r
                    stats.update(r["stats"])
                con.execute("INSERT OR IGNORE INTO link_run_versions VALUES (?, ?)", (lrid, vid))
        con.commit()
        print(f"resolved {len(vids)} versions ({time.time() - t0:.0f} s): {dict(stats)}", flush=True)
        cards = build_cited_works(con, res, load_id)
        con.commit()
        print(f"cited works: {len(cards)} ({time.time() - t0:.0f} s)", flush=True)
        S = link_cards(con, mcon, cards, lrid, load_id)
        G = biblio47.refresh_global(con, mcon, load_id)      # persons (cited authors included), institutions, ...
        np_ = con.execute("SELECT count(*) FROM cited_work_authors WHERE person_id IS NOT NULL").fetchone()[0]
        con.commit()
        C = carry_checks(con, mcon)
        n_links = con.execute("SELECT count(*) FROM citation_links WHERE link_run_id = ?", (lrid,)).fetchone()[0]
        con.execute("UPDATE link_runs SET finished = ?, n_versions = ?, n_links = ? WHERE link_run_id = ?",
                    (now(), len(vids), n_links, lrid))
        con.execute("UPDATE load_events SET finished = ?, n_loaded = ?, rows_by_table = ? WHERE load_id = ?",
                    (now(), len(vids), json.dumps(dict(links=dict(S), cited_authors_as_persons=np_, checks=dict(C)),
                                                  ensure_ascii=False), load_id))
        con.commit()
        print(f"links {dict(S)}; global {G}; cited authors -> persons {np_}; hand checks carried {dict(C)} "
              f"({time.time() - t0:.0f} s)")
    M = metrics(con)
    (work / "metrics47.json").write_text(json.dumps(M, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    print(json.dumps({k: v for k, v in M.items() if not isinstance(v, list)}, ensure_ascii=False, indent=1))
    print("orphans:", len(con.execute("PRAGMA foreign_key_check").fetchall()))


if __name__ == "__main__":
    main()
