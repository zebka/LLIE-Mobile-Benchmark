"""Phase 1 compatibility gate: PyTorch reference parity for Zero-DCE, SCI medium, RUAS lol, and LYT-Net.

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
    CHECKPOINT_PROVENANCE,
    PARITY_INPUT_SIZE,
    assert_parity,
    compute_checkpoint_sha256,
    load_lyt_net,
    load_ruas_lol,
    load_sci_medium,
    load_zero_dce,
    make_parity_input,
    lyt_reference_output,
    ruas_reference_output,
    sci_reference_output,
    zero_dce_reference_output,
)


@pytest.mark.parametrize("model_id", sorted(CHECKPOINT_PROVENANCE))
def test_checkpoint_sha256_matches_recorded_constants(model_id: str):
    path, recorded = CHECKPOINT_PROVENANCE[model_id]
    assert path.is_file(), f"{model_id}: checkpoint missing at {path}"
    assert len(recorded) == 64 and all(c in "0123456789abcdef" for c in recorded)
    assert compute_checkpoint_sha256(path) == recorded, f"{model_id}: checkpoint hash drift"


@pytest.fixture(scope="module")
def parity_input() -> torch.Tensor:
    return make_parity_input()


def export_and_run_onnx(model, name: str, x: torch.Tensor, out_dir: Path) -> torch.Tensor:
    """Export to a temp ONNX with the study-export args and run ORT CPU."""
    import onnxruntime as ort

    artifact = out_dir / f"{name}.onnx"
    torch.onnx.export(
        model,
        x,
        str(artifact),
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {0: "batch", 2: "height", 3: "width"},
            "output": {0: "batch", 2: "height", 3: "width"},
        },
        dynamo=False,
    )
    session = ort.InferenceSession(str(artifact), providers=["CPUExecutionProvider"])
    (output,) = session.run(None, {"input": x.numpy()})
    return torch.from_numpy(output)


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


def test_ruas_lol_loads_and_runs(parity_input):
    model = load_ruas_lol()
    out = ruas_reference_output(model, parity_input)
    assert out.shape == (1, *PARITY_INPUT_SIZE)
    assert torch.isfinite(out).all()
    assert 0.0 <= float(out.min()) and float(out.max()) <= 1.0


def test_ruas_lol_reference_output_deterministic(parity_input):
    model = load_ruas_lol()
    a = ruas_reference_output(model, parity_input)
    b = ruas_reference_output(model, parity_input)
    assert torch.equal(a, b)


def test_ruas_lol_onnx_parity(parity_input, tmp_path):
    model = load_ruas_lol()
    ref = ruas_reference_output(model, parity_input)
    out = export_and_run_onnx(model, "ruas-lol", parity_input, tmp_path)
    err = assert_parity(ref, out, "ruas-lol")
    assert err <= 1e-3


def test_lyt_net_loads_and_runs(parity_input):
    model = load_lyt_net()
    out = lyt_reference_output(model, parity_input)
    assert out.shape == (1, *PARITY_INPUT_SIZE)
    assert torch.isfinite(out).all()
    assert 0.0 <= float(out.min()) and float(out.max()) <= 1.0


def test_lyt_net_onnx_parity(parity_input, tmp_path):
    model = load_lyt_net()
    ref = lyt_reference_output(model, parity_input)
    out = export_and_run_onnx(model, "lyt-net", parity_input, tmp_path)
    err = assert_parity(ref, out, "lyt-net")
    assert err <= 1e-3


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