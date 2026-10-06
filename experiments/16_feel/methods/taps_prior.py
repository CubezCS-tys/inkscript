"""The taps direction's best feeler: taps felt by size and shape, hamzas found again, and the language as a prior.

What it does (experiment 16; helpers in ../taps_lib.py, notes in ../notes/taps.md):

- the feeling and the remembered letters are feel_v1's (walk + pooled outline, examples from the train pages);
- THE TAPS: every dot-shaped mark is felt by its ink in units of the document's own single dot and by its shape
  (round / wide = two merged dots / several marks), and every loose part a bridged piece lost (a hamza) is a tap
  again; what each letter-form's taps feel like is a histogram learned on the train pages (`taps_lib.Taps`);
- WORD KNOWLEDGE: a letter trigram over pieces learned from the train pages' readings (Azure's) enters the chain
  search as lam * (-log P - H * letters): it says which letters follow which, not how many. lam is chosen on a
  held-out TRAIN page from 8 values, never on dev. With TAPS_PRIOR=lex the trigram is mixed with the train
  pages' piece lexicon (Witten-Bell weight); that agrees with Azure ~0.5 point more but reads fewer pieces that
  the train pages never had, so the default is the trigram alone.

Every read also runs the search without the prior and logs both (out/taps/taps_prior[_lex]_<doc>.jsonl).

Dev score (2026-10-06), pieces read as Azure reads them, mean of the four documents: 57.9% (0582 60.1, 0618 52.8,
1036 50.7, 0772 67.9; letters 64.0%) against feel_v1's 43.9% (43.1 / 35.9 / 42.2 / 54.3). Without the prior
(taps_v2) 48.2%; with the lexicon (TAPS_PRIOR=lex) 58.1%. Analysis: `python taps_lib.py overrides taps_prior <docs>`.
"""
import atexit, json, os
import taps_lib as T

TAP_W = 0.5                                            # chosen on held-out train pages (0582 p3, 1036 p6) from {0.5, 1, 2}
GRID = (0.0, 0.05, 0.1, 0.17, 0.25, 0.35, 0.5, 1.0)    # the prior's weight, chosen per document on a held-out train page
USE_LEX = os.environ.get("TAPS_PRIOR", "ngram") == "lex"
_logs = {}


def _mem(train):
    return T.learn_memory(train, T.Memory(T.doc_unit(train), TAP_W, bridged=True))


def _lm(train):
    return T.LM(T.pieces_text(train), USE_LEX)


def learn(train):
    lam, _ = T.pick_lam(train, _mem, _lm, GRID)
    lm = _lm(train)
    print(f"  lexicon {lm.Tw} pieces ({lm.Nw} seen), mu {lm.mu:.2f}, n-gram {lm.H:.2f} nats/letter, "
          f"prior {'lexicon+trigram' if USE_LEX else 'trigram'}, lam {lam}", flush=True)
    return dict(mem=_mem(train), lm=lm, lam=lam)


def read(model, r):
    q = r["q"]; f = T.FE.feeling(q, r["rise"]); mem, lm, lam = model["mem"], model["lm"], model["lam"]
    memo = {}
    k0, c0, _, _ = T.chain(q, f, mem, r["rise"], memo=memo)                      # the feeling alone
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
        with open(os.path.join(d, f"taps_prior{'_lex' if USE_LEX else ''}_{doc}.jsonl"), "w") as fh:
            for x in rows: fh.write(json.dumps(x, ensure_ascii=False) + "\n")
