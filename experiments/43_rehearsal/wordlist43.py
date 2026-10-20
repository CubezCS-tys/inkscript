"""Experiment 43: a word list for telling printed words from Azure's readings of show-through, junk and lost letters.
No model calls.

    wordlist43.py build [--abstracts N]   out/wordlist43.txt: every word seen in >= MIN_DOCS catalogue abstracts / titles
                                          (marc.db, 520 and 245) and in the Azure text of the 355 articles (>= MIN_DOCS
                                          documents), folded (see fold), one per line with its document count (word<TAB>count)
    wordlist43.py check TEXT...           folded form and whether each word is in the list

fold: tashkeel and tatweel out, alef forms -> ا, ى -> ي, ة -> ه, Latin lower-cased, punctuation stripped. A word with a
clitic (و، ف، ب، ل، ك، ال، وال، بال، لل) is also in the list when its stem is (see known()).
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
LIST = OUT / "wordlist43.txt"
MARC = Path.home() / "data" / "marc" / "marc.db"
MIN_DOCS = 3
TASH = re.compile(r"[ً-ْٰـ]")
PUNCT = re.compile(r"^[^\w]+|[^\w]+$")
DIGITS = re.compile(r"^[\d٠-٩.,/\-]+$")
FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"})
PREF = ("وبال", "فبال", "وال", "بال", "فال", "كال", "لل", "ال", "و", "ف", "ب", "ل", "ك", "س")
SUFF = ("هما", "كما", "هم", "هن", "كم", "ها", "نا", "ه", "ك", "ي", "ات", "ون", "ين", "ان")


def fold(t: str) -> str:
    t = TASH.sub("", t or "")
    t = PUNCT.sub("", t)
    return t.translate(FOLD).lower()


def tokens(text: str):
    for t in (text or "").split():
        f = fold(t)
        if f and not DIGITS.match(f):
            yield f


@lru_cache(maxsize=1)
def load() -> dict:
    """word -> number of documents it was seen in (>= MIN_DOCS)."""
    if not LIST.exists():
        return {}
    out = {}
    for ln in LIST.read_text(encoding="utf-8").splitlines():
        w, _, c = ln.partition("\t")
        if w:
            out[w] = int(c or MIN_DOCS)
    return out


def freq(t: str, W=None) -> int:
    """Documents the folded word was seen in (0: never); no clitic stripping."""
    W = load() if W is None else W
    return W.get(fold(t), 0)


def known(t: str, W=None) -> bool | None:
    """True / False for a word; None when it has no letters (digits, marks) or there is no list."""
    W = load() if W is None else W
    f = fold(t)
    if not W or not f or DIGITS.match(f) or not re.search(r"[^\W\d_]", f):
        return None
    if f in W:
        return True
    for p in PREF:
        if f.startswith(p) and len(f) - len(p) >= 2:
            s = f[len(p):]
            if s in W or ("ال" + s) in W:
                return True
            for q in SUFF:
                if s.endswith(q) and len(s) - len(q) >= 2 and s[:-len(q)] in W:
                    return True
    for q in SUFF:
        if f.endswith(q) and len(f) - len(q) >= 2 and f[:-len(q)] in W:
            return True
    return False


def known_share(text: str, W=None) -> tuple[int, int]:
    """(known words, words judged) over a line's words of >= 2 letters."""
    k = n = 0
    for t in text.split():
        if len(re.findall(r"[^\W\d_]", fold(t))) < 2:
            continue
        r = known(t, W)
        if r is None:
            continue
        n += 1
        k += bool(r)
    return k, n


def build(n_abs: int):
    df = Counter()
    con = sqlite3.connect(f"file:{MARC}?mode=ro", uri=True)
    q = "SELECT text FROM abstracts WHERE code IN ('a','b') LIMIT ?"
    for i, (t,) in enumerate(con.execute(q, (n_abs,))):
        df.update(set(tokens(t)))
        if i % 50000 == 0:
            print(f"  abstracts {i}: {len(df)} words", flush=True)
    for i, (t, s) in enumerate(con.execute("SELECT title, subtitle FROM records LIMIT 600000")):
        df.update(set(tokens(f"{t or ''} {s or ''}")))
    print(f"  + titles: {len(df)} words", flush=True)
    # the Azure text of experiment 41's 55 and the 300 (each document counted once)
    sys.path.insert(0, str(HERE))
    import masters43 as M43
    import run43
    from masters43 import ST
    for which in ("a", "b"):
        if which == "b":
            ST.PAGES = OUT / "pages"
        for a in run43.articles(which):
            try:
                az = M43.M.azure_raw(a)
            except Exception:                     # noqa: BLE001
                continue
            seen = set()
            for pg in az.get("pages") or []:
                for L in pg.get("lines") or []:
                    seen.update(tokens(L.get("content", "")))
            df.update(seen)
    W = sorted(w for w, c in df.items() if c >= MIN_DOCS)
    LIST.parent.mkdir(parents=True, exist_ok=True)
    LIST.write_text("\n".join(f"{w}\t{df[w]}" for w in W) + "\n", encoding="utf-8")
    print(f"{len(W)} words (of {len(df)} seen) -> {LIST}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--abstracts", type=int, default=400000)
    c = sub.add_parser("check")
    c.add_argument("text", nargs="+")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.abstracts)
    else:
        for t in " ".join(a.text).split():
            print(t, fold(t), known(t), freq(t))


if __name__ == "__main__":
    main()
