# Resolution scaling: MobileIE-6Ch latency on device

Purpose: check how the on-device latency numbers scale with input resolution, so the
600x400 results are not read as phone-camera-scale numbers.

## Method

- Same on-device protocol as the main study: batch=1, warmup=5, measured=3 per image,
  ORT 1.19.2, float32, default threads, CPU backend, `elapsedRealtimeNanos` timing from
  tensor packing to output unpacking (decode/resize outside).
- Inputs: the 15 `eval15/low` images LANCZOS-upscaled to each target resolution.
  Latency only — no quality metrics are computed at scale, and the upscaled inputs are
  synthetic (they exist to change pixel count, not to represent real high-res scenes).
- One dynamic-axes ONNX artifact (`reports/compatibility/mobileie-6ch.onnx`, 101,471 B)
  pushed once per resolution as `models/mobileie-6ch-<label>.onnx` with a manifest whose
  input/output are the target WxH (`reports/resolution-scaling/compat/`).

## Results (CPU backend)

| Resolution | MP | Images | median [IQR] ms | p90 ms | ms/MP | peak PSS MB |
|---|---|---|---|---|---|---|
| 600x400   | 0.24 | 15 | 289 [282-323]    | 361   | 1205 | 428  |
| 900x600   | 0.54 | 15 | 921 [818-931]    | 940   | 1706 | 763  |
| 1200x800  | 0.96 | 15 | 2234 [2212-2462] | 2492  | 2328 | 1175 |
| 1800x1200 | 2.16 | 5  | 5560 [5557-5604] | 5650  | 2574 | 2430 |

- 9x the pixels costs >19x the latency; per-MP cost roughly doubles (1205 -> 2574 ms),
  i.e. scaling is super-linear, not constant-throughput.
- `latency-summary.csv` in this directory carries the machine-readable table.
- 600x400 row is the main study run (`reports/ntire2026-mobileie/`, n=45).
- 1200x800: the first run (`mobileie-6ch-1200x800/`) was bimodal — first 7 images ~6.7 s
  pass, remainder ~2.1-2.3 s — consistent with transient system interference, not the
  model. The rerun (`mobileie-6ch-1200x800-rerun/`) is unimodal and is what the table
  reports; the contaminated run is kept for the record.
- 1800x1200 uses a 5-image subset (`1,22,55,111,79`, n=15 samples) because the full
  15-image batch OOMs (below).

## Out-of-memory results (also findings)

Full batches and a single 12 MP image fail on the Java-heap 256 MB growth limit; failed
`run.json` files are kept in this directory:

| Case | Outcome |
|---|---|
| 1500x1000, 15 images (x2 runs) | `OutOfMemoryError`: 18,000,016 B allocation, heap at ~255/256 MB |
| 1800x1200, 15 images (x2 runs) | `OutOfMemoryError`: 25,920,016 B allocation |
| 4032x3024 (12 MP), 1 image | `OutOfMemoryError`: 146,313,232 B allocation with ~100 MB free; 0 images processed |
| 1800x1200, 5 images | success (table above) |

Allocation sizes match `W*H*12` bytes per buffered image, so the harness buffers
full-resolution float images on the Java heap; 15 images fit under 256 MB up to about
1.2-1.4 MP. This is a limitation of this harness pipeline (naive whole-image Java-heap
buffering), not a proven limit of the phone or ONNX Runtime: camera-scale frames need
native/Bitmap buffering, tiling, or a larger heap.

## Caveats

- LANCZOS-upscaled inputs: valid for latency scaling, meaningless for quality.
- Peak PSS is the absolute app+runtime process peak (no empty-app baseline).
- Thermal state not controlled/recorded for these runs; energy not measured.
- One device, one model; 1800x1200 point uses a 5-image subset (n=15 samples).
- First 1200x800 run contaminated (see above); rerun reported.
