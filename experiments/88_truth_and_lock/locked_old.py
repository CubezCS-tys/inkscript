"""The LOCKED tests, both of them: experiment 84's 20 journals AND experiment 88's old-print documents.

EVERY future selector, downloader, trainer, text or font source, tuner and test builder must call this guard — not
experiment 84's locked.py alone, which knows only the journals:

    import sys; sys.path.insert(0, "experiments/88_truth_and_lock")
    from locked_old import assert_not_locked, is_locked_any
    candidates = [d for d in candidates if not is_locked_any(d["id"])]   # when selecting or downloading
    assert_not_locked(stems_or_keys)                                     # before training / tuning / showing

- a journal is locked (experiment 84, LOCKED_TEST.json): any stem, line key or code whose first four characters are
  one of its 20 codes;
- a document is locked (experiment 88, LOCKED_OLD_DOCS.json): any stem or line key whose document stem
  ("0123-045-006-007_p001_l002" -> "0123-045-006-007") is one of its documents.  Its journal is NOT locked: other
  documents of the same journal may be used.  The locked documents are never downloaded, never opened, never trained
  or tuned on; they are opened once, for the final claim, with the owner's OK.

experiment 84's locked.py is imported, not edited.
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "84_display_fonts"))
import locked as _locked84                                   # noqa: E402  (experiment 84's journal guard)
from locked import is_locked, locked_codes                   # noqa: E402,F401  (re-exported)

LOCKED_DOCS = HERE / "LOCKED_OLD_DOCS.json"
_STEM = re.compile(r"\d{4}-\d{3}-[\d,]+-\d{3}")


@lru_cache(maxsize=1)
def locked_docs() -> frozenset[str]:
    """The locked old-print document stems (experiment 88)."""
    return frozenset(d["stem"] for d in json.loads(LOCKED_DOCS.read_text(encoding="utf-8"))["documents"])


def doc_stem(s: str) -> str:
    """'0123-045-006-007_p001_l002' / '.../0123-045-006-007.pdf' -> '0123-045-006-007' ('' when none)."""
    m = _STEM.search(str(s))
    return m.group() if m else ""


def is_locked_doc(stem: str) -> bool:
    """True when the stem, line key or file path belongs to a locked old-print document."""
    return doc_stem(stem) in locked_docs()


def is_locked_any(s: str) -> bool:
    """Locked journal (experiment 84) or locked document (experiment 88)."""
    return is_locked(s) or is_locked_doc(s)


def assert_not_locked(stems) -> int:
    """Raise if any stem / line key / code belongs to a locked journal (84) or a locked document (88).
    Returns how many were checked."""
    if isinstance(stems, str):
        stems = [stems]
    stems = list(stems)
    _locked84.assert_not_locked(stems)
    bad = [s for s in stems if is_locked_doc(s)]
    if bad:
        raise AssertionError(f"{len(bad)} item(s) from LOCKED old-print documents (experiment 88), e.g. {bad[:5]}; "
                             "these documents are not to be downloaded, trained on, tuned on or looked at")
    return len(stems)


if __name__ == "__main__":
    print(len(locked_codes()), "locked journals (exp 84);", len(locked_docs()), "locked documents (exp 88)")
    for f in sys.argv[1:]:                 # check files of stems / keys (one per line, or jsonl with key/id/stem)
        items = []
        for l in open(f, encoding="utf-8"):
            l = l.strip()
            if l.startswith("{"):
                d = json.loads(l)
                l = d.get("key") or d.get("id") or d.get("stem") or d.get("jcode") or ""
            if l:
                items.append(l)
        print(f, assert_not_locked(items), "checked, none locked")
