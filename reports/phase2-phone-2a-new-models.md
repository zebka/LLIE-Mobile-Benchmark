# Phase-2 supplement: new models on Nothing Phone (2a)

**Status:** complete (2026-09-25). Extends the Phase-2 CPU study to the two newly
exported models (ruas-lol, lyt-net) on the same device; companion to
`phase1-nothing-phone-2a.md` and `phase2-redmi-note-10-pro.md`.

## Device profile

| Field | Value |
|---|---|
| Model | Nothing Phone (2a) (A142) |
| Android | 16 (API 36) |
| SoC | MT6886 |
| Build | `Nothing/Pacman/Pacman:16/BP2A.250605.031.A3/2608130941:user/release-keys` |
| Runtime | ONNX Runtime 1.19.2, CPUExecutionProvider |
| Precision | float32 |
| Thermal (before/after) | none / none (both runs) |

No ADB serial appears in this report.

## Protocol (frozen)

- batch = 1, warm-up = 5, measured passes = 3 per image
- 15 paired images from `04_datasets/paired/eval15/low` at 600×400 (study shape)
- On-device monotonic clock (`SystemClock.elapsedRealtimeNanos`); ADB only starts/polls the batch
- Quality metrics computed on host after inference, outside any timing loop
- CPU backend only (CPUExecutionProvider); accelerator backends are out of scope for Phase 2

## Model artifacts

| Model | Artifact bytes | Parameters | Precision | SHA-256 (truncated) |
|---|---:|---:|---|---|
| ruas-lol | 44,969 | 1,161 | float32 | `15b9443756258426...` |
| lyt-net | 230,030 | 44,923 | float32 | `610d6515f6c9cc6a...` |

Same ONNX artifacts as the Redmi Note 10 Pro study (`reports/compatibility/`,
parity passed ≤1e-3 against reference implementations at export time).

## Runtime results (CPU, Nothing Phone 2a)

Both runs: `success=true`, schema-valid (`protocol/run-result.schema.json`), 15/15 outputs saved.

### Latency (all 45 timed samples per model: 15 images × 3 passes)

| Model | Load (ms) | Model mean (ms) | Model median (ms) | Model p95 (ms) | E2E mean (ms) | E2E median (ms) | E2E p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| ruas-lol | 154.77 | 123.98 | 122.44 | 128.98 | 123.99 | 122.45 | 129.00 |
| lyt-net | 158.28 | 892.95 | 908.91 | 928.80 | 892.96 | 908.92 | 928.81 |

**Percentile convention:** median, p95, mean, and SD are computed on the pooled
per-sample `model_ns` values (all timed samples, all images × all passes, n=45)
with `numpy.percentile` **linear interpolation** and SD with ddof=1 — the same
convention as the corrected Redmi Note 10 Pro report; every cell is reproducible
from the committed `run.json` files.

### Memory (PSS peak)

| Model | PSS peak (MB) | Samples |
|---|---:|---:|
| ruas-lol | 270.5 | 36 |
| lyt-net | 1517.5 | 190 |

### Quality on paired eval15 (n=15, mean ± std)

| Model | PSNR (dB) | SSIM | LPIPS (alex) |
|---|---|---|---|
| ruas-lol | 16.30 ± 4.35 | 0.484 ± 0.105 | 0.359 ± 0.126 |
| lyt-net | 21.59 ± 4.92 | 0.812 ± 0.096 | 0.134 ± 0.058 |

Per-image rows: `phase2-phone-2a/<model>/metrics.csv`
(columns `image_id,status,psnr,ssim,lpips`). Latency rows:
`phase2-phone-2a/latency.csv`; combo summary:
`phase2-phone-2a/latency-summary.csv`; aggregate:
`phase2-phone-2a/metrics-summary.json`.

## Observations and limitations

1. **ruas-lol is the fastest non-trivial model measured on this device at
   600×400** (median 122.4 ms; only sci-medium at ~70 ms is faster). It runs at
   roughly half zero-dce's latency (2325 ms median on the same device,
   `phase1-nothing-phone-2a.md`) with comparable peak memory (271 vs 614 MB).
2. **lyt-net trades latency and memory for quality**, as on the Redmi Note 10
   Pro: median 908.9 ms (~7.4× ruas-lol) and the highest peak PSS of any run in
   this study (1517 MB), but PSNR 21.59 dB / SSIM 0.812 / LPIPS 0.134 — about
   +6.8 dB PSNR and +0.25 SSIM over the zero-reference baselines.
3. **Cross-device consistency.** Quality metrics are identical to the Redmi
   Note 10 Pro study to 2 decimals (ruas-lol 16.30/0.484/0.359; lyt-net
   21.59/0.812/0.134), as expected for deterministic inference from the same
   artifacts. Latency differs by SoC: ruas-lol is ~1.2× faster on the Phone 2a
   (122.4 vs 145.2 ms median) and lyt-net ~1.3× faster (908.9 vs 1203.9 ms).
4. **No thermal events.** Both runs recorded thermal `none` before and after
   (system thermal status 0); no throttling occurred.
5. **CPU-only scope.** Per the Phase-2 protocol this study is CPU
   (CPUExecutionProvider) only; accelerator backends were a Phase-1 question.
6. **Two models, not five.** zero-dce, sci-medium, and mobileie-6ch on this
   device are reported in the Phase-1 case studies; the numbers above cover
   only the two new models so the tables stay directly comparable to
   `phase2-redmi-note-10-pro.md` rows for the same models.
7. **Setup quirks recorded.** The device's toybox `touch` rejects a
   zero-argument call (same harness quirk documented in the Redmi report), so
   runs pass an explicit `--image-names` list. The host tool's default model
   list also predates these two models, so the artifacts were pushed with the
   low-level `push` path (same layout as `setup`: `models/` + `manifests/`);
   the runs themselves used the standard benchmark flow and are schema-valid.

## Reproduce

```bash
# from 07_mobile_benchmark/host
llie-bench doctor
llie-bench setup --compat-dir ../reports/compatibility --images-dir ../../04_datasets/paired/eval15/low
# ruas-lol/lyt-net are not yet in the tool's default model list; push them explicitly
adb push ../reports/compatibility/ruas-lol.onnx <remote-models-dir>/ruas-lol.onnx
adb push ../reports/compatibility/ruas-lol.manifest.json <remote-manifests-dir>/ruas-lol.manifest.json
adb push ../reports/compatibility/lyt-net.onnx <remote-models-dir>/lyt-net.onnx
adb push ../reports/compatibility/lyt-net.manifest.json <remote-manifests-dir>/lyt-net.manifest.json
llie-bench benchmark --model ruas-lol --backend cpu --image-names 1.png,111.png,146.png,179.png,22.png,23.png,493.png,547.png,55.png,665.png,669.png,748.png,778.png,780.png,79.png --out ../reports/phase2-phone-2a/ruas-lol --timeout 1200
llie-bench benchmark --model lyt-net   --backend cpu --image-names 1.png,111.png,146.png,179.png,22.png,23.png,493.png,547.png,55.png,665.png,669.png,748.png,778.png,780.png,79.png --out ../reports/phase2-phone-2a/lyt-net --timeout 1200
llie-bench report --results-dir ../reports/phase2-phone-2a --ref-dir ../../04_datasets/paired/eval15/high
```

Raw artifacts: `phase2-phone-2a/<model>/{run.json,status.txt,outputs/*.png,metrics.csv,latency.csv}`.
