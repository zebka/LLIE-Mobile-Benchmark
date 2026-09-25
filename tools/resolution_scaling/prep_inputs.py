"""Prepare LANCZOS-upscaled eval15 inputs and per-resolution manifests.

Latency-only artifacts for the resolution-scaling study. Writes:

  reports/resolution-scaling/inputs/<label>/<image>.png
  reports/resolution-scaling/compat/mobileie-6ch-<label>.manifest.json

Inputs are upscaled copies of the eval15 low images; they exist to change the
pixel count for latency scaling and are not meaningful for quality metrics.
Manifests are derived from the dynamic-axes source manifest
reports/compatibility/mobileie-6ch.manifest.json with input/output set to the
target size, so the same ONNX artifact can be pushed once per resolution as
models/mobileie-6ch-<label>.onnx.

Example:
  python tools/resolution_scaling/prep_inputs.py 1200x800
  python tools/resolution_scaling/prep_inputs.py 4032x3024 --subset 1.png 22.png 55.png
"""

import argparse
import json
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
LOW_DEFAULT = REPO.parent / "04_datasets" / "paired" / "eval15" / "low"
OUT = REPO / "reports" / "resolution-scaling"
BASE_MANIFEST = REPO / "reports" / "compatibility" / "mobileie-6ch.manifest.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("label", help="resolution label in WxH form, e.g. 1200x800")
    ap.add_argument("--low-dir", type=Path, default=LOW_DEFAULT, help="source image directory")
    ap.add_argument("--subset", nargs="+", help="restrict to these image file names")
    args = ap.parse_args()

    width, height = (int(v) for v in args.label.lower().split("x"))
    size = (width, height)
    low: Path = args.low_dir
    names = args.subset or sorted(p.name for p in low.glob("*.png"))
    if not names:
        raise SystemExit(f"no images found in {low}")

    dst_dir = OUT / "inputs" / args.label
    dst_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        im = Image.open(low / name).convert("RGB")
        if im.size != size:
            im = im.resize(size, Image.LANCZOS)
        im.save(dst_dir / name)

    mid = "mobileie-6ch-" + args.label
    manifest = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    manifest["model_id"] = mid
    manifest["artifact"] = mid + ".onnx"
    manifest["input"] = {"width": width, "height": height}
    manifest["output"] = {"width": width, "height": height}
    comp = OUT / "compat"
    comp.mkdir(parents=True, exist_ok=True)
    (comp / (mid + ".manifest.json")).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{args.label}: {len(names)} images -> {dst_dir}")
    print(f"manifest: {mid}")


if __name__ == "__main__":
    main()
