"""The page bundle the /lab page reads, and scores against the owner's saved correction.

build_bundle(root, dataset, page_id) -> out/data/bundles/<dataset>/<page_id>.json
    every (non-fixture) run's output for the page: blocks with boxes and types, its text in its own order, lines as
    correction candidates, timing / memory / cost, failures; and how much the engines DISAGREE with each other
    (edit distance between two engines' texts / the mean of their lengths; no truth involved, never called error).
evaluate_page_runs(root, dataset, page_id, revision=None) -> out/data/scores/<page_id>.<revision>.json
    every run scored against the owner's correction (recognition under every policy, completeness, layout, reading
    order).  Cached on (revision, prediction files); a new revision or a new run re-scores without inference.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from . import annotations as A
from . import evaluation as EV
from .ingest import atomic_write, read_manifest, render_by_id, safe_child
from .runs import connect, load_predictions
from .schemas import PagePrediction

SCORER_VERSION = "scores/3"          # bump when scoring or flagging changes: cached scores are then remade

LABELS = {
    ("azure_read", "existing"): ("Ours: Azure Read (existing output)", "ours"),
    ("azure_argon", "existing"): ("Ours: Azure + Gemini Argon (existing output, our masters)", "ours"),
    ("paddle_vl", "pipeline"): ("PaddleOCR-VL-1.6, full pipeline", "open"),
    ("paddle_vl", "bare_ocr"): ("PaddleOCR-VL-1.6, recogniser alone (no layout)", "open"),
    ("paddle_vl", "layout_stage"): ("PP-DocLayoutV3, layout stage alone (no text)", "open"),
    ("nuqta", "as_written"): ("Nuqta-Arabic-OCR-4B, as written", "open"),
    ("nuqta", "markdown"): ("Nuqta-Arabic-OCR-4B, Markdown mode", "open"),
    ("nuqta", "as_written_fast"): ("Nuqta-Arabic-OCR-4B, as written, fast kernels", "open"),
    ("nuqta", "as_written_speedfix"): ("Nuqta-Arabic-OCR-4B, as written, speed fix (same output)", "open"),
    ("nuqta", "markdown_speedfix"): ("Nuqta-Arabic-OCR-4B, Markdown mode, speed fix", "open"),
    ("combo_paddle_nuqta", "regions_speedfix_rtl"): ("COMBINATION + right-to-left column rule (code only)", "open"),
    ("combo_paddle_nuqta", "regions_speedfix"): ("COMBINATION: Paddle 1.6 regions and order, Nuqta's text per region", "open"),
    ("paddle_vl15_exp36", "pipeline"): ("PaddleOCR-VL-1.5, full pipeline (experiment 36, imported)", "earlier"),
}
ENGINE_FACTS = {
    "azure_read": dict(model="Azure AI Document Intelligence prebuilt-read 2024-11-30", licence="commercial service",
                       where="hosted (Microsoft); output already on disk, no new call"),
    "azure_argon": dict(model="Azure prebuilt-read lines + Gemini 4 Argon structure and fixes (experiment 41)",
                        licence="commercial services", where="hosted; output already on disk, no new call"),
    "paddle_vl": dict(model="PaddlePaddle/PaddleOCR-VL-1.6 @ c5630ab + PP-DocLayoutV3", licence="Apache-2.0",
                      where="rented GPU (Vast.ai, datacenter)"),
    "nuqta": dict(model="SalahALHaismawi/Nuqta-Arabic-OCR-4B @ 6a8cdd6", licence="Apache-2.0",
                  where="rented GPU (Vast.ai, datacenter)",
                  caveat="its card discloses 234 KITAB-Bench test images in its training data; public benchmark "
                         "numbers do not replace our own pages"),
    "combo_paddle_nuqta": dict(model="PaddleOCR-VL-1.6 layout (regions, kinds, order) + Nuqta-Arabic-OCR-4B text on "
                                     "each region's crop", licence="Apache-2.0 + Apache-2.0", where="rented GPU"),
    "paddle_vl15_exp36": dict(model="PaddlePaddle/PaddleOCR-VL-1.5 @ 2a4195f + PP-DocLayoutV3", licence="Apache-2.0",
                              where="experiment 36's rented RTX 5090 (2026-10-12)"),
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def con_rows(root: Path, dataset: str, page_id: str) -> list[dict]:
    con = connect(root)
    return [dict(r) for r in con.execute(
        "SELECT r.*, p.state, p.artifact FROM runs r JOIN pages p ON p.run_id=r.run_id WHERE r.dataset=? "
        "AND p.page_id=? AND r.is_fixture=0 ORDER BY r.created_at", (dataset, page_id))]


def latest_runs(root: Path, dataset: str, page_id: str) -> list[dict]:
    """The newest non-fixture run per (engine, variant) that covers the page (succeeded or failed)."""
    con = connect(root)
    rows = con.execute("SELECT r.*, p.state, p.artifact, p.error_kind, p.error_message, p.attempts FROM runs r "
                       "JOIN pages p ON p.run_id=r.run_id WHERE r.dataset=? AND p.page_id=? AND r.is_fixture=0 "
                       "ORDER BY r.created_at", (dataset, page_id)).fetchall()
    best = {}
    for r in rows:
        best[(r["engine"], r["variant"])] = dict(r)
    return list(best.values())


def gpu_sessions(root: Path) -> list[dict]:
    """Every GPU session the lab has had (out/gpu_session*.json beside the data root): card, rate, start, end."""
    from datetime import datetime
    out = []
    for f in sorted(root.parent.glob("gpu_session*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            continue
        st = datetime.fromisoformat(d["started"]).timestamp()
        en = datetime.fromisoformat(d["ended"]).timestamp() if d.get("ended") else float("inf")
        out.append(dict(instance=d["instance"], gpu=f"{d['gpu']} {d.get('gpu_gb', '')} GB".strip(), dph=d["dph"],
                        start=st, end=en, started=d["started"], ended=d.get("ended"), usd=d.get("usd")))
    return out


def session_of(root: Path, created_at: str) -> Optional[dict]:
    from datetime import datetime
    t = datetime.fromisoformat(created_at).timestamp()
    for s in gpu_sessions(root):
        if s["start"] <= t <= s["end"]:
            return s
    return None


def gpu_rate(root: Path) -> Optional[dict]:
    f = root / "gpu_rate.json"
    return json.loads(f.read_text()) if f.exists() else None


# ------------------------------------------------------------------------------------------------ candidates

def candidate_lines(pred: PagePrediction) -> list[dict]:
    """Lines an engine offers as a starting point for the correction: id, text, box (when the engine has one per
    line), region (its block)."""
    if pred.engine == "azure_read":
        raw = pred.result.raw
        pg = raw["page"]
        s = 300.0 if pg["unit"] == "inch" else 1.0
        paras = raw["paragraphs"]
        out = []
        for i, ln in enumerate(pg["lines"]):
            xs, ys = ln["polygon"][0::2], ln["polygon"][1::2]
            off = ln["spans"][0]["offset"]
            reg = None
            for j, p in enumerate(paras):
                sp = p["spans"][0]
                if sp["offset"] <= off < sp["offset"] + sp["length"]:
                    reg = f"b{j}"
            out.append(dict(id=f"L{i}", text=ln["content"], box=[min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s],
                            region=reg))
        return out
    out = []
    for b in EV.text_blocks(pred.result.blocks):
        parts = [x for x in b.raw_text.split("\n") if x.strip()] if b.type != "table" else [b.raw_text]
        for k, t in enumerate(parts):
            out.append(dict(id=f"{b.block_id}.{k}", text=t, box=b.box if len(parts) == 1 else None,
                            region=b.block_id if b.box else None))
    return out


def readings_elsewhere(lines: list[dict], others: dict[str, str]) -> list[dict]:
    """For each line, the best-matching stretch of every other engine's text (for the correction screen)."""
    res = []
    for ln in lines:
        t = EV.POLICIES["raw"](ln["text"])
        row = {}
        for rid, txt in others.items():
            if len(t) < 3 or not txt:
                row[rid] = None
                continue
            al = fuzz.partial_ratio_alignment(t, txt)
            if al is None or al.score < 50:
                row[rid] = dict(text=None, score=round(al.score, 1) if al else 0.0)
                continue
            seg = txt[al.dest_start:al.dest_end]
            # widen to whole words
            a, b = al.dest_start, al.dest_end
            while a > 0 and not txt[a - 1].isspace():
                a -= 1
            while b < len(txt) and not txt[b].isspace():
                b += 1
            seg = txt[a:b]
            row[rid] = dict(text=seg, score=round(al.score, 1), same=seg.strip() == t.strip())
        res.append(row)
    return res


def bag_disagreement(a: str, b: str, policy: str) -> Optional[float]:
    """Order-free: 1 - F1 of the two texts' word multisets under the policy (exp 40/41's measure)."""
    f = EV.POLICIES[policy]
    return EV.bag_error(f(a).split(), f(b).split())["rate"]


def disagreement(a: str, b: str, policy: str) -> Optional[float]:
    f = EV.POLICIES[policy]
    x, y = f(a), f(b)
    m = (len(x) + len(y)) / 2
    return Levenshtein.distance(x, y) / m if m else None


# ------------------------------------------------------------------------------------------------ bundle

def build_bundle(root: Path, dataset: str, page_id: str) -> Path:
    entries = {e.page_id: e for e in read_manifest(root, dataset)}
    e = entries[page_id]
    rr = render_by_id(root, e.render_id)
    rate = gpu_rate(root)
    runs = latest_runs(root, dataset, page_id)
    engines = []
    texts = {}
    for r in runs:
        label, kind = LABELS.get((r["engine"], r["variant"]), (f"{r['engine']} / {r['variant']}", "other"))
        item = dict(run_id=r["run_id"], engine=r["engine"], variant=r["variant"], label=label, kind=kind,
                    imported=bool(r["imported"]), state=r["state"], attempts=r["attempts"],
                    facts=ENGINE_FACTS.get(r["engine"], {}), note=r["note"],
                    health=json.loads(r["health_json"]) if r["health_json"] else None,
                    capabilities=json.loads(r["capabilities_json"]) if r["capabilities_json"] else None,
                    load_s=r["load_s"], run_wall_s=r["wall_s"])
        if r["state"] != "succeeded":
            item["failure"] = dict(kind=r["error_kind"], message=(r["error_message"] or "")[:1000])
            engines.append(item)
            continue
        pred = PagePrediction.model_validate_json(safe_child(root, r["artifact"]).read_text("utf-8"))
        res = pred.result
        txt = EV.prediction_text(pred)
        texts[r["run_id"]] = txt
        inf = res.timing.inference_s
        cost = None
        ses = None if r["imported"] else session_of(root, r["created_at"])
        if ses and inf is not None:
            cost = dict(usd=round(inf / 3600 * ses["dph"], 5), basis=f"inference {inf:.1f} s × ${ses['dph']:.3f}/h "
                        f"({ses['gpu']}, Vast.ai instance {ses['instance']}); excludes setup, download, load")
        item["gpu"] = ses["gpu"] if ses else None
        item.update(
            blocks=[dict(id=b.block_id, type=b.type, raw_label=b.raw_label, box=b.box, order=b.order,
                         text=b.raw_text, flags=b.flags) for b in res.blocks],
            text=txt, lines=candidate_lines(pred), empty=res.empty, truncated=res.truncated,
            repetition=EV.repetition_flag(txt), timing=res.timing.model_dump(), resources=res.resources.model_dump(),
            settings=res.settings_used, cost=cost, has_boxes=any(b.box for b in res.blocks),
            has_text=bool(txt.strip()), raw_artifact=pred.raw_artifact, prediction_file=r["artifact"])
        engines.append(item)
    for it in engines:
        if it.get("lines"):
            others = {k: EV.POLICIES["raw"](v) for k, v in texts.items() if k != it["run_id"]}
            it["elsewhere"] = readings_elsewhere(it["lines"], others)
    dis = []
    ids = [k for k, v in texts.items() if v.strip()]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            ta, tb = texts[ids[i]], texts[ids[j]]
            dis.append(dict(a=ids[i], b=ids[j],
                            # headline: order-free (word bags), so reading order cannot inflate it
                            bag_raw=bag_disagreement(ta, tb, "no_punct"), bag_folded=bag_disagreement(ta, tb, "folded"),
                            # the order-sensitive figures, shown apart as "reading order effect"
                            raw=disagreement(ta, tb, "raw"), folded=disagreement(ta, tb, "folded")))
    # every successful run of each engine on this page, by card (the speed comparison between sessions)
    speed = []
    for r in con_rows(root, dataset, page_id):
        ses = None if r["imported"] else session_of(root, r["created_at"])
        if r["state"] != "succeeded" or r["imported"]:
            continue
        pred = PagePrediction.model_validate_json(safe_child(root, r["artifact"]).read_text("utf-8"))
        res = pred.result
        speed.append(dict(run_id=r["run_id"], engine=r["engine"], variant=r["variant"],
                          label=LABELS.get((r["engine"], r["variant"]), (r["engine"], ""))[0],
                          gpu=ses["gpu"] if ses else None, seconds=res.timing.inference_s,
                          peak_gpu_mem_mb=res.resources.peak_gpu_mem_mb, output_tokens=res.resources.output_tokens,
                          usd=round(res.timing.inference_s / 3600 * ses["dph"], 5) if ses and res.timing.inference_s else None,
                          created_at=r["created_at"], text_sha=hashlib.sha256(EV.prediction_text(pred).encode()).hexdigest()[:12]))
    # superseded failed attempts stay visible (a failure is never hidden by a later success)
    con = connect(root)
    failures = [dict(r) for r in con.execute(
        "SELECT a.run_id, r.engine, r.variant, r.note, a.n, a.started_at, a.error_kind, a.error_message FROM attempts a "
        "JOIN runs r ON r.run_id=a.run_id WHERE a.page_id=? AND r.dataset=? AND a.status IN ('failed','stale') "
        "AND r.is_fixture=0 ORDER BY a.started_at", (page_id, dataset))]
    for f in failures:
        f["label"] = LABELS.get((f["engine"], f["variant"]), (f["engine"], ""))[0]
        f["error_message"] = (f["error_message"] or "")[:600]
    bundle = dict(dataset=dataset, failures=failures, speed=speed, sessions=[
                      {k: v for k, v in x.items() if k not in ("start", "end")} for x in gpu_sessions(root)],
                  page=dict(page_id=page_id, document_id=e.document_id, page_number=e.page_number,
                                             width=rr.width, height=rr.height, render_id=rr.render_id,
                                             render=rr.path, dpi=rr.dpi, renderer=rr.renderer, category=e.category,
                                             native_text=e.native_text.model_dump() if e.native_text else None),
                  engines=engines, disagreements=dis, gpu_rate=rate,
                  disagreement_method="headline: words that differ in any order (1 - F1 of the word multisets, "
                                      "punctuation ignored, and again folded for search); apart: edit distance of "
                                      "the texts in each engine's own order / mean length (the reading order "
                                      "effect). Not error rates: no truth involved")
    # per-page notes written by hand after looking (out/data/reader_notes.json): a default reading, warnings
    notes_f = root / "reader_notes.json"
    notes = (json.loads(notes_f.read_text("utf-8")) if notes_f.exists() else {}).get(page_id, {})
    for it in engines:
        w = notes.get("warnings", {}).get(f"{it['engine']}/{it['variant']}")
        if w:
            it["warning"] = w
    bundle["default_right"] = notes.get("default_right")
    # a display copy of the canonical render (boxes are drawn as fractions of the page, so its size is free)
    import cv2
    img = cv2.imread(str(safe_child(root, rr.path)), cv2.IMREAD_UNCHANGED)
    w = 1400
    small = cv2.resize(img, (w, round(img.shape[0] * w / img.shape[1])), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 90])
    atomic_write(root / "bundles" / dataset / f"{page_id}.jpg", buf.tobytes())
    bundle["page"]["display"] = dict(file=f"{page_id}.jpg", width=w, height=small.shape[0])
    out = root / "bundles" / dataset / f"{page_id}.json"
    atomic_write(out, json.dumps(bundle, ensure_ascii=False, indent=1).encode("utf-8"))
    return out


# ------------------------------------------------------------------------------------------------ scores

def evaluate_page_runs(root: Path, dataset: str, page_id: str, revision: Optional[str] = None) -> dict:
    rev = A.get(root, revision) if revision else A.latest(root, page_id)
    if not rev:
        return dict(available=False, reason="no correction saved for this page yet")
    entries = {e.page_id: e for e in read_manifest(root, dataset)}
    e = entries[page_id]
    rr = render_by_id(root, e.render_id)
    truth = A.to_truth(rev, e.document_id, e.page_number, rr.width, rr.height)
    runs = latest_runs(root, dataset, page_id)
    key = hashlib.sha256(json.dumps([SCORER_VERSION, rev["revision_id"]] + sorted(
        (r["run_id"], _sha(safe_child(root, r["artifact"])) if r["artifact"] else r["state"]) for r in runs)
    ).encode()).hexdigest()[:16]
    out = root / "scores" / dataset / f"{page_id}.{rev['rev_no']}.json"
    if out.exists():
        old = json.loads(out.read_text("utf-8"))
        if old.get("cache_key") == key:
            return old
    con = connect(root)

    def base(run_id):
        x = con.execute("SELECT engine, variant FROM runs WHERE run_id=?", (run_id,)).fetchone() if run_id else None
        return (x[0], x[1].replace("_fast", "").replace("_speedfix", "")) if x else None
    flat = {base(rev.get("started_from")), base(rev.get("layout_from"))} - {None}
    rows = []
    for r in runs:
        label, kind = LABELS.get((r["engine"], r["variant"]), (f"{r['engine']} / {r['variant']}", "other"))
        if r["state"] != "succeeded":
            rows.append(dict(EV.failed_page(page_id, r["run_id"], r["engine"], r["variant"], r["error_message"]),
                             label=label, kind=kind,
                             note="failed page: the whole reference counts as deleted in micro CER/WER"))
            continue
        pred = load_predictions(root, r["run_id"])[page_id]
        ev = EV.evaluate_page(pred, truth)
        ev.update(label=label, kind=kind,
                  flattered=(r["engine"], r["variant"].replace("_fast", "").replace("_speedfix", "")) in flat,
                  micro_raw=EV.micro([ev], {page_id: truth}, "raw"))
        rows.append(ev)
    res = dict(available=True, cache_key=key, revision=rev["revision_id"], rev_no=rev["rev_no"], actor=rev["actor"],
               created_at=rev["created_at"], started_from=rev.get("started_from"), layout_from=rev.get("layout_from"),
               truth_lines=len(truth.lines), truth_regions=len(truth.regions),
               unreadable_lines=sum(1 for ln in rev["body"]["lines"] if ln.get("unreadable")),
               policies=list(EV.POLICIES), primary=EV.PRIMARY, engines=rows,
               note="the engine the correction started from (text or layout) is flattered: its words were the "
                    "default and only changed where the owner saw an error")
    atomic_write(out, json.dumps(res, ensure_ascii=False, indent=1, default=str).encode("utf-8"))
    return res
