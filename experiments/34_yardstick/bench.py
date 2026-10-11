#!/usr/bin/env python3
"""Public Arabic OCR test sets, turned into our gold format.

    python bench.py list
    python bench.py fetch NAME --out DIR [--limit N] [--offset K]
    python bench.py run NAME --gold DIR --pred DIR [--reader "CMD {image} {out}"]

`fetch` uses only the Python standard library. It reads rows from the
Hugging Face "datasets-server" rows API (100 rows per request at most) and
writes, for each sample, the image and `<id>.gold.json`:

    {"schema": "inkscript-gold/1", "page_id": id, "source": "kitab|misraj",
     "benchmark": NAME, "lines": [{"id": "l001", "text": ...}],
     "tables": [{"id": "t1", "html": ...}], "equations": [], "text": ...}

These are TEST sets. Never train or tune on them (see benchmarks.md).
Downloads are untrusted data: this script only writes bytes and JSON; it
never executes or unpickles anything it downloads.

Every dataset id, split and field name below was checked on 2026-10-11
against https://datasets-server.huggingface.co/info and one sample row.
"""
import argparse
import ast
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROWS_API = "https://datasets-server.huggingface.co/rows"
UA = {"User-Agent": "inkscript-bench/0.1"}

# kind: how the gold is stored in the row
#   "text"       one string (a line or a paragraph); newlines/tabs split lines
#   "markdown"   page markdown; HTML <table>s go to "tables"
#   "lines_json" JSON list of {"line_index","bbox":{x1,y1,x2,y2},"text","class"}
#   "table_code" an HTML page in field "code"; keep its <table>; only rows
#                whose metadata "_pipeline" contains "HTML" (as KITAB does)
K = "ahmedheakl/arocrbench_"
SUBSETS = {
    # --- KITAB-Bench, printed text (in scope) ---
    "kitab-hindawi":   dict(source="kitab", dataset=K + "hindawi", rows=200, field="text", kind="text",
                            what="printed book pages (Hindawi e-books), page images 612x792, gold lines tab-separated"),
    "kitab-historicalbooks": dict(source="kitab", dataset=K + "historicalbooks", rows=10, field="answer", kind="text",
                            what="old printed/manuscript book pages, newline-separated lines"),
    "kitab-patsocr":   dict(source="kitab", dataset=K + "patsocr", rows=500, field="answer", kind="text",
                            what="printed text lines (PATS-A01, several fonts)"),
    "kitab-synthesizear": dict(source="kitab", dataset=K + "synthesizear", rows=500, field="text", kind="text",
                            what="synthetic printed lines, many fully vowelled"),
    "kitab-historyar": dict(source="kitab", dataset=K + "historyar", rows=200, field="text", kind="text",
                            what="lines from historical printed Arabic books"),
    "kitab-isippt":    dict(source="kitab", dataset=K + "isippt", rows=500, field="text", kind="text",
                            what="text lines from slides (ISI-PPT)"),
    "kitab-arabicocr": dict(source="kitab", dataset=K + "arabicocr", rows=50, field="text", kind="text",
                            what="small printed snippets"),
    "kitab-adab":      dict(source="kitab", dataset=K + "adab", rows=200, field="text", kind="text",
                            what="single printed words/short phrases (ADAB)"),
    "kitab-lines":     dict(source="kitab", dataset=K + "ourslines", rows=378, field="data", kind="lines_json",
                            what="full pages with gold line boxes and line text (line detection + recognition)"),
    "kitab-tables":    dict(source="kitab", dataset=K + "tables", rows=456, field="code", kind="table_code",
                            what="synthetic rendered Arabic tables; gold HTML table (HTML-pipeline rows only)"),
    # --- KITAB-Bench, out of scope for us (listed so the totals match the paper) ---
    "kitab-evarest":   dict(source="kitab", dataset=K + "evarest", rows=800, field="text", kind="text",
                            what="OUT OF SCOPE: scene text word crops", scope="out"),
    "kitab-khatt":     dict(source="kitab", dataset=K + "khatt", rows=200, field="text", kind="text",
                            what="OUT OF SCOPE: handwriting lines (KHATT)", scope="out"),
    "kitab-khattparagraph": dict(source="kitab", dataset=K + "khattparagraph", rows=200, field="answer", kind="text",
                            what="OUT OF SCOPE: handwritten paragraphs (KHATT)", scope="out"),
    "kitab-onlinekhatt": dict(source="kitab", dataset=K + "onlinekhatt", rows=200, field="text", kind="text",
                            what="OUT OF SCOPE: online handwriting", scope="out"),
    "kitab-muharaf":   dict(source="kitab", dataset=K + "muharaf", rows=200, field="text", kind="text",
                            what="OUT OF SCOPE: handwritten archive lines (Muharaf)", scope="out"),
    # --- page-level markdown sets ---
    "kitab-pdf2md-reviewed": dict(source="misraj", dataset="Misraj/KITAB_pdf_to_markdown_reviewed", rows=62,
                            field="markdown", kind="markdown",
                            what="KITAB PDF-to-Markdown pages, gold corrected by Misraj (Apache-2.0)"),
    "misraj-dococr":   dict(source="misraj", dataset="Misraj/Misraj-DocOCR", rows=400, field="markdown",
                            kind="markdown", id_field="uuid",
                            what="400 expert-checked Arabic pages (real + synthetic), gold markdown (Apache-2.0)"),
}
for _v in SUBSETS.values():
    _v.setdefault("config", "default")
    _v.setdefault("split", "train")
    _v.setdefault("image_field", "image")
    _v.setdefault("scope", "in")

TABLE_RE = re.compile(r"<table[\s\S]*?</table>", re.IGNORECASE)
SAFE_ID = re.compile(r"[^A-Za-z0-9._-]")


def http_get(url, binary=False, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else json.loads(data.decode("utf-8"))
        except Exception as e:  # rate limits (429) and transient errors
            if attempt == tries - 1:
                raise
            print(f"  retry after error: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))


def fetch_rows(spec, offset, length):
    q = urllib.parse.urlencode({"dataset": spec["dataset"], "config": spec["config"],
                                "split": spec["split"], "offset": offset, "length": length})
    return http_get(f"{ROWS_API}?{q}")["rows"]


def split_lines(text):
    return [s.strip() for s in re.split(r"[\n\t]+", text or "") if s.strip()]


def lines_obj(texts):
    return [{"id": f"l{i:03d}", "text": t} for i, t in enumerate(texts, 1)]


def parse_meta(s):
    try:
        return json.loads(s)
    except Exception:
        try:
            return ast.literal_eval(s)  # literal_eval only parses literals; it never runs code
        except Exception:
            return {}


def to_gold(name, spec, row, page_id):
    val = row.get(spec["field"])
    gold = {"schema": "inkscript-gold/1", "page_id": page_id, "source": spec["source"],
            "benchmark": name, "dataset": spec["dataset"], "lines": [], "tables": [],
            "equations": [], "text": ""}
    kind = spec["kind"]
    if kind == "text":
        gold["text"] = val or ""
        gold["lines"] = lines_obj(split_lines(val))
    elif kind == "markdown":
        md = val or ""
        tables = TABLE_RE.findall(md)
        gold["text"] = md
        gold["tables"] = [{"id": f"t{i}", "html": h} for i, h in enumerate(tables, 1)]
        body = TABLE_RE.sub("\n", md)
        gold["lines"] = lines_obj([s.strip() for s in body.split("\n") if s.strip()])
    elif kind == "lines_json":
        items = json.loads(val) if isinstance(val, str) else (val or [])
        lines = []
        for i, it in enumerate(items, 1):
            b = it.get("bbox") or {}
            lines.append({"id": f"l{i:03d}", "text": it.get("text", ""),
                          "box": [b.get("x1"), b.get("y1"), b.get("x2"), b.get("y2")],
                          "class": it.get("class")})
        gold["lines"] = lines
        gold["text"] = "\n".join(l["text"] for l in lines)
    elif kind == "table_code":
        meta = parse_meta(row.get("metadata", ""))
        if "HTML" not in str(meta.get("_pipeline", "")):
            return None  # KITAB scores TEDS on the HTML-pipeline rows only
        m = TABLE_RE.search(val or "")
        html = m.group(0) if m else ""
        gold["tables"] = [{"id": "t1", "html": html}]
        gold["text"] = ""
        gold["category"] = row.get("category")
    else:
        raise ValueError(kind)
    return gold


def image_ext(src):
    path = urllib.parse.urlparse(src).path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".img"


def cmd_list(_args):
    print(f"{'name':24} {'rows':>5} {'scope':5}  dataset [config/split] field -> what")
    for name, s in SUBSETS.items():
        print(f"{name:24} {s['rows']:>5} {s['scope']:5}  {s['dataset']} [{s['config']}/{s['split']}] "
              f"{s['field']}:{s['kind']} -> {s['what']}")


def cmd_fetch(args):
    spec = SUBSETS.get(args.name)
    if not spec:
        sys.exit(f"unknown subset {args.name!r}; see `bench.py list`")
    os.makedirs(args.out, exist_ok=True)
    total = spec["rows"] if args.limit is None else min(args.limit, spec["rows"])
    offset, written, skipped = args.offset, 0, 0
    while written < total and offset < spec["rows"]:
        want = total - written
        if spec["kind"] == "table_code":
            want = max(want, 10)  # some rows are skipped (CSV pipeline), so ask for a few more
        rows = fetch_rows(spec, offset, min(100, want, spec["rows"] - offset))
        if not rows:
            break
        for r in rows:
            row, idx = r["row"], r["row_idx"]
            raw_id = row.get(spec.get("id_field", ""), None) or f"{args.name}-{idx:05d}"
            page_id = SAFE_ID.sub("_", str(raw_id))[:80]
            gold = to_gold(args.name, spec, row, page_id)
            if gold is None:
                skipped += 1
                continue
            img = row.get(spec["image_field"]) or {}
            src = img.get("src") if isinstance(img, dict) else None
            if src:
                fname = page_id + image_ext(src)
                with open(os.path.join(args.out, fname), "wb") as f:
                    f.write(http_get(src, binary=True))
                gold["image"] = fname
                gold["image_size"] = [img.get("width"), img.get("height")]
            with open(os.path.join(args.out, page_id + ".gold.json"), "w", encoding="utf-8") as f:
                json.dump(gold, f, ensure_ascii=False, indent=1)
            written += 1
            if written >= total:
                break
        offset += len(rows)
    print(f"{args.name}: wrote {written} samples to {args.out}" + (f" (skipped {skipped} non-HTML tables)" if skipped else ""))


READER_CONTRACT = """\
Reader contract
---------------
For every <id>.gold.json in --gold there is an image <id>.<ext> beside it
(the gold's "image" field names it). The reader reads that image only
(never the gold) and writes ONE of these into --pred:

  <id>.pred.json  {"lines": [{"text": "..."}],          # reading order
                   "tables": [{"html": "<table>...</table>"}],
                   "equations": [{"latex": "..."}]}
  <id>.txt        plain UTF-8 text, one line per printed line

Missing outputs count as empty predictions (all characters deleted).
With --reader, this script calls the command once per image, without a
shell, after replacing {image} and {out} (out = the .pred.json path):

  python bench.py run misraj-dococr --gold G --pred P --reader "myreader {image} {out}"

Then score:

  inkscript score --gold G --pred P
"""


def cmd_run(args):
    print(READER_CONTRACT)
    if not args.reader:
        return
    if not (args.gold and args.pred):
        sys.exit("--reader needs --gold and --pred")
    os.makedirs(args.pred, exist_ok=True)
    golds = sorted(f for f in os.listdir(args.gold) if f.endswith(".gold.json"))
    for g in golds:
        with open(os.path.join(args.gold, g), encoding="utf-8") as f:
            gold = json.load(f)
        if gold.get("benchmark") not in (None, args.name):
            continue
        image = os.path.join(args.gold, gold.get("image", ""))
        out = os.path.join(args.pred, gold["page_id"] + ".pred.json")
        if os.path.exists(out) or os.path.exists(out[:-len(".pred.json")] + ".txt"):
            continue  # resume
        argv = [a.replace("{image}", image).replace("{out}", out) for a in shlex.split(args.reader)]
        t0 = time.time()
        rc = subprocess.run(argv).returncode
        print(f"{gold['page_id']}: rc={rc} {time.time() - t0:.1f}s")
    print(f"\nnext: inkscript score --gold {args.gold} --pred {args.pred}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    f = sub.add_parser("fetch")
    f.add_argument("name")
    f.add_argument("--out", required=True)
    f.add_argument("--limit", type=int)
    f.add_argument("--offset", type=int, default=0)
    f.set_defaults(fn=cmd_fetch)
    r = sub.add_parser("run")
    r.add_argument("name")
    r.add_argument("--gold")
    r.add_argument("--pred")
    r.add_argument("--reader", help='command with {image} and {out}, e.g. "myreader {image} {out}"')
    r.set_defaults(fn=cmd_run)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
