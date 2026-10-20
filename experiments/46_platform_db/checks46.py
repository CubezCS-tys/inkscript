"""Experiment 46: the hand check of sample46.json (seed 2026), read one by one on 2026-10-20 by the platform agent.
verdict: right | near (the same research in another form: thesis behind a book, conference paper later in a journal)
| wrong | withheld-ok (a non-best candidate that is indeed not the work). Written to sample46_checked.json and to the
`link_checks` table of platform.db (never touches the links)."""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common46 import connect  # noqa: E402

V = {0: "right", 1: "right (no author parsed; title, year, journal agree)", 2: "right", 3: "right", 4: "right",
     5: "near: cited as a 2010 thesis, linked to the 2010 journal article of the same title and author",
     6: "right", 7: "right", 8: "right (1409 H = 1989)", 9: "right", 10: "near: conference paper 2008, journal 2009",
     11: "right", 12: "right", 13: "right", 14: "right", 15: "right", 16: "right (2011 vs 2010, same journal)",
     17: "right", 18: "right", 19: "right (2009 vs 2000, same journal; a year typo on one side)", 20: "right",
     21: "right (corporate author)", 22: "right (OCR: للتعميم = للقيم)", 23: "right",
     24: "near: the 1974 thesis behind the cited 1974 book (author misread العبلي for العيلي)",
     25: "withheld-ok", 26: "withheld-ok (a study of the book)", 27: "withheld-ok", 28: "withheld-ok",
     29: "wrong: Pincus's «Economic Aid» resolved to his C.N.U.C.E.D. communication", 30: "right", 31: "right",
     32: "right", 33: "right", 34: "right", 35: "right", 36: "right", 37: "right", 38: "right (to the reference list)",
     39: "right", 40: "wrong: «Land Evaluation Part II» resolved to Part I",
     41: "right (chain of ibid.)", 42: "right", 43: "right", 44: "right",
     45: "wrong: ibid. after an unparsed court judgment went to La Rosa", 46: "right", 47: "right", 48: "right",
     49: "wrong: op. cit. of the book «L'Esprit piagetien» went to another chapter of it",
     50: "wrong: «واسكو، المصدر السابق» (Arabic spelling of Waskow) matched Sharabi by title words of a long note",
     51: "right (AGUESSY, the same title misprinted)",
     52: "wrong: «ROLDÁN et al., 2006, op. cit.» matched ARTEAGA by the word Carteia in a long note", 53: "right"}


def main():
    d = json.loads((HERE / "sample46.json").read_text(encoding="utf-8"))
    assert len(d) == len(V), (len(d), len(V))
    con = connect()
    now = time.strftime("%Y-%m-%d %H:%M")
    con.execute("DELETE FROM link_checks WHERE checked_by = 'agent-46'")
    for i, x in enumerate(d):
        x["verdict"] = V[i]
        con.execute("INSERT INTO link_checks VALUES (?,?,?,?,?,?,?,?)",
                    (x["from_kind"], x["from_id"], x["target_kind"], x["target_id"], V[i].split(":")[0].split(" (")[0],
                     V[i], "agent-46", now))
    con.commit()
    (HERE / "sample46_checked.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    c = Counter((x["method"], x["verdict"].split(":")[0].split(" (")[0]) for x in d)
    for k, v in sorted(c.items()):
        print(k, v)


if __name__ == "__main__":
    main()
