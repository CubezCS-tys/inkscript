"""Experiment 43, letter fix (2026-10-22): rebuild a run's masters from its saved answers with letters43's fix, into a
new folder, the way fix round 3 did (out/v33_300b_fix3/build3.sh). No calls. rules43.py is not edited: the fix is
added at run time, after table_missed_cells (the last rule before the fix count), in this process only.

    lettersfix43.py plain --run v33_300 --set b --dst out/v33_300_final_lettersfix/plain [--off] [--stems ...]
        the answers through today's rules (+ the letter fix unless --off) -> DST/rules, DST/masters, DST/letters.json
    lettersfix43.py validate DIR/masters      JATS DTD + ALTO XSD of every master
then patches43.py build --run <run> --src DST/rules --out <folder> applies the run's patches (see lettersfix.sh).
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import masters43 as M43  # noqa: E402
import pictures43 as PIC  # noqa: E402
import rules43 as RU  # noqa: E402
import letters43 as LT  # noqa: E402
from masters43 import ST  # noqa: E402

LOG = {"letters": [], "letters_foreign": []}


def install():
    orig = RU.table_missed_cells

    def table_missed_cells_then_letters(ans, lines, words, log):
        orig(ans, lines, words, log)
        LT.letters_fix(ans, lines, log)
        LOG["letters"] += [dict(e, chunk=_cur[0]) for e in log["letters"]]
        LOG["letters_foreign"] += [dict(e, chunk=_cur[0]) for e in log["letters_foreign"]]
    RU.table_missed_cells = table_missed_cells_then_letters


_cur = [None]


def lean():
    """One article at a time in memory: structure's Azure cache emptied after each master (a 300-article build
    otherwise holds every Azure JSON, ~2 GB)."""
    orig = M43.build43

    def build43(a, *k, **kw):
        _cur[0] = a["stem"]
        try:
            return orig(a, *k, **kw)
        finally:
            ST._az.clear()
    M43.build43 = build43
    orig_rules = PIC.RP.apply_rules

    def apply_rules(a, rec):
        _cur[0] = a["stem"]
        return orig_rules(a, rec)
    PIC.RP.apply_rules = apply_rules


def cmd_plain(a):
    lean()
    if not a.off:
        install()
    dst = Path(a.dst).resolve()
    PIC.build(a.run, a.raw, dst, a.stems, a.set)
    if not a.off:
        c = Counter(k for e in LOG["letters"] if e["placed"] for k in e["kinds"])
        (dst / "letters.json").write_text(json.dumps(dict(kinds=dict(c), words=len(LOG["letters"]), **LOG),
                                                     ensure_ascii=False, indent=0), encoding="utf-8")
        print("letters:", dict(c), "words", sum(e["placed"] for e in LOG["letters"]),
              "unplaced", sum(not e["placed"] for e in LOG["letters"]), "lines left", len(LOG["letters_foreign"]))


def cmd_validate(a):
    from inkscript.enrich.schemas import validate_alto, validate_jats
    js = sorted(glob.glob(f"{a.dir}/*.jats.xml"))
    bad = [f for f in js if validate_jats(f)] + [f for f in glob.glob(f"{a.dir}/*.alto.xml") if validate_alto(f)]
    print(f"{len(js)} masters; invalid: {bad if bad else 'none'}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plain")
    p.add_argument("--run", required=True)
    p.add_argument("--raw", default="raw")
    p.add_argument("--set", required=True, choices=["a", "b", "c", "d", "e", "f", "g"])   # a: v2_55, e: the v3.6 check (experiment 65)
    p.add_argument("--dst", required=True)
    p.add_argument("--stems", nargs="*")
    p.add_argument("--off", action="store_true", help="control: today's code without the letter fix")
    v = sp.add_parser("validate")
    v.add_argument("dir")
    a = ap.parse_args()
    {"plain": cmd_plain, "validate": cmd_validate}[a.cmd](a)


if __name__ == "__main__":
    main()
