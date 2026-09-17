"""Gemini's words into Azure's boxes: sequence alignment tolerant of blocks
read in a different order, plus the title-only backstop."""
from __future__ import annotations
import re

from ..text import norm
from .gemini import UNREADABLE

# Shortest run of identical words trusted as the same passage wherever it sits.
# Shorter runs recur by chance ("صلى الله عليه وسلم"); a block that moved is
# hundreds of words, so it clears this easily.
MIN_RUN = 5


# A run this long that did not align exactly ends the trustworthy top of the page.
BAD_RUN = 6


# More stray Gemini words than this in one box also ends it. Azure missing a short
# name fragment beside a title (`مالكـ` for `مالك بن دينار`) leaves 2; verse halves
# piling up leave 4+.
MAX_STRAY = 3


def gemini_tokens(gtext: str) -> list[str]:
    """Gemini's text as match tokens, punctuation riding on the word before.

    Gemini spaces punctuation off (`معجمية :`) where Azure's box holds it
    (`معجمية:`). A lone `:` normalises to "", and as its own token it takes a
    real word's box — pushing the colon onto the title and squeezing the title
    into the next box.
    """
    toks: list[str] = []
    for t in re.split(r"\s+", gtext):
        if not t or t == UNREADABLE:
            continue
        if toks and not norm(t):
            toks[-1] += " " + t
        else:
            toks.append(t)
    return toks


def align_page(p1: list[dict], toks: list[str]
               ) -> tuple[list[list[int]], list[str | None], list[int], dict]:
    """Which Gemini tokens go in which Azure box, tolerant of moved blocks.

    ocr_hybrid.align diffs the two readings front to back, so a block the engines
    read in a different order — a two-column page, a poem read across versus down
    — looks deleted in one place and inserted in another, and every word of it
    loses its box. Both happen on real front pages, and neither engine is the
    one that is always right: Azure reads prose columns in the correct order,
    Gemini reads verse correctly.

    So order is not trusted up front:
      1. Anchor: repeatedly take the longest run of identical words anywhere in
         the two readings (>= MIN_RUN), regardless of where each engine put it.
      2. Fill: every Azure gap left between anchors is diffed, in order, against
         the unplaced Gemini tokens that follow the anchor before it. This is
         where single misread words — the title fixes — are paired up.
      Then 1-2 again over the leftovers, with runs down to 2 words: a poem read
      across by one engine and down by the other leaves verse halves of 3-5
      words unplaced on both sides, which otherwise pile into one box.
      3. Gemini tokens still unplaced ride on the box of the token before them,
         so no text is lost.

    Returns (Gemini token indices per box, "exact"/"interp"/None per box,
    step-3 stray tokens per box, stats).
    Azure boxes holding only punctuation take no part: their punctuation already
    rides on a Gemini word.
    """
    import difflib
    real = [i for i, w in enumerate(p1) if norm(w["text"])]
    a = [norm(p1[i]["text"]) for i in real]
    g = [norm(t) for t in toks]
    n, m = len(a), len(g)
    got: list[list[int]] = [[] for _ in range(n)]
    kind: list[str | None] = [None] * n
    at = [-1] * m                                        # box per gemini token

    def anchor(min_run: int) -> None:
        """Longest identical runs anywhere, longest first. Placed words are
        masked so they cannot rematch."""
        A = [x if kind[i] is None else f"\0a{i}" for i, x in enumerate(a)]
        G = [x if at[j] == -1 else f"\0g{j}" for j, x in enumerate(g)]
        sm = difflib.SequenceMatcher(None, A, G, autojunk=False)
        while True:
            i, j, k = sm.find_longest_match(0, n, 0, m)
            if k < min_run:
                return
            for d in range(k):
                got[i + d], kind[i + d], at[j + d] = [j + d], "exact", i + d
                A[i + d], G[j + d] = f"\0a{i + d}", f"\0g{j + d}"
            sm.set_seqs(A, G)

    def fill(interp: bool = True) -> None:
        """Each Azure gap between anchors, diffed in order against the unplaced
        Gemini tokens that follow the anchor before it."""
        i = 0
        while i < n:
            if kind[i] is not None:
                i += 1
                continue
            s = i
            while i < n and kind[i] is None:
                i += 1
            j0 = got[s - 1][-1] + 1 if s else 0
            j1 = j0
            while j1 < m and at[j1] == -1:
                j1 += 1
            for tag, x1, x2, y1, y2 in difflib.SequenceMatcher(
                    None, a[s:i], g[j0:j1], autojunk=False).get_opcodes():
                na, ng = x2 - x1, y2 - y1
                if tag == "equal":
                    for d in range(na):
                        got[s + x1 + d], kind[s + x1 + d], at[j0 + y1 + d] = [j0 + y1 + d], "exact", s + x1 + d
                elif tag == "replace" and interp:
                    for d in range(min(na, ng)):
                        got[s + x1 + d], kind[s + x1 + d], at[j0 + y1 + d] = [j0 + y1 + d], "interp", s + x1 + d
                    for d in range(na, ng):              # surplus into the last box
                        got[s + x2 - 1].append(j0 + y1 + d)
                        at[j0 + y1 + d] = s + x2 - 1

    # 1-2. whole passages, then exact words between them. Pairing misread words
    # by position waits: done now, it claims verse halves the next pass needs.
    anchor(MIN_RUN)
    fill(interp=False)
    # 1-2 again, over the leftovers only. Verse halves are 3-5 words: too short
    # to anchor page-wide, where a 2-word run recurs by chance, but among words
    # that found no partner the first time, a shared 2-word run is the partner.
    # Measured over 30 front pages: stray words 164 -> 45, exact 93.8% -> 95.4%.
    anchor(2)
    fill()

    # 3. unplaced gemini tokens ride on the box of the token before them
    stray = 0
    strays = [0] * n
    for j in range(m):
        if at[j] != -1:
            continue
        prev = next((at[k] for k in range(j - 1, -1, -1) if at[k] != -1), None)
        box = prev if prev is not None else next((at[k] for k in range(j + 1, m) if at[k] != -1), None)
        if box is None:
            break                                        # nothing placed at all
        got[box].append(j)
        at[j] = box
        stray += 1
        strays[box] += 1

    per_box_got: list[list[int]] = [[] for _ in p1]
    per_box_kind: list[str | None] = [None] * len(p1)
    per_box_stray = [0] * len(p1)
    for r, b in enumerate(real):
        per_box_got[b], per_box_kind[b], per_box_stray[b] = sorted(got[r]), kind[r], strays[r]
    stats = {"exact": kind.count("exact"), "interpolated": kind.count("interp"),
             "azure_only": kind.count(None), "gemini_only": stray, "real_words": n}
    return per_box_got, per_box_kind, per_box_stray, stats


def title_cut(p1: list[dict], got: list[list[int]], kind: list[str | None],
              strays: list[int]) -> int:
    """How many of page 1's boxes, in Azure reading order, form a trustworthy top.

    Trust here is ORDER, not exact agreement. A garbled title is by definition
    not an exact match — Azure's `المغْرَ الكَب الجلد` against Gemini's
    `المَغْرِبُ الكَبِيرُ` — and that is the text this backstop exists to fix. What
    makes its placement safe is that an exact word right after it lands where the
    two readings agree it should, which pins the misread words between two known
    positions, exactly as the in-order fill does anywhere else on the page.

    The top ends at the first exact word out of order (a moved block starting),
    at a run of more than BAD_RUN words with no anchor to close it, or at a box
    holding more than MAX_STRAY stray Gemini words — words that found no box of
    their own piled up there, which is the readings parting ways just as surely.
    Only strays count: a box Azure merged (`{بُوعَلىّاليُوسِى`) rightly holds
    several words.
    """
    last, run, run_start = -1, 0, 0
    for b, w in enumerate(p1):
        if not norm(w["text"]):
            continue
        if strays[b] > MAX_STRAY:
            return run_start if run else b
        if kind[b] == "exact":
            if not (last < got[b][0] <= last + 1 + run + BAD_RUN):
                return run_start if run else b
            last, run = got[b][-1], 0
        else:
            if not run:
                run_start = b
            run += 1
            if run > BAD_RUN:
                return run_start
    return run_start if run else len(p1)


def page1_text(p1: list[dict], gtext: str | None,
               min_exact: float) -> tuple[list[str] | None, dict]:
    """The text for each of page 1's Azure word boxes, or None to keep Azure's.

    The one decision point, shared by build() and the compare viewer so what the
    viewer shows is what the PDF holds. Three outcomes, in `page1`:

      gemini          the page aligns: every box gets Gemini's words
      gemini-title    it does not, but its top does: the title and author boxes
                      get Gemini's words, the rest keep Azure's
      azure-fallback  not even the top aligns: Azure's layer, untouched
    """
    st: dict = {"azure_p1_words": len(p1), "page1": "azure-fallback"}
    if gtext is None:
        st["reason"] = "gemini call failed"
        return None, st
    if not p1:
        st["reason"] = "azure found no words on page 1"
        return None, st
    toks = gemini_tokens(gtext)
    got, kind, strays, a = align_page(p1, toks)
    ratio = a["exact"] / max(1, a["real_words"])
    st.update({"gemini_p1_words": len(toks), **a, "exact_of_azure": round(ratio, 3)})

    def fill(b: int, w: dict, js: list[int]) -> str:
        # Boxes Gemini gave no word keep Azure's — see docstring, point 3 — unless
        # the box is only punctuation: Gemini's copy already rides on a word.
        if js:
            return " ".join(toks[j] for j in js)
        return w["text"] if norm(w["text"]) else ""

    if ratio >= min_exact:
        st["page1"] = "gemini"
        return [fill(b, w, got[b]) for b, w in enumerate(p1)], st

    st["reason"] = f"only {ratio:.0%} of page-1 words aligned (< {min_exact:.0%})"
    cut = title_cut(p1, got, kind, strays)
    top = [b for b in range(cut) if norm(p1[b]["text"])]
    exact_top = sum(1 for b in top if kind[b] == "exact")
    if exact_top < 3:                                    # too little to pin anything
        return None, st
    # Gemini tokens past the last exact word of the top belong to the body.
    gcut = max(got[b][0] for b in top if kind[b] == "exact") + 1
    st.update({"page1": "gemini-title", "title_boxes": cut,
               "title_exact": round(exact_top / len(top), 3)})
    texts = []
    for b, w in enumerate(p1):
        if b < cut:
            js = [j for j in got[b] if j < gcut]
            texts.append(fill(b, w, js) if js or not norm(w["text"]) else w["text"])
        else:
            texts.append(w["text"])                      # Azure's, punctuation and all
    return texts, st
