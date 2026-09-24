"""Reference quality metrics computed on the host, outside any timing loop.

Rules:
- predictions and references are matched by image stem;
- dimensions must be identical -- images are NEVER silently resized;
- LPIPS is injectable so unit tests never download pretrained weights;
- predictions without a paired reference are `runtime_only`, never scored.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image

LpipsFn = Callable[[np.ndarray, np.ndarray], float]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _load_array(path: str | Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.asarray(img)


def _data_range(array: np.ndarray) -> float:
    if np.issubdtype(array.dtype, np.integer):
        return float(np.iinfo(array.dtype).max)
    maximum = float(array.max()) if array.size else 0.0
    return 1.0 if maximum <= 1.0 else 255.0


def compute_psnr(pred: np.ndarray, ref: np.ndarray) -> float:
    a = pred.astype(np.float64)
    b = ref.astype(np.float64)
    mse = float(np.mean((a - b) ** 2))
    if mse == 0.0:
        return float("inf")
    rng = _data_range(pred)
    return 10.0 * math.log10(rng * rng / mse)


def compute_ssim(pred: np.ndarray, ref: np.ndarray) -> float:
    from skimage.metrics import structural_similarity

    rng = _data_range(pred)
    if pred.ndim == 3:
        return float(
            structural_similarity(ref, pred, data_range=rng, channel_axis=2)
        )
    return float(structural_similarity(ref, pred, data_range=rng))


_default_lpips: LpipsFn | None = None


def _default_lpips_fn() -> LpipsFn:
    global _default_lpips
    if _default_lpips is None:
        import lpips as lpips_pkg
        import torch

        model = lpips_pkg.LPIPS(net="alex", verbose=False).eval()

        def fn(pred: np.ndarray, ref: np.ndarray) -> float:
            def to_tensor(array: np.ndarray):
                scaled = array.astype(np.float32) / 255.0
                tensor = torch.from_numpy(scaled * 2.0 - 1.0)
                return tensor.permute(2, 0, 1).unsqueeze(0)

            with torch.no_grad():
                return float(model(to_tensor(pred), to_tensor(ref)).item())

        _default_lpips = fn
    return _default_lpips


def evaluate_pair(
    pred_path: str | Path,
    ref_path: str | Path,
    *,
    lpips_fn: LpipsFn | None = None,
) -> dict:
    pred = _load_array(pred_path)
    ref = _load_array(ref_path)

    if pred.shape[:2] != ref.shape[:2]:
        raise ValueError(
            f"shape mismatch: {pred.shape[:2]} vs {ref.shape[:2]} "
            f"({Path(pred_path).name} vs {Path(ref_path).name}); refusing to resize"
        )
    if pred.ndim == 3 and ref.ndim == 3 and pred.shape[2] == 4 and ref.shape[2] == 3:
        pred = pred[:, :, :3]
    elif pred.ndim == 3 and ref.ndim == 3 and pred.shape[2] == 3 and ref.shape[2] == 4:
        ref = ref[:, :, :3]
    if pred.shape[2:] != ref.shape[2:] or pred.ndim != ref.ndim:
        raise ValueError(
            f"channel mismatch: {pred.shape} vs {ref.shape} "
            f"({Path(pred_path).name} vs {Path(ref_path).name})"
        )

    scorer = lpips_fn if lpips_fn is not None else _default_lpips_fn()
    return {
        "image_id": Path(pred_path).stem,
        "psnr": compute_psnr(pred, ref),
        "ssim": compute_ssim(pred, ref),
        "lpips": float(scorer(pred, ref)),
    }


def _index_by_stem(directory: str | Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in sorted(Path(directory).iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            index.setdefault(path.stem, path)
    return index


def evaluate_folders(
    pred_dir: str | Path,
    ref_dir: str | Path,
    *,
    lpips_fn: LpipsFn | None = None,
) -> list[dict]:
    preds = _index_by_stem(pred_dir)
    refs = _index_by_stem(ref_dir)
    rows: list[dict] = []
    for stem in sorted(preds):
        ref_path = refs.get(stem)
        if ref_path is None:
            rows.append(
                {"image_id": stem, "status": "runtime_only", "psnr": None, "ssim": None, "lpips": None}
            )
            continue
        scored = evaluate_pair(preds[stem], ref_path, lpips_fn=lpips_fn)
        scored["status"] = "scored"
        rows.append(scored)
    return rows


def aggregate(rows: Iterable[dict]) -> dict[str, dict]:
    scored = [row for row in rows if row.get("status") == "scored"]
    stats: dict[str, dict] = {}
    for metric in ("psnr", "ssim", "lpips"):
        values = [float(row[metric]) for row in scored if row.get(metric) is not None]
        if values:
            stats[metric] = {
                "n": len(values),
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
            }
        else:
            stats[metric] = {"n": 0, "mean": None, "std": None}
    return stats


CSV_HEADER = ["image_id", "status", "psnr", "ssim", "lpips"]


def write_metrics_csv(path: str | Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(
                [
                    row["image_id"],
                    row["status"],
                    "" if row.get("psnr") is None else row["psnr"],
                    "" if row.get("ssim") is None else row["ssim"],
                    "" if row.get("lpips") is None else row["lpips"],
                ]
            )
