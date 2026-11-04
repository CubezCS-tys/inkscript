"""Experiment 62: add the librarian's calls to overrides62.json, one per line on stdin:

    A|B ; kind ; confidence ; basis ; reason [; extra]        (a pair of cards; `extra` = a pair the blocking missed)
    split:CID ; split_card ; medium ; judgement ; reason ; groups=m1 + m2 / m3 [; joins=m3 > CID2]   (or card_ok / unsure)
    notwork:CID ; not_a_work ; high ; rule ; reason ; action=drop|one_per_citation
    catalogue:CID ; links_to_publication | relation | no_link ; conf ; basis ; reason [; c999=...]

A later line for the same key replaces the earlier call (the file keeps only the latest; the decisions log keeps all).
"""
import json
import sys
from pathlib import Path

F = Path(__file__).resolve().parent / "overrides62.json"


def main():
    ovr = json.loads(F.read_text(encoding="utf-8")) if F.exists() else {}
    n = 0
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split(" ; ")]
        k, kind, conf, basis, reason = parts[:5]
        o = dict(kind=kind, confidence=conf, basis=basis, reason=reason)
        for extra in parts[5:]:
            if extra == "extra":
                o["extra"] = True
            elif extra.startswith("groups="):      # members by a distinctive piece of their mention id ("p17|w15")
                o["groups"] = [[m.strip() for m in g.split("+")] for g in extra[7:].split(" / ")]
            elif extra.startswith("joins="):       # "<member piece> > <card id>": that member's group is that card's work
                o["joins"] = [dict(zip(("member", "card"), [x.strip() for x in j.split(">")])) for j in extra[6:].split(" & ")]
            elif "=" in extra:
                a, b = extra.split("=", 1)
                o[a] = b
        ovr[k] = o
        n += 1
    F.write_text(json.dumps(ovr, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(n, "calls;", len(ovr), "overrides in all")


if __name__ == "__main__":
    main()
