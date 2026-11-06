"""Modules C and D data: rescue windows and incident alarms."""
from bisect import bisect_left, bisect_right

from common import ceil_div, clamp

DURATIONS = {1: (60, 300), 2: (30, 240), 3: (5, 75), 4: (15, 120), 5: (60, 480), 6: (30, 360)}
PRIORITY_WEIGHTS = {
    1: [8, 10, 12, 12, 12, 12, 10, 9, 8, 7],
    2: [4, 2, 2, 3, 4, 8, 12, 16, 20, 22],      # earthquake: urgent calls dominate
    3: [6, 6, 8, 10, 12, 12, 12, 12, 12, 10],
    4: [10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
    5: [6, 8, 10, 12, 12, 12, 12, 10, 10, 8],
    6: [10, 12, 12, 12, 10, 10, 10, 8, 8, 8],
}


def overlap_total(wins):
    """Sum over windows of the number of other windows that overlap it
    (touching is not overlapping)."""
    starts = sorted(s for s, f, _ in wins)
    fins = sorted(f for s, f, _ in wins)
    n = len(wins)
    tot = 0
    for s, f, _ in wins:
        disjoint = bisect_right(fins, s) + (n - bisect_left(starts, f))
        tot += n - 1 - disjoint
    return tot


def touching_pairs(wins):
    starts = {}
    for s, _f, _ in wins:
        starts[s] = starts.get(s, 0) + 1
    return sum(starts.get(f, 0) for _s, f, _ in wins)


def gen_windows(case, want_overlap):
    for attempt in range(500):
        rng = case.rng("windows", attempt)
        n = case.size("windows", rng)
        scen = case.scenario if not case.is_trap else (case.k % 6 + 1)
        dlo, dhi = DURATIONS[scen]
        centers = [rng.randint(90, 1350) for _ in range(rng.randint(2, max(2, n // 6)))]
        wins = []
        for _ in range(n):
            d = rng.randint(dlo, dhi)
            if scen == 3:              # storm-surge bursts: short, overlapping
                c = rng.choice(centers)
                s = clamp(round(rng.gauss(c - d / 2, 35)), 0, 1440 - d)
            else:
                s = rng.randint(0, 1440 - d)
            wins.append([s, s + d, rng.randint(1, 100)])
        # plant a chain of three touching windows (two touching pairs)
        i, j, l = rng.sample(range(n), 3)
        d1, d2, d3 = (wins[x][1] - wins[x][0] for x in (i, j, l))
        t0 = rng.randint(0, 1440 - d1 - d2 - d3)
        if scen == 3:
            t0 = clamp(rng.choice(centers) - d1, 0, 1440 - d1 - d2 - d3)
        wins[i][:2] = [t0, t0 + d1]
        wins[j][:2] = [t0 + d1, t0 + d1 + d2]
        wins[l][:2] = [t0 + d1 + d2, t0 + d1 + d2 + d3]
        wins = [tuple(w) for w in wins]
        if touching_pairs(wins) < 2:
            continue
        if want_overlap and overlap_total(wins) < 5 * n // 2:
            continue
        return wins
    raise RuntimeError(f"windows: no valid instance for case {case.case_id}")


def gen_incidents(case):
    for attempt in range(500):
        rng = case.rng("incidents", attempt)
        n = case.size("alarms", rng)
        scen = case.scenario
        if case.tier == "S":
            T = max(2, round(n / rng.uniform(0.8, 1.6)))
        else:
            lo_num, lo_den = (3, 2) if (scen == 4 and not case.is_trap) else (6, 5)
            r = rng.uniform(1.55, 1.75) if (scen == 4 and not case.is_trap) else rng.uniform(1.25, 1.75)
            T = round(n / r)
            T = clamp(T, ceil_div(5 * n, 9), (lo_den * n) // lo_num)   # n/T in [lo, 1.8]
        centers = [rng.randrange(T) for _ in range(max(1, T // 40))]
        ticks = [0, T - 1]
        burst = set()
        for a in range(n - 2):
            if rng.random() < 0.45:
                ticks.append(clamp(round(rng.gauss(rng.choice(centers), max(1, T / 60))), 0, T - 1))
                burst.add(len(ticks) - 1)
            else:
                ticks.append(rng.randrange(T))
        w = PRIORITY_WEIGHTS[scen]
        pr = []
        for idx in range(n):
            p = rng.choices(range(1, 11), w)[0]
            if scen == 2 and idx in burst:            # aftershock bursts are urgent
                p = max(p, rng.randint(6, 10))
            pr.append(p)
        order = sorted(range(n), key=lambda x: (ticks[x], x))
        alarms = [(ticks[x], pr[x]) for x in order]
        prios = [p for _, p in alarms]
        if case.tier != "S":
            if len(set(prios)) < 6 or 1 not in prios:
                continue
            last = alarms[-1][0]
            if not (5 * n >= 6 * (last + 1) and 5 * n <= 9 * (last + 1)):
                continue
            if scen == 4 and not case.is_trap and 2 * n < 3 * (last + 1):
                continue
        if scen == 2 and sum(prios) < 6 * n:
            continue
        return alarms
    raise RuntimeError(f"incidents: no valid instance for case {case.case_id}")
