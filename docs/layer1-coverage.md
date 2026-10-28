# Layer 1 dictionary v0.1.1-draft - coverage report

Method: each distinct official `description` formula (docs/inventory-description.json, generated from the v0.4.0 mirror) was classified by `layer1_classify.py` with `layer1_dictionary.json`. Universe: divisions carrying a real description formula. Per-formula assignments are CI-diffed (docs/layer1-formula-buckets.json).

Universe: 10479 divisions = 15.8% of the 66,427-division mirror. The rest has no qualifying description and is outside layer-1 scope - not 'misclassified'.

| bucket | divisions | share of universe | share of corpus |
|---|---|---|---|
| bill_whole | 5820 | 55.5% | 8.8% |
| first_reading_rejection | 1087 | 10.4% | 1.6% |
| unspecified | 1054 | 10.1% | 1.6% |
| resolution_whole | 892 | 8.5% | 1.3% |
| rejection | 702 | 6.7% | 1.1% |
| election | 344 | 3.3% | 0.5% |
| committee_composition | 258 | 2.5% | 0.4% |
| appointment | 132 | 1.3% | 0.2% |
| wotum | 122 | 1.2% | 0.2% |
| re_enactment | 36 | 0.3% | 0.1% |
| dismissal | 32 | 0.3% | 0.0% |

Bucket coverage: 9425 = 89.9% of the described universe; 14.2% of the full corpus.
Formulas: 1494 raw -> 1455 canonical after normalization (39 raw variants collapse into shared canonical forms).
Rule-order conflicts (matched by >1 bucket): 1092 divisions.

Per term:

| bucket | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | total |
|---|---|---|---|---|---|---|---|---|---|
| bill_whole | 657 | 890 | 391 | 970 | 742 | 914 | 635 | 621 | 5820 |
| first_reading_rejection | 107 | 194 | 57 | 116 | 165 | 204 | 119 | 125 | 1087 |
| unspecified | 54 | 132 | 55 | 67 | 114 | 176 | 181 | 275 | 1054 |
| resolution_whole | 129 | 121 | 49 | 94 | 93 | 140 | 119 | 147 | 892 |
| rejection | 76 | 127 | 31 | 114 | 176 | 44 | 124 | 10 | 702 |
| election | 10 | 35 | 35 | 57 | 70 | 83 | 25 | 29 | 344 |
| committee_composition | 2 | 32 | 28 | 46 | 54 | 63 | 33 | 0 | 258 |
| appointment | 7 | 3 | 5 | 1 | 4 | 36 | 37 | 39 | 132 |
| wotum | 9 | 25 | 8 | 11 | 14 | 24 | 19 | 12 | 122 |
| re_enactment | 9 | 4 | 1 | 17 | 1 | 0 | 0 | 4 | 36 |
| dismissal | 1 | 3 | 2 | 1 | 3 | 4 | 3 | 15 | 32 |

Notes: draft status - no layer-1 scores until the dictionary is frozen (CODEBOOK section 10); 1,301 of 1,494 formulas are singletons (min-bucket rule, section 8); validation sample split into tuning (200) and held-out test (100) sets.
