"""Experiment 103, A1: how many training / DEV targets does the fixer change, by kind?  (No exam line is read.)

    nice -n 19 ionice -c3 python3 diag103.py count        -> out/diag/count103.json, out/diag/changed_<set>.jsonl
    nice -n 19 ionice -c3 python3 diag103.py boxes N      -> out/diag/boxes103.json: Azure's word boxes against the
                                                            display of Azure's line and of the fixed line (fribidi), and
                                                            Chromium against fribidi on the same lines
Sets: experiment 102's M (what M trained on), DEV, and L_local (the rest of the local pool).  Every key passes
experiment 102's guard first (guard102.assert_trainable, unchanged).
"""
from __future__ import annotations

import gzip
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(E / "102_qwen_line_reader"))
import guard102  # noqa: E402
from fix103 import fix_line, AR_LETTER, LAT, DIG  # noqa: E402

SETS = E / "102_qwen_line_reader/out/sets"
POOL = E / "102_qwen_line_reader/out/pool/pool102.jsonl.gz"
OUT = HERE / "out/diag"


def jl(p):
    op = gzip.open if str(p).endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as f:
        for l in f:
            if l.strip():
                yield json.loads(l)


def count():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for name in ("M", "dev", "L_local"):
        rows = list(jl(SETS / f"{name}.jsonl"))
        guard102.assert_trainable([r["key"] for r in rows])
        c, kinds, why = Counter(), Counter(), Counter()
        with open(OUT / f"changed_{name}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                s = r["label"]
                new, info = fix_line(s)
                c["lines"] += 1
                mixed = bool(AR_LETTER.search(s)) and bool(LAT.search(s) or DIG.search(s))
                c["arabic_with_latin_or_digit"] += mixed
                c["arabic_with_latin"] += bool(AR_LETTER.search(s)) and bool(LAT.search(s))
                why[info["why"]] += 1
                if info["changed"]:
                    c["changed"] += 1
                    for k in info["kinds"]:
                        kinds[k] += 1
                    f.write(json.dumps(dict(key=r["key"], era=r.get("era"), old=s, new=new, kinds=info["kinds"]),
                                       ensure_ascii=False) + "\n")
        res[name] = dict(counts=dict(c), share_changed=round(c["changed"] / c["lines"], 5),
                         share_of_mixed_changed=round(c["changed"] / max(1, c["arabic_with_latin_or_digit"]), 4),
                         kinds=dict(kinds), why=dict(why))
        print(name, json.dumps(res[name], ensure_ascii=False))
    (OUT / "count103.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


def _line_words(az_path, page, i):
    r = json.loads(Path(az_path).read_text(encoding="utf-8"))
    r = r.get("analyzeResult", r)
    pg = r["pages"][page - 1]
    lines = [ln for ln in pg.get("lines", []) if (ln.get("content") or "").strip()]
    ln = lines[i - 1]
    sp = ln["spans"][0]
    words = []
    for w in pg.get("words", []):
        o = w["span"]["offset"]
        if sp["offset"] <= o < sp["offset"] + sp["length"]:
            xs = w["polygon"][0::2]
            words.append(dict(text=w["content"], start=o - sp["offset"], end=o - sp["offset"] + w["span"]["length"],
                              x=(min(xs) + max(xs)) / 2))
    return ln["content"], words


def _word_order_from_display(s, words):
    """Word indices sorted left to right by the mean visual position (fribidi) of their characters in s."""
    from bidi103 import fribidi_display
    _, v2l, _ = fribidi_display(s)
    pos = {li: vi for vi, li in enumerate(v2l)}
    keyed = []
    for k, w in enumerate(words):
        idx = [j for j in range(w["start"], min(w["end"], len(s))) if not s[j].isspace()]
        if idx:
            keyed.append((sum(pos[j] for j in idx) / len(idx), k))
    return [k for _, k in sorted(keyed)]


def boxes(limit_docs: int = 0):
    """Box mode on every mixed line (Arabic + Latin or digit) of M and DEV: Azure's words placed by their boxes.
    Measures: does Azure's string display as its boxes show; does the text-mode fix equal the box-mode fix; how
    well Azure's habit (fix103.azure_style) reproduces Azure's strings; and Chromium against fribidi."""
    from bidi103 import chrome_display, chrome_base_order, fribidi_base_order, chrome_visual_shapes
    from fix103 import azure_style, display_key, clean_label
    want = {}
    for name in ("dev", "M"):
        for r in jl(SETS / f"{name}.jsonl"):
            s = r["label"]
            if AR_LETTER.search(s) and (LAT.search(s) or DIG.search(s)):
                want[r["key"]] = name
    by_file = {}
    for d in jl(POOL):
        if d["key"] in want:
            by_file.setdefault(d["azure"], []).append(d)
    files = sorted(by_file)
    if limit_docs:
        files = files[:limit_docs]
    res, rows = Counter(), []
    out = open(OUT / "boxes103.jsonl", "w", encoding="utf-8")
    for fi, az in enumerate(files):
        r = json.loads(Path(az).read_text(encoding="utf-8"))
        r = r.get("analyzeResult", r)
        for d in by_file[az]:
            name = want[d["key"]]
            pg = r["pages"][d["page"] - 1]
            lines = [ln for ln in pg.get("lines", []) if (ln.get("content") or "").strip()]
            ln = lines[d["i"] - 1]
            content = ln["content"]
            sp = ln["spans"][0]
            words = []
            for w in pg.get("words", []):
                o = w["span"]["offset"]
                if sp["offset"] <= o < sp["offset"] + sp["length"]:
                    xs = w["polygon"][0::2]
                    words.append(dict(text=w["content"], start=o - sp["offset"],
                                      end=o - sp["offset"] + w["span"]["length"], x=(min(xs) + max(xs)) / 2))
            res[f"{name}_lines"] += 1
            if clean_label(content) != d["label"]:
                res[f"{name}_label_not_line"] += 1          # title overrides, v6r labels: not Azure's line
                continue
            box_order = [k for _, k in sorted((w["x"], k) for k, w in enumerate(words))]
            disp = _word_order_from_display(content, words)
            az_ok = disp == [k for k in box_order if k in disp]
            res[f"{name}_azure_display_matches_boxes"] += az_ok
            res[f"{name}_azure_habit_reproduces"] += azure_style(display_key(content)) == content
            t_new, t_info = fix_line(content)
            t_new = clean_label(t_new)
            res[f"{name}_text_changed"] += t_info["changed"]
            if t_info["changed"]:
                res[f"{name}_changed_and_boxes_ok"] += az_ok
            if t_info["changed"] or not az_ok:
                rows.append(dict(key=d["key"], set=name, era=d.get("era"), azure=content, text_fix=t_new,
                                 kinds=t_info["kinds"], azure_boxes_ok=az_ok,
                                 words_by_box=[words[k]["text"] for k in box_order], pdf=d["pdf"], page=d["page"],
                                 i=d["i"], azure_json=az, poly=ln.get("polygon")))
                out.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
        if fi % 200 == 0:
            print(fi, len(files), dict(res), flush=True)
    out.close()
    # Chromium, the judge, on every line where something differs
    strs = []
    for e in rows:
        strs += [e["azure"], e["text_fix"]]
    xs = chrome_display(strs)
    for t, e in enumerate(rows):
        a, b = strs[2 * t: 2 * t + 2]
        xa, xb = xs[2 * t: 2 * t + 2]
        res["chrome_checked"] += 1
        res["chrome_text_fix_same_display_as_azure"] += chrome_visual_shapes(a, xa) == chrome_visual_shapes(b, xb)
        for s_, x_ in ((a, xa), (b, xb)):
            res["chrome_vs_fribidi_strings"] += 1
            res["chrome_order_eq_fribidi_runs"] += chrome_base_order(s_, x_, True) == fribidi_base_order(s_, True)
    (OUT / "boxes103.json").write_text(json.dumps(dict(res), indent=1))
    print(json.dumps(dict(res), indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "count":
        count()
    elif sys.argv[1] == "boxes":
        boxes(int(sys.argv[2]) if len(sys.argv) > 2 else 0)
