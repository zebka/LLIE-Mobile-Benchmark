"""Backward-compatible entry point: prefer ``llie-bench report``.

Equivalent: llie-bench report --results-dir reports/phase1-accelerators
--ref-dir ../04_datasets/paired/eval15/high
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host" / "src"))

from llie_bench.reporting import build_report

REF = ROOT.parent / "04_datasets" / "paired" / "eval15" / "high"
ACCEL = ROOT / "reports" / "phase1-accelerators"


def main() -> int:
    import json

    summary = build_report(ACCEL, REF if REF.is_dir() else None)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
