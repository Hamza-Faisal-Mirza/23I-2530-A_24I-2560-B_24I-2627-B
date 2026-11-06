"""Modules B/F data: locations, roads, closure waves and the three targets.

Internal construction uses node 0 as the HQ; all other nodes are relabelled with
a random permutation so that loc_id order does not reveal the construction.
The cost of the step u -> v is minutes(u, v) + penalty(v).
"""
import heapq
import math
from collections import deque

from common import ceil_div, clamp

PENS = [0, 1, 2, 4, 6]
PEN_PROBS = {1: [30, 30, 20, 12, 8], 2: [35, 25, 20, 12, 8], 3: [40, 25, 20, 10, 5],
             4: [45, 30, 15, 7, 3], 5: [40, 25, 20, 10, 5], 6: [50, 25, 15, 7, 3]}
MINUTE_SCALE = {1: 1.3, 2: 1.4, 3: 1.0, 4: 0.7, 5: 1.5, 6: 1.0}


# ----------------------------------------------------------------- graph tools
def adjacency(V, roads, banned=frozenset()):
    adj = [[] for _ in range(V)]
    for rid, (u, v, mi, _c) in enumerate(roads):
        if rid in banned:
            continue
        adj[u].append((v, mi))
        adj[v].append((u, mi))
    return adj


def bfs(V, adj, src=0):
    dist = [-1] * V
    dist[src] = 0
    dq = deque([src])
    while dq:
        u = dq.popleft()
        for v, _ in adj[u]:
            if dist[v] < 0:
                dist[v] = dist[u] + 1
                dq.append(v)
    return dist


def dijkstra(V, adj, pen, src=0):
    INF = float("inf")
    dist = [INF] * V
    dist[src] = 0
    pq = [(0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, mi in adj[u]:
            nd = d + mi + pen[v]
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def minhop_cost(V, adj, pen, hop):
    """Cheapest cost among routes that use the fewest roads (DP on BFS layers)."""
    INF = float("inf")
    c = [INF] * V
    c[0] = 0
    for u in sorted((x for x in range(V) if hop[x] >= 0), key=lambda x: hop[x]):
        for v, mi in adj[u]:
            if hop[v] == hop[u] + 1 and c[u] + mi + pen[v] < c[v]:
                c[v] = c[u] + mi + pen[v]
    return c


# ------------------------------------------------------------ types/penalties
def _types(case, rng, V, forced=None, exclude=()):
    types = ["J"] * V
    types[0] = "D"
    forced = forced or {}
    for v, t in forced.items():
        types[v] = t
    scen = case.scenario
    if scen == 3 and not case.is_trap:
        nS = ceil_div(V, 4) + rng.randint(0, max(1, V // 10))
    else:
        nS = max(1, round(V * rng.uniform(0.12, 0.2)))
    nH = max(1, round(V * rng.uniform(0.05, 0.1)))
    if nS + nH < 3:
        nS = 3 - nH
    nD = rng.randint(0, V // 40)
    nS -= sum(1 for t in forced.values() if t == "S")
    nH -= sum(1 for t in forced.values() if t == "H")
    free = [v for v in range(1, V) if v not in forced and v not in exclude]
    rng.shuffle(free)
    for t, cnt in (("S", nS), ("H", nH), ("D", nD)):
        for _ in range(max(0, cnt)):
            types[free.pop()] = t
    return types


def _penalties(case, rng, V):
    pen = [0] * V
    if case.scenario == 1 and not case.is_trap:
        h = min(V - 1, max(ceil_div(4 * V, 10), round(V * rng.uniform(0.45, 0.6))))
        high = set(rng.sample(range(1, V), h))
        for v in range(1, V):
            pen[v] = rng.choices([2, 4, 6], [5, 3, 2])[0] if v in high else rng.choice([0, 1])
    else:
        for v in range(1, V):
            pen[v] = rng.choices(PENS, PEN_PROBS[case.scenario])[0]
    return pen


def _edge_range(case, V):
    s = case.scenario
    maxE = min(3 * V, V * (V - 1) // 2)
    if s == 1:
        lo, hi = ceil_div(11 * V, 10), (16 * V) // 10
    elif s == 2:
        lo, hi = V, (13 * V) // 10
    elif s == 4:
        lo, hi = ceil_div(185 * V, 100), min((26 * V) // 10, maxE)
        lo = min(max(lo, ceil_div(7 * V, 4)), hi)
    elif s == 3:
        lo, hi = ceil_div(115 * V, 100), (16 * V) // 10
    else:
        lo, hi = ceil_div(11 * V, 10), (15 * V) // 10
    return max(lo, V - 1), min(hi, maxE)


# ------------------------------------------------------------------ builders
def _generic(case, rng, V):
    scen = case.scenario
    loE, hiE = _edge_range(case, V)
    E = rng.randint(loE, hiE)
    seen, pts = set(), []
    while len(pts) < V:
        p = (rng.randint(0, 999), rng.randint(0, 999))
        if p not in seen:
            seen.add(p)
            pts.append(p)

    def d2(i, j):
        return (pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2

    edges = set()
    for i in range(1, V):                       # geometric spanning tree
        near = heapq.nsmallest(2, range(i), key=lambda j: (d2(i, j), j))
        j = rng.choice(near)
        edges.add((j, i))
    kk = min(V - 1, ceil_div(2 * E, V) + 3)
    cand = set()
    for i in range(V):                          # local extra roads
        for j in heapq.nsmallest(kk + 1, range(V), key=lambda j: (d2(i, j), j)):
            if j != i:
                cand.add((min(i, j), max(i, j)))
    cand = sorted(cand - edges)
    rng.shuffle(cand)
    for e in cand:
        if len(edges) >= E:
            break
        edges.add(e)
    if len(edges) < E:
        rest = sorted({(a, b) for a in range(V) for b in range(a + 1, V)} - edges)
        rng.shuffle(rest)
        for e in rest[:E - len(edges)]:
            edges.add(e)
    f = 12 * math.sqrt(V) / 500 * MINUTE_SCALE[scen]
    roads = []
    for a, b in sorted(edges):
        d = math.sqrt(d2(a, b))
        mi = clamp(round(d * f) + rng.randint(-2, 4), 1, 60)
        cb = clamp(round(d * f * rng.uniform(0.8, 2.2)) + rng.randint(0, 8), 1, 100)
        roads.append((a, b, mi, cb))
    types = _types(case, rng, V)
    pen = _penalties(case, rng, V)
    return dict(V=V, roads=roads, types=types, pen=pen)


def _corridor(case, rng, V):
    """Scenario 5: one highway (path from the HQ) with short spurs and a few
    local loops; loops never connect two highway nodes, so the far end of the
    highway stays P-1 roads from the HQ."""
    P = min(V, max(V // 4 + 2, round(V * rng.uniform(0.45, 0.6))))
    deg = [0] * V
    pos = list(range(V))
    edges = {}

    def add(a, b, kind):
        edges[(min(a, b), max(a, b))] = kind
        deg[a] += 1
        deg[b] += 1

    for i in range(P - 1):
        add(i, i + 1, "hwy")
    for s in range(P, V):
        path_el = [u for u in range(P) if deg[u] < 4]
        spur_el = [u for u in range(P, s) if deg[u] < 4]
        pool = path_el if (path_el and (rng.random() < 0.6 or not spur_el)) else spur_el
        u = rng.choice(pool)
        add(u, s, "spur")
        pos[s] = pos[u]
    E_target = rng.randint(V - 1, (12 * V) // 10)
    by_pos = {}
    for v in range(V):
        by_pos.setdefault(pos[v], []).append(v)
    cand = []
    for a in range(P, V):                        # loops start at a spur node
        for p in range(pos[a] - 2, pos[a] + 3):
            for b in by_pos.get(p, []):
                if b != a and (min(a, b), max(a, b)) not in edges:
                    cand.append((min(a, b), max(a, b)))
    cand = sorted(set(cand))
    rng.shuffle(cand)
    for a, b in cand:
        if len(edges) >= E_target:
            break
        if deg[a] < 4 and deg[b] < 4 and (a, b) not in edges:
            add(a, b, "loop")
    roads = []
    for (a, b), kind in sorted(edges.items()):
        if kind == "hwy":
            mi, cb = rng.randint(5, 25), rng.randint(30, 100)
        elif kind == "spur":
            mi, cb = rng.randint(8, 45), rng.randint(5, 60)
        else:
            mi, cb = rng.randint(15, 60), rng.randint(10, 80)
        roads.append((a, b, mi, cb))
    types = _types(case, rng, V, forced={P - 1: "S"})
    pen = _penalties(case, rng, V)
    return dict(V=V, roads=roads, types=types, pen=pen, P=P)


def _trap48(case, rng, V):
    """Shortest-looks-cheapest: a long cheap delta road (backbone) and a short
    elevated causeway of slow roads from the HQ to a hospital on the backbone."""
    P = rng.randint(int(0.58 * V), int(0.64 * V))
    pT = rng.randint(250, 330)
    m = rng.randint(35, 60)
    edges = {}
    pos = [0] * V

    def add(a, b, mi, cb):
        edges[(min(a, b), max(a, b))] = (mi, cb)

    for i in range(P - 1):
        add(i, i + 1, rng.randint(1, 4), rng.randint(5, 40))
        pos[i + 1] = i + 1
    chain = [0] + list(range(P, P + m)) + [pT]
    for a, b in zip(chain, chain[1:]):
        add(a, b, rng.randint(50, 60), rng.randint(60, 100))
    for e in range(P, P + m):
        pos[e] = -10**6                       # express nodes take no part in loops
    for s in range(P + m, V):
        if s > P + m and rng.random() < 0.4:
            u = rng.randrange(P + m, s)
        else:
            u = rng.randrange(0, P)
        add(u, s, rng.randint(5, 40), rng.randint(5, 80))
        pos[s] = pos[u]
    loops = round(0.12 * V)
    tries = 0
    while loops > 0 and tries < 50 * V:
        tries += 1
        s = rng.randrange(P + m, V)
        b = pos[s] + rng.randint(-2, 2)
        if 0 <= b < P and (min(s, b), max(s, b)) not in edges:
            add(s, b, rng.randint(10, 50), rng.randint(5, 80))
            loops -= 1
    roads = [(a, b, mi, cb) for (a, b), (mi, cb) in sorted(edges.items())]
    types = _types(case, rng, V, forced={pT: "H"}, exclude=set(range(P, P + m)))
    pen = [0] * V
    for v in range(1, V):
        if v < P:
            pen[v] = rng.choice([0, 0, 1])
        elif v < P + m:
            pen[v] = rng.choice([4, 6])
        else:
            pen[v] = rng.choices(PENS, PEN_PROBS[1])[0]
    return dict(V=V, roads=roads, types=types, pen=pen, T=pT)


# ---------------------------------------------------------------- waves etc.
def _waves(case, rng, net, first=None):
    V, roads, pen = net["V"], net["roads"], net["pen"]
    E = len(roads)
    w = rng.randint(3, 5) if case.scenario in (1, 3, 5) else rng.randint(2, 5)
    size_hi = max(1, min(E // 4, E // 10))
    pool = [r for r in range(E) if r != first]
    if case.scenario == 1:     # flood: low-lying (high-penalty) roads go first
        low = [r for r in pool if max(pen[roads[r][0]], pen[roads[r][1]]) >= 2]
        low_set = set(low)
        hi_ = [r for r in pool if r not in low_set]
        rng.shuffle(low)
        rng.shuffle(hi_)
        pool = low + hi_
    else:
        rng.shuffle(pool)
    waves = []
    for i in range(w):
        sz = rng.randint(1, size_hi)
        wave = [first] if (i == 0 and first is not None) else []
        while len(wave) < sz:
            wave.append(pool.pop(0))
        waves.append(sorted(wave))
    return waves


def _relabel(rng, net):
    V = net["V"]
    perm = list(range(1, V))
    rng.shuffle(perm)
    lab = [0] + perm
    roads = []
    for a, b, mi, cb in net["roads"]:
        x, y = lab[a], lab[b]
        roads.append((min(x, y), max(x, y), mi, cb))
    order = list(range(len(roads)))
    rng.shuffle(order)
    remap = {old: new for new, old in enumerate(order)}
    out = dict(net)
    out["roads"] = [roads[i] for i in order]
    types, pen = [None] * V, [None] * V
    for i in range(V):
        types[lab[i]] = net["types"][i]
        pen[lab[i]] = net["pen"][i]
    out["types"], out["pen"] = types, pen
    out["lab"], out["road_remap"] = lab, remap
    return out


def generate(case, want_minhop_trap):
    for attempt in range(3000):
        rng = case.rng("network", attempt)
        V = case.size("V", rng)
        if case.k == 48:
            net = _trap48(case, rng, V)
        elif case.scenario == 5:
            net = _corridor(case, rng, V)
        else:
            net = _generic(case, rng, V)
        net = _relabel(rng, net)
        V, roads, types, pen = net["V"], net["roads"], net["types"], net["pen"]
        adj = adjacency(V, roads)
        hop = bfs(V, adj)
        if min(hop) < 0:
            continue
        shelters = [v for v in range(V) if types[v] in "SH"]
        if len(shelters) < 3:
            continue
        cost = dijkstra(V, adj, pen)
        mh = minhop_cost(V, adj, pen, hop)
        first = None
        if case.scenario == 5:
            # landslide: find a road whose collapse cuts a shelter/hospital off
            P = net["P"]
            lab = net["lab"]
            inv = {lab[i]: i for i in range(V)}     # label -> construction index
            hwy_ids = [rid for rid, (a, b, _m, _c) in enumerate(roads)
                       if abs(inv[a] - inv[b]) == 1 and inv[a] < P and inv[b] < P
                       and min(inv[a], inv[b]) >= P // 3]
            rng.shuffle(hwy_ids)
            for rid in hwy_ids:
                h2 = bfs(V, adjacency(V, roads, banned={rid}))
                if any(h2[t] < 0 for t in shelters):
                    first = rid
                    break
            if first is None:
                continue
            if max(hop) < V // 4:
                continue
        waves = _waves(case, rng, net, first)
        closed = {r for w in waves for r in w}
        h_after = bfs(V, adjacency(V, roads, banned=closed))
        if case.k == 48:
            t0 = net["lab"][net["T"]]
            if not (max(hop) >= 500 and 2 * mh[t0] >= 3 * cost[t0]):
                continue
            pool = [t0]
        elif case.scenario == 5:
            pool = [t for t in shelters if h_after[t] < 0]
        else:
            pool = [t for t in shelters if mh[t] > cost[t]]
            if not want_minhop_trap:
                pool = shelters
        if not pool:
            continue
        t0 = rng.choice(sorted(pool))
        rest = sorted(t for t in shelters if t != t0)
        t1, t2 = rng.sample(rest, 2)
        return dict(V=V, roads=roads, types=types, pen=pen, waves=waves,
                    targets=[t0, t1, t2],
                    info=dict(minhop_trap=any(mh[t] > cost[t] for t in (t0, t1, t2)),
                              ecc=max(hop)))
    raise RuntimeError(f"network: no valid instance for case {case.case_id}")
