"""D4: page_data.json for the orchestrator's visual page, plus scan crops of the example cards (crops/)."""
import collections, json, os
import cv2
import common_d as cd

PAGES = "/home/appuser/inkscript/experiments/43_rehearsal/out/pages/"
d1 = json.load(open(cd.OUT + "d1_metrics.json", encoding="utf-8"))
nets = json.load(open(cd.OUT + "d1_networks.json", encoding="utf-8"))
d2 = json.load(open(cd.OUT + "d2_growth.json", encoding="utf-8"))
d3 = json.load(open(cd.OUT + "d3_workload.json", encoding="utf-8"))
A = json.load(open(cd.A + "results.json", encoding="utf-8"))
c = cd.plat()


def boxes_for_mention(mid=None, stem=None, page=None, note=None):
    if mid is None:
        r = c.execute("""SELECT m.mention_id FROM citation_mentions m JOIN versions v ON v.version_id=m.version_id AND v.is_current=1
                         WHERE v.stem=? AND m.page=? AND m.container_id=? ORDER BY m.seq_in_container LIMIT 1""",
                      (stem, page, note)).fetchone()
        mid = r[0] if r else None
    if mid is None:
        return None, []
    r = c.execute("SELECT mention_pk, anchor_pk, page FROM citation_mentions WHERE mention_id=?", (mid,)).fetchone()
    pks = [r[1]] + [x[0] for x in c.execute(
        "SELECT anchor_pk FROM anchor_links WHERE owner_kind='citation_mention' AND owner_key=?", (mid,))]
    bx = []
    for pk in pks:
        a = c.execute("SELECT stem,page,x,y,w,h FROM ink_anchors WHERE anchor_pk=?", (pk,)).fetchone()
        if a and a[2] is not None:
            bx.append(a)
    return mid, bx


def boxes_for_block(stem, block):
    return [r for r in c.execute("""SELECT v.stem, b.page, b.x, b.y, b.w, b.h FROM block_parts b
            JOIN versions v ON v.version_id=b.version_id AND v.is_current=1 WHERE v.stem=? AND b.block_id=?""", (stem, block))]


def crop(name, bx):
    if not bx:
        return None
    stem, page = bx[0][0], bx[0][1]
    bx = [b for b in bx if b[1] == page]
    path = PAGES + f"{stem}_p{page:03d}.jpg"
    if not os.path.exists(path):
        return None
    im = cv2.imread(path)
    H, W = im.shape[:2]
    pw = c.execute("SELECT width_px FROM pages WHERE stem=? AND page=?", (stem, page)).fetchone()[0] or W
    s = W / pw
    x0 = min(b[2] for b in bx) * s; y0 = min(b[3] for b in bx) * s
    x1 = max(b[2] + b[4] for b in bx) * s; y1 = max(b[3] + b[5] for b in bx) * s
    m = 0.04 * W
    x0, y0, x1, y1 = int(max(0, x0 - m)), int(max(0, y0 - m)), int(min(W, x1 + m)), int(min(H, y1 + m))
    cut = im[y0:y1, x0:x1]
    if cut.shape[1] > 900:
        f = 900 / cut.shape[1]
        cut = cv2.resize(cut, (900, int(cut.shape[0] * f)), interpolation=cv2.INTER_AREA)
    out = f"crops/{name}.jpg"
    cv2.imwrite(cd.OUT + out, cut, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return dict(file=out, page_image=f"{stem}_p{page:03d}.jpg", box_px=[x0, y0, x1 - x0, y1 - y0])


# the one accepted link whose target is itself one of the 600
inside = c.execute("""SELECT l.cited_work_pk, l.via_mention_pk, p.pub_id, d.stem FROM citation_links l JOIN publications p ON p.pub_id=l.target_pub_id
        JOIN documents d ON d.pub_id=p.pub_id WHERE l.status='accepted' AND p.status='final'""").fetchone()
inside_mid = c.execute("SELECT mention_id FROM citation_mentions WHERE mention_pk=?", (inside[1],)).fetchone()[0] if inside else None

EX = [
    dict(key="a_good_catalogue", probe="A", verdict="right", title="A cited article found in Mandumah's catalogue",
         stem="0527-055-002-059", page=23, note="r3",
         matched="catalogue c999 1089103 (Mandumah record of the same article, same author, 2020)",
         lesson="Arabic journal articles are where catalogue links work: about a third of Arabic-script articles, theses and conference papers are held."),
    dict(key="a_bad_generic_journal", probe="A", verdict="wrong", title="A generic journal name matched to the wrong journal",
         stem="1787-014-002-007", page=24, note="r6",
         matched="journal code 0081 «مجلة كلية التربية» (one of dozens of journals with this name)",
         lesson="Generic journal names need the university parsed from the citation before any journal count."),
    dict(key="a_good_doi", probe="A", verdict="right", title="A Latin-script article resolved to a DOI (source: crossref)",
         stem="0527-055-002-016", page=15, note="r23", matched="DOI 10.1016/j.qref.2005.11.007 (source: crossref)",
         lesson="Crossref finds ~56% of Latin-script journal articles at ≥0.8, 29 of 30 right; books it cannot do."),
    dict(key="b_good_lisan", probe="B", verdict="right", title="One work across 14 articles: Lisan al-'Arab",
         mid="2005-019-003-008|p14|w189-210|1", matched="cited work C7H83S6DX4 «لسان العرب» (14 citing articles)",
         lesson="The classical core (lexica, biographical dictionaries) is what joins articles today."),
    dict(key="b_bad_diwan", probe="B", verdict="wrong", title="Six poets' diwans on one card",
         mid="1967-000-008-012|p13|w13-26|1", matched="cited work CK4KYP6BAX «الديوان» (8 citing articles: an over-merge)",
         lesson="A title-only join through a citation that prints no author chains different works; it would rank #3 in the top-cited list."),
    dict(key="b_bad_backref", probe="B", verdict="wrong", title="op. cit. resolved to the wrong Sartre",
         mid="2051-000-002-017|p6|w362-377|1", matched="resolved to fn-p5-5, Sartre's own «Transcendance de l'ego»; the book is Cabestan & Tomes, «Sartre»",
         lesson="Back references are 95% right overall; the errors sit in small categories."),
    dict(key="c_good_selfcite", probe="C", verdict="right", title="A true self-citation",
         stem="0046-033-064-002", page=25, note="r12", matched="byline «د. عيد مرعي» = cited author «مرعي، عيد»",
         lesson="35 of 40 self-citations the view reports are true; 40 of the 59 citations byline persons receive from the 600 are self-citations."),
    dict(key="c_bad_authority", probe="C", verdict="link right, entity mixed", title="One authority id, two men named Muhammad Kamil Husayn",
         stem="0763-004-002-001", block="p4b5",
         matched="authority 213172 «حسين، محمد كامل، ت. 1977 م»: the Fatimid scholar and the surgeon-novelist",
         lesson="About 10% of authority ids hold another person's records; those go straight into an h-index."),
]
if inside_mid:
    EX.append(dict(key="d_inside_corpus", probe="D", verdict="right (link47 accepted)",
                   title="The only citation in the 600 whose cited article is itself one of the 600",
                   mid=inside_mid, matched=f"publication {inside[2]} «هل يمكن قيام أخلاق وجودية ؟» (Badawi, 1953) = stem {inside[3]}; title and author agree, cited by a 1958 article",
                   lesson="1 of 9,679 citations lands inside the parsed corpus today."))
cards = []
for e in EX:
    if e.get("block"):
        bx = boxes_for_block(e["stem"], e["block"]); mid = None
    else:
        mid, bx = boxes_for_mention(e.get("mid"), e.get("stem"), e.get("page"), e.get("note"))
    pr = c.execute("SELECT printed, page, container_id FROM citation_mentions WHERE mention_id=?", (mid,)).fetchone() if mid else None
    if e.get("block"):
        t = c.execute("""SELECT b.text, b.page FROM blocks b JOIN versions v ON v.version_id=b.version_id AND v.is_current=1
                         WHERE v.stem=? AND b.block_id=?""", (e["stem"], e["block"])).fetchone()
        pr = (t[0], t[1], e["block"]) if t else None
    cr = crop(e["key"], bx)
    stem = (mid.split("|")[0] if mid else e.get("stem"))
    cards.append(dict(key=e["key"], probe=e["probe"], verdict=e["verdict"], title=e["title"], stem=stem,
                      page=pr[1] if pr else e.get("page"), note_id=pr[2] if pr else e.get("note"), mention_id=mid,
                      printed=pr[0] if pr else None, matched_to=e["matched"], lesson=e["lesson"], crop=cr))
    print(e["key"], mid, cr)

# fate by kind for the page
fate = d1["citation_fate"]
page = dict(
    title="Experiment 48 — linking probe: metrics dry run on 600 articles",
    judged_by="agents (Claude), probes A-D; no person checked these verdicts",
    warning=d1["warning"],
    citation_fate=dict(total=fate["total_mentions"], totals=fate["totals"], shares=fate["shares"], by_kind=fate["by_kind"],
                       inside_the_600=fate["inside_the_600"],
                       categories=["held by Mandumah", "review/study/part held", "journal held", "DOI found (Crossref/OpenAlex)", "unlinkable"],
                       note=fate["note"],
                       probe_A_shares_of_9775="held ~2.9% (2.6-3.6), relation 2.5%, journal held 3.2% (incl. held), DOI ~8% projected, unlinkable ~86%"),
    cited_work_types=dict(works=A["A1"]["type_distribution_works"], mentions=A["A1"]["type_distribution_mentions"],
                          note="probe A's regex classifier (not separately judged); 57% of cited works are Latin-script"),
    top30_cited_works=d1["top30_clean"],
    top_held_articles=d1["held_top15_union"],
    top_held_journals=d1["journal_level"]["top15"],
    cocitation_network=dict(kind="bibliographic coupling (articles joined by a shared cited work; probe B's 'co-citation')",
                            summary=d1["coupling"], nodes=nets["coupling"]["nodes"], edges=nets["coupling"]["edges"]),
    coauthorship_network=dict(summary=d1["coauthorship"], nodes=nets["coauthorship"]["nodes"], edges=nets["coauthorship"]["edges"]),
    growth_curves=dict(sizes=[int(k) for k in d2["curves"]],
                       series={k: [d2["curves"][n][k]["mean"] for n in d2["curves"]] for k in
                               ("shared_works", "coupled_articles", "coupling_edges", "largest_component", "held_share",
                                "shared_mention_share", "inside_corpus_mentions", "citing_articles")},
                       sd={k: [d2["curves"][n][k]["sd"] for n in d2["curves"]] for k in
                           ("shared_works", "coupled_articles", "largest_component", "held_share")},
                       fits=d2["power_law_fits_100_to_600"], caution=d2["caution"], seeds=d2["seeds"]),
    h_index=dict((k, d1["h_index"][k]) for k in ("byline_persons", "with_authority", "route_held_links", "route_author_linked_cards")),
    self_citation=dict((k, d1["self_citation"][k]) for k in d1["self_citation"] if k != "top"),
    trending=d1["trending"],
    impact_factor=d1["impact_factor_ingredients"],
    workload=dict(rows=[dict((k, r.get(k)) for k in ("rank", "decision", "probe", "count_600", "per_article", "decisions_1M",
                                                    "minutes", "hours_1M", "hours_per_corrector", "metrics", "after_rules",
                                                    "decisions_1M_prioritised", "hours_1M_prioritised", "hours_per_corrector_prioritised"))
                        for r in d3["rows"]],
                  audit=d3["audit"], total_hours_1M=d3["total_hours_1M"], hours_per_corrector=d3["hours_per_corrector"],
                  working_days_team=d3["working_days_team"], safe_to_leave_unlinked=d3["safe_to_leave_unlinked"],
                  caveats=d3["caveats"]),
    example_cards=cards,
)
cd.save("page_data.json", page)
print("nodes", len(page["cocitation_network"]["nodes"]), "edges", len(page["cocitation_network"]["edges"]))
