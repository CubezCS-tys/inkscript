"""Choose the gold pages (experiment 34).

    python select_pages.py candidates   -> out/candidates.json  pages for Gemini to look at (classify.py)
    python select_pages.py choose       -> out/selection.json   the ~200 pages, their kinds, split and why

Tags per page, from the features (features.py) confirmed by Gemini's look (classify.py) where a feature alone is
a weak guess:
  table       Gemini says table (candidates: ruled lines or columns of numbers)
  equation    Gemini says equation (candidates: lines of operators and Latin letters)
  footnotes   the build's footnote paragraphs (3+ lines) and Gemini agrees there are footnotes
  quran       12+ words inside a Quran quotation the build matched to the verse (exact, needs no look)
  vowelled    a quarter of the Arabic words carry short vowels, or Gemini says vowelled
  latin       10-70% of words in Latin letters, or Gemini says mixed Latin
  headings    2+ heading/title lines, or a first page (title, authors)
  handwriting / decorative   Gemini says so (or Azure's handwriting style covers 10%+ of the words)
  magazine    the cultural monthlies laid out like newspapers (extra.py), or Gemini counts 3+ columns
  body        none of the above: plain running text
Quotas by primary kind (a page counts for one primary kind, the rarest it has, but carries all its tags);
within a kind pages are taken round-robin over decades, at most one page per document unless a kind runs short
(then two), so the set spans 120+ documents. Seed 34.

Split (held out): by journal (the first four digits of the id), so a typeface seen in tuning is never in the test:
journals are put in dev by a hash of their code until dev holds about a quarter of the pages; the rest is test.
Nothing may be tuned, prompted or trained on a test page, its document, or its journal's issue
(out/heldout.txt lists the documents and journals; heldout() below is the guard to import).
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path("/home/yassine/inkscript/experiments/34_yardstick/out")
QUOTA = dict(table=24, equation=14, handwriting=8, decorative=8, magazine=16, quran=16, vowelled=16, latin=16,
             footnotes=24, headings=22, body=40)
ORDER = ["equation", "handwriting", "decorative", "table", "magazine", "vowelled", "quran", "latin", "footnotes",
         "headings", "body"]                          # rarest first: a page's primary kind is the first it has
MAGAZINES = ("المعرفة", "الموقف الأدبي", "المجلة", "الثقافة", "الأديب", "الآداب")


def heldout(stem: str) -> bool:
    """True when a document must never be used for tuning or training (its journal is in the test split)."""
    f = OUT / "heldout.txt"
    if not f.exists():
        return False
    j = {l.split()[1] for l in f.read_text().splitlines() if l.startswith("journal ")}
    d = {l.split()[1] for l in f.read_text().splitlines() if l.startswith("doc ")}
    return stem in d or stem[:4] in j


def load():
    pool = json.loads((OUT / "pool.json").read_text())
    feats, seen = [], set()
    for f in sorted(OUT.glob("features*.jsonl")):
        for l in f.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                if (r["stem"], r.get("page")) not in seen:
                    seen.add((r["stem"], r.get("page")))
                    feats.append(r)
    feats = [f for f in feats if "error" not in f and f["stem"] in pool]
    return pool, feats


def usable(f) -> bool:
    return f.get("words", 0) >= 40 and abs(f.get("angle", 0)) < 45


def guess(f, pool) -> set:
    t = set()
    if f.get("rules_h", 0) >= 4 and f.get("rules_v", 0) >= 2 or f.get("grid", 0) >= 4:
        t.add("table")
    if f.get("math", 0) >= 2:
        t.add("equation")
    if f.get("footnote_lines", 0) >= 3:
        t.add("footnotes")
    if f.get("quran_words", 0) >= 12:
        t.add("quran")
    if f.get("vowelled", 0) >= 0.25:
        t.add("vowelled")
    if 0.10 <= f.get("latin", 0) <= 0.70:
        t.add("latin")
    if f.get("heading_lines", 0) >= 2 or f["page"] == 1:
        t.add("headings")
    if f.get("hw", 0) >= 0.10:
        t.add("handwriting")
    if pool[f["stem"]].get("journal") in MAGAZINES or f.get("columns", 0) >= 3:
        t.add("magazine")
    return t


def candidates() -> int:
    pool, feats = load()
    rnd = random.Random(34)
    by_tag = defaultdict(list)
    for f in feats:
        if usable(f):
            for t in guess(f, pool) or {"body"}:
                by_tag[t].append(f)
    pick = {}
    caps = dict(table=70, equation=50, handwriting=30, magazine=50, quran=40, vowelled=50, latin=50, footnotes=40,
                headings=50, body=60)
    for t, fs in by_tag.items():
        rnd.shuffle(fs)
        per_doc = Counter()
        n = 0
        for f in fs:
            if n >= caps.get(t, 40) or per_doc[f["stem"]] >= 2:
                continue
            per_doc[f["stem"]] += 1
            pick[(f["stem"], f["page"])] = 1
            n += 1
        print(f"{t:12} {len(fs):5} pages guessed, {n} sent to look at")
    # pre-1970 documents and magazines: every usable page up to 4 a document (rare strata)
    for f in feats:
        p = pool[f["stem"]]
        if usable(f) and (p["decade"] in ("pre-1960", "1960s") or p.get("journal") in MAGAZINES):
            if sum(1 for k in pick if k[0] == f["stem"]) < 4:
                pick[(f["stem"], f["page"])] = 1
    # a random page from every document, so no document is only seen through a guess
    by_doc = defaultdict(list)
    for f in feats:
        if usable(f):
            by_doc[f["stem"]].append(f)
    for s, fs in by_doc.items():
        f = rnd.choice(fs)
        pick[(s, f["page"])] = 1
    c = sorted(pick)
    (OUT / "candidates.json").write_text(json.dumps(c))
    print(len(c), "candidate pages from", len({s for s, _ in c}), "documents")
    return 0


def tags(f, pool, g) -> set:
    t = guess(f, pool)
    if g:
        for k in ("table", "equation", "handwriting"):
            if g.get(k):
                t.add(k)
            else:
                t.discard(k)
        if g.get("decorative"):
            t.add("decorative")
        if "footnotes" in t and not g.get("footnotes"):
            t.discard("footnotes")
        if g.get("vowelled"):
            t.add("vowelled")
        if g.get("mixed_latin") and f.get("latin", 0) >= 0.03:
            t.add("latin")
        if g.get("columns", 1) >= 3:
            t.add("magazine")
        if g.get("page_type") in ("cover_or_ad", "blank_or_image", "index_or_contents"):
            t.add("skip")
    else:
        t -= {"table", "equation", "handwriting"}            # unconfirmed guesses are not tags
    return t


def journal_split(stems: list[str], pages_of: dict, share: float = 0.25) -> dict:
    js = sorted({s[:4] for s in stems}, key=lambda j: hashlib.md5(f"34:{j}".encode()).hexdigest())
    total = sum(pages_of.values())
    dev, n = set(), 0
    for j in js:
        if n >= share * total:
            break
        k = sum(v for s, v in pages_of.items() if s[:4] == j)
        dev.add(j)
        n += k
    return {s: ("dev" if s[:4] in dev else "test") for s in stems}


def choose() -> int:
    pool, feats = load()
    gk = json.loads((OUT / "page_kinds.json").read_text()) if (OUT / "page_kinds.json").exists() else {}
    rnd = random.Random(34)
    rows = []
    for f in feats:
        if not usable(f):
            continue
        pid = f"{f['stem']}_p{f['page']:03d}"
        g = gk.get(pid)
        if g is None:
            continue                                          # only pages Gemini has looked at are chosen
        t = tags(f, pool, g)
        if "skip" in t:
            continue
        t = t or {"body"}
        if "body" in t and len(t) > 1:
            t.discard("body")
        if t == {"headings"} and g.get("body_text") and f["page"] != 1:
            t.add("body")
        prim = next(k for k in ORDER if k in t or (k == "body" and True))
        rows.append(dict(pid=pid, stem=f["stem"], page=f["page"], tags=sorted(t), primary=prim,
                         decade=pool[f["stem"]]["decade"], f=f, g=g))
    chosen, per_doc = [], Counter()
    for rnd_pass in (1, 2):
        for k in ORDER:
            have = sum(1 for r in chosen if r["primary"] == k)
            need = QUOTA[k] - have
            if need <= 0:
                continue
            cand = [r for r in rows if r["primary"] == k and r not in chosen and per_doc[r["stem"]] < rnd_pass]
            by_dec = defaultdict(list)
            for r in cand:
                by_dec[r["decade"]].append(r)
            for v in by_dec.values():
                rnd.shuffle(v)
            decs = sorted(by_dec, key=lambda d: (d != "pre-1960", d != "1960s", d))
            while need > 0 and any(by_dec.values()):
                for d in decs:
                    if need <= 0 or not by_dec[d]:
                        continue
                    r = by_dec[d].pop()
                    if per_doc[r["stem"]] >= rnd_pass:
                        continue
                    chosen.append(r)
                    per_doc[r["stem"]] += 1
                    need -= 1
    pages_of = Counter(r["stem"] for r in chosen)
    split = journal_split(sorted(pages_of), pages_of)
    sel = []
    for r in sorted(chosen, key=lambda r: r["pid"]):
        p = pool[r["stem"]]
        sel.append(dict(page_id=r["pid"], stem=r["stem"], page=r["page"], primary=r["primary"], kinds=r["tags"],
                        decade=r["decade"], year=p["year"], journal=p["journal"], field=p["field"],
                        source=p["source"], split=split[r["stem"]], features=r["f"], gemini_look=r["g"]))
    (OUT / "selection.json").write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")
    test_docs = sorted({s["stem"] for s in sel if s["split"] == "test"})
    test_j = sorted({s[:4] for s in test_docs})
    (OUT / "heldout.txt").write_text("".join(f"journal {j}\n" for j in test_j) + "".join(f"doc {d}\n" for d in test_docs))
    print(len(sel), "pages,", len(pages_of), "documents,", len({s[:4] for s in pages_of}), "journals")
    print("primary:", dict(Counter(s["primary"] for s in sel)))
    print("tags:", dict(Counter(t for s in sel for t in s["kinds"])))
    print("decade:", dict(sorted(Counter(s["decade"] for s in sel).items())))
    print("split:", dict(Counter(s["split"] for s in sel)))
    return 0


if __name__ == "__main__":
    sys.exit(candidates() if sys.argv[1:] == ["candidates"] else choose())
