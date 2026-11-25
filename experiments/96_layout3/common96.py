"""Experiment 96 (layout, stage 3): shared pieces.  Imports experiment 94's common94 (which imports experiment 92's
common92: paths, guards, Argon, Azure, geometry), never edits them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
E94 = E / "94_layout2"
O94 = E94 / "out"
sys.path.insert(0, str(E94))
import common94 as C94  # noqa: E402
from common94 import (E92, FINE, RAWS, TO_COARSE, AFF_WORDS, area, assert_not_locked, azure_lines, fixpath,  # noqa: E402,F401
                      heldout_codes, inter, iou, is_locked_any, kendall_tau, norm, page_is_rtl)

MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"


def test_docs() -> set[str]:
    return {json.loads(l)["stem"] for l in open(E92 / "pages92.jsonl", encoding="utf-8")}


def inventory_azure() -> dict[str, str]:
    az = {}
    for l in open(E / "76_finetune_pilot/out/inventory76.jsonl", encoding="utf-8"):
        a = json.loads(l)
        az.setdefault(a["stem"], str(fixpath(a["azure"])))
    return az


def guard_training(stems_or_keys, jcodes=None):
    """Every training input: not locked (both guards), not a held-out journal, not a test document."""
    ks = list(stems_or_keys)
    assert_not_locked(ks)
    held, td = heldout_codes(), test_docs()
    assert not {k[:4] for k in ks} & held, "held-out journal in training"
    assert not {k.split("_p")[0] for k in ks} & td, "test document in training"
