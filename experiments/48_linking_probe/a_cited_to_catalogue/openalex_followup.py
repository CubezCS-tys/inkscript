"""Probe A follow-up (2026-10-21, run by the orchestrating session with the owner's explicit OK to use the key).

The two OpenAlex questions probe A could not answer after the anonymous budget ran out:
  F1. Does OpenAlex know Arabic-language scholarship? The same 20 Arabic-script article citations and 20 Arabic
      book/thesis citations that probe A sent to Crossref (seed 4802), now sent to OpenAlex.
  F2. OpenAlex sources for cited journals (the OpenAlex side of A3): the most-cited journal entities, Latin and
      Arabic script, searched in /sources.

The key is read from ~/.config/inkscript/openalex.env at run time and appended to the request only; ext.get logs and
caches the URL without it. Every result row carries source "openalex".
"""
import json, os, random, sys

import ext
from a2 import (OUT, best_openalex, surnames, tsim)
from match import cited_years, title_fields
from ext import openalex_search, openalex_sources, openalex_works, n_requests


def _key():
    line = open(os.path.expanduser("~/.config/inkscript/openalex.env")).read().strip()
    return line.split("=", 1)[1]


ext._openalex_key = _key          # owner's OK, 2026-10-21
ext.DISABLED.clear()
RES = OUT + "openalex_followup.jsonl"
BUDGET = n_requests() + 400       # this follow-up: at most 400 new requests


def done_keys():
    try:
        return {json.loads(l)["job"] for l in open(RES, encoding="utf-8")}
    except FileNotFoundError:
        return set()


def write(row):
    with open(RES, "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(row, source="openalex"), ensure_ascii=False) + "\n")


def f1(done):
    W = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")}
    C = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "classified.jsonl", encoding="utf-8")}
    pks = sorted(W)
    rng = random.Random(4802)     # the same draws as a2.main (same order of rng calls)
    lat_art = [k for k in pks if C[k]["lang"] == "lat" and C[k]["cls"] == "journal_article"]
    lat_book = [k for k in pks if C[k]["lang"] == "lat" and C[k]["cls"] == "book"]
    ara_art = [k for k in pks if C[k]["lang"] == "ara" and C[k]["cls"] == "journal_article"]
    ara_book = [k for k in pks if C[k]["lang"] == "ara" and C[k]["cls"] in ("book", "thesis")]
    rng.sample(lat_art, min(500, len(lat_art)))
    rng.sample(lat_book, 300)
    aa = rng.sample(ara_art, 20)
    ab = rng.sample(ara_book, 20)
    for group, ks in (("ara_article", aa), ("ara_book", ab)):
        for k in ks:
            job = f"F1|{k}"
            if job in done:
                continue
            w = W[k]
            ct, csrc, p, rep = title_fields(w)
            if not ct:
                continue
            sn, years = surnames(w, p), cited_years(w, p)
            res = openalex_works(ct, f"A follow-up F1 {group}: title of cited work {w['cited_work_id']}")
            hits = best_openalex(res, ct, csrc, sn, years)
            if not hits and res.get("status") == 200:
                res = openalex_search(ct, f"A follow-up F1 {group}: free search, cited work {w['cited_work_id']}")
                hits = best_openalex(res, ct, csrc, sn, years)
            n_results = len((res.get("body") or {}).get("results") or [])
            write(dict(job=job, part="F1", group=group, cited_work_pk=k, cited_work_id=w["cited_work_id"],
                       printed=(rep or {}).get("printed"), title=ct, container=csrc, status=res.get("status"),
                       n_results=n_results, hits=hits))


def f2(done):
    E = json.load(open(OUT + "a3_entities.json", encoding="utf-8"))["entities"]
    lat = sorted([e for e in E if e["script"] == "lat"], key=lambda e: -e["n_cites"])[:120]
    ara = sorted([e for e in E if e["script"] != "lat"], key=lambda e: -e["n_cites"])[:60]
    for e in lat + ara:
        job = f"F2|{e['entity']}"
        if job in done:
            continue
        name = max(e["strings"], key=len)
        res = openalex_sources(name, f"A follow-up F2: journal named in citations ({e['script']}, {e['n_cites']} cites)")
        body = res.get("body") or {}
        hits = []
        for h in (body.get("results") or [])[:3]:
            names = [h.get("display_name") or ""] + (h.get("alternate_titles") or []) + (h.get("abbreviated_title") and [h["abbreviated_title"]] or [])
            hits.append(dict(id=h.get("id"), display_name=h.get("display_name"), issn_l=h.get("issn_l"),
                             country=h.get("country_code"), host=h.get("host_organization_name"),
                             works_count=h.get("works_count"), sim=round(max(tsim(name, x) for x in names if x), 3)))
        write(dict(job=job, part="F2", script=e["script"], entity=e["entity"], name=name, n_cites=e["n_cites"],
                   catalogue=e.get("journal_code"), status=res.get("status"), hits=hits))


def main():
    done = done_keys()
    f1(done)
    f2(done)
    print("done;", n_requests(), "requests in the log; budget for this run ends at", BUDGET)


if __name__ == "__main__":
    main()
