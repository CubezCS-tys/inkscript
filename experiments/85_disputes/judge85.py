"""Experiment 85, step 2c: the blind-first Gemini judge on the sampled held disputes (paid; cap $40, stop at $38.5).

    .venv/bin/python judge85.py pilot                 50 pilot lines, standard calls (judge81's two-call flow), costed
    .venv/bin/python judge85.py submit ROUND N        one Batch job of up to N lines: ROUND 1 = blind reading,
                                                       ROUND 2 = verdict (only lines whose blind answer is in)
    .venv/bin/python judge85.py collect [wait]        collect finished jobs (answers + spend)
    .venv/bin/python judge85.py spent | status

The method is experiment 81's judge81.py, unchanged in substance: gemini-3.8-flash, thinking low, temperature 0, and
two turns of ONE conversation:
  1. BLIND: the 96-px line crop alone -> its own transcription (judge81's BLIND prompt, verbatim);
  2. with its blind answer in the conversation as its own turn, the distinct candidate readings (Azure, v1, v3;
     distinct under the comparison form, lettered in random order, no names) -> which match the image exactly
     (punctuation ignored), or none (+ its corrected reading), or unreadable (judge81's VERDICT prompt, verbatim).
Batch: both turns go through the Gemini Batch API (half the standard price): round 1 for the blind turn, round 2
re-sends image + blind prompt + the blind answer + the verdict prompt.  Price: standard $0.75 / $3.75 per M tokens in /
out, Batch half (thinking billed as output).  Every answer's tokens are appended to out/judge/spend.jsonl when it is
collected; before a job is sent, spent + every open job's expected cost (at the measured mean, x1.5) + this job's must
stay under STOP_AT.  The key is read by inkscript.enrich.judge._key, never printed.
"""
from __future__ import annotations

import base64
import json
import random
import string
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common85 import E, OUT, ROOT, guard, sform  # noqa: E402

sys.path.insert(0, str(E / "81_heldout_scale"))
import judge81 as J81  # noqa: E402  (prompts and schemas, verbatim)

J = OUT / "judge"
SPEND = J / "spend.jsonl"
STATE = J / "batch_state.json"
R1, R2 = J / "blind.jsonl", J / "answers.jsonl"
MODEL = "gemini-3.8-flash"
PIN, POUT = 0.75, 3.75
CAP, STOP_AT = 40.0, 38.5
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


def shown_of(s: dict):
    """Distinct candidates (by comparison form), in a random order fixed by the key."""
    seen, out = set(), []
    for k in ("azure", "v1", "v3"):
        f = sform(s[k])
        if f not in seen:
            seen.add(f)
            out.append(s[k])
    random.Random(s["key"]).shuffle(out)
    return out


def png(key):
    return (J / "crops" / f"{key}.png").read_bytes()


def gclient():
    from google import genai
    sys.path.insert(0, str(ROOT / "src"))
    from inkscript.enrich.judge import _key
    return genai.Client(api_key=_key())


def gen_cfg(schema):
    return {"temperature": 0.0, "maxOutputTokens": MAX_OUT, "responseMimeType": "application/json",
            "responseSchema": schema, "thinkingConfig": {"thinkingLevel": "LOW"}}


def contents(s, blind_text=None):
    img = {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png(s["key"])).decode()}}
    c = [{"role": "user", "parts": [img, {"text": J81.BLIND}]}]
    if blind_text is not None:
        cl = "\n".join(f"{LET[j]}: {c_}" for j, c_ in enumerate(shown_of(s)))
        c += [{"role": "model", "parts": [{"text": blind_text}]},
              {"role": "user", "parts": [{"text": J81.VERDICT.format(cands=cl)}]}]
    return c


def record2(s, a1, a2, usd):
    shown = shown_of(s)
    right = sorted({x.strip().upper()[:1] for x in a2.get("right", []) if x.strip()})
    rec = dict(key=s["key"], shown=shown, blind=a1.get("reading", ""), legible=a1.get("legible"),
               verdict=a2.get("verdict"), right=right,
               right_idx=[LET.index(x) for x in right if x in LET[:len(shown)]], reading=a2.get("reading", ""),
               note=a2.get("note", ""), usd=round(usd, 6))
    with open(R2, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------------------------------------ pilot (standard)

def pilot():
    from google.genai import types
    c = gclient()
    S = jl(J / "pilot.jsonl")
    guard([s["key"] for s in S], "pilot")
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
            cl = "\n".join(f"{LET[j]}: {x}" for j, x in enumerate(shown_of(s)))
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
    A = jl(R2)
    print(f"pilot answers {len(A)}; spent ${spent():.4f}; per line ${spent() / max(1, len(A)):.5f}",
          Counter(a["verdict"] for a in A))


# ------------------------------------------------------------------------------------------------ batch

def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else dict(jobs=[])


def save_state(st):
    STATE.write_text(json.dumps(st, indent=1))


def mean_cost(rnd):
    D = [d for d in jl(SPEND) if d["round"] == rnd]
    if not D:
        return 0.004
    std = [d["usd"] * (0.5 if d["mode"] == "std" else 1.0) for d in D]       # at Batch price
    return sum(std) / len(std)


def submit(rnd: int, n: int):
    from google.genai import types
    st = load_state()
    S = {d["key"]: d for d in jl(J / "sample.jsonl")}
    inflight = {k for j in st["jobs"] if not j.get("collected") for k in j["keys"] if j["round"] == rnd}
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
    guard(todo, "judge")
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
    up = c.files.upload(file=str(bf), config=types.UploadFileConfig(display_name=f"exp85-{tag}", mime_type="jsonl"))
    job = c.batches.create(model=MODEL, src=up.name, config={"display_name": f"exp85-{tag}"})
    st["jobs"].append(dict(job=job.name, round=rnd, n=len(todo), keys=todo, tag=tag,
                           sent=time.strftime("%Y-%m-%d %H:%M:%S")))
    save_state(st)
    print("submitted", job.name, tag)


def collect(wait=False, poll=120):
    st = load_state()
    S = {d["key"]: d for d in jl(J / "sample.jsonl")}
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
                    a1 = json.loads(b1[k]["text"])
                    record2(S[k], a1, a, usd + b1[k].get("usd", 0))
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
    if cmd == "pilot":
        pilot()
    elif cmd == "submit":
        submit(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "collect":
        collect(len(sys.argv) > 2 and sys.argv[2] == "wait")
    elif cmd == "spent":
        print(f"${spent():.4f}")
    elif cmd == "status":
        status()
