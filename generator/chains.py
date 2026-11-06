"""Module G data: matrix-chain dimensions and drum (rod) prices."""
from common import clamp


def gen_pipeline(case, rng):
    n = case.size("stages", rng)
    dims = []
    for _ in range(n + 1):
        r = rng.random()
        if r < 0.25:
            dims.append(rng.randint(2, 10))       # narrow bottleneck stages
        elif r < 0.8:
            dims.append(rng.randint(10, 60))
        else:
            dims.append(rng.randint(60, 100))
    return dims


def gen_drum(case, rng):
    while True:
        L = case.size("drum", rng)
        unit = rng.uniform(2.0, 9.0)
        bonus = set(rng.sample(range(2, L + 1), max(1, min(L - 1, L // 5, 25))))
        sat = rng.randint(400, 500)
        prices = []
        for j in range(1, L + 1):
            p = unit * j * rng.uniform(0.8, 1.2)
            if j in bonus:
                p *= rng.uniform(1.1, 1.45)       # standard lengths sell at a premium
            p = round(p)
            if p > sat:
                p = rng.randint(sat - 150, sat)   # long pieces saturate the market
            prices.append(clamp(p, 1, 500))
        if any(prices[j - 1] != j * prices[0] for j in range(1, L + 1)):
            return prices


def drum_opt_exhaustive(prices):
    """Best total price by enumerating every partition of L."""
    L = len(prices)
    best = 0

    def rec(rest, maxpart, acc):
        nonlocal best
        if rest == 0:
            best = max(best, acc)
            return
        for p in range(min(rest, maxpart), 0, -1):
            rec(rest - p, p, acc + prices[p - 1])

    rec(L, L, 0)
    return best
