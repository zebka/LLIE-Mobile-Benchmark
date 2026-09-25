# Phase-2 case study: Redmi 9T

**Status:** complete (2026-09-26). Single-device case study; not a public leaderboard.
Companion to the Phase-2 Redmi Note 10 Pro study (`phase2-redmi-note-10-pro.md`) and the
Phase-1 Nothing Phone (2a) studies (`phase1-nothing-phone-2a.md`,
`phase1-ntire2026-mobileie.md`, `phase1-accelerators.md`, `reports/resolution-scaling/`).

## Device profile

| Field | Value |
|---|---|
| Model | Redmi 9T (M2010J19SG, codename `lime`) |
| Released | 2021 (budget tier; Note 10 Pro launched 2021 at midrange) |
| Android | 12 (API 31) |
| SoC | SM6115 (`ro.soc.model`; marketed as Snapdragon 662) — 4× Kryo 260 Gold (Cortex-A73) + 4× Kryo 260 Silver (Cortex-A53) |
| Build | `Redmi/lime_global/lime:12/SKQ1.211202.001/V14.0.3.0.SJQMIXM:user/release-keys` (MIUI 14) |
| Runtime | ONNX Runtime 1.19.2, CPUExecutionProvider |
| Precision | float32 |
| Thermal (before/after) | none / none (every run, full set and ladder) |

No ADB serial appears in this report.

## Protocol (frozen)

- batch = 1, warm-up = 5, measured passes = 3 per image
- 15 paired images from `04_datasets/paired/eval15/low` at 600×400 (study shape)
- On-device monotonic clock (`SystemClock.elapsedRealtimeNanos`); ADB only starts/polls the batch
- Quality metrics computed on host after inference, outside any timing loop
- CPU backend only (CPUExecutionProvider); accelerator backends were a Phase-1 question

## Model artifacts

| Model | Artifact bytes | Precision | SHA-256 (truncated) |
|---|---:|---|---|
| zero-dce | 324,671 | float32 | `b73dfcec78c969af...` |
| sci-medium | 3,560 | float32 | `006ae2e76b5a795d...` |
| mobileie-6ch | 101,471 | float32 | `5c3978c66ffe049b...` |
| ruas-lol | 44,969 | float32 | `15b9443756258426...` |
| lyt-net | 230,030 | float32 | `610d6515f6c9cc6a...` |

Same ONNX artifacts as the Note 10 Pro and Phone 2a studies (`reports/compatibility/`,
one dynamic-axes artifact per model; MobileIE-6Ch tiling config in its manifest);
SHA-256 prefixes match the Note 10 Pro report exactly.

## Runtime results (CPU, Redmi 9T)

All five runs: `success=true`, schema-valid (`protocol/run-result.schema.json`), 15/15
outputs saved.

### APK provenance

The APK measured throughout this report came from repo CI run **36186544938**
(`zebka/LLIE-Mobile-Benchmark`, artifact `app-debug`), **76,921,538 bytes**,
`versionName 0.1.0` — the "minSdk 26 + SOC_MODEL fix" build, one CI revision after the
Note 10 Pro build (run 36125774162). It installed via plain streamed ADB install on this
MIUI build without any installer-attribution workaround (a difference from the Note 10
Pro setup, attributable to the minSdk fix).

### Latency (all 45 timed samples per model: 15 images × 3 passes)

Percentiles use the pooled all-45-sample `model_ns` values with `numpy.percentile`
linear interpolation (same convention as the Note 10 Pro report; reproducible from the
committed `run.json` files).

| Model | Load (ms) | Model mean (ms) | Model median (ms) | Model p95 (ms) | E2E mean (ms) | E2E median (ms) | E2E p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| zero-dce | 119.34 | 1789.00 | 1416.38 | 3573.82 | 1789.02 | 1416.40 | 3573.98 |
| sci-medium | 236.49 | 71.49 | 62.51 | 130.12 | 71.51 | 62.53 | 130.15 |
| mobileie-6ch | 148.28 | 1219.78 | 711.83 | 1922.34 | 1219.82 | 711.85 | 1922.41 |
| ruas-lol | 567.47 | 256.92 | 208.23 | 638.11 | 256.95 | 208.25 | 638.14 |
| lyt-net | 253.75 | 4328.74 | 5103.65 | 6123.93 | 4328.78 | 5103.74 | 6123.99 |

Note: on this device the per-sample distributions are wide (e.g. lyt-net SD 1843 ms,
zero-dce SD 941 ms) and means can sit below medians for the slowest models because the
first measured pass of each image is frequently the slowest (post-warm-up cold paths).
Medians are the headline statistic, as in prior reports.

### Memory (PSS peak)

| Model | PSS peak (MB) | Notes |
|---|---:|---|
| zero-dce | 511.9 | |
| sci-medium | 162.2 | |
| mobileie-6ch | 339.1 | |
| ruas-lol | 192.6 | |
| lyt-net | 1409.8 | highest of the five; multi-head-attention activations |

### Quality on paired eval15 (n=15, mean ± std)

| Model | PSNR (dB) | SSIM | LPIPS (alex) |
|---|---|---|---|
| zero-dce | 14.80 ± 4.27 | 0.561 ± 0.125 | 0.335 ± 0.129 |
| sci-medium | 14.78 ± 4.26 | 0.525 ± 0.136 | 0.339 ± 0.132 |
| mobileie-6ch | 17.91 ± 4.74 | 0.717 ± 0.110 | 0.359 ± 0.088 |
| ruas-lol | 16.30 ± 4.35 | 0.484 ± 0.105 | 0.359 ± 0.126 |
| lyt-net | 21.59 ± 4.92 | 0.812 ± 0.096 | 0.134 ± 0.058 |

Identical to the Note 10 Pro quality table to every reported decimal, as expected for
deterministic inference from the same artifacts and protocol.

Per-image rows: `phase2-redmi-9t/<model>/metrics.csv`
(columns `image_id,status,psnr,ssim,lpips`). Latency rows:
`phase2-redmi-9t/latency.csv`; combo summary:
`phase2-redmi-9t/latency-summary.csv`; aggregate:
`phase2-redmi-9t/metrics-summary.json`.

## Resolution scaling: MobileIE-6Ch ladder (CPU backend)

Purpose and method identical to `reports/resolution-scaling/` (Phone 2a) and the Note 10
Pro ladder: same frozen on-device protocol, LANCZOS-upscaled eval15 inputs (latency-only,
synthetic at scale), one dynamic-axes ONNX artifact pushed once per resolution as
`models/mobileie-6ch-<label>.onnx` with a per-resolution manifest.

| Resolution | MP | Images | median [IQR] ms | p90 ms | ms/MP | peak PSS MB |
|---|---|---|---|---|---|---|
| 600x400   | 0.24 | 15 | 712 [664-1844]  | 1896 | 2966 | 339  |
| 900x600   | 0.54 | 15 | 1482 [1391-3714] | 3954 | 2744 | 692  |
| 1200x800  | 0.96 | 15 | 6632 [6476-7341] | 7948 | 6908 | 1122 |
| 1800x1200 | 2.16 | 5  | OOM (below)      | —    | —    | 2327* |
| 4032x3024 | 12.19 | 1 | OOM (below)      | —    | —    | 211*  |

*PSS peak at the moment of failure, not a completed run. The `Images` column counts
image entries in `run.json` (`images[*]`), not timed samples: the 1800x1200 run recorded
13 partial timed samples (4 images × 3 passes + 1 pass on the fifth image, 79.png)
before the OOM — kept in its `run.json` but too sparse for a trustworthy summary, so no
latency stats are reported for that row in the table. The 4032x3024 run recorded zero
timed samples (OOM during input staging, before any inference).

- 2.25× the pixels (600×400 → 900×600) costs ~2.1× the median latency and per-MP cost is
  roughly flat (2966 → 2744 ms/MP). From 900×600 to 1200×800 (1.78× pixels) latency grows
  ~4.5× and per-MP cost jumps 2.5× (2744 → 6908 ms/MP) — the same super-linear wall the
  Note 10 Pro hit between its second and third ladder points, but here it lands one step
  earlier. The bimodal-looking 600×400/900×600 IQRs reflect per-image spread on a
  heterogeneous big.LITTLE cluster (A73/A53), not measurement artifacts; per-image
  medians are stable within each image.
- Machine-readable table: `phase2-redmi-9t-resolution/latency-summary.csv`.
  **Percentile convention (this report and the ladder CSV):** median, IQR, p90, and mean
  are computed on the pooled per-sample `model_ns` values (all timed samples, all images
  × all passes — n=45 for full combos) with `numpy.percentile` **linear interpolation**
  and SD with ddof=1; every cell is reproducible from the committed `run.json` files.
  OOM rows have no latency summary; the failed `run.json` files keep whatever partial
  samples were recorded.
- The 600×400 row is the main-study run (`phase2-redmi-9t/mobileie-6ch/`, n=45).
- 1800×1200 and 4032×3024 failed on-device; failed `run.json` files are kept in the
  ladder directories (`phase2-redmi-9t-resolution/mobileie-6ch-<label>/run.json`,
  findings, not hidden). The 4032x3024 failed artifact is small (1.1 KB): no images,
  peak PSS 211 MB, allocation failure during input staging.

## Out-of-memory results (also findings)

Both failures hit the Java-heap 256 MB growth limit, same mechanism as the Phone 2a and
Note 10 Pro ladders (allocation sizes match `W*H*12` bytes per buffered image):

| Case | Outcome |
|---|---|
| 1800x1200, 5 images | `OutOfMemoryError`: 25,920,016 B allocation (~5.5 MB free, growth limit 268,435,456 B) on the last image (79.png) after 4/5 completed |
| 4032x3024 (12 MP), 1 image | `OutOfMemoryError`: 146,313,232 B allocation with ~8 MB free; 0 images processed |
| 1200x800, 15 images | success (table above) |

Notes:

1. The 1800x1200 failure is byte-for-byte the same OOM the Note 10 Pro hit on its last
   ladder image (identical allocation size 25,920,016 B, identical target footprint
   268,435,456 B, same image 79.png) — the Note 10 Pro reproduced it twice and this
   device reproduces it once more, now across two devices and three independent
   attempts. What differs by device is where the ceiling lands: on the Note 10 Pro the
   5-image 1800×1200 subset also failed, so this device matches that behavior exactly;
   on the Phone 2a the 5-image subset succeeded at ~2.43 GB peak PSS while the 15-image
   batch OOMed. Process PSS at failure here was ~2.33 GB (mostly native ORT arena) while
   the failed allocation was on the Java heap; the two heaps fail independently.
2. The 4032x3024 failure is also identical to the Note 10 Pro's (146,313,232 B
   allocation, ~8 MB free, 0 images processed, peak PSS ~211 vs ~253 MB) — a
   deterministic failure during input staging, before any inference work starts.
3. Same harness caveat as prior devices: this is a limitation of the benchmark pipeline
   (whole-image float buffering on the Java heap), not a proven limit of the phone or
   ONNX Runtime — camera-scale frames need native/Bitmap buffering, tiling, or a larger
   heap.

## Observations and limitations

1. **Speed ranking on SD662 (600×400 median):** sci-medium 62.5 ms < ruas-lol 208.2 ms
   < mobileie-6ch 711.8 ms < zero-dce 1416.4 ms < lyt-net 5103.6 ms. The Phase-1/Phase-2
   ordering holds on a third, slower SoC; the two challenge models (mobileie-6ch,
   lyt-net) again trade latency for much higher quality than the zero-reference
   baselines.
2. **lyt-net is the quality standout, again:** PSNR 21.59 dB / SSIM 0.812 / LPIPS 0.134
   — +6.8 dB PSNR and +0.25 SSIM over zero-dce — but here it costs 4.2× zero-dce's
   median latency (5104 vs 1416 ms) and 1409.8 MB PSS peak, the most memory-hungry run
   of the study at 600×400. On the faster SD732G the same trade was ~1.25×; on SD662
   lyt-net's attention-heavy graph hits the small A73 cluster much harder.
3. **Cross-device scaling vs Note 10 Pro (SD732G):** zero-dce is 1.5× slower here
   (1416 vs 963 ms median), sci-medium 1.4× (62.5 vs 43.5 ms), mobileie-6ch 1.6×
   (711.8 vs 440.1 ms), ruas-lol 1.4× (208.2 vs 145.2 ms), lyt-net 4.2× (5103.6 vs
   1203.9 ms). The two lightest models scale with raw core-count/clock differences;
   the attention-heavy lyt-net degrades disproportionately on the SD662's A73/A53
   cluster and 4 GB-class memory configuration. Quality metrics are identical to the
   Note 10 Pro to every reported decimal (see the Note 10 Pro report for the
   bit-identical-output verification across devices).
4. **The resolution ladder wall moves with the device.** On SD732G the per-MP cost wall
   sat between 900×600 (4823 ms/MP) and 1200×800 (4775 ms/MP, flat) with the 600×400
   point in a cheaper regime (1834 ms/MP); on SD662 the 600×400 and 900×600 points are
   in one flat regime (2966 → 2744 ms/MP) and the wall lands at 1200×800 (6908 ms/MP).
   Both devices OOM at 1800×1200/4032x3024 under the same Java-heap mechanism.
5. **No thermal events.** Every run recorded thermal `none` before and after; no
   throttling occurred during the full set or the ladder.
6. **Single device, subset caveats.** n=15 images for the matrix and the two lowest
   ladder points; 1800×1200 and 4032x3024 are OOM findings, not measurements. The ladder
   uses synthetic upscaled inputs (latency-only, quality meaningless).
7. **Setup quirks recorded.** The CI APK (minSdk 26 fix) installed cleanly on MIUI 14 /
   Android 12 with no installer-attribution workaround and no install dialog on the
   unlocked screen; `setup` still defaults to the stale 2-model set, so the three extra
   models were pushed explicitly (same flow as prior devices); all runs pass an explicit
   `--image-names` list (which the app honors as the authoritative input order).

## Reproduce

```bash
# from 07_mobile_benchmark/host
llie-bench doctor
llie-bench install <app-debug.apk>                      # CI run 36186544938 build, 76,921,538 bytes
llie-bench setup --compat-dir ../reports/compatibility --images-dir ../../04_datasets/paired/eval15/low
# push the three models setup does not include (from reports/compatibility/):
#   mobileie-6ch, ruas-lol, lyt-net  -> files/{models,manifests}/
llie-bench benchmark --model zero-dce --backend cpu \
  --image-names 1.png,111.png,146.png,179.png,22.png,23.png,493.png,547.png,55.png,665.png,669.png,748.png,778.png,780.png,79.png \
  --out ../reports/phase2-redmi-9t/zero-dce --timeout 1800 --poll-interval 15
# ...repeat for sci-medium, mobileie-6ch, ruas-lol, lyt-net
llie-bench report --results-dir ../reports/phase2-redmi-9t --ref-dir ../../04_datasets/paired/eval15/high

# ladder (per resolution, mobileie-6ch only)
python tools/resolution_scaling/prep_inputs.py 900x600
python tools/resolution_scaling/prep_inputs.py 1200x800
python tools/resolution_scaling/prep_inputs.py 1800x1200 --subset 1.png 22.png 55.png 111.png 79.png
python tools/resolution_scaling/prep_inputs.py 4032x3024 --subset 1.png
# push reports/resolution-scaling/compat/mobileie-6ch-<label>.manifest.json -> manifests/mobileie-6ch-<label>.manifest.json
# push reports/compatibility/mobileie-6ch.onnx             -> models/mobileie-6ch-<label>.onnx
# push reports/resolution-scaling/inputs/<label>           -> images/<label>-set
# then: llie-bench benchmark --model mobileie-6ch-<label> --image-set <label>-set --backend cpu \
#         --image-names <matching list> --out ../reports/phase2-redmi-9t-resolution/mobileie-6ch-<label> --timeout 1800
llie-bench report --results-dir ../reports/phase2-redmi-9t-resolution
```

Raw artifacts: `phase2-redmi-9t/<model>/{run.json,status.txt,outputs/*.png,metrics.csv,latency.csv}`
and `phase2-redmi-9t-resolution/mobileie-6ch-<label>/{run.json,status.txt}` (+ outputs for
the successful points; `latency-summary.csv` at the ladder root; failed `run.json` files
kept in place as OOM findings).
