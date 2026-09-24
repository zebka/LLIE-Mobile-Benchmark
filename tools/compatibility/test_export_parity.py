"""Phase 1 compatibility gate: PyTorch reference parity for Zero-DCE and SCI medium.

FAILs until `model_wrappers.py` loads the archived checkpoints and the
documented outputs are finite, correctly shaped, and in range.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model_wrappers import (  # noqa: E402
    PARITY_INPUT_SIZE,
    assert_parity,
    load_sci_medium,
    load_zero_dce,
    make_parity_input,
    sci_reference_output,
    zero_dce_reference_output,
)


@pytest.fixture(scope="module")
def parity_input() -> torch.Tensor:
    return make_parity_input()


def test_zero_dce_reference_output_shape_and_range(parity_input):
    model = load_zero_dce()
    out = zero_dce_reference_output(model, parity_input)
    assert out.shape == (1, *PARITY_INPUT_SIZE)
    assert torch.isfinite(out).all()
    assert 0.0 <= float(out.min()) and float(out.max()) <= 1.0


def test_sci_medium_reference_output_shape_and_range(parity_input):
    model = load_sci_medium()
    out = sci_reference_output(model, parity_input)
    assert out.shape == (1, *PARITY_INPUT_SIZE)
    assert torch.isfinite(out).all()
    assert 0.0 < float(out.max()) and float(out.max()) <= 1.0


def test_reference_outputs_are_deterministic(parity_input):
    zd = load_zero_dce()
    sci = load_sci_medium()
    a = zero_dce_reference_output(zd, parity_input)
    b = zero_dce_reference_output(zd, parity_input)
    assert torch.equal(a, b)
    a = sci_reference_output(sci, parity_input)
    b = sci_reference_output(sci, parity_input)
    assert torch.equal(a, b)


def test_assert_parity_passes_on_identical_outputs(parity_input):
    zd = load_zero_dce()
    out = zero_dce_reference_output(zd, parity_input)
    err = assert_parity(out, out.clone(), "zero-dce self")
    assert err == 0.0


def test_assert_parity_fails_on_mismatch(parity_input):
    zd = load_zero_dce()
    out = zero_dce_reference_output(zd, parity_input)
    mutated = out.clone()
    mutated[..., 0, 0, 0] += 1.0
    with pytest.raises(AssertionError, match="exceeds"):
        assert_parity(out, mutated, "zero-dce mutated")