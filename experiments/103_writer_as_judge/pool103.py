"""Experiment 103: the sets (pre-registered rules; seed 103; every key through experiment 102's guard, unchanged).

    nice -n 19 ionice -c3 python3 pool103.py repair     -> out/sets/R.jsonl (fixed targets), R_cut.jsonl (Azure's labels,
                                                           for cut102's line check), devmix.jsonl, dev103.jsonl
    nice -n 19 ionice -c3 python3 pool103.py heldout    -> out/sets/heldout.jsonl: the held-out pool for job B
    nice -n 19 ionice -c3 python3 pool103.py b READER.jsonl [--adapter NAME]
                                                        -> out/b/: B1 and B2 test sets, writer jobs, blind-reader packets

REPAIR (job A3).  All 4,5xx lines of L_local whose target fix103 changes are split BY DOCUMENT (md5 of the stem,
seed 103): 80% of the documents give the repair's training lines, 20% give DEV-MIXED (never trained on in the
repair).  The repair set R = those affected lines with fixed targets + the same number of ordinary lines from M
(replay, so nothing else is forgotten): one third Arabic+Latin lines that fix103 leaves unchanged (already in
logical order: the reader must not start reordering everything), two thirds random M lines, era-matched to
the affected lines.  DEV-MIXED = the held-back affected lines (fixed targets) + as many unchanged Arabic+Latin
lines of the same documents (controls).  dev103 = experiment 102's DEV with fix103 applied to its labels (7 lines).
Every target keeps its label_source (train102's guard allows only the known sources); "target_fix": "fix103" marks
a changed one, "label_azure" keeps Azure's.

HELD-OUT POOL (job B).  Lines of the 55 DEV documents that are NOT among DEV's 2,000 lines.  These documents are
outside every training set (S, M, L_local, R) and outside every locked set; they are the only such documents with
PDF + Azure on this server (experiment 83's documents would need S3 egress).  About 9,700 lines.

B SETS (after the reader has read the held-out pool on the host, with token log-probabilities):
  eligible: the line has no Latin letter (the writer has no bidi step and AlQalam no Latin: experiment 103's B0),
            Azure's label has at least 3 Arabic letters, and the reader did not hit the token limit.
  B1 REAL candidates: reader vs Azure "far": word error (folded) >= 0.34 of Azure's words, or 2+ words in a row
            wrong, or the reader's text is 30%+ longer or shorter.  All of them go to the blind readers; after
            settling, a REAL gross error = the reader's reading is wrong against the settled truth by the same
            definition.  Lines where the settled truth is the reader's reading become CORRECT lines.
  B1 CORRECT: lines where the reader equals Azure exactly (after whitespace); 1,500 drawn (seed 103), 60 of them
            also go to the blind readers as controls (the agreed-but-wrong rate).
  B1 PLANTED: on 600 other correct lines: 300 "wrong plausible word" (one word of 3+ letters replaced by a word of
            the pool vocabulary with the same first letter and length +-1, seed 103) and 300 "missing word" (one word
            of 3+ letters removed, not the first or last).
  B2 J: lines where the reader and Azure disagree, NOT B1 real candidates (folded word error < 0.34), eligible:
            300 drawn (seed 103), stratified by era as the pool; + 60 agreed control lines (from B1 CORRECT's
            controls).  Candidates shuffled (seed 103), origin hidden: experiment 97's disputes format.
Page styles: each page that has a B line gets its style from its first 3 CORRECT lines (reader = Azure) that are
not themselves test lines; pages with fewer than 3 such lines are left out and counted.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(E / "102_qwen_line_reader"))
import guard102  # noqa: E402
from fix103 import fix_line, AR_LETTER, LAT, DIG  # noqa: E402

S102 = E / "102_qwen_line_reader/out/sets"
POOL = E / "102_qwen_line_reader/out/pool/pool102.jsonl.gz"
OUT = HERE / "out/sets"
B = Path(os.environ.get("B103_OUT", HERE / "out/b"))
BLIND = Path(os.environ.get("BLIND103_OUT", HERE / "out/blind"))       # what the blind readers get (no origin)
SEED = 103
FAR = 0.34


def jl(p):
    op = gzip.open if str(p).endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as f:
        for l in f:
            if l.strip():
                yield json.loads(l)


def wjl(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def h(s: str) -> int:
    return int(hashlib.md5(f"{SEED}|{s}".encode()).hexdigest()[:8], 16)


def mixed_latin(s):
    return bool(AR_LETTER.search(s)) and bool(LAT.search(s))


def repair():
    rng = random.Random(SEED)
    L = list(jl(S102 / "L_local.jsonl"))
    affected, unchanged_mixed = [], []
    for r in L:
        new, info = fix_line(r["label"])
        if info["changed"]:
            affected.append(dict(r, label=new, label_azure=r["label"], target_fix="fix103", fix_kinds=info["kinds"]))
        elif mixed_latin(r["label"]):
            unchanged_mixed.append(r)
    held_docs = {r["stem"] for r in affected if h(r["stem"]) % 100 < 20}
    aff_train = [r for r in affected if r["stem"] not in held_docs]
    aff_dev = [r for r in affected if r["stem"] in held_docs]
    M = [r for r in jl(S102 / "M.jsonl") if r["stem"] not in held_docs]
    Mkeys = {r["key"] for r in M}
    um_M = [r for r in unchanged_mixed if r["key"] in Mkeys]
    n = len(aff_train)
    rng.shuffle(um_M)
    replay = um_M[: n // 3]
    era_need = Counter(r["era"] for r in aff_train)
    total = sum(era_need.values())
    by_era = defaultdict(list)
    taken = {r["key"] for r in replay}
    for r in M:
        if r["key"] not in taken and not r.get("title"):
            by_era[r["era"]].append(r)
    rest = n - len(replay)
    for e, c in era_need.items():
        k = round(rest * c / total)
        rng.shuffle(by_era[e])
        replay += by_era[e][:k]
    R = aff_train + replay
    rng.shuffle(R)
    controls = [r for r in unchanged_mixed if r["stem"] in held_docs]
    rng.shuffle(controls)
    devmix = [dict(r, devmix="fixed") for r in aff_dev] + [dict(r, devmix="control") for r in controls[: len(aff_dev)]]
    dev = []
    for r in jl(S102 / "dev.jsonl"):
        new, info = fix_line(r["label"])
        dev.append(dict(r, label=new, label_azure=r["label"], target_fix="fix103") if info["changed"] else r)
    for name, rows in (("R", R), ("devmix", devmix), ("dev103", dev)):
        guard102.assert_trainable([r["key"] for r in rows])
        guard102.assert_sources([r["label_source"] for r in rows])
    assert not ({r["key"] for r in R} & {r["key"] for r in devmix}), "repair and DEV-MIXED overlap"
    assert not ({r["stem"] for r in R} & held_docs), "a DEV-MIXED document in R"
    wjl(OUT / "R.jsonl", R)
    wjl(OUT / "R_cut.jsonl", [dict(r, label=r.get("label_azure", r["label"])) for r in R])
    wjl(OUT / "devmix.jsonl", devmix)
    wjl(OUT / "devmix_cut.jsonl", [dict(r, label=r.get("label_azure", r["label"])) for r in devmix])
    wjl(OUT / "dev103.jsonl", dev)
    summ = dict(affected_L_local=len(affected), affected_documents=len({r["stem"] for r in affected}),
                held_back_documents=len(held_docs), R=len(R), R_affected=len(aff_train), R_replay=len(replay),
                R_replay_mixed_unchanged=min(len(um_M), n // 3), R_by_era=dict(Counter(r["era"] for r in R)),
                devmix=len(devmix), devmix_fixed=len(aff_dev), devmix_controls=len(devmix) - len(aff_dev),
                dev103_changed=sum(1 for r in dev if r.get("target_fix")),
                kinds_R=dict(Counter(k for r in aff_train for k in r["fix_kinds"])))
    (OUT / "repair103_summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


def heldout():
    dev = list(jl(S102 / "dev.jsonl"))
    dev_keys = {r["key"] for r in dev}
    docs = {r["stem"] for r in dev}
    train_docs = {r["stem"] for r in jl(S102 / "L_local.jsonl")}
    assert not (docs & train_docs)
    rows = []
    for d in jl(POOL):
        if d["stem"] in docs and d["key"] not in dev_keys and not d.get("title"):
            rows.append({k: d[k] for k in ("key", "stem", "page", "i", "jcode", "year", "era", "src", "label",
                                           "label_source", "title", "display", "kind")})
    guard102.assert_trainable([r["key"] for r in rows])
    wjl(OUT / "heldout.jsonl", rows)
    print(len(rows), "held-out lines from", len({r["stem"] for r in rows}), "documents;",
          dict(Counter(r["era"] for r in rows)))


# ------------------------------------------------------------------------------------------------ B sets

def fold(s: str) -> str:
    """Experiment 97's fold for comparing readings (score97.r1_fold), imported where available."""
    try:
        sys.path.insert(0, str(E / "97_extraction_evals"))
        import score97
        return score97.r1_fold(" ".join(s.split()))
    except Exception:                                  # noqa: BLE001  (fallback: NFC + whitespace)
        return unicodedata.normalize("NFC", " ".join(s.split()))


def word_ops(a: list[str], b: list[str]):
    """Levenshtein alignment of word lists a (reference) -> b; returns per-reference-word ok flags and #insertions."""
    n, m = len(a), len(b)
    D = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        D[i][0] = i
    for j in range(m + 1):
        D[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    ok, ins, i, j = [False] * n, 0, n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and D[i][j] == D[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            ok[i - 1] = a[i - 1] == b[j - 1]
            i, j = i - 1, j - 1
        elif i > 0 and D[i][j] == D[i - 1][j] + 1:
            i -= 1
        else:
            ins += 1
            j -= 1
    return ok, ins, D[n][m]


def gross(ref: str, hyp: str) -> bool:
    """The pre-registered "far" test (B1): folded word error >= 0.34 of the reference's words, or 2+ reference words
    in a row wrong, or the hypothesis 30%+ longer or shorter (letters)."""
    a, b = fold(ref).split(), fold(hyp).split()
    if not a:
        return bool(b)
    ok, ins, dist = word_ops(a, b)
    run = best = 0
    for x in ok:
        run = 0 if x else run + 1
        best = max(best, run)
    la, lb = len("".join(a)), len("".join(b))
    return dist / len(a) >= FAR or best >= 2 or abs(lb - la) >= 0.3 * max(1, la)


def eligible(label: str, pred: dict) -> bool:
    return (not LAT.search(label) and not LAT.search(pred["text"]) and len(AR_LETTER.findall(label)) >= 3
            and pred.get("finish") != "length")


def plant(text: str, kind: str, vocab: dict, rng) -> str | None:
    ws = text.split(" ")
    idx = [i for i, w in enumerate(ws) if len(AR_LETTER.findall(w)) >= 3 and (kind == "sub" or 0 < i < len(ws) - 1)]
    if not idx:
        return None
    i = rng.choice(idx)
    if kind == "drop":
        return " ".join(ws[:i] + ws[i + 1:])
    w = ws[i]
    pool = [x for x in vocab.get(w[0], []) if abs(len(x) - len(w)) <= 1 and x != w]
    if not pool:
        return None
    return " ".join(ws[:i] + [rng.choice(pool)] + ws[i + 1:])


def b_sets(reader_path: str, adapter: str | None = None):
    rng = random.Random(SEED)
    rows = {r["key"]: r for r in jl(OUT / "heldout.jsonl")}
    pred = {}
    for d in jl(reader_path):
        if adapter is None or d.get("adapter") == adapter:
            pred[d["key"]] = d
    keys = sorted(k for k in rows if k in pred)
    c = Counter(lines=len(keys))
    correct, far, disagree = [], [], []
    for k in keys:
        lab, p = rows[k]["label"], pred[k]
        if not eligible(lab, p):
            c["not eligible (Latin, short, or token limit)"] += 1
            continue
        if " ".join(p["text"].split()) == " ".join(lab.split()):
            correct.append(k)
        elif gross(lab, p["text"]):
            far.append(k)
        else:
            disagree.append(k)
    c.update(correct=len(correct), b1_real_candidates=len(far), disagreements=len(disagree))
    rng.shuffle(correct)
    neg = correct[:1500]
    controls = neg[:60]
    plant_lines = correct[1500:2100]
    vocab = defaultdict(set)
    for k in keys:
        for w in rows[k]["label"].split():
            if len(AR_LETTER.findall(w)) >= 3 and all(AR_LETTER.match(ch) for ch in w):
                vocab[w[0]].add(w)
    vocab = {a: sorted(v) for a, v in vocab.items()}
    planted = []
    for t, k in enumerate(plant_lines):
        kind = "sub" if t < 300 else "drop"
        v = plant(rows[k]["label"], kind, vocab, rng)
        if v:
            planted.append(dict(key=k, kind=f"planted_{kind}", text=v, true=rows[k]["label"]))
    # B2: era-stratified as the pool
    by_era = defaultdict(list)
    for k in disagree:
        by_era[rows[k]["era"]].append(k)
    for v in by_era.values():
        rng.shuffle(v)
    share = Counter(rows[k]["era"] for k in keys)
    J = []
    for e, v in by_era.items():
        J += v[: round(300 * share[e] / len(keys))]
    J = J[:300]
    c.update(b1_correct=len(neg), b1_planted=len(planted), b2_J=len(J), controls=len(controls))
    # page styles: first 3 correct lines of the page that are not test lines
    test = set(neg) | set(far) | set(J) | {p["key"] for p in planted}
    pages = defaultdict(list)
    for k in correct:
        pages[(rows[k]["stem"], rows[k]["page"])].append(k)
    style_pages = {}
    for k in test:
        pg = (rows[k]["stem"], rows[k]["page"])
        if pg in style_pages:
            continue
        sl = [x for x in sorted(pages.get(pg, []), key=lambda x: rows[x]["i"]) if x not in test][:3]
        style_pages[pg] = sl
    no_style = {pg for pg, v in style_pages.items() if len(v) < 3}
    c["pages"] = len(style_pages)
    c["pages_without_3_style_lines"] = len(no_style)
    page_of = lambda k: (rows[k]["stem"], rows[k]["page"])               # noqa: E731
    # writer jobs: absolute check (B1 + both B2 readings) and contrastive groups (B2)
    jobs = []
    for k in neg:
        jobs.append(dict(id=f"{k}|correct", key=k, text=rows[k]["label"], kind="correct"))
    for k in far:
        jobs.append(dict(id=f"{k}|reader", key=k, text=pred[k]["text"], kind="real_reader"))
        jobs.append(dict(id=f"{k}|azure", key=k, text=rows[k]["label"], kind="real_azure"))
    for p in planted:
        jobs.append(dict(id=f"{p['key']}|{p['kind']}", key=p["key"], text=p["text"], kind=p["kind"]))
        jobs.append(dict(id=f"{p['key']}|orig", key=p["key"], text=p["true"], kind="planted_orig"))
    for k in J:
        jobs.append(dict(id=f"{k}|reader", key=k, text=pred[k]["text"], kind="j_reader"))
        jobs.append(dict(id=f"{k}|azure", key=k, text=rows[k]["label"], kind="j_azure"))
    jobs = [j for j in jobs if page_of(j["key"]) not in no_style]
    from judge103 import writer_text                        # the order the writer must be given (B0): computed here
    for j in jobs:
        j["wtext"] = writer_text(j["text"])
    groups = [dict(gid=f"{k}|j", key=k, cands=[pred[k]["text"], rows[k]["label"]], srcs=["reader", "azure"],
                   anchors=[0, 1], test="j", page=f"{rows[k]['stem']}_{rows[k]['page']}", era=rows[k]["era"])
              for k in J if page_of(k) not in no_style]
    for g in groups:
        g["wcands"] = [writer_text(c) for c in g["cands"]]
    styles = [dict(page=f"{pg[0]}_{pg[1]}", lines=[dict(key=x, text=rows[x]["label"], wtext=writer_text(rows[x]["label"])) for x in v])
              for pg, v in style_pages.items() if pg not in no_style]
    guard102.assert_trainable(list(test) + [x["key"] for s in styles for x in s["lines"]])
    force = []
    for k in J:
        force += [dict(key=k, cid="reader", text=pred[k]["text"]), dict(key=k, cid="azure", text=rows[k]["label"])]
    for p in planted:
        force += [dict(key=p["key"], cid=p["kind"], text=p["text"]), dict(key=p["key"], cid="orig", text=p["true"])]
    wjl(B / "force_cands.jsonl", force)
    wjl(B / "writer_jobs.jsonl", jobs)
    wjl(B / "contrast_groups.jsonl", groups)
    wjl(B / "style_pages.jsonl", styles)
    wjl(B / "planted.jsonl", planted)
    # blind readers: experiment 97's disputes format; candidates shuffled, origin only in private/
    disputes, private = [], []
    for setname, ks in (("b1", far), ("b2", J), ("control", controls)):
        for k in ks:
            r = rows[k]
            cands = [pred[k]["text"], r["label"]] if setname != "control" else [r["label"]]
            src = ["reader", "azure"] if setname != "control" else ["agreed"]
            order = list(range(len(cands)))
            rng.shuffle(order)
            disputes.append(dict(id=k, stem=r["stem"], page=r["page"], line=r["i"],
                                 crop=str(BLIND / "crops" / f"{k}.png"), control=setname == "control",
                                 candidates=[dict(c=i, text=cands[o]) for i, o in enumerate(order)], note=None))
            private.append(dict(id=k, set=setname, witnesses={str(i): src[o] for i, o in enumerate(order)}))
    rng.shuffle(disputes)
    wjl(B / "disputes.jsonl", disputes)
    wjl(BLIND / "disputes.jsonl", disputes)
    wjl(B / "private" / "witnesses.jsonl", private)
    (B / "b_summary.json").write_text(json.dumps(dict(c), indent=1))
    print(json.dumps(dict(c), indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "repair":
        repair()
    elif cmd == "heldout":
        heldout()
    elif cmd == "b":
        b_sets(sys.argv[2], sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--adapter" else None)
