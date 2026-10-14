# simdjson v5 RVV-VLA — 3-hour direct-GCC engine exploration

## Provenance and validation

- Campaign: `night-20261010T220545Z-5e4191`; input ZIP `engine_library_3h_packet.zip`.
- Native board: BPI-F3 / RISC-V RVV VLEN 256 bits, GCC 14.2, `-O3`, CPU 0, DOM-only.
- Stopped normally at 3-hour budget, 2,469 measurements, ten full fixed-grid rounds plus quick screen and partial 11th round.
- Source snapshot SHA256 `997df4f149ad5e880195378302ac3b2555700e3b6c8b02234f527d68e1bdea8c`.
- 17 of 17 candidates compiled, link success and 6 valid / 3 invalid minimal runtime JSON checks each. `failures.csv` contains no failure rows.
- 14 corpus **labels**: seven families, two size buckets. `citm_catalog` and `twitter` are byte-identical across small/large buckets and are not independent corpora.
- Method: per trial DOM throughput median of three, one GB = 1e9 bytes, paired by phase + corpus + iterations + trial. Reported ratios = geometric means of exact matched keys. There are 145–146 pairs per candidate.
- No Stage1, Stage2 or instruction-per-byte measurement. Do not compare magnitude directly to preceding benchmark families.
- Correction coverage is a smoke suite (6 valid, 3 invalid), not complete parser conformance. UTF8 raw-byte input was not established: the `unicode_strings` synthetic generator may primarily contain `\uXXXX` escapes.

## Ranked DOM throughput against official v5.0.3 `rvv_vls256`

| Point | Geo ratio | Median paired ratio | Matched N | Geo excluding dense | Relative to sparse8 reference |
|---|---:|---:|---:|---:|---:|
| `E14_packed_disabled` | 1.473× | 1.332× | 145 | 1.357× | 1.043× |
| `E07_utf8` | 1.438× | 1.327× | 145 | 1.317× | 1.018× |
| `E06_unicode_escape` | 1.434× | 1.324× | 145 | 1.313× | 1.016× |
| `E08_balanced` | 1.433× | 1.329× | 145 | 1.313× | 1.015× |
| `E05_escaped` | 1.433× | 1.325× | 145 | 1.312× | 1.014× |
| `E01_adaptive` | 1.429× | 1.321× | 146 | 1.310× | 1.015× |
| `E04_text` | 1.425× | 1.323× | 145 | 1.304× | 1.009× |
| `E10_packed_escape` | 1.422× | 1.291× | 145 | 1.301× | 1.007× |
| `E13_stage2_prefetch` | 1.420× | 1.324× | 145 | 1.297× | 1.006× |
| `E03_numeric` | 1.415× | 1.328× | 145 | 1.294× | 1.002× |
| `sparse8_escape8_reference` | 1.408× | 1.322× | 146 | 1.283× | 1.000× |
| `E02_dense` | 1.356× | 1.319× | 145 | 1.230× | 0.960× |
| `E09_mask_writer` | 1.251× | 1.286× | 145 | 1.272× | 0.886× |
| `E11_packed_quote_shift` | 1.048× | 0.973× | 145 | 0.947× | 0.742× |
| `upstream_vls256` | 1.000× | 1.000× | 146 | 1.000× | 0.710× |
| `E12_string_fastpath_only` | 0.959× | 0.921× | 145 | 0.945× | 0.679× |
| `E00_historical` | 0.907× | 1.015× | 146 | 0.885× | 0.644× |

## Family-level paired geometric ratios vs official

| Point | ASCII | CITM | Dense | Escapes | Numbers | Twitter | Unicode-escaped |
|---|---:|---:|---:|---:|---:|---:|---:|
| `E14_packed_disabled` | 1.168× | 1.650× | 2.392× | 1.309× | 1.334× | 1.720× | 1.101× |
| `E01_adaptive` | 1.102× | 1.602× | 2.408× | 1.319× | 1.283× | 1.630× | 1.065× |
| `sparse8_escape8_reference` | 0.969× | 1.725× | 2.451× | 1.238× | 1.325× | 1.711× | 0.993× |
| `E07_utf8` | 1.112× | 1.601× | 2.411× | 1.324× | 1.288× | 1.638× | 1.073× |
| `E13_stage2_prefetch` | 1.046× | 1.586× | 2.427× | 1.322× | 1.291× | 1.615× | 1.062× |
| `E09_mask_writer` | 1.114× | 1.578× | 1.130× | 1.325× | 1.289× | 1.340× | 1.069× |
| `E11_packed_quote_shift` | 0.788× | 0.885× | 1.909× | 1.205× | 1.025× | 0.975× | 0.856× |
| `E12_string_fastpath_only` | 0.820× | 0.921× | 1.044× | 1.203× | 1.066× | 0.906× | 0.810× |
| `E00_historical` | 0.587× | 1.018× | 1.055× | 1.095× | 1.150× | 0.946× | 0.693× |

## Direct comparisons of our engines

- `E14_packed_disabled` vs `E01_adaptive`: **1.0285×**, across 145 matched settings (~+2.85%). E14 wins 104/145 individual matched settings.
- `E14_packed_disabled` vs `sparse8_escape8_reference`: **1.0431×** (~+4.31%).
- E14 wins its margin on ASCII (+5.9% vs adaptive), numeric (+4.0%), Twitter (+5.5%) and escaped-Unicode (+3.3%), whereas adaptive wins dense (~+0.65%) and escapes (~+0.7%).
- The older `sparse8_escape8_reference` remains better than E14 on `citm_catalog` (~+4.5%) and dense (~+2.5%), and is strong on Twitter.
- No conclusion about an actual combined dispatch policy: the experiment compiled separate binary modes. It did not measure profile-dependent runtime switching between binaries.

## Corpus weighting and robustness

- Across all 145 paired observations, E14 vs official is 1.473×. Excluding dense corpus pairs it is **1.357×**; removing the repeated small CITM/Twitter labels yields **1.443×**.
- E01 vs official excluding dense is **1.310×**; repeated evidence over ten fixed rounds is internally stable.
- Extreme fast/slow paths change the meaning of one headline ratio. The median paired ratio for E14 is only **1.332×**, whereas the geometric mean is **1.473×**.
- The 14 corpus labels comprise seven families and two size buckets; CITM and Twitter are exact duplicate byte sizes and source contents in both buckets, so reporting 14 independent documents would be incorrect.
- Ratios are paired but execution order is fixed, so temperature/cache/order and the limited synthetic corpus set remain potential confounders. The same source snapshot and compiler settings do not prove production latency.

## Mechanism changes to prioritize

1. **Keep E14 as a primary candidate** while retaining E01 adaptive and the sparse8 reference as required controls. It wins the overall DOM ratio but does not win on every family.
2. **Probe plan selection versus encoding on raw UTF-8**; current labels (`E07_utf8`, `unicode_strings`) are not proof that true raw multibyte UTF-8 was stress-tested.
3. **Profile Stage1 and Stage2** separately on a targeted subset of variants/corpora; 3h DOM-only data do not localize the bottleneck or prove the Stage2 prefetch benefit.
4. **Full correctness**: escaped backslashes, long strings, nested documents, unicode surrogate pairs, malformed numbers, streaming/chunk boundaries and sanitizer checks.
5. **A/B confirmation**: compare E14, adaptive, sparse8 and official against fixed workload corpora, alternate measurement order, log governor/frequency and CPU conditions; avoid broad 17× rebuilds until new code changes justify them.
6. A theoretical offline chooser selecting sparse8 for dense/CITM and E14 elsewhere would show about **1.487×** against official (only +0.97% over E14 in this weighting), before dispatch overhead. This is **not** a tested runtime dispatch design.

## Archival and source constraints

- The copy of the deployed C++ source is not in the ZIP; precise source-level causal attribution and a new engine implementation require the complete current `simdjson-rvv-vla-v5` snapshot.
- `source_git_sha` reports the expected `bf89ddd00ef5fcb6a7f20611ea8853d258b67249` reference; the remote extracted snapshot does not contain `.git`, so remote `git rev-parse` is unavailable.
- The campaign reported 4.43 GiB free at its final checkpoint.
