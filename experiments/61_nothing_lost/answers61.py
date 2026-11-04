"""Experiment 61: ANSWER, BILINGUAL and PLATFORM accounting for one article (called by audit61.audit_article).

answer_accounting  every value of Gemini's answer -> "stored" (in its own JATS field), "elsewhere" (in another
                   specific field), "flattened" (only inside generic text: a front-matter block, an «other»
                   paragraph), "dropped" (nowhere), with the code's reason where it is known
bilingual          title, author names, affiliations, positions, abstracts, keywords: which scripts are printed,
                   which are stored as fields in the JATS and in the platform, and whether the two forms are linked
platform_accounting JATS counts against platform rows, element by element
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

import fields61 as F

# the reasons found in the code for each known drop (README "Mapping fixes" has the fix for each)
REASON = {
    "position": "meta43.names_pre writes <role> only when the phrase names a translator / reviewer / editor / "
                "supervisor / rapporteur (meta43.ROLES); an author's post or rank is dropped (masters41 "
                "Masters.authors() reads name, affiliation and email only)",
    "twin": "meta43.names_pre (Latin fold) / meta43.enrich (same_as) remove the twin contrib after copying its "
            "aff / email only when the main contrib has none",
    "subtitle": "masters41 Masters.front(): <subtitle> is written only when it is not inside the printed title "
                "lines (it stays part of article-title)",
    "enrich_unknown": "enrich43.KNOWN: an enrich key outside the list is not read",
    "refs": "refs43.citation ok(): a part that is not an exact substring of the printed entry is dropped",
    "history_type": "jats43 history: a date whose type is not received / revised / accepted / published / online",
}
AFF_TAG = {"dept": "aff_department", "faculty": "aff_faculty", "orgname": "aff_institution"}
W_TAGS = ("person-group", "name", "surname", "given-names", "string-name", "article-title", "chapter-title", "source",
          "year", "volume", "issue", "fpage", "lpage", "page-range", "publisher-name", "publisher-loc", "series",
          "pub-id", "ext-link", "edition", "comment", "date-in-citation", "institution", "conf-name", "conf-loc",
          "string-date")


def T(s):
    return F.toks(s)


def holds(vt: list[str], lists) -> bool:
    for L in lists:
        n = len(vt)
        if n and n <= len(L):
            for i in range(len(L) - n + 1):
                if L[i:i + n] == vt:
                    return True
        if len(vt) >= 3:
            s = set(L)
            if sum(1 for t in vt if t in s) >= 0.85 * len(vt):
                return True
    return False


def jats_texts(root) -> dict:
    out = defaultdict(list)
    for f, v in F.front_values(root):
        out[f].append(T(v))
    am = root.find("front/article-meta")
    if am is not None:
        for a in am.iter("aff"):
            for x in a:
                if not isinstance(x.tag, str):
                    continue
                if x.tag == "institution":
                    out[AFF_TAG.get(x.get("content-type"), "aff_institution")].append(T(F.text_of(x)))
                elif x.tag == "country":
                    out["aff_country"].append(T(F.text_of(x)))
                elif x.tag == "addr-line":
                    out["aff_city"].append(T(F.text_of(x)))
        for tag in ("volume", "issue", "fpage", "lpage"):
            for x in am.findall(tag):
                out[tag].append(T(F.text_of(x)))
        for d in am.iter("pub-date"):
            out["year"].append(T(F.text_of(d)))
        for sg in am.iter("subj-group"):
            if sg.get("subj-group-type") == "document-type":
                out["doc_type"].append(T(F.text_of(sg)))
        for cm in am.iter("custom-meta"):
            nm = (cm.findtext("meta-name") or "").strip()
            mv = F.text_of(cm.find("meta-value"))
            if nm == "front-matter-block":
                out["_generic"].append(T(mv))
            elif nm == "series-part":
                out["series_part"].append(T(mv))
    for p in root.iter("p"):
        if p.get("content-type") in ("other", "byline", "abstract", "keywords") and "abstract" not in [
                a.tag for a in p.iterancestors()]:
            out["_generic"].append(T(F.text_of(p)))
    for ec in root.iter("element-citation"):
        out["_cite"].append(T(F.text_of(ec)))
    for pr in root.iter("product"):
        out["_cite"].append(T(F.text_of(pr)))
    for at in root.iter("alt-text"):
        out["alt_text"].append(T(F.text_of(at)))
    return out


def status_of(value, want: tuple, J: dict) -> tuple[str, str | None]:
    vt = T(value)
    if not vt:
        return "empty", None
    for f in want:
        if holds(vt, J.get(f, [])):
            return "stored", f
    if len(vt) <= 2 and holds(vt, J.get("_generic", [])):
        return "flattened", "front-matter block / generic paragraph"
    for f, L in J.items():
        if f.startswith("_") or f in want:
            continue
        if holds(vt, L):
            return "elsewhere", f
    if holds(vt, J.get("_generic", [])):
        return "flattened", "front-matter block / generic paragraph"
    return "dropped", None


def answer_accounting(answers, root, words, lines_out, rlogs, prompt) -> dict:
    J = jats_texts(root)
    vals = []
    line_field = {L.get("az_id", L["id"]): (L["bucket"], L["field"]) for L in lines_out}
    twins = {F.fold(F.text_of(s)) for s in root.iter("string-name")
             if s.get("{http://www.w3.org/XML/1998/namespace}lang")}

    def add(key, field, value, want, reason=None):
        st, where = status_of(value, want, J)
        if st == "empty":
            return
        d = dict(key=key, field=field, value=str(value)[:300], status=st, where=where)
        if st != "stored" and reason:
            d["reason"] = reason
        vals.append(d)

    meta = next((j["answer"]["metadata"] for j in answers if isinstance((j.get("answer") or {}).get("metadata"),
                                                                        dict)), {}) or {}
    if meta.get("title"):
        add("metadata.title", "title", meta["title"], ("title",))
    if meta.get("subtitle"):
        st, where = status_of(meta["subtitle"], ("subtitle",), J)
        d = dict(key="metadata.subtitle", field="subtitle", value=str(meta["subtitle"])[:300], status=st, where=where)
        if st == "elsewhere" and where == "title":
            d["status"], d["reason"] = "flattened", REASON["subtitle"]
        vals.append(d)
    aus = [x for x in meta.get("authors") or [] if isinstance(x, dict)]
    for i, au in enumerate(aus):
        k = f"metadata.authors[{i}]"
        is_twin = F.fold(" ".join(str(au.get("name") or "").split())) in twins
        if au.get("name"):
            add(k + ".name", "author_name", au["name"], ("author_name",))
        if au.get("role"):
            add(k + ".role", "position", au["role"], ("position", "role"), REASON["position"])
        if au.get("affiliation"):
            add(k + ".affiliation", "affiliation", au["affiliation"], ("affiliation",),
                REASON["twin"] if is_twin else None)
        if au.get("email"):
            add(k + ".email", "email", au["email"], ("email",), REASON["twin"] if is_twin else None)
        for pk, pv in (au.get("aff_parts") or {}).items() if isinstance(au.get("aff_parts"), dict) else []:
            if pv:
                want = {"department": ("aff_department", "aff_faculty"), "institution": ("aff_institution",),
                        "city": ("aff_city",), "country": ("aff_country",)}.get(pk, ("aff_institution",))
                add(f"{k}.aff_parts.{pk}", "aff_parts", pv, want, REASON["twin"] if is_twin else None)
    for lang, ids in (meta.get("abstract") or {}).items() if isinstance(meta.get("abstract"), dict) else []:
        for lid in ids or []:
            lid = str(lid).rstrip("abcdefgh")
            b, f = line_field.get(lid, (None, None))
            if b is None:
                continue
            st = "stored" if (b == "a" and f == "abstract") else ("flattened" if b == "b" else
                                                                  "elsewhere" if b == "a" else "dropped")
            vals.append(dict(key=f"metadata.abstract.{lang}", field="abstract", value=lid, status=st, where=f))
    kw = meta.get("keywords") or {}
    for lang, v in kw.items() if isinstance(kw, dict) else []:
        for x in (v if isinstance(v, list) else [v]):
            if not x:
                continue
            # one string of several keywords: each keyword against the kwd elements
            parts = [p_ for p_ in re.split(r"[،,;؛]|\s-\s|\.\s", re.sub(r"^[^:]{0,40}:", "", str(x))) if F.toks(p_)]
            for p_ in parts or [x]:
                add(f"metadata.keywords.{lang}", "keywords", p_.strip(), ("keywords",))
    if meta.get("journal"):
        add("metadata.journal", "journal_info", meta["journal"], ("journal_info",))
    for k_ in ("volume", "issue"):
        if meta.get(k_):
            add(f"metadata.{k_}", "journal_info", meta[k_], (k_, "journal_info"))
    if meta.get("year"):
        y = re.findall(r"\d{4}", F.fold(str(meta["year"])))
        if y:
            vals.append(dict(key="metadata.year", field="journal_info", value=str(meta["year"]),
                             status="stored" if any(y[0] in L for L in J.get("year", [])) else "dropped",
                             where="pub-date"))
    if meta.get("pages_printed"):
        pp = re.findall(r"\d+", F.fold(str(meta["pages_printed"])))
        ok = pp and any(pp[0] in L for L in J.get("fpage", []))
        vals.append(dict(key="metadata.pages_printed", field="journal_info", value=str(meta["pages_printed"]),
                         status="stored" if ok else "elsewhere", where="fpage/lpage" if ok else
                         "fpage/lpage from the printed folios / catalogue"))
    for i, tt in enumerate(meta.get("trans_titles") or []):
        if isinstance(tt, dict) and tt.get("title"):
            add(f"metadata.trans_titles[{i}].title", "trans_title", tt["title"], ("trans_title",))
    for i, h in enumerate(meta.get("history") or []):
        if isinstance(h, dict) and h.get("text"):
            add(f"metadata.history[{i}].text", "history_date", h["text"], ("history_date",), REASON["history_type"])

    # ---- enrich (v3.5b)
    E = next((j["answer"]["enrich"] for j in answers if isinstance((j.get("answer") or {}).get("enrich"), dict)),
             None)
    counts = {}
    if isinstance(E, dict):
        import importlib
        known = {"doc_type", "conference", "thesis", "reviewed", "original", "part", "authors", "figures",
                 "table_notes", "note_kinds", "marks", "scan"}
        try:
            known = importlib.import_module("enrich43").KNOWN
        except Exception:  # noqa: BLE001
            pass
        for k_ in E:
            if k_ not in known:
                vals.append(dict(key=f"enrich.{k_}", field="enrich", value=str(E[k_])[:200], status="dropped",
                                 reason=REASON["enrich_unknown"]))
        if E.get("doc_type"):
            add("enrich.doc_type", "doc_type", E["doc_type"], ("doc_type",))
        for grp, fld in (("conference", "conference"), ("thesis", "thesis"), ("original", "original"),
                         ("reviewed", "reviewed_work")):
            g = E.get(grp)
            if isinstance(g, dict):
                for k_, v in g.items():
                    for x in (v if isinstance(v, list) else [v]):
                        if isinstance(x, dict):
                            x = " ".join(str(y) for y in x.values() if isinstance(y, str))
                        if isinstance(x, str) and x and k_ not in ("lang", "type"):
                            add(f"enrich.{grp}.{k_}", fld, x, (fld, "_cite") if grp == "reviewed" else (fld,))
        pt = E.get("part")
        if isinstance(pt, dict) and pt.get("n"):
            add("enrich.part.n", "series_part", pt["n"], ("series_part",))
        am = root.find("front/article-meta")
        n_corresp = sum(1 for c in root.iter("contrib") if c.get("corresp") == "yes")
        n_ids = sum(1 for _ in root.iter("contrib-id"))
        n_notes = sum(1 for fn in root.iter("fn") if fn.get("custom-type") == "author-note")
        r_corresp = r_ids = r_note = r_same = 0
        for au in E.get("authors") or []:
            if not isinstance(au, dict):
                continue
            r_corresp += bool(au.get("corresp"))
            r_ids += bool(au.get("orcid")) + len(au.get("ids") or {})
            r_note += bool(au.get("note"))
            r_same += bool(au.get("same_as"))
            for m, af in enumerate(au.get("affs") or []):
                if isinstance(af, dict):
                    for pk, pv in af.items():
                        if pv:
                            want = {"department": ("aff_department",), "faculty": ("aff_faculty", "aff_department"),
                                    "institution": ("aff_institution",), "city": ("aff_city",),
                                    "country": ("aff_country",)}.get(pk, ("aff_institution",))
                            add(f"enrich.authors[a={au.get('a')}].affs[{m}].{pk}", "aff_parts", pv, want,
                                REASON["twin"] if au.get("same_as") else None)
            if au.get("orcid"):
                add(f"enrich.authors[a={au.get('a')}].orcid", "author_id", au["orcid"], ("author_id",))
        figs_r = sum(len(v) for v in (E.get("figures") or {}).values() if isinstance(v, list))
        figs_j = sum(1 for f in root.iter("fig") if f.get("fig-type"))
        tn_r = len(E.get("table_notes") or [])
        tn_j = sum(1 for p in root.iter("p") if p.get("content-type") in ("table-note", "source", "figure-note"))
        nk_r = len(E.get("note_kinds") or {})
        nk_j = sum(1 for fn in root.iter("fn") if fn.get("custom-type") in ("translator", "editor", "publisher"))
        mk = E.get("marks") or {}
        mk_r = sum(len(v) for v in mk.values() if isinstance(v, list)) if isinstance(mk, dict) else 0
        mk_j = sum(len(F.text_of(cm.find("meta-value")).split()) for cm in root.iter("custom-meta")
                   if (cm.findtext("meta-name") or "").strip() in ("handwriting-lines", "stamp-lines"))
        sc_r = sum(len(v) for v in (E.get("scan") or {}).values() if isinstance(v, list)) \
            if isinstance(E.get("scan"), dict) else 0
        SCAN = ("cut_edge", "blur", "faint", "dark", "skew", "torn", "missing_page", "duplicate_page", "out_of_order")
        sc_j = sum(sum(F.text_of(cm.find("meta-value")).count(w) for w in SCAN) for cm in root.iter("custom-meta")
                   if (cm.findtext("meta-name") or "").strip() == "scan-problem")
        counts.update({"enrich.authors.corresp": [r_corresp, n_corresp], "enrich.authors.ids": [r_ids, n_ids],
                       "enrich.authors.note": [r_note, n_notes], "enrich.authors.same_as": [r_same, None],
                       "enrich.figures": [figs_r, figs_j], "enrich.table_notes": [tn_r, tn_j],
                       "enrich.note_kinds": [nk_r, nk_j], "enrich.marks": [mk_r, mk_j], "enrich.scan": [sc_r, sc_j]})
    # code drops logged by rules43 / enrich43.check
    for lg in rlogs:
        for e in lg.get("enrich") or []:
            vals.append(dict(key=f"enrich.{e.get('key')}", field="enrich", value=str(e.get("value"))[:120],
                             status="dropped", reason=f"enrich43.check: {e.get('why')}"))

    # ---- block attributes, parsed works, fixes / sic / math / missed / ornaments
    wkeys = Counter()
    wdrop = Counter()
    wdrop_ex = defaultdict(list)
    cites = J.get("_cite", [])
    desc = Counter()
    n = Counter()
    for j in answers:
        a = j.get("answer") or {}
        for pg in a.get("pages") or []:
            for b in pg.get("blocks") or []:
                if not isinstance(b, dict):
                    continue
                n[f"calls"] += len(b.get("calls") or [])
                if b.get("type") == "equation" and b.get("latex"):
                    n["equation_latex"] += 1
                d = b.get("description")
                if b.get("type") == "figure" and d:
                    for lg_, v in (d.items() if isinstance(d, dict) else [("?", d)]):
                        if isinstance(v, str) and v.strip():
                            desc["returned"] += 1
                            if holds(T(v), J.get("alt_text", [])):
                                desc["stored"] += 1
                for W in (b.get("parsed") or []) + (b.get("cites") or []):
                    if not isinstance(W, dict):
                        continue
                    for wk, wv in W.items():
                        if wk in ("type", "lang", "cal"):
                            continue
                        xs = wv if isinstance(wv, list) else [wv]
                        for x in xs:
                            if isinstance(x, dict):
                                parts = [str(v) for kk, v in x.items() if isinstance(v, str) and v.strip()]
                                for kk, v in x.items():
                                    if isinstance(v, str) and v.strip():
                                        sub = f"{wk}.{kk}"
                                        wkeys[sub] += 1
                                        if not holds(T(v), cites):
                                            wdrop[sub] += 1
                                            if len(wdrop_ex[sub]) < 3:
                                                wdrop_ex[sub].append(v[:80])
                                continue
                            if isinstance(x, (str, int)) and str(x).strip():
                                wkeys[wk] += 1
                                if not holds(T(str(x)), cites):
                                    wdrop[wk] += 1
                                    if len(wdrop_ex[wk]) < 3:
                                        wdrop_ex[wk].append(str(x)[:80])
        for k_ in ("fixes", "sic", "math", "missed", "ornaments", "splits"):
            n[k_] += len(a.get(k_) or [])
    in_jats = dict(
        fixes=sum(1 for x in root.iter("named-content") if x.get("content-type") == "reader-fix"),
        sic=sum(1 for x in root.iter("named-content") if x.get("content-type") == "sic"),
        math=sum(1 for _ in root.iter("inline-formula")),
        missed=sum(1 for x in root.iter("p", "disp-formula") if x.get("content-type") in ("added", "added-by-argon")),
        calls=sum(1 for x in root.iter("xref") if x.get("ref-type") == "fn"),
        equation_latex=sum(1 for x in root.iter("disp-formula") if x.find(".//tex-math") is not None))
    rej = Counter()
    for lg in rlogs:
        for k_ in ("ornaments_rejected", "bad_splits", "bad_cuts", "exclamation_calls_dropped"):
            v = lg.get(k_)
            rej[k_] += len(v) if isinstance(v, list) else (v or 0) if isinstance(v, int) else 0
    for k_, v in in_jats.items():
        counts[k_] = [n.get(k_, 0), v]
    counts["figure.description"] = [desc["returned"], desc["stored"]]
    counts["ornaments"] = [n["ornaments"], n["ornaments"] - rej["ornaments_rejected"]]
    summ = Counter(d["status"] for d in vals)
    return dict(values=vals, summary=dict(summ), counts=counts, rejected=dict(rej),
                works=dict(returned=dict(wkeys), dropped=dict(wdrop), examples={k: v for k, v in wdrop_ex.items()}))


# ------------------------------------------------------------------------------------------------ bilingual
def bilingual(answers, root, P, lines_out, leaks=None) -> dict:
    XL = "{http://www.w3.org/XML/1998/namespace}lang"
    meta = next((j["answer"]["metadata"] for j in answers if isinstance((j.get("answer") or {}).get("metadata"),
                                                                        dict)), {}) or {}
    printed = defaultdict(set)
    sc = F.script
    aus = [x for x in meta.get("authors") or [] if isinstance(x, dict)]
    for au in aus:
        for k_, f in (("name", "names"), ("affiliation", "affiliations"), ("role", "positions")):
            if au.get(k_):
                printed[f].add(sc(au[k_]))
    if meta.get("title"):
        printed["title"].add(sc(meta["title"]))
    for tt in meta.get("trans_titles") or []:
        if isinstance(tt, dict) and tt.get("title"):
            printed["title"].add(sc(tt["title"]))
    for lang, ids in (meta.get("abstract") or {}).items() if isinstance(meta.get("abstract"), dict) else []:
        if ids:
            printed["abstracts"].add("ar" if lang == "ar" else "lat")
    for lang, v in (meta.get("keywords") or {}).items() if isinstance(meta.get("keywords"), dict) else []:
        if v:
            printed["keywords"].add("ar" if lang == "ar" else "lat")
    FMAP = {"title": "title", "trans_title": "title", "author_name": "names", "affiliation": "affiliations",
            "position": "positions", "abstract": "abstracts", "keywords": "keywords"}
    for L in lines_out:
        if L["page"] <= 2 and L["bucket"] == "a" and L["field"] in FMAP:
            printed[FMAP[L["field"]]].add(sc(L["text"]))
    for lk in leaks or []:
        if lk["page"] <= 2 and lk["field"] in FMAP:
            printed[FMAP[lk["field"]]].add(sc(lk["leak_text"]))
    jats = defaultdict(set)
    linked = {}
    am = root.find("front/article-meta")
    if am is not None:
        for x in am.iter("article-title", "trans-title"):
            jats["title"].add(sc(F.text_of(x)))
        both_names = both_affs = both_pos = False
        for c in am.iter("contrib"):
            ns = {sc(F.text_of(s)) for s in c.iter("string-name")}
            af = {sc(F.text_of(a)) for a in c.findall("aff")}
            ro = {sc(F.text_of(r)) for r in c.findall("role")}
            jats["names"] |= ns
            jats["affiliations"] |= af
            jats["positions"] |= ro
            both_names |= {"ar", "lat"} <= ns
            both_affs |= {"ar", "lat"} <= af
            both_pos |= {"ar", "lat"} <= ro
        for x in am.iter("abstract", "trans-abstract"):
            jats["abstracts"].add(sc(F.text_of(x)))
        for kg in am.iter("kwd-group"):
            if kg.get("specific-use") != "catalogue":
                jats["keywords"].add(sc(F.text_of(kg)))
        linked = dict(title=True, names=both_names, affiliations=both_affs, positions=both_pos, abstracts=True,
                      keywords=True)
    plat = defaultdict(set)
    for f, v, form, lang, bid in P["ma"]:
        if f in ("title", "title_translated") and form == "printed" and v:
            plat["title"].add(sc(v))
    twin_link = False
    for r in P["bm"]:
        plat["names"].add(sc(r[1]))
        twin_link |= bool(r[6])
        if r[3]:
            plat["positions"].add(sc(r[3]))
        if len(r) > 11 and r[11]:                           # experiment 65: byline_mentions.position
            plat["positions"].add(sc(r[11]))
    for r in P["aff"]:
        plat["affiliations"].add(sc(r[2]))
        if r[3]:
            plat["positions"].add(sc(r[3]))
    for lang, t, form, bid in P["ab"]:
        if form == "printed" and t:
            plat["abstracts"].add(sc(t))
    for pr, src in P["kw"]:
        if src == "masters" and pr:
            plat["keywords"].add(sc(pr))
    out = {}
    for k_ in ("title", "names", "affiliations", "positions", "abstracts", "keywords"):
        pr = sorted(printed[k_] - {"none"})
        out[k_] = dict(printed=pr, jats=sorted(jats[k_] - {"none"}), platform=sorted(plat[k_] - {"none"}),
                       linked=bool(linked.get(k_)) if k_ != "names" else bool(linked.get(k_)),
                       platform_linked=twin_link if k_ == "names" else None)
    return out


# ------------------------------------------------------------------------------------------------ platform
def platform_accounting(root, P) -> dict:
    XL = "{http://www.w3.org/XML/1998/namespace}lang"
    am = root.find("front/article-meta")
    c = P["counts"]
    contribs = list(am.iter("contrib")) if am is not None else []
    affs = [a for x in contribs for a in x.findall("aff")]
    part = lambda tag, ct=None: sum(1 for a in affs for x in a.iter(tag) if ct is None or x.get("content-type") == ct)  # noqa: E731
    bm = P["bm"]
    am_rows = P["aff"]
    ma = Counter(f.split(".")[0] for f, v, form, lang, bid in P["ma"] if form in ("printed", "reader"))
    dates = Counter(d[0] for d in P["dates"])
    notes_kind = Counter(n[1] for n in P["notes"])
    figs = c["figures"]
    rows = {
        "contrib (person)": [len(contribs), sum(1 for r in bm if not r[6])],
        "name in another script (twin)": [sum(1 for s in root.iter("string-name") if s.get(XL)),
                                          sum(1 for r in bm if r[6])],
        "contrib/email": [sum(1 for x in contribs for _ in x.iter("email")), sum(1 for r in bm if r[2])],
        "contrib/role": [sum(1 for x in contribs for _ in x.findall("role")), sum(1 for r in bm if r[3])],
        "contrib-id": [sum(1 for _ in root.iter("contrib-id")), sum(1 for r in bm if r[4])],
        "contrib/@corresp": [sum(1 for x in contribs if x.get("corresp") == "yes"), sum(1 for r in bm if r[5])],
        "aff": [len(affs), len(am_rows)],
        "aff/institution dept": [part("institution", "dept"), sum(1 for r in am_rows if r[6])],
        "aff/institution faculty": [part("institution", "faculty"), sum(1 for r in am_rows if r[9])],
        "aff/institution orgname": [part("institution", "orgname"), sum(1 for r in am_rows if r[4])],
        "aff/addr-line city": [part("addr-line"), sum(1 for r in am_rows if r[7])],
        "aff/country": [part("country"), sum(1 for r in am_rows if r[8])],
        "author-notes/fn": [sum(1 for fn in root.iter("fn") if fn.get("custom-type") == "author-note"),
                            notes_kind.get("author-note", 0)],
        "history/date (not published)": [sum(1 for d in root.iter("date") if d.get("date-type") != "published"),
                         sum(v for k, v in dates.items() if k in ("received", "accepted", "revised", "reviewed",
                                                                   "online"))],
        "trans-title (printed)": [sum(1 for g in root.iter("trans-title-group") if g.get("specific-use") == "printed"
                                      for _ in g.iter("trans-title")), ma.get("title_translated", 0)],
        "subtitle": [sum(1 for _ in root.iter("subtitle")), ma.get("subtitle", 0)],
        "abstract + trans-abstract": [sum(1 for _ in root.iter("abstract", "trans-abstract")),
                                      sum(1 for a in P["ab"] if a[2] == "printed")],
        "kwd (author-printed)": [sum(1 for kg in root.iter("kwd-group") if kg.get("specific-use") != "catalogue"
                                     for _ in kg.findall("kwd")), sum(1 for k in P["kw"] if k[1] == "masters")],
        "conference/*": [sum(1 for _ in root.iter("conf-name", "conf-loc", "conf-date")) if am is not None and
                         am.find("conference") is not None else 0, ma.get("conference", 0)],
        "product (thesis / book)": [sum(1 for _ in am.findall("product")) if am is not None else 0,
                                    1 if ma.get("thesis") or ma.get("reviewed_book") else 0],
        "related-article": [sum(1 for _ in am.findall("related-article")) if am is not None else 0,
                            1 if ma.get("original") else 0],
        "custom-meta series-part": [sum(1 for cm in root.iter("custom-meta")
                                        if (cm.findtext("meta-name") or "").strip() == "series-part"), 0],
        "fn (footnote / endnote)": [sum(1 for fn in root.iter("fn") if fn.get("custom-type") != "author-note"),
                                    notes_kind.get("footnote", 0) + notes_kind.get("endnote", 0)],
        "fn/@custom-type (translator / editor / publisher)": [
            sum(1 for fn in root.iter("fn") if fn.get("custom-type") in ("translator", "editor", "publisher")),
            sum(1 for n in P["notes"] if n[2])],
        "ref": [sum(1 for _ in root.iter("ref")), c["citations_ref_list"]],
        "fig": [sum(1 for _ in root.iter("fig")), (figs.get("figure") or [0])[0]],
        "fig/@fig-type": [sum(1 for f in root.iter("fig") if f.get("fig-type")), (figs.get("figure") or [0, 0])[1]],
        "fig/p text-in-figure": [sum(1 for p in root.iter("p") if p.get("content-type") == "text-in-figure"),
                                 (figs.get("figure") or [0, 0, 0, 0, 0])[4]],
        "table-wrap": [sum(1 for _ in root.iter("table-wrap")), (figs.get("table") or [0])[0]],
        "td / th with text": [sum(1 for x in root.iter("td", "th") if F.text_of(x)), c["table_cells"]],
        "disp-formula": [sum(1 for _ in root.iter("disp-formula")), (figs.get("equation") or [0])[0]],
        "verse-line": [sum(1 for _ in root.iter("verse-line")), c["verse_lines"]],
        "table-wrap-foot / fig note": [sum(1 for p in root.iter("p") if p.get("content-type") in
                                           ("table-note", "source", "figure-note")), c["figure_notes"]],
        "reader-fix": [sum(1 for x in root.iter("named-content") if x.get("content-type") == "reader-fix"),
                       c["fixes"]],
        "sic": [sum(1 for x in root.iter("named-content") if x.get("content-type") == "sic"), c["misprints"]],
        "handwriting / stamp / scan-problem": [
            sum(len(F.text_of(cm.find("meta-value")).split()) if "lines" in (cm.findtext("meta-name") or "") else
                F.text_of(cm.find("meta-value")).count(",") + 1 for cm in root.iter("custom-meta")
                if (cm.findtext("meta-name") or "").strip() in ("handwriting-lines", "stamp-lines", "scan-problem")),
            c["page_marks"]],
        "doc_type subject": [sum(1 for sg in root.iter("subj-group") if sg.get("subj-group-type") == "document-type"),
                             1 if c["doc_type"] else 0],
        "sec/title": [sum(1 for s in root.iter("sec") if s.find("title") is not None), c["sections"]],
    }
    return rows
