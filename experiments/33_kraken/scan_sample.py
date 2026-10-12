"""The real-scan sample: the lines that hold experiment 19's judged words, cropped from the scans at 300 dpi.

    nice out/env/bin/python scan_sample.py   -> out/scan/img/<doc>_p<page>_w<i>.png, out/scan/scan.jsonl
Each record: the Azure line (its words joined by spaces, in Azure's order), where the judged word sits in it, the truth
for that word (Azure's text when the judge said RIGHT, the judge's reading when WRONG), the stratum and weight of
experiment 19. Words judged BOX or UNSURE, punctuation-only verdicts and sideways pages are left out; their lines are
still written (silver line truth = Azure's line).
"""
import json
from pathlib import Path
import pymupdf
from PIL import Image

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
DPI = 300

if __name__ == "__main__":
    judged = json.load(open(E19 / "judged.json")); meta = json.load(open(OUT / "meta.json"))
    (OUT / "scan" / "img").mkdir(parents=True, exist_ok=True)
    by_doc = {}
    for w in judged:
        by_doc.setdefault(w["doc"], []).append(w)
    out = open(OUT / "scan" / "scan.jsonl", "w"); n = 0
    for doc_id, ws in sorted(by_doc.items()):
        d = E19 / "docs" / doc_id
        az = json.load(open(d / f"{doc_id}.json")); az = az.get("analyzeResult", az)
        azp = {p["pageNumber"]: p for p in az["pages"]}
        pdf = pymupdf.open(str(d / f"{doc_id}.pdf")); cache = {}
        for w in sorted(ws, key=lambda w: (w["page"], w["i"])):
            pg = azp[w["page"]]
            if abs(pg.get("angle") or 0) > 45:
                continue
            words = pg["words"]; s = DPI if pg.get("unit", "inch") == "inch" else 1.0
            off = words[w["i"]]["span"]["offset"]
            line = next((ln for ln in pg["lines"] if any(sp["offset"] <= off < sp["offset"] + sp["length"] for sp in ln["spans"])), None)
            if line is None:
                continue
            a = min(sp["offset"] for sp in line["spans"]); b = max(sp["offset"] + sp["length"] for sp in line["spans"])
            mem = [k for k, x in enumerate(words) if a <= x["span"]["offset"] < b]
            text = ""; pos = None
            for k in mem:
                if text: text += " "
                if k == w["i"]: pos = (len(text), len(text) + len(words[k]["content"]))
                text += words[k]["content"]
            boxes = []
            for k in mem:
                p = words[k]["polygon"]; xs = [v * s for v in p[0::2]]; ys = [v * s for v in p[1::2]]
                boxes.append((min(xs), min(ys), max(xs), max(ys)))
            x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes); x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
            hs = sorted(b[3] - b[1] for b in boxes); h = hs[len(hs) // 2]
            if w["page"] not in cache:
                cache.clear()
                pix = pdf[w["page"] - 1].get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
                cache[w["page"]] = Image.frombytes("L", (pix.width, pix.height), pix.samples)
            im = cache[w["page"]]
            box = (max(0, int(x0 - 0.25 * h)), max(0, int(y0 - 0.15 * h)), min(im.width, int(x1 + 0.25 * h) + 1), min(im.height, int(y1 + 0.15 * h) + 1))
            if box[2] - box[0] < 4 or box[3] - box[1] < 4:
                continue
            lid = f"{doc_id}_p{w['page']}_w{w['i']}"
            im.crop(box).save(OUT / "scan" / "img" / f"{lid}.png", optimize=True)
            use = w["verdict"] in ("right", "wrong") and not w["punct"]
            truth = w["text"] if w["verdict"] == "right" else (w.get("judge") or w.get("pro_text") or w.get("flash_text"))
            out.write(json.dumps(dict(id=lid, doc=doc_id, page=w["page"], i=w["i"], line=text, word=w["text"], pos=pos, px=box,
                                      truth=truth if use else None, verdict=w["verdict"], err=w["err"], punct=w["punct"],
                                      stratum=w["stratum"], w=w["w"], conf=w["conf"], cause=w.get("cause"),
                                      year=meta.get(doc_id, {}).get("year")), ensure_ascii=False) + "\n")
            n += 1
        print(doc_id, len(ws), flush=True)
    print(n, "lines written")
