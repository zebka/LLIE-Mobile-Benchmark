"""NTIRE 2026 candidate compatibility helpers (TDD).

These tests pin the exact host-side math the benchmark needs before any
third-party checkpoint is touched:
- parameter counting excludes frozen parameters;
- checkpoint file size is the on-disk byte count (not a parameter estimate);
- TCD's [-1, 1] normalization round-trips;
- export wrappers clamp to the benchmark's [0, 1] output contract;
- the TCD wrapper feeds the same normalized tensor to both branches,
  matching the released run.py inference path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ntire2026 import (  # noqa: E402
    MobileIEBenchmarkWrapper,
    TCDenchmarkWrapper,
    checkpoint_file_size_bytes,
    count_trainable_parameters,
    denormalize_tcd_output,
    normalize_tcd_input,
)


def test_count_trainable_parameters_excludes_frozen():
    model = torch.nn.Linear(4, 2)
    model.weight.requires_grad_(False)
    assert count_trainable_parameters(model) == model.bias.numel()


def test_checkpoint_file_size_bytes_reports_actual_bytes(tmp_path):
    blob = tmp_path / "model.pth"
    blob.write_bytes(b"\x00" * 557618)
    assert checkpoint_file_size_bytes(blob) == 557618


def test_tcd_input_output_mapping_roundtrip():
    x = torch.tensor([[[[0.0, 0.25], [0.5, 1.0]]]])
    assert torch.allclose(denormalize_tcd_output(normalize_tcd_input(x)), x)


def test_mobileie_wrapper_clamps_to_unit_range():
    class Raw(torch.nn.Module):
        def forward(self, x):
            return x * 2.0 - 0.25

    x = torch.tensor([[[[0.0, 0.5], [1.0, 2.0]]]])
    out = MobileIEBenchmarkWrapper(Raw())(x)
    assert out.shape == x.shape
    assert float(out.min()) >= 0.0 and float(out.max()) <= 1.0
    assert torch.allclose(out, torch.tensor([[[[0.0, 0.75], [1.0, 1.0]]]]))


def test_tcd_wrapper_matches_reference_math():
    class Dual(torch.nn.Module):
        def forward(self, rgb, grey):
            assert torch.equal(rgb, grey)
            return rgb * 0.5

    x = torch.full((1, 3, 2, 2), 0.75)
    out = TCDenchmarkWrapper(Dual())(x)
    # normalize: 0.75 -> 0.5; model halves -> 0.25; denormalize -> 0.625
    assert torch.allclose(out, torch.full((1, 3, 2, 2), 0.625))
