"""Experiment 56, step 2b: the librarian's verdicts written as decisions (append-only JSONL, one per question).

Two levels of question:
1. **Per printed affiliation** (written batch by batch while judging, `commit_batch`): "which institution(s) does
   this affiliation name, and in which country?" One decision of kind
   - `affiliation_institution` (resolved: the machine's org link is confirmed, or fixed to the real institution),
   - `unit_kept_apart` (a faculty printed without its university: its own unit, never lumped with others),
   - `not_an_institution` (a place or a position only),
   - `unsure` (left as the machine has it, marked).
2. **Per institution** (written once all affiliations are judged, `finalize`): over the authority,
   - `same_institution` (machine rows, printed forms or scripts that are one body: Alexandria University = جامعة
     الإسكندرية), `not_same_institution` (one machine row holding different bodies: the lumped «org:?» faculties),
   - `set_country`, `set_parent`, `set_type` where the authority differs from the machine row.

Every decision carries: the decision, a short reason, the evidence ids (affiliation keys, machine institution ids,
catalogue hits), confidence (high / medium / low), basis (rule | catalogue | world | context | judgement) and
`trivial` (a deterministic rule reproduces it). Decisions are proposals: nothing is applied to the platform.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DEC = OUT / "decisions56.jsonl"
ACTOR = "agent:librarian-56"


def did(*parts) -> str:
    return "D56-" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


def latest() -> dict:
    """The newest decision per question (a later one supersedes an earlier one on the same question)."""
    out = {}
    if DEC.exists():
        for l in open(DEC, encoding="utf-8"):
            d = json.loads(l)
            out[d["qkey"]] = d
    return out


def append(decs: list) -> int:
    """Append-only: a question already decided the same way is skipped; a changed answer is a new decision that
    supersedes the earlier one (both stay in the file)."""
    have = latest()
    n = 0
    with open(DEC, "a", encoding="utf-8") as f:
        for d in decs:
            old = have.get(d["qkey"])
            d["content_id"] = d["decision_id"]          # the hash of what is decided (same answer = same content_id)
            if old and old.get("content_id", old["decision_id"]) == d["content_id"]:
                continue
            if old:
                d["supersedes"] = old["decision_id"]
                # a unique id even when an answer returns to an earlier one (A, then B, then A again)
                d["decision_id"] = did(d["content_id"], old["decision_id"])
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            n += 1
    return n


def packet_text(p: dict) -> str:
    """The evidence a model would read for this packet (its size is what the scale report counts)."""
    keep = {k: p[k] for k in ("key", "stem", "journal", "year", "author", "printed", "parts", "kind", "same_article",
                              "other_articles", "machine", "catalogue")}
    return json.dumps(keep, ensure_ascii=False)


def mention_decision(p: dict, v: dict) -> dict:
    from judge56 import AUTH
    m = p["machine"].get("org")
    morg = m["inst_id"] if m else None
    st = v["status"]
    kind = {"resolved": "affiliation_institution", "unit_only": "unit_kept_apart",
            "not_institution": "not_an_institution", "unsure": "unsure"}[st]
    orgs = v.get("orgs") or []
    machine_names = (m or {}).get("names") or []
    agrees = None
    if st == "resolved":
        # the machine agrees when its org row's printed names are this authority entry's forms
        from judge56 import matches, canon, top_of
        agrees = bool(m) and any(canon(x) == orgs[0] for x, _ in matches(" ".join(machine_names[:3])))
    dec = dict(status=st, institutions=[dict(id=o, name_ar=AUTH[o]["name_ar"], name_en=AUTH[o]["name_en"])
                                        for o in orgs if o in AUTH],
               units=v.get("units") or [], faculty=v.get("faculty"), country=v.get("country"),
               country_basis=v.get("country_basis"), machine_org=morg, machine_org_names=machine_names[:2],
               machine_agrees=agrees)
    q = "Which institution(s) does this printed affiliation name?"
    ev = [p["key"]] + [x["key"] for x in p["same_article"]] + ([morg] if morg else [])
    for lvl in ("faculty", "dept"):
        if p["machine"].get(lvl):
            ev.append(p["machine"][lvl]["inst_id"])
    reason = v.get("reason")
    if not reason and st == "resolved":
        reason = "the printed name is this institution's form"
        if agrees is False:
            mn = machine_names[0] if machine_names else None
            reason = (f"the statement prints {AUTH[orgs[0]]['name_en']}; the machine linked " +
                      (f"«{mn}» instead" if mn else "nothing") +
                      (" (a unit inside it)" if mn and any(canon(x) != orgs[0] and top_of(x) == orgs[0]
                                                          for x, _ in matches(mn)) else ""))
    sig = json.dumps([kind, dec, v.get("confidence"), v.get("basis"), reason], ensure_ascii=False, sort_keys=True)
    out = dict(decision_id=did("aff", p["key"], sig), qkey=f"aff|{p['key']}", made_at=time.strftime("%Y-%m-%dT%H:%M:%S"), actor=ACTOR,
               level="affiliation", kind=kind, question=q, subject_keys=[p["key"]] + ([f"inst:{morg}"] if morg else []),
               decision=dec, reason=reason,
               evidence_ids=ev, confidence=v.get("confidence"), basis=v.get("basis"), trivial=bool(v.get("trivial")),
               printed=p["printed"], stem=p["stem"],
               size=dict(evidence_chars=len(packet_text(p))))
    out["size"]["decision_chars"] = len(json.dumps({k: out[k] for k in ("kind", "decision", "reason", "evidence_ids",
                                                                         "confidence")}, ensure_ascii=False))
    if st == "resolved" and agrees is False:
        out["fix"] = "machine linked " + (f"«{machine_names[0] if machine_names else '(no name)'}» ({morg})" if morg
                                          else "nothing")
    return out


def commit_batch(b: int, packets: list, overrides: dict) -> dict:
    from judge56 import judge
    decs = [mention_decision(p, judge(p, overrides)) for p in packets]
    n = append(decs)
    return dict(batch=b, decisions=len(decs), appended=n, kinds=Counter(d["kind"] for d in decs))
