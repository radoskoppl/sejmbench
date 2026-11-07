# Placebo temporal-cutoff robustness check (issue #14, scope item 5)

9B (basal-omni-1.0-ultra, full corpus n=66,104) winner accuracy pre/post at
the real cutoff (2026-01-01) and at placebo cutoffs. Pre/post at a cutoff is
a composition comparison by construction; the placebo test asks whether the
real cutoff shows a discontinuity the placebo cutoffs do not. Term-10 rows
hold the term composition fixed (see the #5 correction).

| cutoff | scope | n pre | acc pre | n post | acc post | gap (post−pre) |
|---|---|---|---|---|---|---|
| 2024-01-01 | full corpus | 61112 | 0.9821 | 4992 | 0.9483 | -0.0338 |
| 2024-01-01 | term 10 only | 145 | 0.9793 | 4992 | 0.9483 | -0.0310 |
| 2025-01-01 | full corpus | 62407 | 0.9819 | 3697 | 0.9410 | -0.0408 |
| 2025-01-01 | term 10 only | 1440 | 0.9701 | 3697 | 0.9410 | -0.0291 |
| 2026-01-01 | full corpus | 64187 | 0.9808 | 1917 | 0.9384 | -0.0424 |
| 2026-01-01 | term 10 only | 3220 | 0.9556 | 1917 | 0.9384 | -0.0171 |

Reading: the 2026 cutoff isolates the newest, post-training-data sittings;
the placebo cutoffs split older data at arbitrary points. A contamination
signal would appear as a 2026-specific negative gap absent at the placebos;
a gap pattern that moves smoothly with the cutoff date indicates composition,
not contamination. This check does not certify uncontaminatedness.

## Outcome (2026-11-08)

- full corpus: gap by cutoff (2024 → 2025 → 2026): -3.38 pp → -4.08 pp → -4.24 pp.
- term 10 only: gap by cutoff (2024 → 2025 → 2026): -3.10 pp → -2.91 pp → -1.71 pp.

The full-corpus gap grows monotonically with a later cutoff while the
term-10 gap shrinks — the 2026 cutoff is not an outlier in either series,
so there is no 2026-specific discontinuity of the kind a contamination
signal would produce. The trends match composition (post sets become more
term-10-heavy as the cutoff moves later) and a within-term recency trend.
