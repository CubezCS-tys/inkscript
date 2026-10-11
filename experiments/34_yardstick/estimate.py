"""How long will the owner need to correct the gold pages? (experiment 34)

    PYTHONPATH=src python estimate.py   -> out/estimate.json (with an HTML table for the report)

A keystroke-level model on the real counts of the drafted pages (lines, lines where the readers differ, table
cells, equations), with the share of disagreements that need typing (neither reading right) taken from the dry
run (out/dryrun.json, the agent's own pass over a sample of disagreements; dryrun.py). Three cases:
low / expected / high per-action times. Two ways of working:
  A. every line is looked at: Enter on each agreeing line, a decision on each disagreeing line;
  B. disagreements only, then one look over the page (the agreeing lines are taken as read).
B is faster but leaves errors both readers share; the owner chooses (README).
Once the owner has timed 30 lines, the correction mode's own estimate (/api/progress) replaces this one.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path("/home/yassine/inkscript/experiments/34_yardstick/out")
GOLD = OUT / "gold"
# seconds: (low, expected, high)
T = dict(agree=(1.2, 2.0, 3.5),        # glance from crop to text, Enter
         decide=(4.0, 7.0, 12.0),      # read the yellow word on the crop, take one reading (Alt+2) or keep, Enter
         type=(8.0, 15.0, 30.0),       # neither reading right: fix letters by hand (on top of deciding)
         page=(20.0, 35.0, 60.0),      # open, look over the page, missing lines, order, "page done"
         glance=(10.0, 20.0, 40.0),    # way B: look over the agreeing lines of a page at once
         cell=(3.0, 5.0, 10.0),        # check / fix one table cell in the grid
         equation=(30.0, 60.0, 150.0),  # check / fix one equation's LaTeX
         article=(20.0, 40.0, 90.0))   # mark blocks, columns and articles on a magazine page


def counts() -> dict:
    c = dict(pages=0, lines=0, disagree=0, letters=0, forms=0, vowels=0, lowconf_only=0, cells=0, equations=0,
             magazines=0)
    for f in sorted(GOLD.glob("*_p[0-9][0-9][0-9].json")):
        g = json.loads(f.read_text())
        c["pages"] += 1
        c["magazines"] += "magazine" in g.get("kinds", [])
        for ln in g["lines"]:
            c["lines"] += 1
            fl = set(ln.get("flags", []))
            if ln.get("disagree") or fl & {"gemini-differs", "forms-differ", "vowels-differ"}:
                c["disagree"] += 1
                c["letters"] += "gemini-differs" in fl
                c["forms"] += "forms-differ" in fl and "gemini-differs" not in fl
                c["vowels"] += fl == {"vowels-differ"} or fl == {"vowels-differ", "low-conf"}
            elif "low-conf" in fl:
                c["lowconf_only"] += 1
        for t in g.get("tables", []):
            h = (t.get("draft_html") or "").lower()
            c["cells"] += h.count("<td") + h.count("<th")
        c["equations"] += len(g.get("equations", []))
    return c


def main() -> int:
    c = counts()
    dr = json.loads((OUT / "dryrun.json").read_text()) if (OUT / "dryrun.json").exists() else {}
    typed = dr.get("share_typed", 0.2)
    agree = c["lines"] - c["disagree"]
    out = {}
    for way in ("A", "B"):
        hours = []
        for k in range(3):
            s = c["pages"] * T["page"][k] + c["disagree"] * (T["decide"][k] + typed * T["type"][k])
            s += agree * T["agree"][k] if way == "A" else c["pages"] * T["glance"][k] + c["lowconf_only"] * T["decide"][k]
            s += c["cells"] * T["cell"][k] + c["equations"] * T["equation"][k] + c["magazines"] * T["article"][k]
            hours.append(round(s / 3600, 1))
        out[way] = hours
    res = dict(counts=c, typed_share=typed, dryrun=dr, times=T, hours_A=out["A"], hours_B=out["B"],
               hours=dict(low=out["A"][0], expected=out["A"][1], high=out["A"][2]))
    rows = "".join(f"<tr><td>{n}</td><td>{v:,}</td></tr>" for n, v in [
        ("pages", c["pages"]), ("lines", c["lines"]), ("lines where the readers differ", c["disagree"]),
        ("&nbsp;&nbsp;letters differ", c["letters"]), ("&nbsp;&nbsp;only hamza/alef/ى-ي forms differ", c["forms"]),
        ("&nbsp;&nbsp;only vowel marks differ (vowelled pages)", c["vowels"]),
        ("lines with a very unsure word but no disagreement", c["lowconf_only"]),
        ("table cells (drafted)", c["cells"]), ("equations (drafted)", c["equations"]),
        ("magazine pages (blocks and articles)", c["magazines"])])
    res["html"] = (f"<table><tr><th>what</th><th>count</th></tr>{rows}</table>"
                   f"<p>Time per action (low / expected / high, seconds): agreeing line {T['agree']}, deciding a "
                   f"disagreement {T['decide']}, typing a fix {T['type']} (needed on {typed:.0%} of disagreements in the "
                   f"dry run), page {T['page']}, table cell {T['cell']}, equation {T['equation']}, magazine page "
                   f"{T['article']}.</p>"
                   f"<p><b>A. Every line looked at: {out['A'][1]} h</b> (between {out['A'][0]} and {out['A'][2]} h). "
                   f"<b>B. Only the disagreements, then a look over each page: {out['B'][1]} h</b> "
                   f"({out['B'][0]}–{out['B'][2]} h). The research guessed 30–40 h. The correction mode measures your own "
                   f"pace after 30 lines and then shows the hours left from it.</p>")
    (OUT / "estimate.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "html"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
