# Compatibility tools (Phase 1)

Export Zero-DCE and SCI-medium from the archived PyTorch checkpoints, run a
host-side parity gate against the PyTorch reference, and record the runtime
decision.

- `model_wrappers.py` — loads the archived checkpoints read-only (SCI's
  training-time `loss` import is shimmed; archived code is not edited).
- `test_export_parity.py` — pytest gate: finite outputs, documented shapes,
  in-range values, determinism, and a `1e-3` max-abs-error parity helper.
- `export_models.py` — one command to attempt every export candidate and
  write artifacts + a JSON summary under `reports/compatibility/` only.

Run from the repository root:

```powershell
python -m pytest tools/compatibility -q
python tools/compatibility/export_models.py
```
