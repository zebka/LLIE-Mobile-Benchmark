# Runtime decision (Phase 1)

**Status:** confirmed on-device. ONNX Runtime 1.19.2 / CPUExecutionProvider loaded both artifacts on the Nothing Phone (2a) and produced schema-valid runs with 15/15 outputs each.

## Decision table

| Candidate | Exporter available | Export result | Host CPU parity (max abs err) | Artifact size | On-device load | Notes |
|---|---|---|---|---|---|---|
| Zero-DCE → ONNX Runtime | yes (`torch.onnx.export`, legacy path) | exported | **1.8e-07** (pass, ≤1e-3) | 324,671 B | **success** | single-output wrapper `_ZeroDCEEnhanced`; multi-tuple model exported as one output |
| SCI medium → ONNX Runtime | yes | exported | **6.6e-07** (pass, ≤1e-3) | 3,560 B | **success** | wrapper `_SingleOutput(index=0)`; `illu` output |
| Zero-DCE → LiteRT | no (`ai_edge_litert` not installed) | not attempted | — | — | not tested | recorded as failed candidate, not hidden |
| SCI medium → LiteRT | no | not attempted | — | — | not tested | same |

## Selection

**ONNX Runtime (CPUExecutionProvider)** — both models export, pass host parity at ≤1e-3 on the fixed seeded input, and load/run on the Nothing Phone (2a) with schema-valid results. LiteRT remains untested (tooling absent on the host machine); it is not claimed as unsupported by the phone itself.

## On-device verification (2026-09-24)

- [x] Phone loads both artifacts with ONNX Runtime 1.19.2 (CPU EP)
- [x] App output matches host ONNX Runtime output on eval15 (device/host mean abs diff after HWC→CHW fix: ~0; before fix: ~60)
- [x] Available backend recorded as `cpu`; NNAPI/GPU/NPU not exercised in Phase 1
- [x] Both runs `success=true`, `failure_reason` empty, 15/15 output paths present

Artifacts: `reports/compatibility/*.onnx`, `reports/compatibility/export-summary.json`, `reports/phase1-results/`.
