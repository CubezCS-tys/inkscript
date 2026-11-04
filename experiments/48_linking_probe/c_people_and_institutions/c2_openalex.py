"""C2c. Do OpenAlex institutions (ROR-based) cover Arab universities? 50 universities that the 600's affiliations reach
(seeded, seed 4824) are searched by name (every name form we hold: Arabic, English, French), plus one aggregate call
counting OpenAlex institutions per Arab country. Every call is logged (external_calls.jsonl) and cached; every result
is marked source "openalex". Stops at the first refusal (429) rather than retrying: the free budget is shared per IP.

Run: .venv/bin/python c2_openalex.py   -> out/c_people_and_institutions/c2_openalex.json (to be judged by reading)."""
from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict

from common48c import OUT, progress, save
from openalex48c import get

ARAB = "DZ|BH|KM|DJ|EG|IQ|JO|KW|LB|LY|MR|MA|OM|PS|QA|SA|SO|SD|SY|TN|AE|YE"
SEL = "id,display_name,ror,country_code,type,display_name_alternatives,display_name_acronyms,works_count"


def main():
    affs = json.load(open(OUT / "c2_affiliations.json"))
    unis = defaultdict(set)
    for a in affs:
        for l in a["links"]:
            if l["level"] == "org" and l["kind"] == "university":
                unis[l["inst_id"]] |= set(l["names"]) or {a["org_text"] or a["printed"]}
    ids = sorted(unis)
    rnd = random.Random(4824)
    pick = rnd.sample(ids, min(50, len(ids)))
    out = dict(source="openalex", countries=None, items=[])
    cp = OUT / "c2_openalex.json"
    if cp.exists():
        out = json.loads(cp.read_text())
    if out.get("countries") is None:
        d = get("institutions", {"filter": f"country_code:{ARAB}", "group_by": "country_code"},
                "C2: how many OpenAlex institutions each Arab country has (one aggregate call)")
        if d is None:
            save("c2_openalex.json", out)
            sys.exit("OpenAlex refused the first call (see external_calls.jsonl); stopping, nothing retried")
        out["countries"] = d.get("group_by")
        d2 = get("institutions", {"filter": f"country_code:{ARAB},type:education", "group_by": "country_code"},
                 "C2: OpenAlex education-type institutions per Arab country (one aggregate call)")
        out["countries_education"] = d2.get("group_by") if d2 else None
    done = {x["inst_id"] for x in out["items"]}
    for iid in pick:
        if iid in done:
            continue
        rec = dict(inst_id=iid, names=sorted(unis[iid]), searches=[], source="openalex")
        for n in sorted(unis[iid], key=lambda x: (bool(re.search("[؀-ۿ]", x)), x))[:2]:
            d = get("institutions", {"search": n, "per-page": 3, "select": SEL},
                    f"C2: OpenAlex institution search for an affiliation's university name (platform v2 {iid})")
            if d is None:
                out["items"].append(rec)
                save("c2_openalex.json", out)
                sys.exit("OpenAlex refused a call; stopping (resume later: cached calls are not repeated)")
            rec["searches"].append(dict(query=n, count=d["meta"]["count"],
                                        top=[dict(id=r["id"], name=r["display_name"], ror=r["ror"], cc=r["country_code"],
                                                  type=r["type"], works=r["works_count"],
                                                  alts=(r.get("display_name_alternatives") or [])[:5])
                                             for r in d["results"]]))
        out["items"].append(rec)
        save("c2_openalex.json", out)
    progress(f"- c2_openalex.py: {len(out['items'])} universities searched in OpenAlex")
    print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
