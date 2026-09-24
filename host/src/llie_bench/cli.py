"""Host-side CLI: doctor / install / push / run / collect / metrics,
plus the one-command flow: setup / benchmark / matrix / report.

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
    _adb(runner, args.serial).start_benchmark(
        model_id=args.model, image_set=args.image_set, backend=args.backend
    )
    print(f"started on-device batch run for {args.model} backend={args.backend}")
    return 0


def _collect(args: argparse.Namespace, runner: Runner | None) -> int:
    serial = args.serial or _discover_serial(_adb(runner, None))
    _adb(runner, serial).pull(args.remote, args.local)
    print(f"pulled {args.remote} -> {args.local}")
    return 0


def _metrics(args: argparse.Namespace, runner: Runner | None) -> int:
    import json

    from .metrics import aggregate, evaluate_folders, write_metrics_csv

    rows = evaluate_folders(args.pred, args.ref)
    if args.csv:
        write_metrics_csv(args.csv, rows)
        print(f"wrote {args.csv}")
    print(json.dumps({"images": len(rows), "aggregate": aggregate(rows)}, indent=2, sort_keys=True))
    return 0


def _setup(args: argparse.Namespace, runner: Runner | None) -> int:
    from .flow import setup_device

    serial = args.serial or _discover_serial(_adb(runner, None))
    counts = setup_device(
        _adb(runner, serial),
        compat_dir=args.compat_dir,
        images_dir=args.images_dir,
        image_set=args.image_set,
    )
    print(f"setup done: {counts['models']} models, {counts['images']} images (set {args.image_set})")
    return 0


def _benchmark(args: argparse.Namespace, runner: Runner | None) -> int:
    from .flow import run_combo

    serial = args.serial or _discover_serial(_adb(runner, None))
    out = run_combo(
        _adb(runner, serial),
        model_id=args.model,
        backend=args.backend,
        image_set=args.image_set,
        image_names=args.image_names.split(",") if args.image_names else None,
        out_dir=args.out,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )
    print(f"benchmark done: {args.model}/{args.backend} -> {out}")
    return 0


def _matrix(args: argparse.Namespace, runner: Runner | None) -> int:
    from .flow import run_matrix

    serial = args.serial or _discover_serial(_adb(runner, None))
    names = args.image_names.split(",") if args.image_names else None
    done = run_matrix(
        _adb(runner, serial),
        models=args.models.split(",") if args.models else None,
        backends=args.backends.split(",") if args.backends else None,
        image_set=args.image_set,
        image_names=names,
        out_root=args.out,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )
    for path in done:
        print(f"done -> {path}")
    return 0


def _report(args: argparse.Namespace, runner: Runner | None) -> int:
    import json

    from .reporting import build_report

    summary = build_report(args.results_dir, args.ref_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
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
    p_run.add_argument(
        "--backend",
        default="cpu",
        choices=["cpu", "gpu", "npu", "nnapi", "xnnpack"],
        help="execution provider label written into the result JSON",
    )
    p_run.add_argument("--serial", default=None)

    p_collect = sub.add_parser("collect", help="pull run results back from the device")
    p_collect.add_argument("remote")
    p_collect.add_argument("local")
    p_collect.add_argument("--serial", default=None)

    p_metrics = sub.add_parser("metrics", help="PSNR/SSIM/LPIPS for pulled outputs (host-side)")
    p_metrics.add_argument("--pred", required=True, help="directory of enhanced images")
    p_metrics.add_argument("--ref", required=True, help="directory of ground-truth images")
    p_metrics.add_argument("--csv", default=None, help="output CSV path (one row per image)")

    p_setup = sub.add_parser("setup", help="push models+manifests+images to the device in one go")
    p_setup.add_argument("--compat-dir", required=True, help="dir with <model>.onnx + <model>.manifest.json")
    p_setup.add_argument("--images-dir", required=True, help="dir with eval .png images")
    p_setup.add_argument("--image-set", default="eval15")
    p_setup.add_argument("--serial", default=None)

    p_bench = sub.add_parser("benchmark", help="run ONE model x backend batch, wait, pull results")
    p_bench.add_argument("--model", required=True)
    p_bench.add_argument("--backend", default="cpu", choices=["cpu", "gpu", "npu", "nnapi", "xnnpack"])
    p_bench.add_argument("--image-set", default="eval15")
    p_bench.add_argument("--image-names", default=None, help="comma-separated png names for placeholder priming")
    p_bench.add_argument("--out", required=True, help="local dir for run.json/status.txt/outputs/")
    p_bench.add_argument("--timeout", type=float, default=600.0)
    p_bench.add_argument("--poll-interval", type=float, default=5.0)
    p_bench.add_argument("--serial", default=None)

    p_matrix = sub.add_parser("matrix", help="run the full model x backend matrix sequentially")
    p_matrix.add_argument("--models", default=None, help="comma-separated (default: zero-dce,sci-medium)")
    p_matrix.add_argument("--backends", default=None, help="comma-separated (default: cpu,nnapi,xnnpack)")
    p_matrix.add_argument("--image-set", default="eval15")
    p_matrix.add_argument("--image-names", default=None)
    p_matrix.add_argument("--out", required=True, help="local root; one <model>[-<backend>] dir per combo")
    p_matrix.add_argument("--timeout", type=float, default=600.0)
    p_matrix.add_argument("--poll-interval", type=float, default=5.0)
    p_matrix.add_argument("--serial", default=None)

    p_report = sub.add_parser("report", help="build latency/metrics CSVs from a pulled results tree")
    p_report.add_argument("--results-dir", required=True)
    p_report.add_argument("--ref-dir", default=None, help="ground-truth dir; omit to skip quality metrics")
    return parser


def main(argv: list[str] | None = None, *, runner: Runner | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "doctor": _doctor,
        "install": _install,
        "push": _push,
        "run": _run,
        "collect": _collect,
        "metrics": _metrics,
        "setup": _setup,
        "benchmark": _benchmark,
        "matrix": _matrix,
        "report": _report,
    }
    try:
        return handlers[args.command](args, runner)
    except (AdbError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
