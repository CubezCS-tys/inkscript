"""Field coverage before / after, the catalogue's verdicts, and the documents to look at.

    PYTHONPATH=src .venv/bin/python experiments/29_catalogue/summarize.py   -> out/summary.json (and prints it)
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE.parent / "28_scale"))
from summarize import name_sim, sim  # noqa: E402  (experiment 28's scoring against the catalogue)

FIELDS = [("title", lambda r: bool(r["title"])), ("title tied to its ink", lambda r: r["title_words"]),
          ("authors", lambda r: bool(r["authors"])), ("an author tied to its ink", lambda r: r["authors_ink"] > 0),
          ("journal title", lambda r: bool(r["journal"])), ("ISSN", lambda r: bool(r["issn"])),
          ("year", lambda r: bool(r["year"])), ("Hijri year", lambda r: "islamic" in r["year"]),
          ("volume or issue", lambda r: bool(r["volume"] or r["issue"])), ("pages", lambda r: bool(r["fpage"])),
          ("abstract", lambda r: r["abstract"] > 0), ("keywords", lambda r: r["keywords"] > 0),
          ("DOI", lambda r: bool(r["doi"]))]


def main():
    rows = {m: {r["stem"]: r for r in json.loads((OUT / f"{m}.json").read_text())} for m in ("before", "after")}
    cat = json.loads(Path("/home/yassine/inkscript/experiments/28_scale/out/catalogue_titles.json").read_text())
    stems = sorted(rows["after"])
    errors = {m: [s for s, r in rows[m].items() if "error" in r] for m in rows}
    ok = [s for s in stems if s not in errors["before"] and s not in errors["after"]]
    withcat = [s for s in ok if rows["after"][s]["catalogue"]]
    cov = {}
    for name, f in FIELDS:
        cov[name] = dict(before=sum(1 for s in ok if f(rows["before"][s])), after=sum(1 for s in ok if f(rows["after"][s])))
    # the page's own title / names against the catalogue (what the catalogue corrects)
    tb = sum(1 for s in withcat if sim(rows["before"][s]["title"], cat.get(s, {}).get("title", "")) >= 0.6)
    ab = sum(sum(1 for x in cat.get(s, {}).get("authors", []) if any(name_sim(x, y) >= 0.6 for y in rows["before"][s]["authors"]))
             for s in withcat)
    ncat_auth = sum(len(cat.get(s, {}).get("authors", [])) for s in withcat)
    verdicts = Counter(rows["after"][s].get("catalogue_check", {}).get("verdict", "no record") for s in ok)
    titles = Counter(rows["after"][s].get("catalogue_check", {}).get("title", "no record") for s in ok)
    persons = sum(int(rows["after"][s]["catalogue_check"].get("authors", "0/0").split("/")[1]) for s in withcat)
    found = sum(int(rows["after"][s]["catalogue_check"].get("authors", "0/0").split("/")[0]) for s in withcat)
    prefixes = sum(1 for s in withcat for p in rows["after"][s]["prefixes"] if p)
    affs = {m: sum(rows[m][s]["affs"] for s in ok) for m in rows}
    valid = {m: dict(jats=sum(1 for s in ok if rows[m][s]["jats_valid"]), alto=sum(1 for s in ok if rows[m][s]["alto_valid"]))
             for m in rows}
    summary = dict(documents=len(stems), errors=errors, compared=len(ok), with_record=len(withcat), coverage=cov,
                   valid=valid, page_title_right_before=tb, page_authors_right_before=ab, catalogue_authors=ncat_auth,
                   verdicts=verdicts, title=titles, names_found=found, names=persons, prefixes=prefixes, affs=affs,
                   disagree=[s for s in withcat if rows["after"][s]["catalogue_check"]["verdict"].startswith(("disagrees", "doubtful"))],
                   not_found=[s for s in withcat if rows["after"][s]["catalogue_check"].get("title") == "not found on the page"],
                   seconds=dict(before=sum(rows["before"][s]["seconds"] for s in ok), after=sum(rows["after"][s]["seconds"] for s in ok)))
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
