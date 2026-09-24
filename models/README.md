# Model artifacts

Phase 1 runs the archived checkpoints through the compatibility gate and ships
only the exported artifacts selected there. Source checkpoints stay read-only
in `03_models/thirdparty-weights/`.

| model_id | source checkpoint | exported artifact | precision |
|---|---|---|---|
| zero-dce | `03_models/thirdparty-weights/ZeroDCE-snapshots/Epoch99.pth` | `reports/compatibility/zero-dce.onnx` | float32 |
| sci-medium | `03_models/thirdparty-weights/SCI-weights/medium.pt` | `reports/compatibility/sci-medium.onnx` | float32 |
| mobileie-6ch | MobileIE-6Ch `result/model_best.pt` (Apache-2.0, [upstream](https://github.com/w-xb/MobileIE-6Ch)) | `reports/compatibility/mobileie-6ch.onnx` | float32 |

Manifests live next to each artifact at package time
(`reports/compatibility/*.manifest.json`), following
`protocol/model-manifest.schema.json`. On-device file bytes, parameter count,
and weight precision are reported as distinct fields in every run result.
