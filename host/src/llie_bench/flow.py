"""End-to-end benchmark flow: setup -> benchmark -> report.

This module holds the tribal knowledge so a newcomer only runs CLI commands:

- ``setup_device`` pushes models, manifests and images in one go.
- ``run_combo`` runs ONE model x backend batch and pulls its results:
  force-stop (clears the app's ``already running`` latch), delete stale
  status/result, pre-create shell-owned placeholder PNGs (otherwise
  ``adb pull`` fails with Permission denied on app-owned files), start,
  poll the status file, pull run.json + status + the outputs dir named in
  the run.json itself (works with old shared ``outputs-<backend>`` dirs
  and new per-model ``outputs-<model>-<backend>`` dirs).
- ``run_matrix`` repeats ``run_combo`` sequentially (never in parallel:
  the app runs one batch at a time and shared outputs dirs would mix).

Every adb invocation is an argument list, never a shell string, so the
existing test FakeRunner keeps working. Timing always stays on-device.
"""

from __future__ import annotations

import time
from pathlib import Path

from .adb import Adb, AdbError
from .report import validate_result

PACKAGE = "org.llie.mobilebenchmark"
ACTIVITY = "org.llie.mobilebenchmark/.MainActivity"
ACTION_RUN = "org.llie.bench.RUN"

REMOTE_BASE = "/sdcard/Android/data/org.llie.mobilebenchmark/files"
REMOTE_MODELS = REMOTE_BASE + "/models"
REMOTE_MANIFESTS = REMOTE_BASE + "/manifests"
REMOTE_IMAGES = REMOTE_BASE + "/images"
REMOTE_RESULTS = REMOTE_BASE + "/results"

MODELS = ["zero-dce", "sci-medium"]
BACKENDS = ["cpu", "nnapi", "xnnpack"]

POLL_INTERVAL_S = 5.0
TIMEOUT_S = 600.0


def suffix(backend: str) -> str:
    """Result-file suffix: '' for cpu, '-<backend>' otherwise."""
    return "" if backend == "cpu" else "-" + backend


def result_name(model_id: str, backend: str) -> str:
    return model_id + suffix(backend) + "-run.json"


def status_name(model_id: str, backend: str) -> str:
    return model_id + suffix(backend) + ".status"


def candidate_outputs_dirs(model_id: str, backend: str) -> list[str]:
    """Outputs dirs, newest naming first.

    New APK: ``outputs-<model>-<backend>`` (``outputs-<model>`` for cpu).
    Old APK: ``outputs-<backend>`` (``outputs`` for cpu).
    """
    if backend == "cpu":
        return ["outputs-" + model_id, "outputs"]
    return ["outputs-" + model_id + "-" + backend, "outputs-" + backend]


def setup_device(
    adb: Adb,
    *,
    compat_dir: str | Path,
    images_dir: str | Path,
    image_set: str = "eval15",
) -> dict[str, int]:
    """Push models, manifests and images; prepare the results dir.

    Returns counts ``{"models": n, "images": n}``.
    """
    compat = Path(compat_dir)
    images = Path(images_dir)
    pushed_models = 0
    for model_id in MODELS:
        artifact = compat / (model_id + ".onnx")
        manifest = compat / (model_id + ".manifest.json")
        if not artifact.is_file():
            raise ValueError("missing artifact: " + str(artifact))
        if not manifest.is_file():
            raise ValueError("missing manifest: " + str(manifest))
        adb.push(artifact, REMOTE_MODELS + "/" + model_id + ".onnx")
        adb.push(manifest, REMOTE_MANIFESTS + "/" + model_id + ".manifest.json")
        pushed_models += 1
    pngs = sorted(p for p in images.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    if not pngs:
        raise ValueError("no .png images in " + str(images))
    for png in pngs:
        adb.push(png, REMOTE_IMAGES + "/" + image_set + "/" + png.name)
    adb.shell("mkdir", "-p", REMOTE_RESULTS)
    # adb push creates shell-owned dirs without other-execute, which the app
    # cannot traverse (it then reports "manifest missing"). All staged dirs
    # are shell-owned, so plain chmod (no -R, no app-owned files) is safe.
    adb.shell("chmod", "777", REMOTE_MODELS, REMOTE_MANIFESTS, REMOTE_IMAGES, REMOTE_RESULTS)
    adb.shell("chmod", "777", REMOTE_IMAGES + "/" + image_set)
    return {"models": pushed_models, "images": len(pngs)}


def prime_outputs(adb: Adb, outputs_dir: str, image_names: list[str]) -> None:
    """Pre-create shell-owned 666 placeholder PNGs.

    The app overwrites them in place (ownership stays shell), so the
    host ``adb pull`` afterwards succeeds. Without this, app-created
    files are unreadable by shell (Permission denied).
    """
    adb.shell("mkdir", "-p", REMOTE_RESULTS + "/" + outputs_dir)
    paths = [REMOTE_RESULTS + "/" + outputs_dir + "/" + name for name in image_names]
    adb.shell("rm", "-f", *paths)
    adb.shell("touch", *paths)
    adb.shell("chmod", "666", *paths)


def wait_status(
    adb: Adb,
    status_remote: str,
    *,
    timeout: float = TIMEOUT_S,
    poll_interval: float = POLL_INTERVAL_S,
    sleep=time.sleep,
) -> str:
    """Poll a status file until it reads done/failed. Returns the status."""
    deadline = time.monotonic() + timeout
    last = ""
    while True:
        try:
            last = adb.shell("cat", status_remote).strip()
        except AdbError:
            last = ""  # file not created yet (we deleted the stale one)
        if last in ("done", "failed"):
            return last
        if time.monotonic() >= deadline:
            raise TimeoutError(
                "timed out waiting for " + status_remote + " (last seen: " + repr(last) + ")"
            )
        sleep(poll_interval)


def discover_outputs_dir(adb: Adb, model_id: str, backend: str) -> str:
    """Pick the outputs dir the app actually wrote (new vs old APK naming)."""
    try:
        listing = adb.shell("ls", REMOTE_RESULTS)
    except AdbError as exc:
        raise AdbError(
            ["adb", "shell", "ls", REMOTE_RESULTS],
            stderr="cannot list results dir: " + str(exc),
        ) from exc
    present = {line.strip() for line in listing.splitlines() if line.strip()}
    for candidate in candidate_outputs_dirs(model_id, backend):
        if candidate in present:
            return candidate
    raise ValueError(
        "no outputs dir found for " + model_id + "/" + backend + " in " + REMOTE_RESULTS
    )


def run_combo(
    adb: Adb,
    *,
    model_id: str,
    backend: str,
    image_set: str = "eval15",
    image_names: list[str] | None = None,
    out_dir: str | Path,
    timeout: float = TIMEOUT_S,
    poll_interval: float = POLL_INTERVAL_S,
    sleep=time.sleep,
) -> Path:
    """Run one model x backend batch and pull its results into out_dir.

    Layout written: ``out_dir/{run.json,status.txt,outputs/*.png}``.
    Raises on timeout, failed run, schema violation, or missing outputs.
    """
    out = Path(out_dir)
    names = list(image_names) if image_names is not None else []
    result_remote = REMOTE_RESULTS + "/" + result_name(model_id, backend)
    status_remote = REMOTE_RESULTS + "/" + status_name(model_id, backend)

    adb.shell("am", "force-stop", PACKAGE)
    adb.shell("rm", "-f", result_remote, status_remote)
    # Re-create shell-owned placeholders: the app overwrites them in place,
    # so run.json/status stay readable by shell (else polling loops forever).
    adb.shell("touch", result_remote, status_remote)
    adb.shell("chmod", "666", result_remote, status_remote)
    for outputs_dir in candidate_outputs_dirs(model_id, backend):
        prime_outputs(adb, outputs_dir, names)
    adb.start_benchmark(
        model_id=model_id, image_set=image_set, backend=backend, image_names=names or None
    )
    status = wait_status(
        adb, status_remote, timeout=timeout, poll_interval=poll_interval, sleep=sleep
    )
    if status != "done":
        raise RuntimeError("on-device run failed for " + model_id + "/" + backend)

    out_outputs = out / "outputs"
    if out_outputs.is_dir():
        for stale in out_outputs.glob("*.png"):
            stale.unlink()
    out_outputs.mkdir(parents=True, exist_ok=True)
    adb.pull(result_remote, out / "run.json")
    adb.pull(status_remote, out / "status.txt")
    outputs_dir = discover_outputs_dir(adb, model_id, backend)
    adb.pull(REMOTE_RESULTS + "/" + outputs_dir + "/.", out_outputs)

    import json

    payload = json.loads((out / "run.json").read_text(encoding="utf-8"))
    validate_result(payload)
    if not payload.get("success", False):
        raise RuntimeError(
            "run reported success=false for " + model_id + "/" + backend + ": "
            + str(payload.get("failure_reason", ""))
        )
    pulled = sorted(out_outputs.glob("*.png"))
    if len(pulled) < len(payload.get("images", [])):
        raise RuntimeError(
            "only %d/%d outputs pulled for %s/%s"
            % (len(pulled), len(payload.get("images", [])), model_id, backend)
        )
    return out


def run_matrix(
    adb: Adb,
    *,
    models: list[str] | None = None,
    backends: list[str] | None = None,
    image_set: str = "eval15",
    image_names: list[str] | None = None,
    out_root: str | Path,
    timeout: float = TIMEOUT_S,
    poll_interval: float = POLL_INTERVAL_S,
    sleep=time.sleep,
) -> list[Path]:
    """Run every model x backend combo sequentially. Returns out dirs."""
    root = Path(out_root)
    done: list[Path] = []
    for model_id in models or MODELS:
        for backend in backends or BACKENDS:
            combo = model_id if backend == "cpu" else model_id + "-" + backend
            done.append(
                run_combo(
                    adb,
                    model_id=model_id,
                    backend=backend,
                    image_set=image_set,
                    image_names=image_names,
                    out_dir=root / combo,
                    timeout=timeout,
                    poll_interval=poll_interval,
                    sleep=sleep,
                )
            )
    return done
