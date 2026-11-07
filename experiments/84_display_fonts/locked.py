"""The LOCKED final test (experiment 84): journals nobody trains on, tunes on or looks at until the final claim.

Every future selector, trainer, text or font source and test builder must exclude these journals:

    import sys; sys.path.insert(0, "experiments/84_display_fonts")
    from locked import locked_codes, assert_not_locked, is_locked
    candidates = [d for d in candidates if not is_locked(d["id"])]      # when selecting
    assert_not_locked(stems_or_keys)                                    # before training / tuning / showing

A stem, key or code is locked when its first four characters (the journal code: "0123-045-006-007_p001_l002" ->
"0123") are a locked code.  The list is LOCKED_TEST.json next to this file; opening it for the final claim needs the
owner's OK (see the note in that file).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LOCKED = Path(__file__).resolve().parent / "LOCKED_TEST.json"


@lru_cache(maxsize=1)
def locked_codes() -> frozenset[str]:
    return frozenset(j["code"] for j in json.loads(LOCKED.read_text(encoding="utf-8"))["journals"])


def is_locked(stem_or_code: str) -> bool:
    return str(stem_or_code).strip()[:4] in locked_codes()


def assert_not_locked(stems) -> int:
    """Raise if any stem / line key / journal code belongs to a locked journal; returns how many were checked."""
    if isinstance(stems, str):
        stems = [stems]
    n, bad = 0, []
    for s in stems:
        n += 1
        if is_locked(s):
            bad.append(s)
    if bad:
        raise AssertionError(f"{len(bad)} item(s) from LOCKED final-test journals (experiment 84), e.g. {bad[:5]}; "
                             "these journals are not to be trained on, tuned on or looked at")
    return n


if __name__ == "__main__":
    import sys
    codes = locked_codes()
    print(len(codes), "locked journals:", " ".join(sorted(codes)))
    if len(sys.argv) > 1:                       # check files of stems / keys (one per line, or jsonl with a key/id/stem)
        for f in sys.argv[1:]:
            items = []
            for l in open(f, encoding="utf-8"):
                l = l.strip()
                if l.startswith("{"):
                    d = json.loads(l)
                    l = d.get("key") or d.get("id") or d.get("stem") or d.get("jcode") or ""
                if l:
                    items.append(l)
            print(f, assert_not_locked(items), "checked, none locked")
