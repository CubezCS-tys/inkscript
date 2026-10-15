"""Experiment 41: every measure, for each run, on the same articles (no calls). Writes out/scores.json.

    /home/yassine/inkscript/.venv/bin/python score41.py [--runs argon flash] [--r2 argon_r2 flash_r2]

  words wrong     order-free word error vs the truth (1 - F1 of the word multisets, exp 40's D_subset measure: vowel
                  marks counted, punctuation and tatweel ignored, tanween+alef in either order the same; born-digital
                  digits folded) on owner gold pages (status done) and born-digital truth pages; Azure's own lines in
                  Azure's order beside it; also faithful CER (inkscript score_page, reading order counts)
  lines           dropped / duplicated / noise / split, exactly, from book/
  types           coarse label of every Azure line vs experiment 39's Gemini 3.1 Pro referee (lines matched by text and
                  box; referee "other" left out as in 39/40), and between the two runs on every line both used
  order           Kendall concordance of the two runs' line orders per page; multi-column pages apart
  segmentation    of consecutive lines (in one run's order), share where both runs agree on "same block or not"
  tables          paired by their lines (Jaccard >= 0.5); TEDS between the two runs' tables (structure + text)
  footnotes       calls, calls whose target footnote exists, footnotes never called
  page breaks     blocks marked continued; agreement between runs on which first lines continue
  metadata        title / authors / abstract vs the catalogue's merged JATS master (exact after folding, near >= 0.9)
  fixes           applied fixes on truth pages judged against the truth (right / wrong / neutral, exp 40's method)
  cost            dollars and seconds per page and per article from book/ (the spend log's numbers)
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from structure import COARSE, OUT, page_lines, sample  # noqa: E402

E = HERE.parent
GOLD = E / "34_yardstick/out/gold"
BDT = E / "36_vlm_bakeoff/out/ref/bdtruth"
REF = E / "39_ink_geometry/out/score_test"
MERGED = E / "29_catalogue/out/merged"
DIG = str.maketrans({**{chr(0x660 + i): str(i) for i in range(10)}, **{chr(0x6f0 + i): str(i) for i in range(10)}})
TATWEEL = "ـ"
PAGES_PER_DOC = 15.9           # exp 40: 1M documents ~ 15.9M pages


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ reading outputs

def sections(run, stem) -> dict[int, str]:
    f = OUT / run / "docs" / f"{stem}.html"
    if not f.exists():
        return {}
    h = f.read_text(encoding="utf-8")
    return {int(m.group(1)): m.group(2)
            for m in re.finditer(r'<section class="page" data-page="(\d+)"[^>]*>(.*?)</section>', h, re.S)}


def page_text_lines(sec: str) -> list[str]:
    """The page's text units in reading order: each block's text (table: each cell), LaTeX left out (FORMAT.md)."""
    import lxml.html as LH
    if not sec.strip():
        return []
    root = LH.fragment_fromstring(sec, create_parent="div")
    for m in root.xpath('.//span[contains(concat(" ", @class, " "), " math ")]'):
        t = (m.text_content() or "")
        inner = re.sub(r"^\\\(|\\\)$|^\\\[|\\\]$", "", t.strip())
        keep = not re.search(r"[\\^_{]", inner) and not t.strip().startswith("\\[")
        tail = m.tail or ""
        m.drop_tree() if not keep else None
        if keep:
            m.text, m.tail = inner, tail
            for ch in list(m):
                m.remove(ch)
    out = []
    for el in root.xpath(".//*[@data-n]"):
        if el.tag == "table":
            for cell in el.xpath(".//td|.//th"):
                t = re.sub(r"\s+", " ", cell.text_content()).strip()
                if t:
                    out.append(t)
        else:
            t = re.sub(r"\s+", " ", el.text_content()).strip()
            if t:
                out.append(t)
    for el in root.xpath(".//*[@data-added]"):
        t = re.sub(r"\s+", " ", el.text_content()).strip()
        if t:
            out.append(t)
    return out


def labels(run, stem):
    f = OUT / run / "labels" / f"{stem}.json"
    return jl(f) if f.exists() else None


def book(run, stem):
    f = OUT / run / "book" / f"{stem}.json"
    return jl(f) if f.exists() else None


# ------------------------------------------------------------------------------------------------ text measures

def words(lines, dig=False):
    from inkscript.gold.text import folded  # noqa: F401
    s = " ".join(lines).replace(TATWEEL, "")
    s = s.replace("اً", "ًا")
    if dig:
        s = s.translate(DIG)
    s = re.sub(r"[^\w؀-ۿ\s]", " ", s)
    return Counter(s.split())


def bag(p, r):
    m = sum((p & r).values())
    return sum(p.values()) + sum(r.values()) - 2 * m, sum(p.values()) + sum(r.values())


def ref_doc(lines) -> dict:
    ls = [dict(id=f"l{i:03d}", text=t, box=None, kind="text", status="ok") for i, t in enumerate(lines) if t.strip()]
    return dict(page_id="x", stem="x", kinds=[], primary="", decade="", split="", lines=ls,
                order=[x["id"] for x in ls], tables=[], equations=[], status="done")


def truth_of(stem, p):
    """(kind, truth doc for score_page, truth lines) or None."""
    from inkscript.gold.format import gold_lines, load
    g = GOLD / f"{stem}_p{p:03d}.json"
    if g.exists():
        d = load(g)
        if d.get("status") == "done":
            tl = [ln["text"] for ln in gold_lines(d) if ln.get("kind", "text") != "equation"]
            return "gold", d, tl
    b = BDT / f"bd_{stem}_p{p:03d}.json"
    if b.exists():
        t = jl(b)
        tl = [ln["text"].translate(DIG) for ln in t["lines"]]
        return "bd", ref_doc(tl), tl
    return None


def cer(doc, plines, dig=False):
    from inkscript.gold.score import score_page
    sp = score_page(doc, {"lines": [{"text": t.translate(DIG) if dig else t} for t in plines]})
    return sp["faithful.char_err"], sp["faithful.chars"]


# ------------------------------------------------------------------------------------------------ fix verdicts

def semiglobal(a: str, b: str) -> int:
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
        prev = cur
    return min(prev)


def tri(s):
    s = s.replace(" ", "")
    return Counter(s[i:i + 3] for i in range(len(s) - 2))


def fix_verdict(orig_line, new_line, T, dig=False):
    if dig:
        orig_line, new_line = orig_line.translate(DIG), new_line.translate(DIG)
    tk = tri(orig_line)
    sc = [sum((tk & tri(t)).values()) for t in T]
    k = max(range(len(T)), key=lambda i: sc[i])
    win = " ".join(T[max(0, k - 1):k + 2])
    do, dn = semiglobal(orig_line, win), semiglobal(new_line, win)
    return "right" if dn < do else "wrong" if dn > do else "neutral"


# ------------------------------------------------------------------------------------------------ structure measures

def line_labels(lab) -> dict[str, dict]:
    """original Azure line id -> {label, type, block, order, k} (a split line: its first part's)."""
    out = {}
    for r in lab["lines"]:
        base = re.sub(r"[a-p]$", "", r["id"])
        if base not in out:
            out[base] = r
    return out


def kendall(seq_a, seq_b):
    pos = {x: i for i, x in enumerate(seq_b)}
    s = [pos[x] for x in seq_a if x in pos]
    n = len(s)
    if n < 2:
        return None, 0
    conc = sum(1 for i in range(n) for j in range(i + 1, n) if s[i] < s[j])
    pairs = n * (n - 1) // 2
    return conc / pairs, pairs


def multicol(lines, W) -> bool:
    left = sum(1 for l in lines if l["px"][2] < 0.52 * W and l["px"][2] - l["px"][0] > 0.2 * W)
    right = sum(1 for l in lines if l["px"][0] > 0.48 * W and l["px"][2] - l["px"][0] > 0.2 * W)
    return left >= 8 and right >= 8


def table_html(rows, text):
    h = "<table>"
    for r in rows:
        h += "<tr>" + "".join(f"<td{' colspan=%d' % c['colspan'] if c.get('colspan', 1) > 1 else ''}"
                              f"{' rowspan=%d' % c['rowspan'] if c.get('rowspan', 1) > 1 else ''}>"
                              + " ".join(text.get(i, "") for i in c["ids"]) + "</td>" for c in r) + "</tr>"
    return h + "</table>"


def norm_meta(s):
    from inkscript.gold.text import folded
    s = folded(s or "")
    return re.sub(r"[\W_]+", "", s)


def jats_master(stem):
    f = MERGED / f"{stem}.jats.xml"
    if not f.exists():
        return None
    x = f.read_text(encoding="utf-8")
    import html as H
    t = re.search(r"<article-title[^>]*>(.*?)</article-title>", x, re.S)
    names = re.findall(r'<string-name specific-use="printed-on-the-page">(.*?)</string-name>', x)
    if not names:
        for m in re.finditer(r'<name name-style="western" xml:lang="ar">(.*?)</name>', x, re.S):
            g = re.search(r"<given-names>(.*?)</given-names>", m.group(1))
            s = re.search(r"<surname>(.*?)</surname>", m.group(1))
            names.append(" ".join(v.group(1) for v in (g, s) if v))
    ab = re.findall(r"<abstract[^>]*>(.*?)</abstract>", x, re.S)
    strip = lambda s: H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()
    return dict(title=strip(t.group(1)) if t else None, authors=[strip(n) for n in names],
                abstract=[strip(a) for a in ab])


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if (a or b) else 1.0


# ------------------------------------------------------------------------------------------------ main

def score(runs, r2):
    arts = sample()
    res = dict(runs=runs, per_run={}, pair={}, truth_pages=[], referee={}, metadata=[], tables=[], order_pages=[],
               noise={}, articles=[])
    # ---- per run totals
    for run in runs + r2:
        T = Counter()
        per_art = []
        for a in arts:
            b = book(run, a["stem"])
            if not b:
                continue
            T["articles"] += 1
            T["pages"] += b["pages"]
            for k in ("lines", "used", "dropped_chars", "chars", "splits", "math", "blocks", "footnotes", "calls",
                      "calls_resolved", "calls_placed", "continued", "figures", "tables", "equations", "chunks",
                      "chunks_failed", "n_issues", "tin", "tout", "think"):
                T[k] += b.get(k, 0) or 0
            T["dropped"] += len(b["dropped"])
            T["duplicated"] += len(b["duplicated"])
            T["noise"] += len(b["noise"])
            if b["noise"]:
                txt = {}
                for p_ in range(a["first"], a["last"] + 1):
                    for l in page_lines(a, p_)[0]:
                        txt[l["id"]] = l["text"]
                for i in b["noise"]:
                    t = txt.get(i, "")
                    if len(re.findall(r"[^\W\d_]", t)) >= 3:          # 3+ letters: words, not a speck or ornament
                        T["noise_with_words"] += 1
                        T["noise_word_chars"] += len(t)
                        res.setdefault("noise_words", {}).setdefault(run, []).append(dict(stem=a["stem"], line=i, text=t))
            T["misplaced"] += len(b.get("misplaced", []))
            T["fixes"] += len(b["fixes_applied"])
            T["fixes_rejected"] += len(b["fixes_rejected"])
            T["sic"] += len(b["sic"])
            T["sic_rejected"] += len(b["sic_rejected"])
            T["missed"] += len(b["missed"])
            T["footnotes_uncalled"] += len(b["footnotes_uncalled"])
            T["lost_pages"] += len(b["lost_pages"])
            T["articles_with_drop"] += bool(b["dropped"])
            T["articles_with_dup"] += bool(b["duplicated"])
            T["meta_strings"] += b["meta_check"]["strings"]
            T["meta_verbatim"] += b["meta_check"]["verbatim"]
            T["usd"] += b["usd"]
            T["secs"] += b["secs"]
            for i in b.get("issues", []):
                T["issue_" + i["kind"]] += 1
            lab = labels(run, a["stem"])
            if lab:
                fns = set(lab["footnotes"])
                txt = defaultdict(str)
                for r in lab["lines"]:
                    txt[r["block"]] += " " + r["text"]
                starts = Counter()
                for bl in lab["blocks"]:
                    if bl["type"] in ("list_item", "reference", "footnote", "paragraph", "other"):
                        m = re.match(r"\s*[\(\[]?\s*([0-9٠-٩]+)", txt[bl["n"]].translate(DIG))
                        if m:
                            starts[(m.group(1).translate(DIG))] += 1
                for bl in lab["blocks"]:
                    for c in bl.get("calls", []):
                        fid = re.sub(r"\s+", "", str(c.get("fn") or "")).translate(DIG)
                        if fid in fns:
                            continue
                        d = re.sub(r"\D", "", str(c.get("marker") or "").translate(DIG))
                        T["calls_unresolved"] += 1
                        if d and starts.get(d):
                            T["calls_endnote_match"] += 1
            per_art.append(dict(stem=a["stem"], pages=b["pages"], usd=b["usd"], secs=b["secs"],
                                dropped=len(b["dropped"]), dup=len(b["duplicated"]), fixes=len(b["fixes_applied"]),
                                sic=len(b["sic"]), calls=b["calls"], resolved=b["calls_resolved"],
                                failed=b["chunks_failed"]))
        T = dict(T)
        if T.get("pages"):
            T["usd_per_page"] = T["usd"] / T["pages"]
            T["secs_per_page"] = T["secs"] / T["pages"]
            T["usd_per_article"] = T["usd"] / T["articles"]
            T["secs_per_article"] = T["secs"] / T["articles"]
        res["per_run"][run] = dict(totals=T, articles=per_art)

    # ---- truth pages
    from inkscript.gold.text import folded  # noqa: F401
    for a in arts:
        secs = {run: sections(run, a["stem"]) for run in runs + r2}
        for p in range(a["first"], a["last"] + 1):
            t = truth_of(a["stem"], p)
            if not t:
                continue
            kind, doc, tl = t
            dig = kind == "bd"
            row = dict(stem=a["stem"], page=p, kind=kind, truth_words=sum(words(tl, dig).values()))
            az = [l["text"] for l in page_lines(a, p)[0]]
            cand = {"azure": az}
            for run in runs + r2:
                lab = labels(run, a["stem"])
                if lab and p in secs[run]:
                    # every Azure line in the run's order (fixes applied; equations as Azure's text, since the truth
                    # has the formula's characters), plus text the run added as missed
                    rows_ = sorted([r for r in lab["lines"] if r["page"] == p], key=lambda r: (r["order"], r["k"]))
                    added = [m.get("text", "") for m in (book(run, a["stem"]) or {}).get("missed", [])
                             if str(m.get("after", "")).split(":")[0] == str(p)]
                    cand[run] = [r["text"] for r in rows_] + added
                    cand[run + "/edition"] = page_text_lines(secs[run][p])
            for name, pl in cand.items():
                e, n = bag(words(pl, dig), words(tl, dig))
                c, ch = cer(doc, pl, dig)
                row[name] = dict(bag_err=e, bag_n=n, cer=c, chars=ch)     # cer = edit distance in characters
            # fix verdicts on this page
            for run in runs + r2:
                b = book(run, a["stem"])
                if not b:
                    continue
                orig = {l["id"]: l["text"] for l in page_lines(a, p)[0]}
                v = []
                for f in b["fixes_applied"]:
                    if f.get("page") != p:
                        continue
                    base = re.sub(r"[a-p]$", "", f["at"])
                    o = orig.get(base, "")
                    if f["from"] not in o:
                        continue
                    v.append(dict(line=f["at"], frm=f["from"], to=f.get("to"), why=f.get("why"),
                                  verdict=fix_verdict(o, o.replace(f["from"], f.get("to") or "", 1), tl, dig)))
                row.setdefault("fix_verdicts", {})[run] = v
            res["truth_pages"].append(row)

    # ---- referee and model-vs-model types
    def ref_rows(stem, p):
        f = REF / f"{stem}_p{p:03d}.json"
        return jl(f)["lines"] if f.exists() else None

    conf = {run: Counter() for run in runs + r2}
    for run in runs + r2:
        hit = n = 0
        pages = 0
        perlab = defaultdict(lambda: [0, 0])
        for a in arts:
            lab = labels(run, a["stem"])
            if not lab:
                continue
            L = line_labels(lab)
            for p in a["referee"]:
                rr = ref_rows(a["stem"], p)
                if not rr:
                    continue
                pages += 1
                mine = page_lines(a, p)[0]
                for x in rr:
                    if x.get("ref") in (None, "other"):
                        continue
                    cx, cy = (x["box"][0] + x["box"][2]) / 2, (x["box"][1] + x["box"][3]) / 2
                    m = [l for l in mine if l["px"][0] - 5 <= cx <= l["px"][2] + 5 and l["px"][1] - 5 <= cy <= l["px"][3] + 5
                         and ratio(l["text"], x["text"]) > 0.8]
                    n += 1
                    got = L[m[0]["id"]]["label"] if m and m[0]["id"] in L else "none"
                    hit += got == x["ref"]
                    perlab[x["ref"]][0] += got == x["ref"]
                    perlab[x["ref"]][1] += 1
                    conf[run][(x["ref"], got)] += 1
        res["referee"][run] = dict(pages=pages, lines=n, agree=hit / n if n else None,
                                   by_label={k: dict(agree=v[0], n=v[1]) for k, v in perlab.items()},
                                   confusion=[[a_, b_, c] for (a_, b_), c in conf[run].most_common()])

    def pair(ra, rb):
        agree = n = fine_agree = 0
        seg_agree = seg_n = 0
        cm = Counter()
        orders = []
        tabs = []
        cont = [0, 0, 0]
        for a in arts:
            la, lb = labels(ra, a["stem"]), labels(rb, a["stem"])
            if not la or not lb:
                continue
            A, B = line_labels(la), line_labels(lb)
            for i in set(A) & set(B):
                n += 1
                agree += A[i]["label"] == B[i]["label"]
                fine_agree += A[i]["type"] == B[i]["type"]
                if A[i]["label"] != B[i]["label"]:
                    cm[(A[i]["label"], B[i]["label"])] += 1
            for p in range(a["first"], a["last"] + 1):
                sa = [i for i, r in sorted(A.items(), key=lambda kv: (kv[1]["order"], kv[1]["k"])) if r["page"] == p]
                sb = [i for i, r in sorted(B.items(), key=lambda kv: (kv[1]["order"], kv[1]["k"])) if r["page"] == p]
                ls, W, _ = page_lines(a, p)
                az = [l["id"] for l in ls]
                c, pairs = kendall(sa, sb)
                ca, _ = kendall(sa, az)
                cb, _ = kendall(sb, az)
                if c is not None:
                    orders.append(dict(stem=a["stem"], page=p, multicol=multicol(ls, W), tau=c, pairs=pairs,
                                       a_vs_azure=ca, b_vs_azure=cb))
                for x, y in zip(sa, sa[1:]):
                    if y in B and x in B:
                        seg_n += 1
                        seg_agree += (A[x]["block"] == A[y]["block"]) == (B[x]["block"] == B[y]["block"])
            # tables
            text = {r["id"]: r["text"] for r in la["lines"]}
            textb = {r["id"]: r["text"] for r in lb["lines"]}
            ta = [b for b in la["blocks"] if b["type"] == "table"]
            tb = [b for b in lb["blocks"] if b["type"] == "table"]
            used = set()
            from inkscript.gold.score import teds
            for x in ta:
                sx = {re.sub(r"[a-p]$", "", i) for i in x["ids"]}
                best, bj = 0, None
                for j, y in enumerate(tb):
                    sy = {re.sub(r"[a-p]$", "", i) for i in y["ids"]}
                    jac = len(sx & sy) / max(1, len(sx | sy))
                    if jac > best:
                        best, bj = jac, j
                row = dict(stem=a["stem"], page=x["page"], n=x["n"], lines=len(sx),
                           rows_a=len(x["rows"]), cells_a=sum(len(r) for r in x["rows"]))
                if bj is not None and best >= 0.5:
                    used.add(bj)
                    y = tb[bj]
                    row.update(nb=y["n"], jaccard=round(best, 3), rows_b=len(y["rows"]),
                               cells_b=sum(len(r) for r in y["rows"]),
                               teds=teds(table_html(x["rows"], text), table_html(y["rows"], textb)))
                tabs.append(row)
            for j, y in enumerate(tb):
                if j not in used:
                    tabs.append(dict(stem=a["stem"], page=y["page"], nb=y["n"], only_b=True,
                                     lines=len(y["ids"]), rows_b=len(y["rows"])))
            # page-break continuations: first line of each continued block
            fa = {b["ids"][0] for b in la["blocks"] if b.get("continued") and b.get("ids")}
            fb = {b["ids"][0] for b in lb["blocks"] if b.get("continued") and b.get("ids")}
            cont[0] += len(fa & fb)
            cont[1] += len(fa - fb)
            cont[2] += len(fb - fa)
        mc = [o for o in orders if o["multicol"]]

        def wavg(xs, key="tau"):
            w = sum(o["pairs"] for o in xs)
            return sum(o[key] * o["pairs"] for o in xs if o[key] is not None) / w if w else None
        tt = [t for t in tabs if t.get("teds") is not None]
        return dict(lines=n, label_agree=agree / n if n else None, type_agree=fine_agree / n if n else None,
                    disagreements=[[x, y, c] for (x, y), c in cm.most_common(20)],
                    segmentation_agree=seg_agree / seg_n if seg_n else None,
                    order_all=wavg(orders), order_multicol=wavg(mc), multicol_pages=len(mc),
                    pages_order_below_95=[o for o in orders if o["tau"] < 0.95],
                    tables_a=sum(1 for t in tabs if not t.get("only_b")), tables_b_only=sum(1 for t in tabs if t.get("only_b")),
                    tables_paired=len(tt), teds_mean=sum(t["teds"] for t in tt) / len(tt) if tt else None,
                    tables=tabs, continued_both=cont[0], continued_a_only=cont[1], continued_b_only=cont[2],
                    order_pages=orders)

    if len(runs) >= 2:
        res["pair"][f"{runs[0]}~{runs[1]}"] = pair(runs[0], runs[1])
    for r in r2:
        base = r.replace("_r2", "")
        if base in runs:
            res["noise"][f"{base}~{r}"] = pair(base, r)

    # ---- metadata vs JATS
    for a in arts:
        m = jats_master(a["stem"])
        if not m:
            continue
        row = dict(stem=a["stem"], master=m)
        for run in runs:
            f = OUT / run / "docs" / f"{a['stem']}.html"
            if not f.exists():
                continue
            mm = re.search(r'<script type="application/json" id="article-meta">(.*?)</script>', f.read_text(encoding="utf-8"), re.S)
            meta = json.loads(mm.group(1)) if mm else {}
            r = dict(meta={k: meta.get(k) for k in ("title", "subtitle", "authors", "abstract", "journal", "year",
                                                     "volume", "issue", "pages_printed")})
            if m["title"]:
                t = meta.get("title") or ""
                full = t + (" " + meta["subtitle"] if meta.get("subtitle") else "")
                rt = max(ratio(norm_meta(t), norm_meta(m["title"])), ratio(norm_meta(full), norm_meta(m["title"])))
                r["title"] = dict(exact=norm_meta(t) == norm_meta(m["title"]) or norm_meta(full) == norm_meta(m["title"]),
                                  ratio=round(rt, 3))
            if m["authors"]:
                names = [x.get("name") if isinstance(x, dict) else str(x) for x in (meta.get("authors") or [])]
                found = []
                for mn in m["authors"]:
                    k = norm_meta(re.sub(r"^(د|دكتور|الدكتور|أ\.?د|الأستاذ|الاستاذ)\s*[./]?\s*/?", "", mn))
                    best = max([ratio(k, norm_meta(x)) for x in names if x] + [0.0])
                    hit_sub = any(k and (k in norm_meta(x) or norm_meta(x) in k) for x in names if x and norm_meta(x))
                    found.append(dict(master=mn, best=round(best, 3), match=best >= 0.85 or hit_sub))
                r["authors"] = dict(master=len(m["authors"]), model=len(names), matched=sum(f["match"] for f in found),
                                    detail=found)
            if m["abstract"]:
                ab = meta.get("abstract") or {}
                txt = " ".join(v for v in ab.values() if isinstance(v, str)) if isinstance(ab, dict) else str(ab)
                best = max(ratio(norm_meta(x), norm_meta(txt)) for x in m["abstract"])
                r["abstract"] = dict(ratio=round(best, 3), have=bool(txt.strip()))
            row[run] = r
        res["metadata"].append(row)
    (OUT / "scores.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return res


def summary(res):
    runs = res["runs"]
    print("== per run")
    for run, d in res["per_run"].items():
        T = d["totals"]
        print(f" {run:10} art {T.get('articles')} p {T.get('pages')} lines {T.get('used')}/{T.get('lines')} drop "
              f"{T.get('dropped')} dup {T.get('duplicated')} noise {T.get('noise')} fixes {T.get('fixes')} sic "
              f"{T.get('sic')} missed {T.get('missed')} calls {T.get('calls_resolved')}/{T.get('calls')} uncalled "
              f"{T.get('footnotes_uncalled')} cont {T.get('continued')} failed {T.get('chunks_failed')} "
              f"${T.get('usd', 0):.3f} ${T.get('usd_per_page', 0):.4f}/p {T.get('secs_per_page', 0):.1f}s/p")
    print("== truth pages")
    for kind in ("gold", "bd", None):
        rows = [r for r in res["truth_pages"] if kind is None or r["kind"] == kind]
        if not rows:
            continue
        out = []
        names = ["azure"] + runs + [r for r in res["per_run"] if r.endswith("_r2")] + [r + "/edition" for r in runs]
        rows = [r for r in rows if all(nm in r for nm in ["azure"] + runs)]      # like with like: pages all runs have
        for name in names:
            rr = [r for r in rows if name in r]
            e = sum(r[name]["bag_err"] for r in rr)
            n = sum(r[name]["bag_n"] for r in rr)
            c = sum(r[name]["cer"] for r in rr)            # edit distance (characters)
            ch = sum(r[name]["chars"] for r in rr)
            if n:
                out.append(f"{name} {100 * e / n:.2f}% (cer {100 * c / ch:.2f}%, {len(rr)} p)")
        print(f" {kind or 'all':5}", " | ".join(out))
    for run in runs:
        v = Counter(x["verdict"] for r in res["truth_pages"] for x in r.get("fix_verdicts", {}).get(run, []))
        print(f" fix verdicts {run}: {dict(v)}")
    print("== referee")
    for run, d in res["referee"].items():
        print(f" {run}: {d['agree']} on {d['lines']} lines, {d['pages']} pages")
    for k, d in list(res["pair"].items()) + list(res["noise"].items()):
        print(f"== {k}: labels {d['label_agree']:.4f} types {d['type_agree']:.4f} seg {d['segmentation_agree']:.4f} "
              f"order {d['order_all']:.4f} multicol {d['order_multicol']} ({d['multicol_pages']} p) tables "
              f"{d['tables_a']}+{d['tables_b_only']} paired {d['tables_paired']} teds {d['teds_mean']} cont "
              f"{d['continued_both']}/{d['continued_a_only']}/{d['continued_b_only']}")
    print("== metadata")
    for run in runs:
        rows = [r[run] for r in res["metadata"] if run in r]
        t = [r["title"] for r in rows if "title" in r]
        au = [r["authors"] for r in rows if "authors" in r]
        ab = [r["abstract"] for r in rows if "abstract" in r]
        print(f" {run}: title exact {sum(x['exact'] for x in t)}/{len(t)} near>=0.9 {sum(x['ratio'] >= 0.9 for x in t)}"
              f" | authors {sum(x['matched'] for x in au)}/{sum(x['master'] for x in au)} | abstract near "
              f"{sum(x['ratio'] >= 0.9 for x in ab)}/{len(ab)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", default=["argon", "flash"])
    ap.add_argument("--r2", nargs="*", default=[])
    a = ap.parse_args()
    summary(score(a.runs, a.r2))


if __name__ == "__main__":
    main()
