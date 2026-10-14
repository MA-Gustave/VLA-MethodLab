# Targeted holdout validation 2h: descriptive data, no automatic winner

As of 2026-10-12T19:23:00+00:00, 8402 records; 496 planned JSON cases.

These per-shape values are geometric means of matched DOM ratios against
official simdjson VLS256. Repeated trials are correlated. The same corpus
design drives all variants, but there is no multi-hardware replication.
Subgroups with small paired n are especially noisy. These are candidates
for future confirmation, not a winner, not statistically significant.

| Family | Size band | Mode | Matched n | DOM vs VLS256 |
|---|---|---|---:|---:|
| ascii | gate (4-8KiB) | A0_E14_original | 58 | 0.314x |
| ascii | gate (4-8KiB) | A1_size_gate | 58 | 0.318x |
| ascii | gate (4-8KiB) | A2_quick_dispatch | 58 | 0.922x |
| ascii | gate (4-8KiB) | sparse8_escape8_reference | 58 | 0.928x |
| ascii | tiny (<4KiB) | A0_E14_original | 154 | 0.603x |
| ascii | tiny (<4KiB) | A1_size_gate | 154 | 1.539x |
| ascii | tiny (<4KiB) | A2_quick_dispatch | 154 | 1.535x |
| ascii | tiny (<4KiB) | sparse8_escape8_reference | 154 | 1.268x |
| dense | gate (4-8KiB) | A0_E14_original | 116 | 0.389x |
| dense | gate (4-8KiB) | A1_size_gate | 116 | 0.392x |
| dense | gate (4-8KiB) | A2_quick_dispatch | 116 | 1.002x |
| dense | gate (4-8KiB) | sparse8_escape8_reference | 116 | 0.920x |
| dense | medium (8-256KiB) | A0_E14_original | 53 | 0.869x |
| dense | medium (8-256KiB) | A1_size_gate | 53 | 0.872x |
| dense | medium (8-256KiB) | A2_quick_dispatch | 53 | 1.022x |
| dense | medium (8-256KiB) | sparse8_escape8_reference | 53 | 0.711x |
| dense | tiny (<4KiB) | A0_E14_original | 53 | 0.335x |
| dense | tiny (<4KiB) | A1_size_gate | 53 | 1.402x |
| dense | tiny (<4KiB) | A2_quick_dispatch | 53 | 1.394x |
| dense | tiny (<4KiB) | sparse8_escape8_reference | 53 | 0.971x |
| dense+escaped+unicode_escape | gate (4-8KiB) | A0_E14_original | 23 | 1.382x |
| dense+escaped+unicode_escape | gate (4-8KiB) | A1_size_gate | 23 | 1.396x |
| dense+escaped+unicode_escape | gate (4-8KiB) | A2_quick_dispatch | 23 | 1.684x |
| dense+escaped+unicode_escape | gate (4-8KiB) | sparse8_escape8_reference | 23 | 1.679x |
| dense+escaped+unicode_escape | medium (8-256KiB) | A0_E14_original | 25 | 1.708x |
| dense+escaped+unicode_escape | medium (8-256KiB) | A1_size_gate | 25 | 1.709x |
| dense+escaped+unicode_escape | medium (8-256KiB) | A2_quick_dispatch | 25 | 1.760x |
| dense+escaped+unicode_escape | medium (8-256KiB) | sparse8_escape8_reference | 25 | 1.703x |
| dense+numbers+utf8 | gate (4-8KiB) | A0_E14_original | 24 | 1.473x |
| dense+numbers+utf8 | gate (4-8KiB) | A1_size_gate | 24 | 1.524x |
| dense+numbers+utf8 | gate (4-8KiB) | A2_quick_dispatch | 24 | 1.897x |
| dense+numbers+utf8 | gate (4-8KiB) | sparse8_escape8_reference | 24 | 1.922x |
| dense+numbers+utf8 | medium (8-256KiB) | A0_E14_original | 18 | 1.908x |
| dense+numbers+utf8 | medium (8-256KiB) | A1_size_gate | 18 | 1.913x |
| dense+numbers+utf8 | medium (8-256KiB) | A2_quick_dispatch | 18 | 1.973x |
| dense+numbers+utf8 | medium (8-256KiB) | sparse8_escape8_reference | 18 | 1.914x |
| dense+unicode_escape | gate (4-8KiB) | A0_E14_original | 23 | 1.241x |
| dense+unicode_escape | gate (4-8KiB) | A1_size_gate | 23 | 1.255x |
| dense+unicode_escape | gate (4-8KiB) | A2_quick_dispatch | 23 | 1.520x |
| dense+unicode_escape | gate (4-8KiB) | sparse8_escape8_reference | 23 | 1.492x |
| dense+unicode_escape | medium (8-256KiB) | A0_E14_original | 21 | 1.535x |
| dense+unicode_escape | medium (8-256KiB) | A1_size_gate | 21 | 1.542x |
| dense+unicode_escape | medium (8-256KiB) | A2_quick_dispatch | 21 | 1.593x |
| dense+unicode_escape | medium (8-256KiB) | sparse8_escape8_reference | 21 | 1.513x |
| escaped | gate (4-8KiB) | A0_E14_original | 106 | 0.388x |
| escaped | gate (4-8KiB) | A1_size_gate | 106 | 0.392x |
| escaped | gate (4-8KiB) | A2_quick_dispatch | 106 | 0.969x |
| escaped | gate (4-8KiB) | sparse8_escape8_reference | 106 | 0.890x |
| escaped | medium (8-256KiB) | A0_E14_original | 53 | 0.932x |
| escaped | medium (8-256KiB) | A1_size_gate | 53 | 0.939x |
| escaped | medium (8-256KiB) | A2_quick_dispatch | 53 | 1.118x |
| escaped | medium (8-256KiB) | sparse8_escape8_reference | 53 | 0.765x |
| escaped | tiny (<4KiB) | A0_E14_original | 145 | 0.623x |
| escaped | tiny (<4KiB) | A1_size_gate | 145 | 1.442x |
| escaped | tiny (<4KiB) | A2_quick_dispatch | 145 | 1.438x |
| escaped | tiny (<4KiB) | sparse8_escape8_reference | 145 | 1.194x |
| escaped+slashstorm | gate (4-8KiB) | A0_E14_original | 18 | 1.362x |
| escaped+slashstorm | gate (4-8KiB) | A1_size_gate | 18 | 1.372x |
| escaped+slashstorm | gate (4-8KiB) | A2_quick_dispatch | 18 | 1.569x |
| escaped+slashstorm | gate (4-8KiB) | sparse8_escape8_reference | 18 | 1.575x |
| escaped+slashstorm | medium (8-256KiB) | A0_E14_original | 19 | 1.547x |
| escaped+slashstorm | medium (8-256KiB) | A1_size_gate | 19 | 1.547x |
| escaped+slashstorm | medium (8-256KiB) | A2_quick_dispatch | 19 | 1.575x |
| escaped+slashstorm | medium (8-256KiB) | sparse8_escape8_reference | 19 | 1.550x |
| many_keys+long_strings+utf8 | gate (4-8KiB) | A0_E14_original | 20 | 1.139x |
| many_keys+long_strings+utf8 | gate (4-8KiB) | A1_size_gate | 20 | 1.162x |
| many_keys+long_strings+utf8 | gate (4-8KiB) | A2_quick_dispatch | 20 | 1.634x |
| many_keys+long_strings+utf8 | gate (4-8KiB) | sparse8_escape8_reference | 20 | 1.626x |
| many_keys+long_strings+utf8 | medium (8-256KiB) | A0_E14_original | 20 | 1.610x |
| many_keys+long_strings+utf8 | medium (8-256KiB) | A1_size_gate | 20 | 1.611x |
| many_keys+long_strings+utf8 | medium (8-256KiB) | A2_quick_dispatch | 20 | 1.705x |
| many_keys+long_strings+utf8 | medium (8-256KiB) | sparse8_escape8_reference | 20 | 1.592x |
| numbers | gate (4-8KiB) | A0_E14_original | 50 | 0.436x |
| numbers | gate (4-8KiB) | A1_size_gate | 50 | 0.443x |
| numbers | gate (4-8KiB) | A2_quick_dispatch | 50 | 0.985x |
| numbers | gate (4-8KiB) | sparse8_escape8_reference | 50 | 0.817x |
| numbers | medium (8-256KiB) | A0_E14_original | 56 | 0.856x |
| numbers | medium (8-256KiB) | A1_size_gate | 56 | 0.862x |
| numbers | medium (8-256KiB) | A2_quick_dispatch | 56 | 1.012x |
| numbers | medium (8-256KiB) | sparse8_escape8_reference | 56 | 0.705x |
| numbers | tiny (<4KiB) | A0_E14_original | 92 | 0.857x |
| numbers | tiny (<4KiB) | A1_size_gate | 92 | 1.510x |
| numbers | tiny (<4KiB) | A2_quick_dispatch | 92 | 1.502x |
| numbers | tiny (<4KiB) | sparse8_escape8_reference | 92 | 1.346x |
| numbers+utf8 | gate (4-8KiB) | A0_E14_original | 23 | 1.088x |
| numbers+utf8 | gate (4-8KiB) | A1_size_gate | 23 | 1.113x |
| numbers+utf8 | gate (4-8KiB) | A2_quick_dispatch | 23 | 1.470x |
| numbers+utf8 | gate (4-8KiB) | sparse8_escape8_reference | 23 | 1.465x |
| numbers+utf8 | medium (8-256KiB) | A0_E14_original | 24 | 1.466x |
| numbers+utf8 | medium (8-256KiB) | A1_size_gate | 24 | 1.470x |
| numbers+utf8 | medium (8-256KiB) | A2_quick_dispatch | 24 | 1.533x |
| numbers+utf8 | medium (8-256KiB) | sparse8_escape8_reference | 24 | 1.448x |
| sparse+dense+long_strings | gate (4-8KiB) | A0_E14_original | 21 | 1.634x |
| sparse+dense+long_strings | gate (4-8KiB) | A1_size_gate | 21 | 1.662x |
| sparse+dense+long_strings | gate (4-8KiB) | A2_quick_dispatch | 21 | 2.284x |
| sparse+dense+long_strings | gate (4-8KiB) | sparse8_escape8_reference | 21 | 2.235x |
| sparse+dense+long_strings | medium (8-256KiB) | A0_E14_original | 18 | 2.336x |
| sparse+dense+long_strings | medium (8-256KiB) | A1_size_gate | 18 | 2.337x |
| sparse+dense+long_strings | medium (8-256KiB) | A2_quick_dispatch | 18 | 2.455x |
| sparse+dense+long_strings | medium (8-256KiB) | sparse8_escape8_reference | 18 | 2.302x |
| unicode_escape | gate (4-8KiB) | A0_E14_original | 111 | 0.385x |
| unicode_escape | gate (4-8KiB) | A1_size_gate | 111 | 0.386x |
| unicode_escape | gate (4-8KiB) | A2_quick_dispatch | 111 | 0.890x |
| unicode_escape | gate (4-8KiB) | sparse8_escape8_reference | 111 | 0.820x |
| unicode_escape | medium (8-256KiB) | A0_E14_original | 53 | 0.931x |
| unicode_escape | medium (8-256KiB) | A1_size_gate | 53 | 0.937x |
| unicode_escape | medium (8-256KiB) | A2_quick_dispatch | 53 | 1.112x |
| unicode_escape | medium (8-256KiB) | sparse8_escape8_reference | 53 | 0.762x |
| unicode_escape | tiny (<4KiB) | A0_E14_original | 57 | 0.332x |
| unicode_escape | tiny (<4KiB) | A1_size_gate | 57 | 1.121x |
| unicode_escape | tiny (<4KiB) | A2_quick_dispatch | 57 | 1.118x |
| unicode_escape | tiny (<4KiB) | sparse8_escape8_reference | 57 | 0.842x |
| utf8 | gate (4-8KiB) | A0_E14_original | 48 | 0.444x |
| utf8 | gate (4-8KiB) | A1_size_gate | 48 | 0.450x |
| utf8 | gate (4-8KiB) | A2_quick_dispatch | 48 | 1.003x |
| utf8 | gate (4-8KiB) | sparse8_escape8_reference | 48 | 0.837x |
| utf8 | medium (8-256KiB) | A0_E14_original | 50 | 0.931x |
| utf8 | medium (8-256KiB) | A1_size_gate | 50 | 0.940x |
| utf8 | medium (8-256KiB) | A2_quick_dispatch | 50 | 1.117x |
| utf8 | medium (8-256KiB) | sparse8_escape8_reference | 50 | 0.761x |
| utf8 | tiny (<4KiB) | A0_E14_original | 91 | 0.930x |
| utf8 | tiny (<4KiB) | A1_size_gate | 91 | 1.633x |
| utf8 | tiny (<4KiB) | A2_quick_dispatch | 91 | 1.623x |
| utf8 | tiny (<4KiB) | sparse8_escape8_reference | 91 | 1.464x |
| whitespace+dense+utf8 | gate (4-8KiB) | A0_E14_original | 18 | 1.807x |
| whitespace+dense+utf8 | gate (4-8KiB) | A1_size_gate | 18 | 1.861x |
| whitespace+dense+utf8 | gate (4-8KiB) | A2_quick_dispatch | 18 | 2.335x |
| whitespace+dense+utf8 | gate (4-8KiB) | sparse8_escape8_reference | 18 | 2.370x |
| whitespace+dense+utf8 | medium (8-256KiB) | A0_E14_original | 19 | 2.330x |
| whitespace+dense+utf8 | medium (8-256KiB) | A1_size_gate | 19 | 2.338x |
| whitespace+dense+utf8 | medium (8-256KiB) | A2_quick_dispatch | 19 | 2.405x |
| whitespace+dense+utf8 | medium (8-256KiB) | sparse8_escape8_reference | 19 | 2.359x |

## Hypotheses to re-test (single-trial outliers; NOT validated)

The following are extreme A2/A0 DOM comparisons only, selected
post hoc among many related tests. Expect selection bias and noise.
Re-run each with new data, repeated fresh processes, and independent
reference order. Do not publish them as achieved speedups.

| Corpus | Kind | Placement | A2/A0 DOM | Prefix-vs-rest proxy |
|---|---|---|---:|---:|
| `holdout90_corpus/0214_gate4096_dense_threshold_4080_20265620.json` | dense | threshold | 5.042x | 0.0547 |
| `holdout90_corpus/0147_gate4096_escaped_threshold_4080_20465821.json` | escaped | threshold | 4.396x | 0.0664 |
| `holdout90_corpus/0149_gate4096_escaped_threshold_4088_20465829.json` | escaped | threshold | 4.394x | 0.0664 |
| `holdout90_corpus/0152_gate4096_escaped_threshold_4095_20265833.json` | escaped | threshold | 4.391x | 0.0664 |
| `holdout90_corpus/0146_gate4096_escaped_threshold_4080_20265818.json` | escaped | threshold | 4.387x | 0.0664 |
| `holdout90_corpus/0146_gate4096_escaped_threshold_4080_20265818.json` | escaped | threshold | 4.382x | 0.0664 |
| `holdout90_corpus/0150_gate4096_escaped_threshold_4092_20265830.json` | escaped | threshold | 4.378x | 0.0664 |
| `holdout90_corpus/0143_gate4096_escaped_threshold_4032_20465773.json` | escaped | threshold | 4.346x | 0.0664 |
| `holdout90_corpus/0115_gate4096_ascii_threshold_4088_20465625.json` | ascii | threshold | 4.341x | 0.0293 |
| `holdout90_corpus/0116_gate4096_ascii_threshold_4092_20265626.json` | ascii | threshold | 4.340x | 0.0293 |
| `holdout90_corpus/0115_gate4096_ascii_threshold_4088_20465625.json` | ascii | threshold | 4.339x | 0.0293 |
| `holdout90_corpus/0117_gate4096_ascii_threshold_4092_20465629.json` | ascii | threshold | 4.336x | 0.0293 |
| `holdout90_corpus/0112_gate4096_ascii_threshold_4080_20265614.json` | ascii | threshold | 4.335x | 0.0293 |
| `holdout90_corpus/0109_gate4096_ascii_threshold_4032_20465569.json` | ascii | threshold | 4.331x | 0.0293 |
| `holdout90_corpus/0108_gate4096_ascii_threshold_4032_20265566.json` | ascii | threshold | 4.329x | 0.0293 |
