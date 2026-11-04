"""Stable subject keys (DESIGN §2) and the id helpers platform v2 uses.

`hashed_id` and `spk` are copied from experiments/47_platform_v2/common47.py (same algorithm, so ids the Desk mints in
a release look and behave like the machine's): a public id is 'A' / 'I' / 'C' + 9 Crockford base-32 characters of
sha1(kind|natural key); an integer row key is a 53-bit hash of the row's natural key."""
from __future__ import annotations

import hashlib
import re

KINDS = {
    "work": re.compile(r"C[0-9A-Z]{9}"),
    "person": re.compile(r"A[0-9A-Z]{9}"),
    "mention": re.compile(r"[^|]+\|p\d+\|(w\d+-\d+|[^|]+)\|\d+"),   # 4 unanchored ones use the note id
    "byline": re.compile(r"[^|]+\|(p\d+\|w\d+-\d+|[^|]*\|\d+\|[A-Za-z]+)"),
    "authority": re.compile(r"\d+"),
    "pubfield": re.compile(r"W[S0-9A-Za-z-]+\|[a-z_]+"),
    "line": re.compile(r"[^|]+\|p\d+\|l\d+"),
    "inst": re.compile(r"I[0-9A-Z]{9}"),
    "article": re.compile(r"[0-9A-Za-z][0-9A-Za-z,\-]{2,60}"),   # P2: an article page (its stem), for notes on it
    # one printed affiliation statement (experiment 56's key): article stem, byline position, script, its order under
    # the byline: 'aff:0011-005-014-013|b0|Arab|a1'
    "aff": re.compile(r"[0-9A-Za-z][0-9A-Za-z,\-]{2,60}\|b\d+\|[A-Za-z]+\|a\d+"),
    # a Mandumah publication (publications.pub_id: 'W' + the catalogue's 999$c, or 'WS' + stem): the target of a
    # cited work's link or relation (experiment 67)
    "pub": re.compile(r"W(S[0-9A-Za-z,\-]{3,60}|\d{1,12})"),
}
# which op lives in which domain, and in which phase of a build it is applied (DESIGN §8: page, then metadata,
# then identity, then back references)
OPS = {
    # op: (domain, phase, number of subject keys, key kinds)
    "split_work": ("identity", 3, 1, ("work",)),
    "same_work": ("identity", 3, 2, ("work", "work")),
    "not_same_work": ("identity", 3, 2, ("work", "work")),
    "move_member": ("identity", 3, 2, ("mention", "work")),
    "set_work_type": ("identity", 3, 1, ("work",)),
    "confirm_work": ("identity", 3, 1, ("work",)),      # "the machine is right": these members stay one work
    "same_person": ("identity", 3, 2, ("person", "person")),
    "not_same_person": ("identity", 3, 2, ("person", "person")),
    "link_byline": ("identity", 3, 2, ("byline", "person")),
    "unlink_byline": ("identity", 3, 1, ("byline",)),
    "resolve_backref": ("identity", 4, 2, ("mention", "mention")),
    "unresolvable": ("identity", 4, 1, ("mention",)),
    # institutions (experiment 64, 2026-11-02). Phases 5-8 run after the persons and back references: the records
    # of bodies first (5), which rows are one body (6), their country / parent / type (7), which bodies each printed
    # affiliation names (8), and last the splits of machine rows that held several bodies (9: by then the affiliations
    # are on their own bodies, and a split moves only the faculty / department links the machine lumped).
    # "2+" / "1+" = that many keys or more, all of the last kind listed.
    "define_institution": ("identity", 5, 1, ("inst",)),           # a body's record (names, kind); minted if new
    "same_institution": ("identity", 6, "2+", ("inst", "inst")),  # rows 2.. are one body with row 1 (kept)
    "not_same_institution": ("identity", 9, 1, ("inst",)),       # one machine row holds several bodies: split
    "not_an_institution_row": ("identity", 6, 1, ("inst",)),     # a machine row that names no body («بالكلية»)
    "set_inst_country": ("identity", 7, 1, ("inst",)),
    "set_inst_parent": ("identity", 7, 2, ("inst", "inst")),     # unit -> the body it belongs to
    "set_inst_type": ("identity", 7, 1, ("inst",)),
    "link_affiliation": ("identity", 8, "1+", ("aff", "inst")),  # the bodies a printed affiliation names
    "not_an_institution": ("identity", 8, 1, ("aff",)),          # the statement names no body
    "unit_kept_apart": ("identity", 8, 1, ("aff",)),             # a faculty printed without its university
    # cited works, the librarian's operations (experiment 67, 2026-11-02). The shape of the cards first, in phase 3
    # beside split_work / same_work (in the order they were made): a pair that is one work in two editions, a card
    # that is not a work, a work no citation names by itself (a collective book). Links and relations last (phase
    # 10), when every card is where the decisions put it.
    "edition_of": ("identity", 3, 2, ("work", "work")),       # one work; card 2's citations name another edition
    "not_a_work": ("identity", 3, 1, ("work",)),              # drop | retitle | one_per_citation (D: journal names)
    "define_work": ("identity", 3, 1, ("work",)),             # a work cited only through its parts; minted
    "link_publication": ("identity", 10, 2, ("work", "pub")),   # the work is this Mandumah publication (or its text)
    "relate_works": ("identity", 10, 2, ("work", "work")),      # part of, derived from, same text as … (two works)
    "relate_publication": ("identity", 10, 2, ("work", "pub")),  # reviewed in, studied in, derived … (not the work)
    "revert": (None, 0, None, None),       # domain and keys of the decision it reverts
    "retire": (None, 0, None, None),       # an orphaned decision retired: no effect, keys of that decision
}
WORK_TYPES = {"book", "turath", "diwan", "serial", "law", "legal-decision", "article", "thesis", "chapter",
              "conference-paper", "manuscript", "web", "hadith-collection", "report", "dictionary", "not-a-work"}
# institutions.kind: the machine's kinds, the librarian's types (experiment 56) and the three the owner added on
# 2026-11-02 (hospital, union, regional education authority; experiment 63 found the 22 set_type answers could not be
# reproduced without them)
INST_TYPES = {"university", "faculty", "department", "centre", "committee", "ministry", "organisation", "press",
              "society", "institute", "school", "academy", "hospital", "union", "regional_education_authority",
              "other"}
# how a cited work relates to another work or publication (experiment 67): name -> (work_relations.relation, inverse),
# read from the subject (the cited work). D42: a chapter is part of its book; D43: a thesis and the article drawn
# from it are two works, related; D44: one text printed in two journals.
WORK_RELATIONS = {
    "part_of": ("is_part_of", "has_part"),
    "has_part": ("has_part", "is_part_of"),
    "derived_from": ("is_derived_from", "has_derived"),       # this work was drawn from the other (an article from a thesis)
    "has_derived": ("has_derived", "is_derived_from"),        # the other was drawn from this one
    "same_text_as": ("is_same_text_as", "is_same_text_as"),   # the same text, published twice (D44)
    "reviewed_in": ("is_reviewed_in", "reviews"),
    "studied_in": ("is_studied_in", "studies"),
    "translation_of": ("is_translation_of", "has_translation"),
    "related": ("is_related_to", "is_related_to"),            # related, no finer name
}
# what a link to a Mandumah publication says (experiment 67): the publication IS the work cited, or it holds the same
# text published elsewhere (D44: the citation names another journal; Mandumah holds this one)
LINK_AS = {"work", "same_text"}
NOT_A_WORK_ACTIONS = {"drop", "retitle", "one_per_citation"}
# how a printed affiliation relates to a body it names (D37, D38): only `current` counts as the body's output.
# The link is written to affiliation_links with level 'org' (current), 'former' or 'educated_at'.
AFF_ROLES = {"current": "org", "former": "former", "educated_at": "educated_at"}


def split_key(key: str) -> tuple[str, str]:
    kind, sep, val = key.partition(":")
    if not sep or kind not in KINDS or not KINDS[kind].fullmatch(val):
        raise ValueError(f"not a stable subject key: {key!r}")
    return kind, val


def key_kind(key: str) -> str:
    return split_key(key)[0]


def key_value(key: str) -> str:
    return split_key(key)[1]


_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def hashed_id(prefix: str, kind: str, natural: str, n: int = 9) -> str:
    v = int.from_bytes(hashlib.sha1(f"{kind}|{natural}".encode("utf-8")).digest()[:10], "big")
    out = []
    for _ in range(n):
        out.append(_B32[v % 32])
        v //= 32
    return prefix + "".join(out)


def spk(*parts) -> int:
    h = hashlib.sha1("\x1f".join("" if p is None else str(p) for p in parts).encode("utf-8")).digest()
    return int.from_bytes(h[:7], "big") % (2 ** 53 - 1) + 1


def split_card_id(decision_id: str, group: int) -> str:
    """The id of the card a split creates for group i (>= 1): a function of the decision, so every build mints the
    same id."""
    return hashed_id("C", "cited_work", f"desk-split:{decision_id}|g{group}")


def defined_work_id(natural: str) -> str:
    """The id of a work a define_work decision makes (a collective book cited only through its chapters): a function
    of its natural key, so every build and every import mints the same id."""
    return hashed_id("C", "cited_work", f"desk-define:{natural}")


def unlinked_person_id(byline_key: str) -> str:
    return hashed_id("A", "person", f"desk-unlink:{byline_key}")


def authority_inst_id(authority_id: str) -> str:
    """The id of a body the librarian's authority holds and no machine row stands for: a function of the authority
    id, so every build (and every import) mints the same id."""
    return hashed_id("I", "institution", f"librarian:{authority_id}")


def split_inst_id(decision_id: str, group: int) -> str:
    """The id of the row a not_same_institution split makes for group i (>= 1)."""
    return hashed_id("I", "institution", f"desk-split:{decision_id}|g{group}")


def task_key(kind: str, subject_keys) -> str:
    return kind + "|" + "|".join(sorted(subject_keys))
