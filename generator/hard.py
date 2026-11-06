"""Module H data: sensor graph + planted cover, planted 3-SAT safety rules,
planted subset-sum rations."""
from itertools import combinations

RATIO_BUCKETS = {"low": (2.6, 3.3), "mid": (3.7, 4.6), "high": (5.0, 5.9), None: (2.2, 5.8)}


def gen_sensors(case, rng):
    n = case.size("sensors", rng)
    k = rng.randint(max(2, n // 4), n // 2)
    cover = sorted(rng.sample(range(n), k))
    cset = set(cover)
    non = [v for v in range(n) if v not in cset]
    edges = set()
    for v in non:
        for c in rng.sample(cover, rng.randint(1, min(3, k))):
            edges.add((min(v, c), max(v, c)))
    p_in = 0.3 if case.tier == "S" else 0.05
    for a, b in combinations(cover, 2):
        if rng.random() < p_in:
            edges.add((a, b))
    for c in cover:
        if not any(c in e for e in edges):
            o = rng.choice([v for v in range(n) if v != c])
            edges.add((min(c, o), max(c, o)))
    while len(edges) < n - 1:
        c = rng.choice(cover)
        o = rng.choice([v for v in range(n) if v != c])
        edges.add((min(c, o), max(c, o)))
    return n, sorted(edges), cover


def min_cover_exhaustive(n, edges):
    for size in range(0, n + 1):
        for sub in combinations(range(n), size):
            s = set(sub)
            if all(u in s or v in s for u, v in edges):
                return size
    return n


def gen_safety(case, rng, bucket):
    N = case.size("safety", rng)
    lo, hi = RATIO_BUCKETS[bucket]
    m = round(rng.uniform(lo, hi) * N)
    assign = [None] + [rng.randint(0, 1) for _ in range(N)]
    clauses, seen = [], set()
    while len(clauses) < m:
        vs = rng.sample(range(1, N + 1), 3)
        lits = [v if rng.random() < 0.5 else -v for v in vs]
        if not any((l > 0 and assign[l] == 1) or (l < 0 and assign[-l] == 0) for l in lits):
            continue                          # rule would be violated by the plant
        key = tuple(sorted(lits))
        if key in seen:
            continue
        seen.add(key)
        clauses.append(lits)
    return N, clauses, assign[1:]


def gen_rations(case, rng):
    q = case.size("rations", rng)
    lo = 5 if case.tier == "S" else 100
    hi = 300 if case.tier == "S" else 1000
    values = [rng.randint(lo, hi) for _ in range(q)]
    k = rng.randint(2, max(2, q // 2))
    planted = set(rng.sample(range(q), k))
    flags = [1 if i in planted else 0 for i in range(q)]
    return values, flags, sum(values[i] for i in planted)
