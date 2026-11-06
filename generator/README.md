# Generator

One command reproduces `cases.xlsx` from the group seed (run it from the repository root):

```
python generator/generate.py --seed 76 --out cases.xlsx
```

Requirements: Python 3.10+, `openpyxl`, `numpy` (`pip install -r requirements.txt`).

Every random draw comes from `random.Random("LIFELINE|<seed>|<case_no>|<module>|<attempt>")`, so the output is a pure
function of the seed and the case number. When a draw breaks one of the case's rules (a signature rule, a variety rule
or a trap), it is redrawn with `attempt + 1`, which keeps the result deterministic. The script prints a SHA-256 digest of
all cell values; for seed 76 it is `53aa6cf543f0d7eed1464c78645bbbe188aad85cb667a8735c6feb2d8828af18`.

| File | Produces |
|---|---|
| `common.py` | sheet layout, tiers, size ranges, seeded random streams |
| `crates.py` | crates and capacity; trap 46 (dock order), trap 47 (best-looking crate); exhaustive knapsack claim |
| `network.py` | locations, roads, waves, targets; landslide corridor; trap 48 (shortest looks cheapest) |
| `radio.py` | radio log, patterns and counts, reports and edit_bound; trap 49 (near miss) |
| `schedule.py` | rescue windows (with touching chains and surge bursts) and incident alarms |
| `geometry.py` | relief sites, planted tour (nearest neighbour + 2-opt), exhaustive tour claim |
| `chains.py` | pipeline dimensions, drum prices, exhaustive drum claim |
| `hard.py` | sensor graph with planted cover, planted 3-SAT rules, planted rations, exhaustive cover claim |
| `generate.py` | builds the 50 cases, computes the tier-S claims and writes the workbook |
