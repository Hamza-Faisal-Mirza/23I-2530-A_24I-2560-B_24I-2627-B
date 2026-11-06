#!/usr/bin/env python3
"""LIFELINE workbook validator -- group 76.

    python validator/validate.py cases.xlsx --seed 76
    python validator/validate.py validator/tests/broken_xx.xlsx --partial

The validator trusts no field: every count, optimum, planted object, signature
rule and trap property is recomputed from the raw rows. It shares no code with
the generator, and where the generator uses exhaustive search the validator
uses a different exact method (DP, Held-Karp, branch and bound, KMP), so the two
programs cross-check each other.

--partial validates the cases that are present without requiring all 50 (used
for the single-case test copies); the cross-case variety rules are then skipped.
Exit code 0 = PASS, 1 = at least one broken rule.
"""
import argparse
import heapq
import re
import sys
import zipfile
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict, deque

import openpyxl

ALPHA = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
SPEC = [
    ("cases", ["case_id", "group_seed", "case_no", "tier", "scenario", "capacity",
               "target_0", "target_1", "target_2", "edit_bound", "tour_length",
               "sensor_nodes", "sensor_k", "safety_vars", "rations_target"]),
    ("crates", ["case_id", "crate_id", "cat", "weight", "value", "expiry", "serial"]),
    ("locations", ["case_id", "loc_id", "type", "penalty"]),
    ("roads", ["case_id", "road_no", "u", "v", "minutes", "cable"]),
    ("waves", ["case_id", "wave_no", "road_no"]),
    ("radio_log", ["case_id", "part", "text"]),
    ("radio_patterns", ["case_id", "pattern_no", "pattern", "count"]),
    ("radio_reports", ["case_id", "report_a", "report_b"]),
    ("windows", ["case_id", "window_id", "start", "finish", "value"]),
    ("incidents", ["case_id", "alarm_id", "tick", "priority"]),
    ("sites", ["case_id", "site_no", "x", "y"]),
    ("tour", ["case_id", "step", "site_no"]),
    ("pipeline_dims", ["case_id", "idx", "dim"]),
    ("drum_prices", ["case_id", "length", "price"]),
    ("sensor_edges", ["case_id", "u", "v"]),
    ("sensor_cover", ["case_id", "node"]),
    ("safety_rules", ["case_id", "rule_no", "lit_1", "lit_2", "lit_3"]),
    ("safety_planted", ["case_id", "switch", "value"]),
    ("rations", ["case_id", "item", "value", "planted"]),
    ("claims", ["case_id", "cargo_opt", "window_count_opt", "window_value_opt",
                "drum_opt", "tour_opt", "cover_min"]),
]
TEXT_COLS = {"case_id", "tier", "type", "text", "pattern", "report_a", "report_b"}
OFFICIAL = {
    "S": dict(crates=(8, 20), V=(6, 12), waves=(2, 5), log=(200, 500), report=(10, 30),
              windows=(8, 20), alarms=(10, 40), sites=(5, 9), stages=(4, 8), drum=(5, 14),
              sensors=(6, 14), safety=(6, 15), rations=(8, 20)),
    "M": dict(crates=(40, 200), V=(30, 150), waves=(2, 5), log=(2000, 10000), report=(30, 150),
              windows=(50, 300), alarms=(200, 1000), sites=(10, 16), stages=(15, 60),
              drum=(40, 200), sensors=(20, 40), safety=(20, 50), rations=(24, 40)),
    "L": dict(crates=(500, 1500), V=(500, 2000), waves=(2, 5), log=(20000, 100000),
              report=(200, 1000), windows=(1000, 3000), alarms=(2000, 5000), sites=(200, 500),
              stages=(100, 300), drum=(500, 2000), sensors=(100, 400), safety=(20, 50),
              rations=(50, 100)),
}
TRAP_RANGES = {46: {"crates": (1500, 3000)}, 47: {"crates": (12, 60)},
               48: {"V": (1500, 3000)}, 49: {"log": (50000, 100000)}}
PATTERN_LENGTHS = [2, 4, 8, 12, 20, 40]


def expected_tier(k):
    return "S" if k <= 19 else "M" if k <= 39 else "L" if k <= 45 else "X"


def size_range(tier, k, item):
    if k in TRAP_RANGES and item in TRAP_RANGES[k]:
        return TRAP_RANGES[k][item]
    return OFFICIAL["L" if tier == "X" else tier][item]


# =================================================================== algorithms
def knapsack_dp(ws, vs, cap):
    best = [0] * (cap + 1)
    for w, v in zip(ws, vs):
        for c in range(cap, w - 1, -1):
            if best[c - w] + v > best[c]:
                best[c] = best[c - w] + v
    return best[cap]


def ratio_greedy(ws, vs, cap):
    """Decreasing value per kg (exact comparison), ties by crate order."""
    import functools

    def cmp(i, j):
        a, b = vs[i] * ws[j], vs[j] * ws[i]
        return -1 if a > b else 1 if a < b else (i - j)
    load = val = 0
    for i in sorted(range(len(ws)), key=functools.cmp_to_key(cmp)):
        if load + ws[i] <= cap:
            load += ws[i]
            val += vs[i]
    return val


def ratio_ties(ws, vs):
    seen = set()
    for w, v in zip(ws, vs):
        from math import gcd
        g = gcd(v, w)
        key = (v // g, w // g)
        if key in seen:
            return True
        seen.add(key)
    return False


def kmp_positions(text, pat):
    m = len(pat)
    fail = [0] * m
    k = 0
    for i in range(1, m):
        while k and pat[i] != pat[k]:
            k = fail[k - 1]
        if pat[i] == pat[k]:
            k += 1
        fail[i] = k
    out, k = [], 0
    for i, ch in enumerate(text):
        while k and ch != pat[k]:
            k = fail[k - 1]
        if ch == pat[k]:
            k += 1
        if k == m:
            out.append(i - m + 1)
            k = fail[k - 1]
    return out


def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    row = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        diag, row[0] = row[0], i
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            cur = min(row[j] + 1, row[j - 1] + 1, diag + (ai != b[j - 1]))
            diag, row[j] = row[j], cur
    return row[len(b)]


def interval_opt(wins):
    """(most compatible windows, best total value); touching is compatible."""
    by_f = sorted(wins, key=lambda w: w[1])
    cnt, last = 0, -1
    for s, f, _ in by_f:                         # earliest-finish greedy
        if s >= last:
            cnt += 1
            last = f
    fins = [w[1] for w in by_f]
    dp = [0] * (len(by_f) + 1)                   # weighted interval DP
    for i, (s, f, v) in enumerate(by_f, 1):
        p = bisect_right(fins, s, 0, i - 1)
        dp[i] = max(dp[i - 1], dp[p] + v)
    return cnt, dp[-1]


def rod_dp(prices):
    L = len(prices)
    r = [0] * (L + 1)
    for j in range(1, L + 1):
        r[j] = max(prices[i - 1] + r[j - i] for i in range(1, j + 1))
    return r[L]


def held_karp(pts):
    n = len(pts)
    D = [[abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in pts] for p in pts]
    INF = float("inf")
    full = 1 << (n - 1)
    dp = [[INF] * n for _ in range(full)]
    for j in range(1, n):
        dp[1 << (j - 1)][j] = D[0][j]
    for mask in range(1, full):
        for j in range(1, n):
            cur = dp[mask][j]
            if cur == INF or not mask & (1 << (j - 1)):
                continue
            for t in range(1, n):
                bit = 1 << (t - 1)
                if not mask & bit and cur + D[j][t] < dp[mask | bit][t]:
                    dp[mask | bit][t] = cur + D[j][t]
    return min(dp[full - 1][j] + D[j][0] for j in range(1, n))


def min_vertex_cover(edges, n):
    best = [n]

    def rec(es, used):
        if used >= best[0]:
            return
        if not es:
            best[0] = used
            return
        u, v = es[0]
        for x in (u, v):
            rec([e for e in es if x not in e], used + 1)

    rec(list(edges), 0)
    return best[0]


def nn_tour_length(pts, prefer_low):
    n = len(pts)
    used = [False] * n
    used[0] = True
    cur, total = 0, 0
    for _ in range(n - 1):
        best, bd = None, None
        for v in range(n):
            if used[v]:
                continue
            d = abs(pts[cur][0] - pts[v][0]) + abs(pts[cur][1] - pts[v][1])
            if bd is None or d < bd or (d == bd and not prefer_low):
                best, bd = v, d
        used[best] = True
        total += bd
        cur = best
    return total + abs(pts[cur][0] - pts[0][0]) + abs(pts[cur][1] - pts[0][1])


def bfs_hops(V, adj, src, banned=frozenset()):
    dist = [-1] * V
    dist[src] = 0
    q = deque([src])
    while q:
        u = q.popleft()
        for v, _mi, rid in adj[u]:
            if rid not in banned and dist[v] < 0:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def cheapest(V, adj, pen, src):
    INF = float("inf")
    d = [INF] * V
    d[src] = 0
    pq = [(0, src)]
    while pq:
        du, u = heapq.heappop(pq)
        if du > d[u]:
            continue
        for v, mi, _rid in adj[u]:
            if du + mi + pen[v] < d[v]:
                d[v] = du + mi + pen[v]
                heapq.heappush(pq, (d[v], v))
    return d


def cheapest_fewest_roads(V, adj, pen, hop):
    INF = float("inf")
    layers = defaultdict(list)
    for v in range(V):
        if hop[v] >= 0:
            layers[hop[v]].append(v)
    c = [INF] * V
    c[0] = 0
    for h in sorted(layers):
        for v in layers[h]:
            if h == 0:
                continue
            for u, mi, _rid in adj[v]:
                if hop[u] == h - 1 and c[u] + mi + pen[v] < c[v]:
                    c[v] = c[u] + mi + pen[v]
    return c


def monotone(seq, key=None):
    inc = dec = True
    for a, b in zip(seq, seq[1:]):
        r = key(a, b) if key else (a > b) - (a < b)
        if r > 0:
            inc = False
        if r < 0:
            dec = False
    return inc or dec


# ====================================================================== loading
class Report:
    def __init__(self):
        self.case = defaultdict(list)
        self.glob = []

    def add(self, cid, rule, msg):
        (self.case[cid] if cid is not None else self.glob).append((rule, msg))


def load(path, rep):
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                    xml = zf.read(name)
                    if b"<mergeCell" in xml:
                        rep.add(None, "V1", f"{name}: merged cells are not allowed")
                    if re.search(rb"<f[ >]", xml):
                        rep.add(None, "V1", f"{name}: formulas are not allowed")
        wb = openpyxl.load_workbook(path, read_only=True)
    except Exception as ex:          # noqa: BLE001
        rep.add(None, "V1", f"cannot open workbook: {ex}")
        return None, None
    sheets = {ws.title: [tuple(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}
    names = list(wb.sheetnames)
    wb.close()
    return names, sheets


def parse(names, sheets, rep):
    expected = [n for n, _ in SPEC]
    if names != expected:
        rep.add(None, "V1", f"sheets are {names}; expected exactly {expected}")
    data = {}
    for name, header in SPEC:
        data[name] = defaultdict(list)
        rows = sheets.get(name)
        if rows is None:
            rep.add(None, "V1", f"sheet '{name}' is missing")
            continue
        if not rows:
            rep.add(None, "V1", f"sheet '{name}' has no header row")
            continue
        hdr = list(rows[0])
        while hdr and hdr[-1] is None:
            hdr.pop()
        if hdr != header:
            rep.add(None, "V1", f"sheet '{name}': header {hdr} != {header}")
        width, prev = len(header), None
        for rn, raw in enumerate(rows[1:], start=2):
            raw = list(raw)
            row, extra = raw[:width] + [None] * (width - len(raw)), raw[width:]
            if all(v is None for v in raw):
                rep.add(None, "V1", f"sheet '{name}' row {rn}: empty row")
                continue
            cid = row[0]
            if not isinstance(cid, str):
                rep.add(None, "V1", f"sheet '{name}' row {rn}: case_id {cid!r} is not text")
                continue
            bad = []
            if any(v is not None for v in extra):
                bad.append("cells beyond the header")
            for col, val in zip(header, row):
                if val is None:
                    bad.append(f"empty {col}")
                elif col in TEXT_COLS:
                    if not isinstance(val, str):
                        bad.append(f"{col}={val!r} is not text")
                    elif not val.isascii():
                        bad.append(f"{col} is not plain ASCII")
                elif isinstance(val, bool) or not isinstance(val, int):
                    bad.append(f"{col}={val!r} is not an integer")
            if bad:
                rep.add(cid, "V1", f"sheet '{name}' row {rn}: " + "; ".join(bad))
                continue
            key = (cid, row[1])
            if prev is not None and key < prev:
                rep.add(cid, "V1", f"sheet '{name}' row {rn}: rows not sorted by case_id, then {header[1]}")
            prev = key
            data[name][cid].append(tuple(row[1:]))
    return data


# ================================================================ case checking
class CaseCheck:
    def __init__(self, cid, data, rep, seed):
        self.cid, self.rep, self.seed = cid, rep, seed
        self.D = {name: data[name].get(cid, []) for name, _ in SPEC}
        self.f = {}                      # facts shared between checks

    def E(self, rule, msg):
        self.rep.add(self.cid, rule, msg)

    def many(self, rule, what, bad):
        if bad:
            ex = ", ".join(str(b) for b in bad[:3])
            more = f" (+{len(bad) - 3} more)" if len(bad) > 3 else ""
            self.E(rule, f"{what}: {ex}{more}")

    def inrange(self, item, n, what):
        lo, hi = size_range(self.tier, self.k, item)
        if not lo <= n <= hi:
            self.E("V2", f"{what} = {n}, outside {lo}..{hi} for tier {self.tier}")

    def ids(self, rule, sheet, seq, start):
        if seq != list(range(start, start + len(seq))):
            self.E(rule, f"{sheet}: ids must run {start}, {start + 1}, ... without gaps or repeats")

    # ------------------------------------------------------------------ run
    def run(self):
        rows = self.D["cases"]
        if len(rows) != 1:
            self.E("V1", f"{len(rows)} rows in sheet 'cases' (expected 1)")
            return
        (self.gseed, self.k, tier, scen, self.cap, t0, t1, t2, self.ebound, self.tlen,
         self.sn, self.sk, self.svars, self.rtarget) = rows[0]
        self.targets = [t0, t1, t2]
        m = re.fullmatch(r"(\d+)-(\d{2})", self.cid)
        if not m or self.cid != f"{self.gseed}-{self.k:02d}":
            self.E("V1", f"case_id must be '<group_seed>-<case_no as 2 digits>' "
                         f"(group_seed={self.gseed}, case_no={self.k})")
        if self.seed is not None and self.gseed != self.seed:
            self.E("V1", f"group_seed {self.gseed} != {self.seed}")
        if not 0 <= self.k <= 49:
            self.E("V1", f"case_no {self.k} outside 0..49")
            return
        self.tier = expected_tier(self.k)
        self.scen = self.k % 6 + 1
        if tier != self.tier:
            self.E("V1", f"tier '{tier}' but case_no {self.k} is tier {self.tier}")
        if scen != self.scen:
            self.E("V1", f"scenario {scen} but case_no {self.k} is scenario {self.scen}")
        for fn in (self.crates, self.network, self.radio, self.windows, self.incidents,
                   self.sites_tour, self.chains, self.sensors, self.safety, self.rations,
                   self.claims, self.signature, self.trap):
            try:
                fn()
            except Exception as ex:      # noqa: BLE001
                self.E("V?", f"check '{fn.__name__}' could not run on this data: {ex!r}")

    # --------------------------------------------------------------- crates
    def crates(self):
        rows = self.D["crates"]
        n = len(rows)
        self.inrange("crates", n, "number of crates")
        self.ids("V3", "crates.crate_id", [r[0] for r in rows], 1)
        self.many("V2", "crates: cat not in 0..4 at crate_id", [r[0] for r in rows if not 0 <= r[1] <= 4])
        self.many("V2", "crates: weight not in 1..20 at crate_id", [r[0] for r in rows if not 1 <= r[2] <= 20])
        self.many("V2", "crates: value not in 10..100 at crate_id", [r[0] for r in rows if not 10 <= r[3] <= 100])
        self.many("V2", "crates: expiry not in 0..999 at crate_id", [r[0] for r in rows if not 0 <= r[4] <= 999])
        self.many("V2", "crates: serial not 8 digits at crate_id", [r[0] for r in rows if not 10**7 <= r[5] < 10**8])
        dup = [s for s, c in Counter(r[5] for r in rows).items() if c > 1]
        self.many("V3", "crates: repeated serial", dup)
        W = sum(r[2] for r in rows)
        if self.cap < 1 or 10 * self.cap < W or 10 * self.cap > 7 * W:
            self.E("V2", f"capacity {self.cap} is not 10%..70% of total weight {W} (and >= 1)")
        self.f["ws"] = [r[2] for r in rows]
        self.f["vs"] = [r[3] for r in rows]

    # -------------------------------------------------------------- network
    def network(self):
        L = self.D["locations"]
        V = len(L)
        self.inrange("V", V, "number of locations V")
        self.ids("V3", "locations.loc_id", [r[0] for r in L], 0)
        types = {r[0]: r[1] for r in L}
        pen = {r[0]: r[2] for r in L}
        self.many("V2", "locations: type not D/S/H/J at loc_id", [r[0] for r in L if r[1] not in ("D", "S", "H", "J")])
        self.many("V2", "locations: penalty not in {0,1,2,4,6} at loc_id", [r[0] for r in L if r[2] not in (0, 1, 2, 4, 6)])
        if types.get(0) != "D" or pen.get(0) != 0:
            self.E("V2", "location 0 (HQ) must be type D with penalty 0")
        if "S" not in types.values() or "H" not in types.values():
            self.E("V2", "need at least one shelter (S) and one hospital (H)")
        R = self.D["roads"]
        E = len(R)
        self.ids("V3", "roads.road_no", [r[0] for r in R], 0)
        if not V - 1 <= E <= 3 * V:
            self.E("V2", f"E = {E} roads, outside V-1..3V = {V - 1}..{3 * V}")
        self.many("V3", "roads: end point is not a location at road_no", [r[0] for r in R if r[1] not in types or r[2] not in types])
        self.many("V2", "roads: u < v violated at road_no", [r[0] for r in R if not r[1] < r[2]])
        pairs = Counter((min(r[1], r[2]), max(r[1], r[2])) for r in R)
        self.many("V3", "roads: repeated pair", [p for p, c in pairs.items() if c > 1])
        self.many("V2", "roads: minutes not in 1..60 at road_no", [r[0] for r in R if not 1 <= r[3] <= 60])
        self.many("V2", "roads: cable not in 1..100 at road_no", [r[0] for r in R if not 1 <= r[4] <= 100])
        ok_ids = list(range(V)) == [r[0] for r in L]
        adj = [[] for _ in range(V)]
        for rid, u, v, mi, _cb in R:
            if ok_ids and 0 <= u < V and 0 <= v < V and u != v:
                adj[u].append((v, mi, rid))
                adj[v].append((u, mi, rid))
        hop = bfs_hops(V, adj, 0) if V else []
        if V and min(hop) < 0:
            self.E("V4", f"network is not connected before closures "
                         f"({sum(1 for h in hop if h < 0)} locations unreachable from HQ)")
        tg = self.targets
        if len(set(tg)) != 3:
            self.E("V3", f"targets {tg} are not distinct")
        for t in tg:
            if t not in types:
                self.E("V3", f"target {t} is not a location")
            elif t == 0 or types[t] not in ("S", "H"):
                self.E("V3", f"target {t} must be a shelter or hospital other than the HQ")
        Wv = self.D["waves"]
        wave_nos = sorted({r[0] for r in Wv})
        if wave_nos != list(range(1, len(wave_nos) + 1)):
            self.E("V3", f"waves: wave_no must run 1, 2, ... (found {wave_nos})")
        lo, hi = OFFICIAL["S"]["waves"]
        if not lo <= len(wave_nos) <= hi:
            self.E("V2", f"{len(wave_nos)} closure waves, outside {lo}..{hi}")
        road_ids = {r[0] for r in R}
        self.many("V3", "waves: road_no is not a road at road_no", [r[1] for r in Wv if r[1] not in road_ids])
        cnt = Counter(r[1] for r in Wv)
        self.many("V4", "waves: road closed twice (waves must be disjoint) at road_no", [r for r, c in cnt.items() if c > 1])
        cap = max(1, E // 4)
        for w in wave_nos:
            sz = sum(1 for r in Wv if r[0] == w)
            if not 1 <= sz <= cap:
                self.E("V4", f"wave {w} has {sz} roads, outside 1..max(1, floor(E/4)) = 1..{cap}")
        penl = [pen.get(v, 0) for v in range(V)]
        self.f.update(V=V, E=E, adj=adj, pen=penl, types=types, hop=hop,
                      closed={r[1] for r in Wv}, nwaves=len(wave_nos),
                      net_ok=ok_ids and V > 0 and min(hop) >= 0)

    def route_trap(self, factor_num, factor_den):
        """Targets for which every fewest-roads route costs more than
        factor * the cheapest route (factor = num/den; strict if num == den)."""
        V, adj, pen, hop = self.f["V"], self.f["adj"], self.f["pen"], self.f["hop"]
        d = cheapest(V, adj, pen, 0)
        c = cheapest_fewest_roads(V, adj, pen, hop)
        out = []
        for t in self.targets:
            if 0 <= t < V:
                if factor_num == factor_den and c[t] > d[t]:
                    out.append(t)
                elif factor_num != factor_den and factor_den * c[t] >= factor_num * d[t]:
                    out.append(t)
        return out

    # ---------------------------------------------------------------- radio
    def radio(self):
        P = self.D["radio_log"]
        self.ids("V5", "radio_log.part", [r[0] for r in P], 1)
        self.many("V5", "radio_log: part longer than 10,000 symbols or empty at part",
                  [r[0] for r in P if not 1 <= len(r[1]) <= 10000])
        log = "".join(r[1] for r in P)
        bad = sorted(set(log) - ALPHA)
        if bad:
            self.E("V2", f"radio_log uses symbols outside the 38-symbol alphabet: {bad[:5]}")
        self.inrange("log", len(log), "radio log length")
        self.f["log"] = log
        pats = self.D["radio_patterns"]
        if [r[0] for r in pats] != list(range(6)):
            self.E("V3", "radio_patterns: need exactly six rows, pattern_no 0..5")
        lens = [len(r[1]) for r in pats]
        if lens != PATTERN_LENGTHS:
            self.E("V2", f"radio_patterns: lengths {lens}, expected {PATTERN_LENGTHS}")
        occ = 0
        for no, pat, cnt in pats:
            if set(pat) - ALPHA or not pat:
                self.E("V2", f"pattern {no} uses symbols outside the alphabet")
                continue
            true = len(kmp_positions(log, pat))
            occ += true > 0
            if true != cnt:
                self.E("V5", f"pattern {no} count is {cnt}, recomputed {true}")
        if occ < 2 or occ == len(pats):
            self.E("V5", f"{occ} of {len(pats)} patterns occur; need at least two that occur "
                         f"and at least one that does not")
        rr = self.D["radio_reports"]
        if len(rr) != 1:
            self.E("V3", f"radio_reports: {len(rr)} rows (expected 1)")
            return
        a, b = rr[0]
        for nm, s in (("report_a", a), ("report_b", b)):
            self.inrange("report", len(s), f"length of {nm}")
            if set(s) - ALPHA:
                self.E("V2", f"{nm} uses symbols outside the alphabet")
        ed = levenshtein(a, b)
        if not ed <= self.ebound <= len(a) + len(b):
            self.E("V5", f"edit_bound {self.ebound} must lie in [true distance {ed}, "
                         f"len(a)+len(b) = {len(a) + len(b)}]")

    # -------------------------------------------------------------- windows
    def windows(self):
        rows = self.D["windows"]
        n = len(rows)
        self.inrange("windows", n, "number of windows")
        self.ids("V3", "windows.window_id", [r[0] for r in rows], 1)
        self.many("V2", "windows: need 0 <= start < finish <= 1440 at window_id",
                  [r[0] for r in rows if not 0 <= r[1] < r[2] <= 1440])
        self.many("V2", "windows: duration not in 5..480 at window_id", [r[0] for r in rows if not 5 <= r[2] - r[1] <= 480])
        self.many("V2", "windows: value not in 1..100 at window_id", [r[0] for r in rows if not 1 <= r[3] <= 100])
        starts = Counter(r[1] for r in rows)
        touching = sum(starts.get(r[2], 0) for r in rows)
        if n >= 8 and touching < 2:
            self.E("V2", f"only {touching} touching pair(s) of windows; need at least 2")
        self.f["wins"] = [(r[1], r[2], r[3]) for r in rows]

    # ------------------------------------------------------------ incidents
    def incidents(self):
        rows = self.D["incidents"]
        n = len(rows)
        self.inrange("alarms", n, "number of alarms")
        self.ids("V3", "incidents.alarm_id", [r[0] for r in rows], 1)
        if not rows:
            return
        if rows[0][1] != 0:
            self.E("V2", f"first alarm tick is {rows[0][1]}; ticks must start at 0")
        self.many("V2", "incidents: tick decreases at alarm at alarm_id",
                  [rows[i][0] for i in range(1, n) if rows[i][1] < rows[i - 1][1]])
        self.many("V2", "incidents: priority not in 1..10 at alarm_id", [r[0] for r in rows if not 1 <= r[2] <= 10])
        last = max(r[1] for r in rows)
        pr = [r[2] for r in rows]
        if self.tier in ("M", "L", "X"):
            if not (5 * n >= 6 * (last + 1) and 5 * n <= 9 * (last + 1)):
                self.E("V2", f"alarms per tick = {n}/{last + 1} = {n / (last + 1):.3f}, outside 1.2..1.8")
            if len(set(pr)) < 6 or 1 not in pr:
                self.E("V2", f"need at least 6 distinct priorities including 1 (found {sorted(set(pr))})")
        self.f.update(alarms=n, last_tick=last, prio_sum=sum(pr))

    # ---------------------------------------------------------- sites/tour
    def sites_tour(self):
        rows = self.D["sites"]
        n = len(rows)
        self.inrange("sites", n, "number of relief sites")
        self.ids("V3", "sites.site_no", [r[0] for r in rows], 0)
        self.many("V2", "sites: x or y not in 0..999 at site_no",
                  [r[0] for r in rows if not (0 <= r[1] <= 999 and 0 <= r[2] <= 999)])
        pts = [(r[1], r[2]) for r in rows]
        if len(set(pts)) != n:
            self.E("V2", "two relief sites are equal")
        self.f["pts"] = pts
        T = self.D["tour"]
        self.ids("V3", "tour.step", [r[0] for r in T], 0)
        tour = [r[1] for r in T]
        if sorted(tour) != list(range(n)) or not tour or tour[0] != 0:
            self.E("V6", "planted tour is not a permutation of all sites starting at site 0")
            return
        L = sum(abs(pts[tour[i]][0] - pts[tour[(i + 1) % n]][0]) +
                abs(pts[tour[i]][1] - pts[tour[(i + 1) % n]][1]) for i in range(n))
        if L != self.tlen:
            self.E("V6", f"tour_length {self.tlen} but the planted tour measures {L}")
        if self.tier in ("L", "X"):
            nn = min(nn_tour_length(pts, True), nn_tour_length(pts, False))
            if L > nn:
                self.E("V6", f"planted tour ({L}) is longer than the nearest-neighbour tour ({nn})")

    # --------------------------------------------------------------- chains
    def chains(self):
        dims = self.D["pipeline_dims"]
        self.ids("V3", "pipeline_dims.idx", [r[0] for r in dims], 0)
        self.inrange("stages", len(dims) - 1, "pipeline stages n")
        self.many("V2", "pipeline_dims: dim not in 2..100 at idx", [r[0] for r in dims if not 2 <= r[1] <= 100])
        dp = self.D["drum_prices"]
        self.ids("V3", "drum_prices.length", [r[0] for r in dp], 1)
        self.inrange("drum", len(dp), "drum length L")
        self.many("V2", "drum_prices: price not in 1..500 at length", [r[0] for r in dp if not 1 <= r[1] <= 500])
        if dp and all(r[1] == r[0] * dp[0][1] for r in dp):
            self.E("V2", "drum prices are all proportional to length")
        self.f["prices"] = [r[1] for r in dp]

    # -------------------------------------------------------------- sensors
    def sensors(self):
        n, k = self.sn, self.sk
        self.inrange("sensors", n, "sensor_nodes")
        es = self.D["sensor_edges"]
        self.many("V3", "sensor_edges: node outside 0..n-1",
                  [(u, v) for u, v in es if not (0 <= u < n and 0 <= v < n)])
        self.many("V2", "sensor_edges: need u < v (no loops)", [(u, v) for u, v in es if not u < v])
        self.many("V3", "sensor_edges: repeated edge", [e for e, c in Counter(es).items() if c > 1])
        if len(es) < n - 1:
            self.E("V2", f"{len(es)} sensor edges; need at least n-1 = {n - 1}")
        cov = [r[0] for r in self.D["sensor_cover"]]
        if len(cov) != k or len(set(cov)) != k:
            self.E("V6", f"sensor_cover has {len(cov)} rows ({len(set(cov))} distinct) but sensor_k = {k}")
        if not (k >= 2 and 2 * k <= n):
            self.E("V2", f"sensor_k = {k} must satisfy 2 <= k <= n/2 (n = {n})")
        self.many("V3", "sensor_cover: node outside 0..n-1", [c for c in cov if not 0 <= c < n])
        cs = set(cov)
        self.many("V6", "planted cover misses edge", [(u, v) for u, v in es if u not in cs and v not in cs])
        self.f["sedges"] = es

    # --------------------------------------------------------------- safety
    def safety(self):
        N = self.svars
        self.inrange("safety", N, "safety_vars")
        rules = self.D["safety_rules"]
        m = len(rules)
        self.ids("V3", "safety_rules.rule_no", [r[0] for r in rules], 1)
        bad = [r[0] for r in rules if any(l == 0 or abs(l) > N for l in r[1:])]
        self.many("V3", "safety_rules: literal is 0 or names a switch outside 1..safety_vars at rule_no", bad)
        self.many("V2", "safety_rules: literals not on three different switches at rule_no",
                  [r[0] for r in rules if len({abs(l) for l in r[1:]}) != 3])
        if not 2 * N <= m <= 6 * N:
            self.E("V2", f"rules per switch = {m}/{N} = {m / max(N, 1):.3f}, outside 2.0..6.0")
        pl = self.D["safety_planted"]
        self.ids("V3", "safety_planted.switch", [r[0] for r in pl], 1)
        if len(pl) != N:
            self.E("V6", f"safety_planted has {len(pl)} switches, expected {N}")
        self.many("V2", "safety_planted: value not 0/1 at switch", [r[0] for r in pl if r[1] not in (0, 1)])
        val = {r[0]: r[1] for r in pl}
        unsat = [r[0] for r in rules
                 if not any((l > 0 and val.get(l) == 1) or (l < 0 and val.get(-l) == 0) for l in r[1:])]
        self.many("V6", "planted assignment violates rule at rule_no", unsat)
        self.f["rules"] = (m, N)

    # -------------------------------------------------------------- rations
    def rations(self):
        rows = self.D["rations"]
        self.inrange("rations", len(rows), "ration quantities")
        self.ids("V3", "rations.item", [r[0] for r in rows], 0)
        self.many("V2", "rations: value not in 1..1000 at item", [r[0] for r in rows if not 1 <= r[1] <= 1000])
        self.many("V2", "rations: planted not 0/1 at item", [r[0] for r in rows if r[2] not in (0, 1)])
        s = sum(r[1] for r in rows if r[2] == 1)
        if self.rtarget <= 0:
            self.E("V2", f"rations_target {self.rtarget} must be positive")
        if s != self.rtarget:
            self.E("V6", f"planted rations sum to {s}, but rations_target = {self.rtarget}")

    # --------------------------------------------------------------- claims
    def claims(self):
        rows = self.D["claims"]
        if self.tier != "S":
            if rows:
                self.E("V3", "claims rows are only allowed for tier S cases")
            return
        if len(rows) != 1:
            self.E("V5", f"tier S case needs exactly one claims row (found {len(rows)})")
            return
        cargo, wc, wv, drum, tour, cover = rows[0]
        true = {}
        if "ws" in self.f:
            true["cargo_opt"] = knapsack_dp(self.f["ws"], self.f["vs"], max(self.cap, 0))
        if "wins" in self.f:
            true["window_count_opt"], true["window_value_opt"] = interval_opt(self.f["wins"])
        if "prices" in self.f:
            true["drum_opt"] = rod_dp(self.f["prices"])
        if "pts" in self.f and len(self.f["pts"]) >= 2:
            true["tour_opt"] = held_karp(self.f["pts"])
        if "sedges" in self.f:
            true["cover_min"] = min_vertex_cover(self.f["sedges"], self.sn)
        given = dict(cargo_opt=cargo, window_count_opt=wc, window_value_opt=wv,
                     drum_opt=drum, tour_opt=tour, cover_min=cover)
        for key, t in true.items():
            if given[key] != t:
                self.E("V5", f"claim {key} = {given[key]}, recomputed optimum {t}")
        self.f["cargo_true"] = true.get("cargo_opt")

    # ------------------------------------------------------------ signature
    def signature(self):
        if self.k > 45:
            return
        f, s = self.f, self.scen
        V, E = f.get("V", 0), f.get("E", 0)
        ws = f.get("ws", [])
        n = len(ws)
        cats = [r[1] for r in self.D["crates"]]
        log = f.get("log", "")
        fail = lambda msg: self.E("V7", f"scenario {s}: {msg}")
        if s == 1:
            if not (20 * E >= 22 * V and 20 * E <= 32 * V):
                fail(f"average degree 2E/V = {2 * E / V:.3f} not in 2.2..3.2")
            hi = sum(1 for p in f["pen"] if p >= 2)
            if 10 * hi < 4 * V:
                fail(f"only {hi}/{V} locations have penalty >= 2 (need 40%)")
            if f["nwaves"] < 3:
                fail(f"{f['nwaves']} waves (need at least 3)")
            c01 = sum(1 for c in cats if c in (0, 1))
            if 100 * c01 < 55 * n:
                fail(f"food+water crates {c01}/{n} < 55%")
        elif s == 2:
            if not (E >= V and 10 * E <= 13 * V):
                fail(f"average degree 2E/V = {2 * E / V:.3f} not in 2.0..2.6")
            c23 = sum(1 for c in cats if c in (2, 3))
            if 100 * c23 < 45 * n:
                fail(f"medicine+tool crates {c23}/{n} < 45%")
            if f["prio_sum"] < 6 * f["alarms"]:
                fail(f"mean alarm priority {f['prio_sum'] / f['alarms']:.3f} < 6.0")
        elif s == 3:
            sh = sum(1 for t in f["types"].values() if t == "S")
            if 4 * sh < V:
                fail(f"shelters {sh}/{V} < 25%")
            if f["nwaves"] < 3:
                fail(f"{f['nwaves']} waves (need at least 3)")
            wins = f["wins"]
            st, fi = sorted(w[0] for w in wins), sorted(w[1] for w in wins)
            tot = sum(len(wins) - 1 - bisect_right(fi, a) - (len(wins) - bisect_left(st, b))
                      for a, b, _ in wins)
            if tot < 2 * len(wins):
                fail(f"windows overlap {tot / len(wins):.3f} others on average (need >= 2)")
            if len(set(log)) < 30:
                fail(f"log uses {len(set(log))} of the 38 symbols (need >= 30)")
        elif s == 4:
            if 4 * E < 7 * V:
                fail(f"average degree 2E/V = {2 * E / V:.3f} < 3.5")
            if self.tier in ("M", "L") and 2 * f["alarms"] < 3 * (f["last_tick"] + 1):
                fail(f"alarms per tick {f['alarms'] / (f['last_tick'] + 1):.3f} < 1.5")
            c4 = sum(1 for c in cats if c == 4)
            if 10 * c4 < n:
                fail(f"rare crates {c4}/{n} < 10%")
        elif s == 5:
            if 10 * E > 12 * V:
                fail(f"average degree 2E/V = {2 * E / V:.3f} > 2.4")
            deg = [len(a) for a in f["adj"]]
            if deg and max(deg) > 4:
                fail(f"a location has {max(deg)} roads (max 4)")
            if f["net_ok"] and max(f["hop"]) < V // 4:
                fail(f"farthest location is {max(f['hop'])} roads from HQ (< floor(V/4) = {V // 4})")
            if f["nwaves"] < 3:
                fail(f"{f['nwaves']} waves (need at least 3)")
            after = bfs_hops(V, f["adj"], 0, banned=f["closed"])
            if not any(0 <= t < V and after[t] < 0 for t in self.targets):
                fail("after all waves every target is still reachable from the HQ")
        elif s == 6:
            c12 = sum(1 for c in cats if c in (1, 2))
            if 100 * c12 < 55 * n:
                fail(f"water+medicine crates {c12}/{n} < 55%")
            early = sum(1 for r in self.D["crates"] if r[4] <= 300)
            if 2 * early < n:
                fail(f"only {early}/{n} crates expire by hour 300")
            top = max(Counter(log).values()) if log else 0
            if 4 * top < len(log):
                fail(f"most frequent symbol is {top}/{len(log)} of the log (< 25%)")

    # ----------------------------------------------------------------- traps
    def trap(self):
        k, f = self.k, self.f
        fail = lambda msg: self.E("V8", f"trap {k}: {msg}")
        if k == 46:
            rows = self.D["crates"]
            if not 1500 <= len(rows) <= 3000:
                fail(f"{len(rows)} crates (need 1,500..3,000)")
            fields = {
                "value": monotone([r[3] for r in rows]),
                "weight": monotone([r[2] for r in rows]),
                "expiry": monotone([r[4] for r in rows]),
                "serial": monotone([r[5] for r in rows]),
                "value-per-kg": monotone([(r[3], r[2]) for r in rows],
                                         key=lambda a, b: (a[0] * b[1] > b[0] * a[1]) - (a[0] * b[1] < b[0] * a[1])),
            }
            good = [x for x, ok in fields.items() if ok]
            if len(good) < 3:
                fail(f"monotone in only {good} (need at least 3 of 5 fields)")
        elif k == 47:
            ws, vs = f["ws"], f["vs"]
            if not 12 <= len(ws) <= 60:
                fail(f"{len(ws)} crates (need 12..60)")
            opt = knapsack_dp(ws, vs, max(self.cap, 0))
            gr = ratio_greedy(ws, vs, self.cap)
            if 10 * gr > 6 * opt:
                fail(f"ratio greedy reaches {gr} of optimum {opt} (> 60%)")
            if ratio_ties(ws, vs):
                fail("two crates have equal value per kg (greedy order ambiguous)")
        elif k == 48:
            V = f["V"]
            if not 1500 <= V <= 3000:
                fail(f"{V} locations (need 1,500..3,000)")
            if f["net_ok"]:
                d1 = f["hop"]
                far = max(range(V), key=lambda v: d1[v])
                d2 = bfs_hops(V, f["adj"], far)
                diam = max(d2)
                if diam < 500:              # double sweep is a lower bound; confirm exactly
                    diam = max(max(bfs_hops(V, f["adj"], s)) for s in range(V))
                if diam < 500:
                    fail(f"longest distance is {diam} roads (< 500)")
                if not self.route_trap(3, 2):
                    fail("no target whose fewest-roads routes all cost >= 1.5 x the cheapest route")
        elif k == 49:
            log = f["log"]
            n = len(log)
            if not 50000 <= n <= 100000:
                fail(f"log has {n} symbols (need 50,000..100,000)")
            best = 0
            for p in range(1, 9):
                block = Counter(log[i:i + p] for i in range(0, n - p + 1)).most_common(1)[0][0]
                i = cov = 0
                while i <= n - p:
                    if log.startswith(block, i):
                        cov += p
                        i += p
                    else:
                        i += 1
                best = max(best, cov)
            if 10 * best < 9 * n:
                fail(f"best single block of <= 8 symbols covers {best}/{n} (< 90%)")
            near = 0
            for _no, pat, _c in self.D["radio_patterns"]:
                m = len(pat)
                starts = n - m + 1
                hits = sum(1 for i in kmp_positions(log, pat[:-1]) if i <= n - m)
                near += 2 * hits >= starts
            if near < 4:
                fail(f"only {near} patterns have their first (length-1) symbols matching at "
                     f">= half of all start positions (need 4)")


# ============================================================ cross-case rules
def module_signatures(cid, data):
    g = lambda s: tuple(data[s].get(cid, []))
    log = "".join(r[1] for r in data["radio_log"].get(cid, []))
    rep = g("radio_reports")
    return {
        "crates": (len(g("crates")), g("crates")),
        "network": (len(g("locations")), (g("locations"), g("roads"))),
        "waves": (len(g("waves")), g("waves")),
        "radio log": (len(log), log),
        "radio reports": (sum(len(a) + len(b) for a, b in rep), rep),
        "windows": (len(g("windows")), g("windows")),
        "incidents": (len(g("incidents")), g("incidents")),
        "sites/tour": (len(g("sites")), (g("sites"), g("tour"))),
        "pipeline": (len(g("pipeline_dims")), g("pipeline_dims")),
        "drum": (len(g("drum_prices")), g("drum_prices")),
        "sensors": (len(g("sensor_edges")), (g("sensor_edges"), g("sensor_cover"))),
        "safety": (len(g("safety_rules")), g("safety_rules")),
        "rations": (len(g("rations")), g("rations")),
    }


def variety(case_ids, data, rep, checks):
    S = [c for c in case_ids if checks[c].__dict__.get("tier") == "S"]
    greedy_bad, route_bad = [], []
    for c in S:
        ch = checks[c]
        ws, vs = ch.f.get("ws"), ch.f.get("vs")
        if ws and not ratio_ties(ws, vs) and ratio_greedy(ws, vs, ch.cap) < knapsack_dp(ws, vs, ch.cap):
            greedy_bad.append(c)
        if ch.f.get("net_ok") and ch.route_trap(1, 1):
            route_bad.append(c)
    msg = lambda name, lst: f"{name}: {len(lst)} tier-S cases {lst}"
    if len(greedy_bad) < 5:
        rep.add(None, "V7", "variety 1 failed -- " + msg("ratio greedy not optimal", greedy_bad))
    if len(route_bad) < 5:
        rep.add(None, "V7", "variety 2 failed -- " + msg("fewest-roads routes all dearer", route_bad))
    ML = [c for c in case_ids if checks[c].__dict__.get("tier") in ("M", "L")]
    low = mid = high = 0
    for c in ML:
        m, N = checks[c].f.get("rules", (0, 1))
        if not (2 * m >= 5 * N and m <= 6 * N):
            rep.add(None, "V7", f"variety 3: {c} rules per switch {m / N:.3f} outside 2.5..6.0")
        if 2 * m < 7 * N:
            low += 1
        elif 5 * m <= 24 * N:
            mid += 1
        else:
            high += 1
    if len(ML) != 26 or low < 5 or mid < 8 or high < 5:
        rep.add(None, "V7", f"variety 3 failed: {len(ML)} M/L cases, below 3.5: {low}, "
                            f"3.5..4.8: {mid}, above 4.8: {high}")
    seen = {}
    for c in case_ids:
        for mod, (size, sig) in module_signatures(c, data).items():
            if size >= 8:
                if (mod, sig) in seen:
                    rep.add(None, "V7", f"variety 4: cases {seen[(mod, sig)]} and {c} are equal in module {mod}")
                else:
                    seen[(mod, sig)] = c
    return dict(greedy=greedy_bad, route=route_bad, low=low, mid=mid, high=high)


# ========================================================================= main
def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a LIFELINE workbook")
    ap.add_argument("workbook")
    ap.add_argument("--seed", type=int, default=None, help="expected group seed")
    ap.add_argument("--partial", action="store_true",
                    help="validate the cases present without requiring all 50 (test copies)")
    args = ap.parse_args(argv)

    rep = Report()
    names, sheets = load(args.workbook, rep)
    print(f"LIFELINE validator -- {args.workbook} -- mode: {'partial' if args.partial else 'full'}")
    if names is None:
        for rule, msg in rep.glob:
            print(f"  [{rule}] {msg}")
        print("RESULT: FAIL")
        return 1
    data = parse(names, sheets, rep)
    case_ids = [r[0] for r in sheets.get("cases", [])[1:] if r and isinstance(r[0], str)]
    if len(set(case_ids)) != len(case_ids):
        rep.add(None, "V1", "repeated case_id in sheet 'cases'")
    case_ids = list(dict.fromkeys(case_ids))
    for name, _ in SPEC:
        for cid in data[name]:
            if cid not in case_ids:
                rep.add(None, "V3", f"sheet '{name}' has rows for unknown case_id {cid}")
    if not args.partial:
        if len(case_ids) != 50:
            rep.add(None, "V1", f"{len(case_ids)} cases; exactly 50 are required")
        nos = sorted(r[2] for r in sheets.get("cases", [])[1:] if r and isinstance(r[2], int))
        if nos != list(range(50)):
            rep.add(None, "V1", "case_no values are not exactly 0..49")
        serials = Counter(r[5] for rows in data["crates"].values() for r in rows)
        dup = [s for s, c in serials.items() if c > 1]
        if dup:
            rep.add(None, "V3", f"crate serials repeated across cases: {dup[:3]}")
    checks = {}
    for cid in case_ids:
        ch = CaseCheck(cid, data, rep, args.seed)
        ch.run()
        checks[cid] = ch
    stats = None
    if not args.partial:
        try:
            stats = variety(case_ids, data, rep, checks)
        except Exception as ex:          # noqa: BLE001
            rep.add(None, "V7", f"variety rules could not be checked: {ex!r}")

    n_pass = 0
    for cid in case_ids:
        errs = rep.case.get(cid, [])
        if not errs:
            n_pass += 1
            print(f"{cid} PASS")
        else:
            print(f"{cid} FAIL")
            for rule, msg in errs:
                print(f"    [{rule}] {msg}")
    for cid in rep.case:
        if cid not in case_ids:
            print(f"{cid} FAIL (case_id not in sheet 'cases')")
            for rule, msg in rep.case[cid]:
                print(f"    [{rule}] {msg}")
    if stats:
        print(f"variety 1: ratio greedy not optimal in {len(stats['greedy'])} tier-S cases (need >= 5)")
        print(f"variety 2: fewest-roads routes all dearer for a target in {len(stats['route'])} tier-S cases (need >= 5)")
        print(f"variety 3: rules per switch below 3.5: {stats['low']}, 3.5..4.8: {stats['mid']}, "
              f"above 4.8: {stats['high']} (need >= 5, >= 8, >= 5)")
    if rep.glob:
        print("workbook-level problems:")
        for rule, msg in rep.glob:
            print(f"    [{rule}] {msg}")
    else:
        print("workbook-level checks (sheets, headers, types, ordering, cross-case rules): PASS")
    ok = not rep.glob and n_pass == len(case_ids) and not any(c not in case_ids for c in rep.case)
    print(f"RESULT: {'PASS' if ok else 'FAIL'} ({n_pass}/{len(case_ids)} cases pass)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
