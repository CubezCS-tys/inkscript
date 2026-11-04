"""Experiment 72, the lead's follow-up (2026-11-03): citations the machine joined to a card by a shared title phrase
while their authors and years disagree (scan72.py), split off, as Desk decisions of agent:librarian.

The four cards (each read against Azure's own OCR of the printed note, out/scan72.txt):
- CBDD9P2BCR al-Hiti «ثقافة الأطفال» (1988) held three citations of al-Kaabi's «تكنولوجيا الثقافة: دراسة في الأسس العلمية
  لثقافة الأطفال» (2011, Sharjah), all on 0165-007-028-003 p25 (w106-129 «الكعبي، فاضل (٢٠١١) تكنولوجيا الثقافة …»,
  w183-200 and w237-256 «… راجع كتابنا: تكنولوجيا الثقافة …»: the article's author is al-Kaabi). They are split off and
  joined to al-Kaabi's own card C34EFXV0F2 (0165-009-031-004). This pass had confirmed the card (Flash: card ok) and
  joined it with CKY1ACWX0J and kept it apart from C34EFXV0F2 while it held them: those three decisions are
  superseded by their owner, re-made on the card as it is after the split.
- C8B5VY3Z4G «جودة الحياة» (عمر 2014) held «استخدام المدخل الإسكندنافي في تحسين جودة حياة الأشخاص الصم المكفوفين» (عمر 2008).
- CJMAPFK28P al-Maamari «التربية من أجل المواطنة …» (2014) held ناصر، إبراهيم «المواطنة» (2002).
- C18S7AC7QV Tibbitts & Fernekes «Human rights education» (2011) held Tibbitts «Understanding What We Do: Emerging
  Models for Human Rights Education» (2002).
The other five flagged members are one work (a translation, editions 1916 / 1966, 1992 / 2006): not changed.

    cd experiments/49_correction_desk
    .venv/bin/python ../72_librarian_0165/fix72.py --schema desk|test_e72dry [--state RELEASE]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "49_correction_desk"))
from desk import db, ops  # noqa: E402
from desk.reading import Reading  # noqa: E402

ACTOR = "agent:librarian"
KAABI = ["0165-007-028-003|p25|w106-129|1", "0165-007-028-003|p25|w183-200|1", "0165-007-028-003|p25|w237-256|1"]
SPLITS = {   # card -> the mention(s) that are another work (the rest stay on the card)
    "CBDD9P2BCR": KAABI,
    "C8B5VY3Z4G": ["0165-009-030-008|p12|w304-326|1"],
    "CJMAPFK28P": ["0165-008-029-006|p30|w409-421|1"],
    "C18S7AC7QV": ["0165-007-028-006|p34|w100-120|1"],
    "CVDWKPANEQ": ["0165-000-044-002|pNone|r16|1"],
}
WHY = {
    "CBDD9P2BCR": "three citations of Fadhil al-Kaabi's «تكنولوجيا الثقافة: دراسة في الأسس العلمية لثقافة الأطفال» (2011, "
                  "دائرة الثقافة والإعلام، الشارقة) were joined by the machine (in-article repeat) to Hadi Numan al-Hiti's "
                  "«ثقافة الأطفال» (1988) through the phrase «ثقافة الأطفال»: another author, year, place and publisher. The "
                  "print (Azure's OCR of 0165-007-028-003 p25, lines 12, 17, 23) names al-Kaabi and «كتابنا» (our book)",
    "C8B5VY3Z4G": "Suhair Abdel-Hafiz Omar's 2008 article «استخدام المدخل الإسكندنافي في تحسين جودة حياة الأشخاص الصم المكفوفين» "
                  "(مجلة العلوم التربوية) is not her 2014 «جودة الحياة» (مجلة المنال): another title, year and journal",
    "CJMAPFK28P": "Ibrahim Nasser's «المواطنة» (2002, دار مكتبة الرائد العلمية، عمّان) is not Saif al-Maamari's «التربية من أجل "
                  "المواطنة في دول مجلس التعاون» (2014, مجلة رؤى إستراتيجية): another author, title, year and form",
    "CVDWKPANEQ": "«__________ (2011): العلاج النفسي، القاهرة، مصر الجديدة، مركز الطب النفسي والعصبي للأطفال» repeats the author "
                  "of the entry above it in 0165-000-044-002 (r15: محمد عبد الرحمن حمودة); it is not محمد قاسم عبد الله's "
                  "«العلاج النفسي» (2013, جامعة حلب): another author, year, place and publisher (found while reading every "
                  "card Flash called one work)",
    "C18S7AC7QV": "Felisa Tibbitts's 2002 article «Understanding What We Do: Emerging Models for Human Rights Education» "
                  "(International Review of Education 48(3)) is not Tibbitts & Fernekes 2011 «Human rights education» (a "
                  "chapter in Teaching and studying social issues): another title, year and form",
}


def prov(card, extra=None):
    return dict(experiment=72, step="the lead's follow-up 2026-11-03 (scan72.py)", tier="rule", rule="scan72",
                verification=dict(print="Azure's OCR lines of the printed notes, read by agent:exp72", card=card),
                **(extra or {}))


def standing_by_source(pg, src):
    return pg.execute("SELECT * FROM decisions WHERE actor_id = %s AND evidence->>'source_id' = %s AND status IN "
                      "('proposed', 'accepted')", (ACTOR, src)).fetchone()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=db.pg_schema())
    ap.add_argument("--state")
    a = ap.parse_args(argv)
    log = []
    with db.connect(a.schema) as pg:
        state = Path(a.state) if a.state else db.state_path(pg)
        R = Reading(sqlite3.connect(f"file:{state}?mode=ro", uri=True))

        def decide(src, op, keys, payload, note, supersedes_src=None):
            if standing_by_source(pg, f"E72:{src}"):
                log.append(dict(source=src, already=True))
                return standing_by_source(pg, f"E72:{src}")
            sup = None
            if supersedes_src:
                t = standing_by_source(pg, supersedes_src)
                if not t:
                    raise SystemExit(f"{src}: no standing decision {supersedes_src} to supersede")
                sup = t["decision_id"]
            d = ops.decide(pg, ACTOR, op, keys, payload, reason_code="librarian:scan72", note=note, confidence="sure",
                           evidence=dict(source_id=f"E72:{src}", provenance=prov(keys[0], dict(
                               supersedes_source=supersedes_src))), state=R, supersedes=sup)
            log.append(dict(source=src, op=op, keys=keys, decision_id=str(d["decision_id"]), supersedes=str(sup)
                            if sup else None))
            return d
        # Flash's "card ok" read in full (26): 2 wrong (CBDD9P2BCR, CVDWKPANEQ) = 92%, under 98%: the kind is held.
        # Its standing confirm_work decisions are reverted by their owner (a confirm changes nothing shown; it only
        # pins the members together) and each question becomes a Desk task (below); CBDD9P2BCR's is superseded by its
        # split instead.
        held_ok = []
        for d in pg.execute("SELECT * FROM decisions WHERE actor_id = %s AND op = 'confirm_work' AND status = "
                            "'accepted' AND reason_code = 'librarian:flash:card_ok'", (ACTOR,)).fetchall():
            cid = d["subject_keys"][0][5:]
            if cid == "CBDD9P2BCR":
                continue
            src = f"E72:fix|revert|{d['evidence'].get('source_id')}"
            if not standing_by_source(pg, src):
                r = ops.decide(pg, ACTOR, "revert", [], supersedes=d["decision_id"], note="Flash's card ok is held "
                               "as a proposal: the full read of its 26 found 2 wrong (CBDD9P2BCR, CVDWKPANEQ), under "
                               "98%; a person decides (task)", evidence=dict(source_id=src, provenance=prov(cid)), state=R)
                log.append(dict(source=src, op="revert", decision_id=str(r["decision_id"]), supersedes=str(d["decision_id"])))
            held_ok.append(cid)
        for cid, out in SPLITS.items():
            members = R.card_members(cid)
            ids = [m["mention_id"] if isinstance(m, dict) else m for m in members]
            stay = [m for m in ids if m not in out]
            assert set(out) <= set(ids), (cid, out, ids)
            sup = "E72:card|CBDD9P2BCR" if cid == "CBDD9P2BCR" else None
            decide(f"fix|split|{cid}", "split_work", [f"work:{cid}"],
                   dict(groups=[dict(members=stay), dict(members=out, label="another work")]), WHY[cid], sup)
        sp = standing_by_source(pg, "E72:fix|split|CBDD9P2BCR")
        x = sp["payload"]["groups"][1]["card_id"]
        decide("fix|same|CBDD9P2BCR|CKY1ACWX0J", "same_work", ["work:CBDD9P2BCR", "work:CKY1ACWX0J"], {},
               "al-Hiti's «ثقافة الأطفال» (عالم المعرفة 123, 1988), re-made on the card without al-Kaabi's three "
               "citations (it had recorded them)", "E72:pair|CBDD9P2BCR|CKY1ACWX0J")
        decide("fix|notsame|C34EFXV0F2|CBDD9P2BCR", "not_same_work", ["work:C34EFXV0F2", "work:CBDD9P2BCR"], {},
               "al-Kaabi's «تكنولوجيا الثقافة» (2011) and al-Hiti's «ثقافة الأطفال» (1988) are two works; re-made on the card "
               "without al-Kaabi's three citations", "E72:pair|C34EFXV0F2|CBDD9P2BCR")
        # a decision that recorded a card's members before the split holds for all of them: CJMAPFK28P's K1c link to
        # al-Maamari's article recorded Nasser's citation too, so it is re-made on the card without it (dry run: the
        # release found it could not hold)
        old = standing_by_source(pg, "E72:link|CJMAPFK28P")
        if old:
            decide("fix|link|CJMAPFK28P", "link_publication", ["work:CJMAPFK28P", "pub:W621974"], dict(old["payload"]),
                   old["note"] + " (re-made on the card without Nasser's «المواطنة», split off)", "E72:link|CJMAPFK28P")
        decide("fix|same|C34EFXV0F2|kaabi", "same_work", ["work:C34EFXV0F2", f"work:{x}"], {},
               "al-Kaabi's three citations on 0165-007-028-003 p25 and his card C34EFXV0F2 (0165-009-031-004: «الكعبي، "
               "فاضل (٢٠١١) تكنولوجيا الثقافة: دراسة في الأسس العلمية لثقافة الأطفال، دائرة الثقافة والإعلام، الشارقة») are one "
               "book: same author, title, year, publisher and place")
        qs = {json.loads(l)["id"]: json.loads(l) for l in open(HERE / "out" / "questions" / "works.jsonl",
                                                                 encoding="utf-8")}
        ans = {}
        for m in ("gemini-3.8-flash", "claude-opus-5-5"):
            for l in open(HERE / "out" / "answers" / f"{m}.jsonl", encoding="utf-8"):
                x = json.loads(l)
                if x.get("answer"):
                    ans.setdefault(x["id"], {})[m] = x["answer"]
        made = 0
        for cid in held_ok:
            q = qs.get(f"W72-S{cid}")
            if not q or cid in SPLITS:
                continue
            tid = ops.add_task(pg, "librarian_question", [f"work:{cid}"],
                               question=f"{q['question']} (librarian: Flash said card_ok; the kind is held, 2 of 26 "
                                        "were wrong)", candidates=[dict(evidence=q["evidence"], options=q["options"])],
                               machine_guess=dict(librarian=ans.get(q["id"], {})), impact=1, uncertainty=0.5,
                               source=dict(detector="librarian72", experiment=72, question=q["id"], kind=q["kind"],
                                           why="Flash card ok held (hand check 24/26)"), skills=["ar"],
                               check_standing=False)
            made += tid is not None
        log.append(dict(tasks_for_held_card_ok=made))
        pg.commit()
    (HERE / "out" / f"fix72_{a.schema}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(log, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
