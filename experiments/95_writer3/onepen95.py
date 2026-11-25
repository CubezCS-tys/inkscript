"""Experiment 95, idea 3: one pen.

A glyph's strokes (87's programs: centre-line edges for a font, METAFONT draws for AlQalam) become pen ROUTES:
  edges    87 as it is: every edge its own pen-down, in the program's order, each run right to left ("two pens");
  onepen   every connected piece of the body (edge ends within 0.035 em are one node) is ONE route that travels every
           edge, retracing the fewest edges needed (Chinese-postman: the odd nodes are paired by shortest paths,
           except the route's two ends); no order preference: the route starts at the first odd node (or node);
  order    one pen + the soft scribe-order cost: the route starts at the piece's top right (the end with the largest
           x + 0.5 y), and at every node takes the branch that turns least and runs leftward; AlQalam keeps its
           METAFONT draw order (consecutive draws that touch become one route).
Dots and marks are separate pen lifts, written after their body.  The ink of a route equals the ink of its edges
(the same capsules; a retraced edge is drawn twice), so routes change no fit; they change the pen path.

    python onepen95.py data [N]     exp 82's synthetic test lines (lines82.pick_lines, modern and traced, clean)
                                    -> out/data/lines82.jsonl + out/data/crops/l82/<key>.png (+ owner/ink npz, local)
    python onepen95.py fit          GPU: every line fitted with its own face's programs (true text, free style)
                                    -> out/onepen/fits.jsonl (the fitted settings)
    python onepen95.py check        local: the routes' ink equals the edges' ink (3 lines)
    python onepen95.py score        local: the three routes placed with each line's fitted settings, scored with exp
                                    82's metric82.shape_score against truth82 -> out/onepen/shape.json
    python onepen95.py anim         local: stroke animation mid-frames, edges against one pen
"""
from __future__ import annotations

import heapq
import itertools
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from common95 import D95, E, OUT, jl, text_for, use_programs

ONE = Path(os.environ.get("OUT95", OUT)) / "onepen"
TIE = 0.035


# ------------------------------------------------------------------------------------------------ routes
def _graph(strokes):
    """strokes [(pts [N,3])] -> nodes (positions), edges [(u, v, pts)] (pts run u -> v)."""
    ends = []
    for p in strokes:
        ends += [p[0, :2], p[-1, :2]]
    nodes, lab = [], []
    for q in ends:
        for k, n in enumerate(nodes):
            if np.hypot(*(q - n)) < TIE:
                lab.append(k)
                break
        else:
            nodes.append(q.copy())
            lab.append(len(nodes) - 1)
    edges = [(lab[2 * i], lab[2 * i + 1], p) for i, p in enumerate(strokes)]
    return nodes, edges


def _components(n, edges):
    par = list(range(n))

    def f(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for u, v, _ in edges:
        par[f(u)] = f(v)
    comp = defaultdict(list)
    for i, (u, v, _) in enumerate(edges):
        comp[f(u)].append(i)
    return list(comp.values())


def _length(p):
    return float(np.hypot(*np.diff(p[:, :2], axis=0).T).sum()) if len(p) > 1 else 0.0


def _dijkstra(n, E_, src):
    adj = defaultdict(list)
    for i, (u, v, p) in E_:
        L = _length(p)
        adj[u].append((v, L, i))
        adj[v].append((u, L, i))
    dist = {src: 0.0}
    prev = {}
    h = [(0.0, src)]
    while h:
        d, x = heapq.heappop(h)
        if d > dist.get(x, 1e18):
            continue
        for y, L, i in adj[x]:
            if d + L < dist.get(y, 1e18):
                dist[y] = d + L
                prev[y] = (x, i)
                heapq.heappush(h, (d + L, y))
    return dist, prev


def _start_score(p):
    return float(p[0] + 0.5 * p[1])


def route_piece(nodes, edges, idx, order: bool):
    """One connected piece (edge indices idx) -> [(pts [N,3], retrace [N])] (one route)."""
    E_ = [(i, edges[i]) for i in idx]
    E2 = [(i, u, v, p) for i, (u, v, p) in E_]
    deg = defaultdict(int)
    for _, u, v, _ in E2:
        deg[u] += 1
        deg[v] += 1
    odd = sorted(k for k, d in deg.items() if d % 2)
    sp = {}
    for o in odd:
        sp[o] = _dijkstra(len(nodes), [(i, (u, v, p)) for i, u, v, p in E2], o)
    extra = []                                              # duplicated (retraced) edges: (i, u, v, p, retrace)

    def matching_cost(rest):
        if not rest:
            return 0.0, []
        if len(rest) > 10:                                  # greedy for big pieces
            rest = list(rest)
            tot, pairs = 0.0, []
            while rest:
                a = rest.pop(0)
                b = min(rest, key=lambda b: sp[a][0].get(b, 1e9))
                rest.remove(b)
                tot += sp[a][0].get(b, 1e9)
                pairs.append((a, b))
            return tot, pairs
        a = rest[0]
        best = (1e18, None)
        for b in rest[1:]:
            r2 = [x for x in rest if x not in (a, b)]
            c, pr = matching_cost(r2)
            c += sp[a][0].get(b, 1e9)
            if c < best[0]:
                best = (c, [(a, b)] + pr)
        return best
    if odd:
        cands = []
        pairs_se = list(itertools.combinations(odd, 2)) if len(odd) <= 10 else [(odd[0], odd[1])]
        for s, t in pairs_se:
            c, pr = matching_cost([x for x in odd if x not in (s, t)])
            for a, b in ((s, t), (t, s)):
                pen = -0.02 * _start_score(nodes[a]) if order else 0.0     # soft: prefer a top-right start
                cands.append((c + pen, a, pr))
        if not order:
            cands.sort(key=lambda x: (round(x[0], 6), x[1]))
        else:
            cands.sort(key=lambda x: x[0])
        _, start, pairs = cands[0]
        for a, b in pairs:
            dist, prev = sp[a]
            x = b
            while x != a and x in prev:
                y, i = prev[x]
                u, v, p = edges[i]
                extra.append((i, u, v, p))
                x = y
    else:
        cand = sorted(deg, key=lambda k: -_start_score(nodes[k])) if order else sorted(deg)
        start = cand[0]
    # Hierholzer over original + duplicated edges
    alle = [(i, u, v, p, 0) for i, u, v, p in E2] + [(i, u, v, p, 1) for i, u, v, p in extra]
    adj = defaultdict(list)
    for k, (i, u, v, p, rt) in enumerate(alle):
        adj[u].append(k)
        adj[v].append(k)
    used = [False] * len(alle)

    def oriented(k, frm):
        i, u, v, p, rt = alle[k]
        return (p if u == frm else p[::-1]), (v if u == frm else u), rt

    def pick(x, incoming_dir):
        ks = [k for k in adj[x] if not used[k]]
        if not order or incoming_dir is None:
            if order:                                       # first move: leftward, original edges first
                ks.sort(key=lambda k: (alle[k][4], -(oriented(k, x)[0][0, 0] - oriented(k, x)[0][-1, 0])))
            return ks[0]

        def cost(k):
            q, _, rt = oriented(k, x)
            d = q[min(len(q) - 1, 2), :2] - q[0, :2]
            n = np.hypot(*d) + 1e-9
            turn = 1 - float(np.dot(d / n, incoming_dir))
            return turn + 0.3 * max(0.0, float(d[0] / n)) + 0.5 * rt
        return min(ks, key=cost)
    stack = [(start, None, None)]                           # (node, edge used to arrive, direction)
    path = []
    while stack:
        x, k_in, dir_in = stack[-1]
        ks = [k for k in adj[x] if not used[k]]
        if ks:
            k = pick(x, dir_in)
            used[k] = True
            q, y, rt = oriented(k, x)
            d = q[-1, :2] - q[max(0, len(q) - 3), :2]
            d = d / (np.hypot(*d) + 1e-9)
            stack.append((y, (k, x), d))
        else:
            stack.pop()
            if k_in is not None:
                path.append(k_in)
    path = path[::-1]
    pts, rts = [], []
    for k, frm in path:
        q, _, rt = oriented(k, frm)
        r = np.full(len(q), rt)
        if pts:
            r[0] = 1                         # the step from the last end to this edge's start (inside a junction node)
        pts.append(q)
        rts.append(r)
    if not pts:
        return []
    return [(np.vstack(pts), np.concatenate(rts))]


def routes(strokes, mode: str, aq: bool = False):
    """[(pts [N,3], is_mark)] of one glyph -> [(pts, retrace [N], is_mark)] in pen order (body first, then marks)."""
    body = [np.asarray(p, np.float32) for p, m in strokes if not m and len(p)]
    marks = [np.asarray(p, np.float32) for p, m in strokes if m and len(p)]
    out = []
    if mode == "edges" or not body:
        out = [(p, np.zeros(len(p), int), False) for p in body]
    elif aq and mode == "order":                            # AlQalam: its own draw order, touching draws joined
        cur = None
        for p in body:
            if cur is not None:
                e = cur[0][-1, :2]
                if np.hypot(*(p[0, :2] - e)) < TIE:
                    cur = (np.vstack([cur[0], p[1:]]), np.r_[cur[1], np.zeros(len(p) - 1, int)])
                    continue
                if np.hypot(*(p[-1, :2] - e)) < TIE:
                    cur = (np.vstack([cur[0], p[::-1][1:]]), np.r_[cur[1], np.zeros(len(p) - 1, int)])
                    continue
                out.append((cur[0], cur[1], False))
            cur = (p, np.zeros(len(p), int))
        out.append((cur[0], cur[1], False))
    else:
        nodes, edges = _graph(body)
        comps = _components(len(nodes), edges)
        if mode == "order":                                 # pieces right to left
            comps.sort(key=lambda c: -max(float(edges[i][2][:, 0].max()) for i in c))
        for c in comps:
            for p, rt in route_piece(nodes, edges, c, order=(mode == "order")):
                out.append((p, rt, False))
    out += [(p if p[0, 0] >= p[-1, 0] else p[::-1], np.zeros(len(p), int), True) for p in marks]
    return out


# ------------------------------------------------------------------------------------------------ data + fits
def data(n: int = 120):
    import cv2
    sys.path.insert(0, str(E / "82_path_accuracy"))
    import lines82 as L
    (D95 / "crops/l82").mkdir(parents=True, exist_ok=True)
    (OUT / "l82").mkdir(parents=True, exist_ok=True)
    rows = []
    names = {p.stem.replace("font_", ""): p for p in (E / "87_writer/out/programs").glob("font_*.json")}
    for faces in ("modern", "traced"):
        specs = L.pick_lines(n, faces)
        for i, s in enumerate(specs):
            nm = Path(s["font"]).stem.replace("[", "_").replace("]", "").replace(",", "_")
            if nm not in names:
                continue
            grey, owner, ink = L.render(s)
            key = f"l82_{faces}_{i:03d}"
            cv2.imwrite(str(D95 / "crops/l82" / f"{key}.png"), grey)
            np.savez_compressed(OUT / "l82" / f"{key}.npz", owner=owner, ink=ink)
            rows.append(dict(key=key, faces=faces, font=s["font"], lib=f"font:{nm}", text=s["text"], px=s["px"]))
    with open(D95 / "lines82.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(rows), "lines")


def fit(iters: int = 160):
    import cv2
    W = use_programs()
    import fit87 as F
    dev = F.device()
    ONE.mkdir(parents=True, exist_ok=True)
    R = jl(D95 / "lines82.jsonl")
    out = ONE / "fits.jsonl"
    done = {json.loads(l)["key"] for l in open(out)} if out.exists() else set()
    R = [r for r in R if r["key"] not in done]
    f = open(out, "a")
    for i in range(0, len(R), 32):
        B = R[i:i + 32]
        items = []
        for k, r in enumerate(B):
            g = cv2.imread(str(D95 / "crops/l82" / f"{r['key']}.png"), 0)
            items.append(dict(grey=g, text=r["text"], lib=r["lib"], group=k, target=(g < 128).astype(np.float32)))
        bt = F.Batch(items, dev)
        P = F.Params(bt)
        F.init_items(bt, P)
        F.fit(bt, P, mode="free", iters=iters)
        sc = F.scores(bt, P)
        for k, (r, s) in enumerate(zip(B, sc)):
            f.write(json.dumps(dict(key=r["key"], iou=round(s["iou"], 4), chamfer=round(s["chamfer"], 3),
                                    params=F.params_of(P, bt, k),
                                    theta=P.theta[k].detach().cpu().numpy().round(5).tolist())) + "\n")
        f.flush()
        print("onepen fit", i + len(B), "/", len(R), flush=True)


def place_points(F, bt, P, i, pts, mark, above):
    """87's place_batch transform for one line's points (em) -> pixel (x, y)."""
    import torch
    K = F.knots(P, bt)
    g = int(bt.group[i])
    s = {k: float(v[g]) for k, v in P.style.items()}
    lp = {k: float(v[i]) for k, v in P.linep.items()}
    x, y = pts[:, 0].copy(), pts[:, 1].copy()
    x = x + s["mark_dx"] * mark
    y = y + np.where(above, s["mark_dy_up"], s["mark_dy_down"]) * mark
    line = torch.full((len(x),), i, dtype=torch.long)
    xw = F.warp_x(torch.as_tensor(x, dtype=torch.float32), line, P, bt, K).detach().numpy()
    X = lp["x0"] + s["size"] * (xw + s["slant"] * y)
    Wc = bt.Wd[i]
    u = (X - 0.5 * Wc) / F.H
    Y = F.H * 0.62 + lp["base"] + lp["tilt"] * (X - 0.5 * Wc) + lp["curve"] * u * u * 4 - s["size"] * y
    return np.stack([X, Y], 1)


def rebuild_batch(rows, fits):
    """CPU: a Batch of the lines with their fitted settings restored."""
    import cv2
    import torch
    W = use_programs()
    import fit87 as F
    items = []
    for k, r in enumerate(rows):
        g = cv2.imread(str(D95 / "crops/l82" / f"{r['key']}.png"), 0)
        items.append(dict(grey=g, text=r["text"], lib=r["lib"], group=k, target=(g < 128).astype(np.float32)))
    bt = F.Batch(items, "cpu")
    P = F.Params(bt)
    with torch.no_grad():
        for k, r in enumerate(rows):
            p = fits[r["key"]]
            for kk in F.STYLE_KEYS:
                P.style[kk][k] = p["params"][kk]
            for kk in F.LINE_KEYS:
                P.linep[kk][k] = p["params"][kk]
            th = p["theta"]
            P.theta[k, :len(th)] = torch.as_tensor(th[:P.theta.shape[1]])
    return F, bt, P


def signal_of(F, bt, P, i, mode):
    """The fitted line's pen path in exp 82's signal format: strokes {kind, pts [(y, x)] px, retrace}."""
    inst = bt.items[i]["inst"]
    lib = bt.items[i]["lib"]
    order = sorted(range(len(inst)), key=lambda j: inst[j]["char"])           # writing order = logical order
    strokes, marks = [], []
    for j in order:
        g = inst[j]
        for pts, rt, mk in routes(g["strokes"], mode, aq=(lib == "alqalam")):
            p = np.asarray(pts, np.float32)[:, :2] + [g["x"], g["y"]]
            up = np.full(len(p), mk and p[:, 1].mean() > 0.15)
            XY = place_points(F, bt, P, i, p, np.full(len(p), float(mk)), up)
            yx = XY[:, ::-1].copy()
            d = dict(kind="mark" if mk else "main", pts=yx, retrace=np.asarray(rt, int), letter=-1)
            (marks if mk else strokes).append(d)
        strokes += marks
        marks = []
    return dict(strokes=strokes)


def score(n_max: int = 10000):
    import cv2
    sys.path.insert(0, str(E / "82_path_accuracy"))
    import metric82 as MM
    import path82
    fits = {json.loads(l)["key"]: json.loads(l) for l in open(ONE / "fits.jsonl")}
    R = [r for r in jl(D95 / "lines82.jsonl") if r["key"] in fits][:n_max]
    rows = []
    of = open(ONE / "shape_rows.jsonl", "w")
    for c in range(0, len(R), 16):
        B = R[c:c + 16]
        F, bt, P = rebuild_batch(B, fits)
        for i, r in enumerate(B):
            z = np.load(OUT / "l82" / f"{r['key']}.npz")
            owner, ink = z["owner"], z["ink"]
            grey = cv2.imread(str(D95 / "crops/l82" / f"{r['key']}.png"), 0)
            truth = MM.truth82(ink, owner, r["text"])
            for mode in ("edges", "onepen", "order"):
                sig = signal_of(F, bt, P, i, mode)
                sc = MM.shape_score(sig, truth, owner, r["text"], ink)
                rows.append(dict(key=r["key"], faces=r["faces"], font=r["font"], mode=mode, fit_iou=fits[r["key"]]["iou"], **sc))
                of.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
            try:
                rec = path82.rebuild(grey, "skeleton", ink=ink)
                sc = MM.shape_score(rec, truth, owner, r["text"], ink)
                rows.append(dict(key=r["key"], faces=r["faces"], font=r["font"], mode="skeleton82", fit_iou=None, **sc))
                of.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
            except Exception as e:  # noqa: BLE001
                print("skeleton failed", r["key"], e)
        of.flush()
        print("scored", c + len(B), "/", len(R), flush=True)
    summ = {}
    for faces in ("modern", "traced", "all"):
        for mode in ("edges", "onepen", "order", "skeleton82"):
            S = [x for x in rows if x["mode"] == mode and (faces == "all" or x["faces"] == faces)]
            if S:
                summ[f"{faces}/{mode}"] = MM.summarise(S)
    fam = defaultdict(list)
    for x in rows:
        fam[(Path(x["font"]).stem.split("_")[0], x["mode"])].append(x)
    summ["by_family"] = {f"{a}/{b}": MM.summarise(v) for (a, b), v in sorted(fam.items())}
    (ONE / "shape.json").write_text(json.dumps(summ, indent=1))
    for k, v in summ.items():
        if k != "by_family":
            print(k, v)


def check(n: int = 3):
    """The routes' ink equals the edges' ink: render both from the same fitted settings."""
    import torch
    fits = {json.loads(l)["key"]: json.loads(l) for l in open(ONE / "fits.jsonl")}
    R = [r for r in jl(D95 / "lines82.jsonl") if r["key"] in fits][:n]
    F, bt, P = rebuild_batch(R, fits)
    with torch.no_grad():
        R0 = F.render_batch(bt, P).numpy()
    for it in bt.items:
        for g in it["inst"]:
            g["strokes"] = [(np.c_[p[:, :2], p[:, 2]] if p.shape[1] == 3 else p, mk)
                            for p, rt, mk in [(q, rt, mk) for q, rt, mk in routes(g["strokes"], "order")]]
    # rebuild the segments from the routed strokes
    W = use_programs()
    import torch as T
    segs = [W.segments(it["inst"], w) for it, w in zip(bt.items, bt.widths)]
    bt.a = T.cat([s.a for s in segs]); bt.b = T.cat([s.b for s in segs])
    bt.ra = T.cat([s.ra for s in segs]); bt.rb = T.cat([s.rb for s in segs])
    bt.mark = T.cat([s.mark for s in segs]); bt.above = T.cat([s.above for s in segs])
    n_ = [len(s.a) for s in segs]
    bt.line = T.cat([T.full((k,), i, dtype=T.long) for i, k in enumerate(n_)])
    bt.seg_off = np.concatenate([[0], np.cumsum(n_)])
    with torch.no_grad():
        R1 = F.render_batch(bt, P).numpy()
    d = np.abs(R0 - R1).max()
    print("max |ink(edges) - ink(one pen + order)| =", float(d), "; binary pixels differing:", int(((R0 > 0.5) != (R1 > 0.5)).sum()))
    (ONE / "check.json").write_text(json.dumps(dict(lines=n, max_abs_diff=float(d), binary_diff=int(((R0 > 0.5) != (R1 > 0.5)).sum()))))


def anim(keys=None, fracs=(0.35, 0.5, 0.65)):
    """Mid-frames of the stroke animation: the pen path drawn up to a share of its length, the pen tip in red;
    edges (each its own pen-down, the order of the program) against one pen + order."""
    import cv2
    fits = {json.loads(l)["key"]: json.loads(l) for l in open(ONE / "fits.jsonl")}
    R = [r for r in jl(D95 / "lines82.jsonl") if r["key"] in fits]
    if keys:
        R = [r for r in R if r["key"] in keys]
    else:
        R = R[:2] + [r for r in R if r["faces"] == "traced"][:1]
    F, bt, P = rebuild_batch(R, fits)
    S = 3
    panels = []
    for i, r in enumerate(R):
        grey = cv2.imread(str(D95 / "crops/l82" / f"{r['key']}.png"), 0)
        for mode in ("edges", "order"):
            sig = signal_of(F, bt, P, i, mode)
            segs = []
            for st in sig["strokes"]:
                p = st["pts"]
                for j in range(len(p) - 1):
                    segs.append((p[j], p[j + 1], st["retrace"][j + 1] if j + 1 < len(st["retrace"]) else 0))
            Ls = np.array([np.hypot(*(b - a)) for a, b, _ in segs])
            cum = np.cumsum(Ls)
            row = []
            for fr in fracs:
                img = cv2.cvtColor(cv2.resize(grey, None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
                img = (255 - 0.25 * (255 - img.astype(np.float32))).astype(np.uint8)
                lim = fr * cum[-1]
                tip = None
                for (a, b, rt), c in zip(segs, cum):
                    if c > lim:
                        break
                    pa, pb = (int(a[1] * S), int(a[0] * S)), (int(b[1] * S), int(b[0] * S))
                    cv2.line(img, pa, pb, (200, 140, 40) if not rt else (120, 200, 120), 2, cv2.LINE_AA)
                    tip = pb
                if tip:
                    cv2.circle(img, tip, 6, (30, 30, 230), -1)
                cv2.putText(img, f"{'two pens: edges' if mode == 'edges' else 'one pen + order'}  {int(fr * 100)}%",
                            (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 60), 1, cv2.LINE_AA)
                row.append(img)
            panels.append(np.hstack([np.pad(x, ((4, 4), (4, 4), (0, 0)), constant_values=255) for x in row]))
    Wm = max(p.shape[1] for p in panels)
    out = np.vstack([np.pad(p, ((0, 0), (0, Wm - p.shape[1]), (0, 0)), constant_values=255) for p in panels])
    (OUT / "look").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / "look/onepen_frames.png"), out)
    print(OUT / "look/onepen_frames.png", out.shape)


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "data":
        data(int(sys.argv[2]) if len(sys.argv) > 2 else 120)
    elif c == "fit":
        fit()
    elif c == "score":
        score()
    elif c == "check":
        check()
    elif c == "anim":
        anim(sys.argv[2:] or None)
