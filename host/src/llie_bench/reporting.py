"""Build latency + quality report files from a pulled results tree.

Input: a directory whose immediate subdirectories each hold one combo's
``run.json`` (+ ``outputs/*.png`` when images were pulled). Works for both
layouts in this repo: ``phase1-results/<model>/`` and
``phase1-accelerators/<model>-<backend>/`` — the backend is read from the
JSON itself, never from the folder name.

Output (written into the results dir):
- ``latency.csv`` (per-image median/p95 rows, all combos)
- ``latency-summary.csv`` (one row per combo)
- ``<combo>/latency.csv``, ``<combo>/metrics.csv`` (when outputs + ref exist)
- ``metrics-summary.json``
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .metrics import aggregate, evaluate_folders, write_metrics_csv
from .report import results_to_csv, validate_result


def _median(samples: list[int]) -> float:
    ordered = sorted(samples)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def load_result(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_result(payload)
    return payload


def combo_stats(result: dict[str, Any]) -> dict[str, Any]:
    model_ns = [x for im in result["images"] for x in im["model_ns"]]
    e2e_ns = [x for im in result["images"] for x in im["e2e_ns"]]
    ordered = sorted(model_ns)
    rank = max(1, min(math.ceil(0.95 * len(ordered)), len(ordered)))
    return {
        "model_id": result["model_id"],
        "backend": result["backend"],
        "load_ms": result["load_time_ns"] / 1e6,
        "model_median_ms": _median(model_ns) / 1e6,
        "model_p95_ms": ordered[rank - 1] / 1e6,
        "e2e_median_ms": _median(e2e_ns) / 1e6,
        "pss_peak_mb": result.get("pss", {}).get("peak_mb"),
        "success": result["success"],
        "failure_reason": result.get("failure_reason", ""),
        "thermal_before": result.get("thermal", {}).get("before"),
        "thermal_after": result.get("thermal", {}).get("after"),
    }


def find_combos(results_root: str | Path) -> list[tuple[str, Path, dict[str, Any]]]:
    """Return (combo_name, combo_dir, result) sorted by name."""
    root = Path(results_root)
    if not root.is_dir():
        raise ValueError("results dir not found: " + str(root))
    found: list[tuple[str, Path, dict[str, Any]]] = []
    for child in sorted(root.iterdir()):
        run_json = child / "run.json" if child.is_dir() else None
        if run_json is None or not run_json.is_file():
            continue
        found.append((child.name, child, load_result(run_json)))
    if not found:
        raise ValueError("no run.json found in " + str(root))
    return found


def build_report(
    results_root: str | Path, ref_dir: str | Path | None = None
) -> dict[str, Any]:
    """Generate all derived files. Returns {"combos": [...], "metrics": [...] productive summary}."""
    root = Path(results_root)
    ref = Path(ref_dir) if ref_dir else None
    combos = find_combos(root)
    results = [result for _, _, result in combos]

    summary_rows = [combo_stats(result) for result in results]
    summary_path = root / "latency-summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)
    (root / "latency.csv").write_text(results_to_csv(results), encoding="utf-8")

    metrics_summary: dict[str, Any] = {}
    for name, combo_dir, result in combos:
        (combo_dir / "latency.csv").write_text(results_to_csv([result]), encoding="utf-8")
        outputs = combo_dir / "outputs"
        pngs = list(outputs.glob("*.png")) if outputs.is_dir() else []
        if ref is not None and ref.is_dir() and len(pngs) >= len(result.get("images", [])) and pngs:
            rows = evaluate_folders(outputs, ref)
            write_metrics_csv(combo_dir / "metrics.csv", rows)
            metrics_summary[name] = {"metrics": aggregate(rows), "schema_ok": True}
    if metrics_summary:
        (root / "metrics-summary.json").write_text(
            json.dumps(metrics_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return {"combos": [name for name, _, _ in combos], "metrics": sorted(metrics_summary)}
