"""Experiment 60, test 1: the proof pack's 60 pages, Claude's master against Argon's (no calls).

For each page: is Argon's first answer through today's code (out/t1/argon_build) the page the proof pack judged
after fix round 3 (experiment 43 out/v33_300b_fix3/masters, judge + retries applied)? Is Claude's page
(out/t1/build) the same as Argon's first answer? Every difference is written out for a person to judge against the
scan (out/t1/pages_diff/<stem>_pNNN.txt); verdicts are entered by hand in out/t1/page_verdicts.json.

    pages60.py            -> out/t1/pages.json (+ pages_diff/)
"""
from __future__ import annotations

import json
from pathlib import Path

from common60 import E43, OUT, jdump
from pagedump60 import same_page

PROOF = E43 / "out" / "proof"
FIX3 = E43 / "out" / "v33_300b_fix3" / "masters"
# fix round 3's changes to the proof's verdicts (experiment 43 README, "Fix round 3": right 35 -> 43)
FIX3_RIGHT = {("0201-000-044-001", 11), ("0295-014-001-012", 3), ("0764-000-028-013", 1), ("0631-013-004-008", 1),
              ("0416-009-000-008", 8), ("0511-000-051,052-036", 6), ("0511-000-051,052-036", 10),
              ("1173-000-027-061", 3)}


def proof_pages():
    rows = [json.loads(s) for s in (PROOF / "pages.jsonl").read_text().splitlines() if s.strip()]
    return rows


def main():
    T1 = OUT / "t1"
    dd = T1 / "pages_diff"
    dd.mkdir(parents=True, exist_ok=True)
    out = []
    for r in proof_pages():
        s, p = r["stem"], r["page"]
        v_final = "right" if (s, p) in FIX3_RIGHT else r["verdict"]
        a_same_fix3, d1 = same_page(FIX3, T1 / "argon_build" / "masters", s, p)
        c_same, d2 = same_page(T1 / "argon_build" / "masters", T1 / "build" / "masters", s, p)
        if d1 or d2:
            (dd / f"{s}_p{p:03d}.txt").write_text(
                f"{s} p{p}  proof verdict {r['verdict']} -> after fix3 {v_final}: {r['why']}\n\n"
                f"== Argon fix3 (judged) vs Argon first answer, today's code: {'same' if a_same_fix3 else 'DIFFERS'}\n"
                + "\n".join(d1) + f"\n\n== Argon first answer vs Claude: {'same' if c_same else 'DIFFERS'}\n"
                + "\n".join(d2) + "\n", encoding="utf-8")
        out.append(dict(stem=s, page=p, proof=r["verdict"], kinds=r.get("kinds"), after_fix3=v_final,
                        argon_plain_same_as_judged=a_same_fix3, claude_same_as_argon_plain=c_same,
                        n_diff_claude=len([l for l in d2 if l[:1] in "+-"])))
    jdump(T1 / "pages.json", out)
    n = len(out)
    print(f"{n} pages; Argon plain = judged: {sum(o['argon_plain_same_as_judged'] for o in out)}; "
          f"Claude = Argon plain: {sum(o['claude_same_as_argon_plain'] for o in out)}")


if __name__ == "__main__":
    main()
