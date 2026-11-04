"""Render business.html to the PDF and each PDF page to PNG for checking.

    <playwright venv>/bin/python build.py            # -> ../out/Mandumah_Citation_Index_Business_Overview.pdf
    PYTHONPATH=<a venv with Pillow> /home/appuser/inkscript/.venv/bin/python build.py --png  # -> out/pages/page-NN.png
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDF = HERE.parent / "out" / "Mandumah_Citation_Index_Business_Overview.pdf"
CHROME = "/home/appuser/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"


def pdf():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        pg = b.new_page()
        pg.goto((HERE / "business.html").as_uri(), wait_until="load")
        pg.wait_for_timeout(800)
        pg.pdf(path=str(PDF), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()
    print(PDF)


def png():
    import pypdfium2 as pdfium
    out = HERE / "out" / "pages"
    out.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(PDF))
    for i in range(len(doc)):
        doc[i].render(scale=1.4).to_pil().save(out / f"page-{i + 1:02d}.png")
    print(len(doc), "pages")


if __name__ == "__main__":
    png() if "--png" in sys.argv else pdf()
