"""Polite, logged, cached HTTP for OpenAlex and Crossref (brief: every request logged, ≤5/s OpenAlex, ≤2/s Crossref,
User-Agent inkscript-probe/0.1, no e-mail, only titles / authors / citation strings sent)."""
import hashlib, json, os, time, urllib.request, urllib.parse, urllib.error

OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
CACHE = OUT + "http_cache/"
LOG = OUT + "external_calls.jsonl"
UA = "inkscript-probe/0.1"
MIN_GAP = {"openalex": 0.25, "crossref": 1.1}
_last = {"openalex": 0.0, "crossref": 0.0}
os.makedirs(CACHE, exist_ok=True)


def _openalex_key():
    """Not used: reading the owner's key was refused by the permission system on 2026-10-21."""
    return None


def n_requests(source=None, since=None):
    try:
        if source is None:
            return sum(1 for _ in open(LOG, encoding="utf-8"))
        n = 0
        for l in open(LOG, encoding="utf-8"):
            d = json.loads(l)
            if d["source"] == source and (since is None or d["time"] >= since):
                n += 1
        return n
    except FileNotFoundError:
        return 0


DISABLED = set()   # a source whose daily anonymous budget is spent (OpenAlex answers 429 "Insufficient budget")


def get(source: str, url: str, purpose: str, budget: int = 3000):
    key = hashlib.sha1(url.encode()).hexdigest()
    path = CACHE + key + ".json"
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    if source in DISABLED:
        return dict(source=source, url=url, status="skipped: budget spent", body=None)
    if n_requests() >= budget:
        raise RuntimeError("request budget reached")
    gap = time.time() - _last[source]
    if gap < MIN_GAP[source]:
        time.sleep(MIN_GAP[source] - gap)
    status, body, err = None, None, None
    for attempt in range(3):
        t = time.time()
        _last[source] = t
        try:
            real = url
            if source == "openalex" and _openalex_key():
                real = url + "&" + urllib.parse.urlencode({"api_key": _openalex_key()})
            req = urllib.request.Request(real, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                status = r.status
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            status, err = e.code, str(e)
            try:
                err += " " + e.read().decode("utf-8", "ignore")[:300]
                k = _openalex_key()
                if k:
                    err = err.replace(k, "<key>")
            except Exception:
                pass
        except Exception as e:  # network
            status, err = -1, repr(e)
            k = _openalex_key()
            if k:
                err = err.replace(k, "<key>")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(time=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + "Z", source=source,
                                    url=url, status=status, purpose=purpose, error=err), ensure_ascii=False) + "\n")
        if status == 200:
            break
        if status == 429 and "budget" in (err or ""):
            DISABLED.add(source)
            break
        if status in (429, 500, 502, 503, 504, -1):
            time.sleep(2 + 3 * attempt)
            continue
        break
    res = dict(source=source, url=url, status=status, body=body)
    if status == 200 or status == 404:
        json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return res


def openalex_works(title: str, purpose: str):
    t = title.replace(",", " ").replace(":", " ").replace("|", " ")
    q = urllib.parse.urlencode({"filter": "title.search:" + " ".join(t.split())[:300], "per-page": "5",
                                "select": "id,doi,display_name,publication_year,authorships,primary_location,language,type"})
    return get("openalex", "https://api.openalex.org/works?" + q, purpose)


def openalex_search(text: str, purpose: str):
    q = urllib.parse.urlencode({"search": " ".join(text.split())[:300], "per-page": "5",
                                "select": "id,doi,display_name,publication_year,authorships,primary_location,language,type"})
    return get("openalex", "https://api.openalex.org/works?" + q, purpose)


def openalex_sources(name: str, purpose: str):
    q = urllib.parse.urlencode({"search": " ".join(name.split())[:200], "per-page": "5",
                                "select": "id,display_name,issn_l,issn,alternate_titles,abbreviated_title,country_code,type,works_count"})
    return get("openalex", "https://api.openalex.org/sources?" + q, purpose)


def crossref(bib: str, purpose: str):
    q = urllib.parse.urlencode({"query.bibliographic": " ".join(bib.split())[:400], "rows": "3",
                                "select": "DOI,title,author,issued,container-title,score,type,short-container-title"})
    return get("crossref", "https://api.crossref.org/works?" + q, purpose)


def crossref_journals(name: str, purpose: str):
    q = urllib.parse.urlencode({"query": " ".join(name.split())[:200], "rows": "3"})
    return get("crossref", "https://api.crossref.org/journals?" + q, purpose)
