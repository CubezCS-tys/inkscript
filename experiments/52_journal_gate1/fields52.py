"""Experiment 52: the fields prompt v3.5b added, counted in a masters folder's JATS (no calls).

    .venv/bin/python experiments/52_journal_gate1/fields52.py DIR/masters [--out FILE]
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from pathlib import Path

from lxml import etree

X = "{http://www.w3.org/1999/xlink}"


def count(folder: str) -> dict:
    C, arts, doc = Counter(), Counter(), Counter()
    fig_types = Counter()
    files = sorted(glob.glob(f"{folder}/*.jats.xml"))
    for f in files:
        t = etree.parse(f)
        r = t.getroot()
        seen = Counter()
        for s in r.iter("subj-group"):
            if s.get("subj-group-type") == "document-type":
                for sub in s.iter("subject"):
                    doc[(sub.text or "").strip()] += 1
                    seen["document_type"] += 1
        for cb in r.iter("contrib"):
            if cb.get("corresp") == "yes":
                seen["corresponding_author"] += 1
            for ci in cb.iter("contrib-id"):
                seen[f"contrib_id_{ci.get('contrib-id-type')}"] += 1
        for _ in r.iter("author-notes"):
            seen["author_notes"] += 1
        for ref in r.iter("ref"):
            pg = {p.get("person-group-type") for p in ref.iter("person-group")}
            if "editor" in pg:
                seen["refs_with_editor"] += 1
            if "translator" in pg:
                seen["refs_with_translator"] += 1
            if list(ref.iter("edition")):
                seen["refs_with_edition"] += 1
            if any(y.get("calendar") for y in ref.iter("year")):
                seen["refs_with_calendar_year"] += 1
            if any(p.get("content-type") == "cited-pages" for p in ref.iter("page-range")):
                seen["refs_with_cited_pages"] += 1
            if any(d.get("content-type") == "access-date" for d in ref.iter("date-in-citation")):
                seen["refs_with_access_date"] += 1
            for cm in ref.iter("comment"):
                if cm.get("content-type") in ("death-date", "shelfmark", "degree"):
                    seen[f"refs_with_{cm.get('content-type')}"] += 1
            for ec in ref.iter("element-citation", "mixed-citation"):
                if ec.get("publication-type") in ("manuscript", "conference", "thesis"):
                    seen[f"refs_type_{ec.get('publication-type')}"] += 1
        for tw in r.iter("table-wrap-foot"):
            for p in tw.iter("p"):
                if p.get("content-type") in ("table-note", "source"):
                    seen[f"table_{p.get('content-type')}"] += 1
        for fg in r.iter("fig"):
            if fg.get("fig-type"):
                fig_types[fg.get("fig-type")] += 1
            for p in fg.iter("p"):
                if p.get("content-type") in ("table-note", "source"):
                    seen[f"figure_{p.get('content-type')}"] += 1
        for fn in r.iter("fn"):
            if fn.get("fn-type") == "custom" and fn.get("custom-type"):
                seen[f"note_kind_{fn.get('custom-type')}"] += 1
        for _ in r.iter("conference"):
            seen["conference"] += 1
        for pr in r.iter("product"):
            seen[f"product_{pr.get('product-type')}"] += 1
        for ra in r.iter("related-article"):
            if ra.get("related-article-type") == "translated-from":
                seen["translated_from"] += 1
        for cm in r.iter("custom-meta"):
            n = cm.find("meta-name")
            if n is not None and n.text and any(k in n.text for k in ("series", "mark", "scan")):
                seen[f"custom_{n.text}"] += 1
        C.update(seen)
        arts.update({k: 1 for k in seen})
    return dict(masters=len(files), document_types=dict(doc.most_common()), figure_types=dict(fig_types.most_common()),
                counts=dict(sorted(C.items())), articles_with=dict(sorted(arts.items())))


if __name__ == "__main__":
    R = count(sys.argv[1])
    if "--out" in sys.argv:
        Path(sys.argv[sys.argv.index("--out") + 1]).write_text(json.dumps(R, ensure_ascii=False, indent=1))
    print(json.dumps(R, ensure_ascii=False, indent=1))
