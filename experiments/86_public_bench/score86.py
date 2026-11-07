"""Experiment 86, step 4: score every reader on every subset.

    out/venv/bin/python score86.py [READERS...]   -> out/scores86.json, out/scores86.txt

Three measures, all corpus-level (total edits / total reference characters or words, as torchmetrics computes):
  official  KITAB-Bench's own ocr-eval/metrics.py: preprocess_arabic_text (copied verbatim below: newlines/tabs ->
            space, tashkeel removed, أإآٱ->ا, ة->ه, ى->ي, tatweel removed, spaces collapsed), then CER and WER.
            Punctuation, digits and Latin stay.  The published tables print this as a fraction with 2 decimals.
  strict    exp 85's `sform`: exp 77's clean_label with punctuation (Unicode P*/S*) removed; marks, hamza, ى and ة
            kept as printed.  (exp 81's scorer fix: marks stay marks, never turned into spaces.)
  folded    exp 81's folded form: inkscript.gold.text.folded(clean_label(s)): marks dropped, hamza/alef forms, ى->ي,
            ة->ه folded, punctuation ignored.
Per subset also: 95% bootstrap interval of the official CER (items resampled, 1000 draws, seed 86), the share of
lines read exactly (folded), and missing items (no crop: counted as an empty reading).
"""
from __future__ import annotations

import json
import random
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E.parent / "src"))
from common77 import clean_label  # noqa: E402
from inkscript.gold.text import distance, folded  # noqa: E402

D = HERE / "data" / "kitab_img"
OUT = HERE / "out"
PRED = OUT / "pred"
IN_SCOPE = ["patsocr", "synthesizear", "isippt", "ourslines"]
PAGES = ["arabicocr"]   # hindawi: CC BY-NC, skipped and deleted (owner, 2026-11-06)
OUT_SCOPE = ["historyar", "adab", "evarest"]   # khatt, onlinekhatt, muharaf: non-commercial, skipped and deleted
ALL = IN_SCOPE + PAGES + OUT_SCOPE
DIAG = ["ourslines_single"]


# ---- KITAB-Bench ocr-eval/metrics.py preprocess_arabic_text, verbatim
def preprocess_arabic_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = text.replace("\t", " ")
    text = re.sub(r'[ً-ٰٟ]', '', text)
    text = re.sub('[إأٱآا]', 'ا', text)
    text = text.replace('ة', 'ه')
    text = text.replace('ى', 'ي')
    text = re.sub(r'(ـ+)|\s+', lambda m: ' ' if m.group(0).isspace() else '', text).strip()
    text = ' '.join(text.split())
    return text


_WS = re.compile(r"\s+")


def sform(s: str) -> str:
    s = clean_label(s or "")
    s = "".join(" " if (unicodedata.category(c)[0] in "PS" or c == "_") else c for c in s)
    return _WS.sub(" ", s).strip()


def fform(s: str) -> str:
    return _WS.sub(" ", folded(clean_label(s or ""))).strip()


FORMS = {"official": lambda s: preprocess_arabic_text(s or "").strip(), "strict": sform, "folded": fform,
         # diagnostic only (ourslines' references come from a PDF text layer that writes the lam-alef ligature as
         # alef-lam: "ال يقل" for "لا يقل", "االمين" for "الأمين"): the official form with لا and ال made equal on
         # BOTH sides.  Never a headline number.
         "official_lamalef": lambda s: preprocess_arabic_text(s or "").strip().replace("لا", "ال")}


def pairs(reader: str, subset: str):
    """[(item id, reference, reading)] for one subset."""
    rows = [json.loads(l) for l in open(D / f"{subset.split('_')[0]}.jsonl", encoding="utf-8")]
    pf = PRED / f"{reader}_{subset.split('_')[0]}.jsonl"
    if not pf.exists():
        return None
    P = {d["key"]: d["pred"] for d in map(json.loads, open(pf, encoding="utf-8"))}
    out = []
    if subset.startswith("ourslines"):
        for r in rows:
            L = [ln for ln in json.loads(r["gt"]) if ln.get("class") == "line" and (ln.get("text") or "").strip()]
            med = sorted(ln["bbox"]["y2"] - ln["bbox"]["y1"] for ln in L)[len(L) // 2] if L else 0
            for ln in L:
                # diagnostic subset: boxes taller than 1.8x the page's median line box hold several lines
                if subset == "ourslines_single" and ln["bbox"]["y2"] - ln["bbox"]["y1"] > 1.8 * med:
                    continue
                out.append((r["idx"], ln["text"], P.get(f"ourslines_{r['idx']:04d}_{ln['line_index']:03d}")))
    elif subset in PAGES:
        by = defaultdict(list)
        for k, v in P.items():
            _, i, j = k.rsplit("_", 2)
            by[int(i)].append((int(j), v))
        for r in rows:
            got = by.get(r["idx"])
            out.append((r["idx"], r["gt"] or "", " ".join(v for _, v in sorted(got)) if got else None))
    else:
        for r in rows:
            out.append((r["idx"], r["gt"] or "", P.get(f"{subset}_{r['idx']:04d}")))
    return out


def score(prs):
    res = {}
    missing = sum(p is None for _, _, p in prs)
    for name, f in FORMS.items():
        ce = cn = we = wn = exact = 0
        per_item = defaultdict(lambda: [0, 0])
        for it, ref, hyp in prs:
            r, h = f(ref), f(hyp or "")
            e = distance(r, h)
            ce += e
            cn += len(r)
            we += distance(r.split(), h.split())
            wn += len(r.split())
            exact += r == h
            per_item[it][0] += e
            per_item[it][1] += len(r)
        d = dict(cer=ce / max(1, cn), wer=we / max(1, wn), lines_exact=exact / max(1, len(prs)), chars=cn, words=wn)
        if name == "official":
            items = list(per_item.values())
            rng = random.Random(86)
            bs = []
            for _ in range(1000):
                smp = [items[rng.randrange(len(items))] for _ in items]
                bs.append(sum(a for a, _ in smp) / max(1, sum(b for _, b in smp)))
            bs.sort()
            d["ci"] = [bs[25], bs[974]]
        res[name] = d
    res["n"] = len(prs)
    res["missing"] = missing
    return res


def conventions(subset: str):
    """What the references contain that the measures treat differently."""
    rows = [json.loads(l) for l in open(D / f"{subset}.jsonl", encoding="utf-8")]
    refs = []
    for r in rows:
        if subset == "ourslines":
            refs += [ln["text"] for ln in json.loads(r["gt"]) if ln.get("class") == "line"]
        else:
            refs.append(r["gt"] or "")
    s = unicodedata.normalize("NFC", "".join(refs))
    n = max(1, len(s))
    cnt = lambda pat: len(re.findall(pat, s)) / n * 100  # noqa: E731
    return dict(chars=len(s), marks_pct=cnt(r"[ً-ٰٟ]"), western_digits_pct=cnt(r"[0-9]"),
                indic_digits_pct=cnt(r"[٠-٩۰-۹]"), latin_pct=cnt(r"[A-Za-z]"),
                punct_pct=cnt(r"[^\w\s]"))


def main(readers):
    allres = json.loads((OUT / "scores86.json").read_text()) if (OUT / "scores86.json").exists() else {}
    allres.setdefault("conventions", {s: conventions(s) for s in ALL})
    for rd in readers:
        for s in ALL + DIAG:
            prs = pairs(rd, s)
            if prs is None:
                continue
            allres.setdefault(rd, {})[s] = score(prs)
    (OUT / "scores86.json").write_text(json.dumps(allres, indent=1, ensure_ascii=False))
    lines = []
    for rd in [k for k in allres if k != "conventions"]:
        lines.append(f"== {rd}")
        for s, d in allres[rd].items():
            o = d["official"]
            lines.append(f"{s:14s} n={d['n']:5d} miss={d['missing']:3d}  official CER {o['cer']:.4f} "
                         f"[{o['ci'][0]:.4f}-{o['ci'][1]:.4f}] WER {o['wer']:.4f} | strict CER {d['strict']['cer']*100:.2f}% "
                         f"| folded CER {d['folded']['cer']*100:.2f}% WER {d['folded']['wer']*100:.2f}% exact {d['folded']['lines_exact']*100:.1f}%"
                         f" | lamalef-diag {d['official_lamalef']['cer']:.4f}")
    (OUT / "scores86.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1:] or ["v3", "v6r", "v5"])
