# HI-FIVE 코딩 컨벤션

## 1. 문서 기준

이 문서는 현재 확정된 HI-FIVE 파이프라인을 기준으로 한다.

```text
Jetson Edge
-> WebTransport over QUIC/TLS
-> Python Ingress Server
-> Spring Boot REST
-> PostgreSQL
-> Vue 3 + axios + Pinia + Vue Router
```

이 문서에서 정한 이름, 필드, 패키지, 좌표계, 시간 포맷은 Edge, Python Ingress, Spring Boot, PostgreSQL, Vue에서 같은 의미로 사용한다.

## 2. 최상위 원칙

1. Edge-to-server payload는 Protobuf binary를 기준으로 한다.
2. Edge-to-server 전송은 WebTransport over QUIC/TLS를 기준으로 한다.
3. Spring Boot는 WebTransport를 직접 받지 않고 Python Ingress를 통해 REST로 수신한다.
4. Python Ingress 이후 Spring Boot 전달은 REST ingest API를 기준으로 한다.
5. Python Ingress는 전송 어댑터이며 최종 저장소가 아니다.
6. Spring Boot가 검증, 중복 처리, 저장, 요금, 검수, 통계를 담당한다.
7. Vue는 Spring Boot REST API만 호출한다.
8. 원본 이미지와 영상은 기본 전송하지 않는다.
9. `plate_bbox` 저장 좌표는 original frame pixel을 기준으로 한다.
10. 최종 통행 및 과금 단위는 `vehicle_pass_id`다.

## 3. 공통 구조

### 3.1 Jetson Edge

```text
jetson_edge
├─ config        # 카메라, 모델, threshold, 전송 설정
├─ camera        # GStreamer / DeepStream 입력
├─ preprocessing # 1920x1080 -> 960x960 합성
├─ yolo          # YOLO TensorRT 추론, bbox 복원
├─ tracking      # local_track_id, crossing 판단
├─ ipc           # SharedMemory, OCR Queue
├─ ocr           # OCR TensorRT 추론, voting, 필터링
├─ events        # PassageEvent 생성, Protobuf 직렬화
├─ transport     # WebTransport 송신, local spool, ACK 처리
└─ observability # health, status, debug, metrics
```

### 3.2 Python Ingress

```text
ingress_server
├─ main.py       # uvicorn 실행 진입점
├─ web_transport # aioquic WebTransport 수신
├─ protobuf      # PassageEvent schema / generated code
├─ spring_client # Spring REST 전달
├─ ack           # ACK / RETRY / REJECT 응답 처리
├─ observability # FastAPI health / status / metrics
└─ config        # 인증키, Spring URL, TLS 설정
```

### 3.3 Spring Boot

Spring Boot는 레이어드 패키지 구조를 기준으로 한다.

```text
com.hifive.iot
├─ controller   # REST API 진입점
├─ service      # 비즈니스 로직, 트랜잭션
├─ repository   # DB 접근
├─ entity       # JPA Entity
├─ dto          # Request / Response DTO
├─ mapper       # Entity <-> DTO 변환
├─ exception    # GlobalExceptionHandler, ErrorResponse
├─ config       # CORS, Security, Jackson 등
└─ common       # 공통 상수/유틸, 필요할 때만
```

### 3.4 Vue

```text
src
├─ api          # axios client, API 함수
├─ stores       # Pinia store
├─ router       # Vue Router
├─ views        # 페이지 단위 화면
├─ components   # 재사용 컴포넌트
├─ composables  # 공통 Composition 함수
└─ styles       # 전역 스타일
```

### 3.5 PostgreSQL

```text
postgresql
├─ edge_device
├─ camera_config
├─ passage_event
├─ vehicle_pass
├─ gps_telemetry
├─ toll_zone
├─ toll_history
├─ review_task
├─ member
├─ notice
└─ audit_log
```

## 4. 사용 라이브러리 기준

라이브러리 목록은 역할 기준으로 관리한다. 구체적인 버전은 각 프로젝트의 `requirements.txt`, `build.gradle`, `package.json`, lock 파일에서 관리한다.

### 4.1 Jetson Edge Python

| 라이브러리/런타임 | 사용 목적 |
|---|---|
| OpenCV `cv2` | 카메라 입력, crop, 전처리, 디버그 시각화 |
| GStreamer | Jetson 영상 입력 파이프라인 |
| NVIDIA DeepStream / PyDS | Jetson 최적화 입력, metadata, 추론 파이프라인 |
| TensorRT Python bindings | YOLO/OCR engine 추론 |
| NumPy | frame/crop 배열 처리 |
| Protobuf | PassageEvent binary 직렬화 |
| `multiprocessing.shared_memory` | YOLO -> OCR plate crop 공유 |
| `queue` / `multiprocessing.Queue` | OCR 작업 전달 |
| aioquic | WebTransport client 전송 |

### 4.2 Python Ingress Server

| 라이브러리/런타임 | 사용 목적 |
|---|---|
| aioquic | WebTransport 수신 |
| FastAPI | health/status/metrics 운영 endpoint |
| uvicorn | FastAPI ASGI 실행 |
| httpx | Spring Boot REST 전달 |
| Protobuf | PassageEvent bytes decode와 검증 |
| pydantic | 설정값과 운영 API schema 관리 |

### 4.3 Spring Boot

| 라이브러리/런타임 | 사용 목적 |
|---|---|
| Spring Boot Web | REST API |
| Spring Data JPA | DB 접근 |
| PostgreSQL JDBC Driver | PostgreSQL 연결 |
| Bean Validation | Request DTO 검증 |
| Protobuf Java | PassageEvent binary decode |
| Spring Security | 인증/인가 적용 시 사용 |
| Lombok | 반복 코드 감소 |

### 4.4 Vue

| 라이브러리/런타임 | 사용 목적 |
|---|---|
| Vue 3 | 화면 구현 |
| Vue Router | 페이지 라우팅 |
| Pinia | 전역 상태 관리 |
| axios | Spring Boot REST API 호출 |

### 4.5 공통 도구

| 도구 | 사용 목적 |
|---|---|
| protoc | Protobuf 코드 생성 |
| PostgreSQL | 기준 저장소 |
| Gradle | Spring Boot 빌드 |
| Vite | Vue 개발 서버와 빌드 |
| npm | Vue 의존성/빌드 관리 |

## 5. Naming Style

| 영역 | 스타일 | 예시 |
|---|---|---|
| Protobuf field | `snake_case` | `camera_group_id` |
| JSON API field | `camelCase` | `cameraGroupId` |
| Java package | lower-case | `com.hifive.iot.controller` |
| Java class | `PascalCase` | `PassageEventService` |
| Java field/method | `camelCase` | `vehiclePassId` |
| DB table/column | `snake_case` | `passage_event`, `vehicle_pass_id` |
| Python package/module | `snake_case` | `web_transport` |
| Python class | `PascalCase` | `WebTransportSender` |
| Python function/var | `snake_case` | `send_passage_event` |
| Vue component | `PascalCase` | `ReviewTaskTable.vue` |
| Vue composable | `use` + `PascalCase` | `useReviewTasks` |
| Vue store | `use` + `PascalCase` | `useAuthStore` |
| Vue route name | `kebab-case` | `review-tasks` |

팀명이나 프로젝트명은 문서 제목, Java root package, 서비스명에는 사용할 수 있다. Python/Vue 폴더명은 역할 중심 이름을 우선한다.

## 6. 공통 용어

| 용어 | 의미 |
|---|---|
| `event_id` | Edge에서 생성한 이벤트 고유 ID |
| `device_id` | Jetson Edge 장치 ID |
| `camera_id` | 개별 카메라 ID |
| `camera_group_id` | front/rear 카메라 묶음 |
| `camera_role` | `front`, `rear` |
| `lane_no` | 카메라 내부 차선 번호 |
| `global_lane_no` | 전체 톨게이트 기준 차선 번호 |
| `local_track_id` | Edge 내부 추적 ID |
| `vehicle_pass_id` | Backend가 생성한 최종 통과 단위 |
| `plate_text` | OCR 번호판 문자열 |
| `plate_confidence` | OCR confidence |
| `vehicle_confidence` | 차량 또는 번호판 detection confidence |
| `plate_bbox` | 번호판 bbox |
| `needs_review` | 검수 필요 여부 |
| `review_reason` | 검수 사유 |
| `gps_device_id` | GPS 또는 OBU 송신 단말 ID |
| `captured_at` | 단말 또는 Edge 측정 시각 |
| `received_at` | 서버 수신 시각 |

같은 의미에 `plateNo`, `plateNumber`, `licensePlate`, `plate_text`를 섞어 쓰지 않는다. API JSON이 `plateText`를 쓰더라도 Protobuf와 DB 기준 용어는 `plate_text`다.

## 7. Protobuf 규칙

Protobuf는 Edge-to-server 이벤트의 원천 계약이다.

```proto
message PassageEvent
message PlateInfo
message BBox
message GpsPoint
message PassageAck
```

필드명은 `snake_case`를 유지한다.

핵심 필드:

```text
event_id
device_id
camera_id
camera_group_id
camera_role
timestamp
direction
lane_no
global_lane_no
local_track_id
vehicle_pass_id
vehicle_confidence
plate_text
plate_confidence
candidate_count
agreement_ratio
plate_bbox
needs_review
review_reason
schema_version
```

`vehicle_pass_id`는 Spring Boot에서 최종 통과 단위가 생성된 뒤 채워질 수 있으므로 Edge 최초 전송 시점에는 비어 있을 수 있다.

변경 규칙:

- 기존 field number를 재사용하지 않는다.
- 삭제 필드는 `reserved` 처리한다.
- 새 필드는 뒤쪽 field number에 추가한다.
- Python, Spring Boot, PostgreSQL, Vue 계약을 함께 갱신한다.
- JSON 예시는 설명용이며 기본 전송 계약으로 쓰지 않는다.

## 8. Enum / Status 값

문자열 enum은 대소문자와 철자를 고정한다.

| 필드 | 값 |
|---|---|
| `camera_role` | `front`, `rear` |
| `direction` | `entry`, `exit`, `unknown` |
| `bbox_coord` | `original_frame`, `model_input`, `lane_roi` |
| `payload_format` | `protobuf` |
| `ack_status` | `ack`, `retry`, `reject` |
| `review_task.status` | `open`, `resolved`, `rejected` |
| `payment_status` | `paid`, `unpaid`, `pending` |
| `fusion_status` | `pending`, `fused`, `review` |

## 9. Edge Python 규칙

입력 처리:

- 기본 입력은 1920x1080 frame이다.
- 2차선 기준으로 960x480 두 개를 만들고 960x960 YOLO 입력으로 합성한다.
- YOLO plate bbox는 original frame pixel 좌표로 복원한다.
- frame rate, camera role, color space, 좌표계를 코드 주석 또는 config로 명시한다.

YOLO/OCR 병렬 처리:

- YOLO Loop는 OCR 결과를 기다리지 않는다.
- OCR Worker는 YOLO가 넘긴 plate crop만 처리한다.
- YOLO -> OCR 전달은 SharedMemory와 Queue를 사용한다.
- Queue에는 image bytes를 넣지 않고 `shm_name`, `shape`, `dtype`, `plate_bbox`, `track metadata`를 넣는다.
- OCR Queue가 가득 차면 YOLO Loop를 막지 않는다.

OCR 규칙:

- OCR 입력은 현재 팀 OCR 모델 기준인 48x160 RGB를 우선한다.
- plate crop width `< 100px` 또는 height `< 32px`이면 자동 확정하지 않는다.
- OCR 후보는 track 단위로 누적한다.
- 단일 프레임 결과만으로 자동 확정하지 않는다.
- 패턴 검증은 `2~3 digits + Korean character + 4 digits` 기준이다.
- 저신뢰, 후보 불일치, 패턴 불일치는 `needs_review=true`로 보낸다.

전송 규칙:

- PassageEvent 생성 후 local spool에 먼저 저장한다.
- WebTransport ACK를 받기 전에는 spool에서 삭제하지 않는다.
- 네트워크 실패, LTE 전환, timeout은 재시도 대상으로 처리한다.
- 원본 image/video는 기본 전송하지 않는다.

## 10. Python Ingress 규칙

Python Ingress 책임:

- aioquic WebTransport 연결 수신
- Protobuf bytes 수신
- Spring Boot REST API로 전달
- Spring 저장 성공 여부 확인
- Edge에 `ACK`, `RETRY`, `REJECT` 응답
- 운영 확인용 `/healthz`, `/status`, `/metrics` 제공

Python Ingress가 하지 않는 일:

- 최종 DB 저장
- VehiclePass fusion
- toll 계산
- review 상태 확정
- Vue API 제공

Spring 전달 기준:

```text
POST /api/ingest/passage-events
Content-Type: application/x-protobuf
X-Event-Id: {event_id}
```

응답 처리:

| Spring 응답 | Edge 응답 |
|---|---|
| `2xx` | `ACK` |
| `409` | `ACK` |
| `4xx` | `REJECT` |
| `5xx` / timeout | `RETRY` |

## 11. Spring Boot 규칙

Controller:

- REST endpoint만 담당한다.
- Request/Response DTO만 사용한다.
- JPA Entity를 직접 반환하지 않는다.
- `@Valid`로 요청 DTO를 검증한다.

Service:

- 업무 규칙과 transaction boundary를 담당한다.
- 쓰기 작업은 `@Transactional`을 명시한다.
- 중복 `event_id`는 idempotent success로 처리한다.
- 필수 의존성은 constructor injection과 `private final` field를 사용한다.

Repository:

- DB 접근만 담당한다.
- 복잡한 조회는 명확한 method name 또는 `@Query`를 사용한다.
- API 응답용 데이터는 Entity가 아니라 DTO 또는 projection으로 변환한다.

DTO/Mapper:

- Request DTO와 Response DTO를 분리한다.
- DTO 이름은 `XxxRequest`, `XxxResponse`를 사용한다.
- Entity와 DTO 변환은 mapper에서 처리한다.

Exception:

- 예외 응답은 `@ControllerAdvice`에서 공통 처리한다.
- API 오류 응답은 동일한 구조를 사용한다.

```json
{
  "code": "VALIDATION_FAILED",
  "message": "Invalid request",
  "details": []
}
```

Config/Security:

- 환경별 설정은 `application.yml`, `application-dev.yml`, `application-prod.yml`로 분리한다.
- 외부 URL, internal ingest key, DB 계정, TLS 관련 값은 코드에 하드코딩하지 않는다.
- 설정 묶음은 필요 시 `@ConfigurationProperties`로 관리한다.
- CORS, 인증, 인가 정책은 `config` 패키지에서 관리한다.
- password는 평문 저장하지 않고 해시 처리한다.

## 12. GPS 규칙

정식 endpoint:

```text
POST /api/gps/telemetry
GET  /api/gps/telemetry/latest
```

필드 기준:

| DB field | Java/API field |
|---|---|
| `gps_device_id` | `gpsDeviceId` |
| `plate_number` | `plateNumber` |
| `edge_node_id` | `edgeNodeId` |
| `lane_id` | `laneId` |
| `track_id` | `trackId` |
| `speed_kmh` | `speedKmh` |
| `altitude_m` | `altitudeM` |
| `accuracy_m` | `accuracyM` |
| `captured_at` | `capturedAt` |
| `received_at` | `receivedAt` |

검증:

- `latitude`는 `-90 <= latitude <= 90`.
- `longitude`는 `-180 <= longitude <= 180`.
- 외부 payload의 `speed`가 m/s이면 service에서 `speed * 3.6`으로 변환한다.
- `capturedAt`과 `receivedAt`을 분리한다.
- GPS 단독으로 `vehicle_pass_id`를 확정하지 않는다.
- GPS/OBU 식별자는 access control, masking, audit log 대상이다.

## 13. PostgreSQL 규칙

테이블/컬럼:

- table과 column은 `snake_case`를 사용한다.
- PK는 `{table}_id` 또는 명확한 domain id를 사용한다.
- FK는 참조 테이블 기준 `{table}_id`를 사용한다.
- 생성/수정 시각은 `created_at`, `updated_at`을 사용한다.
- confidence는 `0.0 ~ 1.0` range check를 둔다.
- `plate_bbox`의 `w`, `h`는 양수 check를 둔다.

필수 제약:

- `passage_event.event_id` unique
- `gps_telemetry.gps_device_id`, `captured_at` index
- `gps_telemetry.plate_number`, `captured_at` index
- 주요 조회 조건인 `camera_id`, `timestamp`, `vehicle_pass_id`, `needs_review` index
- enum성 문자열 check constraint

## 14. Vue 규칙

기본:

- Vue 3 Composition API를 사용한다.
- SFC는 `<script setup>`을 기준으로 작성한다.
- API 호출은 `src/api`의 axios client로만 수행한다.
- Pinia store는 서버 응답 상태와 화면 상태를 분리해서 관리한다.
- view component는 route 단위 조립 역할을 우선한다.
- 복잡한 UI는 `components`, 상태 로직은 `composables`로 분리한다.
- SFC 작성 순서는 `<script>`, `<template>`, `<style>`을 기준으로 한다.
- component 간 데이터 흐름은 props down, events up을 우선한다.
- `v-html`은 기본 사용하지 않는다.
- template 안의 복잡한 조건식과 계산식은 `computed` 또는 함수로 분리한다.
- list, table, dashboard 화면에는 loading, empty, error 상태를 둔다.

API response 예시:

```js
const passageEventResponse = {
  eventId: 'edge-01-cam-rear-01-20260505-00001',
  cameraId: 'cam-rear-01',
  cameraRole: 'rear',
  laneNo: 1,
  plateText: '12가3456',
  plateConfidence: 0.97,
  needsReview: false
}
```

화면 상태:

- loading 상태를 둔다.
- empty 상태를 둔다.
- error 상태를 둔다.
- pagination, query, filter는 URL query와 동기화한다.
- 관리자 route는 auth guard를 둔다.

## 15. REST API Naming

REST path는 복수 명사를 사용한다.

```text
GET    /api/detections/latest
GET    /api/detections
GET    /api/reviews
PATCH  /api/reviews/{id}
GET    /api/tolls
GET    /api/stats/summary
GET    /api/stats/traffic
GET    /api/stats/ocr
GET    /api/devices
POST   /api/gps/telemetry
GET    /api/gps/telemetry/latest
GET    /api/public/notices
POST   /api/auth/login
POST   /api/auth/signup
```

API JSON은 `camelCase`를 사용한다.

```json
{
  "eventId": "edge-01-cam-rear-01-20260505-00001",
  "cameraId": "cam-rear-01",
  "cameraRole": "rear",
  "plateText": "12가3456",
  "plateConfidence": 0.97,
  "needsReview": false
}
```

## 16. Logging / Error Code

공통 error code:

| code | 의미 |
|---|---|
| `PROTO_DECODE_FAILED` | Protobuf decode 실패 |
| `VALIDATION_FAILED` | DTO validation 실패 |
| `DUPLICATE_EVENT` | 중복 event |
| `SPRING_FORWARD_FAILED` | Python Ingress -> Spring 전달 실패 |
| `WEBTRANSPORT_SEND_FAILED` | WebTransport 전송 실패 |
| `EDGE_SPOOL_RETRY` | Edge spool 재시도 |
| `SPOOL_BACKPRESSURE` | Edge spool 적체 |
| `OCR_PATTERN_MISMATCH` | 번호판 패턴 불일치 |
| `GPS_VALIDATION_FAILED` | GPS validation 실패 |
| `GPS_TIMESTAMP_PARSE_FAILED` | GPS 시간 파싱 실패 |

로그 규칙:

- 원본 번호판은 기본 masking한다.
- GPS/OBU 식별자와 plate linkage를 함께 남기지 않는다.
- token, internal ingest key, TLS key는 로그에 남기지 않는다.
- 재시도 로그에는 `event_id`, `device_id`, retry count만 남긴다.

## 17. 테스트 컨벤션

필수 테스트:

- PassageEvent Protobuf encode/decode contract test
- WebTransport sender -> ingress -> ACK test
- Spring ingest duplicate `event_id` test
- OCR plate pattern validation test
- OCR crop reject rule test
- GPS latitude/longitude validation test
- GPS speed m/s to km/h conversion test
- GPS timestamp parsing test
- Vue API client/response mapping test

Jetson 측 측정 항목:

- FPS
- P50/P95/P99 latency
- dropped frame
- CPU/GPU 사용률
- memory RSS
- OCR Queue depth
- spool queue depth
