"""Experiment 87, stage 2: the planted-error readings.

For a test line whose reading is right (readers agree; the pool's clean Azure lines), five wrong readings are made,
each the kind of error a reader really makes:
  word_sub   - one word (3+ letters) replaced by a REAL word one edit away (لديها -> لديهما): from a vocabulary of
               the pool's texts and exp 78's corpus (words seen 3+ times), never a held-out text
  letter     - one letter changed to its dot sibling (ب ت ث ن ي, ج ح خ, د ذ, ر ز, س ش, ص ض, ط ظ, ع غ, ف ق, ه ة)
  word_drop  - one word (3+ letters) left out (the ink has a word the reading lacks)
  block_drop - the last 40% of the words left out (a skipped block / column)
  word_add   - a vocabulary word put in between two words (the reading has a word the ink lacks)
plus `orig`, the right reading (a flag on it is a false flag).  Seeded per line key.

    python plant87.py vocab         # out/data/vocab.json
    python plant87.py make SET      # SET = pool | held  -> out/data/plants_<SET>.jsonl
"""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
D = HERE / "out/data"
SIBS = ["بتثني", "جحخ", "دذ", "رز", "سش", "صض", "طظ", "عغ", "فق", "هة"]
SIB = {c: g for g in SIBS for c in g}
AR = re.compile("^[ء-ي]+$")
LET = "ابتثجحخدذرزسشصضطظعغفقكلمنهوية"


def vocab():
    C = Counter()
    for l in open(D / "pool.jsonl", encoding="utf-8"):
        C.update(w for w in json.loads(l)["text"].split() if AR.match(w))
    with gzip.open(E / "78_synthetic_lines/out/text/text78.jsonl.gz", "rt", encoding="utf-8") as f:
        for i, l in enumerate(f):
            C.update(w for w in json.loads(l)["t"].split() if AR.match(w))
            if i > 400000:
                break
    V = {w: n for w, n in C.items() if n >= 3 and 2 <= len(w) <= 12}
    (D / "vocab.json").write_text(json.dumps(V, ensure_ascii=False))
    print(len(V), "words")


def _edits1(w: str):
    out = set()
    for i in range(len(w) + 1):
        for c in LET:
            out.add(w[:i] + c + w[i:])
        if i < len(w):
            out.add(w[:i] + w[i + 1:])
            for c in LET:
                out.add(w[:i] + c + w[i + 1:])
    out.discard(w)
    return out


def variants(text: str, key: str, V: dict):
    rng = random.Random(int(hashlib.md5(key.encode()).hexdigest()[:8], 16))
    ws = text.split()
    out = {"orig": text}
    idx = [i for i, w in enumerate(ws) if AR.match(w) and len(w) >= 3]
    # word_sub
    rng.shuffle(idx)
    for i in idx:
        cand = sorted(x for x in _edits1(ws[i]) if x in V)
        if cand:
            c = rng.choice(cand)
            out["word_sub"] = " ".join(ws[:i] + [c] + ws[i + 1:])
            break
    # letter: a dot sibling
    for i in idx:
        pos = [j for j, ch in enumerate(ws[i]) if ch in SIB]
        if pos:
            j = rng.choice(pos)
            ch = ws[i][j]
            c = rng.choice([x for x in SIB[ch] if x != ch])
            out["letter"] = " ".join(ws[:i] + [ws[i][:j] + c + ws[i][j + 1:]] + ws[i + 1:])
            break
    if idx and len(ws) >= 3:
        i = idx[0]
        out["word_drop"] = " ".join(ws[:i] + ws[i + 1:])
    if len(ws) >= 5:
        k = max(2, int(round(0.4 * len(ws))))
        out["block_drop"] = " ".join(ws[:len(ws) - k])
    if len(ws) >= 2:
        i = rng.randrange(1, len(ws))
        words = [w for w, n in V.items() if 3 <= len(w) <= 6 and n >= 20]
        out["word_add"] = " ".join(ws[:i] + [rng.choice(sorted(words))] + ws[i:])
    return out


def make(which: str):
    V = json.loads((D / "vocab.json").read_text())
    rows = []
    if which == "pool":
        for l in open(D / "pool.jsonl", encoding="utf-8"):
            r = json.loads(l)
            rows.append(dict(key=r["key"], page=f"{r['stem']}_{r['page']}", era=r["era"], text=r["text"]))
    else:
        for l in open(D / "held.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if r["role"] == "fit":
                rows.append(dict(key=r["key"], page=f"{r['stem']}_{r['page']}", era=r["era"], text=r["text"]))
    with open(D / f"plants_{which}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            r["variants"] = variants(r["text"], r["key"], V)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    c = Counter(k for r in rows for k in r["variants"])
    print(which, len(rows), dict(c))


if __name__ == "__main__":
    if sys.argv[1] == "vocab":
        vocab()
    else:
        make(sys.argv[2])
