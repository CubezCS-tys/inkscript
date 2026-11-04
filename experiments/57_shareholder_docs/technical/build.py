"""Build the technical documentation PDF from doc.html.

    <pw-venv>/bin/python build.py            # -> ../out/Mandumah_Citation_Index_Technical_Documentation.pdf
                                              #    + out/pages/page-NN.png for review

Steps: fill the contents list and Appendix C (from table_counts.json) into build/doc_built.html; print it with
Chromium (Playwright page.pdf, A4); find the page each section starts on with pypdfium2 (the repo's .venv); write
those page numbers into the contents; print again; render every page to PNG for a look.
Read-only on all data: table_counts.json was counted once from the release copy (opened read-only).
"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "out"
PDF = OUT / "Mandumah_Citation_Index_Technical_Documentation.pdf"
CHROME = "/home/appuser/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
REPO_PY = "/home/appuser/inkscript/.venv/bin/python"
GROUP_NAMES = {"provenance": "Provenance and identity", "ink": "Ink", "readings": "Readings",
               "bibliographic": "Bibliographic", "people": "People and institutions", "citations": "Citations",
               "quality": "Quality", "outside": "Outside (AI-Search ties)"}


def table_list() -> str:
    d = json.loads((HERE / "table_counts.json").read_text())
    c = d["counts"]
    rows = []
    for g, tabs in d["groups"].items():
        cells = ", ".join(f"<code>{t}</code>&nbsp;{c[t]:,}" if t in c else f"<code>{t}</code>" for t in tabs)
        rows.append(f"<tr><td>{GROUP_NAMES.get(g, g)} ({len(tabs)})</td><td>{cells}</td></tr>")
    rows.append("<tr><td>Builder report</td><td><code>reconciliation_v46</code>&nbsp;"
                f"{c.get('reconciliation_v46', 0):,} (comparison with platform v1)</td></tr>")
    return ('<table class="long"><thead><tr><th style="width:20%">Group (tables)</th><th>Tables and rows</th></tr></thead>'
            + "".join(rows) + "</table>")


def toc(pages: dict) -> str:
    out = []
    for hid, title in re.findall(r'<h1 id="(s\w+)"[^>]*data-toc="([^"]+)"', SRC):
        pg = pages.get(hid, "")
        out.append(f'<li><span class="t">{html.escape(title)}</span><span class="dots"></span>'
                   f'<span class="pg">{pg}</span></li>')
        if SUBS.get(hid):
            out.append('<li class="sub">' + " · ".join(html.escape(x) for x in SUBS[hid]) + "</li>")
    return "\n".join(out)


SRC = (HERE / "doc.html").read_text()
SUBS = {}
# sub-entries: the h2s of each section, shown under it in the contents
for m in re.finditer(r'<h1 id="(s\w+)".*?(?=<h1 id=|</body>)', SRC, re.S):
    hs = re.findall(r"<h2>(.*?)</h2>", m.group(0))
    SUBS[m.group(1)] = [re.sub(r"<[^>]+>", "", h) for h in hs][:9]


def render(pages: dict) -> None:
    s = SRC.replace('<ol id="toclist"></ol>', f'<ol id="toclist">{toc(pages)}</ol>')
    s = s.replace('<div id="tablelist"></div>', table_list())
    f = HERE / "doc_built.html"          # beside doc.html so img/ resolves
    f.write_text(s)
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        pg = b.new_page()
        pg.goto(f.as_uri(), wait_until="networkidle")
        pg.wait_for_timeout(800)
        pg.pdf(path=str(PDF), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()


FIND = r'''
import sys, json, pypdfium2 as pdfium
pdf = pdfium.PdfDocument(sys.argv[1]); keys = json.loads(sys.argv[2]); found = {}
texts = []
for i in range(len(pdf)):
    tp = pdf[i].get_textpage(); texts.append(tp.get_text_range()); tp.close()
start = 2   # after the cover and the contents; each heading searched from the previous one on
for hid, title in keys.items():
    for i in range(start, len(texts)):
        if title in " ".join(texts[i].split()):
            found[hid] = i + 1; start = i; break
print(json.dumps({"n": len(pdf), "pages": found}))
'''

SHOT = r'''
import sys, zlib, struct, pypdfium2 as pdfium
from pathlib import Path
def png(path, w, h, rows):
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    raw = b"".join(b"\x00" + r for r in rows)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
pdf = pdfium.PdfDocument(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
for f in out.glob("page-*.png"): f.unlink()
for i in range(len(pdf)):
    bm = pdf[i].render(scale=1.3, rev_byteorder=True)   # RGB(x) order
    buf = bytes(bm.buffer); w, h, st, n = bm.width, bm.height, bm.stride, bm.n_channels
    rows = []
    for y in range(h):
        r = buf[y*st:y*st+w*n]
        rows.append(r if n == 3 else b"".join(r[k:k+3] for k in range(0, len(r), n)))
    png(out / f"page-{i+1:02d}.png", w, h, rows)
print(len(pdf))
'''


def main():
    render({})
    keys = {}
    for hid, title in re.findall(r'<h1 id="(s\w+)"[^>]*data-toc="([^"]+)"', SRC):
        # the heading as printed (first ~4 words), searched after the contents
        h1 = re.search(rf'<h1 id="{hid}"[^>]*>(.*?)</h1>', SRC, re.S).group(1)
        keys[hid] = " ".join(re.sub(r"<[^>]+>", "", h1).split())[:40]
    r = json.loads(subprocess.check_output([REPO_PY, "-c", FIND, str(PDF), json.dumps(keys)]))
    print("pages:", r["n"], r["pages"])
    missing = set(keys) - set(r["pages"])
    if missing:
        print("not found:", missing)
    render(r["pages"])
    r2 = json.loads(subprocess.check_output([REPO_PY, "-c", FIND, str(PDF), json.dumps(keys)]))
    if r2["pages"] != r["pages"]:
        print("page numbers moved; rendering once more", r2["pages"])
        render(r2["pages"])
    if "--no-png" not in sys.argv:
        n = subprocess.check_output([REPO_PY, "-c", SHOT, str(PDF), str(OUT / "tech_pages")]).decode().strip()
        print("png pages:", n)
    print(PDF, PDF.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
