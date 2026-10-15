"""Experiment 40, approach A: "page image in, finished page out".

One call per page: the page image alone -> gemini-4-argon -> the whole page as the semantic HTML of FORMAT.md.

    /home/yassine/inkscript/.venv/bin/python A_oneshot.py VARIANT [--pages pid ...] [--subset]

VARIANT (thinking level / media resolution / image size sent):
    lo_hi    thinking low,  media resolution high,       image long side 3000 px
    hi_hi    thinking high, media resolution high,       image long side 3000 px
    lo_uh    thinking low,  media resolution ultra_high, image long side 3000 px
    lo_med   thinking low,  media resolution medium,     image long side 3000 px
    md_uh    thinking medium, media resolution ultra_high
Outputs: out/A_oneshot/<VARIANT>/<pid>.html (+ <pid>.meta.json: usd, secs, tokens), written as each page finishes;
a rerun skips finished pages (and the client's cache makes repeats free). Every call is tagged
"A_oneshot_<VARIANT>_<pid>" and refused if it could take tags "A_oneshot" past $3.50.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import OUT, gemini, page_ids, page_image_path, page_jpeg, spent, strip_fences  # noqa: E402

ROOT = OUT / "A_oneshot"
SUBCAP = ("A_oneshot", 3.5)
SUBSET = ["0018-010-003-002_p003", "0355-000-002-006_p017", "0747-001-003-001_p006", "0474-008-013-001_p036",
          "bd_2502-000-041-029_p021"]

VARIANTS = {
    "lo_hi": dict(thinking="low", resolution="high", max_side=3000, est_img=1200),
    "hi_hi": dict(thinking="high", resolution="high", max_side=3000, est_img=1200),
    "lo_uh": dict(thinking="low", resolution="ultra_high", max_side=3000, est_img=2400),
    "lo_med": dict(thinking="low", resolution="medium", max_side=3000, est_img=700),
    "md_uh": dict(thinking="medium", resolution="ultra_high", max_side=3000, est_img=2400),
}

PROMPT = r"""You are digitising one scanned page of an Arabic academic journal (it may also contain French or English).
Transcribe the WHOLE page into semantic HTML, exactly as printed.

TEXT RULES (most important)
- Copy every word exactly as printed, in reading order. Never correct spelling or grammar, never modernise, never
  complete a cut-off word or sentence, never translate, never summarise, never add anything that is not printed.
- Keep every vowel mark (fatha, damma, kasra, shadda, sukun, tanwin, dagger alif) exactly where it is printed; do
  not add vowel marks that are not printed. Leave out tatweel (kashida) stretching.
- Digits as printed: Arabic-Indic digits (٠١٢٣٤٥٦٧٨٩) stay Arabic-Indic, Western digits (0-9) stay Western.
- Text in Latin script (French, English, formulas' variable names) is copied in Latin script; Arabic stays Arabic.
- If a word is illegible, write your best reading of the visible letters; do not invent a plausible substitute.
- A word cut at the page edge or broken by a hyphen stays as printed.
- Each piece of text appears once. Do not repeat lines.

STRUCTURE (use only these elements)
- Running header / footer / page number: <header class="furniture">...</header>, <footer class="furniture">...</footer>
- Title and section headings: <h1>, <h2>, <h3>
- Body paragraphs: <p> (one per printed paragraph; join the lines of a paragraph with spaces)
- Numbered / bulleted lists: <ol> / <ul> with <li> (keep the printed number or bullet as text at the start of the li)
- Bibliography / reference list: <ol class="references"><li>...</li></ol>
- Footnotes at the bottom of the page: <aside class="footnote" id="fnN">...</aside> (keep the printed number in the
  text); the marker in the body: <sup><a href="#fnN">N</a></sup> placed exactly where it is printed.
- Poetry: one <div class="verse"> per verse line, with its two half-lines as
  <span class="hemistich">...</span><span class="hemistich">...</span> (right half-line first).
- Tables: an HTML <table> with <tr>, <th>/<td>, rowspan/colspan as printed; caption in <caption>.
- Equations: LaTeX. Inline: <span class="math">\(...\)</span>. Display: <div class="equation"><span class="math">\[...\]</span></div>.
- Figures / pictures / charts: <figure data-bbox="..."><figcaption>printed caption</figcaption></figure> (do not
  describe the picture; transcribe printed words inside a chart only if they are clearly text).
- Anything else: <div class="other">.

ATTRIBUTES
- Every block element (header, footer, h1-h3, p, li, aside, div.verse, div.equation, table, figure, div.other) gets
  data-bbox="x0,y0,x1,y1": its box on the page in 0-1000 coordinates (x from the LEFT edge, y from the TOP).
- dir="rtl" lang="ar" on Arabic blocks; dir="ltr" lang="fr" or lang="en" on Latin-script blocks.
- Multi-column pages: read each column fully (right column first for Arabic) before the next.

Output only the HTML fragment (no <html>/<head>, no Markdown fences, no comments)."""


def run_page(variant: str, pid: str, force: bool = False) -> dict:
    v = VARIANTS[variant]
    d = ROOT / variant
    d.mkdir(parents=True, exist_ok=True)
    out, meta = d / f"{pid}.html", d / f"{pid}.meta.json"
    if out.exists() and meta.exists() and not force:
        return json.loads(meta.read_text())
    page_image_path(pid)                 # renders a whole-document page on first use
    img = page_jpeg(pid, max_side=v["max_side"], quality=90)
    info: dict = {}
    est_in = v["est_img"] + len(PROMPT) // 3 + 200
    ans, usd = gemini(PROMPT, images=[img], tag=f"A_oneshot_{variant}_{pid}", json_out=False, max_out=32000 if v["thinking"] == "high" else 12000,
                      thinking=v["thinking"], resolution=v["resolution"], est_in=est_in, subcap=SUBCAP, info=info)
    m = dict(pid=pid, variant=variant, usd=round(usd, 6), secs=round(info.get("secs", 0.0), 1),
             tin=info.get("tin"), tout=info.get("tout"), think=info.get("think"), finish=info.get("finish"),
             cached=info.get("cached", False), ok=ans is not None, error=info.get("error"))
    if ans is None:
        print(f"  {variant} {pid}: no answer ({m['finish'] or m['error']}) ${usd:.4f}", flush=True)
        if usd:      # paid and truncated: record the cost; no html (counts as read empty)
            (d / f"{pid}.failed.json").write_text(json.dumps(m))
        return m
    out.write_text(strip_fences(ans), encoding="utf-8")
    if m["cached"] and meta.exists():
        return json.loads(meta.read_text())
    meta.write_text(json.dumps(m))
    print(f"  {variant} {pid}: ${usd:.4f} {m['secs']}s in={m['tin']} out={m['tout']} (think {m['think']})"
          f"  A_oneshot total ${spent('A_oneshot'):.3f}", flush=True)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant", choices=list(VARIANTS))
    ap.add_argument("--pages", nargs="*", default=None)
    ap.add_argument("--subset", action="store_true")
    ap.add_argument("--docs", action="store_true", help="every page of the sample's whole documents")
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    if a.docs:
        from score import units
        pids = [u["page_id"] for u in units("docs")]
    else:
        pids = a.pages or (SUBSET if a.subset else page_ids())
    with ThreadPoolExecutor(min(4, a.threads)) as ex:
        ms = list(ex.map(lambda p: run_page(a.variant, p), pids))
    tot = sum(m["usd"] for m in ms if not m.get("cached"))
    print(f"{a.variant}: {sum(m['ok'] for m in ms)}/{len(ms)} pages, this run ${tot:.3f}; "
          f"A_oneshot total ${spent('A_oneshot'):.3f}")


if __name__ == "__main__":
    main()
