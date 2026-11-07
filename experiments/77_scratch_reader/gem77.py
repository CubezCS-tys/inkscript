"""Experiment 77, step 3: Gemini judges the lines where v1 and Azure disagree (paid; owner's cap $20 for this pilot).

    python gem77.py pick N            disputes (v1 != Azure in letters/words, punctuation ignored) -> a sample of N
    python gem77.py crops             judge crops at height 96 (twice the training height), from the page renders
    python gem77.py run [LIMIT] [T]   ask Gemini (T threads, default 4); every answer cached and costed
    python gem77.py spent

Gemini sees the line image and two readings in random order (A/B; which is Azure is recorded, never shown) and answers
A / B / neither (+ its own reading) / unreadable.  Model: gemini-3.8-flash, thinking low (experiment 71's production
Flash).  Price $0.75 / $3.75 per M tokens in / out (thinking billed as output; experiment 71's table).  Every request
appends tokens and $ to out/judge/spend.jsonl; no request is sent that could take the total over CAP.
The key is read from the repo's .env by inkscript.enrich.judge._key and never printed.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from common77 import OUT, POLICIES_NP, azure_pages, clean_label, cut_line, nonempty_lines, render_page, to_visual

J = OUT / "judge"
J.mkdir(exist_ok=True)
SPEND, CACHE = J / "spend.jsonl", J / "answers.jsonl"
MODEL = "gemini-3.8-flash"
PIN, POUT = 0.75, 3.75
CAP = 20.0
STOP_AT = 19.0           # stop sending before the cap: margin for requests in flight
_lock = threading.Lock()

PROMPT = """The image shows ONE printed line cut from a scanned Arabic journal page (it may contain Latin words,
digits or punctuation; edges of neighbouring lines may show at the top or bottom - ignore them).

Two transcriptions of this line follow.
A: {a}
B: {b}

Compare them with the image, character by character, as printed: letters, dots, hamza forms, ى versus ي, ة versus ه,
vowel marks only where printed, digits (Arabic-Indic or Latin, as printed), and punctuation marks. Do not modernise
old spellings and do not correct misprints: the line must be what the page prints. Ignore differences that are only
in spaces around punctuation marks.

Answer with JSON:
- "verdict": "A" if A is exactly right, "B" if B is exactly right, "both" if both are right (they differ only in
  ignorable spacing), "neither" if both are wrong, "unreadable" if the image cannot be read with confidence
  (cut off, blurred, not a text line);
- "reading": when the verdict is "neither", the correct transcription of the whole line; otherwise "";
- "note": a few words on the difference."""

SCHEMA = {"type": "object", "properties": {"verdict": {"type": "string", "enum": ["A", "B", "both", "neither", "unreadable"]},
                                           "reading": {"type": "string"}, "note": {"type": "string"}},
          "required": ["verdict", "reading", "note"]}


def spent() -> float:
    if not SPEND.exists():
        return 0.0
    return sum(json.loads(l)["usd"] for l in SPEND.read_text().splitlines() if l.strip())


def manifest() -> dict:
    m = {}
    import glob
    for f in glob.glob(str(OUT / "shards/manifest-train-*.jsonl")):
        for l in open(f, encoding="utf-8"):
            d = json.loads(l)
            m[d["key"]] = d
    return m


def pick(n: int):
    M = manifest()
    preds = {d["key"]: d for d in map(json.loads, open(OUT / "pred/train_v1.jsonl", encoding="utf-8"))}
    disp, pun, same = [], 0, 0
    for k, p in preds.items():
        lab = M[k]["label"]
        if POLICIES_NP["faithful"](p["pred"]) == POLICIES_NP["faithful"](lab):
            same += 1
        elif POLICIES_NP["no_punct"](p["pred"]) == POLICIES_NP["no_punct"](lab):
            pun += 1
        else:
            disp.append(k)
    rng = random.Random(77)
    # Sample whole pages (every dispute on a chosen page), so that the 96-px judge crops need few page renders;
    # half the lines from pre-2000 pages (scarce, and where Azure errs most), half from the rest.
    def is_old(k):
        y = str(M[k]["year"])[:4]
        return y.isdigit() and int(y) < 2000
    by_page = defaultdict(list)
    for k in disp:
        by_page[k.rsplit("_l", 1)[0]].append(k)
    pages = sorted(by_page)
    rng.shuffle(pages)
    old = [k for k in disp if is_old(k)]
    sample, n_old, n_new = [], 0, 0
    for p in pages:
        ks = by_page[p]
        if is_old(ks[0]):
            if n_old >= n // 2:
                continue
            n_old += len(ks)
        else:
            if n_new >= n - n // 2:
                continue
            n_new += len(ks)
        sample += ks
        if n_old >= n // 2 and n_new >= n - n // 2:
            break
    rng.shuffle(sample)
    with open(J / "sample.jsonl", "w", encoding="utf-8") as f:
        for k in sample:
            ab = rng.random() < 0.5            # True: A = Azure
            f.write(json.dumps(dict(key=k, azure=M[k]["label"], v1=preds[k]["pred"], cmin=preds[k]["cmin"],
                                    cmean=preds[k]["cmean"], year=M[k]["year"], jcode=M[k]["jcode"],
                                    A="azure" if ab else "v1"), ensure_ascii=False) + "\n")
    st = dict(lines=len(preds), agree_faithful=same, punct_only=pun, disputes=len(disp), disputes_pre2000=len(old),
              sample=len(sample), sample_pre2000=n_old, sample_pages=len({k.rsplit('_l', 1)[0] for k in sample}))
    (J / "pick.json").write_text(json.dumps(st, indent=1))
    print(st)


def crops():
    import cv2
    import pypdfium2 as pdfium
    cv2.setNumThreads(1)
    S = [json.loads(l) for l in open(J / "sample.jsonl", encoding="utf-8")]
    pages = {json.loads(l)["stem"]: json.loads(l) for l in open(OUT / "pages77.jsonl", encoding="utf-8")}
    by = defaultdict(list)
    for s in S:
        stem, p, i = s["key"].rsplit("_p", 1)[0], int(s["key"].split("_p")[-1][:3]), int(s["key"][-3:])
        by[(stem, p)].append((i, s["key"]))
    (J / "crops").mkdir(exist_ok=True)
    for (stem, p), items in sorted(by.items()):
        if all((J / "crops" / f"{k}.png").exists() for _, k in items):
            continue
        m = pages[stem]
        doc = pdfium.PdfDocument(m["pdf"])
        pg = azure_pages(m["azure"])[p - 1]
        img = render_page(doc, p - 1, dpi=300)
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        L = {ln["i"]: ln for ln in nonempty_lines(pg)}
        for i, k in items:
            c, _ = cut_line(img, L[i]["poly"], sx, sy, H=96, test=True)
            if c is not None:
                cv2.imwrite(str(J / "crops" / f"{k}.png"), c)
        doc.close()
    print("crops:", len(list((J / "crops").glob("*.png"))))


_client = None


def ask(s: dict) -> dict | None:
    global _client
    from google import genai
    from google.genai import types
    sys.path.insert(0, str(OUT.parent.parent.parent / "src"))
    from inkscript.enrich.judge import _key
    png = (J / "crops" / f"{s['key']}.png").read_bytes()
    a, b = (s["azure"], s["v1"]) if s["A"] == "azure" else (s["v1"], s["azure"])
    prompt = PROMPT.format(a=a, b=b)
    h = hashlib.sha256((MODEL + prompt).encode() + png).hexdigest()
    with _lock:
        if spent() >= STOP_AT:
            return None
        if _client is None:
            _client = genai.Client(api_key=_key())
    parts = [types.Part(inline_data=types.Blob(data=png, mime_type="image/png")), types.Part(text=prompt)]
    cfg = types.GenerateContentConfig(temperature=0.0, max_output_tokens=2000, response_mime_type="application/json",
                                      response_schema=SCHEMA, thinking_config=types.ThinkingConfig(thinking_level="low"))
    for attempt in range(3):
        try:
            t0 = time.time()
            r = _client.models.generate_content(model=MODEL, contents=[types.Content(role="user", parts=parts)], config=cfg)
            um = r.usage_metadata
            tin = um.prompt_token_count or 0
            tout = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
            usd = tin / 1e6 * PIN + tout / 1e6 * POUT
            with _lock:
                with open(SPEND, "a") as f:
                    f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), key=s["key"], tin=tin, tout=tout,
                                            usd=round(usd, 6), secs=round(time.time() - t0, 2))) + "\n")
            ans = json.loads(r.text)
            verdict = ans.get("verdict")
            who = {"A": s["A"], "B": "v1" if s["A"] == "azure" else "azure"}.get(verdict, verdict)
            rec = dict(key=s["key"], hash=h, verdict=verdict, winner=who, reading=ans.get("reading", ""),
                       note=ans.get("note", ""), usd=round(usd, 6))
            with _lock:
                with open(CACHE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return rec
        except Exception as e:  # noqa: BLE001
            print("  request failed:", type(e).__name__, str(e)[:160], flush=True)
            time.sleep(5 * (attempt + 1))
    return None


def run(limit: int | None, threads: int = 4):
    S = [json.loads(l) for l in open(J / "sample.jsonl", encoding="utf-8")]
    done = {json.loads(l)["key"] for l in open(CACHE, encoding="utf-8")} if CACHE.exists() else set()
    # a dispute that is only the order of a left-to-right run (Azure's "(2005 ,Keyes)" vs v1's "(Keyes, 2005)")
    # is the same training target (to_visual), so it is not worth a paid question
    todo = [s for s in S if s["key"] not in done and (J / "crops" / f"{s['key']}.png").exists()
            and to_visual(s["azure"]) != to_visual(s["v1"])]
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} to ask; spent so far ${spent():.3f}", flush=True)
    n = 0
    with ThreadPoolExecutor(threads) as ex:
        for r in ex.map(ask, todo):
            n += 1
            if r is None and spent() >= STOP_AT:
                print("STOP: spend limit reached", flush=True)
                break
            if n % 100 == 0:
                print(f"{n} answered, ${spent():.3f}", flush=True)
    rows = [json.loads(l) for l in open(CACHE, encoding="utf-8")]
    print(f"answers {len(rows)}; spent ${spent():.3f}; mean ${spent() / max(1, len(rows)):.5f}/line;",
          Counter(r["winner"] for r in rows))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "pick":
        pick(int(sys.argv[2]))
    elif c == "crops":
        crops()
    elif c == "run":
        run(int(sys.argv[2]) if len(sys.argv) > 2 else None, int(sys.argv[3]) if len(sys.argv) > 3 else 4)
    elif c == "spent":
        print(f"${spent():.4f}")
