"""크로스플랫폼 proto 생성 스크립트 (Windows/Mac/Linux 공용).

실행:
    python scripts/generate_proto.py

산출물:
    app/grpc_generated/tolling_pb2.py
    app/grpc_generated/tolling_pb2_grpc.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    proto_dir = root / "proto"
    out_dir = root / "app" / "grpc_generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "__init__.py").touch(exist_ok=True)

    proto_file = proto_dir / "tolling.proto"
    if not proto_file.exists():
        print(f"[ERR] {proto_file} 가 없습니다.", file=sys.stderr)
        return 1

    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
        str(proto_file),
    ]
    print("[run]", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return result.returncode

    # tolling_pb2_grpc.py 의 절대 import → 패키지 상대 import 로 패치
    grpc_file = out_dir / "tolling_pb2_grpc.py"
    if grpc_file.exists():
        text = grpc_file.read_text(encoding="utf-8")
        patched = re.sub(
            r"^import tolling_pb2",
            "from . import tolling_pb2",
            text,
            flags=re.MULTILINE,
        )
        grpc_file.write_text(patched, encoding="utf-8")

    print(f"[ok] generated → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
