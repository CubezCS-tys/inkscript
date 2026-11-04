"""Experiment 65: the identifiers code found on every line of the rebuilt runs (<stem>.ids.json), counted by kind,
owner, check and JATS home; plus the new JATS fields counted in the masters. -> out/ids_summary.json, printed.

    ids65.py [run ...]      (default: the four *_fix61 runs)
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
OUT43 = HERE.parent / "43_rehearsal" / "out"
RUNS = ["j0130_final_fix61", "v2_55_fix61", "v33_300b_fix3_lettersfix_fix61", "v33_300_final_lettersfix_fix61"]
XL = "{http://www.w3.org/XML/1998/namespace}lang"


def main():
    runs = sys.argv[1:] or RUNS
    found, homes, arts = Counter(), Counter(), defaultdict(set)
    fields, farts = Counter(), defaultdict(set)
    for run in runs:
        for f in sorted((OUT43 / run / "masters").glob("*.ids.json")):
            stem = f.name[:-len(".ids.json")]
            for x in json.loads(f.read_text(encoding="utf-8"))["ids"]:
                ow = (x.get("owner") or {}).get("kind") or "none"
                found[(x["kind"], ow, "valid" if x["valid"] else "fails its check")] += 1
                arts[(x["kind"], ow)].add(stem)
                if x.get("jats_id"):
                    homes[(x["kind"], x.get("home"))] += 1
            root = etree.parse(str(OUT43 / run / "masters" / f"{stem}.jats.xml")).getroot()
            am = root.find("front/article-meta")

            def n(key, k=1):
                if k:
                    fields[key] += k
                    farts[key].add(stem)
            for c in am.iter("contrib"):
                n("role position", sum(1 for r in c.findall("role") if r.get("content-type") == "position"))
                n("role role-phrase", sum(1 for r in c.findall("role") if r.get("content-type") == "role-phrase"))
                n("aff in the twin's script (xml:lang)", sum(1 for a in c.findall("aff") if a.get(XL)))
                n("  of which linked to the aff it translates (rid)", sum(1 for a in c.findall("aff") if a.get("rid")))
                n("printed name with <prefix> (honorific)", sum(1 for s in c.iter("string-name") if s.find("prefix") is not None))
                n("name printed again in the other script", sum(1 for s in c.iter("string-name")
                                                                 if s.get("specific-use") == "printed-again"))
                n("xref to a byline printed again", sum(1 for x in c.findall("xref") if x.get("specific-use") == "printed-again"))
                n("contrib-id (ORCID)", sum(1 for x in c.findall("contrib-id") if x.get("contrib-id-type") == "orcid"))
            n("article-id doi", sum(1 for x in am.findall("article-id") if x.get("pub-id-type") == "doi"))
            n("subtitle in the printed title (M5)", sum(1 for x in am.iter("subtitle") if x.get("specific-use") == "in-printed-title"))
            n("journal section (subj-group heading)", sum(1 for x in am.iter("subj-group") if x.get("subj-group-type") == "heading"))
            pm = am.find("permissions")
            n("permissions (licence / copyright)", len(pm) if pm is not None else 0)
            for cm in am.iter("custom-meta"):
                nm = (cm.findtext("meta-name") or "").strip()
                if nm in ("how-to-cite", "signature"):
                    n(f"custom-meta {nm}")
            jm = root.find("front/journal-meta")
            n("journal-meta issn printed", sum(1 for x in jm.findall("issn") if x.get("specific-use") == "printed"))
    out = dict(found={" | ".join(k): v for k, v in sorted(found.items())},
               found_articles={" | ".join(k): len(v) for k, v in sorted(arts.items())},
               homes={" | ".join(map(str, k)): v for k, v in sorted(homes.items())},
               fields={k: [v, len(farts[k])] for k, v in fields.items()})
    (HERE / "out" / "ids_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("identifiers found (kind | owner | check): count")
    for k, v in out["found"].items():
        print(f"  {k}: {v}")
    print("written into the JATS (kind | home): count")
    for k, v in out["homes"].items():
        print(f"  {k}: {v}")
    print("new JATS fields: count (articles)")
    for k, (v, a) in out["fields"].items():
        print(f"  {k}: {v} ({a})")


if __name__ == "__main__":
    main()
