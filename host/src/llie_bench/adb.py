"""Thin, testable ADB wrapper.

Every invocation is an argument list passed to an injectable runner; there is
no shell string anywhere in this module. Failures raise AdbError, which keeps
the command and stderr for diagnosis but redacts the device serial so that
messages can be pasted into public reports.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Sequence

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def _redact(command: Sequence[str]) -> list[str]:
    redacted: list[str] = []
    hide_next = False
    for token in command:
        if hide_next:
            redacted.append("[serial]")
            hide_next = False
            continue
        redacted.append(token)
        if token == "-s":
            hide_next = True
    return redacted


class AdbError(RuntimeError):
    """ADB failure carrying the (serial-redacted) command and its stderr."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
        reason: str = "",
    ) -> None:
        self.command = list(command)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        parts = ["adb command failed: " + " ".join(_redact(self.command))]
        if returncode is not None:
            parts.append(f"exit code {returncode}")
        if reason:
            parts.append("reason: " + reason)
        if stderr.strip():
            parts.append("stderr: " + stderr.strip())
        super().__init__("\n".join(parts))


def _default_runner(command: list[str], *, timeout: float | None = None):
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


class Adb:
    def __init__(
        self,
        runner: Runner | None = None,
        serial: str | None = None,
        adb_path: str = "adb",
        timeout: float = 60.0,
    ) -> None:
        self._runner = runner if runner is not None else _default_runner
        self.serial = serial
        self.adb_path = adb_path
        self.timeout = timeout

    def _command(self, *args: str, scoped: bool = True) -> list[str]:
        command = [self.adb_path]
        if scoped and self.serial:
            command += ["-s", self.serial]
        command += list(args)
        return command

    def _run(self, *args: str, scoped: bool = True) -> str:
        command = self._command(*args, scoped=scoped)
        try:
            completed = self._runner(command, timeout=self.timeout)
        except FileNotFoundError as exc:
            raise AdbError(command, reason=str(exc)) from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(command, reason=f"timed out after {self.timeout}s") from exc
        if completed.returncode != 0:
            raise AdbError(
                command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return completed.stdout

    def devices(self) -> list:
        from .device import parse_devices

        text = self._run("devices", "-l", scoped=False)
        return parse_devices(text)

    def shell(self, *args: str) -> str:
        return self._run("shell", *args)

    def getprop(self, key: str) -> str:
        return self.shell("getprop", key).strip()

    def install(self, apk: str | Path) -> None:
        self._run("install", "-r", str(apk))

    def push(self, local: str | Path, remote: str) -> None:
        self._run("push", str(local), remote)

    def pull(self, remote: str, local: str | Path) -> None:
        self._run("pull", remote, str(local))

    def start_benchmark(
        self,
        model_id: str,
        image_set: str = "eval15",
        backend: str = "cpu",
        image_names: list[str] | None = None,
    ) -> None:
        """Kick off one on-device batch run; timing happens on the phone.

        image_names, when given, is sent as an explicit ordered list so the
        app never depends on directory listing (which scoped storage can
        filter); missing names are recorded as per-image failures on-device.
        """
        extras: list[str] = [
            "am",
            "start",
            "-n",
            "org.llie.mobilebenchmark/.MainActivity",
            "-a",
            "org.llie.bench.RUN",
            "--es",
            "model_id",
            model_id,
            "--es",
            "image_set",
            image_set,
            "--es",
            "backend",
            backend,
        ]
        if image_names:
            extras += ["--es", "image_names", ",".join(image_names)]
        self._run("shell", *extras)
