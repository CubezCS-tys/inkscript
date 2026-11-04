"""Headline numbers, from ONE place (experiment 73, 2026-11-03): `GET /desk/api/headlines`.

The Index home, the Story page, the deck and the gate pages quote the same quantities; before this route each page
carried its own copy and they disagreed (experiment 73's audit, section 3). Every value here is computed live from the
release the Desk reads (the index numbers, gate 1, the journals read whole, the cross-citations between them) or read
from the measured output of the experiment that owns it (gate 2's pair: experiment 70's measure70.py run live on the release; its cost and page check: its README and look10_verdicts.json; the audit:
the folder /home/appuser/data/desk/audit_current points at; the proof pack: experiment 43's out/proof; the production
librarian: experiment 71's simulate71.json; the librarian's before/after: experiments 64, 67 and 68). Nothing is typed
in by hand except the price date. A value that cannot be found is None (the pages show "—"); every value has a short
`def` in `defs`, and `sources` names the file each block came from.

Cached per release (keyed by the release file's path and mtime) and by the mtimes of the experiment files.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends

from . import index_pages as X
from .pages import open_ro

router = APIRouter()
_cache: dict = {}            # one entry: (release path, its mtime, the experiment files' mtimes) -> the headlines

EXP = Path(__file__).resolve().parents[2]                 # experiments/
GATE2_DIR = EXP / "70_gate2_pilot"
PROOF_DIR = EXP / "43_rehearsal" / "out" / "proof"
LIB71 = EXP / "71_librarian_models" / "out" / "simulate71.json"
LIB64 = EXP / "64_apply_institutions" / "out" / "numbers64.json"
LIB67 = EXP / "67_apply_works" / "out" / "numbers67.json"
GOLIVE68 = EXP / "68_go_live" / "README.md"
GATE2_PAIR = ("J0130", "J0165")
PRICE_DOUBLES = "2026-12-01"          # Gemini 4 Argon's price doubles (experiment 70 README, 'Prices double on 1 December')
PRODUCTION_LIBRARIAN = "Flash strong kinds -> Opus high"   # experiment 71's chosen design

COUNTRIES = dict(EG="Egypt", SA="Saudi Arabia", MA="Morocco", DZ="Algeria", IQ="Iraq", JO="Jordan", BH="Bahrain",
                 LY="Libya", KW="Kuwait", SD="Sudan", OM="Oman", AE="United Arab Emirates", QA="Qatar", TN="Tunisia",
                 SY="Syria", LB="Lebanon", PS="Palestine", YE="Yemen", MR="Mauritania", SO="Somalia", DJ="Djibouti",
                 KM="Comoros", TR="Turkey", IR="Iran", US="United States", GB="United Kingdom", FR="France",
                 DE="Germany", MY="Malaysia", PK="Pakistan", IN="India", ID="Indonesia", NG="Nigeria", CA="Canada",
                 AU="Australia", ES="Spain", IT="Italy", NL="Netherlands", BE="Belgium", CH="Switzerland",
                 SE="Sweden", RU="Russia", CN="China", JP="Japan", KR="South Korea", BR="Brazil", ZA="South Africa")

DEFS = dict(
    release="The Desk release these numbers are read from (the newest release copy).",
    articles=X.DEFS["articles"] + " Includes the articles built from the publisher's Word file (no scan).",
    pages=X.DEFS["pages"],
    words=X.DEFS["words"],
    references=X.DEFS["references"],
    journals_read_whole="Journals of which every research article of 2010-2025 Mandumah holds has been read "
                        "(not a random sample): gate 1's journal and gate 2's pilot journal.",
    institutions=X.DEFS["institutions"],
    institutions_with_country_pct="Share of those institutions whose country is recorded.",
    cited_works=X.DEFS["cited_works"],
    cited_by_2plus="Cited works that two or more of the articles read cite.",
    held_pct=X.DEFS["held"],
    audit_pct="Share of the printed lines of the scanned articles that end up in the article file (a field, a "
              "paragraph, a reference, a note): nothing lost. Measured line by line on every scanned article of the "
              "release (the audit of experiments 61/68).",
    words_wrong="Words checked one by one against the scan on pages drawn at random from articles the pipeline "
                "had never seen (the proof pack, an independent check): words wrong, of words checked.",
    gate1="Gate 1: one journal (0130) read whole against random articles of the same size (the mean of 20 random "
          "sets of 126). Each pair is [the journal, random sets of the same size].",
    gate1_authors_2plus="Authors who signed two or more articles of the set.",
    gate1_institutions_2plus="Institutions seen in two or more articles of the set.",
    gate1_shared_works="Cited works that two or more articles of the set cite.",
    gate2="Gate 2's pilot: the second education journal (0165) read whole, and the two journals measured as a pair "
          "against random sets of the same sizes (20 seeded sets from the random 600), measured on the current release "
          "with experiment 70's code, so the numbers move together when the release changes.",
    gate2_cites="References from one journal's articles that land on a publication of the other journal.",
    gate2_shared_authors="Persons who signed articles in both journals, [the pair, random sets of the same sizes].",
    gate2_shared_works="Cited works cited by articles of both journals, [the pair, random sets].",
    gate2_shared_institutions="Institutions seen in both journals, [the pair, random sets]: no more than chance.",
    gate2_coupled_pairs="Article pairs, one from each journal, that cite a common work, [the pair, random sets].",
    gate2_cost="What the pilot cost in model calls (scan route + Word route).",
    gate2_ten="The ten journals of gate 2 at the pilot's measured rates (per scan page, per Word article).",
    librarian="The AI librarian decides whether two records are the same institution or the same cited work. "
              "Production design: a cheap model answers the kinds it is reliable on, a strong model the rest, the "
              "unsure go to a person.",
    librarian_precision="Share of the librarian's applied decisions that are right, on a gold set checked by hand.",
    librarian_cost="Model cost per 1,000 decisions.",
    librarian_to_person="Share of decisions left to a person.",
    librarian_institutions="Institutions on the first 780 articles: [before the librarian, after].",
    librarian_cited_works="Cited-work cards on the first 780 articles: [before the librarian, after].",
    costs="Model cost per unit, measured on gate 2's pilot.",
    per_scan_page_usd="Model cost to read one scanned page.",
    per_word_article_usd="Model cost to build one article from the publisher's Word file.",
    price_doubles="The day the reading model's price doubles.",
)


def _mt(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def _num(s: str | None):
    if s is None:
        return None
    s = s.replace(",", "")
    try:
        return int(s) if re.fullmatch(r"-?\d+", s) else float(s)
    except ValueError:
        return None


def _audit_dir() -> Path:
    from .audit import audit_dir
    return audit_dir()


def _index_numbers(path: Path) -> dict:
    ov = X.overview(path)
    return {n["key"]: n for n in ov["numbers"]}


def _whole_journals(path: Path) -> list[dict]:
    B = X._base(path)
    con = open_ro(path)
    try:
        cc = dict(con.execute("SELECT journal_id, country_code FROM journals").fetchall())
    finally:
        con.close()
    out = []
    for j in sorted(X.WHOLE_JOURNALS):
        read = [x for x in B["pubs"].values() if x["stem"] and x["journal_id"] == j]
        word = sum(1 for x in read if (x["run"] or "").startswith("w"))
        years = [x["year_shown"] for x in read if x["year_shown"]]
        code = cc.get(j)
        out.append(dict(id=j, title=B["jname"].get(j), title_en=B["jen"].get(j), articles=len(read),
                        scan=len(read) - word, word=word, first=min(years) if years else None,
                        last=max(years) if years else None, country=COUNTRIES.get(code or "", code),
                        country_code=code, gate="gate 1" if j == X.GATE1_JOURNAL else "gate 2 pilot"))
    return out


def _institutions_country_pct(path: Path):
    B = X._base(path)
    read = {p for p, x in B["pubs"].items() if x["stem"]}
    orgs = {a["inst_id"] for a in X._org_affs(B, read).values()}
    if not orgs:
        return None
    return round(100 * sum(1 for i in orgs if (B["inst"].get(i) or {}).get("country_code")) / len(orgs), 1)


def _gate1(path: Path) -> dict | None:
    try:
        g = X.gate1(path)
    except Exception:          # experiment 52's measure missing on this machine
        return None
    rows = {r["key"]: r for r in g["rows"]}

    def pair(k):
        r = rows.get(k)
        if not r:
            return None
        j = r["journal"]["n"] if isinstance(r["journal"], dict) else r["journal"]
        s = r.get("random_same_size")
        return [j, round(s, 2) if isinstance(s, float) else s]
    return dict(journal=g["journal_id"], title=g.get("journal"), articles=g["n_journal"], random_articles=g["n_random"],
                authors_2plus=pair("authors2"), institutions_2plus=pair("insts2"), shared_works=pair("shared"))


def _gate2_live(path: Path) -> dict:
    """Gate 2's pair measured NOW on the release the Desk reads, with experiment 70's own code (measure70.base / cross /
    shared, imported read-only) and its baseline: J against 20 random sets of K's size from the random 600, seed 7070.
    So every gate-2 number moves together when a new release lands (experiment 72's librarian, the next journals)."""
    import random
    import sys
    from collections import defaultdict
    for d in (GATE2_DIR, EXP / "52_journal_gate1"):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
    import measure70 as M  # noqa: E402  (experiment 70's measure, unchanged)
    a, b = GATE2_PAIR
    B = M.base(str(path))
    cur = B["cur"].values()
    J = {v["pub_id"] for v in cur if v["journal_id"] == a}
    K = {v["pub_id"] for v in cur if v["journal_id"] == b}
    Ks = {v["pub_id"] for v in cur if v["journal_id"] == b and v["has_azure_json"]}
    Rr = {v["pub_id"] for v in cur if v["run"] in M.R_RUNS and v["journal_id"] not in GATE2_PAIR}
    jk, kj = M.cross(B, J, K, b, M.NAME_K), M.cross(B, K, J, a, M.NAME_J)
    sh = M.shared(B, J, K)
    rnd, rl = random.Random(7070), sorted(Rr)
    rows = defaultdict(list)
    for _ in range(20):                      # the same draws as measure70.main (it also draws a J-sized set each time)
        S = set(rnd.sample(rl, min(len(K), len(rl))))
        for k, v in M.shared(B, J, S).items():
            rows[k].append(v)
        rnd.sample(rl, min(len(J), len(rl)))
    mean = {k: round(sum(v) / len(v), 2) for k, v in rows.items()}
    return dict(sets=dict(J=len(J), K=len(K), K_scan=len(Ks), K_word=len(K - Ks), R=len(Rr)),
                J_to_K=jk.get("to_journal", 0), K_to_J=kj.get("to_journal", 0), shared=sh, baseline=mean,
                ranges={k: [min(v), max(v)] for k, v in rows.items()})


def _gate2(path: Path, release_id: str | None) -> dict | None:
    readme = _text(GATE2_DIR / "README.md")
    a, b = GATE2_PAIR
    out = dict(pair=[a, b])
    try:
        L = _gate2_live(path)
    except Exception as e:                   # experiment 70's code missing on this machine: no numbers, never stale ones
        out["error"] = f"gate 2 not measured: {type(e).__name__}"
        L = None
    if L:
        sh, base = L["shared"], L["baseline"]
        out.update(cites_a_to_b=L["J_to_K"], cites_b_to_a=L["K_to_J"],
                   shared_authors=[sh["authors"], base.get("authors")],
                   shared_works=[sh["cited_works"], base.get("cited_works")],
                   shared_institutions=[sh["institutions"], base.get("institutions")],
                   coupled_pairs=[sh["coupling_edges"], round(base["coupling_edges"]) if base.get("coupling_edges") is not None else None],
                   random_ranges=L["ranges"], measured_on=release_id or path.stem,
                   articles=L["sets"]["K"], scan=L["sets"]["K_scan"], word=L["sets"]["K_word"])
    t = re.search(r"\*\*total\*\*\s*\|\s*\*\*([0-9.]+)\*\*", readme)
    out["cost_usd"] = round(float(t.group(1)), 2) if t else _num((re.search(r"Done, for \$([0-9.]+)", readme) or [None, None])[1])
    t = re.search(r"10 journals of experiment 54 at these rates:.*?≈ \*\*\$([0-9,]+)\*\*", readme)
    out["ten_journals_usd"] = _num(t.group(1)) if t else None
    v = _json(GATE2_DIR / "out" / "look10_verdicts.json")
    if v and v.get("pages"):
        c = Counter(p.get("verdict") for p in v["pages"])
        out["pages_checked"] = dict(right=c.get("right", 0), minor=c.get("minor", 0), serious=c.get("serious", 0),
                                    of=len(v["pages"]), words_wrong=sum(p.get("words_wrong") or 0 for p in v["pages"]))
    return out


def _librarian() -> dict | None:
    s = _json(LIB71)
    out = {}
    d = ((s or {}).get("designs") or {}).get("all|both", {}).get(PRODUCTION_LIBRARIAN)
    if d:
        out.update(precision_pct=round(100 * d["precision"], 1), usd_per_1000=round(d["usd_per_1000"]),
                   usd_per_1000_exact=d["usd_per_1000"], to_person_pct=round(100 * d["human_share"]),
                   decisions_checked=d["n"])
    n64 = _json(LIB64)
    if n64:
        out["institutions"] = [n64["before"]["institutions"], n64["after"]["institutions"]]
    n67 = _json(LIB67)
    golive = re.search(r"\|\s*cited works\s*\|\s*[0-9,]+\s*\|\s*\*\*([0-9,]+)\*\*", _text(GOLIVE68))
    if n67:
        after = _num(golive.group(1)) if golive else n67.get("after", {}).get("cited_works")
        out["cited_works"] = [n67["before"]["cited_works"], after]
    return out or None


def _words_wrong() -> dict | None:
    rows = []
    for line in _text(PROOF_DIR / "words.jsonl").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    if not rows:
        return None
    n_pages = sum(1 for line in _text(PROOF_DIR / "pages.jsonl").splitlines() if line.strip())
    return dict(wrong=sum(r.get("wrong") or 0 for r in rows), of=sum(r.get("words") or 0 for r in rows),
                pages=n_pages or None, pages_word_checked=len(rows))


def _audit() -> dict | None:
    d = _json(_audit_dir() / "audit.json")
    if not d:
        return None
    t = (d.get("totals") or {}).get("all") or {}
    return dict(pct=t.get("accounted_lines"), lines=t.get("lines"), articles=t.get("articles"),
                release=(d.get("release") or "").replace(".db", "") or None)


def _costs() -> dict:
    readme = _text(GATE2_DIR / "README.md")
    p = re.search(r"\$([0-9.]+) per scan page", readme)
    w = re.search(r"\$([0-9.]+) per Word article", readme)
    return dict(per_scan_page_usd=_num(p.group(1)) if p else None,
                per_word_article_usd=_num(w.group(1)) if w else None, price_doubles=PRICE_DOUBLES)


def headlines(path: Path, release_id: str | None) -> dict:
    files = [GATE2_DIR / "measure70.py", GATE2_DIR / "README.md", GATE2_DIR / "out" / "look10_verdicts.json",
             PROOF_DIR / "words.jsonl", LIB71, LIB64, LIB67, GOLIVE68, _audit_dir() / "audit.json"]
    key = "headlines:" + str(_audit_dir()) + ":" + ",".join(f"{_mt(f):.0f}" for f in files)

    def build():
        n = _index_numbers(path)

        def v(k):
            return (n.get(k) or {}).get("value")
        cited2 = None
        sub = (n.get("cited_works") or {}).get("sub") or ""
        mm = re.match(r"([0-9,]+) cited by 2\+", sub)
        if mm:
            cited2 = _num(mm.group(1))
        aud = _audit()
        return dict(
            release=release_id or path.stem,
            articles=v("articles"), pages=v("pages"), words=v("words"), references=v("references"),
            authors=v("authors"), journals=v("journals"),
            journals_read_whole=_whole_journals(path),
            institutions=v("institutions"), institutions_with_country_pct=_institutions_country_pct(path),
            cited_works=v("cited_works"), cited_by_2plus=cited2, held_pct=v("held"),
            audit_pct=aud["pct"] if aud else None, audit=aud,
            words_wrong=_words_wrong(),
            gate1=_gate1(path), gate2=_gate2(path, release_id), librarian=_librarian(), costs=_costs(),
            defs=DEFS,
            sources=dict(index=str(path), gate2=str(GATE2_DIR / "measure70.py") + " (run live on the release)",
                         audit=str(_audit_dir() / "audit.json"), proof=str(PROOF_DIR / "words.jsonl"),
                         librarian=str(LIB71)),
        )
    k = (str(path), _mt(path), key)
    hit = _cache.get("v")
    if hit and hit[0] == k:
        return hit[1]
    data = build()
    _cache["v"] = (k, data)
    return data


def _deps():
    from .api import P, jsonable, me, pgc, _state   # noqa: F401  (api.py includes this router after defining them)
    return P, jsonable, me, pgc, _state


P, jsonable, me, pgc, _state = _deps()


@router.get(f"{P}/headlines")
def get_headlines(actor: dict = Depends(me)):
    """The headline numbers every show page quotes, each with its definition (experiment 73)."""
    with pgc() as pg:
        path, st = _state(pg)
    return jsonable(headlines(path, st.get("release_id")))



@router.on_event("startup")
def _warm():
    """Compute the headlines (and with them the index base, the overview and gate 1) in the background when the API
    starts, so the first visitor after a restart does not wait 30+ s and hit the web proxy's time-out (exp 73)."""
    import threading

    def run():
        try:
            with pgc() as pg:
                path, st = _state(pg)
            headlines(path, st.get("release_id"))
        except Exception:          # a warm-up only: the route computes on demand anyway
            pass
    threading.Thread(target=run, name="headlines-warm", daemon=True).start()
