# HI-FIVE GPS RC카 시연 계획서 및 매뉴얼 v1

## 1. 시연 목표

RC카에 `Pico 2 W`와 `NEO-7M GPS 모듈`을 올려 GPS 로그를 수집하고, Wi-Fi를 통해 HI-FIVE Spring Boot 서버로 전송한다.

최종 목표 흐름은 다음과 같다.

```text
NEO-7M GPS 모듈
-> Pico 2 W
-> Wi-Fi
-> Spring Boot /api/gps/telemetry
-> PostgreSQL gps_telemetry
-> Vue 관리자 대시보드 GPS Telemetry 로그 표시
```

현재 프로젝트 방향 기준으로 GPS telemetry는 **FastAPI를 거치지 않고 Spring Boot가 직접 수신**한다. FastAPI는 Edge/Python Ingress 역할이며, GPS 로그 저장에는 필수 경로가 아니다.

## 2. 사용 장비

### 필수 장비

| 구분 | 장비 |
|---|---|
| GPS | NEO-7M GPS 모듈 |
| MCU | Raspberry Pi Pico 2 W |
| 전원 | 5000mAh USB 보조배터리 |
| 이동체 | RC카 |
| 연결 | 점퍼선 |
| 서버 | Windows PC |
| DB | PostgreSQL |
| Backend | Spring Boot |
| Frontend | Vue |

### 전원 관련 결론

5000mAh USB 보조배터리를 사용하면 별도의 변압기, 승압기, DC-DC 컨버터가 필요 없다.

보조배터리 내부에서 이미 배터리 전압을 USB `5V`로 승압한다.

```text
5000mAh USB 보조배터리
-> Pico 2 W USB 포트
-> Pico 내부 3.3V 변환
-> NEO-7M GPS 모듈 전원 공급
```

## 3. 전체 시연 구조

```text
[RC카]
  ├─ 5000mAh USB 보조배터리
  │   └─ Pico 2 W USB 전원 공급
  │
  ├─ Pico 2 W
  │   ├─ NEO-7M GPS UART 수신
  │   └─ Wi-Fi로 Spring Boot에 HTTP POST
  │
  └─ NEO-7M GPS 모듈
      └─ 위성 위치 수신

[PC]
  ├─ PostgreSQL
  ├─ Spring Boot :8585
  └─ Vue :5173
```

## 4. 전원 연결 방법

### 4.1 보조배터리에서 Pico 2 W 전원 공급

```text
5000mAh USB 보조배터리
-> USB 케이블
-> Pico 2 W USB 포트
```

Pico 2 W는 USB로 `5V`를 입력받고, 보드 내부에서 `3.3V`를 만든다.

### 4.2 Pico 2 W에서 NEO-7M 전원 공급

NEO-7M 모듈 상세 기준 동작전압은 `2.7V~5V`이므로 Pico 2 W의 `3V3 OUT`에서 전원을 공급한다.

```text
Pico 2 W 3V3 OUT -> NEO-7M VCC
Pico 2 W GND     -> NEO-7M GND
```

이 방식의 장점:

- GPS 모듈과 Pico UART 전압 레벨이 3.3V로 맞는다.
- 별도 전원 변환 장치가 필요 없다.
- RC카 시연 구성이 가볍고 단순하다.

## 5. GPS UART 배선

UART는 반드시 교차 연결한다.

```text
NEO-7M TXD -> Pico 2 W GP1 / UART0 RX
NEO-7M RXD -> Pico 2 W GP0 / UART0 TX
NEO-7M VCC -> Pico 2 W 3V3 OUT
NEO-7M GND -> Pico 2 W GND
NEO-7M PPS -> 연결하지 않음
```

전체 배선표:

| NEO-7M GPS | Pico 2 W | 설명 |
|------------|----------|------|
|     VCC    | 3V3 OUT | GPS 전원 |
|     GND    |   GND   | 공통 접지 |
|     TXD    |   GP1   | GPS 데이터 수신 |
|     RXD    |   GP0   | GPS 설정 송신, 선택 가능 |
|     PPS    |  미연결 | 이번 시연에서는 사용하지 않음 |

GPS 수신만 한다면 `RXD -> GP0`은 생략 가능하지만, 연결해 두는 것을 권장한다.

## 6. RC카 장착 위치

### 6.1 GPS 모듈 위치

NEO-7M GPS 안테나는 RC카 위쪽에 올려야 한다.

권장 위치:

```text
RC카 상단
하늘이 보이는 위치
모터/ESC/배터리와 가능한 떨어진 위치
안테나 면이 하늘 방향
```

피해야 할 위치:

```text
RC카 내부
배터리 아래
모터 또는 ESC 바로 옆
금속 프레임 아래
손이나 케이스로 안테나를 덮는 위치
```

### 6.2 고정 방법

시연용 고정 권장:

- GPS 모듈: 폼 양면테이프 또는 벨크로
- Pico 2 W: 벨크로 또는 얇은 케이스
- 보조배터리: RC카 무게중심 낮은 위치에 벨크로 또는 케이블타이
- 점퍼선: 진동으로 빠지지 않게 테이프 또는 케이블타이로 보강

## 7. 서버 실행 준비

### 7.1 PostgreSQL 실행

PostgreSQL이 먼저 실행되어 있어야 한다.

현재 Spring Boot DB 설정 기본값:

```yaml
url: jdbc:postgresql://localhost:5433/hifive
username: pgadmin
password: 1004
```

### 7.2 Spring Boot 실행

```powershell
cd C:\jh\team_hifive\ver2\straffic_hi-five-1st-project\backend
.\gradlew.bat bootRun
```

Spring Boot는 `8585` 포트로 실행된다.

```text
http://localhost:8585
```

### 7.3 PC IP 확인

Pico 2 W에서는 `localhost`를 사용할 수 없다. 반드시 PC의 실제 IP를 사용한다.

```powershell
ipconfig
```

예시:

```text
IPv4 주소: 192.168.0.25
```

Pico 코드에서는 다음 URL을 사용한다.

```text
http://192.168.0.25:8585/api/gps/telemetry
```

### 7.4 Windows 방화벽 확인

Pico 2 W가 PC Spring Boot에 접근하려면 Windows 방화벽에서 TCP `8585` 포트를 허용해야 한다.

체크 항목:

- PC와 Pico가 같은 Wi-Fi에 연결되어 있는가
- Spring Boot가 `server.address: 0.0.0.0`으로 실행되는가
- TCP 8585 인바운드가 허용되어 있는가

## 8. Spring Boot GPS API 확인

GPS 저장 endpoint:

```text
POST /api/gps/telemetry
GET  /api/gps/telemetry/latest
```

PC에서 먼저 수동 테스트한다.

```powershell
curl -X POST http://localhost:8585/api/gps/telemetry `
  -H "Content-Type: application/json" `
  -d "{\"gpsDeviceId\":\"MANUAL-TEST\",\"latitude\":37.5665,\"longitude\":126.978,\"speedKmh\":1.2,\"heading\":90.0,\"provider\":\"manual\"}"
```

조회:

```text
http://localhost:8585/api/gps/telemetry/latest
```

DB 확인:

```sql
SELECT *
FROM gps_telemetry
ORDER BY gps_telemetry_id DESC;
```

## 9. Vue 실행

```powershell
cd C:\jh\team_hifive\ver2\straffic_hi-five-1st-project\frontend
npm run dev
```

브라우저:

```text
http://localhost:5173
```

관리자 대시보드 또는 GPS Telemetry 로그 영역에서 수신 데이터가 표시되는지 확인한다.

## 10. Pico 2 W 개발 환경 준비

### 10.1 MicroPython 설치

1. Pico 2 W를 BOOTSEL 버튼을 누른 상태로 PC에 USB 연결
2. MicroPython UF2 펌웨어 복사
3. Thonny 실행
4. 인터프리터를 `MicroPython (Raspberry Pi Pico)`로 설정

### 10.2 GPS 원문 수신 테스트

먼저 GPS 모듈이 UART로 NMEA 문장을 보내는지 확인한다.

```python
from machine import UART, Pin
import time

uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))

while True:
    if uart.any():
        line = uart.readline()
        if line:
            try:
                print(line.decode().strip())
            except Exception:
                print(line)
    time.sleep(0.1)
```

정상 출력 예:

```text
$GNRMC,...
$GNGGA,...
$GPGSV,...
```

`$GNRMC` 문장에서 상태가 `A`이면 위치가 유효하다.

```text
$GNRMC,...,A,...
```

`V`이면 아직 GPS fix 전이다.

```text
$GNRMC,...,V,...
```

## 11. Pico 2 W GPS 전송 코드

아래 코드를 Pico 2 W에 `main.py`로 저장한다.

수정해야 할 값:

- `WIFI_SSID`
- `WIFI_PASSWORD`
- `SPRING_GPS_URL`

```python
import network
import time
from machine import UART, Pin

try:
    import requests
except ImportError:
    import urequests as requests

WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# PC IP로 변경한다. localhost 사용 금지.
SPRING_GPS_URL = "http://192.168.0.25:8585/api/gps/telemetry"

GPS_DEVICE_ID = "PICO2W-NEO7M-RC-01"
EDGE_NODE_ID = "EDGE-RC-01"
LANE_ID = "RC-DEMO-LANE"

# Pico UART0
# GP0 = TX, GP1 = RX
# GPS TXD -> Pico GP1
# GPS RXD -> Pico GP0
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))

POST_INTERVAL_SEC = 3
last_post_sec = 0
buffer = b""


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("WiFi connecting...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        while not wlan.isconnected():
            time.sleep(0.5)
            print(".")

    print("WiFi connected:", wlan.ifconfig())
    return wlan


def nmea_coord_to_decimal(value, direction):
    if not value:
        return None

    dot_index = value.find(".")
    if dot_index < 0:
        return None

    degree_len = dot_index - 2
    degrees = float(value[:degree_len])
    minutes = float(value[degree_len:])

    decimal = degrees + minutes / 60.0

    if direction in ("S", "W"):
        decimal = -decimal

    return decimal


def nmea_datetime_to_iso(date_str, time_str):
    if len(date_str) < 6 or len(time_str) < 6:
        return None

    day = date_str[0:2]
    month = date_str[2:4]
    year = "20" + date_str[4:6]

    hour = time_str[0:2]
    minute = time_str[2:4]
    second = time_str[4:6]

    return "{}-{}-{}T{}:{}:{}Z".format(
        year, month, day, hour, minute, second
    )


def parse_rmc(sentence):
    # Example:
    # $GNRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,...
    parts = sentence.split(",")

    if len(parts) < 10:
        return None

    status = parts[2]
    if status != "A":
        return None

    raw_lat = parts[3]
    lat_dir = parts[4]
    raw_lng = parts[5]
    lng_dir = parts[6]
    speed_knots = parts[7]
    course = parts[8]
    raw_date = parts[9]
    raw_time = parts[1]

    latitude = nmea_coord_to_decimal(raw_lat, lat_dir)
    longitude = nmea_coord_to_decimal(raw_lng, lng_dir)

    if latitude is None or longitude is None:
        return None

    speed_kmh = float(speed_knots or "0") * 1.852
    heading = float(course or "0")
    captured_at = nmea_datetime_to_iso(raw_date, raw_time)

    return {
        "latitude": latitude,
        "longitude": longitude,
        "speedKmh": speed_kmh,
        "heading": heading,
        "capturedAt": captured_at
    }


def post_gps(data):
    payload = {
        "gpsDeviceId": GPS_DEVICE_ID,
        "edgeNodeId": EDGE_NODE_ID,
        "laneId": LANE_ID,
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "speedKmh": data["speedKmh"],
        "heading": data["heading"],
        "provider": "pico2w-neo-7m"
    }

    if data.get("capturedAt"):
        payload["capturedAt"] = data["capturedAt"]

    print("POST payload:", payload)

    try:
        res = requests.post(SPRING_GPS_URL, json=payload)
        print("POST status:", res.status_code)
        print("POST response:", res.text)
        res.close()
    except Exception as e:
        print("POST failed:", e)


wlan = connect_wifi()

print("Pico 2 W NEO-7M GPS logger started")

while True:
    if wlan and not wlan.isconnected():
        wlan = connect_wifi()

    if uart.any():
        buffer += uart.read()

        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)

            try:
                sentence = line.decode().strip()
            except UnicodeError:
                continue

            if sentence.startswith("$GNRMC") or sentence.startswith("$GPRMC"):
                print(sentence)

                gps_data = parse_rmc(sentence)
                now = time.time()

                if gps_data is None:
                    print("GPS not fixed yet")
                    continue

                if now - last_post_sec >= POST_INTERVAL_SEC:
                    last_post_sec = now
                    post_gps(gps_data)

    time.sleep(0.05)
```

## 12. 시연 전 체크리스트

### 장비 체크

- [ ] Pico 2 W에 MicroPython 설치 완료
- [ ] NEO-7M GPS 모듈 도착
- [ ] 5000mAh 보조배터리 충전 완료
- [ ] 점퍼선 준비
- [ ] RC카 배터리 충전 완료
- [ ] PC와 Pico가 같은 Wi-Fi 사용 가능

### 배선 체크

- [ ] Pico `3V3 OUT` -> GPS `VCC`
- [ ] Pico `GND` -> GPS `GND`
- [ ] GPS `TXD` -> Pico `GP1`
- [ ] GPS `RXD` -> Pico `GP0`
- [ ] GPS `PPS` 미연결

### 서버 체크

- [ ] PostgreSQL 실행
- [ ] Spring Boot 실행
- [ ] Spring Boot 포트 `8585`
- [ ] Windows 방화벽 `8585` 허용
- [ ] `/api/gps/telemetry/latest` 조회 가능
- [ ] Vue 실행

### Pico 코드 체크

- [ ] Wi-Fi SSID 수정
- [ ] Wi-Fi password 수정
- [ ] `SPRING_GPS_URL`에 PC IP 입력
- [ ] `main.py`로 저장
- [ ] Thonny 콘솔에서 Wi-Fi 연결 확인

## 13. 시연 순서

### 13.1 사전 테스트

1. PC에서 PostgreSQL 실행
2. PC에서 Spring Boot 실행
3. PC에서 Vue 실행
4. Pico 2 W와 NEO-7M 연결
5. Pico 2 W를 PC USB 또는 보조배터리로 켬
6. GPS NMEA 문장 출력 확인
7. 실외 또는 창가에서 GPS fix 대기
8. Pico 콘솔에서 `POST status: 201` 또는 `POST status: 200` 확인
9. 브라우저에서 `/api/gps/telemetry/latest` 확인
10. Vue 대시보드에서 GPS 로그 확인

### 13.2 RC카 장착

1. RC카 상단에 GPS 모듈 고정
2. Pico 2 W를 GPS 근처에 고정
3. 5000mAh 보조배터리를 무게중심 낮은 곳에 고정
4. 점퍼선을 테이프 또는 케이블타이로 고정
5. RC카 전원을 켜기 전 GPS/Pico가 정상 동작하는지 확인

### 13.3 실제 시연

1. Spring Boot 실행 화면을 보여준다.
2. Vue 대시보드를 연다.
3. Pico 2 W 전원을 켠다.
4. GPS fix 상태를 확인한다.
5. RC카를 천천히 이동시킨다.
6. Vue GPS Telemetry 로그가 3초 주기로 갱신되는지 확인한다.
7. DB `gps_telemetry` row가 실시간으로 쌓이는지 확인한다.

## 14. 시연 중 보여줄 핵심 포인트

발표 시 설명 흐름:

```text
1. RC카에 장착된 GPS 모듈이 위치 데이터를 수신합니다.
2. Pico 2 W가 NMEA GPS 로그를 파싱합니다.
3. Wi-Fi를 통해 Spring Boot GPS API로 전송합니다.
4. Spring Boot는 gps_telemetry 테이블에 실시간 저장합니다.
5. Vue 관리자 대시보드는 저장된 GPS 로그를 조회해 표시합니다.
```

## 15. 트러블슈팅

### GPS 문장이 출력되지 않음

확인:

- GPS VCC/GND 연결 확인
- GPS TXD -> Pico GP1 연결 확인
- GPS RXD -> Pico GP0 연결 확인
- baudrate `9600` 확인
- 점퍼선 접촉 확인

### `GPS not fixed yet`만 계속 출력

원인:

- 실내라 위성 신호가 약함
- 안테나가 하늘을 보지 않음
- RC카 차체나 손이 안테나를 가림

조치:

- 실외로 이동
- 창가에서 1~3분 대기
- 안테나를 RC카 위쪽에 배치

### POST 실패

확인:

- Pico와 PC가 같은 Wi-Fi인지 확인
- `SPRING_GPS_URL`이 PC IP인지 확인
- `localhost`를 쓰고 있지 않은지 확인
- Spring Boot 실행 여부 확인
- Windows 방화벽 8585 허용 여부 확인

### Spring Boot에는 들어오는데 Vue에 안 보임

확인:

- `/api/gps/telemetry/latest` 직접 호출
- DB `gps_telemetry` 저장 확인
- Vue dev server 실행 확인
- Vue proxy가 Spring Boot `8585`로 연결되는지 확인

### 주행 중 Pico가 꺼짐

확인:

- 보조배터리 자동 꺼짐 기능
- USB 케이블 접촉
- RC카 진동으로 인한 전원선 이탈

조치:

- 케이블 고정
- 보조배터리를 충분히 충전
- 저전류 자동 꺼짐이 없는 보조배터리 사용

## 16. 최종 성공 기준

다음이 모두 확인되면 시연 성공으로 판단한다.

- [ ] Pico 2 W가 Wi-Fi에 연결된다.
- [ ] NEO-7M GPS에서 NMEA 문장이 수신된다.
- [ ] `$GNRMC` 상태가 `A`로 바뀐다.
- [ ] Pico가 Spring Boot `/api/gps/telemetry`에 POST한다.
- [ ] Spring Boot 응답이 `200` 또는 `201`이다.
- [ ] PostgreSQL `gps_telemetry`에 row가 쌓인다.
- [ ] Vue 대시보드에서 GPS Telemetry 로그가 갱신된다.

