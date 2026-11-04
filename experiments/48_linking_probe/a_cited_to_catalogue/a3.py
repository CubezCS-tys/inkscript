"""A3: journals as cited sources. Normalise every journal string printed in a journal citation into a journal
entity, then match entities to the catalogue's journals (773 forms) and, for foreign journals, OpenAlex sources.

Run: a3.py local    -> out/.../a3_entities.json (entities, catalogue matches)
     a3.py openalex -> adds OpenAlex sources for the unmatched Latin-script entities (top by citations, ≤ 250 calls)
"""
import json, re, sys, collections, difflib, unicodedata
sys.path.insert(0, "/home/appuser/inkscript/experiments/45_marc_db")
from build45 import fold  # noqa: E402

OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
AR = re.compile(r"[؀-ۿ]")
ABBR = {"j": "journal", "jr": "journal", "jour": "journal", "int": "international", "intl": "international",
        "rev": "review", "res": "research", "educ": "education", "edu": "education", "psychol": "psychology",
        "psych": "psychology", "sci": "science", "am": "american", "soc": "social",
        "med": "medicine", "econ": "economics", "stud": "studies",
        "q": "quarterly", "ann": "annals", "bull": "bulletin", "proc": "proceedings",
        "acad": "academy", "assoc": "association", "dev": "development", "manag": "management", "mgmt": "management",
        "lang": "language", "ling": "linguistics", "lit": "literature", "hist": "history", "philos": "philosophy",
        "clin": "clinical", "environ": "environmental", "agric": "agriculture",
        "eng": "engineering", "technol": "technology", "tech": "technology",
        "behav": "behavior", "disord": "disorders", "nutr": "nutrition", "arch": "archives", "geogr": "geography", "anal": "analysis", "financ": "finance", "account": "accounting", "polit": "political",
        "sociol": "sociology", "anthropol": "anthropology", "z": "zeitschrift", "n": "new"}
LSTOP = {"the", "of", "and", "for", "in", "on", "de", "des", "du", "la", "le", "les", "et", "d", "l", "a", "an", "&"}
AR_PREFIX = {"مجله", "المجله", "مجلة", "المجلة", "دوريه", "الدوريه", "حوليه", "حوليات"}
AR_STOP = {"في", "و", "من", "على", "عن", "لل"}


def latin_key(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    out = []
    for t in s.split():
        if t.isdigit():
            continue
        t = ABBR.get(t, t)
        if t in LSTOP:
            continue
        out.append(t)
    return out


def arabic_key(s):
    s = fold(s)
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    out = []
    for t in s.split():
        if t.isdigit() or t in AR_STOP:
            continue
        t2 = t
        if t2.startswith("وال"):
            t2 = t2[1:]
        if t2.startswith("لل") and len(t2) > 4:
            t2 = "ال" + t2[2:]
        if t2.startswith("ال") and len(t2) > 4:
            t2 = t2[2:]
        out.append(t2)
    while out and out[0] in {"مجله", "دوريه", "حوليه", "حوليات"}:
        out = out[1:]
    # trailing locators: ع 3, مج 2, العدد ...
    while out and out[-1] in {"ع", "مج", "عدد", "عد", "مجلد", "جزء", "ج", "سنه", "س", "vol", "no"}:
        out = out[:-1]
    return out


def jkey(s):
    s = (s or "").strip()
    if not s:
        return ""
    s = re.split(r"\s[،,]\s?(?:ع|العدد|مج|المجلد|vol|no)\b", s)[0]
    toks = arabic_key(s) if AR.search(s) else latin_key(s)
    return " ".join(toks)


def dice(a, b):
    a, b = set(a.split()), set(b.split())
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def sim(a, b):
    return max(dice(a, b), difflib.SequenceMatcher(None, a, b).ratio())


def local():
    W = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")}
    C = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "classified.jsonl", encoding="utf-8")}
    cites = []          # one per full citation in a journal-type work naming a source
    n_journal_cites = 0
    for k, w in W.items():
        for m in w["members"]:
            p = m["parsed"] or {}
            if C[k]["cls"] in ("journal_article", "news") or p.get("pub_type") == "journal":
                n_journal_cites += 1
                if p.get("source_title"):
                    y = re.search(r"(1[3-9]\d\d|20[0-3]\d)", fold(str(p.get("year") or "")))
                    cites.append(dict(cited_work_pk=k, mention_id=m["mention_id"], stem=m["stem"], page=m["page"],
                                      note=m["container_id"], printed=m["printed"], source=p["source_title"],
                                      year=int(y.group(1)) if y else None, cls=C[k]["cls"]))
    strings = collections.Counter(c["source"] for c in cites)
    # 1. key, 2. fuzzy union of keys (same script, sim ≥ 0.9, ≥ 2 tokens, first token equal)
    keys = collections.defaultdict(list)
    for s in strings:
        keys[jkey(s)].append(s)
    keys.pop("", None)
    par = {k: k for k in keys}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    kl = sorted(keys, key=lambda k: (-sum(strings[s] for s in keys[k]), k))
    for i, a in enumerate(kl):
        for b in kl[i + 1:]:
            if bool(AR.search(a)) != bool(AR.search(b)):
                continue
            if len(a.split()) < 2 or len(b.split()) < 2 or a.split()[0] != b.split()[0]:
                continue
            if sim(a, b) >= (0.9 if AR.search(a) else 0.93):
                par[find(b)] = find(a)
    ent = collections.defaultdict(lambda: dict(keys=[], strings=[], n=0))
    for k in keys:
        e = ent[find(k)]
        e["keys"].append(k)
        for s in keys[k]:
            e["strings"].append(s); e["n"] += strings[s]
    # catalogue journals: index of keys of every form
    CJ = json.load(open(OUT + "catalogue_journals.json", encoding="utf-8"))
    cidx = collections.defaultdict(set); tok_idx = collections.defaultdict(set)
    for code, v in CJ.items():
        for f, n in v["forms"]:
            k = jkey(f)
            if not k:
                continue
            cidx[k].add(code)
            for t in set(k.split()):
                tok_idx[t].add(k)
    out = []
    for root, e in ent.items():
        best = None
        for k in e["keys"]:
            if k in cidx:
                codes = sorted(cidx[k], key=lambda c: -CJ[c]["n"])
                cand = (1.0, k, codes, "exact-key")
            else:
                pool = collections.Counter()
                for t in set(k.split()):
                    if len(tok_idx.get(t, ())) < 3000:
                        for ck in tok_idx.get(t, ()):
                            pool[ck] += 1
                cand = None
                # a cited name that is the start of a catalogue name (≥ 2 words): a family / series match
                fam = [ck for ck in pool if len(k.split()) >= 2 and ck.startswith(k + " ")]
                if fam:
                    codes = sorted({c for ck in fam for c in cidx[ck]}, key=lambda c: -CJ[c]["n"])
                    cand = (0.88, fam[0], codes, "prefix-family")
                for ck, _ in pool.most_common(200):
                    s = sim(k, ck)
                    if cand is None or (s > cand[0] and not (cand[3] == "prefix-family" and s < 0.9)):
                        cand = (s, ck, sorted(cidx[ck], key=lambda c: -CJ[c]["n"]), "fuzzy")
            if cand and (best is None or cand[0] > best[0]):
                best = cand
        rec = dict(entity=root, n_cites=e["n"], n_strings=len(e["strings"]), strings=sorted(e["strings"]),
                   keys=sorted(e["keys"]), script="ara" if AR.search(root) else "lat")
        if best:
            s, ck, codes, how = best
            rec.update(cat_sim=round(s, 3), cat_key=ck, cat_codes=codes[:3], cat_how=how,
                       cat_forms=[f for f, _ in CJ[codes[0]]["forms"][:3]], cat_n_records=CJ[codes[0]]["n"],
                       cat_issn=[i for i, _ in CJ[codes[0]]["issn"][:2]])
        out.append(rec)
    out.sort(key=lambda r: (-r["n_cites"], r["entity"]))
    json.dump(dict(n_journal_cites=n_journal_cites, n_cites_with_source=len(cites), n_strings=len(strings),
                   n_keys=len(keys), n_entities=len(out), entities=out, cites=cites),
              open(OUT + "a3_entities.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(n_journal_cites, "journal citations;", len(cites), "name a source;", len(strings), "strings →", len(keys),
          "keys →", len(out), "entities")
    for th in (1.0, 0.95, 0.9, 0.85, 0.8):
        m = [r for r in out if r.get("cat_sim", 0) >= th]
        print(f"catalogue sim ≥ {th}: {len(m)} entities, {sum(r['n_cites'] for r in m)} citations")


def openalex():
    from ext import openalex_sources
    D = json.load(open(OUT + "a3_entities.json", encoding="utf-8"))
    todo = [r for r in D["entities"] if r["script"] == "lat" and r.get("cat_sim", 0) < 0.9]
    todo = todo[:250]
    for r in todo:
        name = max(r["strings"], key=len)
        res = openalex_sources(name, f"A3: journal name {name[:60]}")
        hits = []
        for h in ((res.get("body") or {}).get("results") or []):
            forms = [h.get("display_name") or ""] + (h.get("alternate_titles") or []) + [h.get("abbreviated_title") or ""]
            s = max(sim(jkey(name), jkey(f)) for f in forms if f) if any(forms) else 0
            s2 = max(sim(jkey(x), jkey(f)) for x in r["strings"] for f in forms if f) if any(forms) else 0
            hits.append(dict(source="openalex", id=h.get("id"), name=h.get("display_name"), issn_l=h.get("issn_l"),
                             type=h.get("type"), works_count=h.get("works_count"), sim=round(max(s, s2), 3)))
        hits.sort(key=lambda x: -x["sim"])
        r["openalex"] = hits[:2]
    json.dump(D, open(OUT + "a3_entities.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    for th in (0.95, 0.9, 0.85):
        m = [r for r in todo if r.get("openalex") and r["openalex"][0]["sim"] >= th]
        print(f"openalex sim ≥ {th}: {len(m)} of {len(todo)} entities, {sum(r['n_cites'] for r in m)} citations")


if __name__ == "__main__":
    {"local": local, "openalex": openalex, "decide": lambda: None, "crossref": lambda: None}[sys.argv[1]]()


def decide():
    """Final journal → catalogue decision per entity, then a seeded citation-level sample (seed 4803) to judge."""
    import random
    D = json.load(open(OUT + "a3_entities.json", encoding="utf-8"))
    CJ = json.load(open(OUT + "catalogue_journals.json", encoding="utf-8"))
    # article links that confirm a journal: an accepted A1 link of a citation in the entity to a record of that journal
    dec = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "decisions.jsonl", encoding="utf-8")}
    from q import marc
    mc = marc()
    code_of = {}
    for k, d in dec.items():
        if d["decision"] == "accept":
            r = mc.execute("SELECT journal_code FROM records WHERE c999 = ?", (d["c999"],)).fetchone()
            code_of[k] = r[0] if r else None
    by_string = collections.defaultdict(set)
    for c in D["cites"]:
        if code_of.get(c["cited_work_pk"]):
            by_string[c["source"]].add(code_of[c["cited_work_pk"]])
    S = collections.Counter()
    for e in D["entities"]:
        confirmed = set().union(*[by_string.get(s, set()) for s in e["strings"]]) if e["strings"] else set()
        sim, how, codes = e.get("cat_sim", 0), e.get("cat_how"), e.get("cat_codes", [])
        if confirmed and (set(codes) & confirmed or sim < 0.95):
            e["journal_decision"], e["journal_code"] = "accept", sorted(confirmed)[0] if not (set(codes) & confirmed) else sorted(set(codes) & confirmed)[0]
            e["journal_why"] = "confirmed by an accepted article link"
        elif e["script"] == "ara" and sim >= 0.95:
            e["journal_decision"], e["journal_code"], e["journal_why"] = "accept", codes[0], "same key (folded, «مجلة» dropped)"
        elif e["script"] == "ara" and how == "prefix-family":
            e["journal_decision"], e["journal_code"], e["journal_why"] = "family", codes[0], "cited name begins a catalogue name (a series)"
        elif e["script"] == "ara" and sim >= 0.88:
            e["journal_decision"], e["journal_code"], e["journal_why"] = "candidate", codes[0], "close Arabic name"
        elif e["script"] == "lat" and sim >= 0.95:
            e["journal_decision"], e["journal_code"], e["journal_why"] = "candidate", codes[0], "Latin name equals an Arab journal's English title"
        else:
            e["journal_decision"], e["journal_code"], e["journal_why"] = "none", None, ""
        S[(e["script"], e["journal_decision"])] += 1
    n_cites = collections.Counter()
    ent_of = {s: e for e in D["entities"] for s in e["strings"]}
    for c in D["cites"]:
        e = ent_of.get(c["source"])
        n_cites[e["journal_decision"] if e else "no entity"] += 1
    D["decision_counts"] = {f"{a}/{b}": v for (a, b), v in S.items()}
    D["cites_by_decision"] = dict(n_cites)
    json.dump(D, open(OUT + "a3_entities.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(S); print(n_cites)
    rng = random.Random(4803)
    smp = rng.sample(D["cites"], 40)
    with open(OUT + "a3_sample.txt", "w", encoding="utf-8") as f:
        for i, c in enumerate(smp):
            e = ent_of.get(c["source"])
            f.write(f"#{i} {c['stem']} p{c['page']} {c['note']}  source={c['source']!r}\n  CITED: {c['printed'][:300]}\n")
            if e:
                f.write(f"  entity={e['entity']!r} strings={e['strings'][:5]} n_cites={e['n_cites']}\n")
                f.write(f"  -> {e['journal_decision']} {e['journal_code']} ({e['journal_why']}) sim={e.get('cat_sim')} forms={[x for x, _ in CJ[e['journal_code']]['forms'][:3]] if e['journal_code'] else e.get('cat_forms')}\n\n")
    json.dump([dict(i=i, mention_id=c["mention_id"], source=c["source"]) for i, c in enumerate(smp)], open(OUT + "a3_sample.json", "w"), ensure_ascii=False)


if __name__ == "__main__" and sys.argv[1] == "decide":
    decide()


def crossref_sources(limit=200):
    """Foreign journal entities with no catalogue match → Crossref journals (source marked 'crossref')."""
    from ext import crossref_journals
    D = json.load(open(OUT + "a3_entities.json", encoding="utf-8"))
    todo = [e for e in D["entities"] if e["script"] == "lat" and e.get("journal_decision") in ("none", "candidate")]
    todo = todo[:limit]
    for e in todo:
        name = max(e["strings"], key=len)
        res = crossref_journals(name, f"A3: journal name {name[:60]}")
        hits = []
        for h in (((res.get("body") or {}).get("message") or {}).get("items") or []):
            forms = [h.get("title") or ""]
            s = max(sim(jkey(x), jkey(f)) for x in e["strings"] for f in forms if f) if any(forms) else 0
            hits.append(dict(source="crossref", title=h.get("title"), issn=h.get("ISSN"), publisher=h.get("publisher"),
                             sim=round(s, 3)))
        hits.sort(key=lambda x: -x["sim"])
        e["crossref"] = hits[:2]
        e["crossref_status"] = res.get("status")
    json.dump(D, open(OUT + "a3_entities.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    for th in (1.0, 0.95, 0.9):
        m = [e for e in todo if e.get("crossref") and e["crossref"][0]["sim"] >= th]
        print(f"crossref sim ≥ {th}: {len(m)} of {len(todo)} entities, {sum(e['n_cites'] for e in m)} of {sum(e['n_cites'] for e in todo)} citations")


if __name__ == "__main__" and sys.argv[1] == "crossref":
    crossref_sources()
