"""Front page three ways: the searchable PDF itself | Azure's text | the text
now in that PDF, both rebuilds in the same Azure boxes, changed words marked."""
from __future__ import annotations
import html, json, shutil, sys
from pathlib import Path

from .static import blocks_html, shell, to_blocks
from ..text import fold_digits, norm
from ..ocr.azure import load_azure
from ..ocr.align import page1_text

MARK_ON, MARK_OFF = "", ""     # survive html.escape; swapped for <mark> after
MODE_CELL = {"gemini": "gemini", "gemini-title": "<b style=color:#0F6E76>title</b>",
             "azure-fallback": "<b style=color:#C4571A>fallback</b>"}

CSS = """<style>
mark.chg{background:#6B4FA833;color:inherit;border-radius:2px;padding:0 .05em}
.status{font-family:var(--mono);font-size:.7rem;margin:0 0 .8rem;color:var(--mut)}
.status b.g{color:#6B4FA8}.status b.t{color:#0F6E76}.status b.f{color:#C4571A}
details.raw{margin-top:1.4rem}details.raw summary{cursor:pointer;font-family:var(--mono);
font-size:.72rem;color:var(--mut)}
details.raw pre{white-space:pre-wrap;direction:rtl;font-family:var(--ar);font-size:.95rem;
background:var(--surf);border:1px solid var(--rule);padding:.8rem;max-width:80ch}
table.ix{border-collapse:collapse;font-size:.85rem;width:100%}
.ixwrap{overflow-x:auto}
table.ix td,table.ix th{border-bottom:1px solid var(--rule);padding:.45rem .5rem;
vertical-align:top;text-align:start}
table.ix th{font-family:var(--mono);font-size:.66rem;color:var(--mut);font-weight:500;
text-transform:uppercase;letter-spacing:.06em}
table.ix td.t{direction:rtl;font-family:var(--ar)}
table.ix td.m{font-family:var(--mono);font-size:.72rem;white-space:nowrap}
.pane.pv h2{color:#8A6D1F}
.pane.pv iframe{display:block;width:100%;border:1px solid var(--rule);
box-shadow:inset 0 2px 0 #8A6D1F;background:var(--sheet)}
.pane.pv .hint{font-family:var(--mono);font-size:.62rem;color:var(--mut);margin:.3rem 0 0}
</style>"""


def build(a) -> int:

    import fitz
    fd, ad = (Path(p).expanduser() for p in (a.frontpage_dir, a.azure_dir))
    out = Path(a.out).expanduser()
    (out / "pdf").mkdir(parents=True, exist_ok=True)

    stems = sorted(p.name.split(".")[0] for p in fd.glob("*.frontpage.json")
                   if (fd / f"{p.name.split('.')[0]}.gemini.p1.md").exists())
    if not stems:
        print(f"no ocr_frontpage.py output in {fd}", file=sys.stderr); return 2

    rows = []
    for stem in stems:
        words, paras, dims = load_azure(ad / stem / f"{stem}.json")
        p1 = [w for w in words if w["page"] == 1]
        raw = (fd / f"{stem}.gemini.p1.md").read_text(encoding="utf-8")
        texts, st = page1_text(p1, fold_digits(raw), a.min_exact)
        used = texts is not None

        az_text = [w["text"] for w in p1]
        if used:
            pdf_text = [t if norm(t) == norm(w["text"]) else f"{MARK_ON}{t}{MARK_OFF}"
                        for w, t in zip(p1, texts)]
        else:
            pdf_text = az_text
        p1paras = [p for p in paras if p["page"] == 1]
        az_pg = to_blocks(p1, az_text, p1paras, {1: dims[1]}, 150)[0]["pages"][0]
        pdf_pg = to_blocks(p1, pdf_text, p1paras, {1: dims[1]}, 150)[0]["pages"][0]

        # The PDF pane shows the scan itself, so no page image is rendered; the
        # page is opened only for its size and for blocks_html's signature.
        pdf = fitz.open(fd / f"{stem}.pdf")
        page = pdf[0]

        def pane(pg, cls, label):
            divs, (W, H), _ = blocks_html(pg, {}, stem, 0, page, out, fitz, crops=False)
            divs = divs.replace(MARK_ON, '<mark class="chg">').replace(MARK_OFF, "</mark>")
            return (f'<div class="pane {cls}"><h2>{label}</h2>'
                    f'<div class="sheet" style="aspect-ratio:{W}/{H}">{divs}</div></div>')

        right = {"gemini": "in the pdf — gemini text, azure boxes",
                 "gemini-title": "in the pdf — gemini title, azure body",
                 "azure-fallback": "in the pdf — azure (fallback)"}[st["page1"]]
        # The PDF itself, in the browser's own viewer: not a rebuild of the text
        # layer but the layer, so select and Ctrl-F inside it are the real test.
        pw, ph = page.rect.width, page.rect.height
        pdf_pane = (f'<div class="pane pv"><h2>searchable pdf — real text layer</h2>'
                    f'<iframe src="pdf/{html.escape(stem)}.pdf#page=1&amp;view=FitH&amp;toolbar=0'
                    f'&amp;navpanes=0" style="aspect-ratio:{pw:.1f}/{ph:.1f}" '
                    f'title="searchable PDF" loading="lazy"></iframe>'
                    f'<p class="hint">click inside, then Ctrl-F or drag to select — the text '
                    f'is invisible, only the selection shows it</p></div>')
        panes = (f'<div class="split3">{pdf_pane}{pane(az_pg, "az", "azure — before")}'
                 f'{pane(pdf_pg, "hy", right)}</div>')
        pdf.close()
        shutil.copy2(fd / f"{stem}.pdf", out / "pdf" / f"{stem}.pdf")

        changed = sum(1 for t in pdf_text if t.startswith(MARK_ON)) if used else 0
        if st["page1"] == "gemini":
            status = (f'<b class="g">gemini</b> · {st["exact_of_azure"]:.0%} of Azure words '
                      f'aligned exactly · {changed} words changed (highlighted)')
        elif st["page1"] == "gemini-title":
            status = (f'<b class="t">gemini-title</b> · page as a whole aligned only '
                      f'{st["exact_of_azure"]:.0%}, so Gemini\'s words fill the top '
                      f'{st["title_boxes"]} boxes and the rest stays Azure\'s · '
                      f'{changed} words changed (highlighted)')
        else:
            status = f'<b class="f">azure-fallback</b> · {html.escape(st.get("reason", ""))}'
        body = (CSS + f'<p class="status">{status} · '
                f'<a href="pdf/{html.escape(stem)}.pdf" target="_blank">open searchable PDF</a>'
                f' in its own tab</p>{panes}'
                f'<details class="raw"{"" if used else " open"}><summary>gemini page-1 '
                f'transcription, as returned</summary><pre>{html.escape(raw)}</pre></details>')
        (out / f"{stem}.html").write_text(shell(stem, body, stems, cur=stem), encoding="utf-8")

        first = lambda pg: (pg["blocks"][0]["content"] if pg["blocks"] else "")
        rows.append((stem, used, st, changed, first(az_pg),
                     first(pdf_pg).replace(MARK_ON, "").replace(MARK_OFF, "")))

    ok = sum(r[2]["page1"] == "gemini" for r in rows)
    tt = sum(r[2]["page1"] == "gemini-title" for r in rows)
    trs = "".join(
        f'<tr><td class="m"><a href="{html.escape(s)}.html">{html.escape(s)}</a></td>'
        f'<td class="m">{MODE_CELL[st["page1"]]}'
        f'<br>{st.get("exact_of_azure", 0):.0%} · {c} chg</td>'
        f'<td class="t">{html.escape(az[:90])}</td><td class="t">{html.escape(ge[:90])}</td></tr>'
        for s, u, st, c, az, ge in rows)
    idx = (CSS + f'<h2 class="big">{len(rows)} front pages · {ok} rebuilt with gemini text · '
           f'{tt} gemini title only</h2>'
           f'<p class="lede">Each document shows page 1 three ways: the searchable PDF '
           f'itself, Azure\'s text, and the text now in that PDF. Both '
           f'rebuilds use the same Azure boxes, so only the words differ; words Gemini '
           f'changed are highlighted. Pages 2+ of every PDF are Azure\'s, untouched — '
           f'scroll the PDF pane to see them.</p>'
           f'<p class="lede">First block of each version below — usually the title.</p>'
           f'<div class="ixwrap"><table class="ix"><tr><th>doc</th><th>page 1</th><th>azure</th>'
           f'<th>in the pdf</th></tr>{trs}</table></div>')
    (out / "index.html").write_text(shell("front page — azure vs gemini", idx, stems),
                                    encoding="utf-8")

    size = sum(f.stat().st_size for f in out.rglob("*")) / 1e6
    print(f"  {len(rows)} documents -> {out}  ({size:.0f} MB)")
    print(f"  open: {out / 'index.html'}")
    if a.zip:
        z = shutil.make_archive(str(out), "zip", root_dir=out.parent, base_dir=out.name)
        print(f"  zip:  {z}  ({Path(z).stat().st_size / 1e6:.0f} MB)")
    return 0
