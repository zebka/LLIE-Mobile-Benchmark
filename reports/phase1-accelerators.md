# Phase-1 accelerators: NNAPI / XNNPACK on Nothing Phone (2a)

**Status:** complete (2026-09-24). Companion to the CPU case study
(`phase1-nothing-phone-2a.md`). Single-device study; not a leaderboard.

## Scope

ORT Android 1.19.2 exposes `addNnapi()` and `addXnnpack(Map)` on this
build. There is no standalone GPU execution provider in the ORT Android
package (GPU is reachable only through NNAPI drivers) and no direct NPU
path (QNN targets Qualcomm; this SoC is MediaTek MT6886). The schema
labels `gpu`/`npu` therefore route to the NNAPI EP in
`SelectedRuntimeEngine`; only `nnapi` and `xnnpack` were exercised
on-device, one full eval15 batch each for `zero-dce` and `sci-medium`.

## Protocol (same frozen protocol as the CPU study)

- batch = 1, warm-up = 5, measured passes = 3 per image, 15 paired
  eval15 images at 600×400
- On-device monotonic clock; ADB only starts/polls the batch
- Quality metrics computed on host after inference, outside timing
- Each combo re-ran to a clean `done` with 15 pulled PNGs whose bytes
  match the reported `run.json` (shell-owned 666 placeholders, overwrite
  in place, pull between runs so shared `outputs-<backend>` dirs never mix
  models; per-model `outputs-<model>-<backend>` dirs are in the app as of
  the committed fix)

No ADB serial appears in this report.

## Results (verified runs, Nothing Phone 2a, ORT 1.19.2, float32)

### Latency (global median / p95 over all 45 timed samples per combo)

| Model | Backend | Load (ms) | Model median (ms) | Model p95 (ms) | PSS peak (MB) |
|---|---|---:|---:|---:|---:|
| zero-dce | cpu | 240.51 | 2324.93 | 2371.50 | 613.5 |
| zero-dce | nnapi | 170.70 | 2365.50 | 2398.52 | 591.0 |
| zero-dce | xnnpack | 165.86 | 2305.01 | 2331.79 | 586.8 |
| sci-medium | cpu | 122.73 | 70.40 | 85.26 | 218.7 |
| sci-medium | nnapi | 418.89 | 70.66 | 105.68 | 227.4 |
| sci-medium | xnnpack | 112.50 | 69.59 | 92.80 | 225.0 |

Per-image rows: `phase1-accelerators/latency.csv`
(`llie_bench.report.results_to_csv`); summary: `latency-summary.csv`.
All runs `success=true`, schema-valid, thermal light/light.

### Quality on paired eval15 (n=15, mean ± std)

| Model | Backend | PSNR (dB) | SSIM | LPIPS (alex) |
|---|---|---|---|---|
| zero-dce | cpu | 14.80 ± 4.27 | 0.561 ± 0.125 | 0.335 ± 0.129 |
| zero-dce | nnapi | 14.80 ± 4.27 | 0.561 ± 0.125 | 0.335 ± 0.129 |
| zero-dce | xnnpack | 14.80 ± 4.27 | 0.561 ± 0.125 | 0.335 ± 0.129 |
| sci-medium | cpu | 14.78 ± 4.26 | 0.525 ± 0.136 | 0.339 ± 0.132 |
| sci-medium | nnapi | 14.78 ± 4.26 | 0.525 ± 0.136 | 0.339 ± 0.132 |
| sci-medium | xnnpack | 14.78 ± 4.26 | 0.525 ± 0.136 | 0.339 ± 0.132 |

Per-image rows: `phase1-accelerators/<model>-<backend>/metrics.csv`;
summary: `metrics-summary.json`. All 60 pulled PNGs (4 combos × 15)
are **byte-identical (SHA-256) to the CPU outputs**.

## Findings

1. **No effective acceleration.** On this device/build, NNAPI and
   XNNPACK run both graphs at CPU speed (within ±2%) with
   byte-identical outputs — consistent with CPU fallback inside ORT's
   EPs for these graphs, not with device-side acceleration. No
   per-node EP placement log exists in the app to confirm partition
   boundaries; that logging is Phase-2 work.
2. **Quality parity is exact, not approximate.** Bit-identical PNGs
   mean the EPs change neither quality metric by any epsilon on eval15.
3. **NNAPI session load is not free.** `sci-medium/nnapi` paid
   418.89 ms load vs 122.73 ms on CPU for the same 3.5 KB artifact —
   delegate setup cost dominates for tiny graphs.
4. **Unresolved variance (reported, not hidden).** An earlier
   same-day batch measured ~28 ms (sci-medium/NNAPI+XNNPACK) and
   ~909 ms median (zero-dce/XNNPACK). Three subsequent clean,
   sequential re-runs of `sci-medium/nnapi` (69.51 / 70.37 / ~69 ms,
   screen-on control included, `stayon` reset afterwards) reproduce the
   CPU-level numbers reported above. Screen state was ruled out as the
   cause; CPU governor history and background activity remain
   uncontrolled. Follow-up needs locked clocks / cooldown protocol and
   per-node placement logs before any speedup claim.
5. **`gpu`/`npu` labels untested as distinct paths.** They map to the
   NNAPI EP in this codebase and were not run separately; no claim is
   made about them beyond that mapping.

## Raw artifacts

`phase1-accelerators/<model>-<backend>/{run.json,status.txt,latency.csv,metrics.csv,outputs/*.png}`
plus `latency.csv`, `latency-summary.csv`, `metrics-summary.json`.
Regenerate from `host/` with `llie-bench report --results-dir
../reports/phase1-accelerators --ref-dir ../04_datasets/paired/eval15/high`.
Host tests: 47 passed (`host/tests`, `tools/compatibility`).
