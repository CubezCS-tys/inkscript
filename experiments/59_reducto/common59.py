"""Experiment 59: the one place that talks to Reducto.  Every call is logged to out/calls.jsonl (never the key).

Guards (owner's rules, 2026-10-30):
  * only files listed in out/approved_pages.json (written by units59.py, at most 60 page ids) may be uploaded;
    every upload is written to out/sent_pages.jsonl first; a 61st distinct page is refused;
  * public sample URLs (cdn.reducto.ai/samples/...) may be parsed for smoke tests (no Mandumah data);
  * a call stops the run if the response carries a usage shape that is not covered by the free credits
    (we cannot see the balance; we price each response's usage at list price and stop at USD_CAP).
The API key is read from /home/appuser/inkscript/.env (REDUCTO_API_KEY) and only ever put in the Authorization header.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
BASE = "https://platform.reducto.ai"
CALLS = OUT / "calls.jsonl"
SENT = OUT / "sent_pages.jsonl"
APPROVED = OUT / "approved_pages.json"
MAX_PAGES = 60
USD_CAP = 20.0             # list-price dollars; the 15,000 free credits are ~$225 at $0.015 a credit: stop far below
_KEY = dotenv_values(E.parent / ".env").get("REDUCTO_API_KEY") or os.environ.get("REDUCTO_API_KEY")


def _h():
    if not _KEY:
        raise SystemExit("REDUCTO_API_KEY missing")
    return {"Authorization": f"Bearer {_KEY}"}


def _log(rec):
    rec["t"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(CALLS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# list prices from docs.reducto.ai/reference/credit-usage (effective 2026-09-01), $ per page
PRICE = dict(r1=0.010, legacy_credit=0.015, ocr=0.002, prompted=0.005, extract=0.020, deep_extract=0.040,
             chart=0.06)


def usd_of(u):
    """list-price dollars of one response's usage (per-product account: usage_breakdown; credit account: credits)"""
    if not u:
        return 0.0
    if isinstance(u.get("credits"), (int, float)):
        return u["credits"] * PRICE["legacy_credit"]
    b = u.get("usage_breakdown") or {}
    usd = 0.0
    if "parse_pages" in b:
        usd += (b.get("parse_pages") or 0) * PRICE["r1"] * (1 if (b.get("parse_model") or "").upper() == "R-1" else 0)
        usd += (b.get("legacy_parse_credits") or 0) * PRICE["legacy_credit"]
    if "extract_pages" in b:
        deep = "deep" in str(b.get("extract_model") or "").lower()
        usd += (b.get("extract_pages") or 0) * PRICE["deep_extract" if deep else "extract"]
    usd += (b.get("ocr_pages") or 0) * PRICE["ocr"] + (b.get("prompted_blocks") or 0) * PRICE["prompted"]
    usd += (b.get("charts") or 0) * PRICE["chart"]
    return usd


def credits_used():
    """list-price dollars so far"""
    tot = 0.0
    if CALLS.exists():
        for ln in CALLS.read_text().splitlines():
            tot += usd_of(json.loads(ln).get("usage"))
    return tot


def sent_ids():
    if not SENT.exists():
        return set()
    return {json.loads(l)["id"] for l in SENT.read_text().splitlines() if l.strip()}


def _usage(j):
    u = j.get("usage") if isinstance(j, dict) else None
    return u if isinstance(u, dict) else None


def call(method, path, *, tag, page_id=None, **kw):
    if credits_used() > USD_CAP:
        raise SystemExit(f"cap ${USD_CAP} (list price) reached: stop")
    t0 = time.time()
    r = requests.request(method, BASE + path, headers=_h(), timeout=kw.pop("timeout", 900), **kw)
    dt = time.time() - t0
    try:
        j = r.json()
    except Exception:
        j = {"_text": r.text[:500]}
    u = _usage(j)
    rec = dict(tag=tag, method=method, path=path, page=page_id, status=r.status_code, seconds=round(dt, 2),
               usage=u, usd_list=round(usd_of(u), 4), job_id=j.get("job_id") if isinstance(j, dict) else None,
               duration=j.get("duration") if isinstance(j, dict) else None)
    if r.status_code >= 400:
        rec["error"] = json.dumps(j, ensure_ascii=False)[:600]
    _log(rec)
    return r.status_code, j


def upload(path: Path, page_id: str):
    approved = set(json.loads(APPROVED.read_text())) if APPROVED.exists() else set()
    if page_id not in approved:
        raise SystemExit(f"{page_id} is not an approved page")
    s = sent_ids()
    if page_id not in s and len(s) >= MAX_PAGES:
        raise SystemExit("page budget reached")
    if page_id not in s:
        with open(SENT, "a") as f:
            f.write(json.dumps(dict(id=page_id, file=str(path), bytes=path.stat().st_size,
                                    t=time.strftime("%Y-%m-%dT%H:%M:%S"))) + "\n")
    with open(path, "rb") as fh:
        st, j = call("POST", "/upload", tag="upload", page_id=page_id, files={"file": (path.name, fh)})
    if st != 200:
        raise RuntimeError(f"upload {page_id}: {st} {j}")
    return j["file_id"]


def delete_upload(file_id, page_id=None):
    return call("DELETE", f"/upload/{file_id}", tag="delete_upload", page_id=page_id)


def delete_job(job_id, page_id=None):
    return call("DELETE", f"/job/{job_id}", tag="delete_job", page_id=page_id)


def parse(inp, body, *, tag, page_id=None):
    b = dict(body)
    b["input"] = inp
    b.setdefault("settings", {})["persist_results"] = False
    return call("POST", "/parse", tag=tag, page_id=page_id, json=b)


def extract(inp, body, *, tag, page_id=None):
    b = dict(body)
    b["input"] = inp
    b.setdefault("settings", {})
    return call("POST", "/extract", tag=tag, page_id=page_id, json=b)


def fetch_result(j):
    """inline chunks or the URL result"""
    res = j.get("result") or {}
    if isinstance(res, dict) and res.get("type") == "url":
        return requests.get(res["url"], timeout=120).json()
    if isinstance(res, dict):
        return res.get("chunks")
    return res
