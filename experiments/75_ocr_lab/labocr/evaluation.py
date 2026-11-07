"""Evaluation: recognition (CER/WER under named Unicode policies), completeness, layout, reading order.

Text convention.  A prediction's page text = its blocks' `raw_text` in its own reading order, joined by newlines; the
truth's = its lines in reading order.  Every policy below is applied to both sides, and every report names the
policy.  Primary = `raw`: nothing is collapsed (hamza forms, ى/ي, ة/ه, digits, diacritics, punctuation, bidi
controls all count); only runs of whitespace become one space.  CER/WER are edit operations / reference length,
unclamped (they can pass 100%); an empty reference gives null with a reason, never 0.

Policies (cumulative from left to right, except `raw` which is the base):
  raw              whitespace runs -> one space; nothing else
  faithful         experiment 34's printed text: NFC, tatweel removed, presentation forms decomposed
  markup_stripped  faithful + emitted markup removed (HTML tags, Markdown #/**/|, LaTeX $^{1}$ -> 1, $…$ unwrapped)
  no_punct         markup_stripped + punctuation removed (exp 41's word measure removes it too)
  folded           search folding (inkscript.gold.text.folded): diacritics, hamza/alef forms, ى->ي, ة->ه,
                   Persian look-alikes, digits to ASCII, punctuation removed, Latin lowercased
"""
from __future__ import annotations

import difflib
import html
import re
import unicodedata
from collections import Counter
from typing import Optional

from rapidfuzz.distance import Levenshtein
from rapidfuzz import fuzz

from .schemas import Block, PagePrediction, TruthPage

_WS = re.compile(r"\s+")


def _faithful(s: str) -> str:
    from inkscript.gold.text import faithful
    return faithful(s)


def _folded(s: str) -> str:
    from inkscript.gold.text import folded
    return folded(s)


_TAG = re.compile(r"<[^>]{0,200}>")
_SUP = re.compile(r"\$\s*\^\s*\{?\s*([^${}]{1,12}?)\s*\}?\s*\$")
_MATH = re.compile(r"\$([^$]{1,200})\$")
_MD = re.compile(r"(^|\s)#{1,6}\s+|\*\*|__|^\s*[-*]\s+|\|", re.M)


def strip_markup(s: str) -> str:
    s = _SUP.sub(r"\1", s)
    s = _MATH.sub(r"\1", s)
    s = re.sub(r"\\(?:text|mathrm|textbf)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\^\{?([0-9٠-٩]{1,3})\}?", r"\1", s)
    s = _TAG.sub(" ", s)
    s = html.unescape(s)
    s = _MD.sub(" ", s)
    return s


_PUNCT = re.compile(r"[^\w\s]|_", re.UNICODE)

POLICIES = {
    "raw": lambda s: _WS.sub(" ", s or "").strip(),
    "faithful": lambda s: _faithful(s),
    "markup_stripped": lambda s: _faithful(strip_markup(s or "")),
    "no_punct": lambda s: _WS.sub(" ", _PUNCT.sub(" ", _faithful(strip_markup(s or "")))).strip(),
    "folded": lambda s: _folded(strip_markup(s or "")),
}
PRIMARY = "raw"


# ------------------------------------------------------------------------------------------------ texts

def ordered_blocks(blocks: list[Block]) -> list[Block]:
    if blocks and all(b.order is not None for b in blocks):
        return sorted(blocks, key=lambda b: b.order)
    return list(blocks)


def text_blocks(blocks: list[Block]) -> list[Block]:
    """Blocks that carry transcription (a table's text is its HTML as emitted; figures carry none)."""
    return [b for b in ordered_blocks(blocks) if b.raw_text and b.raw_text.strip()]


def prediction_text(pred: PagePrediction) -> str:
    return "\n".join(b.raw_text for b in text_blocks(pred.result.blocks))


def truth_text(t: TruthPage) -> str:
    by = {ln.line_id: ln for ln in t.lines}
    return "\n".join(by[i].text for i in t.order)


# ------------------------------------------------------------------------------------------------ recognition

def edit_counts(hyp, ref) -> dict:
    """Levenshtein operations turning ref into hyp, over code points (str) or tokens (list)."""
    ops = Levenshtein.editops(ref, hyp)
    c = Counter(op.tag for op in ops)
    return dict(sub=c.get("replace", 0), dele=c.get("delete", 0), ins=c.get("insert", 0), dist=len(ops))


def rate(hyp, ref) -> dict:
    n = len(ref)
    e = edit_counts(hyp, ref)
    return dict(e, ref_len=n, hyp_len=len(hyp),
                rate=(e["dist"] / n) if n else None, null_reason=None if n else "empty reference")


def bag_error(hyp_words: list[str], ref_words: list[str]) -> dict:
    """Order-free word error (exp 40/41): 1 - F1 of the word multisets."""
    p, r = Counter(hyp_words), Counter(ref_words)
    m = sum((p & r).values())
    tot = sum(p.values()) + sum(r.values())
    return dict(errors=tot - 2 * m, total=tot, rate=(tot - 2 * m) / tot if tot else None)


def recognition(hyp_text: str, ref_text: str) -> dict:
    out = {}
    for name, f in POLICIES.items():
        h, r = f(hyp_text), f(ref_text)
        out[name] = dict(cer=rate(h, r), wer=rate(h.split(), r.split()), bag=bag_error(h.split(), r.split()))
    return out


def word_diff(hyp_text: str, ref_text: str, policy: str = "raw") -> list[dict]:
    """Word-level differences against the truth, for display: equal / replace / delete (missing) / insert (extra)."""
    f = POLICIES[policy]
    h, r = f(hyp_text).split(), f(ref_text).split()
    sm = difflib.SequenceMatcher(None, r, h, autojunk=False)
    return [dict(op=op, truth=" ".join(r[i1:i2]), engine=" ".join(h[j1:j2]))
            for op, i1, i2, j1, j2 in sm.get_opcodes()]


def char_confusions(hyp_text: str, ref_text: str, policy: str = "faithful", top: int = 30) -> list:
    f = POLICIES[policy]
    h, r = f(hyp_text), f(ref_text)
    c = Counter()
    for op in Levenshtein.editops(r, h):
        a = r[op.src_pos] if op.tag in ("replace", "delete") else "∅"
        b = h[op.dest_pos] if op.tag in ("replace", "insert") else "∅"
        c[f"{a}>{b}"] += 1
    return c.most_common(top)


def letter_classes(hyp_text: str, ref_text: str) -> dict:
    classes = {"vowel marks": set("ًٌٍَُِّْٰ"), "hamza forms": set("أإآءئؤ"), "ة": {"ة"}, "ى": {"ى"},
               "Persian ی/ک": {"ی", "ک"}, "Arabic-Indic digits": set("٠١٢٣٤٥٦٧٨٩"), "ASCII digits": set("0123456789"),
               "Latin letters": set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"),
               "bidi controls": set("\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u061c")}
    return {k: dict(truth=sum(ch in v for ch in ref_text), engine=sum(ch in v for ch in hyp_text))
            for k, v in classes.items()}


# ------------------------------------------------------------------------------------------------ completeness

def locate_lines(hyp_text: str, truth: TruthPage, threshold: float = 70.0, policy: str = "markup_stripped") -> dict:
    """Each truth line located in the engine's page text (rapidfuzz partial_ratio_alignment on the policy's text).
    A line scoring >= threshold is `found` at that position; the rest are `missing`.  Method recorded as such."""
    f = POLICIES[policy]
    h = f(hyp_text)
    out = {}
    for ln in truth.lines:
        t = f(ln.text)
        if not t:
            out[ln.line_id] = dict(found=False, score=None, pos=None, reason="empty after policy")
            continue
        if len(t) < 4:
            # very short lines (page numbers, single words) are too ambiguous to locate by fuzzy search
            i = h.find(t)
            out[ln.line_id] = dict(found=i >= 0, score=100.0 if i >= 0 else 0.0, pos=i if i >= 0 else None,
                                   reason="short line: exact search")
            continue
        al = fuzz.partial_ratio_alignment(t, h)
        ok = al is not None and al.score >= threshold
        out[ln.line_id] = dict(found=bool(ok), score=round(al.score, 1) if al else 0.0,
                               pos=al.dest_start if ok else None, reason=None)
    return out


def repetition_flag(text: str, max_k: int = 20, times: int = 3) -> bool:
    """A generation loop: some run of 2..max_k words repeated back to back `times` times or more.  (A phrase the
    page itself prints three times in different places is not a loop.)"""
    w = text.split()
    for k in range(2, max_k + 1):
        for i in range(0, len(w) - k * times + 1):
            if all(w[i:i + k] == w[i + j * k:i + (j + 1) * k] for j in range(1, times)):
                return True
    return False


def completeness(pred: PagePrediction, truth: TruthPage, located: dict) -> dict:
    found = [k for k, v in located.items() if v["found"]]
    txt = prediction_text(pred)
    return dict(truth_lines=len(truth.lines), found=len(found), missing=[k for k, v in located.items() if not v["found"]],
                empty=pred.result.empty, truncated=pred.result.truncated, repetition=repetition_flag(txt),
                method="truth line located in the engine's page text, rapidfuzz partial_ratio_alignment >= 70 "
                       "(markup_stripped policy); lines under 4 characters by exact search")


# ------------------------------------------------------------------------------------------------ layout

COARSE = {"header": "furniture", "footer": "furniture", "page_number": "furniture", "footnote": "footnote"}


def coarse(t: str) -> str:
    return COARSE.get(t, "body")


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def cover(line_box, block_box) -> float:
    """Share of the line's area inside the block."""
    ix = max(0.0, min(line_box[2], block_box[2]) - max(line_box[0], block_box[0]))
    iy = max(0.0, min(line_box[3], block_box[3]) - max(line_box[1], block_box[1]))
    a = (line_box[2] - line_box[0]) * (line_box[3] - line_box[1])
    return ix * iy / a if a > 0 else 0.0


def layout(pred: PagePrediction, truth: TruthPage, thresholds=(0.5, 0.75)) -> dict:
    boxed = [b for b in pred.result.blocks if b.box is not None]
    if not boxed:
        return dict(available=False, reason="the engine gives no boxes; layout is not scored (no boxes invented)")
    regions = truth.regions
    res = dict(available=True, pred_regions=len(boxed), truth_regions=len(regions), by_threshold={})
    for th in thresholds:
        pairs = sorted(((iou(b.box, r.box), i, j) for i, b in enumerate(boxed) for j, r in enumerate(regions)),
                       reverse=True)
        used_p, used_t, matches = set(), set(), []
        for s, i, j in pairs:
            if s < th:
                break
            if i in used_p or j in used_t:
                continue
            used_p.add(i)
            used_t.add(j)
            matches.append((i, j, s))
        typed = sum(1 for i, j, _ in matches if coarse(boxed[i].type) == regions[j].coarse)
        res["by_threshold"][str(th)] = dict(
            matched=len(matches), precision=len(matches) / len(boxed) if boxed else None,
            recall=len(matches) / len(regions) if regions else None,
            class_agree=typed, class_precision=typed / len(boxed) if boxed else None,
            class_recall=typed / len(regions) if regions else None,
            unmatched_pred=[boxed[i].block_id for i in range(len(boxed)) if i not in used_p],
            unmatched_truth=[regions[j].region_id for j in range(len(regions)) if j not in used_t],
            pairs=[dict(pred=boxed[i].block_id, truth=regions[j].region_id, iou=round(s, 3),
                        pred_type=boxed[i].type, truth_type=regions[j].type) for i, j, s in matches])
    # line view (granularity-free): each truth line -> the predicted block covering most of it
    rmap = {r.region_id: r for r in regions}
    lines = []
    for ln in truth.lines:
        if ln.box is None:
            continue
        best = max(((cover(ln.box, b.box), b) for b in boxed), key=lambda x: x[0], default=(0.0, None))
        blk = best[1] if best[0] >= 0.5 else None
        tcoarse = rmap[ln.region].coarse if ln.region in rmap else ("furniture" if ln.kind == "furniture" else "body")
        lines.append(dict(line=ln.line_id, block=blk.block_id if blk else None, covered=round(best[0], 3),
                          pred_coarse=coarse(blk.type) if blk else None, truth_coarse=tcoarse,
                          pred_type=blk.type if blk else None, raw_label=blk.raw_label if blk else None))
    cov = [x for x in lines if x["block"]]
    res["lines"] = dict(total=len(lines), covered=len(cov),
                        coarse_agree=sum(x["pred_coarse"] == x["truth_coarse"] for x in cov),
                        rows=lines, method="a truth line belongs to the predicted block covering >= 50% of its box")
    return res


# ------------------------------------------------------------------------------------------------ reading order

def pairwise(seq_truth: list[str], pos: dict[str, float]) -> dict:
    """Pairwise order accuracy of truth items that have a predicted position (ties not counted as pairs)."""
    items = [x for x in seq_truth if pos.get(x) is not None]
    ok = tot = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = pos[items[i]], pos[items[j]]
            if a == b:
                continue
            tot += 1
            ok += a < b
    n = len(seq_truth)
    all_pairs = n * (n - 1) // 2
    return dict(accuracy=ok / tot if tot else None, pairs=tot, all_pairs=all_pairs,
                pair_coverage=tot / all_pairs if all_pairs else None,
                missing=[x for x in seq_truth if pos.get(x) is None])


def reading_order(pred: PagePrediction, truth: TruthPage, located: dict, lay: dict) -> dict:
    out = {}
    # (a) by text position, for every engine: where each truth line was found in the engine's ordered text
    out["text_position"] = dict(pairwise(truth.order, {k: v["pos"] for k, v in located.items() if v["found"]}),
                                method="truth lines located in the engine's ordered page text (see completeness); "
                                       "pairs of located lines in truth order vs text position")
    # (b) by blocks, for engines with boxes and an order: the order of the block each truth line falls in
    if lay.get("available"):
        bo = {b.block_id: b.order for b in pred.result.blocks}
        if all(v is not None for v in bo.values()):
            pos = {r["line"]: bo[r["block"]] for r in lay["lines"]["rows"] if r["block"]}
            out["block_order"] = dict(pairwise(truth.order, pos),
                                      method="each truth line takes the reading position of the predicted block "
                                             "covering it; lines in the same block are a tie (not counted)")
        else:
            out["block_order"] = dict(accuracy=None, reason="the engine's blocks carry no reading order")
    else:
        out["block_order"] = dict(accuracy=None, reason="no boxes")
    return out


# ------------------------------------------------------------------------------------------------ one page

def evaluate_page(pred: PagePrediction, truth: TruthPage) -> dict:
    hyp, ref = prediction_text(pred), truth_text(truth)
    has_text = any(b.raw_text.strip() for b in pred.result.blocks)
    rec = recognition(hyp, ref) if (has_text or pred.result.status == "succeeded") else None
    located = locate_lines(hyp, truth)
    lay = layout(pred, truth)
    return dict(page_id=pred.page_id, run_id=pred.run_id, engine=pred.engine, variant=pred.variant,
                status=pred.result.status, text_available=has_text,
                recognition=rec if has_text else None,
                recognition_reason=None if has_text else "this output carries no text (layout only, or empty)",
                completeness=completeness(pred, truth, located), located=located, layout=lay,
                reading_order=reading_order(pred, truth, located, lay),
                letter_classes=letter_classes(POLICIES["raw"](hyp), POLICIES["raw"](ref)),
                confusions=char_confusions(hyp, ref) if has_text else [],
                diff=word_diff(hyp, ref, "raw") if has_text else [],
                timing=pred.result.timing.model_dump(), resources=pred.result.resources.model_dump())


def failed_page(page_id: str, run_id: str, engine: str, variant: str, error: Optional[str]) -> dict:
    """A failed page stays in the denominator: recognition counts the whole reference as deleted."""
    return dict(page_id=page_id, run_id=run_id, engine=engine, variant=variant, status="failed", error=error)


def micro(pages: list[dict], truths: dict[str, TruthPage], policy: str = PRIMARY) -> dict:
    """Micro CER/WER over pages; a failed page or a text-less output counts its whole reference as deletions."""
    agg = {"cer": [0, 0], "wer": [0, 0]}
    f = POLICIES[policy]
    for p in pages:
        ref = f(truth_text(truths[p["page_id"]]))
        if p.get("recognition"):
            r = p["recognition"][policy]
            agg["cer"][0] += r["cer"]["dist"]
            agg["wer"][0] += r["wer"]["dist"]
        else:
            agg["cer"][0] += len(ref)
            agg["wer"][0] += len(ref.split())
        agg["cer"][1] += len(ref)
        agg["wer"][1] += len(ref.split())
    return {k: (v[0] / v[1] if v[1] else None) for k, v in agg.items()}
