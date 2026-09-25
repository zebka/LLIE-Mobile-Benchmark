"""Parity and export helpers for the Phase 1 runtime compatibility gate.

TDD: `test_export_parity.py` FAILs until the wrappers below load the
archived checkpoints and produce finite outputs of the documented shape.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import torch

THIRDPARTY = Path(__file__).resolve().parents[3] / "02_code" / "IBDiff" / "thirdparty"
WEIGHTS = Path(__file__).resolve().parents[3] / "03_models" / "thirdparty-weights"

ZERO_DCE_CODE = THIRDPARTY / "Zero-DCE" / "Zero-DCE_code"
ZERO_DCE_WEIGHTS = WEIGHTS / "ZeroDCE-snapshots" / "Epoch99.pth"
ZERO_DCE_WEIGHTS_SHA256 = "a4395acb874f320375d9704997cef874eaaaaa26a1777ceb29a92b70f74c3612"
SCI_CVPR = THIRDPARTY / "SCI" / "CVPR"
SCI_WEIGHTS = WEIGHTS / "SCI-weights" / "medium.pt"
SCI_WEIGHTS_SHA256 = "4ff1e7e66e8f18114f790e5085ca4c936f0858e329e7ad1cb65b8aa09a9c6916"
RUAS_CODE = THIRDPARTY / "RUAS"
RUAS_WEIGHTS = WEIGHTS / "RUAS-ckpt" / "lol.pt"
RUAS_WEIGHTS_SHA256 = "f45a881a9b836fff4a3172481f28c9eb4d91bc4df54ec064092f39ce40abcdcd"
LYT_CODE = THIRDPARTY / "LYT-Net" / "PyTorch"
LYT_WEIGHTS = WEIGHTS / "LYTNet-weights" / "best_model_LOLv1.pth"
LYT_WEIGHTS_SHA256 = "19c15bbe5e4d961d7c27f26998c90c39ef81759af027ba1aba9f32d6fe98462d"

CHECKPOINT_PROVENANCE: dict[str, tuple[Path, str]] = {
    "zero-dce": (ZERO_DCE_WEIGHTS, ZERO_DCE_WEIGHTS_SHA256),
    "sci-medium": (SCI_WEIGHTS, SCI_WEIGHTS_SHA256),
    "ruas-lol": (RUAS_WEIGHTS, RUAS_WEIGHTS_SHA256),
    "lyt-net": (LYT_WEIGHTS, LYT_WEIGHTS_SHA256),
}

PARITY_TOLERANCE = 1e-3
PARITY_INPUT_SIZE = (3, 64, 96)


def compute_checkpoint_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def make_parity_input(
    seed: int = 7, size: tuple[int, int, int] = PARITY_INPUT_SIZE
) -> torch.Tensor:
    generator = torch.Generator().manual_seed(seed)
    return torch.rand((1, *size), generator=generator, dtype=torch.float32)


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


def load_ruas_lol() -> torch.nn.Module:
    """Load the RUAS lol enhancement network for inference.

    RUAS `model.py` imports `from operations import *` and `import genotypes`
    at import time, so the RUAS directory goes on `sys.path` first. The full
    `Network` class is avoided entirely: its `_init_weights` hardcodes
    `torch.load('./model/denoise.pt')`, so only `EnhanceNetwork` is
    instantiated (the misspelled `iteratioin` kwarg is the real signature).
    `lol.pt` stores the full `Network` state dict; the `enhance_net.` prefix
    is stripped for strict loading into the enhance net alone.
    """
    if str(RUAS_CODE) not in sys.path:
        sys.path.insert(0, str(RUAS_CODE))
    ruas_mod = _load_module("ruas_model", RUAS_CODE / "model.py")
    enhance = ruas_mod.EnhanceNetwork(iteratioin=3, channel=3, genotype=ruas_mod.genotypes.IEM)
    state = torch.load(RUAS_WEIGHTS, map_location="cpu", weights_only=True)
    enhance_prefix = "enhance_net."
    enhance_state = {
        key[len(enhance_prefix):]: value
        for key, value in state.items()
        if key.startswith(enhance_prefix)
    }
    enhance.load_state_dict(enhance_state)
    enhance.eval()
    return _RUASEnhanced(enhance)


def load_lyt_net() -> torch.nn.Module:
    """Load the LYT-Net enhancement model (PyTorch port, LOLv1 checkpoint).

    The repo's HF release only contains a README, so the official PyTorch
    weights come from the Google-Drive archive linked in `PyTorch/README.md`;
    its LOLv1 member `best_model_LOLv1.pth` is the checkpoint used here. The
    state dict matches `LYT(filters=32)` strictly, RGB->YCbCr happens
    in-graph, and the model already returns a sigmoid RGB tensor.
    """
    lyt_mod = _load_module("lyt_model", LYT_CODE / "model.py")
    model = lyt_mod.LYT(filters=32)
    state = torch.load(LYT_WEIGHTS, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model


class _RUASEnhanced(torch.nn.Module):
    """RUAS full Network couples the denoiser via a hardcoded ckpt path;
    the benchmark uses only the enhancement output (last u)."""

    def __init__(self, enhance_net: torch.nn.Module):
        super().__init__()
        self.enhance_net = enhance_net

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        u_list, _ = self.enhance_net(x)
        return u_list[-1]


def zero_dce_reference_output(model: torch.nn.Module, x: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        _, enhanced, _ = model(x)
    return enhanced


def sci_reference_output(model: torch.nn.Module, x: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        _, enhanced = model(x)
    return enhanced


def ruas_reference_output(model: torch.nn.Module, x: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        return model(x)


def lyt_reference_output(model: torch.nn.Module, x: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        return model(x)


def assert_parity(reference: torch.Tensor, candidate: torch.Tensor, label: str) -> float:
    if reference.shape != candidate.shape:
        raise AssertionError(f"{label}: shape mismatch {tuple(reference.shape)} vs {tuple(candidate.shape)}")
    if not torch.isfinite(candidate).all():
        raise AssertionError(f"{label}: non-finite values in output")
    max_abs_err = float((reference - candidate).abs().max())
    if max_abs_err > PARITY_TOLERANCE:
        raise AssertionError(f"{label}: max abs error {max_abs_err} exceeds {PARITY_TOLERANCE}")
    return max_abs_err