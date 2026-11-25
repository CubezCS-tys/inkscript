#!/usr/bin/env python3
"""Self-test of score97.py (no real keys involved): writes fake keys into out/selftest/keys/<PART>/{A,B}/ where
A = the pipeline's own output in key format (so pipeline vs A must score 100%) and B = A with known damage, then runs
the scorer on them with EXP97_KEYS / EXP97_SCORES pointing into out/selftest.  Checks the numbers that must hold.
Run:  nice -n 19 python3 selftest97.py
"""
import copy
import json
import os
import random
import re
import subprocess
import sys

from common97 import ARTS, OUT, jdump
import score97 as S

ST = f"{OUT}/selftest"
K = f"{ST}/keys"
rnd = random.Random(5)


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items() if not k.startswith("_") and k not in ("unordered",)}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x


arts = ARTS[:12]
n_damage = dict(roles=0, merges=0, titles=0, cells=0)
for a in arts:
    s = a["stem"]
    for kind, pg in a["pages"].items():
        A = S.pipeline_page(s, pg)
        # pipeline regions are pieces in the key too; keep them, but in the key's order (by ord then lines)
        A = clean(A)
        A["columns"] = 1
        # rulings: accept-either roles and unsure pieces must not cost the pipeline anything
        for p in A["pieces"]:
            if p["role"] == "abstract" and not n_damage.get("label_of"):
                p["role"], p["label_of"] = "heading", "abstract"; n_damage["label_of"] = 1
            elif p["role"] == "front-matter" and not n_damage.get("byline"):
                p["role"] = "byline"; n_damage["byline"] = 1
            elif p["role"] == "paragraph" and not n_damage.get("unsure_piece"):
                p["role"], p["unsure"] = "equation", True; n_damage["unsure_piece"] = 1
        B = copy.deepcopy(A)
        for p in B["pieces"]:
            if p["role"] == "paragraph" and rnd.random() < 0.2:
                p["role"] = "quote"
                n_damage["roles"] += len(p["lines"])
        if len(B["pieces"]) > 3:                          # merge two neighbouring pieces in B
            i = 1
            B["pieces"][i]["lines"] += B["pieces"][i + 1]["lines"]
            del B["pieces"][i + 1]
            n_damage["merges"] += 1
        jdump(A, f"{K}/PAGE/A/{s}_p{pg:03d}.json"); jdump(B, f"{K}/PAGE/B/{s}_p{pg:03d}.json")
        if kind == "table":
            T = clean(S.pipeline_tab(s, pg))
            jdump(T, f"{K}/TAB/A/{s}_p{pg:03d}.json")
            T2 = copy.deepcopy(T)
            if T2["tables"] and T2["tables"][0].get("cells"):
                g = T2["tables"][0]["cells"]
                g[0][0] += "x"                                 # different letters
                n_damage["cells"] += 1
                for row in g:                                  # a numeric cell typed with its minus on the other side
                    for c, v in enumerate(row):
                        if v and S.cell_fold(v).startswith("#") and not n_damage.get("sign_moved_" + s):
                            row[c] = (v.strip() + " -") if not v.strip().startswith("-") else v.strip()[1:] + "-"
                            n_damage["sign_moved_" + s] = 1
                if len(g) > 4 and not n_damage.get("row_shift"):  # one table with a row shifted down by one
                    g.insert(2, [""] * len(g[2]))
                    g.pop()
                    n_damage["row_shift"] = 1
            jdump(T2, f"{K}/TAB/B/{s}_p{pg:03d}.json")
        if kind == "refs":
            R = clean(S.pipeline_refs(s, pg))
            for r in R["references"]:                      # the key writes authors as printed strings
                r["authors"] = [" ".join(x) for x in r.get("authors") or []]
            jdump(R, f"{K}/REFS/A/{s}_p{pg:03d}.json")
            R2 = copy.deepcopy(R)
            for r in R2["references"]:                     # a range typed in the other order: same numbers
                m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", (r.get("pages") or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
                if m and not n_damage.get("pages_reversed"):
                    r["pages"] = f"{m.group(2)}-{m.group(1)}"; n_damage["pages_reversed"] = 1
            jdump(R2, f"{K}/REFS/B/{s}_p{pg:03d}.json")
    F = clean(S.pipeline_front(s))
    for au in F["authors"]:
        au.pop("name_text", None)
    jdump(F, f"{K}/FRONT/A/{s}.json")
    F2 = copy.deepcopy(F)
    if F2["titles"]:
        F2["titles"][0]["text"] = F2["titles"][0]["text"] + "ـ"           # tatweel: exact differs, folded equal
        n_damage["titles"] += 1
        if len(F2["titles"]) > 1 and not n_damage.get("title_extra"):
            F2["titles"][1]["text"] += " plus words that ran in"            # part extra
            n_damage["title_extra"] = 1
    jdump(F2, f"{K}/FRONT/B/{s}.json")
    jdump(clean(S.pipeline_sect(s)), f"{K}/SECT/A/{s}.json")
# a broken file must be tolerated
open(f"{K}/PAGE/A/broken.json", "w").write("{not json")

# R1: two fake blind readers who both type Azure's line (so Azure is right by construction) except one line
priv = {d["id"]: d["witnesses"] for d in map(json.loads, open(f"{OUT}/reading/private/dispute_witnesses.jsonl"))}
disp = [json.loads(x) for x in open(f"{OUT}/reading/disputes.jsonl")]
os.makedirs(f"{ST}/settle/A", exist_ok=True); os.makedirs(f"{ST}/settle/B", exist_ok=True)
with open(f"{ST}/settle/A/readings.jsonl", "w") as fa, open(f"{ST}/settle/B/readings.jsonl", "w") as fb:
    for n, d in enumerate(disp):
        t = d["candidates"][priv[d["id"]]["azure"]]["text"]
        fa.write(json.dumps(dict(id=d["id"], printed=t, unsure=False)) + "\n")
        fb.write(json.dumps(dict(id=d["id"], printed=t + (" xx" if n in (0, 1, 2) else ""), unsure=False)) + "\n")
# third reader: line 0 order only, line 1 settled (glyph only, = Azure), line 2 unreadable
with open(f"{ST}/settle/C/readings.jsonl" if os.makedirs(f"{ST}/settle/C", exist_ok=True) is None else "", "w") as fc:
    for n, d in enumerate(disp[:3]):
        t = d["candidates"][priv[d["id"]]["azure"]]["text"]
        fc.write(json.dumps(dict(id=d["id"], printed=t, order_only=n == 0, glyph_only=n == 1, unreadable=n == 2, unsure=False)) + "\n")

env = dict(os.environ, EXP97_KEYS=K, EXP97_SCORES=f"{ST}/scores", EXP97_SETTLE=f"{ST}/settle")
r = subprocess.run([sys.executable, "score97.py", "--keys", "A"], env=env, capture_output=True, text=True, cwd=os.path.dirname(__file__) or ".")
print(r.stdout[-1500:], r.stderr[-3000:])
sc = json.load(open(f"{ST}/scores/scorecard.json"))
P, Cc = sc["parts"], sc["ceiling"]
checks = {
    "pipeline vs its own key: P1 = 1": P["PAGE"]["P1"]["accuracy"] == 1.0,
    "P2 F1 = 1": P["PAGE"]["P2"]["f1"] == 1.0,
    "P3 one-column = 1": P["PAGE"]["P3"]["one"]["share"] in (1.0, None),
    "P6 notes = 1": P["PAGE"]["P6"]["notes_right"] in (1.0, None),
    # (calls_linked_right < 1 here is real: the pipeline links some calls to a note with another label)
    "P6 calls found = 1": P["PAGE"]["P6"]["calls_found"] in (1.0, None),
    "P4 title = 1": P["FRONT"]["P4.title"]["exact"] == 1.0,
    "P4 authors = 1": P["FRONT"].get("P4.authors", {}).get("exact") in (1.0, None),
    "P7 found = 1": P["TAB"]["P7.found"]["share"] == 1.0,
    "P7 cells = 1": P["TAB"]["P7.cells"]["exact"] == 1.0,
    "P9 boundaries = 1": P["REFS"]["P9.boundaries"]["share"] == 1.0,
    "P9 authors folded = 1": P["REFS"]["P9.authors"]["folded"] == 1.0,
    "P5 found = 1": P["SECT"]["P5"]["found"] == 1.0,
    "ceiling P1 < 1 (roles damaged in B)": Cc["PAGE"]["P1"]["accuracy"] < 1.0,
    "ceiling P2 < 1 (a merge in B)": Cc["PAGE"]["P2"]["f1"] < 1.0,
    "ceiling title exact < folded": Cc["FRONT"]["P4.title"]["exact"] < Cc["FRONT"]["P4.title"]["folded"],
    "ceiling cells < 1": Cc["TAB"]["P7.cells"]["exact"] < 1.0,
    "broken file reported": len(sc["inputs"]["PAGE"]["unreadable"]) == 1,
    "rulings: label_of / byline / unsure piece cost nothing (P1 still 1)": P["PAGE"]["P1"]["accuracy"] == 1.0,
    "cells: a moved minus is folded-equal, not content wrong": Cc["TAB"]["P7.cells"]["folded"] > Cc["TAB"]["P7.cells"]["exact"],
    "cells: a shifted row is misplaced / structure": any(k.startswith("misplaced") for k in Cc["TAB"].get("P7.cell_kinds", {})),
    "cells: changed letters are different text": any(k.startswith("different text") for k in Cc["TAB"].get("P7.cell_kinds", {})),
    "cells (d): some table carries content-wrong cells": Cc["TAB"]["P7.cell_tables"]["zero_content_wrong"] < 1.0,
    "fields: title with run-in words is 'part extra'": Cc["FRONT"].get("P4.title kinds", {}).get("part extra", 0) >= 1 or not n_damage.get("title_extra"),
    "P9 pages reversed: exact wrong, as numbers right": (not n_damage.get("pages_reversed")) or (Cc["REFS"]["P9.pages"]["exact"] < 1.0 and Cc["REFS"]["P9.pages_as_numbers"]["share"] == 1.0),
    "R1: Azure 0 errors where the fake readers agree": sc["R1_settled"]["exact"]["azure"]["letter_error_on_settled"] == 0.0,
    "R1: reader disagreements listed (3 made)": sc["R1_settled"]["readers_disagree"] == 3,
    "key state printed per part": all("key_source" in v for v in sc["inputs"].values()),
}
# ---------------------------------------------------------------- round 3: unit checks of the new rules
from common97 import shown_segment, line_targets
e3 = S._eq3
acc, dif = S.new_acc(), []
S._field(acc, dif, {}, "X.aff", "مدرس بقسم علم النفس، جامعة المنيا", "قسم علم النفس، جامعة المنيا",
         cands=["مدرس قسم علم النفس، جامعة المنيا"],
         extra_folded=lambda g, c: S.fold(g).endswith(S.fold("قسم علم النفس، جامعة المنيا")))
pg = dict(stem="x", page=5, columns=1, pieces=[dict(role="paragraph", lines=[1, 2]),
          dict(role="footnote", lines=[9], continues_from_previous_page=True, note_label=None),
          dict(role="footnote", lines=[10], note_label="1")], note_calls=[dict(label="1", in_line=2)])
pp = dict(pieces=[dict(role="paragraph", lines=[1, 2]), dict(role="footnote", lines=[9], note_label="7"),
          dict(role="footnote", lines=[10], note_label="5-")],
          note_calls=[dict(label="(1)", in_line=2, target_label="5-", target_lines=[10])])
a6, d6 = S.new_acc(), []
S.compare_page(pg, pp, a6, d6, {})
g7, i7 = S.compact_grid([["a", "b"], ["", ""], ["c", "d"], ["Source: x", ""]], table_note="Source: x")
rf = S._ref_fields({"pub_type": "confproc", "article_title": "T", "source_title": "Proc", "conf_name": "Conf 4"})
rj = S._ref_fields({"pub_type": "journal", "source_title": "J", "editors": [["Ferrari", "J.R."]], "cited_pages": "5-9"})
ar, dr = S.new_acc(), []
S.compare_refs(dict(stem="x", page=1, references=[
    dict(lines=[1], year="1994a", title="Effect of Things", pages="٢٦٤-٢٢٣", small_caps=True, notes_printed=["(in Arabic)"],
         authors=["Dr. Smith, J.", "Doe, A. et al."], other_numbers=["160"], volume="3"),
    dict(lines=[2], merged_in_print=True, title="x"),
    dict(lines=[3], continues_on_next_page=True, title="The begin")]),
    dict(references=[dict(lines=[1], year="1994", title="EFFECT OF THINGS (in Arabic)", pages="264-223",
                          authors=[["Smith", "J."], ["Doe", "A."]], volume="160"),
                     dict(lines=[2], title="y"), dict(lines=[3], title="The beginning of it")]), ar, dr, {})
kw = S.unrewrite("القيم؛ الشباب", "الكلمات المفتاحية: القيم، الشباب", "keywords")
t3 = line_targets("0345-045-004-023", 2, 3)
r3 = {
    "title language from letters": S.text_lang("Hello world", None) == "en" and S.text_lang("عنوان", "en") == "ar",
    "exact strips trailing separators; ' : ' joiner ignored for titles": e3("a : b.", "a b", colon=True)[0],
    "typography fold: ’ = ' (exact no, typography yes)": e3("Teachers’", "Teachers'") == (False, True, True),
    "affiliation: position + row accepted when folded": acc["X.aff"]["folded"] == 1 and acc["X.aff"]["exact"] == 0,
    "P6: continued note without label is right": a6["P6"]["notes_ok_no_label_to_compare"] == 1,
    "P6: call linked by target lines despite labels": a6["P6"]["calls_linked"] == 1,
    "P7: empty row and table-note row dropped": g7 == [["a", "b"], ["c", "d"]] and i7 == [0, 2],
    "P7: number read whole": S.table_number("جدول (٣-٣) نتائج") == "3-3",
    "P7: bullets folded away": S.cell_fold("□Link") == S.cell_fold("Link"),
    "P9: conference source from conf_name": rf["source"] == "Conf 4" and rf["title"] == "T",
    "P9: journal title not moved; editors; cited_pages": rj["title"] is None and rj["source"] == "J" and rj["authors"] and rj["pages"] == "5-9",
    "P9: honorifics and et al. off; small caps; notes_printed; year digits": ar["P9.authors"]["folded"] == 1 and ar["P9.title"]["exact"] >= 1 and ar["P9.year"]["folded"] == 1,
    "P9: pages as printed numbers": ar["P9.pages_as_numbers"]["ok"] == 1 and S.page_set("223-264") == frozenset({223, 264}),
    "P9: other_numbers not counted": ar["P9.volume"]["pred_is_other_number"] == 1 and ar["P9.volume"]["n"] == 0,
    "P9: merged_in_print left out": ar["P9.left_out"]["merged_in_print"] == 1 and ar["P9.boundaries"]["n"] == 2,
    "P9: reference cut by the page edge accepts a prefix": ar["P9.title"]["n"] == 2 and ar["P9.title"]["exact"] == 2,
    "R1: keyword rewrite undone": kw == "الكلمات المفتاحية: القيم، الشباب",
    "R1: hyphen-broken word cut after the stored hyphen": shown_segment("0345-045-004-023", 2, 3, t3[0][1])[0].endswith("eco-"),
    "R1: third reader: order only reported apart, glyph only settles, unreadable left out":
        sc["R1_settled"]["order_only_lines"] == 1 and sc["R1_settled"]["settled_by_third_reader"] == 1
        and sc["R1_settled"]["left_out_by_third_reader"].get("unreadable") == 1,
    "R1: shown with rewrites removed reported": "shown_no_rewrites" in sc["R1_settled"]["exact"],
    "P3 first pages: body-piece number present": "first_body" in P["PAGE"]["P3"],
    "banner: NOT FINAL while keys are not final": sc["banner"] == "NOT FINAL" and not sc["all_final"],
    "scorecard rows carry 'what a miss means' and pass": all("miss_means" in r and "passed" in r for r in sc["rows"]),
}
checks.update(r3)
# ---------------------------------------------------------------- round 4: revised key fields (keys rev 2)
pg4 = dict(stem="x", page=5, columns=1, pieces=[
    dict(role="other", lines=[1, 2], other_article=True), dict(role="paragraph", lines=[3, 4]),
    dict(role="figure", lines=[5], either_ok=["figure", "(not-text)"]),
    dict(role="footnote", lines=[6, 7], tabular_list=True, note_label="□", note_label_also_ok=["*"])],
    note_calls=[dict(label="٠", in_line=3, label_also_ok=["*"])])
pp4 = dict(pieces=[dict(role="paragraph", lines=[3, 4]), dict(role="table", lines=[6, 7]),
                   dict(role="footnote", lines=[], note_label="*")],
           azure_lines_that_are_not_text=[1, 2, 5], note_calls=[dict(label="*", in_line=3, target_label="*", target_lines=None)])
a4, d4 = S.new_acc(), []
S.compare_page(pg4, pp4, a4, d4, {})
pg4b = dict(pg4, pieces=pg4["pieces"][:3] + [dict(role="footnote", lines=[6, 7], note_label="□", note_label_also_ok=["*"])])
pp4b = dict(pp4, pieces=[dict(role="paragraph", lines=[3, 4]), dict(role="footnote", lines=[6, 7], note_label="*")])
a4b, d4b = S.new_acc(), []
S.compare_page(pg4b, pp4b, a4b, d4b, {})
af, dfr = S.new_acc(), []
S.compare_front(dict(stem="x", titles=[dict(lang="ar", text="العنوان : الفرعي", title_main="العنوان")],
                     dates=dict(received="09-10-2023"), date_numbers=dict(received=[9, 10, 2023])),
                dict(titles=[dict(lang="ar", text="العنوان")], dates=dict(received="2023-10-09")), af, dfr, {})
af2, df2 = S.new_acc(), []
S.compare_front(dict(stem="x", titles=[dict(lang="ar", text="المدارس فى الميزان")]),
                dict(titles=[dict(lang="ar", text="المدارس فى الميزان ( ٤ )")]), af2, df2, {})
ar4, dr4 = S.new_acc(), []
S.compare_refs(dict(stem="x", page=1, references=[
    dict(lines=[1], source="مجلة كلية التربية", publisher="جامعة أسيوط", place=["مصر"]),
    dict(lines=[2], source=None, series="سلسلة عالم المعرفة", source_as_printed="سلسلة عالم المعرفة")]),
    dict(references=[dict(lines=[1], source="مجلة كلية التربية، جامعة أسيوط، مصر", _publisher=None, _place=None),
                     dict(lines=[2], source="سلسلة عالم المعرفة")]), ar4, dr4, {})
a7, d7 = S.new_acc(), []
S.compare_cells([["1", "x"]], [["1", "y"]], {(0, 1)}, a7, d7, {})
r4 = {
    "rev2: other_article lines left out of P1 and R2": a4["P1_conf"].get(("other", "(not-text)"), 0) == 0 and a4["R2k"]["lost"] == 0,
    "rev2: either_ok (not-text) accepted": a4["P1_ok"][("figure", "(not-text)")] == 1,
    "rev2: tabular_list footnote accepts table": a4["P1_ok"][("footnote", "table")] == 2,
    "rev2: note_label_also_ok / label_also_ok accepted": a4b["P6"]["notes_ok"] == 1 and a4b["P6"]["calls_found"] == 1,
    "rev2: title_main accepted and reported": af["P4.title"]["folded"] == 1 and af["P4.title"]["matched_title_main"] == 1,
    "rev2: date_numbers compared as a set": af["P4.date_received"]["folded"] == 1,
    "ruling: part number on the title line may be in or out": af2["P4.title"]["exact"] == 1,
    "rev2: source + publisher + place in the pipeline's source is right": ar4["P9.source"]["right_with_place_series_publisher"] == 1 and ar4["P9.source"]["exact"] >= 1,
    "rev2: key source null with series: a pipeline series is not scored wrong": ar4["P9.source"]["n"] == 1,
    "rev2: unreadable / unsure cells left out": a7["P7.cells"]["unsure_left_out"] == 1 and a7["P7.cells"]["n"] == 1,
    "rev2: _v1 folders and _ files are not read": not any(k.startswith("_") for k in S.load_keys("PAGE", "final")["files"]),
}
checks.update(r4)
for k, v in checks.items():
    print("OK  " if v else "FAIL", k)
print("damage", n_damage, "P9 authors exact (joins)", P["REFS"]["P9.authors"]["exact"])
