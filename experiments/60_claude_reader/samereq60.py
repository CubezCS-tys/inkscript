"""Plumbing check: prompt43.make_prompt (v3.3, the chunk context from Argon's own earlier answers) rebuilds the
exact text and images Gemini was sent in the exam (stored batch requests). No calls.
    samereq60.py STEM_cX-Y ...  [--set c --run v33_300b --prompt v3.3]"""
import argparse, base64, json, sys
from common60 import OUT, articles, pipeline, jl
def stored(key):
    idx = jl(OUT / "req_index.json")
    f, off = idx[key][-1]
    with open(f, "rb") as fh:
        fh.seek(off)
        return json.loads(fh.readline())
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("chunks", nargs="+"); ap.add_argument("--set", default="c")
    ap.add_argument("--run", default="v33_300b"); ap.add_argument("--prompt", default="v3.3")
    ap.add_argument("--state-run", default="v33_300b_fix3")
    a = ap.parse_args(); P = pipeline(); P.use(a.prompt); import run43
    arts = articles(a.set)
    for c in a.chunks:
        stem, xy = c.rsplit("_c", 1); x, y = map(int, xy.split("-"))
        art = arts[stem]; ci = [i for i, (u, v) in enumerate(P.ST.chunks(art)) if u == x][0]
        txt, imgs, n = P.make_prompt(art, ci, x, y, run43.state_for(art, ci, a.state_run))
        req = stored(f"{a.run}_{stem}_c{x:03d}-{y:03d}")
        parts = req["request"]["contents"][0]["parts"]
        gt = parts[-1]["text"]; gimgs = [base64.b64decode(p["inlineData"]["data"]) for p in parts if "inlineData" in p]
        print(c, "text same" if gt == txt else f"TEXT DIFFERS ({len(gt)} vs {len(txt)})",
              "images same" if gimgs == imgs else f"images differ ({len(gimgs)} vs {len(imgs)}; sizes {[len(i) for i in gimgs][:3]} vs {[len(i) for i in imgs][:3]})")
        if gt != txt:
            import difflib
            for l in list(difflib.unified_diff(gt.splitlines(), txt.splitlines(), lineterm="", n=0))[:12]: print("   ", l[:200])
main()
