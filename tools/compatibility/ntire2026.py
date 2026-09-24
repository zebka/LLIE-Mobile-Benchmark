"""NTIRE 2026 candidate compatibility helpers.

Host-side math the benchmark needs before any third-party checkpoint is
touched: parameter counting, checkpoint byte size, the TCD [-1, 1]
normalization pair, and export wrappers that enforce the benchmark's
[0, 1] RGB output contract.
"""

from __future__ import annotations

from pathlib import Path

import torch


def count_trainable_parameters(model: torch.nn.Module) -> int:
    """Count parameters with requires_grad=True (frozen weights excluded)."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def checkpoint_file_size_bytes(path: str | Path) -> int:
    """On-disk byte count of a checkpoint file (not a parameter estimate)."""
    return Path(path).stat().st_size


def normalize_tcd_input(x: torch.Tensor) -> torch.Tensor:
    """Map benchmark [0, 1] RGB to the TCD model's [-1, 1] input range."""
    return x * 2.0 - 1.0


def denormalize_tcd_output(y: torch.Tensor) -> torch.Tensor:
    """Map the TCD model's [-1, 1] output back to benchmark [0, 1] RGB."""
    return (y + 1.0) / 2.0


class MobileIEBenchmarkWrapper(torch.nn.Module):
    """Clamp a MobileIE-style model to the benchmark output contract."""

    def __init__(self, model: torch.nn.Module):
        super().__init__()
        self.model = model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x).clamp(0.0, 1.0)


class TCDenchmarkWrapper(torch.nn.Module):
    """Wrap the dual-branch TCD model exactly like the released run.py.

    run.py feeds the same normalized tensor to both the RGB and grey
    branches (the grey branch takes 3 channels, not grayscale), then
    denormalizes the [-1, 1] output. This wrapper reproduces that path
    and clamps to [0, 1].
    """

    def __init__(self, model: torch.nn.Module):
        super().__init__()
        self.model = model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        norm = normalize_tcd_input(x)
        return denormalize_tcd_output(self.model(norm, norm)).clamp(0.0, 1.0)

