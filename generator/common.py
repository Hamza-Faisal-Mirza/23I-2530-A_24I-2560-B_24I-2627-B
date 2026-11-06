"""Shared definitions for the LIFELINE case generator (group 76).

All randomness is drawn from random.Random objects whose seed string is built
only from the group seed s, the case number k and a fixed module label, so the
workbook is a pure function of s.
"""
import random

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"   # the 38 radio symbols
LETTERS_DIGITS = ALPHABET[:36]

SHEETS = [
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

# Ranges we actually draw sizes from. They are sub-ranges of the official
# ranges of Section 3 (tier L sizes are kept in the lower part of the range so
# that the workbook stays a manageable size; tier X = tier L except traps).
GEN_RANGES = {
    "S": dict(crates=(8, 20), V=(6, 12), log=(200, 500), report=(10, 30),
              windows=(8, 20), alarms=(10, 40), sites=(5, 9), stages=(4, 8),
              drum=(5, 14), sensors=(6, 14), safety=(6, 15), rations=(8, 20)),
    "M": dict(crates=(40, 200), V=(30, 150), log=(2000, 10000), report=(30, 150),
              windows=(50, 300), alarms=(200, 1000), sites=(10, 16), stages=(15, 60),
              drum=(40, 200), sensors=(20, 40), safety=(20, 50), rations=(24, 40)),
    "L": dict(crates=(500, 900), V=(500, 900), log=(20000, 40000), report=(200, 500),
              windows=(1000, 1600), alarms=(2000, 3200), sites=(200, 320),
              stages=(100, 180), drum=(500, 900), sensors=(100, 200), safety=(20, 50),
              rations=(50, 100)),
}
TRAP_OVERRIDES = {
    46: dict(crates=(1500, 2000)),
    47: dict(crates=(14, 20)),
    48: dict(V=(1500, 1800)),
    49: dict(log=(50000, 60000)),
}


def tier_of(k):
    if k <= 19:
        return "S"
    if k <= 39:
        return "M"
    if k <= 45:
        return "L"
    return "X"


def ceil_div(a, b):
    return -(-a // b)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


class Case:
    def __init__(self, seed, k):
        self.seed = seed
        self.k = k
        self.tier = tier_of(k)
        self.scenario = k % 6 + 1
        self.case_id = f"{seed}-{k:02d}"
        self.is_trap = k >= 46

    def rng(self, module, attempt=0):
        return random.Random(f"LIFELINE|{self.seed}|{self.k}|{module}|{attempt}")

    def gen_range(self, item):
        if self.k in TRAP_OVERRIDES and item in TRAP_OVERRIDES[self.k]:
            return TRAP_OVERRIDES[self.k][item]
        base = "L" if self.tier == "X" else self.tier
        return GEN_RANGES[base][item]

    def size(self, item, rng):
        lo, hi = self.gen_range(item)
        return rng.randint(lo, hi)
