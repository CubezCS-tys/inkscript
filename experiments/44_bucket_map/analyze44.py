"""Experiment 44: read list44.py's listing (out/listing/*.tsv) and count what the buckets hold.

Writes out/summary44.json (per-prefix counts and sizes, key patterns with examples, document counts for the main
folders and legacy/, overlaps, the comparison with experiment 19's listing and with the catalogue, and the
experiment 43 missing ids) and out/ids_main.txt, out/ids_legacy.txt. No network.

    .venv/bin/python experiments/44_bucket_map/analyze44.py
"""
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
LST = OUT / "listing"
MAIN = HERE.parents[1]
EXP19 = MAIN / "experiments/19_azure_map/out/listing.txt"
FETCH43 = MAIN / "experiments/43_rehearsal/out/fetch"
CATALOGUE = Path.home() / ".cache/inkscript/catalogue/catalogue.sqlite"

SRC = "mandumah-source-docs"
ID4 = re.compile(r"^\d{4}-\d{3}-\d{3}-\d{3}$")               # the common form, e.g. 0001-000-002-003
DOC = re.compile(r"^(?P<area>legacy/|legacy-test/)?(?P<id>[^/]+)/(?P<name>[^/]+)$")


def ext(key):
    n = key.rsplit("/", 1)[-1]
    if n.endswith(".snapshot.manifest.json"):
        return ".snapshot.manifest.json"
    if n.endswith(".sql.gz") or n.endswith(".xml.gz") or n.endswith(".json.gz"):
        return "." + ".".join(n.split(".")[-2:])
    return "." + n.rsplit(".", 1)[-1].lower() if "." in n else "(none)"


def rows():
    for f in sorted(LST.glob("*.tsv")):
        bucket = f.stem.split("__")[0]
        with f.open() as fh:
            for line in fh:
                k, s, t, c = line.rstrip("\n").split("\t")
                yield bucket, k, int(s), t, c


def top(bucket, key):
    if bucket == SRC:
        first = key.split("/", 1)[0]
        if first in ("legacy", "legacy-test", "metadata"):
            return first + "/"
        return "(document folders)/" if "/" in key else "(root files)"
    return key.split("/", 1)[0] + "/" if "/" in key else "(root files)"


def id_form(i):
    if ID4.match(i):
        return "NNNN-NNN-NNN-NNN"
    return re.sub(r"\d", "N", i)


def main():
    prefixes = defaultdict(lambda: dict(objects=0, bytes=0, ext=Counter(), ext_bytes=Counter(), months=Counter(),
                                        first=None, last=None, classes=Counter()))
    docs = {"main": defaultdict(set), "legacy": defaultdict(set), "legacy-test": defaultdict(set)}
    sizes = {"main": Counter(), "legacy": Counter(), "legacy-test": Counter()}
    patterns = defaultdict(lambda: dict(n=0, examples=[]))
    other = defaultdict(list)
    qdrant, mysql, trail = [], [], Counter()

    for bucket, k, s, t, c in rows():
        p = prefixes[f"{bucket}/{top(bucket, k)}"]
        e = ext(k)
        p["objects"] += 1
        p["bytes"] += s
        p["ext"][e] += 1
        p["ext_bytes"][e] += s
        p["months"][t[:7]] += 1
        p["classes"][c] += 1
        p["first"] = min(p["first"] or t, t)
        p["last"] = max(p["last"] or t, t)
        if bucket == SRC:
            m = DOC.match(k)
            if m and k.split("/")[0] != "metadata":
                area = (m.group("area") or "").rstrip("/") or "main"
                i, n = m.group("id"), m.group("name")
                pat = f"{m.group('area') or ''}<id>/" + ("<id>" + e if n == i + e else n.replace(i, "<id>"))
                docs[area][i].add(e if n == i + e else "other:" + n.replace(i, "<id>"))
                sizes[area][e] += s
            else:
                pat = re.sub(r"\d", "N", k)
            pp = patterns[pat]
            pp["n"] += 1
            if len(pp["examples"]) < 4 and (not pp["examples"] or pp["examples"][-1][0] != k.split("/")[0]):
                pp["examples"].append((k, s))
            if not m or k.startswith("metadata/") or pat.endswith("other"):
                other[pat].append(k) if len(other[pat]) < 5 else None
        elif bucket.startswith("mandumah-qdrant"):
            (qdrant if k.startswith("qdrant/") else mysql).append(dict(key=k, bytes=s, modified=t))
        else:
            parts = k.split("/")                               # AWSLogs/<acct>/CloudTrail/<region>/<y>/<m>/<d>/file
            trail["/".join(parts[:4])] += 1

    def doc_counts(d):
        kinds = Counter()
        for i, es in d.items():
            has_pdf, has_json = ".pdf" in es, ".json" in es
            kinds["pdf+json" if has_pdf and has_json else "pdf only" if has_pdf else "json only" if has_json
                  else "neither"] += 1
        forms = Counter(id_form(i) for i in d)
        extra = Counter(e for es in d.values() for e in es if e not in (".pdf", ".json"))
        return dict(ids=len(d), kinds=dict(kinds), id_forms=dict(forms.most_common(12)), id_forms_n=len(forms),
                    other_files=dict(extra.most_common(12)),
                    journals=len({i[:4] for i in d}))

    main_ids, leg_ids, lt_ids = set(docs["main"]), set(docs["legacy"]), set(docs["legacy-test"])
    S = dict(listed_on=max(p["last"] for p in prefixes.values())[:10])
    S["prefixes"] = {k: dict(v, ext=dict(v["ext"]), ext_bytes=dict(v["ext_bytes"]),
                             months=dict(sorted(v["months"].items())), classes=dict(v["classes"]))
                     for k, v in sorted(prefixes.items())}
    S["patterns"] = dict(sorted(((k, v) for k, v in patterns.items()), key=lambda kv: -kv[1]["n"]))
    S["other_examples"] = dict(other)
    S["docs"] = {a: doc_counts(d) for a, d in docs.items()}
    S["sizes"] = {a: dict(v) for a, v in sizes.items()}
    S["overlap"] = dict(main=len(main_ids), legacy=len(leg_ids), legacy_test=len(lt_ids),
                        main_and_legacy=len(main_ids & leg_ids), legacy_only=len(leg_ids - main_ids),
                        main_only=len(main_ids - leg_ids), union=len(main_ids | leg_ids),
                        union_all=len(main_ids | leg_ids | lt_ids),
                        legacy_test_in_legacy=len(lt_ids & leg_ids), legacy_test_in_main=len(lt_ids & main_ids))
    # In the overlap, which has the JSON?
    both = main_ids & leg_ids
    S["overlap"]["both_kinds"] = dict(Counter(
        ("main:" + "+".join(sorted(docs["main"][i])) + " | legacy:" + "+".join(sorted(docs["legacy"][i])))
        for i in both).most_common(8))
    S["overlap"]["legacy_only_kinds"] = dict(Counter("+".join(sorted(docs["legacy"][i])) for i in leg_ids - main_ids))
    # Legacy files: same bytes as main? (size equality on the PDF as a cheap proxy)
    (OUT / "ids_main.txt").write_text("\n".join(sorted(main_ids)) + "\n")
    (OUT / "ids_legacy.txt").write_text("\n".join(sorted(leg_ids)) + "\n")

    # Experiment 19's listing (aws s3 ls of the root: "PRE <id>/" lines), 2026-10-06
    if EXP19.exists():
        old = {ln.split()[-1].rstrip("/") for ln in EXP19.open() if ln.strip().startswith("PRE")}
        old -= {"legacy", "legacy-test", "metadata"}
        S["exp19"] = dict(listed="2026-10-06", ids=len(old), still_there=len(old & main_ids), gone=len(old - main_ids),
                          new=len(main_ids - old), gone_examples=sorted(old - main_ids)[:8],
                          new_examples=sorted(main_ids - old)[:8])

    # The catalogue (metadata_final.xml.gz -> pdf stems)
    if CATALOGUE.exists():
        db = sqlite3.connect(CATALOGUE)
        cat = {r[0] for r in db.execute("select stem from pdf")}
        info = dict(db.execute("select k, v from info").fetchall())
        union = main_ids | leg_ids
        cat_main = cat & main_ids
        cat_leg_only = (cat & leg_ids) - main_ids
        S["catalogue"] = dict(records=int(info.get("records", 0)), pdf_stems=len(cat), built=info.get("built"),
                              source_bytes=int(info.get("source_bytes", 0)),
                              in_main=len(cat_main), in_legacy_only=len(cat_leg_only),
                              in_union=len(cat & union), in_neither=len(cat - union),
                              bucket_not_in_catalogue_main=len(main_ids - cat),
                              bucket_not_in_catalogue_legacy=len(leg_ids - cat),
                              not_in_catalogue_examples=sorted(main_ids - cat)[:8],
                              missing_examples=sorted(cat - union)[:8],
                              missing_by_form=dict(Counter(id_form(i) for i in cat - union).most_common(6)),
                              missing_by_journal_top=Counter(i[:4] for i in cat - union).most_common(10),
                              cat_by_form=dict(Counter(id_form(i) for i in cat).most_common(6)))
        # Missing journals: whole journals absent vs gaps inside journals present
        jb = {i[:4] for i in union}
        miss = cat - union
        S["catalogue"]["missing_in_journals_with_files"] = sum(1 for i in miss if i[:4] in jb)
        S["catalogue"]["missing_in_journals_without_files"] = sum(1 for i in miss if i[:4] not in jb)
        S["catalogue"]["journals_catalogue"] = len({i[:4] for i in cat})
        S["catalogue"]["journals_bucket"] = len(jb)
        # Journal codes 98xx are dissertations (the catalogue's db "Dissertations"), one record split into several
        # PDFs (<base>-0, -1, ..., -A, -C, -F, -R, -T); everything else is an article-like stem.
        fam = Counter()
        diss_bases, diss_bases_any = set(), set()
        for s in cat:
            f = "dissertation" if s.startswith("98") else "article"
            w = "main" if s in main_ids else "legacy" if s in leg_ids else "none"
            fam[f"{f}:{w}"] += 1
            if f == "dissertation":
                diss_bases.add(s.rsplit("-", 1)[0])
        S["catalogue"]["by_family"] = dict(fam)
        S["catalogue"]["dissertation_records"] = len(diss_bases)
        S["catalogue"]["dissertation_ids_in_bucket"] = sum(1 for i in union if i.startswith("98"))
        art_missing = Counter(i[:4] for i in miss if not i.startswith("98"))
        S["catalogue"]["article_missing_top_journals"] = art_missing.most_common(12)
        S["catalogue"]["article_missing_journals"] = len(art_missing)
        S["catalogue"]["main_not_in_catalogue_top_journals"] = Counter(i[:4] for i in main_ids - cat).most_common(8)
        del cat

    # Experiment 43's catalogue draws that were not in the bucket
    miss43 = []
    for name, tag in (("fetch_log.txt", "MISSING"), ("reserve_log.txt", "FAIL")):
        f = FETCH43 / name
        if f.exists():
            miss43 += [ln.split()[0].rstrip(":") for ln in f.open() if tag in ln]
    drawn = sum(1 for n in ("fetch_log.txt", "reserve_log.txt") if (FETCH43 / n).exists()
                for _ in (FETCH43 / n).open())
    S["exp43_missing"] = dict(drawn=drawn, missing=len(miss43), in_main_now=sorted(set(miss43) & main_ids),
                              in_legacy=sorted(set(miss43) & leg_ids), in_legacy_test=sorted(set(miss43) & lt_ids),
                              nowhere=sorted(set(miss43) - main_ids - leg_ids - lt_ids))
    # Same ids under another spelling? (prefix match on the first three parts)
    stem3 = defaultdict(list)
    for i in main_ids | leg_ids | lt_ids:
        stem3[i.rsplit("-", 1)[0]].append(i)
    S["exp43_missing"]["issue_siblings"] = {i: len(stem3.get(i.rsplit("-", 1)[0], [])) for i in miss43}

    S["qdrant"] = qdrant
    S["mysql"] = dict(n=len(mysql), bytes=sum(x["bytes"] for x in mysql), first=min((x["key"] for x in mysql), default=None),
                      last=max((x["key"] for x in mysql), default=None),
                      names=dict(Counter(re.sub(r"-\d{8}T\d{6}Z.*", "", x["key"]) for x in mysql)),
                      newest_bytes=max((x["bytes"] for x in mysql), default=0))
    S["cloudtrail"] = dict(trail)
    req = OUT / "listing/requests.json"
    S["requests"] = json.loads(req.read_text())["total"] if req.exists() else None
    (OUT / "summary44.json").write_text(json.dumps(S, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: S[k] for k in ("listed_on", "docs", "overlap", "requests")}, indent=1))


if __name__ == "__main__":
    main()
