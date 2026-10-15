"""Experiment 40, approach D: "draft, look again, fix" — a multi-pass loop with gemini-4-argon.

    /home/yassine/inkscript/.venv/bin/python D_agentic.py run VARIANT [--pages pid ...|--explore|--all]
    /home/yassine/inkscript/.venv/bin/python D_agentic.py gallery VARIANT      (before/after pictures of every fix)
    /home/yassine/inkscript/.venv/bin/python D_agentic.py dial                 (cost and gain of each pass)

Pass 1 (draft): the whole page image -> semantic HTML (FORMAT.md), every top-level block with data-id and data-bbox,
        thinking low.
Pass 2 (look again): the draft's blocks are grouped into REGIONS to check — tables, equations, verse, footnotes
        (always) and, in the Azure variants, any block whose letters disagree with Azure's lines inside its box.
        Each region is cut from the 300 dpi scan (zoomed: the crop gets the whole image budget the page had) and sent
        with the draft fragment; the model answers {"verdict": "ok"|"fixed", "html": ..., "changes": [...]} and a
        fixed fragment replaces the draft's blocks.
Pass 3 (consistency, optional): the whole page + the current HTML -> a short list of edits (dropped or duplicated
        text, wrong block type, order, footnote links), applied by data-id.

Variants (out/D_agentic/<variant>/<pid>.html + <pid>.meta.json with the real cost of every pass):
  p1      pass 1 only (the draft)
  s       p1 + pass 2 on structural regions (table, equation, verse, footnote); no Azure anywhere
  sa      s + blocks that disagree with Azure (Azure only chooses WHERE to look; its text is not shown)
  sah     sa, and Azure's reading of each region is shown to the model as a hint (the image is the judge)
  ...c    the same + pass 3 (e.g. sc, sahc)
  ..._m   pass 2 at thinking medium (e.g. sah_m)
Every call is tagged D_agentic_<pass>_<pid>_<hash> and capped by common.gemini (sub-cap $3.5 on "D_agentic").
"""
from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import html as htmlmod
import json
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import OUT, SPEND, azure_lines, gemini, page_ids, page_image_path, page_info, spent, strip_fences  # noqa

from inkscript.gold.text import folded  # noqa: E402
import lxml.html  # noqa: E402

TAG = "D_agentic"
SUBCAP = (TAG, 3.5)
D = OUT / "D_agentic"
EXPLORE = ["0747-001-003-001_p006", "0474-008-013-001_p036", "bd_2502-000-041-029_p021",
           "0355-000-002-006_p017", "0018-010-003-002_p003"]
WLOCK = threading.Lock()

FORMAT_RULES = """Output format: semantic HTML (a fragment, no <html>/<head>/<body>), blocks in reading order (Arabic pages read
right to left; in multi-column pages finish the right column before the left one).
* title, section headings: <h1>/<h2>/<h3>; body paragraph: <p> (one per printed paragraph, lines joined with spaces)
* numbered / bulleted list: <ol>/<ul> with <li>; bibliography / references: <ol class="references"> with <li>
* footnote: <aside class="footnote" id="fnN">…</aside>; its marker in the text: <sup><a href="#fnN">N</a></sup>
* verse (a line of poetry in two half-lines): <div class="verse"><span class="hemistich">…</span><span class="hemistich">…</span></div>, one div per verse line
* table: <table> with <tr>, <th>/<td>, rowspan/colspan as printed, caption in <caption>
* equation: inline <span class="math">\\(…\\)</span>; display <div class="equation"><span class="math">\\[…\\]</span></div> (LaTeX)
* figure / picture / chart: <figure> (+ <figcaption>)
* running header, footer, page number: <header class="furniture">…</header> / <footer class="furniture">…</footer>
* anything else: <div class="other">
* dir="rtl"/"ltr" and lang="ar"/"fr"/"en" on blocks.
Text: exactly what is printed — every letter, every vowel mark (tashkeel, shadda, tanween) that is printed, digits as
printed (Arabic-Indic stays Arabic-Indic), punctuation as printed. No tatweel. Do not correct, modernise or complete
anything; do not translate."""

P1 = """You are transcribing one scanned page of an Arabic journal article into a faithful digital edition.

""" + FORMAT_RULES + """

Every TOP-LEVEL block (each h1/h2/h3, p, ol, ul, aside, div.verse, table, div.equation, figure, header, footer,
div.other) carries data-id="b1", "b2", … in order, and data-bbox="x0,y0,x1,y1": its box on the page in 0-1000
coordinates (x from the left edge, y from the top edge), tight around its ink.

Answer with the HTML only."""

P1B = P1.replace("Answer with the HTML only.", """Vowel marks: copy ONLY the marks that are actually printed. Most body text in these journals is printed
without vowel marks: then write none. Never add a fatha, damma or kasra on a hamza seat (أ إ ؤ) unless you see it
printed; Quran, verse and some words do carry marks — copy those exactly. Tanween al-fath goes where it is printed
(usually on the alef: ـاً). Keep words joined or separated as printed (لا بد, ما يقطع), and the hamza forms and
ى / ي, ة / ه exactly as printed.

Answer with the HTML only.""")

P2 = """Image 1 is a ZOOMED crop of a scanned Arabic journal page (crop box on the page, 0-1000 coordinates: {box}).
It shows a region that a first pass transcribed from a low-resolution view of the whole page. What the region is:
{kinds}.

The first pass's HTML for the blocks in this region:
<<<
{frag}
>>>
{hint}
Check the HTML against the crop, slowly, character by character:
* every letter, every printed vowel mark (fatha, damma, kasra, sukun, shadda, tanween), hamza forms, dots, digits
  (Arabic-Indic stays Arabic-Indic), punctuation, Latin words;
* tables: number of rows and columns, rowspan/colspan, every cell's text, header cells, caption;
* equations: the LaTeX must render exactly the printed formula (symbols, sub/superscripts, fractions, signs);
* verse: one <div class="verse"> per printed verse line with its two hemistichs in reading order (right one first);
* footnotes: marker numbers and their text; each footnote in its own <aside class="footnote" id="fnN">;
* a block of the wrong type (e.g. verse written as <p>, a footnote as <p>, a list as <p>) gets the right element.
Text that lies outside the crop or is cut by its edge: keep the first pass's text for it unchanged. Do not add text
of neighbouring blocks that are not in the HTML above. Keep every data-id and data-bbox attribute as it is.

Answer JSON: {{"verdict": "ok" | "fixed", "html": "<the corrected HTML of these blocks, only when fixed>",
"changes": ["short English note of each correction"]}}"""

P2_HINT = """
A second OCR engine (letters usually right, but no structure, often drops vowel marks and can misorder columns)
read this region as:
<<<
{az}
>>>
It is only a hint: where it and the HTML differ, the crop decides.
"""

P3 = """Image 1 is a scanned Arabic journal page. Below is a digital edition of it in HTML, made and already
checked region by region. Do a last consistency check of the WHOLE page against the image:
* printed text that is missing from the HTML (a dropped line, paragraph, heading, caption, footnote, page number);
* text that is in the HTML twice, or that is not on the page at all;
* a block of the wrong type (heading vs paragraph, footnote, verse, list, running header/footer);
* blocks in the wrong reading order (right column before left; footnotes after the body text);
* footnote markers in the text not linked to their <aside class="footnote" id="fnN"> (or linked to the wrong one).
Do NOT re-transcribe blocks that are right; do not change spelling or vowel marks unless an error is obvious.

""" + FORMAT_RULES + """

HTML:
<<<
{html}
>>>

Answer JSON: {{"edits": [{{"op": "replace" | "insert_after" | "insert_before" | "delete" | "move_after",
"id": "<data-id of the block concerned>", "html": "<new block(s) HTML for replace/insert, with data-id and
data-bbox>", "target": "<for move_after: the data-id to move it after>", "why": "<short English reason>"}}]}}
An empty list when nothing is wrong."""


# ------------------------------------------------------------------------------------------------ helpers

def cost_of(tag: str) -> tuple[float, float]:
    """The real cost and seconds of a tag from the spend log (a cached answer was paid for by its first call)."""
    usd = secs = 0.0
    if SPEND.exists():
        for l in SPEND.read_text().splitlines():
            if l.strip() and f'"{tag}"' in l:
                r = json.loads(l)
                if r.get("tag") == tag:
                    usd += r["usd"]; secs += r.get("secs") or 0
    return usd, secs


def call(pass_: str, pid: str, prompt: str, images: list[bytes], ledger: list, **kw):
    h = hashlib.sha256(prompt.encode() + b"".join(hashlib.sha256(i).digest() for i in images)
                       + str(sorted(kw.items())).encode()).hexdigest()[:10]
    tag = f"{TAG}_{pass_}_{pid}_{h}"
    info = {}
    ans, usd = gemini(prompt, images=images, tag=tag, subcap=SUBCAP, info=info, **kw)
    for wait in (20, 60):                 # a server error (503, timeout) is retried; a truncated answer never
        if ans is not None or not info.get("error"):
            break
        import time
        time.sleep(wait)
        info = {}
        ans, usd = gemini(prompt, images=images, tag=tag, subcap=SUBCAP, info=info, **kw)
    if info.get("cached"):
        usd, secs = cost_of(tag)
    else:
        usd, secs = cost_of(tag) if "usd" in info else (usd, 0.0)
    ledger.append(dict(pass_=pass_, tag=tag, usd=round(usd, 6), secs=round(secs, 1), cached=bool(info.get("cached")),
                       ok=ans is not None, tin=info.get("tin"), tout=info.get("tout"), think=info.get("think")))
    return ans


def parse(html: str):
    """The HTML as a tree under one root div; top-level blocks = elements with data-id and no data-id ancestor
    (falls back to the root's children)."""
    html = strip_fences(html)
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    if m:
        html = m.group(1)
    root = lxml.html.fragment_fromstring(f'<div id="__root">{html}</div>')
    return root


def blocks(root) -> list:
    out = [e for e in root.iter() if isinstance(e.tag, str) and e.get("data-id") and e is not root
           and not any(a.get("data-id") for a in e.iterancestors() if a is not root)]
    return out or [e for e in root if isinstance(e.tag, str)]


def ser(e) -> str:
    return lxml.html.tostring(e, encoding="unicode", method="html", with_tail=False)


def ser_root(root) -> str:
    s = (root.text or "") + "".join(lxml.html.tostring(c, encoding="unicode", method="html") for c in root)
    return s.strip()


def text_of(e) -> str:
    """Plain text without LaTeX."""
    e2 = lxml.html.fragment_fromstring(ser(e))
    for m in e2.iter():
        if isinstance(m.tag, str) and "math" in (m.get("class") or "").split():
            m.text = " "; [m.remove(c) for c in list(m)]
    return re.sub(r"\s+", " ", e2.text_content()).strip()


def bbox(e):
    b = e.get("data-bbox")
    if not b:
        return None
    try:
        v = [float(x) for x in re.split(r"[,\s]+", b.strip()) if x]
        if len(v) == 4 and v[2] > v[0] and v[3] > v[1]:
            return v
    except ValueError:
        pass
    return None


def kind_of(e) -> str | None:
    cls = set((e.get("class") or "").split())
    if e.tag == "table" or e.find(".//table") is not None:
        return "table"
    if "equation" in cls or any("math" in (m.get("class") or "").split() and re.search(r"[\\^_{]", m.text_content())
                                for m in e.iter() if isinstance(m.tag, str)):
        return "equation"
    if "verse" in cls or e.find('.//*[@class="hemistich"]') is not None:
        return "verse"
    if "footnote" in cls:
        return "footnote"
    return None


def azure_in(pid: str, box, W, H, lines) -> list[dict]:
    if not box:
        return []
    x0, y0, x1, y1 = box[0] * W / 1000, box[1] * H / 1000, box[2] * W / 1000, box[3] * H / 1000
    mx, my = 0.01 * W, 0.006 * H
    return [ln for ln in lines if x0 - mx <= (ln["box"][0] + ln["box"][2]) / 2 <= x1 + mx
            and y0 - my <= (ln["box"][1] + ln["box"][3]) / 2 <= y1 + my]


def agree(a: str, b: str) -> float:
    a, b = folded(a).replace(" ", ""), folded(b).replace(" ", "")
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def crop(img, box, pad=(18, 14)):
    H, W = img.shape[:2]
    x0 = max(0, int((box[0] - pad[0]) * W / 1000)); x1 = min(W, int((box[2] + pad[0]) * W / 1000))
    y0 = max(0, int((box[1] - pad[1]) * H / 1000)); y1 = min(H, int((box[3] + pad[1]) * H / 1000))
    return img[y0:y1, x0:x1], [round(x0 * 1000 / W), round(y0 * 1000 / H), round(x1 * 1000 / W), round(y1 * 1000 / H)]


def union(bs):
    bs = [b for b in bs if b]
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)] if bs else None


# ------------------------------------------------------------------------------------------------ passes

def pass1(pid: str, ledger: list, ver: str = "") -> str | None:
    f = D / f"{ver}p1" / f"{pid}.html"
    mf = D / f"{ver}p1" / f"{pid}.meta.json"
    if f.exists() and mf.exists():
        ledger.extend(json.loads(mf.read_text())["calls"])
        return f.read_text(encoding="utf-8")
    from common import page_jpeg
    led = []
    ans = call("p1", pid, P1B if ver == "B" else P1, [page_jpeg(pid)], led, json_out=False, max_out=20000,
               thinking="low")
    ledger.extend(led)
    if ans is None:
        return None
    root = parse(ans)
    out = ser_root(root)
    save(D / f"{ver}p1", pid, out, led, dict(regions=0, fixed=0))
    return out


def regions_of(pid: str, root, use_azure: bool, W, H, every: bool = False) -> list[dict]:
    lines = azure_lines(pid) if use_azure else []
    bl = blocks(root)
    tagged = []
    for e in bl:
        k = kind_of(e)
        why = []
        if k:
            why.append(k)
        if use_azure:
            b = bbox(e)
            t = text_of(e)
            az = azure_in(pid, b, W, H, lines)
            azt = " ".join(ln["text"] for ln in az)
            if k != "table" and len(folded(t).replace(" ", "")) >= 12:
                a = agree(t, azt)
                if a < 0.85:
                    why.append(f"disagrees with a second reader (agreement {a:.2f})")
        if every and not k:
            why.append("a body block, re-read at full resolution")
        tagged.append((e, k or ("check" if why else None), why))
    regs, cur = [], None
    for e, k, why in tagged:
        b = bbox(e)
        if k is None or b is None:
            cur = None
            continue
        if cur and cur["kind"] == k and k != "table":
            u = union([cur["box"], b])
            if u[3] - u[1] <= 380 and len(cur["els"]) < 8:
                cur["els"].append(e); cur["box"] = u; cur["why"] |= set(why)
                continue
        cur = dict(kind=k, els=[e], box=b, why=set(why))
        regs.append(cur)
    return regs


def parse_variant(v: str):
    """'sahc_m' -> ('sah', True, 'medium', ''); 'p1' -> (None, False, 'low', ''); 'Bsa' -> ('sa', False, 'low', 'B').
    A leading B = the stricter pass-1 prompt (P1B)."""
    ver = "B" if v.startswith("B") else ""
    v = v.removeprefix("B")
    think = "medium" if v.endswith("_m") else "low"
    v = v.removesuffix("_m")
    p3 = v.endswith("c")
    v = v.removesuffix("c")
    return (None if v == "p1" else v), p3, think, ver


def pass2(pid: str, root, mode: str, think: str, img, ledger: list, fixes: list, variant: str):
    use_az = mode in ("sa", "sah")    # mode "s": structure only; "x": every block, no Azure
    hint = mode == "sah"
    H, W = img.shape[:2]
    regs = regions_of(pid, root, use_az, W, H, every=mode == "x")
    lines = azure_lines(pid) if hint else []
    for i, r in enumerate(regs):
        c, cbox = crop(img, r["box"])
        if c.size == 0:
            continue
        frag = "\n".join(ser(e) for e in r["els"])
        hint_txt = ""
        if hint:
            az = azure_in(pid, cbox, W, H, lines)
            if az:
                hint_txt = P2_HINT.format(az="\n".join(ln["text"] for ln in az))
        kinds = "; ".join(sorted(r["why"])) or r["kind"]
        prompt = P2.format(box=",".join(map(str, cbox)), kinds=kinds, frag=frag, hint=hint_txt)
        jb = cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes()
        n_out = max(4000, int(len(frag) * 1.2) + 3000)
        ans = call("p2" + ("h" if hint else "") + ("m" if think == "medium" else ""), pid, prompt, [jb], ledger,
                   json_out=True, max_out=min(n_out, 16000), thinking=think)
        rec = dict(pid=pid, region=i, kind=r["kind"], why=sorted(r["why"]), box=cbox, before=frag,
                   usd=ledger[-1]["usd"], verdict=None)
        if isinstance(ans, dict):
            rec["verdict"] = ans.get("verdict")
            rec["changes"] = ans.get("changes") or []
            new = ans.get("html")
            if ans.get("verdict") == "fixed" and isinstance(new, str) and new.strip():
                try:
                    nr = parse(new)
                    new_els = [c for c in nr if isinstance(c.tag, str)]
                except Exception as ex:
                    new_els = []
                    rec["error"] = f"unparsable html {type(ex).__name__}"
                ok_ids = {e.get("data-id") for e in r["els"]}
                new_ids = [x.get("data-id") for x in new_els]
                if new_els and all(i in ok_ids for i in new_ids) and len(set(new_ids)) == len(new_ids) \
                        and len(new_els) < len(r["els"]):
                    # the model sent back only the blocks it changed: keep the others (merge by data-id)
                    byid = {x.get("data-id"): x for x in new_els}
                    new_els = [byid.get(e.get("data-id"), e) for e in r["els"]]
                    rec["merged_by_id"] = True
                n_before = len(folded(" ".join(text_of(e) for e in r["els"])).replace(" ", ""))
                n_after = len(folded(" ".join(text_of(x) for x in new_els)).replace(" ", ""))
                if not new_els or (n_after < 0.85 * n_before and n_before > 20):
                    rec["verdict"] = f"fixed-but-rejected (text {n_before} -> {n_after} letters; kept draft)"
                else:
                    first = r["els"][0]
                    par = first.getparent()
                    idx = list(par).index(first)
                    tail = first.tail
                    for e in r["els"]:
                        if e.getparent() is not None:
                            e.getparent().remove(e)
                    for k, x in enumerate(new_els):
                        par.insert(idx + k, x)
                    new_els[-1].tail = tail
                    rec["after"] = "\n".join(ser(x) for x in new_els)
                    rec["letters"] = [n_before, n_after]
                    cd = D / variant / "fixes"
                    cd.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(cd / f"{pid}_r{i:02d}_crop.jpg"), c, [cv2.IMWRITE_JPEG_QUALITY, 85])
        fixes.append(rec)
    return len(regs)


def apply_edits(root, edits) -> list[dict]:
    done = []
    byid = {e.get("data-id"): e for e in root.iter() if isinstance(e.tag, str) and e.get("data-id")}
    for ed in edits or []:
        if not isinstance(ed, dict):
            continue
        op, i = ed.get("op"), ed.get("id")
        e = byid.get(i)
        if e is None or e.getparent() is None:
            continue
        par = e.getparent()
        idx = list(par).index(e)
        new = []
        if ed.get("html"):
            try:
                new = [c for c in parse(ed["html"]) if isinstance(c.tag, str)]
            except Exception:
                new = []
        before = ser(e)
        if op == "delete":
            par.remove(e)
        elif op == "replace" and new:
            par.remove(e)
            for k, x in enumerate(new):
                par.insert(idx + k, x)
        elif op == "insert_after" and new:
            for k, x in enumerate(new):
                par.insert(idx + 1 + k, x)
        elif op == "insert_before" and new:
            for k, x in enumerate(new):
                par.insert(idx + k, x)
        elif op == "move_after" and byid.get(ed.get("target")) is not None:
            t = byid[ed["target"]]
            if t is e or t.getparent() is None:
                continue
            par.remove(e)
            tp = t.getparent()
            tp.insert(list(tp).index(t) + 1, e)
        else:
            continue
        done.append(dict(op=op, id=i, why=ed.get("why"), before=before,
                         after="\n".join(ser(x) for x in new) if new else ""))
    return done


def pass3(pid: str, root, variant: str, ledger: list, fixes: list):
    from common import page_jpeg
    prompt = P3.format(html=ser_root(root))
    ans = call("p3", pid, prompt, [page_jpeg(pid)], ledger, json_out=True, max_out=12000, thinking="low")
    if isinstance(ans, dict):
        for d in apply_edits(root, ans.get("edits")):
            fixes.append(dict(pid=pid, region="p3", kind="consistency", verdict="fixed", **d))


def save(vd: Path, pid: str, html: str, calls: list, extra: dict):
    vd.mkdir(parents=True, exist_ok=True)
    by = {}
    for c in calls:
        k = c["pass_"][:2]
        by[k] = round(by.get(k, 0) + c["usd"], 6)
    meta = dict(usd=round(sum(c["usd"] for c in calls), 6), secs=round(sum(c["secs"] for c in calls), 1),
                by_pass=by, calls=calls, **extra)
    (vd / f"{pid}.html").write_text(html, encoding="utf-8")
    (vd / f"{pid}.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


FORCE = False


def run_page(pid: str, variant: str):
    vd = D / variant
    if (vd / f"{pid}.meta.json").exists() and not FORCE:
        return "done"
    ledger = []
    mode, p3, think, ver = parse_variant(variant)
    draft = pass1(pid, ledger, ver)
    if draft is None:
        print(f"  {pid}: no draft", flush=True)
        return "no draft"
    if mode is None and not p3:
        return "ok"
    root = parse(draft)
    img = cv2.imread(str(page_image_path(pid)), cv2.IMREAD_COLOR)
    fixes = []
    nreg = pass2(pid, root, mode, think, img, ledger, fixes, variant) if mode else 0
    if p3:
        pass3(pid, root, variant, ledger, fixes)
    save(vd, pid, ser_root(root), ledger, dict(regions=nreg, fixed=sum(1 for f in fixes if f.get("after") or
                                                                     f.get("region") == "p3")))
    (vd / "fixes").mkdir(parents=True, exist_ok=True)
    (vd / "fixes" / f"{pid}.json").write_text(json.dumps(fixes, ensure_ascii=False, indent=1), encoding="utf-8")
    m = json.loads((vd / f"{pid}.meta.json").read_text())
    print(f"  {variant} {pid}: regions {nreg}, fixed {m['fixed']}, ${m['usd']:.4f} {m['by_pass']} "
          f"(D_agentic spent ${spent(TAG):.3f})", flush=True)
    return "ok"


def run(variant: str, pids: list[str]):
    print(f"run {variant} on {len(pids)} pages; D_agentic spent so far ${spent(TAG):.3f} of ${SUBCAP[1]}", flush=True)
    with ThreadPoolExecutor(4) as ex:
        for pid, r in zip(pids, ex.map(lambda p: run_page(p, variant), pids)):
            pass
    print(f"done; D_agentic spent ${spent(TAG):.3f}", flush=True)


# ------------------------------------------------------------------------------------------------ pictures

def word_diff(a: str, b: str) -> str:
    wa, wb = a.split(), b.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes():
        if op == "equal":
            seg = wa[i1:i2]
            if len(seg) > 12:
                seg = seg[:5] + ["…"] + seg[-5:]
            out.append(htmlmod.escape(" ".join(seg)))
        if op in ("delete", "replace"):
            out.append(f'<del style="background:#fdd;color:#b00">{htmlmod.escape(" ".join(wa[i1:i2]))}</del>')
        if op in ("insert", "replace"):
            out.append(f'<ins style="background:#dfd;color:#060;text-decoration:none">'
                       f'{htmlmod.escape(" ".join(wb[j1:j2]))}</ins>')
    return " ".join(out)


def plain(h: str) -> str:
    try:
        return text_of(parse(h))
    except Exception:
        return re.sub(r"<[^>]+>", " ", h)


def gallery(variant: str):
    from render import SHOT, VENV_PY, wrap
    vd = D / variant / "fixes"
    jobs = []
    for f in sorted(vd.glob("*.json")):
        for r in json.loads(f.read_text(encoding="utf-8")):
            if not r.get("after") and r.get("region") != "p3":
                continue
            name = f"{r['pid']}_r{r['region']:02d}" if r["region"] != "p3" else f"{r['pid']}_p3_{r['id']}_{r['op']}"
            cf = vd / f"{name}_crop.jpg"
            img = ""
            if cf.exists():
                img = ('<div style="direction:ltr"><img style="max-width:100%;border:1px solid #ccc" '
                       f'src="data:image/jpeg;base64,{base64.b64encode(cf.read_bytes()).decode()}"></div>')
            lab = ('<div style="font:13px sans-serif;direction:ltr;color:#333;margin:8px 0 2px">{}</div>')
            body = (lab.format(f"<b>{htmlmod.escape(r['pid'])}</b> — {htmlmod.escape(r['kind'])} — "
                               f"{htmlmod.escape('; '.join(r.get('why') or []) or (r.get('why') or ''))}")
                    + img
                    + lab.format("BEFORE (pass 1)") + f'<div style="background:#fff6f6;padding:4px">{r["before"]}</div>'
                    + lab.format("AFTER") + f'<div style="background:#f4fff4;padding:4px">{r.get("after","")}</div>'
                    + lab.format("word changes") + f'<div style="font-size:.9em">{word_diff(plain(r["before"]), plain(r.get("after","")))}</div>'
                    + lab.format("model's notes: " + htmlmod.escape("; ".join(r.get("changes") or [])[:600])))
            wf = vd / f"{name}.html"
            wf.write_text(wrap(body), encoding="utf-8")
            jobs.append([str(wf), str(vd / f"{name}.png")])
    if jobs:
        jf = vd / "_jobs.json"
        jf.write_text(json.dumps(jobs))
        subprocess.run([str(VENV_PY), "-c", SHOT, str(jf)], text=True, stdout=subprocess.DEVNULL)
    print(f"{len(jobs)} fix pictures in {vd}")


def dial():
    """Cost and accuracy of every variant (whole sample where it ran on all 25 pages, else the 5 exploration
    pages) -> out/D_agentic/dial.json. Order-free word measures from D_subset."""
    import D_subset
    rows = []
    for vd in sorted(p for p in D.iterdir() if p.is_dir() and (p / "score_sample.json").exists()):
        metas = {f.name[:-10]: json.loads(f.read_text()) for f in vd.glob("*.meta.json")}
        pids = page_ids() if len(metas) >= 25 else EXPLORE
        ms = [metas[p] for p in pids if p in metas]
        s, _, _ = D_subset.report(vd, pids)
        by = {}
        for m in ms:
            for k, v in m["by_pass"].items():
                by[k] = by.get(k, 0) + v
        n = len(ms) or 1
        rows.append(dict(variant=vd.name, pages=len(ms), usd_per_page=round(sum(m["usd"] for m in ms) / n, 4),
                         secs_per_page=round(sum(m["secs"] for m in ms) / n, 1),
                         by_pass_per_page={k: round(v / n, 4) for k, v in by.items()},
                         regions=sum(m.get("regions", 0) for m in ms), fixed=sum(m.get("fixed", 0) for m in ms),
                         **{k: s.get(k) for k in ("bag_truth", "bag_az_f", "cer_gold", "cer_bd", "cer_az",
                                                  "dropped_per_1000w", "layout_text_acc", "word_order",
                                                  "teds_vs_pro_draft", "eq_sim_vs_pro_draft")}))
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    (D / "dial.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "gallery", "dial"])
    ap.add_argument("variant", nargs="?")
    ap.add_argument("--pages", nargs="*", default=[])
    ap.add_argument("--explore", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true", help="redo pages already written (cached calls cost nothing)")
    a = ap.parse_args()
    FORCE = a.force
    if a.cmd == "run":
        pids = a.pages or (EXPLORE if a.explore else page_ids())
        run(a.variant, pids)
    elif a.cmd == "gallery":
        gallery(a.variant)
    else:
        dial()
