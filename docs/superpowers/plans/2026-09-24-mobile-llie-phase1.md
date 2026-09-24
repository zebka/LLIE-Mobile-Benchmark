# Phase 1: Nothing Phone 2a LLIE Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable Android app and ADB host runner that execute available LLIE models on the Nothing Phone (2a), save enhanced images, and report image quality and on-device cost for the review article.

**Architecture:** A native Android runner loads one standardized model artifact, processes still images locally, and records timings with the phone's monotonic clock. A Python host CLI uses ADB for setup, bulk transfer, invocation, and result collection; image-quality metrics run after inference on the host. CPU and supported accelerator runs are separate. This plan covers only the single-phone case study; the public three-device benchmark is a later project phase.

**Tech Stack:** Android Studio 2026.1.4.7 and Temurin JDK 21.0.12.101 (available through the installed winget source), Kotlin, Gradle Wrapper, Android SDK Platform Tools, Python 3.14.4, pytest 9.1.1, jsonschema 4.26.0, PyTorch 2.11.0, OpenCV 5.0.0, NumPy 2.5.2, scikit-image 0.26.0, Pillow 12.3.0, and LPIPS 0.1.4. ONNX Runtime and LiteRT are compatibility candidates; only the runtime that passes the model/device compatibility gate will be included in the initial app.

**Spec:** `LLIE/07_mobile_benchmark/design.md`

## Adaptation (2026-09-24): GitHub Actions instead of a local Android build

- User decision: do NOT install Android Studio/JDK/SDK on this machine. Every Gradle build and Kotlin unit test runs in GitHub Actions on `zebka/LLIE-Mobile-Benchmark`; the debug APK is downloaded from workflow artifacts.
- Task 1: the local `winget` JDK/Android Studio steps are cancelled. The phone/ADB steps stay local; Android platform-tools will be requested separately when the phone is connected.
- Verification gate: `.\gradlew.bat testDebugUnitTest assembleDebug` runs inside the `android` CI job. Host and compatibility pytest commands still run on this machine.
- Task order: Task 2 (contracts) and Task 3 (compatibility) come first; the Android project skeleton and its CI job are added with Task 4.

## Global Constraints

- Write project files only below `LLIE/07_mobile_benchmark/`; keep the archived IBDiff code, model weights, datasets, and prior benchmark results unchanged.
- Phase 1 uses the Nothing Phone (2a), still photographs, batch size 1, and a paired set only at its actual resolution.
- Measure inference inside the Android process with a monotonic clock; ADB must not run in the per-image timing loop.
- Report CPU and each supported accelerator backend separately.
- Report model file bytes, parameter count, and weight precision as distinct fields.
- Run quality evaluation after inference; reject reference image size mismatches instead of silently resizing them.
- Do not report phone battery estimates as official joules per image. Phase 1 energy is not an official benchmark result.
- Treat high-resolution images without valid paired references as stress-test inputs for runtime and memory only.
- Phase 1 results are a case study on one phone, not a cross-device leaderboard.

## File Structure

Create the following focused files under `LLIE/07_mobile_benchmark/`:

```text
android/
  gradlew
  gradlew.bat
  settings.gradle.kts
  build.gradle.kts
  gradle/wrapper/gradle-wrapper.jar
  gradle/wrapper/gradle-wrapper.properties
  gradle/libs.versions.toml
  app/build.gradle.kts
  app/src/main/AndroidManifest.xml
  app/src/main/java/org/llie/mobilebenchmark/MainActivity.kt
  app/src/main/java/org/llie/mobilebenchmark/model/ModelManifest.kt
  app/src/main/java/org/llie/mobilebenchmark/model/ModelEngine.kt
  app/src/main/java/org/llie/mobilebenchmark/model/RgbImage.kt
  app/src/main/java/org/llie/mobilebenchmark/model/SelectedRuntimeEngine.kt
  app/src/main/java/org/llie/mobilebenchmark/runner/BenchmarkConfig.kt
  app/src/main/java/org/llie/mobilebenchmark/runner/BenchmarkRunner.kt
  app/src/main/java/org/llie/mobilebenchmark/runner/LatencyStats.kt
  app/src/main/java/org/llie/mobilebenchmark/runner/RunResult.kt
  app/src/main/java/org/llie/mobilebenchmark/storage/ResultWriter.kt
  app/src/test/java/org/llie/mobilebenchmark/runner/LatencyStatsTest.kt
  app/src/test/java/org/llie/mobilebenchmark/model/ModelManifestTest.kt
host/
  pyproject.toml
  src/llie_bench/__init__.py
  src/llie_bench/cli.py
  src/llie_bench/adb.py
  src/llie_bench/device.py
  src/llie_bench/metrics.py
  src/llie_bench/report.py
  tests/test_device.py
  tests/test_metrics.py
  tests/test_report.py
tools/compatibility/
  README.md
  export_models.py
  test_export_parity.py
protocol/
  model-manifest.schema.json
  run-result.schema.json
models/README.md
reports/.gitkeep
reports/compatibility/
```

`ModelEngine` is the Android runtime boundary. Its public contract is `load(modelFile: File, manifest: ModelManifest)`, `infer(input: RgbImage): RgbImage`, and `close()`. `LatencyStats.summarize(samplesNs: List<Long>)` returns `LatencySummary(medianNs: Double, p95Ns: Long)` and rejects an empty list. On the host, `validate_manifest(payload: dict) -> None` and `validate_result(payload: dict) -> None` validate protocol data; `evaluate_pair(prediction: Path, reference: Path) -> dict[str, float]` computes image metrics. `SelectedRuntimeEngine` is the single adapter selected by the compatibility task; do not ship two unverified runtime implementations in the first phase. `BenchmarkRunner` owns the run protocol and `ResultWriter` owns the stable JSON output. The host package is split into ADB transport, device metadata, image metrics, and report generation.

## Task 1: Prepare Android Toolchain and Phone Connection

**Files:**
- Modify: `LLIE/07_mobile_benchmark/README.md` with the verified tool/device state
- Create: `LLIE/07_mobile_benchmark/reports/device-profile.json`

- [ ] Install the tested JDK and Android Studio package versions:

```powershell
winget install --id EclipseAdoptium.Temurin.21.JDK -e --version 21.0.12.101
winget install --id Google.AndroidStudio -e --version 2026.1.4.7
```

- [ ] Open Android Studio SDK Manager and install the current stable Android SDK platform, Android SDK Build-Tools, and Android SDK Platform-Tools. Record the installed versions in `README.md`.
- [ ] Enable Developer options and USB debugging on the Nothing Phone (2a), connect it over USB, and accept the computer authorization prompt.
- [ ] Verify the device and toolchain:

```powershell
java -version
adb version
adb devices -l
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb shell getprop ro.build.fingerprint
adb shell getprop ro.soc.model
adb shell getprop ro.board.platform
```

- [ ] Write the returned phone model, build, Android release/API, SoC string when available, and date to `reports/device-profile.json`; do not include the ADB serial number in published reports.
- [ ] Run the same commands again after disconnect/reconnect. Expected: the phone remains `device` (not `unauthorized` or `offline`) and reports the same build properties.

## Task 2: Define Model and Result Contracts

**Files:**
- Create: `protocol/model-manifest.schema.json`
- Create: `protocol/run-result.schema.json`
- Create: `host/pyproject.toml`
- Create: `host/tests/test_report.py`
- Create: `host/src/llie_bench/report.py`

- [ ] Create `host/pyproject.toml` with the `src` package layout, `[tool.pytest.ini_options] pythonpath = ["src"]`, `jsonschema==4.26.0` as a runtime dependency, `pytest==9.1.1` in the `test` extra, the pinned image-metric dependencies from the Tech Stack in the `metrics` extra, and `llie-bench = "llie_bench.cli:main"` as the console entry point.
- [ ] Install the schema/test dependencies with `python -m pip install jsonschema==4.26.0 pytest==9.1.1` from `LLIE/07_mobile_benchmark/host`; the image-metric dependencies are already present in the current Python environment.
- [ ] Write failing schema tests for a valid manifest and for missing `model_id`, `artifact`, `input`, `output`, `precision`, and `preprocessing` fields. The manifest must also declare RGB channel order, input range, tensor layout, output range, and any tiling parameters.

```python
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

def test_manifest_requires_input_and_output_fields():
    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "protocol/model-manifest.schema.json").read_text())
    with pytest.raises(ValidationError):
        validate(instance={"model_id": "demo", "artifact": "demo.onnx"}, schema=schema)
```

- [ ] Run `python -m pytest tests/test_report.py -q` from `LLIE/07_mobile_benchmark/host`. Expected: FAIL because the schema file does not exist yet.
- [ ] Define the result schema with `model_id`, SHA-256 artifact hash, device profile (excluding serial), Android build, runtime/version, backend, precision, image IDs, warm-up count, load time, per-image model/end-to-end nanoseconds, PSS samples/peak, thermal status, output paths, and explicit `success`/`failure_reason` fields.
- [ ] Implement report validation and JSON/CSV serialization in `report.py`; invalid or incomplete runs must fail validation rather than silently produce leaderboard rows.
- [ ] Install the host package in editable mode after `src/llie_bench/` and its `__init__.py` exist so the CLI uses the same import path as tests: from `LLIE/07_mobile_benchmark/host`, run `python -m pip install -e ".[test,metrics]"`.
- [ ] Re-run `python -m pytest tests/test_report.py -q` from `LLIE/07_mobile_benchmark/host`. Expected: PASS for valid inputs and explicit validation errors for invalid inputs.

## Task 3: Choose the Runtime with a Two-Model Compatibility Test

**Files:**
- Create: `tools/compatibility/README.md`
- Create: `tools/compatibility/export_models.py`
- Create: `tools/compatibility/test_export_parity.py`
- Create: `models/README.md`
- Create: `reports/runtime-decision.md`

**Inputs already in the archive:**
- Zero-DCE model: `LLIE/02_code/IBDiff/thirdparty/Zero-DCE/Zero-DCE_code/model.py`
- Zero-DCE weights: `LLIE/03_models/thirdparty-weights/ZeroDCE-snapshots/Epoch99.pth`
- SCI CVPR model: `LLIE/02_code/IBDiff/thirdparty/SCI/CVPR/model.py`
- SCI medium weights: `LLIE/03_models/thirdparty-weights/SCI-weights/medium.pt`

- [ ] Add a parity test that loads Zero-DCE and SCI medium in PyTorch, feeds the same fixed RGB `[0,1]` image tensor, and checks that outputs are finite, retain the expected spatial size, and stay in the documented output range.
- [ ] Run `python -m pytest tools/compatibility/test_export_parity.py -q`. Expected: FAIL before the wrappers and fixtures are added.
- [ ] Attempt ONNX export and LiteRT export for both models using their maintained PyTorch export paths. A missing exporter, unsupported operator, or failed conversion is recorded as a failed candidate, not hidden. Save generated artifacts only under `reports/compatibility/`, not beside archived checkpoints.
- [ ] Add a provisional runtime decision table to `reports/runtime-decision.md`: exporter availability, model export success, host CPU output parity, artifact size, and output error versus PyTorch. Phone load and accelerator support are confirmed after the Android runner exists in Task 4.
- [ ] Select one provisional runtime only if both models export and their float32 outputs differ from the PyTorch reference by at most `1e-3` maximum absolute error on the fixed parity input. If the Nothing Phone (2a) cannot load either model with that runtime in Task 4, switch to the next candidate that passed host parity or mark the model/runtime unsupported.
- [ ] Run `python -m pytest tools/compatibility/test_export_parity.py -q`. Expected: PASS for all supported exported artifacts; unsupported exports are marked explicitly with the converter/runtime error.

## Task 4: Build the Android Runner and Deterministic Timing Core

**Files:**
- Create: `android/settings.gradle.kts`
- Create: `android/build.gradle.kts`
- Create: `android/gradle/libs.versions.toml`
- Create: `android/app/build.gradle.kts`
- Create: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/src/main/java/org/llie/mobilebenchmark/MainActivity.kt`
- Create: `android/app/src/main/java/org/llie/mobilebenchmark/model/ModelManifest.kt`
- Create: `android/app/src/main/java/org/llie/mobilebenchmark/model/ModelEngine.kt`
- Create: `android/app/src/main/java/org/llie/mobilebenchmark/model/RgbImage.kt`
- Create: `android/app/src/main/java/org/llie/mobilebenchmark/model/SelectedRuntimeEngine.kt`
- Create: `android/app/src/main/java/org/llie/mobilebenchmark/runner/BenchmarkConfig.kt`
- Create: `android/app/src/main/java/org/llie/mobilebenchmark/runner/BenchmarkRunner.kt`
- Create: `android/app/src/main/java/org/llie/mobilebenchmark/runner/LatencyStats.kt`
- Create: `android/app/src/main/java/org/llie/mobilebenchmark/runner/RunResult.kt`
- Create: `android/app/src/main/java/org/llie/mobilebenchmark/storage/ResultWriter.kt`
- Create: `android/app/src/test/java/org/llie/mobilebenchmark/runner/LatencyStatsTest.kt`
- Create: `android/app/src/test/java/org/llie/mobilebenchmark/model/ModelManifestTest.kt`
- Modify: `reports/runtime-decision.md` with on-device compatibility results

- [ ] Write failing tests for manifest parsing and percentile calculation. `LatencyStats.summarize` must return a median and nearest-rank p95 from a non-empty list of nanosecond samples, and reject an empty list.

```kotlin
@Test
fun summarizeUsesMedianAndNearestRankP95() {
    val summary = LatencyStats.summarize(listOf(1L, 2L, 3L, 4L))
    assertEquals(2.5, summary.medianNs, 0.0)
    assertEquals(4L, summary.p95Ns)
}
```

- [ ] Run `cd LLIE/07_mobile_benchmark/android; .\gradlew.bat testDebugUnitTest`. Expected: FAIL until the app and tested classes exist.
- [ ] Create a native Kotlin Android app with a simple screen to select a model, backend, and image set, start/stop a run, and export its report. Use Android's Storage Access Framework for standalone file selection and the app-specific external files directory for ADB-pushed files. Use the runtime selected in Task 3 through `ModelEngine`.
- [ ] Implement `BenchmarkRunner` with batch size 1, five warm-up inferences, three measured passes over each selected image, and timings from `SystemClock.elapsedRealtimeNanos()` inside the app. Record model load time separately.
- [ ] Measure PSS in a separate memory pass so memory sampling does not perturb latency. Sample thermal status before and after each measured pass. Record full-resolution OOM as an explicit failed run.
- [ ] Implement whole-image execution first. Add tiling only when a model cannot process the target resolution within device memory; record tile size and overlap in the manifest and include tiling/merge in end-to-end latency.
- [ ] Save output images and one schema-valid JSON run result to app-specific external files. Add a manual export/share action so the installed app can run without the host CLI.
- [ ] Run `cd LLIE/07_mobile_benchmark/android; .\gradlew.bat testDebugUnitTest assembleDebug`. Expected: PASS and a debug APK is created.
- [ ] Install and smoke-test on the Nothing Phone (2a): from the Android project directory run `adb install -r app\build\outputs\apk\debug\app-debug.apk`; push one image from `LLIE/04_datasets/paired/eval15/low` to `/sdcard/Android/data/org.llie.mobilebenchmark/files/images/`. Expected: app opens, lists CPU and any supported delegates, and processes the pushed image.
- [ ] Compare app output with the PyTorch output on the same fixed test image. If CPU inference fails to load or exceeds `1e-3` maximum absolute error, test the next host-compatible runtime candidate before freezing `SelectedRuntimeEngine`. Record phone load and available delegates in `reports/runtime-decision.md`.

## Task 5: Add the ADB Host Controller

**Files:**
- Create: `host/src/llie_bench/cli.py`
- Create: `host/src/llie_bench/adb.py`
- Create: `host/src/llie_bench/device.py`
- Create: `host/tests/test_device.py`
- Modify: `host/pyproject.toml`
- Modify: `LLIE/07_mobile_benchmark/README.md`

- [ ] Write tests against a fake ADB command runner for `doctor`, device property capture, app install, file push, run start, and file pull. ADB command failures must include the command and stderr in the error without printing private device serials in the public report.
- [ ] Run `python -m pytest tests/test_device.py -q` from `LLIE/07_mobile_benchmark/host`. Expected: FAIL before the ADB wrapper and CLI are implemented.
- [ ] Implement `adb.py` around `subprocess.run` with an argument list (never a shell string), timeout, exit-code check, and injectable command runner for tests.
- [ ] Implement `device.py` to parse `adb devices -l` and the `getprop` values from Task 1 into the device profile.
- [ ] Implement `llie-bench doctor`, `install`, `push`, `run`, and `collect` commands. `run` sends one batch command to the app; it must not time individual image calls over ADB.
- [ ] Run `python -m pytest tests/test_device.py -q` from `LLIE/07_mobile_benchmark/host`. Expected: PASS with the fake ADB runner.
- [ ] Connect the real device and, from `LLIE/07_mobile_benchmark/host`, run `python -m llie_bench.cli doctor`. Expected: one authorized Nothing Phone (2a) and matching Android build metadata.

## Task 6: Compute Reference Metrics and Generate the Case-Study Report

**Files:**
- Create: `host/src/llie_bench/metrics.py`
- Create: `host/tests/test_metrics.py`
- Create: `reports/README.md`
- Modify: `host/src/llie_bench/cli.py`

- [ ] Write metric tests using small generated RGB arrays for exact-match PSNR/SSIM, an injected LPIPS stub returning a finite score, and rejection of shape/channel mismatches. The evaluator must never resize images silently and unit tests must not download pretrained weights.

```python
import numpy as np
import pytest
from PIL import Image
from llie_bench.metrics import evaluate_pair

def test_metrics_reject_different_shapes(tmp_path):
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(tmp_path / "pred.png")
    Image.fromarray(np.zeros((8, 9, 3), dtype=np.uint8)).save(tmp_path / "ref.png")
    with pytest.raises(ValueError, match="shape mismatch"):
        evaluate_pair(tmp_path / "pred.png", tmp_path / "ref.png")
```

- [ ] Run `python -m pytest tests/test_metrics.py -q` from `LLIE/07_mobile_benchmark/host`. Expected: FAIL before metric functions are implemented.
- [ ] Implement PSNR, SSIM, and LPIPS evaluation on the host, outside the Android timing interval. Reuse the pinned research environment versions already present in the workspace; do not edit `02_code/IBDiff/src/evaluate.py`.
- [ ] Match predictions and ground truth by image stem, require identical dimensions, save one row per image/metric to CSV, and report mean and standard deviation for valid pairs.
- [ ] Mark images with no paired reference as `runtime_only`; do not score them with full-reference metrics.
- [ ] Run `python -m pytest tests/test_metrics.py -q` from `LLIE/07_mobile_benchmark/host`. Expected: PASS, including explicit failures on invalid image pairs.

## Task 7: Run the End-to-End Phone Study and Freeze the Phase-1 Protocol

**Files:**
- Create: `reports/phase1-nothing-phone-2a.md`
- Create: `reports/phase1-results/`
- Modify: `LLIE/07_mobile_benchmark/README.md`
- Modify: `LLIE/07_mobile_benchmark/design.md`

- [ ] Run the paired low-resolution validation set at `LLIE/04_datasets/paired/eval15/low` through PyTorch and the selected Android runtime for Zero-DCE and SCI medium; compare output parity before interpreting image metrics against `LLIE/04_datasets/paired/eval15/high`.
- [ ] Run a separate high-resolution stress set from genuine Nothing Phone (2a)-sized photos or a licensed full-resolution set. Keep private photos outside published artifacts. If no paired ground truth is licensed and aligned, report only latency, memory, backend, and completion/failure for that set.
- [ ] Run the full protocol separately on CPU and each supported accelerator. Capture model and end-to-end latency distributions, model load time, PSS pass, thermal state, artifact bytes, precision, output quality, and unsupported/OOM events.
- [ ] Re-run the same study after a cool-down. Expected: schema-valid reports, same model/input hashes, and complete outputs for all successful runs.
- [ ] Generate CSV and Markdown summary from the saved JSON and images. Verify every metric is traceable to an image ID and every runtime result records exact phone/build/runtime/backend.
- [ ] Update README and design status with measured environment and limitations; do not label the single-device result a public benchmark leaderboard.

## Verification Gate

The phase is complete only when `testDebugUnitTest assembleDebug` passes from `LLIE/07_mobile_benchmark/android`, `python -m pytest tests -q` passes from `LLIE/07_mobile_benchmark/host`, `python -m pytest tools/compatibility -q` passes from `LLIE/07_mobile_benchmark`, the APK installs on the Nothing Phone (2a), and the end-to-end report can be regenerated from saved JSON and images. Run Gradle as `.\gradlew.bat testDebugUnitTest assembleDebug` from the Android project directory.
