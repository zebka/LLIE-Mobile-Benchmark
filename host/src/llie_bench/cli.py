"""Host-side CLI: doctor / install / push / run / collect.

`run` sends exactly one batch command to the device; all timing stays on the
phone (SystemClock in the app). Nothing here ever prints a device serial.
"""

from __future__ import annotations

import argparse
import os
import sys

from .adb import Adb, AdbError, Runner
from .device import DeviceProfile, PROP_KEYS


def _adb(runner: Runner | None, serial: str | None) -> Adb:
    return Adb(runner=runner, serial=serial or os.environ.get("ANDROID_SERIAL") or None)


def _discover_serial(adb: Adb) -> str:
    devices = adb.devices()
    authorized = [d for d in devices if d.state == "device"]
    unauthorized = [d for d in devices if d.state == "unauthorized"]
    if not authorized:
        if unauthorized:
            raise AdbError(
                ["adb", "devices", "-l"],
                stderr="device unauthorized: accept the USB debugging prompt on the phone",
            )
        raise AdbError(["adb", "devices", "-l"], stderr="no device found; connect the phone with USB debugging enabled")
    return authorized[0].serial


def _doctor(args: argparse.Namespace, runner: Runner | None) -> int:
    probe = _adb(runner, args.serial)
    serial = _discover_serial(probe)
    adb = _adb(runner, serial)
    values = {key: adb.getprop(key) for key in PROP_KEYS.values()}
    profile = DeviceProfile.from_getprops(values)
    print(profile.to_public_json())
    return 0


def _install(args: argparse.Namespace, runner: Runner | None) -> int:
    serial = args.serial or _discover_serial(_adb(runner, None))
    _adb(runner, serial).install(args.apk)
    print(f"installed {args.apk}")
    return 0


def _push(args: argparse.Namespace, runner: Runner | None) -> int:
    serial = args.serial or _discover_serial(_adb(runner, None))
    _adb(runner, serial).push(args.local, args.remote)
    print(f"pushed {args.local} -> {args.remote}")
    return 0


def _run(args: argparse.Namespace, runner: Runner | None) -> int:
    # Exactly one batch command; no per-image timing crosses ADB.
    _adb(runner, args.serial).start_benchmark(model_id=args.model, image_set=args.image_set)
    print(f"started on-device batch run for {args.model}")
    return 0


def _collect(args: argparse.Namespace, runner: Runner | None) -> int:
    serial = args.serial or _discover_serial(_adb(runner, None))
    _adb(runner, serial).pull(args.remote, args.local)
    print(f"pulled {args.remote} -> {args.local}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="llie-bench", description="LLIE mobile benchmark host controller")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="verify ADB and print the device profile (no serial)")
    p_doctor.add_argument("--serial", default=None)

    p_install = sub.add_parser("install", help="install the benchmark APK")
    p_install.add_argument("apk")
    p_install.add_argument("--serial", default=None)

    p_push = sub.add_parser("push", help="push files (models, manifests) to the device")
    p_push.add_argument("local")
    p_push.add_argument("remote")
    p_push.add_argument("--serial", default=None)

    p_run = sub.add_parser("run", help="start one on-device batch run (single ADB command)")
    p_run.add_argument("--model", required=True)
    p_run.add_argument("--image-set", default="eval15")
    p_run.add_argument("--serial", default=None)

    p_collect = sub.add_parser("collect", help="pull run results back from the device")
    p_collect.add_argument("remote")
    p_collect.add_argument("local")
    p_collect.add_argument("--serial", default=None)
    return parser


def main(argv: list[str] | None = None, *, runner: Runner | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "doctor": _doctor,
        "install": _install,
        "push": _push,
        "run": _run,
        "collect": _collect,
    }
    try:
        return handlers[args.command](args, runner)
    except (AdbError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
