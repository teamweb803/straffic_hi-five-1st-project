from __future__ import annotations

import shutil
import subprocess


def check_jetson_runtime() -> dict[str, str]:
    result: dict[str, str] = {}
    result["tegrastats"] = "found" if shutil.which("tegrastats") else "missing"
    result["gst-launch-1.0"] = "found" if shutil.which("gst-launch-1.0") else "missing"
    result["python"] = "ok"
    try:
        import gi

        gi.require_version("Gst", "1.0")
        result["gi.Gst"] = "ok"
    except Exception as exc:
        result["gi.Gst"] = f"missing: {exc}"
    try:
        import pyds  # noqa: F401

        result["pyds"] = "ok"
    except Exception as exc:
        result["pyds"] = f"missing: {exc}"
    try:
        output = subprocess.check_output(["nvpmodel", "-q"], text=True, timeout=3)
        result["nvpmodel"] = output.strip().splitlines()[0] if output.strip() else "ok"
    except Exception as exc:
        result["nvpmodel"] = f"unavailable: {exc}"
    return result


if __name__ == "__main__":
    for key, value in check_jetson_runtime().items():
        print(f"{key}: {value}")

