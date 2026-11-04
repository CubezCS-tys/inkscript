"""A1 step 3: match every cited work against Mandumah's catalogue (marc.db), harder than link47.

For each cited work: two FTS queries (title words OR-ed, ranked by bm25; author surname AND title words), the union
of candidates (≤ 60) scored on title (Dice / sequence ratio against title, title+subtitle, English and parallel
titles), authors (shared uncommon name word, either script; supervisors excluded), year (± 1, hijri converted),
journal name, volume / issue / first page, and type. The best candidate and its components are written to
out/a_cited_to_catalogue/matches.jsonl (resumable: works already there are skipped).
"""
import json, re, sys, time, difflib
sys.path.insert(0, "/home/appuser/inkscript/experiments/45_marc_db")
from build45 import fold  # noqa: E402
from q import marc, pv  # noqa: E402
from classify import classify  # noqa: E402

OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
STOP = set(fold(x) for x in """في من على عن الى إلى و او أو ثم مع بين حول نحو لدى لدي عند ذلك هذه هذا التي الذي التى الذى كما ما لا
 دراسة دراسه حالة حاله وصفية تحليلية تحليليه مقارنة مقارنه ميدانية ميدانيه نموذجا انموذجا أنموذجا بعض كل
 the of and in on for a an to with by at from al el la le les de des du et en un une der die und das an its as is are
 study case analysis""".split())
CAT_TYPE = {"journal_article": ("بحوث ومقالات",), "thesis": ("رسائل جامعية",), "conference_paper": ("بحوث المؤتمرات", "بحوث ومقالات")}
_freq = dict(json.load(open(OUT + "name_token_freq.json", encoding="utf-8"))["top"])
COMMON = {t for t, n in _freq.items() if n >= 8000} | {"ابن", "بن", "ابو", "بنت", "عبد", "ال", "al", "el", "ibn", "abu", "bin", "د", "ا", "م"}
LATIN = re.compile(r"[A-Za-zÀ-ÿ]")


def toks(s):
    s = fold(s or "")
    s = re.sub(r"[^\w\s]", " ", s)
    out = []
    for t in s.split():
        if t.isdigit() or len(t) < 2:
            continue
        if re.match(r"^(وال|بال|فال|كال|لل)", t) and len(t) > 5:
            t = t[3:] if not t.startswith("لل") else t[2:]
        elif t.startswith("ال") and len(t) > 4:
            t = t[2:]
        elif t.startswith("و") and len(t) > 4 and t[1:2] != "ا":
            t = t[1:]
        if t.endswith("ه") and len(t) > 3:
            t = t[:-1]
        if t not in STOP:
            out.append(t)
    return out


def dice(a, b):
    a, b = set(a), set(b)
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def cover(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a) if a else 0.0


def join_abd(s):
    return re.sub(r"\b(عبد|ابو|أبو)\s+(\S)", r"\1\2", s)


def name_toks(s):
    s = join_abd(fold(s or ""))
    s = re.sub(r"[^\w\s]", " ", s)
    out = set()
    for t in s.split():
        if len(t) < 2:
            continue
        out.add(t)
        if t.startswith("ال") and len(t) > 4:
            out.add(t[2:])
    return out


def title_fields(w):
    ms = sorted(w["members"], key=lambda m: -len(m["printed"] or ""))
    p = next((m["parsed"] for m in ms if m["parsed"]), None) or {}
    t = p.get("article_title") or p.get("chapter_title")
    if not t and (p.get("pub_type") in ("book", "thesis", "other", "web") or not p.get("article_title")):
        t = p.get("source_title")
    t = t or w["title"]
    src = p.get("source_title") if (p.get("article_title") or p.get("chapter_title")) else None
    return t, src, p, ms[0] if ms else None


def year_of(s):
    m = re.search(r"(1[3-9]\d\d|20[0-3]\d)", fold(str(s or "")))
    if not m:
        return None
    y = int(m.group(1))
    return y


def cited_years(w, p):
    ys = set()
    if w.get("year_greg"):
        ys.add(int(w["year_greg"]))
    y = year_of(p.get("year"))
    if y:
        ys.add(round(y * 0.970229 + 621.5643) if y < 1500 else y)
    return ys


def num(s):
    m = re.search(r"\d+", fold(str(s or "")))
    return int(m.group(0)) if m else None


def fts_or(words):
    return " OR ".join('"' + x.replace('"', "") + '"' for x in words)


class Matcher:
    def __init__(self):
        self.m = marc()
        self.m.execute("CREATE VIRTUAL TABLE temp.v USING fts5vocab(main, fts, 'row')")
        self.df = {}

    def docfreq(self, t):
        if t not in self.df:
            r = self.m.execute("SELECT doc FROM temp.v WHERE term = ?", (t,)).fetchone()
            self.df[t] = r[0] if r else 0
        return self.df[t]

    def query_words(self, title):
        # the raw folded words (as indexed: FTS has no light stemming), rarest first, very common ones dropped
        ws = []
        for t in re.sub(r"[^\w\s]", " ", fold(title or "")).split():
            if len(t) < 3 or t.isdigit() or t in STOP:
                continue
            ws.append(t)
        ws = sorted(set(ws), key=lambda t: (self.docfreq(t), t))
        ws = [t for t in ws if 0 < self.docfreq(t) < 150000]
        return ws[:10]

    def candidates(self, title, authors):
        ws = self.query_words(title)
        if len(ws) < 2:
            return set(), ws
        cands = set()
        try:
            cands |= {r[0] for r in self.m.execute(
                "SELECT rowid FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT 40", ("title: (" + fts_or(ws) + ")",))}
        except Exception:
            pass
        for a in authors[:2]:
            nt = [t for t in name_toks(a) if t not in COMMON and len(t) >= 3 and self.docfreq(t) > 0][:2]
            if not nt:
                continue
            q = "authors: (" + " OR ".join('"' + t + '"' for t in nt) + ") AND title: (" + fts_or(ws) + ")"
            try:
                cands |= {r[0] for r in self.m.execute("SELECT rowid FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT 20", (q,))}
            except Exception:
                pass
        return cands, ws

    def score(self, rec, ct, csrc, cauth, cyears, p, cls):
        r = self.m.execute("SELECT rec, c999, title, subtitle, title_en, subtitle_en, parallel_titles, year_int, journal, "
                           "journal_en, journal_romanised, volume, issue, page_first, type FROM records WHERE rec = ?",
                           (rec,)).fetchone()
        (rec, c999, title, subtitle, title_en, subtitle_en, par, ry, jr, jen, jrom, vol, iss, pf, rtype) = r
        ctk = toks(ct)
        forms = [title, " ".join(x for x in (title, subtitle) if x), title_en,
                 " ".join(x for x in (title_en, subtitle_en) if x)] + (par or "").split(" | ")
        best_t = 0.0
        for f in forms:
            if not f:
                continue
            ft = toks(f)
            d = dice(ctk, ft)
            sr = difflib.SequenceMatcher(None, " ".join(ctk), " ".join(ft)).ratio()
            cv = cover(ctk, ft) if len(ctk) >= 4 else 0
            best_t = max(best_t, d, (d + sr) / 2, min(cv, 0.9) * (0.95 if len(ft) <= 2.2 * len(ctk) else 0.7))
        au = self.m.execute("SELECT name, latin, role FROM authors WHERE rec = ? ORDER BY seq", (rec,)).fetchall()
        rnames = set()
        for n, lat, role in au:
            if role and ("مشرف" in role or "محكم" in role or "مناقش" in role):
                continue
            rnames |= name_toks(n) | name_toks(lat)
        a_strong = a_weak = 0
        for a in cauth:
            sh = name_toks(a) & rnames
            if any(t not in COMMON and len(t) >= 3 for t in sh):
                a_strong += 1
            elif len(sh) >= 2:
                a_weak += 1
        author = None if not cauth or not rnames else (1.0 if a_strong else 0.5 if a_weak else 0.0)
        ydiff = min((abs(y - ry) for y in cyears), default=None) if ry else None
        year = None if ydiff is None else (1.0 if ydiff == 0 else 0.7 if ydiff == 1 else 0.2 if ydiff == 2 else 0.0)
        journal = None
        if csrc and (jr or jen or jrom):
            jt = [x for x in toks(csrc) if x not in ("مجل", "مجله", "journal", "revue", "review")]
            journal = max(dice(jt, [x for x in toks(j) if x not in ("مجل", "مجله", "journal", "revue", "review")])
                          for j in (jr, jen, jrom) if j) if jt else None
        vip = None
        cv_, ci_, cf_ = num(p.get("volume")), num(p.get("issue")), num(p.get("fpage"))
        hits = [x for x in ((cv_, num(vol)), (ci_, num(iss)), (cf_, pf)) if x[0] is not None and x[1] is not None]
        if hits:
            vip = sum(a == b for a, b in hits) / len(hits)
        tmatch = any(t in (rtype or "") for t in CAT_TYPE.get(cls, ()))
        return dict(rec=rec, c999=c999, title=title, subtitle=subtitle, title_en=title_en, year=ry, journal=jr or jen,
                    type=rtype, authors=[a[0] for a in au][:4], s_title=round(best_t, 3), s_author=author,
                    s_year=year, s_journal=None if journal is None else round(journal, 3),
                    s_vip=None if vip is None else round(vip, 2), type_ok=tmatch)


def total(c):
    s = 0.55 * c["s_title"]
    for k, wt in (("s_author", 0.2), ("s_year", 0.1), ("s_journal", 0.1), ("s_vip", 0.05)):
        s += wt * (0.5 if c[k] is None else c[k])
    return round(s, 3)


def main():
    done = set()
    try:
        for line in open(OUT + "matches.jsonl", encoding="utf-8"):
            done.add(json.loads(line)["cited_work_pk"])
    except FileNotFoundError:
        pass
    con = pv()
    citing = {}
    for stem, c999 in con.execute("SELECT d.stem, p.c999 FROM documents d JOIN publications p USING (pub_id)"):
        citing[stem] = c999
    M = Matcher()
    W = [json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")]
    t0 = time.time(); n = 0
    with open(OUT + "matches.jsonl", "a", encoding="utf-8") as f:
        for w in W:
            if w["cited_work_pk"] in done:
                continue
            cls, why = classify(w)
            ct, csrc, p, rep = title_fields(w)
            cauth = [a["printed"] for a in w["authors"] if a["printed"]] + [a["latin"] for a in w["authors"] if a["latin"]]
            if not cauth:
                cauth = [" ".join(x for x in a if x) for a in (p.get("authors") or []) if isinstance(a, list)]
            own = {citing.get(m["stem"]) for m in w["members"]}
            cands, ws = M.candidates(ct, cauth)
            cyears = cited_years(w, p)
            scored = []
            for rec in cands:
                c = M.score(rec, ct, csrc, cauth, cyears, p, cls)
                if c["c999"] in own:
                    continue
                c["total"] = total(c)
                scored.append(c)
            scored.sort(key=lambda c: (-c["total"], c["rec"]))
            f.write(json.dumps(dict(cited_work_pk=w["cited_work_pk"], cls=cls, title=ct, source=csrc, authors=cauth[:4],
                                    years=sorted(cyears), query=ws, n_cands=len(cands), top=scored[:3]),
                               ensure_ascii=False) + "\n")
            n += 1
            if n % 200 == 0:
                f.flush()
                print(f"{n} works, {time.time() - t0:.0f} s", flush=True)
    print("done", n, f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
