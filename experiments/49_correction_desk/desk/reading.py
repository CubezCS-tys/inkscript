"""What the Desk needs to know about a platform v2 database (the machine's reading, or a release built on it).

Only the shown versions (`versions.is_current = 1`) count. Everything is looked up by stable key; a key the database
no longer holds is followed through `merged_ids`, then (for a card) through the members the decision recorded.
The same class reads a release copy while it is being written (release.py passes a read-write connection)."""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter

from .keys import split_key

CURRENT_MENTION = """SELECT m.mention_pk, m.mention_id, m.version_id, m.kind, m.printed, m.parsed, m.full_mention_pk,
       m.reading_ord, m.container_id, m.page, m.resolve_method, m.resolve_score, m.unresolved_why, m.resolved_by,
       v.stem, d.pub_id, a.anchor_key
FROM citation_mentions m JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
JOIN documents d ON d.stem = v.stem LEFT JOIN ink_anchors a ON a.anchor_pk = m.anchor_pk"""

BYLINE_KEY = "coalesce(i.anchor_key, v.stem || '|' || coalesce(b.block_id, '') || '|' || b.byline_pos || '|' || " \
             "coalesce(b.script, ''))"


class Reading:
    def __init__(self, con: sqlite3.Connection):
        self.con = con
        con.row_factory = sqlite3.Row
        self._bylines = None

    def q(self, sql, args=()):
        return self.con.execute(sql, args).fetchall()

    def q1(self, sql, args=()):
        return self.con.execute(sql, args).fetchone()

    # ------------------------------------------------------------------ citation mentions
    def mention(self, mention_id: str):
        return self.q1(CURRENT_MENTION + " WHERE m.mention_id = ?", (mention_id,))

    def mention_by_pk(self, pk: int):
        return self.q1(CURRENT_MENTION + " WHERE m.mention_pk = ?", (pk,))

    # ------------------------------------------------------------------ cited-work cards
    def card(self, cid: str):
        return self.q1("SELECT * FROM cited_works WHERE cited_work_id = ?", (cid,))

    def live_card(self, cid: str) -> bool:
        c = self.card(cid)
        return bool(c and c["status"] == "active")

    def card_members(self, cid: str) -> list[str]:
        return [r[0] for r in self.q(
            """SELECT m.mention_id FROM cited_work_members cm JOIN cited_works w ON w.cited_work_pk = cm.cited_work_pk
               JOIN citation_mentions m ON m.mention_pk = cm.full_mention_pk
               JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
               WHERE w.cited_work_id = ? ORDER BY m.mention_id""", (cid,))]

    def card_of_mention(self, mention_id: str) -> str | None:
        r = self.q1("""SELECT w.cited_work_id FROM citation_mentions m
                       JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
                       JOIN cited_work_members cm ON cm.full_mention_pk = m.mention_pk
                       JOIN cited_works w ON w.cited_work_pk = cm.cited_work_pk WHERE m.mention_id = ?""", (mention_id,))
        return r[0] if r else None

    def merged_into(self, old_id: str) -> str | None:
        """Follow merged_ids old -> new to the end of the chain."""
        seen, cur = set(), old_id
        while True:
            r = self.q1("SELECT new_id FROM merged_ids WHERE old_id = ? AND relation = 'merged-into'", (cur,))
            if not r or r[0] in seen:
                return cur if cur != old_id else None
            seen.add(cur)
            cur = r[0]

    def resolve_work(self, cid: str, members: list[str] | None = None) -> tuple[str | None, str]:
        """Where a card id stands now: itself; the card merged_ids says it went into; else the card that holds most
        of the members the decision saw (link47's own rule for a card whose key moved)."""
        if self.live_card(cid):
            return cid, "live"
        t = self.merged_into(cid)
        if t and self.live_card(t):
            return t, "merged_ids"
        if members:
            votes = Counter(c for c in (self.card_of_mention(m) for m in members) if c)
            if votes:
                return sorted(votes.items(), key=lambda x: (-x[1], x[0]))[0][0], "members"
        return None, "vanished"

    def card_info(self, cid: str) -> dict | None:
        c = self.card(cid)
        if not c:
            return None
        tc = self.q1("SELECT n_citing_pubs, n_mentions FROM v_times_cited WHERE cited_work_pk = ?", (c["cited_work_pk"],))
        authors = [r[0] for r in self.q("SELECT printed FROM cited_work_authors WHERE cited_work_pk = ? ORDER BY seq",
                                        (c["cited_work_pk"],))]
        return dict(id=cid, status=c["status"], title=c["title"], pub_type=c["pub_type"], authors=authors,
                    year=c["year_printed"], members=self.card_members(cid),
                    n_citing_pubs=tc[0] if tc else 0, n_mentions=tc[1] if tc else 0)

    def member_rows(self, cid: str) -> list[dict]:
        """Each member with what a person needs to see: the printed citation, its article, its ink anchor."""
        rows = self.q(CURRENT_MENTION + """ JOIN cited_work_members cm ON cm.full_mention_pk = m.mention_pk
                      JOIN cited_works w ON w.cited_work_pk = cm.cited_work_pk WHERE w.cited_work_id = ?
                      ORDER BY m.mention_id""", (cid,))
        out = []
        for r in rows:
            p = json.loads(r["parsed"]) if r["parsed"] else {}
            out.append(dict(mention=f"mention:{r['mention_id']}", stem=r["stem"], printed=r["printed"],
                            authors=[" ".join(x for x in (a[1], a[0]) if x) for a in (p.get("authors") or [])],
                            anchor=r["anchor_key"], parsed=p))
        return out

    # ------------------------------------------------------------------ persons and bylines
    def person(self, pid: str):
        return self.q1("SELECT * FROM persons WHERE person_id = ?", (pid,))

    def resolve_person(self, pid: str) -> tuple[str | None, str]:
        p = self.person(pid)
        if p and p["status"] != "merged":
            return pid, "live"
        t = self.merged_into(pid)
        if t:
            q = self.person(t)
            if q and q["status"] != "merged":
                return t, "merged_ids"
        return None, "vanished"

    def bylines(self) -> dict:
        """byline key -> byline mention pk (shown versions). Bylines are not changed by a build, so this is cached."""
        if self._bylines is None:
            self._bylines = {r[0]: r[1] for r in self.q(
                f"""SELECT {BYLINE_KEY}, b.mention_pk FROM byline_mentions b
                    JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1
                    LEFT JOIN ink_anchors i ON i.anchor_pk = b.anchor_pk""")}
        return self._bylines

    def byline(self, key: str) -> dict | None:
        """A byline mention and the authorship it belongs to."""
        pk = self.bylines().get(key)
        if pk is None:
            return None
        r = self.q1("""SELECT b.mention_pk, b.printed, b.name_text, b.script, a.authorship_pk, a.pub_id, a.position,
                              a.role_code, a.person_id, a.c999, a.catalogue_seq, a.method
                       FROM byline_mentions b LEFT JOIN authorship_mentions am ON am.mention_pk = b.mention_pk
                       LEFT JOIN authorships a ON a.authorship_pk = am.authorship_pk
                       WHERE b.mention_pk = ?""", (pk,))
        return dict(r) if r else None

    def authorship_ref(self, authorship_pk: int) -> str:
        """A stable reference to an authorship: its byline's ink, else its catalogue contributor row."""
        keys = {pk: k for k, pk in self.bylines().items()}
        ms = sorted(keys[r[0]] for r in self.q("SELECT mention_pk FROM authorship_mentions WHERE authorship_pk = ?",
                                               (authorship_pk,)) if r[0] in keys)
        if ms:
            return f"byline:{ms[0]}"
        a = self.q1("SELECT pub_id, position, role_code, c999, catalogue_seq FROM authorships WHERE authorship_pk = ?",
                    (authorship_pk,))
        if a["c999"] is not None and a["catalogue_seq"] is not None:
            return f"catseq:{a['c999']}|{a['catalogue_seq']}"
        return f"pos:{a['pub_id']}|{a['position']}|{a['role_code']}"

    def authorship_by_ref(self, ref: str):
        kind, _, val = ref.partition(":")
        if kind == "byline":
            b = self.byline(val)
            return self.q1("SELECT * FROM authorships WHERE authorship_pk = ?", (b["authorship_pk"],)) \
                if b and b["authorship_pk"] else None
        if kind == "catseq":
            c999, seq = val.rsplit("|", 1)
            return self.q1("SELECT * FROM authorships WHERE c999 = ? AND catalogue_seq = ?", (c999, int(seq)))
        if kind == "pos":
            pub, pos, role = val.split("|")
            return self.q1("SELECT * FROM authorships WHERE pub_id = ? AND position = ? AND role_code = ?",
                           (pub, int(pos), role))
        return None

    def authorships_of(self, pid: str):
        return self.q("SELECT * FROM authorships WHERE person_id = ? ORDER BY pub_id, position", (pid,))

    def n_works(self, pid: str) -> int:
        return self.q1("SELECT count(DISTINCT pub_id) FROM authorships WHERE person_id = ?", (pid,))[0]

    def person_info(self, pid: str) -> dict | None:
        p = self.person(pid)
        if not p:
            return None
        names = [dict(r) for r in self.q("SELECT full_form, script, form_type FROM person_names WHERE person_id = ? "
                                         "ORDER BY form_type, full_form", (pid,))]
        auth = [r[0] for r in self.q("SELECT authority_id FROM person_authorities WHERE person_id = ? ORDER BY 1",
                                     (pid,))]
        return dict(id=pid, status=p["status"], name_ar=p["preferred_name_ar"], name_lat=p["preferred_name_lat"],
                    source=p["source"], authorities=auth, names=names,
                    authorships=[dict(ref=self.authorship_ref(a["authorship_pk"]), pub_id=a["pub_id"],
                                      position=a["position"], role=a["role_code"], method=a["method"])
                                 for a in self.authorships_of(pid)])

    # ------------------------------------------------------------------ institutions and printed affiliations
    def aff(self, key: str) -> dict | None:
        """A printed affiliation by its key 'stem|b<pos>|<script>|a<seq>' (shown versions only)."""
        stem, b, scr, a = key.split("|")
        r = self.q1("""SELECT am.aff_pk, am.printed, am.country_code, am.mention_pk, v.stem, v.version_id, d.pub_id,
                              p.journal_id
                       FROM affiliation_mentions am JOIN byline_mentions bm ON bm.mention_pk = am.mention_pk
                       JOIN versions v ON v.version_id = bm.version_id AND v.is_current = 1
                       JOIN documents d ON d.stem = v.stem LEFT JOIN publications p ON p.pub_id = d.pub_id
                       WHERE v.stem = ? AND bm.byline_pos = ? AND bm.script = ? AND am.seq = ?""",
                    (stem, int(b[1:]), scr, int(a[1:])))
        return dict(r) if r else None

    def aff_moved_twin(self, key: str, printed: str | None) -> dict | None:
        """Experiment 68: a key made before experiment 65 may name an affiliation printed in the other script that
        then sat under the main name ('stem|b0|Arab|a2' = an English line); since experiment 65 it hangs on the twin's
        own mention (byline_mentions.twin_of_pk, affiliation_mentions.twin_of_aff_pk). Found again by the decision's
        recorded printed text, among the twin rows of the same byline: exactly one match, else None."""
        if not printed:
            return None
        cols = {r[1] for r in self.q("PRAGMA table_info(affiliation_mentions)")}
        if "twin_of_aff_pk" not in cols:
            return None
        stem, b, scr, a = key.split("|")
        rows = self.q("""SELECT am.aff_pk, am.printed, am.country_code, am.mention_pk, v.stem, v.version_id, d.pub_id,
                                p.journal_id
                         FROM affiliation_mentions am JOIN byline_mentions bm ON bm.mention_pk = am.mention_pk
                         JOIN byline_mentions mm ON mm.mention_pk = bm.twin_of_pk
                         JOIN versions v ON v.version_id = bm.version_id AND v.is_current = 1
                         JOIN documents d ON d.stem = v.stem LEFT JOIN publications p ON p.pub_id = d.pub_id
                         WHERE v.stem = ? AND mm.byline_pos = ? AND mm.script = ? AND am.twin_of_aff_pk IS NOT NULL""",
                      (stem, int(b[1:]), scr))
        same = [r for r in rows if r["printed"] == printed]
        if len(same) == 1:
            return dict(same[0], moved_from=key, moved_by="text")
        # experiment 65 also rewrote the line as printed (the post kept, Latin commas): the twin row whose words
        # overlap the recorded text most, if it is clearly the one (half its words or more, and no tie)
        words = lambda t: set(re.findall(r"\w+", (t or "").lower()))  # noqa: E731
        w0 = words(printed)
        sc = sorted(((len(w0 & words(r["printed"])) / max(1, len(w0 | words(r["printed"]))), i)
                     for i, r in enumerate(rows)), reverse=True)
        if sc and sc[0][0] >= 0.5 and (len(sc) == 1 or sc[1][0] < sc[0][0]):
            return dict(rows[sc[0][1]], moved_from=key, moved_by=f"words {sc[0][0]:.2f}")
        return None

    def aff_by_text(self, key: str, printed: str | None, rank: int = 0) -> dict | None:
        """Experiment 68: a key whose byline moved (experiment 65 folds each Latin name into its Arabic twin, so the
        authors' order changes: 'b2|Arab' becomes 'b0|Arab'), or whose name lost its script, found again by the
        recorded printed text in the same article, among the main (not twin) rows; several rows with that text are
        taken in byline order, the key's rank among the decided keys with the same text choosing (`rank`)."""
        if not printed:
            return None
        stem = key.split("|")[0]
        rows = self.q("""SELECT am.aff_pk, am.printed, am.country_code, am.mention_pk, v.stem, v.version_id, d.pub_id,
                                p.journal_id
                         FROM affiliation_mentions am JOIN byline_mentions bm ON bm.mention_pk = am.mention_pk
                         JOIN versions v ON v.version_id = bm.version_id AND v.is_current = 1
                         JOIN documents d ON d.stem = v.stem LEFT JOIN publications p ON p.pub_id = d.pub_id
                         WHERE v.stem = ? AND am.printed = ? AND bm.twin_of_pk IS NULL
                         ORDER BY bm.byline_pos, am.seq""", (stem, printed))
        return dict(rows[rank], moved_from=key, moved_by="text in the article") if rank < len(rows) else None

    def aff_links(self, aff_pk: int) -> list[dict]:
        return [dict(r) for r in self.q("SELECT inst_id, level, method, asserted_by FROM affiliation_links "
                                         "WHERE aff_pk = ? ORDER BY level, inst_id", (aff_pk,))]

    def inst(self, iid: str):
        return self.q1("SELECT * FROM institutions WHERE inst_id = ?", (iid,))

    def resolve_inst(self, iid: str) -> tuple[str | None, str]:
        """An institution id, followed through merged_ids to the row that stands for it now."""
        r = self.inst(iid)
        if r and r["status"] != "merged":
            return iid, "live"
        t = self.merged_into(iid)
        if t:
            q = self.inst(t)
            if q and q["status"] != "merged":
                return t, "merged_ids"
        return None, "vanished"

    def inst_name(self, iid: str) -> str | None:
        r = self.q1("SELECT name FROM institution_names WHERE inst_id = ? ORDER BY (type = 'label') DESC, "
                    "(script = 'Arab') DESC, n_seen DESC LIMIT 1", (iid,))
        return r[0] if r else None

    def inst_info(self, iid: str) -> dict | None:
        r = self.inst(iid)
        if not r:
            return None
        d = dict(r)
        d["name"] = self.inst_name(iid)
        d["names"] = [dict(x) for x in self.q("SELECT name, lang, script, type, n_seen FROM institution_names "
                                               "WHERE inst_id = ? ORDER BY n_seen DESC, name", (iid,))]
        d["n_affiliations"] = self.q1("SELECT count(DISTINCT aff_pk) FROM affiliation_links WHERE inst_id = ?",
                                      (iid,))[0]
        return d

    # ------------------------------------------------------------------ Mandumah publications (experiment 67)
    def pub(self, pub_id: str):
        """A publication of the archive or the catalogue, following merged_ids."""
        r = self.q1("SELECT * FROM publications WHERE pub_id = ?", (pub_id,))
        if r:
            return r
        t = self.merged_into(pub_id)
        return self.q1("SELECT * FROM publications WHERE pub_id = ?", (t,)) if t else None

    def best_link(self, cid: str):
        """The accepted best link of a card (the one the index counts), or None."""
        return self.q1("""SELECT l.* FROM citation_links l JOIN cited_works w ON w.cited_work_pk = l.cited_work_pk
                          WHERE w.cited_work_id = ? AND l.status = 'accepted' AND l.best = 1""", (cid,))

    # ------------------------------------------------------------------ any key
    def exists(self, key: str) -> bool:
        kind, val = split_key(key)
        if kind == "work":
            return self.resolve_work(val)[0] is not None
        if kind == "person":
            return self.resolve_person(val)[0] is not None
        if kind == "mention":
            return self.mention(val) is not None
        if kind == "byline":
            return self.byline(val) is not None
        if kind == "authority":
            return self.q1("SELECT 1 FROM person_authorities WHERE authority_id = ?", (val,)) is not None
        if kind == "inst":
            return self.resolve_inst(val)[0] is not None
        if kind == "aff":
            return self.aff(val) is not None
        if kind == "pub":
            return self.pub(val) is not None
        return False

    def describe(self, key: str) -> dict | None:
        """The current state of a subject, for the API's subject page."""
        kind, val = split_key(key)
        if kind == "work":
            cid, how = self.resolve_work(val)
            if not cid:
                return None
            d = self.card_info(cid)
            d["resolved_from"] = None if how == "live" else val
            d["member_rows"] = self.member_rows(cid)
            return d
        if kind == "person":
            pid, how = self.resolve_person(val)
            if not pid:
                return None
            d = self.person_info(pid)
            d["resolved_from"] = None if how == "live" else val
            return d
        if kind == "mention":
            m = self.mention(val)
            if not m:
                return None
            d = {k: m[k] for k in m.keys() if k not in ("parsed",)}
            d["parsed"] = json.loads(m["parsed"]) if m["parsed"] else None
            d["card"] = self.card_of_mention(val)
            if m["full_mention_pk"] and m["full_mention_pk"] != m["mention_pk"]:
                t = self.mention_by_pk(m["full_mention_pk"])
                d["resolves_to"] = f"mention:{t['mention_id']}" if t else None
            return d
        if kind == "byline":
            return self.byline(val)
        if kind == "authority":
            r = self.q1("SELECT * FROM person_authorities WHERE authority_id = ?", (val,))
            return dict(r) if r else None
        if kind == "inst":
            iid, how = self.resolve_inst(val)
            if not iid:
                return None
            d = self.inst_info(iid)
            d["resolved_from"] = None if how == "live" else val
            return d
        if kind == "aff":
            a = self.aff(val)
            if a:
                a["links"] = self.aff_links(a["aff_pk"])
            return a
        if kind == "pub":
            r = self.pub(val)
            return dict(r) if r else None
        return None

    def label(self, key: str) -> str | None:
        try:
            d = self.describe(key)
        except ValueError:
            return None
        if not d:
            return None
        kind = key.split(":", 1)[0]
        if kind == "work":
            return d["title"]
        if kind == "person":
            return d["name_ar"] or d["name_lat"]
        if kind in ("mention", "byline", "aff"):
            return (d.get("printed") or "")[:200]
        if kind == "inst":
            return d.get("name")
        if kind == "pub":
            return d.get("title_shown")
        return None
