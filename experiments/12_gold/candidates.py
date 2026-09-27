"""Mark the words that are ALREADY known to be suspect, instead of reading whole pages.

    python candidates.py --limit 120 [--source conflicts|numbers|both] [--review DIR] [--azure DIR]

A first hand-marked page (0005 p2, 2026-09-21) came back 277 words, 0 errors. At an error rate near or under
1%, marking pages in order would need ten thousand words to collect enough errors to classify — so the
taxonomy has to come from a pool that is already enriched for errors:

* **conflicts** — `inkscript check`'s contradictions: the same ink read two different ways somewhere in the
  document, so one of the readings IS wrong. 1,399 over the 227 journals.
* **numbers** — every reading containing a digit, where a mistake costs most and shows least.

Both pools are biased, and the bias is the point to remember when reading the result: a conflict needs the
same ink to occur twice, which favours common words and look-alike confusions, so the look-alike share it
reports is an OVER-estimate of the share among all errors. It bounds the question rather than settling it —
what it can settle is whether the errors a checker could pose a hypothesis about are worth chasing at all.

Candidates are taken round-robin across documents so one long journal cannot fill the sheet.
"""
from __future__ import annotations
import argparse, glob, json, sys
from collections import defaultdict
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import importlib.util
_spec = importlib.util.spec_from_file_location("gold_mark", Path(__file__).parent / "mark.py")
mark = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(mark)


WORTH = re.compile(r"[\u0621-\u064A0-9\u0660-\u0669]")     # an Arabic letter or a digit


def whole_word(s: dict, sig: str) -> bool:
    """Does the signature cover the WHOLE word, or only part of its ink?

    A conflict is "same ink, different text" — but the ink is the word's blob signature, and a word whose
    leading run was not attached to it has a signature of only part of itself. Then two different words match
    on a fragment and the contradiction is an artefact: `وعلى` "conflicts" with `على` because only the `على`
    blob was signed. Measured over the 227-journal review files: 61% of `extension` conflicts are like this,
    against 13% of `substitution` ones. Those rows cannot be judged — the reading and the ink shown are not
    the same word — so they are dropped."""
    from inkscript.text import pieces as text_pieces, MARKS
    txt = (s.get("text") or "").strip()
    if not txt:
        return False
    return len(text_pieces(MARKS.sub("", txt))) <= len(sig.split("+"))


def gather(review: Path, source: str, keep_punct: bool = False, kinds: set | None = None):
    """Every suspect word, tagged with why it is suspect and what else that ink is read as."""
    per_doc = defaultdict(list)
    for f in sorted(glob.glob(f"{review}/*.review.json")):
        stem = Path(f).name[: -len(".review.json")]
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if source in ("conflicts", "both"):
            for c in d.get("conflicts", []):
                if kinds and c.get("kind") not in kinds:
                    continue
                rivals = sorted(c.get("readings", {}), key=lambda k: -c["readings"][k])
                for s in c.get("suspects", []):
                    if not keep_punct and not WORTH.search(s.get("text", "")):
                        continue                              # "،" against "له،" is a click that teaches nothing
                    if not whole_word(s, c.get("sig", "")):
                        continue                              # the signature is only part of this word
                    per_doc[stem].append(dict(s, why=c.get("kind", "contradiction"),
                                              alt=[r for r in rivals if r != s.get("text")][:4]))
        if source in ("numbers", "both"):
            for n in d.get("numbers", []):
                per_doc[stem].append(dict(n, why="a number", alt=[]))
    return per_doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", default=str(Path.home() / "Desktop/OCR_gem_json/output/s3_night/review"))
    ap.add_argument("--azure", default=str(Path.home() / "Desktop/OCR_gem_json/output/s3_night/azure"))
    ap.add_argument("--source", default="conflicts", choices=["conflicts", "numbers", "both"])
    ap.add_argument("--limit", type=int, default=120)
    ap.add_argument("--pad", type=int, default=8)
    ap.add_argument("--keep-punct", action="store_true", help="keep suspects that are punctuation only")
    ap.add_argument("--kinds", default="substitution",
                    help="conflict kinds to draw from, comma separated, or 'all'. Default substitution: 61% of "
                         "`extension` conflicts are a signature covering only part of a word, not a real error.")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    kinds = None if a.kinds == "all" else set(a.kinds.split(","))
    per_doc = gather(Path(a.review), a.source, a.keep_punct, kinds)
    if not per_doc:
        sys.exit(f"no candidates in {a.review}")
    # round robin: one from each document in turn, so a single long journal cannot fill the sheet
    order = sorted(per_doc); picked = []
    while len(picked) < a.limit and any(per_doc[s] for s in order):
        for s in order:
            if per_doc[s] and len(picked) < a.limit:
                picked.append((s, per_doc[s].pop(0)))

    by_page = defaultdict(list)
    for stem, w in picked:
        by_page[(stem, w["page"], w.get("rot", 0))].append(w)

    rows = []; skipped_narrow = 0
    for (stem, pn, rot), ws in sorted(by_page.items()):
        try:
            g = mark.page_image(Path(a.azure), stem, pn, rot)                 # one render per page, then freed
            aw, _, (W_in, H_in) = mark.azure_page(Path(a.azure), stem, pn)
        except SystemExit:
            continue
        H, W = g.shape
        # Crop the whole WORD, not the box the signature happened to match: a suspect box can cover one blob
        # of a two-run word, and then the crop shows `على` beside a reading of `وعلى` and cannot be judged.
        sx, sy = W / W_in, H / H_in
        boxes = []
        for q in aw:
            bx0, by0, bx1, by1 = q.pop("_box")
            boxes.append((int(bx0 * sx), int(by0 * sy), int(bx1 * sx), int(by1 * sy)))

        def plausible(b, text):
            """Is this box wide enough to hold this reading? The repo's own rule for a piece of ink
            (pdf-writing-rules.md, "Pieces"): 0.12-1.4 line heights per letter. Azure boxed the number `١٩`
            with 14 px of width and 85 px of height — the box covers the `١` only — and the sheet then showed
            one digit beside a two-digit reading, which cannot be judged."""
            x0, y0, x1, y1 = b
            n = len(re.sub(r"\s", "", text or ""))
            h = max(1, y1 - y0)
            return n == 0 or (x1 - x0) / h / n >= 0.12

        def widen(b):
            """The Azure word box that overlaps this suspect box most, if it contains more of it."""
            x0, y0, x1, y1 = b; best = None; area = 0
            for c in boxes:
                ox = min(x1, c[2]) - max(x0, c[0]); oy = min(y1, c[3]) - max(y0, c[1])
                if ox > 0 and oy > 0 and ox * oy > area:
                    area = ox * oy; best = c
            return best if best and area > 0.5 * max(1, (x1 - x0) * (y1 - y0)) else b

        for w in ws:
            box = widen(w["box"])
            if not plausible(box, w.get("text", "")):
                skipped_narrow += 1
                continue                                      # the box cannot hold the reading; not judgeable
            x0, y0, x1, y1 = box
            x0, y0 = max(0, x0 - a.pad), max(0, y0 - a.pad); x1, y1 = min(W, x1 + a.pad), min(H, y1 + a.pad)
            if x1 <= x0 or y1 <= y0:
                continue
            rows.append(dict(i=len(rows), text=w.get("text", ""), box=w["box"], stem=stem, page=pn,
                             src=f"{stem} · p{pn}", why=w.get("why", ""), alt=w.get("alt", []),
                             img=mark.png(g[y0:y1, x0:x1])))
        del g

    out = Path(a.out) if a.out else Path(__file__).parent / "out" / f"candidates_{a.source}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    tpl = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    title = f"suspect words · {a.source} · {len(rows)} of {sum(len(v) for v in per_doc.values()) + len(picked)}"
    html = (tpl.replace("__DATA__", json.dumps(dict(stem=f"candidates-{a.source}", page=0, dpi=mark.DPI, rot=0,
                                                    classes=[dict(id=c, label=l, key=k, hint=h) for c, l, k, h in mark.CLASSES],
                                                    words=rows), ensure_ascii=False))
                .replace("__OVERVIEW__", "")
                .replace("__TITLE__", title))
    # there is no one page to show: these words come from many documents
    html = html.replace('<details>', '<details hidden>')
    out.write_text(html, encoding="utf-8")
    print(f"{len(rows)} suspect words from {len({r['stem'] for r in rows})} documents -> {out.resolve()}")
    if skipped_narrow:
        print(f"  ({skipped_narrow} dropped: the box is too narrow to hold its reading — an Azure boxing error, not a reading one)")
    print(f"  serve it:  python3 -m http.server 8731 --bind 127.0.0.1 --directory {out.parent.resolve()}\n"
          f"  then open: http://127.0.0.1:8731/{out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
