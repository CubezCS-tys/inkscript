"""Experiment 43: the bespoke retry — when the judge says "look again" (route retry), the reader model (Argon, the
run's own prompt) answers that ONE page again: the run's request for the page (its lines, its image, the context of
the pages before it) + the judge's evidence and instruction + close-ups of the region at full resolution (300 dpi
render). The answer goes through rules43 like any answer; what it changes on the page becomes one patch
(source gemini-retry, action replace_page_blocks: blocks and noise by line id — no word changes: the first answer's
fixes stay), applied only when the code check passes (every Azure line of the page used once or noise, every split
part known, every call's note found). One retry per page; after that the owner.

    python3 retry43.py --run v33_300 --page STEM:P --instruction "..." [--evidence "..."] [--blocks p11b4 p11b5]
                       [--model gemini-4-argon] [--dry-run]
Answers: out/judge/retry/<run>/<stem>_pNNN.json; patch proposal printed and added to
out/v33_300_judged/patches/<stem>.json (apply = check passed).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import judge43 as JG  # noqa: E402
import patches43 as PA  # noqa: E402
import prompt43 as P  # noqa: E402
import replay43 as RP  # noqa: E402

ST, C, OUT = JG.ST, JG.C, JG.OUT
NOTE = """
A REVIEWER compared your earlier answer for page {page} with the scan and found a problem:
  {evidence}
Instruction: {instruction}
The last {n} image(s) are close-ups of that region at full resolution. Answer page {page} again, whole, in exactly
the same format and rules as above (every line id of the page once, or noise). Do not change any word: give the
structure only (fixes as before only where the ink demands it).
"""


def raw_rec(run: str, a: dict, p: int):
    for ci, (x, y) in enumerate(ST.chunks(a)):
        if x <= p <= y:
            return ci, x, y, ST.jl(OUT / run / "raw" / f"{a['stem']}_c{x:03d}-{y:03d}.json")
    raise KeyError(p)


def state_before(run: str, a: dict, ci: int, x: int, p: int, rec: dict) -> dict | None:
    """The context the run gave the chunk, extended with this chunk's own pages before p."""
    st = JG.run43.state_for(a, ci, run) if ci else None
    if p == x:
        return st
    outline = json.loads(st["outline"]) if st else []
    part = dict(pages=[pg for pg in rec["answer"].get("pages") or [] if isinstance(pg, dict) and pg.get("page", 0) < p])
    s2 = ST.state_of(part, [])
    for o in s2["outline"]:
        outline.append(dict(level=o["level"], text=" ".join(ST.lines_text(a, o.get("lines") or []))[:120]))
    lb = s2["last_block"]
    last = " ".join(ST.lines_text(a, PA.block_lines(lb))) if lb else (st or {}).get("last", "")
    return dict(outline=json.dumps(outline[-25:], ensure_ascii=False), btype=(lb or {}).get("type", "?"),
                last=last[-500:])


def crops(a: dict, p: int, boxes: list) -> list[bytes]:
    import cv2
    img = cv2.imread(str(ST.page_image(a, p)), cv2.IMREAD_COLOR)
    H, W = img.shape[:2]
    bx = JG.PA_union([b for b in boxes if b]) or [0, 0, 1000, 1000]
    x0, y0, x1, y1 = (max(0, int((bx[0] - 30) * W / 1000)), max(0, int((bx[1] - 30) * H / 1000)),
                      min(W, int((bx[2] + 30) * W / 1000)), min(H, int((bx[3] + 30) * H / 1000)))
    c = img[y0:y1, x0:x1]
    out = []
    step = 1400                                      # tall regions: in overlapping strips of ~1400 px
    for t in range(0, max(1, c.shape[0] - 200), step - 200):
        part = c[t:t + step]
        s = min(1.0, 2000 / max(part.shape[:2]))
        if s < 1:
            part = cv2.resize(part, (int(part.shape[1] * s), int(part.shape[0] * s)), interpolation=cv2.INTER_AREA)
        out.append(cv2.imencode(".jpg", part, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes())
        if len(out) == 3:
            break
    return out


def check(a: dict, p: int, old_ans: dict, new_ans: dict, all_notes: set = frozenset()) -> dict:
    ls, _, _ = ST.page_lines(a, p)
    ids = {l["id"] for l in ls}
    pg = next((x for x in new_ans.get("pages") or [] if isinstance(x, dict) and x.get("page") == p), None)
    if not pg:
        return dict(ok=False, why="no page in the answer")
    used = [x for b in pg.get("blocks") or [] if isinstance(b, dict) for x in PA.block_lines(b)]
    noise = [str(x) for x in new_ans.get("noise") or [] if str(x).startswith(f"{p}:")]
    old_splits = {s["line"] for s in old_ans.get("splits") or [] if isinstance(s, dict)}
    bad_split = [x for x in used + noise if x not in ids and x.rstrip("abcdefgh") not in old_splits]
    base = [x if x in ids else x.rstrip("abcdefgh") for x in used + noise]
    missing = sorted(ids - set(base))
    dup = sorted({x for x in used if used.count(x) > 1})
    notes = set(all_notes) | {b.get("id") for pg2 in old_ans.get("pages") or [] if isinstance(pg2, dict)
             for b in pg2.get("blocks") or [] if isinstance(b, dict) and b.get("id")}
    notes |= {b.get("id") for b in pg.get("blocks") or [] if isinstance(b, dict) and b.get("id")}
    calls = [c.get("fn") for b in pg.get("blocks") or [] if isinstance(b, dict) for c in b.get("calls") or []
             if isinstance(c, dict)]
    lost = [f for f in calls if f and f not in notes]
    ok = not (missing or dup or bad_split or lost)
    return dict(ok=ok, why=f"{len(ids)} lines: missing {len(missing)}, twice {len(dup)}, split parts unknown "
                         f"{len(bad_split)}, calls without a note {len(lost)}",
                missing=missing[:10], dup=dup[:10], bad_split=bad_split[:10], lost=lost[:10], page=pg, noise=noise)


def retry(run: str, stem: str, p: int, instruction: str, evidence: str, blocks: list[str], model: str,
          dry: bool = False) -> dict | None:
    a = JG.art(run, stem)
    ci, x, y, rec = raw_rec(run, a, p)
    P.use(rec.get("prompt") or "v3.3")
    st = state_before(run, a, ci, x, p, rec)
    prompt, imgs, n = P.make_prompt(a, ci if p == x else max(ci, 1), p, p, st)
    v = JG.page_view(run, stem, p)
    B = {b["id"]: b for b in v["blocks"]}
    cs = crops(a, p, [B[b]["box"] for b in blocks if b in B])
    prompt = prompt + NOTE.format(page=p, evidence=evidence, instruction=instruction, n=len(cs))
    imgs = imgs + cs
    est = ST.est_tokens(prompt, len(imgs))
    mo = JG.run43.max_out(1)
    pin, pout = JG.PRICE[model]
    print(f"  {stem} p{p}: {len(imgs)} images, ~{est} tokens in, worst ${est / 1e6 * pin + mo / 1e6 * pout:.3f}")
    if dry:
        return None
    C.CAP = JG.CAP_TOTAL
    info = {}
    ans, usd = C.gemini(prompt, images=imgs, tag=f"judge_retry_{run}_{stem}_p{p:03d}", model=model, max_out=mo,
                        thinking="low", json_out=True, est_in=est, info=info)
    out = dict(stem=stem, first=p, last=p, pages=1, usd=usd, mode="standard", prompt=P.PROMPT_VERSION, model=model,
               instruction=instruction, evidence=evidence, blocks=blocks, answer=ans,
               **{k: info.get(k) for k in ("finish", "tin", "tout", "think", "secs")})
    f = JG.J / "retry" / run / f"{stem}_p{p:03d}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ${usd:.4f} {info.get('tin')}/{info.get('tout')} {info.get('finish')}  [log ${C.spent():.3f}]")
    if ans is None:
        return out
    new_ans, _log = RP.apply_rules(a, dict(out, answer=ans if isinstance(ans, dict) else {"pages": ans}))
    old = ST.jl(JG.RUNS[run]["rules"] / f"{stem}_c{x:03d}-{y:03d}.json")["answer"]
    notes = {b.get("id") for x2, y2 in ST.chunks(a)
             for pg2 in ST.jl(JG.RUNS[run]["rules"] / f"{stem}_c{x2:03d}-{y2:03d}.json")["answer"].get("pages") or []
             if isinstance(pg2, dict) for b in pg2.get("blocks") or [] if isinstance(b, dict) and b.get("id")}
    chk = check(a, p, old, new_ans, notes)   # endnotes may sit in a later chunk
    old_pg = next(g for g in old["pages"] if isinstance(g, dict) and g.get("page") == p)
    was = sorted({i for b in old_pg.get("blocks") or [] if isinstance(b, dict) for i in PA.block_lines(b)})
    patch = dict(id=f"r-{stem[:4]}-p{p}-1", run=run, article=stem, page=p, action="replace_page_blocks",
                 targets=dict(lines=was, blocks=[]),
                 payload=dict(blocks=chk.get("page", {}).get("blocks", []), noise=chk.get("noise", []), was_lines=was),
                 source="gemini-retry", confidence=None, evidence=evidence, reason=f"retry: {chk['why']}",
                 created=time.strftime("%Y-%m-%d %H:%M"), apply=bool(chk["ok"]), model=model)
    out.update(check={k: chk[k] for k in ("ok", "why", "missing", "dup", "bad_split", "lost")}, patch=patch,
               old_blocks=[dict(type=b.get("type"), lines=PA.block_lines(b)) for b in old_pg.get("blocks") or []
                           if isinstance(b, dict)],
               new_blocks=[dict(type=b.get("type"), lines=PA.block_lines(b)) for b in patch["payload"]["blocks"]
                           if isinstance(b, dict)])
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  check: {chk['why']} -> {'apply' if chk['ok'] else 'owner'}")
    pdir = OUT / "v33_300_judged" / "patches" if run == "v33_300" else JG.J / "patches_other" / run
    ps = [q for q in PA.load_patches(pdir, stem) if q["id"] != patch["id"]]
    PA.save_patches(pdir, stem, ps + [patch])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="v33_300")
    ap.add_argument("--page", required=True)
    ap.add_argument("--instruction", required=True)
    ap.add_argument("--evidence", default="")
    ap.add_argument("--blocks", nargs="*", default=[])
    ap.add_argument("--model", default="gemini-4-argon")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    s, p = a.page.rsplit(":", 1)
    retry(a.run, s, int(p), a.instruction, a.evidence, a.blocks, a.model, a.dry_run)


if __name__ == "__main__":
    main()
