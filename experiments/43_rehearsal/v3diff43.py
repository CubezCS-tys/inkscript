"""Experiment 43: prompt v3 against prompt v2 on the same articles (no model calls).

    v3diff43.py --v3 v3_test --v2 v2_55 --v2-masters out/v3_test/v2_now
        -> out/<v3>/v3_vs_v2.json + v3_vs_v2.txt

Both runs' answers go through today's rules and masters (the v2 masters rebuilt with today's code, so only the prompt
differs). Per article: block types (answers, after rules43) and the pages where a type's count changed; the v3
metadata fields (trans_titles, history, aff_parts) and figure descriptions; the JATS slots (coverage43.SLOTS); words
of the article (JATS body + front printed text + notes + references; catalogue text left out) and the words that
appear only in one; calls in the answers and calls linked; misprint flags and fixes.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coverage43 as CV  # noqa: E402
import masters43 as M43  # noqa: E402
from masters43 import ST, etree  # noqa: E402

OUT = HERE / "out"


def answers(run, a):
    out = []
    for x, y in ST.chunks(a):
        f = OUT / run / "rules" / f"{a['stem']}_c{x:03d}-{y:03d}.json"
        if f.exists():
            out.append(ST.jl(f))
    return out


def blocks(recs):
    per_page, tot = {}, Counter()
    figs, meta = [], {}
    calls = 0
    for r in recs:
        ans = r.get("answer") or {}
        if ans.get("metadata"):
            meta = ans["metadata"]
        for pg in ans.get("pages") or []:
            for b in pg.get("blocks") or []:
                t = b.get("type")
                tot[t] += 1
                per_page.setdefault(pg.get("page"), Counter())[t] += 1
                calls += len(b.get("calls") or [])
                if t == "figure":
                    figs.append(b.get("description"))
    return tot, per_page, figs, meta, calls


def article_words(path: Path) -> list[str]:
    r = etree.parse(str(path), etree.XMLParser(load_dtd=False, no_network=True)).getroot()
    for c in list(r.iter("custom-meta")):
        if (c.findtext("meta-name") or "") != "front-matter-block":
            c.getparent().remove(c)
    for e in r.xpath("//*[@specific-use='catalogue'] | //journal-meta | //article-categories | //article-id | "
                     "//notes | //tex-math | //alt-text | //history | //pub-date | //name | //contrib-id | //kwd-group"):
        if e.getparent() is not None:
            e.getparent().remove(e)
    for m in r.iter("{http://www.w3.org/1998/Math/MathML}math"):
        m.getparent().remove(m)
    w = " ".join(" ".join(r.itertext()).split())
    return re.findall(r"\w+", w)


def slots(path: Path) -> dict:
    r = etree.parse(str(path), etree.XMLParser(load_dtd=False, no_network=True)).getroot()
    return {name: len(r.xpath(xp)) for _, name, xp in CV.SLOTS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v3", default="v3_test")
    ap.add_argument("--v2", default="v2_55")
    ap.add_argument("--v2-masters", default=str(OUT / "v3_test" / "v2_now"))
    a = ap.parse_args()
    m3, m2 = OUT / a.v3 / "masters", Path(a.v2_masters)
    res, lines = {}, []
    for art in ST.sample():
        s = art["stem"]
        if not (m3 / f"{s}.jats.xml").exists():
            continue
        r3, r2 = answers(a.v3, art), answers(a.v2, art)
        t3, pp3, f3, meta3, c3 = blocks(r3)
        t2, pp2, f2, meta2, c2 = blocks(r2)
        pages_changed = {}
        for p in sorted(set(pp3) | set(pp2), key=lambda x: int(x or 0)):
            d = {k: pp3.get(p, Counter())[k] - pp2.get(p, Counter())[k] for k in set(pp3.get(p, {})) | set(pp2.get(p, {}))}
            d = {k: v for k, v in d.items() if v}
            if d:
                pages_changed[p] = d
        w3, w2 = article_words(m3 / f"{s}.jats.xml"), article_words(m2 / f"{s}.jats.xml")
        only3, only2 = Counter(w3) - Counter(w2), Counter(w2) - Counter(w3)
        st3 = json.loads((m3 / "stats" / f"{s}.json").read_text())
        st2 = json.loads((m2 / "stats" / f"{s}.json").read_text())
        sl3, sl2 = slots(m3 / f"{s}.jats.xml"), slots(m2 / f"{s}.jats.xml")
        usd = sum(r.get("usd") or 0 for r in r3)
        res[s] = dict(
            usd=round(usd, 4), tout=sum(r.get("tout") or 0 for r in r3), tout_v2=sum(r.get("tout") or 0 for r in r2),
            types_v3=dict(t3), types_v2=dict(t2), pages_changed=pages_changed,
            meta_v3={k: meta3.get(k) for k in ("trans_titles", "history", "authors", "abstract", "keywords")},
            figure_descriptions_v3=f3[:6], figure_descriptions_v2=f2[:6],
            words_v3=len(w3), words_v2=len(w2), only_v3=sum(only3.values()), only_v2=sum(only2.values()),
            only_v3_ex=[w for w, _ in only3.most_common(12)], only_v2_ex=[w for w, _ in only2.most_common(12)],
            calls_v3=c3, calls_v2=c2, linked_v3=st3.get("calls_linked"), linked_v2=st2.get("calls_linked"),
            slots_changed={k: (sl2[k], sl3[k]) for k in sl3 if sl3[k] != sl2[k]})
        x = res[s]
        lines.append(f"== {s}  ${x['usd']}  out tokens {x['tout']} (v2 {x['tout_v2']})")
        keys = sorted(set(t3) | set(t2))
        lines.append("  types v2→v3: " + ", ".join(f"{k} {t2[k]}→{t3[k]}" for k in keys if t2[k] != t3[k]))
        lines.append("  pages: " + "; ".join(f"p{p} " + " ".join(f"{k}{v:+d}" for k, v in d.items())
                                             for p, d in pages_changed.items()))
        lines.append(f"  words v2 {x['words_v2']} v3 {x['words_v3']}; only v3 {x['only_v3']} {x['only_v3_ex'][:8]}; "
                     f"only v2 {x['only_v2']} {x['only_v2_ex'][:8]}")
        lines.append(f"  calls v2 {c2}/{x['linked_v2']} linked, v3 {c3}/{x['linked_v3']} linked")
        lines.append("  slots v2→v3: " + "; ".join(f"{k} {u}→{v}" for k, (u, v) in x["slots_changed"].items()))
        lines.append(f"  v3 metadata: trans_titles {meta3.get('trans_titles')}; history {meta3.get('history')}; "
                     f"aff_parts {[au.get('aff_parts') for au in meta3.get('authors') or [] if isinstance(au, dict)]}")
        lines.append(f"  descriptions v3 {f3[:2]}  v2 {f2[:2]}")
    (OUT / a.v3 / "v3_vs_v2.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    (OUT / a.v3 / "v3_vs_v2.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
