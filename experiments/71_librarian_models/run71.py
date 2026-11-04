"""Experiment 71, step 2: ask each model every packet, the same instruction and schema for all.

    python3 run71.py count  --model M [--ids FILE]          input tokens of every request (free count endpoints)
    python3 run71.py pilot  --model M --n 12                 Standard calls on a small stratified pilot (latency, tokens)
    python3 run71.py batch  --model M [--ids FILE]           submit one Batch job of the packets not yet answered
    python3 run71.py collect --model M                       poll / collect the open Batch job

Models: gemini-3.8-flash, gemini-4-argon (Gemini API, the pipeline's key loader), claude-sonnet-5-5, claude-opus-5-5
(ANTHROPIC_API_KEY from the checkout's .env, read here, never printed).
Spend: every answer is a row of out/spend71.jsonl (model, id, mode, tokens in / out / thinking, usd). The caps are
TOTALS of that log: Gemini $6, Anthropic $4 (owner, 2026-11-02). A job is refused when the log + its worst case
(input counted, max output at list price) would cross its provider's cap.
Answers: out/answers/<model>.jsonl (id, answer JSON, tokens, usd, secs, mode).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
MAIN = HERE.parents[1]
sys.path.insert(0, str(HERE))
import prompt71 as PR  # noqa: E402

SPEND = OUT / "spend71.jsonl"
ANS = OUT / "answers"
STATE = OUT / "batch_state71.json"
CAP = {"gemini": 6.0, "anthropic": 4.0}
# USD per M tokens, Standard (input, output; thinking billed as output). Batch = half on both providers.
# Gemini: experiments/41_azure_structure/common.py (checked on ai.google.dev 2026-10-15; valid through 2026-11-30 for
# Argon, 2026-12-31 for Flash). Anthropic: the claude-api skill's model table (cached 2026-09-25).
PRICE = {"gemini-3.8-flash": (0.75, 3.75), "gemini-4-argon": (2.0, 10.0),
         "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}
MAX_OUT = {"gemini-3.8-flash": 3000, "gemini-4-argon": 3000, "claude-sonnet-5-5": 1500, "claude-opus-5-5": 1200}
# Claude lowered to 1500 (Opus 1200; Sonnet max over all 522 = 313, Opus pilot max 641) after the first Sonnet batch (212 answers: max 313 output tokens incl. thinking, mean 146)
# pilot (12 Standard calls each): answers 65-215 tokens incl. thinking; 3000 leaves 14x room and bounds the worst case
THINK = {"gemini-3.8-flash": "low", "gemini-4-argon": "low", "gemini-3.8-flash@high": "high", "gemini-4-argon@high": "high"}
# variants "<api model>@<thinking>": the same model with another thinking level, scored as its own row
for _v in ("gemini-3.8-flash@high", "gemini-4-argon@high"):
    PRICE[_v], MAX_OUT[_v] = PRICE[_v.split("@")[0]], 8000


def api(model):
    return model.split("@")[0]
EFFORT = {"claude-sonnet-5-5": "medium", "claude-opus-5-5": "medium"}


def provider(m):
    return "anthropic" if m.startswith("claude") else "gemini"


def packets(ids_file=None):
    P = [json.loads(l) for l in open(OUT / "packets71.jsonl", encoding="utf-8")]
    if ids_file:
        keep = set(Path(ids_file).read_text().split())
        P = [p for p in P if p["id"] in keep]
    return P


def spent(prov=None):
    if not SPEND.exists():
        return 0.0
    return sum(r["usd"] for r in map(json.loads, open(SPEND)) if prov is None or provider(r["model"]) == prov)


def answered(model):
    f = ANS / f"{model}.jsonl"
    return {json.loads(l)["id"] for l in open(f)} if f.exists() else set()


def price(model, mode):
    pin, pout = PRICE[model]
    return (pin / 2, pout / 2) if mode == "batch" else (pin, pout)


def record(model, iid, ans, tin, tout, think, mode, secs=None, finish=None, raw=None, cache_read=0, cache_write=0):
    pin, pout = price(model, mode)
    usd = (tin + cache_write * 1.25 + cache_read * 0.1) / 1e6 * pin + (tout + think) / 1e6 * pout
    OUT.mkdir(exist_ok=True)
    ANS.mkdir(exist_ok=True)
    with open(SPEND, "a") as f:
        f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=model, id=iid, mode=mode, tin=tin,
                                tout=tout, think=think, cache_read=cache_read, cache_write=cache_write,
                                usd=round(usd, 6), finish=finish)) + "\n")
    with open(ANS / f"{model}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(id=iid, model=model, answer=ans, tin=tin, tout=tout, think=think, usd=round(usd, 6),
                                secs=secs, mode=mode, finish=finish, raw=None if ans is not None else raw,
                                prompt=PR.PROMPT_VERSION), ensure_ascii=False) + "\n")
    return usd


def parse(text):
    try:
        t = text.strip()
        if t.startswith("```"):
            t = t.strip("`").split("\n", 1)[1]
        return json.loads(t)
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ clients

def gclient():
    sys.path.insert(0, str(MAIN / "src"))
    from google import genai
    from inkscript.enrich.judge import _key
    return genai.Client(api_key=_key())


def aclient():
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        for line in open(MAIN / ".env"):
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return anthropic.Anthropic(api_key=key)


def g_request(model, p):
    return {"contents": [{"role": "user", "parts": [{"text": PR.user_text(p)}]}],
            "systemInstruction": {"parts": [{"text": PR.SYSTEM}]},
            "generationConfig": {"maxOutputTokens": MAX_OUT[model], "responseMimeType": "application/json",
                                 "responseSchema": PR.GSCHEMA,
                                 "thinkingConfig": {"thinkingLevel": THINK[model].upper()}}}


def a_params(model, p):
    return dict(model=api(model), max_tokens=MAX_OUT[model],
                system=[{"type": "text", "text": PR.SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": PR.user_text(p)}],
                thinking={"type": "adaptive"},
                output_config={"effort": EFFORT[model], "format": {"type": "json_schema", "schema": PR.SCHEMA}})


def g_usage(um):
    um = um or {}
    g = lambda *ks: next((um[k] for k in ks if um.get(k)), 0)  # noqa: E731
    return g("promptTokenCount", "prompt_token_count"), g("candidatesTokenCount", "candidates_token_count"), \
        g("thoughtsTokenCount", "thoughts_token_count")


# ------------------------------------------------------------------------------------------------ count

def count(model, P):
    tot, per = 0, []
    if provider(model) == "gemini":
        from google.genai import types
        c = gclient()
        for p in P:
            n = c.models.count_tokens(model=api(model), contents=PR.SYSTEM + "\n\n" + PR.user_text(p)).total_tokens
            per.append(n)
    else:
        c = aclient()
        for p in P:
            kw = a_params(model, p)
            n = c.messages.count_tokens(model=api(model), system=kw["system"], messages=kw["messages"]).input_tokens
            per.append(n)
    tot = sum(per)
    print(f"{model}: {len(P)} requests, input {tot} tokens (mean {tot // max(1, len(P))}, max {max(per)})")
    return per


# ------------------------------------------------------------------------------------------------ standard (pilot)

def standard(model, P):
    prov = provider(model)
    pin, pout = price(model, "standard")
    done = answered(model)
    for p in P:
        if p["id"] in done:
            continue
        worst = (len(PR.SYSTEM) + len(PR.user_text(p))) / 2.0 / 1e6 * pin + MAX_OUT[model] / 1e6 * pout
        if spent(prov) + worst > CAP[prov]:
            print(f"STOP: {prov} spent ${spent(prov):.3f}; next call up to ${worst:.3f} would cross ${CAP[prov]}")
            return
        t0 = time.time()
        if prov == "gemini":
            from google.genai import types
            c = gclient()
            r = g_request(model, p)
            resp = c.models.generate_content(
                model=api(model), contents=r["contents"],
                config=types.GenerateContentConfig(
                    system_instruction=PR.SYSTEM, max_output_tokens=MAX_OUT[model],
                    response_mime_type="application/json", response_schema=PR.GSCHEMA,
                    thinking_config=types.ThinkingConfig(thinking_level=THINK[model])))
            um = resp.usage_metadata
            tin, tout, th = um.prompt_token_count or 0, um.candidates_token_count or 0, um.thoughts_token_count or 0
            text = resp.text or ""
            fin = str(resp.candidates[0].finish_reason) if resp.candidates else "none"
            cr = cw = 0
        else:
            c = aclient()
            m = c.messages.create(**a_params(model, p))
            u = m.usage
            tin, tout, th = u.input_tokens, u.output_tokens, 0       # Anthropic output_tokens includes thinking
            cr, cw = u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0
            text = next((b.text for b in m.content if b.type == "text"), "")
            fin = m.stop_reason
        secs = round(time.time() - t0, 2)
        ans = parse(text)
        usd = record(model, p["id"], ans, tin, tout, th, "standard", secs, fin, text, cr, cw)
        print(f"  {p['id']:12s} {secs:6.1f}s in {tin} out {tout}+{th} ${usd:.4f} -> "
              f"{(ans or {}).get('answer')} ({(ans or {}).get('confidence')})", flush=True)


# ------------------------------------------------------------------------------------------------ batch

def load_state():
    return json.load(open(STATE)) if STATE.exists() else {}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=1))


def open_jobs(st, model):
    return [j for j in st.get(model, []) if not j.get("collected")]


def batch(model, P, limit=None):
    """One Batch job of up to `limit` unanswered packets, refused unless the provider's logged spend + the job's
    worst case (every answer at max output) + the worst case of jobs still open stays under the cap."""
    prov = provider(model)
    st = load_state()
    inflight = {i for m in st for j in open_jobs(st, m) if m == model for i in j["keys"]}
    open_worst = sum(j["worst"] for m in st for j in open_jobs(st, m) if provider(m) == prov)
    done = answered(model)
    P = [p for p in P if p["id"] not in done and p["id"] not in inflight][:limit]
    if not P:
        print("nothing to send")
        return
    pin, pout = price(model, "batch")
    est_in = sum((len(PR.SYSTEM) + len(PR.user_text(p))) / 2.0 for p in P)    # generous: measured ~2.6-3.3 chars/token
    worst = est_in / 1e6 * pin + len(P) * MAX_OUT[model] / 1e6 * pout
    print(f"{model}: {len(P)} requests; worst case ${worst:.2f}; {prov} spent ${spent(prov):.3f} + open jobs' worst "
          f"${open_worst:.2f} of ${CAP[prov]}")
    if spent(prov) + open_worst + worst > CAP[prov]:
        print("STOP: the job's worst case could cross the cap; send fewer (--limit)")
        return
    keys = [p["id"] for p in P]
    if prov == "gemini":
        from google.genai import types
        c = gclient()
        bf = OUT / "batch" / f"{model}_{len(st.get(model, [])) + 1}.jsonl"
        bf.parent.mkdir(parents=True, exist_ok=True)
        bf.write_text("".join(json.dumps({"key": p["id"], "request": g_request(model, p)}, ensure_ascii=False) + "\n"
                              for p in P), encoding="utf-8")
        up = c.files.upload(file=str(bf), config=types.UploadFileConfig(display_name=f"exp71-{model.replace('@', '-')}",
                                                                        mime_type="jsonl"))
        job = c.batches.create(model=api(model), src=up.name, config={"display_name": f"exp71-{model.replace('@', '-')}"})
        jid = job.name
    else:
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request
        c = aclient()
        reqs = [Request(custom_id=p["id"], params=MessageCreateParamsNonStreaming(**a_params(model, p))) for p in P]
        job = c.messages.batches.create(requests=reqs)
        jid = job.id
    st.setdefault(model, []).append(dict(job=jid, sent=time.strftime("%Y-%m-%d %H:%M:%S"), n=len(P),
                                         worst=round(worst, 3), keys=keys))
    save_state(st)
    print(f"  submitted {jid}")


def collect(model, wait=False, poll=60):
    st = load_state()
    for s in open_jobs(st, model):
        if collect_one(model, s, wait, poll):
            save_state(st)


def collect_one(model, s, wait, poll):
    prov = provider(model)
    while True:
        if prov == "gemini":
            c = gclient()
            job = c.batches.get(name=s["job"])
            state = job.state.name if hasattr(job.state, "name") else str(job.state)
            done = state in {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
        else:
            c = aclient()
            job = c.messages.batches.retrieve(s["job"])
            state, done = job.processing_status, job.processing_status == "ended"
        print(f"  {model} {s['job']}: {state}", flush=True)
        if done or not wait:
            break
        time.sleep(poll)
    if not done:
        return False
    sent = time.mktime(time.strptime(s["sent"], "%Y-%m-%d %H:%M:%S"))
    wall = round(time.time() - sent)
    n = 0
    if prov == "gemini":
        if state == "JOB_STATE_SUCCEEDED":
            lines = c.files.download(file=job.dest.file_name).decode("utf-8").splitlines()
            for row in (json.loads(x) for x in lines if x.strip()):
                key = row.get("key")
                resp = row.get("response") or {}
                tin, tout, th = g_usage(resp.get("usageMetadata") or resp.get("usage_metadata"))
                cand = (resp.get("candidates") or [{}])[0]
                fin = str(cand.get("finishReason") or row.get("error") or "none")
                text = "".join(x.get("text", "") for x in (cand.get("content") or {}).get("parts") or []
                               if not x.get("thought"))
                record(model, key, parse(text), tin, tout, th, "batch", None, fin, text)
                n += 1
    else:
        for r in c.messages.batches.results(s["job"]):
            if r.result.type != "succeeded":
                print("   ", r.custom_id, r.result.type)
                continue
            m = r.result.message
            u = m.usage
            text = next((b.text for b in m.content if b.type == "text"), "")
            record(model, r.custom_id, parse(text), u.input_tokens, u.output_tokens, 0, "batch", None, m.stop_reason,
                   text, u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0)
            n += 1
    s.update(collected=True, final=state, collected_at=time.strftime("%Y-%m-%d %H:%M:%S"), wall_secs=wall, got=n)
    print(f"  collected {n} answers; wall {wall}s; {prov} spent ${spent(prov):.3f}")
    return True


def pilot_ids(n):
    """A small stratified pilot: one or two per kind."""
    G = [json.loads(l) for l in open(OUT / "gold71.jsonl")]
    by = defaultdict(list)
    for g in G:
        by[g["kind"]].append(g["id"])
    ids = []
    k = 0
    while len(ids) < n:
        for kind in sorted(by):
            if k < len(by[kind]) and len(ids) < n:
                ids.append(by[kind][k * 7 % len(by[kind])])
        k += 1
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["count", "pilot", "batch", "collect"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--ids")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.cmd == "count":
        count(a.model, packets(a.ids))
    elif a.cmd == "pilot":
        keep = set(pilot_ids(a.n))
        standard(a.model, [p for p in packets() if p["id"] in keep])
    elif a.cmd == "batch":
        batch(a.model, packets(a.ids), a.limit)
    else:
        collect(a.model, a.wait)


if __name__ == "__main__":
    main()
