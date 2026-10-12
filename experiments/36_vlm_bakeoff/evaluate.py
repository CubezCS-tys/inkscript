"""Experiment 36: every reader scored on three page sets, with hallucination accounting and Kraken as a checker.

    PYTHONPATH=<worktree>/src /home/yassine/inkscript/.venv/bin/python evaluate.py [--readers a,b] [--workers 3]
                                                                                     [--boot 1000]
Reads out/pred/<reader>/ (convert.py) and writes out/results.json (+ out/eval_pages.jsonl, one row per page and
reader, everything the summary is summed from).

Page sets (each measure is reported per set; the references differ, so the sets are never pooled):
  gold      yardstick pages whose gold status is "done" (read afresh on every run: rerun at the end); truth = the
            owner's corrections; scored with `inkscript score`'s own function (gold/score.py run()), so the numbers
            are the CLI's. NB the gold was corrected from Azure's draft: Azure's gold numbers are flattered.
  bd        born-digital pages vs the PDF's own text (out/ref/bdtruth); digits folded to ASCII on both sides (some
            producers store Western codes for Arabic-Indic glyphs: bd.py).
  ys_azure  all 202 yardstick pages vs Azure: AGREEMENT WITH AZURE, not accuracy (Azure is a reader too). Tables
            and equations here are compared with the gold files' drafts (gemini-3.1-pro), a draft, not truth.
Strata: split, decade band, vowelled/Quran, table, equation, multi-column (columns/magazine/ncols>1), footnotes,
Latin. Intervals: 95% percentile bootstrap over documents, 1,000 draws (a document's pages go in or out together).

Text measures (score.py's score_page on a reference made from the set's truth): faithful/folded CER and WER in the
reader's order; line CER and inserted/dropped/repeated LINES (from the .kl re-cut where the reader gives blocks, since
block models give paragraphs); line-pair order; TEDS; LaTeX similarity.

Hallucination accounting (words, order-free, on folded words; experiment 36's own, see README):
  anchor    a reader word is anchored when it matches (equal, or >= 0.75 character similarity for words of 4+
            letters) a reference word AND a neighbour matches that reference word's neighbour (an aligned pair).
  invented  a run of >= 3 consecutive unanchored reader words that is not a misreading: not similar (>= 0.5 character
            similarity) to the reference text between the anchors either side of it, and fewer than 70% of its
            3+-letter words loosely (>= 0.6) match any reference word. Truth where there is one; on ys_azure the run
            must also be unexplained by Kraken's reading (Azure misses text Kraken sees); `invented_az` is the
            Azure-only version (the label for the checker there, so the checker is not scored against itself).
  dropped   the same, the other way: reference word runs the reader does not have.
  repeated  reader words covered by a 4-word run occurring more often in the reader than in the reference (loops,
            duplicated lines); not counted as invented.
  runaway   the page hit the token cap, timed out or failed, or the reader has > 2x the reference's words + 50.
Per 1,000 reference words and share of pages affected (>= 1 run).

Kraken as a checker (for every reader but Kraken): flag reader words in runs unexplained by Kraken's reading (the
invented rule with Kraken as the reference: no Kraken counterpart, or text that strongly disagrees) plus every word of
a block whose box holds no Kraken line; precision/recall of the flags against the invented words above (word level).
Dropped: Kraken word runs with no counterpart in the reader, scored against the reference's dropped words.
Vowel marks: on anchored word pairs whose letters (marks removed) are equal, marks compared letter by letter:
precision, recall. Word order: Kendall concordance of anchored words' reference positions in the reader's order
(robust to line cutting; catches swapped columns and left-to-right reversals).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from inkscript.gold.format import gold_lines, load
from inkscript.gold.score import loops, score_page
from inkscript.gold.text import HARAKAT, distance, faithful, folded

OUT = Path("/home/yassine/inkscript/experiments/36_vlm_bakeoff/out")
GOLD = Path("/home/yassine/inkscript/experiments/34_yardstick/out/gold")
PRED = OUT / "pred"
MANIFEST = json.load(open(OUT / "pack" / "manifest.json"))["pages"]
MAN = {p["page_id"]: p for p in MANIFEST}
DIG = str.maketrans({**{chr(0x660 + i): str(i) for i in range(10)}, **{chr(0x6f0 + i): str(i) for i in range(10)}})
RUN = 3


# ---------------------------------------------------------------- references

def jload(f: Path):
    return json.loads(f.read_text(encoding="utf-8"))


def gold_done() -> dict:
    out = {}
    for f in sorted(GOLD.glob("*.json")):
        try:
            g = load(f)
        except Exception:
            continue
        if g.get("status") == "done" and g["page_id"] in MAN:
            out[g["page_id"]] = g
    return out


def pseudo_gold(pid: str, lines: list[dict], tables=(), equations=()) -> dict:
    p = MAN[pid]
    ls = [dict(id=f"l{i:03d}", text=ln.get("text", ""), box=ln.get("box"), kind=ln.get("kind") or "text", status="ok")
          for i, ln in enumerate(lines) if (ln.get("text") or "").strip()]
    return dict(page_id=pid, stem=p["stem"], kinds=p.get("tags", []), primary=p.get("primary", ""),
                decade=p.get("decade", ""), split=p.get("split", ""), lines=ls, order=[x["id"] for x in ls],
                tables=list(tables), equations=list(equations), status="done")


def drafts_of(pid: str):
    """The gold file's drafted tables/equations (gemini-3.1-pro), as references for the ys_azure set."""
    f = GOLD / f"{pid}.json"
    if not f.exists():
        return [], []
    g = jload(f)
    t = [dict(html=x.get("html") or x.get("draft_html") or "", box=x.get("box")) for x in g.get("tables", [])]
    e = [dict(latex=x.get("latex") or x.get("draft_latex") or "", box=x.get("box")) for x in g.get("equations", [])]
    return [x for x in t if x["html"]], [x for x in e if x["latex"]]


def digits_folded(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    for ln in d.get("lines", []):
        ln["text"] = (ln.get("text") or "").translate(DIG)
    return d


# ---------------------------------------------------------------- words, anchors, runs

_PUNCT = re.compile("[^\\w\u064b-\u065f\u0670\u06d6-\u06ed\u08d3-\u08ff]|_")   # keeps vowel marks (combining marks are not \\w)


def tokens(lines: list[str]) -> list[tuple[str, str, int]]:
    """(folded word, faithful word without punctuation, line index) for every word with letters or digits."""
    out = []
    for li, t in enumerate(lines):
        for w in faithful(t).split():
            fw = folded(w).replace(" ", "")
            if fw:
                out.append((fw, _PUNCT.sub("", w.replace("ـ", "")) or w, li))
    return out


def _sim(a: str, b: str) -> float:
    return 1.0 - distance(a, b) / max(len(a), len(b), 1)


class Ref:
    """A reference's words, indexed for fuzzy lookups."""

    def __init__(self, toks):
        self.toks = toks
        self.w = [t[0] for t in toks]
        self.pos = defaultdict(list)
        for j, w in enumerate(self.w):
            self.pos[w].append(j)
        self.bylen = defaultdict(list)
        for w in self.pos:
            self.bylen[len(w)].append(w)
        self._fz, self._loose, self._tri = {}, {}, None

    def tri(self) -> set:
        if self._tri is None:
            self._tri = _tri(" ".join(self.w))
        return self._tri

    def matches(self, w: str) -> set:
        """Reference positions whose word is w or (4+ letters) within 0.75 similarity."""
        if w in self._fz:
            return self._fz[w]
        s = set(self.pos.get(w, ()))
        if len(w) >= 4:
            d = max(1, len(w) // 4)
            for L in range(len(w) - d, len(w) + d + 1):
                for r in self.bylen.get(L, ()):
                    if r != w and _sim(w, r) >= 0.75:
                        s.update(self.pos[r])
        self._fz[w] = s
        return s

    def loose(self, w: str) -> bool:
        if w in self._loose:
            return self._loose[w]
        ok = w in self.pos
        if not ok:
            d = len(w) // 2 + 1
            for L in range(max(1, len(w) - d), len(w) + d + 1):
                if any(_sim(w, r) >= 0.6 for r in self.bylen.get(L, ())):
                    ok = True
                    break
        self._loose[w] = ok
        return ok


def _tri(s: str) -> set:
    s = s.replace(" ", "")
    return {s[i:i + 3] for i in range(len(s) - 2)}


def anchors(P: list[str], R: Ref) -> list[int]:
    """For each reader word the reference position it is anchored to, or -1."""
    M = [R.matches(w) for w in P]
    out = [-1] * len(P)
    prev = None
    for i in range(len(P)):
        if not M[i]:
            continue
        # an aligned neighbour pair, in either direction (a left-to-right reversal is still the page's text)
        cand = [j for j in M[i] if (i > 0 and (j - 1 in M[i - 1] or j + 1 in M[i - 1]))
                or (i + 1 < len(P) and (j + 1 in M[i + 1] or j - 1 in M[i + 1]))]
        if not cand:
            continue
        # a common word pair occurs many times: take the occurrence that continues the previous anchor
        out[i] = min(cand, key=lambda j: (abs(j - (prev + 1)) if prev is not None else j, j))
        prev = out[i]
    return out


def runs(flags: list[bool]) -> list[tuple[int, int]]:
    out, s = [], None
    for i, f in enumerate(flags + [False]):
        if f and s is None:
            s = i
        elif not f and s is not None:
            out.append((s, i))
            s = None
    return out


def unexplained(P: list[str], anc: list[int], R: Ref, skip: set = frozenset()) -> list[tuple[int, int]]:
    """Runs of >= RUN unanchored reader words that are not misreadings of the reference (see the docstring)."""
    from collections import Counter
    avail = Counter(R.w) - Counter(R.w[a] for a in anc if a >= 0)      # reference words no reader word took
    out = []
    for s, e in runs([a < 0 and i not in skip for i, a in enumerate(anc)]):
        if e - s < RUN:
            continue
        # reordered, not invented: most of the run's words are reference words still unclaimed (a table read in
        # another cell order, numbers, a moved caption)
        av, present = avail.copy(), 0
        for w in P[s:e]:
            if av[w] > 0:
                av[w] -= 1
                present += 1
        if present >= 0.7 * (e - s):
            continue
        run_text = " ".join(P[s:e])
        # a misreading of text on the page: most of its letter triples occur in the reference (a true invention,
        # measured with lines from other pages, has a median 0.28 and a 90th centile 0.46)
        t3 = _tri(run_text)
        if t3 and len(t3 & R.tri()) >= 0.6 * len(t3):
            continue
        ja = next((anc[k] for k in range(s - 1, -1, -1) if anc[k] >= 0), None)
        jb = next((anc[k] for k in range(e, len(P)) if anc[k] >= 0), None)
        if ja is not None and jb is not None and 0 <= jb - ja - 1 <= 3 * (e - s) + 5:
            # anchored on both sides in order: an insertion (gap 0) or a substitution, judged by the gap's text only
            if jb - ja - 1 > 0 and _sim(run_text, " ".join(R.w[ja + 1:jb])) >= 0.5:
                continue
            out.append((s, e))
            continue
        if ja is not None or jb is not None:
            # out of order (a column jump) or at an end of the page: the reference text that would follow the left
            # anchor or precede the right one
            L = e - s
            win = ([" ".join(R.w[ja + 1:ja + 1 + L])] if ja is not None else []) + \
                  ([" ".join(R.w[max(0, jb - L):jb])] if jb is not None else [])
            if any(x and _sim(run_text, x) >= 0.5 for x in win):
                continue
            out.append((s, e))
            continue
        long = [w for w in P[s:e] if len(w) >= 3]
        if long and sum(R.loose(w) for w in long) >= 0.7 * len(long):
            continue
        out.append((s, e))
    return out


def repeated_words(P: list[str], R: list[str], n: int = 4) -> set:
    rc = defaultdict(int)
    for j in range(len(R) - n + 1):
        rc[tuple(R[j:j + n])] += 1
    # a word occurrence is excess once the reader has used the word more often than the reference has it (so a
    # header printed twice, or a table the reference reads in another cell order, is not a repetition)
    wc, have, excess = defaultdict(int), defaultdict(int), []
    for w in R:
        wc[w] += 1
    for w in P:
        have[w] += 1
        excess.append(have[w] > wc[w])
    seen, rep = defaultdict(int), set()
    for i in range(len(P) - n + 1):
        g = tuple(P[i:i + n])
        seen[g] += 1
        if seen[g] > max(1, rc.get(g, 0)) and sum(excess[i:i + n]) >= n - 1:
            rep.update(range(i, i + n))
    return rep


def concordance(seq: list[int]) -> tuple[int, int]:
    """(concordant pairs, pairs) of a sequence, ties left out; merge sort inversion count."""
    def sort(a):
        if len(a) <= 1:
            return a, 0
        m = len(a) // 2
        l, x = sort(a[:m])
        r, y = sort(a[m:])
        out, i, j, inv = [], 0, 0, x + y
        while i < len(l) and j < len(r):
            if r[j] < l[i]:
                inv += len(l) - i
                out.append(r[j]); j += 1
            else:
                out.append(l[i]); i += 1
        out += l[i:] + r[j:]
        return out, inv
    n = len(seq)
    if n < 2:
        return 0, 0
    _, inv = sort(list(seq))
    from collections import Counter
    ties = sum(c * (c - 1) // 2 for c in Counter(seq).values())
    pairs = n * (n - 1) // 2 - ties
    return pairs - inv, pairs


def marks(w: str) -> tuple[str, list[frozenset]]:
    base, ms = "", []
    for ch in w:
        if HARAKAT.match(ch):
            if ms:
                ms[-1] = ms[-1] | {ch}
        else:
            base += ch
            ms.append(frozenset())
    return base, ms


def _boxes_hit(box, kboxes) -> bool:
    for k in kboxes:
        ix = max(0.0, min(box[2], k[2]) - max(box[0], k[0]))
        iy = max(0.0, min(box[3], k[3]) - max(box[1], k[1]))
        a = (k[2] - k[0]) * (k[3] - k[1])
        if a > 0 and ix * iy / a >= 0.5:
            return True
    return False


# ---------------------------------------------------------------- one page, one reader

def page_eval(job) -> dict | None:
    reader, pid, sset = job
    pf = PRED / reader / f"{pid}.json"
    pred = jload(pf) if pf.exists() else {"lines": [], "meta": {"status": "missing"}}
    klf = PRED / f"{reader}.kl" / f"{pid}.json"
    predkl = jload(klf) if klf.exists() else None
    meta = pred.get("meta", {})
    kr = jload(OUT / "kraken" / f"{pid}.json")
    klines = [ln for ln in kr["lines"] if (ln.get("text") or "").strip()]
    az = jload(OUT / "ref" / "azure" / f"{pid}.json")
    # the reference
    if sset == "gold":
        g = load(GOLD / f"{pid}.json")
        every = gold_lines(g)
        ref_lines = [ln["text"] for ln in every if ln.get("kind", "text") != "equation"]
        ref_kinds = [ln.get("kind", "text") for ln in every if ln.get("kind", "text") != "equation"]
        pool_extra = [ln["text"] for ln in every if ln.get("kind") == "equation"]
        gref, p_s, kl_s = g, pred, predkl
    elif sset == "bd":
        t = jload(OUT / "ref" / "bdtruth" / f"{pid}.json")
        ref_lines = [ln["text"].translate(DIG) for ln in t["lines"]]
        ref_kinds = [ln.get("kind", "text") for ln in t["lines"]]
        pool_extra = []
        gref = pseudo_gold(pid, digits_folded(t)["lines"], t.get("tables", []), t.get("equations", []))
        p_s = digits_folded(pred)
        kl_s = digits_folded(predkl) if predkl else None
    else:
        ref_lines = [ln["text"] for ln in az["lines"]]
        ref_kinds = [ln.get("kind", "text") for ln in az["lines"]]
        pool_extra = []
        tb, eq = drafts_of(pid)
        gref = pseudo_gold(pid, az["lines"], tb, eq)
        p_s, kl_s = pred, predkl
    row = dict(reader=reader, page_id=pid, set=sset, stem=MAN[pid]["stem"])
    sp = score_page(gref, p_s)
    for k in ("faithful.char_err", "faithful.chars", "faithful.word_err", "faithful.words", "folded.char_err",
              "folded.chars", "folded.word_err", "folded.words", "faithful.line_err", "gold_lines", "pred_lines",
              "inserted", "dropped", "repeated", "order_ok", "order_pairs"):
        row[k] = sp.get(k, 0)
    if kl_s is not None:
        sk = score_page(gref, kl_s)
        for k in ("faithful.line_err", "inserted", "dropped", "repeated", "order_ok", "order_pairs", "pred_lines"):
            row[k] = sk.get(k, 0)
        row["line_source"] = "kl"
    has_t, has_e = meta.get("has_tables", False), meta.get("has_equations", False)
    if has_t and sp["teds"]:
        row["teds_sum"], row["teds_n"] = sum(sp["teds"]), len(sp["teds"])
    if has_e and sp["eq"]:
        row["eq_sum"], row["eq_n"] = sum(v for v, _ in sp["eq"]), len(sp["eq"])
        row["eq_exact"] = sum(1 for _, x in sp["eq"] if x)
    # words
    plines = [ln["text"] if sset != "bd" else ln["text"].translate(DIG) for ln in pred.get("lines", [])
              if (ln.get("text") or "").strip()]
    pblock = [ln.get("box") for ln in pred.get("lines", []) if (ln.get("text") or "").strip()]
    psynth = [bool(ln.get("synth")) for ln in pred.get("lines", []) if (ln.get("text") or "").strip()]
    PT, RT = tokens(plines), tokens(ref_lines)
    P, Rw = [t[0] for t in PT], [t[0] for t in RT]
    R = Ref(RT)
    Rpool = Ref(RT + tokens(pool_extra)) if pool_extra else R
    anc = anchors(P, Rpool)
    rep = repeated_words(P, Rw)
    inv = unexplained(P, anc, Rpool, skip=rep)
    inv_w = {i for s, e in inv for i in range(s, e)}
    if sset == "bd":      # the text layer can miss text (a running head in an image): Azure AND Kraken both reading it
        others = {}       # puts it on the page
        for nm, lines in (("azure", [ln["text"] for ln in az["lines"]]), ("kraken", [ln["text"] for ln in klines])):
            X = Ref(tokens([t.translate(DIG) for t in lines]))
            others[nm] = {i for s, e in unexplained(P, anchors(P, X), X, skip=rep) for i in range(s, e)}
        inv_w = inv_w & (others["azure"] | others["kraken"])
        inv = [r for r in runs([i in inv_w for i in range(len(P))])]
    if sset == "ys_azure" and reader != "kraken":       # also unexplained by Kraken's reading of the page
        K = Ref(tokens([ln["text"] for ln in klines]))
        ancK = anchors(P, K)
        invK = {i for s, e in unexplained(P, ancK, K, skip=rep) for i in range(s, e)}
        inv_label = inv_w                                  # Azure-only: the checker's label
        inv_w = inv_w & invK
        inv = [r for r in runs([i in inv_w for i in range(len(P))])]
    else:
        inv_label = inv_w
    Ptok = Ref(PT)
    ancR = anchors(Rw, Ptok)
    drp = unexplained(Rw, ancR, Ptok)
    drp_w = {j for s, e in drp for j in range(s, e)}
    row.update(ref_words=len(Rw), pred_words=len(P), invented=len(inv_w), invented_runs=len(inv),
               invented_label=len(inv_label), dropped_w=len(drp_w), dropped_runs=len(drp), repeated_w=len(rep),
               dropped_w_furniture=sum(1 for j in drp_w if ref_kinds[RT[j][2]] == "furniture"),
               dropped_w_cell=sum(1 for j in drp_w if ref_kinds[RT[j][2]] == "cell"),
               inv_page=int(bool(inv_w)), drop_page=int(bool(drp_w)), rep_page=int(len(rep) >= 4))
    run_away = bool(meta.get("hit_cap")) or meta.get("status") not in (None, "ok") or len(P) > 2 * len(Rw) + 50
    row["runaway"] = int(run_away)
    row["hit_cap"] = int(bool(meta.get("hit_cap")))
    row["examples"] = dict(invented=[" ".join(t[1] for t in PT[s:e])[:200] for s, e in inv[:3]],
                           dropped=[" ".join(t[1] for t in RT[s:e])[:200] for s, e in drp[:3]])
    # word order
    seq = [a for a in anchors(P, R) if a >= 0]
    c, n = concordance(seq)
    row["word_order_ok"], row["word_order_pairs"] = c, n
    # vowel marks
    ancR0 = anchors(P, R)
    tp = fp = fn = 0
    for i, j in enumerate(ancR0):
        if j < 0:
            continue
        bp, mp = marks(PT[i][1])
        br, mr = marks(RT[j][1])
        if bp != br:
            continue
        for a, b in zip(mp, mr):
            tp += len(a & b); fp += len(a - b); fn += len(b - a)
    row["mark_tp"], row["mark_fp"], row["mark_fn"] = tp, fp, fn
    # Kraken as checker
    if reader != "kraken":
        K = Ref(tokens([ln["text"] for ln in klines]))
        ancK = anchors(P, K)
        flag = {i for s, e in unexplained(P, ancK, K, skip=rep) for i in range(s, e)}
        kboxes = [ln["box"] for ln in kr["lines"] if ln.get("box")]
        if meta.get("has_boxes") and reader != "azure":
            li_of = [t[2] for t in PT]
            bad_line = {li for li, b in enumerate(pblock) if b and not _boxes_hit(b, kboxes)}
            flag |= {i for i, li in enumerate(li_of) if li in bad_line}
        if any(psynth):     # the calibration reader: its inserted lines are known inventions
            sw = {i for i, t in enumerate(PT) if psynth[t[2]]}
            row.update(synth_w=len(sw), synth_found=len(sw & inv_label), synth_found_pool=len(sw & inv_w),
                       synth_flagged=len(sw & flag), synth_other_label=len(inv_label - sw))
        row["chk_flag"] = len(flag)
        row["chk_tp"] = len(flag & inv_label)
        row["chk_label"] = len(inv_label)
        row["chk_flag_page"] = int(bool(flag))
        row["chk_label_page"] = int(bool(inv_label))
        row["chk_both_page"] = int(bool(flag) and bool(inv_label))
        # dropped: Kraken words with no counterpart in the reader
        KT = K.toks
        Kw = [t[0] for t in KT]
        ancKP = anchors(Kw, Ptok)
        kd = unexplained(Kw, ancKP, Ptok)
        ancKR = anchors(Kw, R)
        dtp_runs, covered = 0, set()
        for s, e in kd:
            js = [ancKR[k] for k in range(s, e) if ancKR[k] >= 0]
            if not js:
                continue
            if sum(j in drp_w for j in js) >= 0.5 * len(js):
                dtp_runs += 1
                covered.update(j for j in range(min(js), max(js) + 1) if j in drp_w)
        row["chkd_runs"], row["chkd_tp_runs"] = len(kd), dtp_runs
        row["chkd_label"], row["chkd_caught"] = len(drp_w), len(covered)
    return row


# ---------------------------------------------------------------- summing and bootstrap

RATIOS = {
    "faithful.cer": ("faithful.char_err", "faithful.chars"), "faithful.wer": ("faithful.word_err", "faithful.words"),
    "folded.cer": ("folded.char_err", "folded.chars"), "folded.wer": ("folded.word_err", "folded.words"),
    "line_cer": ("faithful.line_err", "faithful.chars"),
    "inserted_lines_per_1000": ("inserted", "gold_lines", 1000), "dropped_lines_per_1000": ("dropped", "gold_lines", 1000),
    "repeated_lines_per_1000": ("repeated", "gold_lines", 1000), "line_order": ("order_ok", "order_pairs"),
    "word_order": ("word_order_ok", "word_order_pairs"),
    "invented_per_1000w": ("invented", "ref_words", 1000), "dropped_per_1000w": ("dropped_w", "ref_words", 1000),
    "repeated_per_1000w": ("repeated_w", "ref_words", 1000),
    "dropped_furniture_per_1000w": ("dropped_w_furniture", "ref_words", 1000),
    "dropped_cell_per_1000w": ("dropped_w_cell", "ref_words", 1000),
    "pages_inventing": ("inv_page", "_pages"), "pages_dropping": ("drop_page", "_pages"),
    "pages_repeating": ("rep_page", "_pages"), "pages_runaway": ("runaway", "_pages"), "pages_hit_cap": ("hit_cap", "_pages"),
    "mark_precision": ("mark_tp", "_mark_p"), "mark_recall": ("mark_tp", "_mark_r"),
    "teds": ("teds_sum", "teds_n"), "eq_sim": ("eq_sum", "eq_n"), "eq_exact": ("eq_exact", "eq_n"),
    "checker_precision": ("chk_tp", "chk_flag"), "checker_recall": ("chk_tp", "chk_label"),
    "checker_flag_rate_per_1000w": ("chk_flag", "ref_words", 1000),
    "checker_page_recall": ("chk_both_page", "chk_label_page"), "checker_page_precision": ("chk_both_page", "chk_flag_page"),
    "synth_label_recall": ("synth_found", "synth_w"), "synth_label_recall_pool": ("synth_found_pool", "synth_w"),
    "synth_checker_recall": ("synth_flagged", "synth_w"),
    "checker_drop_run_precision": ("chkd_tp_runs", "chkd_runs"), "checker_drop_recall": ("chkd_caught", "chkd_label"),
}
CI = ("faithful.cer", "folded.cer", "faithful.wer", "line_cer", "word_order", "invented_per_1000w", "dropped_per_1000w",
      "repeated_per_1000w", "pages_inventing", "pages_runaway", "mark_precision", "mark_recall", "teds", "eq_sim",
      "checker_precision", "checker_recall", "checker_drop_recall")


def _derived(r: dict) -> dict:
    r = dict(r)
    r["_pages"] = 1
    r["_mark_p"] = r.get("mark_tp", 0) + r.get("mark_fp", 0)
    r["_mark_r"] = r.get("mark_tp", 0) + r.get("mark_fn", 0)
    return r


def summarise(rows: list[dict], boot: int) -> dict:
    rows = [_derived(r) for r in rows]
    keys = sorted({v for a in RATIOS.values() for v in a[:2]})
    docs = sorted({r["stem"] for r in rows})
    X = np.zeros((len(docs), len(keys)))
    di = {d: i for i, d in enumerate(docs)}
    for r in rows:
        X[di[r["stem"]]] += [r.get(k, 0) or 0 for k in keys]
    tot = X.sum(axis=0)
    ki = {k: i for i, k in enumerate(keys)}
    o = dict(pages=len(rows), docs=len(docs), ref_words=int(tot[ki["ref_words"]]), ref_marks_compared=int(tot[ki["_mark_r"]]),
             tables_scored=int(tot[ki["teds_n"]]), equations_scored=int(tot[ki["eq_n"]]))
    for m, spec in RATIOS.items():
        a, b = spec[0], spec[1]
        f = spec[2] if len(spec) > 2 else 1
        o[m] = float(f * tot[ki[a]] / tot[ki[b]]) if tot[ki[b]] > 0 else None
    if boot and len(docs) >= 2:
        rng = np.random.default_rng(36)
        S = X[rng.integers(0, len(docs), size=(boot, len(docs)))].sum(axis=1)
        ci = {}
        for m in CI:
            spec = RATIOS[m]
            a, b = spec[0], spec[1]
            f = spec[2] if len(spec) > 2 else 1
            ok = S[:, ki[b]] > 0
            if ok.sum() >= boot // 2 and o[m] is not None:
                v = f * S[ok, ki[a]] / S[ok, ki[b]]
                ci[m] = [round(float(np.percentile(v, 2.5)), 5), round(float(np.percentile(v, 97.5)), 5)]
        o["ci95"] = ci
    return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in o.items()}


def band(dec: str) -> str | None:
    return {"pre-1960": "<=1960s", "1960s": "<=1960s", "1970s": "1970s-80s", "1980s": "1970s-80s",
            "1990s": "1990s-2000s", "2000s": "1990s-2000s", "2010s": "2010s-20s", "2020s": "2010s-20s"}.get(dec)


def strata(pid: str) -> list[str]:
    p = MAN[pid]
    t = set(p.get("tags", []))
    out = ["all", f"split:{p['split']}"]
    if band(p.get("decade", "")):
        out.append(f"decade:{band(p['decade'])}")
    if t & {"vowelled", "quran"}:
        out.append("vowelled_quran")
    if "table" in t:
        out.append("table")
    if "equation" in t:
        out.append("equation")
    if t & {"columns", "magazine"} or (p.get("ncols") or 1) > 1:
        out.append("multicolumn")
    if "footnotes" in t:
        out.append("footnotes")
    if t & {"latin", "mixed_latin"}:
        out.append("latin")
    return out


# ---------------------------------------------------------------- speed and cost

def speed() -> dict:
    dph = None
    f = OUT / "gpu_spend.jsonl"
    if f.exists():
        ev = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        rates = [e["dph"] for e in ev if e.get("dph")]
        dph = rates[-1] if rates else None
    out = {}
    for d in sorted((OUT / "raw").glob("*/run.json")) if (OUT / "raw").exists() else []:
        r = jload(d)
        pph = r.get("pages_per_hour")
        out[r.get("tag", d.parent.name)] = dict(
            pages_ok=r.get("pages_ok"), pages_per_hour=pph, mean_s_per_page=r.get("mean_s_per_page"),
            hit_cap=r.get("hit_cap"), completion_tokens=r.get("completion_tokens"), gpu=r.get("gpu"),
            concurrency=r.get("concurrency"), gpu_usd_per_hour=dph,
            hours_per_1000_pages=round(1000 / pph, 2) if pph else None,
            usd_per_1000_pages=round(1000 / pph * dph, 2) if pph and dph else None)
    return dict(models=out, note="pages_per_hour from each run.json (wall time over all sessions, at the run's "
                                 "concurrency); $/h = the rented GPU's last logged rate (out/gpu_spend.jsonl).")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--readers", default="")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    readers = [r for r in a.readers.split(",") if r] or sorted(
        d.name for d in PRED.iterdir() if d.is_dir() and not d.name.endswith(".kl"))
    gd = gold_done()
    sets = {"gold": sorted(gd), "bd": sorted(p["page_id"] for p in MANIFEST if p["kind"] == "born-digital"),
            "ys_azure": sorted(p["page_id"] for p in MANIFEST if p["kind"] == "yardstick")}
    jobs = [(r, pid, s) for r in readers for s, pids in sets.items() for pid in pids
            if not (r == "azure" and s == "ys_azure")]
    with Pool(a.workers) as pool:
        rows = [r for r in pool.imap_unordered(page_eval, jobs, chunksize=4) if r]
    with open(OUT / "eval_pages.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(rows, key=lambda r: (r["reader"], r["set"], r["page_id"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    res = dict(about=__doc__.split("\n\n")[0], sets={k: len(v) for k, v in sets.items()},
               gold_pages=sets["gold"], labels={"gold": "accuracy vs the owner's gold (Azure flattered: gold was "
                                                          "corrected from Azure's draft)",
                                                "bd": "accuracy vs born-digital text layer (digits folded)",
                                                "ys_azure": "AGREEMENT WITH AZURE, not accuracy; tables/equations vs "
                                                            "gemini-3.1-pro drafts"},
               results={}, speed=speed())
    groups = defaultdict(list)
    for r in rows:
        for st in strata(r["page_id"]):
            groups[(r["set"], r["reader"], st)].append(r)
    for (s, rd, st), rs in sorted(groups.items()):
        res["results"].setdefault(s, {}).setdefault(rd, {})[st] = summarise(rs, a.boot)
    # the CLI's own report per reader on the gold pages (same function as the rows above; kept for the record)
    import subprocess
    (OUT / "score").mkdir(exist_ok=True)
    for rd in readers:
        for d in (PRED / rd, PRED / f"{rd}.kl"):
            if d.exists() and sets["gold"]:
                subprocess.run(["/home/yassine/inkscript/.venv/bin/inkscript", "score", "--gold", str(GOLD), "--pred",
                                str(d), "--name", d.name, "--out", str(OUT / "score" / f"{d.name}.json")],
                               check=False, stdout=subprocess.DEVNULL)
    res["gold_cli_reports"] = str(OUT / "score")
    (OUT / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in res["results"]:
        for rd, v in res["results"][s].items():
            x = v["all"]
            print(f"{s:9} {rd:22} p{x['pages']:4} cer {x['faithful.cer']} fold {x['folded.cer']} wer {x['faithful.wer']}"
                  f" inv/kw {x['invented_per_1000w']} drop/kw {x['dropped_per_1000w']} rep/kw {x['repeated_per_1000w']}"
                  f" order {x['word_order']} chk P {x['checker_precision']} R {x['checker_recall']}", flush=True)


if __name__ == "__main__":
    main()
