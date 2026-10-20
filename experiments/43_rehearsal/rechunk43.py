"""Experiment 43: a chunk that failed with MAX_TOKENS asked again in smaller chunks (code only; no model calls here).

    rechunk43.py --run v33_300 [--pages 3] [--stems ...]   every MAX_TOKENS failure of the run (out/<run>/raw/
                                                           *.failed.json) cut into chunks of <= --pages pages:
                                                           out/rechunk43.json {stem: {"chunks": [[x, y], ...],
                                                           "max_out": 32768, "why", "run", "date"}}
    rechunk43.py --show                                    the map

install(ST) (called by masters43 and run43 at import) makes experiment 41's ST.chunks(a) return the map's chunks for
those articles, so run43 asks for the new chunks (a later chunk still gets the previous chunk's answer: state_for),
and the rules, masters, flags and views read them like any other chunk. The failed answer stays as it was
(<stem>_cAAA-BBB.failed.json); its chunk name is no longer asked for.

1764-003-005-006 pages 9-15 (the 300, 2026-10-19/20): 531 one-line table cells, the answer pretty-printed, ran into
its 27,000-token limit twice. Command to ask again (owner's approval and a cap first; ~3 requests, ~$0.15 on Batch):
    .venv/bin/python experiments/43_rehearsal/rechunk43.py --run v33_300 --stems 1764-003-005-006
    .venv/bin/python experiments/43_rehearsal/run43.py --set b --prompt v3.3 --run v33_300 --stems 1764-003-005-006 \\
        --cap <logged spend + 1>
(prompt v3.4's "compact JSON" line would make the answers smaller still.) The map is written only by that first
command (a preview, made 2026-10-20 and not installed: out/fixes2/rechunk43_1764_preview.json: 1-8 | 9-11, 12-14, 15).
A dry run (run43.py --dry-run) writes out/<run>/dry_run.json: give it another --run name to keep the run's own.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
MAP = OUT / "rechunk43.json"
BATCH_MAX_OUT = 32768


def load() -> dict:
    try:
        return json.loads(MAP.read_text(encoding="utf-8")) if MAP.exists() else {}
    except (OSError, ValueError):
        return {}


def install(ST):
    """Wrap ST.chunks once: an article in the map gets the map's chunks."""
    if getattr(ST.chunks, "_rechunk43", False):
        return
    orig = ST.chunks

    def chunks(a):
        m = load().get(a.get("stem"))
        if m and m.get("chunks") and m["chunks"][0][0] == a["first"] and m["chunks"][-1][1] == a["last"]:
            return [tuple(c) for c in m["chunks"]]
        return orig(a)
    chunks._rechunk43 = True
    chunks.orig = orig
    ST.chunks = chunks


def max_out_for(a: dict, x: int, y: int) -> int | None:
    """The output limit for a chunk the map made (None: the run's usual one)."""
    m = load().get(a.get("stem"))
    if m and [x, y] in [list(c) for c in m.get("chunks") or []] and [x, y] not in [list(c) for c in m.get("kept") or []]:
        return int(m.get("max_out") or BATCH_MAX_OUT)
    return None


def split(x: int, y: int, n: int) -> list[list[int]]:
    pages = y - x + 1
    k = -(-pages // n)
    size = -(-pages // k)
    out, p = [], x
    while p <= y:
        out.append([p, min(y, p + size - 1)])
        p = out[-1][1] + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    m = load()
    if a.show or not a.run:
        print(json.dumps(m, ensure_ascii=False, indent=1))
        return
    import sys
    sys.path.insert(0, str(HERE))
    import masters43  # noqa: F401  (experiment 41's paths)
    import structure as ST
    import run43
    arts = {x["stem"]: x for w in ("a", "b", "c") for x in (run43.articles(w) if Path(run43.SETS[w][1]).exists() else [])}
    for f in sorted((OUT / a.run / "raw").glob("*.failed.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        stem = rec.get("stem") or f.name.split("_c")[0]
        if a.stems and stem not in a.stems or "MAX_TOKENS" not in str(rec.get("finish")) or stem not in arts:
            continue
        art = arts[stem]
        old = [list(c) for c in getattr(ST.chunks, "orig", ST.chunks)(art)]
        x, y = rec["first"], rec["last"]
        if [x, y] not in old:
            print(f"{stem}: chunk {x}-{y} is not one of {old}; skipped")
            continue
        new = []
        for c in old:
            new += split(x, y, a.pages) if c == [x, y] else [c]
        m[stem] = dict(chunks=new, kept=[c for c in old if c != [x, y]], max_out=BATCH_MAX_OUT, run=a.run,
                       why=f"pages {x}-{y} hit MAX_TOKENS ({rec.get('tout')} output tokens)",
                       date=time.strftime("%Y-%m-%d"))
        print(f"{stem}: {old} -> {new}")
    MAP.parent.mkdir(parents=True, exist_ok=True)
    MAP.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"-> {MAP}")


if __name__ == "__main__":
    main()
