"""Summarise cases.xlsx per case (used for the approach note and the viva).

    python tools/dataset_stats.py cases.xlsx > docs/dataset_summary.md
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validator"))
import openpyxl  # noqa: E402
from validate import (SPEC, bfs_hops, cheapest, cheapest_fewest_roads, knapsack_dp,  # noqa: E402
                      nn_tour_length, ratio_greedy)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "cases.xlsx"
    wb = openpyxl.load_workbook(path, read_only=True)
    data = {}
    for name, _ in SPEC:
        d = {}
        for r in list(wb[name].iter_rows(values_only=True))[1:]:
            d.setdefault(r[0], []).append(r[1:])
        data[name] = d
    wb.close()
    print("| case | tier | scen | crates | cap % W | key crate share | V | E | 2E/V | pen>=2 | shelters | waves "
          "| ecc(HQ) | maxdeg | log | symbols | top sym | windows | avg overlap | alarms/tick | mean prio "
          "| sites | tour/NN | rules/switch | greedy/opt | dear fewest-roads target |")
    print("|" + "---|" * 26)
    for cid, crow in data["cases"].items():
        seed, k, tier, scen, cap, t0, t1, t2, eb, tl, sn, sk, sv, rt = crow[0]
        cr = data["crates"][cid]
        n = len(cr)
        W = sum(r[2] for r in cr)
        cats = Counter(r[1] for r in cr)
        key = {1: ("food+water", cats[0] + cats[1]), 2: ("med+tool", cats[2] + cats[3]),
               3: ("-", 0), 4: ("rare", cats[4]), 5: ("-", 0), 6: ("water+med", cats[1] + cats[2])}[scen]
        keys = f"{key[0]} {100 * key[1] / n:.0f}%" if key[0] != "-" else "-"
        if scen == 6:
            keys += f", exp<=300 {100 * sum(1 for r in cr if r[4] <= 300) / n:.0f}%"
        L = data["locations"][cid]
        V = len(L)
        R = data["roads"][cid]
        E = len(R)
        pen = [r[2] for r in L]
        adj = [[] for _ in range(V)]
        for rid, u, v, mi, cb in R:
            adj[u].append((v, mi, rid))
            adj[v].append((u, mi, rid))
        hop = bfs_hops(V, adj, 0)
        d = cheapest(V, adj, pen, 0)
        c = cheapest_fewest_roads(V, adj, pen, hop)
        dear = [t for t in (t0, t1, t2) if c[t] > d[t]]
        dear_s = ", ".join(f"{t}: {c[t]}/{d[t]}" for t in dear) or "-"
        waves = len({r[0] for r in data["waves"][cid]})
        log = "".join(r[1] for r in data["radio_log"][cid])
        top = max(Counter(log).values())
        wins = data["windows"][cid]
        nw = len(wins)
        ov = sum(1 for a in wins for b in wins if a is not b and a[1] < b[2] and b[1] < a[2]) / nw if nw <= 400 else None
        inc = data["incidents"][cid]
        rate = len(inc) / (inc[-1][1] + 1)
        mp = sum(r[2] for r in inc) / len(inc)
        pts = [(r[1], r[2]) for r in data["sites"][cid]]
        nn = min(nn_tour_length(pts, True), nn_tour_length(pts, False))
        m = len(data["safety_rules"][cid])
        gr = opt = None
        if tier == "S" or k == 47:
            ws, vs = [r[2] for r in cr], [r[3] for r in cr]
            gr, opt = ratio_greedy(ws, vs, cap), knapsack_dp(ws, vs, cap)
        shel = sum(1 for r in L if r[1] == "S")
        print(f"| {cid} | {tier} | {scen} | {n} | {100 * cap / W:.0f} | {keys} | {V} | {E} | {2 * E / V:.2f} "
              f"| {100 * sum(1 for p in pen if p >= 2) / V:.0f}% | {100 * shel / V:.0f}% | {waves} | {max(hop)} "
              f"| {max(len(a) for a in adj)} | {len(log)} | {len(set(log))} | {100 * top / len(log):.0f}% | {nw} "
              f"| {'%.2f' % ov if ov is not None else 'n/a'} | {rate:.2f} | {mp:.2f} | {len(pts)} | {tl}/{nn} "
              f"| {m / sv:.2f} | {f'{gr}/{opt}' if gr is not None else '-'} | {dear_s} |")


if __name__ == "__main__":
    main()
