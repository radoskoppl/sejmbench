# Layer 1 dictionary v0.1.0-draft — coverage over the official description inventory

Method: each distinct official `description` formula (docs/inventory-description.json, generated from the v0.4.0 mirror) was classified by `layer1_classify.py` with `layer1_dictionary.json` v0.1.0-draft. Universe: divisions carrying a real description formula.

Universe: 10479 divisions (mirror total 66,427; 10479 with a real description = 15.8%).

| bucket | divisions | share of universe |
|---|---|---|
| bill_whole | 5819 | 55.5% |
| unspecified | 1194 | 11.4% |
| first_reading_rejection | 1087 | 10.4% |
| resolution_whole | 882 | 8.4% |
| rejection | 702 | 6.7% |
| committee_composition | 258 | 2.5% |
| election | 213 | 2.0% |
| appointment | 132 | 1.3% |
| wotum | 122 | 1.2% |
| re_enactment | 36 | 0.3% |
| dismissal | 34 | 0.3% |

Per term:

| bucket | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | total |
|---|---|---|---|---|---|---|---|---|---|
| bill_whole | 657 | 890 | 391 | 970 | 742 | 913 | 635 | 621 | 5819 |
| unspecified | 65 | 154 | 62 | 80 | 138 | 212 | 196 | 287 | 1194 |
| first_reading_rejection | 107 | 194 | 57 | 116 | 165 | 204 | 119 | 125 | 1087 |
| resolution_whole | 126 | 118 | 49 | 91 | 93 | 140 | 119 | 146 | 882 |
| rejection | 76 | 127 | 31 | 114 | 176 | 44 | 124 | 10 | 702 |
| committee_composition | 2 | 32 | 28 | 46 | 54 | 63 | 33 | 0 | 258 |
| election | 2 | 16 | 28 | 47 | 45 | 47 | 10 | 18 | 213 |
| appointment | 7 | 3 | 5 | 1 | 4 | 36 | 37 | 39 | 132 |
| wotum | 9 | 25 | 8 | 11 | 14 | 24 | 19 | 12 | 122 |
| re_enactment | 9 | 4 | 1 | 17 | 1 | 0 | 0 | 4 | 36 |
| dismissal | 1 | 3 | 2 | 1 | 4 | 5 | 3 | 15 | 34 |

Bucket coverage: 9285 (88.6%); `unspecified` tail is by design (1,301 of 1,494 formulas are singletons; min-bucket rule, CODEBOOK section 8).
Draft status: no layer-1 scores until the dictionary is frozen (CODEBOOK section 10).
