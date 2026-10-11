"""Hand-made test masters with tables and equations (experiment 35).

The 205 archive masters have no structured tables and no equations; the future Kraken + VLM stage will write them.
These two small articles are written here by hand, in the shape research/02_formats.md proposes, so every edition
writer can be tested on them now:

    test-0001-table-math    2 A5 pages: title, author, heading, footnote, a Latin citation, an inline formula,
                            two display formulas (MathML dir="rtl" + LaTeX + scan crop), a table with a header row,
                            a colspan and rowspans, cells in reading order (rightmost column first)
    test-0002-two-columns   1 A4 page: two columns read right then left, an inline formula, a 4-column x 5-row
                            table with a row-header column and merged header cells, a footnote

They are NOT archive pages. How a "scan" is made: each page is typeset as HTML in Chromium (Noto Naskh Arabic, a
greyish paper, MathML for the formulas), every word's box is measured in the browser (Range.getClientRects), the
page is screenshot at 300 dpi, given a little noise and blur, and stored as a grey JPEG at 200 dpi inside
<id>.pdf (as the archive's faithful PDFs hold the scan at about 200 dpi while ALTO counts 300-dpi pixels). The
ALTO is written from the measured boxes; the JATS by hand from the same spec below.

    .venv/bin/python experiments/35_edition/testdocs/make_testdocs.py [OUT_DIR]     # default tests/fixtures/edition

Needs a Python with playwright (PW_PYTHON, default the scratch venv of experiment 35) for the browser step.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[3]
PW_PYTHON = os.environ.get(
    "PW_PYTHON", "/tmp/claude-1000/-home-yassine-inkscript/ed816869-9be5-4008-b630-480b426fc462/scratchpad/pw/bin/python")
DSF = 3                       # CSS px -> 300-dpi pixels (CSS px is 1/96 in; 96 * 3.125 = 300; 3 is close: 288 dpi)
SIZES = {"A5": (583, 827), "A4": (827, 1170)}     # CSS px at 96 dpi -> x3 = 1749x2481 / 2481x3510 pixels
DPI = 96 * DSF                # the ALTO pixel unit's resolution (288 dpi)
JPEG_SCALE = 2 / 3            # the scan stored in the PDF at 2/3 of the ALTO pixels (192 dpi)
MML = "http://www.w3.org/1998/Math/MathML"

# ------------------------------------------------------------------------------------------------- the spec
# inline parts: "text" | ("fn", rid, label) | ("math", mathml_inner, tex)


def M(inner):
    return inner


EQ1 = ('<mi>س</mi><mo>=</mo><mrow><mo>(</mo><mi>أ</mi><mo>+</mo><mi>ب</mi><mo>)</mo></mrow><mo>÷</mo><mn>٢</mn>',
       r"\text{س} = (\text{أ} + \text{ب}) \div ٢")
EQ2 = ('<msup><mi>ع</mi><mn>٢</mn></msup><mo>=</mo><mfrac><mrow><munderover><mo>∑</mo><mrow><mi>ر</mi><mo>=</mo>'
       '<mn>١</mn></mrow><mi>ن</mi></munderover><msup><mrow><mo>(</mo><msub><mi>س</mi><mi>ر</mi></msub><mo>−</mo>'
       '<mi>م</mi><mo>)</mo></mrow><mn>٢</mn></msup></mrow><mi>ن</mi></mfrac>',
       r"\text{ع}^{٢} = \frac{\sum_{\text{ر}=١}^{\text{ن}} (\text{س}_{\text{ر}} - \text{م})^{٢}}{\text{ن}}")
IM1 = ('<mi>م</mi><mo>=</mo><mrow><mo>مج</mo><mi>س</mi></mrow><mo>÷</mo><mi>ن</mi>',
       r"\text{م} = \text{مج}\,\text{س} \div \text{ن}")
IM2 = ('<mi>ن</mi><mo>=</mo><mi>ك</mi><mo>÷</mo><mi>م</mi><mo>×</mo><mn>١٠٠</mn>',
       r"\text{ن} = \text{ك} \div \text{م} \times ١٠٠")


def T(text, th=False, colspan=1, rowspan=1, scope=None):
    return dict(t=text, th=th, colspan=colspan, rowspan=rowspan, scope=scope)


TABLE1 = [("thead", [T("الفئة", True, rowspan=2), T("عدد الطلاب", True, colspan=2), T("النسبة", True, rowspan=2)]),
          ("thead", [T("الصف الأول", True), T("الصف الثاني", True)]),
          ("tbody", [T("ذكور", True, scope="row"), T("٤٠"), T("٣٢"), T("٪٦٠")]),
          ("tbody", [T("إناث", True, scope="row"), T("٢٦"), T("٢٢"), T("٪٤٠")]),
          ("tbody", [T("المجموع", True, scope="row"), T("٦٦"), T("٥٤"), T("٪١٠٠")])]

TABLE2 = [("thead", [T("المادة", True, rowspan=2), T("متوسط الدرجات", True, colspan=2), T("الفرق", True, rowspan=2)]),
          ("thead", [T("القبلي", True), T("البعدي", True)]),
          ("tbody", [T("الرياضيات", True, scope="row"), T("٥٤٫٢"), T("٧١٫٨"), T("١٧٫٦")]),
          ("tbody", [T("العلوم", True, scope="row"), T("٥٨٫٠"), T("٦٩٫٤"), T("١١٫٤")]),
          ("tbody", [T("اللغة العربية", True, scope="row"), T("٦٢٫٥"), T("٧٠٫١"), T("٧٫٦")]),
          ("tbody", [T("اللغة الإنجليزية", True, scope="row"), T("٤٩٫٣"), T("٦٠٫٢"), T("١٠٫٩")]),
          ("tbody", [T("المتوسط العام", True, scope="row"), T("٥٦٫٠"), T("٦٧٫٩"), T("١١٫٩")])]

DOCS = {
    "test-0001-table-math": dict(
        size="A5", title="أثر التعلم النشط في تحصيل طلاب المرحلة الثانوية في الرياضيات",
        author="د. سامي عبد الله الخطيب", fpage="45", lpage="46",
        pages=[
            [("pagenum", "p1b1", "٤٥"),
             ("title", "p1b2"),
             ("author", "p1b3"),
             ("heading", "p1b4", "أولاً: منهج الدراسة"),
             ("p", "p1b5", ["اتبعت الدراسة المنهج شبه التجريبي، وطبقت أدواتها على عينة من ١٢٠ طالباً في العام "
                            "الدراسي 2019/2020، على نحو ما اقترحه هيك ", "(Hake, 1998)", " في قياس الكسب ",
                            ("fn", "fn-p1-1", "(١)"), "."]),
             ("p", "p1b6", ["ويحسب متوسط الدرجات بالعلاقة ", ("math",) + IM1,
                            " حيث مج مجموع الدرجات و ن عدد الطلاب، ثم يجمع الأثر في المعادلة الآتية:"]),
             ("eq", "p1eq1", "(٣)") + EQ1,
             ("p", "p1b7", ["ويستخرج الانحراف المعياري للدرجات من العلاقة:"]),
             ("eq", "p1eq2", "(٤)") + EQ2,
             ("fn", "p1b8", "fn-p1-1", "١", "أجريت الدراسة بإشراف وزارة التربية والتعليم، تقرير رقم 17-B.")],
            [("pagenum", "p2b1", "٤٦"),
             ("heading", "p2b2", "ثانياً: عينة الدراسة"),
             ("p", "p2b3", ["توزعت العينة على صفين دراسيين، ويبين الجدول الآتي أعداد الطلاب ونسبهم بحسب "
                            "الجنس والصف:"]),
             ("table", "p2t1", "p2b4", "جدول (١): توزيع عينة الدراسة بحسب الجنس والصف", TABLE1),
             ("p", "p2b5", ["ويتضح من الجدول أن نسبة الذكور في العينة أعلى من نسبة الإناث، وأن الصف الأول "
                            "أكثر عدداً من الصف الثاني في الفئتين."])],
        ]),
    "test-0002-two-columns": dict(
        size="A4", title="تحصيل الطلاب قبل البرنامج التدريبي وبعده في أربع مواد دراسية",
        author="أ. د. ليلى حسن المصري", fpage="127", lpage="127",
        pages=[
            [("pagenum", "p1b1", "١٢٧"),
             ("title", "p1b2"),
             ("author", "p1b3"),
             ("columns",
              [("heading", "p1b4", "مقدمة"),
               ("p", "p1b5", ["يهدف هذا البحث إلى قياس أثر برنامج تدريبي قصير في تحصيل الطلاب في أربع مواد "
                              "دراسية، وقد طبق البرنامج مدة ستة أسابيع في ثلاث مدارس حكومية ",
                              ("fn", "fn-p1-1", "(١)"), "."]),
               ("p", "p1b6", ["واعتمد البحث على اختبارين متكافئين، قبلي وبعدي، أعدهما فريق من المعلمين "
                              "وحكمهما عدد من المختصين في القياس والتقويم."])],
              [("heading", "p1b7", "النتائج"),
               ("p", "p1b8", ["حسبت نسبة النجاح في كل مادة بالعلاقة ", ("math",) + IM2,
                              " حيث ك عدد الناجحين و م عدد الطلاب في المادة."]),
               ("p", "p1b9", ["ويعرض الجدول الآتي متوسطات الدرجات في الاختبارين والفرق بينهما في كل مادة، "
                              "مع المتوسط العام للمواد الأربع."])]),
             ("table", "p1t1", "p1b10", "جدول (٢): متوسطات درجات الطلاب في الاختبارين القبلي والبعدي", TABLE2),
             ("p", "p1b11", ["وتدل النتائج على تحسن واضح في جميع المواد، وكان أكبر الفروق في الرياضيات وأصغرها في "
                             "اللغة العربية."]),
             ("fn", "p1b12", "fn-p1-1", "١", "المدارس هي: مدرسة النور، ومدرسة الأمل، ومدرسة الفجر (العام 2021).")],
        ]),
}


def grid_ids(page, tnum, rows):
    """Each cell's id p<page>t<n>c<row><col> from its place in the grid (spans taken into account)."""
    taken, out = set(), []
    for r, (_, cells) in enumerate(rows):
        c, ids = 0, []
        for cell in cells:
            while (r, c) in taken:
                c += 1
            ids.append(f"p{page}t{tnum}c{r}{c}")
            for dr in range(cell["rowspan"]):
                for dc in range(cell["colspan"]):
                    taken.add((r + dr, c + dc))
            c += cell["colspan"]
        out.append(ids)
    return out


# ------------------------------------------------------------------------------------------------- the scan (HTML)

CSS = """
@font-face { font-family: Scan; src: local("Noto Naskh Arabic"); }
html, body { margin: 0; padding: 0; }
body { width: %(w)dpx; height: %(h)dpx; background: #e8e4d8; color: #1e1b16; font-family: "Noto Naskh Arabic", serif;
       font-size: %(fs)spx; line-height: 1.72; overflow: hidden; }
.page { position: relative; box-sizing: border-box; width: 100%%; height: 100%%; padding: %(pad)s; }
.pagenum { position: absolute; top: 22px; left: 0; right: 0; text-align: center; font-size: 0.9em; }
.title { text-align: center; font-weight: bold; font-size: 1.55em; line-height: 1.5; margin: 0 6%% 0.4em; }
.author { text-align: center; font-size: 1.05em; margin: 0 0 1.1em; }
h2 { font-size: 1.12em; font-weight: bold; margin: 0.6em 0 0.25em; }
p { margin: 0 0 0.35em; text-align: justify; text-indent: 1.2em; }
.eq { display: flex; align-items: center; justify-content: center; position: relative; margin: 0.4em 0 0.5em;
      direction: rtl; }
.eq .lab { position: absolute; left: 0; }
math { font-family: "Noto Naskh Arabic", "Latin Modern Math", "STIX Two Math", serif; }
math[display=block] { font-size: 1.15em; }
.cols { display: grid; grid-template-columns: 1fr 1fr; column-gap: 26px; }
.cols > div { border-left: 0; }
.cols > div:first-child { border-left: 1px solid #555; padding-left: 13px; }
table { border-collapse: collapse; margin: 0.3em auto 0.6em; font-size: 0.92em; line-height: 1.45; }
th, td { border: 1px solid #333; padding: 2px 9px; text-align: center; }
th { font-weight: bold; }
.caption { text-align: center; font-weight: bold; font-size: 0.95em; text-indent: 0; margin: 0.4em 0 0.1em; }
.fns { position: absolute; bottom: %(fnb)dpx; left: %(side)dpx; right: %(side)dpx; border-top: 1px solid #444;
       padding-top: 4px; font-size: 0.82em; }
.fns p { text-indent: 0; }
.latin { font-family: "DejaVu Serif", serif; font-size: 0.85em; }
"""


def inline_html(parts):
    out = []
    for p in parts:
        if isinstance(p, str):
            cls = ' class="latin" dir="ltr"' if p.isascii() and p.strip() else ""
            out.append(f"<span{cls}>{escape(p)}</span>" if cls else escape(p))
        elif p[0] == "fn":
            out.append(f'<sup class="fnref">{escape(p[2])}</sup>')
        elif p[0] == "math":
            out.append(f'<math class="imath" dir="rtl">{p[1]}</math>')
    return "".join(out)


def page_html(doc, n, items):
    w, h = SIZES[doc["size"]]
    a4 = doc["size"] == "A4"
    css = CSS % dict(w=w, h=h, fs="15.5" if a4 else "13.4", pad="58px 56px 40px 56px" if a4 else "50px 44px 30px 44px",
                     fnb=34 if a4 else 26, side=56 if a4 else 44)
    tnum = 0

    def el(it):
        nonlocal tnum
        k = it[0]
        if k == "pagenum":
            return f'<div class="pagenum" data-b="{it[1]}" data-role="pageNumber">{escape(it[2])}</div>'
        if k == "title":
            return f'<div class="title" data-b="{it[1]}" data-role="title">{escape(doc["title"])}</div>'
        if k == "author":
            return f'<div class="author" data-b="{it[1]}" data-role="author">{escape(doc["author"])}</div>'
        if k == "heading":
            return f'<h2 data-b="{it[1]}" data-role="sectionHeading">{escape(it[2])}</h2>'
        if k == "p":
            return f'<p data-b="{it[1]}" data-role="body">{inline_html(it[2])}</p>'
        if k == "eq":
            return (f'<div class="eq" data-ill="{it[1]}"><math display="block" dir="rtl">{it[3]}</math>'
                    f'<span class="lab">{escape(it[2])}</span></div>')
        if k == "table":
            tnum += 1
            ids = grid_ids(n, tnum, it[4])
            rows = []
            for (sec, cells), rid in zip(it[4], ids):
                tds = "".join(
                    f'<{"th" if c["th"] else "td"} data-b="{i}" data-role="body"'
                    f'{" colspan=%d" % c["colspan"] if c["colspan"] > 1 else ""}'
                    f'{" rowspan=%d" % c["rowspan"] if c["rowspan"] > 1 else ""}>{escape(c["t"])}'
                    f'</{"th" if c["th"] else "td"}>' for c, i in zip(cells, rid))
                rows.append(f"<tr>{tds}</tr>")
            return (f'<div data-table="{it[1]}"><p class="caption" data-b="{it[2]}" data-role="body">'
                    f'{escape(it[3])}</p><table dir="rtl">{"".join(rows)}</table></div>')
        if k == "columns":
            return ('<div class="cols"><div>' + "".join(el(x) for x in it[1]) + "</div><div>"
                    + "".join(el(x) for x in it[2]) + "</div></div>")
        if k == "fn":
            return (f'<div class="fns"><p data-b="{it[1]}" data-role="footnote">({escape(it[3])}) '
                    f'{inline_html([it[4]])}</p></div>')
        raise ValueError(k)
    body = "".join(el(it) for it in items)
    return (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{css}</style></head>'
            f'<body><div class="page">{body}</div></body></html>')


MEASURE_JS = r"""
() => {
  const R = r => [r.left, r.top, r.width, r.height];
  const out = {blocks: [], ills: [], tables: []};
  function words(el) {
    const ws = [];
    const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = tw.nextNode())) {
      const s = node.data; const re = /\S+/g; let m;
      const math = !!(node.parentElement && node.parentElement.closest('math.imath'));
      while ((m = re.exec(s))) {
        const r = document.createRange(); r.setStart(node, m.index); r.setEnd(node, m.index + m[0].length);
        const b = r.getBoundingClientRect();
        if (b.width > 0) ws.push({t: m[0], b: R(b), math});
      }
    }
    return ws;
  }
  document.querySelectorAll('[data-b]').forEach(el => {
    out.blocks.push({id: el.dataset.b, role: el.dataset.role, cell: /^(TD|TH)$/.test(el.tagName),
                     table: el.closest('[data-table]') ? el.closest('[data-table]').dataset.table : null,
                     box: R(el.getBoundingClientRect()), words: words(el)});
  });
  document.querySelectorAll('[data-ill]').forEach(el => {
    out.ills.push({id: el.dataset.ill, box: R(el.querySelector('math').getBoundingClientRect()),
                   lab: R(el.querySelector('.lab').getBoundingClientRect())});
  });
  document.querySelectorAll('[data-table]').forEach(el => {
    out.tables.push({id: el.dataset.table, box: R(el.getBoundingClientRect())});
  });
  return out;
}
"""


def measure(html_path, out_json, out_png, w, h):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport=dict(width=w, height=h), device_scale_factor=DSF)
        pg.goto(Path(html_path).resolve().as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        data = pg.evaluate(MEASURE_JS)
        pg.screenshot(path=out_png, full_page=False)
        b.close()
    Path(out_json).write_text(json.dumps(data, ensure_ascii=False))


# ------------------------------------------------------------------------------------------------- ALTO + JATS

def lines_of(words):
    """Words (logical order) into lines: a new line where the vertical centre jumps."""
    lines = []
    for w in words:
        cy = w["b"][1] + w["b"][3] / 2
        if lines and abs(cy - lines[-1]["cy"]) < 0.5 * w["b"][3]:
            lines[-1]["w"].append(w)
        else:
            lines.append(dict(cy=cy, w=[w]))
    return [ln["w"] for ln in lines]


def px(v):
    return int(round(v * DSF))


def union(boxes):
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


def boxattr(b):
    return f'HPOS="{px(b[0])}" VPOS="{px(b[1])}" WIDTH="{max(1, px(b[2]))}" HEIGHT="{max(1, px(b[3]))}"'


ROLE_TAGS = ["body", "title", "author", "sectionHeading", "footnote", "pageNumber"]


def alto_xml(stem, pages_meas, size):
    W, H = (v * DSF for v in SIZES[size])
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#" xmlns:xlink="http://www.w3.org/1999/xlink" '
           'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SCHEMAVERSION="4.4" xsi:schemaLocation='
           '"http://www.loc.gov/standards/alto/ns-v4# https://www.loc.gov/standards/alto/v4/alto-4-4.xsd">',
           " <Description>", "  <MeasurementUnit>pixel</MeasurementUnit>", "  <sourceImageInformation>",
           f"   <fileName>{stem}.pdf</fileName>",
           f'   <documentIdentifier documentIdentifierLocation="inkscript test fixtures">{stem}</documentIdentifier>',
           "  </sourceImageInformation>", '  <OCRProcessing ID="handmade">', "   <ocrProcessingStep>",
           "    <processingCategory>contentGeneration</processingCategory>",
           "    <processingStepDescription>Hand-made test master (experiment 35), NOT an archive page: the page was "
           "typeset in Chromium from a written spec and every word's box measured in the browser; no OCR. "
           f"Pixels at {DPI} dpi.</processingStepDescription>",
           "    <processingSoftware>", "     <softwareCreator>inkscript</softwareCreator>",
           "     <softwareName>experiments/35_edition/testdocs/make_testdocs.py</softwareName>",
           "     <softwareVersion>exp35</softwareVersion>", "    </processingSoftware>", "   </ocrProcessingStep>",
           "  </OCRProcessing>", " </Description>", " <Tags>"]
    for r in ROLE_TAGS:
        out.append(f'  <StructureTag ID="role.{r}" TYPE="paragraph-role" LABEL="{r}"/>')
    out += ['  <OtherTag ID="trust.agreed" TYPE="trust" LABEL="agreed" DESCRIPTION="No signal raised a doubt '
            '(hand-made: the text is the spec\'s)."/>',
            '  <OtherTag ID="kind.formula" TYPE="content-kind" LABEL="formula" DESCRIPTION="The ink of an inline '
            'formula: the word is a symbol of the formula held in the JATS as inline-formula (MathML + LaTeX)."/>',
            " </Tags>", " <Layout>"]
    wn = 0
    for n, meas in enumerate(pages_meas, 1):
        allb = [b["box"] for b in meas["blocks"]] + [i["box"] for i in meas["ills"]]
        ps = union(allb)
        out.append(f'  <Page ID="page{n}" PHYSICAL_IMG_NR="{n}" WIDTH="{W}" HEIGHT="{H}">')
        out.append(f"   <PrintSpace {boxattr(ps)}>")
        # blocks in reading order: the measure gives them in DOM order (= reading order); tables and formulas
        # are emitted where their first element falls
        order = []
        seen_tables = set()
        for b in meas["blocks"]:
            if b["table"]:
                if b["table"] not in seen_tables:
                    seen_tables.add(b["table"])
                    order.append(("table", b["table"]))
            else:
                order.append(("block", b))
        # formulas: after the block that precedes them vertically
        for ill in meas["ills"]:
            y = ill["box"][1]
            k = max([i for i, (t, b) in enumerate(order) if t == "block" and b["box"][1] < y and
                     b["role"] != "pageNumber"] or [0])
            order.insert(k + 1, ("ill", ill))
        tables = {t["id"]: t for t in meas["tables"]}

        def textblock(b, ind):
            nonlocal wn
            role = b["role"]
            href = "" if role == "pageNumber" else f' xlink:href="{stem}.jats.xml#{b["id"]}" xlink:type="simple"'
            ws = b["words"]
            box = b["box"] if b["cell"] else union([w["b"] for w in ws])
            s = [f'{ind}<TextBlock ID="{b["id"]}" TAGREFS="role.{role}" LANG="ar" BASEDIRECTION="rtl" '
                 f'{boxattr(box)}{href}>']
            for li, ln in enumerate(lines_of(ws), 1):
                s.append(f'{ind} <TextLine ID="{b["id"]}l{li}" BASEDIRECTION="rtl" {boxattr(union([w["b"] for w in ln]))}>')
                for wi, w in enumerate(ln):
                    wn += 1
                    tags = "trust.agreed" + (" kind.formula" if w["math"] else "")
                    lang = ' LANG="en"' if w["t"].isascii() and any(c.isalpha() for c in w["t"]) else ""
                    if wi:
                        s.append(f"{ind}  <SP/>")
                    s.append(f'{ind}  <String ID="p{n}w{wn:04d}" CONTENT="{escape(w["t"], {chr(34): "&quot;"})}" '
                             f'WC="0.95" TAGREFS="{tags}"{lang} {boxattr(w["b"])}/>')
                s.append(f"{ind} </TextLine>")
            s.append(f"{ind}</TextBlock>")
            return s
        for t, x in order:
            if t == "block":
                out += textblock(x, "    ")
            elif t == "ill":
                box = union([x["box"], x["lab"]])
                out.append(f'    <Illustration ID="{x["id"]}" TYPE="formula" {boxattr(box)} '
                           f'xlink:href="{stem}.jats.xml#{x["id"]}" xlink:type="simple"/>')
            else:
                tb = tables[x]
                out.append(f'    <ComposedBlock ID="{x}" TYPE="table" {boxattr(tb["box"])} '
                           f'xlink:href="{stem}.jats.xml#{x}" xlink:type="simple">')
                for b in meas["blocks"]:
                    if b["table"] == x:
                        out += textblock(b, "     ")
                out.append("    </ComposedBlock>")
        out.append("   </PrintSpace>")
        out.append("  </Page>")
    out += [" </Layout>", "</alto>"]
    return "\n".join(out) + "\n", wn


def jats_inline(parts, mid):
    s = []
    for p in parts:
        if isinstance(p, str):
            s.append(escape(p))
        elif p[0] == "fn":
            s.append(f'<xref ref-type="fn" rid="{p[1]}">{escape(p[2])}</xref>')
        elif p[0] == "math":
            mid[0] += 1
            s.append(f'<inline-formula id="{mid[1]}f{mid[0]}"><alternatives><mml:math dir="rtl">{mml(p[1])}'
                     f'</mml:math><tex-math><![CDATA[{p[2]}]]></tex-math></alternatives></inline-formula>')
    return "".join(s)


def mml(inner):
    import re
    return re.sub(r"<(/?)(\w+)", r"<\1mml:\2", inner)


def jats_xml(stem, doc, nwords):
    body, fns, sec_open = [], [], False
    pages = doc["pages"]

    def walk(items, n):
        nonlocal sec_open
        tnum = 0
        for it in items:
            k = it[0]
            mid = [0, f"p{n}"]
            if k in ("pagenum", "title", "author"):
                continue
            if k == "columns":
                walk(it[1], n); walk(it[2], n)
                continue
            if k == "heading":
                if sec_open:
                    body.append("  </sec>")
                body.append(f'  <sec id="sec{sum(1 for b in body if "<sec " in b) + 1}">')
                body.append(f'   <title id="{it[1]}">{escape(it[2])}</title>')
                sec_open = True
            elif k == "p":
                body.append(f'   <p id="{it[1]}">{jats_inline(it[2], mid)}</p>')
            elif k == "eq":
                body.append(f'   <disp-formula id="{it[1]}">\n    <label>{escape(it[2])}</label>\n    <alternatives>\n'
                            f'     <mml:math display="block" dir="rtl">{mml(it[3])}</mml:math>\n'
                            f'     <tex-math><![CDATA[{it[4]}]]></tex-math>\n'
                            f'     <graphic xlink:href="{stem}.crops/{it[1]}.png" specific-use="scan-crop"/>\n'
                            f'    </alternatives>\n   </disp-formula>')
            elif k == "table":
                tnum += 1
                ids = grid_ids(n, tnum, it[4])
                rows = {"thead": [], "tbody": []}
                for (sec, cells), rid in zip(it[4], ids):
                    tds = "".join(
                        f'<{"th" if c["th"] else "td"} id="{i}"'
                        f'{" scope=%s" % chr(34) + c["scope"] + chr(34) if c["scope"] else ""}'
                        f'{" colspan=%s" % chr(34) + str(c["colspan"]) + chr(34) if c["colspan"] > 1 else ""}'
                        f'{" rowspan=%s" % chr(34) + str(c["rowspan"]) + chr(34) if c["rowspan"] > 1 else ""}>'
                        f'{escape(c["t"])}</{"th" if c["th"] else "td"}>' for c, i in zip(cells, rid))
                    rows[sec].append(f"       <tr>{tds}</tr>")
                body.append(
                    f'   <table-wrap id="{it[1]}">\n    <caption><p id="{it[2]}">{escape(it[3])}</p></caption>\n'
                    f'    <alternatives>\n     <graphic xlink:href="{stem}.crops/{it[1]}.png" specific-use="scan-crop"/>\n'
                    f'     <table>\n      <thead>\n' + "\n".join(rows["thead"]) + "\n      </thead>\n"
                    "      <tbody>\n" + "\n".join(rows["tbody"]) + "\n      </tbody>\n     </table>\n"
                    "    </alternatives>\n   </table-wrap>")
            elif k == "fn":
                fns.append(f'   <fn id="{it[2]}">\n    <label>{escape(it[3])}</label>\n'
                           f'    <p id="{it[1]}">{jats_inline([it[4]], mid)}</p>\n   </fn>')
    for n, items in enumerate(pages, 1):
        walk(items, n)
    if sec_open:
        body.append("  </sec>")
    title_id = next(it[1] for it in pages[0] if it[0] == "title")
    author_id = next(it[1] for it in pages[0] if it[0] == "author")
    meta = [("hand-made-test-file", "Hand-made test master (experiment 35): NOT an archive page. Written by hand to "
             "test tables (XHTML, merged cells, cells in reading order: the first cell of a row is the rightmost on "
             "the page) and equations (MathML dir=rtl + LaTeX + scan crop) in every derived edition; the 'scan' is "
             "the same text typeset in Chromium. See tests/fixtures/edition/README.md."),
            ("text-direction", "rtl (text stored in logical order; xml:lang carries the script)"),
            ("cell-order", "logical: the first cell of a row is the rightmost on the page"),
            ("faithful-pdf", f"{stem}.pdf (stand-in: the typeset page as a grey image)"),
            ("alto-file", f"{stem}.alto.xml"),
            ("trust", f"0 words verified, {nwords} agreed, 0 flagged (per-word marks in the ALTO file)"),
            ("quran-quotations", "0 found, 0 equal to the verse")]
    cm = "\n".join(f"    <custom-meta>\n     <meta-name>{k}</meta-name>\n     <meta-value>{escape(v)}</meta-value>\n"
                   "    </custom-meta>" for k, v in meta)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD with MathML3 v1.4 20241031//EN" "JATS-archivearticle1-4-mathml3.dtd">
<article xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:mml="http://www.w3.org/1998/Math/MathML" article-type="research-article" dtd-version="1.4" xml:lang="ar">
 <processing-meta tagset-family="jats" base-tagset="archiving" table-model="xhtml" math-representation="mathml tex" mathml-version="3.0"/>
 <front>
  <journal-meta>
   <journal-id journal-id-type="publisher-id">test</journal-id>
   <journal-title-group>
    <journal-title>مجلة الاختبار</journal-title>
   </journal-title-group>
   <publisher>
    <publisher-name>inkscript (hand-made test files)</publisher-name>
   </publisher>
  </journal-meta>
  <article-meta>
   <article-id pub-id-type="other" assigning-authority="inkscript">{stem}</article-id>
   <title-group>
    <article-title id="{title_id}">{escape(doc["title"])}</article-title>
   </title-group>
   <contrib-group>
    <contrib contrib-type="author" id="{author_id}">
     <string-name>{escape(doc["author"])}</string-name>
    </contrib>
   </contrib-group>
   <pub-date publication-format="print" date-type="pub" calendar="gregorian">
    <year>2026</year>
   </pub-date>
   <volume>1</volume>
   <issue>1</issue>
   <fpage>{doc["fpage"]}</fpage>
   <lpage>{doc["lpage"]}</lpage>
   <counts>
    <page-count count="{len(pages)}"/>
   </counts>
   <custom-meta-group>
{cm}
   </custom-meta-group>
  </article-meta>
 </front>
 <body>
{chr(10).join(body)}
 </body>
 <back>
  <fn-group>
{chr(10).join(fns)}
  </fn-group>
 </back>
</article>
"""


# ------------------------------------------------------------------------------------------------- main

def scanify(png_path):
    """A screenshot -> a scan-like grey image: a little blur and noise, 32 grey levels."""
    import cv2
    import numpy as np
    g = cv2.imread(str(png_path), cv2.IMREAD_GRAYSCALE)
    g = cv2.GaussianBlur(g, (3, 3), 0.7)
    rng = np.random.default_rng(35)
    g = np.clip(g.astype(np.float32) + rng.normal(0, 2, g.shape), 0, 255).astype(np.uint8)
    g = (g // 8) * 8                       # fewer grey levels: the crops stay small as PNG
    return g


def build(out_dir: Path, work: Path):
    import cv2
    import pymupdf
    out_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    for stem, doc in DOCS.items():
        w, h = SIZES[doc["size"]]
        meas, grays = [], []
        for n, items in enumerate(doc["pages"], 1):
            hp = work / f"{stem}-p{n}.html"
            hp.write_text(page_html(doc, n, items), encoding="utf-8")
            jp, pp = work / f"{stem}-p{n}.json", work / f"{stem}-p{n}.png"
            subprocess.run([PW_PYTHON, __file__, "--measure", str(hp), str(jp), str(pp), str(w), str(h)], check=True)
            meas.append(json.loads(jp.read_text()))
            grays.append(scanify(pp))
        alto, nwords = alto_xml(stem, meas, doc["size"])
        (out_dir / f"{stem}.alto.xml").write_text(alto, encoding="utf-8")
        (out_dir / f"{stem}.jats.xml").write_text(jats_xml(stem, doc, nwords), encoding="utf-8")
        crops = out_dir / f"{stem}.crops"
        crops.mkdir(exist_ok=True)
        for n, m in enumerate(meas, 1):
            g = grays[n - 1]
            things = [(i["id"], union([i["box"], i["lab"]])) for i in m["ills"]] + \
                     [(t["id"], t["box"]) for t in m["tables"]]
            for cid, b in things:
                x0, y0 = max(0, px(b[0]) - 12), max(0, px(b[1]) - 12)
                x1, y1 = px(b[0] + b[2]) + 12, px(b[1] + b[3]) + 12
                cv2.imwrite(str(crops / f"{cid}.png"), g[y0:y1, x0:x1])
        pdf = pymupdf.open()
        pt_w, pt_h = w * DSF * 72 / DPI, h * DSF * 72 / DPI
        for g in grays:
            small = cv2.resize(g, None, fx=JPEG_SCALE, fy=JPEG_SCALE, interpolation=cv2.INTER_AREA)
            ok, jpg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 55])
            page = pdf.new_page(width=pt_w, height=pt_h)
            page.insert_image(page.rect, stream=jpg.tobytes())
        pdf.save(str(out_dir / f"{stem}.pdf"), garbage=3, deflate=True)
        print(stem, nwords, "words,", len(meas), "pages")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--measure":
        measure(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), int(sys.argv[6]))
    else:
        out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tests" / "fixtures" / "edition"
        build(out, Path(os.environ.get("TESTDOCS_WORK", "/tmp/claude-1000/-home-yassine-inkscript/"
                                       "ed816869-9be5-4008-b630-480b426fc462/scratchpad/testdocs")))
