# FastAPI 엣지 서버 — 실행 & 점검 가이드

런타임은 **uvicorn** 입니다. ASGI 표준이라 `uvicorn`, `hypercorn`, `gunicorn -k uvicorn.workers.UvicornWorker` 모두 호환됩니다.
운영에서는 보통 멀티워커로 `uvicorn app.main:app --workers 2` 또는 `gunicorn` 으로 띄웁니다.

## 0. 사전 준비

- Python 3.11+ 권장 (3.10 도 동작)
- (선택) Spring Boot 백엔드가 `localhost:9090` 에서 gRPC 수신
  - **백엔드가 안 떠있어도 FastAPI 자체는 정상 기동**합니다. gRPC 송신은 내부 큐에 쌓이고 백오프 재연결을 반복합니다.

## 1. 의존성 설치 + Proto 컴파일

Windows / macOS / Linux 공통:

```bash
cd fastapi-edge
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python scripts/generate_proto.py
```

`scripts/generate_proto.py` 실행 후 `app/grpc_generated/tolling_pb2.py` 와 `tolling_pb2_grpc.py` 가 생성되면 OK.

> Proto 컴파일을 빠뜨리면 서버 기동 시 `ImportError: tolling_pb2` 가 납니다. 가장 흔한 함정입니다.

## 2. 서버 기동

```bash
# 가장 단순 (개발)
uvicorn app.main:app --reload --port 8000

# 환경변수로 백엔드 지정
EDGE_GRPC_TARGET=localhost:9090 \
EDGE_EDGE_NODE_ID=EDGE-SEOUL-01 \
uvicorn app.main:app --reload --port 8000
```

기동 로그에 다음 라인이 보이면 정상:

```
INFO ... TollingGrpcClient started → localhost:9090
INFO ... hifive Edge API ready (node=EDGE-SEOUL-01)
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## 3. 점검 (3가지 방법)

### 방법 A — 자동 스모크 테스트 (권장)

서버를 띄운 별도 터미널에서:

```bash
python scripts/smoke_test.py
```

5단계 시나리오를 실행하고 PASS/FAIL 을 출력합니다.

### 방법 B — 브라우저 / Swagger UI

FastAPI 가 자동으로 OpenAPI 문서를 띄워 줍니다.

- Swagger : http://localhost:8000/docs
- ReDoc   : http://localhost:8000/redoc

`POST /v1/yolo/detections` 를 펼쳐서 "Try it out" 으로 즉시 호출 가능합니다.

### 방법 C — curl

```bash
# 1) 헬스체크
curl http://localhost:8000/healthz
# {"status":"ok"}

# 2) GPS 푸시
curl -X POST http://localhost:8000/v1/gps/lane/LANE-A-1 \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 37.5665, "longitude": 126.9780,
    "speed_kmh": 78.4, "heading": 92.1,
    "captured_at": "2026-05-01T09:21:11.480Z"
  }'

# 3) YOLO 검출 1차 (통과선 위쪽)
curl -X POST http://localhost:8000/v1/yolo/detections \
  -H "Content-Type: application/json" \
  -d '{
    "detections": [{
      "track_id": 9001, "lane_id": "LANE-A-1",
      "frame_index": 100,
      "captured_at": "2026-05-01T09:21:11.482Z",
      "bbox": {"x": 910, "y": 350, "w": 100, "h": 100},
      "vehicle_type": "passenger",
      "vehicle_type_confidence": 0.95,
      "plate_text": "12가3456", "plate_confidence": 0.92
    }]
  }'
# → {"received":1,"crossed":0}

# 4) 같은 트랙이 통과선 아래로 (y=350 → y=600)
curl -X POST http://localhost:8000/v1/yolo/detections \
  -H "Content-Type: application/json" \
  -d '{
    "detections": [{
      "track_id": 9001, "lane_id": "LANE-A-1",
      "frame_index": 102,
      "captured_at": "2026-05-01T09:21:11.550Z",
      "bbox": {"x": 910, "y": 550, "w": 100, "h": 100},
      "vehicle_type": "passenger",
      "vehicle_type_confidence": 0.95,
      "plate_text": "12가3456", "plate_confidence": 0.92
    }]
  }'
# → {"received":1,"crossed":1}
```

`crossed:1` 이 떨어졌고 서버 로그에 `[CROSSED] track_id=9001 ...` 가 찍히면 통과선 알고리즘 + gRPC 큐 적재까지 정상 동작한 것입니다.

## 4. gRPC 백엔드가 없을 때 동작

`EDGE_GRPC_TARGET` 으로 설정한 주소가 죽어 있으면 서버 로그에 다음이 반복적으로 보입니다.

```
WARNING ... Stream broken: StatusCode.UNAVAILABLE (...). reconnect in 0.5s
WARNING ... Stream broken: StatusCode.UNAVAILABLE (...). reconnect in 1.0s
WARNING ... Stream broken: StatusCode.UNAVAILABLE (...). reconnect in 2.0s
```

이는 **에러가 아니라 기대된 동작**입니다 (지수 백오프). 백엔드가 다시 살아나면 큐에 쌓인 이벤트가 일괄 송신됩니다.

## 5. 운영 모드

```bash
# 멀티 워커
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --no-access-log

# gunicorn + uvicorn worker
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000

# Docker
docker run -p 8000:8000 \
  -e EDGE_GRPC_TARGET=spring-backend:9090 \
  -e EDGE_EDGE_NODE_ID=EDGE-SEOUL-01 \
  hifive/edge:0.1.0
```
