"""Contract tests for the Phase 1 model manifest and run-result schemas.

TDD: these tests FAIL until protocol/*.schema.json and
src/llie_bench/report.py exist.
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA = ROOT / "protocol" / "model-manifest.schema.json"
RESULT_SCHEMA = ROOT / "protocol" / "run-result.schema.json"


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


VALID_MANIFEST = {
    "model_id": "zero-dce",
    "artifact": "zero-dce.onnx",
    "precision": "float32",
    "input": {"width": 400, "height": 600},
    "output": {"width": 400, "height": 600},
    "preprocessing": {"steps": ["normalize_0_1"]},
    "channel_order": "RGB",
    "input_range": [0.0, 1.0],
    "tensor_layout": "NCHW",
    "output_range": [0.0, 1.0],
    "tiling": {"tile_width": 512, "tile_height": 512, "overlap": 32},
}

VALID_RESULT = {
    "model_id": "zero-dce",
    "artifact_sha256": "0" * 64,
    "device": {
        "model": "Nothing Phone (2a)",
        "android_release": "14",
        "android_sdk": 34,
        "build_fingerprint": "Nothing/2a/2a:14/unknown",
        "soc": "Dimensity 7200 Pro",
    },
    "runtime": {"name": "onnxruntime", "version": "1.0.0"},
    "backend": "cpu",
    "precision": "float32",
    "image_ids": ["1.png"],
    "warmup_count": 5,
    "load_time_ns": 1000,
    "images": [
        {"image_id": "1.png", "model_ns": [2000, 2100], "e2e_ns": [3000, 3100]}
    ],
    "pss": {"samples_mb": [10.0], "peak_mb": 10.0},
    "thermal": {"before": "none", "after": "none"},
    "output_paths": ["outputs/1.png"],
    "success": True,
}


def test_manifest_schema_accepts_valid_manifest():
    validate(instance=VALID_MANIFEST, schema=load_schema(MANIFEST_SCHEMA))


def test_manifest_requires_input_and_output_fields():
    with pytest.raises(ValidationError):
        validate(
            instance={"model_id": "demo", "artifact": "demo.onnx"},
            schema=load_schema(MANIFEST_SCHEMA),
        )


@pytest.mark.parametrize("field", ["model_id", "artifact", "input", "output", "precision", "preprocessing"])
def test_manifest_requires_core_fields(field):
    payload = copy.deepcopy(VALID_MANIFEST)
    del payload[field]
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=load_schema(MANIFEST_SCHEMA))


def test_result_schema_accepts_valid_result():
    validate(instance=VALID_RESULT, schema=load_schema(RESULT_SCHEMA))


@pytest.mark.parametrize("backend", ["cpu", "gpu", "npu", "nnapi", "xnnpack"])
def test_result_schema_accepts_each_backend(backend):
    payload = copy.deepcopy(VALID_RESULT)
    payload["backend"] = backend
    validate(instance=payload, schema=load_schema(RESULT_SCHEMA))


def test_result_schema_rejects_unknown_backend():
    payload = copy.deepcopy(VALID_RESULT)
    payload["backend"] = "tpu"
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=load_schema(RESULT_SCHEMA))


def test_result_rejects_missing_images():
    payload = copy.deepcopy(VALID_RESULT)
    del payload["images"]
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=load_schema(RESULT_SCHEMA))


def test_result_requires_failure_reason_on_failure():
    payload = copy.deepcopy(VALID_RESULT)
    payload["success"] = False
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=load_schema(RESULT_SCHEMA))


def test_report_module_validates_manifest_and_result():
    from llie_bench.report import validate_manifest, validate_result

    validate_manifest(copy.deepcopy(VALID_MANIFEST))
    validate_result(copy.deepcopy(VALID_RESULT))
    with pytest.raises(ValidationError):
        validate_manifest({"model_id": "demo"})
    bad = copy.deepcopy(VALID_RESULT)
    del bad["images"]
    with pytest.raises(ValidationError):
        validate_result(bad)
