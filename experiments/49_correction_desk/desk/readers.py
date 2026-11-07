"""Our own readers (experiments 77, 78, 79; 2026-11-05): the overnight results of the from-scratch Arabic line readers,
read-only, for the /readers page.

    GET /desk/api/readers                 scoreboard, line gallery (~30 held-out lines with every reading), the
                                          "what we learned" examples, spend (GPU and Gemini)
    GET /desk/api/readers/crop/{key}      one held-out line crop (48 px grey JPEG, from experiment 77's test shard)
    GET /desk/api/readers/look/{name}     one picture from the experiments' out/look or out/real (fixed list)

Everything is read from the experiments' out/ folders (gitignored, private) on each change of their files; nothing
is written.  Crops are our scans: served only through the local Desk.  Line keys must be in the test manifest and
picture names in LOOK; no path comes from the request.
"""
from __future__ import annotations

import json
import re
import tarfile
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response

from . import api as A

router = APIRouter()
E = Path(__file__).resolve().parents[2]
X77, X78, X79 = E / "77_scratch_reader" / "out", E / "78_synthetic_lines" / "out", E / "79_signal_reader" / "out"
TAR = X77 / "test" / "test-0-000.tar"
PAGES = X77 / "test" / "pages.json"
PRED77 = X77 / "pred" / "test_v1.jsonl"
PRED78 = X78 / "pred"
SIG = X79 / "host" / "p3t" / "pred_real.jsonl"
FUSE = X79 / "fuse" / "p3t" / "summary.json"
LOOPS = X79 / "res" / "loops_p3t_p3n_p3tp.json"
KEY = re.compile(r"^[0-9][0-9A-Za-z,\-]{3,60}_p\d{3}_l\d{3}$")

LOOK = {  # name -> (file, caption)
    "kashida": (X78 / "look" / "confusions_syn_only.png", "The synthetic-only reader's most frequent error"),
    "judge": (X77 / "look" / "judge_sheet.png", "Where v1 and Azure disagreed, Gemini looked at the line"),
    "loop": (X79 / "real" / "zoomcmp_0718-003-003-002_p006_l023.png", "A filled loop: the pen path round the blob"),
    "signal": (X79 / "real" / "0718-003-003-002_p006_l023.png", "A 1937 line followed as a pen"),
    "synthetic": (X78 / "look" / "syn_v2.png", "Lines we rendered ourselves (v2)"),
}

# the readers on the scoreboard: (id, label, family, source); results78 holds every reader but v2 (results77_v2)
READERS = [
    ("real_only", "Ours: real lines only (v1)", "ours"),
    ("v2", "Ours: Gemini-judged labels (v2)", "ours"),
    ("syn_then_real", "Ours: synthetic, then real", "ours"),
    ("syn2_then_real", "Ours: synthetic v2, then real", "ours"),
    ("syn_then_real10", "Ours: synthetic, then 10% real", "ours"),
    ("real10", "Ours: 10% of the real lines", "ours"),
    ("syn2_only", "Ours: synthetic only (v2)", "ours"),
    ("syn_only", "Ours: synthetic only (v1)", "ours"),
    ("azure", "Azure", "other"),
    ("argon", "Argon (Azure + fixes)", "other"),
    ("nuqta_as_written", "Nuqta", "other"),
]
SETS = [("yardstick", "Your 20 corrected pages", "745 lines, 1937–2006, your October corrections"),
        ("lab_docs12", "Lab documents 1–2", "your rev 1 corrections (Argon: document 2 only)"),
        ("doc3_vs_argon", "Lab document 3", "no correction yet: disagreement with Argon, not errors")]

TATWEEL = "ـ"
_lock = threading.Lock()
_cache: dict = {}


def _jsonl(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _load(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default


def norm(s: str | None) -> str:
    """For deciding 'same reading': NFC, no tatweel, no punctuation, one space (marks and hamza forms still count)."""
    s = unicodedata.normalize("NFC", s or "").replace(TATWEEL, "")
    s = "".join(" " if unicodedata.category(c).startswith("P") or c in "«»*" else c for c in s)
    return " ".join(s.split())


def edits(a: str, b: str) -> list[tuple[str, str]]:
    """Letter substitutions/insertions/deletions turning a into b (Levenshtein backtrace); '' = nothing."""
    n, m = len(a), len(b)
    D = [list(range(m + 1))] + [[i] + [0] * m for i in range(1, n + 1)]
    for i in range(1, n + 1):
        ai, row, prev = a[i - 1], D[i], D[i - 1]
        for j in range(1, m + 1):
            row[j] = min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (ai != b[j - 1]))
    out, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and D[i][j] == D[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            if a[i - 1] != b[j - 1]:
                out.append((a[i - 1], b[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and D[i][j] == D[i - 1][j] + 1:
            out.append((a[i - 1], "")); i -= 1
        else:
            out.append(("", b[j - 1])); j -= 1
    return out[::-1]


def _arabic_share(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    return sum("؀" <= c <= "ۿ" for c in letters) / max(1, len(letters))


def _gallery() -> tuple[list[dict], dict]:
    pages = _load(PAGES, [])
    ours = {r["key"]: r["pred"] for r in _jsonl(PRED77)}
    sig = {r["key"]: r["pred"] for r in _jsonl(SIG)}
    syn1 = {r["key"]: r["pred"] for r in _jsonl(PRED78 / "test_syn_only.jsonl")}
    syn2 = {r["key"]: r["pred"] for r in _jsonl(PRED78 / "test_syn2_only.jsonl")}
    lines, by_key = [], {}
    for p in pages:
        if p["set"] != "yardstick" or not p.get("gold_pos"):
            continue
        gp = {int(k): v for k, v in p["gold_pos"].items()}
        for r in p["lines"]:
            if r["i"] not in gp or r["key"] not in ours:
                continue
            t = p["truth"][gp[r["i"]]]
            d = dict(key=r["key"], page_id=p["page_id"], i=r["i"], decade=p.get("decade"), width=r["cut_info"]["W"],
                     truth=t, ours=ours[r["key"]], azure=r["azure"], signal=sig.get(r["key"]),
                     syn1=syn1.get(r["key"]), syn2=syn2.get(r["key"]))
            nt = norm(t)
            d["ours_ok"], d["azure_ok"] = norm(d["ours"]) == nt, norm(d["azure"]) == nt
            d["signal_ok"] = d["signal"] is not None and norm(d["signal"]) == nt
            by_key[r["key"]] = d
            if len(nt) >= 22 and len(nt.split()) >= 4 and _arabic_share(nt) > 0.9:
                lines.append(d)

    def loops(d: dict, who: str) -> int:
        h = d.get(who)
        if h is None or norm(h) == norm(d["truth"]):
            return 0
        return sum(1 for x, y in edits(norm(d["truth"]), norm(h)) if {x, y} == {"و", "ر"})

    def spread(cands: list[dict], k: int, taken: set) -> list[dict]:
        """k lines, one page at a time (round robin), skipping lines already shown."""
        per: dict[str, list[dict]] = {}
        for d in cands:
            if d["key"] not in taken:
                per.setdefault(d["page_id"], []).append(d)
        out, queues = [], list(per.values())
        while len(out) < k and any(queues):
            for q in queues:
                if q and len(out) < k:
                    out.append(q.pop(0))
        taken.update(d["key"] for d in out)
        return out

    taken: set = set()
    pick: list[tuple[str, list[dict]]] = []
    pick.append(("ours_beat_azure", spread([d for d in lines if d["ours_ok"] and not d["azure_ok"]], 8, taken)))
    pick.append(("azure_beat_ours", spread([d for d in lines if d["azure_ok"] and not d["ours_ok"]], 8, taken)))
    old = [d for d in lines if d["decade"] in ("pre-1960", "1960s")]
    old.sort(key=lambda d: (d["ours_ok"] and d["azure_ok"], d["page_id"], d["i"]))   # disagreements first
    pick.append(("old_print", spread(old, 7, taken)))
    lp = [(loops(d, "ours") + loops(d, "azure"), loops(d, "signal"), d) for d in lines]
    lp = [x for x in lp if x[0] or x[1]]
    lp.sort(key=lambda x: (-x[0], -x[1], x[2]["page_id"], x[2]["i"]))
    pick.append(("loops", spread([x[2] for x in lp], 7, taken)))
    out = []
    for cat, ds in pick:
        for d in ds:
            out.append({**{k: v for k, v in d.items() if k not in ("syn1", "syn2")}, "group": cat,
                        "loops": dict(ours=loops(d, "ours"), azure=loops(d, "azure"), signal=loops(d, "signal"))})
    return out, by_key


def _scoreboard() -> dict:
    r78 = (_load(X78 / "results78.json", {}) or {}).get("sets", {})
    r77 = (_load(X77 / "results77_v2.json", {}) or {}).get("sets", {})
    rows = []
    for rid, label, fam in READERS:
        vals = {}
        for s, _, _ in SETS:
            src = r77 if rid == "v2" else r78
            v = src.get(s, {}).get(rid)
            vals[s] = None if v is None else dict(letters=v["letters"], words=v["words"],
                                                  letters_punct=v.get("letters_punct"), pages=v.get("pages"))
        if any(vals.values()):
            rows.append(dict(id=rid, label=label, family=fam, sets=vals))
    le = {**(_load(X77 / "results77_v1.json", {}) or {}).get("line_exact", {})}
    return dict(sets=[dict(id=s, label=l, note=n) for s, l, n in SETS], rows=rows,
                line_exact={k: v.get("no_punct_pct") for k, v in le.items()})


def _spend() -> dict:
    now = datetime.now(timezone.utc)
    exps = []
    for name, folder, cap in [("77", X77, 20.0), ("78", X78, 20.0), ("79", X79, 20.0)]:
        inst: dict[int, dict] = {}
        for r in (x for x in _jsonl(folder / "gpu" / "gpu_spend.jsonl") if x.get("instance")):
            i = inst.setdefault(r["instance"], dict(instance=r["instance"], usd=0.0, minutes=0.0, ended=False))
            if r["event"] == "start":
                i.update(gpu=r.get("gpu"), started=r["time"], dph=r.get("dph"))
            if "usd" in r:
                i["usd"] = max(i["usd"], r["usd"])
                i["minutes"] = max(i["minutes"], r.get("minutes") or 0)
            if r["event"] == "end":
                i["ended"], i["end_reason"] = True, r.get("reason")
            i["last"] = r["time"]
        for i in inst.values():
            age = (now - datetime.fromisoformat(i["last"])).total_seconds() / 60 if i.get("last") else 1e9
            i["running"] = not i["ended"] and age < 15
            i["usd"] = round(i["usd"], 2)
        exps.append(dict(exp=name, cap=cap, usd=round(sum(i["usd"] for i in inst.values()), 2),
                         instances=sorted(inst.values(), key=lambda i: i.get("started") or "")))
    j = _jsonl(X77 / "judge" / "spend.jsonl")
    ans = _jsonl(X77 / "judge" / "answers.jsonl")
    gem = dict(usd=round(sum(r.get("usd") or 0 for r in j), 2), calls=len(j), answers=len(ans), cap=20.0,
               model="gemini-3.8-flash (thinking low)", extra_cap_unused=40.0,
               first=j[0]["when"] if j else None, last=j[-1]["when"] if j else None)
    return dict(gpu=exps, gemini=gem, at=now.isoformat(timespec="seconds"))


def _example(by_key: dict, key: str, extra: dict | None = None) -> dict | None:
    d = by_key.get(key)
    if not d:
        return None
    return dict(key=key, truth=d["truth"], ours=d["ours"], azure=d["azure"], signal=d["signal"], width=d["width"],
                decade=d["decade"], **(extra or {}))


def _learned(by_key: dict) -> dict:
    fuse = _load(FUSE, {}) or {}
    loops = _load(LOOPS, {}) or {}
    k = by_key.get("0005-055-003-004_p008_l004")
    kash = _example(by_key, "0005-055-003-004_p008_l004",
                    dict(syn1=k and k["syn1"], syn2=k and k["syn2"])) if k else None
    return dict(
        kashida=kash,
        quotes=[x for x in (_example(by_key, "0382-016-063-013_p003_l006"),
                            _example(by_key, "0382-016-063-013_p003_l011")) if x],
        fuse=dict(all=fuse.get("all"), era=fuse.get("era"), warning=fuse.get("warning")),
        waw={m: dict(n=v["n"], err=v["err"], top=v["top"][:3]) for m in ("p3t", "p3n")
             if (v := (loops.get(m) or {}).get("real", {}).get("و"))},
        looks={k2: dict(caption=c, available=f.is_file()) for k2, (f, c) in LOOK.items()},
    )


def _stamp() -> tuple:
    files = [PAGES, PRED77, SIG, FUSE, X78 / "results78.json", X77 / "results77_v2.json", X77 / "results77_v1.json",
             X77 / "gpu" / "gpu_spend.jsonl", X78 / "gpu" / "gpu_spend.jsonl", X79 / "gpu" / "gpu_spend.jsonl",
             X77 / "judge" / "spend.jsonl"]
    return tuple(f.stat().st_mtime if f.is_file() else 0 for f in files)


def _bundle() -> dict:
    with _lock:
        st = _stamp()
        if _cache.get("stamp") != st:
            gallery, by_key = _gallery()
            _cache.update(stamp=st, by_key=by_key, data=dict(
                scoreboard=_scoreboard(), gallery=gallery, learned=_learned(by_key), spend=_spend()))
        return _cache["data"]


@router.get(A.P + "/readers")
def readers(actor: dict = Depends(A.me)):
    d = dict(_bundle())
    d["spend"] = _spend()        # live: a GPU session may still be running
    return d


_tar_index: dict = {}


@router.get(A.P + "/readers/crop/{key}")
def readers_crop(key: str, actor: dict = Depends(A.me)):
    if not KEY.fullmatch(key) or not TAR.is_file():
        raise HTTPException(404, "no such line")
    with _lock:
        st = TAR.stat().st_mtime
        if _tar_index.get("stamp") != st:
            with tarfile.open(TAR) as t:
                _tar_index.clear()
                _tar_index.update(stamp=st, members={m.name: (m.offset_data, m.size) for m in t.getmembers()
                                                     if m.isfile() and m.name.endswith(".jpg")})
        hit = _tar_index["members"].get(f"{key}.jpg")
    if not hit:
        raise HTTPException(404, "no such line")
    with open(TAR, "rb") as f:
        f.seek(hit[0])
        data = f.read(hit[1])
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.get(A.P + "/readers/look/{name}")
def readers_look(name: str, actor: dict = Depends(A.me)):
    if name not in LOOK or not LOOK[name][0].is_file():
        raise HTTPException(404, "no such picture")
    return FileResponse(str(LOOK[name][0]), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})

