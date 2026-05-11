# MQTT vs WebTransport 비교 및 HI-FIVE 프로젝트 적용 근거

## 1. 문서 목적

HI-FIVE 프로젝트에서는 Jetson Nano 기반 Edge 장치에서 차량 번호판 인식 결과, 프레임 메타데이터, GPS 로그, 통행 이벤트 등을 서버로 전송해야 한다.

초기에는 MQTT와 WebTransport 두 가지 통신 방식을 검토하였다. 본 문서는 두 기술의 차이점, 장단점, 프로젝트 적용 관점에서의 판단 기준을 정리하고, 최종적으로 WebTransport를 선택한 이유를 설명한다.

---

## 2. 프로젝트 통신 요구사항

HI-FIVE 프로젝트의 주요 데이터 흐름은 다음과 같다.

```text
Jetson Nano / Edge Device
→ FastAPI Edge Gateway
→ Spring Boot Backend
→ PostgreSQL
→ Vue Admin Dashboard
```

전송해야 하는 데이터는 단순 센서 값뿐 아니라 다음과 같은 복합 이벤트이다.

- 차량 번호판 OCR 결과
- YOLO 차량/번호판 검출 메타데이터
- 차로 정보
- 검출 시간
- OCR confidence
- GPS 좌표
- GPS fix 상태
- 통행 이벤트
- 과금 구간 통과 여부
- Edge 장치 상태
- 향후 이미지 crop 또는 영상 프레임 일부 전송 가능성

따라서 통신 방식은 다음 조건을 만족해야 한다.

- 실시간성
- 낮은 지연 시간
- 양방향 통신 가능성
- 브라우저/웹 기반 관제 시스템과의 친화성
- HTTP/3 기반 확장성
- 이벤트와 스트림 데이터를 함께 처리할 수 있는 구조
- Edge 장치와 서버 간 안정적인 연결 관리
- 향후 영상/바이너리 데이터 전송 확장 가능성

---

## 3. MQTT 개요

MQTT는 Message Queuing Telemetry Transport의 약자로, IoT 환경에서 널리 사용되는 경량 메시징 프로토콜이다.

기본 구조는 Publisher, Broker, Subscriber 모델이다.

```text
Publisher
→ MQTT Broker
→ Subscriber
```

예를 들어 GPS 장치가 특정 topic으로 데이터를 발행하면, 서버나 대시보드가 해당 topic을 구독하여 데이터를 수신한다.

```text
topic: hifive/gps/telemetry
payload: {
  "deviceId": "PICO2W-NEO7M-RC-01",
  "lat": 37.4012,
  "lng": 127.1045
}
```

---

## 4. WebTransport 개요

WebTransport는 HTTP/3와 QUIC 기반의 최신 양방향 통신 기술이다.

기존 W으ebSocket처럼 서버와 클라이언트가 지속 연결을 유지할 수 있며, HTTP/3 기반으로 동작하기 때문에 QUIC의 장점을 활용할 수 있다.

WebTransport는 다음 전송 방식을 지원한다.

- 양방향 스트림
- 단방향 스트림
- Datagram 전송
- 바이너리 데이터 전송
- 낮은 지연 시간의 실시간 통신

구조는 다음과 같다.

```text
Edge Device
→ WebTransport Session
→ FastAPI Edge Gateway
→ Spring Boot Backend
```

---

## 5. MQTT와 WebTransport 핵심 차이

| 구분                  | MQTT                   | WebTransport                              |
| --------------------- | ----------------------- ----------------------------------------- |
| 기본 구조             | Pub/Sub + Broker       | Client-Server 직접 세션                   |
| 기반 프로토콜         | TCP 기반                | HTTP/3 + QUIC 기반                        |
| 중간 서버             | MQTT Broker 필요        | 별도 Broker 없이 Gateway 직접 연결 가능  |
| 브라우저 친화성       | 브라우저 직접 사용 제한적 | 브라우저/Web API와 친화적                 |
| 실시간성              | 좋음                    | 매우 좋음                                 |
| 지연 시간             | 낮음                    | 낮음, QUIC 기반으로 더 유리               |
| 메시지 전달 보장      | QoS 지원                 | 애플리케이션 레벨에서 설계                |
| 양방향 통신           | 가능하나 Broker 중심     | 세션 기반 양방향 통신에 적합              |
| 바이너리/스트림       | 가능하지만 메시지 중심    | 스트림/Datagram/바이너리에 적합           |
| 영상/프레임 확장      | 별도 설계 필요           | 구조적으로 더 적합                        |
| 운영 복잡도           | Broker 운영 필요        | HTTP/3 Gateway 운영 필요                  |
| IoT 센서 데이터       | 매우 적합               | 적합                                      |
| AI Edge 실시간 스트림 | 제한적                  | 더 적합                                   |

---

## 6. MQTT 장점

### 6.1 IoT 표준에 가까운 경량 프로토콜

MQTT는 IoT 분야에서 오래 사용되어 온 검증된 프로토콜이다. 센서 데이터, 온도, 습도, GPS 좌표처럼 작고 반복적인 메시지를 전송하는 데 적합하다.

### 6.2 Pub/Sub 구조

Publisher와 Subscriber가 직접 서로를 알 필요 없이 Broker를 통해 데이터를 주고받는다.

예를 들어 여러 대의 GPS 장치가 topic에 데이터를 발행하고, 여러 서버가 이를 구독할 수 있다.

```text
gps/device-01 → Broker → Backend
gps/device-02 → Broker → Dashboard
gps/device-03 → Broker → Monitoring
```

이 구조는 다수 장치의 상태를 분산 처리할 때 유리하다.

### 6.3 QoS 지원

MQTT는 QoS 0, 1, 2를 지원한다.

| QoS |      의미      |
|-----|----------------|
|  0  | 최대 1회 전달   |
|  1  | 최소 1회 전달   |
|  2  | 정확히 1회 전달 |

데이터 유실을 줄여야 하는 IoT 환경에서 장점이 있다.

### 6.4 저전력 장치에 적합

메시지 구조가 가볍기 때문에 ESP32, Pico W, 저전력 IoT 장비에 적합하다.

---

## 7. MQTT 단점

### 7.1 Broker가 추가로 필요

MQTT를 사용하려면 Mosquitto, EMQX, HiveMQ 같은 Broker를 별도로 구축해야 한다.

```text
Edge Device
→ MQTT Broker
→ Backend
```

즉, 시스템 구성 요소가 하나 더 늘어난다.

운영 관점에서는 다음 관리가 추가된다.

- Broker 설치
- Broker 포트 관리
- 계정/인증 설정
- topic 권한 관리
- 장애 대응
- 로그 관리
- 메시지 보존 정책

### 7.2 브라우저 기반 대시보드와 직접 연결이 애매함

일반 MQTT는 TCP 기반이므로 브라우저에서 직접 사용하기 어렵다. 브라우저에서 MQTT를 사용하려면 MQTT over WebSocket 구성이 필요하다.

즉 다음처럼 구조가 복잡해질 수 있다.

```text
Device
→ MQTT Broker
→ MQTT over WebSocket
→ Browser Dashboard
```

HI-FIVE 프로젝트는 Vue 기반 관리자 대시보드를 사용하기 때문에 브라우저 친화성도 중요한 판단 요소이다.

### 7.3 영상/프레임/AI 이벤트 스트림에는 덜 적합

MQTT는 작은 메시지를 주고받는 데 최적화되어 있다.

하지만 HI-FIVE 프로젝트는 단순 GPS만 다루는 것이 아니라 다음과 같은 데이터 확장 가능성이 있다.

- 번호판 crop 이미지
- OCR 검출 이벤트 묶음
- Edge AI 처리 상태
- 영상 프레임 일부
- 실시간 관제 이벤트 스트림

이 경우 MQTT만으로 처리하면 topic 설계, payload 분리, 바이너리 처리, 순서 보장 등을 별도로 세밀하게 설계해야 한다.

### 7.4 요청/응답 구조가 직관적이지 않음

MQTT는 Pub/Sub 중심이기 때문에 REST API처럼 명확한 요청/응답 구조가 아니다.

예를 들어 Edge 장치에 "현재 상태를 보내라", "설정을 변경하라" 같은 명령을 내리려면 command topic과 response topic을 별도로 설계해야 한다.

```text
hifive/edge/EDGE-RC-01/command
hifive/edge/EDGE-RC-01/response
```

---

## 8. WebTransport 장점

### 8.1 HTTP/3 + QUIC 기반의 낮은 지연 시간

WebTransport는 HTTP/3와 QUIC 기반이다. QUIC은 TCP가 아닌 UDP 위에서 동작하며, 연결 수립과 재전송 처리에서 실시간성에 유리한 구조를 가진다.

실시간 관제 시스템에서는 지연 시간이 중요하다.

HI-FIVE 프로젝트에서는 차량이 특정 감지 영역을 통과하는 시점에 다음 데이터를 빠르게 연결해야 한다.

```text
번호판 인식 이벤트
+ GPS 좌표
+ 통행 시각
+ 차로
+ 과금 구간 판정
```

따라서 실시간 스트림에 적합한 WebTransport가 유리하다.

### 8.2 양방향 세션 기반 통신

WebTransport는 클라이언트와 서버가 세션을 유지하면서 양방향으로 데이터를 주고받을 수 있다.

```text
Edge → Server: OCR/GPS 이벤트 전송
Server → Edge: 설정 변경, ACK, 제어 명령 전송
```

이는 HI-FIVE의 Edge 장치 운영 구조와 잘 맞는다.

예를 들어 향후 다음 기능을 넣기 쉽다.

- Edge 장치 상태 확인
- 카메라 설정 변경
- OCR 임계값 변경
- GPS 감지 영역 업데이트
- 서버 ACK 기반 재전송
- Edge 장치별 실시간 모니터링

### 8.3 Stream과 Datagram을 모두 지원

WebTransport는 스트림과 Datagram을 모두 지원한다.

데이터 특성에 따라 전송 방식을 나눌 수 있다.

| 데이터               | 적합한 방식           |
| -------------------- | --------------------- |
| OCR 결과 이벤트      | Stream                |
| GPS 실시간 좌표      | Datagram 또는 Stream  |
| Edge 상태 heartbeat  | Datagram              |
| 이미지 crop          | Stream                |
| 대용량 바이너리      | Stream                |

즉, 단순 메시지뿐 아니라 다양한 데이터 형태를 하나의 통신 세션에서 다룰 수 있다.

### 8.4 브라우저 기반 실시간 서비스와 잘 맞음

WebTransport는 웹 플랫폼을 고려한 기술이다.

HI-FIVE는 Vue 관리자 대시보드를 사용하며, 관제 화면에서 다음 데이터를 실시간으로 보여준다.

- GPS Telemetry 로그
- OCR 차량 검출 상세
- 통행 이벤트
- GPS 경로 분석
- 시스템 상태

따라서 웹 기반 실시간 대시보드와 구조적으로 잘 맞는다.

### 8.5 Broker 없이 Gateway 중심 구조 가능

MQTT는 Broker 중심 구조가 일반적이다.

반면 WebTransport는 FastAPI Edge Gateway가 직접 WebTransport 세션을 받고, 필요한 데이터를 Spring Boot로 전달하는 구조가 가능하다.

```text
Jetson Edge
→ FastAPI WebTransport Gateway
→ Spring Boot API
→ PostgreSQL
```

이 구조는 현재 프로젝트의 BE, FE, FastAPI 분리 구조와 잘 맞는다.

### 8.6 AI Edge 파이프라인 확장에 유리

HI-FIVE는 단순 IoT 센서 프로젝트가 아니라 AI Edge 기반 관제 프로젝트이다.

핵심은 다음과 같다.

```text
YOLO 차량 검출
→ 번호판 OCR
→ GPS 위치 판정
→ 과금 이벤트 생성
→ 관리자 대시보드 실시간 표시
```

이 과정에서는 이벤트가 단순하지 않고, 여러 종류의 데이터가 시간 순서대로 묶여야 한다.

WebTransport는 세션 기반으로 Edge 장치와 서버가 지속 연결되므로, 장치 단위의 이벤트 흐름을 추적하기 좋다.

---

## 9. WebTransport 단점

### 9.1 MQTT보다 생태계가 작음

MQTT는 오래된 기술이고 IoT 분야에서 자료와 예제가 많다.

반면 WebTransport는 상대적으로 최신 기술이므로 MQTT만큼 자료가 풍부하지 않다.

### 9.2 HTTP/3/QUIC 환경 구성이 필요

WebTransport를 제대로 운영하려면 HTTP/3, TLS, QUIC 구성을 고려해야 한다.

개발 환경에서는 FastAPI 또는 별도 Gateway로 테스트할 수 있지만, 운영 환경에서는 다음 요소를 고려해야 한다.

- TLS 인증서
- HTTP/3 지원 서버
- 방화벽 UDP 포트
- 프록시 서버의 HTTP/3 지원 여부
- 브라우저 호환성

### 9.3 메시지 전달 보장은 직접 설계해야 함

MQTT는 QoS를 기본 제공하지만 WebTransport는 MQTT식 QoS가 없다.

따라서 중요한 이벤트는 애플리케이션 레벨에서 ACK와 재전송 정책을 설계해야 한다.

예시:

```text
Edge → Server: passageEventId=abc123
Server → Edge: ACK abc123
Edge: ACK 없으면 spool 저장 후 재전송
```

다만 HI-FIVE 프로젝트에서는 이미 Edge spool, ACK, Spring forwarder 같은 구조를 확장할 수 있으므로 이 단점은 설계로 보완 가능하다.

---

## 10. HI-FIVE 프로젝트에서 MQTT가 아쉬운 이유

MQTT는 다음과 같은 경우 매우 적합하다.

- 온도 센서
- 습도 센서
- 단순 GPS 좌표
- 조도 센서
- 저전력 IoT 장치
- 다수 장치의 단순 상태 수집

하지만 HI-FIVE는 단순 센서 수집 시스템이 아니다.

HI-FIVE는 다음 성격이 강하다.

- AI 영상 분석 시스템
- Edge Computing 시스템
- 실시간 관제 시스템
- OCR/GPS/요금정산 통합 이벤트 시스템
- 웹 관리자 대시보드 기반 시스템

따라서 MQTT의 Pub/Sub 구조만으로는 다음 요구를 처리할 때 복잡도가 커질 수 있다.

- Edge 장치별 세션 관리
- OCR 이벤트와 GPS 이벤트의 시간 동기화
- 이미지 crop 또는 바이너리 데이터 전송
- 서버 ACK 기반 재전송
- 웹 대시보드와 실시간 연동
- FastAPI Edge Gateway 중심 구조
- 향후 Web 기반 실시간 스트림 확장

---

## 11. HI-FIVE 프로젝트에서 WebTransport가 적합한 이유

### 11.1 프로젝트 구조와 맞음

현재 프로젝트는 이미 다음 구조를 가진다.

```text
FE: Vue 관리자 대시보드
BE: Spring Boot API 서버
Edge: FastAPI 기반 Edge Gateway
AI: Jetson Nano YOLO/OCR 파이프라인
DB: PostgreSQL
```

WebTransport는 FastAPI Edge Gateway와 연결하기 좋고, Spring Boot는 최종 데이터 저장 API 역할을 유지할 수 있다.

즉, 역할 분리가 명확하다.

```text
WebTransport
→ 실시간 Edge 데이터 수신

Spring Boot REST API
→ 데이터 저장, 관리자 기능, 정산 처리

Vue Dashboard
→ 실시간 관제 화면
```

### 11.2 OCR/GPS 이벤트를 실시간 스트림으로 처리하기 좋음

번호판 인식과 GPS 로그는 각각 따로 존재하는 데이터가 아니라, 같은 차량 통행 이벤트 안에서 결합되어야 한다.

예시:

```text
10:21:03 OCR: 33나9029, confidence 92%
10:21:04 GPS: 감지 영역 진입
10:21:05 Toll: 과금 대상 확정
```

WebTransport는 연결된 세션 안에서 이런 이벤트 흐름을 순서 있게 처리하기 좋다.

### 11.3 향후 영상/이미지 데이터 확장에 유리

현재는 로그와 메타데이터 중심이지만, 향후 다음 데이터가 필요할 수 있다.

- 번호판 crop 이미지
- 검출 프레임
- YOLO debug frame
- OCR 원본 이미지
- Edge 상태 스트림

WebTransport는 바이너리 스트림 전송에 적합하므로 향후 확장성이 좋다.

### 11.4 브라우저 기반 관제 대시보드와 방향성이 맞음

HI-FIVE의 최종 시연과 운영 화면은 웹 대시보드이다.

WebTransport는 웹 기반 실시간 통신 기술이므로, 장기적으로 다음 구조도 가능하다.

```text
FastAPI WebTransport Gateway
→ Vue Dashboard 실시간 반영
```

또는 백엔드에서 WebSocket/SSE로 변환하여 대시보드에 전달할 수도 있다.

### 11.5 Broker 운영 부담 감소

MQTT를 도입하면 Broker가 필수 구성 요소가 된다.

그러나 현재 프로젝트는 이미 다음 서버가 존재한다.

- Spring Boot Backend
- FastAPI Edge Gateway
- Vue Frontend
- PostgreSQL

여기에 MQTT Broker까지 추가하면 시연과 운영 구성이 복잡해진다.

WebTransport를 사용하면 FastAPI Edge Gateway가 실시간 수신 지점이 되므로 구조가 단순해진다.

---

## 12. 최종 선택

HI-FIVE 프로젝트에서는 WebTransport를 사용하는 것이 더 적합하다.

이유는 다음과 같다.

1. 단순 IoT 센서 데이터가 아니라 AI Edge 기반 실시간 관제 데이터이다.
2. OCR, GPS, 통행 이벤트, 과금 판정이 시간 흐름 안에서 결합되어야 한다.
3. 향후 이미지 crop, 영상 프레임, 바이너리 데이터 전송 확장 가능성이 있다.
4. Vue 기반 관리자 대시보드와 실시간 연동 방향성이 맞다.
5. FastAPI Edge Gateway 중심 구조와 잘 맞는다.
6. MQTT Broker를 별도로 운영하지 않아도 된다.
7. HTTP/3 + QUIC 기반으로 낮은 지연 시간과 실시간 스트림 처리에 유리하다.
8. Edge 장치와 서버 간 양방향 제어 구조를 만들기 쉽다.

---

## 13. 결론

MQTT는 가볍고 안정적인 IoT 메시징 프로토콜이며, 단순 센서 수집에는 매우 좋은 선택이다.

하지만 HI-FIVE 프로젝트는 단순 센서 수집 시스템이 아니라 다음 특성을 가진다.

```text
AI 영상 분석
+ 번호판 OCR
+ GPS 위치 판정
+ 통행 이벤트 생성
+ 과금 처리
+ 실시간 관제 대시보드
```

따라서 메시지 중심의 MQTT보다, 실시간 세션과 스트림 중심의 WebTransport가 프로젝트 방향성에 더 적합하다.

최종적으로 HI-FIVE 프로젝트는 WebTransport를 사용하여 Edge 장치의 실시간 OCR/GPS 이벤트를 FastAPI Gateway로 수신하고, Spring Boot Backend를 통해 DB 저장 및 관리자 대시보드 연동을 수행하는 구조로 진행한다.

```text
Jetson Nano / Edge Device
→ WebTransport
→ FastAPI Edge Gateway
→ Spring Boot Backend
→ PostgreSQL
→ Vue Admin Dashboard
```

