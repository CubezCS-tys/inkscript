"""Typeset test sentences in the given installed font families with LibreOffice and save a PNG: specimen.py out.png "Family A" "Family B" ..."""
import sys, subprocess, os, fitz
out = os.path.abspath(sys.argv[1]); fams = sys.argv[2:]; d = os.path.dirname(out); stem = os.path.splitext(os.path.basename(out))[0]
lines = ["هذا نص جديد مكتوب بخط الكتاب القديم", "محمد على سليمان فى بيت كبير", "لئن كان المعجم قد نشأ بالمشرق", "السلام عليكم ورحمة الله وبركاته", "ثم جاء الشيخ صالح بعد غروب الشمس"]
html = '<html><head><meta charset="utf-8"></head><body dir="rtl" style="font-size:30pt; line-height:1.45">' + "".join(
    "".join('<p style="font-family:&quot;%s&quot;; margin:0">%s</p>' % (f, l) for f in fams) + '<p style="font-size:8pt">&nbsp;</p>' for l in lines) + "</body></html>"
open(f"{d}/{stem}.html", "w", encoding="utf-8").write(html)
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", d, f"{d}/{stem}.html"], capture_output=True, timeout=180)
fitz.open(f"{d}/{stem}.pdf")[0].get_pixmap(dpi=120).save(out)
