# hifive — FastAPI Edge Server

엣지(Edge) 단에서 YOLO/OCR 결과를 받아 **가상 통과선(Crossing)** 을 판정하고, 그 결과를 **gRPC + Protobuf** 로 Spring Boot 백엔드에 실시간 전송합니다.

## 디렉터리 구조

```
fastapi-edge/
├── proto/
│   └── tolling.proto              # Edge ↔ Backend 전송 계약(.proto)
├── scripts/
│   └── generate_proto.sh          # proto → python stub 생성
├── app/
│   ├── main.py                    # FastAPI 진입점, lifespan 으로 gRPC 워커 관리
│   ├── core/config.py             # 환경변수 기반 Settings
│   ├── models/schemas.py          # YOLO 입력 Pydantic 스키마
│   ├── services/
│   │   ├── crossing.py            # 가상 통과선 판정 (선분 교차 + 방향 판정)
│   │   ├── gps_service.py         # 트랙/차로별 GPS 캐시
│   │   └── grpc_client.py         # 비동기 gRPC 스트리밍 클라이언트
│   ├── api/routes.py              # /v1/yolo/detections, /v1/gps/...
│   └── grpc_generated/            # protoc 산출물 (생성 후 채워짐)
└── requirements.txt
```

## 빠른 시작

```bash
pip install -r requirements.txt
bash scripts/generate_proto.sh
EDGE_GRPC_TARGET=localhost:9090 \
EDGE_EDGE_NODE_ID=EDGE-SEOUL-01 \
uvicorn app.main:app --reload --port 8000
```

## 데이터 흐름

```
[YOLOv8/OCR]  ──HTTP POST──▶  /v1/yolo/detections
                                   │
                                   ▼
                       CrossingLineDetector (선분 교차 판정)
                                   │ crossed=true
                                   ▼
                  TollingGrpcClient.enqueue_event()
                          │                    │
              저신뢰도 OCR │                    │ 정상
                          ▼                    ▼
                 SendPassageEvent       StreamPassageEvents
                  (단건, 검수 큐)       (양방향 스트림)
                                   │
                                   ▼
                         [Spring Boot Backend]
```

## YOLO 담당과의 인터페이스 (`POST /v1/yolo/detections`)

```json
{
  "edge_node_id": "EDGE-SEOUL-01",
  "detections": [
    {
      "track_id": 1042,
      "lane_id": "LANE-A-3",
      "frame_index": 18293,
      "captured_at": "2026-05-01T09:21:11.482Z",
      "bbox": {"x": 812.3, "y": 410.1, "w": 220.0, "h": 180.5},
      "vehicle_type": "passenger",
      "vehicle_type_confidence": 0.94,
      "plate_text": "12가3456",
      "plate_confidence": 0.88,
      "gps": {
        "latitude": 37.5665,
        "longitude": 126.9780,
        "speed_kmh": 78.4,
        "heading": 92.1,
        "captured_at": "2026-05-01T09:21:11.480Z"
      }
    }
  ]
}
```

## 가상 통과선 알고리즘 요약

1. 트랙별로 직전 프레임 중심좌표를 보존합니다.
2. (직전 → 현재) 선분이 통과선 선분과 교차하면 통과로 판정합니다.
3. 외적 부호로 ENTRY / EXIT 를 구분합니다.
4. 동일 트랙의 중복 판정을 막기 위해 cooldown(2초) 을 둡니다.
5. 5초간 보이지 않는 트랙은 GC 됩니다.

## 검수(저신뢰도) 분기

`plate_confidence < EDGE_LOW_OCR_CONFIDENCE_THRESHOLD` (기본 0.7) 인 이벤트는 스트리밍이 아니라 단건 RPC(`SendPassageEvent`) 로 전송되며, 백엔드는 `PENDING_REVIEW` 상태로 적재합니다. 관리자 대시보드에서 수동 보정 → 보정 결과만 다시 단건 RPC 로 재전송하는 흐름을 권장합니다.

## 환경변수 (`EDGE_` prefix)

| 변수 | 설명 | 기본값 |
|---|---|---|
| `EDGE_EDGE_NODE_ID` | 엣지 식별자 | `EDGE-LOCAL-01` |
| `EDGE_GRPC_TARGET` | Spring Boot gRPC 주소 | `localhost:9090` |
| `EDGE_GRPC_USE_TLS` | TLS 사용 여부 | `false` |
| `EDGE_LOW_OCR_CONFIDENCE_THRESHOLD` | 검수 임계값 | `0.7` |
| `EDGE_CROSSING_LINE_P1_X/Y` | 통과선 시작점 | `0 / 540` |
| `EDGE_CROSSING_LINE_P2_X/Y` | 통과선 끝점 | `1920 / 540` |
| `EDGE_SEND_QUEUE_MAX_SIZE` | 송신 큐 크기 | `10000` |
