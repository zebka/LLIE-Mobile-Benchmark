# LLIE Mobile Deployment Benchmark

Open, reproducible tooling to measure the quality and on-device cost of
low-light image enhancement (LLIE) models on real phones — so conclusions
are not limited to parameter counts or server-side runs.

## Phase 1: paper models on one phone

- Goal: run the survey shortlist on a real phone and check deployment feasibility.
- Device: Nothing Phone (2a). Exact Android version and build are recorded at connect time.
- Input: fixed photos, targeting full mobile resolution (12 MP stress test).
- The Android app runs the model on the phone itself and times it in-process.
- The host tool moves models/data over ADB, starts a run, and collects the
  report. ADB never sits inside the per-image timing loop.
- CPU and each supported GPU/NPU-accelerated path are measured separately.
- Models ship in a standard package with a manifest (input/output spec,
  numeric precision, pre/post-processing). Format and runtime were picked
  by a compatibility gate over the candidate models and are versioned.

Phase 1 is a case study; on its own it generalizes to no other phone and
ranks nothing publicly.

## Phase 2: public benchmark

- Official runs on three reference tiers; per-device, per-backend results.
- Open, reproducible Android runner + ADB controller for other researchers.
- Overall score is "quality within budget" under pre-announced execution limits.

## Reports and metrics

Each raw report (per model and device) holds image quality, median/p95
latency, peak memory, real artifact size, weight precision, and sustained-run
degradation. Official energy numbers require validated power instrumentation
on reference devices.

In the public phase, pre-announced execution gates pass first; qualifying
models then score on quality. Raw numbers, Pareto fronts, and over-budget
results are published too. No-reference metrics and human ratings are
reported separately from the main score.

## Host tool (`host/`)

Step-by-step run guide: [`QUICKSTART.md`](QUICKSTART.md) (4 commands:
doctor/install, setup, matrix, report). Summary:

```bash
cd host
pip install -e ".[test]"      # and for quality metrics: pip install -e ".[metrics]"
llie-bench doctor             # check ADB (never prints the serial)
llie-bench install app-debug.apk
llie-bench setup --compat-dir ../reports/compatibility --images-dir ../../04_datasets/paired/eval15/low
llie-bench matrix --out ../reports/my-study     # every model x backend, sequential
llie-bench report --results-dir ../reports/my-study --ref-dir ../../04_datasets/paired/eval15/high
python -m pytest -q ../tools/compatibility   # tests (host + compatibility), no phone needed
```

Low-level commands (`run`/`collect`/`push`/`metrics`) remain for special
cases; normal runs only need `setup`/`benchmark`/`matrix`/`report`.

## Status

Phase-1 summary in `PHASE_1.md`, frozen technical design in `design.md`.

**Phase 1 done (2026-09-24):**

- Task 2: `protocol/*.schema.json` contracts + `host/src/llie_bench/report.py` (12 tests green).
- Task 3: ONNX compatibility gate for both models (zero-dce and SCI-medium)
  with parity under `1e-3`; final runtime: ONNX Runtime 1.19.2 / CPU
  (`reports/runtime-decision.md`, confirmed on-device).
- Task 4: Android project skeleton, in-app timing, green CI, APK installed
  on the Nothing Phone (2a).
- Task 5: host ADB controller (14 tests green; serial never exposed).
- Task 6: host quality metrics (PSNR/SSIM/LPIPS, RGBA→RGB, shape-mismatch
  rejection; 39 tests green across host+compatibility).
- Task 7: real-phone study — both models ran with `success=true` and valid
  schemas; outputs, `run.json`, `metrics.csv`, `latency.csv` under
  `reports/phase1-results/`; write-up in `reports/phase1-nothing-phone-2a.md`.

Implementation notes:

- Device PNG outputs are RGBA; metrics drop alpha before comparing to RGB refs.
- Model input layout is NCHW; the HWC→CHW conversion lives in
  `SelectedRuntimeEngine` (before the fix, host/device diff was ~60).
- NNAPI/XNNPACK ran separately on the same phone: no effective speedup,
  byte-identical outputs to CPU (details: `reports/phase1-accelerators.md`).
- Single-device result, not a public ranking.
