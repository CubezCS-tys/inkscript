"""D2: how the networks and the coverage shares move as the corpus grows. Random subsets of the 600
(sizes 50..600, 30 seeds each, seed base 4840) -> out/d_metrics_and_workload/d2_growth.json."""
import collections, itertools, json, math, random, statistics, time
import common_d as cd

t0 = time.time()
D = cd.load()
arts, ms, works = D["arts"], D["mentions"], D["works"]
bad_pks = {pk for pk, w in works.items() if D["B_verdict"].get(w["id"]) in ("wrong", "serial", "mixed")}
held = {pk: r["c999"] for pk, r in D["decA"].items() if r["decision"] == "accept" and r.get("c999")}
held.update({pk: v["c999"] for pk, v in D["links47"].items() if pk not in held})
c999_of_pub = {p: a["c999"] for p, a in arts.items()}

by_pub = collections.defaultdict(list)
for m in ms:
    by_pub[m["pub_id"]].append(m)
pubs = sorted(arts)


def measure(sub):
    w2p = collections.defaultdict(set)
    n_m = n_card = n_held = 0
    held_recs = set()
    for p in sub:
        for m in by_pub[p]:
            n_m += 1
            if m["work"] is not None:
                n_card += 1
                if m["work"] not in bad_pks:
                    w2p[m["work"]].add(p)
                if m["work"] in held:
                    n_held += 1
                    held_recs.add(held[m["work"]])
    shared = {w: ps for w, ps in w2p.items() if len(ps) >= 2}
    e = set()
    for ps in shared.values():
        for a, b in itertools.combinations(sorted(ps), 2):
            e.add((a, b))
    nodes = set().union(*shared.values()) if shared else set()
    comps = cd.components(nodes, list(e))
    subc = {c999_of_pub[p] for p in sub if c999_of_pub[p]}
    inside = sum(1 for p in sub for m in by_pub[p] if m["work"] in held and held[m["work"]] in subc)
    citing = sum(1 for p in sub if by_pub[p])
    # mentions on works shared with another article of the subset
    m_shared = sum(1 for p in sub for m in by_pub[p] if m["work"] in shared)
    return dict(articles=len(sub), citing_articles=citing, mentions=n_m, distinct_works=len(w2p),
                shared_works=len(shared), coupled_articles=len(nodes), coupling_edges=len(e),
                largest_component=len(comps[0]) if comps else 0,
                held_share=n_held / n_m if n_m else 0, held_records=len(held_recs),
                inside_corpus_mentions=inside, shared_mention_share=m_shared / n_m if n_m else 0)


sizes = [50, 100, 200, 300, 400, 500, 600]
curves = {}
for n in sizes:
    runs = []
    for s in range(30 if n < 600 else 1):
        rnd = random.Random(4840 + s)
        runs.append(measure(rnd.sample(pubs, n)))
    agg = {}
    for k in runs[0]:
        vals = [r[k] for r in runs]
        agg[k] = dict(mean=round(statistics.mean(vals), 4), sd=round(statistics.pstdev(vals), 4),
                      min=min(vals), max=max(vals))
    curves[n] = agg
    print(n, {k: v["mean"] for k, v in agg.items()})


def fit(key, lo=100):
    xs = [math.log(n) for n in sizes if n >= lo and curves[n][key]["mean"] > 0]
    ys = [math.log(curves[n][key]["mean"]) for n in sizes if n >= lo and curves[n][key]["mean"] > 0]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return round(b, 3), my - b * mx


fits = {}
for k in ("shared_works", "coupled_articles", "coupling_edges", "largest_component", "distinct_works", "held_records"):
    b, a = fit(k)
    fits[k] = dict(exponent=b, at_3000=round(math.exp(a + b * math.log(3000))))
# shares of mentions that sit on a work shared with another article: fitted on n (log-linear)
R = dict(
    seeds="30 random subsets per size (seed 4840+s); the 600 once",
    curves={str(n): v for n, v in curves.items()},
    power_law_fits_100_to_600=fits,
    caution="Fits over 100-600 random articles from many fields. Extrapolating to 3,000 is a guess within a factor of "
            "~2; to 1M it is not a measurement at all (saturation, field mix and the classical-works core change "
            "the curve). The coupled-article share is bounded by 1 and the held share is a property of what is cited.",
    runtime_s=round(time.time() - t0, 1))
cd.save("d2_growth.json", R)
print(json.dumps(fits, indent=1))
