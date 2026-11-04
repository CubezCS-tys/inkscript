"""Three detectors from experiment 48 that turn the machine's doubts into tasks (DESIGN §5–6).

    .venv/bin/python -m desk.detectors [--db PATH]      # default: the newest release on disk, else platform_v2.db

| task kind                   | rule (experiment 48)                                                    |
|-----------------------------|--------------------------------------------------------------------------|
| work_joined_without_author  | probe B: a card cited by 2+ articles whose members include citations with no author («الديوان» CK4KYP6BAX) |
| possible_same_work          | probe B's under-merge candidates (`b_works_and_backrefs/under_cands.py`): same author word + title equal / contained / similar once author words, «ابن», edition and volume marks are stripped; or equal stripped titles with an author missing on one side |
| byline_twin                 | probe C: a provisional byline person beside a catalogue-only contributor of the same article («Khalid Talal Alotaibi» = «العتيبي، خالد طلال») |

Each task carries candidates, the machine's guess, a priority = impact × uncertainty (impact: the citations or
works the answer moves; uncertainty: 1 − the machine's confidence, from probe B/C's judged samples) and the
language skills it needs. A subject with a standing decision gets no task (DESIGN §5); an open task that its
detector no longer finds is marked stale.

The title and author helpers are experiment 47's own (`link47.author_tokens`, `common47.ratio` / `tokset`),
imported read-only, so the detectors see cards exactly as the linker builds them."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import db
from .ops import add_task, pending_cards, task_event
from .reading import Reading

E47 = Path(__file__).resolve().parents[2] / "47_platform_v2"
sys.path.insert(0, str(E47))
import link47  # noqa: E402  (read-only use of its helpers; nothing in experiment 47 is changed)
from common47 import ratio, tokset  # noqa: E402

ARABIC = re.compile(r"[؀-ۿ]")
FRENCH = re.compile(r"[éèêàçùâîôœ]|\b(le|la|les|des|du|une|et|dans|sur|pour|histoire|essai|œuvres)\b", re.I)
# under-merge rules: measured share "same work" in probe B's sample of 50 (seed 4812)
P_SAME = {"R1 stripped-equal": 0.9, "R1 contained": 0.82, "R1 similar": 0.25, "R2 stripped-equal, an author missing": 0.5}
MARK = re.compile(r"\b(ط|طبعه|الطبعه|طبعة|ج|جزء|الجزء|مج|مجلد|المجلد|مجلدات|اجزاء|vol|volume|tome|t|ed|edition|"
                  r"تحقيق|تح|شرح|قسم|القسم|part|teil|band|bd|[0-9]+|اول|ثاني|ثالث|الاول|الثاني|الثالث)\b")


def lang_of(text: str | None, names: bool = False) -> str:
    """The skill a task needs: 'ar', 'en', 'fr', or 'en|fr' for Latin names (either reader can read them)."""
    t = text or ""
    if ARABIC.search(t):
        return "ar"
    if names:
        return "en|fr"
    return "fr" if FRENCH.search(t) else "en"


def load_cards(R: Reading) -> dict:
    cards = {}
    for r in R.q("""SELECT w.cited_work_id, w.cited_work_pk, w.title, w.title_key, w.pub_type,
                           coalesce(t.n_mentions, 0) n_mentions, coalesce(t.n_citing_pubs, 0) n_pubs
                    FROM cited_works w LEFT JOIN v_times_cited t ON t.cited_work_pk = w.cited_work_pk
                    WHERE w.status = 'active'"""):
        cards[r["cited_work_id"]] = dict(r) | dict(members=[])
    for r in R.q("""SELECT w.cited_work_id, m.mention_id, m.printed, m.parsed, v.stem, a.anchor_key
                    FROM cited_work_members cm JOIN cited_works w ON w.cited_work_pk = cm.cited_work_pk
                    JOIN citation_mentions m ON m.mention_pk = cm.full_mention_pk
                    JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
                    LEFT JOIN ink_anchors a ON a.anchor_pk = m.anchor_pk
                    WHERE w.status = 'active' ORDER BY m.mention_id"""):
        p = json.loads(r["parsed"]) if r["parsed"] else None
        if r["cited_work_id"] in cards:
            cards[r["cited_work_id"]]["members"].append(dict(
                mention=r["mention_id"], stem=r["stem"], printed=r["printed"], anchor=r["anchor_key"],
                au=frozenset(link47.author_tokens(p)),
                authors=[" ".join(x for x in (a[1], a[0]) if x) for a in ((p or {}).get("authors") or [])]))
    return cards


def decided(pg) -> set:
    """Subjects people have settled: keys of standing decisions, and the cards a standing split made."""
    keys = {k for r in pg.execute("SELECT subject_keys FROM decisions WHERE status IN ('proposed', 'accepted') "
                                         "AND op NOT IN ('revert', 'retire')")
            for k in r["subject_keys"]}
    return keys | {f"work:{c}" for c in pending_cards(pg)}


def _member_view(m):
    return dict(mention=f"mention:{m['mention']}", stem=m["stem"], printed=m["printed"], anchor=m["anchor"],
                authors=m["authors"])


# ------------------------------------------------------------------ 1. a cross-article card joined without an author
def work_joined_without_author(R: Reading, cards: dict) -> list[dict]:
    out = []
    for cid, cd in sorted(cards.items()):
        ms = cd["members"]
        if len({m["stem"] for m in ms}) < 2 or all(m["au"] for m in ms):
            continue
        comps = []                          # connected components of non-empty author sets (probe B, conflict.py)
        for m in (m for m in ms if m["au"]):
            hit = [c for c in comps if any(m["au"] & x["au"] for x in c)]
            comps = [c for c in comps if c not in hit] + [[m] + [x for c in hit for x in c]]
        comps.sort(key=lambda c: (-len(c), min(x["mention"] for x in c)))
        noauth = [m for m in ms if not m["au"]]
        groups = [dict(label=" / ".join(sorted({w for x in c for w in x["au"]}))[:80],
                       members=[_member_view(x) for x in sorted(c, key=lambda x: x["mention"])]) for c in comps]
        groups.append(dict(label="(no author printed)", members=[_member_view(x) for x in noauth]))
        if len(comps) >= 2:
            guess = dict(op="split_work", groups=[[f"mention:{x['mention']}" for x in c] for c in comps],
                         note="citations with no author stay with the first group until a person places them")
            unc = 0.9
        else:
            guess = dict(op="confirm_work")
            unc = 0.4
        out.append(dict(
            kind="work_joined_without_author", keys=[f"work:{cid}"],
            question=f"«{cd['title']}» is one card for {len(ms)} citations in {len({m['stem'] for m in ms})} "
                     f"articles, joined through citations that print no author. Is it one work? If not, group the "
                     f"citations into works.",
            candidates=groups, guess=guess, impact=max(1, cd["n_mentions"]), uncertainty=unc,
            skills=[lang_of(cd["title"])], source=dict(rule="probe B: cross-article card with author-less members",
                                                      author_groups=len(comps), authorless=len(noauth))))
    return out


# ------------------------------------------------------------------ 2. one work on two cards
def possible_same_work(R: Reading, cards: dict) -> list[dict]:
    info = []
    for cid, cd in sorted(cards.items()):
        au = set().union(*[m["au"] for m in cd["members"]]) if cd["members"] else set()
        tk = cd["title_key"] or ""
        words = [w for w in MARK.sub(" ", tk).split() if w not in ("بن", "ابن") and w not in au
                 and re.sub("^ل", "", w) not in au]
        info.append(dict(id=cid, cd=cd, st=" ".join(words), au=au))
    by_au, by_st = defaultdict(list), defaultdict(list)
    for i, x in enumerate(info):
        for w in x["au"]:
            by_au[w].append(i)
        if x["st"]:
            by_st[x["st"]].append(i)
    pairs = {}
    for w, ix in by_au.items():
        if len(ix) > 400:
            continue
        for a in ix:
            for b in ix:
                if b <= a:
                    continue
                s1, s2 = info[a]["st"], info[b]["st"]
                if not s1 or not s2:
                    continue
                why = None
                if s1 == s2:
                    why = "R1 stripped-equal"
                elif min(len(s1), len(s2)) >= 4 and (f" {s1} " in f" {s2} " or f" {s2} " in f" {s1} "):
                    why = "R1 contained"
                elif tokset(s1, s2) >= 0.6 and ratio(s1, s2) >= 0.6 and min(len(s1.split()), len(s2.split())) >= 2:
                    why = "R1 similar"
                if why:
                    pairs[(a, b)] = why
    for st, ix in by_st.items():
        if len(st.split()) < 2 and len(st) < 8:
            continue
        for a in ix:
            for b in ix:
                if b <= a or (a, b) in pairs:
                    continue
                if (not info[a]["au"]) != (not info[b]["au"]) or (not info[a]["au"] and not info[b]["au"]):
                    pairs[(a, b)] = "R2 stripped-equal, an author missing"
    out = []
    for (a, b), why in sorted(pairs.items()):
        A, B = info[a], info[b]
        p = P_SAME[why]
        side = lambda x: dict(work=f"work:{x['id']}", title=x["cd"]["title"], authors=sorted(  # noqa: E731
            {n for m in x["cd"]["members"] for n in m["authors"]})[:5], n_mentions=x["cd"]["n_mentions"],
            n_articles=x["cd"]["n_pubs"], sample=[_member_view(m) for m in x["cd"]["members"][:3]])
        out.append(dict(
            kind="possible_same_work", keys=sorted([f"work:{A['id']}", f"work:{B['id']}"]),
            question=f"Are «{A['cd']['title']}» and «{B['cd']['title']}» the same work?",
            candidates=[side(A), side(B)],
            guess=dict(op="same_work" if p >= 0.5 else "not_same_work", p_same=p),
            impact=max(1, A["cd"]["n_mentions"]) + max(1, B["cd"]["n_mentions"]), uncertainty=round(1 - max(p, 1 - p), 2),
            skills=[lang_of(A["cd"]["title"] + " " + B["cd"]["title"])], source=dict(rule=f"probe B under-merge: {why}")))
    return out


# ------------------------------------------------------------------ 3. a byline counted twice
def _latin_tokens(name: str) -> list[str]:
    s = re.sub(r"\b(dr|prof|mr|mrs|ms|pr)\b\.?", " ", (name or "").lower())
    toks = []
    for w in re.findall(r"[a-z\-']+", s):
        w = w.strip("-'")
        if not w:
            continue
        toks.append(w.replace("-", ""))
        if "-" in w:
            toks.extend(x for x in w.split("-") if len(x) > 1)
    return toks


def _arabic_tokens(name: str) -> list[str]:
    return [w for w in re.split(r"[\s،,]+", name or "") if w and not re.fullmatch(r"ت\.?|\d+|م|هـ", w)]


def name_score(R: Reading, byline: str, heading: str, cache: dict) -> float:
    """Share of the catalogue heading's words that the byline also carries: the same word, or (Latin byline against
    an Arabic heading) a pair in platform v2's translit_pairs, learned from 1.08M catalogue headings."""
    hw = _arabic_tokens(heading)
    if not hw:
        return 0.0
    if ARABIC.search(byline or ""):
        bw = set(_arabic_tokens(byline))
        strip = lambda w: re.sub("^ال", "", w)  # noqa: E731
        return sum(strip(w) in {strip(x) for x in bw} for w in hw) / len(hw)
    lt = _latin_tokens(byline)
    hit, used = 0, set()
    for w in hw:
        forms = {w, re.sub("^ال", "", w), "ال" + w}
        for lat in lt:
            if lat in used:
                continue
            k = (tuple(sorted(forms)), lat)
            if k not in cache:          # share = how often the catalogue writes this Arabic word this way (>= 5%)
                cache[k] = R.q1(f"SELECT 1 FROM translit_pairs WHERE latin = ? AND n >= 3 AND share >= 0.05 AND "
                                f"arabic IN ({','.join('?' * len(forms))})", (lat, *forms)) is not None
            if cache[k]:
                hit += 1
                used.add(lat)
                break
    return hit / len(hw)


def byline_twin(R: Reading) -> list[dict]:
    prov = R.q("""SELECT a.authorship_pk, a.pub_id, a.position, a.person_id, b.printed, b.name_text, b.script,
                         v.stem FROM authorships a
                  JOIN authorship_mentions am ON am.authorship_pk = a.authorship_pk
                  JOIN byline_mentions b ON b.mention_pk = am.mention_pk
                  JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1
                  WHERE a.method = 'provisional' AND a.person_id IS NOT NULL ORDER BY a.pub_id, a.position""")
    cats = defaultdict(list)
    for r in R.q("""SELECT a.pub_id, a.person_id, a.position, a.role_code, c.name, c.latin, c.authority_id, c.seq
                    FROM authorships a JOIN catalogue_contributors c ON c.c999 = a.c999 AND c.seq = a.catalogue_seq
                    WHERE a.method = 'catalogue-only' AND a.person_id IS NOT NULL AND coalesce(c.is_org, 0) = 0
                    ORDER BY a.pub_id, c.seq"""):
        cats[r["pub_id"]].append(dict(r))
    out, cache, seen = [], {}, set()
    for p in prov:
        if p["pub_id"] not in cats or p["person_id"] in seen:
            continue
        seen.add(p["person_id"])
        name = p["name_text"] or p["printed"]
        cands = []
        for c in cats[p["pub_id"]]:
            sc = name_score(R, name, c["name"] or "", cache)
            cands.append(dict(person=f"person:{c['person_id']}", heading=c["name"], latin=c["latin"],
                              authority=c["authority_id"], role=c["role_code"], catalogue_seq=c["seq"],
                              n_works=R.n_works(c["person_id"]), score=round(sc, 2)))
        cands.sort(key=lambda c: (-c["score"], c["catalogue_seq"]))
        best = cands[0]
        unique = len(cands) == 1 or cands[1]["score"] < best["score"]
        guess = dict(op="same_person", subject_keys=[best["person"], f"person:{p['person_id']}"],
                     score=best["score"]) if best["score"] >= 0.5 and unique else None
        out.append(dict(
            kind="byline_twin", keys=[f"person:{p['person_id']}"],
            question=f"The byline «{name}» of {p['stem']} has no authority, and the article's catalogue record lists "
                     f"{len(cands)} contributor(s) no byline matched. Is «{name}» one of them?",
            candidates=cands, guess=guess, impact=1 + max(c["n_works"] for c in cands),
            uncertainty=round(max(0.1, 1 - 0.9 * best["score"]) if guess else 0.9, 2),
            skills=["ar", lang_of(name, names=True)] if not ARABIC.search(name or "") else ["ar"],
            source=dict(rule="probe C: provisional byline beside catalogue-only contributors", pub_id=p["pub_id"],
                        stem=p["stem"], byline=name)))
    return out


DETECTORS = dict(work_joined_without_author=lambda R, cards: work_joined_without_author(R, cards),
                 possible_same_work=lambda R, cards: possible_same_work(R, cards),
                 byline_twin=lambda R, cards: byline_twin(R))


def run(pg, path: Path | str | None = None, release_id: str | None = None, only=None, is_demo=False) -> dict:
    """Run the detectors on a reading or release and write their tasks. The caller commits."""
    path = Path(path or db.state_path(pg))
    R = Reading(db.open_reading(path))
    cards = load_cards(R)
    done = decided(pg)
    report = {}
    for kind, fn in DETECTORS.items():
        if only and kind not in only:
            continue
        found = fn(R, cards)
        made, skipped, keys = 0, 0, set()
        for t in found:
            if len(t["keys"]) == 1 and t["keys"][0] in done:   # pairs: add_task's standing check decides
                skipped += 1
                continue
            tid = add_task(pg, kind, t["keys"], question=t["question"], candidates=t["candidates"],
                           machine_guess=t["guess"], impact=t["impact"], uncertainty=t["uncertainty"],
                           source=dict(t["source"], detector=kind, db=str(path), release=release_id),
                           skills=t["skills"], release=release_id, is_demo=is_demo)
            if tid is None:
                skipped += 1
            else:
                made += 1
                keys.add(tid)
        stale = pg.execute("""UPDATE tasks SET state = 'stale', claimed_by = NULL, lease_until = NULL, updated_at = now()
                              WHERE kind = %s AND state IN ('open', 'claimed') AND NOT (task_id = ANY(%s))
                              RETURNING task_id""", (kind, list(keys))).fetchall()
        for s in stale:
            task_event(pg, s["task_id"], None, "stale", f"no longer found by {kind} on {path.name}")
        report[kind] = dict(found=len(found), tasks=made, skipped_decided=skipped, stale=len(stale))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="reading or release to run on (default: newest release on disk, else platform_v2.db)")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    with db.connect() as pg:
        r = run(pg, a.db, only=a.only)
        pg.commit()
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
