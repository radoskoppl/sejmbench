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

Bucket coverage: 9285 (88.6%); `unspecified` tail is by design (1,301 of 1,494 formulas are singletons; min-bucket rule, CODEBOOK section 8).
Draft status: no layer-1 scores until the dictionary is frozen (CODEBOOK section 10).
