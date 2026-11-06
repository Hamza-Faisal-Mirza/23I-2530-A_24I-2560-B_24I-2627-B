# Validator

```
python validator/validate.py cases.xlsx --seed 76          # full mode: 50 cases + cross-case variety rules
python validator/validate.py <copy>.xlsx --partial         # validate only the cases present (test copies)
python validator/tests/make_tests.py cases.xlsx            # rebuild validator/tests/*.xlsx and manifest.txt
python validator/make_report.py cases.xlsx                 # write validation_report.txt
```

For every case the validator prints `PASS`, or `FAIL` followed by each broken rule tagged V1-V8. It then prints the
workbook-level problems and a final `RESULT`. The exit code is 0 only if everything passes.

It trusts no field: every count, optimum, planted object, signature rule and trap property is recomputed from the
raw rows. It does not import generator code. Where the generator uses exhaustive search for a tier-S claim, the
validator uses a different exact method, so the two programs check each other:

| Claim | Generator | Validator |
|---|---|---|
| cargo_opt | all 2^n subsets (meet in the middle) | O(nW) dynamic programme |
| window_count_opt / window_value_opt | DFS over all compatible subsets | earliest-finish greedy / weighted-interval DP |
| drum_opt | all integer partitions of L | O(L^2) rod-cutting DP |
| tour_opt | all (n-1)!/2 tours | Held-Karp DP |
| cover_min | all subsets by increasing size | branch and bound on an uncovered edge |
| pattern counts | `str.find` scan | KMP |

| Check | What is verified |
|---|---|
| V1 | exactly the 20 sheets in order and the exact headers; integer/text cell types; no empty rows, formulas or merged cells; rows sorted by case_id then the second column; 50 distinct case_ids `76-kk`; correct tier and scenario |
| V2 | every size within its tier range (tier X = L, except the trap overrides) and every value within its range |
| V3 | consecutive identifiers; every reference (road ends, targets, waves, planted items, cover nodes, literals) exists; serials unique |
| V4 | network connected before closures; waves disjoint, each with 1..max(1, floor(E/4)) roads |
| V5 | pattern counts (overlaps included) and the six pattern lengths; edit_bound within [true distance, len a + len b]; log parts in order and at most 10,000 symbols; tier-S claims |
| V6 | planted tour and its length (and on L/X, not longer than the nearest-neighbour tour, under both tie rules); cover; safety assignment; ration selection |
| V7 | the signature rules of cases 0-45 and the four variety rules |
| V8 | traps 46-49 |

`tests/manifest.txt` lists each test copy with the rule it must trigger. `make_report.py` checks that each broken copy is
rejected and that the rejection names the expected rule.
