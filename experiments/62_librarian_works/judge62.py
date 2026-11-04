"""Experiment 62, step 3a: the judging unit — `judge(packet) -> verdicts`, a rule proposal replaced by the
librarian's call where one was needed (overrides62.json, each with its reason).

Verdict kinds
- per candidate pair of cards (merge packets): same_work | edition_of (same work, another printing / translation /
  tahqiq) | part_of (a volume, chapter or part of the other) | different_work | unsure
- per card: split_card (its members are 2+ works: groups given) | card_ok (one work after all) |
  not_a_work (the Quran, a journal / newspaper / series named alone, unpublished data, a bare web site; with what to
  do: `drop` from work counts, or `one_per_citation` — each citation is its own work whose title the reader missed)
- per card and catalogue record: links_to_publication (Mandumah publication X) | relation (a review / study of it,
  not the work) | no_link
Every verdict has: reason, confidence (high / medium / low), basis (rule | catalogue | world | context |
judgement), trivial (the rule's own proposal stood).

    python3 judge62.py view merge 0 [size]     # the packets of batch 0 to read, with the rule proposals
    python3 judge62.py commit merge 0 [size]   # judge batch 0 and append its decisions
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from norm62 import GENERIC, tokens  # noqa: E402
from tools62 import cards, view_card  # noqa: E402

BATCH = 60
OVR = HERE / "overrides62.json"


def overrides() -> dict:
    return json.loads(OVR.read_text(encoding="utf-8")) if OVR.exists() else {}


def packets(kind: str | None = None) -> list[dict]:
    P = [json.loads(l) for l in open(OUT / "packets62.jsonl", encoding="utf-8")]
    return [p for p in P if kind is None or p["kind"] == kind]


def batch(kind: str, b: int, size: int = BATCH) -> list[dict]:
    P = packets(kind)
    if kind == "catalogue":
        P = [p for p in P if p["proposal"] != "accept"] if b >= 0 else [p for p in P if p["proposal"] == "accept"]
        b = abs(b) - (1 if b < 0 else 0) if b < 0 else b
    return P[b * size:(b + 1) * size]


# ------------------------------------------------------------------ rule proposals
def _years(c):
    out = set()
    for m in c["members"]:
        y = (m["parsed"] or {}).get("year")
        for x in re.findall(r"[0-9٠-٩]{4}", str(y or "")):
            out.add(int(x.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))))
    return out


def propose_edge(e: dict) -> dict:
    C = cards()
    A, B = C[e["a"]], C[e["b"]]
    t, au = e["title"], e["author"]
    types = set(e["types"])
    d, cov, ns = t["dice"], t["cover"], t["n_short"]
    generic = ns <= 1 and any(w in GENERIC for w in tokens(t["ta"]) + tokens(t["tb"]))
    articles = types <= {"journal", "confproc"}
    other_journal = articles and e.get("container") is not None and e["container"] < 0.5
    ya, yb = _years(A), _years(B)
    ydiff = bool(ya and yb and not any(abs(x - y) <= 1 for x in ya for y in yb))
    if other_journal and d < 0.95:
        return dict(kind="different_work", confidence="medium", basis="rule",
                    reason="two journal articles with alike titles in different journals")
    if d >= 0.85 or (cov >= 0.99 and ns >= 3 and t["prefix"]):
        if au in ("agree", "translit"):
            if ydiff and types <= {"book", "chapter"}:
                return dict(kind="edition_of", confidence="high", basis="rule",
                            reason="same title and author, another year: another printing of the book")
            return dict(kind="same_work", confidence="high" if not ydiff else "medium", basis="rule",
                        reason="same title (folded, misprints forgiven) and the same author"
                               + ("; the years differ" if ydiff else ""))
        if au == "unknown":
            if ns >= 3 and not generic and d >= 0.95:
                return dict(kind="same_work", confidence="medium", basis="rule",
                            reason="the same long title; one side prints no author")
            return dict(kind="unsure", confidence="low", basis="rule",
                        reason="a short title and no author on one side: could be any work of that name")
        return dict(kind="different_work", confidence="medium", basis="rule",
                    reason="the same title but different authors")
    if au in ("agree", "translit") and cov >= 0.99 and (t["prefix"] or A["short_only"] or B["short_only"]):
        return dict(kind="same_work", confidence="medium", basis="rule",
                    reason="the short title is the start of the long one (or a short form standing alone), same "
                           "author: a short form of the title")
    if e["rule"].startswith("B5"):
        return dict(kind="unsure", confidence="low", basis="rule",
                    reason="a one-word short form standing alone, no author: cannot tell by rule")
    conf = "high" if d < 0.5 else "medium" if d < 0.7 else "low"
    return dict(kind="different_work", confidence=conf, basis="rule",
                reason="alike titles but not the same title")


def propose_split(p: dict) -> dict:
    if "two author sets with nothing in common" in p["why"]:
        return dict(kind="split_card", confidence="medium", basis="rule", groups=p["author_groups"],
                    no_author=p["no_author"], reason="members print authors with nothing in common")
    return dict(kind="unsure", confidence="low", basis="rule",
                reason="joined through citations with no author: cannot tell by rule")


def _sig(m: dict) -> tuple:
    p = m["parsed"] or {}
    au = (p.get("authors") or [[""]])[0]
    sur = (au[0] if isinstance(au, list) and au else "") or ""
    return (sur.strip(), str(p.get("year") or "").strip())


def propose_notwork(p: dict) -> dict:
    c = cards()[p["cards"][0]]
    if p["why"] == "journal or newspaper named alone":
        ms = c["members"]
        long_ = [m for m in ms if len((m["printed"] or "")) > len(c["title"] or "") + 40]
        sigs = {_sig(m) for m in ms}
        if len(ms) >= 2 and len(sigs) == 1 and all(sigs.pop()):
            return dict(kind="not_a_work", action="retitle", confidence="medium", basis="rule",
                        reason="the card's title is the journal's name; its citations are one item (same author and "
                               "year) whose own title the reader missed: one work, wrongly titled")
        if len(ms) == 1 and long_:
            return dict(kind="not_a_work", action="retitle", confidence="medium", basis="rule",
                        reason="the card's title is the journal's name; the citation is an article whose title the "
                               "reader missed: one work, wrongly titled")
        if len(ms) >= 2 and len(long_) == len(ms):
            return dict(kind="not_a_work", action="one_per_citation", confidence="medium", basis="rule",
                        reason="the card's title is the journal's name; its citations are different articles whose "
                               "titles the reader missed")
        return dict(kind="not_a_work", action="drop", confidence="medium", basis="rule",
                    reason="a journal or newspaper named alone (an issue, a date): a serial citation, not a work")
    if p["why"] == "quran":
        return dict(kind="card_ok", confidence="low", basis="rule", reason="a title naming the Quran, not the Quran")
    return dict(kind="unsure", confidence="low", basis="rule", reason=p["why"])


def propose_catalogue(p: dict) -> dict:
    if p["proposal"] == "accept":
        return dict(kind="links_to_publication", confidence="high", basis="catalogue", target=p["best"],
                    reason=f"catalogue match ({p['why']})")
    if p["proposal"] == "read-article":
        return dict(kind="unsure", confidence="low", basis="rule", target=dict(c999=p["target_c999"], stem=p["target_stem"],
                                                                                 title=p["target_title"]),
                    reason="the cited title is one of the 780 articles' titles")
    if p["proposal"] == "relation":
        return dict(kind="relation", confidence="medium", basis="catalogue", target=p["best"], reason=p["why"])
    return dict(kind="no_link", confidence="low", basis="rule", target=p["best"], reason=p["why"])


def judge(p: dict, ovr: dict) -> list[dict]:
    """The verdicts of one packet: one per edge (merge), one per card (split, notwork, catalogue)."""
    out = []
    if p["kind"] == "merge":
        for e in p["edges"]:
            k = f"{e['a']}|{e['b']}"
            v = propose_edge(e)
            v["trivial"] = True
            if k in ovr:
                v = dict(v, **ovr[k], trivial=ovr[k].get("kind", v["kind"]) == v["kind"] and "reason" not in ovr[k])
            out.append(dict(v, qkey=f"pair|{k}", edge=e))
        have = {f"{e['a']}|{e['b']}" for e in p["edges"]}
        cs = set(p["cards"])
        for k, o in sorted(ovr.items()):
            a, _, b = k.partition("|")
            if k not in have and a in cs and b in cs and o.get("extra"):
                out.append(dict(o, trivial=False, qkey=f"pair|{k}", edge=dict(a=a, b=b, rule="found while judging")))
        return out
    key = p["key"]
    v = dict(split=propose_split, notwork=propose_notwork, catalogue=propose_catalogue)[p["kind"]](p)
    v["trivial"] = True
    if key in ovr:
        o = ovr[key]
        v = dict(v, **o, trivial=o.get("kind", v["kind"]) == v["kind"] and "reason" not in o)
    out.append(dict(v, qkey=key))
    return out


# ------------------------------------------------------------------ the view the librarian reads
def view(kind: str, b: int, size: int = BATCH) -> str:
    ovr = overrides()
    lines = []
    for i, p in enumerate(batch(kind, b, size)):
        lines.append(f"=== {b}.{i} {p['key']}" + (" (cut edge)" if p.get("cut_edge") else ""))
        for cid in p["cards"]:
            lines.append(view_card(cid, n_members=1, width=130))
        if kind == "merge":
            for e, v in zip(p["edges"], judge(p, ovr)):
                t = e["title"]
                lines.append(f"   ~ {e['a']}-{e['b']} {e['rule'][:3]} d{t['dice']} c{t['cover']} n{t['n_short']} "
                             f"au:{e['author']} y:{e['year']} -> {v['kind']} ({v['confidence']})"
                             + (" *" if not v["trivial"] else ""))
        elif kind == "split":
            lines.append(f"   why: {p['why']} groups={len(p['author_groups'])} no_author={len(p['no_author'])}")
            lines.append(f"   -> {judge(p, ovr)[0]['kind']}")
        elif kind == "notwork":
            lines.append(f"   why: {p['why']} -> {judge(p, ovr)[0]['kind']} {judge(p, ovr)[0].get('action', '')}")
        elif kind == "catalogue":
            x = p.get("best") or {}
            if p["proposal"] == "read-article":
                lines.append(f"   READ {p['target_stem']}: {p['target_title']} (d{p['s_title']})")
            else:
                for y in (p.get("top") or [])[:2]:
                    lines.append(f"   cat {y['c999']} {y['type']} «{y['title']}{(' : ' + y['subtitle']) if y.get('subtitle') else ''}»"
                                 f" {y['authors'][:2]} {y['year']} {y.get('journal') or ''} | t{y['s_title']} a{y['s_author']} "
                                 f"y{y['s_year']} j{y['s_journal']}")
            v = judge(p, ovr)[0]
            lines.append(f"   -> {p['proposal']} => {v['kind']} ({v['confidence']})" + (" *" if not v["trivial"] else ""))
    return "\n".join(lines)


def main():
    cmd, kind, b = sys.argv[1], sys.argv[2], int(sys.argv[3])
    size = int(sys.argv[4]) if len(sys.argv) > 4 else BATCH
    if cmd == "view":
        print(view(kind, b, size))
    elif cmd == "commit":
        from decisions62 import commit_batch
        print(commit_batch(kind, b, size))


if __name__ == "__main__":
    main()
