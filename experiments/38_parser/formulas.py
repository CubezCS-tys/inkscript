"""Experiment 38, step 2: every displayed formula checked on its crop, then MathML -> out/pages/<pid>/formulas.json.

    PYTHONPATH=<worktree>/src /home/yassine/inkscript/.venv/bin/python formulas.py [--estimate]

One Gemini 3.1 Pro call per formula: the crop of the scan and dots.mocr's LaTeX (or nothing, where dots gave none).
The model returns the LaTeX as printed: dots' unchanged when it is right, corrected, or redone. The equation's number
is split off as its label. LaTeX -> MathML with latex2mathml (the JATS holds MathML, tex-math and the crop in
<alternatives>). A formula the converter cannot take keeps its tex-math and crop only.
"""
from __future__ import annotations

import json
import re
import sys

import cv2

from common import OUT, gemini, jpeg, pages

MODEL = "gemini-3.1-pro-preview"
PROMPT = """Image 1 is a crop of a scanned Arabic journal page holding one displayed formula (Arabic words may appear
inside it). An OCR system transcribed it as this LaTeX:

{tex}

Check it against the image only, and give the LaTeX that renders exactly what is printed:
- if the transcription is right, return it unchanged (verdict "correct");
- if it has errors (a wrong or missing symbol, sub/superscript, fraction, bracket, sign, digit), fix them (verdict "fixed");
- if it is unusable or empty, transcribe the formula from the image (verdict "redone").
Rules: Arabic words go in \\text{{...}}, in the printed reading order of the formula; keep digits as printed (Arabic-Indic
digits stay Arabic-Indic); do not add anything that is not printed; no \\tag, no $ signs, no \\begin{{equation}}.
Put the formula's printed number, if any (for example (3) or (٣)), in "label" and leave it out of the LaTeX.
If the crop holds no formula at all (plain text), set verdict "not-a-formula" and latex "".
"""
SCHEMA = {"type": "object", "properties": {
    "verdict": {"type": "string", "enum": ["correct", "fixed", "redone", "not-a-formula"]},
    "latex": {"type": "string"}, "label": {"type": "string"}, "note": {"type": "string"}},
    "required": ["verdict", "latex", "label", "note"]}


def split_label(tex: str) -> tuple[str, str]:
    m = re.search(r"\\(?:q?quad|,|;|\s)*\(([0-9\u0660-\u0669]{1,3})\)\s*$", tex)
    if m:
        return tex[:m.start()].rstrip(), f"({m.group(1)})"
    m = re.search(r"\\tag\{([^}]*)\}\s*$", tex)
    if m:
        return tex[:m.start()].rstrip(), f"({m.group(1)})"
    return tex, ""


def to_mathml(tex: str) -> str:
    import latex2mathml.converter as c
    try:
        return c.convert(tex, display="block")
    except Exception:
        return ""


def main(argv):
    est = "--estimate" in argv
    n = 0
    for meta in pages():
        pid = meta["page_id"]
        lf = OUT / "pages" / pid / "layout.json"
        ff = OUT / "pages" / pid / "formulas.json"
        if not lf.exists() or ff.exists():
            continue
        L = json.loads(lf.read_text(encoding="utf-8"))
        res = []
        for b in L["blocks"]:
            if b["role"] != "formula":
                continue
            n += 1
            if est:
                continue
            img = cv2.imread(str(OUT / "pages" / pid / b["crop"]))
            tex0 = b.get("tex_dots") or ""
            ans, usd = gemini(PROMPT.format(tex=tex0 or "(nothing: the OCR system gave no LaTeX)"),
                              [jpeg(img, 1400)], f"formula {pid} {b['id']}", model=MODEL, max_out=6000,
                              schema=SCHEMA, thinking="low")
            dtex, dlab = split_label(tex0)
            if ans and ans.get("verdict") != "not-a-formula" and ans.get("latex", "").strip():
                tex, lab = split_label(ans["latex"].strip())
                lab = lab or (ans.get("label") or "").strip() or dlab
                src = "gemini-" + ans["verdict"]
            else:
                tex, lab, src = dtex, dlab, "dots" if ans else "dots (no check)"
            if lab and not lab.startswith("("):
                lab = f"({lab.strip('()')})"
            res.append(dict(id=b["id"], tex_dots=tex0, tex=tex, label=lab, source=src,
                            verdict=(ans or {}).get("verdict"), note=(ans or {}).get("note"),
                            mathml=to_mathml(tex), usd=usd))
            print(pid, b["id"], src, "|", tex[:80], lab, flush=True)
        if not est:
            ff.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if est:
        print(n, "formulas; about", round(n * 0.03, 2), "USD at most")


if __name__ == "__main__":
    main(sys.argv[1:])
