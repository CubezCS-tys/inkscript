"""Experiment 43: the judge — a model looks at one page (the scan, the scan with our blocks outlined and numbered,
and our Layout page) with our block list, and answers as data what is wrong; code (evidence43.py) checks the
evidence; only an edit with two keys (judge confident AND the code check passes) becomes a patch that is applied
(patches43.py). Otherwise a bespoke retry of the chunk (retry43.py) or the owner. Owner-approved design:
docs/ideas.md "A judge with authority, through patches"; README "The judge".

    python3 judge43.py shots  --run v33_300 --pages STEM:P ...              Layout screenshots (no calls)
    python3 judge43.py ask    --run v33_300 --pages STEM:P ... --model gemini-3.8-flash [--dry-run]   Standard calls
    python3 judge43.py batch  --run v33_300 --pagelist FILE --model gemini-3.8-flash --cap USD          Batch API
    python3 judge43.py decide --run v33_300 --model gemini-3.8-flash       two keys -> out/v33_300_judged/patches/

Answers: out/judge/answers/<model>/<run>/<stem>_pNNN.json (the answer, the block list sent, tokens, usd). Spend: every
call is a row of out/gemini_spend.jsonl (the experiment's live log); the cap is a TOTAL of that log (CAP_TOTAL).
The judge never changes a word: its actions are the patch layer's (no word-changing action exists there).
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import masters43 as M43  # noqa: E402
import run43  # noqa: E402
import patches43 as PA  # noqa: E402
import evidence43 as EV  # noqa: E402

ST, C = M43.ST, run43.C
OUT = HERE / "out"
J = OUT / "judge"
PW = HERE.parent / "40_gemini4_vlm" / "out" / "venv" / "bin" / "python"
CAP_TOTAL = 33.9235 + 5.0          # the live log's total when this work began + the owner's $5 cap for the judge
PRICE = {"gemini-3.8-flash": (0.75, 3.75), "gemini-4-argon": (2.0, 10.0)}   # Standard, per M tokens; Batch = half
THRESHOLD = 0.85                   # judge confidence needed for an automatic edit (and the evidence check)

RUNS = {
    "v33_300": dict(rules=OUT / "v33_300" / "rules", views=OUT / "v33_300" / "views", set="b"),
    "v33_300_judged": dict(rules=OUT / "v33_300_judged" / "rules", views=OUT / "v33_300_judged" / "views", set="b"),
    "v2_55": dict(rules=OUT / "v2_55" / "rules", views=OUT / "v2_55" / "views", set="a"),
    "replay": dict(rules=OUT / "replay" / "raw", views=OUT / "judge" / "views_replay", set="a"),   # views43 on out/masters
}
KINDS = ["title", "trans_title", "subtitle", "byline", "abstract", "keywords", "heading", "paragraph", "list_item",
         "quote", "verse", "boxed", "footnote", "reference", "caption", "figure", "table", "equation", "header",
         "footer", "other_article", "other"]
TYPES = ["missing_text", "text_not_on_scan", "wrong_kind", "wrong_order", "picture_box", "table_box", "note_link",
         "other_article", "verse_layout", "other"]
ACTIONS = ["mark_noise", "set_kind", "reorder", "split_block", "merge_blocks", "relink_call", "mark_other_article",
           "unmark_other_article", "fix_picture_box", "retry", "human"]


# ------------------------------------------------------------------------------------------------ the page

_arts = {}


def art(run: str, stem: str) -> dict:
    w = RUNS[run]["set"]
    if w not in _arts:
        _arts[w] = {a["stem"]: a for a in run43.articles(w)}
    ST.PAGES = OUT / "pages" if w == "b" else M43.E41 / "out" / "pages"
    return _arts[w][stem]


def chunk_answer(run: str, a: dict, p: int) -> dict:
    for x, y in ST.chunks(a):
        if x <= p <= y:
            return ST.jl(RUNS[run]["rules"] / f"{a['stem']}_c{x:03d}-{y:03d}.json")
    raise KeyError(p)


def short(t: str, n: int = 90) -> str:
    t = " ".join(t.split())
    return t if len(t) <= n else t[:n - 25] + " … " + t[-20:]


def page_view(run: str, stem: str, p: int) -> dict:
    """Our page as the judge sees it: blocks in reading order with ids p<P>b<K>, kinds, line ids, boxes (0-1000,
    x from the left), short text; the lines we left out as noise."""
    a = art(run, stem)
    rec = chunk_answer(run, a, p)
    ans = rec["answer"]
    ls, _, _ = ST.page_lines(a, p)
    L = {l["id"]: l for l in ls}
    splits = {s["line"]: s["parts"] for s in ans.get("splits") or [] if isinstance(s, dict)}

    def text(i):
        base = i.rstrip("abcdefgh") if i not in L else i
        if base != i and base in splits:
            k = "abcdefgh".index(i[-1])
            return splits[base][k] if k < len(splits[base]) else ""
        return (L.get(base) or {}).get("text", "")

    def box(i):
        base = i if i in L else i.rstrip("abcdefgh")
        return (L.get(base) or {}).get("b")

    pg = next((x for x in ans.get("pages") or [] if isinstance(x, dict) and x.get("page") == p), {"blocks": []})
    blocks, notes = [], set()
    for k, b in enumerate([b for b in pg.get("blocks") or [] if isinstance(b, dict)], 1):
        ids = PA.block_lines(b)
        bx = b.get("box")
        if not (isinstance(bx, list) and len(bx) == 4 and all(isinstance(x, (int, float)) for x in bx)):
            bx = PA_union([box(i) for i in ids])
        t = " / ".join(text(i) for i in ids) if ids else (b.get("description") or "")
        if b.get("id"):
            notes.add(b["id"])
        blocks.append(dict(id=f"p{p}b{k}", type=b.get("type"), level=b.get("level"), lines=ids,
                           box=[round(v) for v in bx] if bx else None, text=short(t),
                           n=len(ids), from_noise=bool(b.get("from_noise")), note=b.get("id"),
                           calls=[f"{c.get('marker')}@{c.get('line')}->{c.get('fn')}" for c in b.get("calls") or []
                                  if isinstance(c, dict)]))
    # notes elsewhere in the chunk count too (endnotes)
    for pg2 in ans.get("pages") or []:
        for b in (pg2.get("blocks") or []) if isinstance(pg2, dict) else []:
            if isinstance(b, dict) and b.get("id"):
                notes.add(b["id"])
    noise = [i for i in map(str, ans.get("noise") or []) if i.split(":")[0] == str(p)]
    return dict(run=run, stem=stem, page=p, blocks=blocks, notes=notes,
                noise=[dict(id=i, text=short(text(i), 60), box=box(i)) for i in noise],
                line_box={i: box(i) for b in blocks for i in b["lines"]} | {n: box(n) for n in noise},
                line_text={i: text(i) for b in blocks for i in b["lines"]})


def PA_union(bs):
    bs = [b for b in bs if b]
    if not bs:
        return None
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def block_table(v: dict) -> str:
    rows = []
    for b in v["blocks"]:
        extra = []
        if b["level"]:
            extra.append(f"level {b['level']}")
        if b["from_noise"]:
            extra.append("put back by code: the reader had called it noise")
        if b["note"]:
            extra.append(f"note id {b['note']}")
        if b["calls"]:
            extra.append("calls " + ", ".join(b["calls"][:6]))
        ln = f"lines {' '.join(b['lines'])}" if b["lines"] else "no lines"
        rows.append(f"{b['id']} | {b['type']} | {ln} | box {b['box']} | {'; '.join(extra) + ' | ' if extra else ''}"
                    f"«{b['text']}»")
    if v["noise"]:
        rows.append("LEFT OUT AS NOISE (not in the text): " + "; ".join(
            f"{n['id']} box {n['box']} «{n['text']}»" for n in v["noise"]))
    return "\n".join(rows)


COL = {"title": (200, 0, 0), "heading": (200, 0, 0), "paragraph": (0, 110, 200), "footnote": (0, 150, 0),
       "figure": (230, 120, 0), "table": (150, 0, 150), "other_article": (120, 120, 120), "verse": (0, 160, 160)}


def scan_jpeg(a: dict, p: int, outlined: dict | None = None) -> bytes:
    """The page scan (long side 1600), or with our blocks outlined and labelled by id."""
    import cv2
    img = cv2.imread(str(ST.page_image(a, p)), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    s = min(1.0, 1600 / max(h, w))
    img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    if outlined:
        H, W = img.shape[:2]
        for b in outlined["blocks"]:
            if not b["box"]:
                continue
            x0, y0, x1, y1 = (int(b["box"][0] * W / 1000), int(b["box"][1] * H / 1000),
                              int(b["box"][2] * W / 1000), int(b["box"][3] * H / 1000))
            c = COL.get(b["type"], (0, 0, 220))[::-1]
            cv2.rectangle(img, (x0, y0), (x1, y1), c, 2)
            lab = b["id"].split("b")[1]
            cv2.putText(img, lab, (x0 + 2, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 4)
            cv2.putText(img, lab, (x0 + 2, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2)
        for n in outlined["noise"]:
            if n["box"]:
                x0, y0, x1, y1 = (int(n["box"][0] * W / 1000), int(n["box"][1] * H / 1000),
                                  int(n["box"][2] * W / 1000), int(n["box"][3] * H / 1000))
                cv2.line(img, (x0, y0), (x1, y1), (60, 60, 60), 1)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()


def shot_path(run: str, stem: str, p: int) -> Path:
    return J / "shots" / run / f"{stem}_p{p:03d}.png"


def shots(run: str, stem: str, pages: list[int]):
    need = [p for p in pages if not shot_path(run, stem, p).exists()]
    if not need:
        return
    html = RUNS[run]["views"] / "mirror" / f"{stem}.html"
    pre = J / "shots" / run / stem
    pre.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(PW), str(HERE / "shots43.py"), str(pre), str(html)] + [str(p) for p in need],
                   check=True, capture_output=True, timeout=600)


def ours_jpeg(run: str, stem: str, p: int) -> bytes:
    import cv2
    img = cv2.imread(str(shot_path(run, stem, p)), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    s = min(1.0, 1600 / max(h, w))
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()


def side_path(run: str, stem: str, p: int) -> Path:
    return J / "side" / run / f"{stem}_p{p:03d}.jpg"


def side(run: str, stem: str, p: int, height: int = 1300, outlined: bool = True) -> Path:
    """scan (with our blocks outlined and numbered) | our Layout page, one JPEG (the review page's picture)."""
    import cv2
    import numpy as np
    f = side_path(run, stem, p)
    if f.exists():
        return f
    a = art(run, stem)
    shots(run, stem, [p])
    sc = cv2.imdecode(np.frombuffer(scan_jpeg(a, p, page_view(run, stem, p) if outlined else None), np.uint8),
                      cv2.IMREAD_COLOR)
    us = cv2.imread(str(shot_path(run, stem, p)), cv2.IMREAD_COLOR)
    sc = cv2.resize(sc, (round(sc.shape[1] * height / sc.shape[0]), height), interpolation=cv2.INTER_AREA)
    us = cv2.resize(us, (round(us.shape[1] * height / us.shape[0]), height), interpolation=cv2.INTER_AREA)
    o = np.full((height, sc.shape[1] + us.shape[1] + 16, 3), 255, np.uint8)
    o[:, :sc.shape[1]] = sc
    o[:, sc.shape[1] + 16:] = us
    f.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(f), o, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return f


# ------------------------------------------------------------------------------------------------ prompt

PROMPT = """You are the quality judge of a digital edition made from a scanned journal page (Arabic, sometimes French or
English). An OCR engine (Azure) read the page's lines; another model grouped those lines into blocks (kinds, reading
order, notes, pictures, tables); code drew the result as a page. You decide whether that STRUCTURE is right.

Image 1: the scan. Image 2: the same scan with our blocks outlined; each label is the block's number K (block id
p{page}bK); a thin grey diagonal marks a line we left out as noise. Image 3: our page as we draw it (reading order
right-to-left for Arabic).

Our blocks on page {page}, in our reading order (id | kind | Azure line ids | box [x0,y0,x1,y1] in 0-1000 of the
page, x from the LEFT | notes | the text, shortened):
{blocks}

Look for these problems only:
- text_not_on_scan: our text that is not printed on this side of the paper: show-through (the reverse side's
  print seen through the paper, pale and MIRRORED), bleed from a facing page, scanner junk (specks, borders, stamps
  read as letters). Garbled words in our text where the scan shows only faint mirrored print are the sign.
  Action mark_noise with every affected line id and kind show-through | bleed | scanner-junk.
- missing_text: printed text on the scan that our page does not show (a line, a side tab, a caption, a box).
  Action human (or retry with an instruction) — you cannot add text.
- wrong_kind: a block of the wrong kind (a signature drawn as a heading, a running head as a paragraph, a caption
  as a paragraph, an author and an affiliation run into one byline...). Action set_kind, or split_block (at_line =
  the first line of the second part, kind = its kind).
- wrong_order: blocks read in the wrong order (columns crossed, a footnote before the body...). Action reorder with
  the full new order of ALL block ids of the page.
- picture_box: a picture missing, cut, shredded into pieces, or its box covering text. Action fix_picture_box with
  the corrected box, or retry/human.
- table_box: a table drawn wrong (a table split across two columns drawn as one box over the text, cells lost).
  Action retry with an instruction, or human.
- note_link: a note call linked to the wrong note or not at all. Action relink_call (line, marker as printed, fn =
  the note id) when the note exists in our list.
- other_article: a block that belongs to a different article (or an advertisement) is in our text, or one of ours is
  wrongly marked other_article. Action mark_other_article / unmark_other_article.
- verse_layout: poetry drawn wrong (hemistichs joined or split wrongly, two printed lines in one row). Action retry
  with an instruction, or human.
- other: anything else structural.

Rules:
- NEVER propose changing, adding or correcting words, spelling, letters, punctuation or numbers. Misread words,
  lost diacritics, wrong brackets or hyphens are NOT your business: ignore them. Your actions only move, relabel,
  remove (not printed on this side) or re-box what is there.
- Compare with the scan, not with what a page "usually" has. A page our blocks render faithfully is "none": answer
  {{"verdict": "none", "problems": []}}. Do not report small differences of drawing (fonts, line breaks, justification,
  spacing) — only structure that a reader would find wrong.
- confidence 0-1 = how sure you are that the problem is real AND your action fixes it. Use >= 0.9 only when the
  scan shows it plainly.
- evidence: one sentence on what the scan shows (where, what it looks like).
- Use our ids exactly (block ids p{page}bK, line ids as listed). For mark_noise give the blocks whose every line
  is not printed on this side, and/or the single line ids.
- route "patch" with an action from the list; "retry" with a short instruction for the reader model when it should
  look at the region again; "human" when only a person can settle it.
"""

# v2 (2026-10-20, after calibrating v1: Flash caught 3 of 10 known problems): the same, plus a checklist the
# judge answers first, question by question (docs/ideas.md: "answers fixed questions as data")
PROMPT_V2 = PROMPT.replace("""
Rules:
""", """CHECKS_PLACEHOLDER
Rules:
""", 1)
PROMPT_V2 = PROMPT_V2.replace("CHECKS_PLACEHOLDER", """
First go through these nine questions in order, comparing the scan (image 1) with our page (image 3) region by
region, and answer each in "checks" in a few words ("ok" or what is wrong and where):
 1 show-through: is any text of ours not printed on this side (pale mirrored print from the reverse, bleed, junk)?
 2 missing: is any printed text missing from our page (a line, a side tab or margin label, a caption, a stamp with
   words)? Running heads and page numbers count too.
 3 pictures: is every picture, drawing and ornament drawn whole, in its place, as one piece, not over text, and is
   no picture missing (e.g. one of a pair of ornaments)?
 4 tables: is every table drawn like the print (a table printed in two parts in two columns = two parts, each in
   its own place; no table box over running text)?
 5 kinds: is each block the right kind — title, heading, byline (an author and an affiliation are two blocks),
   signature at the end (not a heading), caption, running head, footnote?
 6 order: does the reading order follow the columns? (A paragraph that runs from the foot of one column to the
   top of the next is ONE block and right. The title may be printed low on the page: its place in the order does
   not matter.)
 7 notes: are the notes laid out as printed (notes printed side by side in one row are separate notes) and does
   each call point to its note? (A star, ٥ or other ornament between verse halves is not a call.)
 8 verse: are the poem's lines and hemistichs as printed (one printed line per row, halves not joined)?
 9 other article: is any block of a different article or an advertisement in our text, or is one of ours wrongly
   marked other_article?
Then list every "no" as a problem below (a problem for each wrong thing).
""")
PROMPTS = {"v1": PROMPT, "v2": PROMPT_V2}
PV = "v1"                          # judge43 --prompt; answers of v2 go to <model>_v2/

SCHEMA = {"type": "object", "properties": {
    "verdict": {"type": "string", "enum": ["none", "problems"]},
    "problems": {"type": "array", "items": {"type": "object", "properties": {
        "type": {"type": "string", "enum": TYPES},
        "subtype": {"type": "string"},
        "blocks": {"type": "array", "items": {"type": "string"}},
        "lines": {"type": "array", "items": {"type": "string"}},
        "box": {"type": "array", "items": {"type": "integer"}},
        "confidence": {"type": "number"},
        "evidence": {"type": "string"},
        "route": {"type": "string", "enum": ["patch", "retry", "human"]},
        "action": {"type": "string", "enum": ACTIONS},
        "kind": {"type": "string"},
        "order": {"type": "array", "items": {"type": "string"}},
        "at_line": {"type": "string"},
        "line": {"type": "string"},
        "marker": {"type": "string"},
        "fn": {"type": "string"},
        "new_box": {"type": "array", "items": {"type": "integer"}},
        "instruction": {"type": "string"},
    }, "required": ["type", "confidence", "evidence", "route", "action"]}},
}, "required": ["verdict", "problems"]}


SCHEMA_V2 = {"type": "object", "properties": dict(checks={"type": "array", "items": {"type": "string"}},
                                                  **SCHEMA["properties"]),
             "required": ["checks", "verdict", "problems"]}


def rest_schema(s):
    """The schema in the REST shape the Batch JSONL takes (types upper-case)."""
    if isinstance(s, dict):
        return {k: (v.upper() if k == "type" else rest_schema(v)) for k, v in s.items()}
    if isinstance(s, list):
        return [rest_schema(x) for x in s]
    return s


def request(run: str, stem: str, p: int):
    a = art(run, stem)
    v = page_view(run, stem, p)
    shots(run, stem, [p])
    imgs = [scan_jpeg(a, p), scan_jpeg(a, p, v), ours_jpeg(run, stem, p)]
    return PROMPTS[PV].format(page=p, blocks=block_table(v)), imgs, v


def mdir(model: str) -> str:
    return model if PV == "v1" else f"{model}_{PV}"


def schema():
    return SCHEMA if PV == "v1" else SCHEMA_V2


def answer_path(model: str, run: str, stem: str, p: int) -> Path:
    """model may already be a dir name (gemini-3.8-flash_v2)"""
    return J / "answers" / (model if "_v" in model else mdir(model)) / run / f"{stem}_p{p:03d}.json"


def ask(run: str, stem: str, p: int, model: str, dry: bool = False) -> dict | None:
    f = answer_path(model, run, stem, p)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    prompt, imgs, v = request(run, stem, p)
    est = int(len(prompt) / 2.5) + 1200 * len(imgs)
    if dry:
        print(f"  {stem} p{p}: ~{est} input tokens, {len(v['blocks'])} blocks")
        return None
    C.CAP = CAP_TOTAL
    info = {}
    ans, usd = C.gemini(prompt, images=imgs, tag=f"judge_{mdir(model)}_{run}_{stem}_p{p:03d}", model=model, max_out=6000,
                        schema=schema(), thinking="low", json_out=True, est_in=est, info=info)
    rec = dict(run=run, stem=stem, page=p, model=model, prompt=PV, mode="standard", usd=usd, answer=ans, view=_jsonable(v),
               **{k: info.get(k) for k in ("finish", "tin", "tout", "think", "secs", "cached", "error")})
    if ans is not None:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {stem} p{p} {model}: ${usd:.4f} {info.get('tin')}/{info.get('tout')} "
          f"{(ans or {}).get('verdict')} {len((ans or {}).get('problems') or [])}  [log ${C.spent():.3f}]", flush=True)
    return rec


def _jsonable(v):
    return {k: (sorted(x) if isinstance(x, set) else x) for k, x in v.items()}


# ------------------------------------------------------------------------------------------------ batch

def log_spend(tag, model, tin, tout, think, usd, finish, mode):
    total = C.spent() + usd
    with open(C.SPEND, "a") as f:
        f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=model, tag=tag, tin=tin, tout=tout,
                                think=think, usd=round(usd, 6), secs=None, finish=finish, mode=mode,
                                total=round(total, 4))) + "\n")


def batch(run: str, pages: list[tuple[str, int]], model: str, cap_total: float, poll: int = 30):
    """All pages in one Batch job (Flash: a page is ~6k tokens in); answers saved like ask()'s."""
    from google.genai import types
    st_f = J / f"batch_{mdir(model)}_{run}.json"
    state = json.loads(st_f.read_text()) if st_f.exists() else {}
    client = C._client()
    pin, pout = (x / 2 for x in PRICE[model])
    if not state.get("job"):
        todo = [(s, p) for s, p in pages if not answer_path(model, run, s, p).exists()]
        lines, keys, worst, views = [], [], 0.0, {}
        for s, p in todo:
            prompt, imgs, v = request(run, s, p)
            parts = []
            for k, im in enumerate(imgs, 1):
                parts.append({"text": f"Image {k}:"})
                parts.append({"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(im).decode()},
                              "mediaResolution": {"level": "MEDIA_RESOLUTION_HIGH"}})
            parts.append({"text": prompt})
            key = f"judge_{mdir(model)}_{run}_{s}_p{p:03d}"
            req = {"contents": [{"role": "user", "parts": parts}],
                   "generationConfig": {"maxOutputTokens": 6000, "responseMimeType": "application/json",
                                        "responseSchema": rest_schema(schema()),
                                        "thinkingConfig": {"thinkingLevel": "LOW"}}}
            w = (len(prompt) / 2.5 + 1200 * len(imgs)) / 1e6 * pin + 6000 / 1e6 * pout
            if C.spent() + worst + w > cap_total:
                print(f"  cap: job cut at {len(lines)} of {len(todo)} pages (worst ${worst:.3f})", flush=True)
                break
            worst += w
            lines.append(json.dumps({"key": key, "request": req}) + "\n")
            keys.append(key)
            views[key] = _jsonable(v)
        if not lines:
            print("nothing to send")
            return
        bf = J / "batch" / f"{mdir(model)}_{run}.jsonl"
        bf.parent.mkdir(parents=True, exist_ok=True)
        bf.write_text("".join(lines), encoding="utf-8")
        (J / "batch" / f"{mdir(model)}_{run}_views.json").write_text(json.dumps(views, ensure_ascii=False))
        up = client.files.upload(file=str(bf), config=types.UploadFileConfig(display_name=f"judge-{run}",
                                                                             mime_type="jsonl"))
        job = client.batches.create(model=model, src=up.name, config={"display_name": f"judge-{run}"})
        state = dict(job=job.name, keys=keys, worst=round(worst, 4), sent=time.strftime("%Y-%m-%d %H:%M:%S"))
        st_f.write_text(json.dumps(state, indent=1))
        print(f"  {len(lines)} pages, worst ${worst:.3f}, job {job.name}", flush=True)
    while True:
        job = client.batches.get(name=state["job"])
        s = job.state.name if hasattr(job.state, "name") else str(job.state)
        print(f"  {time.strftime('%H:%M:%S')} {s}", flush=True)
        if s in run43.DONE_STATES:
            break
        time.sleep(poll)
    if s != "JOB_STATE_SUCCEEDED" or state.get("collected"):
        return
    views = json.loads((J / "batch" / f"{mdir(model)}_{run}_views.json").read_text())
    rows = [json.loads(x) for x in client.files.download(file=job.dest.file_name).decode().splitlines() if x.strip()]
    n = 0
    for row in rows:
        key = row.get("key")
        resp = row.get("response") or {}
        um = resp.get("usageMetadata") or {}
        tin, think = um.get("promptTokenCount") or 0, um.get("thoughtsTokenCount") or 0
        tout = (um.get("candidatesTokenCount") or 0) + think
        usd = tin / 1e6 * pin + tout / 1e6 * pout
        cand = (resp.get("candidates") or [{}])[0]
        fin = str(cand.get("finishReason") or row.get("error") or "none")
        log_spend(key, model, tin, tout, think, usd, fin, "batch")
        text = "".join(x.get("text", "") for x in (cand.get("content") or {}).get("parts") or [] if not x.get("thought"))
        try:
            ans = json.loads(text)
        except Exception:
            ans = None
        s_, p_ = key[len(f"judge_{mdir(model)}_{run}_"):].rsplit("_p", 1)
        rec = dict(run=run, stem=s_, page=int(p_), model=model, prompt=PV, mode="batch", usd=usd, answer=ans, view=views.get(key),
                   finish=fin, tin=tin, tout=tout, think=think)
        f = answer_path(model, run, s_, int(p_))
        f.parent.mkdir(parents=True, exist_ok=True)
        if ans is None:
            f = f.with_suffix(".failed.json")
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        n += ans is not None
    state["collected"] = True
    st_f.write_text(json.dumps(state, indent=1))
    print(f"  collected {n}/{len(rows)}; log ${C.spent():.3f}", flush=True)


# ------------------------------------------------------------------------------------------------ two keys

def decide(rec: dict, threshold: float = THRESHOLD) -> list[dict]:
    """Every problem of one judged page with its route: auto (two keys), retry, human, or none; a patch when auto
    or proposed."""
    run, stem, p = rec["run"], rec["stem"], rec["page"]
    v = rec["view"] or page_view(run, stem, p)
    v = dict(v, notes=set(v.get("notes") or []))
    E = None
    B = {b["id"]: b for b in v["blocks"]}
    out = []
    for k, pr in enumerate((rec.get("answer") or {}).get("problems") or [], 1):
        act, conf = pr.get("action"), float(pr.get("confidence") or 0)
        f = dict(n=k, type=pr.get("type"), subtype=pr.get("subtype"), confidence=conf, evidence=pr.get("evidence"),
                 action=act, judge_route=pr.get("route"), instruction=pr.get("instruction"),
                 blocks=pr.get("blocks") or [], lines=pr.get("lines") or [])
        if act in ("retry", "human") or pr.get("route") in ("retry", "human") or act not in PA.ACTIONS:
            f["route"] = "retry" if (act == "retry" or pr.get("route") == "retry") else "human"
            f["check"] = dict(ok=None, why="no edit proposed")
            if pr.get("type") in ("wrong_order", "other"):
                # "columns mixed": a block running from the foot of one column to the top of the next is right
                import re
                named = [b for b in dict.fromkeys(f["blocks"] + re.findall(r"p\d+b\d+", pr.get("evidence") or ""))
                         if b in B]
                named = [b for b in named if B[b]["type"] in EV.RUNNING]      # a table across columns is no run-on
                spans = [EV.continuation(B[b], v["line_box"]) for b in named]
                spans = [(b, c) for b, c in zip(named, spans) if c["why"] != "one column" and c["why"] != "too few lines"]
                if spans and all(c["ok"] for _, c in spans):
                    f["route"] = "dismissed"
                    f["check"] = dict(ok=False, why="code: " + "; ".join(f"{b} {c['why']}" for b, c in spans))
                elif spans:
                    f["check"] = dict(ok=True, why="code: " + "; ".join(f"{b} {c['why']}" for b, c in spans))
            out.append(f)
            continue
        bl = [b for b in f["blocks"] if b in B]
        targets = dict(lines=[], blocks=[dict(id=b, lines=B[b]["lines"], type=B[b]["type"], box=B[b]["box"]) for b in bl])
        payload = {}
        if act == "mark_noise":
            lines = list(f["lines"]) or [i for b in bl for i in B[b]["lines"]]
            known = set(v["line_box"])
            lines = [i for i in lines if i in known and i not in {n["id"] for n in v["noise"]}]
            targets = dict(lines=lines, blocks=[])
            kind = pr.get("subtype") or pr.get("kind") or "show-through"
            payload = dict(kind=kind if kind in PA.NOISE_KINDS else "show-through")
            if E is None:
                E = EV.PageEvidence(art(run, stem), p)
            chk = E.noise_check(lines) if lines else dict(ok=False, why="no known lines")
            if not chk["ok"] and chk.get("lines_pass") and len(chk["lines_pass"]) >= 0.5 * len(lines):
                # the judge lumped some real lines in: keep only the lines that pass alone
                kept = chk["lines_pass"]
                chk2 = E.noise_check(kept)
                if chk2["ok"]:
                    chk = dict(chk2, why=chk2["why"] + f"; {len(lines) - len(kept)} of {len(lines)} lines left out "
                                                        f"(they failed alone)")
                    targets["lines"] = kept
        else:
            payload = {"set_kind": dict(kind=pr.get("kind"), level=None),
                       "split_block": dict(at_line=pr.get("at_line"), kind=pr.get("kind")),
                       "reorder": dict(order=pr.get("order") or [],
                                       fp={b: PA.fingerprint(dict(type=B[b]["type"], lines=B[b]["lines"],
                                                                  box=B[b]["box"])) for b in B}),
                       "relink_call": dict(line=pr.get("line"), marker=pr.get("marker"), fn=pr.get("fn")),
                       "unmark_other_article": dict(kind=pr.get("kind")),
                       "fix_picture_box": dict(box=pr.get("new_box") or pr.get("box"))}.get(act, {})
            pv = dict(v, blocks=v["blocks"])
            chk = EV.check(act, dict(payload, blocks=bl), pv)
        f["check"] = dict(ok=chk["ok"], why=chk["why"], **{k: chk[k] for k in ("pale", "nonword", "conf") if k in chk})
        auto = conf >= threshold and chk["ok"]
        f["route"] = "auto" if auto else ("human" if act == "mark_noise" and not chk["ok"] else "retry"
                                          if pr.get("route") == "retry" else "human")
        f["patch"] = dict(id=f"j-{stem[:4]}-p{p}-{k}", run=run, article=stem, page=p, action=act, targets=targets,
                          payload=payload, source="judge", confidence=conf, evidence=pr.get("evidence"),
                          reason=f"{pr.get('type')}: {chk['why']}", created=time.strftime("%Y-%m-%d %H:%M"),
                          apply=auto, model=rec.get("model"))
        out.append(f)
    return out


def write_patches(model: str, run: str, dst: Path):
    """Every judged page's proposals -> dst/patches/<stem>.json (judge patches replaced, others kept)."""
    by = {}
    for f in sorted((J / "answers" / mdir(model) / run).glob("*_p[0-9][0-9][0-9].json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        for x in decide(rec):
            if x.get("patch"):
                by.setdefault(rec["stem"], []).append(x["patch"])
    pdir = dst / "patches"
    for s, ps in by.items():
        keep = [p for p in PA.load_patches(pdir, s) if p.get("source") != "judge"]
        PA.save_patches(pdir, s, keep + ps)
    n = sum(len(v) for v in by.values())
    auto = sum(p["apply"] for v in by.values() for p in v)
    print(f"{n} proposed edits in {len(by)} articles, {auto} with two keys -> {pdir}")
    return by


def parse_pages(xs) -> list[tuple[str, int]]:
    out = []
    for x in xs:
        s, p = x.rsplit(":", 1)
        out.append((s, int(p)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["shots", "ask", "batch", "decide", "show", "side"])
    ap.add_argument("--run", default="v33_300")
    ap.add_argument("--pages", nargs="*", default=[])
    ap.add_argument("--pagelist")
    ap.add_argument("--model", default="gemini-3.8-flash")
    ap.add_argument("--cap", type=float, default=CAP_TOTAL, help="log total not to cross")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prompt", default="v1", choices=["v1", "v2"])
    ap.add_argument("--out", default=str(OUT / "v33_300_judged"))
    a = ap.parse_args()
    global PV
    PV = a.prompt
    pages = parse_pages(a.pages + (Path(a.pagelist).read_text().split() if a.pagelist else []))
    if a.cmd == "shots":
        by = {}
        for s, p in pages:
            by.setdefault(s, []).append(p)
        for s, ps in by.items():
            art(a.run, s)
            shots(a.run, s, ps)
            print(s, ps, flush=True)
    elif a.cmd == "side":
        for s, p in pages:
            print(side(a.run, s, p))
    elif a.cmd == "show":
        for s, p in pages:
            print(block_table(page_view(a.run, s, p)))
    elif a.cmd == "ask":
        for s, p in pages:
            ask(a.run, s, p, a.model, a.dry_run)
    elif a.cmd == "batch":
        batch(a.run, pages, a.model, min(a.cap, CAP_TOTAL))
    elif a.cmd == "decide":
        write_patches(a.model, a.run, Path(a.out))


if __name__ == "__main__":
    main()
