"""Experiment 40: Azure's own reading written in the common format (out/a0_azure/<pid>.html), one block per Azure
line, tag by Azure's line kind, data-bbox from its box. The scorer's sanity check (vs Azure it must score ~0) and
the baseline every Gemini approach is compared with (vs truth: what today's reader gives). Free: no Gemini call.

    /home/yassine/inkscript/.venv/bin/python azure_baseline.py
"""
from __future__ import annotations

import html
import json

from common import OUT, sample
from score import azure_doc_lines, units

TAG = {"furniture": ("footer", ' class="furniture"'), "heading": ("h2", ""), "title": ("h1", ""),
       "footnote": ("aside", ' class="footnote"'), "caption": ("p", ' class="caption"'), "verse": ("div", ' class="verse"')}


def page_html(lines, W, H) -> str:
    out, in_table = [], False
    for ln in lines:
        t = (ln.get("text") or "").strip()
        if not t:
            continue
        b = ln.get("box")
        bb = f' data-bbox="{b[0] * 1000 / W:.0f},{b[1] * 1000 / H:.0f},{b[2] * 1000 / W:.0f},{b[3] * 1000 / H:.0f}"' if b else ""
        k = ln.get("kind") or "text"
        if k == "cell":
            if not in_table:
                out.append("<table><tr>")
                in_table = True
            out.append(f"<td{bb}>{html.escape(t)}</td>")
            continue
        if in_table:
            out.append("</tr></table>")
            in_table = False
        tag, attr = TAG.get(k, ("p", ""))
        out.append(f'<{tag}{attr}{bb} dir="auto">{html.escape(t)}</{tag}>')
    if in_table:
        out.append("</tr></table>")
    return "\n".join(out) + "\n"


def main():
    d = OUT / "a0_azure"
    d.mkdir(parents=True, exist_ok=True)
    for u in units("all"):
        if u["unit"] == "sample":
            lines = json.load(open(u["azure_file"]))["lines"]
        else:
            lines, _, _ = azure_doc_lines(u["stem"], u["page"])
        (d / f"{u['page_id']}.html").write_text(page_html(lines, u["width"], u["height"]), encoding="utf-8")
    print("wrote", d)


if __name__ == "__main__":
    main()
