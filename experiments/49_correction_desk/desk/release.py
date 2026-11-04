"""A release = the machine's reading + every accepted decision (DESIGN §8). platform_v2.db is only ever read.

    .venv/bin/python -m desk.release [--reading PATH] [--out DIR] [--keep 2] [--note TEXT]

1. The reading is copied with SQLite's backup API (it has a live WAL; a file copy could miss pages) to
   <releases>/<release_id>.db.
2. Decisions are applied in phases (page, metadata, identity, back references), in the order they were made.
   Superseded ones are recorded and skipped. Each is applied inside a savepoint and then the constraints of the
   decisions applied so far that depend on anything this decision changed are checked (a change log kept by
   temporary triggers on the copy says what changed; constraints with unknown dependencies are always checked;
   DESK_FULL_CHECK=1 checks every constraint every time, as P1 did):
     - a must-link (same_work, confirm_work, a split's group, same_person, link_byline) keeps its members on one
       card / one person;
     - a cannot-link (not_same_*, the groups of a split) keeps its sides apart,
   so identity decisions act like linker constraints: whatever the machine joined or split, the release holds what
   people decided. A decision that would break an earlier one is rolled back as a `conflict`: the earlier one
   holds, both owners get a note and the later owner a task (only an owner or an admin changes a decision).
3. A decision whose keys are not in the reading is `orphaned`: nothing of it is applied, the subject is marked
   orphaned, and a task to re-anchor it is created for its owner. It is never dropped silently.
4. Retired ids go to the release's merged_ids; every applied decision is a `patches` row (source person,
   priority 1) with a `patch_applications` row, so the release describes itself.
5. Checks: PRAGMA foreign_key_check (as many violations as the reading had: 0), counts before and after, and
   every applied decision re-checked on the final state. A fingerprint of every table a decision can touch (no
   clocks) shows whether two builds are identical.
6. At most `keep` release copies stay on disk; older copies this tool made are deleted (the release rows stay).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from psycopg.types.json import Jsonb

from . import db
from .keys import AFF_ROLES, OPS, WORK_RELATIONS, hashed_id, key_value, spk
from .ops import add_note, add_task, ensure_subject
from .reading import Reading

FINGERPRINT_TABLES = ["cited_works", "cited_work_members", "cited_work_authors", "citation_links", "work_relations",
                      "merged_ids", "id_registry", "persons", "person_names", "person_authorities", "authorships",
                      "authorship_mentions", "supervisions", "patches", "patch_applications", "institutions",
                      "institution_names", "institution_relations", "affiliation_links",
                      # experiment 67: editions, catalogue records and publications a link or relation adds
                      "cited_work_editions", "cited_work_contributors", "publications", "catalogue_records",
                      "catalogue_contributors", "journals", "journal_titles"]
# a catalogue record's type -> publications.type (platform v2's biblio47.TYPE, copied: the release adds the
# catalogued-only publications a librarian's link or relation points at, as link47 adds its own)
CAT_TYPE = {"بحوث ومقالات": "article", "رسائل جامعية": "thesis", "بحوث المؤتمرات": "conference-paper",
            "عروض كتب": "book-review", "افتتاحيات": "editorial", "نصوص أدبية": "literary-text", "عروض رسائل": "thesis-review",
            "ببليوجرافية": "bibliography", "عروض ابحاث": "paper-review", "تشريعات": "legislation", "فتاوى": "fatwa",
            "اخرى": "other"}
ORG_LEVELS = tuple(AFF_ROLES.values())     # 'org' (current), 'former', 'educated_at': the body an affiliation names
MENTION_COLS = "mention_pk, mention_id, full_mention_pk, resolve_method, resolve_score, resolve_evidence, resolved_by, " \
               "unresolved_why"
CONF = dict(sure=1.0, likely=0.75, unsure=0.5)
RELEASE_FILE = re.compile(r"R\d{8}T\d{6}(-\d+)?\.db")


class Orphan(Exception):
    """A key the decision needs is not in this reading."""


class Conflict(Exception):
    """Applying the decision would break an earlier person's decision."""


def _iso(ts) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------ applying decisions to a release copy
class Builder:
    def __init__(self, con: sqlite3.Connection, release_id: str):
        self.con = con
        self.R = Reading(con)
        self.decided_affs = set()          # experiment 68: affiliation rows a decision named (inherit_twins)
        self.aff_by_key = {}               # experiment 68: aff key -> row, as a decision found it (moved twins too)
        self.aff_peers = {}                # experiment 68: (stem, printed) -> the decided aff keys with that text
        self.release_id = release_id
        self.constraints = []          # (decision_id, description, check() -> bool, deps or None)
        self.full_check = os.environ.get("DESK_FULL_CHECK") == "1"
        self._changelog()
        cur = con.execute("INSERT INTO load_events (started, tool, args) VALUES (?, 'desk-release', ?)",
                          ("(release)", release_id))
        self.load_id = cur.lastrowid

    def x(self, sql, args=()):
        return self.con.execute(sql, args)

    # --- what a decision changed (so only constraints that depend on it are re-checked)
    def _changelog(self):
        x = self.con.execute
        x("CREATE TEMP TABLE IF NOT EXISTS desk_dirty (kind TEXT, k TEXT)")
        for t, ev, cols in [("cited_work_members", "INSERT", ["NEW.full_mention_pk"]),
                            ("cited_work_members", "DELETE", ["OLD.full_mention_pk"]),
                            ("cited_work_members", "UPDATE", ["OLD.full_mention_pk", "NEW.full_mention_pk"])]:
            vals = " UNION ALL ".join(f"SELECT 'm', {c}" for c in cols)
            x(f"CREATE TEMP TRIGGER IF NOT EXISTS desk_log_{t}_{ev.lower()} AFTER {ev} ON main.{t} BEGIN "
              f"INSERT INTO desk_dirty (kind, k) {vals}; END")
        x("CREATE TEMP TRIGGER IF NOT EXISTS desk_log_mentions AFTER UPDATE ON main.citation_mentions BEGIN "
          "INSERT INTO desk_dirty (kind, k) VALUES ('m', NEW.mention_pk); END")
        x("CREATE TEMP TRIGGER IF NOT EXISTS desk_log_cards AFTER UPDATE ON main.cited_works BEGIN "
          "INSERT INTO desk_dirty (kind, k) VALUES ('c', NEW.cited_work_pk); END")
        for ev, rows in [("INSERT", ["('a', NEW.authorship_pk)", "('p', NEW.person_id)"]),
                         ("DELETE", ["('a', OLD.authorship_pk)", "('p', OLD.person_id)"]),
                         ("UPDATE", ["('a', OLD.authorship_pk)", "('a', NEW.authorship_pk)", "('p', OLD.person_id)",
                                     "('p', NEW.person_id)"])]:
            x(f"CREATE TEMP TRIGGER IF NOT EXISTS desk_log_authorships_{ev.lower()} AFTER {ev} ON main.authorships "
              f"BEGIN INSERT INTO desk_dirty (kind, k) VALUES {', '.join(rows)}; END")
        x("CREATE TEMP TRIGGER IF NOT EXISTS desk_log_persons AFTER UPDATE ON main.persons BEGIN "
          "INSERT INTO desk_dirty (kind, k) VALUES ('p', NEW.person_id); END")
        # institutions (experiment 64): 'f' = a printed affiliation (aff_pk) whose links changed, 'i' = an institution
        for ev, rows in [("INSERT", ["('f', NEW.aff_pk)", "('i', NEW.inst_id)"]),
                         ("DELETE", ["('f', OLD.aff_pk)", "('i', OLD.inst_id)"]),
                         ("UPDATE", ["('f', OLD.aff_pk)", "('f', NEW.aff_pk)", "('i', OLD.inst_id)",
                                     "('i', NEW.inst_id)"])]:
            x(f"CREATE TEMP TRIGGER IF NOT EXISTS desk_log_afflinks_{ev.lower()} AFTER {ev} ON main.affiliation_links "
              f"BEGIN INSERT INTO desk_dirty (kind, k) VALUES {', '.join(rows)}; END")
        for ev in ("INSERT", "UPDATE"):
            x(f"CREATE TEMP TRIGGER IF NOT EXISTS desk_log_institutions_{ev.lower()} AFTER {ev} ON main.institutions "
              f"BEGIN INSERT INTO desk_dirty (kind, k) VALUES ('i', NEW.inst_id); END")
        # cited works' links and relations (experiment 67): 'c' = the card whose link or relation changed
        for ev, rows in [("INSERT", ["('c', NEW.cited_work_pk)"]), ("DELETE", ["('c', OLD.cited_work_pk)"]),
                         ("UPDATE", ["('c', OLD.cited_work_pk)", "('c', NEW.cited_work_pk)"])]:
            x(f"CREATE TEMP TRIGGER IF NOT EXISTS desk_log_links_{ev.lower()} AFTER {ev} ON main.citation_links "
              f"BEGIN INSERT INTO desk_dirty (kind, k) VALUES {', '.join(rows)}; END")
        for ev, rows in [("INSERT", ["('c', NEW.subject_cited_work_pk)", "('c', NEW.object_cited_work_pk)"]),
                         ("DELETE", ["('c', OLD.subject_cited_work_pk)", "('c', OLD.object_cited_work_pk)"]),
                         ("UPDATE", ["('c', OLD.subject_cited_work_pk)", "('c', NEW.subject_cited_work_pk)",
                                     "('c', OLD.object_cited_work_pk)", "('c', NEW.object_cited_work_pk)"])]:
            x(f"CREATE TEMP TRIGGER IF NOT EXISTS desk_log_relations_{ev.lower()} AFTER {ev} ON main.work_relations "
              f"BEGIN INSERT INTO desk_dirty (kind, k) VALUES {', '.join(rows)}; END")
        x("CREATE TEMP TRIGGER IF NOT EXISTS desk_log_merged_ids AFTER INSERT ON main.merged_ids BEGIN "
          "INSERT INTO desk_dirty (kind, k) VALUES ('i', NEW.old_id), ('i', NEW.new_id); END")

    def _take_dirty(self) -> dict:
        d = {"m": set(), "a": set(), "p": set(), "c": set(), "f": set(), "i": set()}
        for kind, k in self.con.execute("SELECT kind, k FROM temp.desk_dirty"):
            if k is not None:
                d[kind].add(str(k))
        self.con.execute("DELETE FROM temp.desk_dirty")
        if d["c"]:   # a card that changed touches all its members
            q = ",".join("?" * len(d["c"]))
            d["m"] |= {str(r[0]) for r in self.con.execute(
                f"SELECT full_mention_pk FROM cited_work_members WHERE cited_work_pk IN ({q})", tuple(d["c"]))}
        return d

    def _mention_deps(self, mids) -> dict:
        return {"m": {str(m["mention_pk"]) for m in (self.R.mention(x) for x in mids) if m}}

    def _person_deps(self, refs, pids=()) -> dict:
        a, p = set(), {str(x) for x in pids if x}
        for r in refs:
            au = self.R.authorship_by_ref(r)
            if au:
                a.add(str(au["authorship_pk"]))
                if au["person_id"]:
                    p.add(str(au["person_id"]))
        return {"a": a, "p": p}

    # --- provenance in the copy
    def patch(self, d: dict) -> str:
        pk = f"desk|{d['decision_id']}"
        stem = None
        for k in d["subject_keys"]:
            if k.startswith(("mention:", "byline:", "aff:")):
                stem = k.split(":", 1)[1].split("|")[0]
                break
        self.x("INSERT OR IGNORE INTO actors (actor_id, kind, name, note) VALUES (?, ?, ?, 'the Desk')",
               (d["actor_id"], d["actor_id"].split(":")[0] if d["actor_id"].split(":")[0] in
                ("person", "agent", "model", "rule") else "person", d["actor_id"]))
        domain = "citation" if d["op"] in ("resolve_backref", "unresolvable", "edition_of", "link_publication",
                                           "relate_publication") or "work" in d["op"] else "entity"
        self.x("""INSERT OR REPLACE INTO patches (patch_key, run, stem, patch_id, domain, op, page, targets, payload,
                  source, priority, actor_id, confidence, evidence, reason, apply, created, payload_copy)
                  VALUES (?, NULL, ?, ?, ?, ?, NULL, ?, ?, 'person', 1, ?, ?, ?, ?, 1, ?, ?)""",
               (pk, stem, str(d["decision_id"]), domain, d["op"], json.dumps(d["subject_keys"], ensure_ascii=False),
                json.dumps(d["payload"], ensure_ascii=False, sort_keys=True), d["actor_id"], CONF[d["confidence"]],
                json.dumps(d["evidence"], ensure_ascii=False, sort_keys=True),
                " ".join(x for x in (d["reason_code"], d["note"]) if x) or None, _iso(d["created_at"]),
                json.dumps(d["payload"], ensure_ascii=False, sort_keys=True)))
        return pk

    def patch_application(self, d, status, why):
        self.x("INSERT OR REPLACE INTO patch_applications (patch_key, version_id, load_id, status, why) "
               "VALUES (?, NULL, ?, ?, ?)", (f"desk|{d['decision_id']}", self.load_id, status, why))

    # --- cards
    def card_pk(self, cid):
        r = self.R.card(cid)
        return r["cited_work_pk"] if r else None

    def mention_pk(self, mid):
        m = self.R.mention(mid)
        if not m:
            raise Orphan(f"mention:{mid} is not in the reading")
        return m["mention_pk"]

    def retire_card(self, old: str, new: str, d, pk_patch, why):
        self.x("UPDATE cited_works SET status = 'merged' WHERE cited_work_id = ?", (old,))
        self.x("INSERT OR REPLACE INTO merged_ids VALUES (?, ?, 'cited_work', 'merged-into', ?, ?, 'person', ?)",
               (old, new, _iso(d["created_at"]), why, pk_patch))

    def ensure_card(self, cid: str, members: list[str], natural: str, template: str | None, label: str | None, d,
                    pk_patch) -> int:
        """A card for a split's group (or a card a person keeps apart): reactivated if the copy holds it, else made
        from its first member's parsed citation."""
        r = self.R.card(cid)
        if r:
            if r["status"] != "active":
                self.x("UPDATE cited_works SET status = 'active' WHERE cited_work_id = ?", (cid,))
                self.x("DELETE FROM merged_ids WHERE old_id = ?", (cid,))
            return r["cited_work_pk"]
        rep = None
        for mid in sorted(members):
            m = self.R.mention(mid)
            p = json.loads(m["parsed"]) if m and m["parsed"] else {}
            if rep is None or (bool(p.get("authors")), len(json.dumps(p))) > (bool(rep.get("authors")),
                                                                               len(json.dumps(rep))):
                rep = p
        rep = rep or {}
        t = self.R.card(template) if template else None
        title = rep.get("article_title") or rep.get("chapter_title") or rep.get("source_title") or (t["title"] if t
                                                                                                  else None)
        pk = spk("cited_works", cid)
        self.x("""INSERT INTO cited_works (cited_work_pk, cited_work_id, pub_type, title, title_key, first_author_key,
                  year_printed, place, publisher, lang, status, method, built_load)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
               (pk, cid, t["pub_type"] if t else "book", title, t["title_key"] if t else None,
                (rep.get("authors") or [[None]])[0][0], rep.get("year"), rep.get("place"), rep.get("publisher"),
                t["lang"] if t else None, f"person: desk {d['op']}" + (f" ({label})" if label else ""), self.load_id))
        self.x("INSERT OR IGNORE INTO id_registry (public_id, kind, natural_key, created_load) VALUES (?, 'cited_work', "
               "?, ?)", (cid, natural, self.load_id))
        for k, a in enumerate(rep.get("authors") or []):
            sn, gn = (list(a) + [None, None])[:2]
            self.x("INSERT OR REPLACE INTO cited_work_authors (cited_work_pk, seq, printed) VALUES (?, ?, ?)",
                   (pk, k + 1, " ".join(x for x in (gn, sn) if x)))
        return pk

    def move(self, mid: str, card_pk: int, pk_patch: str) -> str | None:
        """Put a full mention on a card. Returns the card it left when that card is now empty."""
        mpk = self.mention_pk(mid)
        r = self.x("SELECT cited_work_pk FROM cited_work_members WHERE full_mention_pk = ?", (mpk,)).fetchone()
        if r and r[0] == card_pk:
            return None
        if r:
            self.x("UPDATE cited_work_members SET cited_work_pk = ?, method = 'person', score = 1.0, "
                   "asserted_by = 'person', patch_key = ? WHERE full_mention_pk = ?", (card_pk, pk_patch, mpk))
            self.carry_edition(mpk, card_pk)
            left = self.x("SELECT count(*) FROM cited_work_members WHERE cited_work_pk = ?", (r[0],)).fetchone()[0]
            if left == 0:
                return self.x("SELECT cited_work_id FROM cited_works WHERE cited_work_pk = ?", (r[0],)).fetchone()[0]
        else:
            self.x("INSERT INTO cited_work_members (full_mention_pk, cited_work_pk, method, score, evidence, asserted_by, "
                   "patch_key) VALUES (?, ?, 'person', 1.0, NULL, 'person', ?)",
                   (mpk, card_pk, pk_patch))
        return None

    def carry_edition(self, mpk: int, card_pk: int):
        """A citation that moves to another card takes the edition it names along (experiment 67): the new card's
        row of that edition (same key), else the row itself when no citation stays on it, else a copy."""
        e = self.x("""SELECT e.* FROM cited_work_members cm JOIN cited_work_editions e ON e.edition_pk = cm.edition_pk
                      WHERE cm.full_mention_pk = ?""", (mpk,)).fetchone()
        if not e or e["cited_work_pk"] == card_pk:
            return
        old = e["edition_pk"]
        tgt = self.x("SELECT edition_pk FROM cited_work_editions WHERE cited_work_pk = ? AND edition_key = ?",
                     (card_pk, e["edition_key"])).fetchone()
        others = self.x("SELECT count(*) FROM cited_work_members WHERE edition_pk = ? AND full_mention_pk <> ?",
                        (old, mpk)).fetchone()[0]
        if tgt:
            self.x("UPDATE cited_work_members SET edition_pk = ? WHERE full_mention_pk = ?", (tgt[0], mpk))
            new = tgt[0]
        elif not others:
            self.x("UPDATE cited_work_editions SET cited_work_pk = ? WHERE edition_pk = ?", (card_pk, old))
            new = old
        else:
            new = spk("cited_work_editions", card_pk, e["edition_key"])
            self.x("""INSERT INTO cited_work_editions (edition_pk, cited_work_pk, edition_key, edition_printed,
                      year_printed, year_calendar, year2, publisher, place, n_members, first_mention_pk)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                   (new, card_pk, e["edition_key"], e["edition_printed"], e["year_printed"], e["year_calendar"],
                    e["year2"], e["publisher"], e["place"], mpk))
            self.x("UPDATE cited_work_members SET edition_pk = ? WHERE full_mention_pk = ?", (new, mpk))
        if new != old and not others:
            self.drop_edition_if_unused(old, new)
        for x in {old, new}:
            self.recount_edition(x)

    def recount_edition(self, epk: int):
        self.x("UPDATE cited_work_editions SET n_members = (SELECT count(*) FROM cited_work_members WHERE edition_pk "
               "= ?) WHERE edition_pk = ?", (epk, epk))

    def drop_edition_if_unused(self, epk: int, to: int | None = None):
        """An edition row no citation names any more (its citations moved to `to`, another row of that edition)."""
        if not self.x("SELECT 1 FROM cited_work_members WHERE edition_pk = ? LIMIT 1", (epk,)).fetchone():
            self.x("UPDATE cited_work_contributors SET edition_pk = ? WHERE edition_pk = ?", (to, epk))
            self.x("DELETE FROM cited_work_editions WHERE edition_pk = ?", (epk,))

    def cards_of(self, mids) -> set:
        return {self.R.card_of_mention(m) for m in mids} - {None}

    def present(self, mids) -> list[str]:
        return [m for m in mids if self.R.mention(m)]

    # --- persons
    def person_of_ref(self, ref):
        a = self.R.authorship_by_ref(ref)
        return a["person_id"] if a else None

    def resolve_person(self, pid: str, refs=None):
        p, how = self.R.resolve_person(pid)
        if p:
            return p
        votes = Counter(x for x in (self.person_of_ref(r) for r in refs or []) if x)
        return sorted(votes.items(), key=lambda v: (-v[1], v[0]))[0][0] if votes else None

    def ensure_person(self, pid: str, name: str | None, natural: str):
        p = self.R.person(pid)
        if p:
            if p["status"] == "merged":
                self.x("UPDATE persons SET status = ? WHERE person_id = ?",
                       ("active" if p["source"] == "catalogue-authority" else "provisional", pid))
                self.x("DELETE FROM merged_ids WHERE old_id = ?", (pid,))
            return
        lat = name if name and re.search("[A-Za-z]", name) else None
        self.x("INSERT INTO persons (person_id, status, preferred_name_ar, preferred_name_lat, source, created_load) "
               "VALUES (?, 'provisional', ?, ?, 'person', ?)", (pid, None if lat else name, lat, self.load_id))
        self.x("INSERT OR IGNORE INTO id_registry (public_id, kind, natural_key, created_load) VALUES (?, 'person', ?, ?)",
               (pid, natural, self.load_id))
        if name:
            self.x("INSERT OR IGNORE INTO person_names (name_pk, person_id, full_form, script, form_type, source) "
                   "VALUES (?, ?, ?, ?, 'printed', 'person')",
                   (spk("person_names", pid, name, "printed"), pid, name, "Latn" if lat else "Arab"))

    def set_authorship_person(self, apk: int, pid: str, pk_patch: str):
        """Give an authorship to a person; if that person already holds an authorship of the same publication, the two
        are twins (a Latin byline and its catalogue row): they become one authorship, as platform v2 joins its own
        bilingual twins."""
        a = self.x("SELECT * FROM authorships WHERE authorship_pk = ?", (apk,)).fetchone()
        twin = self.x("SELECT * FROM authorships WHERE pub_id = ? AND person_id = ? AND authorship_pk <> ?",
                      (a["pub_id"], pid, apk)).fetchone()
        self.x("UPDATE authorships SET person_id = ?, method = 'person', asserted_by = 'person', patch_key = ? "
               "WHERE authorship_pk = ?", (pid, pk_patch, apk))
        if twin:
            nm = lambda r: self.x("SELECT count(*) FROM authorship_mentions WHERE authorship_pk = ?",  # noqa: E731
                                  (r["authorship_pk"],)).fetchone()[0]
            keep, drop = (a, twin) if (-nm(a), a["position"]) <= (-nm(twin), twin["position"]) else (twin, a)
            if keep["c999"] is None and drop["c999"] is not None:
                self.x("UPDATE authorships SET c999 = ?, catalogue_seq = ? WHERE authorship_pk = ?",
                       (drop["c999"], drop["catalogue_seq"], keep["authorship_pk"]))
            self.x("UPDATE authorships SET person_id = ?, method = 'person', asserted_by = 'person', patch_key = ? "
                   "WHERE authorship_pk = ?", (pid, pk_patch, keep["authorship_pk"]))
            self.x("INSERT OR IGNORE INTO authorship_mentions SELECT ?, mention_pk FROM authorship_mentions "
                   "WHERE authorship_pk = ?", (keep["authorship_pk"], drop["authorship_pk"]))
            self.x("DELETE FROM authorship_mentions WHERE authorship_pk = ?", (drop["authorship_pk"],))
            self.x("DELETE FROM authorships WHERE authorship_pk = ?", (drop["authorship_pk"],))

    def retire_person_if_empty(self, old: str, new: str, d, pk_patch, why):
        if old == new or self.x("SELECT 1 FROM authorships WHERE person_id = ? LIMIT 1", (old,)).fetchone():
            return
        p = self.R.person(old)
        if p and p["status"] == "provisional":
            self.merge_person_rows(old, new)
            self.x("UPDATE persons SET status = 'merged' WHERE person_id = ?", (old,))
            self.x("INSERT OR REPLACE INTO merged_ids VALUES (?, ?, 'person', 'merged-into', ?, ?, 'person', ?)",
                   (old, new, _iso(d["created_at"]), why, pk_patch))

    def merge_person_rows(self, old: str, new: str):
        for r in self.x("SELECT * FROM person_names WHERE person_id = ?", (old,)).fetchall():
            self.x("""INSERT OR IGNORE INTO person_names (name_pk, person_id, full_form, script, lang, form_type, ism,
                      nasab, nisba, laqab, kunya, family, name_key, n_seen, source)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (spk("person_names", new, r["full_form"], r["form_type"]), new, r["full_form"], r["script"],
                    r["lang"], r["form_type"], r["ism"], r["nasab"], r["nisba"], r["laqab"], r["kunya"], r["family"],
                    r["name_key"], r["n_seen"], r["source"]))
        self.x("DELETE FROM person_names WHERE person_id = ?", (old,))
        self.x("UPDATE person_authorities SET person_id = ? WHERE person_id = ?", (new, old))
        self.x("UPDATE cited_work_authors SET person_id = ? WHERE person_id = ?", (new, old))
        self.x("UPDATE OR IGNORE supervisions SET supervisor_person_id = ? WHERE supervisor_person_id = ?", (new, old))
        self.x("UPDATE supervisions SET student_person_id = ? WHERE student_person_id = ?", (new, old))
        o, n = self.R.person(old), self.R.person(new)
        for col in ("preferred_name_ar", "preferred_name_lat"):
            if o and n and not n[col] and o[col]:
                self.x(f"UPDATE persons SET {col} = ? WHERE person_id = ?", (o[col], new))

    # --- constraints
    def must_cards(self, did, mids, what):
        mids = list(mids)
        self.constraints.append((did, f"{what}: on one card", lambda: len(self.cards_of(self.present(mids))) <= 1,
                                 self._mention_deps(mids)))

    def cannot_cards(self, did, a, b, what):
        a, b = list(a), list(b)
        self.constraints.append((did, f"{what}: kept apart",
                                 lambda: not (self.cards_of(self.present(a)) & self.cards_of(self.present(b))),
                                 self._mention_deps(a + b)))

    def must_persons(self, did, refs, what):
        refs = list(refs)
        self.constraints.append((did, f"{what}: one person",
                                 lambda: len({self.person_of_ref(r) for r in refs} - {None}) <= 1,
                                 self._person_deps(refs)))

    def cannot_persons(self, did, a, b, what):
        a, b = list(a), list(b)
        self.constraints.append((did, f"{what}: kept apart", lambda: not (
            ({self.person_of_ref(r) for r in a} - {None}) & ({self.person_of_ref(r) for r in b} - {None})),
            self._person_deps(a + b)))

    def holds(self, did, what, fn, deps=None):
        # deps None = unknown: checked after every decision
        self.constraints.append((did, what, fn, deps))

    @staticmethod
    def _touches(deps, dirty) -> bool:
        return deps is None or any(deps.get(k, set()) & dirty[k] for k in ("m", "a", "p", "f", "i", "c"))

    def broken(self, since: int | None = None, full: bool = False):
        """Constraints that no longer hold. `full` (or DESK_FULL_CHECK=1) checks all of them; otherwise only those
        whose dependencies this decision changed, plus every constraint added since `since`."""
        dirty = self._take_dirty()
        if full or self.full_check or since is None:
            todo = self.constraints
        else:
            todo = [c for i, c in enumerate(self.constraints) if i >= since or self._touches(c[3], dirty)]
        self.checked = getattr(self, "checked", 0) + len(todo)
        return [(did, what) for did, what, fn, _ in todo if not fn()]

    # --- one decision
    def apply(self, d: dict) -> dict:
        op, keys, p, ev, did = d["op"], d["subject_keys"], d["payload"], d["evidence"], str(d["decision_id"])
        n_before = len(self.constraints)
        self.x("SAVEPOINT dec")
        try:
            detail = getattr(self, f"op_{op}")(d, keys, p, ev, did)
            broken = self.broken(since=n_before)
            if broken:
                raise Conflict("; ".join(f"breaks {w} (decision {x})" if x != did else f"cannot hold: {w}"
                                         for x, w in broken))
            self.patch_application(d, "applied", (detail or {}).get("how"))
            self.x("RELEASE dec")
            return dict(status="applied", **(detail or {}))
        except (Orphan, Conflict) as e:
            self.x("ROLLBACK TO dec")
            self.x("RELEASE dec")
            del self.constraints[n_before:]
            st = "orphaned" if isinstance(e, Orphan) else "conflict"
            self.patch(d)
            self.patch_application(d, "skipped", f"{st}: {e}")
            return dict(status=st, why=str(e),
                        with_decisions=sorted({x for x, _ in self.broken_with(e)}) if st == "conflict" else [])

    def broken_with(self, e):
        return [(m, None) for m in re.findall(r"decision ([0-9a-f-]{36})", str(e))]

    # --- the operations
    def op_revert(self, d, keys, p, ev, did):
        self.patch(d)
        return dict(how=f"reverts {p.get('decision_id')}: the machine's reading stands for these subjects")

    def op_retire(self, d, keys, p, ev, did):
        self.patch(d)
        return dict(how=f"retires orphaned decision {p.get('decision_id')}")

    def op_split_work(self, d, keys, p, ev, did):
        groups = p["groups"]
        allm = [m for g in groups for m in g["members"]] + list(p.get("unlisted_stay_on_first") or [])
        missing = [m for m in allm if not self.R.mention(m)]
        if missing:
            raise Orphan(f"{len(missing)} of the split's mentions are not in the reading: {missing[:5]}")
        k0, how = self.R.resolve_work(key_value(keys[0]), members=groups[0]["members"])
        if not k0:
            raise Orphan(f"{keys[0]} is not in the reading")
        pk_patch = self.patch(d)
        pk0 = self.card_pk(k0)
        moved = 0
        made = []
        for i, g in enumerate(groups):
            if i == 0:
                pk = pk0
                for m in list(g["members"]) + list(p.get("unlisted_stay_on_first") or []):
                    moved += self.move(m, pk, pk_patch) is not None or 0
            else:
                pk = self.ensure_card(g["card_id"], g["members"], f"desk-split:{did}|g{i}", k0, g.get("label"), d,
                                      pk_patch)
                made.append(g["card_id"])
                for m in g["members"]:
                    left = self.move(m, pk, pk_patch)
                    if left:
                        self.retire_card(left, g["card_id"], d, pk_patch, f"emptied by split {did}")
            self.must_cards(did, g["members"], f"split group {i} of {keys[0]}")
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                self.cannot_cards(did, groups[i]["members"], groups[j]["members"], f"split groups {i}/{j}")
        return dict(how=f"{keys[0]} -> {k0} ({how}); new cards {made}", cards=[k0] + made)

    def op_confirm_work(self, d, keys, p, ev, did):
        ms = self.present(p["members"])
        if not ms:
            raise Orphan(f"none of {keys[0]}'s members are in the reading")
        votes = Counter(self.R.card_of_mention(m) for m in ms)
        target = sorted(votes.items(), key=lambda v: (-v[1], v[0] or ""))[0][0]
        pk_patch = self.patch(d)
        for m in ms:
            left = self.move(m, self.card_pk(target), pk_patch)
            if left:
                self.retire_card(left, target, d, pk_patch, f"joined by confirm_work {did}")
        self.must_cards(did, ms, f"{keys[0]} confirmed one work")
        return dict(how=f"{len(ms)} members pinned on {target}", missing=sorted(set(p["members"]) - set(ms)))

    def op_same_work(self, d, keys, p, ev, did):
        mem = ev.get("members", {})
        k1, h1 = self.R.resolve_work(key_value(keys[0]), members=mem.get(keys[0]))
        k2, h2 = self.R.resolve_work(key_value(keys[1]), members=mem.get(keys[1]))
        if not k1 or not k2:
            raise Orphan(f"{keys[0] if not k1 else keys[1]} is not in the reading")
        pk_patch = self.patch(d)
        if k1 != k2:
            pk1 = self.card_pk(k1)
            for m in self.R.card_members(k2):
                self.move(m, pk1, pk_patch)
            pk2 = self.card_pk(k2)
            self.x("UPDATE OR IGNORE citation_links SET cited_work_pk = ? WHERE cited_work_pk = ?", (pk1, pk2))
            self.x("UPDATE work_relations SET subject_cited_work_pk = ? WHERE subject_cited_work_pk = ?", (pk1, pk2))
            self.x("UPDATE work_relations SET object_cited_work_pk = ? WHERE object_cited_work_pk = ?", (pk1, pk2))
            self.move_card_rows(pk2, pk1)
            self.retire_card(k2, k1, d, pk_patch, f"same work as {k1} (desk decision {did})")
        allm = (mem.get(keys[0]) or []) + (mem.get(keys[1]) or [])
        self.must_cards(did, allm, f"{keys[0]} = {keys[1]}")
        return dict(how=f"{k2} ({h2}) -> {k1} ({h1})" if k1 != k2 else f"already one card {k1}", cards=[k1])

    def move_card_rows(self, pk2: int, pk1: int):
        """A card joined into another brings its editions and its editors / translators (experiment 67): each
        citation keeps the edition it names; an edition both cards have (same key) becomes one row."""
        x = self.x
        for e in x("SELECT edition_pk, edition_key FROM cited_work_editions WHERE cited_work_pk = ?", (pk2,)).fetchall():
            have = x("SELECT edition_pk FROM cited_work_editions WHERE cited_work_pk = ? AND edition_key = ?",
                     (pk1, e[1])).fetchone()
            if have:
                x("UPDATE cited_work_members SET edition_pk = ? WHERE edition_pk = ?", (have[0], e[0]))
                x("UPDATE cited_work_contributors SET edition_pk = ? WHERE edition_pk = ?", (have[0], e[0]))
                x("DELETE FROM cited_work_editions WHERE edition_pk = ?", (e[0],))
            else:
                x("UPDATE cited_work_editions SET cited_work_pk = ? WHERE edition_pk = ?", (pk1, e[0]))
        top = x("SELECT coalesce(max(seq), 0) FROM cited_work_contributors WHERE cited_work_pk = ?", (pk1,)).fetchone()[0]
        for r in x("SELECT * FROM cited_work_contributors WHERE cited_work_pk = ? ORDER BY role, seq", (pk2,)).fetchall():
            if not x("SELECT 1 FROM cited_work_contributors WHERE cited_work_pk = ? AND role = ? AND printed IS ?",
                     (pk1, r["role"], r["printed"])).fetchone():
                top += 1
                x("INSERT INTO cited_work_contributors (cited_work_pk, role, seq, printed, name_key, edition_pk, "
                  "n_mentions) VALUES (?, ?, ?, ?, ?, ?, ?)", (pk1, r["role"], top, r["printed"], r["name_key"],
                                                               r["edition_pk"], r["n_mentions"]))
        x("DELETE FROM cited_work_contributors WHERE cited_work_pk = ?", (pk2,))
        self.recount_editions(pk1)

    def recount_editions(self, pk: int):
        self.x("""UPDATE cited_work_editions SET n_members = (SELECT count(*) FROM cited_work_members m
                  WHERE m.edition_pk = cited_work_editions.edition_pk) WHERE cited_work_pk = ?""", (pk,))

    def op_not_same_work(self, d, keys, p, ev, did):
        a, b = self.present(p["a_members"]), self.present(p["b_members"])
        if not a or not b:
            raise Orphan("the members of one side are no longer in the reading")
        pk_patch = self.patch(d)
        shared = self.cards_of(a) & self.cards_of(b)
        how = "already apart"
        if shared:
            c1, c2 = key_value(keys[0]), key_value(keys[1])
            if c2 in shared:            # the machine kept the second id for the joined card: move the first side out
                pk = self.ensure_card(c1, a, f"desk-apart:{did}|a", c2, None, d, pk_patch)
                for m in a:
                    if self.R.card_of_mention(m) in shared:
                        self.move(m, pk, pk_patch)
                how = f"the machine joined them on {sorted(shared)}: side a moved back to {c1}"
            else:
                pk = self.ensure_card(c2, b, f"desk-apart:{did}|b", sorted(shared)[0], None, d, pk_patch)
                for m in b:
                    if self.R.card_of_mention(m) in shared:
                        self.move(m, pk, pk_patch)
                how = f"the machine joined them on {sorted(shared)}: side b moved back to {c2}"
        self.cannot_cards(did, a, b, f"{keys[0]} ≠ {keys[1]}")
        return dict(how=how, missing=sorted(set(p["a_members"] + p["b_members"]) - set(a) - set(b)))

    def op_move_member(self, d, keys, p, ev, did):
        mid = key_value(keys[0])
        if not self.R.mention(mid):
            raise Orphan(f"{keys[0]} is not in the reading")
        mem = ev.get("members", {}).get(keys[1])
        k, how = self.R.resolve_work(key_value(keys[1]), members=mem)
        if not k:
            raise Orphan(f"{keys[1]} is not in the reading")
        pk_patch = self.patch(d)
        left = self.move(mid, self.card_pk(k), pk_patch)
        if left:
            self.retire_card(left, k, d, pk_patch, f"its last member moved to {k} (desk decision {did})")
        self.must_cards(did, [mid] + list(mem or [])[:1] + self.R.card_members(k)[:1], f"{keys[0]} on {keys[1]}")
        return dict(how=f"-> {k} ({how})")

    def op_set_work_type(self, d, keys, p, ev, did):
        k, how = self.R.resolve_work(key_value(keys[0]), members=ev.get("members", {}).get(keys[0]))
        if not k:
            raise Orphan(f"{keys[0]} is not in the reading")
        self.patch(d)
        self.x("UPDATE cited_works SET pub_type = ? WHERE cited_work_id = ?", (p["type"], k))
        mem = ev.get("members", {}).get(keys[0]) or []
        self.holds(did, f"{keys[0]} is a {p['type']}", lambda: all(
            (self.R.card(c) or {"pub_type": p["type"]})["pub_type"] == p["type"] for c in self.cards_of(
                self.present(mem)) or {k}))
        return dict(how=f"{k} ({how}) type {p['type']}")

    def op_same_person(self, d, keys, p, ev, did):
        refs = ev.get("authorships", {})
        p1 = self.resolve_person(key_value(keys[0]), refs.get(keys[0]))
        p2 = self.resolve_person(key_value(keys[1]), refs.get(keys[1]))
        if not p1 or not p2:
            raise Orphan(f"{keys[0] if not p1 else keys[1]} is not in the reading")
        pk_patch = self.patch(d)
        if p1 != p2:
            for a in self.R.authorships_of(p2):
                if self.x("SELECT 1 FROM authorships WHERE authorship_pk = ?", (a["authorship_pk"],)).fetchone():
                    self.set_authorship_person(a["authorship_pk"], p1, pk_patch)
            self.merge_person_rows(p2, p1)
            self.x("UPDATE persons SET status = 'merged' WHERE person_id = ?", (p2,))
            self.x("INSERT OR REPLACE INTO merged_ids VALUES (?, ?, 'person', 'merged-into', ?, ?, 'person', ?)",
                   (p2, p1, _iso(d["created_at"]), f"same person as {p1} (desk decision {did})", pk_patch))
        self.must_persons(did, (refs.get(keys[0]) or []) + (refs.get(keys[1]) or []), f"{keys[0]} = {keys[1]}")
        return dict(how=f"{p2} -> {p1}" if p1 != p2 else f"already one person {p1}")

    def op_not_same_person(self, d, keys, p, ev, did):
        a = [r for r in p.get("a_authorships") or [] if self.R.authorship_by_ref(r)]
        b = [r for r in p.get("b_authorships") or [] if self.R.authorship_by_ref(r)]
        pid_a, pid_b = key_value(keys[0]), key_value(keys[1])
        if not b or (not a and not self.R.resolve_person(pid_a)[0]):
            raise Orphan("the authorships of one side are no longer in the reading")
        pk_patch = self.patch(d)
        pa = {self.person_of_ref(r) for r in a} | {self.R.resolve_person(pid_a)[0]}
        moved = 0
        for r in b:
            row = self.R.authorship_by_ref(r)
            if row["person_id"] in pa - {None}:
                if any(self.R.authorship_by_ref(x)["authorship_pk"] == row["authorship_pk"] for x in a):
                    raise Conflict(f"{r} and side a are one authorship now: cannot keep them apart")
                self.ensure_person(pid_b, (ev.get("names") or {}).get(keys[1]), f"desk-apart:{did}")
                self.x("UPDATE authorships SET person_id = ?, method = 'person', asserted_by = 'person', "
                       "patch_key = ? WHERE authorship_pk = ?", (pid_b, pk_patch, row["authorship_pk"]))
                moved += 1
        self.cannot_persons(did, a or [], b, f"{keys[0]} ≠ {keys[1]}")
        return dict(how=f"the machine joined them: {moved} authorship(s) back to {pid_b}" if moved else "already apart")

    def op_link_byline(self, d, keys, p, ev, did):
        bk = key_value(keys[0])
        b = self.R.byline(bk)
        if not b or not b["authorship_pk"]:
            raise Orphan(f"{keys[0]} is not in the reading")
        pid = self.resolve_person(key_value(keys[1]))
        if not pid:
            raise Orphan(f"{keys[1]} is not in the reading")
        pk_patch = self.patch(d)
        old = b["person_id"]
        if old != pid:
            self.set_authorship_person(b["authorship_pk"], pid, pk_patch)
            if old:
                self.retire_person_if_empty(old, pid, d, pk_patch, f"its byline is {pid}'s (desk decision {did})")
        self.holds(did, f"{keys[0]} is {keys[1]}", lambda: self.person_of_ref(keys[0]) == self.resolve_person(
            key_value(keys[1])), self._person_deps([keys[0]], [pid]))
        return dict(how=f"{old} -> {pid}")

    def op_unlink_byline(self, d, keys, p, ev, did):
        bk = key_value(keys[0])
        b = self.R.byline(bk)
        if not b or not b["authorship_pk"]:
            raise Orphan(f"{keys[0]} is not in the reading")
        frm = key_value(p["from"])
        pk_patch = self.patch(d)
        if b["person_id"] == frm or self.resolve_person(frm) == b["person_id"]:
            self.ensure_person(p["new_person"], b["name_text"] or b["printed"], f"desk-unlink:{bk}")
            self.x("UPDATE authorships SET person_id = ?, method = 'person', asserted_by = 'person', patch_key = ? "
                   "WHERE authorship_pk = ?", (p["new_person"], pk_patch, b["authorship_pk"]))
        self.holds(did, f"{keys[0]} is not {p['from']}", lambda: self.person_of_ref(keys[0]) not in (
            frm, self.resolve_person(frm)), self._person_deps([keys[0]], [frm, p["new_person"]]))
        return dict(how=f"{b['person_id']} -> {p['new_person']}")

    def op_resolve_backref(self, d, keys, p, ev, did):
        m, t = self.R.mention(key_value(keys[0])), self.R.mention(key_value(keys[1]))
        if not m or not t:
            raise Orphan(f"{keys[0] if not m else keys[1]} is not in the reading")
        target = t["full_mention_pk"] if t["kind"] != "full" and t["full_mention_pk"] else t["mention_pk"]
        self.patch(d)
        self.x("UPDATE citation_mentions SET full_mention_pk = ?, resolve_method = 'person', resolve_score = 1.0, "
               "resolved_by = 'person', unresolved_why = NULL, resolve_evidence = ? WHERE mention_pk = ?",
               (target, json.dumps(dict(desk_decision=did), sort_keys=True), m["mention_pk"]))
        self.holds(did, f"{keys[0]} -> {keys[1]}", lambda: (self.R.mention(key_value(keys[0])) or {})[
            "full_mention_pk"] == target, {"m": {str(m["mention_pk"])}})
        followed = self.follow_chain(m, target, did)
        return dict(how=f"was {m['full_mention_pk']} ({m['resolve_method']}), now {target}"
                        + (f"; {len(followed)} back reference(s) after it follow" if followed else ""),
                    followers=followed)

    def op_unresolvable(self, d, keys, p, ev, did):
        m = self.R.mention(key_value(keys[0]))
        if not m:
            raise Orphan(f"{keys[0]} is not in the reading")
        self.patch(d)
        self.x("UPDATE citation_mentions SET full_mention_pk = NULL, resolve_method = 'person', resolve_score = NULL, "
               "resolved_by = 'person', unresolved_why = 'person: no earlier full citation in the article', "
               "resolve_evidence = ? WHERE mention_pk = ?",
               (json.dumps(dict(desk_decision=did), sort_keys=True), m["mention_pk"]))
        self.holds(did, f"{keys[0]} unresolved", lambda: (self.R.mention(key_value(keys[0])) or {})[
            "full_mention_pk"] is None, {"m": {str(m["mention_pk"])}})
        followed = self.follow_chain(m, None, did)
        return dict(how=f"was {m['full_mention_pk']} ({m['resolve_method']})"
                        + (f"; {len(followed)} back reference(s) after it follow" if followed else ""),
                    followers=followed)

    CHAIN_METHODS = ("previous-mention", "previous-mention (chain collapsed)", "previous-mention (follows person)")

    def follow_chain(self, m: dict, target, did) -> list[str]:
        """After a person re-points (or unresolves) mention m, the ibids that link47 resolved through it by the
        "mention just before" rule follow: walking forward in reading order (link47's order: reading_ord,
        mention_id), each next mention that is an ibid / op. cit. / loc. cit. resolved by that rule, and not decided
        by a person, takes the same target. The walk stops at anything else (a fresh citation breaks the chain) and
        at a person's own decision."""
        rows = self.x("SELECT mention_pk, mention_id, kind, resolve_method, resolved_by FROM citation_mentions "
                      "WHERE version_id = ? ORDER BY reading_ord, mention_id", (m["version_id"],)).fetchall()
        ids = [r[0] for r in rows]
        if m["mention_pk"] not in ids:
            return []
        out = []
        for pk, mid, kind, method, by in rows[ids.index(m["mention_pk"]) + 1:]:
            if kind not in ("ibid", "op_cit", "loc_cit") or method not in self.CHAIN_METHODS or by == "person":
                break
            if target is None:
                self.x("UPDATE citation_mentions SET full_mention_pk = NULL, resolve_method = NULL, resolve_score = NULL, "
                       "resolved_by = 'desk-chain', unresolved_why = ?, resolve_evidence = ? WHERE mention_pk = ?",
                       ("chain-broken: the back reference before it was marked unresolvable by a person",
                        json.dumps(dict(desk_decision=did, follows=m["mention_id"]), sort_keys=True), pk))
            else:
                self.x("UPDATE citation_mentions SET full_mention_pk = ?, resolve_method = 'previous-mention (follows "
                       "person)', resolve_score = 0.9, resolved_by = 'desk-chain', unresolved_why = NULL, "
                       "resolve_evidence = ? WHERE mention_pk = ?",
                       (target, json.dumps(dict(desk_decision=did, follows=m["mention_id"]), sort_keys=True), pk))
            out.append(mid)
        return out

    # --- institutions and printed affiliations (experiment 64)
    def res_inst(self, key_or_id: str) -> str | None:
        return self.R.resolve_inst(key_value(key_or_id) if ":" in key_or_id else key_or_id)[0]

    def need_inst(self, key: str) -> str:
        iid = self.res_inst(key)
        if not iid:
            raise Orphan(f"{key} is not in the reading")
        return iid

    def need_aff(self, key: str, ev: dict | None = None) -> dict:
        a = self.R.aff(key_value(key))
        if not a:       # experiment 68: an English line that moved to its twin's mention (exp 65), by its printed text
            a = self.R.aff_moved_twin(key_value(key), (ev or {}).get("printed"))
        if not a:       # experiment 68: the byline moved (exp 65's fold) or lost its script: by text in the article
            pr = (ev or {}).get("printed")
            peers = self.aff_peers.get((key_value(key).split("|")[0], pr), [])
            a = self.R.aff_by_text(key_value(key), pr, peers.index(key_value(key)) if key_value(key) in peers else 0)
            if a and a["aff_pk"] in self.decided_affs:
                a = None                    # never two decided keys on one row
        if not a:
            raise Orphan(f"{key} is not in the reading")
        self.decided_affs.add(a["aff_pk"])
        self.aff_by_key[key_value(key)] = a
        return a

    def inherit_twins(self) -> int:
        """Experiment 68: an affiliation printed again in the other script (twin_of_aff_pk -> the main line) that no
        decision names takes the organisation-level links of its main line when a decision settled that line: the
        same statement, translated. Counts skip twin rows (twin_of_aff_pk IS NOT NULL), so this is for display."""
        cols = {r[1] for r in self.x("PRAGMA table_info(affiliation_mentions)").fetchall()}
        if "twin_of_aff_pk" not in cols:
            return 0
        n = 0
        for t, s in self.x("SELECT aff_pk, twin_of_aff_pk FROM affiliation_mentions WHERE twin_of_aff_pk IS NOT NULL "
                           "ORDER BY aff_pk").fetchall():
            if t in self.decided_affs or s not in self.decided_affs:
                continue
            want = self.x("SELECT inst_id, level, evidence FROM affiliation_links WHERE aff_pk = ?", (s,)).fetchall()
            want = [w for w in want if w[1] in ORG_LEVELS]
            for iid, lvl in self.links_of(t, ORG_LEVELS):
                self.x("DELETE FROM affiliation_links WHERE aff_pk = ? AND inst_id = ?", (t, iid))
            for iid, lvl, evd in want:
                self.x("INSERT OR REPLACE INTO affiliation_links (aff_pk, inst_id, level, method, score, asserted_by, "
                       "evidence) VALUES (?, ?, ?, ?, 1.0, 'person', ?)",
                       (t, iid, lvl, f"desk: twin of aff {s}", json.dumps(dict(twin_of_aff_pk=s, main=evd),
                                                                         ensure_ascii=False, sort_keys=True)))
            n += 1
        return n

    def links_of(self, aff_pk: int, levels=None) -> set:
        rows = self.x("SELECT inst_id, level FROM affiliation_links WHERE aff_pk = ?", (aff_pk,)).fetchall()
        return {(r[0], r[1]) for r in rows if levels is None or r[1] in levels}

    def ancestors(self, iid: str) -> list[str]:
        out, cur = [], iid
        while True:
            r = self.x("SELECT parent_id FROM institutions WHERE inst_id = ?", (cur,)).fetchone()
            if not r or not r[0] or r[0] in out or r[0] == iid:
                return out
            out.append(r[0])
            cur = r[0]

    def add_inst_names(self, iid: str, names, source: str):
        for n in names:
            self.x("""INSERT OR IGNORE INTO institution_names (inst_id, name, lang, script, type, name_key, n_seen,
                      source) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)""",
                   (iid, n["name"].strip(), n.get("lang"), n.get("script"), n.get("type", "label"), source))

    def new_inst_row(self, iid: str, kind: str, natural: str, source: str, parent=None, country=None, city=None):
        self.x("INSERT INTO institutions (inst_id, kind, parent_id, country_code, city, status, catalogue_authority_id, "
               "source) VALUES (?, ?, ?, ?, ?, 'active', NULL, ?)", (iid, kind, parent, country, city, source))
        self.x("INSERT OR IGNORE INTO id_registry (public_id, kind, natural_key, created_load) VALUES (?, 'institution', "
               "?, ?)", (iid, natural, self.load_id))
        if parent:
            self.set_parent_row(iid, parent, source, None)

    def set_parent_row(self, iid: str, parent: str, source: str, reason):
        self.x("UPDATE institutions SET parent_id = ? WHERE inst_id = ?", (parent, iid))
        self.x("DELETE FROM institution_relations WHERE from_id = ? AND relation = 'parent'", (iid,))
        self.x("INSERT OR REPLACE INTO institution_relations (from_id, to_id, relation, start_year, end_year, source, "
               "reason) VALUES (?, ?, 'parent', NULL, NULL, ?, ?)", (iid, parent, source, reason))

    def merge_inst(self, old: str, keep: str, d, pk_patch, why):
        x = self.x
        x("INSERT OR IGNORE INTO affiliation_links (aff_pk, inst_id, level, method, score, asserted_by, evidence) "
          "SELECT aff_pk, ?, level, method, score, asserted_by, evidence FROM affiliation_links WHERE inst_id = ?",
          (keep, old))
        x("DELETE FROM affiliation_links WHERE inst_id = ?", (old,))
        for r in x("SELECT * FROM institution_names WHERE inst_id = ?", (old,)).fetchall():
            cur = x("SELECT n_seen FROM institution_names WHERE inst_id = ? AND name = ? AND type = ?",
                    (keep, r["name"], r["type"])).fetchone()
            if cur:
                if r["n_seen"]:
                    x("UPDATE institution_names SET n_seen = coalesce(n_seen, 0) + ? WHERE inst_id = ? AND name = ? "
                      "AND type = ?", (r["n_seen"], keep, r["name"], r["type"]))
            else:
                x("INSERT INTO institution_names (inst_id, name, lang, script, type, name_key, n_seen, source) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (keep, r["name"], r["lang"], r["script"], r["type"],
                                                      r["name_key"], r["n_seen"], r["source"]))
        for r in x("SELECT inst_id FROM institutions WHERE parent_id = ?", (old,)).fetchall():
            self.set_parent_row(r[0], keep, "desk", why)
        x("UPDATE OR IGNORE institution_relations SET to_id = ? WHERE to_id = ? AND from_id <> ?", (keep, old, keep))
        x("UPDATE OR IGNORE institution_relations SET from_id = ? WHERE from_id = ? AND to_id <> ? "
          "AND relation <> 'parent'", (keep, old, keep))
        x("UPDATE supervisions SET inst_id = ? WHERE inst_id = ?", (keep, old))
        o, k = self.R.inst(old), self.R.inst(keep)
        for col in ("country_code", "city"):
            if o[col] and not k[col]:
                x(f"UPDATE institutions SET {col} = ? WHERE inst_id = ?", (o[col], keep))
        x("UPDATE institutions SET status = 'merged' WHERE inst_id = ?", (old,))
        x("INSERT OR REPLACE INTO merged_ids VALUES (?, ?, 'institution', 'merged-into', ?, ?, 'person', ?)",
          (old, keep, _iso(d["created_at"]), why, pk_patch))

    def op_define_institution(self, d, keys, p, ev, did):
        iid = key_value(keys[0])
        pk_patch = self.patch(d)
        now = self.res_inst(iid)
        if not now:
            # experiment 68: a machine row the decision named that the machine no longer reads (a reload changed
            # its clustering) is kept by the decision: re-made under its registered id, as a new body would be
            known = self.x("SELECT 1 FROM id_registry WHERE public_id = ? AND kind = 'institution'", (iid,)).fetchone()
            if not p.get("new") and not known:
                raise Orphan(f"{keys[0]} is not in the reading")
            was = (ev or {}).get("was") or {} if not p.get("new") else {}
            self.new_inst_row(iid, p["kind"], f"librarian:{p['authority']}", f"desk: {d['actor_id']}",
                              city=p.get("city"), country=was.get("country"))   # as the decision saw it
            now, how = iid, "new row" if p.get("new") else "the machine's row, gone from this reading: kept as it was"
        else:
            how = "the machine's row" if now == iid else f"merged into {now}"
        self.add_inst_names(now, p["names"], "desk")
        self.holds(did, f"{keys[0]} is an active institution named {p['names'][0]['name']}", lambda: bool(
            self.res_inst(iid) and self.x("SELECT 1 FROM institution_names WHERE inst_id = ? AND name = ?",
                                          (self.res_inst(iid), p["names"][0]["name"].strip())).fetchone()),
            {"i": {iid, now}})
        return dict(how=f"{p['authority']} = {now} ({how})")

    def op_same_institution(self, d, keys, p, ev, did):
        keep = self.need_inst(keys[0])
        others = [self.need_inst(k) for k in keys[1:]]
        pk_patch = self.patch(d)
        gone = []
        for o in dict.fromkeys(others):
            if o != keep:
                self.merge_inst(o, keep, d, pk_patch, f"same institution as {keep} (desk decision {did})")
                gone.append(o)
        ids = [key_value(k) for k in keys]
        self.holds(did, f"{', '.join(keys)} are one institution",
                   lambda: len({self.res_inst(i) for i in ids}) == 1, {"i": set(ids) | {keep}})
        return dict(how=f"{gone} -> {keep}" if gone else f"already one row {keep}")

    def op_not_an_institution_row(self, d, keys, p, ev, did):
        iid = self.need_inst(keys[0])
        self.patch(d)
        n = self.x("DELETE FROM affiliation_links WHERE inst_id = ?", (iid,)).rowcount
        self.x("UPDATE institutions SET status = 'not-an-institution' WHERE inst_id = ?", (iid,))
        self.holds(did, f"{keys[0]} names no body: nothing linked to it", lambda: self.x(
            "SELECT 1 FROM affiliation_links WHERE inst_id = ? LIMIT 1", (iid,)).fetchone() is None, {"i": {iid}})
        return dict(how=f"{n} link(s) to {iid} removed")

    def op_set_inst_country(self, d, keys, p, ev, did):
        iid = self.need_inst(keys[0])
        self.patch(d)
        was = self.R.inst(iid)["country_code"]
        self.x("UPDATE institutions SET country_code = ? WHERE inst_id = ?", (p["country"], iid))
        k0 = key_value(keys[0])
        self.holds(did, f"{keys[0]} is in {p['country']}", lambda: (self.R.inst(self.res_inst(k0) or k0) or {
            "country_code": None})["country_code"] == p["country"], {"i": {k0, iid}})
        return dict(how=f"{iid}: {was} -> {p['country']}")

    def op_set_inst_parent(self, d, keys, p, ev, did):
        u, par = self.need_inst(keys[0]), self.need_inst(keys[1])
        if u == par or u in self.ancestors(par):
            raise Conflict(f"cannot hold: {keys[1]} is {keys[0]} or lies under it (a parent cycle)")
        self.patch(d)
        was = self.R.inst(u)["parent_id"]
        self.set_parent_row(u, par, "desk", f"desk decision {did}")
        ku, kp = key_value(keys[0]), key_value(keys[1])
        self.holds(did, f"{keys[0]} is a unit of {keys[1]}", lambda: (self.R.inst(self.res_inst(ku) or ku) or {
            "parent_id": None})["parent_id"] == self.res_inst(kp), {"i": {ku, kp, u, par}})
        return dict(how=f"{u}: parent {was} -> {par}")

    def op_set_inst_type(self, d, keys, p, ev, did):
        iid = self.need_inst(keys[0])
        self.patch(d)
        self.x("UPDATE institutions SET kind = ? WHERE inst_id = ?", (p["type"], iid))
        k0 = key_value(keys[0])
        self.holds(did, f"{keys[0]} is a {p['type']}", lambda: (self.R.inst(self.res_inst(k0) or k0) or {
            "kind": None})["kind"] == p["type"], {"i": {k0, iid}})
        return dict(how=f"{iid} kind {p['type']}")

    def op_link_affiliation(self, d, keys, p, ev, did):
        a = self.need_aff(keys[0], ev)
        apk = a["aff_pk"]
        want = []
        for t in p["institutions"]:
            want.append((self.need_inst(t["inst"]), AFF_ROLES[t["role"]], t))
        pk_patch = self.patch(d)
        targets = {w[0] for w in want if w[1] == "org"}
        units = []
        for iid, lvl in sorted(self.links_of(apk, ORG_LEVELS)):
            if (iid, lvl) in {(w[0], w[1]) for w in want}:
                continue
            self.x("DELETE FROM affiliation_links WHERE aff_pk = ? AND inst_id = ?", (apk, iid))
            if lvl == "org" and iid not in targets and targets & set(self.ancestors(iid)):
                kind = (self.R.inst(iid) or {"kind": None})["kind"]
                self.x("INSERT OR IGNORE INTO affiliation_links (aff_pk, inst_id, level, method, score, asserted_by, "
                       "evidence) VALUES (?, ?, ?, ?, 1.0, 'person', ?)",
                       (apk, iid, "faculty" if kind == "faculty" else "dept", f"desk {d['op']}: a unit of the body",
                        json.dumps(dict(desk_decision=did), sort_keys=True)))
                units.append(iid)
        for iid, lvl, t in want:
            inf = t.get("inferred")
            self.x("INSERT OR REPLACE INTO affiliation_links (aff_pk, inst_id, level, method, score, asserted_by, "
                   "evidence) VALUES (?, ?, ?, ?, 1.0, 'person', ?)",
                   (apk, iid, lvl, f"desk {d['op']}" + (f"; inferred from the {inf['from']}" if inf else ""),
                    json.dumps(dict(desk_decision=did, actor=d["actor_id"], role=t["role"],
                                    inferred=inf), ensure_ascii=False, sort_keys=True)))
        spec = [(key_value(t["inst"]), AFF_ROLES[t["role"]], t.get("country")) for t in p["institutions"]]

        def holds():
            have = self.links_of(apk, ORG_LEVELS)
            exp = {(self.res_inst(i), lvl) for i, lvl, _ in spec}
            if have != exp:
                return False
            return all(c is None or (self.R.inst(self.res_inst(i)) or {"country_code": None})["country_code"] == c
                       for i, _, c in spec)
        self.holds(did, f"{keys[0]} names {', '.join(f'{i} ({l})' for i, l, _ in spec)}, each in its own country",
                   holds, {"f": {str(apk)}, "i": {i for i, _, _ in spec} | {w[0] for w in want}})
        return dict(how=f"aff {apk} -> {[(w[0], w[1]) for w in want]}" + (f"; kept as units {units}" if units else "")
                    + (f"; the line moved to its twin's mention (key {a['moved_from']})" if a.get("moved_from") else ""))

    def op_not_an_institution(self, d, keys, p, ev, did):
        """The statement names no body: its organisation-level links go. A faculty or department the machine read
        from it (printed words such as «قسم التاريخ») stays as the machine has it."""
        apk = self.need_aff(keys[0], ev)["aff_pk"]
        self.patch(d)
        n = 0
        for iid, lvl in self.links_of(apk, ORG_LEVELS):
            n += self.x("DELETE FROM affiliation_links WHERE aff_pk = ? AND inst_id = ?", (apk, iid)).rowcount
        self.holds(did, f"{keys[0]} names no body", lambda: not self.links_of(apk, ORG_LEVELS), {"f": {str(apk)}})
        return dict(how=f"{n} organisation link(s) removed")

    def op_unit_kept_apart(self, d, keys, p, ev, did):
        apk = self.need_aff(keys[0], ev)["aff_pk"]
        self.patch(d)
        n = 0
        for iid, lvl in self.links_of(apk, ORG_LEVELS):
            n += self.x("DELETE FROM affiliation_links WHERE aff_pk = ? AND inst_id = ?", (apk, iid)).rowcount
        self.holds(did, f"{keys[0]} names a unit only, no body", lambda: not self.links_of(apk, ORG_LEVELS),
                   {"f": {str(apk)}})
        return dict(how=f"{n} organisation link(s) removed; its faculty kept")

    def op_not_same_institution(self, d, keys, p, ev, did):
        row = self.need_inst(keys[0])
        groups = p["groups"]
        pks, missing = [], []
        for g in groups:
            affs = [self.R.aff(key_value(a)) or self.aff_by_key.get(key_value(a)) for a in g["affiliations"]]
            missing += [a for a, x in zip(g["affiliations"], affs) if not x]
            pks.append([x["aff_pk"] for x in affs if x])
        # experiment 68: a printed line the reading no longer holds on its own (experiment 65 read it as part of
        # another line) has nothing to move; the split stands on the rest, and is an orphan only if nothing is left
        if not any(pks):
            raise Orphan(f"none of the split's {len(missing)} affiliations is in the reading")
        pk_patch = self.patch(d)
        made = []
        tmpl = self.R.inst(row)
        for i, (g, gp) in enumerate(zip(groups, pks)):
            body = self.res_inst(g["body"]) if g.get("body") else None
            if not p.get("lumped_faculty"):
                continue
            if i == 0:
                if body and body != row and row not in self.ancestors(body):
                    self.set_parent_row(row, body, "desk", f"desk decision {did}")
                continue
            if not gp:
                continue
            q = ",".join("?" * len(gp))
            if not self.x(f"SELECT 1 FROM affiliation_links WHERE inst_id = ? AND aff_pk IN ({q}) LIMIT 1",
                          (row, *gp)).fetchone():
                continue
            new = g["row"]
            if not self.R.inst(new):
                country = (self.R.inst(body) or {"country_code": None})["country_code"] if body else None
                self.new_inst_row(new, tmpl["kind"], f"desk-split:{did}|g{i}", "desk split", parent=body,
                                  country=country, city=tmpl["city"] if not body else None)
                for r in self.x("SELECT name, lang, script, type FROM institution_names WHERE inst_id = ?",
                                (row,)).fetchall():
                    self.add_inst_names(new, [dict(r)], "desk split")
            self.x(f"UPDATE OR IGNORE affiliation_links SET inst_id = ? WHERE inst_id = ? AND aff_pk IN ({q})",
                   (new, row, *gp))
            self.x(f"DELETE FROM affiliation_links WHERE inst_id = ? AND aff_pk IN ({q})", (row, *gp))
            made.append(new)
        allpk = {str(x) for gp in pks for x in gp}

        def apart():
            sets = [set().union(*(self.links_of(x) for x in gp)) for gp in pks]
            sets = [{i for i, _ in s} for s in sets]
            return all(not (sets[i] & sets[j]) for i in range(len(sets)) for j in range(i + 1, len(sets)))
        self.holds(did, f"the {len(groups)} groups of {keys[0]} share no institution", apart, {"f": allpk})
        return dict(how=(f"{keys[0]} -> {row}; new rows {made}" if made else f"{keys[0]}: groups already apart")
                    + (f"; not in the reading any more: {missing}" if missing else ""), rows=[row] + made)

    # --- cited works: editions, not a work, collective books, links and relations (experiment 67)
    def side_cards(self, key: str, members) -> set:
        """The cards a decision's work sits on now: those holding its recorded citations, else its id resolved."""
        cs = self.cards_of(self.present(members or []))
        if not cs:
            k = self.R.resolve_work(key_value(key))[0]
            cs = {k} if k else set()
        return cs

    def edition_row(self, pk: int, ekey: str, printed, like: dict | None, members) -> int:
        epk = spk("cited_work_editions", pk, ekey)
        like = like or {}
        firsts = sorted(self.mention_pk(m) for m in members)
        self.x("""INSERT OR REPLACE INTO cited_work_editions (edition_pk, cited_work_pk, edition_key, edition_printed,
                  year_printed, year_calendar, year2, publisher, place, n_members, first_mention_pk)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
               (epk, pk, ekey, printed or like.get("edition_printed"), like.get("year_printed"),
                like.get("year_calendar"), like.get("year2"), like.get("publisher"), like.get("place"), len(members),
                firsts[0] if firsts else None))
        q = ",".join("?" * len(firsts))
        self.x(f"UPDATE cited_work_members SET edition_pk = ? WHERE full_mention_pk IN ({q})", (epk, *firsts))
        return epk

    def editions_of(self, mids) -> list:
        out = []
        for m in mids:
            r = self.x("SELECT cm.edition_pk FROM cited_work_members cm JOIN citation_mentions c ON c.mention_pk = "
                       "cm.full_mention_pk WHERE c.mention_id = ?", (m,)).fetchone()
            out.append(r[0] if r else None)
        return out

    def op_edition_of(self, d, keys, p, ev, did):
        """One work in two editions (D41): card 2 joins card 1 as same_work does, and the citations of each side
        keep an edition of their own. A side given a label (payload.edition_a / edition_b, e.g. «بشرح النووي», D40)
        gets an edition row with that label, its year and publisher taken from the edition it named before."""
        mem = ev.get("members", {})
        ma, mb = mem.get(keys[0]) or [], mem.get(keys[1]) or []
        k1, h1 = self.R.resolve_work(key_value(keys[0]), members=ma)
        k2, h2 = self.R.resolve_work(key_value(keys[1]), members=mb)
        if not k1 or not k2:
            raise Orphan(f"{keys[0] if not k1 else keys[1]} is not in the reading")
        pk_patch = self.patch(d)
        pk1 = self.card_pk(k1)
        c2 = dict(self.R.card(k2))
        if k1 != k2:
            pk2 = self.card_pk(k2)
            for m in self.R.card_members(k2):
                self.move(m, pk1, pk_patch)
            self.x("UPDATE OR IGNORE citation_links SET cited_work_pk = ? WHERE cited_work_pk = ?", (pk1, pk2))
            self.x("UPDATE work_relations SET subject_cited_work_pk = ? WHERE subject_cited_work_pk = ?", (pk1, pk2))
            self.x("UPDATE work_relations SET object_cited_work_pk = ? WHERE object_cited_work_pk = ?", (pk1, pk2))
            self.move_card_rows(pk2, pk1)
            self.retire_card(k2, k1, d, pk_patch, f"an edition of {k1}: one work (desk decision {did})")
        a, b = self.present(ma), self.present(mb)
        made = []
        c1 = dict(self.R.card(k1))
        for side, ms, label, card in (("a", a, p.get("edition_a"), c1), ("b", b, p.get("edition_b"), c2)):
            if not ms:
                continue
            other = set(self.editions_of(b if side == "a" else a))
            groups = {}
            for m, e in zip(ms, self.editions_of(ms)):
                groups.setdefault(e, []).append(m)
            for e, gm in sorted(groups.items(), key=lambda kv: str(kv[0])):
                # card 2's citations are the other edition: one naming no edition gets card 2's (its year and
                # publisher), one naming an edition card 1's citations name too gets a row of its own; a label (D40)
                # is given to every edition of its side (a copy that carries it). Card 1's citations that name no
                # edition stay so.
                if not (label or (e is None and side == "b") or (e is not None and e in other)):
                    continue
                r = self.x("SELECT * FROM cited_work_editions WHERE edition_pk = ?", (e,)).fetchone() if e else None
                like = dict(r) if r else dict(year_printed=card["year_printed"], publisher=card["publisher"],
                                              place=card["place"])
                made.append(self.edition_row(pk1, f"desk:{did}|{side}|{r['edition_key'] if r else ''}", label, like,
                                             gm))
                if e is not None:
                    self.drop_edition_if_unused(e, made[-1])
        self.recount_editions(pk1)
        self.must_cards(did, ma + mb, f"{keys[0]} and its edition {keys[1]}")

        def apart():
            ea, eb = self.editions_of(self.present(ma)), self.editions_of(self.present(mb))
            return None not in eb and not (set(ea) & set(eb))
        self.holds(did, f"the editions of {keys[0]} and {keys[1]} kept apart", apart, self._mention_deps(ma + mb))
        return dict(how=(f"{k2} ({h2}) -> {k1} ({h1})" if k1 != k2 else f"already one card {k1}")
                    + (f"; {len(made)} edition row(s) made" if made else ""), cards=[k1])

    def op_not_a_work(self, d, keys, p, ev, did):
        """A card that is not a work as it stands (exp 62: a journal's name): `drop` takes its citations off every
        card (they name no work: they count for none); `retitle` keeps the one work and gives it its title;
        `one_per_citation` puts each citation on a card of its own (each prints another article)."""
        ms = self.present(p["members"])
        if not ms:
            raise Orphan(f"none of {keys[0]}'s citations are in the reading")
        k, how = self.R.resolve_work(key_value(keys[0]), members=ms)
        act = p["action"]
        pk_patch = self.patch(d)
        titles = p.get("titles") or {}
        if act == "drop":
            n = 0
            for m in ms:
                n += self.x("DELETE FROM cited_work_members WHERE full_mention_pk = ?", (self.mention_pk(m),)).rowcount
            if k and not self.R.card_members(k):
                self.x("UPDATE cited_works SET status = 'not-a-work' WHERE cited_work_id = ?", (k,))
            if k:
                self.recount_editions(self.card_pk(k))
            self.holds(did, f"{keys[0]}'s citations name no work", lambda: not self.cards_of(self.present(ms)),
                       self._mention_deps(ms))
            return dict(how=f"{n} citation(s) off {k}: not a work")
        if not k:
            raise Orphan(f"{keys[0]} is not in the reading")
        if act == "retitle":
            t = p.get("title") or next((titles[m] for m in ms if titles.get(m)), None)
            if t:
                self.x("UPDATE cited_works SET title = ? WHERE cited_work_id = ?", (t, k))
            self.must_cards(did, ms, f"{keys[0]} is one work")
            if t:              # while the card is this one: joined into another work, that work's title stands
                self.holds(did, f"{keys[0]} is titled «{t[:60]}»", lambda: all(
                    (self.R.card(c) or {"title": None})["title"] == t for c in self.cards_of(self.present(ms))
                    if c == k), self._mention_deps(ms))
            return dict(how=f"{k}: one work, " + (f"titled «{t[:80]}»" if t else "no title printed to give it"))
        made = []
        for i, g in enumerate(p["groups"]):
            m = g["members"][0]
            if not self.R.mention(m):
                continue
            if i == 0:
                pk = self.card_pk(k)
                self.move(m, pk, pk_patch)
                cid = k
            else:
                cid = g["card_id"]
                pk = self.ensure_card(cid, [m], f"desk-notwork:{did}|g{i}", k, None, d, pk_patch)
                self.move(m, pk, pk_patch)
                made.append(cid)
            if titles.get(m):
                self.x("UPDATE cited_works SET title = ? WHERE cited_work_id = ?", (titles[m], cid))
        groups = [g["members"] for g in p["groups"]]
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                self.cannot_cards(did, groups[i], groups[j], f"citations {i}/{j} of {keys[0]}")
        return dict(how=f"{k}: one card per citation; new cards {made}", cards=[k] + made)

    def op_define_work(self, d, keys, p, ev, did):
        cid = key_value(keys[0])
        now = self.R.resolve_work(cid)[0]
        self.patch(d)
        if not now:
            if not p.get("new"):
                raise Orphan(f"{keys[0]} is not in the reading")
            pk = spk("cited_works", cid)
            authors = p.get("authors") or []
            self.x("""INSERT INTO cited_works (cited_work_pk, cited_work_id, pub_type, title, title_key, first_author_key,
                      year_printed, place, publisher, lang, status, method, built_load)
                      VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, 'active', 'person: desk define_work', ?)""",
                   (pk, cid, p.get("pub_type") or "book", p["title"], p.get("year"), p.get("place"), p.get("publisher"),
                    p.get("lang"), self.load_id))
            self.x("INSERT OR IGNORE INTO id_registry (public_id, kind, natural_key, created_load) VALUES (?, "
                   "'cited_work', ?, ?)", (cid, f"desk-define:{p['natural']}", self.load_id))
            for k_, a in enumerate(authors):
                self.x("INSERT OR REPLACE INTO cited_work_authors (cited_work_pk, seq, printed) VALUES (?, ?, ?)",
                       (pk, k_ + 1, a))
            for k_, e in enumerate(p.get("editors") or []):
                self.x("INSERT OR IGNORE INTO cited_work_contributors (cited_work_pk, role, seq, printed, n_mentions) "
                       "VALUES (?, 'editor', ?, ?, 0)", (pk, k_ + 1, e))
            now, how = cid, "new card"
        else:
            how = "the card exists" if now == cid else f"merged into {now}"
        self.holds(did, f"{keys[0]} is an active work", lambda: self.R.resolve_work(cid)[0] is not None,
                   {"c": {str(spk("cited_works", cid))}})
        return dict(how=f"{keys[0]}: {how}")

    def ensure_pub(self, key: str, p: dict) -> str:
        """The publication a link or relation points at; a catalogue record the decision carries is added as a
        catalogued-only publication W<c999> (with its record, contributors and journal), as link47 adds its own
        targets (platform v2's biblio47.ensure_catalogued_pub, from the record the decision saw)."""
        pid = key_value(key)
        r = self.R.pub(pid)
        if r:
            return r["pub_id"]
        rec = p.get("record")
        if not rec:
            raise Orphan(f"{key} is not in the reading (and the decision carries no catalogue record)")
        c999 = str(rec["c999"])
        exp = self.x("SELECT export_id FROM catalogue_exports ORDER BY built DESC LIMIT 1").fetchone()
        jid = None
        if rec.get("journal_code"):
            jid = f"J{rec['journal_code']}"
            if not self.x("SELECT 1 FROM journals WHERE journal_id = ?", (jid,)).fetchone():
                self.x("INSERT INTO journals (journal_id, code, country_code, databases, first_year, last_year) "
                       "VALUES (?, ?, NULL, ?, NULL, NULL)", (jid, rec["journal_code"], rec.get("databases")))
                for col, form in (("journal", "catalogue"), ("journal_en", "catalogue-en")):
                    if rec.get(col):
                        self.x("INSERT OR IGNORE INTO journal_titles (journal_id, title, lang, form, n, source, is_chosen)"
                               " VALUES (?, ?, NULL, ?, 1, 'desk: the catalogue record of a link', ?)",
                               (jid, rec[col], form, int(form == "catalogue")))
        if not self.x("SELECT 1 FROM catalogue_records WHERE c999 = ?", (c999,)).fetchone():
            self.x("""INSERT INTO catalogue_records (c999, export_id, rec, type, title, subtitle, title_en, language_raw,
                      year_raw, year_int, year_hijri, pages_raw, page_first, page_last, journal_code, journal_raw,
                      volume_raw, issue_raw, article_seq, doi, databases)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (c999, exp[0] if exp else None, rec.get("rec"), rec.get("type"), rec["title"], rec.get("subtitle"),
                    rec.get("title_en"), rec.get("language"), rec.get("year"), rec.get("year_int"),
                    rec.get("year_hijri"), rec.get("pages"), rec.get("page_first"), rec.get("page_last"),
                    rec.get("journal_code"), rec.get("journal"), rec.get("volume"), rec.get("issue"),
                    rec.get("article_seq"), rec.get("doi"), rec.get("databases")))
            for a in rec.get("authors") or []:
                self.x("""INSERT OR IGNORE INTO catalogue_contributors (c999, seq, tag, name, latin, role_raw, role_code,
                          authority_id, is_org) VALUES (?, ?, ?, ?, ?, ?, 'author', ?, ?)""",
                       (c999, a.get("seq"), a.get("tag"), a.get("name"), a.get("latin"), a.get("role"),
                        a.get("authority_id") or None, a.get("is_org") or 0))
            for i, st in enumerate(rec.get("stems") or []):
                self.x("INSERT OR IGNORE INTO catalogue_record_documents (c999, stem, seq, label) VALUES (?, ?, ?, NULL)",
                       (c999, st, i + 1))
        self.x("""INSERT INTO publications (pub_id, c999, journal_id, issue_id, seq_in_issue, type, type_catalogue,
                  status, title_shown, year_shown, current_version) VALUES (?, ?, ?, NULL, ?, ?, ?, 'catalogued-only',
                  ?, ?, NULL)""", (pid, c999, jid, rec.get("article_seq"), CAT_TYPE.get(rec.get("type"), "other"),
                                    rec.get("type"), rec["title"], rec.get("year_int")))
        return pid

    def op_link_publication(self, d, keys, p, ev, did):
        """The cited work is this Mandumah publication (`as: work`), or Mandumah holds the same text published in
        another journal (`as: same_text`, D44): the link becomes the card's accepted best link, the one the index
        counts; the machine's other links of the card stay, not best."""
        mem = ev.get("members", {}).get(keys[0]) or []
        k, how = self.R.resolve_work(key_value(keys[0]), members=mem)
        if not k:
            raise Orphan(f"{keys[0]} is not in the reading")
        pid = self.ensure_pub(keys[1], p)
        self.patch(d)
        pk = self.card_pk(k)
        # exp 74: a card that two joined cards made can hold two rows to this one publication (each card had its own
        # link: a reference printed in Arabic and in English); every best row is cleared first, then the chosen row
        # is made best (before, the second row tripped the one-best-link-per-card index)
        self.x("UPDATE citation_links SET best = 0 WHERE cited_work_pk = ? AND best = 1", (pk,))
        evj = json.dumps(dict(desk_decision=did, actor=d["actor_id"], link_as=p["as"], cited_as=p.get("cited_as"),
                              reason=d["reason_code"]), ensure_ascii=False, sort_keys=True)
        method = "person" if p["as"] == "work" else "person: the same text (D44)"
        row = self.x("SELECT link_pk FROM citation_links WHERE cited_work_pk = ? AND target_kind = 'publication' AND "
                     "target_pub_id = ?", (pk, pid)).fetchone()
        if row:
            self.x("""UPDATE citation_links SET status = 'accepted', best = 1, score = 1.0, method = ?, matched_on = ?,
                      evidence = ?, asserted_by = 'person' WHERE link_pk = ?""",
                   (method, "same-text" if p["as"] == "same_text" else "person", evj, row[0]))
        else:
            via = sorted(self.mention_pk(m) for m in self.present(mem))
            self.x("""INSERT INTO citation_links (link_pk, cited_work_pk, via_mention_pk, target_kind, target_pub_id,
                      status, best, score, method, matched_on, evidence, asserted_by, link_run_id, created)
                      VALUES (?, ?, ?, 'publication', ?, 'accepted', 1, 1.0, ?, ?, ?, 'person', NULL, ?)""",
                   (spk("citation_links", did), pk, via[0] if via else None, pid, method,
                    "same-text" if p["as"] == "same_text" else "person", evj, _iso(d["created_at"])))
        k0 = key_value(keys[0])

        def holds():
            for c in self.side_cards(keys[0], mem):
                b = self.R.best_link(c)
                if not b or b["target_pub_id"] != pid:
                    return False
            return bool(self.side_cards(keys[0], mem))
        self.holds(did, f"{keys[0]} is linked to {pid} ({p['as']})", holds,
                   dict(self._mention_deps(mem), c={str(pk), str(spk("cited_works", k0))}))
        return dict(how=f"{k} ({how}) -> {pid} as {p['as']}")

    def relation_row(self, did, d, pk, rel, inv, obj_pub=None, obj_pk=None, why=None):
        have = self.x("""SELECT relation_pk FROM work_relations WHERE subject_cited_work_pk = ? AND relation = ? AND
                         object_pub_id IS ? AND object_cited_work_pk IS ?""", (pk, rel, obj_pub, obj_pk)).fetchone()
        if have:
            return have[0], False
        rpk = spk("work_relations", did)
        self.x("""INSERT INTO work_relations (relation_pk, subject_cited_work_pk, relation, inverse, object_pub_id,
                  object_cited_work_pk, score, method, evidence, asserted_by, link_run_id)
                  VALUES (?, ?, ?, ?, ?, ?, 1.0, 'person', ?, 'person', NULL)""",
               (rpk, pk, rel, inv, obj_pub, obj_pk, json.dumps(dict(desk_decision=did, actor=d["actor_id"], why=why),
                                                               ensure_ascii=False, sort_keys=True)))
        return rpk, True

    def has_relation(self, ca: set, cb_or_pub, rel: str, pub: bool) -> bool:
        for c in ca:
            pk = self.card_pk(c)
            if pub:
                ok = self.x("SELECT 1 FROM work_relations WHERE subject_cited_work_pk = ? AND relation = ? AND "
                            "object_pub_id = ?", (pk, rel, cb_or_pub)).fetchone()
            else:
                ok = any(self.x("SELECT 1 FROM work_relations WHERE subject_cited_work_pk = ? AND relation = ? AND "
                                "object_cited_work_pk = ?", (pk, rel, self.card_pk(o))).fetchone() for o in cb_or_pub)
            if not ok:
                return False
        return bool(ca)

    def op_relate_works(self, d, keys, p, ev, did):
        """Two works, related (D42 a chapter part of its book; D43 an article derived from a thesis): a
        work_relations row, and the two kept apart."""
        mem = ev.get("members", {})
        ma, mb = mem.get(keys[0]) or [], mem.get(keys[1]) or []
        k1 = self.R.resolve_work(key_value(keys[0]), members=ma)[0]
        k2 = self.R.resolve_work(key_value(keys[1]), members=mb)[0]
        if not k1 or not k2:
            raise Orphan(f"{keys[0] if not k1 else keys[1]} is not in the reading")
        if k1 == k2:
            raise Conflict(f"cannot hold: {keys[0]} and {keys[1]} are one card ({k1}) in this release")
        rel, inv = WORK_RELATIONS[p["relation"]]
        self.patch(d)
        pk1, pk2 = self.card_pk(k1), self.card_pk(k2)
        _, new = self.relation_row(did, d, pk1, rel, inv, obj_pk=pk2, why=p.get("why"))

        def holds():
            ca, cb = self.side_cards(keys[0], ma), self.side_cards(keys[1], mb)
            return bool(ca and cb) and not (ca & cb) and self.has_relation(ca, cb, rel, False)
        self.holds(did, f"{keys[0]} {rel} {keys[1]}, two works", holds,
                   dict(self._mention_deps(ma + mb), c={str(pk1), str(pk2)}))
        return dict(how=f"{k1} {rel} {k2}" + ("" if new else " (the relation was there)"))

    def op_relate_publication(self, d, keys, p, ev, did):
        """The Mandumah publication is related to the cited work and is not the work (a review of it, the article
        drawn from a thesis …): a work_relations row; an accepted link of the card to that publication is rejected
        (`unlink`, the default), so the index does not count it as held."""
        mem = ev.get("members", {}).get(keys[0]) or []
        k, how = self.R.resolve_work(key_value(keys[0]), members=mem)
        if not k:
            raise Orphan(f"{keys[0]} is not in the reading")
        pid = self.ensure_pub(keys[1], p)
        rel, inv = WORK_RELATIONS[p["relation"]]
        self.patch(d)
        pk = self.card_pk(k)
        _, new = self.relation_row(did, d, pk, rel, inv, obj_pub=pid, why=p.get("why"))
        n = 0
        if p.get("unlink", True):
            n = self.x("""UPDATE citation_links SET status = 'rejected', best = 0, asserted_by = 'person', evidence = ?
                          WHERE cited_work_pk = ? AND target_kind = 'publication' AND target_pub_id = ? AND
                          status = 'accepted'""", (json.dumps(dict(desk_decision=did, why="related, not the work"),
                                                                sort_keys=True), pk, pid)).rowcount

        def holds():
            cs = self.side_cards(keys[0], mem)
            if not self.has_relation(cs, pid, rel, True):
                return False
            return not p.get("unlink", True) or not any(self.x(
                "SELECT 1 FROM citation_links WHERE cited_work_pk = ? AND target_pub_id = ? AND status = 'accepted'",
                (self.card_pk(c), pid)).fetchone() for c in cs)
        self.holds(did, f"{keys[0]} {rel} {pid}, not linked as the work", holds,
                   dict(self._mention_deps(mem), c={str(pk)}))
        return dict(how=f"{k} {rel} {pid}" + ("" if new else " (the relation was there)")
                    + (f"; {n} accepted link(s) to it rejected" if n else ""))

# ------------------------------------------------------------------ measuring a release
def counts(con) -> dict:
    q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    # experiment 68: an affiliation printed again in the other script (twin_of_aff_pk) is not counted twice
    tw = (" AND am.twin_of_aff_pk IS NULL" if "twin_of_aff_pk" in
          {r[1] for r in con.execute("PRAGMA table_info(affiliation_mentions)").fetchall()} else "")
    return dict(
        cited_works_active=q("SELECT count(*) FROM cited_works WHERE status = 'active'"),
        cited_works_merged=q("SELECT count(*) FROM cited_works WHERE status = 'merged'"),
        cited_work_members=q("SELECT count(*) FROM cited_work_members"),
        cross_article_cards=q("SELECT count(*) FROM v_times_cited WHERE n_citing_pubs > 1"),
        merged_ids=q("SELECT count(*) FROM merged_ids"),
        persons_live=q("SELECT count(*) FROM persons WHERE status <> 'merged'"),
        persons_merged=q("SELECT count(*) FROM persons WHERE status = 'merged'"),
        authorships=q("SELECT count(*) FROM authorships"),
        authorship_mentions=q("SELECT count(*) FROM authorship_mentions"),
        backrefs_resolved=q("""SELECT count(*) FROM citation_mentions m JOIN versions v USING (version_id)
                               WHERE v.is_current = 1 AND m.kind IN ('ibid','op_cit','loc_cit')
                               AND m.full_mention_pk IS NOT NULL"""),
        person_patches=q("SELECT count(*) FROM patches WHERE source = 'person'"),
        # institutions (experiment 64): what the index counts (organisation-level links of the shown versions)
        institutions_active=q("SELECT count(*) FROM institutions WHERE status = 'active'"),
        institutions_merged=q("SELECT count(*) FROM institutions WHERE status = 'merged'"),
        institutions_linked_org=q(f"SELECT count(DISTINCT l.inst_id) FROM affiliation_links l {_CUR_AFF} "
                                  "WHERE l.level = 'org'" + tw),
        institutions_linked_org_with_country=q(f"""SELECT count(DISTINCT l.inst_id) FROM affiliation_links l
                                                   {_CUR_AFF} JOIN institutions i ON i.inst_id = l.inst_id
                                                   WHERE l.level = 'org' AND i.country_code IS NOT NULL""" + tw),
        affiliations_linked_org=q(f"SELECT count(DISTINCT l.aff_pk) FROM affiliation_links l {_CUR_AFF} "
                                  "WHERE l.level = 'org'" + tw),
        affiliation_links_former=q("SELECT count(*) FROM affiliation_links WHERE level = 'former'"),
        affiliation_links_educated_at=q("SELECT count(*) FROM affiliation_links WHERE level = 'educated_at'"),
        affiliation_links=q("SELECT count(*) FROM affiliation_links"),
        # cited works (experiment 67): what the index counts, and what people decided
        cited_works_cited=q("SELECT count(DISTINCT cited_work_pk) FROM v_mention_work WHERE cited_work_pk IS NOT NULL"),
        cited_works_not_a_work=q("SELECT count(*) FROM cited_works WHERE status = 'not-a-work'"),
        references=q("SELECT count(*) FROM v_mention_work"),
        references_held=q("""SELECT count(*) FROM v_mention_work mw JOIN citation_links l ON l.cited_work_pk =
                             mw.cited_work_pk AND l.status = 'accepted' AND l.best = 1 AND l.target_kind = 'publication'"""),
        citation_links_best=q("SELECT count(*) FROM citation_links WHERE status = 'accepted' AND best = 1"),
        citation_links_person=q("SELECT count(*) FROM citation_links WHERE asserted_by = 'person'"),
        work_relations=q("SELECT count(*) FROM work_relations"),
        work_relations_person=q("SELECT count(*) FROM work_relations WHERE asserted_by = 'person'"),
        cited_work_editions=q("SELECT count(*) FROM cited_work_editions"),
        publications=q("SELECT count(*) FROM publications"),
    )


_CUR_AFF = """JOIN affiliation_mentions am ON am.aff_pk = l.aff_pk JOIN byline_mentions b ON b.mention_pk = am.mention_pk
              JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1"""


def fingerprint(con) -> tuple[str, dict]:
    per = {}
    for t in FINGERPRINT_TABLES:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        h = hashlib.sha256()
        for r in con.execute(f"SELECT * FROM {t} ORDER BY {', '.join(str(i + 1) for i in range(len(cols)))}"):
            h.update(repr(tuple(r)).encode("utf-8"))
        per[t] = h.hexdigest()[:16]
    h = hashlib.sha256()
    for r in con.execute(f"SELECT {MENTION_COLS} FROM citation_mentions ORDER BY mention_pk"):
        h.update(repr(tuple(r)).encode("utf-8"))
    per["citation_mentions(resolution)"] = h.hexdigest()[:16]
    return hashlib.sha256(json.dumps(per, sort_keys=True).encode()).hexdigest(), per


def reading_sig(path: Path) -> dict:
    out = {}
    for suf in ("", "-wal"):
        p = Path(str(path) + suf)
        if p.exists():
            st = p.stat()
            out[p.name] = dict(size=st.st_size, mtime=int(st.st_mtime))
    return out


def copy_reading(src: Path, dst: Path) -> None:
    """SQLite backup API, from a read-only connection: consistent even while the reading has a WAL."""
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(dst)
    try:
        s.backup(d, pages=-1)         # one step: ~3 s for 570 MB (stepwise with its sleeps took 150 s)
        d.execute("PRAGMA journal_mode=DELETE")
    finally:
        d.close()
        s.close()


def new_release_id(pg) -> str:
    base = "R" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    rid, n = base, 1
    while pg.execute("SELECT 1 FROM releases WHERE release_id = %s", (rid,)).fetchone():
        n += 1
        rid = f"{base}-{n}"
    return rid


PHASE_ORDER = {"page": 1, "metadata": 2}


def phase(d) -> int:
    if d["op"] in OPS and OPS[d["op"]][1]:
        return OPS[d["op"]][1]
    return PHASE_ORDER.get(d["domain"], 0) if d["op"] not in ("revert", "retire") else 0


def build_release(pg, reading: Path | str | None = None, out_dir: Path | str | None = None, *, keep: int = 2,
                  built_by: str = "agent:desk-release", note: str | None = None, is_demo: bool = False,
                  release_id: str | None = None) -> dict:
    """Build one release. Commits its own work in the Desk database."""
    t0 = time.time()
    reading = Path(reading or db.reading_path())
    out_dir = Path(out_dir or db.releases_dir())
    out_dir.mkdir(parents=True, exist_ok=True)
    pg.execute("INSERT INTO actors (actor_id, kind, name) VALUES (%s, 'agent', 'the release step') "
               "ON CONFLICT DO NOTHING", (built_by,))
    rid = release_id or new_release_id(pg)
    final = out_dir / f"{rid}.db"
    tmp = out_dir / f"{rid}.db.building"
    pg.execute("INSERT INTO releases (release_id, reading_path, reading_sig, status, built_by, note, is_demo) "
               "VALUES (%s, %s, %s, 'building', %s, %s, %s)",
               (rid, str(reading), Jsonb(reading_sig(reading)), built_by, note, is_demo))
    pg.commit()
    timings = {}
    try:
        copy_reading(reading, tmp)
        timings["copy_s"] = round(time.time() - t0, 1)
        con = sqlite3.connect(tmp)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=OFF")        # as platform v2: declared, checked after the build
        before = counts(con)
        fk_before = len(con.execute("PRAGMA foreign_key_check").fetchall())
        timings["counts_before_s"] = round(time.time() - t0, 1)
        B = Builder(con, rid)
        decs = pg.execute("SELECT * FROM decisions WHERE status IN ('accepted', 'superseded') ORDER BY seq").fetchall()
        peers = defaultdict(set)              # experiment 68: aff keys by (article, recorded printed text)
        for d in decs:
            for k in d["subject_keys"]:
                if k.startswith("aff:") and d["status"] == "accepted" and (d["evidence"] or {}).get("printed"):
                    peers[(key_value(k).split("|")[0], d["evidence"]["printed"])].add(key_value(k))
        B.aff_peers = {k: sorted(v, key=lambda x: (int(x.split("|")[1][1:]), int(x.split("|")[3][1:])))
                       for k, v in peers.items()}
        decs = sorted(decs, key=lambda d: (phase(d), d["seq"]))
        apps = []
        for i, d in enumerate(decs):
            if d["status"] == "superseded":
                res = dict(status="superseded", by=str(d["superseded_by"]))
                B.patch(d)
                B.patch_application(d, "overridden", f"superseded by {d['superseded_by']}")
            else:
                res = B.apply(dict(d))
            apps.append((d, i + 1, res))
        timings["twins_inherited"] = B.inherit_twins()      # experiment 68
        # every applied decision, re-checked on the final state
        failing = B.broken(full=True)
        timings["apply_s"] = round(time.time() - t0, 1)
        timings["constraint_checks"] = getattr(B, "checked", 0)
        after = counts(con)
        con.commit()
        fk_after = len(con.execute("PRAGMA foreign_key_check").fetchall())
        fp, per = fingerprint(con)
        timings["checks_s"] = round(time.time() - t0, 1)
        con.close()
        os.replace(tmp, final)
        st = Counter(r["status"] for _, _, r in apps)
        for d, ordn, res in apps:
            pg.execute("INSERT INTO applications (release_id, decision_id, ord, status, detail) VALUES (%s,%s,%s,%s,%s)",
                       (rid, d["decision_id"], ordn, res["status"], Jsonb({k: v for k, v in res.items()
                                                                            if k != "status"})))
            for k in d["subject_keys"]:
                ensure_subject(pg, k, release=rid)
            if res["status"] == "orphaned":
                pg.execute("UPDATE subjects SET status = 'orphaned', updated_at = now() WHERE subject_key = ANY(%s)",
                           (list(d["subject_keys"]),))
                add_task(pg, "orphaned_decision", d["subject_keys"], about=d["decision_id"], reserved_for=d["actor_id"],
                         question="This decision's keys are gone from the new reading. Re-anchor it (answer with the "
                                  "same operation on the new keys) or retire it.",
                         candidates=[dict(decision=str(d["decision_id"]), op=d["op"], subject_keys=d["subject_keys"],
                                          payload=d["payload"], evidence=d["evidence"], why=res["why"])],
                         impact=5, uncertainty=1.0, source=dict(detector="release", release=rid),
                         release=rid, is_demo=d["is_demo"], check_standing=False)
            elif res["status"] == "conflict":
                # two people's decisions disagree: the earlier one holds; both owners get a note, the later one a task
                others = res.get("with_decisions") or []
                text = (f"Release {rid}: this decision ({d['op']}) could not be applied: {res['why']}. "
                        f"It disagrees with decision(s) {', '.join(others) or '(its own constraints)'}; the earlier "
                        f"one holds. Talk it over and let the owner supersede or revert one of them.")
                add_note(pg, built_by, d["subject_keys"][0], text, d["decision_id"], is_demo=d["is_demo"])
                for o in others:
                    od = pg.execute("SELECT subject_keys FROM decisions WHERE decision_id = %s", (o,)).fetchone()
                    if od and o != str(d["decision_id"]):
                        add_note(pg, built_by, od["subject_keys"][0],
                                 f"Release {rid}: decision {d['decision_id']} by {d['actor_id']} disagrees with this "
                                 f"one and was not applied; this one holds. {res['why']}", o, is_demo=d["is_demo"])
                add_task(pg, "conflict", d["subject_keys"], about=d["decision_id"], reserved_for=d["actor_id"],
                         question="Your decision disagrees with an earlier one and was not applied. Read the notes, "
                                  "then supersede or retire yours (or ask the other owner to change theirs).",
                         candidates=[dict(decision=str(d["decision_id"]), op=d["op"], why=res["why"],
                                          with_decisions=others)],
                         impact=5, uncertainty=1.0, source=dict(detector="release", release=rid),
                         release=rid, is_demo=d["is_demo"], check_standing=False)
            elif res["status"] == "applied":
                pg.execute("UPDATE subjects SET status = 'live', updated_at = now() WHERE subject_key = ANY(%s) "
                           "AND status = 'orphaned'", (list(d["subject_keys"]),))
        checks = dict(foreign_key_violations_before=fk_before, foreign_key_violations_after=fk_after,
                      fk_ok=fk_after <= fk_before, decisions_hold=len(failing) == 0,
                      failing=[dict(decision=x, what=w) for x, w in failing], tables=per,
                      count_changes={k: after[k] - before[k] for k in after if after[k] != before[k]})
        timings["total_s"] = round(time.time() - t0, 1)
        timings["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
        pg.execute("""UPDATE releases SET path = %s, status = 'built', n_decisions = %s, n_applied = %s,
                      n_superseded = %s, n_orphaned = %s, n_conflict = %s, counts_before = %s, counts_after = %s,
                      checks = %s, fingerprint = %s, timings = %s, finished_at = now() WHERE release_id = %s""",
                   (str(final), len(apps), st["applied"], st["superseded"], st["orphaned"], st["conflict"],
                    Jsonb(before), Jsonb(after), Jsonb(checks), fp, Jsonb(timings), rid))
        pg.commit()
    except Exception:
        pg.rollback()
        pg.execute("UPDATE releases SET status = 'failed', finished_at = now() WHERE release_id = %s", (rid,))
        pg.commit()
        for p in (tmp, Path(str(tmp) + "-journal")):
            if p.exists():
                p.unlink()
        raise
    prune(pg, out_dir, keep)
    return dict(pg.execute("SELECT * FROM releases WHERE release_id = %s", (rid,)).fetchone())


def prune(pg, out_dir: Path, keep: int) -> list[str]:
    """Keep the newest `keep` release copies; delete older copies this tool wrote (registered, in out_dir, named
    R<stamp>.db). Nothing else is ever deleted."""
    rows = pg.execute("SELECT release_id, path FROM releases WHERE status = 'built' AND copy_deleted_at IS NULL "
                      "AND path IS NOT NULL ORDER BY finished_at DESC").fetchall()
    gone = []
    for r in rows[keep:]:
        p = Path(r["path"])
        if p.parent.resolve() == out_dir.resolve() and RELEASE_FILE.fullmatch(p.name) and p.exists():
            p.unlink()
            gone.append(str(p))
        if p.parent.resolve() == out_dir.resolve():
            pg.execute("UPDATE releases SET copy_deleted_at = now() WHERE release_id = %s", (r["release_id"],))
    pg.commit()
    return gone


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reading", help="platform v2 database to build on (default platform_v2.db, read-only)")
    ap.add_argument("--out", help="folder for release copies (default /home/appuser/data/desk/releases)")
    ap.add_argument("--keep", type=int, default=2)
    ap.add_argument("--note")
    a = ap.parse_args(argv)
    with db.connect() as pg:
        r = build_release(pg, a.reading, a.out, keep=a.keep, note=a.note)
    print(json.dumps({k: (str(v) if not isinstance(v, (int, float, dict, list, type(None))) else v)
                      for k, v in r.items()}, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
