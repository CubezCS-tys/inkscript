"""(Superseded by taps_prior, kept because its runs are in the log.) Taps felt by size + word knowledge from the train pages (experiment 16, taps direction).

The feeling and the taps are `taps_v1`'s. On top, a back-reader who knows the language: a letter trigram over
pieces and a piece lexicon with counts, both from the TRAIN pages' readings only (`taps_lib.LM`), enter the chain
search as lam * (-log P(piece) - H * (letters + 1)). lam is chosen on a held-out train page (`taps_lib.pick_lam`).

Every read also runs the search without the prior and logs both readings (out/taps/<module>_<doc>.jsonl), so the
notes can say how often the prior overrode the feeling and how often it chose a piece outside the train lexicon.
"""
import atexit, json, os
import taps_lib as T

TAP_W = 0.5
GRID = (0.0, 0.05, 0.1, 0.17, 0.25, 0.35, 0.5, 1.0)
USE_LEX = os.environ.get("TAPS_PRIOR", "lex") == "lex"      # "ngram": letter trigram only, no piece lexicon
LAM = os.environ.get("TAPS_LAM")                         # for the record only: a fixed lam instead of the train choice
_logs = {}


def _mem(train):
    return T.learn_memory(train, T.Memory(T.doc_unit(train), TAP_W))


def learn(train):
    if LAM is None: lam, acc = T.pick_lam(train, _mem, lambda tr: T.LM(T.pieces_text(tr), USE_LEX), GRID)
    else: lam = float(LAM)
    lm = T.LM(T.pieces_text(train), USE_LEX)
    print(f"  lexicon {lm.Tw} pieces ({lm.Nw} seen), mu {lm.mu:.2f}, n-gram {lm.H:.2f} nats/letter, lam {lam}", flush=True)
    return dict(mem=_mem(train), lm=lm, lam=lam)


def read(model, r):
    q = r["q"]; f = T.FE.feeling(q, r["rise"]); mem, lm, lam = model["mem"], model["lm"], model["lam"]
    memo = {}
    k0, c0, _, _ = T.chain(q, f, mem, r["rise"], memo=memo)
    k1, c1, _, _ = T.chain(q, f, mem, r["rise"], lm, lam, memo=memo) if lam > 0 else (k0, c0, 0, 0)
    q.pop("_sv", None)
    a, b = [k[0] for k in k0], [k[0] for k in k1]
    _logs.setdefault(r["doc"], []).append(dict(page=r["page"], feel="".join(a), prior="".join(b), lam=lam,
                                               feel_known=lm.known(a), prior_known=lm.known(b)))
    return b, c1


@atexit.register
def _dump():
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "taps")
    os.makedirs(d, exist_ok=True)
    for doc, rows in _logs.items():
        with open(os.path.join(d, f"{__name__.split('.')[-1]}{'' if USE_LEX else '_ngram'}_{doc}.jsonl"), "w") as fh:
            for x in rows: fh.write(json.dumps(x, ensure_ascii=False) + "\n")
