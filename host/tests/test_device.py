"""Tests for the ADB host controller against a fake command runner.

TDD: these tests FAIL until adb.py, device.py, and cli.py exist.

Invariants under test:
- every adb invocation is an argument list, never a shell string;
- ADB failures carry the command and stderr but redact the device serial;
- public doctor output never contains the device serial;
- `run` sends exactly one batch command (timing happens on-device);
- install/push/pull map to the expected adb verbs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

DEVICES_L_OUTPUT = """List of devices attached
24091PN22Y               device product:NR1234 model:Nothing_Phone_2a device:NR1 transport_id:7
"""

DEVICES_L_UNAUTHORIZED = """List of devices attached
24091PN22Y               unauthorized transport_id:7
"""

GETPROPS = {
    "ro.product.model": "Nothing Phone (2a)",
    "ro.build.version.release": "14",
    "ro.build.version.sdk": "34",
    "ro.build.fingerprint": "Nothing/2a/2a:14/UKQN1.240507.002/eng.root.2026:user/release-keys",
    "ro.soc.model": "Dimensity 7200 Pro",
}

SERIAL = "24091PN22Y"


class FakeRunner:
    """Scripted replacement for subprocess.run keyed by exact argv tuples."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.responses: dict[tuple[str, ...], tuple[int, str, str]] = {}
        self.default = (0, "", "")

    def queue(self, command: list[str], *, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.responses[tuple(command)] = (returncode, stdout, stderr)

    def __call__(self, command: list[str], *, timeout: float | None = None):
        assert isinstance(command, list), "adb must be invoked with an argument list"
        self.calls.append(list(command))
        code, out, err = self.responses.get(tuple(command), self.default)
        return _Completed(code, out, err)


class _Completed:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def runner() -> FakeRunner:
    r = FakeRunner()
    r.queue(["adb", "devices", "-l"], stdout=DEVICES_L_OUTPUT)
    for key, value in GETPROPS.items():
        r.queue(["adb", "-s", SERIAL, "shell", "getprop", key], stdout=value + "\n")
    return r


def test_devices_parses_serial_and_state():
    from llie_bench.device import parse_devices

    devices = parse_devices(DEVICES_L_OUTPUT)
    assert len(devices) == 1
    assert devices[0].serial == SERIAL
    assert devices[0].state == "device"
    assert devices[0].model == "Nothing_Phone_2a"


def test_devices_parse_marks_unauthorized():
    from llie_bench.device import parse_devices

    devices = parse_devices(DEVICES_L_UNAUTHORIZED)
    assert devices[0].state == "unauthorized"


def test_doctor_outputs_profile_without_serial(runner, capsys):
    from llie_bench.cli import main

    code = main(["doctor"], runner=runner)
    captured = capsys.readouterr()
    assert code == 0
    assert "Nothing Phone (2a)" in captured.out
    assert "Dimensity 7200 Pro" in captured.out
    assert SERIAL not in captured.out
    assert SERIAL not in captured.err


def test_doctor_fails_on_unauthorized_device(runner, capsys):
    from llie_bench.cli import main

    runner.queue(["adb", "devices", "-l"], stdout=DEVICES_L_UNAUTHORIZED)
    code = main(["doctor"], runner=runner)
    captured = capsys.readouterr()
    assert code != 0
    assert "unauthorized" in captured.err
    assert SERIAL not in captured.out


def test_adb_failure_carries_command_and_stderr_redacts_serial(runner):
    from llie_bench.adb import Adb, AdbError

    failing = ["adb", "-s", SERIAL, "shell", "getprop", "ro.product.model"]
    runner.queue(failing, returncode=1, stderr="boom: property not found")
    adb = Adb(runner=runner, serial=SERIAL)

    with pytest.raises(AdbError) as excinfo:
        adb.shell("getprop", "ro.product.model")

    message = str(excinfo.value)
    assert "boom: property not found" in message
    assert "getprop" in message
    assert SERIAL not in message
    assert "[serial]" in message
    assert excinfo.value.returncode == 1


def test_install_uses_argument_list(runner):
    from llie_bench.adb import Adb

    adb = Adb(runner=runner, serial=SERIAL)
    apk = "app-debug.apk"
    adb.install(apk)
    assert runner.calls[-1] == ["adb", "-s", SERIAL, "install", "-r", apk]


def test_push_and_pull_are_separate_verbs(runner):
    from llie_bench.adb import Adb

    adb = Adb(runner=runner, serial=SERIAL)
    adb.push("local/zero-dce.onnx", "/sdcard/zero-dce.onnx")
    assert runner.calls[-1] == ["adb", "-s", SERIAL, "push", "local/zero-dce.onnx", "/sdcard/zero-dce.onnx"]

    adb.pull("/sdcard/results/run.json", "local/run.json")
    assert runner.calls[-1] == ["adb", "-s", SERIAL, "pull", "/sdcard/results/run.json", "local/run.json"]


def test_run_sends_exactly_one_batch_command(runner):
    from llie_bench.adb import Adb

    runner.calls.clear()
    adb = Adb(runner=runner, serial=SERIAL)
    adb.start_benchmark(model_id="zero-dce")
    batch_calls = [c for c in runner.calls if "am" in c]
    assert len(batch_calls) == 1
    assert "start" in batch_calls[0]
    assert "zero-dce" in " ".join(batch_calls[0])


def test_run_sends_nothing_per_image(runner):
    """The run command must not time or iterate images over ADB."""
    from llie_bench.cli import main

    runner.calls.clear()
    code = main(["run", "--model", "zero-dce"], runner=runner)
    assert code == 0
    assert len(runner.calls) == 1


def test_run_passes_backend_extra(runner):
    from llie_bench.cli import main

    runner.calls.clear()
    code = main(
        ["run", "--model", "zero-dce", "--backend", "nnapi"], runner=runner
    )
    assert code == 0
    assert len(runner.calls) == 1
    assert "nnapi" in runner.calls[0]
    # backend is sent as its own --es pair
    idx = runner.calls[0].index("backend")
    assert runner.calls[0][idx + 1] == "nnapi"


def test_run_defaults_to_cpu_backend(runner):
    from llie_bench.cli import main

    runner.calls.clear()
    code = main(["run", "--model", "zero-dce"], runner=runner)
    assert code == 0
    assert "cpu" in runner.calls[0]


def test_profile_requires_all_props(runner):
    from llie_bench.device import DeviceProfile

    incomplete = {k: v for k, v in GETPROPS.items() if k != "ro.soc.model"}
    with pytest.raises(ValueError) as excinfo:
        DeviceProfile.from_getprops(incomplete)
    assert "ro.soc.model" in str(excinfo.value)


def test_profile_json_excludes_serial(runner):
    from llie_bench.device import DeviceProfile

    profile = DeviceProfile.from_getprops(GETPROPS)
    text = profile.to_public_json()
    assert SERIAL not in text
    assert '"model"' in text


def test_collect_pulls_results_directory(runner):
    from llie_bench.adb import Adb

    adb = Adb(runner=runner, serial=SERIAL)
    adb.pull("/sdcard/Android/data/org.llie.mobilebenchmark/files/results", "local/results")
    assert runner.calls[-1] == [
        "adb", "-s", SERIAL, "pull",
        "/sdcard/Android/data/org.llie.mobilebenchmark/files/results",
        "local/results",
    ]


def test_adb_missing_binary_reports_command(runner):
    from llie_bench.adb import Adb, AdbError

    def exploding(command, timeout=None):  # pragma: no cover - error path
        raise FileNotFoundError("adb not found")

    adb = Adb(runner=exploding, serial=SERIAL)
    with pytest.raises(AdbError) as excinfo:
        adb.devices()
    assert "adb not found" in str(excinfo.value)
    assert "devices" in str(excinfo.value)


def test_adb_enforces_timeout_argument(runner):
    from llie_bench.adb import Adb

    seen_timeouts: list[float | None] = []

    def recording_runner(command, *, timeout=None):
        seen_timeouts.append(timeout)
        return _Completed(0, "", "")

    adb = Adb(runner=recording_runner, serial=SERIAL, timeout=12.5)
    adb.shell("echo", "hi")
    assert seen_timeouts == [12.5]
