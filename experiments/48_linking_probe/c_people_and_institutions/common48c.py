"""Probe C (people and institutions), experiment 48: shared read-only connections and name helpers.

Nothing here writes to platform_v2.db, marc.db or the heading-key index; all three are opened read-only."""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = REPO / "experiments" / "48_linking_probe" / "out" / "c_people_and_institutions"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO / "experiments" / "47_platform_v2"))
sys.path.insert(0, str(REPO / "experiments" / "45_marc_db"))
from common47 import (akey, heading_display, heading_key, key, latin_key, name_key, split_life,  # noqa: E402,F401
                      split_titles)
from build45 import fold as mfold  # noqa: E402  (the fold marc.db's name_folded was built with)

PDB = "file:/home/appuser/data/platform_v2/platform_v2.db?mode=ro"
MDB = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
HOLD = "file:/home/appuser/data/platform_v2/marc_heading_keys47_afd08d1c91d88dff.sqlite?mode=ro"
RUNS600 = ("v33_300_final", "v33_300b_fix3")


def _c(uri):
    c = sqlite3.connect(uri, uri=True)
    c.row_factory = sqlite3.Row
    return c


def pcon():
    return _c(PDB)


def mcon():
    return _c(MDB)


def hcon():
    return _c(HOLD)


def save(name: str, obj) -> Path:
    p = OUT / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return p


def progress(line: str):
    with open(OUT / "progress.md", "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(c - h, 3), round(c + h, 3)]


def is_arab(s: str | None) -> bool:
    return bool(re.search("[؀-ۿ]", s or ""))


def given_surname(printed: str) -> tuple[str | None, str | None]:
    """«د. محمد أحمد الغنام» -> ('محمد', 'الغنام'); «Ahmed, M.» -> ('m', 'ahmed'); compounds «عبد الله» kept whole."""
    _, s = split_titles(printed or "")
    s, _ = split_life(s)
    if re.search("[،,]", s):                    # «Surname, Given»
        a, b = re.split(r"\s*[،,]\s*", s, maxsplit=1)
        s = f"{b} {a}"
    toks = [t for t in re.split(r"[\s.]+", s) if t]
    if not toks:
        return None, None
    if is_arab(s):
        toks = [mfold(t) for t in toks]
    else:
        toks = [latin_key(t) for t in toks]
        toks = [t for t in toks if t]
    if not toks:
        return None, None
    g = toks[0]
    if g in ("عبد", "ابو", "abd", "abdel", "abdul") and len(toks) > 2:
        g = g + toks[1]
    sur = toks[-1] if len(toks) > 1 else None
    return g, sur


def loose_holders(m, given: str | None, sur: str | None) -> set:
    """Authority ids whose Arabic heading is «surname، given…» (with and without «ال» on the surname): every person
    the catalogue knows who could be printed as «given … surname». Indexed range queries on name_folded only."""
    if not given or not sur or not is_arab(sur):
        return set()
    out = set()
    surs = {sur, sur[2:] if sur.startswith("ال") and len(sur) > 4 else "ال" + sur}
    givens = {given}
    if given.startswith("عبد") and len(given) > 3:
        givens.add("عبد " + given[3:])
    for s_ in surs:
        for g_ in givens:
            lo = f"{s_}، {g_}"
            for aid, nf in m.execute("SELECT DISTINCT authority_id, name_folded FROM authors WHERE name_folded >= ? AND "
                                     "name_folded < ? AND authority_id IS NOT NULL AND authority_id <> '' AND "
                                     "NOT coalesce(is_org,0)", (lo, lo + "￿")):
                if len(nf) == len(lo) or nf[len(lo)] in " ،,":
                    out.add(aid)
    return out


def exact_holders(h, keys) -> dict:
    keys = sorted({k for k in keys if k})
    out = {}
    for i in range(0, len(keys), 500):
        part = keys[i:i + 500]
        for k, aid in h.execute(f"SELECT key, authority_id FROM k WHERE key IN ({','.join('?' * len(part))})", part):
            out.setdefault(k, set()).add(aid)
    return out


def latin_loose_holders(h, given: str | None, sur: str | None) -> set:
    """Latin: authority ids with a Latin heading key «given…surname» (prefix range on the heading-key index, then the
    surname must end the key). «M. Ahmed» -> every «m…ahmed» (Mohamed Ahmed, Mahmoud Ahmed, …)."""
    if not given or not sur or is_arab(sur):
        return set()
    out = set()
    for k, aid in h.execute("SELECT key, authority_id FROM k WHERE key >= ? AND key < ?", (given, given + "￿")):
        if k.endswith(sur) and len(k) > len(sur):
            out.add(aid)
    return out
