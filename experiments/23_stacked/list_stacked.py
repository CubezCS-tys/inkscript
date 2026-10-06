"""List the words of a built PDF that hold stacked letters (stackrule), with the stacked letters' positions.
    ../../.venv/bin/python list_stacked.py PDF [PAGE]"""
import sys
from pathlib import Path
import fitz
sys.path.insert(0, str(Path(__file__).resolve().parent))
import glyphs as G, stackrule as SR, post


def stacked_words(doc, pno):
    gl = G.glyphs(doc, pno); by = {}; out = []
    for g in gl: by.setdefault(g["font"], []).append(g)
    for fname, run in by.items():
        wids = post.words_of(run)
        gs = [dict(word=w, text=g["text"], paths=g["paths"], d1=g["d1"], x0=g["origin"][0], k=0.0576) for g, w in zip(run, wids)]
        st = SR.stacked(gs)
        for w in sorted(set(wids)):
            idx = [i for i, x in enumerate(wids) if x == w]
            if any(i in st for i in idx):
                text = "".join(run[i]["text"] for i in idx)[::-1]
                ks = [len(idx) - idx.index(i) for i in idx if i in st]
                out.append((text, sorted(ks), fname))
    return out


if __name__ == "__main__":
    doc = fitz.open(sys.argv[1])
    for p in ([int(sys.argv[2])] if len(sys.argv) > 2 else range(1, len(doc) + 1)):
        for t, ks, f in stacked_words(doc, p): print(p, t, ks, f)
