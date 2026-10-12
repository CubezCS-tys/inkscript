"""Score on the owner's gold pages (experiment 34's yardstick: inkscript score, status "done" only). Scoring only.

    out/env/bin/python gold_eval.py        -> out/gold_eval.json
Lines: each gold line's box cut from the yardstick's own page image (300 dpi), read by every model; Azure's reading is
the yardstick's own Azure draft of that line. Pages: each line finder (kraken's default, the fine-tuned one) with the
round-B Kraken reader, matched to the gold lines as evaluate.py matches pages. Faithful normalisation (textnorm.py).
"""
import json, sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textnorm import faithful, search
from evaluate import match_pages
from rapidfuzz.distance import Levenshtein

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); G = Path("/home/yassine/inkscript/experiments/34_yardstick/out/gold")
MODELS = {"base": OUT / "models/arabic_best.mlmodel", "ftA": OUT / "models/ftA.safetensors", "ppA": OUT / "models/ppA.safetensors",
          "ftB": OUT / "models/ftB.safetensors", "ppB": OUT / "models/ppB.safetensors"}
if (OUT / "models/ftC.safetensors").exists():
    MODELS["ftC"] = OUT / "models/ftC.safetensors"
pages = [json.load(open(p)) for p in sorted(G.glob("*.json"))]
pages = [p for p in pages if p.get("status") == "done"]
crops = []
for p in pages:
    im = Image.open(G / p["image"]["file"]).convert("L")
    for l in p["lines"]:
        x0, y0, x1, y1 = l["box"]; h = y1 - y0
        box = (max(0, int(x0 - 0.25 * h)), max(0, int(y0 - 0.15 * h)), min(im.width, int(x1 + 0.25 * h) + 1), min(im.height, int(y1 + 0.15 * h) + 1))
        path = OUT / "gold_crops" / f"{p['page_id']}_{l['id']}.png"; path.parent.mkdir(exist_ok=True)
        im.crop(box).save(path)
        crops.append(dict(page=p["page_id"], id=l["id"], gold=l["text"], azure=(l.get("draft") or {}).get("azure", ""), img=str(path), kind=l.get("kind")))
import krk
res = {"pages": [p["page_id"] for p in pages], "lines": len(crops), "readers": {}}
def score(get):
    out = {}
    for norm, f in (("faithful", faithful), ("search", search)):
        e = n = 0
        for c in crops:
            g = f(c["gold"]); e += Levenshtein.distance(g, f(get(c) or "")); n += len(g)
        out[norm] = e / max(n, 1)
    return out
res["readers"]["azure"] = score(lambda c: c["azure"])
preds = {}
for name, m in MODELS.items():
    krk._init(str(m), 4)
    preds[name] = {c["id"] + c["page"]: krk.read_line(c["img"])["text"] for c in crops}
    res["readers"][name] = score(lambda c: preds[name][c["id"] + c["page"]])
# pages: line finders x the round-B Kraken reader
import fullpage
res["page_runs"] = {}
for segname, segm in (("blla", None), ("segcpu", str(OUT / "models/segcpu.safetensors"))):
    fullpage._init(str(MODELS["ftB"]), 4, segm)
    from kraken import blla, rpred
    e = n = 0; dropped = inserted = 0
    for p in pages:
        im = Image.open(G / p["image"]["file"]).convert("L")
        seg = fullpage._seg[0].predict(im, fullpage._seg[1]) if fullpage._seg else blla.segment(im, text_direction="horizontal-rl")
        net = fullpage._net
        lines = []
        for rec in (net[0].predict(im, seg, net[1]) if isinstance(net, tuple) else rpred.rpred(net, im, seg)):
            xs = [q[0] for q in rec.boundary]; ys = [q[1] for q in rec.boundary]
            lines.append(dict(bbox=[min(xs), min(ys), max(xs), max(ys)], text=rec.prediction))
        gl = [dict(bbox=l["box"], gold=l["text"]) for l in p["lines"]]
        pairs, ins = match_pages(gl, lines, 1.0)
        for g, t in pairs:
            e += Levenshtein.distance(faithful(g["gold"]), faithful(t)); n += len(faithful(g["gold"])); dropped += not t.strip()
        e += sum(len(faithful(q["text"])) for q in ins); inserted += len(ins)
    res["page_runs"][f"ftB+{segname}"] = dict(cer=e / max(n, 1), dropped=dropped, inserted=inserted)
res["examples"] = [dict(c, **{k: preds[k][c["id"] + c["page"]] for k in preds}) for c in crops]
json.dump(res, open(OUT / "gold_eval.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "examples"}, indent=1))
