"""Experiment 43: prompt v3.5's "enrich" part of an answer (draft, 2026-10-22; no model calls here).

Prompt v3.5 (prompt43.V35_CHANGES) asks for experiment 51's 37 priority-1 items in a part of the answer of its own,
"enrich", written after the structure. Every value is a line id, a word from a closed list, or an exact substring
of Azure's text (D30: Gemini never retypes text). An answer without "enrich" (every answer before v3.5) is never
touched: both entry points return at once, so v3.3 answers build byte for byte as before (README "Prompt v3.5").

  check(ans, lines, log)      rules43.normalize, FIRST (before any rule moves a block): every value checked
                              (enums, line ids of the chunk, substrings of the chunk's text after the answer's fixes;
                              ORCID shape), the rest dropped and logged in log["enrich"]; each figure block gets
                              its kind as "_kind" (the model's order of figures on a page is only known here) and a
                              table note pointing at "fP.K" gets that figure's box
  apply(Mo, A, raw_dir)       masters43.build43, after refs43: the JATS homes
      doc_type                  article/@article-type (JATS list) + article-categories/subj-group
                                [@subj-group-type="document-type"]/subject (the prompt's word)   — meta43.enrich
      conference / thesis /     conference (conf-name, conf-loc, conf-date); product[@product-type="thesis"];
      reviewed / original /     product[@product-type="book"] (refs43's element-citation parts); related-article
      part                      [@related-article-type="translated-from"]; custom-meta series-part — meta43.enrich
      authors                   contrib/@corresp, contrib-id[@contrib-id-type="orcid" | ...], same_as folds the
                                twin into the person (string-name xml:lang), affs (faculty tagged, extra aff),
                                author note fn moved to author-notes                               — meta43.enrich
      figures                   fig/@fig-type
      table_notes               the note's paragraph moved (id and line targets kept) into the table's
                                table-wrap-foot (p content-type="table-note" | "source"), or into the fig
      note_kinds                fn[@fn-type="custom"][@custom-type="translator" | "editor" | "publisher"]
      marks / scan              custom-meta "handwriting-lines", "stamp-lines", "scan-problem" (no ALTO change)
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from lxml import etree

DOC_TYPES = {"research", "review", "editorial", "book_review", "report", "conference_paper", "thesis_summary",
             "interview", "news", "letter", "obituary", "poem", "documents", "bibliography", "front_matter", "other"}
FIG_KINDS = {"chart", "photo", "map", "diagram", "drawing", "manuscript", "portrait", "logo", "stamp", "cartoon",
             "calligraphy", "table_image", "ornament", "advert", "other"}
NOTE_KINDS = {"translator", "editor", "publisher"}
MARK_KINDS = {"handwriting", "stamp"}
SCAN = {"cut_edge", "blur", "faint", "dark", "skew", "torn", "missing_page", "duplicate_page", "out_of_order"}
TN_KINDS = {"note", "source"}
ID_KINDS = {"scopus", "researcherid", "scholar"}
ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")
LID = re.compile(r"^\d+:\d+[a-z]?$")
FIGREF = re.compile(r"^f(\d+)\.(\d+)$")
AFF_KEYS = ("department", "faculty", "institution", "city", "country")
KNOWN = {"doc_type", "conference", "thesis", "reviewed", "original", "part", "authors", "figures", "table_notes",
         "note_kinds", "marks", "scan",
         "doi", "license", "section", "printings"}       # prompt v3.6 (experiment 65): homes in leaks43.v36
DOI = re.compile(r"10\.\d{4,9}/\S+")
PRINTING_KEYS = ("a", "name", "lines", "orcid", "email", "position", "corresp")


def ws(s) -> str:
    return " ".join(str(s or "").split())


def has_enrich(answers) -> bool:
    return any(isinstance(a, dict) and isinstance(a.get("enrich"), dict) for a in answers)


# ------------------------------------------------------------------------------------------------ check (rules43)

def chunk_text(ans: dict, lines: dict) -> str:
    """The chunk's Azure text with the answer's fixes applied (values may be quoted after a fix)."""
    fx = {}
    for f in ans.get("fixes") or []:
        if isinstance(f, dict) and f.get("from"):
            fx.setdefault(str(f.get("line")), []).append((str(f["from"]), str(f.get("to") or "")))
    out = []
    for lid, L in lines.items():
        t = L.get("text") or ""
        for a, b in fx.get(lid, []):
            t = t.replace(a, b, 1)
        out.append(t)
    return ws(" ".join(out))


def _lid_ok(i, lines) -> bool:
    i = str(i)
    return bool(LID.match(i)) and (i in lines or i.rstrip("abcdefgh") in lines)


def check(ans: dict, lines: dict, log: dict):
    """Clean ans["enrich"] in place (v3.5 answers only); log every value dropped."""
    E = ans.get("enrich")
    if not isinstance(E, dict):
        if "enrich" in ans:
            ans["enrich"] = {}
        return
    drop = log.setdefault("enrich", [])
    text = chunk_text(ans, lines)
    flat = text.replace(" ", "")                  # a value may run over Azure's line break

    def sub_ok(where, v):
        v = ws(v)
        if not v:
            return None
        if v not in text and v.replace(" ", "") not in flat:
            drop.append(dict(key=where, value=v[:80], why="not a substring of the chunk's text"))
            return None
        return v

    def lids(where, xs):
        out = []
        for i in xs if isinstance(xs, list) else [xs]:
            if _lid_ok(i, lines):
                out.append(str(i))
            else:
                drop.append(dict(key=where, value=str(i)[:40], why="not a line id of this chunk"))
        return out

    out = {}
    dt = str(E.get("doc_type") or "").strip().lower()
    if dt:
        if dt in DOC_TYPES:
            out["doc_type"] = dt
        else:
            drop.append(dict(key="doc_type", value=dt, why="not in the list"))
    for key, parts in (("conference", ("name", "place", "date")),
                       ("thesis", ("degree", "university", "year", "supervisor")),
                       ("original", ("title", "author", "source")), ("part", ("n", "of"))):
        v = E.get(key)
        if not isinstance(v, dict):
            continue
        got = {k: x for k in parts if (x := sub_ok(f"{key}.{k}", v.get(k)))}
        if key == "original" and str(v.get("lang") or "").lower() in ("ar", "en", "fr", "de", "fa", "tr", "es",
                                                                       "it", "ru", "ur"):
            got["lang"] = str(v["lang"]).lower()
        if got:
            out[key] = got
    if isinstance(E.get("reviewed"), dict):
        out["reviewed"] = E["reviewed"]          # a W: its fields are checked by refs43.citation in meta43.enrich
    aus = []
    for au in E.get("authors") or []:
        if not isinstance(au, dict) or not str(au.get("a", "")).strip().isdigit():
            drop.append(dict(key="authors", value=json.dumps(au, ensure_ascii=False)[:80], why="no author number"))
            continue
        x = {"a": int(au["a"])}
        if au.get("corresp") in (True, "true", 1, "yes"):
            x["corresp"] = True
        o = ws(au.get("orcid"))
        if o:
            m = ORCID.search(o)
            if m and m.group(0) in flat:
                x["orcid"] = m.group(0)
            else:
                drop.append(dict(key="authors.orcid", value=o[:40], why="not an ORCID printed here"))
        ids0 = au.get("ids") if isinstance(au.get("ids"), dict) else {}
        ids = {str(k).lower(): v for k, v0 in ids0.items()
               if str(k).lower() in ID_KINDS and (v := sub_ok(f"authors.ids.{k}", v0))}
        if ids:
            x["ids"] = ids
        if str(au.get("same_as", "")).strip().isdigit() and int(au["same_as"]) != x["a"]:
            x["same_as"] = int(au["same_as"])
        affs = []
        for af in au.get("affs") or []:
            if isinstance(af, dict):
                d = {k: v for k in AFF_KEYS if (v := sub_ok(f"authors.affs.{k}", af.get(k)))}
                if d:
                    affs.append(d)
        if affs:
            x["affs"] = affs
        note = lids("authors.note", au.get("note") or [])
        if note:
            x["note"] = note
        if len(x) > 1:
            aus.append(x)
    if aus:
        out["authors"] = aus
    # figures: the k-th kind of a page goes on the page's k-th figure block, as the model gave them
    figs = E.get("figures")
    if isinstance(figs, dict):
        blocks_of = {str(pg.get("page")): [b for b in pg.get("blocks") or [] if isinstance(b, dict)
                                           and b.get("type") == "figure"]
                     for pg in ans.get("pages") or [] if isinstance(pg, dict)}
        n = 0
        for p, kinds in figs.items():
            fb = blocks_of.get(str(p), [])
            kinds = kinds if isinstance(kinds, list) else [kinds]
            if len(kinds) != len(fb):
                drop.append(dict(key="figures", value=f"page {p}: {len(kinds)} kinds, {len(fb)} figures",
                                 why="count differs: kinds kept in order up to the shorter"))
            for b, k in zip(fb, kinds):
                k = str(k or "").strip().lower()
                b["_kind"] = k if k in FIG_KINDS else "other"
                n += 1
        if n:
            out["figures"] = n
    tns = []
    for tn in E.get("table_notes") or []:
        if not isinstance(tn, dict):
            continue
        of, ls = str(tn.get("of") or ""), lids("table_notes.lines", tn.get("lines") or [])
        kind = str(tn.get("kind") or "note").lower()
        x = dict(lines=ls, kind=kind if kind in TN_KINDS else "note")
        m = FIGREF.match(of)
        if m:
            pg = next((pg for pg in ans.get("pages") or [] if isinstance(pg, dict)
                       and str(pg.get("page")) == m.group(1)), None)
            fb = [b for b in (pg or {}).get("blocks") or [] if isinstance(b, dict) and b.get("type") == "figure"]
            k = int(m.group(2))
            if 1 <= k <= len(fb) and isinstance(fb[k - 1].get("box"), list):
                x["fig"] = dict(page=int(m.group(1)), box=fb[k - 1]["box"])
        elif _lid_ok(of, lines):
            x["of"] = of
        if ls and ("of" in x or "fig" in x):
            tns.append(x)
        else:
            drop.append(dict(key="table_notes", value=json.dumps(tn, ensure_ascii=False)[:80],
                             why="no table / figure or no lines"))
    if tns:
        out["table_notes"] = tns
    nk = E.get("note_kinds")
    if isinstance(nk, dict):
        d = {str(k): str(v).lower() for k, v in nk.items() if str(v).lower() in NOTE_KINDS}
        if d:
            out["note_kinds"] = d
    mk = E.get("marks")
    if isinstance(mk, dict):
        d = {k: v for k in MARK_KINDS if (v := lids(f"marks.{k}", mk.get(k) or []))}
        if d:
            out["marks"] = d
    sc = E.get("scan")
    if isinstance(sc, dict):
        d = {}
        for p, ks in sc.items():
            ks = [str(k).lower() for k in (ks if isinstance(ks, list) else [ks]) if str(k).lower() in SCAN]
            if ks and str(p).isdigit():
                d[str(p)] = ks
        if d:
            out["scan"] = d
    # prompt v3.6 (experiment 65): the article's DOI, licence and section lines; every other printing of an author
    d = sub_ok("doi", E.get("doi"))
    if d:
        m = DOI.search(d.replace(" ", ""))
        if m:
            out["doi"] = m.group(0).rstrip(".,;)")
        else:
            drop.append(dict(key="doi", value=d[:60], why="not a DOI"))
    for key in ("license", "section"):
        ls = lids(key, E.get(key) or [])
        if ls:
            out[key] = ls
    prs = []
    for pr in E.get("printings") or []:
        if not isinstance(pr, dict):
            continue
        x = {}
        if str(pr.get("a", "")).strip().isdigit():
            x["a"] = int(pr["a"])
        for k in ("name", "email", "position"):
            v = sub_ok(f"printings.{k}", pr.get(k))
            if v:
                x[k] = v
        o = ws(pr.get("orcid"))
        if o:
            m = ORCID.search(o.replace(" ", ""))
            if m and (m.group(0) in flat or m.group(0).replace("-", "") in flat.replace("-", "")):
                x["orcid"] = m.group(0)
            else:
                drop.append(dict(key="printings.orcid", value=o[:40], why="not an ORCID printed here"))
        if pr.get("corresp") in (True, "true", 1, "yes"):
            x["corresp"] = True
        ls = lids("printings.lines", pr.get("lines") or [])
        if ls:
            x["lines"] = ls
        for k in pr:
            if k not in PRINTING_KEYS:
                drop.append(dict(key=f"printings.{k}", value=str(pr[k])[:40], why="unknown key"))
        if ("a" in x or "name" in x) and len(x) > 1:
            prs.append(x)
        elif x:
            drop.append(dict(key="printings", value=json.dumps(pr, ensure_ascii=False)[:80],
                             why="no author number or name, or nothing else"))
    if prs:
        out["printings"] = prs
    for k in E:
        if k not in KNOWN and E[k] not in (None, {}, [], ""):
            drop.append(dict(key=k, value=json.dumps(E[k], ensure_ascii=False)[:80], why="unknown key"))
    ans["enrich"] = out


# ------------------------------------------------------------------------------------------------ apply (masters)

def answers_of(a: dict, raw_dir: Path) -> list[dict]:
    import structure as ST
    out = []
    for x, y in ST.chunks(a):
        f = Path(raw_dir) / f"{a['stem']}_c{x:03d}-{y:03d}.json"
        if f.exists():
            ans = json.loads(f.read_text(encoding="utf-8")).get("answer")
            if isinstance(ans, dict):
                out.append(ans)
    return out


def target_el(A, Mo, lid):
    """The JATS element holding Azure line `lid` (its <target>'s parent), or None."""
    tl = Mo.tl_of.get(lid)
    if tl is None and lid[-1:].isalpha():
        tl = Mo.tl_of.get(lid[:-1])
    if tl is None:
        return None
    tg = _TARGETS[0]
    if tg is None or tg[0] is not A:
        tg = (A, {t.get("id"): t for t in A.iter("target")})
        _TARGETS[0] = tg
    t = _TARGETS[0][1].get(tl)
    return t.getparent() if t is not None else None


_TARGETS = [None]


def fig_by_box(A, Mo, page: int, box) -> etree._Element | None:
    """The fig drawn from an answer's figure box (0-1000 on its page): the ALTO illustration with that box."""
    try:
        W, H = Mo.S.dims[page]
        x0, y0, x1, y1 = (float(v) for v in box[:4])
    except Exception:                                         # noqa: BLE001
        return None
    want = [min(x0, x1) * W / 1000, min(y0, y1) * H / 1000, max(x0, x1) * W / 1000, max(y0, y1) * H / 1000]
    lp = Mo.lp(page)
    best = None
    for b in Mo.alto.get(lp, []):
        if b.get("kind") != "ill" or not re.match(rf"^p{lp}f\d+$", str(b.get("id"))):
            continue
        d = max(abs(u - v) for u, v in zip(b["box"], want))
        if d <= 3 and (best is None or d < best[0]):
            best = (d, b["id"])
    if best is None:
        return None
    return next((f for f in A.iter("fig") if f.get("id") == best[1]), None)


def custom_meta(A, name: str, value: str, cid: str):
    cmg = A.find("front/article-meta/custom-meta-group")
    if cmg is None:
        return
    c = etree.SubElement(cmg, "custom-meta", {"id": cid})
    etree.SubElement(c, "meta-name").text = name
    etree.SubElement(c, "meta-value").text = value


def apply(Mo, A, raw_dir: Path | None = None, answers: list[dict] | None = None) -> Counter:
    st = Counter()
    if answers is None:
        if raw_dir is None:
            return st
        answers = answers_of(Mo.a, Path(raw_dir))
    if not has_enrich(answers):
        return st                                             # every answer before v3.5: nothing happens
    import meta43
    meta43.enrich(Mo, A, answers, st)
    # figure kinds
    for ans in answers:
        for pg in ans.get("pages") or []:
            for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
                if isinstance(b, dict) and b.get("type") == "figure" and b.get("_kind") and b.get("box"):
                    f = fig_by_box(A, Mo, int(pg.get("page")), b["box"])
                    if f is None:
                        st["enrich_fig_kind_no_fig"] += 1
                        continue
                    f.set("fig-type", b["_kind"])
                    st[f"enrich_fig_{b['_kind']}"] += 1
    # table / figure notes
    for ans in answers:
        for tn in (ans.get("enrich") or {}).get("table_notes") or []:
            holder = None
            if tn.get("of"):
                el = target_el(A, Mo, tn["of"])
                holder = next((e for e in ([el] + list(el.iterancestors()) if el is not None else [])
                               if e.tag in ("table-wrap", "fig")), None)
            elif tn.get("fig"):
                holder = fig_by_box(A, Mo, tn["fig"]["page"], tn["fig"]["box"])
            if holder is None:
                st["enrich_table_note_no_holder"] += 1
                continue
            els = []
            for lid in tn["lines"]:
                el = target_el(A, Mo, lid)
                if el is not None and el not in els:
                    els.append(el)
            for el in els:
                if el.tag != "p" or el.getparent() is None or any(x is holder for x in el.iterancestors()):
                    st["enrich_table_note_kept"] += 1            # inside a caption / cell / already the table's
                    continue
                own = {t.get("id") for t in el.iter("target")}
                want = {Mo.tl_of.get(i) for i in tn["lines"]}
                if not own <= want:                               # the paragraph holds other text too: leave it
                    st["enrich_table_note_mixed"] += 1
                    continue
                par = el.getparent()
                el.set("content-type", "source" if tn["kind"] == "source" else
                       ("table-note" if holder.tag == "table-wrap" else "figure-note"))
                if par.tag == "fn" and len(par.findall("p")) == 1:
                    # the note is a footnote (its call sits in a cell, exp 52: 0130-020-080-001 p22): moving only its
                    # paragraph left an fn with a label alone (DTD-invalid). A table's footnote moves whole, id kept,
                    # so the call still points at it; a figure's stays where it is.
                    if holder.tag == "table-wrap":
                        foot = holder.find("table-wrap-foot")
                        if foot is None:
                            foot = etree.SubElement(holder, "table-wrap-foot")
                        par.getparent().remove(par)
                        foot.append(par)
                        st[f"enrich_{holder.tag}_{tn['kind']}_footnote"] += 1
                    else:
                        st["enrich_table_note_kept"] += 1
                    continue
                par.remove(el)
                # exp 70 (0165-009-031-001 p13): a note printed as bullet items under the table left empty
                # list-items (DTD-invalid): an emptied item goes, and an emptied list with it
                if par.tag == "list-item" and not [c for c in par if c.tag in ("p", "def-list", "list")]:
                    lst = par.getparent()
                    lst.remove(par)
                    st["enrich_table_note_list_item_removed"] += 1
                    if lst.tag == "list" and lst.find("list-item") is None and lst.getparent() is not None:
                        if lst.tail and lst.tail.strip():
                            st["enrich_table_note_list_tail_kept"] += 1
                        else:
                            lst.getparent().remove(lst)
                if holder.tag == "table-wrap":
                    foot = holder.find("table-wrap-foot")
                    if foot is None:
                        foot = etree.SubElement(holder, "table-wrap-foot")
                    foot.append(el)
                else:
                    at = holder.find("attrib")
                    (at.addprevious(el) if at is not None else holder.append(el))
                st[f"enrich_{holder.tag}_{tn['kind']}"] += 1
    # notes not by the author
    import structure as ST
    kinds = {}
    for ans in answers:
        kinds.update((ans.get("enrich") or {}).get("note_kinds") or {})
    if kinds:
        fm = getattr(Mo, "fn_map", {}) or {}
        fns = {f.get("id"): f for f in A.iter("fn")}
        for k, v in kinds.items():
            f = fns.get(fm.get(ST.fn_norm(k)))
            if f is None:
                st["enrich_note_kind_no_note"] += 1
                continue
            f.set("fn-type", "custom")
            f.set("custom-type", v)
            st[f"enrich_note_{v}"] += 1
    # marks and scan problems: recorded, nothing moved
    marks, scan = {}, {}
    for ans in answers:
        E = ans.get("enrich") or {}
        for k, v in (E.get("marks") or {}).items():
            marks.setdefault(k, []).extend(v)
        for p, v in (E.get("scan") or {}).items():
            scan.setdefault(int(p), []).extend(v)
    for k, v in marks.items():
        custom_meta(A, f"{k}-lines", " ".join(v), f"enrich-{k}")
        st[f"enrich_marks_{k}"] += len(v)
    if scan:
        custom_meta(A, "scan-problem", "; ".join(f"page {p}: {', '.join(v)}" for p, v in sorted(scan.items())),
                    "enrich-scan")
        st["enrich_scan_pages"] += len(scan)
    if hasattr(Mo, "stats"):
        Mo.stats.update(st)
    return st
