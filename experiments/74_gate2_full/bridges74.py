"""Experiment 74: gate 2's question across the loaded gate-2 journals, on a release DB (read-only; experiment 70's
measure70.base / cross / shared, unchanged).

    bridges74.py --db RELEASE.db [--journals 0130,0165,...] [--out out/bridges74.json] [--one J]

For every ordered pair of journals (A -> B): references of A whose card has an accepted best link to a B publication
(and to a B article read here); for every pair: shared byline authors, shared institutions (org level), shared cited
works, coupling edges. Baseline: each journal against 20 random sets of the same size from the random 600 (seed
7474): the same shared measures. Network density: the share of ordered pairs with at least one citation, and with
shared authors / works above the random baseline. Inside each journal: its own citations and held share.
--one J prints J's line for the owner (bridges of J with the others)."""
from __future__ import annotations
import argparse, json, random, sys
from collections import defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "70_gate2_pilot"))
import measure70 as M  # noqa: E402

ALL = ["0130", "0165", "0011", "0523", "1001", "0246", "1182", "0097", "0840", "0013"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--journals", default=",".join(ALL))
    ap.add_argument("--out", default=str(HERE / "out" / "bridges74.json"))
    ap.add_argument("--one")
    ap.add_argument("--draws", type=int, default=20)
    a = ap.parse_args()
    B = M.base(a.db)
    cur = B["cur"]
    sets = {}
    for j in a.journals.split(","):
        S = {v["pub_id"] for v in cur.values() if v["journal_id"] == "J" + j}
        if S:
            sets[j] = S
    R = sorted({v["pub_id"] for v in cur.values() if v["run"] in M.R_RUNS and v["journal_id"] not in
                {"J" + j for j in ALL}})
    js_ = sorted(sets)
    out = dict(db=a.db, sizes={j: len(S) for j, S in sets.items()}, random_pool=len(R))
    cites, inside = {}, {}
    for x in js_:
        c = M.cross(B, sets[x], sets[x], "J" + x, None)
        inside[x] = dict(references=c.get("references", 0), held=c.get("held", 0),
                         held_share=round(c.get("held", 0) / max(1, c.get("references", 0)), 4),
                         self_citations=c.get("to_journal", 0), self_to_read=c.get("to_read_article", 0))
        for y in js_:
            if x != y:
                c = M.cross(B, sets[x], sets[y], "J" + y, None)
                cites[f"{x}->{y}"] = dict(refs=c.get("to_journal", 0), to_read=c.get("to_read_article", 0))
    sh, base = {}, {}
    rnd = random.Random(7474)
    for x in js_:
        rows = defaultdict(list)
        for _ in range(a.draws):
            S = set(rnd.sample(R, min(len(sets[x]), len(R))))
            for y in js_:
                if y != x:
                    pass
            s = M.shared(B, S, set().union(*[sets[y] for y in js_ if y != x]) if len(js_) > 1 else set())
            for k, v in s.items():
                rows[k].append(v)
        base[x] = {k: round(sum(v) / len(v), 2) for k, v in rows.items()}
        for y in js_:
            if x < y:
                sh[f"{x}|{y}"] = M.shared(B, sets[x], sets[y])
    # each journal against all the other gate-2 journals together, and the random sets of its size against the same
    vs_rest = {}
    for x in js_:
        rest = set().union(*[sets[y] for y in js_ if y != x]) if len(js_) > 1 else set()
        vs_rest[x] = dict(observed=M.shared(B, sets[x], rest), random_mean=base[x])
    pairs = [(x, y) for x in js_ for y in js_ if x != y]
    dens = dict(ordered_pairs=len(pairs), with_citation=sum(1 for x, y in pairs if cites[f"{x}->{y}"]["refs"] > 0),
                unordered_pairs=len(sh), with_shared_author=sum(1 for v in sh.values() if v["authors"] > 0),
                with_shared_work=sum(1 for v in sh.values() if v["cited_works"] > 0))
    dens["citation_density"] = round(dens["with_citation"] / max(1, len(pairs)), 3)
    out.update(inside=inside, citations=cites, shared=sh, vs_rest=vs_rest, density=dens)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    if a.one:
        x = a.one
        cto = sorted(((cites[f"{x}->{y}"]["refs"], y) for y in js_ if y != x), reverse=True)
        cfrom = sorted(((cites[f"{y}->{x}"]["refs"], y) for y in js_ if y != x), reverse=True)
        o = vs_rest[x]
        print(f"cites {sum(n for n, _ in cto)} refs to the others (" + ", ".join(f"{y}:{n}" for n, y in cto if n) +
              f"), cited {sum(n for n, _ in cfrom)} times by them; shared with the rest: authors {o['observed']['authors']}"
              f" (random {o['random_mean']['authors']}), cited works {o['observed']['cited_works']} (random "
              f"{o['random_mean']['cited_works']}), institutions {o['observed']['institutions']} (random "
              f"{o['random_mean']['institutions']})")
    else:
        print(json.dumps(dict(sizes=out["sizes"], density=dens, inside=inside), indent=1))


if __name__ == "__main__":
    main()
