"""Experiment 103: the bidi tools behind the mixed-direction target fix.

Two displays of a logical string in a right-to-left paragraph (the lab's PDFs are /Direction /R2L; experiment 97's
rule is "typed in logical order, so that a Chromium RTL paragraph shows it as printed"):

  fribidi_display(s)  -> (V, v2l): the visual string left to right, bracket-like characters at odd levels mirrored
                         (so V holds the glyph SHAPES seen on the page), and for each visual position the logical
                         index it came from.  libfribidi 1.0 (system library, ctypes; Unicode bidi with brackets N0).
  chrome_display(ss)  -> for each string, its characters' x positions as laid out by headless Chromium (the
                         repo's headless shell, --no-sandbox, local file only, profile and temp inside out/).
                         This is the judge; fribidi is the fast stand-in, and selftest103 measures their agreement.

Both ignore combining marks for order comparisons (zero-width, they ride on their base letter).
"""
from __future__ import annotations

import ctypes
import html
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
CHROME = Path.home() / ".cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell"

_fb = ctypes.CDLL("libfribidi.so.0")
_fb.fribidi_log2vis.restype = ctypes.c_int8
_fb.fribidi_get_mirror_char.restype = ctypes.c_int
PAR_RTL = 0x111          # FRIBIDI_PAR_RTL = FRIBIDI_TYPE_RTL
PAR_LTR = 0x110


def _mirror(ch: str) -> str:
    out = ctypes.c_uint32(0)
    if _fb.fribidi_get_mirror_char(ctypes.c_uint32(ord(ch)), ctypes.byref(out)):
        return chr(out.value)
    return ch


def fribidi_display(s: str, rtl: bool = True):
    """(V, v2l, levels): visual string L->R with odd-level mirroring, visual->logical index map, logical levels."""
    n = len(s)
    if n == 0:
        return "", [], []
    Arr = ctypes.c_uint32 * n
    src = Arr(*[ord(c) for c in s])
    vis = Arr()
    l2v = (ctypes.c_int * n)()
    v2l = (ctypes.c_int * n)()
    lev = (ctypes.c_int8 * n)()
    pd = ctypes.c_uint32(PAR_RTL if rtl else PAR_LTR)
    r = _fb.fribidi_log2vis(src, n, ctypes.byref(pd), vis, l2v, v2l, lev)
    if r == 0:
        raise RuntimeError("fribidi_log2vis failed")
    order = list(v2l)
    V = "".join(_mirror(s[i]) if (lev[i] % 2) else s[i] for i in order)
    return V, order, list(lev)


def is_mark(c: str) -> bool:
    return unicodedata.category(c) in ("Mn", "Me", "Cf")


def base_visual(s: str, rtl: bool = True) -> str:
    """The display as shapes left to right, marks dropped: what an order comparison looks at."""
    V, order, _ = fribidi_display(s, rtl)
    return "".join(c for c in V if not is_mark(c))


def same_display(a: str, b: str) -> bool:
    return base_visual(a) == base_visual(b)


# ------------------------------------------------------------------------------------------------ Chromium

_PAGE_HEAD = """<html><head><meta charset="utf-8"><style>
body{margin:0} div{font-family:"Noto Naskh Arabic","Noto Sans Arabic",serif;font-size:24px;white-space:pre;
direction:rtl;text-align:right;width:6000px}</style></head><body>
"""
_PAGE_TAIL = """<pre id="out"></pre><script>
const res=[];for(const d of document.querySelectorAll('div.t')){const t=d.firstChild;const xs=[];
if(t){for(let i=0;i<t.length;i++){const r=document.createRange();r.setStart(t,i);r.setEnd(t,i+1);
const b=r.getBoundingClientRect();xs.push([Math.round(b.left*10)/10,Math.round(b.width*10)/10]);}}res.push(xs);}
document.getElementById('out').textContent=JSON.stringify(res);</script></body></html>"""


def chrome_display(strings, rtl: bool = True, batch: int = 2000):
    """For each string: list of (left, width) per UTF-16-free character index (all our text is in the BMP)."""
    tmp = OUT / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMPDIR=str(tmp))
    out = []
    for k in range(0, len(strings), batch):
        part = strings[k:k + batch]
        p = tmp / f"chrome_{os.getpid()}.html"
        body = "".join(f'<div class="t" dir="{"rtl" if rtl else "ltr"}">{html.escape(s)}</div>\n' for s in part)
        p.write_text(_PAGE_HEAD + body + _PAGE_TAIL, encoding="utf-8")
        r = subprocess.run(["nice", "-n", "19", str(CHROME), "--no-sandbox", "--disable-gpu", "--headless",
                            f"--user-data-dir={OUT / 'chrome'}", "--virtual-time-budget=60000", "--dump-dom",
                            p.as_uri()], capture_output=True, text=True, env=env, timeout=600)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout, re.S)
        if not m:
            raise RuntimeError("chromium gave no output: " + r.stderr[-500:])
        got = json.loads(html.unescape(m.group(1)))
        assert len(got) == len(part), (len(got), len(part))
        for s, xs in zip(part, got):
            assert len(xs) == len(s), "non-BMP character?"
        out.extend(got)
    return out


_ARL = re.compile("[\u0620-\u064A\u066E-\u06D3\u06FA-\u06FF]")


def chrome_base_order(s: str, xs, skip_arabic: bool = False) -> list[int]:
    """Logical indices of the non-mark, non-space characters, sorted left to right by Chromium's x centre.
    skip_arabic: leave Arabic letters out (Chromium gives every letter of a ligature the ligature's box, so their
    order inside a word is not measurable; the order of runs and punctuation is)."""
    idx = [i for i, c in enumerate(s) if not is_mark(c) and not c.isspace() and xs[i][1] > 0
           and not (skip_arabic and _ARL.match(c))]
    return sorted(idx, key=lambda i: xs[i][0] + xs[i][1] / 2)


def fribidi_base_order(s: str, skip_arabic: bool = False) -> list[int]:
    _, order, _ = fribidi_display(s)
    return [i for i in order if not is_mark(s[i]) and not s[i].isspace() and not (skip_arabic and _ARL.match(s[i]))]


def chrome_visual_shapes(s: str, xs) -> str:
    """Chromium's display as a string of shapes, left to right: characters at an RTL position that are mirrored
    are given their mirror, using fribidi's level (Chromium does not expose the level; the mirror pairs are the
    same table).  Used only to compare two strings' displays in Chromium: both get the same treatment."""
    _, _, lev = fribidi_display(s)
    return "".join(_mirror(s[i]) if lev[i] % 2 else s[i] for i in chrome_base_order(s, xs))
