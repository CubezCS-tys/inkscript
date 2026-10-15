"""Summarise scored approach folders over a subset of pages, plus ORDER-FREE word measures (D_agentic's analysis).

    .venv/bin/python D_subset.py [--all] out/D_agentic/<variant> [...]

score.py's CER is order-sensitive: on multi-column and verse pages most of it is reading order. To see what a
"look again" pass fixes (letters and vowel marks), this also reports, per page group:
  bag_truth  = 1 - F1 of the page's word multiset vs the truth's (gold: faithful words with vowel marks;
               born-digital: digits folded) — misread words, order ignored
  bag_az_f   = the same vs Azure's words, folded (letters only, no vowel marks) — agreement, not accuracy
"""
import json, re, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score import summarise, blocks_of, jload, e36, GOLD, read_unit, units   # noqa
from inkscript.gold.format import load as gold_load
from inkscript.gold.text import folded
from D_agentic import EXPLORE

K = ("cer_gold", "cer_bd", "cer_az", "invented_per_1000w", "dropped_per_1000w", "layout_text_acc", "word_order",
     "teds_vs_pro_draft", "eq_sim_vs_pro_draft", "usd_per_page")
U = {u["page_id"]: u for u in units("sample")}
TATWEEL = "ـ"


def words(lines, fold=False, dig=False):
    s = " ".join(lines).replace(TATWEEL, "")
    if dig:
        s = s.translate(e36.DIG)
    if fold:
        s = folded(s)
    s = re.sub(r"[^\w؀-ۿ\s]", " ", s)
    return Counter(s.split())


def bag(p, r):
    m = sum((p & r).values())
    n = sum(p.values()) + sum(r.values())
    return (n - 2 * m), n


def page_bags(adir, pid):
    u = U[pid]
    bl, _, _ = read_unit(adir, u)
    pl = [b["text"] for b in (bl or []) if b["text"]]
    out = {}
    az = [ln["text"] for ln in jload(u["azure_file"])["lines"]]
    out["az"] = bag(words(pl, fold=True), words(az, fold=True))
    if u.get("truth") == "gold":
        g = gold_load(GOLD / f"{pid}.json")
        tl = [ln["text"] for ln in e36.gold_lines(g) if ln.get("kind", "text") != "equation"]
        out["truth"] = bag(words(pl), words(tl))
    elif u.get("truth") == "born_digital":
        t = jload(u["truth_file"])
        out["truth"] = bag(words(pl, dig=True), words([ln["text"] for ln in t["lines"]], dig=True))
    return out


def report(d, pids):
    adir = Path(d)
    rows = [r for r in json.loads((adir / "score_sample.json").read_text())["rows"] if r["page_id"] in pids]
    s = summarise(rows)["all"]
    bt = [0, 0]; ba = [0, 0]; per = {}
    for pid in pids:
        b = page_bags(adir, pid)
        ba[0] += b["az"][0]; ba[1] += b["az"][1]
        if "truth" in b:
            bt[0] += b["truth"][0]; bt[1] += b["truth"][1]
        per[pid] = b
    s["bag_truth"] = round(bt[0] / bt[1], 4) if bt[1] else None
    s["bag_az_f"] = round(ba[0] / ba[1], 4) if ba[1] else None
    return s, rows, per


if __name__ == "__main__":
    args = sys.argv[1:]
    allp = "--all" in args
    args = [a for a in args if a != "--all"]
    pids = list(U) if allp else EXPLORE
    for d in args:
        s, rows, per = report(d, pids)
        print(f"{Path(d).name:8}", " ".join(f"{k}={s[k]}" for k in ("bag_truth", "bag_az_f") + K if s.get(k) is not None))
        if not allp:
            for pid, b in per.items():
                print("    ", pid[:24], " ".join(f"{k}={v[0] / max(1, v[1]):.4f}" for k, v in b.items()))
