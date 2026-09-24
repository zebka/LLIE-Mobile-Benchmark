"""Host-side quality metrics tests using generated RGB arrays.

TDD: these FAIL until llie_bench/metrics.py exists.

Rules under test:
- shape/channel mismatches raise; images are never silently resized;
- exact match gives PSNR=inf and SSIM=1.0;
- LPIPS is injected (a stub) so unit tests never download weights;
- unpaired predictions are reported as `runtime_only`, never scored;
- one CSV row per image; mean/std over scored pairs only.
"""

from __future__ import annotations

import csv

import numpy as np
import pytest
from PIL import Image

from llie_bench.metrics import aggregate, evaluate_folders, evaluate_pair, write_metrics_csv


def _save(path, array):
    Image.fromarray(array).save(path)
    return path


def _stub_lpips(value: float = 0.42):
    calls = []

    def fn(pred, ref):
        calls.append((pred.shape, ref.shape))
        return value

    fn.calls = calls
    return fn


def test_metrics_reject_different_shapes(tmp_path):
    _save(tmp_path / "pred.png", np.zeros((8, 8, 3), dtype=np.uint8))
    _save(tmp_path / "ref.png", np.zeros((8, 9, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match="shape mismatch"):
        evaluate_pair(tmp_path / "pred.png", tmp_path / "ref.png", lpips_fn=_stub_lpips())


def test_metrics_accepts_rgba_pred_vs_rgb_ref(tmp_path):
    rng = np.random.default_rng(4)
    rgb = rng.integers(0, 256, size=(8, 8, 3), dtype=np.uint8)
    rgba = np.dstack([rgb, np.full((8, 8), 255, dtype=np.uint8)])
    _save(tmp_path / "pred.png", rgba)
    _save(tmp_path / "ref.png", rgb)
    result = evaluate_pair(tmp_path / "pred.png", tmp_path / "ref.png", lpips_fn=_stub_lpips())
    assert result["psnr"] == float("inf")
    assert result["ssim"] == pytest.approx(1.0, abs=1e-6)


def test_metrics_reject_channel_mismatch(tmp_path):
    _save(tmp_path / "pred.png", np.zeros((8, 8, 2), dtype=np.uint8))
    _save(tmp_path / "ref.png", np.zeros((8, 8, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match="channel mismatch"):
        evaluate_pair(tmp_path / "pred.png", tmp_path / "ref.png", lpips_fn=_stub_lpips())


def test_exact_match_gives_perfect_scores(tmp_path):
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 256, size=(32, 32, 3), dtype=np.uint8)
    _save(tmp_path / "pred.png", arr)
    _save(tmp_path / "ref.png", arr.copy())
    result = evaluate_pair(tmp_path / "pred.png", tmp_path / "ref.png", lpips_fn=_stub_lpips(0.0))
    assert result["psnr"] == float("inf")
    assert result["ssim"] == pytest.approx(1.0, abs=1e-6)
    assert result["lpips"] == 0.0
    assert result["image_id"] == "pred"


def test_lpips_stub_is_used_and_is_finite(tmp_path):
    rng = np.random.default_rng(1)
    _save(tmp_path / "pred.png", rng.integers(0, 256, size=(16, 16, 3), dtype=np.uint8))
    _save(tmp_path / "ref.png", rng.integers(0, 256, size=(16, 16, 3), dtype=np.uint8))
    stub = _stub_lpips(0.25)
    result = evaluate_pair(tmp_path / "pred.png", tmp_path / "ref.png", lpips_fn=stub)
    assert result["lpips"] == 0.25
    assert np.isfinite(result["psnr"])
    assert len(stub.calls) == 1


def test_folders_match_by_stem_and_mark_runtime_only(tmp_path):
    pred = tmp_path / "pred"
    ref = tmp_path / "ref"
    pred.mkdir()
    ref.mkdir()
    rng = np.random.default_rng(2)
    scored = rng.integers(0, 256, size=(12, 12, 3), dtype=np.uint8)
    _save(pred / "a.png", scored)
    _save(ref / "a.png", scored)
    _save(pred / "lone.png", rng.integers(0, 256, size=(12, 12, 3), dtype=np.uint8))

    rows = evaluate_folders(pred, ref, lpips_fn=_stub_lpips())
    by_id = {row["image_id"]: row for row in rows}
    assert by_id["a"]["status"] == "scored"
    assert by_id["a"]["ssim"] == pytest.approx(1.0, abs=1e-6)
    assert by_id["lone"]["status"] == "runtime_only"
    assert by_id["lone"]["psnr"] is None

    agg = aggregate(rows)
    assert agg["psnr"]["n"] == 1
    assert agg["psnr"]["mean"] == float("inf")


def test_write_metrics_csv_one_row_per_image(tmp_path):
    pred = tmp_path / "pred"
    ref = tmp_path / "ref"
    pred.mkdir()
    ref.mkdir()
    rng = np.random.default_rng(3)
    for stem in ("x", "y"):
        arr = rng.integers(0, 256, size=(10, 10, 3), dtype=np.uint8)
        _save(pred / f"{stem}.png", arr)
        _save(ref / f"{stem}.png", arr)
    _save(pred / "z.png", rng.integers(0, 256, size=(10, 10, 3), dtype=np.uint8))

    rows = evaluate_folders(pred, ref, lpips_fn=_stub_lpips())
    csv_path = tmp_path / "metrics.csv"
    write_metrics_csv(csv_path, rows)

    with open(csv_path, newline="", encoding="utf-8") as handle:
        loaded = list(csv.reader(handle))
    assert loaded[0] == ["image_id", "status", "psnr", "ssim", "lpips"]
    assert len(loaded) == 4  # header + 3 images


def test_aggregate_reports_mean_and_std_over_scored_only():
    rows = [
        {"image_id": "a", "status": "scored", "psnr": 20.0, "ssim": 0.8, "lpips": 0.3},
        {"image_id": "b", "status": "scored", "psnr": 30.0, "ssim": 0.9, "lpips": 0.1},
        {"image_id": "c", "status": "runtime_only", "psnr": None, "ssim": None, "lpips": None},
    ]
    agg = aggregate(rows)
    assert agg["psnr"]["n"] == 2
    assert agg["psnr"]["mean"] == pytest.approx(25.0)
    assert agg["psnr"]["std"] == pytest.approx(5.0, abs=1e-9)
    assert agg["lpips"]["mean"] == pytest.approx(0.2)
    assert agg["ssim"]["n"] == 2
