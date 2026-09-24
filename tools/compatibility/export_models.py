"""Attempt every Phase 1 export candidate and record successes/failures.

Writes artifacts and a JSON summary under `reports/compatibility/` only;
archived checkpoints are never modified.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch


class _SingleOutput(torch.nn.Module):
    """Wrap a multi-output model for export so the artifact has one tensor."""

    def __init__(self, model, index: int):
        super().__init__()
        self.model = model
        self.index = index

    def forward(self, x):
        out = self.model(x)
        if isinstance(out, (tuple, list)):
            return out[self.index]
        return out


class _ZeroDCEEnhanced(torch.nn.Module):
    """Zero-DCE returns (enhance1, enhanced, r); the benchmark uses `enhanced`."""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x):
        _, enhanced, _ = self.model(x)
        return enhanced

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from model_wrappers import (  # noqa: E402
    load_sci_medium,
    load_zero_dce,
    make_parity_input,
    sci_reference_output,
    zero_dce_reference_output,
)

OUT_DIR = ROOT / "reports" / "compatibility"
SUMMARY_PATH = OUT_DIR / "export-summary.json"


def try_onnx_export(name: str, model, input_tensor) -> dict:
    record: dict = {"candidate": f"{name}:onnx", "status": "failed", "error": "", "artifact": "", "seconds": 0.0}
    started = time.time()
    try:
        import onnx  # noqa: F401
        import onnxruntime as ort  # noqa: F401
    except ImportError as exc:
        record["error"] = f"onnx tooling not installed: {exc}"
        record["seconds"] = time.time() - started
        return record
    try:
        artifact = OUT_DIR / f"{name}.onnx"
        torch.onnx.export(
            model,
            input_tensor,
            str(artifact),
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={
                "input": {0: "batch", 2: "height", 3: "width"},
                "output": {0: "batch", 2: "height", 3: "width"},
            },
            dynamo=False,
        )
        record["artifact"] = str(artifact.relative_to(ROOT))
        record["status"] = "exported"
        record["artifact_bytes"] = artifact.stat().st_size
    except Exception as exc:  # export failures are data, not crashes
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["seconds"] = round(time.time() - started, 2)
    return record


def try_litert_export(name: str, model, input_tensor) -> dict:
    record: dict = {"candidate": f"{name}:litert", "status": "failed", "error": "", "artifact": "", "seconds": 0.0}
    started = time.time()
    try:
        import ai_edge_litert  # noqa: F401
        import tensorflow as tf  # noqa: F401
    except ImportError as exc:
        record["error"] = f"LiteRT tooling not installed: {exc}"
        record["seconds"] = time.time() - started
        return record
    try:
        buffer = io_bytes = None  # noqa: F841
        onnx_path = OUT_DIR / f"{name}.onnx"
        if not onnx_path.is_file():
            raise RuntimeError("LiteRT path currently requires the ONNX artifact from torch.onnx.export")
        from onnx2tf import convert  # type: ignore

        convert(
            input_onnx_file_path=str(onnx_path),
            output_folder_path=str(OUT_DIR / f"{name}_litert"),
            non_verbose=True,
        )
        record["status"] = "exported"
        record["artifact"] = str((OUT_DIR / f"{name}_litert").relative_to(ROOT))
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["seconds"] = round(time.time() - started, 2)
    return record


def parity_vs_torch(name: str, model, artifact_path: Path, reference, input_tensor) -> dict:
    record: dict = {"candidate": f"{name}:ort-parity", "status": "failed", "error": "", "max_abs_err": None}
    try:
        import onnxruntime as ort
        import numpy as np

        session = ort.InferenceSession(str(artifact_path), providers=["CPUExecutionProvider"])
        x = input_tensor.numpy()
        output = session.run(None, {"input": x})[0]
        if output.ndim == 4 and output.shape[1] not in (1, 3, 8, 24):
            output = output.transpose(0, 3, 1, 2)
        ref = reference.detach().numpy()
        max_abs_err = float(np.abs(ref - output).max())
        record["max_abs_err"] = max_abs_err
        record["status"] = "passed" if max_abs_err <= 1e-3 else "parity_failed"
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


STUDY_WIDTH = 600
STUDY_HEIGHT = 400
STUDY_INPUT_SIZE = (3, STUDY_HEIGHT, STUDY_WIDTH)


def write_manifest(name: str) -> dict:
    """Write the schema-shaped manifest next to the exported artifact."""
    from jsonschema import validate

    manifest = {
        "model_id": name,
        "artifact": f"{name}.onnx",
        "precision": "float32",
        "input": {"width": STUDY_WIDTH, "height": STUDY_HEIGHT},
        "output": {"width": STUDY_WIDTH, "height": STUDY_HEIGHT},
        "preprocessing": {"steps": ["rgb", "normalize_0_1", "nchw"]},
        "channel_order": "RGB",
        "input_range": [0.0, 1.0],
        "tensor_layout": "NCHW",
        "output_range": [0.0, 1.0],
        "tiling": {"tile_width": 512, "tile_height": 512, "overlap": 32},
    }
    schema = json.loads((ROOT / "protocol" / "model-manifest.schema.json").read_text(encoding="utf-8"))
    validate(instance=manifest, schema=schema)
    path = OUT_DIR / f"{name}.manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"candidate": f"{name}:manifest", "status": "written", "error": "", "artifact": str(path.relative_to(ROOT))}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict = {"candidates": [], "selected_runtime": None, "study_input_size": list(STUDY_INPUT_SIZE)}

    zero_dce = load_zero_dce()
    sci = load_sci_medium()
    x = make_parity_input(size=STUDY_INPUT_SIZE)

    for name, model, reference, wrapper in (
        ("zero-dce", zero_dce, zero_dce_reference_output(zero_dce, x), _ZeroDCEEnhanced(zero_dce)),
        ("sci-medium", sci, sci_reference_output(sci, x), _SingleOutput(sci, 1)),
    ):
        onnx_record = try_onnx_export(name, wrapper, x)
        summary["candidates"].append(onnx_record)
        if onnx_record["status"] == "exported":
            summary["candidates"].append(
                parity_vs_torch(name, model, OUT_DIR / f"{name}.onnx", reference, x)
            )
            try:
                summary["candidates"].append(write_manifest(name))
            except Exception as exc:
                summary["candidates"].append(
                    {"candidate": f"{name}:manifest", "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
                )
        summary["candidates"].append(try_litert_export(name, model, x))

    exported = [c for c in summary["candidates"] if c["candidate"].endswith(":ort-parity") and c["status"] == "passed"]
    if exported:
        summary["selected_runtime"] = {
            "name": "onnxruntime",
            "basis": f"{len(exported)}/2 models passed host parity at <=1e-3",
        }
    else:
        summary["selected_runtime"] = None

    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for record in summary["candidates"]:
        status = record["status"]
        extra = f" err={record['max_abs_err']}" if record.get("max_abs_err") is not None else ""
        err = f" ({record['error']})" if record.get("error") else ""
        print(f"[{status:>13}] {record['candidate']}{extra}{err}")
    print("summary:", SUMMARY_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())