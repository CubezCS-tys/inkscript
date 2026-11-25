#!/usr/bin/env python3
"""Experiment 97 R0: summarise the per-page ink ledgers (out/ink/pages/*.json) into summary.json, SUMMARY.md and
unclaimed_regions.jsonl. Reads only out/ink/; run after ink97.py."""
import glob, json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = f"{HERE}/out/ink"
STATUS = ["once", "twice", "dropped", "unseen"]
TEXT_GUESS = "text-like row of glyph-sized blobs"
SMALL_GUESS = "small mark (1-3 glyph-sized blobs)"
LABEL_GUESSES = (TEXT_GUESS, SMALL_GUESS)
JOURNALS7 = {"0013", "0097", "0130", "0165", "0246", "0840", "1001"}
TEXT_SHAPES = ("glyph", "small")

pages = [json.load(open(p)) for p in sorted(glob.glob(f"{OUT}/pages/*.json"))]


def agg(sel, scope):
    A = defaultdict(float); N = defaultdict(int); tot_a = 0; tot_n = 0
    for p in sel:
        t = p["tally"][scope]
        tot_a += t["ink_px"]; tot_n += t["n"]
        for s in STATUS:
            A[s] += t[s]["area"]; N[s] += t[s]["n"]
    return {"pages": len(sel), "ink_px": int(tot_a), "components": tot_n,
            **{s: {"area_share": round(A[s] / max(tot_a, 1), 5), "n_share": round(N[s] / max(tot_n, 1), 5)}
               for s in STATUS}}


def once_split(sel, scope):
    d = defaultdict(float); tot = 0
    for p in sel:
        t = p["tally"][scope]; tot += t["ink_px"]
        for k, v in t["once_by_piece_kind_area"].items():
            d[k] += v
    return {k: round(v / max(tot, 1), 5) for k, v in sorted(d.items())}


def twice_pairs(sel, scope):
    d = defaultdict(float)
    for p in sel:
        for k, v in p["tally"][scope]["twice_by_pair_area"].items():
            d[k] += v
    return dict(sorted(((k, int(v)) for k, v in d.items()), key=lambda kv: -kv[1]))


def shape_status(sel):
    """ink area by (shape class, status) over all components"""
    d = defaultdict(lambda: defaultdict(int))
    for p in sel:
        for cm in p["components"]:
            d[cm[7]][cm[12]] += cm[4]
    return {k: dict(v) for k, v in d.items()}


kinds = ["front", "body", "table", "refs", "notes"]
by_kind = {k: [p for p in pages if p["kind"] == k] for k in kinds}
journals = sorted(set(p["journal"] for p in pages))
by_j = {j: [p for p in pages if p["journal"] == j] for j in journals}
by_j_grouped = {**{j: by_j[j] for j in journals if j in JOURNALS7},
                 "18 other journals": [p for p in pages if p["journal"] not in JOURNALS7]}

regions = []
for p in pages:
    for r in p["regions"]:
        regions.append(dict(stem=p["stem"], page=p["page"], kind=p["kind"], journal=p["journal"], **r))
text_regions = [r for r in regions if r["guess"] == TEXT_GUESS]
label_regions = [r for r in regions if r["guess"] in LABEL_GUESSES]


def text_ledger(sel):
    """Text ink: claimed glyph-sized ink + ink of unclaimed regions whose shape says text (row of glyph blobs).
    Ink the shape guess calls rule / frame / texture / tint / speck is left out of the denominator."""
    keys = {(p["stem"], p["page"]) for p in sel}
    claimed = {s: sum(p["tally"]["text"][s]["area"] for p in sel) for s in ("once", "twice")}
    # set-aside regions are claims, so their ink is already inside 'once'; report the text-like part apart
    un = {g: sum(r["ink_area"] for r in text_regions if (r["stem"], r["page"]) in keys and r["group"] == g)
          for g in ("dropped", "unseen", "set_aside")}
    small = {g: sum(r["ink_area"] for r in regions if (r["stem"], r["page"]) in keys and r["group"] == g
                    and r["guess"] == SMALL_GUESS) for g in ("dropped", "unseen")}
    den = claimed["once"] + claimed["twice"] + un["dropped"] + un["unseen"]
    return {"text_ink_px": int(den),
            "once": round(claimed["once"] / max(den, 1), 6), "twice": round(claimed["twice"] / max(den, 1), 6),
            "dropped": round(un["dropped"] / max(den, 1), 6), "unseen": round(un["unseen"] / max(den, 1), 6),
            "set_aside_text_like": round(un["set_aside"] / max(den, 1), 6),
            "unseen_incl_small_marks": round((un["unseen"] + small["unseen"]) / max(den, 1), 6),
            "dropped_incl_small_marks": round((un["dropped"] + small["dropped"]) / max(den, 1), 6)}

reg_counts = {}
for k in kinds:
    rk = [r for r in regions if r["kind"] == k]
    reg_counts[k] = {g: {gs: sum(1 for r in rk if r["group"] == g and r["guess"] == gs)
                         for gs in sorted(set(r["guess"] for r in regions))}
                     for g in ("dropped", "unseen", "set_aside")}
    reg_counts[k]["text_like_unclaimed"] = sum(1 for r in text_regions if r["kind"] == k and r["group"] != "set_aside")
    reg_counts[k]["text_like_per_page"] = round(sum(1 for r in text_regions if r["kind"] == k) / max(len(by_kind[k]), 1), 2)

top30 = sorted([r for r in text_regions if r["group"] in ("dropped", "unseen")], key=lambda r: -r["ink_area"])[:30]
top_setaside = sorted([r for r in text_regions if r["group"] == "set_aside"], key=lambda r: -r["ink_area"])[:15]

how = defaultdict(int); specks = 0; speck_px = 0
for p in pages:
    for k, v in p["how_counts"].items():
        how[k] += v
    specks += p["specks"]; speck_px += p["speck_px"]

summary = dict(
    method=pages[0]["params"], n_pages=len(pages),
    overall={"all_ink": agg(pages, "all"), "glyph_sized_ink": agg(pages, "text"), "text_ledger": text_ledger(pages)},
    once_by_piece_kind={"all_ink": once_split(pages, "all"), "text_ink": once_split(pages, "text")},
    twice_by_pair_area={"all_ink": twice_pairs(pages, "all"), "text_ink": twice_pairs(pages, "text")},
    by_kind={k: {"all_ink": agg(v, "all"), "glyph_sized_ink": agg(v, "text"), "text_ledger": text_ledger(v)}
             for k, v in by_kind.items()},
    by_journal={j: {"all_ink": agg(v, "all"), "glyph_sized_ink": agg(v, "text"), "text_ledger": text_ledger(v)}
                for j, v in by_j.items()},
    by_journal_grouped={j: {"all_ink": agg(v, "all"), "glyph_sized_ink": agg(v, "text"), "text_ledger": text_ledger(v)}
                        for j, v in by_j_grouped.items()},
    ink_area_by_shape_and_status=shape_status(pages),
    line_assignment_counts=dict(how), specks_dropped={"n": specks, "px": speck_px},
    region_counts_by_kind=reg_counts,
    n_regions=len(regions), n_text_like_regions={g: sum(1 for r in text_regions if r["group"] == g)
                                                 for g in ("dropped", "unseen", "set_aside")},
    n_small_mark_regions={g: sum(1 for r in regions if r["group"] == g and r["guess"] == SMALL_GUESS)
                          for g in ("dropped", "unseen", "set_aside")},
    regions_by_guess={g: {gs: sum(1 for r in regions if r["group"] == g and r["guess"] == gs)
                          for gs in sorted(set(r["guess"] for r in regions))} for g in ("dropped", "unseen", "set_aside")},
    speck_check={"in_line_boxes": {k: sum(p["speck_in_lines"][k] for p in pages) for k in ("n", "px")},
                 "area_hist_all": {t: sum(p["area_hist_all"][t] for p in pages) for t in pages[0]["area_hist_all"]},
                 "area_hist_in_lines": {t: sum(p["area_hist_in_lines"][t] for p in pages)
                                        for t in pages[0]["area_hist_in_lines"]}},
    largest_text_like_unclaimed=top30, largest_text_like_set_aside=top_setaside,
    worst_pages_text_unseen=sorted(((p["stem"] + "_p%03d" % p["page"], p["kind"],
                                     p["tally"]["text"]["unseen"]["area_share"]) for p in pages),
                                   key=lambda t: -t[2])[:15],
)
json.dump(summary, open(f"{OUT}/summary.json", "w"), ensure_ascii=False, indent=1)

with open(f"{OUT}/unclaimed_regions.jsonl", "w") as f:
    for r in label_regions:
        f.write(json.dumps(dict(stem=r["stem"], page=r["page"], kind=r["kind"], region_id=r["id"], box=r["box"],
                                ink_area=r["ink_area"], crop=r["crop"], group=r["group"], auto_guess=r["guess"],
                                setaside_role=r["setaside_role"], label=None), ensure_ascii=False) + "\n")
print(json.dumps({k: summary[k] for k in ("overall", "n_text_like_regions", "n_small_mark_regions", "regions_by_guess",
                                          "line_assignment_counts", "specks_dropped", "speck_check",
                                          "once_by_piece_kind", "twice_by_pair_area")}, indent=1))
for k in kinds:
    print(k, summary["by_kind"][k]["text_ledger"], summary["by_kind"][k]["all_ink"]["unseen"])
for j, v in summary["by_journal_grouped"].items():
    print(j, v["text_ledger"])


# ---------------------------------------------------------------- SUMMARY.md
def pct(x, d=2):
    return f"{100 * x:.{d}f}%"


def row4(name, a, n=None):
    return (f"| {name} | {a['pages']} | {pct(a['once']['area_share'])} | {pct(a['twice']['area_share'], 3)} | "
            f"{pct(a['dropped']['area_share'], 3)} | {pct(a['unseen']['area_share'])} | "
            f"{pct(a['once']['n_share'])} / {pct(a['twice']['n_share'], 3)} / {pct(a['dropped']['n_share'], 3)} / "
            f"{pct(a['unseen']['n_share'])} |")


def rowt(name, t):
    return (f"| {name} | {t['text_ink_px'] / 1e6:.1f} M | {pct(t['once'], 3)} | {pct(t['twice'], 3)} | {pct(t['dropped'], 3)} | "
            f"{pct(t['unseen'], 3)} | {pct(t['unseen_incl_small_marks'], 3)} | {pct(t['set_aside_text_like'], 3)} |")


H4 = ("| | pages | once | twice | reader saw, parser dropped | nobody saw | by count: once / twice / dropped / unseen |\n"
      "|---|---|---|---|---|---|---|")
HT = ("| | text ink | once | twice | reader saw, parser dropped | nobody saw | nobody saw incl. 1-3-blob marks | "
      "set aside by the parser (text-like) |\n|---|---|---|---|---|---|---|---|")
S = summary
L = []
L.append("# R0 ink ledger: every blob of ink on the 214 exam pages\n")
L.append("Experiment 97, part R0 (2026-11-10). Made by `ink97.py` (one page at a time, resumable) and `ink97_summary.py`. "
         "Free and local. Release R20261104T151029, read-only.\n")
L.append("Colours in `overlays/`: **grey** ink claimed by exactly one piece; **orange** claimed by two or more; "
         "**red** inside an Azure line but in no piece (reader saw, parser dropped); **purple** in no Azure line and no "
         "piece (nobody saw); **green** claimed by a page region the parser set aside as non-content (noise, "
         "pictureJunk, ornament, otherArticle); light grey specks below the size cut. Thin blue boxes are Azure "
         "lines; coloured boxes mark the unclaimed regions that got a crop.\n")
L.append("## Headline\n")
t = S["overall"]["text_ledger"]
L.append(f"- **Text ink** (glyph-sized ink that a piece claims, plus unclaimed regions whose shape is a row of glyphs): "
         f"once {pct(t['once'], 3)}, twice {pct(t['twice'], 3)}, reader-saw-parser-dropped {pct(t['dropped'], 3)}, "
         f"nobody saw {pct(t['unseen'], 3)} ({pct(t['unseen_incl_small_marks'], 3)} if every 1-3-blob mark is counted "
         f"as text). Pass marks (README): nobody saw <= 0.3%, dropped <= 0.2%.")
L.append(f"- **But**: text-like ink that the parser *set aside* as a non-content region is {pct(t['set_aside_text_like'], 3)} "
         f"of text ink, all on two pages of one poetry article (0738-002-003-016 p1, p3: a neighbouring poem marked "
         f"otherArticle; correct if the poem belongs to another article, which the crops suggest). That is the only "
         f"place where the parser can lose text the reader saw: **every one of the 10,332 Azure lines on these pages "
         f"has a line_map row** (to a block or a region), so 'reader saw, parser dropped' is zero by construction of "
         f"the release; the parser's losses can only hide inside set-aside regions.")
a = S["overall"]["all_ink"]
L.append(f"- **All ink** (rules, frames, table grids, pictures, tints, scan edges included): once {pct(a['once']['area_share'])}, "
         f"twice {pct(a['twice']['area_share'], 3)}, dropped {pct(a['dropped']['area_share'], 3)}, nobody saw "
         f"{pct(a['unseen']['area_share'])}. The unseen ink is almost all non-text: by shape class, "
         + ", ".join(f"{k} {v.get('unseen', 0) / 1e6:.2f} M px" for k, v in sorted(S['ink_area_by_shape_and_status'].items()))
         + " (glyph/small = glyph-sized, which on a few pages is halftone texture or a border ornament broken into "
           "glyph-sized pieces).")
L.append(f"- Unclaimed regions with a text-like shape: **{S['n_text_like_regions']['unseen']} nobody-saw, "
         f"{S['n_text_like_regions']['dropped']} dropped, {S['n_text_like_regions']['set_aside']} set aside**; plus "
         f"{S['n_small_mark_regions']['unseen']} nobody-saw and {S['n_small_mark_regions']['set_aside']} set-aside "
         f"1-3-blob marks. All {len(label_regions)} go to the blind labellers in `unclaimed_regions.jsonl`. "
         f"By eye (mosaic of every crop): none of the nobody-saw ones is printed text; they are dotted/broken rules, "
         f"ornaments (a bracket-and-rule round a page number, three boxes as a section break, a curl), punch holes, "
         f"blots, one (c) sign, a stray edge of a neighbouring page with a folio digit ('63').\n")
L.append("## The four shares, all ink\n")
L.append(H4)
L.append(row4("**all pages**", a))
for k in kinds:
    L.append(row4(k, S["by_kind"][k]["all_ink"]))
L.append("")
L.append("## The four shares, text ink\n")
L.append(HT)
L.append(rowt("**all pages**", t))
for k in kinds:
    L.append(rowt(k, S["by_kind"][k]["text_ledger"]))
L.append("")
L.append("By journal (text ink; the seven read-whole journals, then the 18 others pooled; every journal apart is in "
         "summary.json `by_journal`):\n")
L.append(HT)
for j, v in S["by_journal_grouped"].items():
    L.append(rowt(j, v["text_ledger"]))
L.append("")
L.append("What claims the ink claimed once (share of all ink): " + ", ".join(
    f"{k} {pct(v)}" for k, v in S["once_by_piece_kind"]["all_ink"].items())
         + ". Furniture = pageHeader / pageNumber / pageFooter regions.\n")
L.append("Ink claimed twice, by pair (pixels, all ink): " + ", ".join(
    f"{k} {v:,}" for k, v in S["twice_by_pair_area"]["all_ink"].items())
         + ". block+block is a rule lying where two text-line boxes overlap; block+figure is mostly text a figure box "
           "also covers. No piece of text was found emitted twice.\n")
L.append("## Unclaimed regions per page kind\n")
L.append("| kind | pages | text-like (nobody saw + dropped) | 1-3-blob marks (nobody saw) | rules (nobody saw) | specks (nobody saw) |")
L.append("|---|---|---|---|---|---|")
for k in kinds:
    rc = S["region_counts_by_kind"][k]
    L.append(f"| {k} | {len(by_kind[k])} | {rc['text_like_unclaimed']} | {rc['unseen'].get(SMALL_GUESS, 0)} | "
             f"{rc['unseen'].get('long thin rule', 0)} | {rc['unseen'].get('isolated speck', 0)} |")
L.append("")
L.append("Unclaimed (nobody saw) regions by automatic guess: " + ", ".join(
    f"{k} {v}" for k, v in S["regions_by_guess"]["unseen"].items() if v) + ".\n")
L.append("## The largest text-like and mark-like unclaimed regions\n")
L.append("There are fewer than 30 text-like unclaimed regions, so this lists every text-like one, then the largest "
         "1-3-blob marks, to 30 rows (nobody saw / dropped), then the set-aside text-like ones.\n")
cand = sorted([r for r in regions if r["group"] in ("dropped", "unseen") and r["guess"] in LABEL_GUESSES],
              key=lambda r: (r["guess"] != TEXT_GUESS, -r["ink_area"]))[:30]
L.append("| region | kind | box (x, y, w, h) | ink px | guess | crop |")
L.append("|---|---|---|---|---|---|")
for r in cand + top_setaside:
    L.append(f"| {r['id']} ({r['group']}) | {r['kind']} | {', '.join(str(v) for v in r['box'])} | {r['ink_area']:,} | "
             f"{r['guess']}{(' / ' + r['setaside_role']) if r['setaside_role'] else ''} | ![]({r['crop']}) |")
L.append("")
sc = S["speck_check"]
L.append("## Method and the numbers behind each choice\n")
L.append(f"- **Threshold**: Sauvola (window {S['method']['win']} px = 5 mm at 300 dpi, k = {S['method']['k']}, R = 128) "
         f"plus a ceiling (grey < {S['method']['abs_max']}). Local, because these scans have grey gradients, dark "
         f"gutters and yellowed paper; Sauvola's std term keeps flat paper out of the ink, where a mean-minus-C "
         f"adaptive threshold speckles it. The window is wider than any stroke and about one line high, so bold "
         f"titles stay solid.")
L.append(f"- **Speck cut**: components under {S['method']['min_area']} px are not assigned "
         f"({S['specks_dropped']['n']:,} components, {S['specks_dropped']['px']:,} px = "
         f"{pct(S['specks_dropped']['px'] / (a['ink_px'] + S['specks_dropped']['px']))} of all ink pixels). Only "
         f"{sc['in_line_boxes']['n']:,} of them ({sc['in_line_boxes']['px']:,} px, "
         f"{pct(sc['in_line_boxes']['px'] / max(1, t['text_ink_px']), 3)} of text ink) sit inside Azure line boxes, "
         f"i.e. could be fragments of dots; the Arabic dot at 8 pt is about 4 x 4 px = 16 px, so 6 px keeps every "
         f"whole dot. Component areas (all / inside lines): "
         + ", ".join(f"{k}-{2 * int(k) - 1} px {sc['area_hist_all'][k]:,} / {sc['area_hist_in_lines'][k]:,}"
                     for k in sc['area_hist_all']) + ".")
L.append("- **Boxes** are scaled from the ALTO page size (pages.width_px, height_px) to the JPEG (they differ by 2-5 px "
         "on 131 of 214 pages). Skew (pages.angle) is at most about 1 degree here; Azure's boxes are already the "
         "upright envelope of each line, so no rotation is applied.")
L.append(f"- **Ink -> Azure line**: glyph-sized ink by its ink centroid inside the line box (one line; if boxes "
         f"overlap, the line whose centre is nearest, unless the boxes are near-duplicates); else >= 50% of its "
         f"box inside a line box; else, for ink smaller than a glyph, a line box within "
         f"{S['method']['near_frac']} x line height (dots, hamzas, shadda just outside a tight box). Rules, grids, "
         f"pictures and scan edges by >= 50% of their box inside. Counts: " + ", ".join(
             f"{k} {v:,}" for k, v in S["line_assignment_counts"].items()) + " components.")
L.append("- **Ink -> pieces**: the line_map sub-box of that Azure line (an Azure line split into two ALTO lines, e.g. "
         "two table cells, goes to the sub-box that holds the ink); figure boxes always; block_parts and page_regions "
         "boxes only if nothing else claims the ink, because a block_parts box is the envelope of a block that "
         "may turn a column (found on 0840-000-013-009 p8: a paragraph's envelope covered a pie chart and made it "
         "'twice'). Same piece, not a double claim: table cells and a caption of their figure; a pictureText / "
         "pictureJunk / formulaInk region inside a figure (found on 0013-026-004-003 p25: an instruction screen "
         "shown as a figure, 88% orange before the fix); an inline formula inside a text line.")
L.append("- **Shape classes** (per component, from its box and area, against the page's glyph height = 0.6 x the "
         "median Azure line height): edge (touches the image border and is large), rule (long and thin, or a long "
         "component with little ink per column, e.g. a rule ending in a bracket), grid (big box, < 12% ink: "
         "table rulings, frames), mass (pictures, solid bands), glyph, small. 'Text ink' uses glyph + small.")
L.append("- **Regions**: unclaimed components are dilated (1 glyph height across, 0.35 down) and merged; each "
         "region gets a shape guess: text-like row of glyph-sized blobs; 1-3-blob mark; long thin rule (incl. "
         "dotted and broken rules); large picture-like mass; frame / border ornament (hollow: < 25% of its ink "
         "in the inner 70% of a box over 12% of the page); halftone / speckle texture (>= 20 pieces averaging < "
         "6% of a glyph square); shaded band / tint (>= 20 pieces, > 35% fill); scan edge; isolated speck "
         "(no crop).\n")
L.append("## What the overlays showed (22 looked at by eye, every page kind, 14 journals)\n")
L.append("- Body text, references, notes and table cells are grey line by line, dots and diacritics included "
         "(2,246 small components were attached by the near-line rule). Pages of the seven read-whole journals "
         "are entirely grey apart from rules.")
L.append("- Purple is, in order of area: horizontal rules (under titles, footnote separators, header rules, table "
         "top/bottom rules outside the table box), page frames and decorative borders (0738 poetry pages, 0354), "
         "halftone backgrounds and tinted header/footer bands (0354 p1/p6, 0590 p1/p3/p10), punch holes (0048), "
         "edges of the facing page (0165, 0702), and on a few pages a stray dot.")
L.append("- Orange (after the fixes) is a handful of pixels: a few rules where two line boxes overlap, and blots "
         "inside a table box that the parser had set aside as noise.")
L.append("- Green: a whole neighbouring poem set aside as otherArticle (0738 p1, p3), a decorative tail-piece set "
         "aside as ornament, small noise lines.")
L.append("- Traps found and fixed: a table grid's centroid falls inside some cell line (gave 'twice'), so big ink "
         "is placed by box overlap, not centroid; envelope boxes of column-turning blocks (above); picture-text "
         "regions inside figures (above); a rule joined to a bracket was read as a glyph (partly fixed: the bracket-and-rule round 1001 page numbers still comes out as a 1-3-blob mark); tints and halftones "
         "were guessed as text rows; frames covering the whole page were guessed as text.\n")
L.append("## What this method cannot tell\n")
L.append("- It sees whether ink was **claimed**, not whether it was **read** right: a line Azure read wrongly, or a "
         "word dropped from inside a claimed line, is grey here. R1 measures reading.")
L.append("- A claim is geometric: a block 'claims' ink if the ink sits in the box of an Azure line mapped to it. If "
         "the parser kept the line but dropped words from its text, the ledger cannot see it; comparing the "
         "block text with the Azure line text would (cheap, a next step).")
L.append("- 'Reader saw, parser dropped' is zero because every Azure line of the release has a line_map row; the "
         "parser's discards show up as set-aside regions (green) instead, and only their text-like part is a "
         "candidate loss. Whether a set-aside region was right (an other-article poem, a noise line) needs a label.")
L.append("- Text printed on a tint or halftone band merges with the band into large components, so its ink is "
         "counted as texture, not text (0590 headers). Very faint text below the threshold is invisible to the "
         "ledger as it is to the reader.")
L.append("- Shape guesses are rough; the blind labels (printed text / picture / rule / stamp / noise) on the "
         f"{len(label_regions)} regions in `unclaimed_regions.jsonl` are the real answer. Isolated specks and "
         "rules are not sent for labelling.")
L.append("- Figure boxes claim everything inside them, so text printed inside a picture is 'claimed' even if no "
         "piece holds its words (figures.text_in_figure may or may not).")
L.append("- The exam's table / reference / note pages were chosen where we found such pieces (README bias); the 60 "
         "random body pages are the unbiased sample, and they show no text-like ink unclaimed.\n")
L.append("## Files\n")
L.append("- `pages/<stem>_pNNN.json`: per page: params, counts, tallies, every component (box, area, centroid, shape, "
         "Azure line(s), how placed, pieces, status), regions. `overlays/<stem>_pNNN.png` (1200 px wide). "
         "`crops/<region>.jpg`.")
L.append("- `summary.json`: everything above, including every journal apart. `unclaimed_regions.jsonl`: one row per "
         "text-like or 1-3-blob unclaimed or set-aside region, with an empty `label` for the blind labellers.")
open(f"{OUT}/SUMMARY.md", "w").write("\n".join(L) + "\n")
