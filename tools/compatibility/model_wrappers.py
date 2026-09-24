"""Parity and export helpers for the Phase 1 runtime compatibility gate.

TDD: `test_export_parity.py` FAILs until the wrappers below load the
archived checkpoints and produce finite outputs of the documented shape.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import torch

THIRDPARTY = Path(__file__).resolve().parents[3] / "02_code" / "IBDiff" / "thirdparty"
WEIGHTS = Path(__file__).resolve().parents[3] / "03_models" / "thirdparty-weights"

ZERO_DCE_CODE = THIRDPARTY / "Zero-DCE" / "Zero-DCE_code"
ZERO_DCE_WEIGHTS = WEIGHTS / "ZeroDCE-snapshots" / "Epoch99.pth"
SCI_CVPR = THIRDPARTY / "SCI" / "CVPR"
SCI_WEIGHTS = WEIGHTS / "SCI-weights" / "medium.pt"

PARITY_TOLERANCE = 1e-3
PARITY_INPUT_SIZE = (3, 64, 96)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _loss_function_shim() -> None:
    """SCI's model.py imports `from loss import LossFunction` at import time.

    Only inference is needed for parity, so provide a no-op criterion before
    loading the module instead of editing the archived third-party code.
    """
    if "loss" in sys.modules:
        return

    loss_mod = importlib.util.module_from_spec(importlib.machinery.ModuleSpec("loss", None))

    class LossFunction(torch.nn.Module):
        def forward(self, *args: Any, **kwargs: Any):
            return torch.zeros(())

    loss_mod.LossFunction = LossFunction  # type: ignore[attr-defined]
    sys.modules["loss"] = loss_mod


def make_parity_input(seed: int = 7) -> torch.Tensor:
    generator = torch.Generator().manual_seed(seed)
    return torch.rand((1, *PARITY_INPUT_SIZE), generator=generator, dtype=torch.float32)


def load_zero_dce() -> torch.nn.Module:
    model_mod = _load_module("zerodce_model", ZERO_DCE_CODE / "model.py")
    model = model_mod.enhance_net_nopool()
    state = torch.load(ZERO_DCE_WEIGHTS, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model


def load_sci_medium() -> torch.nn.Module:
    _loss_function_shim()
    sci_mod = _load_module("sci_model", SCI_CVPR / "model.py")
    model = sci_mod.Finetunemodel(str(SCI_WEIGHTS))
    model.eval()
    return model


def zero_dce_reference_output(model: torch.nn.Module, x: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        _, enhanced, _ = model(x)
    return enhanced


def sci_reference_output(model: torch.nn.Module, x: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        illu, _ = model(x)
    return illu


def assert_parity(reference: torch.Tensor, candidate: torch.Tensor, label: str) -> float:
    if reference.shape != candidate.shape:
        raise AssertionError(f"{label}: shape mismatch {tuple(reference.shape)} vs {tuple(candidate.shape)}")
    if not torch.isfinite(candidate).all():
        raise AssertionError(f"{label}: non-finite values in output")
    max_abs_err = float((reference - candidate).abs().max())
    if max_abs_err > PARITY_TOLERANCE:
        raise AssertionError(f"{label}: max abs error {max_abs_err} exceeds {PARITY_TOLERANCE}")
    return max_abs_err