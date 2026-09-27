"""The same documents, two text layers, one reader: our vector PDF against the Azure searchable PDF shipped
with them.

    python compare.py <azure_dir> <ours_dir>

Read with pdfium (Chrome's engine, pinned build 7947). The reference for both layers is what OUR layer placed
— Azure's own reading, since neither build used Gemini here — so the comparison is about how a layer is
READ, not about who recognised the page.

Four things are measured:

* **words intact** — a reference word comes back whole (experiment 07's measure).
* **lines in order** — a line's Arabic words come back contiguous and in reading order.
* **numbers intact** — every Arabic-Indic digit run of the reference, found unreversed. A date read backwards
  (`١٩٨١` copying out as `١٨٩١`) is the error that hurts most and shows least, so it gets its own column.
* **letter selection** — widest character box divided by narrowest INSIDE a word. 1.00 means every character
  of a word was given the same width: the viewer is slicing the word evenly because the layer never knew
  where the letters are (docs/glossary.md, "equal slicing"). Above 1 means the boxes follow the ink.
"""
from __future__ import annotations
import json, re, sys, unicodedata, statistics as st
from pathlib import Path
import pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from inkscript.text import norm, ARABIC_LETTER, _class

N = lambda s: unicodedata.normalize("NFKC", s)
DIGITS = re.compile(r"[0-9٠-٩۰-۹]{2,}")


def edge(t):
    while t and unicodedata.category(t[0])[0] in "PSZ": t = t[1:]
    while t and unicodedata.category(t[-1])[0] in "PSZ": t = t[:-1]
    return t


def key(line):
    return tuple(x for x in (edge(w) for w in N(line).split()) if x and ARABIC_LETTER.search(x))


def latin_majority(text):
    segs = [_class(c) for c in N(text)]
    runs = [d for i, d in enumerate(segs) if i == 0 or segs[i - 1] != d]
    return runs.count("L") > runs.count("R")


def uniformity(doc):
    """Widest char box / narrowest, inside a word. 1.00 = the viewer is slicing words evenly."""
    rs = []
    for pi in range(len(doc)):
        tp = doc[pi].get_textpage(); t = tp.get_text_range()
        b = [tp.get_charbox(i) for i in range(len(t))]
        cur = []
        for i, c in enumerate(t):
            if c.isspace():
                if len(cur) >= 4:
                    w = [b[k][2] - b[k][0] for k in cur]
                    if min(w) > 0.01: rs.append(max(w) / min(w))
                cur = []
            else:
                cur.append(i)
        tp.close()
        if pi > 6: break                                   # a few pages are enough for a ratio
    return (st.median(rs), len(rs)) if rs else (float("nan"), 0)


def measure(pdf, report):
    doc = pdfium.PdfDocument(str(pdf))
    tw = ti = tl = tok = 0; nd = ndok = ndrev = 0
    for pi in report["pages"]:
        if not pi.get("glyphs"):
            continue
        t = re.sub(r"[‎‏‪-‮]", "", N(doc[pi["page"] - 1].get_textpage().get_text_range())).replace("\r\n", "\n")
        got = {edge(x) for x in t.split()}
        want = [x for x in (edge(x) for tt in pi["placed"] for x in N(tt).split() if norm(x)) if x]
        tw += len(want); ti += sum(1 for x in want if x in got)
        lines = [key(l) for l in t.split("\n")]
        for r in pi["runs"]:
            k = key(r)
            if len(k) < 3 or latin_majority(r):
                continue
            tl += 1; n = len(k)
            tok += any(l[i:i + n] == k for l in lines if len(l) >= n for i in range(len(l) - n + 1))
        flat = " ".join(t.split())
        for tt in pi["placed"]:
            for d in DIGITS.findall(N(tt)):
                nd += 1
                if d in flat: ndok += 1
                elif d[::-1] in flat: ndrev += 1
    u, un = uniformity(doc)
    doc.close()
    return dict(words=(ti, tw), lines=(tok, tl), nums=(ndok, nd, ndrev), unif=(u, un))


def main(azure_dir, ours_dir):
    ours = Path(ours_dir); az = Path(azure_dir)
    reps = {r["doc"]: r for r in json.load(open(ours / "native_pdf_report.json"))}
    rows = []
    print(f"{'document':24s} {'layer':10s} {'words intact':>17s} {'lines in order':>17s} {'numbers intact':>17s}  {'letter boxes':>12s}")
    agg = {}
    for stem in sorted(reps):
        r = reps[stem]
        for label, pdf in (("inkscript", ours / f"{stem}_vector.pdf"), ("azure", az / stem / f"{stem}.pdf")):
            if not pdf.exists():
                print(f"{stem:24s} {label:10s} (missing)"); continue
            m = measure(pdf, r)
            a = agg.setdefault(label, dict(w=[0, 0], l=[0, 0], n=[0, 0, 0], u=[]))
            a["w"][0] += m["words"][0]; a["w"][1] += m["words"][1]
            a["l"][0] += m["lines"][0]; a["l"][1] += m["lines"][1]
            a["n"][0] += m["nums"][0]; a["n"][1] += m["nums"][1]; a["n"][2] += m["nums"][2]
            if m["unif"][1]: a["u"].append(m["unif"][0])
            print(f"{stem:24s} {label:10s} {m['words'][0]:>6d}/{m['words'][1]:<5d}{m['words'][0]/max(1,m['words'][1]):6.1%} "
                  f"{m['lines'][0]:>6d}/{m['lines'][1]:<5d}{m['lines'][0]/max(1,m['lines'][1]):6.1%} "
                  f"{m['nums'][0]:>6d}/{m['nums'][1]:<5d}{m['nums'][0]/max(1,m['nums'][1]):6.1%}  {m['unif'][0]:>11.2f}")
            rows.append(dict(stem=stem, layer=label, **{k: list(v) for k, v in m.items()}))
    print()
    for label, a in agg.items():
        print(f"ALL TEN, {label:10s} words {a['w'][0]}/{a['w'][1]} ({a['w'][0]/max(1,a['w'][1]):.1%})   "
              f"lines {a['l'][0]}/{a['l'][1]} ({a['l'][0]/max(1,a['l'][1]):.1%})   "
              f"numbers {a['n'][0]}/{a['n'][1]} ({a['n'][0]/max(1,a['n'][1]):.1%}, {a['n'][2]} reversed)   "
              f"letter boxes {st.median(a['u']):.2f}")
    json.dump(rows, open(ours / "compare_vs_azure.json", "w"), ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
