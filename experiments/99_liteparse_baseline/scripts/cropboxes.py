"""Media box vs crop box of every exam page (repo's pinned pypdfium2, read only) -> out/cropboxes.json.
78 of 214 exam pages (ScanToPDF files) have a crop box set inside the media box; their invisible text layer sits
offset from the scanned ink by the crop box's origin (see README, 'How lines were matched')."""
import json
import pypdfium2 as pdfium
E = "/home/appuser/inkscript/experiments/99_liteparse_baseline"
inv = {r["stem"]: r for r in json.load(open(f"{E}/out/inventory.json"))}
L = json.load(open("/home/appuser/inkscript/experiments/97_extraction_evals/LOCKED_EVAL.json"))["articles"]
out = {}
for a in L:
    doc = pdfium.PdfDocument(inv[a["stem"]]["pdf"])
    for pg in sorted(set(a["pages"].values())):
        p = doc[pg - 1]
        out[f"{a['stem']}|{pg}"] = dict(media=list(p.get_mediabox()), crop=list(p.get_cropbox()))
json.dump(out, open(f"{E}/out/cropboxes.json", "w"), indent=0)
print(len(out), sum(1 for v in out.values() if [round(x, 1) for x in v["media"]] != [round(x, 1) for x in v["crop"]]))
