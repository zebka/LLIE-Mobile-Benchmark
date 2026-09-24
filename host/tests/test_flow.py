"""Tests for the one-command flow (setup / benchmark / matrix / report).

Uses scripted fake runners: every adb invocation must be an argument list
(never a shell string), status polling tolerates a missing file, and a
materializing runner stands in for `adb pull` by writing canned files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llie_bench.adb import Adb, AdbError

SERIAL = "TESTSERIAL123"

DEVICES_L_OUTPUT = """List of devices attached
TESTSERIAL123               device product:NR1234 model:Nothing_Phone_2a device:NR1 transport_id:7
"""


class _Completed:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRunner:
    def __init__(self):
        self.calls: list[list[str]] = []
        self.responses: dict[tuple[str, ...], tuple[int, str, str]] = {}
        self.default = (0, "", "")

    def queue(self, command, *, returncode=0, stdout="", stderr=""):
        self.responses[tuple(command)] = (returncode, stdout, stderr)

    def __call__(self, command, *, timeout=None):
        assert isinstance(command, list), "adb must be invoked with an argument list"
        self.calls.append(list(command))
        code, out, err = self.responses.get(tuple(command), self.default)
        return _Completed(code, out, err)


def _canned_result(model_id="zero-dce", backend="cpu"):
    return {
        "model_id": model_id,
        "artifact_sha256": "a" * 64,
        "device": {
            "model": "A142",
            "android_release": "16",
            "android_sdk": 36,
            "build_fingerprint": "Nothing/Pacman:16/test",
            "soc": "MT6886",
        },
        "runtime": {"name": "onnxruntime", "version": "1.19.2"},
        "backend": backend,
        "precision": "float32",
        "image_ids": ["1.png", "2.png"],
        "warmup_count": 5,
        "load_time_ns": 1000,
        "images": [
            {"image_id": "1.png", "model_ns": [1000, 1100], "e2e_ns": [1200, 1300]},
            {"image_id": "2.png", "model_ns": [1000, 1100], "e2e_ns": [1200, 1300]},
        ],
        "pss": {"samples_mb": [10.0], "peak_mb": 10.0},
        "thermal": {"before": "light", "after": "light"},
        "output_paths": ["outputs/1.png", "outputs/2.png"],
        "success": True,
    }


class MaterializingRunner(FakeRunner):
    """Fake device: status flips running->done; pull writes canned files."""

    def __init__(self, model_id="zero-dce", backend="cpu", outputs_dir="outputs"):
        super().__init__()
        self.model_id = model_id
        self.backend = backend
        self.outputs_dir = outputs_dir
        self.status_reads = 0
        self.queue(["adb", "devices", "-l"], stdout=DEVICES_L_OUTPUT)

    def __call__(self, command, *, timeout=None):
        assert isinstance(command, list), "adb must be invoked with an argument list"
        self.calls.append(list(command))
        if command[-2:] == ["devices", "-l"]:
            return _Completed(0, DEVICES_L_OUTPUT, "")
        # status polling: first read missing, then running, then done
        if "cat" in command:
            self.status_reads += 1
            if self.status_reads == 1:
                return _Completed(1, "", "No such file")
            if self.status_reads == 2:
                return _Completed(0, "running\n", "")
            return _Completed(0, "done\n", "")
        if "ls" in command:
            return _Completed(
                0,
                "outputs\noutputs-nnapi\noutputs-zero-dce\noutputs-zero-dce-nnapi\n",
                "",
            )
        if "pull" in command:
            remote, local = command[-2], command[-1]
            dest = Path(local)
            if remote.endswith(".status"):
                dest.write_text("done\n", encoding="utf-8")
            elif remote.endswith("-run.json"):
                dest.write_text(json.dumps(_canned_result(self.model_id, self.backend)), encoding="utf-8")
            else:  # outputs dir pull
                dest.mkdir(parents=True, exist_ok=True)
                from PIL import Image

                for name in ("1.png", "2.png"):
                    Image.new("RGB", (4, 4), (10, 20, 30)).save(dest / name)
            return _Completed(0, "", "")
        return _Completed(0, "", "")


def test_naming_helpers():
    from llie_bench.flow import candidate_outputs_dirs, result_name, status_name, suffix

    assert suffix("cpu") == ""
    assert suffix("nnapi") == "-nnapi"
    assert result_name("zero-dce", "cpu") == "zero-dce-run.json"
    assert result_name("zero-dce", "nnapi") == "zero-dce-nnapi-run.json"
    assert status_name("sci-medium", "xnnpack") == "sci-medium-xnnpack.status"
    assert candidate_outputs_dirs("zero-dce", "nnapi") == [
        "outputs-zero-dce-nnapi",
        "outputs-nnapi",
    ]
    assert candidate_outputs_dirs("zero-dce", "cpu") == ["outputs-zero-dce", "outputs"]


def test_prime_outputs_uses_arg_lists():
    runner = FakeRunner()
    adb = Adb(runner=runner, serial=SERIAL)
    from llie_bench.flow import prime_outputs

    prime_outputs(adb, "outputs-nnapi", ["1.png", "2.png"])
    verbs = [c[4] for c in runner.calls]
    assert verbs == ["mkdir", "rm", "touch", "chmod"]
    # no shell metacharacters anywhere: pure argument lists
    for call in runner.calls:
        assert all(";" not in token and ">" not in token for token in call)
    assert runner.calls[-1][:4] == ["adb", "-s", SERIAL, "shell"]


def test_wait_status_done_failed_timeout():
    from llie_bench.flow import wait_status

    runner = FakeRunner()
    adb = Adb(runner=runner, serial=SERIAL)
    runner.queue(
        ["adb", "-s", SERIAL, "shell", "cat", "s.status"], stdout="done\n"
    )
    assert wait_status(adb, "s.status", sleep=lambda s: None) == "done"

    runner2 = FakeRunner()
    adb2 = Adb(runner=runner2, serial=SERIAL)
    runner2.queue(
        ["adb", "-s", SERIAL, "shell", "cat", "s.status"], stdout="failed\n"
    )
    assert wait_status(adb2, "s.status", sleep=lambda s: None) == "failed"

    runner3 = FakeRunner()
    adb3 = Adb(runner=runner3, serial=SERIAL)
    runner3.queue(
        ["adb", "-s", SERIAL, "shell", "cat", "s.status"], stdout="running\n"
    )
    with pytest.raises(TimeoutError):
        wait_status(adb3, "s.status", timeout=0.01, poll_interval=0.001, sleep=lambda s: None)


def test_wait_status_tolerates_missing_file():
    from llie_bench.flow import wait_status

    runner = FakeRunner()
    adb = Adb(runner=runner, serial=SERIAL)
    runner.queue(
        ["adb", "-s", SERIAL, "shell", "cat", "s.status"],
        returncode=1,
        stderr="No such file",
    )
    with pytest.raises(TimeoutError):
        wait_status(adb, "s.status", timeout=0.01, poll_interval=0.001, sleep=lambda s: None)
    assert len(runner.calls) >= 1


def test_discover_outputs_dir_prefers_new_naming():
    from llie_bench.flow import discover_outputs_dir

    runner = FakeRunner()
    adb = Adb(runner=runner, serial=SERIAL)
    from llie_bench.flow import REMOTE_RESULTS

    runner.queue(
        ["adb", "-s", SERIAL, "shell", "ls", REMOTE_RESULTS],
        stdout="outputs-nnapi\noutputs-zero-dce-nnapi\n",
    )
    assert discover_outputs_dir(adb, "zero-dce", "nnapi") == "outputs-zero-dce-nnapi"

    runner2 = FakeRunner()
    adb2 = Adb(runner=runner2, serial=SERIAL)
    runner2.queue(
        ["adb", "-s", SERIAL, "shell", "ls", REMOTE_RESULTS], stdout="outputs-nnapi\n"
    )
    assert discover_outputs_dir(adb2, "zero-dce", "nnapi") == "outputs-nnapi"

    runner3 = FakeRunner()
    adb3 = Adb(runner=runner3, serial=SERIAL)
    runner3.queue(
        ["adb", "-s", SERIAL, "shell", "ls", REMOTE_RESULTS], stdout="other\n"
    )
    with pytest.raises(ValueError):
        discover_outputs_dir(adb3, "zero-dce", "nnapi")


def test_setup_device_pushes_everything(tmp_path):
    from llie_bench.flow import setup_device

    compat = tmp_path / "compat"
    compat.mkdir()
    for model_id in ("zero-dce", "sci-medium"):
        (compat / (model_id + ".onnx")).write_bytes(b"onnx")
        (compat / (model_id + ".manifest.json")).write_text("{}", encoding="utf-8")
    images = tmp_path / "images"
    images.mkdir()
    from PIL import Image

    Image.new("RGB", (4, 4)).save(images / "1.png")
    Image.new("RGB", (4, 4)).save(images / "2.png")

    runner = FakeRunner()
    adb = Adb(runner=runner, serial=SERIAL)
    counts = setup_device(adb, compat_dir=compat, images_dir=images)
    assert counts == {"models": 2, "images": 2}
    pushes = [c for c in runner.calls if "push" in c]
    assert len(pushes) == 2 + 2 + 2  # models + manifests + images


def test_setup_device_rejects_missing_artifact(tmp_path):
    from llie_bench.flow import setup_device

    runner = FakeRunner()
    adb = Adb(runner=runner, serial=SERIAL)
    with pytest.raises(ValueError, match="missing artifact"):
        setup_device(adb, compat_dir=tmp_path, images_dir=tmp_path)


def test_run_combo_end_to_end(tmp_path):
    from llie_bench.flow import run_combo

    runner = MaterializingRunner()
    adb = Adb(runner=runner, serial=SERIAL)
    out = run_combo(
        adb,
        model_id="zero-dce",
        backend="cpu",
        image_names=["1.png", "2.png"],
        out_dir=tmp_path / "zero-dce",
        poll_interval=0,
        sleep=lambda s: None,
    )
    assert (out / "run.json").is_file()
    assert (out / "status.txt").read_text(encoding="utf-8").strip() == "done"
    assert len(list((out / "outputs").glob("*.png"))) == 2
    # force-stop first, exactly one batch start
    starts = [c for c in runner.calls if "am" in c and "start" in c]
    assert len(starts) == 1
    assert any("force-stop" in c for c in runner.calls)


def test_run_combo_rejects_failed_run(tmp_path):
    from llie_bench.flow import run_combo

    class FailingRunner(MaterializingRunner):
        def __call__(self, command, *, timeout=None):
            if "cat" in command:
                return _Completed(0, "failed\n", "")
            return super().__call__(command, timeout=timeout)

    runner = FailingRunner()
    adb = Adb(runner=runner, serial=SERIAL)
    with pytest.raises(RuntimeError, match="failed"):
        run_combo(
            adb,
            model_id="zero-dce",
            backend="cpu",
            out_dir=tmp_path / "x",
            poll_interval=0,
            sleep=lambda s: None,
        )


def test_run_matrix_runs_sequentially(tmp_path):
    from llie_bench.flow import run_matrix

    runner = MaterializingRunner()
    adb = Adb(runner=runner, serial=SERIAL)
    done = run_matrix(
        adb,
        models=["zero-dce"],
        backends=["cpu", "nnapi"],
        out_root=tmp_path,
        poll_interval=0,
        sleep=lambda s: None,
    )
    assert [p.name for p in done] == ["zero-dce", "zero-dce-nnapi"]
    starts = [c for c in runner.calls if "am" in c and "start" in c]
    assert len(starts) == 2


def _write_combo(root: Path, name: str, model_id: str, backend: str):
    combo = root / name
    combo.mkdir(parents=True)
    (combo / "run.json").write_text(json.dumps(_canned_result(model_id, backend)), encoding="utf-8")
    return combo


def test_reporting_builds_latency_without_ref(tmp_path):
    from llie_bench.reporting import build_report

    root = tmp_path / "results"
    root.mkdir()
    _write_combo(root, "zero-dce", "zero-dce", "cpu")
    _write_combo(root, "zero-dce-nnapi", "zero-dce", "nnapi")
    summary = build_report(root, None)
    assert summary["combos"] == ["zero-dce", "zero-dce-nnapi"]
    assert summary["metrics"] == []
    assert (root / "latency.csv").is_file()
    assert (root / "latency-summary.csv").is_file()
    assert (root / "zero-dce" / "latency.csv").is_file()
    assert not (root / "metrics-summary.json").exists()


def test_reporting_rejects_empty_tree(tmp_path):
    from llie_bench.reporting import build_report

    with pytest.raises(ValueError, match="no run.json"):
        build_report(tmp_path, None)


def test_cli_setup_benchmark_report(tmp_path, capsys):
    from llie_bench.cli import main

    compat = tmp_path / "compat"
    compat.mkdir()
    for model_id in ("zero-dce", "sci-medium"):
        (compat / (model_id + ".onnx")).write_bytes(b"onnx")
        (compat / (model_id + ".manifest.json")).write_text("{}", encoding="utf-8")
    images = tmp_path / "images"
    images.mkdir()
    from PIL import Image

    Image.new("RGB", (4, 4)).save(images / "1.png")

    setup_runner = FakeRunner()
    setup_runner.queue(["adb", "devices", "-l"], stdout=DEVICES_L_OUTPUT)
    code = main(
        ["setup", "--compat-dir", str(compat), "--images-dir", str(images)],
        runner=setup_runner,
    )
    assert code == 0
    assert "2 models, 1 images" in capsys.readouterr().out

    bench_runner = MaterializingRunner()
    code = main(
        [
            "benchmark", "--model", "zero-dce", "--backend", "cpu",
            "--out", str(tmp_path / "out"), "--poll-interval", "0",
        ],
        runner=bench_runner,
    )
    assert code == 0
    assert (tmp_path / "out" / "run.json").is_file()

    code = main(["report", "--results-dir", str(tmp_path / "out2")], runner=FakeRunner())
    assert code != 0  # empty tree
