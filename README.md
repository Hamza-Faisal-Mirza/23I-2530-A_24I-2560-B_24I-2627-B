# LIFELINE - Algorithmic Relief-Command Engine (Group 76)

Design and Analysis of Algorithms project, Iteration 1: data generation and algorithm selection.

| Member | Roll number | Section |
|---|---|---|
| Hamza Faisal | 23I-2530-A | A |
| Ahmed Hassan | 24I-2560-B | B |
| Zeyan Ahmed | 24I-2627-B | B |

Group number / seed: **76**

## Reproduce everything

```
pip install -r requirements.txt
python generator/generate.py --seed 76 --out cases.xlsx      # writes the 50-case workbook (~25 s)
python validator/validate.py cases.xlsx --seed 76             # PASS / broken rules for every case (~15 s)
python validator/tests/make_tests.py cases.xlsx               # rebuilds the valid and broken test copies
python validator/make_report.py cases.xlsx                    # writes validation_report.txt
python tools/dataset_stats.py cases.xlsx > docs/dataset_summary.md
python tools/build_docs.py                                    # approach_note.pdf and proposal.pdf
python tools/make_zip.py                                      # submission ZIP
```

The generator prints a SHA-256 digest of every cell it writes. For seed 76 it is
`53aa6cf543f0d7eed1464c78645bbbe188aad85cb667a8735c6feb2d8828af18`. The `.xlsx` bytes differ between runs only
because the file stores a save timestamp; the cell contents are identical.

## Layout

| Path | Content |
|---|---|
| `cases.xlsx` | The workbook: exactly 50 cases, 20 sheets, written by the generator (never edited by hand) |
| `generator/` | `generate.py` (entry point) plus one module per data family: `crates.py`, `network.py`, `radio.py`, `schedule.py`, `geometry.py`, `chains.py`, `hard.py`, `common.py` |
| `validator/validate.py` | Independent validator for checks V1-V8 (shares no code with the generator) |
| `validator/tests/` | `make_tests.py`, 4 valid single-case copies, 27 broken copies, `manifest.txt` (expected rule per copy) |
| `validator/make_report.py` | Runs the validator on `cases.xlsx` and every test copy, then writes `validation_report.txt` |
| `validation_report.txt` | PASS for all 50 cases, and the rejection of every broken copy |
| `approach.md`, `approach_note.pdf` | The two-page approach note (Section 5), as Markdown source and PDF |
| `proposal.md`, `proposal.pdf` | The two-page algorithm-selection report and work division (Section 6) |
| `docs/dataset_summary.md` | Measured properties of every case (degrees, shares, rates, trap measurements) |
| `tools/` | Statistics, PDF builder and ZIP builder |
| `members.txt`, `repository.txt` | Group members and the GitHub link |

## Conventions we chose where the statement leaves a choice

- `wave_no` runs 1, 2, ...; `tour.step` runs 0, 1, ... (step 0 is site 0); `rule_no` runs 1, 2, ...
- Routes are measured from the HQ (location 0) on the network before closures (variety rule 2, trap 48).
- "Every window overlaps at least 2 other windows on average" means: the mean, over all windows, of the number of
  *other* windows sharing a positive-length interval with it is at least 2. Touching windows do not overlap.
- Trap 49 "repetition of one block": the block covers at least 90% of the symbols as non-overlapping consecutive copies.
- The tier M/L rule on alarms per tick is also applied to tier X (it uses the tier L ranges).
- Crate serials are distinct across the whole workbook, not only within each case.

## Library use (as the statement requires)

| Library | Where | Used for |
|---|---|---|
| `openpyxl` | generator, validator, tests | writing and reading the `.xlsx` workbook (data handling only) |
| `numpy` | `generator/geometry.py` | vectorised distance arithmetic inside our own 2-opt, which builds the planted tour |
| `random`, `bisect`, `heapq`, `itertools`, `fractions` | generator and validator | seeded random numbers, binary search, the priority queue used by verification Dijkstra, enumeration, exact ratios |
| `reportlab` | `tools/build_docs.py` | rendering the PDFs |

No library performs a decision-module algorithm on our behalf. Every optimum (knapsack, intervals, rod, tour, cover,
edit distance, pattern counts) is computed by code in this repository. In Iteration 2 the evaluated algorithms,
including their heaps, will be our own implementations; Python's built-in operations will be used only to verify them.
