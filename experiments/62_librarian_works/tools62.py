"""Experiment 62: the librarian's tools — what a person at the card catalogue would reach for.

- `Seen`: the "seen list" — the machine's cards (out/cards62.jsonl) plus the librarian's own standing decisions so far
  (out/decisions62.jsonl): search by title words (fuzzy), by author word, by id; which work a card now belongs to
  (union of the same-work decisions); which earlier decision touched a card.
- `evidence(card)`: the printed citations of a card, their article, the note they sit in, the ink anchor.
- `catalogue(q)`: search the catalogue drawer (out/catalogue/cat62.db, the Mandumah records that share words with
  some cited title) by words; `record(rec)`.
- `view_card(cid)`: one compact line block per card, as the librarian reads it.

    python3 tools62.py card C7H83S6DX4            # a card with its evidence
    python3 tools62.py find "لسان العرب"           # the seen list, by title words
    python3 tools62.py author منظور                # by author word
    python3 tools62.py cat "تاج العروس"            # the catalogue drawer
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from norm62 import name_words, title_sim, tokens  # noqa: E402

_cards = None


def cards() -> dict:
    global _cards
    if _cards is None:
        _cards = {json.loads(l)["cited_work_id"]: json.loads(l) for l in open(OUT / "cards62.jsonl", encoding="utf-8")}
    return _cards


def authors_of(c: dict) -> list[str]:
    out = [a["printed"] + (f" (ت {a['died']})" if a.get("died") else "") for a in c["authors"] if a.get("printed")]
    if not out:
        for m in c["members"]:
            for x in ((m["parsed"] or {}).get("authors") or []):
                if isinstance(x, list):
                    out.append(" ".join(y for y in x[::-1] if y))
            if out:
                break
    if not out:
        for m in c["members"]:
            for x in ((m["parsed"] or {}).get("editors") or []):
                if isinstance(x, list):
                    out.append("(ed.) " + " ".join(y for y in x[::-1] if y))
            if out:
                break
    return list(dict.fromkeys(out))[:4]


def years_printed(c: dict) -> list[str]:
    return sorted({str((m["parsed"] or {}).get("year")) for m in c["members"] if (m["parsed"] or {}).get("year")})[:4]


def view_card(cid: str, n_members: int = 2, width: int = 170) -> str:
    c = cards()[cid]
    eds = sorted({e["printed"] for e in c["editions"] if e.get("printed")})[:2]
    pubs = sorted({e["publisher"] for e in c["editions"] if e.get("publisher")})[:2]
    contrib = [f"{x['role'][:3]}:{x['printed']}" for x in c["contributors"]][:2]
    head = (f"  [{cid}] {c['pub_type']}/{c['lang']} «{c['title']}» | au: {'; '.join(authors_of(c)) or '-'} | "
            f"y: {','.join(years_printed(c)) or '-'} | {c['n_articles']} art/{c['n_mentions']} ment"
            + (" | SHORT-ONLY" if c["short_only"] else "")
            + (f" | ed: {'; '.join(eds)}" if eds else "") + (f" | pub: {'; '.join(pubs)}" if pubs else "")
            + (f" | {'; '.join(contrib)}" if contrib else ""))
    lines = [head]
    for m in c["members"][:n_members]:
        lines.append(f"      {m['stem'][:16]} {m['kind'][:4]}: {(m['printed'] or '').replace(chr(10), ' ')[:width]}")
    if len(c["members"]) > n_members:
        lines.append(f"      … {len(c['members']) - n_members} more members")
    return "\n".join(lines)


def evidence(cid: str) -> list[dict]:
    c = cards()[cid]
    arts = json.loads((OUT / "articles62.json").read_text(encoding="utf-8"))
    out = []
    for m in c["members"]:
        a = arts.get(m["stem"], {})
        out.append(dict(mention_id=m["mention_id"], stem=m["stem"], journal=a.get("journal"), year=a.get("year"),
                        article=a.get("title"), kind=m["kind"], container=m["container"], page=m["page"],
                        printed=m["printed"], note=m.get("note"), anchor=m["anchor"], parsed=m["parsed"]))
    return out


class Seen:
    """The card catalogue as the librarian sees it now: the machine's cards and the decisions made so far."""

    def __init__(self, decisions: list[dict] | None = None):
        self.C = cards()
        self.idx = defaultdict(set)
        self.aidx = defaultdict(set)
        for cid, c in self.C.items():
            for w in set(tokens(c["title"])):
                self.idx[w].add(cid)
            for a in c["authors"]:
                for w in name_words(a["printed"]):
                    self.aidx[w].add(cid)
        self.decisions = decisions or []
        self.by_card = defaultdict(list)
        for d in self.decisions:
            for k in d.get("subject_keys") or []:
                self.by_card[k].append(d)

    def find(self, title: str, n: int = 10) -> list[tuple]:
        ts = tokens(title)
        cand = set()
        for w in ts:
            cand |= self.idx.get(w, set())
        scored = [(title_sim(ts, tokens(self.C[c]["title"]))["dice"], c) for c in cand]
        return sorted(scored, reverse=True)[:n]

    def by_author(self, word: str) -> list[str]:
        out = set()
        for w in name_words(word):
            out |= self.aidx.get(w, set())
        return sorted(out)

    def earlier(self, cid: str) -> list[dict]:
        return self.by_card.get(cid, [])


def context(mention_id: str, width: int = 260) -> str | None:
    """The article's text just before the note call of the note a citation sits in (what «ديوانه» or «المرجع
    نفسه» refers to): read-only on the release."""
    import sqlite3 as _s
    from norm62 import release
    rel = release()
    con = _s.connect(f"file:{rel}?mode=ro", uri=True)
    r = con.execute("""SELECT m.version_id, m.container_id FROM citation_mentions m WHERE m.mention_id = ?""",
                    (mention_id,)).fetchone()
    if not r:
        return None
    vid, nid = r
    c = con.execute("""SELECT nc.block_id, nc.char_offset FROM note_call_targets t JOIN note_calls nc
                       ON nc.version_id = t.version_id AND nc.call_seq = t.call_seq
                       WHERE t.version_id = ? AND t.note_id = ?""", (vid, nid)).fetchone()
    if not c:
        return None
    b = con.execute("SELECT text FROM blocks WHERE version_id = ? AND block_id = ?", (vid, c[0])).fetchone()
    if not b or not b[0]:
        return None
    off = c[1] if c[1] is not None else len(b[0])
    return b[0][max(0, off - width):off] + " ⟨call⟩"


def catalogue(q: str, n: int = 8) -> list[dict]:
    k = sqlite3.connect(OUT / "catalogue" / "cat62.db")
    ts = tokens(q)
    if not ts:
        return []
    rows = k.execute("SELECT rec, c999, title, subtitle, year_int, type, journal, toks FROM recs WHERE " +
                     " AND ".join("(' ' || toks || ' ') LIKE ?" for _ in ts[:4]), [f"% {w} %" for w in ts[:4]]).fetchall()
    out = []
    for r in rows:
        s = title_sim(ts, r[7].split("|")[0].split())
        au = [x[0] for x in k.execute("SELECT name FROM auth WHERE rec = ? ORDER BY seq", (r[0],))]
        out.append(dict(rec=r[0], c999=r[1], title=r[2], subtitle=r[3], year=r[4], type=r[5], journal=r[6],
                        authors=au[:4], s_title=s["dice"]))
    return sorted(out, key=lambda x: -x["s_title"])[:n]


def main():
    cmd, arg = sys.argv[1], " ".join(sys.argv[2:])
    if cmd == "card":
        print(view_card(arg, n_members=50, width=400))
        for e in evidence(arg):
            if e["note"]:
                print("   note:", e["note"][:300])
    elif cmd == "ctx":
        for m in cards()[arg]["members"]:
            print(m["mention_id"], "::", context(m["mention_id"]))
    elif cmd == "find":
        S = Seen()
        for s, c in S.find(arg):
            print(s, view_card(c, 1))
    elif cmd == "author":
        S = Seen()
        for c in S.by_author(arg)[:30]:
            print(view_card(c, 1))
    elif cmd == "cat":
        for x in catalogue(arg):
            print(json.dumps(x, ensure_ascii=False))


if __name__ == "__main__":
    main()
