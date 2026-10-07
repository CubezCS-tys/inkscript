"""The owner's page: title pages beside the JATS front matter before / after the catalogue, field coverage as bars,
the records that do not fit, the MARC -> JATS map. Self-contained (pages embedded as JPEG), light/dark, phone width.

    PYTHONPATH=src .venv/bin/python experiments/29_catalogue/report.py [--look]
    -> out/report.html   (--look also writes out/look/<stem>.jpg: the page with the boxes, for checking by eye)
"""
import base64
import html
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
from lxml import etree

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SET28 = Path("/home/yassine/inkscript/experiments/28_scale/out")
E = html.escape
# 15 documents for the eye: every 14th of the 205 in id order (a fixed, unchosen draw), then the ones the
# catalogue check flags
SPOT_STEP = 14
NOTES = json.loads((HERE / "spotcheck.json").read_text(encoding="utf-8")) if (HERE / "spotcheck.json").exists() else {}


def load_rows():
    return {m: {r["stem"]: r for r in json.loads((OUT / f"{m}.json").read_text())} for m in ("before", "after")}


def words_of(stem, mode="after"):
    t = etree.parse(str(OUT / mode / f"{stem}.alto.xml"))
    pages = {}
    for p in t.iter("{*}Page"):
        pages[int(p.get("PHYSICAL_IMG_NR"))] = (float(p.get("WIDTH")), float(p.get("HEIGHT")))
    w = {}
    for s in t.iter("{*}String"):
        w[s.get("ID")] = (s.get("CONTENT"), float(s.get("HPOS")), float(s.get("VPOS")), float(s.get("WIDTH")), float(s.get("HEIGHT")))
    return pages, w


def page_image(stem, rows, width=560, crop=0.62):
    """Page 1 (or the title's page) with the title / name boxes: after in solid colours, before dashed."""
    a, b = rows["after"][stem], rows["before"][stem]
    pages, W = words_of(stem)
    ids = a["title_word_ids"] or b["title_word_ids"]
    pn = int(ids[0][1:].split("w")[0]) if ids else 1
    pdf = pdfium.PdfDocument(str(SET28 / "azure" / stem / f"{stem}.pdf"))
    pg = pdf[pn - 1]
    img = pg.render(scale=width / pg.get_width(), grayscale=True).to_numpy()
    img = img if img.ndim == 2 else img[..., 0]
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    pw, ph = pages.get(pn, (1, 1))
    sx, sy = img.shape[1] / pw, img.shape[0] / ph
    ymax = 0

    def box(idlist, col, dashed=False, pad=4):
        nonlocal ymax
        ws = [W[i] for i in idlist if i in W and i.startswith(f"p{pn}w")]
        if not ws:
            return
        x0 = min(w[1] for w in ws) * sx - pad
        y0 = min(w[2] for w in ws) * sy - pad
        x1 = max(w[1] + w[3] for w in ws) * sx + pad
        y1 = max(w[2] + w[4] for w in ws) * sy + pad
        ymax = max(ymax, y1)
        p0, p1 = (int(x0), int(y0)), (int(x1), int(y1))
        if dashed:
            for x in range(p0[0], p1[0], 12):
                cv2.line(img, (x, p0[1]), (min(x + 6, p1[0]), p0[1]), col, 2)
                cv2.line(img, (x, p1[1]), (min(x + 6, p1[0]), p1[1]), col, 2)
            for y in range(p0[1], p1[1], 12):
                cv2.line(img, (p0[0], y), (p0[0], min(y + 6, p1[1])), col, 2)
                cv2.line(img, (p1[0], y), (p1[0], min(y + 6, p1[1])), col, 2)
        else:
            cv2.rectangle(img, p0, p1, col, 3)
    box(b["title_word_ids"], (52, 104, 235), dashed=True, pad=8)        # before: orange, dashed (BGR)
    for ids_ in b.get("author_word_ids", []):
        box(ids_, (52, 104, 235), dashed=True, pad=8)
    box(a["title_word_ids"], (214, 120, 42))                             # after: blue
    for ids_ in a.get("author_word_ids", []):
        box(ids_, (122, 175, 27))                                        # names: green
    h = int(max(crop * img.shape[0], min(img.shape[0], ymax + 40)))
    img = img[:h]
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return buf.tobytes(), pn


def front_html(r, cls, label):
    rows = []

    def li(k, v, src=""):
        if v:
            rows.append(f"<li><b>{E(k)}</b> <span dir=auto>{E(str(v))}</span>" + (f" <small>{E(src)}</small>" if src else "") + "</li>")
    li("title", r["title"], "" if cls == "before" else r.get("title_source", "").split(";")[0].split(",")[0])
    li("subtitle", r.get("subtitle", ""))
    for n, (a, p) in enumerate(zip(r["authors"], r.get("prefixes", [""] * len(r["authors"]))), 1):
        li(f"author {n}", (p + " " if p else "") + a,
           "on the page" if (r.get("author_word_ids") or [[]] * 9)[n - 1] else "not on the page")
    li("journal", r["journal"])
    li("ISSN", r["issn"])
    li("date", r["year"])
    li("volume / issue", " / ".join(x for x in (r["volume"], r["issue"]) if x))
    li("pages", "–".join(x for x in (r["fpage"], r["lpage"]) if x))
    if r.get("abstract"):
        li("abstracts", r["abstract"])
    if r.get("keywords"):
        li("keywords", r["keywords"])
    li("DOI", r.get("doi"))
    return f'<div class="ol {cls}"><h4>{label}</h4><ul>{"".join(rows) or "<li>(nothing)</li>"}</ul></div>'


def bars(summary):
    out = []
    n = summary["compared"]
    for name, v in summary["coverage"].items():
        b, a = v["before"], v["after"]
        out.append(f'<div class="prrow"><div class="el">{E(name)}</div>'
                   f'<div><div class="bar before"><i style="width:{100 * b / n:.1f}%"></i><b>{b}</b></div>'
                   f'<div class="bar after"><i style="width:{100 * a / n:.1f}%"></i><b>{a}</b></div></div></div>')
    return "".join(out)


MAPPING = [
    ("245 $a, $b", "title, subtitle", "article-title, subtitle (ISBD ' :' dropped); the ink: title-words custom-meta, the block id on article-title"),
    ("242 / 246 $a $b", "English title", "trans-title-group xml:lang=en"),
    ("100, 700 $a", "people, “Surname، Given”", "contrib › name-alternatives › name (surname, given-names), xml:lang=ar; the printed honorific as prefix; the printed form as string-name"),
    ("100, 700 $g / $q", "the name in Latin script", "a second name, xml:lang=en"),
    ("100, 700 $e", "role: مؤلف, م. مشارك, مترجم, مشرف, عارض", "contrib-type author / translator / supervisor / presenter; role"),
    ("100, 700 $9", "authority number", "contrib-id contrib-id-type=mandumah-authority"),
    ("110 $a", "a body (هيئة التحرير)", "contrib › collab"),
    ("— (no 100 $u)", "affiliation", "from the page (the byline's next lines), aff specific-use=page"),
    ("773 $s, $t/$e, $f", "journal title, English, romanised", "journal-title, trans-title, abbrev-journal-title"),
    ("773 $x", "ISSN", "issn"),
    ("773 $v, $l, $m", "volume, issue, as printed (مج34, ع390)", "volume, issue content-type=catalogue; the printed form in custom-meta"),
    ("773 $4, $6", "field of study ar / en", "article-categories subj-group subj-group-type=field"),
    ("260 $b, 773 $d, 044 $b", "publisher, place, country", "journal-meta publisher"),
    ("260 $c, $m, $g", "year Gregorian, Hijri, month(s)", "two pub-date (calendar gregorian / islamic) with month or season"),
    ("300 $a", "pages “184 - 238”", "fpage, lpage content-type=catalogue (the page's own numbering noted when it differs)"),
    ("041 $a", "language", "custom-meta catalogue-language (the article stays xml:lang=ar)"),
    ("336 $a $b", "kind: Article, Book Review…", "subj-group subj-group-type=mandumah-type"),
    ("520 $a $b $d $e $f", "abstracts: author's ar/en/other, Mandumah's ar/en", "abstract (article's language first) and trans-abstract, abstract-type author / mandumah"),
    ("653 $a", "subject terms", "kwd-group kwd-group-type=subject-terms"),
    ("692 $a $b", "keywords ar + en", "two kwd-group kwd-group-type=keywords"),
    ("001, 024 $3", "record number, DOI", "article-id custom-type=mandumah-record; article-id pub-id-type=doi"),
    ("856 $n", "the publisher's page", "self-uri"),
    ("500, 502, 995", "note, thesis, database", "custom-meta"),
]


def main():
    rows = load_rows()
    s = json.loads((OUT / "summary.json").read_text())
    stems = sorted(rows["after"])
    spot = stems[::SPOT_STEP][:15]
    flagged = [x for x in stems if not rows["after"][x].get("catalogue_check", {}).get("verdict", "").startswith("agrees")
               or rows["after"][x].get("catalogue_check", {}).get("page_title_differs")]
    look = "--look" in sys.argv
    (OUT / "look").mkdir(exist_ok=True)

    def doc_block(stem, note=""):
        jpg, pn = page_image(stem, rows)
        if look:
            (OUT / "look" / f"{stem}.jpg").write_bytes(jpg)
        a, b = rows["after"][stem], rows["before"][stem]
        chk = a.get("catalogue_check", {})
        verdict = chk.get("verdict", "no catalogue record")
        extra = ""
        if chk.get("page_title_differs"):
            extra = f'<p class="m">the page\'s own title ({E(chk.get("page_title_source", ""))}): «<span dir=auto>{E(chk["page_title_differs"])}</span>»</p>'
        return (f'<section class="doc"><h3>{E(stem)} <small class="m">page {pn} · {E(verdict)}</small></h3>'
                f'<div class="docgrid"><figure><img alt="title page of {E(stem)}" src="data:image/jpeg;base64,'
                f'{base64.b64encode(jpg).decode()}"><figcaption>blue: the catalogue\'s title on the ink; green: its '
                f'names; orange dashes: what the page alone found</figcaption></figure><div>'
                f'{front_html(b, "before", "before: the page alone")}{front_html(a, "after", "after: the catalogue, tied to the ink")}'
                f'{extra}' + (f'<p class="note"><b>By eye:</b> {E(note)}</p>' if note else "") + '</div></div></section>')

    cov = s["coverage"]
    t = s["title"]
    tiles = [(f'{s["with_record"]}/{s["documents"]}', "documents with a catalogue record"),
             (f'{t.get("found on the page", 0)}/{s["with_record"]}', "catalogue titles found on the page (their words' ids in the JATS)"),
             (f'{s["names_found"]}/{s["names"]}', "catalogue names found on the page (before: the page found " + f'{s["page_authors_right_before"]} of {s["catalogue_authors"]})'),
             (f'{s["valid"]["after"]["jats"]}/{s["compared"]} · {s["valid"]["after"]["alto"]}/{s["compared"]}', "JATS 1.4 / ALTO 4.4 valid")]
    idx = json.loads((OUT / "index_stats.json").read_text()) if (OUT / "index_stats.json").exists() else {}
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Catalogue front matter</title>
<style>
:root{{--bg:#fcfcfb;--fg:#0b0b0b;--muted:#52514e;--line:#e4e3df;--card:#ffffff;--before:#eb6834;--after:#2a78d6;--track:#f0efec}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#1a1a19;--fg:#fff;--muted:#c3c2b7;--line:#383835;--card:#232322;--before:#d95926;--after:#3987e5;--track:#383835}}}}
:root[data-theme="dark"]{{--bg:#1a1a19;--fg:#fff;--muted:#c3c2b7;--line:#383835;--card:#232322;--before:#d95926;--after:#3987e5;--track:#383835}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:24px 16px 64px}} h1{{font-size:26px;margin:0 0 6px}} h2{{margin:40px 0 8px;font-size:20px}}
h3{{margin:20px 0 8px;font-size:16px}} p{{max-width:75ch}} .note,.m{{color:var(--muted);font-size:13px}} .lead{{color:var(--muted)}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:16px 0}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}} .tile b{{font-size:24px;display:block}} .tile span{{color:var(--muted);font-size:13px}}
.pr{{display:grid;gap:8px}} .prrow{{display:grid;grid-template-columns:190px 1fr;gap:12px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px}}
.el{{font-weight:600}} .bar{{position:relative;height:16px;background:var(--track);border-radius:4px;margin:3px 0;overflow:hidden}}
.bar i{{position:absolute;inset:0 auto 0 0;border-radius:0 4px 4px 0}} .bar.before i{{background:var(--before)}} .bar.after i{{background:var(--after)}}
.bar b{{position:absolute;right:6px;top:0;font-size:12px;line-height:16px;font-weight:600;color:var(--fg)}}
.legend{{display:flex;gap:14px;font-size:13px;color:var(--muted);margin:6px 0}} .legend span::before{{content:"";display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-1px;background:var(--k)}}
.doc{{border-top:1px solid var(--line);padding-top:6px}} .docgrid{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}}
figure{{margin:0}} img{{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:4px}} figcaption{{font-size:12px;color:var(--muted)}}
.ol{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:10px}} .ol h4{{margin:0 0 4px;font-size:13px}}
.ol.before h4{{color:var(--before)}} .ol.after h4{{color:var(--after)}} .ol ul{{list-style:none;margin:0;padding:0;font-size:13px}} .ol li{{margin:3px 0}} .ol small{{color:var(--muted)}}
.tablewrap{{overflow-x:auto}} table{{border-collapse:collapse;font-size:13px;width:100%}} td,th{{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}}
th{{color:var(--muted);font-weight:600}} code{{font-size:12px}}
@media (max-width:760px){{.docgrid{{grid-template-columns:1fr}} .prrow{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>Front matter from the library catalogue</h1>
<p class="lead">Experiment 29 · 2026-10-07. Each JATS file now takes its title, authors, journal, dates, pages, abstract and
keywords from Mandumah's own MARC catalogue, and ties the title and each name to the printed words on the page (their
ALTO word ids), with the honorific printed before a name as its <code>&lt;prefix&gt;</code> and the affiliation under it
from the page. Every element says where it came from. Measured on experiment 28's 205 scanned documents.</p>
<div class="tiles">{"".join(f'<div class="tile"><b>{E(v)}</b><span>{E(k)}</span></div>' for v, k in tiles)}</div>
<h2>What the JATS front matter holds, before and after</h2>
<div class="legend"><span style="--k:var(--before)">before: the page alone (Gemini's title file where the bucket has one, else the layout)</span><span style="--k:var(--after)">after: the catalogue first</span></div>
<p class="note">Documents (of {s["compared"]}) whose JATS has the element. "Tied to its ink" = the words are found on the page and
their ids written. Before, a title was <i>present</i> in {cov["title"]["before"]} but matched the catalogue in only {s["page_title_right_before"]} of {s["with_record"]};
the page found {s["page_authors_right_before"]} of the catalogue's {s["catalogue_authors"]} names.</p>
<div class="pr">{bars(s)}</div>
<h2>Records that do not fit their page</h2>
<p>No record looked like the wrong one (a title, every name and the page count all failing). What the check finds instead
is the catalogue naming an article by its <b>rubric</b> (the journal's column: «ديوان العرب», «البيت المسلم», «كلمة العدد»), with
the article's own title as the subtitle — found on the page then — or not at all.</p>
{"".join(doc_block(x, NOTES.get(x, "")) for x in flagged)}
<h2>Fifteen documents by eye</h2>
<p class="note">Every {SPOT_STEP}th document of the 205 in id order (not chosen). The page as scanned; boxes from the ALTO word ids the JATS lists.</p>
{"".join(doc_block(x, NOTES.get(x, "")) for x in spot)}
<h2>MARC → JATS</h2>
<p class="note">Fields read on all 1,558,415 records; see <code>src/inkscript/enrich/catalogue.py</code> for the counts of each.</p>
<div class="tablewrap"><table><tr><th>MARC</th><th>what Mandumah puts there</th><th>JATS</th></tr>
{"".join(f"<tr><td>{E(a)}</td><td>{E(b)}</td><td>{E(c)}</td></tr>" for a, b, c in MAPPING)}</table></div>
<h2>The index</h2>
<p>{E(idx.get("text", ""))}</p>
</main></body></html>"""
    (OUT / "report.html").write_text(page, encoding="utf-8")
    print("wrote", OUT / "report.html", f"{len(page) / 1e6:.1f} MB; spot", spot, "flagged", flagged)


if __name__ == "__main__":
    main()
