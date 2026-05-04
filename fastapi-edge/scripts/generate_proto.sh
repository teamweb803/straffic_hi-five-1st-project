#!/usr/bin/env bash
# Protobuf → Python 코드 생성 스크립트
# 실행 후 app/grpc_generated/ 아래에 tolling_pb2.py, tolling_pb2_grpc.py 가 생성된다.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROTO_DIR="${ROOT_DIR}/proto"
OUT_DIR="${ROOT_DIR}/app/grpc_generated"

mkdir -p "${OUT_DIR}"
touch "${OUT_DIR}/__init__.py"

python -m grpc_tools.protoc \
  -I"${PROTO_DIR}" \
  --python_out="${OUT_DIR}" \
  --grpc_python_out="${OUT_DIR}" \
  "${PROTO_DIR}/tolling.proto"

# grpcio-tools 가 만든 import 경로(absolute) 를 패키지 내부 상대경로로 패치
# (Python 3 환경에서 grpc 코드 import 오류 회피)
sed -i.bak 's/^import tolling_pb2/from . import tolling_pb2/' "${OUT_DIR}/tolling_pb2_grpc.py"
rm -f "${OUT_DIR}/tolling_pb2_grpc.py.bak"

echo "Proto generated → ${OUT_DIR}"
