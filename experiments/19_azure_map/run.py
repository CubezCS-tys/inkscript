"""Judge every sampled word (out/sample.json): Flash first (calibrated as good as Pro on the gold pages, half the price),
then every word Flash did not call RIGHT goes to Pro for a second opinion.

    .venv/bin/python run.py [--limit-usd 6]
"""
import sys, json
from pathlib import Path
import cv2
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
sys.path.insert(0, str(HERE))
import judge1 as J
FLASH, PRO = "gemini-3.8-flash", "gemini-3.1-pro-preview"

def items(ws):
    return [dict(id=w["id"], reading=w["text"], img=cv2.imread(str(OUT / "crops" / (w["id"].replace(":", "_") + ".png")))) for w in ws]

if __name__ == "__main__":
    a = sys.argv[1:]; lim = float(a[a.index("--limit-usd") + 1]) if "--limit-usd" in a else 6.0
    sample = json.load(open(OUT / "sample.json"))
    print(len(sample), "words; Flash estimate $%.2f; spent so far $%.3f" % (J.estimate(len(sample), FLASH), J.spent()), flush=True)
    r1 = J.judge(items(sample), FLASH, tag="run", limit_usd=lim)
    flag = [w for w in sample if w["id"] in r1 and r1[w["id"]]["verdict"] != "right"]
    print(len(flag), "not RIGHT by Flash; Pro estimate $%.2f" % J.estimate(len(flag), PRO), flush=True)
    r2 = J.judge(items(flag), PRO, batch=6, tag="run2", limit_usd=lim)
    print("done; spent $%.3f" % J.spent())
