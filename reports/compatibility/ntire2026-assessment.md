# NTIRE 2026 candidate assessment (host-side compatibility)

Date: 2026-09-24. Scope: feasibility check for running challenge models
through this repo's compatibility gate (PyTorch reference → ONNX export →
ORT parity ≤ 1e-3). **No phone was attached, so no on-device run was made.**

## Sources (checked 2026-09-24)

- Challenge report: arXiv:2605.02212 (methods + results, team contacts).
- HIT-LLIE / MobileIE-6Ch: https://github.com/w-xb/MobileIE-6Ch —
  inference code + `result/model_best.pt` checkpoint, **Apache-2.0**.
- CVPR TCD: https://github.com/Mdraqibkhan/NTIRE2026-ELLIE-CVPR-TCD —
  `run.py` + `greya_scalequery_reduced.py` + `model.pth`. **No license
  file in the repo** (evaluation use only; do not redistribute weights).
- S3 / Norm U-Net: technical report only (arXiv:2604.11071); **no public
  code repo found**.
- MiVideo, Bustaaa, SYSU-FVL: methods documented in the challenge
  report; **no official public repos found**.

## Parameter-count correction

Both released checkpoints show the same reporting mix-up: the widely
circulated "parameter counts" equal the **checkpoint file size in bytes**,
not the parameter count. Verified by loading each checkpoint into the
released architecture and counting the live model (key sets match exactly,
missing = 0, extra = 0):

| Team | Reported params | Checkpoint bytes | Measured live params | Dtype |
|---|---|---:|---:|---|
| HIT-LLIE (MobileIE-6Ch) | 101,922 | 101,922 | **23,882** | fp32 |
| CVPR TCD | 557,618 | 557,618 | **252,341** | fp16 |

The correction favors efficiency (both models are smaller than reported),
but the survey's Pareto figure should use measured counts.

## PyTorch reference (CPU, eval15 `1.png` at 600×400)

- MobileIE-6Ch: output (1, 3, 400, 600), finite, range [0.106, 1.126],
  deterministic; ~0.10 s/run on host CPU. Output slightly exceeds 1.0,
  so the benchmark wrapper clamps to [0, 1] (`ntire2026.py`).
- CVPR TCD: output (1, 3, 400, 600), finite, normalized range
  [-0.926, 0.996], deterministic; ~0.6–0.7 s/run on host CPU.
  The released `run.py` feeds the same normalized tensor to **both**
  branches (`model(inp, inp)`); the grey branch takes 3 channels (not
  grayscale), so this is the intended path, and the wrapper reproduces
  it exactly (covered by `test_tcd_wrapper_matches_reference_math`).

## ONNX export + ORT parity

- MobileIE-6Ch: **exported** with the repo's standard legacy path
  (dynamic batch/height/width) in 0.3 s; artifact 101,471 bytes;
  ORT CPU parity **1.13e-06 ≤ 1e-3 — PASS**. Ready for a phone run.
- CVPR TCD: **blocked**. Legacy `torch.onnx.export` fails in the
  FFT PhaseTrans block with `RuntimeError: Unknown number type:
  complex`. The torch.export-based path needs `onnxscript`, which is
  not installed in this environment (no new packages were added).
  Unblocks: install onnxscript and retry dynamo export, or replace the
  FFT phase transfer with an export-safe equivalent and re-verify parity.

## Rank-table note

The challenge report has two tables: teams with technical reports and
the full final-testing table. Ranks differ between them (e.g. TCD 2nd →
3rd, S3 3rd → 4th, MobileIE 7th → 9th). Cite which table each rank comes
from.

## Next step (needs a phone on ADB)

1. Export MobileIE-6Ch ONNX into `reports/compatibility/` + manifest,
   following `tools/compatibility/export_models.py` conventions.
2. `llie-bench setup`, then `llie-bench matrix --models mobileie-6ch
   --backends cpu,nnapi,xnnpack --out reports/ntire2026-mobileie`.
3. `llie-bench report` with the eval15 refs; extend the survey's
   deployment-cost section with the measured numbers.

## On-device results (Nothing Phone 2a, ORT 1.19.2, 2026-09-25)

Done — `reports/ntire2026-mobileie/` (15/15 images each, schema-valid):

| Backend | Load (ms) | Median (ms) | p95 (ms) | PSS peak (MB) | PSNR | SSIM | LPIPS |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| cpu | 88.2 | 289.2 | 363.8 | 428.3 | 17.91 | 0.717 | 0.359 |
| nnapi | 143.4 | 322.6 | 369.9 | 433.2 | 17.91 | 0.717 | 0.359 |
| xnnpack | 104.6 | 327.6 | 375.5 | 425.9 | 17.91 | 0.717 | 0.359 |

vs baselines on the same phone/eval15: ~8× faster than zero-dce
(2325 ms) at +3.1 dB PSNR / +0.16 SSIM; ~4× slower than sci-medium
(70 ms) at +3.1 dB / +0.19 SSIM — with only 23,882 parameters.
No effective EP acceleration (same CPU-level pattern as the baselines).

## Infrastructure root cause found during these runs

Every post-reinstall run recorded exactly "leading failures + 1 success"
with no error trace. Cause: shell-created `outputs*` dirs with mode 770
made the app's `savePng` throw on the first success; the outer catch
stored it in `runFailureReason`, but `success` stayed true (no failure
*entries*) so `ResultWriter` dropped `failure_reason` and wrote "done".
Fixed in `flow.prime_outputs` (chmod 777 the outputs dir itself, not
just the files). Follow-up: surface save errors honestly in the app
instead of masking them behind success=true.
