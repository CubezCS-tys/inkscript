"""Experiment 76, step 1: how many Azure lines can be trusted as training labels? (read only; no calls)

A. 202 pages of experiment 34's yardstick (8,457 lines): each line has Azure's reading and a *blind*
   gemini-3.8-flash reading of the line crop (never saw Azure). Share of lines where the two agree, under the lab's
   policies (raw, faithful, no_punct, folded; experiment 75 labocr/evaluation.py).
B. The 20 owner-checked pages among them (756 lines): is an agreed line right? (precision of the label) and how
   many right lines does agreement keep? (yield). Same for Argon's reading (Azure + Argon's fixes, experiment 43's
   v2_55 run) and for Argon + Gemini.
C. Every Argon fix on disk (all runs of inventory76): share that only touches marks / punctuation.
Writes out/consensus76.json.
"""
from __future__ import annotations
import json, re, sys, collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E.parent / "src"))
from inkscript.gold.text import faithful, folded  # noqa: E402

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]|_", re.UNICODE)
POL = {"raw": lambda s: _WS.sub(" ", s or "").strip(),
       "faithful": faithful,
       "no_punct": lambda s: _WS.sub(" ", _PUNCT.sub(" ", faithful(s or ""))).strip(),
       "folded": lambda s: _WS.sub(" ", folded(s or "")).strip()}
GOLD = E / "34_yardstick/out/gold"


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def argon_lines():
    """{(stem, page): {azure_text: argon_text}} from the v2_55 run (the 55 articles holding all 20 gold pages)."""
    arts = {a["stem"]: a for a in jl(E / "41_azure_structure/out/sample.json")["articles"]}
    out = {}
    for f in sorted((E / "43_rehearsal/out/v2_55/raw").glob("*.json")):
        d = jl(f)
        a = arts.get(d["stem"])
        if not a or not isinstance(d.get("answer"), dict):
            continue
        az = jl(str(a["azure"]).replace("/home/yassine/", "/home/appuser/"))
        pages = az.get("analyzeResult", az)["pages"]
        fixes = collections.defaultdict(list)
        for x in d["answer"].get("fixes") or []:
            fixes[str(x.get("line"))].append(x)
        for p in range(d["first"], d["last"] + 1):
            lines = [t for t in ((ln.get("content") or "").strip() for ln in pages[p - 1].get("lines", [])) if t]
            m = out.setdefault((d["stem"], p), {})
            for i, t in enumerate(lines, 1):
                s = t
                for x in fixes.get(f"{p}:{i}", []):
                    if x.get("from") and x["from"] in s:
                        s = s.replace(x["from"], x.get("to") or "", 1)
                m.setdefault(t, s)
    return out


def main():
    res = {}
    # ---------------------------------------------------------------- A: Azure vs blind Gemini, 202 pages
    agree = {k: 0 for k in POL}
    n = 0
    kinds = collections.defaultdict(lambda: collections.Counter())
    dec = collections.defaultdict(lambda: collections.Counter())
    pages = 0
    done = []
    for f in sorted(GOLD.glob("*.json")):
        g = jl(f)
        pages += 1
        if g.get("status") == "done":
            done.append(g)
        for L in g["lines"]:
            dr = L.get("draft") or {}
            if "gemini" not in dr or not (dr.get("azure") or "").strip():
                continue
            n += 1
            k = L.get("kind") or "?"
            kinds[k]["n"] += 1
            dec[g.get("decade") or "?"]["n"] += 1
            for p, fn in POL.items():
                if fn(dr["azure"]) == fn(dr["gemini"]):
                    agree[p] += 1
                    kinds[k][p] += 1
                    dec[g.get("decade") or "?"][p] += 1
    res["A_azure_vs_gemini_blind"] = dict(pages=pages, lines=n, agree={p: agree[p] / n for p in POL},
                                          agree_n=agree, by_kind={k: dict(v) for k, v in kinds.items()},
                                          by_decade={k: dict(v) for k, v in dec.items()})
    print("A", json.dumps(res["A_azure_vs_gemini_blind"]["agree"]), n, pages, flush=True)

    # ---------------------------------------------------------------- B: against the owner's truth, 20 pages
    AR = argon_lines()
    B = {p: collections.Counter() for p in POL}
    examples = []
    for g in done:
        amap = AR.get((g["stem"], g["page"]), {})
        for L in g["lines"]:
            if L.get("status") in ("deleted", "todo"):
                continue
            dr = L.get("draft") or {}
            az, ge, tr = dr.get("azure") or "", dr.get("gemini"), L.get("text") or ""
            if not az.strip() or ge is None:
                continue
            ar = amap.get(az.strip())
            for p, fn in POL.items():
                c = B[p]
                T = fn(tr)
                c["lines"] += 1
                c["truth_eq_azure"] += fn(az) == T
                c["truth_eq_gemini"] += fn(ge) == T
                ag = fn(az) == fn(ge)
                c["agree"] += ag
                c["agree_right"] += ag and fn(az) == T
                if ar is not None:
                    c["argon_found"] += 1
                    c["argon_right"] += fn(ar) == T
                    c["argon_changed"] += ar != az.strip()
                    c["argon_unchanged"] += ar == az.strip()
                    c["argon_unchanged_right"] += ar == az.strip() and fn(az) == T
                    ag2 = fn(ar) == fn(ge)
                    c["argon_gemini_agree"] += ag2
                    c["argon_gemini_agree_right"] += ag2 and fn(ar) == T
                    c["argon_right_n_found"] += 0
                if p == "faithful" and ag and fn(az) != T and len(examples) < 40:
                    examples.append(dict(page=g["page_id"], azure=az, gemini=ge, truth=tr, argon=ar))
    res["B_owner_truth_20_pages"] = {p: dict(c) for p, c in B.items()}
    res["B_agreed_but_wrong_examples"] = examples
    for p, c in B.items():
        print("B", p, dict(c), flush=True)

    # ---------------------------------------------------------------- C: what Argon's fixes touch
    C = collections.Counter()
    inv = [json.loads(x) for x in open(HERE / "out/inventory76.jsonl", encoding="utf-8")]
    raws = {"v2_55": E / "43_rehearsal/out/v2_55/raw", "v33_300": E / "43_rehearsal/out/v33_300/raw",
            "v33_300b": E / "43_rehearsal/out/v33_300b/raw", "j0130": E / "52_journal_gate1/out/j0130/raw",
            "j0165": E / "70_gate2_pilot/out/j0165/raw"}
    for j in ("0011", "0013", "0097", "0246", "0523", "0840", "1001"):
        raws[f"j{j}"] = E / f"74_gate2_full/out/{j}/j{j}/raw"
    for name, rd in raws.items():
        for f in rd.glob("*.json"):
            d = jl(f)
            ans = d.get("answer")
            if not isinstance(ans, dict):
                continue
            for x in ans.get("fixes") or []:
                a, b = x.get("from") or "", x.get("to") or ""
                C["fixes"] += 1
                if POL["faithful"](a) == POL["faithful"](b):
                    C["same_faithful"] += 1
                elif POL["no_punct"](a) == POL["no_punct"](b):
                    C["punct_only"] += 1
                elif POL["folded"](a) == POL["folded"](b):
                    C["marks_or_letterforms_only"] += 1
                else:
                    C["letters_or_words"] += 1
    res["C_argon_fixes"] = dict(C)
    print("C", dict(C), flush=True)
    (HERE / "out/consensus76.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
