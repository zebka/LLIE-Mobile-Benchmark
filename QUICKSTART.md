# QUICKSTART — full benchmark in 4 commands

All operational knowledge (push order, 666 placeholder files, force-stop,
status polling, pull-between-runs) lives inside the tool. Just run these
4 commands in order.

## 0. Prerequisites

- One phone with USB debugging enabled, connected over USB
- Python 3.11+ and `adb` on PATH
- APK from this repo's CI (`Actions → android-ci → app-debug`)

## 1. Install the host tool

```bash
cd 07_mobile_benchmark/host
pip install -e ".[test]"
pip install -e ".[metrics]"   # only for PSNR/SSIM/LPIPS (downloads alex weights once)
```

## 2. Check connection + install the app

```bash
llie-bench doctor                          # must print the phone model, never the serial
llie-bench install /path/to/app-debug.apk
```

## 3. Stage the phone (models + images, one command)

```bash
llie-bench setup --compat-dir ../reports/compatibility --images-dir ../04_datasets/paired/eval15/low
```

Expected output: `setup done: 2 models, 15 images (set eval15)`

## 4. Run the full matrix (model x backend)

```bash
llie-bench matrix --out ../reports/my-study
```

- By default runs `zero-dce,sci-medium` x `cpu,nnapi,xnnpack` **sequentially**
  (each zero-dce combo takes ~5 min; full matrix ~15 min).
- Subset: `llie-bench matrix --models sci-medium --backends nnapi --out ...`
- Single run: `llie-bench benchmark --model zero-dce --backend xnnpack --out ...`
- Each combo lands in `my-study/<model>[-<backend>]/{run.json,status.txt,outputs/*.png}`.

## 5. Build the report

```bash
llie-bench report --results-dir ../reports/my-study --ref-dir ../04_datasets/paired/eval15/high
```

Produces: `latency.csv`, `latency-summary.csv`, per-combo `metrics.csv`,
and `metrics-summary.json`. Omit `--ref-dir` for latency/memory only.

## Conventions (kept for you, nothing to memorize)

- Timing happens only on the phone; ADB never enters the timing loop.
- Every `run.json` is validated against `protocol/run-result.schema.json`;
  a failed run raises an error instead of silently passing.
- The tool pre-creates shell-owned placeholder files, force-stops the app
  between runs, polls the status until `done`/`failed`, and pulls immediately
  (shared on-device output dirs never mix models).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `device unauthorized` | USB prompt not accepted | Tap Allow on the phone, run `doctor` again |
| `no device found` | cable/driver | Swap cable; `adb devices` must show `device` |
| `timed out waiting for ...status` | app stuck (`already running`) | It force-stops by itself; just re-run the same command |
| `run reported success=false` | on-device error (e.g. OOM) | Check `adb shell logcat -d \| grep llie` |
| `Permission denied` on manual pull | app-owned files without priming | Use `benchmark`/`matrix` (priming is automatic); don't pull by hand |
| LPIPS won't download | offline | Drop `--ref-dir` (latency only), re-run `report` later |

Tests (no phone): `python -m pytest host/tests tools/compatibility -q`
