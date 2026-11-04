"""Experiment 58: Azure's lines (id, text, 300 dpi box) of the truth pages -> out/azure_truth34.json (for crops58.py)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "41_azure_structure"))
from structure import page_lines, sample  # noqa: E402
arts = {a["stem"]: a for a in sample()}
units = json.loads((HERE / "out/units_truth34.json").read_text())
out = {}
for u in units:
    stem, p = u["id"].rsplit("_p", 1)
    out[u["id"]] = [dict(id=l["id"], text=l["text"], px=l["px"]) for l in page_lines(arts[stem], int(p))[0]]
(HERE / "out/azure_truth34.json").write_text(json.dumps(out, ensure_ascii=False))
print(len(out))
