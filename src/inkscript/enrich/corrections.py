"""Corrections from exact sources, judged on the ink, written into the text only (experiment 27; D13, D14, D21).

    props, skipped = propose(doc, quotes)          # a Quran quotation's verse word where Azure's reading differs
    entries = load(path); save(path, entries)      # <stem>.corrections.json: every decision, with why and who judged
    overlay(doc, marks, entries)                   # applied corrections into the reading the XML is written from

What is proposed. A word inside a Quran quotation (enrich/quran.py) that differs from its verse word by dots or
letters gets the verse's word as its proposed reading. The ink decides (enrich/judge.py, blind A/B); only the
judge's "this is what the print says" makes a proposal *accepted*, and only an accepted correction is applied.

What is not proposed (the author's own wording and the quotation's edges, experiment 20 and 27):
  wording      و/ف at the start (the author's choice of where to begin), a missing word, a word not in the verse,
               a different word, and a confident (>= 0.95) reading that differs only by a particle or ending added
               or dropped at the word's edge (آمنوا for آمن, كل for بكل: paraphrase, not ink)
  spelling     the print's orthography: final ة/ت (فطرة, Uthmani فطرت), ى/ي, داود/داوود, hamza seats and a bare
               hamza (مسؤولا/مسئولا, النبيئين), alef spellings; the reading is the same word, the ink is right
  edge         the first or last word of a quotation that is not close to its verse word (the alignment ran past
               the quotation: وقوله, a citation glued on), or a token with digits or a slash
  split        two reading words for one verse word: joining them would take the space away from ink that has
               one, and a glyph cannot be given no text (D13); the reading is left as it is

A merge (Azure read إلا ما شاء as one word, إلاماشاء) is proposed as one correction whose text holds the words
with their spaces: the ink is one box, so the PDF keeps one word's glyphs and the copied text gains the spaces.

The corrected text keeps the word's punctuation (﴿ ﴾ « ) . …) and takes the verse's letters; the verse's short
vowels too when Azure's reading was vowelled (Tanzil Simple, Quranic annotation signs dropped), its plain
letters (Tanzil Simple Clean) otherwise.
"""
from __future__ import annotations

import difflib
import json
import re
import time
import unicodedata
from pathlib import Path

from .quran import norm, noalef

CORE = "\u0621-\u064A\u0671-\u06D3\u064B-\u065F\u0670\u0640\u25CC"
_SPLIT = re.compile(f"^([^{CORE}]*)([{CORE}].*?[{CORE}]|[{CORE}])?([^{CORE}]*)$", re.S)
HARAKAT = re.compile("[ً-ْ]")
_KEEP_V = re.compile("[^ء-يً-ْ ]")          # vowelled verse word: letters and the eight harakat only
PARTICLES = "وفبلك"


def _parts(t: str) -> tuple[str, str, str]:
    m = _SPLIT.match(t)
    if not m or m.group(2) is None:
        return t, "", ""
    return m.group(1), m.group(2), m.group(3)


def ortho(s: str) -> str:
    """A key that forgets the print's orthography: hamza and its seats, alefs, final ة/ت/ه, ى/ي, doubled و/ي."""
    s = unicodedata.normalize("NFC", s)
    s = re.sub("[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640\u25CC]", "", s)
    s = s.translate(str.maketrans({"أ": "", "إ": "", "آ": "", "ٱ": "", "ء": "", "ؤ": "", "ئ": "", "ا": "",
                                   "ى": "ي", "ة": "ه"}))
    s = re.sub("[^ء-ي]", "", s)
    if s.endswith("ت"):
        s = s[:-1] + "ه"
    return re.sub("وو+", "و", re.sub("يي+", "ي", s))


def ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _edge_change(d: str, q: str) -> bool:
    """d and q differ only by letters added or dropped at the start (a particle) or the end (an ending)."""
    if d == q:
        return False
    short, long_ = sorted((d, q), key=len)
    i = long_.find(short)
    if i < 0 or not short:
        return False
    head, tail = long_[:i], long_[i + len(short):]
    return len(head) <= 2 and len(tail) <= 3 and (not head or all(c in PARTICLES for c in head))


def _split_like(core: str, verse_words: list[dict]) -> str | None:
    """Azure's own letters, with a space before the letter that starts each next verse word (a merge whose
    letters are right: the print's spelling is kept). Letters are lined up on the matching key (difflib)."""
    pos = [i for i, ch in enumerate(core) if norm(ch)]          # base letters that count in the key
    a = "".join(norm(core[i]) for i in pos)
    v = [norm(x["w"]) for x in verse_words]
    bounds, acc = [], 0
    for t in v[:-1]:
        acc += len(t)
        bounds.append(acc)
    ops = difflib.SequenceMatcher(None, a, "".join(v), autojunk=False).get_opcodes()
    cuts = []
    for b in bounds:
        for tag, i1, i2, j1, j2 in ops:
            if j1 <= b < j2 or (b == j2 and tag == "equal" and j2 == len("".join(v))):
                cuts.append(i1 + (b - j1 if tag == "equal" else min(b - j1, i2 - i1)))
                break
    if len(cuts) != len(bounds) or any(c <= 0 or c >= len(pos) for c in cuts) or cuts != sorted(set(cuts)):
        return None
    out, last = [], 0
    for c in cuts:
        out.append(core[last:pos[c]])
        last = pos[c]
    out.append(core[last:])
    return " ".join(out)


def corrected_text(was: str, verse_words: list[dict]) -> str:
    pre, core, post = _parts(was)
    if len(verse_words) > 1 and ortho(core) == ortho("".join(x["w"] for x in verse_words)):
        same = _split_like(core, verse_words)
        if same:
            return pre + same + post
    vowelled = bool(HARAKAT.search(core))
    words = [_KEEP_V.sub("", x["v"]).replace("\u0640", "") if vowelled else x["w"] for x in verse_words]
    return pre + " ".join(w for w in words if w) + post


def propose(doc: dict, quotes: list[dict]) -> tuple[list[dict], list[dict]]:
    """Proposals (one per word) and the differences not proposed, each with its category."""
    words = doc["words"]
    props, skipped = [], []

    def skip(qt, o, cat, why):
        skipped.append(dict(ref=qt["ref"], kind=o["kind"], category=cat, why=why,
                            ids=[words[i]["id"] for i in o["doc"]], reading=" ".join(words[i]["text"] for i in o["doc"]),
                            verse=" ".join(x["w"] for x in o["q"])))

    seen = set()
    for qt in quotes:
        ops = qt["ops"]
        for n, o in enumerate(ops):
            k = o["kind"]
            if k in ("exact", "spelling", "split", "joined"):
                continue
            if k in ("missing", "extra", "other"):
                if k == "missing" and o.get("_merged"):          # a verse word a merge took in
                    continue
                skip(qt, o, "wording", {"missing": "a verse word not in the reading (omitted by the author, or lost)",
                                        "extra": "a word not in the verse (the author's, or the quotation's edge)",
                                        "other": "a different word"}[k])
                continue
            if len(o["doc"]) != 1:
                skip(qt, o, "split", "two reading words for one verse word (D13)")
                continue
            i = o["doc"][0]
            w = words[i]
            if i in seen:
                continue
            dn, qn = norm(w["text"]), norm(o["q"][0]["w"])
            # a merge: this word and the verse words the alignment calls missing right after (or before) it
            qwords = list(o["q"])
            after = []
            for o2 in ops[n + 1:]:
                if o2["kind"] != "missing":
                    break
                after += o2["q"]
            before = []
            for o2 in reversed(ops[:n]):
                if o2["kind"] != "missing":
                    break
                before = o2["q"] + before
            best, best_r = qwords, ratio(dn, qn)
            for a in range(len(before) + 1):
                for b in range(len(after) + 1):
                    if not a and not b:
                        continue
                    cand = before[len(before) - a:] + qwords + after[:b]
                    r = ratio(dn, "".join(norm(x["w"]) for x in cand))
                    if r > best_r + 0.15:
                        best, best_r = cand, r
            merged = len(best) > 1
            if merged:
                if best_r < 0.75:
                    skip(qt, o, "edge", "one reading word against several verse words, not close enough")
                    continue
                for o2 in ops:
                    if o2["kind"] == "missing" and any(x in best for x in o2["q"]):
                        o2["_merged"] = True
            qn_all = "".join(norm(x["w"]) for x in best)
            first_last = n == 0 or n == len(ops) - 1
            if o.get("verdict") == "quotation choice (و/ف)":
                skip(qt, o, "wording", "و/ف at the start: where the author began the quotation")
                continue
            if re.search(r"[0-9٠-٩۰-۹/]", w["text"]):
                skip(qt, o, "edge", "a token with digits or a slash (a citation glued on)")
                continue
            if not merged and ortho(w["text"]) == ortho(" ".join(x["w"] for x in best)):
                skip(qt, o, "spelling", "the print's orthography (ة/ت, ى/ي, hamza seat, alef, و/ي doubled)")
                continue
            if len(dn) > 1.5 * len(qn_all) + 2:
                skip(qt, o, "edge", "the reading word is much longer than the verse word (words outside the verse)")
                continue
            if first_last and k != "dots" and best_r < 0.75:
                skip(qt, o, "edge", "the quotation's first or last word, not close to its verse word")
                continue
            conf = w["conf"] if w["conf"] is not None else 1.0
            if not merged and conf >= 0.95 and k != "dots" and (_edge_change(noalef(dn), noalef(qn_all))
                                                                or _edge_change(dn, qn_all)):
                skip(qt, o, "wording", "a confident reading that differs by a particle or ending (paraphrase)")
                continue
            if not merged and conf >= 0.95 and k != "dots" and best_r < 0.8:
                skip(qt, o, "wording", "a confident reading of a different word (the author's wording)")
                continue
            if norm(w["out"]) == qn_all and w["out"] != w["text"]:
                skip(qt, o, "spelling", "the PDF already carries the verse's word (Gemini's page-1 reading)")
                continue
            seen.add(i)
            text = corrected_text(w["text"], best)
            props.append(dict(
                id=w["id"], page=w["page"], box=[round(v, 1) for v in w["box"]], poly=[round(v, 1) for v in w["poly"]],
                was=w["out"], azure=w["text"], text=text, conf=w["conf"],
                kind="merge" if merged else k, source="quran", ref=f"{best[0]['s']}:{best[0]['a']}",
                sura_name=qt["sura_name"], verse_word=" ".join(x["v"] for x in best),
                quotation=qt["ref"], bracketed=qt["bracketed"], verse_pos=[[x["s"], x["a"], x["i"]] for x in best],
                why=("Azure joined the verse words into one" if merged else
                     f"differs from the verse word by {'dots only' if k == 'dots' else 'letters'}")))
    for qt in quotes:
        for o in qt["ops"]:
            o.pop("_merged", None)
    return props, skipped


# ---------------------------------------------------------------- the log beside the PDFs

def log_path(out_dir: Path, stem: str) -> Path:
    return Path(out_dir) / f"{stem}.corrections.json"


def load(path: Path) -> dict:
    """{"stem", "runs": [...], "corrections": [...]}. A legacy list (what `inkscript correct` wrote before
    2026-10-06) becomes manual corrections."""
    path = Path(path)
    if not path.exists():
        return dict(runs=[], corrections=[])
    d = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(d, list):
        return dict(runs=[], corrections=[dict(c, source=c.get("source", "manual"),
                                               status="applied" if c.get("applied") else "declined")
                                          for c in d])
    d.setdefault("runs", [])
    d.setdefault("corrections", [])
    return d


def save(path: Path, data: dict) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def key(c: dict) -> tuple:
    return (c.get("id") or f"{c['page']}:{','.join(str(round(v)) for v in c['box'])}", c["text"])


def merge(data: dict, props: list[dict]) -> list[dict]:
    """Add new proposals to the log; return the entries for this run's proposals (old decisions kept)."""
    have = {key(c): c for c in data["corrections"]}
    out = []
    for p in props:
        k = key(p)
        if k not in have:
            c = dict(p, status="proposed", proposed=time.strftime("%Y-%m-%d %H:%M:%S"))
            data["corrections"].append(c)
            have[k] = c
        out.append(have[k])
    return out


def overlay(doc: dict, marks: dict, entries: list[dict], quotes: list[dict] | None = None) -> int:
    """Applied corrections into the reading the JATS and ALTO are written from: the word's text becomes the
    corrected one and its mark `corrected` (the original kept as `other`); in the quotations, the corrected
    differences (and the verse words a merge took in) become `corrected` and stop counting as differing.
    Returns how many words changed."""
    from .trust import Mark
    by_id = {w["id"]: w for w in doc["words"]}
    n = 0
    fixed_idx, fixed_pos = set(), set()
    for c in entries:
        if c.get("status") != "applied" or c.get("id") not in by_id:
            continue
        w = by_id[c["id"]]
        fixed_idx.add(w["idx"])
        fixed_pos |= {tuple(p) for p in c.get("verse_pos", [])}
        if w["out"] != c["text"]:
            was = w["out"]
            w["out"] = c["text"]
            judge = c.get("judge") or {}
            w["corrected"] = dict(was=was, source=c.get("source"), ref=c.get("ref"), judge=judge.get("model"))
            marks[w["idx"]] = Mark("corrected", [], verse=c.get("verse_word"), other=was,
                                   source=f"{c.get('source')} {c.get('ref') or ''}".strip())
            n += 1
    done_kinds = ("exact", "spelling", "split", "joined", "corrected")
    for qt in quotes or []:
        for o in qt["ops"]:
            if o["kind"] in done_kinds:
                continue
            by_word = bool(o["doc"]) and all(i in fixed_idx for i in o["doc"])
            by_verse = not o["doc"] and bool(o["q"]) and all((x["s"], x["a"], x["i"]) in fixed_pos for x in o["q"])
            if by_word or by_verse:
                o["kind"], o["verdict"] = "corrected", None
        qt["differs"] = sum(o["kind"] not in done_kinds for o in qt["ops"])
        qt["corrected"] = sum(o["kind"] == "corrected" for o in qt["ops"])
    return n


def applied_entries(out_dir: Path, stem: str) -> list[dict]:
    return [c for c in load(log_path(out_dir, stem))["corrections"] if c.get("status") == "applied" and c.get("id")]


def reapply(out_dir: Path, stem: str, entries: list[dict]) -> dict:
    """Write applied corrections into the faithful PDFs (after a rebuild they are gone; otherwise a no-op)."""
    from ..pdf.correct import apply_corrections
    out_dir = Path(out_dir)
    res = {}
    cs = [dict(page=c["page"], box=c["box"], text=c["text"], id=c["id"], was=c["was"]) for c in entries]
    for name in (f"{stem}.pdf", f"{stem}_vector.pdf"):
        pdf = out_dir / name
        if cs and pdf.exists():
            shapes = out_dir / f"{stem}.shapes.json" if name == f"{stem}.pdf" else None
            done = apply_corrections(pdf, cs, shapes, log=False)
            res[name] = dict(written=sum(1 for d in done if d["applied"] and not d.get("already")),
                             already=sum(1 for d in done if d.get("already")),
                             declined=sum(1 for d in done if not d["applied"]))
    return res


# ---------------------------------------------------------------- inkscript fix

FLASH, PRO = "gemini-3.8-flash", "gemini-3.1-pro-preview"


def _report(out_dir: Path, stem: str) -> tuple:
    rp = Path(out_dir) / "native_pdf_report.json"
    if not rp.exists():
        return None, [], {}
    reps = json.loads(rp.read_text(encoding="utf-8"))
    return rp, reps, next((r for r in reps if r.get("doc") == stem), {})


def _verdict(v: str) -> str:
    return {"r1": "printed reading", "r2": "proposal", "neither": "neither", "unsure": "unsure"}.get(v, v)


def fix(out_dir: Path, stem: str, azure_json: Path, scan_pdf: Path, judge: str = "gemini", model: str = FLASH,
        confirm: str | None = PRO, apply: bool = False, cap: float = 1.0, spend_log: Path | None = None,
        cache: Path | None = None, echo=print) -> dict:
    """Propose corrections from exact sources, judge them on the ink, apply the accepted ones; idempotent (every
    decision is kept in <stem>.corrections.json and a judged proposal is never judged again) and logged.

    Statuses: proposed (not judged yet) -> candidate (the first judge picked the proposal; waits for the
    confirming judge) -> accepted (both picked it) -> applied (in both faithful PDFs, then the XML and trust PDFs);
    rejected (the first judge picked the printed reading as it is, or neither, or could not tell), disputed (the
    confirming judge did not agree), declined (the PDF could not take it, D13)."""
    from collections import Counter
    from . import enrich, verify as verify_enrich
    from .document import load as load_doc
    from .quran import check_document
    from ..pdf.correct import apply_corrections, verify_ink
    out_dir = Path(out_dir)
    rp, reps, rep = _report(out_dir, stem)
    pages = rep.get("pages", [])
    gemini_pages = {p["page"] for p in pages if p.get("text") == "gemini"}
    born_digital = {p["page"] for p in pages if str(p.get("text", "")).startswith("native-")}
    shapes = out_dir / f"{stem}.shapes.json"
    doc = load_doc(azure_json, shapes if shapes.exists() else None, gemini_pages)
    quotes = check_document(doc)
    props, skipped = propose(doc, quotes)
    props = [p for p in props if p["page"] not in born_digital]
    path = log_path(out_dir, stem)
    data = load(path)
    data["stem"] = stem
    entries = merge(data, props)
    run = dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), judge=judge, model=model if judge == "gemini" else None,
               confirm=confirm if judge == "gemini" else None, proposed=len(props),
               not_proposed=dict(Counter(s["category"] for s in skipped)), spend=0.0)
    if judge == "gemini":
        from .judge import Judge
        for stage, m, todo_status in (("judge", model, "proposed"), ("confirm", confirm, "candidate")):
            todo = [c for c in entries if c["status"] == todo_status]
            if not m or not todo:
                continue
            j = Judge(m, cache, spend_log, cap=cap, tag=f"{stage}:{stem}")
            echo(f"{stem}: {stage} {len(todo)} proposals with {m}, estimate ${j.estimate(len(todo)):.3f}, "
                 f"spent so far ${j.spent():.3f} of the ${cap} cap")
            items = [dict(id=f"{stem}:{c['id']}:{c['text']}", scan=scan_pdf, page=c["page"], box=c["box"],
                          r1=c["was"], r2=c["text"]) for c in todo]
            res = j.judge(items)
            run["spend"] += j.this_run
            for c, it in zip(todo, items):
                r = res.get(it["id"])
                if r is None:
                    continue                        # not judged (cap reached): stays as it was, for the next run
                c[stage] = dict(model=m, verdict=_verdict(r["verdict"]), text=r["text"], why=r["why"], A=r["A"],
                                B=r["B"], when=r.get("when"))
                if r["verdict"] == "r2":
                    c["status"] = "candidate" if stage == "judge" and confirm else "accepted"
                else:
                    c["status"] = "rejected" if stage == "judge" else "disputed"
            if j.stopped:
                break
    applied_now = []
    if apply:
        todo = [c for c in data["corrections"] if c.get("status") == "accepted" and c.get("id") and c.get("was")]   # this run's and earlier ones (or accepted by hand)
        main, vec = out_dir / f"{stem}.pdf", out_dir / f"{stem}_vector.pdf"
        before = {p: p.read_bytes() for p in (main, vec) if p.exists()}
        if todo:
            cs = [dict(page=c["page"], box=c["box"], text=c["text"], id=c["id"], was=c["was"]) for c in todo]
            results = {}
            for pdf in before:
                done = apply_corrections(pdf, cs, shapes if pdf == main else None, log=False)
                results[pdf.name] = {d.get("id"): d for d in done}
            for c in todo:
                per = {name: r.get(c["id"]) for name, r in results.items()}
                ok = bool(per) and all(d and d["applied"] for d in per.values())
                c["applied"] = {name: {k: d[k] for k in ("applied", "glyphs", "was", "reason", "already")
                                       if d and k in d} for name, d in per.items()}
                c["status"] = "applied" if ok else "declined"
                if ok:
                    c["applied_when"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    applied_now.append(c)
            touched = sorted({c["page"] for c in applied_now})
            run["ink"] = {}
            for pdf, b in before.items():
                v = verify_ink(b, pdf, touched)
                v["prefix_identical"] = pdf.read_bytes()[:len(b)] == b
                v["text_changed_only_on_corrected_pages"] = set(v["text_changed"]) <= set(touched)
                run["ink"][pdf.name] = v
        save(path, data)                            # the PDFs carry them now: the XML and trust PDFs follow
        has_xml = (out_dir / f"{stem}.alto.xml").exists()
        has_trust = any((out_dir / n).exists() for n in (f"{stem}_trust.pdf", f"{stem}_vector_trust.pdf"))
        if applied_now and (has_xml or has_trust):
            e = enrich(stem, azure_json, scan_pdf, out_dir, rep or {"pages": []}, xml=has_xml, trust=has_trust)
            run["enrich_problems"] = verify_enrich(stem, out_dir, e)
            run["trust"] = e["trust"]
            if rp and rep:
                rep["enrich"] = e
                rp.write_text(json.dumps(reps, ensure_ascii=False, indent=1), encoding="utf-8")
    st = Counter(c.get("status") for c in data["corrections"])
    run.update(statuses=dict(st), applied_now=len(applied_now), spend=round(run["spend"], 4))
    data["runs"].append(run)
    save(path, data)
    return dict(run=run, entries=entries, skipped=skipped, log=str(path))
