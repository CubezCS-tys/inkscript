"""The decision operations (DESIGN §4) and the review rules (DESIGN §7).

A decision is validated against the current state (the newest release on disk, else the machine's reading), given a
snapshot of what the person saw (`evidence`), and written once. It is never changed afterwards: only its status
moves, and a later decision can supersede it.

The review model (owner, 2026-10-21):
- **One key.** Every decision is accepted as soon as its corrector makes it. The rule stays a per-kind setting
  (`review_rules`, all `single`); no second-key flow is built.
- **Ownership.** A decision's owner is its actor. Only the owner, or an admin, can supersede or revert it; anyone
  else is refused with a message naming the owner.
- **Notes.** A corrector who disagrees leaves a note on the decision; its owner sees it under /me/notes.
- **Gold** is a quiet accuracy gauge for admins only; it never changes what happens to a decision.

Page and metadata operations wait for P2+. How page decisions map to platform v2's `patches` (so that patches43
applies them with no new code path), recorded here and not implemented:

    decision (domain 'page', op set_role | set_order | split_block | merge_blocks | mark_noise | unmark_noise |
              mark_other_article | fix_word | flag_misprint | set_cell | set_picture_box | link_note_call)
      -> patches row:  patch_key   = 'desk|<stem>|<decision_id>'   (run NULL: a person's patch holds for every run)
                       stem, patch_id = decision_id, domain = 'content', op = the patches43 op of the same name,
                       page        = the page of subject key 'line:<stem>|p<page>|l<n>',
                       targets     = the Azure 'P:N' line labels of the subject keys (json list),
                       payload     = decision.payload (the patches43 payload, unchanged), payload_copy = the same,
                       source      = 'person', priority = 1 (person > judge 2 > gemini-retry 3 > rule 4),
                       actor_id    = decision.actor_id, confidence = sure 1.0 | likely 0.75 | unsure 0.5,
                       evidence    = decision.evidence, reason = reason_code + note, apply = 1,
                       created     = decision.created_at
      -> patch_applications: written by load47 per version it builds (applied | skipped | overridden), copied
         into the Desk's `applications` by the release step.
    Metadata (D33): decision op set_field on 'pubfield:W<c999>|<field>' -> a metadata_assertions row with
    source 'person', the printed form kept beside it, and a patches row of domain 'metadata'.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from psycopg.types.json import Jsonb

from . import db
from .keys import (AFF_ROLES, INST_TYPES, LINK_AS, NOT_A_WORK_ACTIONS, OPS, WORK_RELATIONS, WORK_TYPES,
                   authority_inst_id, defined_work_id, key_kind, key_value, split_card_id, split_inst_id, split_key,
                   task_key, unlinked_person_id)
from .reading import Reading

SYMMETRIC = {"same_work", "not_same_work", "same_person", "not_same_person"}
WORK_EXTRA = {"edition_of", "not_a_work", "define_work", "link_publication", "relate_works", "relate_publication"}
BACKREF_KINDS = {"ibid", "op_cit", "loc_cit", "short"}
FAMILY = dict(split_work="card", same_work="card", not_same_work="card", confirm_work="card", move_member="card",
              set_work_type="work_type", same_person="person", not_same_person="person", link_byline="byline",
              unlink_byline="byline", resolve_backref="backref", unresolvable="backref",
              define_institution="inst_record", same_institution="inst_same", not_same_institution="inst_row",
              not_an_institution_row="inst_row", set_inst_country="inst_country", set_inst_parent="inst_parent",
              set_inst_type="inst_type", link_affiliation="affiliation", not_an_institution="affiliation",
              unit_kept_apart="affiliation",
              # experiment 67: a pair of cards has one answer (same work, edition of, not the same); a card's status as
              # a work, a card's link, a relation of two items each one answer
              edition_of="card", not_a_work="work_status", define_work="work_record", link_publication="pub_link",
              relate_works="work_relation", relate_publication="pub_relation")
# ops whose question is about their first key only (one standing answer per printed affiliation, one parent per unit)
KEYED_BY_FIRST = {"link_affiliation", "not_an_institution", "unit_kept_apart", "set_inst_parent",
                  "link_publication"}      # one Mandumah link per card
NAME_TYPES = {"label", "alias", "acronym", "printed"}
DETECTOR_KINDS = {"work_joined_without_author", "possible_same_work", "byline_twin"}


class OpError(ValueError):
    """The decision does not make sense against the current state; nothing was written."""


class NotOwner(OpError):
    """Someone else's decision: only its owner or an admin can change it."""


# ------------------------------------------------------------------ state
def open_state(pg, path: Path | None = None) -> Reading:
    return Reading(db.open_reading(path or db.state_path(pg)))


def pending_cards(pg) -> dict:
    """Cards minted by standing split decisions that no release holds yet: id -> members."""
    out = {}
    for r in pg.execute("SELECT op, subject_keys, payload FROM decisions WHERE op IN ('split_work', 'not_a_work', "
                        "'define_work') AND status IN ('proposed', 'accepted')"):
        if r["op"] == "define_work":
            out[key_value(r["subject_keys"][0])] = []
            continue
        for g in r["payload"].get("groups", [])[1:]:
            out[g["card_id"]] = g["members"]
    return out


def pending_moves(pg) -> dict:
    """Citations that standing decisions take off the card the state shows them on (experiment 67): mention id ->
    the card id they go to (a split's group, a move, one card per citation), or None (a card that is not a work:
    its citations name no work). In the order the decisions were made. A decision about a card then records the
    members it will have, not those the state still shows: a same_work on a card split since holds only the group
    that stays on it."""
    out = {}
    for r in pg.execute("SELECT op, subject_keys, payload FROM decisions WHERE op IN ('split_work', 'not_a_work', "
                        "'move_member') AND status IN ('proposed', 'accepted') ORDER BY seq"):
        p = r["payload"]
        if r["op"] == "move_member":
            out[key_value(r["subject_keys"][0])] = key_value(r["subject_keys"][1])
        elif r["op"] == "not_a_work" and p.get("action") == "drop":
            for m in p.get("members") or []:
                out[m] = None
        else:
            for g in p.get("groups") or []:
                for m in g.get("members") or []:
                    out[m] = g.get("card_id")
    return out


def pending_persons(pg) -> set:
    return {r["payload"]["new_person"] for r in pg.execute(
        "SELECT payload FROM decisions WHERE op = 'unlink_byline' AND status IN ('proposed', 'accepted')")}


def pending_insts(pg) -> set:
    """Institution rows that standing decisions make (a body's record, a split's groups) and no release holds yet."""
    out = set()
    for r in pg.execute("SELECT op, subject_keys, payload FROM decisions WHERE op IN ('define_institution', "
                        "'not_same_institution') AND status IN ('proposed', 'accepted')"):
        if r["op"] == "define_institution":
            out.add(key_value(r["subject_keys"][0]))
        else:
            out |= {g["row"] for g in r["payload"].get("groups", [])}
    return out


def standing(pg, keys) -> list[dict]:
    """Decisions that cover all of these keys and still stand (proposed or accepted). An undo (revert, retire) is
    not an answer: after it the machine's reading stands, and the question may be asked again."""
    return pg.execute("SELECT * FROM decisions WHERE subject_keys @> %s AND status IN ('proposed', 'accepted') "
                      "AND op NOT IN ('revert', 'retire') ORDER BY seq", (list(keys),)).fetchall()


# ------------------------------------------------------------------ validation, per operation
def _work(R: Reading, pend: dict, key: str, moves: dict | None = None) -> tuple[str, list[str]]:
    if key_kind(key) != "work":
        raise OpError(f"{key} is not a work key")
    cid, _ = R.resolve_work(key_value(key))
    if cid:
        members = R.card_members(cid)
        if moves:                       # what standing splits, moves and drops leave on it, and bring to it
            here = {cid, key_value(key)}
            kept = [m for m in members if moves.get(m, cid) in here]
            members = kept + sorted(m for m, c in moves.items() if c in here and m not in set(kept))
        return cid, members
    if key_value(key) in pend:
        members = list(pend[key_value(key)])
        if moves:
            members = [m for m in members if moves.get(m, key_value(key)) == key_value(key)] + sorted(
                m for m, c in moves.items() if c == key_value(key) and m not in set(members))
        return key_value(key), members
    raise OpError(f"{key}: no such card in the current state")


def _person(R: Reading, pend: set, key: str) -> str:
    if key_kind(key) != "person":
        raise OpError(f"{key} is not a person key")
    pid, _ = R.resolve_person(key_value(key))
    if pid:
        return pid
    if key_value(key) in pend:
        return key_value(key)
    raise OpError(f"{key}: no such person in the current state")


def _mention(R: Reading, key: str):
    if key_kind(key) != "mention":
        raise OpError(f"{key} is not a mention key")
    m = R.mention(key_value(key))
    if not m:
        raise OpError(f"{key}: no such citation mention in the shown versions")
    return m


def _mentions_of(keys_or_ids) -> list[str]:
    return [k.split(":", 1)[1] if k.startswith("mention:") else k for k in keys_or_ids]


def _inst(R: Reading, pend: set, key: str) -> str:
    if key_kind(key) != "inst":
        raise OpError(f"{key} is not an institution key")
    iid, _ = R.resolve_inst(key_value(key))
    if iid:
        return iid
    if key_value(key) in pend:
        return key_value(key)
    raise OpError(f"{key}: no such institution in the current state (nor one a standing decision makes)")


def _aff(R: Reading, key: str) -> dict:
    if key_kind(key) != "aff":
        raise OpError(f"{key} is not a printed-affiliation key")
    a = R.aff(key_value(key))
    if not a:
        raise OpError(f"{key}: no such printed affiliation in the shown versions")
    return a


def _country(c) -> str:
    if not isinstance(c, str) or not re.fullmatch(r"[A-Z]{2}", c):
        raise OpError(f"a country is a two-letter ISO code, got {c!r}")
    return c


def _inst_evidence(R: Reading, iid: str) -> dict:
    i = R.inst(iid)
    return dict(name=R.inst_name(iid), kind=i["kind"], country=i["country_code"], parent=i["parent_id"],
                status=i["status"]) if i else dict(new=True)


def _prepare_institution(pg, R: Reading, decision_id: str, op: str, keys: list[str], payload: dict) -> tuple[dict, int]:
    """Institution and printed-affiliation operations (experiment 64): validate and complete the payload."""
    pend = pending_insts(pg)
    ev: dict = {}
    impact = 1
    if op == "define_institution":
        iid = key_value(keys[0])
        exists = R.resolve_inst(iid)[0]
        auth = payload.get("authority")
        if not isinstance(auth, str) or not auth:
            raise OpError("define_institution needs payload.authority (the body's authority id)")
        if not exists and iid != authority_inst_id(auth):
            raise OpError(f"define_institution: a new body's id is minted from its authority id: "
                          f"inst:{authority_inst_id(auth)}, not {keys[0]}")
        if payload.get("kind") not in INST_TYPES:
            raise OpError(f"define_institution: kind must be one of {sorted(INST_TYPES)}")
        names = payload.get("names") or []
        if not names or not all(isinstance(n, dict) and isinstance(n.get("name"), str) and n["name"].strip()
                                and n.get("type", "label") in NAME_TYPES for n in names):
            raise OpError(f"define_institution: payload.names is a list of {{name, lang, script, type in "
                          f"{sorted(NAME_TYPES)}}}")
        payload["new"] = not exists
        ev["was"] = _inst_evidence(R, exists) if exists else dict(new=True)
    elif op == "same_institution":
        if len(set(keys)) != len(keys):
            raise OpError("same_institution: a row is listed twice")
        ids = [_inst(R, pend, k) for k in keys]
        if len(set(ids)) < 2:
            raise OpError("same_institution: these are already one institution")
        ev["rows"] = {k: _inst_evidence(R, i) for k, i in zip(keys, ids)}
    elif op == "not_same_institution":
        row = _inst(R, pend, keys[0])
        groups = payload.get("groups")
        if not isinstance(groups, list) or len(groups) < 2:
            raise OpError("not_same_institution needs payload.groups: at least two groups of affiliation keys")
        seen, out = set(), []
        for i, g in enumerate(groups):
            affs = g.get("affiliations") or []
            if not affs:
                raise OpError(f"not_same_institution: group {i} is empty")
            for a in affs:
                _aff(R, a)
                if a in seen:
                    raise OpError(f"not_same_institution: {a} is in two groups")
                seen.add(a)
            body = g.get("body")
            if body:
                _inst(R, pend, body)
            out.append(dict(label=g.get("label"), body=body, affiliations=sorted(affs),
                            row=row if i == 0 else split_inst_id(decision_id, i)))
        payload["groups"] = out
        payload["lumped_faculty"] = bool(payload.get("lumped_faculty"))
        ev["row"] = _inst_evidence(R, row)
        impact = len(seen)
    elif op == "not_an_institution_row":
        ev["row"] = _inst_evidence(R, _inst(R, pend, keys[0]))
    elif op == "set_inst_country":
        iid = _inst(R, pend, keys[0])
        payload["country"] = _country(payload.get("country"))
        ev["row"] = _inst_evidence(R, iid)
    elif op == "set_inst_parent":
        u, par = _inst(R, pend, keys[0]), _inst(R, pend, keys[1])
        if u == par:
            raise OpError("set_inst_parent: a body cannot be its own parent")
        ev["unit"], ev["parent"] = _inst_evidence(R, u), _inst_evidence(R, par)
    elif op == "set_inst_type":
        if payload.get("type") not in INST_TYPES:
            raise OpError(f"set_inst_type: type must be one of {sorted(INST_TYPES)}")
        ev["row"] = _inst_evidence(R, _inst(R, pend, keys[0]))
    else:                                           # link_affiliation | not_an_institution | unit_kept_apart
        a = _aff(R, keys[0])
        ev["printed"] = a["printed"]
        ev["links_were"] = R.aff_links(a["aff_pk"])
        ev["journal_id"] = a["journal_id"]
        if op == "link_affiliation":
            insts = payload.get("institutions") or []
            if [x.get("inst") for x in insts] != keys[1:]:
                raise OpError("link_affiliation: payload.institutions[].inst must list the institution keys in the "
                              "order of subject_keys[1:]")
            for x in insts:
                _inst(R, pend, x["inst"])
                x.setdefault("role", "current")
                if x["role"] not in AFF_ROLES:
                    raise OpError(f"link_affiliation: role must be one of {sorted(AFF_ROLES)}")
                if x.get("country") is not None:
                    _country(x["country"])
                inf = x.get("inferred")
                if inf is not None and (not isinstance(inf, dict) or inf.get("from") not in ("journal", "article")):
                    raise OpError("link_affiliation: inferred is {from: journal | article, why}")
            payload["institutions"] = insts
            impact = len(insts)
    return ev, impact


RECORD_FIELDS = ("c999", "rec", "title", "subtitle", "title_en", "type", "year", "year_int", "year_hijri", "language",
                 "journal", "journal_en", "journal_code", "volume", "issue", "pages", "page_first", "page_last",
                 "article_seq", "doi", "databases", "country", "publisher", "authors", "stems")


def _pub_target(R: Reading, key: str, payload: dict, op: str) -> dict:
    """The Mandumah publication a link or relation points at: in the state, or a catalogue record the decision carries
    (`payload.record`, read from the catalogue when the decision was made), which the release adds as a
    catalogued-only publication W<c999>, the way platform v2 adds its own link targets."""
    pid = key_value(key)
    p = R.pub(pid)
    rec = payload.get("record")
    if rec is not None:
        if not isinstance(rec, dict) or str(rec.get("c999") or "") != pid[1:] or not rec.get("title"):
            raise OpError(f"{op}: payload.record is the catalogue record of {key} ({{c999: {pid[1:]!r}, title, ...}})")
        payload["record"] = {k: rec.get(k) for k in RECORD_FIELDS if rec.get(k) is not None}
    if not p and rec is None:
        raise OpError(f"{op}: {key} is not a publication in the current state; give payload.record (its catalogue "
                      f"record) to add it")
    return dict(pub_id=p["pub_id"], title=p["title_shown"], status=p["status"]) if p else dict(new=True)


def _prepare_work_extra(pg, R: Reading, decision_id: str, op: str, keys: list[str], payload: dict) -> tuple[dict, int]:
    """Experiment 67's cited-work operations: validate and complete the payload."""
    pend = pending_cards(pg)
    mv = pending_moves(pg)
    ev: dict = {}
    impact = 1
    if op == "define_work":
        cid = key_value(keys[0])
        nat = payload.get("natural")
        if not isinstance(nat, str) or not nat.strip():
            raise OpError("define_work needs payload.natural (what makes the work itself: e.g. title|publisher|year)")
        if not R.resolve_work(cid)[0] and cid != defined_work_id(nat):
            raise OpError(f"define_work: a new work's id is minted from its natural key: work:{defined_work_id(nat)}, "
                          f"not {keys[0]}")
        if not (payload.get("title") or "").strip():
            raise OpError("define_work needs payload.title")
        payload.setdefault("pub_type", "book")
        if payload["pub_type"] not in WORK_TYPES | {"journal", "other", "confproc"}:
            raise OpError(f"define_work: pub_type must be one of {sorted(WORK_TYPES)}")
        payload["new"] = not R.resolve_work(cid)[0]
        return ev, impact
    cid, members = _work(R, pend, keys[0], mv)
    info = R.card_info(cid) if R.card(cid) else None
    ev["members"] = {keys[0]: members}
    ev["title"] = info["title"] if info else None
    impact = max(1, info["n_mentions"] if info else len(members))
    if op == "edition_of":
        c2, m2 = _work(R, pend, keys[1], mv)
        if keys[0] == keys[1]:
            raise OpError("edition_of: the two keys are the same")
        if c2 == cid:
            raise OpError("edition_of: these are already one card (record the edition on the members instead)")
        ev["members"][keys[1]] = m2
        ev["titles"] = {keys[0]: ev.pop("title"), keys[1]: (R.card(c2)["title"] if R.card(c2) else None)}
        for side in ("edition_a", "edition_b"):
            if payload.get(side) is not None and not isinstance(payload[side], str):
                raise OpError(f"edition_of: payload.{side} is the edition's label as text")
    elif op == "not_a_work":
        act = payload.get("action")
        if act not in NOT_A_WORK_ACTIONS:
            raise OpError(f"not_a_work: payload.action must be one of {sorted(NOT_A_WORK_ACTIONS)}")
        if not members:
            raise OpError(f"not_a_work: {keys[0]} has no citations")
        titles = payload.get("titles") or {}
        if not isinstance(titles, dict) or not all(isinstance(v, str) for v in titles.values()):
            raise OpError("not_a_work: payload.titles is {mention id: the work's title as printed}")
        if act == "retitle" and payload.get("title") is not None and not isinstance(payload["title"], str):
            raise OpError("not_a_work: payload.title is text")
        if act == "one_per_citation":
            if len(members) < 2:
                raise OpError("not_a_work: one_per_citation needs a card of two citations or more (use retitle)")
            ms = sorted(members)
            payload["groups"] = [dict(members=[m], card_id=key_value(keys[0]) if i == 0 else
                                      split_card_id(decision_id, i)) for i, m in enumerate(ms)]
        payload["members"] = sorted(members)
    elif op == "link_publication":
        if payload.get("as", "work") not in LINK_AS:
            raise OpError(f"link_publication: payload.as must be one of {sorted(LINK_AS)}")
        payload.setdefault("as", "work")
        ev["target"] = _pub_target(R, keys[1], payload, op)
        bl = R.best_link(cid) if R.card(cid) else None
        ev["best_link_was"] = bl["target_pub_id"] if bl else None
    elif op in ("relate_works", "relate_publication"):
        rel = payload.get("relation")
        if rel not in WORK_RELATIONS:
            raise OpError(f"{op}: payload.relation must be one of {sorted(WORK_RELATIONS)}")
        if op == "relate_works":
            c2, m2 = _work(R, pend, keys[1], mv)
            if keys[0] == keys[1] or c2 == cid:
                raise OpError("relate_works: a work is not related to itself (these are one card)")
            ev["members"][keys[1]] = m2
            ev["other_title"] = R.card(c2)["title"] if R.card(c2) else None
        else:
            ev["target"] = _pub_target(R, keys[1], payload, op)
            payload["unlink"] = bool(payload.get("unlink", True))
            bl = R.best_link(cid) if R.card(cid) else None
            ev["best_link_was"] = bl["target_pub_id"] if bl else None
    return ev, impact


def prepare(pg, R: Reading, decision_id: str, op: str, keys: list[str], payload: dict) -> tuple[list, dict, dict, int]:
    """Validate; return (keys, payload completed, evidence, impact)."""
    if op not in OPS or op in ("revert", "retire"):
        raise OpError(f"unknown operation {op!r}")
    _, _, n, kinds = OPS[op]
    if isinstance(n, str):                       # "2+" / "1+": at least that many, the rest of the last kind
        if len(keys) < int(n[0]):
            raise OpError(f"{op} takes {n} subject keys, got {len(keys)}")
        kinds = tuple(kinds) + (kinds[-1],) * max(0, len(keys) - len(kinds))
    elif len(keys) != n:
        raise OpError(f"{op} takes {n} subject key(s), got {len(keys)}")
    for k, kind in zip(keys, kinds):
        split_key(k)
        if key_kind(k) != kind:
            raise OpError(f"{op}: key {k} should be a {kind} key")
    if FAMILY.get(op, "").startswith("inst") or FAMILY.get(op) == "affiliation":
        payload = dict(payload or {})
        ev, impact = _prepare_institution(pg, R, decision_id, op, list(keys), payload)
        return list(keys), payload, ev, impact
    if op in WORK_EXTRA:
        payload = dict(payload or {})
        ev, impact = _prepare_work_extra(pg, R, decision_id, op, list(keys), payload)
        return list(keys), payload, ev, impact
    payload = dict(payload or {})
    pend_c, pend_p = pending_cards(pg), pending_persons(pg)
    mv = pending_moves(pg) if op in ("same_work", "not_same_work", "confirm_work", "set_work_type", "move_member") \
        else None
    ev: dict = {}
    impact = 1

    if op in ("split_work", "confirm_work", "set_work_type"):
        cid, members = _work(R, pend_c, keys[0], mv)
        ev["members"] = {keys[0]: members}
        ev["card_now"] = cid
        info = R.card_info(cid) if R.card(cid) else None
        ev["title"] = info["title"] if info else None
        impact = max(1, info["n_mentions"] if info else len(members))
        if op == "split_work":
            groups = payload.get("groups")
            if not isinstance(groups, list) or len(groups) < 2:
                raise OpError("split_work needs payload.groups: at least two groups of mention keys")
            seen, out = set(), []
            for i, g in enumerate(groups):
                ms = _mentions_of(g.get("members") if isinstance(g, dict) else g)
                if not ms:
                    raise OpError(f"split_work: group {i} is empty")
                for m in ms:
                    if m in seen:
                        raise OpError(f"split_work: {m} is in two groups")
                    if m not in members:
                        raise OpError(f"split_work: mention:{m} is not a member of {keys[0]}")
                    seen.add(m)
                gg = dict(members=sorted(ms), label=(g.get("label") if isinstance(g, dict) else None))
                gg["card_id"] = key_value(keys[0]) if i == 0 else split_card_id(decision_id, i)
                out.append(gg)
            payload["groups"] = out
            payload["unlisted_stay_on_first"] = sorted(set(members) - seen)
        elif op == "confirm_work":
            payload["members"] = sorted(_mentions_of(payload.get("members") or members))
        else:
            t = payload.get("type")
            if t not in WORK_TYPES:
                raise OpError(f"set_work_type: type must be one of {sorted(WORK_TYPES)}")
            ev["type_was"] = R.card(cid)["pub_type"] if R.card(cid) else None

    elif op in ("same_work", "not_same_work"):
        (c1, m1), (c2, m2) = _work(R, pend_c, keys[0], mv), _work(R, pend_c, keys[1], mv)
        if keys[0] == keys[1]:
            raise OpError(f"{op}: the two keys are the same")
        ev["members"] = {keys[0]: m1, keys[1]: m2}
        ev["titles"] = {k: (R.card(c)["title"] if R.card(c) else None) for k, c in ((keys[0], c1), (keys[1], c2))}
        impact = sum(max(1, (R.card_info(c) or {}).get("n_mentions", 0)) for c in (c1, c2) if R.card(c))
        if op == "same_work":
            if c1 == c2:
                raise OpError("same_work: these are already one card")
        else:
            if c1 == c2:
                a, b = payload.get("a_members"), payload.get("b_members")
                if not a or not b:
                    raise OpError("not_same_work: the two are one card now; give payload.a_members and b_members "
                                  "(or use split_work)")
                payload["a_members"], payload["b_members"] = sorted(_mentions_of(a)), sorted(_mentions_of(b))
            else:
                payload["a_members"], payload["b_members"] = sorted(m1), sorted(m2)

    elif op == "move_member":
        m = _mention(R, keys[0])
        if m["kind"] not in ("full", "short"):
            raise OpError("move_member: only a full citation (or an untied short form) is a card member")
        cid, members = _work(R, pend_c, keys[1], mv)
        now = R.card_of_mention(key_value(keys[0]))
        if not now:
            raise OpError(f"move_member: {keys[0]} is on no card")
        if now == cid:
            raise OpError(f"move_member: {keys[0]} is already on {keys[1]}")
        ev["members"] = {keys[1]: members}
        ev["card_was"] = now
        ev["printed"] = m["printed"]

    elif op in ("same_person", "not_same_person"):
        if keys[0] == keys[1]:
            raise OpError(f"{op}: the two keys are the same")
        p1, p2 = _person(R, pend_p, keys[0]), _person(R, pend_p, keys[1])
        info = {k: R.person_info(p) for k, p in ((keys[0], p1), (keys[1], p2))}
        ev["names"] = {k: (i["name_ar"] or i["name_lat"]) if i else None for k, i in info.items()}
        ev["authorships"] = {k: [a["ref"] for a in i["authorships"]] if i else [] for k, i in info.items()}
        ev["authorities"] = {k: i["authorities"] if i else [] for k, i in info.items()}
        impact = min(R.n_works(p1), R.n_works(p2))
        if op == "same_person" and p1 == p2:
            raise OpError("same_person: these are already one person")
        if op == "not_same_person":
            payload["b_authorships"] = sorted(payload.get("b_authorships") or ev["authorships"][keys[1]])
            payload["a_authorships"] = sorted(payload.get("a_authorships") or ev["authorships"][keys[0]])
            if p1 == p2 and not payload.get("b_authorships"):
                raise OpError("not_same_person: one person now; give payload.b_authorships")

    elif op in ("link_byline", "unlink_byline"):
        b = R.byline(key_value(keys[0]))
        if not b or not b["authorship_pk"]:
            raise OpError(f"{keys[0]}: no such byline (with an authorship) in the shown versions")
        ev["printed"] = b["printed"]
        ev["person_was"] = b["person_id"]
        ev["pub_id"] = b["pub_id"]
        if op == "link_byline":
            pid = _person(R, pend_p, keys[1])
            if b["person_id"] == pid:
                raise OpError("link_byline: the byline is already this person's")
        else:
            if not b["person_id"]:
                raise OpError("unlink_byline: the byline has no person")
            payload["from"] = f"person:{b['person_id']}"
            payload["new_person"] = unlinked_person_id(key_value(keys[0]))

    elif op in ("resolve_backref", "unresolvable"):
        m = _mention(R, keys[0])
        if m["kind"] not in BACKREF_KINDS:
            raise OpError(f"{op}: {keys[0]} is a {m['kind']} citation, not a back reference or short form")
        ev["printed"] = m["printed"]
        ev["was"] = dict(full_mention_pk=m["full_mention_pk"], method=m["resolve_method"], score=m["resolve_score"],
                         why=m["unresolved_why"])
        if op == "resolve_backref":
            t = _mention(R, keys[1])
            if t["stem"] != m["stem"]:
                raise OpError("resolve_backref: a back reference points inside its own article")
            if t["kind"] not in ("full", "short"):
                raise OpError("resolve_backref: the target must be a full citation (or a short form)")
            if t["mention_pk"] == m["mention_pk"]:
                raise OpError("resolve_backref: a mention cannot point at itself")
            ev["target_printed"] = t["printed"]
    return list(keys), payload, ev, impact


# ------------------------------------------------------------------ comparing answers (gold)
def canonical(op: str, keys, payload: dict | None) -> str:
    keys = sorted(keys) if op in SYMMETRIC else list(keys)
    payload = payload or {}
    if op == "split_work":
        p = sorted(sorted(_mentions_of(g["members"] if isinstance(g, dict) else g)) for g in payload.get("groups", []))
    elif op == "set_work_type":
        p = payload.get("type")
    elif op == "not_a_work":
        p = payload.get("action")
    elif op in ("relate_works", "relate_publication"):
        p = payload.get("relation")
    elif op == "link_publication":
        p = payload.get("as", "work")
    else:
        p = None
    return json.dumps([op, keys, p], ensure_ascii=False, sort_keys=True)


def gold_accuracy(pg, actor_id: str | None = None) -> list[dict]:
    """Per person and task kind: right / answered on gold tasks. A quiet gauge for admins; never a gate."""
    rows = pg.execute("""SELECT d.actor_id, t.kind, d.op, d.subject_keys, d.payload, g.answer FROM decisions d
                         JOIN gold g ON g.task_id = d.task_id JOIN tasks t ON t.task_id = d.task_id
                         WHERE %s::text IS NULL OR d.actor_id = %s""", (actor_id, actor_id)).fetchall()
    tally = {}
    for r in rows:
        t = tally.setdefault((r["actor_id"], r["kind"]), [0, 0])
        t[1] += 1
        t[0] += canonical(r["op"], r["subject_keys"], r["payload"]) == canonical(
            r["answer"]["op"], r["answer"]["subject_keys"], r["answer"].get("payload"))
    return [dict(actor=a, kind=k, right=v[0], answered=v[1]) for (a, k), v in sorted(tally.items())]


# ------------------------------------------------------------------ the review rule in force
def rule_for(pg, op: str) -> dict:
    r = pg.execute("SELECT * FROM review_rules WHERE op = %s", (op,)).fetchone()
    return dict(r) if r else dict(op=op, rule="single", sample_pct=0, two_keys_min_impact=None)


def policy(pg, op: str) -> str:
    """One key by default (owner, 2026-10-21). Another rule can be set per kind; P1 builds no flow for it, so a
    decision under such a rule stays `proposed` (and is not applied) until that flow exists."""
    r = rule_for(pg, op)
    return "single" if r["rule"] == "single" else (f"sample:{r['sample_pct']}" if r["rule"] == "sample"
                                                   else "two_keys")


# ------------------------------------------------------------------ ownership
def actor_row(pg, actor_id: str) -> dict:
    a = pg.execute("SELECT * FROM actors WHERE actor_id = %s AND active", (actor_id,)).fetchone()
    if not a:
        raise OpError(f"no active actor {actor_id}")
    return a


def can_supersede(actor: dict, target: dict) -> bool:
    """Only the owner of a decision (its actor), or an admin, may supersede or revert it."""
    return target["actor_id"] == actor["actor_id"] or actor["role"] == "admin"


def check_owner(actor: dict, target: dict, what: str) -> None:
    if not can_supersede(actor, target):
        raise NotOwner(f"decision {target['decision_id']} belongs to {target['actor_id']}: only they or an admin can "
                       f"{what} it. Leave a note on it instead (POST /subjects/{{key}}/notes with its decision_id).")


# ------------------------------------------------------------------ writing
def _event(pg, decision_id, status, why, actor_id):
    pg.execute("INSERT INTO decision_events (decision_id, status, why, actor_id) VALUES (%s,%s,%s,%s)",
               (decision_id, status, why, actor_id))


def set_status(pg, decision_id, status: str, why: str, actor_id: str | None = None) -> None:
    d = pg.execute("SELECT * FROM decisions WHERE decision_id = %s", (decision_id,)).fetchone()
    if d["status"] == status:
        return
    pg.execute("UPDATE decisions SET status = %s WHERE decision_id = %s", (status, decision_id))
    _event(pg, decision_id, status, why, actor_id)
    if status == "accepted" and d["supersedes"]:
        old = pg.execute("SELECT status FROM decisions WHERE decision_id = %s", (d["supersedes"],)).fetchone()
        if old and old["status"] in ("proposed", "accepted"):
            pg.execute("UPDATE decisions SET status = 'superseded', superseded_by = %s WHERE decision_id = %s",
                       (decision_id, d["supersedes"]))
            _event(pg, d["supersedes"], "superseded", f"superseded by {decision_id}", actor_id)


def ensure_subject(pg, key: str, label: str | None = None, release: str | None = None) -> None:
    pg.execute("""INSERT INTO subjects (subject_key, kind, label, first_seen_release, last_seen_release)
                  VALUES (%s, %s, %s, %s, %s)
                  ON CONFLICT (subject_key) DO UPDATE SET label = coalesce(excluded.label, subjects.label),
                     last_seen_release = coalesce(excluded.last_seen_release, subjects.last_seen_release),
                     updated_at = now()""", (key, key.split(":", 1)[0], label, release, release))


def add_task(pg, kind: str, keys, *, question=None, candidates=None, machine_guess=None, impact=1.0,
             uncertainty=0.5, source=None, skills=None, about=None, reserved_for=None, release=None,
             is_demo=False, check_standing=True) -> int | None:
    """Write a task unless its subject already has a standing decision (DESIGN §5) or the same question is already
    open. Returns the task id (new or the open one), or None when a standing decision answers it."""
    if check_standing and standing(pg, keys):
        return None
    tk = f"{kind}|{about}" if about else task_key(kind, keys)
    pr = float(impact) * float(uncertainty)
    r = pg.execute("""INSERT INTO tasks (task_key, kind, subject_keys, question, candidates, machine_guess, impact,
                         uncertainty, priority, source, skills, about_decision, reserved_for, created_release, is_demo)
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                      ON CONFLICT (task_key) WHERE state IN ('open', 'claimed') DO UPDATE SET
                         candidates = excluded.candidates, machine_guess = excluded.machine_guess,
                         impact = excluded.impact, uncertainty = excluded.uncertainty, priority = excluded.priority,
                         source = excluded.source, skills = excluded.skills, question = excluded.question,
                         updated_at = now()
                      RETURNING task_id""",
                   (tk, kind, list(keys), question, Jsonb(candidates or []), Jsonb(machine_guess) if machine_guess is not None else None, impact, uncertainty,
                    pr, Jsonb(source or {}), list(skills or []), about, reserved_for, release, is_demo)).fetchone()
    return r["task_id"]


def task_event(pg, task_id, actor_id, event, note=None):
    pg.execute("INSERT INTO task_events (task_id, actor_id, event, note) VALUES (%s,%s,%s,%s)",
               (task_id, actor_id, event, note))


def _close_covered_tasks(pg, d: dict, except_task: int | None) -> None:
    """Once decided, a detector's task never comes back (DESIGN §5): open tasks on these subjects are closed."""
    for t in pg.execute("""SELECT task_id FROM tasks WHERE state IN ('open', 'claimed') AND kind = ANY(%s)
                           AND subject_keys <@ %s AND task_id IS DISTINCT FROM %s""",
                        (list(DETECTOR_KINDS), d["subject_keys"], except_task)).fetchall():
        pg.execute("UPDATE tasks SET state = 'closed', claimed_by = NULL, lease_until = NULL, updated_at = now() "
                   "WHERE task_id = %s", (t["task_id"],))
        task_event(pg, t["task_id"], d["actor_id"], "closed", f"answered by decision {d['decision_id']}")


def decide(pg, actor_id: str, op: str, subject_keys, payload: dict | None = None, *, reason_code=None, note=None,
           confidence="sure", evidence=None, task: dict | None = None, supersedes=None, state: Reading | None = None,
           is_demo=False) -> dict:
    """Validate and write one decision; it is accepted at once under the one-key rule. The caller commits.

    Ownership: `supersedes` (and revert / retire) is allowed only for the owner of the decision superseded, or an
    admin. A decision on exactly the subjects someone else has a standing decision on is refused too: it would
    override theirs. Leave a note on theirs instead."""
    actor = actor_row(pg, actor_id)
    did = str(uuid.uuid4())
    R = state or open_state(pg)
    target = None
    if supersedes or op in ("revert", "retire"):
        target = pg.execute("SELECT * FROM decisions WHERE decision_id = %s",
                            (supersedes or (payload or {}).get("decision_id"),)).fetchone()
        if not target:
            raise OpError(f"{op}: no such decision to supersede")
        if target["status"] not in ("proposed", "accepted"):
            raise OpError(f"decision {target['decision_id']} is {target['status']}: it cannot be superseded")
        check_owner(actor, target, "revert" if op == "revert" else "supersede")
        supersedes = target["decision_id"]
    if op in ("revert", "retire"):
        keys, payload, ev = list(target["subject_keys"]), dict(decision_id=str(target["decision_id"]),
                                                               op=target["op"]), {}
        domain = target["domain"]
    else:
        keys, payload, ev, _ = prepare(pg, R, did, op, list(subject_keys), payload or {})
        domain = OPS[op][0]
        by_first = op in KEYED_BY_FIRST
        for other in standing(pg, keys[:1] if by_first else keys):
            same_q = other["subject_keys"][:1] == keys[:1] if by_first else sorted(other["subject_keys"]) == sorted(keys)
            if same_q and str(other["decision_id"]) != str(supersedes) \
                    and FAMILY.get(other["op"]) == FAMILY.get(op):
                if other["actor_id"] != actor_id and actor["role"] != "admin":
                    raise NotOwner(f"{other['actor_id']} has already decided this ({other['op']}, decision "
                                   f"{other['decision_id']}). Only they or an admin can change it: leave a note on "
                                   f"it instead.")
                raise OpError(f"there is already a standing decision on these subjects ({other['op']}, decision "
                              f"{other['decision_id']}): supersede it (supersedes = its id) to change it")
    ev.update(evidence or {})
    pol = policy(pg, op)
    pg.execute("""INSERT INTO decisions (decision_id, domain, op, subject_keys, payload, reason_code, note, evidence,
                     actor_id, role_at_time, task_id, confidence, status, supersedes, review_policy_at_time, is_demo)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'proposed',%s,%s,%s)""",
               (did, domain, op, keys, Jsonb(payload), reason_code, note, Jsonb(ev), actor_id, actor["role"],
                task["task_id"] if task else None, confidence, supersedes, pol, is_demo))
    _event(pg, did, "proposed", f"made under {pol}", actor_id)
    for k in keys:
        ensure_subject(pg, k, R.label(k) if R else None)
    if pol == "single":
        set_status(pg, did, "accepted", "one key: accepted when made", actor_id)
    d = pg.execute("SELECT * FROM decisions WHERE decision_id = %s", (did,)).fetchone()
    if op not in ("revert", "retire"):
        _close_covered_tasks(pg, d, task["task_id"] if task else None)
    return dict(d)


def revert(pg, actor_id: str, decision_id, note=None, is_demo=False) -> dict:
    """Undo: a superseding decision that restores the machine's reading for these subjects. Owner or admin only."""
    return decide(pg, actor_id, "revert", [], supersedes=decision_id, note=note, is_demo=is_demo)


# ------------------------------------------------------------------ notes (a corrector who disagrees leaves one)
def add_note(pg, author: str, subject_key: str, text: str, decision_id=None, is_demo=False) -> dict:
    actor_row(pg, author)
    split_key(subject_key)
    if not (text or "").strip():
        raise OpError("a note needs text")
    if decision_id:
        d = pg.execute("SELECT subject_keys FROM decisions WHERE decision_id = %s", (decision_id,)).fetchone()
        if not d:
            raise OpError("no such decision")
        if subject_key not in d["subject_keys"]:
            raise OpError(f"decision {decision_id} is not about {subject_key}")
    ensure_subject(pg, subject_key)
    return dict(pg.execute("INSERT INTO notes (subject_key, decision_id, author, text, is_demo) VALUES (%s,%s,%s,%s,%s)"
                           " RETURNING *", (subject_key, decision_id, author, text.strip(), is_demo)).fetchone())


def my_notes(pg, actor_id: str, include_resolved=False) -> list[dict]:
    """Notes others left on my decisions."""
    return [dict(r) for r in pg.execute(
        """SELECT n.*, d.op, d.subject_keys FROM notes n JOIN decisions d ON d.decision_id = n.decision_id
           WHERE d.actor_id = %s AND n.author <> %s AND (%s OR n.resolved_at IS NULL)
           ORDER BY n.created_at DESC""", (actor_id, actor_id, include_resolved)).fetchall()]


def resolve_note(pg, actor_id: str, note_id: int) -> dict:
    """The note's author, the owner of the decision it is on, or an admin, marks it resolved."""
    actor = actor_row(pg, actor_id)
    n = pg.execute("SELECT n.*, d.actor_id AS owner FROM notes n LEFT JOIN decisions d USING (decision_id) "
                   "WHERE note_id = %s", (note_id,)).fetchone()
    if not n:
        raise OpError("no such note")
    if actor_id not in (n["author"], n["owner"]) and actor["role"] != "admin":
        raise NotOwner("only the note's author, the decision's owner or an admin can resolve this note")
    if n["resolved_at"]:
        raise OpError("the note is already resolved")
    return dict(pg.execute("UPDATE notes SET resolved_at = now(), resolved_by = %s WHERE note_id = %s RETURNING *",
                           (actor_id, note_id)).fetchone())


# ------------------------------------------------------------------ the operations P1 needs, by name
def split_work(pg, actor, card_key, groups, **kw):
    """«الديوان» → one card per poet: groups = [[mention keys …], [...], …]; the first group keeps the card's id."""
    return decide(pg, actor, "split_work", [card_key], dict(groups=[dict(members=g) if isinstance(g, list) else g
                                                                   for g in groups]), **kw)


def same_work(pg, actor, keep_key, other_key, **kw):
    return decide(pg, actor, "same_work", [keep_key, other_key], {}, **kw)


def not_same_work(pg, actor, a_key, b_key, **kw):
    return decide(pg, actor, "not_same_work", [a_key, b_key], {}, **kw)


def move_member(pg, actor, mention_key, card_key, **kw):
    return decide(pg, actor, "move_member", [mention_key, card_key], {}, **kw)


def set_work_type(pg, actor, card_key, type_, **kw):
    return decide(pg, actor, "set_work_type", [card_key], dict(type=type_), **kw)


def confirm_work(pg, actor, card_key, **kw):
    return decide(pg, actor, "confirm_work", [card_key], {}, **kw)


def same_person(pg, actor, keep_key, other_key, **kw):
    return decide(pg, actor, "same_person", [keep_key, other_key], {}, **kw)


def not_same_person(pg, actor, a_key, b_key, **kw):
    return decide(pg, actor, "not_same_person", [a_key, b_key], {}, **kw)


def link_byline(pg, actor, byline_key, person_key, **kw):
    return decide(pg, actor, "link_byline", [byline_key, person_key], {}, **kw)


def unlink_byline(pg, actor, byline_key, **kw):
    return decide(pg, actor, "unlink_byline", [byline_key], {}, **kw)


def resolve_backref(pg, actor, mention_key, target_key, **kw):
    return decide(pg, actor, "resolve_backref", [mention_key, target_key], {}, **kw)


def unresolvable(pg, actor, mention_key, **kw):
    return decide(pg, actor, "unresolvable", [mention_key], {}, **kw)
