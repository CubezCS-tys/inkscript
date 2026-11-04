"""Experiment 74: this experiment's model spend so far = (experiment 43's log - $127.387, its total at the start) + every
librarian spend log under out/<J>/lib/spend.jsonl. Prints the total, the room under the $400 cap, and the parts.

    python3 experiments/74_gate2_full/spend74.py [--json]
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG43 = HERE.parent / "43_rehearsal" / "out" / "gemini_spend.jsonl"
BASE43, CAP = 127.387, 400.0


def parts():
    t43 = sum((json.loads(l).get("usd") or 0) for l in open(LOG43) if l.strip())
    lib = {}
    for f in sorted(HERE.glob("out/*/lib/spend.jsonl")) + sorted(HERE.glob("out/lib*/spend.jsonl")):
        lib[str(f.relative_to(HERE))] = round(sum((json.loads(l).get("usd") or 0) for l in open(f) if l.strip()), 4)
    read = round(t43 - BASE43, 4)
    total = round(read + sum(lib.values()), 4)
    return dict(log43=round(t43, 4), reading=read, librarian=lib, total=total, room=round(CAP - total, 4),
                log43_abs_cap=round(BASE43 + CAP - sum(lib.values()), 4))


if __name__ == "__main__":
    p = parts()
    print(json.dumps(p, indent=1) if "--json" in sys.argv else
          f"exp 74 spend ${p['total']:.2f} of $400 (reading ${p['reading']:.2f}, librarian ${sum(p['librarian'].values()):.2f}); "
          f"room ${p['room']:.2f}; exp 43 log ${p['log43']:.3f} (absolute cap for it now ${p['log43_abs_cap']:.2f})")
