# Runtime decision (Phase 1, provisional)

**Status:** host-side compatibility done; on-device load/delegates pending Task 4.

## Decision table

| Candidate | Exporter available | Export result | Host CPU parity (max abs err) | Artifact size | Notes |
|---|---|---|---|---|---|
| Zero-DCE → ONNX Runtime | yes (`torch.onnx.export`, legacy path) | exported | **1.8e-07** (pass, ≤1e-3) | see export-summary.json | single-output wrapper `_ZeroDCEEnhanced`; multi-tuple model exported as one output |
| SCI medium → ONNX Runtime | yes | exported | **6.6e-07** (pass, ≤1e-3) | see export-summary.json | wrapper `_SingleOutput(index=0)`; `illu` output |
| Zero-DCE → LiteRT | no (`ai_edge_litert` not installed) | not attempted | — | — | recorded as failed candidate, not hidden |
| SCI medium → LiteRT | no | not attempted | — | — | same |

## Provisional selection

**ONNX Runtime (CPUExecutionProvider)** — both models export and pass host
parity at ≤1e-3 on the fixed seeded input (`make_parity_input`, seed 7).
LiteRT is rejected for now only because tooling is absent on this machine, not
because a conversion failed; the decision stays provisional until the Nothing
Phone (2a) load test in Task 4.

## Verification carried forward to Task 4

- [ ] Phone loads both artifacts with the selected runtime (CPU EP)
- [ ] App output vs PyTorch on a fixed eval15 image ≤1e-3 max abs error
- [ ] Available delegates on the phone recorded (CPU/GPU/NPU or "unsupported")
- [ ] If the phone cannot load a model/runtime: switch to the next host-parity
      candidate or mark model/runtime unsupported

Artifacts: `reports/compatibility/*.onnx`, `reports/compatibility/export-summary.json`.
