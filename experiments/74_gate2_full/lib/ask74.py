"""Experiment 74 (from experiment 72's ask72.py): ask a model the librarian's questions of one journal (Batch), with the
spend guard and the per-call log.

    python ask74.py count   --model M --ids FILE           input tokens (free count endpoints) of those questions
    python ask74.py batch   --model M --ids FILE [--limit N] submit one Batch job of the listed questions not yet
                                                           answered by M
    python ask74.py collect --model M [--wait]              collect M's open jobs
    python ask74.py spend                                   the log's totals

Questions: every OUT/questions/*.jsonl (id, domain, question, options, evidence; `meta` is never sent). Models
(experiment 71's settings): gemini-3.8-flash (thinking low), claude-opus-5-5 and claude-sonnet-5-5 (adaptive thinking,
effort medium, the system prompt cached). Keys: experiment 71's clients (never printed).

Spend: every answer is a row of OUT/spend.jsonl (experiment 74's spend74.py sums them with the reading log). GUARD:
a job is refused unless this journal's log + the worst case of the open jobs + this job's worst case (every input
counted generously, every answer at its maximum output, Batch list price) stays under LIB74_GUARD dollars (set per
journal by the lead so that experiment 74's $400 cap holds).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import os

from common74 import E71, JOURNAL, OUT, add_paths, jl

add_paths(E71)
import prompt74 as PR  # noqa: E402
import run71  # noqa: E402  (its clients, parse and usage helpers; nothing in experiment 71 is changed)

SPEND = OUT / "spend.jsonl"
ANS = OUT / "answers"
STATE = OUT / "batch_state74.json"
GUARD = float(os.environ["LIB74_GUARD"]) if os.environ.get("LIB74_GUARD") else None
CAP_TOTAL = GUARD
PRICE = {"gemini-3.8-flash": (0.75, 3.75), "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}
MAX_OUT = {"gemini-3.8-flash": 1500, "claude-sonnet-5-5": 1200, "claude-opus-5-5": 1200}
# exp 71: Flash (thinking low) max 1,381 / mean 155 output tokens (here 1,325 / 150); Opus max 738; Sonnet max 313. A
# truncated answer is
# re-asked or goes up a tier, never guessed.
THINK = {"gemini-3.8-flash": "low"}
EFFORT = {"claude-sonnet-5-5": "medium", "claude-opus-5-5": "medium"}


def provider(m):
    return "anthropic" if m.startswith("claude") else "gemini"


def questions(ids=None) -> list[dict]:
    Q = []
    for f in sorted((OUT / "questions").glob("*.jsonl")):
        Q += jl(f)
    if ids is not None:
        keep = set(ids)
        Q = [q for q in Q if q["id"] in keep]
    return Q


def spent(prov=None) -> float:
    return sum(r["usd"] for r in jl(SPEND) if prov is None or provider(r["model"]) == prov)


def answered(model) -> set:
    return {a["id"] for a in jl(ANS / f"{model}.jsonl")}


def record(model, qid, ans, tin, tout, think, mode, finish=None, raw=None, cache_read=0, cache_write=0, job=None):
    pin, pout = PRICE[model]
    if mode == "batch":
        pin, pout = pin / 2, pout / 2
    usd = (tin + cache_write * 1.25 + cache_read * 0.1) / 1e6 * pin + (tout + think) / 1e6 * pout
    OUT.mkdir(exist_ok=True)
    ANS.mkdir(exist_ok=True)
    with open(SPEND, "a") as f:
        f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=model, id=qid, mode=mode, tin=tin,
                                tout=tout, think=think, cache_read=cache_read, cache_write=cache_write,
                                usd=round(usd, 6), finish=finish, job=job)) + "\n")
    with open(ANS / f"{model}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(id=qid, model=model, answer=ans, tin=tin, tout=tout, think=think, usd=round(usd, 6),
                                mode=mode, finish=finish, raw=None if ans is not None else raw,
                                prompt=PR.PROMPT_VERSION, job=job), ensure_ascii=False) + "\n")
    return usd


def send(q: dict) -> dict:
    return {k: q[k] for k in ("id", "domain", "question", "options", "evidence")}


def g_request(model, q):
    return {"contents": [{"role": "user", "parts": [{"text": PR.user_text(send(q))}]}],
            "systemInstruction": {"parts": [{"text": PR.SYSTEM}]},
            "generationConfig": {"maxOutputTokens": MAX_OUT[model], "responseMimeType": "application/json",
                                 "responseSchema": PR.GSCHEMA,
                                 "thinkingConfig": {"thinkingLevel": THINK[model].upper()}}}


def a_params(model, q):
    return dict(model=model, max_tokens=MAX_OUT[model],
                system=[{"type": "text", "text": PR.SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": PR.user_text(send(q))}],
                thinking={"type": "adaptive"},
                output_config={"effort": EFFORT[model], "format": {"type": "json_schema", "schema": PR.SCHEMA}})


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=1))


def open_jobs(st, model=None):
    return [(m, j) for m, js_ in st.items() for j in js_ if not j.get("collected") and (model is None or m == model)]


def worst_case(model, Q) -> float:
    pin, pout = (x / 2 for x in PRICE[model])
    est_in = sum((len(PR.SYSTEM) + len(PR.user_text(send(q)))) / 2.0 for q in Q)     # ~2.6-3.3 chars a token measured
    return est_in / 1e6 * pin + len(Q) * MAX_OUT[model] / 1e6 * pout


def count(model, Q):
    per = []
    if provider(model) == "gemini":
        c = run71.gclient()
        for q in Q:
            per.append(c.models.count_tokens(model=model, contents=PR.SYSTEM + "\n\n" + PR.user_text(send(q))).total_tokens)
    else:
        c = run71.aclient()
        for q in Q:
            kw = a_params(model, q)
            per.append(c.messages.count_tokens(model=model, system=kw["system"], messages=kw["messages"]).input_tokens)
    print(f"{model}: {len(Q)} requests, input {sum(per)} tokens (mean {sum(per) // max(1, len(per))}, max {max(per)})")


def batch(model, Q, limit=None, tag=""):
    st = load_state()
    inflight = {i for m, j in open_jobs(st, model) for i in j["keys"]}
    done = answered(model)
    Q = [q for q in Q if q["id"] not in done and q["id"] not in inflight][:limit]
    if not Q:
        print("nothing to send")
        return
    worst = worst_case(model, Q)
    open_worst = sum(j["worst"] for m, j in open_jobs(st))
    total = spent()
    print(f"{model}: {len(Q)} requests; worst case ${worst:.2f}; spent ${total:.3f} + open jobs' worst ${open_worst:.2f}"
          f" (guard ${GUARD})")
    if GUARD is None:
        raise SystemExit("set LIB74_GUARD (dollars) before any call")
    if total + open_worst + worst > GUARD:
        print("STOP: the job's worst case could cross the cap; send fewer (--limit)")
        return
    keys = [q["id"] for q in Q]
    n = len(st.get(model, [])) + 1
    if provider(model) == "gemini":
        from google.genai import types
        c = run71.gclient()
        bf = OUT / "batch" / f"{model}_{n}{tag}.jsonl"
        bf.parent.mkdir(parents=True, exist_ok=True)
        bf.write_text("".join(json.dumps({"key": q["id"], "request": g_request(model, q)}, ensure_ascii=False) + "\n"
                              for q in Q), encoding="utf-8")
        up = c.files.upload(file=str(bf), config=types.UploadFileConfig(display_name=f"exp74-{JOURNAL}-{model}-{n}",
                                                                        mime_type="jsonl"))
        job = c.batches.create(model=model, src=up.name, config={"display_name": f"exp74-{JOURNAL}-{model}-{n}"})
        jid = job.name
    else:
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request
        c = run71.aclient()
        reqs = [Request(custom_id=q["id"], params=MessageCreateParamsNonStreaming(**a_params(model, q))) for q in Q]
        job = c.messages.batches.create(requests=reqs)
        jid = job.id
    st.setdefault(model, []).append(dict(job=jid, sent=time.strftime("%Y-%m-%d %H:%M:%S"), n=len(Q),
                                         worst=round(worst, 3), keys=keys, tag=tag))
    save_state(st)
    print(f"  submitted {jid}")


def collect(model, wait=False, poll=60):
    st = load_state()
    for m, s in open_jobs(st, model):
        if collect_one(m, s, wait, poll):
            save_state(st)


def collect_one(model, s, wait, poll):
    prov = provider(model)
    while True:
        if prov == "gemini":
            c = run71.gclient()
            job = c.batches.get(name=s["job"])
            state = job.state.name if hasattr(job.state, "name") else str(job.state)
            done = state in {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
        else:
            c = run71.aclient()
            job = c.messages.batches.retrieve(s["job"])
            state, done = job.processing_status, job.processing_status == "ended"
        print(f"  {model} {s['job']}: {state}", flush=True)
        if done or not wait:
            break
        time.sleep(poll)
    if not done:
        return False
    n = 0
    if prov == "gemini":
        if state == "JOB_STATE_SUCCEEDED":
            lines = c.files.download(file=job.dest.file_name).decode("utf-8").splitlines()
            for row in (json.loads(x) for x in lines if x.strip()):
                resp = row.get("response") or {}
                tin, tout, th = run71.g_usage(resp.get("usageMetadata") or resp.get("usage_metadata"))
                cand = (resp.get("candidates") or [{}])[0]
                fin = str(cand.get("finishReason") or row.get("error") or "none")
                text = "".join(x.get("text", "") for x in (cand.get("content") or {}).get("parts") or []
                               if not x.get("thought"))
                record(model, row.get("key"), run71.parse(text), tin, tout, th, "batch", fin, text, job=s["job"])
                n += 1
    else:
        for r in c.messages.batches.results(s["job"]):
            if r.result.type != "succeeded":
                print("   ", r.custom_id, r.result.type)
                continue
            m = r.result.message
            u = m.usage
            text = next((b.text for b in m.content if b.type == "text"), "")
            record(model, r.custom_id, run71.parse(text), u.input_tokens, u.output_tokens, 0, "batch", m.stop_reason,
                   text, u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0, job=s["job"])
            n += 1
    sent = time.mktime(time.strptime(s["sent"], "%Y-%m-%d %H:%M:%S"))
    s.update(collected=True, final=state, collected_at=time.strftime("%Y-%m-%d %H:%M:%S"),
             wall_secs=round(time.time() - sent), got=n)
    print(f"  collected {n} answers; spent ${spent():.3f} (gemini ${spent('gemini'):.3f}, anthropic "
          f"${spent('anthropic'):.3f})")
    return True


def pilot(model, Q):
    """Standard calls on a few questions (to see the schema work before a Batch job), under the same guard."""
    done = answered(model)
    for q in Q:
        if q["id"] in done:
            continue
        pin, pout = PRICE[model]
        worst = (len(PR.SYSTEM) + len(PR.user_text(send(q)))) / 2.0 / 1e6 * pin + MAX_OUT[model] / 1e6 * pout
        st = load_state()
        if GUARD is None:
            raise SystemExit("set LIB74_GUARD (dollars) before any call")
        if spent() + sum(j["worst"] for m, j in open_jobs(st)) + worst > GUARD:
            print("STOP: the guard")
            return
        if provider(model) == "gemini":
            from google.genai import types
            c = run71.gclient()
            resp = c.models.generate_content(
                model=model, contents=[{"role": "user", "parts": [{"text": PR.user_text(send(q))}]}],
                config=types.GenerateContentConfig(
                    system_instruction=PR.SYSTEM, max_output_tokens=MAX_OUT[model],
                    response_mime_type="application/json", response_schema=PR.GSCHEMA,
                    thinking_config=types.ThinkingConfig(thinking_level=THINK[model])))
            um = resp.usage_metadata
            tin, tout, th = um.prompt_token_count or 0, um.candidates_token_count or 0, um.thoughts_token_count or 0
            text, fin, cr, cw = resp.text or "", str(resp.candidates[0].finish_reason) if resp.candidates else "none", 0, 0
        else:
            c = run71.aclient()
            m = c.messages.create(**a_params(model, q))
            u = m.usage
            tin, tout, th = u.input_tokens, u.output_tokens, 0
            cr, cw = u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0
            text, fin = next((b.text for b in m.content if b.type == "text"), ""), m.stop_reason
        ans = run71.parse(text)
        usd = record(model, q["id"], ans, tin, tout, th, "standard", fin, text, cr, cw)
        print(f"  {q['id']:22s} in {tin} out {tout}+{th} ${usd:.4f} -> {(ans or {}).get('answer')} "
              f"{(ans or {}).get('ids')} {(ans or {}).get('roles')} ({(ans or {}).get('confidence')})", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["count", "pilot", "batch", "collect", "spend"])
    ap.add_argument("--model")
    ap.add_argument("--ids")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--tag", default="")
    ap.add_argument("--wait", action="store_true")
    a = ap.parse_args()
    ids = Path(a.ids).read_text().split() if a.ids else None
    if a.cmd == "count":
        count(a.model, questions(ids)[: a.limit or 30])
    elif a.cmd == "pilot":
        pilot(a.model, questions(ids)[: a.limit or 5])
    elif a.cmd == "batch":
        batch(a.model, questions(ids), a.limit, a.tag)
    elif a.cmd == "collect":
        collect(a.model, a.wait)
    else:
        rows = jl(SPEND)
        by = {}
        for r in rows:
            by.setdefault(r["model"], [0, 0.0])
            by[r["model"]][0] += 1
            by[r["model"]][1] += r["usd"]
        print(json.dumps(dict(total=round(spent(), 4), by_model={m: dict(answers=n, usd=round(u, 4))
                                                                  for m, (n, u) in by.items()}), indent=1))


if __name__ == "__main__":
    main()
