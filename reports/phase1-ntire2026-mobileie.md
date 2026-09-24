# Phase-1 NTIRE 2026 on-device study: MobileIE-6Ch

**Status:** complete (2026-09-25). Companion to the CPU case study
(`phase1-nothing-phone-2a.md`) and the accelerator study
(`phase1-accelerators.md`). Single-device study; not a leaderboard.

## Scope

MobileIE-6Ch (HIT-LLIE team, NTIRE 2026 efficient-LLIE challenge) is the
first challenge model run through this repo's full gate: public code and
checkpoint ([upstream](https://github.com/w-xb/MobileIE-6Ch), Apache-2.0),
PyTorch reference, ONNX export, ORT parity, and on-device measurement.
Measured live parameters: **23,882** (the widely quoted 101,922 is the
fp32 checkpoint file size in bytes — see
`reports/compatibility/ntire2026-assessment.md`).

## Protocol (same frozen protocol as the CPU study)

- batch = 1, warm-up = 5, measured passes = 3 per image, 15 paired
  eval15 images at 600×400, float32
- On-device monotonic clock; ADB only starts/polls the batch
- Quality metrics computed on host after inference, outside timing
- One full batch per backend (cpu, nnapi, xnnpack), pulled between runs

No ADB serial appears in this report.

## Results (Nothing Phone 2a, ORT 1.19.2)

### Latency (global median / p95 over all 45 timed samples per combo)

| Backend | Load (ms) | Model median (ms) | Model p95 (ms) | PSS peak (MB) |
|---|---:|---:|---:|---:|
| cpu | 88.17 | 289.19 | 363.77 | 428.3 |
| nnapi | 143.35 | 322.56 | 369.91 | 433.2 |
| xnnpack | 104.58 | 327.62 | 375.50 | 425.9 |

Per-image rows: `ntire2026-mobileie/latency.csv`
(`llie_bench.report.results_to_csv`); summary: `latency-summary.csv`.
All runs `success=true`, schema-valid, thermal none/none.

### Quality on paired eval15 (n=15, mean ± std)

| Backend | PSNR (dB) | SSIM | LPIPS (alex) |
|---|---|---|---|
| cpu | 17.91 ± 4.74 | 0.717 ± 0.110 | 0.359 ± 0.088 |
| nnapi | 17.91 ± 4.74 | 0.717 ± 0.110 | 0.359 ± 0.088 |
| xnnpack | 17.91 ± 4.74 | 0.717 ± 0.110 | 0.359 ± 0.088 |

Per-image rows: `ntire2026-mobileie/<combo>/metrics.csv`;
summary: `metrics-summary.json`. NNAPI outputs are byte-identical
(SHA-256, 15/15) to CPU; XNNPACK outputs differ at ~1e-6 (EP numerical
noise, quality-neutral).

### Against the Phase-1 baselines (same phone, same eval15)

| Model | Params | Median (ms) | PSNR | SSIM | LPIPS |
|---|---:|---:|---:|---:|---:|
| zero-dce | 79,416 | 2324.9 | 14.80 | 0.561 | 0.335 |
| sci-medium | 252 | 70.4 | 14.78 | 0.525 | 0.339 |
| mobileie-6ch | 23,882 | 289.2 | 17.91 | 0.717 | 0.359 |

## Findings

1. **Best quality-per-cost point measured so far.** MobileIE-6Ch is ~8×
   faster than zero-dce at +3.1 dB PSNR / +0.16 SSIM, and costs +3.1 dB /
   +0.19 SSIM over sci-medium for ~4× the latency — with 23,882
   parameters. It is the only tested model that is both fast and clearly
   better-looking than the baselines on paired references.
2. **No EP acceleration, same as the baselines.** NNAPI is a full CPU
   fallback (bit-identical outputs); XNNPACK executes (distinct
   numerics) but lands at CPU speed. Delegate setup cost dominates tiny
   graphs (`sci-medium/nnapi` load was 419 ms for a 3.5 KB artifact).
3. **Quality caveat as before.** n=15, no human study; the numbers are
   reported as measured, not as a ranking claim. TCD (252,341 measured
   params) is the pending comparison — its ONNX export is blocked on the
   FFT phase-transfer block (see the assessment note).

## Raw artifacts

`ntire2026-mobileie/<combo>/{run.json,status.txt,latency.csv,metrics.csv,outputs/*.png}`
plus `latency.csv`, `latency-summary.csv`, `metrics-summary.json`.
Regenerate from `host/` with `llie-bench report --results-dir
../reports/ntire2026-mobileie --ref-dir ../../04_datasets/paired/eval15/high`.
Host tests: 70 passed (`host/tests`, `tools/compatibility`).
