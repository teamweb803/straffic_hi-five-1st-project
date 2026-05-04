"""FastAPI 엣지 서버 기능 점검(스모크 테스트).

전제: `uvicorn app.main:app` 가 :8000 에서 떠 있어야 한다.
Spring Boot 백엔드가 떠있지 않아도 OK — gRPC 송신은 큐에서 재시도된다.

검증 시나리오
-------------
1. /healthz  : 서버가 살아 있는지
2. /v1/gps/lane/{lane_id} : GPS 캐시 푸시
3. /v1/yolo/detections (1차) : 통과선 위쪽에서 검출 → crossed=False 여야 함
4. /v1/yolo/detections (2차) : 같은 트랙이 통과선 아래로 → crossed=True 여야 함
5. /v1/yolo/detections (저신뢰 OCR) : confidence < 0.7 → 이벤트는 단건 RPC 로 분리됨

성공 기준: 1~4 단계의 응답이 기대값과 일치하면 PASS.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "http://localhost:8000"


def post(path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def get(path: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.URLError as e:
        print(f"[FATAL] FastAPI 서버에 접근할 수 없습니다: {e}")
        sys.exit(1)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_detection(track_id: int, cy: float, *, plate_conf: float = 0.92) -> dict:
    return {
        "track_id": track_id,
        "lane_id": "LANE-A-1",
        "frame_index": int(time.time() * 30) % 100000,
        "captured_at": now_iso(),
        "bbox": {"x": 910.0, "y": cy - 50, "w": 100.0, "h": 100.0},
        "vehicle_type": "passenger",
        "vehicle_type_confidence": 0.95,
        "plate_text": "12가3456",
        "plate_confidence": plate_conf,
    }


def expect(label: str, actual, expected) -> bool:
    ok = actual == expected
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}: expected={expected} actual={actual}")
    return ok


def main() -> int:
    failures = 0

    # 1) /healthz
    print("\n# Step 1: /healthz")
    status, body = get("/healthz")
    failures += 0 if expect("status", status, 200) else 1
    failures += 0 if expect("body", body, {"status": "ok"}) else 1

    # 2) GPS 푸시
    print("\n# Step 2: GPS 푸시 (/v1/gps/lane/LANE-A-1)")
    status, _ = post("/v1/gps/lane/LANE-A-1", {
        "latitude": 37.5665, "longitude": 126.9780,
        "speed_kmh": 78.4, "heading": 92.1,
        "captured_at": now_iso(),
    })
    failures += 0 if expect("status", status, 200) else 1

    # 3) YOLO 1차 (통과선=540, y=400 → 위쪽)
    print("\n# Step 3: YOLO 1차 (통과선 위쪽)")
    status, body = post("/v1/yolo/detections", {
        "edge_node_id": "EDGE-LOCAL-01",
        "detections": [make_detection(track_id=9001, cy=400)],
    })
    failures += 0 if expect("status", status, 202) else 1
    failures += 0 if expect("crossed (1차)", body.get("crossed"), 0) else 1

    # 4) YOLO 2차 (같은 트랙이 y=600 → 아래쪽으로 통과)
    print("\n# Step 4: YOLO 2차 (통과선 통과)")
    status, body = post("/v1/yolo/detections", {
        "edge_node_id": "EDGE-LOCAL-01",
        "detections": [make_detection(track_id=9001, cy=600)],
    })
    failures += 0 if expect("status", status, 202) else 1
    failures += 0 if expect("crossed (2차)", body.get("crossed"), 1) else 1

    # 5) 저신뢰 OCR (confidence 0.55) → 단건 RPC 분기
    print("\n# Step 5: 저신뢰 OCR 분기 (track 9002)")
    post("/v1/yolo/detections", {
        "detections": [make_detection(track_id=9002, cy=400, plate_conf=0.55)],
    })
    status, body = post("/v1/yolo/detections", {
        "detections": [make_detection(track_id=9002, cy=600, plate_conf=0.55)],
    })
    failures += 0 if expect("crossed (저신뢰)", body.get("crossed"), 1) else 1
    print("  [INFO] 위 이벤트는 단건 RPC(SendPassageEvent) 로 분기됩니다. 서버 로그에서 [unary] 라인을 확인하세요.")

    print("\n" + ("=" * 50))
    if failures == 0:
        print("ALL SMOKE TESTS PASSED")
        return 0
    print(f"FAILED: {failures} 건")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
