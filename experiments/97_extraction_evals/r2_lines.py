#!/usr/bin/env python3
"""Experiment 97, R2 (mechanical): on all 214 exam pages, every Azure line should land in exactly one block.

Counts Azure lines with no line_map row (lost), with more than one distinct target (doubled), and the lines that went
to a page region (running head, page number, noise ...) instead of a block, by region role.  The key's
`azure_lines_that_are_not_text` is not used here (that is the keyed R2, scored by score97.py once keys exist).
Run:  nice -n 19 python3 r2_lines.py   ->  out/scores/r2_lines.json
"""
import collections as C
from common97 import OUT, article_index, cache, exam_pages, jdump, line_targets

tot = C.Counter()
by_kind = C.defaultdict(C.Counter)
region_roles = C.Counter()
ex_lost, ex_multi, ex_noise = [], [], []
multi_kinds = C.Counter()
for stem, page, kind in exam_pages():
    ix = article_index(stem)
    for l in cache(stem)["azure_lines"]:
        if l["page"] != page:
            continue
        t = line_targets(stem, page, l["line_no"])
        tot["lines"] += 1
        by_kind[kind]["lines"] += 1
        rec = dict(stem=stem, page=page, kind=kind, line=l["line_no"], text=l["text"])
        if not t:
            tot["lost"] += 1
            by_kind[kind]["lost"] += 1
            ex_lost.append(rec)
            continue
        if len(t) > 1:
            tot["multi"] += 1
            by_kind[kind]["multi"] += 1
            roles = [ix["blocks"][i]["role"] if k == "block" else "region:" + ix["regions"][i]["role"] for k, i in t]
            multi_kinds["+".join(sorted(set(roles)))] += 1
            ex_multi.append(dict(rec, targets=[f"{k}:{i}" for k, i in t], roles=roles))
        if t[0][0] == "region":
            role = ix["regions"][t[0][1]]["role"]
            region_roles[role] += 1
            tot["to_region"] += 1
            if role in ("noise", "showThrough", "pictureJunk", "ornament") and len(l["text"].strip()) >= 3:
                ex_noise.append(dict(rec, region_role=role))
n = tot["lines"]
res = dict(
    pages=len(exam_pages()), azure_lines=n,
    lost_no_block=tot["lost"], lost_share=round(tot["lost"] / n, 5),
    doubled_more_than_one_block=tot["multi"], doubled_share=round(tot["multi"] / n, 5),
    pass_marks=dict(lost="<= 0.5%", doubled="<= 0.2%"),
    doubled_by_roles=dict(multi_kinds.most_common()),
    doubled_note="a line split over several table-cell blocks is how the pipeline stores a table row; it is counted "
                 "here as the mechanical number, and separately in doubled_by_roles so the non-table cases stand out",
    doubled_not_all_table_cells=sum(v for k, v in multi_kinds.items() if k != "table-cell"),
    to_page_region=tot["to_region"], page_region_roles=dict(region_roles.most_common()),
    region_note="lines sent to a page region are not in any text block: running heads and page numbers are meant to "
                "be there; noise / showThrough / pictureJunk / ornament regions holding 3+ characters are possible losses "
                "(examples below) that only the keys (azure_lines_that_are_not_text) can settle",
    by_kind={k: dict(v) for k, v in by_kind.items()},
    examples_lost=ex_lost[:40], examples_doubled=ex_multi[:40],
    examples_doubled_not_table=[e for e in ex_multi if set(e["roles"]) != {"table-cell"}][:40],
    text_lines_in_noise_regions=len(ex_noise), examples_text_in_noise_regions=ex_noise[:40],
)
jdump(res, f"{OUT}/scores/r2_lines.json")
print({k: res[k] for k in ("azure_lines", "lost_no_block", "lost_share", "doubled_more_than_one_block", "doubled_share",
                           "doubled_not_all_table_cells", "to_page_region", "text_lines_in_noise_regions")})
print(res["doubled_by_roles"], res["page_region_roles"])
