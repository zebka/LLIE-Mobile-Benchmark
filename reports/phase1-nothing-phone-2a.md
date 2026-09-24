# Phase-1 case study: Nothing Phone (2a)

**Status:** complete (2026-09-24). Single-device case study; not a public leaderboard.

## Device profile

| Field | Value |
|---|---|
| Model | Nothing Phone (2a) (A142) |
| Android | 16 (API 36) |
| SoC | MT6886 |
| Build | `Nothing/Pacman/Pacman:16/BP2A.250605.031.A3/2608130941:user/release-keys` |
| Runtime | ONNX Runtime 1.19.2, CPUExecutionProvider |
| Precision | float32 |
| Thermal (before/after) | light / light (both runs) |

No ADB serial appears in this report.

## Protocol (frozen)

- batch = 1, warm-up = 5, measured passes = 3 per image
- 15 paired images from `04_datasets/paired/eval15/low` at 600×400 (study shape)
- On-device monotonic clock (`SystemClock.elapsedRealtimeNanos`); ADB only starts/polls the batch
- Quality metrics computed on host after inference, outside any timing loop

## Model artifacts

| Model | Artifact bytes | Parameters | Precision | SHA-256 (truncated) |
|---|---:|---:|---|---|
| zero-dce | 324,671 | 79,416 | float32 | `b73dfcec78c969af…` |
| sci-medium | 3,560 | 252 | float32 | `006ae2e76b5a795d…` |

## Runtime results (CPU, Nothing Phone 2a)

Both runs: `success=true`, schema-valid (`protocol/run-result.schema.json`), 15/15 outputs saved.

### Latency (all 45 timed samples per model: 15 images × 3 passes)

| Model | Load (ms) | Model mean (ms) | Model median (ms) | Model p95 (ms) | E2E mean (ms) | E2E median (ms) | E2E p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| zero-dce | 240.51 | 2305.80 | 2324.93 | 2371.50 | 2305.83 | 2324.95 | 2371.52 |
| sci-medium | 122.73 | 72.80 | 70.40 | 85.26 | 72.82 | 70.42 | 85.28 |

### Memory (PSS peak)

| Model | PSS peak (MB) | Samples |
|---|---:|---:|
| zero-dce | 613.5 | 476 |
| sci-medium | 218.7 | 32 |

### Quality on paired eval15 (n=15, mean ± std)

| Model | PSNR (dB) | SSIM | LPIPS (alex) |
|---|---|---|---|
| zero-dce | 14.80 ± 4.27 | 0.561 ± 0.125 | 0.335 ± 0.129 |
| sci-medium | 14.78 ± 4.26 | 0.525 ± 0.136 | 0.339 ± 0.132 |

Per-image rows: `phase1-results/<model>/metrics.csv` (columns `image_id,status,psnr,ssim,lpips`).
Latency rows: `phase1-results/latency.csv` (median/p95 per image from `results_to_csv`).

## Observations and limitations

1. **sci-medium is ~32× faster than zero-dce** on this CPU at 600×400 (median 70 ms vs 2325 ms) while using ~2.8× less peak PSS (219 MB vs 614 MB). Quality is statistically indistinguishable on this 15-image set.
2. **Neither model reaches high paired-reference quality** on eval15 (SSIM ≈ 0.53–0.56). This is expected for zero-reference/heuristic LLIE against a single paired ground truth; the numbers are reported as measured, not as a ranking claim.
3. **CPU only.** NNAPI/GPU/NPU delegates were not exercised in this phase; LiteRT tooling was absent on the host machine (recorded as a failed candidate, not hidden).
4. **Thermal stayed at `light`** for both runs; no throttling event was recorded. A cool-down re-run was not required for schema validity but is listed as optional follow-up.
5. **Single device, single resolution.** High-resolution stress inputs and multi-device comparison belong to Phase 2.

## Reproduce

```bash
# on host (from 07_mobile_benchmark/)
python -m pytest host/tests tools/compatibility -q   # 39 tests
# regenerate metrics from saved outputs
python -c "from llie_bench.metrics import evaluate_folders, aggregate, write_metrics_csv; ..."
# regenerate latency CSV
python -c "from llie_bench.report import results_to_csv; ..."
```

Raw artifacts: `phase1-results/<model>/{run.json,status.txt,outputs/*.png,metrics.csv,latency.csv}`.
