"""LIFELINE case generator -- group 76.

Usage (from the repository root):
    python generator/generate.py --seed 76 --out cases.xlsx

Every number in the workbook is a deterministic function of the group seed and
the case number. The script prints a SHA-256 digest of the cell contents so two
runs can be compared (the .xlsx bytes themselves contain a save timestamp).
"""
import argparse
import hashlib
import random
import sys
import time

from openpyxl import Workbook

import chains
import crates
import geometry
import hard
import network
import radio
import schedule
from common import SHEETS, Case


def windows_opt_exhaustive(wins):
    """Most windows and best value over every pairwise-compatible subset
    (touching windows are compatible)."""
    n = len(wins)
    order = sorted(range(n), key=lambda i: (wins[i][0], i))
    best = [0, 0]

    def dfs(pos, last_finish, cnt, val):
        if cnt > best[0]:
            best[0] = cnt
        if val > best[1]:
            best[1] = val
        for p in range(pos, n):
            s, f, v = wins[order[p]]
            if s >= last_finish:
                dfs(p + 1, f, cnt + 1, val + v)

    dfs(0, -1, 0, 0)
    return best[0], best[1]


def safety_buckets(seed):
    """Rules-per-switch bucket for the 26 tier M/L cases (variety rule 3)."""
    r = random.Random(f"LIFELINE|{seed}|safety-buckets")
    b = ["low"] * 7 + ["mid"] * 12 + ["high"] * 7
    r.shuffle(b)
    return {20 + i: b[i] for i in range(26)}


def build_case(seed, k, buckets):
    c = Case(seed, k)
    S = c.tier == "S"
    cid = c.case_id
    cr_rows, cap, cr_info = crates.generate(c, want_greedy_fail=S and k % 3 != 2)
    net = network.generate(c, want_minhop_trap=S and c.scenario in (1, 3, 4, 6))
    rad = radio.generate(c)
    wins = schedule.gen_windows(c, want_overlap=(c.scenario == 3 and not c.is_trap))
    alarms = schedule.gen_incidents(c)
    pts = geometry.gen_sites(c, c.rng("sites"))
    tour, tlen, nnlen = geometry.planted_tour(pts)
    assert tlen <= nnlen
    dims = chains.gen_pipeline(c, c.rng("pipeline"))
    prices = chains.gen_drum(c, c.rng("drum"))
    sn, sedges, scover = hard.gen_sensors(c, c.rng("sensors"))
    N, clauses, assign = hard.gen_safety(c, c.rng("safety"), buckets.get(k))
    rvals, rflags, rtarget = hard.gen_rations(c, c.rng("rations"))

    rows = {name: [] for name, _ in SHEETS}
    t0, t1, t2 = net["targets"]
    rows["cases"].append([cid, seed, k, c.tier, c.scenario, cap, t0, t1, t2,
                          rad["edit_bound"], tlen, sn, len(scover), N, rtarget])
    for i, (cat, w, v, e, s) in enumerate(cr_rows):
        rows["crates"].append([cid, i + 1, cat, w, v, e, s])
    for v in range(net["V"]):
        rows["locations"].append([cid, v, net["types"][v], net["pen"][v]])
    for r, (u, v, mi, cb) in enumerate(net["roads"]):
        rows["roads"].append([cid, r, u, v, mi, cb])
    for wi, wave in enumerate(net["waves"]):
        for r in wave:
            rows["waves"].append([cid, wi + 1, r])
    for p, text in enumerate(rad["parts"]):
        rows["radio_log"].append([cid, p + 1, text])
    for i, (pat, cnt) in enumerate(rad["patterns"]):
        rows["radio_patterns"].append([cid, i, pat, cnt])
    rows["radio_reports"].append([cid, rad["report"][0], rad["report"][1]])
    for i, (s, f, v) in enumerate(wins):
        rows["windows"].append([cid, i + 1, s, f, v])
    for i, (t, p) in enumerate(alarms):
        rows["incidents"].append([cid, i + 1, t, p])
    for i, (x, y) in enumerate(pts):
        rows["sites"].append([cid, i, x, y])
    for step, s in enumerate(tour):
        rows["tour"].append([cid, step, s])
    for i, d in enumerate(dims):
        rows["pipeline_dims"].append([cid, i, d])
    for j, p in enumerate(prices):
        rows["drum_prices"].append([cid, j + 1, p])
    for u, v in sedges:
        rows["sensor_edges"].append([cid, u, v])
    for node in scover:
        rows["sensor_cover"].append([cid, node])
    for i, lits in enumerate(clauses):
        rows["safety_rules"].append([cid, i + 1] + lits)
    for j, val in enumerate(assign):
        rows["safety_planted"].append([cid, j + 1, val])
    for i, (val, fl) in enumerate(zip(rvals, rflags)):
        rows["rations"].append([cid, i, val, fl])
    if S:
        wc, wv = windows_opt_exhaustive(wins)
        rows["claims"].append([cid, cr_info["opt"], wc, wv,
                               chains.drum_opt_exhaustive(prices),
                               geometry.tour_opt_exhaustive(pts),
                               hard.min_cover_exhaustive(sn, sedges)])
    summary = dict(case=cid, tier=c.tier, scen=c.scenario, V=net["V"], E=len(net["roads"]),
                   ecc=net["info"]["ecc"], minhop_trap=net["info"]["minhop_trap"],
                   crates=len(cr_rows), greedy=cr_info.get("greedy"), opt=cr_info.get("opt"),
                   log=len(rad["log"]), rules_per_switch=round(len(clauses) / N, 3),
                   tour=tlen, nn=nnlen)
    return rows, summary


def main():
    ap = argparse.ArgumentParser(description="Generate the LIFELINE workbook")
    ap.add_argument("--seed", type=int, default=76, help="group seed (group number)")
    ap.add_argument("--out", default="cases.xlsx")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    buckets = safety_buckets(args.seed)
    all_rows = {name: [] for name, _ in SHEETS}
    t_start = time.time()
    for k in range(50):
        t = time.time()
        rows, summ = build_case(args.seed, k, buckets)
        for name in all_rows:
            all_rows[name].extend(rows[name])
        if not args.quiet:
            print(f"case {summ['case']} tier {summ['tier']} scen {summ['scen']}  "
                  f"V={summ['V']} E={summ['E']} crates={summ['crates']} log={summ['log']} "
                  f"greedy/opt={summ['greedy']}/{summ['opt']} r/s={summ['rules_per_switch']} "
                  f"({time.time() - t:.1f}s)", flush=True)

    digest = hashlib.sha256()
    wb = Workbook(write_only=True)
    for name, header in SHEETS:
        ws = wb.create_sheet(name)
        ws.append(header)
        # rows are produced case by case in case_no order and, inside a case,
        # in increasing order of the second column; sort defensively anyway.
        data = sorted(all_rows[name], key=lambda r: (r[0], r[1:]))
        for r in data:
            ws.append(r)
            digest.update(repr(r).encode())
    wb.save(args.out)
    print(f"wrote {args.out} in {time.time() - t_start:.1f}s; content sha256 = {digest.hexdigest()}")


if __name__ == "__main__":
    sys.exit(main())
