"""Experiment 74 (from experiment 70's wordmodel70.py): the Word route's text-only model step for one journal (J).

Changes against exp 70 (its fix list): a reference list over 80 entries is sent in parts of 50 from the start (one
request per part, the headings with the first part; exp 70: one answer covered 73 of 292 entries, one hit MAX_TOKENS
on 162); failed answers (malformed JSON, MAX_TOKENS) are asked again automatically after each Batch job (Standard,
in smaller parts). Paths: out/J/wJ_code (code), out/J/wJ_model, out/J/wJ_final.


Code (build53, out/w0165_code/masters) already gives the text, footnotes, tables and lists exactly. What code cannot
judge (exp 53, measured): heading roles and levels (~10% wrong), reference fields beyond APA patterns, the document
type. One text-only call an article (no image; the words are the publisher's own and are never changed) sends:
  - every heading code made, with its level, its label and the first words of the text after it;
  - every reference-list entry, with its id;
  - the title and the opening of the body (for the document type).
and gets back only the heading changes, the parsed works W (prompt v3.6's PARSED REFERENCES schema, copied from
prompt43 verbatim) and the document type (prompt v3.6's list). Code applies them (apply): headings re-nested from a
flat outline, each W written by refs43.citation (every value checked to be a substring of the printed entry; a W that
loses everything keeps code's fields), doc type as meta43 writes it. Then DTD validation.

Model: gemini-3.8-flash (the cheapest exp 53 priced: $0.375 / $1.875 per M tokens on Batch until 2026-12-31),
thinking low. Spend rows go to experiment 43's log (one log for the whole cap).

    wordmodel74.py J requests [stems]          -> out/J/wJ_model/requests/<rid>.json (no calls; rid = stem or stem__pK)
    wordmodel74.py J pilot --n 5 --cap USD     Standard calls for a seeded sample (seed 7420): the quality check
    wordmodel74.py J batch --cap USD           one Batch job for every request not answered yet, then retry
    wordmodel74.py J retry --cap USD           failed answers asked again on Standard, references in parts of 25
    wordmodel74.py J apply                     -> out/J/wJ_final/masters (+ apply.json), DTD validated
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import re
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
E43 = ROOT / "experiments" / "43_rehearsal"
sys.path.insert(0, str(E43))
sys.dont_write_bytecode = True
J = sys.argv[1]
JD = HERE / "out" / J
CODE = JD / f"w{J}_code" / "masters"
MW = JD / f"w{J}_model"
FINAL = JD / f"w{J}_final"
PART, SPLIT_OVER = 50, 80             # exp 70's issue 6: lists over 80 entries go in parts of 50 from the start
MODEL = "gemini-3.8-flash"
BATCH_PRICE = (0.375, 1.875)          # $ per M tokens in / out, Batch, until 2026-12-31 (exp 41's table, halved)
STD_PRICE = (0.75, 3.75)
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
MAX_OUT = 24000


def tx(e) -> str:
    return " ".join("".join(e.itertext()).split()) if e is not None else ""


def _between(s: str, a: str, b: str) -> str:
    i = s.index(a)
    j = s.index(b, i)
    return s[i:j].rstrip()


def schema_text() -> tuple[str, str]:
    import prompt43 as P
    s = P.PROMPT_V36.replace("{{", "{").replace("}}", "}")
    w = _between(s, "W = {\"type\"", "FOOTNOTE AND ENDNOTE CALLS")
    d = _between(s, "  doc_type      what the piece is", "  conference")
    return w, d


PROMPT = """You check the STRUCTURE of one article of an Arabic scholarly journal («{journal}», {year}). Its text is
the publisher's own Word file, so every word is right: NEVER change, correct, complete or translate a word. Code has
already built the article; you decide only three things code cannot.

1. HEADINGS. Under HEADINGS is every line code took as a heading, in reading order: its id, the level code gave it
   (1 = a main part of the article, 2 = a section inside it, 3 = a subsection), the line as printed, and after "→"
   the first words of what follows it. Say what each really is:
   - a real heading (it names the part that follows: مقدمة، مشكلة الدراسة، أهداف الدراسة، الإطار النظري، منهج
     الدراسة، النتائج، التوصيات، المراجع, a numbered or ordinal title such as «أولاً: ...», «1- ...»), at its true
     level in the article's outline: parts in the same series (أولاً، ثانياً، ثالثاً / 1، 2، 3) share one level; a
     numbered title under another heading is one level deeper; «1-2» deeper than «1»;
   - NOT a heading: a sentence that leads into a list or passage (often ending with «:» — «وتتمثل أهداف الدراسة
     فيما يلي:»), a quotation, a verse, a source or note line, a reference left in the body, a table or figure
     caption, a label inside a list, a line of a book review's details («دار النشر:», «سنة النشر:»), or an item of a
     list. For these give the role "paragraph", "list_item", "quote" or "caption".
   Answer ONLY for lines whose role or level should change: "headings": {{"h7": {{"role": "paragraph"}},
   "h3": {{"role": "heading", "level": 1}}}}. A heading code got right is left out.
2. REFERENCES. Under REFERENCES is every paragraph code took as an entry of the article's list of sources, with its
   id. For EVERY id give "parsed": the work(s) it cites, as W below; if the paragraph is not a reference entry at all
   (a heading, a note, a comment, a stray line), give [] for it.
   {w_schema}
3. DOCUMENT. "doc_type": one word from this list:
{d_schema}
   For a book review also give "reviewed": the reviewed book as one W (its values exact substrings of the text
   under OPENING).

Answer with JSON only: {{"doc_type": "research", "headings": {{...}}, "references": {{"w120": [W], "w121": [W]}},
"reviewed": W}} (leave out "reviewed" unless it is a book review; "headings": {{}} when every heading is right).

TITLE: {title}

OPENING:
{opening}

HEADINGS:
{headings}

REFERENCES:
{references}
"""


# ------------------------------------------------------------------------------------------------ requests
def article_parts(stem: str) -> dict:
    root = etree.parse(str(CODE / f"{stem}.jats.xml")).getroot()
    am = root.find("front/article-meta")
    title = tx(am.find("title-group/article-title"))
    journal = tx(root.find("front/journal-meta/journal-title-group/journal-title")) or ""
    year = tx(am.find("pub-date/year"))
    body = root.find("body")
    heads, opening = [], []
    if body is not None:
        for t in body.iter("title"):
            sec = t.getparent()
            if sec.tag != "sec" or not t.get("id"):
                continue
            lab = tx(sec.find("label"))
            nxt = []
            for ch in sec:
                if ch.tag in ("label", "title"):
                    continue
                s = tx(ch)
                if s:
                    nxt.append(s)
                if sum(map(len, nxt)) > 120:
                    break
            after = " ".join(nxt)[:120] or "(nothing: another heading follows)"
            heads.append(dict(id=t.get("id"), level=int(sec.get("disp-level") or 2),
                              text=((lab + " ") if lab else "") + tx(t), after=after))
        for p in body.iter("p"):
            s = tx(p)
            if s:
                opening.append(s)
            if sum(map(len, opening)) > 700:
                break
    refs = [dict(id=m.get("id"), text=tx(m)) for m in root.iter("mixed-citation") if m.get("id")]
    return dict(stem=stem, title=title, journal=journal, year=year, opening=" ".join(opening)[:800],
                headings=heads, references=refs)


def make_prompt(parts: dict) -> str:
    w, d = schema_text()
    hl = "\n".join(f"{h['id']} [{h['level']}] {h['text']} → {h['after']}" for h in parts["headings"]) or "(none)"
    rl = "\n".join(f"{r['id']}: {r['text']}" for r in parts["references"]) or "(none)"
    return PROMPT.format(journal=parts["journal"], year=parts["year"], w_schema=w, d_schema=d, title=parts["title"],
                         opening=parts["opening"], headings=hl, references=rl)


def stems_all() -> list[str]:
    return sorted(p.name[:-len(".jats.xml")] for p in CODE.glob("*.jats.xml"))


def est_tokens(prompt: str) -> int:
    return int(len(prompt) / 2.6 * 1.117)          # the project's rule (run43.estimate)


def max_out_for(parts: dict) -> int:
    return min(MAX_OUT, 2000 + 160 * len(parts["references"]) + 30 * len(parts["headings"]))


def split(parts: dict) -> list[tuple[str, dict]]:
    """(rid, parts) per request: the whole article, or for a list over SPLIT_OVER entries one request per PART
    entries (rid stem__p0, stem__p1 ...; the headings, title and opening go with every part, the headings are answered
    from the first only)."""
    refs = parts["references"]
    if len(refs) <= SPLIT_OVER:
        return [(parts["stem"], parts)]
    return [(f"{parts['stem']}__p{k // PART}", dict(parts, references=refs[k:k + PART],
                                                    headings=parts["headings"] if k == 0 else []))
            for k in range(0, len(refs), PART)]


def rids_all() -> list[str]:
    return sorted(p.name[:-len(".json")] for p in (MW / "requests").glob("*.json"))


def stem_of(rid: str) -> str:
    return rid.split("__p")[0]


def cmd_requests(stems):
    (MW / "requests").mkdir(parents=True, exist_ok=True)
    tot = Counter()
    for s in stems or stems_all():
        parts = article_parts(s)
        for rid, pp in split(parts):
            pr = make_prompt(pp)
            r = dict(pp, rid=rid, prompt=pr, est_in=est_tokens(pr), max_out=max_out_for(pp))
            (MW / "requests" / f"{rid}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
            tot["requests"] += 1
            tot["est_in"] += r["est_in"]
            tot["max_out"] += r["max_out"]
        tot["articles"] += 1
        tot["split_articles"] += len(parts["references"]) > SPLIT_OVER
        tot["headings"] += len(parts["headings"])
        tot["references"] += len(parts["references"])
    pin, pout = BATCH_PRICE
    exp_out = tot["references"] * 92 + tot["headings"] * 4 + tot["articles"] * 300
    print(dict(tot), f"batch: expected ~${tot['est_in'] / 1e6 * pin + exp_out / 1e6 * pout:.2f} "
          f"(output ~{exp_out:,} tokens), worst ${tot['est_in'] / 1e6 * pin + tot['max_out'] / 1e6 * pout:.2f}")


# ------------------------------------------------------------------------------------------------ calls
def _common():
    sys.path.insert(0, str(ROOT / "experiments" / "41_azure_structure"))
    import common as C
    C.OUT = E43 / "out"
    C.SPEND = E43 / "out" / "gemini_spend.jsonl"
    C.CACHE = E43 / "out" / "gemini_cache.jsonl"
    return C


def answer_file(stem):
    return MW / "answers" / f"{stem}.json"


def cmd_pilot(n: int, cap: float, seed: int = 7420):
    C = _common()
    C.CAP = cap
    stems = [s for s in rids_all()]
    pick = sorted(random.Random(seed).sample(stems, min(n, len(stems))))
    (MW / "answers").mkdir(parents=True, exist_ok=True)
    tot = 0.0
    for s in pick:
        if answer_file(s).exists():
            continue
        r = json.loads((MW / "requests" / f"{s}.json").read_text(encoding="utf-8"))
        info = {}
        ans, usd = C.gemini(r["prompt"], tag=f"w{J}_{s}", model=MODEL, max_out=r["max_out"], thinking="low",
                            est_in=r["est_in"], json_out=True, info=info)
        tot += usd
        print(f"  {s}: {info.get('finish')} in {info.get('tin')} out {info.get('tout')} ${usd:.4f}", flush=True)
        if ans is None:
            continue
        answer_file(s).write_text(json.dumps(dict(stem=s, mode="standard", model=MODEL, usd=usd, tin=info.get("tin"),
                                                  tout=info.get("tout"), finish=info.get("finish"), answer=ans),
                                             ensure_ascii=False, indent=1), encoding="utf-8")
    (MW / "pilot.json").write_text(json.dumps(dict(seed=seed, stems=pick), indent=1))
    print(f"pilot: {len(pick)} articles, ${tot:.3f}; log ${C.spent():.3f}")


def cmd_batch(cap: float, poll: int = 60):
    C = _common()
    from google.genai import types
    client = C._client()
    sf = MW / "batch_state.json"
    state = json.loads(sf.read_text()) if sf.exists() else dict(rounds=[])
    (MW / "answers").mkdir(parents=True, exist_ok=True)
    pin, pout = BATCH_PRICE
    while True:
        open_ = [r for r in state["rounds"] if not r.get("collected")]
        if open_:
            r = open_[0]
            while True:
                job = client.batches.get(name=r["job"])
                st = job.state.name if hasattr(job.state, "name") else str(job.state)
                print(f"  job {r['job']}: {st} {time.strftime('%H:%M')}", flush=True)
                if st in ("JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"):
                    break
                time.sleep(poll)
            if st == "JOB_STATE_SUCCEEDED":
                collect(C, client, job, r)
            r.update(collected=True, final_state=st, done=time.strftime("%Y-%m-%d %H:%M:%S"))
            sf.write_text(json.dumps(state, indent=1))
            continue
        todo = [s for s in rids_all() if not answer_file(s).exists() and
                not (MW / "answers" / f"{s}.failed.json").exists()]
        if not todo:
            print("nothing left to send; the failed ones are asked again (retry)")
            cmd_retry(cap)
            return
        room = cap - C.spent()
        lines, keys, worst = [], [], 0.0
        for s in todo:
            r = json.loads((MW / "requests" / f"{s}.json").read_text(encoding="utf-8"))
            w = r["est_in"] / 1e6 * pin + r["max_out"] / 1e6 * pout
            if worst + w > room:
                print(f"  cap: the job is cut at {len(lines)} of {len(todo)} (worst ${worst:.3f} of ${room:.3f} room)")
                break
            key = f"w{J}_{s}"
            lines.append(dict(key=key, request={"contents": [{"role": "user", "parts": [{"text": r["prompt"]}]}],
                                                "generationConfig": {"maxOutputTokens": r["max_out"],
                                                                     "responseMimeType": "application/json",
                                                                     "thinkingConfig": {"thinkingLevel": "LOW"}}}))
            keys.append(key)
            worst += w
        if not lines:
            print(f"STOP: the cap ${cap} leaves no room (spent ${C.spent():.3f})")
            return
        k = len(state["rounds"]) + 1
        bf = MW / "batch" / f"round{k}.jsonl"
        bf.parent.mkdir(parents=True, exist_ok=True)
        bf.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8")
        up = client.files.upload(file=str(bf), config=types.UploadFileConfig(display_name=f"w{J}-round{k}",
                                                                             mime_type="jsonl"))
        job = client.batches.create(model=MODEL, src=up.name, config={"display_name": f"w{J}-round{k}"})
        state["rounds"].append(dict(round=k, job=job.name, file=up.name, keys=keys, worst_usd=round(worst, 4),
                                    sent=time.strftime("%Y-%m-%d %H:%M:%S"), requests=len(lines)))
        sf.write_text(json.dumps(state, indent=1))
        print(f"  round {k}: {len(lines)} requests, worst ${worst:.3f}, job {job.name}", flush=True)


def collect(C, client, job, meta):
    pin, pout = BATCH_PRICE
    lines = client.files.download(file=job.dest.file_name).decode("utf-8").splitlines()
    n_ok = 0
    for row in (json.loads(s) for s in lines if s.strip()):
        key = row.get("key")
        stem = key[len(f"w{J}_"):]
        resp = row.get("response") or {}
        um = resp.get("usageMetadata") or {}
        tin = um.get("promptTokenCount") or 0
        think = um.get("thoughtsTokenCount") or 0
        tout = (um.get("candidatesTokenCount") or 0) + think
        usd = tin / 1e6 * pin + tout / 1e6 * pout
        cand = (resp.get("candidates") or [{}])[0]
        fin = str(cand.get("finishReason") or row.get("error") or "none")
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts") or [] if not p.get("thought"))
        if not (tin or tout) and resp:
            usd = meta["worst_usd"] / max(1, len(meta["keys"]))
        with open(C.SPEND, "a") as f:
            f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=MODEL, tag=key, tin=tin, tout=tout,
                                    think=think, usd=round(usd, 6), secs=None, finish=fin, mode="batch",
                                    total=round(C.spent() + usd, 4))) + "\n")
        ans = None
        if "MAX_TOKENS" not in fin and text.strip():
            try:
                ans = json.loads(text)
            except Exception:  # noqa: BLE001
                ans = None
        rec = dict(stem=stem, mode="batch", model=MODEL, usd=usd, tin=tin, tout=tout, finish=fin, job=job.name)
        if ans is None:
            (MW / "answers" / f"{stem}.failed.json").write_text(json.dumps(dict(rec, text=text[:20000]),
                                                                          ensure_ascii=False))
            continue
        answer_file(stem).write_text(json.dumps(dict(rec, answer=ans), ensure_ascii=False, indent=1), encoding="utf-8")
        n_ok += 1
    print(f"  collected {len(lines)} ({n_ok} usable); log ${C.spent():.3f}", flush=True)


def cmd_retry(cap: float, part: int = 25):
    """A failed answer (MAX_TOKENS; malformed JSON) asked again on Standard: the request's references in parts of
    `part`, the headings with the first part only; the parts' answers merged."""
    C = _common()
    C.CAP = cap
    for ff in sorted((MW / "answers").glob("*.failed.json")):
        s = ff.name[:-len(".failed.json")]
        if answer_file(s).exists():
            continue
        parts = json.loads((MW / "requests" / f"{s}.json").read_text(encoding="utf-8"))
        refs = parts["references"]
        merged, usd_all, ok = dict(headings={}, references={}), 0.0, True
        for k in range(0, max(1, len(refs)), part):
            pp = dict(parts, references=refs[k:k + part], headings=parts["headings"] if k == 0 else [])
            pr = make_prompt(pp)
            info = {}
            ans, usd = C.gemini(pr, tag=f"w{J}r_{s}_{k}", model=MODEL, max_out=MAX_OUT, thinking="low",
                                est_in=est_tokens(pr), json_out=True, info=info)
            usd_all += usd
            print(f"  {s} part {k}: {info.get('finish')} in {info.get('tin')} out {info.get('tout')} ${usd:.4f}", flush=True)
            if not isinstance(ans, dict):
                ok = False
                break
            if k == 0:
                merged.update({x: ans[x] for x in ("doc_type", "reviewed") if x in ans})
                merged["headings"] = ans.get("headings") or {}
            merged["references"].update(ans.get("references") or {})
        if ok:
            answer_file(s).write_text(json.dumps(dict(stem=s, mode="standard-retry", model=MODEL, usd=usd_all,
                                                      answer=merged), ensure_ascii=False, indent=1), encoding="utf-8")
    # an answer that left references out (one article gave 73 of 292): the missing ones asked in parts
    for af in sorted((MW / "answers").glob("*.json")):
        if af.name.endswith(".failed.json"):
            continue
        rec = json.loads(af.read_text(encoding="utf-8"))
        A = rec["answer"]
        if not isinstance(A, dict):
            continue
        rid = af.name[:-len(".json")]
        parts = json.loads((MW / "requests" / f"{rid}.json").read_text(encoding="utf-8"))
        have = A.get("references") or {}
        miss = [r for r in parts["references"] if r["id"] not in have]
        if len(miss) < 10:
            continue
        for k in range(0, len(miss), part):
            pp = dict(parts, references=miss[k:k + part], headings=[])
            pr = make_prompt(pp)
            info = {}
            ans, usd = C.gemini(pr, tag=f"w{J}m_{rid}_{k}", model=MODEL, max_out=MAX_OUT, thinking="low",
                                est_in=est_tokens(pr), json_out=True, info=info)
            print(f"  {rid} missing part {k}: {info.get('finish')} ${usd:.4f}", flush=True)
            if isinstance(ans, dict):
                have.update(ans.get("references") or {})
            rec["usd"] = (rec.get("usd") or 0) + usd
        A["references"] = have
        rec["completed_missing"] = len(miss)
        af.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"log ${C.spent():.3f}")


# ------------------------------------------------------------------------------------------------ apply
ROLE_TAG = {"paragraph": "p", "list_item": "p", "quote": "p", "caption": "p"}


def renest(body, changes: dict, st: Counter):
    """Flatten the body's sections into (heading | block) items, apply the heading changes, nest them again (a block
    always goes into the last open section, so no block follows a sub-section: JATS order holds)."""
    items = []

    def walk(el):
        for ch in list(el):
            if not isinstance(ch.tag, str):
                continue
            if ch.tag == "sec":
                t = ch.find("title")
                lab = ch.find("label")
                items.append(("H", int(ch.get("disp-level") or 2), t, lab, dict(ch.attrib)))
                for g in list(ch):
                    if g is t or g is lab:
                        continue
                    if g.tag == "sec":
                        walk_one(g)
                    elif isinstance(g.tag, str):
                        items.append(("B", g))
            else:
                items.append(("B", ch))

    def walk_one(sec):
        tmp = etree.Element("tmp")
        tmp.append(sec)
        walk(tmp)

    walk(body)
    for ch in list(body):
        body.remove(ch)
    out = []
    for it in items:
        if it[0] == "H" and it[2] is not None and it[2].get("id") in changes:
            c = changes[it[2].get("id")]
            role = str(c.get("role") or "heading")
            if role == "heading":
                lv = c.get("level")
                if isinstance(lv, int) and 1 <= lv <= 3 and lv != it[1]:
                    st["heading_level_changed"] += 1
                    it = ("H", lv) + it[2:]
                out.append(it)
            else:
                t, lab = it[2], it[3]
                p = etree.Element("p", id=t.get("id"))
                if role in ("quote", "caption", "list_item"):
                    p.set("content-type", role.replace("_", "-"))
                if lab is not None and tx(lab):
                    p.text = tx(lab) + " "
                p.text = (p.text or "") + (t.text or "")
                for g in t:
                    p.append(g)
                st[f"heading_to_{role}"] += 1
                out.append(("B", p))
        else:
            out.append(it)
    stack = [(0, body)]
    for it in out:
        if it[0] == "H":
            lv = it[1]
            while len(stack) > 1 and stack[-1][0] >= lv:
                stack.pop()
            attrs = dict(it[4])
            attrs["disp-level"] = str(lv)
            sec = etree.SubElement(stack[-1][1], "sec", attrs)
            if it[3] is not None:
                sec.append(it[3])
            if it[2] is not None:
                sec.append(it[2])
            stack.append((lv, sec))
        else:
            stack[-1][1].append(it[1])


def merged_answer(stem: str):
    """The article's answer: its one request's, or its parts' merged (doc type, reviewed and headings from the first
    part; references from every part). None when any part has no answer."""
    rids = [r for r in rids_all() if stem_of(r) == stem] or [stem]
    out = None
    for rid in sorted(rids, key=lambda x: int(x.split("__p")[1]) if "__p" in x else 0):
        af = answer_file(rid)
        A = json.loads(af.read_text(encoding="utf-8"))["answer"] if af.exists() else None
        if not isinstance(A, dict):
            return None
        if out is None:
            out = dict(A, references=dict(A.get("references") or {}))
        else:
            out["references"].update(A.get("references") or {})
    return out


def cmd_apply():
    import refs43
    import meta43
    from inkscript.enrich.jats import DOCTYPE
    from inkscript.enrich.schemas import validate_jats
    m = FINAL / "masters"
    m.mkdir(parents=True, exist_ok=True)
    res, tot = [], Counter()
    for s in stems_all():
        st = Counter()
        af = answer_file(s)
        tree = etree.parse(str(CODE / f"{s}.jats.xml"))
        root = tree.getroot()
        for side in CODE.glob(f"{s}.*"):            # sidecars (metachanges, pdfmap, media) unchanged
            if side.name.endswith(".jats.xml"):
                continue
            dst = m / side.name
            if side.is_dir():
                if not dst.exists():
                    shutil.copytree(side, dst)
            else:
                shutil.copy2(side, dst)
        A = merged_answer(s)
        if not isinstance(A, dict):
            st["no_answer"] += 1
            A = None
        if A:
            lang = root.get(XML_LANG) or "ar"
            body = root.find("body")
            hc = {k: v for k, v in (A.get("headings") or {}).items() if isinstance(v, dict)}
            known = {t.get("id") for t in root.iter("title") if t.get("id")}
            st["heading_changes_unknown_id"] += sum(1 for k in hc if k not in known)
            if body is not None and hc:
                renest(body, {k: v for k, v in hc.items() if k in known}, st)
            refs = A.get("references") or {}
            for mc in root.iter("mixed-citation"):
                i = mc.get("id")
                if i not in refs:
                    st["refs_not_answered"] += 1
                    continue
                ws_ = refs[i] if isinstance(refs[i], list) else [refs[i]]
                ws_ = [w for w in ws_ if isinstance(w, dict)]
                ref = mc.getparent()
                if not ws_:
                    st["refs_model_no_new_work"] += 1
                    for ec in ref.findall("element-citation"):
                        ref.remove(ec)
                    ref.set("specific-use", "no-new-work (gemini-3.8-flash: not a reference entry, or «مرجع سابق» / op. cit.)")
                    continue
                plain = " ".join("".join(mc.itertext()).split())
                c2 = Counter()
                ec = refs43.citation(ws_[0], plain, c2, lang)
                st.update({f"model_{k}": v for k, v in c2.items()})
                if ec is None:
                    st["refs_model_empty_code_kept"] += 1
                    continue
                old = ref.find("element-citation")
                st["refs_model_fields" if old is None else "refs_model_replaced_code"] += 1
                if old is not None:
                    ref.remove(old)
                ref.append(ec)
                if len(ws_) > 1:
                    st["refs_model_extra_works_not_written"] += len(ws_) - 1
            dt = str(A.get("doc_type") or "").strip().lower()
            am = root.find("front/article-meta")
            if dt in meta43.DOC_JATS:
                root.set("article-type", meta43.DOC_JATS[dt])
                ac = am.find("article-categories")
                if ac is not None:
                    sg = etree.SubElement(ac, "subj-group", {"subj-group-type": "document-type",
                                                             "specific-use": MODEL})
                    etree.SubElement(sg, "subject").text = dt
                st[f"doc_{dt}"] += 1
            rv = A.get("reviewed")
            if dt == "book_review" and isinstance(rv, dict):
                printed = " ".join(" ".join(root.find("body").itertext()).split()) if root.find("body") is not None else ""
                ec = refs43.citation(rv, printed, Counter(), lang)
                if ec is not None:
                    pr = etree.Element("product", {"product-type": "book"})
                    for ch in list(ec):
                        pr.append(ch)
                    pos = [i for i, c in enumerate(am) if c.tag in ("history", "permissions", "self-uri",
                                                                     "related-article", "abstract", "trans-abstract",
                                                                     "kwd-group", "funding-group", "conference",
                                                                     "counts", "custom-meta-group")]
                    am.insert(pos[0] if pos else len(am), pr)
                    st["reviewed_book"] += 1
        # source marks (structure-source; D36 page note)
        for cm in root.iter("custom-meta"):
            if tx(cm.find("meta-name")) == "structure-source" and A:
                cm.find("meta-value").text = (tx(cm.find("meta-value")) + "; then a text-only gemini-3.8-flash call "
                                              "(experiment 74, wordmodel74.py; no word changed): heading roles and "
                                              "levels, reference fields (every value a substring of the printed "
                                              "entry), document type")
        cmg = root.find("front/article-meta/custom-meta-group")
        if cmg is not None:
            cm = etree.SubElement(cmg, "custom-meta")
            etree.SubElement(cm, "meta-name").text = "page-numbers"
            etree.SubElement(cm, "meta-value").text = (
                "D36: the first printed page and the catalogue's page range are facts; the printed page of anything "
                "after the first page is an ESTIMATE (pdfmap printed_page_est), flagged as such")
        out = m / f"{s}.jats.xml"
        out.write_bytes(etree.tostring(root, encoding="UTF-8", xml_declaration=True, doctype=DOCTYPE,
                                       pretty_print=True))
        errs = validate_jats(out)
        st["valid" if not errs else "invalid"] += 1
        res.append(dict(stem=s, valid=not errs, errors=errs[:3], stats=dict(st)))
        tot.update(st)
    (FINAL / "apply.json").write_text(json.dumps(dict(totals=dict(tot), articles=res), ensure_ascii=False, indent=1))
    print(json.dumps(dict(tot), indent=1))
    bad = [r for r in res if not r["valid"]]
    print(len(res), "articles;", len(bad), "invalid", [(r["stem"], r["errors"][:1]) for r in bad[:5]])


if __name__ == "__main__":
    sys.argv.pop(1)                           # the journal (read above)
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["requests", "pilot", "batch", "retry", "apply"])
    ap.add_argument("stems", nargs="*")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--cap", type=float)
    a = ap.parse_args()
    if a.cmd == "requests":
        cmd_requests(a.stems)
    elif a.cmd == "pilot":
        cmd_pilot(a.n, a.cap)
    elif a.cmd == "batch":
        cmd_batch(a.cap)
    elif a.cmd == "retry":
        cmd_retry(a.cap)
    else:
        cmd_apply()
