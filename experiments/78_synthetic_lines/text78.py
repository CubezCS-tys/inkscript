"""Experiment 78, step 1: the text to render.  Our own Azure lines from TRAINING-POOL journals only, plus random
strings, with the rare things the archive needs weighted up.

    .venv/bin/python text78.py [N]     -> out/text/text78.jsonl.gz   (one {"t": text, "src": kind} per line)

Source pages: experiment 77's out/pages77.jsonl (read only), which already leaves out experiment 76's 27 held-out
journal codes; every article is checked again here against split76.json.  No line of a held-out journal, of the
owner's corrected pages or of the lab's documents can enter.

Mixture (by line):
  azure   ~85%: an Azure line (clean_label), as is (60%), cut to a 1-6 word snippet (20%), or two lines joined (20%)
          lines with rare things are drawn more often (weights below); pre-2000 articles twice as often;
          a share is rewritten in the old spelling (final ي -> ى in the words old print spells so, إلى -> الى,
          hamza dropped on initial alef) and a share gets printed vowel marks (shadda, tanween, a few harakat).
  random  ~15%: random letters/words, digits (Arabic-Indic and Latin), punctuation, footnote marks «(1)» «١» «¹»,
          brackets, page numbers, dates, references, Latin words.
"""
from __future__ import annotations

import gzip
import json
import random
import re
import sys
from collections import Counter, defaultdict

from common78 import OUT, OUT77, azure_pages, clean_label, nonempty_lines, pages80, test_codes

SRC80 = "--src80" in sys.argv
NAME = "text80" if SRC80 else "text78"     # all text from the experiment 80 old-print pull -> out/text/text80.jsonl.gz

RARE = [  # (pattern, extra weight)
    (re.compile("لل"), 1.0), (re.compile("ى"), 1.0), (re.compile("ة"), 0.5), (re.compile("[أإآؤئء]"), 1.0),
    (re.compile("[ً-ْٰ]"), 3.0), (re.compile("[0-9٠-٩]"), 1.0), (re.compile("[«»()\\[\\]]"), 1.0),
    (re.compile("[A-Za-z]"), 1.0), (re.compile("[؟!:؛]"), 1.0), (re.compile("ـ"), 0.0)]
AR = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"
ARX = AR + "ةىأإآؤئء"
MARKS = "ًٌٍَُِّْ"
LATIN = ("the of and in to education study analysis journal university research learning students teacher method "
         "results social psychology Vol No pp et al ed Press Cairo Journal of Educational Research SPSS ANOVA "
         "Abstract Keywords International Review Arabic language Ibid op cit The Effect Development Science").split()
PUNCT = list("،.:؛؟!-–()[]«»\"'/*…") + ["..", "...", " - "]


def old_spelling(s: str, rng: random.Random) -> str:
    """Old Egyptian print: final ي printed ى (فى، التى، الذى، يدرى), «الى», hamza often left off initial alef."""
    w = s.split(" ")
    out = []
    for x in w:
        if len(x) > 1 and x.endswith("ي") and rng.random() < 0.8:
            x = x[:-1] + "ى"
        if x in ("إلى", "إلي") and rng.random() < 0.6:
            x = "الى"
        elif x[:1] in "أإ" and rng.random() < 0.25:
            x = "ا" + x[1:]
        out.append(x)
    return " ".join(out)


def add_marks(s: str, rng: random.Random) -> str:
    """Printed vowel marks where old print has them: shadda, tanween on final alef, now and then a haraka."""
    o = []
    for i, c in enumerate(s):
        o.append(c)
        if c in AR and rng.random() < 0.08:
            o.append(rng.choice("ّّّ" + MARKS))
        if c == "ا" and (i + 1 == len(s) or s[i + 1] == " ") and i > 1 and rng.random() < 0.3:
            o[-1:] = ["اً"] if rng.random() < 0.5 else ["ًا"]
    return clean_label("".join(o))


def ar_word(rng, n=None):
    n = n or rng.randint(1, 7)
    return "".join(rng.choice(ARX if k else AR + "أإا") for k in range(n))


def dig(rng, n, ar=None):
    ar = rng.random() < 0.55 if ar is None else ar
    d = "٠١٢٣٤٥٦٧٨٩" if ar else "0123456789"
    return "".join(rng.choice(d) for _ in range(n))


def random_line(rng: random.Random, words: list[str]) -> str:
    k = rng.random()
    ar = rng.random() < 0.55
    if k < 0.18:   # random letters, words, marks
        return " ".join(ar_word(rng) if rng.random() < 0.6 else rng.choice(words) for _ in range(rng.randint(1, 10)))
    if k < 0.36:   # numbers and punctuation
        toks = []
        for _ in range(rng.randint(1, 9)):
            r = rng.random()
            toks.append(dig(rng, rng.randint(1, 5), ar) if r < 0.45 else
                        rng.choice(PUNCT) if r < 0.65 else
                        f"{dig(rng, rng.randint(1, 3), ar)}{rng.choice('.,/:-%')}{dig(rng, rng.randint(1, 3), ar)}" if r < 0.8
                        else rng.choice(words))
        return " ".join(toks)
    if k < 0.56:   # footnote marks and note calls in Arabic text
        n = dig(rng, 1 if rng.random() < 0.8 else 2, ar)
        mark = rng.choice([f"({n})", f"({n})", n, f"[{n}]", "*", f"{n}-", f"{n}."])
        ws = rng.sample(words, min(len(words), rng.randint(2, 9)))
        if rng.random() < 0.5:
            return f"{mark} " + " ".join(ws)
        i = rng.randint(1, len(ws))
        ws[i - 1] = ws[i - 1] + (mark if rng.random() < 0.5 else " " + mark)
        return " ".join(ws)
    if k < 0.68:   # page numbers, dates, references
        return rng.choice([f"- {dig(rng, rng.randint(1, 3), ar)} -", f"{dig(rng, 4, ar)}/{dig(rng, 1, ar)}/{dig(rng, 2, ar)}",
                           f"ص {dig(rng, rng.randint(1, 3), True)} .", f"ص ص {dig(rng, 2, ar)}-{dig(rng, 2, ar)}",
                           f"العدد {dig(rng, rng.randint(1, 3), ar)} ، السنة {dig(rng, 4, ar)}",
                           f"Vol. {dig(rng, 2, False)}, No. {dig(rng, 1, False)}, pp. {dig(rng, 2, False)}-{dig(rng, 3, False)}",
                           f"({dig(rng, 4, ar)})", f"{rng.choice(words)} ({dig(rng, 4, ar)}) :"])
    if k < 0.84:   # Latin words, alone or inside Arabic
        lat = " ".join(rng.choice(LATIN) for _ in range(rng.randint(1, 6)))
        if rng.random() < 0.4:
            return lat
        ws = rng.sample(words, min(len(words), rng.randint(1, 7)))
        ws.insert(rng.randint(0, len(ws)), rng.choice([lat, f"({lat})"]))
        return " ".join(ws)
    # brackets, quotes and mixed
    ws = rng.sample(words, min(len(words), rng.randint(1, 8)))
    a, b = rng.choice([("«", "»"), ("(", ")"), ("[", "]"), ("\"", "\""), ("((", "))"), ("{", "}")])
    i = rng.randint(0, len(ws) - 1)
    j = rng.randint(i, len(ws) - 1)
    ws[i] = a + ws[i]
    ws[j] = ws[j] + b
    return " ".join(ws) + rng.choice(["", " .", "،", ".", " :", "؟"])


def main(n_out: int):
    rng = random.Random(78)
    held = test_codes()
    P = pages80() if SRC80 else [json.loads(l) for l in open(OUT77 / "pages77.jsonl", encoding="utf-8")]
    by = defaultdict(list)
    for p in P:
        assert p["jcode"] not in held
        by[p["stem"]].append(p)
    stems = sorted(by)
    rng.shuffle(stems)
    old = [s for s in stems if str(by[s][0].get("year"))[:4].isdigit() and int(str(by[s][0]["year"])[:4]) < 2000]
    oldset = set(old)
    mod = [s for s in stems if s not in oldset]
    # every old article, and as many modern ones; at most 400 lines an article
    pick = old if SRC80 else old + mod[:len(old)]
    lines, eras = [], []
    for k, s in enumerate(pick):
        p0 = by[s][0]
        try:
            pgs = azure_pages(p0["azure"])
        except Exception:  # noqa: BLE001
            continue
        got = []
        for pg in pgs:
            for ln in nonempty_lines(pg):
                t = clean_label(ln["text"])
                if 2 <= len(t) <= 120:
                    got.append(t)
        rng.shuffle(got)
        for t in got[:400]:
            lines.append(t)
            eras.append(s in oldset)
        if k % 200 == 0:
            print(k, len(pick), len(lines), flush=True)
    words = [w for t in lines[:200000] for w in t.split() if re.fullmatch("[ء-ي]+", w)]
    wts = []
    for t, o in zip(lines, eras):
        w = 1.0 + sum(x for r, x in RARE if r.search(t))
        wts.append(w * (2.0 if o else 1.0))
    print("source lines", len(lines), "old", sum(eras), flush=True)
    src = Counter()
    OUT.joinpath("text").mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / f"text/{NAME}.jsonl.gz", "wt", encoding="utf-8") as f:
        idx = rng.choices(range(len(lines)), weights=wts, k=n_out)
        for i in idx:
            if rng.random() < 0.15:
                t, kind = random_line(rng, words), "random"
            else:
                t, kind = lines[i], "azure"
                r = rng.random()
                if r < 0.2:
                    ws = t.split()
                    a = rng.randint(0, max(0, len(ws) - 1))
                    t, kind = " ".join(ws[a:a + rng.randint(1, 6)]), "snippet"
                elif r < 0.4:
                    t2 = lines[rng.randrange(len(lines))]
                    t, kind = (t + " " + t2)[:rng.randint(60, 140)].rsplit(" ", 1)[0] or t, "joined"
                if re.search("[ء-ي]", t):
                    if rng.random() < (0.35 if eras[i] else 0.15):
                        t, kind = old_spelling(t, rng), kind + "+old"
                    if rng.random() < 0.06:
                        t, kind = add_marks(t, rng), kind + "+marks"
            t = clean_label(t)
            if t:
                f.write(json.dumps(dict(t=t, src=kind), ensure_ascii=False) + "\n")
                src[kind.split("+")[0]] += 1
                src["old_spelling"] += "+old" in kind
                src["marks"] += "+marks" in kind
    chars = Counter()
    with gzip.open(OUT / f"text/{NAME}.jsonl.gz", "rt", encoding="utf-8") as f:
        for l in f:
            chars.update(json.loads(l)["t"])
    (OUT / f"text/{NAME}_stats.json").write_text(json.dumps(dict(source_lines=len(lines), articles=len(pick),
                                                               old_articles=len(old), out=dict(src),
                                                               chars=chars.most_common()), ensure_ascii=False, indent=0))
    print(dict(src))


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(int(args[0]) if args else 1_500_000)
