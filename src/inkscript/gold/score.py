"""`inkscript score`: one reader's output against the gold pages (experiment 34).

    inkscript score --gold GOLD_DIR --pred PRED_DIR [--name NAME] [--out report.json] [--drafts]
    inkscript score --gold GOLD_DIR --reader azure-draft|gemini-draft [--drafts]     the readings kept in the gold
                                                                                     files (a smoke test)
A prediction per page, PRED_DIR/<page_id>.json (or .pred.json):
    {"lines": [{"text": "...", "box": [x0, y0, x1, y1]}, ...],      # reading order; box optional (gold pixels)
     "tables": [{"html": "<table>...</table>", "box": [...]}],     # optional
     "equations": [{"latex": "...", "box": [...]}]}                 # optional
or PRED_DIR/<page_id>.txt: one line of text per line, in reading order. A page with no prediction file counts
as read empty (everything dropped).

Only pages whose status is "done" are gold; --drafts also scores pages still in draft (their draft text taken as
the truth: plumbing only, never a result).

What is measured, per page, then summed over pages (micro averages) and broken down by the page's kinds, its
decade, and by line kind:
  cer, wer           edit distance over the page's text in the reader's order (lines joined by a space) divided by
                     the gold's characters / words; under the faithful and the folded normalisation (gold/text.py)
  line_cer           order-free: each reader line matched to a gold line (by box overlap when both have boxes,
                     otherwise by text), then the matched pairs' distances + every dropped gold line's characters +
                     every invented line's characters, over the gold's characters
  dropped            gold lines with no reader line (text skipped)
  inserted           reader lines matching no gold line and repeating none (invented text: hallucination)
  repeated           reader lines matching no gold line that repeat another reader line, plus lines that loop
                     (the same 1-6 word run four or more times in a row)
  order              share of pairs of matched lines the reader puts in the gold's order (Kendall concordance)
  teds               tree edit distance similarity of each gold table with the reader's table at the same place
                     (PubTabNet's TEDS: 1 - TED / max nodes; a cell's rename cost is its text's normalised edit
                     distance); a missing table scores 0
  eq_sim             1 - normalised edit distance over LaTeX tokens (spacing, \\left/\\right, \\displaystyle and
                     braces around one token removed); eq_exact: equal after that normalisation. Not CDM (which
                     renders both): a cheap stand-in until formulas matter.
Intervals: 95% percentile bootstrap over documents (1,000 resamples, seed 34): a document's pages go in or out
together, because pages of one document share a typeface and a scan.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from .format import gold_lines, load, pages
from .text import NORMS, distance, faithful

TEXT_KINDS = ("text", "heading", "title", "footnote", "caption", "cell", "furniture", "verse")


# ---------------------------------------------------------------- predictions

def read_pred(pred_dir: Path, pid: str) -> dict | None:
    for name in (f"{pid}.pred.json", f"{pid}.json"):
        f = pred_dir / name
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(d, list):
                d = {"lines": d}
            d["lines"] = [x if isinstance(x, dict) else {"text": str(x)} for x in d.get("lines", [])]
            return d
    f = pred_dir / f"{pid}.txt"
    if f.exists():
        return {"lines": [{"text": t} for t in f.read_text(encoding="utf-8").splitlines() if t.strip()]}
    return None


def draft_pred(g: dict, which: str) -> dict:
    """The reading the draft was made from (azure) or the second one (gemini), in the draft's line order, with
    the draft boxes; lines that reading has no text for are left out."""
    by = {ln["id"]: ln for ln in g["lines"]}
    out = []
    for i in g["order"]:
        ln = by[i]
        t = (ln.get("draft") or {}).get(which)
        if t:
            out.append({"text": t, "box": ln["box"]})
    return {"lines": out, "tables": [{"html": t.get("draft_html", "")} for t in g.get("tables", [])],
            "equations": [{"latex": e.get("draft_latex", "")} for e in g.get("equations", [])]}


def as_gold_draft(g: dict) -> dict:
    """A draft page scored as if it were gold (--drafts): every line counts, its text as it stands."""
    return g


# ---------------------------------------------------------------- line matching

def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def _sim(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 1.0 - distance(a, b) / max(len(a), len(b))


def match_lines(gold: list[tuple[str, list | None]], pred: list[tuple[str, list | None]]) -> list[tuple[int, int]]:
    """Pairs (gold index, pred index), each line used at most once. Boxes on both sides: by overlap (IoU >= 0.3,
    best first; a pred line whose box overlaps no gold line falls back to text). Otherwise by text: best similarity
    first, at least 0.4 of the longer line's characters right."""
    cand = []
    use_box = all(b for _, b in gold) and all(b for _, b in pred) and gold and pred
    for i, (gt, gb) in enumerate(gold):
        for j, (pt, pb) in enumerate(pred):
            if use_box:
                v = _iou(gb, pb)
                if v >= 0.3:
                    cand.append((1.0 + v, i, j))
                    continue
            if gt and pt and abs(len(gt) - len(pt)) <= max(len(gt), len(pt)) * 0.7:
                s = _sim(gt, pt)
                if s >= 0.4:
                    cand.append((s, i, j))
    cand.sort(key=lambda t: (-t[0], t[1], t[2]))       # ties: the earlier lines first
    gi, pj, pairs = set(), set(), []
    for _, i, j in cand:
        if i in gi or j in pj:
            continue
        gi.add(i)
        pj.add(j)
        pairs.append((i, j))
    return sorted(pairs)


_LOOP = re.compile(r"((?:\S+\s+){1,6}?)\1{3,}")


def loops(t: str) -> bool:
    return bool(_LOOP.search(t + " "))


def concordance(seq: list[int]) -> tuple[int, int]:
    """(concordant pairs, all pairs) of a sequence of gold indices in the reader's order."""
    n = len(seq)
    c = 0
    for a in range(n):
        for b in range(a + 1, n):
            c += seq[a] < seq[b]
    return c, n * (n - 1) // 2


# ---------------------------------------------------------------- tables: TEDS (Zhang-Shasha tree edit distance)

class _Node:
    __slots__ = ("tag", "text", "span", "kids")

    def __init__(self, tag, text="", span=(1, 1), kids=None):
        self.tag, self.text, self.span, self.kids = tag, text, span, kids or []


def table_tree(html: str) -> _Node | None:
    if not html or "<t" not in html.lower():
        return None
    from lxml import html as LH
    try:
        root = LH.fromstring(html)
    except Exception:
        return None
    t = root if root.tag == "table" else root.find(".//table")
    if t is None:
        return None
    rows = []
    for tr in t.iter("tr"):
        cells = []
        for c in tr:
            if c.tag not in ("td", "th"):
                continue
            span = (int(c.get("rowspan", 1) or 1), int(c.get("colspan", 1) or 1))
            cells.append(_Node("td", faithful(c.text_content()), span))
        rows.append(_Node("tr", kids=cells))
    return _Node("table", kids=rows)


def _post(root):
    nodes, lml = [], []

    def walk(n):
        first = None
        for k in n.kids:
            f = walk(k)
            first = f if first is None else first
        nodes.append(n)
        me = len(nodes) - 1
        lml.append(first if first is not None else me)
        return lml[me]
    walk(root)
    return nodes, lml


def tree_distance(a: _Node, b: _Node) -> float:
    na, la = _post(a)
    nb, lb = _post(b)

    def ren(x, y):
        if x.tag != y.tag:
            return 1.0
        if x.tag == "td":
            if x.span != y.span:
                return 1.0
            if not x.text and not y.text:
                return 0.0
            return distance(x.text, y.text) / max(len(x.text), len(y.text))
        return 0.0
    kra = sorted({max(i for i in range(len(na)) if la[i] == la[k]) for k in range(len(na))})
    krb = sorted({max(j for j in range(len(nb)) if lb[j] == lb[k]) for k in range(len(nb))})
    td = [[0.0] * len(nb) for _ in range(len(na))]
    for i in kra:
        for j in krb:
            li, lj = la[i], lb[j]
            m, n = i - li + 2, j - lj + 2
            fd = [[0.0] * n for _ in range(m)]
            for x in range(1, m):
                fd[x][0] = fd[x - 1][0] + 1
            for y in range(1, n):
                fd[0][y] = fd[0][y - 1] + 1
            for x in range(1, m):
                for y in range(1, n):
                    ii, jj = li + x - 1, lj + y - 1
                    if la[ii] == li and lb[jj] == lj:
                        fd[x][y] = min(fd[x - 1][y] + 1, fd[x][y - 1] + 1, fd[x - 1][y - 1] + ren(na[ii], nb[jj]))
                        td[ii][jj] = fd[x][y]
                    else:
                        p, q = la[ii] - li, lb[jj] - lj
                        fd[x][y] = min(fd[x - 1][y] + 1, fd[x][y - 1] + 1, fd[p][q] + td[ii][jj])
    return td[len(na) - 1][len(nb) - 1]


def teds(gold_html: str, pred_html: str) -> float | None:
    g = table_tree(gold_html)
    if g is None:
        return None
    p = table_tree(pred_html)
    if p is None:
        return 0.0
    ng, np_ = len(_post(g)[0]), len(_post(p)[0])
    return max(0.0, 1.0 - tree_distance(g, p) / max(ng, np_))


# ---------------------------------------------------------------- equations

_TOK = re.compile(r"\\[A-Za-z]+|\\.|[A-Za-z]|\d|\S")


def latex_tokens(s: str) -> list[str]:
    s = re.sub(r"\\(left|right|displaystyle|textstyle|,|;|!|quad|qquad)(?![A-Za-z])", " ", s or "")
    s = s.strip().strip("$").strip()
    toks = _TOK.findall(s)
    out = []
    i = 0
    while i < len(toks):                      # {x} -> x
        if toks[i] == "{" and i + 2 < len(toks) and toks[i + 2] == "}":
            out.append(toks[i + 1])
            i += 3
            continue
        out.append(toks[i])
        i += 1
    return out


def eq_sim(g: str, p: str) -> tuple[float, bool]:
    a, b = latex_tokens(g), latex_tokens(p)
    if not a and not b:
        return 1.0, True
    return 1.0 - distance(a, b) / max(len(a), len(b)), a == b


# ---------------------------------------------------------------- one page

def score_page(g: dict, pred: dict | None, drafts: bool = False) -> dict:
    pred = pred or {"lines": []}
    every = gold_lines(g)
    gl = [ln for ln in every if ln.get("kind", "text") != "equation"]
    pl = [x for x in pred.get("lines", []) if (x.get("text") or "").strip()]
    eq = [ln for ln in every if ln.get("kind") == "equation"]
    if eq and pl:                 # a reader's lines that are the page's equations are scored as equations, not text
        f = NORMS["faithful"]
        hit = {j for _, j in match_lines([(f(ln.get("text", "")), ln.get("box")) for ln in eq],
                                         [(f(x["text"]), x.get("box")) for x in pl])}
        pl = [x for j, x in enumerate(pl) if j not in hit]
    out = dict(page_id=g["page_id"], stem=g["stem"], kinds=g.get("kinds", []), primary=g.get("primary", ""),
               decade=g.get("decade", ""), split=g.get("split", ""), gold_lines=len(gl), pred_lines=len(pl))
    for name, norm in NORMS.items():
        gt = [norm(ln.get("text", "")) for ln in gl]
        pt = [norm(x.get("text", "")) for x in pl]
        G, P = " ".join(t for t in gt if t), " ".join(t for t in pt if t)
        out[f"{name}.chars"] = len(G)
        out[f"{name}.char_err"] = distance(G, P)
        out[f"{name}.words"] = len(G.split())
        out[f"{name}.word_err"] = distance(G.split(), P.split())
        pairs = match_lines([(t, ln.get("box")) for t, ln in zip(gt, gl)], [(t, x.get("box")) for t, x in zip(pt, pl)])
        mg, mp = {i for i, _ in pairs}, {j for _, j in pairs}
        line_err = sum(distance(gt[i], pt[j]) for i, j in pairs)
        dropped = [i for i in range(len(gt)) if i not in mg and gt[i]]
        extra = [j for j in range(len(pt)) if j not in mp and pt[j]]
        repeated = [j for j in extra if any(_sim(pt[j], pt[k]) >= 0.8 for k in range(len(pt)) if k != j)]
        looping = [j for j in range(len(pt)) if loops(pt[j])]
        inserted = [j for j in extra if j not in repeated]
        line_err += sum(len(gt[i]) for i in dropped) + sum(len(pt[j]) for j in extra)
        out[f"{name}.line_err"] = line_err
        if name == "faithful":
            out["dropped"] = len(dropped)
            out["inserted"] = len(inserted)
            out["repeated"] = len(repeated) + len([j for j in looping if j not in repeated])
            out["dropped_chars"] = sum(len(gt[i]) for i in dropped)
            out["inserted_chars"] = sum(len(pt[j]) for j in inserted)
            c, n = concordance([i for i, j in sorted(pairs, key=lambda t: t[1])])
            out["order_ok"], out["order_pairs"] = c, n
            # per line kind: matched errors + dropped chars, over gold chars of that kind
            bk = defaultdict(lambda: [0, 0])
            pj = dict(pairs)
            for i, ln in enumerate(gl):
                k = ln.get("kind", "text")
                bk[k][1] += len(gt[i])
                bk[k][0] += distance(gt[i], pt[pj[i]]) if i in pj else len(gt[i])
            out["by_line_kind"] = {k: v for k, v in bk.items()}
    ts = []
    ptab = pred.get("tables", [])
    for k, t in enumerate(g.get("tables", [])):
        v = teds(t.get("html") or (t.get("draft_html") if drafts else ""), ptab[k].get("html", "") if k < len(ptab) else "")
        if v is not None:
            ts.append(v)
    out["teds"] = ts
    es = []
    peq = pred.get("equations", [])
    for k, e in enumerate(g.get("equations", [])):
        ref = e.get("latex") or (e.get("draft_latex") if drafts else "")
        if ref:
            es.append(eq_sim(ref, peq[k].get("latex", "") if k < len(peq) else ""))
    out["eq"] = es
    return out


# ---------------------------------------------------------------- summing up

def _sum(rows: list[dict]) -> dict:
    s = defaultdict(float)
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                s[k] += v
    o = dict(pages=len(rows), docs=len({r["stem"] for r in rows}))
    for name in NORMS:
        c, w = s[f"{name}.chars"], s[f"{name}.words"]
        o[f"{name}.cer"] = s[f"{name}.char_err"] / c if c else None
        o[f"{name}.wer"] = s[f"{name}.word_err"] / w if w else None
        o[f"{name}.line_cer"] = s[f"{name}.line_err"] / c if c else None
    gl = s["gold_lines"]
    o["gold_lines"], o["pred_lines"] = int(gl), int(s["pred_lines"])
    for k in ("dropped", "inserted", "repeated"):
        o[k] = int(s[k])
        o[f"{k}_per_1000_lines"] = 1000 * s[k] / gl if gl else None
    o["order"] = s["order_ok"] / s["order_pairs"] if s["order_pairs"] else None
    ts = [v for r in rows for v in r.get("teds", [])]
    o["tables"], o["teds"] = len(ts), (sum(ts) / len(ts) if ts else None)
    es = [v for r in rows for v in r.get("eq", [])]
    o["equations"] = len(es)
    o["eq_sim"] = sum(v for v, _ in es) / len(es) if es else None
    o["eq_exact"] = sum(1 for _, x in es if x) / len(es) if es else None
    bk = defaultdict(lambda: [0, 0])
    for r in rows:
        for k, (e, c) in r.get("by_line_kind", {}).items():
            bk[k][0] += e
            bk[k][1] += c
    o["line_kind_cer"] = {k: (e / c if c else None) for k, (e, c) in sorted(bk.items())}
    return o


METRICS = ("faithful.cer", "faithful.wer", "folded.cer", "folded.wer", "faithful.line_cer", "inserted_per_1000_lines",
           "dropped_per_1000_lines", "repeated_per_1000_lines", "order", "teds", "eq_sim")


def bootstrap(rows: list[dict], n: int = 1000, seed: int = 34) -> dict:
    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["stem"]].append(r)
    docs = sorted(by_doc)
    if len(docs) < 2:
        return {}
    import numpy as np
    F = ["faithful.char_err", "faithful.chars", "faithful.word_err", "faithful.words", "folded.char_err",
         "folded.chars", "folded.word_err", "folded.words", "faithful.line_err", "inserted", "dropped", "repeated",
         "gold_lines", "order_ok", "order_pairs"]
    X = np.zeros((len(docs), len(F) + 4))
    for di, d in enumerate(docs):
        for r in by_doc[d]:
            X[di, :len(F)] += [r.get(k, 0) for k in F]
            X[di, len(F)] += sum(r.get("teds", []))
            X[di, len(F) + 1] += len(r.get("teds", []))
            X[di, len(F) + 2] += sum(v for v, _ in r.get("eq", []))
            X[di, len(F) + 3] += len(r.get("eq", []))
    rng = np.random.default_rng(seed)
    S = X[rng.integers(0, len(docs), size=(n, len(docs)))].sum(axis=1)
    c = {k: S[:, i] for i, k in enumerate(F)}
    c["teds_sum"], c["teds_n"], c["eq_sum"], c["eq_n"] = S[:, -4], S[:, -3], S[:, -2], S[:, -1]
    ratios = {"faithful.cer": ("faithful.char_err", "faithful.chars"), "faithful.wer": ("faithful.word_err", "faithful.words"),
              "folded.cer": ("folded.char_err", "folded.chars"), "folded.wer": ("folded.word_err", "folded.words"),
              "faithful.line_cer": ("faithful.line_err", "faithful.chars"), "order": ("order_ok", "order_pairs"),
              "teds": ("teds_sum", "teds_n"), "eq_sim": ("eq_sum", "eq_n")}
    out = {}
    for m, (a, b) in ratios.items():
        ok = c[b] > 0
        if ok.sum() >= n // 2:
            v = c[a][ok] / c[b][ok]
            out[m] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    for k in ("inserted", "dropped", "repeated"):
        ok = c["gold_lines"] > 0
        if ok.any():
            v = 1000 * c[k][ok] / c["gold_lines"][ok]
            out[f"{k}_per_1000_lines"] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    return out


def summarise(rows: list[dict], boot: int = 1000) -> dict:
    groups = defaultdict(list)
    for r in rows:
        groups["all"].append(r)
        groups[f"split:{r['split']}"].append(r)
        groups[f"decade:{r['decade']}"].append(r)
        groups[f"primary:{r['primary']}"].append(r)
        for k in r["kinds"]:
            groups[f"kind:{k}"].append(r)
    out = {}
    for name, rs in sorted(groups.items()):
        s = _sum(rs)
        if boot and name in ("all", "split:test", "split:dev") or (boot and name.startswith(("decade:", "kind:"))):
            s["ci95"] = bootstrap(rs, boot)
        out[name] = s
    return out


def run(gold_dir: Path, pred_dir: Path | None = None, reader: str | None = None, drafts: bool = False,
        split: str | None = None, boot: int = 1000) -> dict:
    rows = []
    skipped = 0
    for p in pages(gold_dir):
        g = load(p)
        if split and g.get("split") != split:
            continue
        if g.get("status") != "done" and not drafts:
            skipped += 1
            continue
        if g.get("status") == "skip":
            continue
        if reader:
            pred = draft_pred(g, reader.replace("-draft", ""))
        else:
            pred = read_pred(Path(pred_dir), g["page_id"])
        rows.append(score_page(g, pred, drafts))
    return dict(pages=rows, summary=summarise(rows, boot), not_done=skipped)


def _fmt(v, pct=True):
    if v is None:
        return "—"
    return f"{100 * v:.2f}%" if pct else f"{v:.2f}"


def print_summary(rep: dict, name: str = "") -> None:
    S = rep["summary"]
    print(f"{name}: {len(rep['pages'])} pages scored, {rep['not_done']} pages not done yet (left out)")
    hdr = f"{'group':<26}{'pages':>6}{'docs':>5}{'CER':>9}{'CER fold':>9}{'WER':>9}{'WER fold':>9}{'lineCER':>9}{'ins/1k':>8}{'drop/1k':>8}{'rep/1k':>8}{'order':>8}{'TEDS':>7}{'eq':>7}"
    print(hdr)
    for g, s in S.items():
        print(f"{g[:26]:<26}{s['pages']:>6}{s['docs']:>5}{_fmt(s['faithful.cer']):>9}{_fmt(s['folded.cer']):>9}"
              f"{_fmt(s['faithful.wer']):>9}{_fmt(s['folded.wer']):>9}{_fmt(s['faithful.line_cer']):>9}"
              f"{_fmt(s['inserted_per_1000_lines'], False):>8}{_fmt(s['dropped_per_1000_lines'], False):>8}"
              f"{_fmt(s['repeated_per_1000_lines'], False):>8}{_fmt(s['order']):>8}{_fmt(s['teds'], False):>7}"
              f"{_fmt(s['eq_sim'], False):>7}")
    ci = S.get("all", {}).get("ci95", {})
    if ci:
        print("95% intervals over documents (all): " + ", ".join(
            f"{m} [{_fmt(a, m not in ('teds', 'eq_sim') and 'per_1000' not in m)}–{_fmt(b, m not in ('teds', 'eq_sim') and 'per_1000' not in m)}]"
            for m, (a, b) in ci.items()))


def main(a) -> int:
    if not a.pred and not a.reader:
        print("give --pred DIR or --reader azure-draft|gemini-draft")
        return 2
    rep = run(Path(a.gold), Path(a.pred) if a.pred else None, a.reader, a.drafts, a.split, a.boot)
    name = a.name or a.reader or Path(a.pred).name
    rep["reader"] = name
    print_summary(rep, name)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print("wrote", a.out)
    return 0


def add_parser(sub) -> None:
    p = sub.add_parser("score", help="score a reader's output against the gold pages (CER/WER, invented and dropped lines, TEDS, equations, order)")
    p.add_argument("--gold", required=True, help="the gold dir (<page_id>.json, inkscript-gold/1)")
    p.add_argument("--pred", help="dir of <page_id>.json / .pred.json / .txt from the reader")
    p.add_argument("--reader", choices=["azure-draft", "gemini-draft"], help="score a reading kept in the gold files instead")
    p.add_argument("--drafts", action="store_true", help="also score pages not yet corrected, their draft as truth (smoke test only)")
    p.add_argument("--split", choices=["test", "dev"], help="only this split")
    p.add_argument("--name", help="the reader's name in the report")
    p.add_argument("--boot", type=int, default=1000, help="bootstrap resamples (0 = no intervals)")
    p.add_argument("--out", help="write the full report (every page) as JSON")
    p.set_defaults(fn=lambda a: main(a))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    add_parser(ap.add_subparsers(dest="cmd", required=True))
    a = ap.parse_args(["score"] + sys.argv[1:])
    sys.exit(a.fn(a))
