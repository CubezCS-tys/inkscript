"""A polite, logged, cached OpenAlex client for probe C (C2 only). Every request is appended to
out/c_people_and_institutions/external_calls.jsonl (time, URL, status, purpose); responses are cached on disk; at most
2 requests a second; the API key is added to the request only; User-Agent inkscript-probe/0.1; no e-mail address is sent; only institution names are sent."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from common48c import OUT

LOG = OUT / "external_calls.jsonl"
CACHE = OUT / "openalex_cache"
CACHE.mkdir(exist_ok=True)
_last = [0.0]


def _key() -> str | None:
    """The owner's API key, read at run time; it is only ever put in the request, never in a log, cache or file."""
    p = Path.home() / ".config" / "inkscript" / "openalex.env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("OPENALEX_API_KEY="):
                return line.split("=", 1)[1].strip() or None
    return None


def get(path: str, params: dict, purpose: str) -> dict | None:
    url = "https://api.openalex.org/" + path + "?" + urllib.parse.urlencode(params)   # logged/cached form: no key
    h = hashlib.sha1(url.encode()).hexdigest()[:20]
    cp = CACHE / f"{h}.json"
    if cp.exists():
        with open(LOG, "a") as f:
            f.write(json.dumps(dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), url=url, status="cache", purpose=purpose,
                                    source="openalex"), ensure_ascii=False) + "\n")
        return json.loads(cp.read_text())
    wait = 0.5 - (time.time() - _last[0])          # at most 2 requests a second
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    k = _key()
    req_url = url + ("&" + urllib.parse.urlencode({"api_key": k}) if k else "")
    req = urllib.request.Request(req_url, headers={"User-Agent": "inkscript-probe/0.1"})
    status, data, err = None, None, None
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            err = e.read().decode()[:300]
            if k:
                err = err.replace(k, "***")
        except Exception:
            pass
    except Exception as e:  # network error
        status = f"error: {type(e).__name__}"
    with open(LOG, "a") as f:
        f.write(json.dumps(dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), url=url, status=status, purpose=purpose,
                                source="openalex", error=err), ensure_ascii=False) + "\n")
    if data is not None:
        cp.write_text(json.dumps(data, ensure_ascii=False))
    return data
