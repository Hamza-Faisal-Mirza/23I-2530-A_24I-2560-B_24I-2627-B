"""Module A data: crates and truck capacity (plus trap cases 46 and 47)."""
from bisect import bisect_right
from fractions import Fraction

from common import ceil_div, clamp

# Per-category profile: weight range (kg), value range, expiry range (hour).
CAT_SPEC = {
    0: dict(w=(4, 20), v=(10, 55), e=(72, 999)),    # Food: bulky, cheap, keeps
    1: dict(w=(6, 20), v=(15, 65), e=(150, 999)),   # Water: heaviest
    2: dict(w=(1, 8), v=(40, 100), e=(24, 720)),    # Medicine: light, valuable, spoils
    3: dict(w=(3, 18), v=(25, 85), e=(600, 999)),   # Tool: durable
    4: dict(w=(1, 12), v=(60, 100), e=(0, 999)),    # Rare equipment
}
# Background category mix per scenario (used for the crates that are not forced).
BASE_PROBS = {
    1: [36, 30, 14, 12, 8], 2: [18, 14, 30, 28, 10], 3: [25, 25, 20, 20, 10],
    4: [22, 20, 18, 18, 22], 5: [25, 20, 20, 25, 10], 6: [12, 33, 35, 10, 10],
}
# Forced share per scenario: (categories, minimum percent, drawn share range).
FORCED = {1: ((0, 1), 55, (0.58, 0.72)), 2: ((2, 3), 45, (0.48, 0.62)),
          4: ((4,), 10, (0.12, 0.20)), 6: ((1, 2), 55, (0.58, 0.72))}


def knapsack_exhaustive(ws, vs, cap):
    """Exact optimum by enumerating every subset (meet in the middle)."""
    n = len(ws)
    h = n // 2

    def enum(idx):
        res = [(0, 0)]
        for i in idx:
            res += [(w + ws[i], v + vs[i]) for (w, v) in res]
        return res

    A = enum(range(h))
    B = sorted(enum(range(h, n)))
    bw = [w for w, _ in B]
    best, m = [], -1
    for _, v in B:
        m = max(m, v)
        best.append(m)
    ans = 0
    for w, v in A:
        if w <= cap:
            j = bisect_right(bw, cap - w) - 1
            ans = max(ans, v + best[j])
    return ans


def greedy_ratio(ws, vs, cap):
    order = sorted(range(len(ws)), key=lambda i: (-Fraction(vs[i], ws[i]), i))
    load = val = 0
    for i in order:
        if load + ws[i] <= cap:
            load += ws[i]
            val += vs[i]
    return val


def ratios_distinct(ws, vs):
    return len({Fraction(v, w) for w, v in zip(ws, vs)}) == len(ws)


SERIAL_BLOCK = 1_800_000          # 50 blocks x 1.8M = the whole 8-digit range


def _serials(rng, n, k):
    """Distinct 8-digit serials; case k draws from its own block, so serials
    are also distinct across the whole workbook."""
    lo = 10_000_000 + k * SERIAL_BLOCK
    return rng.sample(range(lo, lo + SERIAL_BLOCK), n)


def _capacity(rng, W, lo_f, hi_f):
    lo, hi = max(1, ceil_div(W, 10)), (7 * W) // 10
    return clamp(round(W * rng.uniform(lo_f, hi_f)), lo, hi)


def _normal(case, rng):
    n = case.size("crates", rng)
    scen = case.scenario
    cats = []
    if scen in FORCED:
        forced, pct, (a, b) = FORCED[scen]
        k = max(ceil_div(pct * n, 100), round(n * rng.uniform(a, b)))
        cats = [rng.choice(forced) for _ in range(k)]
    cats += rng.choices(range(5), weights=BASE_PROBS[scen], k=n - len(cats))
    rng.shuffle(cats)
    rows = []
    for c in cats:
        s = CAT_SPEC[c]
        rows.append([c, rng.randint(*s["w"]), rng.randint(*s["v"]), rng.randint(*s["e"])])
    if scen == 6:   # outbreak: supplies spoil -> at least half expire by hour 300
        k = max(ceil_div(n, 2), round(n * rng.uniform(0.55, 0.7)))
        for i in rng.sample(range(n), k):
            rows[i][3] = rng.randint(6, 300)
    for r, s in zip(rows, _serials(rng, n, case.k)):
        r.append(s)
    W = sum(r[1] for r in rows)
    cap = _capacity(rng, W, 0.2, 0.5)
    return rows, cap


def _trap46(case, rng):
    """Dock-order trap: list already monotone in all five fields."""
    n = case.size("crates", rng)
    weights = sorted(rng.randint(1, 20) for _ in range(n))                  # non-decreasing
    values = sorted((rng.randint(10, 100) for _ in range(n)), reverse=True)  # non-increasing
    expiry = sorted((rng.randint(0, 999) for _ in range(n)), reverse=True)   # non-increasing
    serials = sorted(_serials(rng, n, case.k))                                       # increasing
    cats = rng.choices(range(5), weights=BASE_PROBS[5], k=n)
    rows = [[cats[i], weights[i], values[i], expiry[i], serials[i]] for i in range(n)]
    cap = _capacity(rng, sum(weights), 0.15, 0.3)
    return rows, cap


def _trap47(case, rng):
    """Best-looking-crate trap: one light decoy with the best value per kg
    blocks the second heavy crate, so ratio-greedy gets ~55% of the optimum."""
    n = case.size("crates", rng)
    heavy_vals = rng.sample(range(80, 101), n - 1)
    rows = [[rng.choice((1, 2)), 20, v, rng.randint(6, 400)] for v in heavy_vals]
    rows.append([2, 1, 10, rng.randint(6, 300)])     # the decoy: 10 per kg
    rng.shuffle(rows)
    for r, s in zip(rows, _serials(rng, n, case.k)):
        r.append(s)
    return rows, 40


def generate(case, want_greedy_fail):
    """Return (rows, capacity, info). rows: [cat, weight, value, expiry, serial]."""
    for attempt in range(500):
        rng = case.rng("crates", attempt)
        if case.k == 46:
            rows, cap = _trap46(case, rng)
        elif case.k == 47:
            rows, cap = _trap47(case, rng)
        else:
            rows, cap = _normal(case, rng)
        ws = [r[1] for r in rows]
        vs = [r[2] for r in rows]
        info = {}
        if case.tier == "S" or case.k == 47:
            if not ratios_distinct(ws, vs):
                continue          # keep the greedy order unambiguous
            opt = knapsack_exhaustive(ws, vs, cap)
            gr = greedy_ratio(ws, vs, cap)
            info = dict(opt=opt, greedy=gr)
            if case.k == 47 and 100 * gr > 58 * opt:
                continue
            if want_greedy_fail and gr == opt:
                continue
        return rows, cap, info
    raise RuntimeError(f"crates: no valid instance for case {case.case_id}")
