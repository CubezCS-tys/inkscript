"""Experiment 60: send chunk requests to Claude Opus 5.5 (Standard or Message Batches), save the answers in
experiment 43's raw format under out/<run>/raw/, log every call in out/calls.jsonl, stop before the cap.

    run60.py --run t1 --set c --prompt v3.3 --plan out/plan_t1.json [--mode batch|standard] --cap 40 [--dry-run]

The plan (plan60.py) lists, per article, either "upto": the last page needed (every chunk up to the one holding it,
in rounds: a later chunk's context comes from CLAUDE's own earlier answers, exactly as run43.state_for does for
Gemini), or "chunks": single chunks sent with the exact request Gemini was sent in the exam (text and images read
back from the stored batch file, i.e. the context from Argon's earlier answers).
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import common60 as K
from common60 import OUT, jdump, jl


def raw_file(run, stem, x, y) -> Path:
    return OUT / run / "raw" / f"{stem}_c{x:03d}-{y:03d}.json"


def state_for(a, ci, run):
    """run43.state_for on this experiment's answers."""
    import run43
    real = run43.raw_file
    run43.raw_file = lambda r, s, x, y: raw_file(run, s, x, y)
    try:
        return run43.state_for(a, ci, run)
    finally:
        run43.raw_file = real


def stored_parts(key):
    idx = jl(OUT / "req_index.json")
    f, off = idx[key][-1]
    with open(f, "rb") as fh:
        fh.seek(off)
        return json.loads(fh.readline())["request"]["contents"][0]["parts"]


def todo(plan, arts, run, P, gemini_run):
    """(custom_id, stem, x, y, content) of every request ready now (earlier chunks answered, not answered)."""
    out = []
    for stem, want in plan.items():
        a = arts[stem]
        chs = P.ST.chunks(a)
        if "chunks" in want:
            for x, y in want["chunks"]:
                rf = raw_file(run, stem, x, y)
                if rf.exists() or rf.with_name(rf.stem + ".failed.json").exists():
                    continue
                parts = stored_parts(f"{gemini_run}_{stem}_c{x:03d}-{y:03d}")
                out.append((stem, x, y, K.content_from_gemini_parts(parts)))
            continue
        upto = want["upto"]
        for ci, (x, y) in enumerate(chs):
            if x > upto:
                break
            rf = raw_file(run, stem, x, y)
            if rf.exists():
                continue
            if rf.with_name(rf.stem + ".failed.json").exists():
                break
            try:
                st = state_for(a, ci, run)
            except KeyError:
                break
            txt, imgs, _ = P.make_prompt(a, ci, x, y, st)
            P.ST._az.pop(stem, None)
            out.append((stem, x, y, K.content_from(txt, imgs)))
            break
    return out


def worst(content, n_pages, mode):
    pin, pout = K.PRICE[mode]
    return (K.est_in(content) * pin + K.max_out(n_pages) * pout) / 1e6


def run_standard(reqs, run, args):
    c = K.client()

    def one(r):
        stem, x, y, content = r
        if K.spent() + worst(content, y - x + 1, "standard") > args.cap:
            print(f"  {stem} c{x}-{y}: skipped, cap", flush=True)
            return
        t0 = time.time()
        msg = c.messages.create(**K.params(content, y - x + 1, args.effort))
        secs = round(time.time() - t0, 1)
        rec = K.save_answer(raw_file(run, stem, x, y), stem, x, y, msg, "standard", args.prompt, args.effort,
                            dict(secs=secs))
        K.log_call(run=run, tag=f"{stem}_c{x:03d}-{y:03d}", mode="standard", tin=rec["tin"], tout=rec["tout"],
                   usd=round(rec["usd"], 6), finish=rec["finish"], parse=rec["parse"], secs=secs,
                   request_id=getattr(msg, "_request_id", None), msg_id=msg.id, pages=y - x + 1,
                   images=sum(1 for b in content if b["type"] == "image"))
        print(f"  {stem} c{x}-{y}: {rec['finish']} {rec['parse']} in {rec['tin']} out {rec['tout']} "
              f"${rec['usd']:.4f} {secs}s [total ${K.spent():.3f}]", flush=True)
    with ThreadPoolExecutor(args.threads) as ex:
        list(ex.map(one, reqs))


MAX_BYTES = 150_000_000          # the Message Batches API refuses a body over 256 MB (413 on the first try)


def run_batch_round(reqs, run, args):
    """One Message Batch: submit what fits under the cap, poll, collect, delete the batch on Anthropic's side."""
    c = K.client()
    sf = OUT / run / "batches.json"
    state = jl(sf) if sf.exists() else []
    room = args.cap - K.spent() - sum(b["worst_usd"] for b in state if not b.get("collected"))
    sel, w, size = [], 0.0, 0
    for r in reqs:
        ww = worst(r[3], r[2] - r[1] + 1, "batch")
        sz = sum(len(b.get("text") or b.get("source", {}).get("data", "")) for b in r[3]) + 2000
        if sel and size + sz > MAX_BYTES:
            print(f"  size: batch cut at {len(sel)} of {len(reqs)} ({size / 1e6:.0f} MB); the rest go next", flush=True)
            break
        if w + ww > room:
            print(f"  cap: round cut at {len(sel)} of {len(reqs)} (worst ${w:.2f} of ${room:.2f} room)", flush=True)
            break
        sel.append(r)
        w += ww
        size += sz
    if not sel:
        print("STOP: no room under the cap", flush=True)
        return False
    batch = c.messages.batches.create(requests=[
        dict(custom_id=f"q{k:04d}", params=K.params(cont, y - x + 1, args.effort))
        for k, (s, x, y, cont) in enumerate(sel)])
    meta = dict(id=batch.id, sent=time.strftime("%Y-%m-%d %H:%M:%S"), n=len(sel), worst_usd=round(w, 4),
                keys=[f"{s}_c{x:03d}-{y:03d}" for s, x, y, _ in sel])
    state.append(meta)
    jdump(sf, state)
    print(f"  batch {batch.id}: {len(sel)} requests, worst ${w:.2f}", flush=True)
    collect(c, meta, run, args, state, sf)
    return True


def collect(c, meta, run, args, state, sf):
    t0 = time.time()
    while True:
        b = c.messages.batches.retrieve(meta["id"])
        if b.processing_status == "ended":
            break
        print(f"    {meta['id']}: {b.processing_status} {dict(b.request_counts)} {int(time.time() - t0)}s", flush=True)
        time.sleep(args.poll)
    n_ok = 0
    for res in c.messages.batches.results(meta["id"]):
        key = meta["keys"][int(res.custom_id[1:])]
        stem, xy = key.rsplit("_c", 1)
        x, y = map(int, xy.split("-"))
        if res.result.type != "succeeded":
            K.log_call(run=run, tag=key, mode="batch", usd=0, finish=res.result.type, batch_id=meta["id"])
            print(f"    {key}: {res.result.type}", flush=True)
            continue
        msg = res.result.message
        rec = K.save_answer(raw_file(run, stem, x, y), stem, x, y, msg, "batch", args.prompt, args.effort,
                            dict(batch_id=meta["id"]))
        K.log_call(run=run, tag=key, mode="batch", tin=rec["tin"], tout=rec["tout"], usd=round(rec["usd"], 6),
                   finish=rec["finish"], parse=rec["parse"], batch_id=meta["id"], msg_id=msg.id, pages=y - x + 1)
        n_ok += rec["ok"]
    meta.update(collected=True, ended=time.strftime("%Y-%m-%d %H:%M:%S"), secs=int(time.time() - t0),
                created_at=str(b.created_at), ended_at=str(b.ended_at))
    try:                                   # privacy: the batch's inputs and outputs off Anthropic's storage now
        c.messages.batches.delete(meta["id"])
        meta["deleted"] = time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:                 # noqa: BLE001
        meta["delete_error"] = f"{type(e).__name__}: {e}"[:300]
    jdump(sf, state)
    print(f"  collected {meta['n']} ({n_ok} usable) in {meta['secs']}s; spent ${K.spent():.3f}; "
          f"deleted: {meta.get('deleted', meta.get('delete_error'))}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--set", default="c")
    ap.add_argument("--prompt", default="v3.3")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--gemini-run", default="v33_300b", help="the run whose stored requests 'chunks' entries reuse")
    ap.add_argument("--mode", choices=["batch", "standard"], default="batch")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--cap", type=float, default=K.CAP)
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--poll", type=int, default=60)
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true", help="one round only")
    args = ap.parse_args()
    args.cap = min(args.cap, K.CAP)
    P = K.pipeline()
    P.use(args.prompt)
    arts = K.articles(args.set)
    plan = {s: v for s, v in jl(args.plan).items() if not args.stems or s in args.stems}
    while True:
        reqs = todo(plan, arts, args.run, P, args.gemini_run)
        if not reqs:
            print("nothing left to send", flush=True)
            return
        if args.dry_run:
            ins = sum(K.est_in(r[3]) for r in reqs)
            print(f"ready now: {len(reqs)} requests, {sum(r[2] - r[1] + 1 for r in reqs)} pages, est. input {ins} "
                  f"tokens, worst batch ${sum(worst(r[3], r[2] - r[1] + 1, 'batch') for r in reqs):.2f}")
            return
        print(f"{args.run}: {len(reqs)} ready; spent ${K.spent():.3f} of cap ${args.cap}", flush=True)
        if args.mode == "standard":
            run_standard(reqs, args.run, args)
        elif not run_batch_round(reqs, args.run, args):
            return
        if args.once:
            return


if __name__ == "__main__":
    main()
