"""Experiment 102's data guard: every key that may be trained on or used to choose anything passes here first.

Locked or held-out, never trained on and never used to choose a checkpoint or a setting:
  1. experiment 97's 60 exam articles (LOCKED_EVAL.json): every line of those documents, not only the 600 sampled;
  2. experiment 84's 20 locked journals and experiment 88's 280 locked old-print documents, through experiment 88's
     guard `locked_old.assert_not_locked` (imported unchanged; it calls experiment 84's `locked.py` too);
  3. experiment 76's held-out split (split76.json "test": 27 journal codes, the owner's 20 held-out pages among them);
  4. also kept out, by this experiment's own choice: the documents of experiments 100/101's 40 dev pages
     (DEV_PAGES.json: five exam-adjacent articles), so later page-level comparisons stay clean.
Never a source of targets: experiment 100's OCRia-1 outputs (licence) and experiment 101's plain-Qwen outputs
(evaluation records): `assert_sources` refuses any label source but the allowed ones.

    from guard102 import assert_trainable, is_forbidden, assert_sources
    assert_trainable(keys)          # raises AssertionError naming the rule and examples; returns the count checked
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "88_truth_and_lock"))
import locked_old  # noqa: E402  (experiment 88's guard; it imports experiment 84's locked.py)

LOCKED_EVAL = E / "97_extraction_evals/LOCKED_EVAL.json"
SPLIT76 = E / "76_finetune_pilot/out/split76.json"
DEV_PAGES = E / "101_qwen_base_exam/DEV_PAGES.json"
_STEM = re.compile(r"\d{4}-\d{3}-[\d,]+-\d{3}")

# label sources a target may come from (pool102.py writes one of these on every line)
ALLOWED_SOURCES = frozenset({"azure_consensus", "azure_r77", "v6r_judged", "v6r_rule85", "t91_title"})
FORBIDDEN_SOURCE_WORDS = ("ocria", "exp100", "exp101", "qwen")


@lru_cache(maxsize=1)
def exam_stems() -> frozenset[str]:
    return frozenset(a["stem"] for a in json.loads(LOCKED_EVAL.read_text())["articles"])


@lru_cache(maxsize=1)
def heldout_codes() -> frozenset[str]:
    return frozenset(json.loads(SPLIT76.read_text())["test"])


@lru_cache(maxsize=1)
def devpage_stems() -> frozenset[str]:
    return frozenset(p["stem"] for p in json.loads(DEV_PAGES.read_text())["pages"])


def doc_stem(s: str) -> str:
    m = _STEM.search(str(s))
    return m.group() if m else ""


def why_forbidden(s: str) -> str | None:
    s = str(s).strip()
    st = doc_stem(s)
    if st in exam_stems():
        return "exam article (experiment 97 LOCKED_EVAL)"
    if locked_old.is_locked(s):
        return "locked journal (experiment 84)"
    if locked_old.is_locked_doc(s):
        return "locked old-print document (experiment 88)"
    if s[:4] in heldout_codes():
        return "held-out journal (experiment 76 split)"
    if st in devpage_stems():
        return "experiment 100/101 dev-page document"
    return None


def is_forbidden(s: str) -> bool:
    return why_forbidden(s) is not None


def assert_trainable(keys) -> int:
    """Raise if any key / stem is locked or held out; returns how many were checked.  Experiment 88's own assertion
    runs too (belt and braces: it is the lab's shared guard)."""
    keys = [keys] if isinstance(keys, str) else list(keys)
    locked_old.assert_not_locked(keys)
    bad = {}
    for k in keys:
        w = why_forbidden(k)
        if w:
            bad.setdefault(w, []).append(k)
    if bad:
        raise AssertionError("experiment 102 guard: " + "; ".join(f"{len(v)} {w}, e.g. {v[:3]}" for w, v in bad.items()))
    return len(keys)


def assert_sources(sources) -> int:
    n = 0
    for s in sources:
        n += 1
        low = str(s).lower()
        if s not in ALLOWED_SOURCES or any(w in low for w in FORBIDDEN_SOURCE_WORDS):
            raise AssertionError(f"experiment 102 guard: label source {s!r} is not allowed (OCRia-1 / experiment 100-101 "
                                 f"outputs are never targets; allowed: {sorted(ALLOWED_SOURCES)})")
    return n


def export(path=HERE / "forbidden102.json"):
    """The frozen list the host-side trainer checks (train102.guard): journal codes and document stems."""
    J = sorted(set(locked_old.locked_codes()) | set(heldout_codes()))
    Dd = sorted(set(locked_old.locked_docs()) | set(exam_stems()) | set(devpage_stems()))
    Path(path).write_text(json.dumps(dict(experiment=102, journal_codes=J, document_stems=Dd,
                                          note="exp 84 locked journals + exp 76 held-out journals; exp 88 locked documents "
                                               "+ exp 97 exam articles + exp 100/101 dev-page documents"), indent=0))
    return len(J), len(Dd)


if __name__ == "__main__":
    if sys.argv[1:] == ["export"]:
        print("forbidden102.json:", export())
    print(len(exam_stems()), "exam articles;", len(locked_old.locked_codes()), "locked journals;",
          len(locked_old.locked_docs()), "locked documents;", len(heldout_codes()), "held-out journals;",
          len(devpage_stems()), "dev-page documents")
