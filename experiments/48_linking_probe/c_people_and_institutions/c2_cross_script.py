"""C2b. One institution printed in Arabic, English and French: candidate pairs of org-level institutions of the 600 that
are still separate in platform v2 though they look like one body (same consonant skeleton of the distinctive words, after
dropping «جامعة / University / Université / of / de / ال»). The candidates are written out to be judged by reading."""
from __future__ import annotations

import json
import re
from collections import defaultdict

from common48c import OUT, mfold, progress, save

AR = dict(zip("ابتثجحخدذرزسشصضطظعغفقكلمنهةويىءئؤأإآ",
              ["", "b", "t", "t", "j", "h", "k", "d", "d", "r", "z", "s", "s", "s", "d", "t", "z", "", "g", "f", "k", "k",
               "l", "m", "n", "h", "", "", "", "", "", "", "", "", "", ""]))
GENERIC = {"جامعه", "الجامعه", "university", "universite", "universit", "universitaire", "of", "de", "du", "d", "the", "la",
           "le", "centre", "center", "مركز", "college", "كليه", "faculty", "faculte", "institute", "institut", "معهد",
           "national", "nationale", "et", "and", "و", "في", "ب", "عين", "ain"}


def skel(word: str) -> str:
    w = mfold(word).lower()
    if re.search("[؀-ۿ]", w):
        w = re.sub(r"^(ال|بال|وال)", "", w)
        s = "".join(AR.get(c, "") for c in w)
    else:
        w = re.sub(r"[^a-z]", "", w.replace("é", "e").replace("è", "e"))
        w = re.sub(r"^(al|el)(?=[a-z]{3})", "", w)
        for a, b in (("ph", "f"), ("kh", "k"), ("sh", "s"), ("ch", "s"), ("th", "t"), ("dh", "d"), ("gh", "g"),
                     ("ou", "w"), ("q", "k"), ("c", "k"), ("g", "j"), ("x", "ks")):
            w = w.replace(a, b)
        s = re.sub(r"[aeiouyw]", "", w)
    s = s.replace("g", "j")
    s = re.sub(r"h$", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


def core(name: str) -> tuple:
    toks = [t for t in re.split(r"[\s\-–,.'’()]+", mfold(name).lower()) if t and t not in GENERIC and not t.isdigit()]
    return tuple(sorted({skel(t) for t in toks if len(skel(t)) >= 2}))


def main():
    affs = json.load(open(OUT / "c2_affiliations.json"))
    orgs = defaultdict(lambda: dict(names=set(), n=0, stems=set()))
    for a in affs:
        for l in a["links"]:
            if l["level"] == "org":
                o = orgs[l["inst_id"]]
                o["names"] |= set(l["names"])
                o["n"] += 1
                o["stems"].add(a["stem"])
                o["kind"] = l["kind"]
                o["printed"] = a["printed"]
    by = defaultdict(set)
    for iid, o in orgs.items():
        for n in o["names"] or {o["printed"]}:
            c = core(n)
            if c:
                by[c].add(iid)
    cands = []
    for c, ids in by.items():
        if len(ids) > 1:
            cands.append(dict(skeleton=c, institutions=[dict(inst_id=i, names=sorted(orgs[i]["names"]), n_aff=orgs[i]["n"],
                                                               kind=orgs[i].get("kind")) for i in sorted(ids)]))
    save("c2_cross_script_candidates.json", cands)
    multi = sum(1 for o in orgs.values() if len({bool(re.search("[؀-ۿ]", n)) for n in o["names"]}) > 1)
    progress(f"- c2_cross_script.py: {len(cands)} candidate groups of separate org institutions; {multi} already hold both scripts")
    print(len(orgs), "org institutions;", multi, "hold Arabic+Latin names;", len(cands), "candidate groups")
    for c in cands:
        print(c["skeleton"], " || ".join(f"{x['inst_id']}:{x['names']}({x['n_aff']})" for x in c["institutions"]))


if __name__ == "__main__":
    main()
