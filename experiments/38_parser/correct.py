"""Experiment 38, step 3: correction with understanding, under strict rules -> out/pages/<pid>/corrections.json.

    PYTHONPATH=<worktree>/src /home/yassine/inkscript/.venv/bin/python correct.py [--estimate] [PID ...]

One call per block with Azure words (text, headings, list items, notes, captions, furniture, table cells as one call
per table): the block's crop of the scan and Azure's text, line by line. The model may propose only clear OCR
errors the ink shows (wrong letters, missing hamza or dots, words split or joined, digits); it must not touch style,
spelling conventions, grammar, or vowel marks that are not printed. It answers with edits: line, the exact words
before, the words after, kind, reason, confidence.

Every proposal is logged. It is applied only if all of these hold (rules fixed before any page was seen):
  - its "before" is a run of whole words found in that line (else: not-found);
  - confidence >= 0.8 (else: low-confidence);
  - at most 3 words before and 3 after (else: too-long, a rewrite);
  - it does not only add vowel marks (else: adds-marks); it does not only remove or change vowel marks
    (else: marks-only: Azure keeps 89% of printed marks, the model's reading of marks on a crop is not trusted);
  - after is not empty unless before is pure punctuation/noise (else: deletes-words).
Applied edits rewrite the words (a join takes the union of the boxes, a split shares the box by letters); the
original Azure words stay recoverable (ALTO <ALTERNATIVE>, and this log).
"""
from __future__ import annotations

import json
import re
import sys

import cv2

from common import OUT, TASHKEEL, gemini, jpeg, pages, page_image

MODEL = "gemini-3.8-flash"
PROMPT = """Image 1 is a crop of a scanned page (Arabic, sometimes with Latin script). Below is what an OCR system
read in it, line by line. Your only job is to find CLEAR OCR ERRORS that the ink in the image shows, so they can be
fixed. Do not edit for any other reason.

You MAY fix, where the image clearly shows it:
- a wrong letter or a letter missing or extra (e.g. dots read wrong: ب/ت/ث/ن/ي, ح/ج/خ, ر/ز, س/ش, ص/ض, ط/ظ, ع/غ, ف/ق);
- a hamza or madda that is printed but missing, or read but not printed (أ إ آ ا ؤ ئ ء);
- ة/ه or ى/ي read differently from what is printed;
- a word wrongly split in two or two words wrongly joined;
- a wrong digit or number, a Latin word misread.
You MUST NOT:
- change the author's style, word choice, grammar or spelling conventions (old or unusual spellings stay as printed);
- modernise spelling, or "correct" a word that is printed that way;
- add or remove vowel marks (harakat, shadda, tanween); leave all marks as they are;
- reorder words, translate, or add words that are not printed;
- touch anything you cannot read clearly in the image.
If you are not sure, do not propose an edit. Most lines need no edit at all; an empty list is the usual answer.

For each edit give: the line number; "before": the exact word or words as they appear in that line (copy them
character for character); "after": what is printed; "kind" (letters, hamza, dots, ta-marbuta/alef-maqsura, split,
join, digits, latin, punctuation); a short reason; your confidence from 0 to 1.

OCR text:
{lines}
"""
SCHEMA = {"type": "object", "properties": {"edits": {"type": "array", "items": {"type": "object", "properties": {
    "line": {"type": "integer"}, "before": {"type": "string"}, "after": {"type": "string"},
    "kind": {"type": "string"}, "reason": {"type": "string"}, "confidence": {"type": "number"}},
    "required": ["line", "before", "after", "kind", "reason", "confidence"]}}}, "required": ["edits"]}
TEXT_ROLES = ("p", "li", "fn", "caption", "heading", "title", "header", "footer", "pagenum")
PUNCT = re.compile(r"^[\W_]*$")


def units(L: dict) -> list[dict]:
    """What is sent: one unit per text block (its Azure lines) and one per table (its Azure cells)."""
    out = []
    for b in L["blocks"]:
        if b["role"] in TEXT_ROLES and b.get("lines") and b["source"] != "dots":
            out.append(dict(id=b["id"], box=b["box"], lines=[[w["id"] for w in ln] for ln in b["lines"]],
                            texts=[" ".join(w["text"] for w in ln) for ln in b["lines"]]))
        elif b["role"] == "table":
            cells = [c for r in b["rows"] for c in r["cells"] if c.get("words")]
            if cells:
                out.append(dict(id=b["id"], box=b["box"], lines=[[w["id"] for w in c["words"]] for c in cells],
                                texts=[" ".join(w["text"] for w in c["words"]) for c in cells], table=True))
    return out


def check(e: dict, words: list[str]) -> tuple[str, int]:
    """(status, start index) of a proposal against its line's words."""
    before = e.get("before", "").split()
    after = e.get("after", "").split()
    if not before:
        return "not-found", -1
    start = -1
    for i in range(len(words) - len(before) + 1):
        if words[i:i + len(before)] == before:
            start = i
            break
    if start < 0:
        return "not-found", -1
    if " ".join(before) == " ".join(after):
        return "no-change", start
    if float(e.get("confidence") or 0) < 0.8:
        return "low-confidence", start
    if len(before) > 3 or len(after) > 3:
        return "too-long", start
    b0, a0 = " ".join(before), " ".join(after)
    if TASHKEEL.sub("", b0) == TASHKEEL.sub("", a0):
        return ("adds-marks" if len(TASHKEEL.findall(a0)) > len(TASHKEEL.findall(b0)) else "marks-only"), start
    if len(TASHKEEL.findall(a0)) > len(TASHKEEL.findall(b0)):
        return "adds-marks", start
    if not after and not all(PUNCT.match(w) for w in before):
        return "deletes-words", start
    return "applied", start


def main(argv):
    est = "--estimate" in argv
    want = [a for a in argv if not a.startswith("--")]
    n_units = 0
    for meta in pages():
        pid = meta["page_id"]
        if want and pid not in want:
            continue
        lf = OUT / "pages" / pid / "layout.json"
        cf = OUT / "pages" / pid / "corrections.json"
        if not lf.exists() or cf.exists():
            continue
        L = json.loads(lf.read_text(encoding="utf-8"))
        us = units(L)
        n_units += len(us)
        if est:
            continue
        img = page_image(pid)
        H, W = img.shape[:2]
        log, failed = [], 0

        def ask(u):
            x0, y0, x1, y1 = u["box"]
            m = 10
            crop = img[max(0, int(y0) - m):min(H, int(y1) + m), max(0, int(x0) - m):min(W, int(x1) + m)]
            lines = "\n".join(f"{k}: {t}" for k, t in enumerate(u["texts"], 1))
            return gemini(PROMPT.format(lines=lines), [jpeg(crop, 1600)], f"correct {pid} {u['id']}",
                          model=MODEL, max_out=4000, schema=SCHEMA, thinking="low",
                          est_in=int(1200 + len(lines) / 2 + 700))
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(4) as ex:
            answers = list(ex.map(ask, us))
        for u, (ans, usd) in zip(us, answers):
            if ans is None:
                failed += 1
                log.append(dict(unit=u["id"], failed=True))
                continue
            for e in ans.get("edits", []):
                k = int(e.get("line") or 0) - 1
                if not 0 <= k < len(u["lines"]):
                    st, s = "not-found", -1
                else:
                    st, s = check(e, u["texts"][k].split())
                ids = u["lines"][k][s:s + len(e.get("before", "").split())] if s >= 0 else []
                log.append(dict(unit=u["id"], line=k + 1, before=e.get("before"), after=e.get("after"),
                                kind=e.get("kind"), reason=e.get("reason"), confidence=e.get("confidence"),
                                status=st, word_ids=ids, line_text=u["texts"][k] if 0 <= k < len(u["texts"]) else ""))
        # two applied edits on the same word: keep the first
        seen = set()
        for r in log:
            if r.get("status") == "applied":
                if seen & set(r["word_ids"]):
                    r["status"] = "overlaps"
                seen |= set(r["word_ids"])
        cf.write_text(json.dumps(dict(model=MODEL, units=len(us), failed=failed, edits=log), ensure_ascii=False,
                                 indent=1), encoding="utf-8")
        ap = sum(r.get("status") == "applied" for r in log)
        print(f"{pid}: {len(us)} blocks, {len(log)} proposals, {ap} applied, {failed} failed", flush=True)
    if est:
        print(n_units, "units")


if __name__ == "__main__":
    main(sys.argv[1:])
