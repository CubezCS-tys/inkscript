"""Experiment 43: run prompt v2 on (a) experiment 41's 55 articles or (b) the fresh sample (sample43.json), through
the Gemini Batch API (default) or one call at a time (Standard), with a cost cap, a live spend log, resume and a
dry run. First run with calls 2026-10-18: the Batch test (README "Batch test"; 4 articles, $0.30, `--run batch_test`).

    .venv/bin/python run43.py --set a --dry-run                     request count, tokens, cost (Batch and Standard)
    .venv/bin/python run43.py --set a --cap 5 [--mode batch]        submit, poll, collect, round after round
    .venv/bin/python run43.py --set a --cap 5 --mode standard --threads 4
    .venv/bin/python run43.py --set a --assemble                    rules43 + masters (no calls)

Chunks are experiment 41's (<= 10 pages; an article of 11-30 pages is 2-3 chunks). A later chunk needs the previous
chunk's answer (the outline so far and the last block, exp 40 E), so the Batch API runs in ROUNDS: round 1 = every
article's first chunk, round 2 = the second chunks of the articles whose first came back, ... (3 rounds at most).

Outputs (out/<run>/, run = v2_55 for set a, v2_fresh for set b):
  raw/<stem>_cAAA-BBB.json  experiment 41's raw format (answer + tokens + usd + mode); saved as it arrives: a rerun
                            skips what is there (resume)
  batch_state.json          the job of each round (a rerun polls an unfinished job instead of submitting again)
  batch/round<k>.jsonl      the requests sent (kept; images inline, base64)
  dry_run.json              the estimate
Spend: out/gemini_spend.jsonl (one row per answer, like experiment 41's: tokens, usd, mode, running total). The cap
counts every logged row plus the WORST case of what is in flight (each request's input estimate + its max output);
a round that could cross the cap is cut to the requests that fit, and the run stops after it.

Batch API facts this follows (ai.google.dev, read 2026-10-18; README "Batch API"): gemini-4-argon and
gemini-3.8-flash both list Batch "Supported"; Batch = 50% of Standard, and both double on the same dates (Argon
1 Dec 2026, Flash 1 Jan 2027); thinking billed as output; JSONL file input up to 2 GB via the File API, one line
{"key", "request"}; Argon Tier 1 enqueues at most 5M tokens across active jobs (a job here is cut at
--max-enqueued, 4.5M; the rest goes in the next job); results kept 6 weeks, a job pending or running > 48 h expires; target turnaround 24 h.
Confirmed by the Batch test (probe43.py, 2026-10-18): base64 inlineData images inside the JSONL work (so do File API
fileData, --upload-images); the per-part field is "mediaResolution": {"level": "MEDIA_RESOLUTION_HIGH"} (snake_case
media_resolution is read too; HIGH is also the default: 1107 tokens a page either way, LOW 260); every answer carries
usageMetadata (promptTokenCount, candidatesTokenCount; no thoughtsTokenCount at thinking "low", as in Standard).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prompt43 as P  # noqa: E402
ST = P.ST
import common as C  # noqa: E402  (experiment 41's client: paths re-pointed below, before any call)

OUT = HERE / "out"
MODEL, THINKING = "gemini-4-argon", "low"
SETS = {"a": ("v2_55", P.E41 / "out" / "sample.json"), "b": ("v2_fresh", HERE / "sample43.json"),
        "c": ("v33_300b", HERE / "sample43b.json")}       # c: the second 300 (sample43b.py)
LOCK = threading.Lock()
DONE_STATES = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}

# experiment 41's client writes to this experiment's own log and cache, under this run's cap
C.OUT = OUT
C.SPEND = OUT / "gemini_spend.jsonl"
C.CACHE = OUT / "gemini_cache.jsonl"


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def jdump(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def articles(which: str) -> list[dict]:
    return jl(SETS[which][1])["articles"]


def raw_file(run, stem, x, y) -> Path:
    return OUT / run / "raw" / f"{stem}_c{x:03d}-{y:03d}.json"


def price(mode: str, when: str | None = None) -> tuple[float, float]:
    """USD per million tokens (input, output) for Argon on `when` (YYYY-MM-DD, default today); Batch = half."""
    when = when or time.strftime("%Y-%m-%d")
    pin, pout = C.PRICE_LATER[MODEL][1] if when >= C.PRICE_LATER[MODEL][0] else C.PRICE[MODEL]
    return (pin / 2, pout / 2) if mode == "batch" else (pin, pout)


BATCH_MAX_OUT = 32768                                       # the Batch API's limit on maxOutputTokens


def max_out(n_pages: int) -> int:
    return min(65000, 3000 * n_pages + 6000)                  # experiment 41's


# ------------------------------------------------------------------------------------------------ chunk state

def state_for(a: dict, ci: int, run: str) -> dict | None:
    """The context a later chunk gets (experiment 41's run_article): outline so far, the last block's type and text,
    from the saved answers of the earlier chunks. None for a first chunk; raises KeyError while one is missing."""
    if ci == 0:
        return None
    outline, last_b = [], None
    for x, y in ST.chunks(a)[:ci]:
        rf = raw_file(run, a["stem"], x, y)
        if not rf.exists():
            raise KeyError(rf.name)
        st = ST.state_of(jl(rf)["answer"], outline)
        outline, last_b = st["outline"], st["last_block"] or last_b
    ot = [dict(level=o["level"], text=" ".join(ST.lines_text(a, o.get("lines") or []))[:120]) for o in outline[-25:]]
    last_text = ""
    if last_b:
        ids = last_b.get("lines") or [i for h in (last_b.get("hemistichs") or []) for i in (h or [])] or \
            [i for r in (last_b.get("rows") or []) for c in r if isinstance(c, dict) for i in c.get("lines") or []]
        last_text = " ".join(ST.lines_text(a, ids))
    return dict(outline=json.dumps(ot, ensure_ascii=False), btype=(last_b or {}).get("type", "?"), last=last_text[-500:])


def ready_chunks(arts, run) -> list[tuple]:
    """(article, chunk index, x, y) whose earlier chunks are answered and which are not answered themselves."""
    out = []
    for a in arts:
        for ci, (x, y) in enumerate(ST.chunks(a)):
            if raw_file(run, a["stem"], x, y).exists():
                continue
            if (raw_file(run, a["stem"], x, y).parent / f"{a['stem']}_c{x:03d}-{y:03d}.failed.json").exists():
                break                                         # a failed chunk stops its article (as in 41)
            try:
                state_for(a, ci, run)
            except KeyError:
                break
            out.append((a, ci, x, y))
            break
    return out


# ------------------------------------------------------------------------------------------------ estimate

def calibration() -> dict:
    """Experiment 41's Argon run, as estimated here vs as billed: input factor and output tokens per Azure line."""
    est_in = tin = tout = nlines = 0
    for f in sorted((HERE.parent / "41_azure_structure/out/argon/raw").glob("*.json")):
        r = jl(f)
        a = ST.art_of(r["stem"])
        chars = sum(len(L["text"]) + 26 for p in range(r["first"], r["last"] + 1) for L in ST.page_lines(a, p)[0])
        est_in += 1150 * (r["pages"] + (r["first"] > 1)) + (chars + len(ST.PROMPT)) / 2.6
        nlines += sum(len(ST.page_lines(a, p)[0]) for p in range(r["first"], r["last"] + 1))
        tin += r.get("tin") or 0
        tout += r.get("tout") or 0
    return dict(in_factor=tin / est_in, out_per_line=tout / nlines, v2_out_factor=1.10,
                note="from experiment 41's 67 Argon chunks; output +10% for v2 (ornaments, cuts, endnote ids)")


def estimate(arts, run, calib) -> dict:
    """Requests, tokens and cost of everything not yet answered (no calls; images not rendered)."""
    n = tin = tout = worst_out = pages = 0
    rounds = {}
    missing = []
    for a in arts:
        if not Path(a["azure"]).exists():
            missing.append(a["stem"])
            npg = a.get("n") or a.get("pages_total") or 10
            lines_pp, chars_pl = 43, 70                        # experiment 41's averages per page / line
            for ci, (x, y) in enumerate(ST.chunks(dict(a, first=1, last=npg))):
                k = y - x + 1
                n += 1
                pages += k
                rounds[ci + 1] = rounds.get(ci + 1, 0) + 1
                tin += calib["in_factor"] * (1150 * (k + (x > 1)) + (k * lines_pp * (chars_pl + 26) +
                                                                     len(P.PROMPT_V2)) / 2.6)
                tout += calib["out_per_line"] * calib["v2_out_factor"] * k * lines_pp
                worst_out += max_out(k)
            continue
        for ci, (x, y) in enumerate(ST.chunks(a)):
            if raw_file(run, a["stem"], x, y).exists():
                continue
            k = y - x + 1
            ls = sum(len(ST.page_lines(a, p)[0]) for p in range(x, y + 1))
            ptxt = P.prompt_text_only(a, ci, x, y, dict(outline="[]" * 300, btype="paragraph", last="x" * 500)
                                      if ci else None)
            n += 1
            pages += k
            rounds[ci + 1] = rounds.get(ci + 1, 0) + 1
            tin += calib["in_factor"] * (1150 * (k + (x > 1)) + len(ptxt) / 2.6)
            tout += calib["out_per_line"] * calib["v2_out_factor"] * ls
            worst_out += max_out(k)
    cost = {}
    for mode in ("batch", "standard"):
        for label, when in (("now", None), ("from 2026-12-01", "2026-12-01")):
            pin, pout = price(mode, when)
            cost[f"{mode} {label}"] = dict(expected=round(tin / 1e6 * pin + tout / 1e6 * pout, 2),
                                           worst=round(tin / 1e6 * pin + worst_out / 1e6 * pout, 2))
    return dict(run=run, articles=len(arts), requests=n, rounds=rounds, pages=pages, input_tokens=int(tin),
                output_tokens_expected=int(tout), output_tokens_worst=int(worst_out), usd=cost,
                not_on_disk=len(missing), calibration=calib)


# ------------------------------------------------------------------------------------------------ standard mode

def run_standard(arts, run, cap, threads):
    C.CAP = cap

    def one(a):
        for ci, (x, y) in enumerate(ST.chunks(a)):
            rf = raw_file(run, a["stem"], x, y)
            if rf.exists():
                continue
            prompt, imgs, nimg = P.make_prompt(a, ci, x, y, state_for(a, ci, run))
            info = {}
            ans, usd = C.gemini(prompt, images=imgs, tag=f"{run}_{a['stem']}_c{x:03d}-{y:03d}", model=MODEL,
                                max_out=max_out(y - x + 1), thinking=THINKING, json_out=True,
                                est_in=ST.est_tokens(prompt, nimg), info=info)
            rec = dict(stem=a["stem"], first=x, last=y, pages=y - x + 1, usd=usd, mode="standard",
                       prompt=P.PROMPT_VERSION, **{k: info.get(k) for k in ("finish", "tin", "tout", "think", "secs",
                                                                           "cached", "error")})
            if ans is None:
                jdump(rf.parent / (rf.stem + ".failed.json"), dict(rec, failed=True))
                print(f"  {a['stem']} c{x}-{y}: FAILED {info.get('finish') or info.get('error') or 'refused'}",
                      flush=True)
                return
            jdump(rf, dict(rec, answer=ans if isinstance(ans, dict) else {"pages": ans}))
            print(f"  {a['stem']} c{x}-{y}: ${usd:.4f}  [total ${C.spent():.3f}]", flush=True)
    with ThreadPoolExecutor(min(4, threads)) as ex:
        list(ex.map(one, arts))


# ------------------------------------------------------------------------------------------------ batch mode

def request_line(a, ci, x, y, run, upload, client) -> tuple[str, dict, int, int]:
    prompt, imgs, nimg = P.make_prompt(a, ci, x, y, state_for(a, ci, run))
    parts = []
    for k, im in enumerate(imgs, 1):
        if len(imgs) > 1:
            parts.append({"text": f"Image {k}:"})
        if upload:
            import io
            f = client.files.upload(file=io.BytesIO(im), config=dict(mime_type="image/jpeg"))
            img = {"fileData": {"fileUri": f.uri, "mimeType": "image/jpeg"}}
        else:
            img = {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(im).decode()}}
        img["mediaResolution"] = {"level": "MEDIA_RESOLUTION_HIGH"}     # the SDK's REST shape (camelCase)
        parts.append(img)
    parts.append({"text": prompt})
    key = f"{run}_{a['stem']}_c{x:03d}-{y:03d}"
    mo = min(max_out(y - x + 1), BATCH_MAX_OUT)   # Batch refuses more (no decoding continuation); 41's largest answer: 13.9k
    req = {"contents": [{"role": "user", "parts": parts}],
           "generationConfig": {"maxOutputTokens": mo, "responseMimeType": "application/json",
                                "thinkingConfig": {"thinkingLevel": THINKING.upper()}}}
    return key, {"key": key, "request": req}, ST.est_tokens(prompt, nimg), mo


def log_spend(tag, tin, tout, think, usd, finish, mode):
    with LOCK:
        total = C.spent() + usd
        C.SPEND.parent.mkdir(parents=True, exist_ok=True)
        with open(C.SPEND, "a") as f:
            f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=MODEL, tag=tag, tin=tin, tout=tout,
                                    think=think, usd=round(usd, 6), secs=None, finish=finish, mode=mode,
                                    total=round(total, 4))) + "\n")


def collect(job, run, meta, client):
    """Write every answer of a finished job: raw file (or .failed.json + the text in out/truncated), spend row."""
    pin, pout = price("batch")
    if job.dest and getattr(job.dest, "file_name", None):
        lines = client.files.download(file=job.dest.file_name).decode("utf-8").splitlines()
        rows = [json.loads(s) for s in lines if s.strip()]
    else:
        rows = [dict(key=meta["keys"][k], response=r.response.model_dump(mode="json") if r.response else None,
                     error=str(r.error) if getattr(r, "error", None) else None)
                for k, r in enumerate(job.dest.inlined_responses or [])]
    n_ok = 0
    for row in rows:
        key = row.get("key") or (row.get("metadata") or {}).get("key")
        stem, cx = key[len(run) + 1:].rsplit("_c", 1)
        x, y = (int(v) for v in cx.split("-"))
        rf = raw_file(run, stem, x, y)
        resp = row.get("response") or {}
        um = resp.get("usageMetadata") or resp.get("usage_metadata") or {}
        tin = um.get("promptTokenCount") or um.get("prompt_token_count") or 0
        think = um.get("thoughtsTokenCount") or um.get("thoughts_token_count") or 0
        tout = (um.get("candidatesTokenCount") or um.get("candidates_token_count") or 0) + think
        usd = tin / 1e6 * pin + tout / 1e6 * pout
        cand = (resp.get("candidates") or [{}])[0]
        fin = str(cand.get("finishReason") or cand.get("finish_reason") or row.get("error") or "none")
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts") or []
                       if not p.get("thought"))
        if tin or tout:
            log_spend(key, tin, tout, think, usd, fin, "batch")
        elif resp:                     # an answer without usage metadata: log the worst case, never nothing
            usd = meta.get("worst_usd", 0) / max(1, len(meta.get("keys") or [1]))
            log_spend(key, 0, 0, 0, usd, fin + " (no usage metadata: worst-case share logged)", "batch")
        rec = dict(stem=stem, first=x, last=y, pages=y - x + 1, usd=usd, mode="batch", prompt=P.PROMPT_VERSION,
                   finish=fin, tin=tin, tout=tout, think=think, job=job.name)
        ans = None
        if "MAX_TOKENS" not in fin and text.strip():
            try:
                ans = json.loads(text)
            except Exception:
                ans = None
        if ans is None:
            (OUT / "truncated").mkdir(parents=True, exist_ok=True)
            (OUT / "truncated" / f"{key}.txt").write_text(text, encoding="utf-8")
            jdump(rf.parent / (rf.stem + ".failed.json"), dict(rec, failed=True))
            continue
        jdump(rf, dict(rec, answer=ans if isinstance(ans, dict) else {"pages": ans}))
        n_ok += 1
    print(f"  collected {len(rows)} answers ({n_ok} usable); spent ${C.spent():.3f}", flush=True)


def run_batch(arts, run, cap, upload, poll, max_enqueued):
    from google.genai import types
    client = C._client()
    sf = OUT / run / "batch_state.json"
    state = jl(sf) if sf.exists() else dict(rounds=[])
    while True:
        open_jobs = [r for r in state["rounds"] if not r.get("collected")]
        if open_jobs:
            r = open_jobs[0]
            while True:
                job = client.batches.get(name=r["job"])
                st = job.state.name if hasattr(job.state, "name") else str(job.state)
                print(f"  round {r['round']} job {r['job']}: {st}", flush=True)
                if st in DONE_STATES:
                    break
                time.sleep(poll)
            if st == "JOB_STATE_SUCCEEDED":
                collect(job, run, r, client)
            r.update(collected=True, final_state=st, done=time.strftime("%Y-%m-%d %H:%M:%S"),
                     create_time=str(getattr(job, "create_time", "")), end_time=str(getattr(job, "end_time", "")))
            jdump(sf, state)
            continue
        todo = ready_chunks(arts, run)
        if not todo:
            print("nothing left to send", flush=True)
            return
        # the round's worst case must fit under the cap (logged spend + this round)
        pin, pout = price("batch")
        room = cap - C.spent()
        lines, keys, worst, toks = [], [], 0.0, 0
        for a, ci, x, y in todo:
            key, line, est_in, mo = request_line(a, ci, x, y, run, upload, client)
            w = est_in / 1e6 * pin + mo / 1e6 * pout
            if lines and toks + est_in > max_enqueued:
                print(f"  enqueued-token limit: this job takes {len(lines)} of {len(todo)} ready requests; the rest "
                      f"go in the next job", flush=True)
                break
            toks += est_in
            if worst + w > room:
                print(f"  cap: ${C.spent():.3f} spent, the round is cut at {len(lines)} of {len(todo)} requests "
                      f"(worst case ${worst:.3f} of ${room:.3f} room)", flush=True)
                break
            lines.append(line)
            keys.append(key)
            worst += w
        if not lines:
            print(f"STOP: the cap ${cap} leaves no room for another request (spent ${C.spent():.3f})", flush=True)
            return
        k = len(state["rounds"]) + 1
        bf = OUT / run / "batch" / f"round{k}.jsonl"
        bf.parent.mkdir(parents=True, exist_ok=True)
        bf.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8")
        up = client.files.upload(file=str(bf), config=types.UploadFileConfig(display_name=f"{run}-round{k}",
                                                                             mime_type="jsonl"))
        job = client.batches.create(model=MODEL, src=up.name, config={"display_name": f"{run}-round{k}"})
        state["rounds"].append(dict(round=k, job=job.name, file=up.name, keys=keys, worst_usd=round(worst, 4),
                                    sent=time.strftime("%Y-%m-%d %H:%M:%S"), requests=len(lines)))
        jdump(sf, state)
        print(f"  round {k}: {len(lines)} requests, worst case ${worst:.3f}, job {job.name}", flush=True)
        # the loop goes on: it waits for this job, collects it, then sends the next round if the cap leaves room


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["a", "b", "c"], required=True,
                    help="a: experiment 41's 55; b: sample43.json; c: sample43b.json (the second 300)")
    ap.add_argument("--mode", choices=["batch", "standard"], default="batch")
    ap.add_argument("--cap", type=float, help="USD: stop before the logged spend could pass this")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--assemble", action="store_true", help="rules43 + masters of what is answered (no calls)")
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--run", help="output folder name under out/ (default v2_55 / v2_fresh)")
    ap.add_argument("--prompt", default="v2", help="prompt version (prompt43.PROMPTS): v2 or v3 (live 2026-10-18)")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--upload-images", action="store_true", help="batch: pages through the File API, not inline")
    ap.add_argument("--poll", type=int, default=60, help="seconds between job polls")
    ap.add_argument("--max-enqueued", type=int, default=4_500_000,
                    help="input tokens per job (Argon Tier 1 allows 5M enqueued tokens across active jobs)")
    args = ap.parse_args()
    P.use(args.prompt)
    run = args.run or SETS[args.set][0]
    if args.set in ("b", "c"):                # page renders of the fresh samples stay in this experiment
        ST.PAGES = OUT / "pages"
    arts = [a for a in articles(args.set) if not args.stems or a["stem"] in args.stems]
    if args.dry_run:
        e = estimate(arts, run, calibration())
        jdump(OUT / run / "dry_run.json", e)
        print(json.dumps(e, indent=1))
        return
    if args.assemble:
        import replay43 as RP
        RP.assemble_run(run, arts)
        return
    if args.cap is None:
        sys.exit("--cap is required for a run with calls")
    print(f"{run}: {len(arts)} articles, prompt {P.PROMPT_VERSION}, mode {args.mode}, cap ${args.cap}; spent so far ${C.spent():.3f}", flush=True)
    if args.mode == "standard":
        run_standard(arts, run, args.cap, args.threads)
    else:
        run_batch(arts, run, args.cap, args.upload_images, args.poll, args.max_enqueued)
    print(f"spent ${C.spent():.3f}")


if __name__ == "__main__":
    main()
