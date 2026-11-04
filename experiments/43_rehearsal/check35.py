"""Experiment 43: the prompt v3.5 check (README "Prompt v3.5 (draft, 2026-10-22)"; plan out/v35_check/PLAN_v35.md).
No model calls: this scores answers that run43.py fetched (once the owner approves a cap).

    check35.py build    the v3.5 answers (out/v35_check/raw) and the v3.3 answers of the same articles through
                        today's rules + masters, side by side: out/v35_check/{v35,v33}/{rules,masters}; every master
                        checked against the JATS DTD and the ALTO XSD; the v3.3 replicates (where they exist) through
                        today's rules: out/v35_check/v33rep/rules
    check35.py score    out/v35_check/score.json + score.md (+ fields.md, the new fields for a person to look at):
        structure       per article, v3.5 against v3.3: share of Azure lines whose block type is the same, reading
                        order agreement (blocks keyed by their first line, page by page), block counts by type,
                        pages whose blocks changed; the same numbers v3.3 against its own replicate (run-to-run
                        noise) where one exists; the v3.4 loss pages (1010-006 pp 2 and 4: the advert; 0787 p 9: the
                        paragraphs) block by block
        gold            the owner's gold articles (gold43 snapshots): differences and JATS words off, v3.5 against
                        v3.3 and its replicate (the G0 yardstick: out/stepEF/g0/gold.json)
        new fields      everything "enrich" and the new keys of cited works hold, after rules43's check (what was
                        dropped and why), and the JATS homes they reached in the masters, for both arms
        fixes           the model's fixes, misprints, fixes in fully vowelled lines, honorific glyphs written, math
        cost            input / output tokens and dollars per article and per page, v3.5 against v3.3 (same chunks)

Articles: CHECK below (sets a and b of run43.py); the v3.3 answers are the first 300's run (out/v33_300/raw) for
set b and step G0's v3.3 arm (out/g0a_v33_low/raw) for the gold articles of set a.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE / "out"
D = OUT / "v35_check"

# why each article is in the check (inventory ids of experiment 51 in brackets)
CHECK = {
    "2382-005-003-001": ("a", "gold; English references, history dates, affiliation parts, translated title"),
    "0747-001-003-001": ("a", "gold; vowelled verse, glossary notes, a printed editor (ضبطها وشرحها), Hijri years"),
    "0069-000-026-005": ("b", "an English byline twin «Prof. Ibrahim Khalil» [x024]; تحقيق, ترجمة, ص cited pages, "
                              "death years (761هـ) [x117-x121, x127]"),
    "1608-023-001-025": ("b", "editors تحقيق (38), editions (10), access dates «Retrieved» (12) [x118, x120, x133]"),
    "0500-015-002-013": ("b", "«Corresponding author» [x026]; «المصدر:» under tables (12) [x112]; تحقيق"),
    "0412-005-001-005": ("b", "manuscripts cited (55) with folios [x137]; Hijri years"),
    "0042-004-009-012": ("b", "a conference report: the conference line in the subtitle today [x003, x063]"),
    "0295-016-002-014": ("b", "a book review and a translation («اختيار وترجمة») of documents [x066, x067]"),
    "0881-031-355-002": ("b", "a news page [x061]"),
    "1875-005-020-001": ("b", "fully vowelled verse: letters Azure drops (p17 «الزَّاد») [x178, v3.4 line]"),
    "1010-006-011-015": ("b", "the advert v3.4 shredded in 2 of 2 runs (pp 2, 4) [v3.4 regression]"),
    "0787-011-001-003": ("b", "paragraphs v3.4 merged in 2 of 2 runs (p 9) [v3.4 regression]"),
}
EXTRA_GOLD = {"0877-007-027-003": ("a", "gold"), "0924-012-005-007": ("a", "gold; table headers with units"),
              "1140-000-021-003": ("a", "gold; French CV and list of own works")}
WATCH = [("1010-006-011-015", 2), ("1010-006-011-015", 4), ("0787-011-001-003", 9)]
BASE_RAW = {"a": OUT / "g0a_v33_low" / "raw", "b": OUT / "v33_300" / "raw"}
REP_RAW = {"a": OUT / "g0a_v33_low_rep" / "raw", "b": OUT / "g0_v33_low_rep" / "raw"}
HONORIFIC = re.compile("[ﷺﷻﷲ﷽]")


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def jdump(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def stems_of(args) -> dict:
    s = dict(CHECK)
    if getattr(args, "extra_gold", False):
        s.update(EXTRA_GOLD)
    if getattr(args, "stems", None):
        s = {k: v for k, v in s.items() if k in args.stems}
    return s


def chunk_recs(a, raw: Path) -> list[dict] | None:
    from masters43 import ST
    out = []
    for x, y in ST.chunks(a):
        f = raw / f"{a['stem']}_c{x:03d}-{y:03d}.json"
        if not f.exists():
            return None
        out.append(jl(f))
    return out


# ------------------------------------------------------------------------------------------------ build

def build_arm(stems: dict, raw_of, dst: Path, masters: bool = True) -> dict:
    import flags43 as F
    import masters43 as M43
    import replay43 as RP
    from masters43 import ST
    arts = F.all_articles()
    res = {}
    for s in stems:
        a = arts[s]
        F.use_pages_of(a)
        raw = raw_of(a)
        recs = chunk_recs(a, raw) if raw else None
        if recs is None:
            res[s] = dict(missing=True)
            continue
        for x_y, rec in zip(ST.chunks(a), recs):
            ans, log = RP.apply_rules(a, rec)
            RP.jdump(dst / "rules" / f"{s}_c{x_y[0]:03d}-{x_y[1]:03d}.json", dict(rec, answer=ans, rules43=log))
        if not masters:
            res[s] = dict(rules=True)
            continue
        from inkscript.enrich.schemas import validate_alto, validate_jats
        try:
            r = M43.build43(a, dst / "rules", dst / "masters", True, run=dst.name)
        except Exception as e:                    # one article's failure must not stop the rest (latex2mathml...)
            res[s] = dict(error=f"{type(e).__name__}: {e}")
            print(f"  {dst.name:7} {s:24} ERROR {res[s]['error'][:90]}", flush=True)
            continue
        j = validate_jats(dst / "masters" / f"{s}.jats.xml")
        al = validate_alto(dst / "masters" / f"{s}.alto.xml")
        res[s] = dict(error=r.get("error"), jats_errors=j[:3], alto_errors=al[:3])
        print(f"  {dst.name:7} {s:24} {'ERROR ' + r['error'] if r.get('error') else 'ok'}"
              f"{' INVALID' if j or al else ' valid'}", flush=True)
    return res


def cmd_build(args):
    stems = stems_of(args)
    res = dict(v35=build_arm(stems, lambda a: D / "raw", D / "v35"),
               v33=build_arm(stems, lambda a: BASE_RAW[stems[a["stem"]][0]], D / "v33"),
               v33rep=build_arm({s: v for s, v in stems.items() if any(REP_RAW[v[0]].glob(f"{s}_c*.json"))},
                                lambda a: REP_RAW[stems[a["stem"]][0]], D / "v33rep", masters=False))
    jdump(D / "build.json", res)
    bad = [s for arm in ("v35", "v33") for s, r in res[arm].items() if r.get("error") or r.get("jats_errors")
           or r.get("alto_errors")]
    print("all JATS DTD + ALTO XSD valid" if not bad else f"invalid or failed: {bad}")


# ------------------------------------------------------------------------------------------------ score

def rules_answers(dst: Path, stem: str) -> list[dict]:
    return [jl(f) for f in sorted((dst / "rules").glob(f"{stem}_c*.json"))]


def line_types(recs) -> tuple[dict, dict]:
    """line id -> block type; page -> [first line of each block, in reading order] (after rules43)."""
    import rules43 as RU
    ty, order = {}, {}
    for r in recs:
        for pg in (r["answer"].get("pages") or []):
            if not isinstance(pg, dict):
                continue
            for b in pg.get("blocks") or []:
                if not isinstance(b, dict):
                    continue
                ids = [re.sub(r"[a-p]$", "", str(i)) for i in RU.block_ids(b)]
                t = b.get("type")
                if t == "figure" and "other" in str(b.get("level") or ""):
                    t = "figure_other"
                for i in ids:
                    ty.setdefault(i, t)
                if ids:
                    order.setdefault(pg.get("page"), []).append(ids[0])
    return ty, order


def compare(ra, rb) -> dict:
    ta, oa = line_types(ra)
    tb, ob = line_types(rb)
    common = set(ta) & set(tb)
    same = sum(1 for i in common if ta[i] == tb[i])
    pairs = ok = 0
    pages_changed = []
    for p in sorted(set(oa) | set(ob), key=lambda v: int(v or 0)):
        A, B = oa.get(p, []), ob.get(p, [])
        keys = [k for k in A if k in set(B)]
        kb = [k for k in B if k in set(A)]
        sm = difflib.SequenceMatcher(a=keys, b=kb, autojunk=False)
        ok += sum(m.size for m in sm.get_matching_blocks())
        pairs += len(keys)
        sig_a = [(ta.get(k), k) for k in A]
        sig_b = [(tb.get(k), k) for k in B]
        if sig_a != sig_b:
            pages_changed.append(p)
    ca, cb = Counter(ta.values()), Counter(tb.values())
    return dict(lines_both=len(common), type_same=round(same / max(1, len(common)), 4),
                lines_only_one=len(set(ta) ^ set(tb)), order_same=round(ok / max(1, pairs), 4),
                pages_changed=pages_changed, line_types_a=dict(ca), line_types_b=dict(cb),
                type_changes=dict(Counter(f"{ta[i]}->{tb[i]}" for i in common if ta[i] != tb[i]).most_common(8)))


def page_blocks(recs, page) -> list[str]:
    out = []
    for r in recs:
        for pg in r["answer"].get("pages") or []:
            if isinstance(pg, dict) and pg.get("page") == page:
                for b in pg.get("blocks") or []:
                    if isinstance(b, dict):
                        n = len(b.get("lines") or b.get("hemistichs") or b.get("rows") or [])
                        out.append(f"{b.get('type')}{'(' + str(b.get('level')) + ')' if b.get('level') else ''}:{n}")
    return out


def fixes_of(recs, a) -> dict:
    import ab43
    from masters43 import ST
    c = Counter()
    for r in recs:
        lines = {}
        for p in range(r["first"], r["last"] + 1):
            for L in ST.page_lines(a, p)[0]:
                lines[str(L["id"])] = L["text"]
        ans = r["answer"]
        for fx in ans.get("fixes") or []:
            if str(fx.get("why") or "").startswith("code:"):
                continue
            c["fixes"] += 1
            if ab43.vowelled(lines.get(str(fx.get("line")), "")):
                c["fixes_vowelled"] += 1
            if HONORIFIC.search(str(fx.get("to") or "")) and not HONORIFIC.search(str(fx.get("from") or "")):
                c["honorific_glyphs_written"] += 1
        c["sic"] += len(ans.get("sic") or [])
        c["math"] += len(ans.get("math") or [])
        c["missed"] += len(ans.get("missed") or [])
    return dict(c)


def cost_of(raw: Path, stem: str) -> dict:
    c = Counter()
    for f in sorted(raw.glob(f"{stem}_c*.json")):
        if f.name.endswith(".failed.json"):
            c["failed"] += 1
            continue
        r = jl(f)
        c["chunks"] += 1
        c["pages"] += r["last"] - r["first"] + 1
        for k in ("tin", "tout", "think"):
            c[k] += r.get(k) or 0
        c["usd"] += r.get("usd") or 0
        c["max_tokens"] += "MAX_TOKENS" in str(r.get("finish"))
    c["usd"] = round(c["usd"], 5)
    return dict(c)


V35_W = ("editors", "translators", "edition", "cal", "year2", "cited", "accessed", "library", "shelf", "folio", "conf",
         "degree")
JATS_HOMES = {
    "subj-group document-type": ".//subj-group[@subj-group-type='document-type']",
    "conference": ".//article-meta/conference", "product": ".//article-meta/product",
    "related-article translated-from": ".//related-article[@related-article-type='translated-from']",
    "contrib @corresp": ".//contrib[@corresp='yes']", "contrib-id orcid": ".//contrib-id[@contrib-id-type='orcid']",
    "author-notes fn": ".//author-notes/fn", "aff faculty": ".//aff/institution[@content-type='faculty']",
    "aff additional": ".//aff[@content-type='additional']", "fig @fig-type": ".//fig[@fig-type]",
    "table-wrap-foot p": ".//table-wrap-foot/p", "fig p source": ".//fig/p[@content-type='source']",
    "fn custom-type": ".//fn[@custom-type]", "edition": ".//element-citation/edition",
    "person-group editor": ".//element-citation/person-group[@person-group-type='editor']",
    "person-group translator": ".//element-citation/person-group[@person-group-type='translator']",
    "year @calendar": ".//element-citation/year[@calendar]",
    "page-range cited-pages": ".//element-citation/page-range[@content-type='cited-pages']",
    "date-in-citation access-date": ".//element-citation/date-in-citation[@content-type='access-date']",
    "comment death-date": ".//element-citation/comment[@content-type='death-date']",
    "manuscript library / folio": ".//element-citation/institution[@content-type='library']",
    "conf-name in citation": ".//element-citation/conf-name",
    "custom-meta scan / marks / series": ".//custom-meta[@id='enrich-scan']|.//custom-meta[@id='enrich-handwriting']"
                                         "|.//custom-meta[@id='enrich-stamp']|.//custom-meta[@id='enrich-series-part']",
    "element-citation (all)": ".//element-citation",
}


def homes(mast: Path, stem: str) -> dict:
    from lxml import etree
    f = mast / f"{stem}.jats.xml"
    if not f.exists():
        return {}
    r = etree.parse(str(f), etree.XMLParser(load_dtd=False, no_network=True)).getroot()
    out = {k: len(r.findall(x)) if "|" not in x else len(r.xpath(x.replace(".//", "//"))) for k, x in JATS_HOMES.items()}
    out["article-type"] = r.get("article-type")
    return out


def new_fields(recs) -> dict:
    """What the v3.5 answer added, after rules43's check: enrich (+ drops) and the new keys of cited works."""
    import refs43
    en, drops, works = [], [], []
    for r in recs:
        ans = r["answer"]
        e = ans.get("enrich")
        if e:
            en.append(dict(first=r["first"], last=r["last"], enrich=e))
        drops += (r.get("rules43") or {}).get("enrich") or []
        kinds = {pg.get("page"): [b.get("_kind") for b in pg.get("blocks") or [] if isinstance(b, dict)
                                  and b.get("_kind")] for pg in ans.get("pages") or [] if isinstance(pg, dict)}
        if any(kinds.values()) and en and en[-1]["first"] == r["first"]:
            en[-1]["figure_kinds"] = {p: k for p, k in kinds.items() if k}
        for kind, lid, ws in refs43.parsed_blocks([ans]):
            for w in ws:
                extra = {k: w[k] for k in V35_W if k in w}
                died = [au.get("died") for au in w.get("authors") or [] if isinstance(au, dict) and au.get("died")]
                if died:
                    extra["died"] = died
                if extra:
                    works.append(dict(kind=kind, line=lid, title=w.get("title"), extra=extra))
    return dict(enrich=en, dropped=drops, works_with_new_keys=works)


def printed_line(a, lid: str) -> str:
    from masters43 import ST
    try:
        p = int(str(lid).split(":")[0])
        return next((L["text"] for L in ST.page_lines(a, p)[0] if str(L["id"]) == re.sub(r"[a-p]$", "", lid)), "")
    except Exception:                                         # noqa: BLE001
        return ""


def cmd_score(args):
    import flags43 as F
    import gold43 as GD
    stems = stems_of(args)
    arts = F.all_articles()
    res, md, fld = {}, [], ["# v3.5 check: the new fields, for a person to look at", "",
                           "Local only (Mandumah's text). Each value is what rules43 kept after its check; "
                           "dropped values are listed with the reason.", ""]
    tot = Counter()
    for s, (st_, why) in stems.items():
        a = arts[s]
        F.use_pages_of(a)
        new, old = rules_answers(D / "v35", s), rules_answers(D / "v33", s)
        if not new:
            res[s] = dict(missing="no v3.5 answers")
            continue
        rep = rules_answers(D / "v33rep", s)
        r = dict(why=why, structure=compare(old, new), noise=compare(old, rep) if rep else None,
                 fixes_v33=fixes_of(old, a), fixes_v35=fixes_of(new, a),
                 cost_v33=cost_of(BASE_RAW[st_], s), cost_v35=cost_of(D / "raw", s),
                 homes_v33=homes(D / "v33" / "masters", s), homes_v35=homes(D / "v35" / "masters", s),
                 fields=new_fields(new))
        r["watch"] = {p: dict(v33=page_blocks(old, p), v35=page_blocks(new, p), v33rep=page_blocks(rep, p) if rep else None)
                      for st2, p in WATCH if st2 == s}
        if st_ == "a" and list(GD.GOLD.glob(f"{s}__*.json")):
            g = jl(next(GD.GOLD.glob(f"{s}__*.json")))
            gr = {}
            for arm, raw in (("v35", D / "raw"), ("v33", BASE_RAW["a"]), ("v33rep", REP_RAW["a"])):
                if not any(raw.glob(f"{s}_c*.json")):
                    continue
                try:
                    now = GD.snapshot(a, raw)
                except Exception as e:            # e.g. latex2mathml missing for an article with equations
                    gr[arm] = dict(error=f"{type(e).__name__}: {e}")
                    continue
                d = GD.diff(g["snapshot"], now, g["scope"])
                gw, nw = g["snapshot"]["jats"]["text"].split(), now["jats"]["text"].split()
                sm = difflib.SequenceMatcher(a=gw, b=nw, autojunk=False)
                gr[arm] = dict(differences=len(d), words_off=sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2
                                                                 in sm.get_opcodes() if op != "equal"), words=len(gw))
            r["gold"] = gr
        res[s] = r
        for arm in ("v33", "v35"):
            for k, v in r[f"cost_{arm}"].items():
                tot[f"{arm}_{k}"] += v
        # the person's list
        fld += [f"## {s} — {why}", ""]
        for e in r["fields"]["enrich"]:
            fld.append(f"- pages {e['first']}–{e['last']}: `{json.dumps(e['enrich'], ensure_ascii=False)}`"
                       + (f"; figure kinds by page `{json.dumps(e['figure_kinds'], ensure_ascii=False)}`"
                          if e.get("figure_kinds") else ""))
        for e in r["fields"]["works_with_new_keys"]:
            fld.append(f"- {e['kind']} at {e['line']} «{printed_line(a, e['line'])[:90]}»: «{(e['title'] or '')[:60]}» "
                       f"`{json.dumps(e['extra'], ensure_ascii=False)}`")
        for d in r["fields"]["dropped"]:
            fld.append(f"- dropped {d['key']} «{d['value']}»: {d['why']}")
        fld += ["", "JATS homes (v3.3 → v3.5): " + ", ".join(
            f"{k} {r['homes_v33'].get(k)}→{v}" for k, v in r["homes_v35"].items() if v != r["homes_v33"].get(k)), ""]
    # summary
    pg3, pg5 = tot["v33_pages"] or 1, tot["v35_pages"] or 1
    summ = dict(articles=len([v for v in res.values() if "structure" in v]),
                v33=dict(pages=tot["v33_pages"], tin=tot["v33_tin"], tout=tot["v33_tout"], usd=round(tot["v33_usd"], 4),
                         out_per_page=round(tot["v33_tout"] / pg3), in_per_page=round(tot["v33_tin"] / pg3),
                         usd_per_page=round(tot["v33_usd"] / pg3, 5)),
                v35=dict(pages=tot["v35_pages"], tin=tot["v35_tin"], tout=tot["v35_tout"], usd=round(tot["v35_usd"], 4),
                         out_per_page=round(tot["v35_tout"] / pg5), in_per_page=round(tot["v35_tin"] / pg5),
                         usd_per_page=round(tot["v35_usd"] / pg5, 5), max_tokens=tot["v35_max_tokens"],
                         failed=tot["v35_failed"]))
    jdump(D / "score.json", dict(summary=summ, articles=res))
    md += ["# Prompt v3.5 check: score", "", f"Articles scored: {summ['articles']}. v3.3 = the same articles' v3.3 "
           "answers, both through today's rules and masters (only the prompt differs).", "",
           "| | pages | in tokens / page | out tokens / page | $ / page | $ |", "|---|---|---|---|---|---|",
           *[f"| {k} | {v['pages']} | {v['in_per_page']} | {v['out_per_page']} | {v['usd_per_page']} | {v['usd']} |"
             for k, v in (("v3.3", summ["v33"]), ("v3.5", summ["v35"]))], "",
           "## Structure (v3.5 against v3.3; noise = v3.3 against its own replicate)", "",
           "| article | lines same type | order same | pages changed | noise: type / order | top type changes |",
           "|---|---|---|---|---|---|"]
    for s, r in res.items():
        if "structure" not in r:
            md.append(f"| {s} | (no v3.5 answer) | | | | |")
            continue
        x, n = r["structure"], r["noise"]
        noise = f"{n['type_same']:.1%} / {n['order_same']:.1%}" if n else "–"
        top = ", ".join(f"{k} {v}" for k, v in list(x["type_changes"].items())[:3])
        md.append(f"| {s} | {x['type_same']:.1%} | {x['order_same']:.1%} | {len(x['pages_changed'])} | {noise} | {top} |")
    md += ["", "## The v3.4 loss pages", ""]
    for s, r in res.items():
        for p, w in (r.get("watch") or {}).items():
            md += [f"- {s} p{p}: v3.3 {w['v33']}", f"  v3.5 {w['v35']}"] + ([f"  v3.3 rep {w['v33rep']}"] if w["v33rep"]
                                                                           else [])
    md += ["", "## Gold (differences from the owner's snapshots; G0: v3.3 / rep / v3.4 in out/stepEF/g0/gold.json)", ""]
    for s, r in res.items():
        if r.get("gold"):
            md.append(f"- {s}: " + "; ".join(f"{k} {v['differences']} differences, {v['words_off']} words off"
                                             if "error" not in v else f"{k} {v['error'][:60]}"
                                             for k, v in r["gold"].items()))
    md += ["", "## Fixes (the model's) v3.3 → v3.5", "",
           "| article | fixes | in vowelled lines | sic | math | honorific glyphs written |", "|---|---|---|---|---|---|"]
    for s, r in res.items():
        if "fixes_v35" in r:
            a3, a5 = r["fixes_v33"], r["fixes_v35"]
            md.append(f"| {s} | {a3.get('fixes', 0)} → {a5.get('fixes', 0)} | {a3.get('fixes_vowelled', 0)} → "
                      f"{a5.get('fixes_vowelled', 0)} | {a3.get('sic', 0)} → {a5.get('sic', 0)} | {a3.get('math', 0)} → "
                      f"{a5.get('math', 0)} | {a5.get('honorific_glyphs_written', 0)} |")
    md += ["", "New fields, value by value: fields.md. Every number: score.json."]
    (D / "score.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (D / "fields.md").write_text("\n".join(fld) + "\n", encoding="utf-8")
    print("\n".join(md))


# extra output tokens v3.5 should write (estimate, before any call; the check measures the real number): the
# "enrich" part (article keys on the first chunk, page keys on each), the new keys of cited works, v3.4's two
# content lines (G0: +22 fixes in vowelled lines on 185 pages, ~35 tokens a fix)
EXTRA_OUT = dict(per_first_chunk=60, per_chunk=12, per_page=6, per_work=12, per_page_fixes=4)


def cmd_price(args):
    """The check priced from the same chunks' real v3.3 tokens (no calls): input = v3.3's billed input scaled by the
    v3.5 prompt's length (ST.est_tokens ratio); output = v3.3's billed output + EXTRA_OUT; worst case = the larger
    of that input and run43's cap estimate (est_tokens of the v3.5 prompt) + each request's maxOutputTokens (Batch
    limit 32,768), all of it billed."""
    import flags43 as F
    import prompt43 as P
    import rechunk43
    import refs43
    import run43
    from masters43 import ST
    stems = stems_of(args)
    arts = F.all_articles()
    rows, T = [], Counter()
    for s, (st_, why) in stems.items():
        a = arts[s]
        F.use_pages_of(a)
        for ci, (x, y) in enumerate(ST.chunks(a)):
            f = BASE_RAW[st_] / f"{s}_c{x:03d}-{y:03d}.json"
            r = jl(f)
            state = dict(outline="[]" * 30, btype="paragraph", last="x" * 500) if ci else None
            nimg = (y - x + 1) + (x > 1)
            P.use("v3.3")
            e33 = ST.est_tokens(P.prompt_text_only(a, ci, x, y, state), nimg)
            P.use("v3.5")
            e35 = ST.est_tokens(P.prompt_text_only(a, ci, x, y, state), nimg)
            works = sum(len(ws) for _, _, ws in refs43.parsed_blocks([r["answer"]]))
            k = y - x + 1
            extra = (EXTRA_OUT["per_first_chunk"] if ci == 0 else 0) + EXTRA_OUT["per_chunk"] + \
                (EXTRA_OUT["per_page"] + EXTRA_OUT["per_page_fixes"]) * k + EXTRA_OUT["per_work"] * works
            tin = (r.get("tin") or 0) * e35 / e33
            mo = min(rechunk43.max_out_for(a, x, y) or run43.max_out(k), run43.BATCH_MAX_OUT)
            row = dict(stem=s, chunk=f"{x}-{y}", pages=k, works=works, tin_v33=r.get("tin"), tout_v33=r.get("tout"),
                       est_in_v33=e33, est_in_v35=e35, tin_v35=round(tin), tout_v35=(r.get("tout") or 0) + extra,
                       extra_out=extra, max_out=mo, worst_in=max(round(tin), e35))
            rows.append(row)
            for kk in ("pages", "works", "tin_v33", "tout_v33", "tin_v35", "tout_v35", "extra_out", "est_in_v35",
                       "max_out", "est_in_v33", "worst_in"):
                T[kk] += row[kk] or 0
            T["requests"] += 1
    P.use("v3.5")
    out = dict(rows=rows, totals=dict(T), extra_out_assumed=EXTRA_OUT, usd={})
    for mode in ("batch", "standard"):
        for label, when in (("now", None), ("from 2026-12-01", "2026-12-01")):
            pin, pout = run43.price(mode, when)
            out["usd"][f"{mode} {label}"] = dict(
                v33_billed_tokens=round(T["tin_v33"] / 1e6 * pin + T["tout_v33"] / 1e6 * pout, 3),
                expected=round(T["tin_v35"] / 1e6 * pin + T["tout_v35"] / 1e6 * pout, 3),
                worst=round(T["worst_in"] / 1e6 * pin + T["max_out"] / 1e6 * pout, 3))
    pg = T["pages"] or 1
    out["per_page"] = dict(in_v33=round(T["tin_v33"] / pg), in_v35=round(T["tin_v35"] / pg),
                           out_v33=round(T["tout_v33"] / pg), out_v35=round(T["tout_v35"] / pg),
                           extra_out=round(T["extra_out"] / pg, 1))
    jdump(D / ("price_extra.json" if args.extra_gold else "price.json"), out)
    print(json.dumps(dict(totals=out["totals"], per_page=out["per_page"], usd=out["usd"]), indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "score", "list", "price"])
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--extra-gold", action="store_true", help="also the other three gold articles (0877, 0924, 1140)")
    ap.add_argument("--dir", help="the check's folder (default out/v35_check; a test folder for simulated answers)")
    args = ap.parse_args()
    global D
    if args.dir:
        D = Path(args.dir).resolve()
    if args.cmd == "list":
        for s, (st_, why) in stems_of(args).items():
            print(st_, s, why)
    elif args.cmd == "build":
        cmd_build(args)
    elif args.cmd == "price":
        cmd_price(args)
    else:
        cmd_score(args)


if __name__ == "__main__":
    main()
