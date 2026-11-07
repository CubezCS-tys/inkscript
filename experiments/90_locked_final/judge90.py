"""Experiment 90, step 4: the blind-first Gemini judge on the locked sample (paid; cap $25, no request past STOP_AT).

    python judge90.py crops                     judge crops: 96 px from a 300-dpi render (judge81.crops' cut)
    .venv/bin/python judge90.py pilot           50 pilot lines, standard calls, costed
    .venv/bin/python judge90.py submit ROUND N  one Batch job of up to N lines (ROUND 1 = blind, 2 = verdict)
    .venv/bin/python judge90.py collect [wait]
    .venv/bin/python judge90.py spent | status

Experiment 81's judge, unchanged in substance (judge81's BLIND and VERDICT prompts and schemas, imported verbatim;
gemini-3.8-flash, thinking low, temperature 0; two turns of ONE conversation: the crop alone -> its own transcription;
then, with that answer in the conversation, the distinct candidate readings lettered in random order with no names ->
which match exactly (punctuation ignored), or none (+ its reading), or unreadable).  The Batch API carries both
turns as experiment 85's judge85.py does (round 2 re-sends the image, the blind prompt, the blind answer and the
verdict prompt), at half the standard price.  Spend: every answer's tokens go to out/judge/spend.jsonl; before a job
is sent, spent + every open job's expected cost (x1.5) + this job's must stay under STOP_AT.
The key is read by inkscript.enrich.judge._key and never printed.
"""
from __future__ import annotations

import base64
import json
import string
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
ROOT = E.parent
OUT = HERE / "out"
J = OUT / "judge"
sys.path.insert(0, str(E / "81_heldout_scale"))
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "88_truth_and_lock"))
sys.path.insert(0, str(ROOT / "src"))
import judge81 as J81  # noqa: E402  (prompts and schemas, verbatim)

SPEND = J / "spend.jsonl"
STATE = J / "batch_state.json"
R1, R2 = J / "blind.jsonl", J / "answers.jsonl"
MODEL = "gemini-3.8-flash"
PIN, POUT = 0.75, 3.75
CAP, STOP_AT = 25.0, 24.0
MAX_OUT = 4000
LET = string.ascii_uppercase


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if Path(p).exists() else []


def spent() -> float:
    return sum(d["usd"] for d in jl(SPEND))


def log_spend(key, rnd, mode, tin, tout):
    f = 0.5 if mode == "batch" else 1.0
    usd = f * (tin / 1e6 * PIN + tout / 1e6 * POUT)
    with open(SPEND, "a") as fh:
        fh.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), key=key, round=rnd, mode=mode, tin=tin,
                                 tout=tout, usd=round(usd, 7))) + "\n")
    return usd


def samples():
    return {d["key"]: d for f in ("sample", "pilot", "extra") for d in jl(J / f"{f}.jsonl")}


def crops():
    import cv2
    import pypdfium2 as pdfium
    from common77 import azure_pages, cut_line, nonempty_lines, render_page
    from locked_old import is_locked_any
    cv2.setNumThreads(1)
    S = list(samples().values()) + jl(OUT / "titles90.jsonl")       # + every title line, for the title sheet
    assert all(is_locked_any(s["key"]) for s in S)
    by = defaultdict(list)
    for s in S:
        by[(s["stem"], s["page"])].append((s["i"], s["key"]))
    (J / "crops").mkdir(parents=True, exist_ok=True)
    for (stem, p), items in sorted(by.items()):
        if all((J / "crops" / f"{k}.png").exists() for _, k in items):
            continue
        doc = pdfium.PdfDocument(str(OUT / "src" / f"{stem}.pdf"))
        pg = azure_pages(OUT / "src" / f"{stem}.json")[p - 1]
        img = render_page(doc, p - 1, dpi=300)
        doc.close()
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        L = {ln["i"]: ln for ln in nonempty_lines(pg)}
        for i, k in items:
            c, _ = cut_line(img, L[i]["poly"], sx, sy, H=96, test=True)
            if c is not None:
                cv2.imwrite(str(J / "crops" / f"{k}.png"), c)
    print("crops:", len(list((J / "crops").glob("*.png"))))


def png(key):
    return (J / "crops" / f"{key}.png").read_bytes()


def gclient():
    from google import genai
    from inkscript.enrich.judge import _key
    return genai.Client(api_key=_key())


def gen_cfg(schema):
    return {"temperature": 0.0, "maxOutputTokens": MAX_OUT, "responseMimeType": "application/json",
            "responseSchema": schema, "thinkingConfig": {"thinkingLevel": "LOW"}}


def contents(s, blind_text=None):
    img = {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png(s["key"])).decode()}}
    c = [{"role": "user", "parts": [img, {"text": J81.BLIND}]}]
    if blind_text is not None:
        cl = "\n".join(f"{LET[j]}: {c_}" for j, c_ in enumerate(s["shown"]))
        c += [{"role": "model", "parts": [{"text": blind_text}]},
              {"role": "user", "parts": [{"text": J81.VERDICT.format(cands=cl)}]}]
    return c


def record2(s, a1, a2, usd):
    shown = s["shown"]
    right = sorted({x.strip().upper()[:1] for x in a2.get("right", []) if x.strip()})
    rec = dict(key=s["key"], stratum=s["stratum"], blind=a1.get("reading", ""), legible=a1.get("legible"),
               verdict=a2.get("verdict"), right=right,
               right_idx=[LET.index(x) for x in right if x in LET[:len(shown)]], reading=a2.get("reading", ""),
               note=a2.get("note", ""), usd=round(usd, 6))
    with open(R2, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def pilot():
    from google.genai import types
    c = gclient()
    S = jl(J / "pilot.jsonl")
    done = {d["key"] for d in jl(R2)}
    for s in S:
        if s["key"] in done or not (J / "crops" / f"{s['key']}.png").exists():
            continue
        if spent() >= STOP_AT:
            print("STOP: cap")
            break
        img = types.Part(inline_data=types.Blob(data=png(s["key"]), mime_type="image/png"))
        try:
            c1 = [types.Content(role="user", parts=[img, types.Part(text=J81.BLIND)])]
            cfg = lambda sc: types.GenerateContentConfig(  # noqa: E731
                temperature=0.0, max_output_tokens=MAX_OUT, response_mime_type="application/json", response_schema=sc,
                thinking_config=types.ThinkingConfig(thinking_level="low"))
            r1 = c.models.generate_content(model=MODEL, contents=c1, config=cfg(J81.S1))
            u = r1.usage_metadata
            usd = log_spend(s["key"], 1, "std", u.prompt_token_count or 0,
                            (u.candidates_token_count or 0) + (u.thoughts_token_count or 0))
            a1 = json.loads(r1.text)
            cl = "\n".join(f"{LET[j]}: {x}" for j, x in enumerate(s["shown"]))
            c2 = c1 + [types.Content(role="model", parts=[types.Part(text=r1.text)]),
                       types.Content(role="user", parts=[types.Part(text=J81.VERDICT.format(cands=cl))])]
            r2 = c.models.generate_content(model=MODEL, contents=c2, config=cfg(J81.S2))
            u = r2.usage_metadata
            usd += log_spend(s["key"], 2, "std", u.prompt_token_count or 0,
                             (u.candidates_token_count or 0) + (u.thoughts_token_count or 0))
            with open(R1, "a", encoding="utf-8") as f:
                f.write(json.dumps(dict(key=s["key"], text=r1.text, mode="std"), ensure_ascii=False) + "\n")
            record2(s, a1, json.loads(r2.text), usd)
        except Exception as e:  # noqa: BLE001
            print("  failed:", s["key"], type(e).__name__, str(e)[:160])
    A = [a for a in jl(R2) if a["stratum"] == "pilot"]
    sp = sum(d["usd"] for d in jl(SPEND) if d["mode"] == "std")
    print(f"pilot answers {len(A)}; standard spend ${sp:.4f}; per line ${sp / max(1, len(A)):.5f}",
          Counter(a["verdict"] for a in A))


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else dict(jobs=[])


def save_state(st):
    STATE.write_text(json.dumps(st, indent=1))


def mean_cost(rnd):
    D = [d for d in jl(SPEND) if d["round"] == rnd]
    if not D:
        return 0.004
    return sum(d["usd"] * (0.5 if d["mode"] == "std" else 1.0) for d in D) / len(D)      # at Batch price


def submit(rnd: int, n: int, which: str = "sample"):
    from google.genai import types
    st = load_state()
    S = {d["key"]: d for d in jl(J / f"{which}.jsonl")}
    inflight = {k for j in st["jobs"] if not j.get("collected") and j["round"] == rnd for k in j["keys"]}
    if rnd == 1:
        done = {d["key"] for d in jl(R1)}
        todo = [k for k in S if k not in done and k not in inflight and (J / "crops" / f"{k}.png").exists()]
    else:
        b = {d["key"]: d for d in jl(R1)}
        done = {d["key"] for d in jl(R2)}
        todo = [k for k in S if k in b and k not in done and k not in inflight]
    todo = todo[:n]
    if not todo:
        print("nothing to send")
        return
    exp_open = sum(j["n"] * mean_cost(j["round"]) * 1.5 for j in st["jobs"] if not j.get("collected"))
    exp_this = len(todo) * mean_cost(rnd) * 1.5
    tot = spent()
    print(f"round {rnd}: {len(todo)} lines; expected ${exp_this:.2f} (x1.5); spent ${tot:.3f}; open jobs ${exp_open:.2f}")
    if tot + exp_open + exp_this > STOP_AT:
        print("STOP: could cross the stop line; send fewer")
        return
    tag = f"r{rnd}_{len(st['jobs']) + 1}"
    bf = J / "batch" / f"{tag}.jsonl"
    bf.parent.mkdir(parents=True, exist_ok=True)
    blind = {d["key"]: d["text"] for d in jl(R1)} if rnd == 2 else {}
    with open(bf, "w", encoding="utf-8") as f:
        for k in todo:
            req = {"contents": contents(S[k], blind.get(k) if rnd == 2 else None),
                   "generationConfig": gen_cfg(J81.S1 if rnd == 1 else J81.S2)}
            f.write(json.dumps({"key": k, "request": req}, ensure_ascii=False) + "\n")
    c = gclient()
    up = c.files.upload(file=str(bf), config=types.UploadFileConfig(display_name=f"exp90-{tag}", mime_type="jsonl"))
    job = c.batches.create(model=MODEL, src=up.name, config={"display_name": f"exp90-{tag}"})
    st["jobs"].append(dict(job=job.name, round=rnd, n=len(todo), keys=todo, tag=tag, which=which,
                           sent=time.strftime("%Y-%m-%d %H:%M:%S")))
    save_state(st)
    print("submitted", job.name, tag)


def collect(wait=False, poll=120):
    st = load_state()
    S = samples()
    c = gclient()
    for j in st["jobs"]:
        if j.get("collected"):
            continue
        while True:
            job = c.batches.get(name=j["job"])
            state = job.state.name if hasattr(job.state, "name") else str(job.state)
            fin = state in {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
            print(f"  {j['tag']} {j['job']}: {state}", time.strftime("%H:%M:%S"), flush=True)
            if fin or not wait:
                break
            time.sleep(poll)
        if not fin:
            continue
        got = bad = 0
        if state == "JOB_STATE_SUCCEEDED":
            b1 = {d["key"]: d for d in jl(R1)}
            for row in (json.loads(x) for x in c.files.download(file=job.dest.file_name).decode("utf-8").splitlines()
                        if x.strip()):
                k = row.get("key")
                resp = row.get("response") or {}
                um = resp.get("usageMetadata") or {}
                tin = um.get("promptTokenCount", 0)
                tout = um.get("candidatesTokenCount", 0) + um.get("thoughtsTokenCount", 0)
                usd = log_spend(k, j["round"], "batch", tin, tout)
                cand = (resp.get("candidates") or [{}])[0]
                text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts") or []
                               if not p.get("thought"))
                try:
                    a = json.loads(text)
                except Exception:  # noqa: BLE001
                    bad += 1
                    continue
                if j["round"] == 1:
                    with open(R1, "a", encoding="utf-8") as f:
                        f.write(json.dumps(dict(key=k, text=text, mode="batch", usd=round(usd, 7)), ensure_ascii=False)
                                + "\n")
                else:
                    record2(S[k], json.loads(b1[k]["text"]), a, usd + b1[k].get("usd", 0))
                got += 1
        j.update(collected=True, final=state, got=got, bad=bad, collected_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        save_state(st)
        print(f"  collected {got} ({bad} unparsable); spent ${spent():.3f}")


def status():
    st = load_state()
    print(f"spent ${spent():.3f}; blind {len(jl(R1))}; answers {len(jl(R2))};",
          Counter(a["verdict"] for a in jl(R2)))
    for j in st["jobs"]:
        print(" ", j["tag"], j["n"], j.get("final", "open"), j.get("got"))
    print("mean $/line at Batch price: round 1", round(mean_cost(1), 6), "round 2", round(mean_cost(2), 6))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "crops":
        crops()
    elif cmd == "pilot":
        pilot()
    elif cmd == "submit":
        submit(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else "sample")
    elif cmd == "collect":
        collect(len(sys.argv) > 2 and sys.argv[2] == "wait")
    elif cmd == "spent":
        print(f"${spent():.4f}")
    elif cmd == "status":
        status()
