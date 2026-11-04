"""Probe D shared loading: the 600 shown versions, their citation mentions, cards, accepted links (link47 in the DB,
probe A's v3 decisions), probe B's census verdicts, probe A's journal entities.  Read-only everywhere."""
import json, os, sqlite3, collections

ROOT = "/home/appuser/inkscript/experiments/48_linking_probe"
OUT = ROOT + "/out/d_metrics_and_workload/"
A = ROOT + "/out/a_cited_to_catalogue/"
B = ROOT + "/out/b_works_and_backrefs/"
C = ROOT + "/out/c_people_and_institutions/"
PLAT = "file:/home/appuser/data/platform_v2/platform_v2.db?mode=ro"
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
RUNS600 = ("v33_300_final", "v33_300b_fix3")


def plat():
    return sqlite3.connect(PLAT, uri=True)


def marc():
    return sqlite3.connect(MARC, uri=True)


def save(name, obj):
    with open(OUT + name, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def jl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def load():
    """Everything the metrics need, as plain Python structures (small: < 50 MB)."""
    c = plat()
    D = {}
    arts = c.execute("""
        SELECT v.version_id, v.stem, v.run, d.pub_id, p.c999, p.journal_id, p.year_shown, p.type,
               (SELECT value FROM metadata_assertions a WHERE a.pub_id=p.pub_id AND a.field='title' AND a.is_chosen=1 LIMIT 1)
        FROM versions v JOIN documents d ON d.stem=v.stem LEFT JOIN publications p ON p.pub_id=d.pub_id
        WHERE v.is_current=1 AND v.run IN (?,?)""", RUNS600).fetchall()
    D["arts"] = {r[3]: dict(version_id=r[0], stem=r[1], run=r[2], pub_id=r[3], c999=r[4], journal_id=r[5],
                            year=r[6], type=r[7], title=r[8]) for r in arts}
    vids = {a["version_id"]: a["pub_id"] for a in D["arts"].values()}
    D["vid2pub"] = vids
    # journal names
    jt = {}
    for jid, t, form, ch in c.execute("SELECT journal_id,title,form,is_chosen FROM journal_titles"):
        if jid not in jt or ch:
            jt[jid] = t
    D["journal_title"] = jt
    # mentions (no quran / hadith), with their card
    ms = []
    for row in c.execute("""
        SELECT m.mention_pk, m.mention_id, m.version_id, m.kind, coalesce(m.full_mention_pk, m.mention_pk), w.cited_work_pk,
               m.page, m.container_id, m.anchor_pk, m.printed
        FROM citation_mentions m LEFT JOIN cited_work_members w ON w.full_mention_pk = coalesce(m.full_mention_pk, m.mention_pk)
        WHERE m.kind NOT IN ('quran','hadith')"""):
        if row[2] in vids:
            ms.append(dict(mention_pk=row[0], mention_id=row[1], pub_id=vids[row[2]], kind=row[3], full_pk=row[4],
                           work=row[5], page=row[6], note=row[7], anchor_pk=row[8], printed=row[9]))
    D["mentions"] = ms
    D["works"] = {r[0]: dict(pk=r[0], id=r[1], pub_type=r[2], title=r[3], year_greg=r[4], year_printed=r[5], lang=r[6])
                  for r in c.execute("SELECT cited_work_pk,cited_work_id,pub_type,title,year_greg,year_printed,lang "
                                     "FROM cited_works WHERE status='active'")}
    D["work_authors"] = collections.defaultdict(list)
    for pk, seq, printed, pid, aid, mm in c.execute(
            "SELECT cited_work_pk,seq,printed,person_id,authority_id,match_method FROM cited_work_authors ORDER BY 1,2"):
        D["work_authors"][pk].append(dict(printed=printed, person_id=pid, authority_id=aid, method=mm))
    # accepted links in the DB (link47)
    D["links47"] = {}
    for pk, tp, c999, score in c.execute("""SELECT l.cited_work_pk, l.target_pub_id, p.c999, l.score FROM citation_links l
            JOIN publications p ON p.pub_id=l.target_pub_id WHERE l.status='accepted' AND l.best=1 AND l.target_kind='publication'"""):
        D["links47"][pk] = dict(target_pub_id=tp, c999=c999, score=score)
    # authorships of the 600
    D["authorships"] = [dict(pub_id=r[0], position=r[1], role=r[2], person_id=r[3], method=r[4])
                        for r in c.execute("SELECT pub_id,position,role_code,person_id,method FROM authorships")
                        if r[0] in D["arts"]]
    D["person_auth"] = collections.defaultdict(list)
    for aid, pid in c.execute("SELECT authority_id, person_id FROM person_authorities"):
        D["person_auth"][pid].append(aid)
    D["person_name"] = {r[0]: r[1] or r[2] for r in c.execute(
        "SELECT person_id, preferred_name_ar, preferred_name_lat FROM persons")}
    c.close()
    # probe A
    D["cls"] = {r["cited_work_pk"]: r for r in jl(A + "classified.jsonl")}
    D["decA"] = {r["cited_work_pk"]: r for r in jl(A + "decisions.jsonl")}
    ext = collections.defaultdict(list)
    for r in jl(A + "external.jsonl"):
        for h in r.get("hits") or []:
            if (h.get("total") or 0) >= 0.8 and h.get("doi"):
                ext[r["cited_work_pk"]].append(dict(source=h.get("source", r["source"]), doi=h["doi"], group=r["group"],
                                                    total=h["total"], id=h.get("id")))
    D["extA"] = ext
    D["extA_looked"] = {r["cited_work_pk"]: r["group"] for r in jl(A + "external.jsonl")}
    a3 = json.load(open(A + "a3_entities.json", encoding="utf-8"))
    s2e = {}
    for e in a3["entities"]:
        for s in e["strings"]:
            s2e[s] = e
    D["a3_cites"] = a3["cites"]
    D["a3_s2e"] = s2e
    # probe B census verdicts on cross-article cards
    cj = json.load(open(B + "cross_article_judged.json", encoding="utf-8"))
    D["B_verdict"] = {x["cited_work_id"]: x["verdict"] for x in cj["cards"]}
    return D


def wilson(k, n, z=1.96):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return [round((c - r) / d, 3), round((c + r) / d, 3)]


def components(nodes, edges):
    par = {n: n for n in nodes}

    def f(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for a, b in edges:
        ra, rb = f(a), f(b)
        if ra != rb:
            par[ra] = rb
    comp = collections.defaultdict(list)
    for n in nodes:
        comp[f(n)].append(n)
    return sorted(comp.values(), key=len, reverse=True)
