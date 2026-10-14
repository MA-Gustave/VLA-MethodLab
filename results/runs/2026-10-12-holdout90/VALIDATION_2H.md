# Test 90 — held-out targeted native validation (2h)

Predeclared hypotheses from Test 89. New JSON seeds, no reruns of the original JSON.
Five separately compiled native RISC-V v5.0.3 backends, including official VLS256.
All reported ratios are matched within the same JSON and trial; each JSON counts once.
Primary protocols require at least TWO independent subprocess trials per JSON to count.
All primary scenarios are scheduled for THREE trials before secondary coverage.
Stage1 and Stage2 measured directly, not inferred from public DOM.
Single host and compiler; intervals below are naive case-resampling estimates,
NOT a performance guarantee, hardware generalization, or corrected multiple-testing inference.

Observations: 8402; primary paired case-metric clusters: 704.
Independent holdout JSON generated: 496.

## Precommitted questions
- H1: quantify A1/A0 overhead near 512B, not a backend switch.
- H2: is the 4095 -> 4096B discontinuity of A1/A0 and A2/A0 reproducible?
- H3: when does sparse8 outperform A2 on mixed JSON?
- H4: does moving difficulty after byte 512 change A2 against A0/sparse8?
- H5: are A2/A0 differences mainly in Stage1, not Stage2?

## Primary per-corpus geometric mean, with 90% case-bootstrap interval

| Numerator / denominator | Metric | Design | Subgroup | JSON n | Geo-mean | 90% case CI |
|---|---|---|---|---:|---:|---|
| A1_size_gate / A0_E14_original | dom_ratio | all_primary | all | 88 | 1.470x | 1.341–1.615x |
| A1_size_gate / A0_E14_original | dom_ratio | deceptive_prefix | deceptive_prefix | 20 | 1.009x | 1.006–1.011x |
| A1_size_gate / A0_E14_original | dom_ratio | gate4096 | 3840 | 2 | 3.776x | 3.349–4.258x |
| A1_size_gate / A0_E14_original | dom_ratio | gate4096 | 3968 | 2 | 3.318x | 3.273–3.364x |
| A1_size_gate / A0_E14_original | dom_ratio | gate4096 | 4032 | 2 | 3.728x | 3.383–4.109x |
| A1_size_gate / A0_E14_original | dom_ratio | gate4096 | 4064 | 2 | 4.071x | 3.946–4.199x |
| A1_size_gate / A0_E14_original | dom_ratio | gate4096 | 4080 | 2 | 4.183x | 4.161–4.205x |
| A1_size_gate / A0_E14_original | dom_ratio | gate4096 | 4088 | 2 | 4.194x | 4.102–4.287x |
| A1_size_gate / A0_E14_original | dom_ratio | gate4096 | 4092 | 2 | 3.759x | 3.401–4.154x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 480 | 2 | 1.121x | 1.116–1.127x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 496 | 2 | 1.128x | 1.118–1.137x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 504 | 2 | 1.132x | 1.125–1.138x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 508 | 2 | 1.127x | 1.124–1.129x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 511 | 2 | 1.126x | 1.111–1.141x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 512 | 2 | 2.375x | 2.303–2.449x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 513 | 2 | 2.150x | 2.060–2.244x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 516 | 2 | 2.291x | 2.251–2.332x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 520 | 2 | 2.249x | 2.064–2.451x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 528 | 2 | 2.335x | 2.312–2.358x |
| A1_size_gate / A0_E14_original | dom_ratio | gate512 | 544 | 2 | 2.444x | 2.407–2.481x |
| A1_size_gate / A0_E14_original | dom_ratio | hard_offset | 2048 | 3 | 1.008x | 1.003–1.013x |
| A1_size_gate / A0_E14_original | dom_ratio | hard_offset | 4095 | 3 | 1.007x | 1.002–1.012x |
| A1_size_gate / A0_E14_original | dom_ratio | hard_offset | 4096 | 3 | 1.014x | 1.010–1.017x |
| A1_size_gate / A0_E14_original | dom_ratio | hard_offset | 4097 | 3 | 1.008x | 1.002–1.014x |
| A1_size_gate / A0_E14_original | dom_ratio | hard_offset | 480 | 2 | 1.011x | 1.003–1.019x |
| A1_size_gate / A0_E14_original | dom_ratio | hard_offset | 511 | 2 | 1.006x | 1.003–1.009x |
| A1_size_gate / A0_E14_original | dom_ratio | hard_offset | 512 | 2 | 1.005x | 1.005–1.005x |
| A1_size_gate / A0_E14_original | dom_ratio | hard_offset | 513 | 2 | 1.010x | 1.008–1.012x |
| A1_size_gate / A0_E14_original | dom_ratio | prefix_after512 | no | 4 | 1.008x | 1.003–1.015x |
| A1_size_gate / A0_E14_original | dom_ratio | prefix_after512 | yes | 16 | 1.009x | 1.006–1.011x |
| A1_size_gate / A0_E14_original | dom_ratio | sparse_challenge | sparse_challenge | 20 | 1.011x | 1.006–1.017x |
| A1_size_gate / A0_E14_original | stage1_ratio | all_primary | all | 88 | 1.655x | 1.493–1.858x |
| A1_size_gate / A0_E14_original | stage1_ratio | deceptive_prefix | deceptive_prefix | 20 | 1.013x | 1.011–1.015x |
| A1_size_gate / A0_E14_original | stage1_ratio | hard_offset | 2048 | 3 | 1.010x | 1.006–1.014x |
| A1_size_gate / A0_E14_original | stage1_ratio | hard_offset | 4095 | 3 | 1.013x | 1.011–1.014x |
| A1_size_gate / A0_E14_original | stage1_ratio | hard_offset | 4096 | 3 | 1.021x | 1.020–1.023x |
| A1_size_gate / A0_E14_original | stage1_ratio | hard_offset | 4097 | 3 | 1.014x | 1.009–1.018x |
| A1_size_gate / A0_E14_original | stage1_ratio | hard_offset | 480 | 2 | 1.012x | 1.005–1.019x |
| A1_size_gate / A0_E14_original | stage1_ratio | hard_offset | 511 | 2 | 1.011x | 1.010–1.012x |
| A1_size_gate / A0_E14_original | stage1_ratio | hard_offset | 512 | 2 | 1.009x | 1.005–1.012x |
| A1_size_gate / A0_E14_original | stage1_ratio | hard_offset | 513 | 2 | 1.012x | 1.009–1.016x |
| A1_size_gate / A0_E14_original | stage1_ratio | prefix_after512 | no | 4 | 1.011x | 1.007–1.015x |
| A1_size_gate / A0_E14_original | stage1_ratio | prefix_after512 | yes | 16 | 1.013x | 1.011–1.016x |
| A1_size_gate / A0_E14_original | stage1_ratio | sparse_challenge | sparse_challenge | 20 | 1.027x | 1.018–1.038x |
| A1_size_gate / A0_E14_original | stage2_ratio | all_primary | all | 88 | 1.000x | 0.999–1.002x |
| A1_size_gate / A0_E14_original | stage2_ratio | deceptive_prefix | deceptive_prefix | 20 | 0.998x | 0.994–1.002x |
| A1_size_gate / A0_E14_original | stage2_ratio | hard_offset | 2048 | 3 | 1.005x | 1.000–1.009x |
| A1_size_gate / A0_E14_original | stage2_ratio | hard_offset | 4095 | 3 | 0.987x | 0.978–0.996x |
| A1_size_gate / A0_E14_original | stage2_ratio | hard_offset | 4096 | 3 | 1.003x | 0.996–1.010x |
| A1_size_gate / A0_E14_original | stage2_ratio | hard_offset | 4097 | 3 | 0.990x | 0.987–0.992x |
| A1_size_gate / A0_E14_original | stage2_ratio | hard_offset | 480 | 2 | 1.011x | 1.010–1.011x |
| A1_size_gate / A0_E14_original | stage2_ratio | hard_offset | 511 | 2 | 0.997x | 0.997–0.998x |
| A1_size_gate / A0_E14_original | stage2_ratio | hard_offset | 512 | 2 | 1.005x | 0.996–1.013x |
| A1_size_gate / A0_E14_original | stage2_ratio | hard_offset | 513 | 2 | 0.996x | 0.996–0.996x |
| A1_size_gate / A0_E14_original | stage2_ratio | prefix_after512 | no | 4 | 1.004x | 1.000–1.010x |
| A1_size_gate / A0_E14_original | stage2_ratio | prefix_after512 | yes | 16 | 0.997x | 0.993–1.001x |
| A1_size_gate / A0_E14_original | stage2_ratio | sparse_challenge | sparse_challenge | 20 | 0.999x | 0.997–1.001x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | all_primary | all | 88 | 1.851x | 1.697–2.019x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | deceptive_prefix | deceptive_prefix | 20 | 1.518x | 1.372–1.677x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate4096 | 3840 | 2 | 3.758x | 3.333–4.237x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate4096 | 3968 | 2 | 3.355x | 3.355–3.355x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate4096 | 4032 | 2 | 3.705x | 3.366–4.078x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate4096 | 4064 | 2 | 4.057x | 3.931–4.186x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate4096 | 4080 | 2 | 4.205x | 4.152–4.258x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate4096 | 4088 | 2 | 4.168x | 4.081–4.256x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate4096 | 4092 | 2 | 3.742x | 3.381–4.143x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 480 | 2 | 1.115x | 1.104–1.127x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 496 | 2 | 1.127x | 1.118–1.135x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 504 | 2 | 1.133x | 1.129–1.137x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 508 | 2 | 1.126x | 1.122–1.129x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 511 | 2 | 1.120x | 1.106–1.135x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 512 | 2 | 2.378x | 2.286–2.473x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 513 | 2 | 2.143x | 2.075–2.215x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 516 | 2 | 2.249x | 2.200–2.299x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 520 | 2 | 2.233x | 2.036–2.450x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 528 | 2 | 2.328x | 2.288–2.369x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | gate512 | 544 | 2 | 2.434x | 2.396–2.473x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | hard_offset | 2048 | 3 | 1.469x | 1.194–1.801x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | hard_offset | 4095 | 3 | 1.781x | 1.435–2.210x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | hard_offset | 4096 | 3 | 1.190x | 1.179–1.202x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | hard_offset | 4097 | 3 | 1.466x | 1.177–1.825x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | hard_offset | 480 | 2 | 1.556x | 1.181–2.051x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | hard_offset | 511 | 2 | 1.604x | 1.184–2.174x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | hard_offset | 512 | 2 | 1.635x | 1.187–2.252x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | hard_offset | 513 | 2 | 1.632x | 1.173–2.270x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | prefix_after512 | no | 4 | 1.580x | 1.183–2.111x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | prefix_after512 | yes | 16 | 1.503x | 1.335–1.692x |
| A2_quick_dispatch / A0_E14_original | dom_ratio | sparse_challenge | sparse_challenge | 20 | 1.176x | 1.126–1.234x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | all_primary | all | 88 | 2.257x | 2.064–2.474x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | deceptive_prefix | deceptive_prefix | 20 | 1.695x | 1.477–1.896x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | hard_offset | 2048 | 3 | 1.621x | 1.284–2.047x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | hard_offset | 4095 | 3 | 2.040x | 1.596–2.606x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | hard_offset | 4096 | 3 | 1.296x | 1.294–1.297x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | hard_offset | 4097 | 3 | 1.637x | 1.283–2.088x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | hard_offset | 480 | 2 | 1.768x | 1.287–2.430x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | hard_offset | 511 | 2 | 1.786x | 1.263–2.525x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | hard_offset | 512 | 2 | 1.833x | 1.262–2.661x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | hard_offset | 513 | 2 | 1.825x | 1.267–2.630x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | prefix_after512 | no | 4 | 1.777x | 1.281–2.453x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | prefix_after512 | yes | 16 | 1.675x | 1.466–1.919x |
| A2_quick_dispatch / A0_E14_original | stage1_ratio | sparse_challenge | sparse_challenge | 20 | 1.411x | 1.278–1.551x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | all_primary | all | 88 | 0.999x | 0.997–1.000x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | deceptive_prefix | deceptive_prefix | 20 | 0.994x | 0.991–0.997x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | hard_offset | 2048 | 3 | 0.995x | 0.992–0.997x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | hard_offset | 4095 | 3 | 0.999x | 0.994–1.004x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | hard_offset | 4096 | 3 | 0.994x | 0.984–1.004x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | hard_offset | 4097 | 3 | 0.985x | 0.977–0.992x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | hard_offset | 480 | 2 | 1.000x | 0.989–1.012x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | hard_offset | 511 | 2 | 0.992x | 0.989–0.995x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | hard_offset | 512 | 2 | 0.999x | 0.995–1.003x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | hard_offset | 513 | 2 | 0.989x | 0.985–0.993x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | prefix_after512 | no | 4 | 0.996x | 0.989–1.004x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | prefix_after512 | yes | 16 | 0.993x | 0.989–0.997x |
| A2_quick_dispatch / A0_E14_original | stage2_ratio | sparse_challenge | sparse_challenge | 20 | 0.999x | 0.997–1.001x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | all_primary | all | 88 | 1.165x | 1.139–1.192x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | deceptive_prefix | deceptive_prefix | 20 | 1.337x | 1.290–1.379x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate4096 | 3840 | 2 | 1.369x | 1.318–1.422x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate4096 | 3968 | 2 | 1.320x | 1.319–1.321x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate4096 | 4032 | 2 | 1.359x | 1.328–1.391x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate4096 | 4064 | 2 | 1.411x | 1.399–1.424x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate4096 | 4080 | 2 | 1.437x | 1.424–1.451x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate4096 | 4088 | 2 | 1.408x | 1.391–1.424x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate4096 | 4092 | 2 | 1.391x | 1.350–1.433x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 480 | 2 | 1.093x | 1.070–1.116x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 496 | 2 | 1.099x | 1.091–1.107x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 504 | 2 | 1.096x | 1.087–1.105x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 508 | 2 | 1.110x | 1.106–1.115x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 511 | 2 | 1.083x | 1.082–1.084x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 512 | 2 | 1.088x | 1.075–1.100x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 513 | 2 | 1.089x | 1.083–1.096x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 516 | 2 | 1.104x | 1.090–1.118x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 520 | 2 | 1.098x | 1.092–1.104x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 528 | 2 | 1.121x | 1.111–1.131x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | gate512 | 544 | 2 | 1.112x | 1.100–1.125x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | hard_offset | 2048 | 3 | 1.362x | 1.270–1.461x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | hard_offset | 4095 | 3 | 1.270x | 1.190–1.356x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | hard_offset | 4096 | 3 | 1.443x | 1.427–1.459x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | hard_offset | 4097 | 3 | 1.355x | 1.280–1.433x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | hard_offset | 480 | 2 | 1.284x | 1.160–1.422x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | hard_offset | 511 | 2 | 1.305x | 1.172–1.453x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | hard_offset | 512 | 2 | 1.332x | 1.217–1.458x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | hard_offset | 513 | 2 | 1.310x | 1.204–1.425x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | prefix_after512 | no | 4 | 1.295x | 1.221–1.437x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | prefix_after512 | yes | 16 | 1.347x | 1.304–1.396x |
| A2_quick_dispatch / sparse8_escape8_reference | dom_ratio | sparse_challenge | sparse_challenge | 20 | 1.021x | 1.011–1.033x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | all_primary | all | 88 | 1.239x | 1.197–1.281x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | deceptive_prefix | deceptive_prefix | 20 | 1.488x | 1.407–1.570x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | hard_offset | 2048 | 3 | 1.508x | 1.373–1.657x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | hard_offset | 4095 | 3 | 1.388x | 1.250–1.540x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | hard_offset | 4096 | 3 | 1.674x | 1.662–1.687x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | hard_offset | 4097 | 3 | 1.533x | 1.398–1.681x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | hard_offset | 480 | 2 | 1.428x | 1.223–1.668x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | hard_offset | 511 | 2 | 1.421x | 1.229–1.644x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | hard_offset | 512 | 2 | 1.455x | 1.283–1.650x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | hard_offset | 513 | 2 | 1.448x | 1.260–1.663x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | prefix_after512 | no | 4 | 1.425x | 1.227–1.650x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | prefix_after512 | yes | 16 | 1.504x | 1.408–1.586x |
| A2_quick_dispatch / sparse8_escape8_reference | stage1_ratio | sparse_challenge | sparse_challenge | 20 | 1.010x | 0.984–1.036x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | all_primary | all | 88 | 1.007x | 1.004–1.009x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | deceptive_prefix | deceptive_prefix | 20 | 0.997x | 0.993–1.001x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | hard_offset | 2048 | 3 | 0.992x | 0.987–1.002x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | hard_offset | 4095 | 3 | 1.008x | 1.003–1.012x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | hard_offset | 4096 | 3 | 0.997x | 0.989–1.004x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | hard_offset | 4097 | 3 | 0.990x | 0.983–0.997x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | hard_offset | 480 | 2 | 1.003x | 0.994–1.013x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | hard_offset | 511 | 2 | 0.993x | 0.988–0.997x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | hard_offset | 512 | 2 | 1.003x | 1.002–1.003x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | hard_offset | 513 | 2 | 0.990x | 0.989–0.990x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | prefix_after512 | no | 4 | 0.998x | 0.991–1.005x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | prefix_after512 | yes | 16 | 0.996x | 0.993–1.000x |
| A2_quick_dispatch / sparse8_escape8_reference | stage2_ratio | sparse_challenge | sparse_challenge | 20 | 1.021x | 1.016–1.025x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | all_primary | all | 88 | 1.334x | 1.281–1.390x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | deceptive_prefix | deceptive_prefix | 20 | 1.032x | 1.011–1.051x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate4096 | 3840 | 2 | 1.222x | 1.112–1.343x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate4096 | 3968 | 2 | 1.116x | 1.112–1.120x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate4096 | 4032 | 2 | 1.201x | 1.108–1.303x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate4096 | 4064 | 2 | 1.325x | 1.317–1.333x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate4096 | 4080 | 2 | 1.367x | 1.329–1.406x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate4096 | 4088 | 2 | 1.321x | 1.310–1.333x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate4096 | 4092 | 2 | 1.290x | 1.194–1.394x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 480 | 2 | 1.598x | 1.517–1.683x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 496 | 2 | 1.577x | 1.532–1.623x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 504 | 2 | 1.590x | 1.557–1.623x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 508 | 2 | 1.515x | 1.508–1.522x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 511 | 2 | 1.603x | 1.517–1.694x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 512 | 2 | 1.657x | 1.626–1.689x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 513 | 2 | 1.537x | 1.513–1.562x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 516 | 2 | 1.536x | 1.499–1.574x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 520 | 2 | 1.596x | 1.521–1.675x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 528 | 2 | 1.567x | 1.508–1.629x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | gate512 | 544 | 2 | 1.589x | 1.504–1.679x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | hard_offset | 2048 | 3 | 1.079x | 1.041–1.118x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | hard_offset | 4095 | 3 | 0.987x | 0.958–1.017x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | hard_offset | 4096 | 3 | 1.046x | 1.011–1.083x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | hard_offset | 4097 | 3 | 1.032x | 1.019–1.045x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | hard_offset | 480 | 2 | 0.960x | 0.923–0.999x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | hard_offset | 511 | 2 | 1.048x | 0.995–1.104x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | hard_offset | 512 | 2 | 1.082x | 1.055–1.110x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | hard_offset | 513 | 2 | 1.020x | 1.015–1.025x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | prefix_after512 | no | 4 | 1.003x | 0.959–1.056x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | prefix_after512 | yes | 16 | 1.039x | 1.017–1.060x |
| A2_quick_dispatch / upstream_vls256 | dom_ratio | sparse_challenge | sparse_challenge | 20 | 1.724x | 1.643–1.835x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | all_primary | all | 88 | 1.395x | 1.301–1.514x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | deceptive_prefix | deceptive_prefix | 20 | 0.958x | 0.923–0.995x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | hard_offset | 2048 | 3 | 0.962x | 0.840–1.030x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | hard_offset | 4095 | 3 | 0.895x | 0.821–0.977x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | hard_offset | 4096 | 3 | 1.032x | 1.030–1.033x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | hard_offset | 4097 | 3 | 1.006x | 0.973–1.041x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | hard_offset | 480 | 2 | 0.894x | 0.777–1.029x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | hard_offset | 511 | 2 | 0.912x | 0.827–1.005x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | hard_offset | 512 | 2 | 0.978x | 0.943–1.013x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | hard_offset | 513 | 2 | 0.965x | 0.893–1.044x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | prefix_after512 | no | 4 | 0.903x | 0.828–0.974x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | prefix_after512 | yes | 16 | 0.972x | 0.940–1.008x |
| A2_quick_dispatch / upstream_vls256 | stage1_ratio | sparse_challenge | sparse_challenge | 20 | 2.409x | 2.103–2.743x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | all_primary | all | 88 | 1.327x | 1.294–1.362x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | deceptive_prefix | deceptive_prefix | 20 | 1.226x | 1.144–1.297x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | hard_offset | 2048 | 3 | 1.383x | 1.322–1.448x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | hard_offset | 4095 | 3 | 1.230x | 1.107–1.368x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | hard_offset | 4096 | 3 | 1.089x | 0.981–1.208x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | hard_offset | 4097 | 3 | 1.102x | 0.979–1.239x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | hard_offset | 480 | 2 | 1.131x | 0.953–1.342x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | hard_offset | 511 | 2 | 1.425x | 1.328–1.529x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | hard_offset | 512 | 2 | 1.363x | 1.331–1.396x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | hard_offset | 513 | 2 | 1.195x | 0.991–1.440x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | prefix_after512 | no | 4 | 1.269x | 1.038–1.429x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | prefix_after512 | yes | 16 | 1.215x | 1.139–1.298x |
| A2_quick_dispatch / upstream_vls256 | stage2_ratio | sparse_challenge | sparse_challenge | 20 | 1.206x | 1.152–1.278x |

## Interpretation restrictions

Do NOT treat a narrow CI on one machine as independent-machine replication.
512B is a classifier INSPECTION WINDOW for large JSON, NOT the dispatch gate (4096B).
Iterations change between 512B and 513B; benchmark iteration count is a possible confound.
The 512- and 4096-byte families are selected due to Test89, so confirmatory
language applies only to this held-out corpus and prespecified contrasts.
All per-trial rows and exact content SHA256 values are archived; inconclusive n is not hidden.
The stop_reason and partial primary-round coverage must be checked before claiming a result.
