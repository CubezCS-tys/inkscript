"""`inkscript edition`: every derived edition of each article, from its master files (JATS + ALTO; the faithful PDF
only for the scan pictures).

    inkscript edition MASTERS_DIR --out OUT [--doc ID ...] [--only html,epub,layout,onecol,md,jsonl] [--workers 2]

For each <id>.jats.xml (with <id>.alto.xml and <id>.pdf beside it) it writes OUT/<id>/:

    <id>.html  + scan/p<n>.jpg     the reading edition (phone first), each paragraph with its clip of the scan
    <id>.epub                      EPUB 3, reflowable, right-to-left page progression
    <id>.layout.pdf                re-typeset, every block where it was on the page
    <id>.onecol.pdf                re-typeset, one column, research-paper style
    <id>.md, <id>.jsonl            Markdown with YAML front matter; one dataset record (also appended to
                                   OUT/articles.jsonl)
    <id>.checks.json               the automatic checks on the files above (every ALTO word once; print order)

and OUT/fonts/ (the bundled OFL fonts), OUT/summary.json. A document that fails is recorded and skipped.
"""
from __future__ import annotations

import json
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

KINDS = ("html", "epub", "layout", "onecol", "md", "jsonl")


def build_one(jats: str, out: str, only: tuple = KINDS, check: bool = True) -> dict:
    from .model import load
    t0 = time.time()
    ed = load(jats)
    d = Path(out) / ed.stem
    d.mkdir(parents=True, exist_ok=True)
    res = dict(id=ed.stem, pages=len(ed.pages), files={}, stats={}, errors={})

    def step(kind, fn):
        t = time.time()
        try:
            r = fn()
            res["stats"][kind] = dict(r or {}, seconds=round(time.time() - t, 2))
        except Exception as e:
            res["errors"][kind] = f"{type(e).__name__}: {e}"[:500]
            res["stats"][kind] = dict(seconds=round(time.time() - t, 2), trace=traceback.format_exc()[-1500:])

    if "html" in only:
        from .html import write_html
        step("html", lambda: write_html(ed, Path(out)))
    if "epub" in only:
        from .epub import write_epub
        step("epub", lambda: write_epub(ed, Path(out)))
    if "layout" in only:
        from .printpdf import layout_pdf
        step("layout", lambda: layout_pdf(ed, d / f"{ed.stem}.layout.pdf"))
    if "onecol" in only:
        from .printpdf import onecol_pdf
        step("onecol", lambda: onecol_pdf(ed, d / f"{ed.stem}.onecol.pdf"))
    if "md" in only or "jsonl" in only:
        from .data import markdown, record

        def data():
            (d / f"{ed.stem}.md").write_text(markdown(ed), encoding="utf-8")
            (d / f"{ed.stem}.jsonl").write_text(json.dumps(record(ed), ensure_ascii=False), encoding="utf-8")
            return {}
        step("data", data)
    files = {k: d / n for k, n in (("html", f"{ed.stem}.html"), ("epub", f"{ed.stem}.epub"),
                                    ("layout_pdf", f"{ed.stem}.layout.pdf"),
                                    ("onecol_pdf", f"{ed.stem}.onecol.pdf"), ("md", f"{ed.stem}.md"),
                                    ("jsonl", f"{ed.stem}.jsonl"))}
    res["files"] = {k: str(p) for k, p in files.items() if p.exists()}
    if check:
        from .check import check_article

        def chk():
            c = check_article(ed, {k: Path(v) for k, v in res["files"].items()})
            (d / f"{ed.stem}.checks.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
            res["checks"] = c
            return {}
        step("checks", chk)
    res["seconds"] = round(time.time() - t0, 2)
    return res


def _limit_memory(gb: float):
    """Workers run niced. No address-space limit: Chromium (a child process) reserves far more virtual memory
    than it uses and would not start under one; peak resident memory is measured instead (README)."""
    try:
        os.nice(10)
    except OSError:
        pass


def main(a) -> int:
    src = Path(a.masters)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jats = sorted(src.glob("*.jats.xml"))
    if a.doc:
        jats = [j for j in jats if j.name[:-len(".jats.xml")] in set(a.doc)]
    only = tuple(a.only.split(",")) if a.only else KINDS        # --only check: no edition, the checks again
    done = {}
    summ = out / "summary.json"
    if a.resume and summ.exists():
        done = {r["id"]: r for r in json.loads(summ.read_text())["docs"]
                if not r.get("errors") and r["id"] not in set(a.doc or [])}   # --doc: build those again
    todo = [j for j in jats if j.name[:-len(".jats.xml")] not in done]
    print(f"{len(jats)} documents, {len(todo)} to build, {a.workers} worker(s)", flush=True)
    rows = list(done.values())

    def save():
        summ.write_text(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), docs=rows), ensure_ascii=False,
                                   indent=0))
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_limit_memory, initargs=(a.max_gb,)) as ex:
        futs = {ex.submit(build_one, str(j), str(out), only, not a.no_check): j for j in todo}
        for i, f in enumerate(as_completed(futs), 1):
            j = futs[f]
            try:
                r = f.result()
            except Exception as e:
                r = dict(id=j.name[:-len(".jats.xml")], errors=dict(build=f"{type(e).__name__}: {e}"[:500]))
            rows.append(r)
            print(f"[{i}/{len(todo)}] {r['id']} {r.get('seconds', '?')} s"
                  + (f"  ERRORS {list(r['errors'])}" if r.get("errors") else ""), flush=True)
            if i % 5 == 0:
                save()
    save()
    with open(out / "articles.jsonl", "w", encoding="utf-8") as f:     # the dataset: one record per article
        for r in sorted(rows, key=lambda r: r["id"]):
            p = out / r["id"] / f"{r['id']}.jsonl"
            if p.exists():
                f.write(p.read_text(encoding="utf-8").strip() + "\n")
    bad = [r["id"] for r in rows if r.get("errors")]
    print(f"done: {len(rows) - len(bad)} clean, {len(bad)} with errors {bad[:10]}")
    return 0 if not bad else 1


def add_parser(sub):
    p = sub.add_parser("edition", help="derived editions from the master files: reading HTML, EPUB, two print PDFs "
                                       "(layout-faithful, one column), Markdown and a dataset record; checked")
    p.add_argument("masters", help="a folder of <id>.jats.xml + <id>.alto.xml (+ <id>.pdf, the faithful PDF)")
    p.add_argument("--out", required=True)
    p.add_argument("--doc", action="append", help="only this document id (repeatable)")
    p.add_argument("--only", help="comma list of " + ",".join(KINDS))
    p.add_argument("--workers", type=int, default=min(2, os.cpu_count() or 1))
    p.add_argument("--max-gb", type=float, default=3.0, help="address-space limit per worker")
    p.add_argument("--resume", action="store_true", help="keep the rows of documents already built cleanly "
                   "(summary.json) and build the rest; with --doc, build those again and keep every other row")
    p.add_argument("--no-check", action="store_true")
    p.set_defaults(fn=main)
    return p
