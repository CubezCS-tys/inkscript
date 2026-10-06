"""Scaling the trained feeler to many books (2026-10-06): extraction, a faster trainer, and the growth curve.

Question: does training the CTC reader (model_lib / model_ctc_ft) on many more scanned books — many more
typefaces — make it read the four benchmark books better, and how does accuracy grow with the number of books?

Books: random documents from the corpus bucket, one per journal, kept only if scanned (the PDF's only font is
"Dummy") and mostly Arabic (screen.jsonl in out/books/). The four benchmark journals (0582, 0618, 1036, 0772)
and the gold-set journals (0005, 1110) are excluded. Up to PAGES pages per book whose Azure page angle is
within 5 degrees of upright (page 1 is used last: covers and title pages). Each book's pieces are extracted
exactly as bench.build_cache does for TRAIN pages (reader.pieces_of, reader.blind, the cutter's cuts from
penpath.plan + solve with that book's own atlas) and stored straight away as model_lib.raw feature arrays.

    python scale_lib.py extract ID [ID ...]        # -> out/books/feats/<id>.pkl  (~0.5-1.3 GB peak each)
    python scale_lib.py train N [--tag T] [k=v ...]  # joint model on the first N books + the 4 bench TRAIN pages
    python scale_lib.py stats                      # pieces per extracted book

Benchmark dev/test pages are never trained on: the bench books contribute only model_lib.doc_train_raw (their
TRAIN pages). Run with out/torchenv/bin/python.
"""
import sys, os, json, pickle, time, hashlib, resource
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[0] / "10_atlas_reader"))
BOOKS = HERE / "out" / "books"; RAW = BOOKS / "raw"; FEATS = BOOKS / "feats"; MODELS = HERE / "out" / "models"
PAGES = 8
EXCLUDE = ("0582", "0618", "1036", "0772", "0005", "1110")
BENCH = ("0582", "0618", "1036", "0772")


# ------------------------------------------------------------------ which books, in which order
def book_order():
    """Every screened book (scanned, Arabic), in a fixed random order: the first N are 'N books'."""
    rows = [json.loads(l) for l in open(BOOKS / "screen.jsonl")]
    ok = [r["id"] for r in rows if r.get("fonts") == ["Dummy"] and r.get("arab", 0) > 0.8 and r["id"][:4] not in EXCLUDE]
    rng = np.random.default_rng(16); ok = sorted(ok); rng.shuffle(ok)
    return ok


def extracted():
    """Books in book_order() whose features exist and carry at least 300 pieces."""
    out = []
    for i in book_order():
        p = FEATS / f"{i}.meta.json"
        if not p.exists(): break                                       # only a complete prefix of the order counts
        if json.load(open(p))["pieces"] >= 300: out.append(i)
    return out


# ------------------------------------------------------------------ extraction (as bench.build_cache, train pages)
def pages_of(i):
    j = json.load(open(RAW / i / f"{i}.json")); ar = j.get("analyzeResult", j)
    up = [p["pageNumber"] for p in ar["pages"] if abs(p.get("angle", 0) or 0) < 5 and len(p.get("words", [])) >= 40]
    up = [p for p in up if p != 1] + [p for p in up if p == 1]
    return sorted(up[:PAGES])


def extract(i):
    import cv2
    cv2.setNumThreads(int(os.environ.get("SCALE_CV_THREADS", 2)))          # 16 OpenCV threads x 3 processes thrash the CPU
    from reader import pieces_of, blind
    from inkscript.geometry import penpath as P
    import model_lib as ML
    az, sc = str(RAW / i / f"{i}.json"), str(RAW / i / f"{i}.pdf")
    t0 = time.time(); recs = []; plans = []; pages = pages_of(i); bad = []
    for pn in pages:
        try:
            for _, pc, (units, forms), lg in pieces_of(az, sc, [pn]):
                if not lg or lg["rise"] < 10: continue
                q = blind(pc, lg)
                if q is None: continue
                q.pop("cache", None)
                rec = dict(doc=i, page=pn, units=units, forms=forms, rise=float(lg["rise"]), q=q)
                try: x = ML.raw(rec)
                except Exception: x = None
                if x is None or not np.isfinite(x).all(): continue
                rec = dict(x=x.astype(np.float16), rise=rec["rise"], units=units, forms=forms, W=q["G"]["W"], doc=i)
                if len(units) >= 2:
                    p = P.plan(units, pc["blobs"], lg, forms)
                    if p is not None and p["G"]["W"] == q["G"]["W"]: plans.append((p, rec))
                del q
                recs.append(rec)
        except Exception as e:                                         # a page the layout cannot handle: skip it
            bad.append((pn, repr(e)[:80]))
    if plans:
        try:
            P.solve([p for p, _ in plans])
            for p, rec in plans: rec["cuts"] = sorted(int(c) for c in p["cuts"])
        except Exception as e:
            bad.append(("solve", repr(e)[:80]))
    for r in recs: r["cuts"] = r.get("cuts")
    items = recs
    FEATS.mkdir(parents=True, exist_ok=True)
    pickle.dump(items, open(FEATS / f"{i}.pkl", "wb"))
    meta = dict(id=i, pages=pages, pieces=len(items), with_cuts=sum(1 for d in items if d["cuts"]), bad=bad,
                seconds=round(time.time() - t0, 1), peak_gb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2))
    json.dump(meta, open(FEATS / f"{i}.meta.json", "w"))
    print(json.dumps(meta), flush=True)


# ------------------------------------------------------------------ training on many books
def load_items(n_books, bench=True):
    """The first n_books extracted books' pieces + (if bench) the four bench books' TRAIN pages."""
    import model_lib as ML
    items = []
    if bench:
        for d in BENCH: items += ML.doc_train_raw(d)
    for i in extracted()[:n_books]:
        items += pickle.load(open(FEATS / f"{i}.pkl", "rb"))
    return items


def clean(items, min_count=20):
    """Keep pieces whose every letter-form is seen at least min_count times (rare forms: Latin, odd marks)."""
    import model_lib as ML
    from collections import Counter
    c = Counter(k for d in items for k in ML.labels_of(d))
    keep = {k for k, v in c.items() if v >= min_count}
    return [d for d in items if all(k in keep for k in ML.labels_of(d))], sorted(keep)


def train(items, vocab, rate=20, steps=20000, seed=0, bs=32, lr=2e-3, cut_w=0.5, model=None, log=None, stretch=0.15,
          aug=True, bucket=1, threads=int(os.environ.get("SCALE_THREADS", 8)), warm=0.15, bench_items=None, bench_frac=0.0, **kw):
    """model_lib.train with the length fixed in optimiser STEPS instead of passes (so that 15 or 60 books cost
    what we can afford), and, if bench_frac > 0, that share of every batch drawn from bench_items."""
    import torch, torch.nn as nn, torch.nn.functional as Fn
    import model_lib as ML
    torch.set_num_threads(threads); torch.manual_seed(seed); rng = np.random.default_rng(seed)
    idx = {k: i + 1 for i, k in enumerate(vocab)}
    data = [d for d in items if all(k in idx for k in ML.labels_of(d))]
    bdata = [d for d in (bench_items or []) if all(k in idx for k in ML.labels_of(d))]
    m = model or ML.Reader(len(vocab), **kw)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=1e-2)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=warm)
    ctc = nn.CTCLoss(blank=0, zero_infinity=True); t0 = time.time(); tot = n = 0
    nb = int(round(bs * bench_frac)) if bdata else 0; k = bs - nb
    plen = np.array([len(d["x"]) / d["rise"] for d in data]); queue = []

    def refill():
        # length buckets: 64 batches' worth of pieces, sorted by length, cut into batches, batches shuffled
        # (2.3x faster on CPU than random batches, whose length is set by the longest piece)
        perm = rng.permutation(len(data))
        for c in range(0, len(perm), 64 * k):
            ch = perm[c:c + 64 * k]; ch = ch[np.argsort(plen[ch])]
            bl = [ch[i:i + k] for i in range(0, len(ch), k)]
            for j in rng.permutation(len(bl)): queue.append(bl[j])
    for step in range(steps):
        m.train()
        if not queue: refill()
        pick = [data[j] for j in queue.pop()]
        if nb: pick += [bdata[j] for j in rng.integers(0, len(bdata), nb)]
        batch = []
        for d in pick:
            r = rate * (rng.uniform(1 - stretch, 1 + stretch) if aug else 1.0)
            x = d["x"].astype(np.float32)
            f, edges = ML.resample(x, d["rise"], r)
            lab = [idx[k] for k in ML.labels_of(d)]
            if len(f) < 2 * len(lab):
                f, edges = ML.resample(x, d["rise"], r * (2 * len(lab) + 1) / len(f))
            bt = ML.boundary_target(d, edges)
            if aug: f = ML.augment(f, rng)
            batch.append((f, lab, bt))
        x, lens, tg, tl, yb, mb = ML.collate(batch)
        lo, cu = m(x, lens)
        loss = ctc(Fn.log_softmax(lo, -1).transpose(0, 1), tg, lens, tl)
        if mb.sum() > 0:
            bce = Fn.binary_cross_entropy_with_logits(cu, yb, reduction="none", pos_weight=torch.tensor(4.0))
            loss = loss + cut_w * (bce * mb).sum() / mb.sum()
        opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); sched.step()
        tot += float(loss.detach()) * len(batch); n += len(batch)
        if log and (step + 1) % 1000 == 0:
            log(f"step {step + 1}/{steps} loss {tot / n:.3f} ({time.time() - t0:.0f}s, "
                f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6:.2f} GB)"); tot = n = 0
    m.eval(); m.vocab = list(vocab); m.rate = rate
    return m


def tag_of(n_books, cfg):
    return hashlib.md5(json.dumps([n_books, extracted()[:n_books], cfg], sort_keys=True).encode()).hexdigest()[:8]


DEFAULT = dict(rate=20, steps=12000, bucket=1, seed=0, bs=32, lr=2e-3, cut_w=0.5, h=128, conv=96, layers=2, drop=0.2, stretch=0.15)
ARCH = ("h", "conv", "layers", "drop")


def joint_path(n_books, cfg):
    return MODELS / f"scale_joint_{n_books}_{tag_of(n_books, cfg)}.pt"


def joint(n_books, cfg=None, log=print):
    """The joint reader on n_books new books + the bench TRAIN pages; trained once, cached in out/models/."""
    import torch, model_lib as ML
    cfg = dict(DEFAULT, **(cfg or {})); path = joint_path(n_books, cfg)
    meta = path.with_suffix(".json")
    if path.exists():
        vocab = [tuple(v) for v in json.load(open(meta))["vocab"]]
        m = ML.Reader(len(vocab), **{k: cfg[k] for k in ARCH})
        m.load_state_dict(torch.load(path)); m.eval(); m.vocab = vocab; m.rate = cfg["rate"]
        return m
    items, vocab = clean(load_items(n_books))
    log(f"joint {n_books} books: {len(items)} pieces, {len(vocab)} letter-forms, cfg {cfg}")
    t0 = time.time()
    m = train(items, vocab, log=log, **cfg)
    MODELS.mkdir(parents=True, exist_ok=True); torch.save(m.state_dict(), path)
    json.dump(dict(n_books=n_books, books=extracted()[:n_books], pieces=len(items), vocab=vocab, cfg=cfg,
                   params=sum(p.numel() for p in m.parameters()), seconds=round(time.time() - t0),
                   peak_gb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2)), open(meta, "w"))
    log(f"trained {path.name} in {time.time() - t0:.0f}s")
    return m


FT = dict(epochs=10, lr=5e-4)


def finetune(n_books, train_recs, cfg=None, ft=None, log=print):
    """model_ctc_ft's second step: the joint model, then this bench book's own TRAIN pages (10 passes, lr 5e-4)."""
    import torch, model_lib as ML
    cfg = dict(DEFAULT, **(cfg or {})); ft = dict(FT, **(ft or {})); doc = train_recs[0]["doc"]
    m = joint(n_books, cfg, log=log)
    path = MODELS / f"scale_ft_{doc}_{n_books}_{tag_of(n_books, [cfg, ft])}.pt"
    if path.exists():
        m.load_state_dict(torch.load(path)); m.eval(); return m
    items = ML.from_records(train_recs)
    fcfg = dict(cfg, **{k: v for k, v in ft.items() if k != "epochs"})
    fcfg["steps"] = ft["epochs"] * ((len(items) + fcfg["bs"] - 1) // fcfg["bs"])
    m = train(items, m.vocab, model=m, log=log, **fcfg)
    torch.save(m.state_dict(), path)
    return m


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "extract":
        for i in a[1:]:
            if (FEATS / f"{i}.meta.json").exists(): continue
            extract(i)
    elif a[0] == "order":
        print("\n".join(book_order()))
    elif a[0] == "stats":
        tot = 0
        for i in book_order():
            p = FEATS / f"{i}.meta.json"
            if p.exists():
                m = json.load(open(p)); tot += m["pieces"]; print(i, m["pieces"], m["with_cuts"], m["seconds"], m["peak_gb"], m["bad"][:1])
        print("extracted", len(extracted()), "books,", tot, "pieces")
    elif a[0] == "train":
        n = int(a[1]); cfg = {}
        for kv in a[2:]:
            k, v = kv.split("="); cfg[k] = type(DEFAULT[k])(v) if k in DEFAULT else v
        joint(n, cfg, log=lambda s: print("   ", s, flush=True))


# ------------------------------------------------------------------ a second yardstick: books no model has seen
PROBE = 10                                                            # the last PROBE books in the order


def probe(m, per_book=300, seed=0):
    """Read pieces of the last PROBE books (never in any n<=83 model's training) with joint model m: mean per-book
    piece accuracy against Azure, letters only (no cuts). For 'does a new typeface read better with more books'."""
    import model_lib as ML, bench
    books = extracted()[-PROBE:]; rng = np.random.default_rng(seed); accs = []
    for i in books:
        items = pickle.load(open(FEATS / f"{i}.pkl", "rb"))
        pick = rng.choice(len(items), min(per_book, len(items)), replace=False); ok = 0
        for j in pick:
            d = items[j]
            seq, _ = ML.decode(m, d["x"].astype(np.float32), d["rise"], [], d["W"])
            ok += [bench.base(k[0]) for k in seq] == [bench.base(u) for u in d["units"]]
        accs.append(100 * ok / len(pick))
    return dict(books=books, per_book=[round(a, 1) for a in accs], mean=round(float(np.mean(accs)), 2))


def _probe_cli(n, cfg):
    import torch
    torch.set_num_threads(int(os.environ.get("SCALE_THREADS", 2)))
    m = joint(n, cfg); r = probe(m); r.update(n_books=n, cfg=cfg, when=time.strftime("%Y-%m-%d %H:%M"))
    with open(BOOKS / "probe.jsonl", "a") as f: f.write(json.dumps(r) + "\n")
    print(json.dumps(r), flush=True)


if __name__ == "__main__" and sys.argv[1] == "probe":
    cfg = {}
    for kv in sys.argv[3:]:
        k, v = kv.split("="); cfg[k] = type(DEFAULT[k])(v)
    _probe_cli(int(sys.argv[2]), cfg)
