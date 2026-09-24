"""Device discovery and profiling for public (serial-free) reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass

# getprop key -> DeviceProfile field
PROP_KEYS: dict[str, str] = {
    "model": "ro.product.model",
    "android_release": "ro.build.version.release",
    "android_sdk": "ro.build.version.sdk",
    "build_fingerprint": "ro.build.fingerprint",
    "soc": "ro.soc.model",
}


@dataclass(frozen=True)
class DeviceEntry:
    serial: str
    state: str
    model: str | None = None
    product: str | None = None
    transport_id: str | None = None


def parse_devices(text: str) -> list[DeviceEntry]:
    entries: list[DeviceEntry] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        extras: dict[str, str] = {}
        for token in parts[2:]:
            if ":" in token:
                key, value = token.split(":", 1)
                extras[key] = value
        entries.append(
            DeviceEntry(
                serial=serial,
                state=state,
                model=extras.get("model"),
                product=extras.get("product"),
                transport_id=extras.get("transport_id"),
            )
        )
    return entries


@dataclass(frozen=True)
class DeviceProfile:
    model: str
    android_release: str
    android_sdk: int
    build_fingerprint: str
    soc: str

    @classmethod
    def from_getprops(cls, values: dict[str, str]) -> "DeviceProfile":
        missing = [key for key in PROP_KEYS.values() if key not in values]
        if missing:
            raise ValueError("missing device properties: " + ", ".join(missing))
        return cls(
            model=values[PROP_KEYS["model"]],
            android_release=values[PROP_KEYS["android_release"]],
            android_sdk=int(values[PROP_KEYS["android_sdk"]]),
            build_fingerprint=values[PROP_KEYS["build_fingerprint"]],
            soc=values[PROP_KEYS["soc"]],
        )

    def to_public_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "android_release": self.android_release,
            "android_sdk": self.android_sdk,
            "build_fingerprint": self.build_fingerprint,
            "soc": self.soc,
        }

    def to_public_json(self) -> str:
        return json.dumps(self.to_public_dict(), indent=2, sort_keys=True)
