"""Build the validator test copies from cases.xlsx.

    python validator/tests/make_tests.py cases.xlsx

Writes into validator/tests/:
  valid_<case>.xlsx            single-case copies that must PASS (--partial)
  broken_<case>_<defect>.xlsx  the same case with exactly one deliberate defect
  full_<defect>.xlsx           whole-workbook copies breaking a cross-case rule
and manifest.txt listing every copy with the rule it must trigger.
"""
import copy
import os
import sys

import openpyxl
from openpyxl import Workbook

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from validate import SPEC, levenshtein  # noqa: E402

BASE_A, BASE_B, TRAP47, TRAP48 = "76-06", "76-29", "76-47", "76-48"


def read(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    out = {}
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        out[ws.title] = {"header": rows[0], "rows": rows[1:]}
    wb.close()
    return out


def extract(book, cids):
    return {name: {"header": list(book[name]["header"]),
                   "rows": [list(r) for r in book[name]["rows"] if r[0] in cids]}
            for name, _ in SPEC}


def write(book, path, extra_sheet=False):
    wb = Workbook(write_only=True)
    for name, _ in SPEC:
        ws = wb.create_sheet(name)
        ws.append(book[name]["header"])
        for r in book[name]["rows"]:
            ws.append(r)
    if extra_sheet:
        ws = wb.create_sheet("notes")
        ws.append(["case_id", "note"])
    wb.save(path)


def rows(b, sheet):
    return b[sheet]["rows"]


def case_row(b):
    return rows(b, "cases")[0]


H = {name: hdr for name, hdr in SPEC}


def col(sheet, name):
    return H[sheet].index(name)


# ------------------------------------------------------------ base A defects
def a_header(b):
    b["crates"]["header"][col("crates", "weight")] = "weight_kg"


def a_weight(b):
    rows(b, "crates")[2][col("crates", "weight")] = 25


def a_road_ref(b):
    V = len(rows(b, "locations"))
    rows(b, "roads")[0][col("roads", "v")] = V          # loc_id V does not exist


def a_disconnect(b):
    """Re-route every road of one location elsewhere: same E, but that
    location is cut off from the HQ."""
    R = rows(b, "roads")
    V = len(rows(b, "locations"))
    targets = set(case_row(b)[6:9])
    deg = {v: 0 for v in range(V)}
    for r in R:
        deg[r[2]] += 1
        deg[r[3]] += 1
    x = min((v for v in range(1, V) if v not in targets), key=lambda v: (deg[v], v))
    pairs = {(r[2], r[3]) for r in R}
    for r in R:
        if x in (r[2], r[3]):
            other = r[3] if r[2] == x else r[2]
            for z in range(V):
                p = (min(other, z), max(other, z))
                if z not in (x, other) and p not in pairs:
                    pairs.discard((r[2], r[3]))
                    r[2], r[3] = p
                    pairs.add(p)
                    break


def a_wave_overlap(b):
    W = rows(b, "waves")
    first = next(r for r in W if r[1] == 1)
    other = next(r for r in W if r[1] == 2)
    other[2] = first[2]


def a_pattern_count(b):
    rows(b, "radio_patterns")[1][3] += 1


def a_claim(b):
    rows(b, "claims")[0][col("claims", "cargo_opt")] += 1


def a_edit_bound(b):
    a, bb = rows(b, "radio_reports")[0][1:3]
    case_row(b)[col("cases", "edit_bound")] = levenshtein(a, bb) - 1


def a_tour(b):
    T = rows(b, "tour")
    T[2][2] = T[1][2]                                    # a site visited twice


def a_penalties(b):
    for r in rows(b, "locations"):
        if r[3] >= 2:
            r[3] = 1


def a_cover(b):
    cov = [r[1] for r in rows(b, "sensor_cover")]
    n = case_row(b)[col("cases", "sensor_nodes")]
    E = [(r[1], r[2]) for r in rows(b, "sensor_edges")]
    cs = set(cov)
    for u, v in E:
        c, x = (u, v) if u in cs and v not in cs else (v, u) if v in cs and u not in cs else (None, None)
        if c is not None:
            break
    rep = next(z for z in range(n) if z not in cs and z != x)
    new = sorted((cs - {c}) | {rep})
    cid = rows(b, "sensor_cover")[0][0]
    b["sensor_cover"]["rows"] = [[cid, z] for z in new]


# ------------------------------------------------------------ base B defects
def b_scenario(b):
    case_row(b)[col("cases", "scenario")] = 1


def b_window(b):
    w = next(r for r in rows(b, "windows") if r[2] <= 900)
    w[3] = w[2] + 481


def b_tick(b):
    I = rows(b, "incidents")
    i = next(i for i in range(1, len(I)) if I[i - 1][2] > 0)
    I[i][2] = I[i - 1][2] - 1


def b_rations(b):
    r = next(r for r in rows(b, "rations") if r[3] == 0)
    r[3] = 1


def b_planted(b):
    val = {r[1]: r[2] for r in rows(b, "safety_planted")}
    for r in rows(b, "safety_rules"):
        true = [l for l in r[2:5] if (l > 0 and val[l] == 1) or (l < 0 and val[-l] == 0)]
        if len(true) == 1:
            sw = abs(true[0])
            break
    for r in rows(b, "safety_planted"):
        if r[1] == sw:
            r[2] = 1 - r[2]


def b_expiry(b):
    for r in rows(b, "crates"):
        r[col("crates", "expiry")] = max(r[col("crates", "expiry")], 301)


def b_symbol(b):
    p = rows(b, "radio_log")[0]
    p[2] = p[2][:10] + "a" + p[2][11:]


def b_capacity(b):
    W = sum(r[col("crates", "weight")] for r in rows(b, "crates"))
    case_row(b)[col("cases", "capacity")] = (8 * W) // 10


def b_serial(b):
    C = rows(b, "crates")
    C[1][col("crates", "serial")] = C[0][col("crates", "serial")]


def b_one_wave(b):
    b["waves"]["rows"] = [r for r in rows(b, "waves") if r[1] == 1]


# ---------------------------------------------------------------- trap defects
def c_capacity(b):
    case_row(b)[col("cases", "capacity")] = 60       # greedy now gets ~70%


def c_few_crates(b):
    b["crates"]["rows"] = rows(b, "crates")[:11]


def d_flat_minutes(b):
    for r in rows(b, "roads"):
        r[col("roads", "minutes")] = 30


TESTS = [
    (BASE_A, "header", "V1", "crates header 'weight' renamed to 'weight_kg'", a_header, False),
    (BASE_A, "extra_sheet", "V1", "a 21st sheet 'notes' is added", None, True),
    (BASE_A, "weight", "V2", "crate 3 weighs 25 kg (range 1..20)", a_weight, False),
    (BASE_A, "road_ref", "V3", "road 0 ends at a location that does not exist", a_road_ref, False),
    (BASE_A, "disconnected", "V4", "all roads of one location re-routed, so it is cut off", a_disconnect, False),
    (BASE_A, "waves_overlap", "V4", "wave 2 closes a road that wave 1 already closed", a_wave_overlap, False),
    (BASE_A, "pattern_count", "V5", "count of pattern 1 increased by one", a_pattern_count, False),
    (BASE_A, "claim", "V5", "cargo_opt claim increased by one", a_claim, False),
    (BASE_A, "edit_bound", "V5", "edit_bound set below the true edit distance", a_edit_bound, False),
    (BASE_A, "tour", "V6", "planted tour visits one site twice", a_tour, False),
    (BASE_A, "cover", "V6", "one cover node swapped so an edge is uncovered", a_cover, False),
    (BASE_A, "penalties", "V7", "flood penalties lowered: < 40% of locations have penalty >= 2", a_penalties, False),
    (BASE_B, "scenario", "V1", "scenario changed to 1 (case 29 is scenario 6)", b_scenario, False),
    (BASE_B, "window", "V2", "a window lasts 481 minutes", b_window, False),
    (BASE_B, "tick", "V2", "an alarm tick decreases", b_tick, False),
    (BASE_B, "capacity", "V2", "capacity set to 80% of total crate weight", b_capacity, False),
    (BASE_B, "symbol", "V2", "lower-case 'a' inserted into the radio log", b_symbol, False),
    (BASE_B, "one_wave", "V2", "only one closure wave left", b_one_wave, False),
    (BASE_B, "serial", "V3", "crate 2 repeats the serial of crate 1", b_serial, False),
    (BASE_B, "rations", "V6", "an extra ration marked planted: sum != target", b_rations, False),
    (BASE_B, "safety", "V6", "a planted switch flipped so a rule fails", b_planted, False),
    (BASE_B, "expiry", "V7", "no crate expires by hour 300 (outbreak rule)", b_expiry, False),
    (TRAP47, "capacity60", "V8", "capacity 60: ratio greedy now exceeds 60% of optimum", c_capacity, False),
    (TRAP47, "11_crates", "V8", "only 11 crates (trap needs 12..60)", c_few_crates, False),
    (TRAP48, "flat_minutes", "V8", "all roads 30 minutes: fewest-roads route is no longer dear", d_flat_minutes, False),
]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "cases.xlsx"
    book = read(src)
    for f in os.listdir(HERE):
        if f.endswith(".xlsx"):
            os.remove(os.path.join(HERE, f))
    manifest = []
    for cid in (BASE_A, BASE_B, TRAP47, TRAP48):
        name = f"valid_{cid}.xlsx"
        write(extract(book, {cid}), os.path.join(HERE, name))
        manifest.append((name, "partial", "PASS", f"unchanged copy of case {cid}"))
    for cid, tag, rule, desc, fn, extra in TESTS:
        b = copy.deepcopy(extract(book, {cid}))
        if fn:
            fn(b)
        name = f"broken_{cid}_{tag}.xlsx"
        write(b, os.path.join(HERE, name), extra_sheet=extra)
        manifest.append((name, "partial", rule, desc))

    all_ids = [r[0] for r in book["cases"]["rows"]]
    full = {name: {"header": list(book[name]["header"]), "rows": [list(r) for r in book[name]["rows"]]}
            for name, _ in SPEC}
    b = copy.deepcopy(full)
    for name, _ in SPEC:
        b[name]["rows"] = [r for r in b[name]["rows"] if r[0] != all_ids[-1]]
    write(b, os.path.join(HERE, "full_49_cases.xlsx"))
    manifest.append(("full_49_cases.xlsx", "full", "V1", f"case {all_ids[-1]} removed: only 49 cases"))
    b = copy.deepcopy(full)
    src_w = [r[1:] for r in b["windows"]["rows"] if r[0] == "76-21"]
    b["windows"]["rows"] = [r for r in b["windows"]["rows"] if r[0] != "76-27"]
    b["windows"]["rows"] += [["76-27"] + list(r) for r in src_w]
    b["windows"]["rows"].sort(key=lambda r: (r[0], r[1]))
    write(b, os.path.join(HERE, "full_duplicate_module.xlsx"))
    manifest.append(("full_duplicate_module.xlsx", "full", "V7",
                     "case 76-27 gets exactly the windows of case 76-21 (variety rule 4)"))

    with open(os.path.join(HERE, "manifest.txt"), "w") as fh:
        for name, mode, rule, desc in manifest:
            fh.write(f"{name}\t{mode}\t{rule}\t{desc}\n")
    print(f"wrote {len(manifest)} test workbooks to {HERE}")


if __name__ == "__main__":
    main()
