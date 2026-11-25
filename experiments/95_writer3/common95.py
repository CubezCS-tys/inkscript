"""Experiment 95: shared paths, guards and small helpers.  Experiment 87's modules are imported, never edited.

Guards (asserted wherever data is selected): no split76 held-out journal is ever fitted or learned on; no locked
journal (exp 84) or locked old-print document (exp 88) is used at all.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
E87 = Path(os.environ.get("E87", E / "87_writer"))       # on the GPU host: /work (87's code sits beside ours)
sys.path.insert(0, str(E87))
D87 = Path(os.environ.get("DATA87", E87 / "out/data"))
D95 = Path(os.environ.get("DATA95", OUT / "data"))
PROG95 = Path(os.environ.get("PROG95", OUT / "programs"))   # 87's letter programs + the glyphs our new texts need


def _guards():
    """(split76 test journal codes, is_locked_any) — on the GPU host the lists travel as a json (no locked files)."""
    g = D95 / "guards.json"
    if (E / "76_finetune_pilot/out/split76.json").exists() and (E / "88_truth_and_lock/locked_old.py").exists():
        test = set(json.loads((E / "76_finetune_pilot/out/split76.json").read_text())["test"])
        sys.path.insert(0, str(E / "88_truth_and_lock"))
        from locked_old import is_locked_any
        return test, is_locked_any
    test = set(json.loads(g.read_text())["test"])
    return test, (lambda s: False)                       # the host only ever gets data already checked here


TEST76, is_locked_any = _guards()


def assert_pool(keys, what="pool"):
    """Training-pool data: no held-out journal, nothing locked."""
    keys = list(keys)
    bad = [k for k in keys if str(k)[:4] in TEST76]
    assert not bad, f"{what}: {len(bad)} held-out (split76) items, e.g. {bad[:3]}"
    assert_unlocked(keys, what)
    return len(keys)


def assert_unlocked(keys, what="data"):
    bad = [k for k in keys if is_locked_any(str(k))]
    assert not bad, f"{what}: {len(bad)} LOCKED items, e.g. {bad[:3]}"
    return len(keys)


def use_programs():
    """Point 87's writer at our program folder (87's programs plus the glyphs our new texts need)."""
    import writer87 as W
    if PROG95.exists() and any(PROG95.glob("font_*.json")):
        W.PROG = PROG95
    W.font_lib.cache_clear()
    W.aq_chars.cache_clear()
    return W


# AlQalam's shaping (87's RASM) knows the Arabic letters only; Persian / presentation code points that print the
# same are mapped to them before writing (the fonts' HarfBuzz shaping needs no map).
_AQ_MAP = {"ک": "ك", "ھ": "ه", "ہ": "ه", "ۀ": "ه", "ي": "ي", "ى": "ى", "ؠ": "ي", "ٹ": "ت", "ﻻ": "لا"}


def aq_text(t: str) -> str:
    out = []
    ws = t.split(" ")
    for w in ws:
        s = []
        for j, ch in enumerate(w):
            if ch == "ی":                                # Persian yeh: no dots at the end of a word, dots inside
                nxt = w[j + 1] if j + 1 < len(w) else ""
                s.append("ى" if not ("ء" <= nxt <= "ي") else "ي")
            else:
                s.append(_AQ_MAP.get(ch, ch))
        out.append("".join(s))
    return " ".join(out)


def norm_ws(t: str) -> str:
    return " ".join((t or "").split())


def text_for(lib: str, t: str) -> str:
    t = norm_ws(t)
    return aq_text(t) if lib == "alqalam" else t


def jl(p):
    p = Path(p)
    return [json.loads(l) for l in open(p, encoding="utf-8")] if p.exists() else []


def device():
    import torch
    if torch.cuda.is_available():
        return "cuda"
    torch.set_num_threads(int(os.environ.get("THREADS", 2)))
    return "cpu"
