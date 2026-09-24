from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import Any

from jsonschema import validate

CSV_HEADER = [
    "model_id",
    "backend",
    "image_id",
    "median_model_ns",
    "p95_model_ns",
    "median_e2e_ns",
    "p95_e2e_ns",
    "success",
    "failure_reason",
]


def _protocol_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "protocol"
        if (candidate / "model-manifest.schema.json").is_file() and (
            candidate / "run-result.schema.json"
        ).is_file():
            return candidate
    raise FileNotFoundError(
        "protocol schemas not found above " + str(Path(__file__).resolve())
    )


def _schema(name: str) -> dict[str, Any]:
    return json.loads((_protocol_dir() / name).read_text(encoding="utf-8"))


def validate_manifest(payload: dict[str, Any]) -> None:
    validate(instance=payload, schema=_schema("model-manifest.schema.json"))


def validate_result(payload: dict[str, Any]) -> None:
    validate(instance=payload, schema=_schema("run-result.schema.json"))


def _median(samples: list[int]) -> float:
    ordered = sorted(samples)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _p95_nearest_rank(samples: list[int]) -> int:
    ordered = sorted(samples)
    rank = math.ceil(0.95 * len(ordered))
    return ordered[rank - 1]


def results_to_csv(results: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for result in results:
        validate_result(result)
        failure = result.get("failure_reason", "")
        for image in result["images"]:
            writer.writerow(
                [
                    result["model_id"],
                    result["backend"],
                    image["image_id"],
                    _median(image["model_ns"]),
                    _p95_nearest_rank(image["model_ns"]),
                    _median(image["e2e_ns"]),
                    _p95_nearest_rank(image["e2e_ns"]),
                    result["success"],
                    failure,
                ]
            )
    return buffer.getvalue()


def write_json(path: Path, payload: dict[str, Any], *, kind: str = "result") -> None:
    if kind == "result":
        validate_result(payload)
    elif kind == "manifest":
        validate_manifest(payload)
    else:
        raise ValueError("unknown kind: " + kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
