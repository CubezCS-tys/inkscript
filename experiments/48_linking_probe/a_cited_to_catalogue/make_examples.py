"""examples.json: real examples, good and bad, each with the printed citation (stem, page, note id) and the target."""
import json
OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
W = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")}
M = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "matches.jsonl", encoding="utf-8")}
D = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "decisions.jsonl", encoding="utf-8")}
X = {json.loads(l)["cited_work_pk"]: [] for l in open(OUT + "works.jsonl", encoding="utf-8")}
for l in open(OUT + "external.jsonl", encoding="utf-8"):
    d = json.loads(l); X[d["cited_work_pk"]].append(d)
S1 = json.load(open(OUT + "a1_sample.json")); S2 = json.load(open(OUT + "a1b_sample.json")); S3 = json.load(open(OUT + "a1c_sample.json"))
A2 = json.load(open(OUT + "a2_sample.json"))["sample"]
def cite(k):
    w = W[k]; rep = max(w["members"], key=lambda x: len(x["printed"] or ""))
    return dict(cited_work_id=w["cited_work_id"], stem=rep["stem"], page=rep["page"], note_id=rep["container_id"], printed=rep["printed"])
def cat(k, c999=None):
    c999 = c999 or D[k]["c999"]
    t = next((t for t in M[k]["top"] if t["c999"] == c999), None)
    return dict(source="mandumah-catalogue", c999=c999, title=t and t["title"], authors=t and t["authors"][:3], year=t and t["year"], journal=t and t["journal"], type=t and t["type"]) if t else dict(source="mandumah-catalogue", c999=c999)
def ext(k, src):
    r = next(r for r in X[k] if r["source"] == src); h = r["hits"][0]
    return dict(source=src, doi=h.get("doi"), openalex_id=h.get("id"), title=h["title"], authors=h.get("authors", [])[:3], year=h.get("year"), venue=h.get("venue"))
E = []
def add(kind, verdict, k, target, note):
    E.append(dict(kind=kind, verdict=verdict, citation=cite(k), matched_to=target, decision_v3=D[k]["decision"], note=note))
add("A1 catalogue", "right", S1[0]["cited_work_pk"], cat(S1[0]["cited_work_pk"]), "everything agrees; link47 also accepted it")
add("A1 catalogue", "right", S1[24]["cited_work_pk"], cat(S1[24]["cited_work_pk"]), "Latin translation of an Arabic article; matched through the record's English title, authors through translit_pairs; link47 missed it")
add("A1 catalogue", "right", S1[18]["cited_work_pk"], cat(S1[18]["cited_work_pk"]), "catalogue gives 'هيئة التحرير' as author (a catalogue error); link47 rejected the link for that")
add("A1 catalogue", "wrong (not accepted)", S1[15]["cited_work_pk"], cat(S1[15]["cited_work_pk"], M[S1[15]["cited_work_pk"]]["top"][0]["c999"]), "cited master's thesis (2013); record is the 2015 article drawn from it: kept as candidate by the thesis rule")
add("A1 catalogue", "unsure → candidate in v3", S2[3]["cited_work_pk"], cat(S2[3]["cited_work_pk"], M[S2[3]["cited_work_pk"]]["top"][0]["c999"]), "same title, author and year but another journal: a second publication; v3 sends these to a person")
add("A1 catalogue", "wrong (rule d, removed)", S3[14]["cited_work_pk"], cat(S3[14]["cited_work_pk"], M[S3[14]["cited_work_pk"]]["top"][0]["c999"]), "authors share only common name words; the reason rule d now needs the journal to agree")
k85 = S2[85]["cited_work_pk"]; l = [x for x in W[k85]["links47"] if x["status"] == "accepted"][0]
add("A1 link47 check", "wrong (link47)", k85, dict(source="mandumah-catalogue", c999=l["c999"], note="link47 accepted: a 1990 reprint of the classical poem (نصوص أدبية)"), "a classical poem cited; link47 linked a modern reprint")
add("A1 relation", "right (relation, not holding)", S1[56]["cited_work_pk"], cat(S1[56]["cited_work_pk"], M[S1[56]["cited_work_pk"]]["top"][0]["c999"]), "a review of the cited book (عروض كتب) is a relation, never the work")
for i, v, n in [(1, "right", "DOI from Crossref, everything agrees"), (23, "right", "Arabic article found in Crossref under Mandumah's own DOI prefix 10.47337; also in the catalogue"),
                (20, "wrong", "Crossref: same author, a different 2008 paper"), (3, "wrong", "a cited book (Pradel, Procédure pénale) matched to a journal article: Crossref is not a book index"),
                (15, "right", "OpenAlex: found without DOI (Dialnet)")]:
    s = A2[i]; add("A2 external", v, s["cited_work_pk"], ext(s["cited_work_pk"], s["source"]), n)
A3 = json.load(open(OUT + "a3_entities.json", encoding="utf-8"))
ent = {s: e for e in A3["entities"] for s in e["strings"]}
s3 = json.load(open(OUT + "a3_sample.json"))
cites = {c["mention_id"]: c for c in A3["cites"]}
for i, v, n in [(1, "right", "«الآداب» / «الاداب» / «مجلة الآداب» collapse to one journal, confirmed by an accepted article link"),
                (9, "wrong", "generic «مجلة كلية التربية»: dozens of journals share it"), (28, "wrong (missed)", "JGUAA is held as «مجلة الاتحاد العام للآثاريين العرب»; abbreviations are not resolved")]:
    c = cites[s3[i]["mention_id"]]; e = ent[c["source"]]
    E.append(dict(kind="A3 journal", verdict=v, citation=dict(stem=c["stem"], page=c["page"], note_id=c["note"], printed=c["printed"], journal_string=c["source"]),
                  matched_to=dict(source="mandumah-catalogue", journal_code=e.get("journal_code"), decision=e.get("journal_decision"), entity_strings=e["strings"]), note=n))
json.dump(E, open(OUT + "examples.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(E))
