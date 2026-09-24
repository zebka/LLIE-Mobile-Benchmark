"""Generate Phase-1 accelerator latency CSVs and metrics summaries.

Reads reports/phase1-accelerators/<model>-<backend>/{run.json,outputs/} and
reports/phase1-results/<model>/run.json as the CPU baseline. Writes:
- reports/phase1-accelerators/latency.csv (all backends)
- reports/phase1-accelerators/latency-summary.csv
- reports/phase1-accelerators/<combo>/latency.csv
- reports/phase1-accelerators/<combo>/metrics.csv (when outputs/ has PNGs)
- reports/phase1-accelerators/metrics-summary.json
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host" / "src"))

from llie_bench.metrics import aggregate, evaluate_folders, write_metrics_csv
from llie_bench.report import results_to_csv, validate_result

REF = ROOT.parent / "04_datasets" / "paired" / "eval15" / "high"
ACCEL = ROOT / "reports" / "phase1-accelerators"
CPU_RESULTS = ROOT / "reports" / "phase1-results"

COMBOS = [
    ("zero-dce", "nnapi"),
    ("zero-dce", "xnnpack"),
    ("sci-medium", "nnapi"),
    ("sci-medium", "xnnpack"),
]


def _median(samples: list[int]) -> float:
    ordered = sorted(samples)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_result(payload)
    return payload


def _global_stats(result: dict) -> dict:
    model_ns = [x for im in result["images"] for x in im["model_ns"]]
    e2e_ns = [x for im in result["images"] for x in im["e2e_ns"]]
    import math

    ordered = sorted(model_ns)
    rank = math.ceil(0.95 * len(ordered))
    rank = max(1, min(rank, len(ordered)))
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


def main() -> int:
    results: list[dict] = []
    # CPU baseline from phase1-results
    for model_id in ("zero-dce", "sci-medium"):
        results.append(_load(CPU_RESULTS / model_id / "run.json"))

    accel_results: list[dict] = []
    for model_id, backend in COMBOS:
        combo_dir = ACCEL / f"{model_id}-{backend}"
        result = _load(combo_dir / "run.json")
        accel_results.append(result)
        results.append(result)
        # per-combo latency.csv
        (combo_dir / "latency.csv").write_text(results_to_csv([result]), encoding="utf-8")
        # metrics if outputs present
        outputs = combo_dir / "outputs"
        pngs = list(outputs.glob("*.png")) if outputs.is_dir() else []
        if len(pngs) >= 15 and REF.is_dir():
            rows = evaluate_folders(outputs, REF)
            write_metrics_csv(combo_dir / "metrics.csv", rows)
            print(f"{model_id}-{backend}: metrics n={len(rows)} agg={aggregate(rows)}")
        else:
            print(f"{model_id}-{backend}: outputs missing ({len(pngs)} pngs), metrics skipped")

    # combined latency.csv
    combined = results_to_csv(results)
    (ACCEL / "latency.csv").write_text(combined, encoding="utf-8")

    # latency-summary.csv
    summary_rows = [_global_stats(r) for r in results]
    summary_path = ACCEL / "latency-summary.csv"
    fields = list(summary_rows[0].keys())
    with summary_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)

    # metrics summary for accelerator combos only
    metrics_summary = {}
    for model_id, backend in COMBOS:
        combo_dir = ACCEL / f"{model_id}-{backend}"
        csv_path = combo_dir / "metrics.csv"
        if csv_path.is_file():
            import csv as csv_mod

            with csv_path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv_mod.DictReader(fh))
            for row in rows:
                for key in ("psnr", "ssim", "lpips"):
                    if row.get(key):
                        row[key] = float(row[key])
                    else:
                        row[key] = None
            metrics_summary[f"{model_id}-{backend}"] = {
                "metrics": aggregate(rows),
                "schema_ok": True,
            }
    if metrics_summary:
        (ACCEL / "metrics-summary.json").write_text(
            json.dumps(metrics_summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(summary_rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
