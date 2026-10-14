Holdout validation 2h — fixed hypotheses from Test 89

- Snapshot updated: 2026-10-12T19:22:57+00:00
- State: stopped
- Measurements: 8402
- GCC direct compile; separate DOM, Stage1 and Stage2 wall times, each median of 3; GB=1e9 bytes.
- Stage1 and Stage2 are measured from implementation methods, not derived from DOM; warm allocated parser.
- Five fixed points, holdout corpus and three precommitted independent-process repeats per primary case.
- Randomized corpus order and alternated/reversed candidates; exploratory results only.

## Paired metric ratios against official v5.0.3 VLS256

| Candidate | Metric | Geo-mean vs official VLS256 | N | MAD |
|---|---|---:|---:|---:|
| A2_quick_dispatch | dom_all | 1.281x | 1680 | 0.292 |
| sparse8_escape8_reference | dom_all | 1.096x | 1680 | 0.187 |
| upstream_vls256 | dom_all | 1.000x | 1680 | 0.000 |
| A1_size_gate | dom_all | 0.937x | 1680 | 0.413 |
| A0_E14_original | dom_all | 0.686x | 1680 | 0.357 |
| A2_quick_dispatch | stage1 | 1.295x | 1680 | 0.279 |
| sparse8_escape8_reference | stage1 | 1.044x | 1680 | 0.176 |
| upstream_vls256 | stage1 | 1.000x | 1680 | 0.000 |
| A1_size_gate | stage1 | 0.865x | 1680 | 0.696 |
| A0_E14_original | stage1 | 0.576x | 1680 | 0.289 |
| A0_E14_original | stage2 | 1.350x | 1680 | 0.095 |
| A1_size_gate | stage2 | 1.350x | 1680 | 0.100 |
| A2_quick_dispatch | stage2 | 1.349x | 1680 | 0.099 |
| sparse8_escape8_reference | stage2 | 1.339x | 1680 | 0.108 |
| upstream_vls256 | stage2 | 1.000x | 1680 | 0.000 |
