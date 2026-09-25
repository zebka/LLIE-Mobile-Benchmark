# Phase-2 case study: Redmi Note 10 Pro

**Status:** complete (2026-09-25). Single-device case study; not a public leaderboard.
Companion to the Phase-1 Nothing Phone (2a) studies (`phase1-nothing-phone-2a.md`,
`phase1-ntire2026-mobileie.md`, `phase1-accelerators.md`, `reports/resolution-scaling/`).

## Device profile

| Field | Value |
|---|---|
| Model | Redmi Note 10 Pro (M2101K6G) |
| Android | 13 (API 33) |
| SoC | SM7150 (`ro.soc.model` platform code; marketed as Snapdragon 732G) |
| Build | `Redmi/sweet_global/sweet:13/TKQ1.221013.002/V14.0.8.0.TKFMIXM:user/release-keys` |
| Runtime | ONNX Runtime 1.19.2, CPUExecutionProvider |
| Precision | float32 |
| Thermal (before/after) | none / none (every run, matrix and ladder) |

No ADB serial appears in this report.

## Protocol (frozen)

- batch = 1, warm-up = 5, measured passes = 3 per image
- 15 paired images from `04_datasets/paired/eval15/low` at 600×400 (study shape)
- On-device monotonic clock (`SystemClock.elapsedRealtimeNanos`); ADB only starts/polls the batch
- Quality metrics computed on host after inference, outside any timing loop

## Model artifacts

| Model | Artifact bytes | Parameters | Precision | SHA-256 (truncated) |
|---|---:|---:|---|---|
| zero-dce | 324,671 | 79,416 | float32 | `b73dfcec78c969af...` |
| sci-medium | 3,560 | 252 | float32 | `006ae2e76b5a795d...` |
| mobileie-6ch | 101,471 | 23,882 | float32 | `5c3978c66ffe049b...` |
| ruas-lol | 44,969 | 1,161 | float32 | `15b9443756258426...` |
| lyt-net | 230,030 | 44,923 | float32 | `610d6515f6c9cc6a...` |

Same ONNX artifacts as the Phase-1 studies (`reports/compatibility/`, one dynamic-axes
artifact per model; MobileIE-6Ch tiling config in its manifest).

## Runtime results (CPU, Redmi Note 10 Pro)

All five runs: `success=true`, schema-valid (`protocol/run-result.schema.json`), 15/15
outputs saved.

### APK provenance

The APK measured throughout this report came from repo CI run **36125774162**
(`zebka/LLIE-Mobile-Benchmark`, `main`, 2026-09-25T10:46Z, "Resolution scaling
study..."), artifact `app-debug`, 81,147,094 bytes, `versionName 0.1.0` — the same
build used for the Phone 2a ladder. A local build was not possible on this host
(the local SDK is empty of platforms/build-tools, so `gradlew assembleDebug` was
never run and no APK exists under `android/`). Installing on this MIUI build
required installer attribution (`pm install -i com.android.vending`; see the
setup-quirks note below and the reproduce section).

### Latency (all 45 timed samples per model: 15 images × 3 passes)

| Model | Load (ms) | Model mean (ms) | Model median (ms) | Model p95 (ms) | E2E mean (ms) | E2E median (ms) | E2E p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| zero-dce | 158.85 | 972.98 | 962.80 | 1072.71 | 972.99 | 962.82 | 1072.72 |
| sci-medium | 89.58 | 43.93 | 43.45 | 54.20 | 43.95 | 43.47 | 54.23 |
| mobileie-6ch | 78.98 | 440.15 | 440.10 | 461.18 | 440.16 | 440.11 | 461.20 |
| ruas-lol | 123.80 | 147.53 | 145.15 | 158.73 | 147.54 | 145.16 | 158.74 |
| lyt-net | 189.90 | 1238.18 | 1203.87 | 1317.43 | 1238.20 | 1203.88 | 1317.45 |

### Memory (PSS peak)

| Model | PSS peak (MB) | Notes |
|---|---:|---|
| zero-dce | 515.1 | |
| sci-medium | 172.5 | |
| mobileie-6ch | 353.9 | |
| ruas-lol | 184.9 | |
| lyt-net | 1429.4 | highest of the five; multi-head-attention activations |

### Quality on paired eval15 (n=15, mean ± std)

| Model | PSNR (dB) | SSIM | LPIPS (alex) |
|---|---|---|---|
| zero-dce | 14.80 ± 4.27 | 0.561 ± 0.125 | 0.335 ± 0.129 |
| sci-medium | 14.78 ± 4.26 | 0.525 ± 0.136 | 0.339 ± 0.132 |
| mobileie-6ch | 17.91 ± 4.74 | 0.717 ± 0.110 | 0.359 ± 0.088 |
| ruas-lol | 16.30 ± 4.35 | 0.484 ± 0.105 | 0.359 ± 0.126 |
| lyt-net | 21.59 ± 4.92 | 0.812 ± 0.096 | 0.134 ± 0.058 |

Per-image rows: `phase2-redmi-note-10-pro/<model>/metrics.csv`
(columns `image_id,status,psnr,ssim,lpips`). Latency rows:
`phase2-redmi-note-10-pro/latency.csv`; combo summary:
`phase2-redmi-note-10-pro/latency-summary.csv`; aggregate:
`phase2-redmi-note-10-pro/metrics-summary.json`.

## Resolution scaling: MobileIE-6Ch ladder (CPU backend)

Purpose: check how on-device latency scales with input resolution so the 600×400
numbers are not read as phone-camera-scale numbers. Method identical to
`reports/resolution-scaling/` (Phone 2a): same frozen on-device protocol, LANCZOS-upscaled
eval15 inputs (latency-only, synthetic at scale), one dynamic-axes ONNX artifact pushed
once per resolution as `models/mobileie-6ch-<label>.onnx` with a per-resolution manifest.

| Resolution | MP | Images | median [IQR] ms | p90 ms | ms/MP | peak PSS MB |
|---|---|---|---|---|---|---|
| 600x400   | 0.24 | 15 | 440 [439-447]    | 460   | 1834 | 354  |
| 900x600   | 0.54 | 15 | 2604 [2580-2629] | 2653  | 4823 | 687  |
| 1200x800  | 0.96 | 15 | 4584 [4555-4616] | 4638  | 4775 | 1157 |
| 1800x1200 | 2.16 | 5  | OOM (below)      | —     | —    | 2419* |
| 4032x3024 | 12.19 | 1 | OOM (below)      | —     | —    | 253*  |

*PSS peak at the moment of failure, not a completed run. The `Images` column counts
image entries in `run.json` (`images[*]`), not timed samples: the 1800x1200 run
recorded 13 partial timed samples (4 images × 3 passes + 1 pass on the fifth image,
79.png) before the OOM — kept in its `run.json` but too sparse for a trustworthy
summary, so no latency stats are reported for that row.

- 2.25× the pixels (600×400 → 900×600) costs ~5.9× the latency; per-MP cost ~2.6×
  (1834 → 4823 ms/MP). From 900×600 to 1200×800 (1.78× pixels) latency grows 1.76× and
  per-MP cost is flat (4823 → 4775 ms/MP). The 600×400 point sits in a cheaper per-MP
  regime than every upscaled resolution on this SoC; scaling is super-linear, not
  constant-throughput.
- Machine-readable table: `phase2-redmi-note-10-pro-resolution/latency-summary.csv`.
  **Percentile convention (this report and the ladder CSV):** median, IQR, p90, mean,
  and SD are computed on the pooled per-sample `model_ns` values (all timed samples,
  all images × all passes — n=45 for full combos, 15 for the Phone-2a-style 5-image
  point) with `numpy.percentile` **linear interpolation** and SD with ddof=1; every
  cell is reproducible from the committed `run.json` files. The p95 in the latency
  table above uses the same convention (all-45-sample, linear interpolation).
  OOM rows have no latency summary (see the footnote above); the failed
  `run.json` files keep whatever partial samples were recorded.
- The 600×400 row is the main-study run (`phase2-redmi-note-10-pro/mobileie-6ch/`, n=45).
- 1200×800: the first run (`mobileie-6ch-1200x800/`) was bimodal — first 12 images
  ~4.6 s/pass, last 3 ~1.6 s — consistent with transient system interference, not the
  model. The rerun (`mobileie-6ch-1200x800-rerun/`) is unimodal (all 15 images
  4.55–4.74 s) and is what the table reports; the contaminated run is kept for the record.
- 1800×1200 and 4032×3024 failed on-device; failed `run.json` files are kept in the
  ladder root (findings, not hidden).

## Out-of-memory results (also findings)

Both failures hit the Java-heap 256 MB growth limit, same mechanism as the Phone 2a
ladder (allocation sizes match `W*H*12` bytes per buffered image):

| Case | Outcome |
|---|---|
| 1800x1200, 5 images (x2 runs) | `OutOfMemoryError`: 25,920,016 B allocation (~5.5 MB free, growth limit 268,435,456 B) on the last image (79.png) after 4/5 completed, in both runs |
| 4032x3024 (12 MP), 1 image | `OutOfMemoryError`: 146,313,232 B allocation with ~8 MB free; 0 images processed |
| 1200x800, 15 images | success (table above) |

Notes:

1. Both failures hit the Java-heap 256 MB growth limit with allocations matching
   `W*H*12` bytes per buffered image — the same mechanism as the Phone 2a ladder. The
   device difference is where the ceiling lands: on the Phone 2a the full 15-image
   1800×1200 batch OOMed while the 5-image subset succeeded (peak PSS ~2.43 GB); on
   this device even the 5-image subset fails, with the OOM landing on the same image
   (79.png) in two independent attempts — a deterministic device-specific manifestation
   of the same harness limitation. Process PSS at failure was ~2.42 GB (mostly native
   ORT arena), while the failed allocation was on the Java heap; the two heaps fail
   independently and this device's Java heap had no headroom left at that point.
2. The second 1800×1200 run was not host-initiated: MIUI restored the app task with the
   preserved RUN intent shortly after the first failure and re-ran the identical batch,
   which failed identically. The incidental re-run is recorded because it makes the OOM
   deterministic (two attempts, same allocation, same image), strengthening the finding.
3. Same harness caveat as Phase 2a: this is a limitation of the benchmark pipeline
   (whole-image float buffering on the Java heap), not a proven limit of the phone or
   ONNX Runtime — camera-scale frames need native/Bitmap buffering, tiling, or a
   larger heap.

## Observations and limitations

1. **Speed ranking on SD732G (600×400 median):** sci-medium 43.5 ms < ruas-lol 145.2 ms
   < mobileie-6ch 440.1 ms < zero-dce 962.8 ms < lyt-net 1203.9 ms. The Phase-1 ordering
   (sci-medium fastest) holds; the two challenge models (mobileie-6ch, lyt-net) trade
   latency for much higher quality than the zero-reference baselines.
2. **lyt-net is the quality standout:** PSNR 21.59 dB / SSIM 0.812 / LPIPS 0.134 —
   +6.8 dB PSNR and +0.25 SSIM over zero-dce at ~1.25× zero-dce's latency (and ~2.7×
   mobileie-6ch's, ~27× sci-medium's) — but it is also the most memory-hungry run of
   the whole study (1429 MB PSS peak, at 600×400).
3. **Cross-device consistency is strong for the shared models.** zero-dce is 2.4×
   faster here than on Phone 2a (963 vs 2325 ms median), sci-medium 1.6× faster
   (43.5 vs 70.4 ms). Quality metrics are identical to 2 decimals (zero-dce
   14.80/0.561/0.335; sci-medium 14.78/0.525/0.339) — as expected for deterministic
   inference from the same artifacts, and verified beyond the summary stats: decoded
   output pixels are bit-identical across the two devices for spot-checked images of
   zero-dce, sci-medium, and mobileie-6ch (PNG container bytes differ due to
   platform zlib encoder versions; pixel values do not). Latency differences are the
   SoC story.
4. **No thermal events.** Every run recorded thermal `none` before and after; no
   throttling occurred during either study.
5. **CPU-only scope.** Per the phase-2 protocol this study is CPU
   (CPUExecutionProvider) only; accelerator backends were a Phase-1 question and are
   not re-run here.
6. **Single device, subset caveats.** n=15 images for the matrix and the two lowest
   ladder points; 1800×1200 and 4032×3024 are OOM findings, not measurements. The
   ladder uses synthetic upscaled inputs (latency-only, quality meaningless).
7. **Setup quirks recorded.** MIUI required installer-attribution workarounds for ADB
   install (documented in the reproduce section); the device's toybox `touch` rejects
   zero-argument calls, so all runs pass an explicit `--image-names` list (which the
   app honors as the authoritative input order).

## Reproduce

```bash
# from 07_mobile_benchmark/host
llie-bench doctor
llie-bench install <app-debug.apk>                      # MIUI: may need installer attribution (see notes)
llie-bench setup --compat-dir ../reports/compatibility --images-dir ../../04_datasets/paired/eval15/low
llie-bench matrix --models zero-dce,sci-medium,mobileie-6ch,ruas-lol,lyt-net --backends cpu \
  --image-names 1.png,111.png,146.png,179.png,22.png,23.png,493.png,547.png,55.png,665.png,669.png,748.png,778.png,780.png,79.png \
  --out ../reports/phase2-redmi-note-10-pro --timeout 1200
llie-bench report --results-dir ../reports/phase2-redmi-note-10-pro --ref-dir ../../04_datasets/paired/eval15/high

# ladder (per resolution, mobileie-6ch only)
python tools/resolution_scaling/prep_inputs.py 900x600
python tools/resolution_scaling/prep_inputs.py 1200x800
python tools/resolution_scaling/prep_inputs.py 1800x1200 --subset 1.png 22.png 55.png 111.png 79.png
python tools/resolution_scaling/prep_inputs.py 4032x3024 --subset 1.png
# push reports/compatibility/mobileie-6ch.onnx as models/mobileie-6ch-<label>.onnx,
# push reports/resolution-scaling/compat/mobileie-6ch-<label>.manifest.json,
# stage inputs via setup --images-dir reports/resolution-scaling/inputs/<label> --image-set res<label>,
# then: llie-bench benchmark --model mobileie-6ch-<label> --backend cpu --image-set res<label> --image-names <list> --out ...
```

Raw artifacts: `phase2-redmi-note-10-pro/<model>/{run.json,status.txt,outputs/*.png,metrics.csv,latency.csv}`
and `phase2-redmi-note-10-pro-resolution/mobileie-6ch-<label>/{run.json,status.txt}` (+ outputs for
the successful points; `latency-summary.csv` at the ladder root).