"""Whole pieces containing a letter-form, each letter's ink in its own colour: peek_pieces.py <azure.json> <scan.pdf> <letter> <form> <out.png>"""
import sys, os, numpy as np, cv2, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("mf", os.path.join(here, "make_font.py")); mf = importlib.util.module_from_spec(spec); spec.loader.exec_module(mf)
sys.path.insert(0, os.path.join(here, "..", "09_pen_path")); from penpath import picture
from atlas import sheet
azure, scan, letter, form, out = sys.argv[1:6]; mf.MAX_PLANS = 1200
plans, iso = mf.collect(azure, scan); P = mf.P; P.solve([p for p, _, _ in plans]); tiles = []; texts = []
for p, pc, lg in plans:
    if any(P.key(p, k) == (letter, form) for k in range(p["n"])) and len(tiles) < 32:
        im = picture(p["F"], p["ink_s"].astype(int), p["cuts"], p["G"], p["n"], up=5); tiles.append(cv2.copyMakeBorder(im, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=(255, 255, 255))); texts.append("".join(p["units"]))
sheet(tiles, out); print(texts)
