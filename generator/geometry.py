"""Modules H (tour) and I (closest pair) data: relief sites and a planted tour."""
from itertools import permutations

import numpy as np

from common import clamp


def gen_sites(case, rng):
    n = case.size("sites", rng)
    k = rng.randint(1, max(1, n // 8))
    centers = [(rng.randint(80, 920), rng.randint(80, 920)) for _ in range(k)]
    sigma = rng.randint(40, 160)
    seen, pts = set(), []
    while len(pts) < n:
        if rng.random() < 0.8:
            cx, cy = rng.choice(centers)
            p = (clamp(round(rng.gauss(cx, sigma)), 0, 999), clamp(round(rng.gauss(cy, sigma)), 0, 999))
        else:
            p = (rng.randint(0, 999), rng.randint(0, 999))
        if p not in seen:
            seen.add(p)
            pts.append(p)
    return pts


def manhattan_matrix(pts):
    a = np.array(pts, dtype=np.int64)
    return np.abs(a[:, None, 0] - a[None, :, 0]) + np.abs(a[:, None, 1] - a[None, :, 1])


def tour_length(pts, tour):
    n = len(tour)
    return sum(abs(pts[tour[i]][0] - pts[tour[(i + 1) % n]][0]) +
               abs(pts[tour[i]][1] - pts[tour[(i + 1) % n]][1]) for i in range(n))


def nearest_neighbour(D):
    n = D.shape[0]
    seen = [False] * n
    tour = [0]
    seen[0] = True
    for _ in range(n - 1):
        u = tour[-1]
        best = None
        for v in range(n):                     # ties -> smallest site_no
            if not seen[v] and (best is None or D[u, v] < D[u, best]):
                best = v
        tour.append(best)
        seen[best] = True
    return tour


def two_opt(tour, D, max_passes=1000):
    """Deterministic best-improvement 2-opt; site 0 stays at step 0."""
    t = np.array(tour, dtype=np.int64)
    n = len(t)
    for _ in range(max_passes):
        improved = False
        for i in range(n - 2):
            a, b = t[i], t[i + 1]
            js = np.arange(i + 2, n)
            c, d = t[js], t[(js + 1) % n]
            delta = D[a, c] + D[b, d] - D[a, b] - D[c, d]
            k = int(np.argmin(delta))
            if delta[k] < 0:
                j = i + 2 + k
                t[i + 1:j + 1] = t[i + 1:j + 1][::-1].copy()
                improved = True
        if not improved:
            break
    return [int(x) for x in t]


def planted_tour(pts):
    D = manhattan_matrix(pts)
    nn = nearest_neighbour(D)
    tour = two_opt(nn, D) if len(pts) >= 4 else nn
    return tour, tour_length(pts, tour), tour_length(pts, nn)


def tour_opt_exhaustive(pts):
    """Shortest closed tour by trying every permutation (site 0 fixed)."""
    n = len(pts)
    D = [[abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in pts] for p in pts]
    best = None
    for perm in permutations(range(1, n)):
        if perm[0] > perm[-1]:                  # each cycle once per direction
            continue
        L = D[0][perm[0]] + D[perm[-1]][0]
        for x, y in zip(perm, perm[1:]):
            L += D[x][y]
        if best is None or L < best:
            best = L
    return best
