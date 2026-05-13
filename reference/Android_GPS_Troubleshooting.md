# Android GPS Logger 프로젝트 트러블슈팅 & 구축 기록

작성일: 2026-05-07
작성자: 안민수

## 1. 프로젝트 목표

최종 목표는 Android 스마트폰 GPS 위치 데이터를 실시간으로 수집하고, CSV로 저장한 뒤 Spring Boot 서버로 전송하여 PostgreSQL에 저장하는 시스템을 구축하는 것이다.

최종 파이프라인:

```text
Android GPS
→ Termux:API
→ Python Logger
→ CSV 저장
→ Spring Boot API
→ PostgreSQL 저장
```

## 2. 초기 방향: GPS 모듈 구매 검토

초기에는 실제 GPS 하드웨어 모듈 구매를 검토하였다.

### 2.1 검토한 GPS 제품

| 제품 | 특징 | 장점 | 단점 |
| --- | --- | --- | --- |
| NEO-6M GPS 모듈 | UART 기반, NEO-6M + HC-05 블루투스 구성 가능 | 저렴하고 개발 실험용으로 적합, NMEA 직접 확인 가능 | 배선, 블루투스 연결, 전원 구성이 필요 |
| USB GPS 수신기 | 노트북 연결이 쉬움 | PC 테스트에 적합 | 스마트폰 연동이 어렵고 모바일 테스트에 비효율적 |
| Bluetooth GPS Receiver | Dual XGPS160, Garmin GLO 2 등 | 안정적이고 상용 수준 품질 | 가격이 높고 개발 테스트용으로 과함 |

## 3. 방향 변경: 스마트폰 GPS 사용

GPS 모듈 구매 전 즉시 테스트가 필요했기 때문에 Android 스마트폰 내장 GPS를 활용하는 방식으로 변경하였다.

## 4. 스마트폰 GPS 상태 테스트

### GPSTest

목적:
- 실제 GPS 수신 상태 확인
- 위성 수 확인
- Accuracy 확인
- 위치 변화 확인

### Geo Tracker

목적:
- 이동 시 GPS 좌표 변화 확인
- 실제 이동 경로 기록 가능 여부 확인

## 5. Python 기반 GPS Logger 시도

목표는 별도 앱 없이 Python 코드로 GPS 로그를 수집하는 것이었다.

## 6. Pydroid 시도 및 실패

Pydroid는 Python 실행이 가능하고 설치가 간단해서 먼저 시도하였다.

발생 오류:

```text
No such file or directory: termux-location
```

원인:
- `termux-location`은 Termux 내부 명령어이다.
- Pydroid 환경에서는 Termux 명령어를 실행할 수 없다.

결론:

```text
Pydroid ≠ Termux
```

## 7. 최종 방향: Termux 기반 구조

Termux는 Linux shell, Android API 연동, Python 실행을 모두 지원한다.

따라서 GPS 수집과 Python 처리를 동시에 수행할 수 있어 최종 방향으로 선택하였다.

## 8. Termux 설치 문제

초기에는 Play Store 버전 Termux를 사용했다.

발생 오류:

```text
Termux:API is not yet available on Google Play
```

원인:
- Google 정책 변경으로 Play Store 버전 Termux 지원이 중단되었다.

해결:
- F-Droid 설치
- F-Droid에서 Termux 설치
- F-Droid에서 Termux:API 설치

필수 설치 앱:
- F-Droid
- Termux
- Termux:API

## 9. 권한 문제

발생 오류:

```text
android.permission.ACCESS_FINE_LOCATION
```

원인:
- Android 위치 권한이 허용되지 않았다.

해결:
- 설정 → 앱 → Termux → 위치 허용
- 설정 → 앱 → Termux:API → 위치 허용
- 정확한 위치 ON

## 10. GPS 정상 확인

Termux에서 아래 명령어로 GPS 수신 여부를 확인한다.

```bash
termux-location -p gps -r once
```

정상 출력 예:

```json
{
  "latitude": 37.xxxx,
  "longitude": 126.xxxx
}
```

## 11. Python GPS Logger 구현

사용 기술:
- Python
- subprocess
- termux-location

처리 구조:

```text
termux-location 실행
→ JSON 반환
→ Python 처리
→ CSV 저장
```

## 12. 저장소 권한 문제

발생 오류:

```text
Permission denied:
/storage/emulated/0/Download/gps_log.csv
```

원인:
- Android 저장소 sandbox 정책 때문에 직접 접근이 제한되었다.

해결 명령:

```bash
termux-setup-storage
```

최종 저장 경로:

```python
CSV_FILE = "/data/data/com.termux/files/home/storage/downloads/gps_log.csv"
```

## 13. nano 사용 문제

문제:
- 스마트폰에서의 파이썬 nano 저장 방법이 익숙하지 않아 파일 저장에 어려움이 있었다.

해결:

```text
CTRL 버튼을 누른채로 키보드를 활성화 하여 조합 방식으로 해결
저장: CTRL + O
종료: CTRL + X
```

## 14. Python 문법 오류

발생 오류:

```text
SyntaxError
```

원인:
- 두 줄이 한 줄로 붙어 Python 문법 오류 발생

잘못된 예:

```python
CSV_FILE = "..."import subprocess
```

해결:

```python
import subprocess

CSV_FILE = "..."
```

## 15. GPS Logger 성공

최종 성공 상태:
- 1초마다 GPS 좌표 기록 성공
- CSV 저장 성공

출력 예:

```text
2026-05-03 13:50:01 37.xxxx 126.xxxx
```

## 16. CSV 확인 방법

Termux에서 확인:

```bash
tail ~/storage/downloads/gps_log.csv
```

스마트폰 파일 앱에서 확인:

```text
내 파일 → Download → gps_log.csv
```

## 17. Spring Boot 서버 연동

목표:
- GPS 데이터를 실시간으로 서버에 전송
- 서버에서 PostgreSQL에 저장

## 18. 서버 구조

전체 구조:

```text
Android GPS
→ Termux Python
→ REST API
→ Spring Boot
→ PostgreSQL
```

## 19. Spring Boot 설계

사용 기술:
- Spring Boot
- REST API
- PostgreSQL
- JPA

API:

```http
POST /api/gps/log
```

저장 데이터:
- deviceId
- timestamp
- latitude
- longitude
- accuracy
- speed
- altitude
- provider

## 20. 네트워크 문제

중요 포인트:
- 스마트폰 기준 `localhost`는 스마트폰 자신을 의미한다.
- PC에서 실행 중인 Spring Boot 서버로 접근하려면 PC 내부 IP를 사용해야 한다.

예:

```text
http://192.168.0.15:8585
```

## 21. 최종 성공 파이프라인

```text
Android GPS
↓
termux-location
↓
Python gps_logger.py
↓
CSV 저장
↓
Spring Boot REST API
↓
PostgreSQL 저장
```

## 22. GPS 시스템 핵심 구조 이해

GPS는 사용자 정보를 제공하지 않고 위치 정보만 제공한다.

따라서 프로젝트에서는 아래 구조가 필요하다.

```text
GPS Device ID
→ 서버
→ 사용자 또는 차량 매핑
```

## 23. 최종 기술 스택

### 모바일

- Android
- Termux
- Termux:API
- Python

### 서버

- Spring Boot
- PostgreSQL

## 24. 최종적으로 성공한 기능

- GPS 위치 수집
- 1초 단위 기록
- CSV 저장
- Python 처리
- 서버 전송 가능 구조 확보

## 25. 이후 확장 가능 기능

- 실시간 지도 표시
- 차량 이동 분석
- 경로 시각화
- 속도 분석
- WebSocket 스트리밍
- Kafka 이벤트 처리
- GPS 이상 감지

## 26. 최종 결론

GPS 모듈 구매 없이 Android 스마트폰과 Termux 기반으로 아래 파이프라인을 구축할 수 있었다.

```text
GPS 수집
→ CSV 저장
→ Spring Boot 전송
→ PostgreSQL 저장
```

즉, Android 스마트폰 내장 GPS만으로도 프로젝트의 GPS 로그 수집 및 서버 연동 테스트가 가능하다.

## 27. NEO-7M GPS 모듈 최종 선택 및 재검토

초기에는 스마트폰 GPS 기반으로 빠르게 테스트를 진행했지만, 실제 RC카 시연 환경을 고려하여 하드웨어 GPS 모듈도 함께 검토하였다.

최종 하드웨어 GPS 후보로는 `NEO-7M GPS 모듈`을 선택하였다.

선택 이유:
- 가격이 비교적 저렴하다.
- UART 기반이라 Pico 2 W, ESP32 계열 보드와 연결하기 쉽다.
- NMEA 로그를 직접 확인할 수 있다.
- 외부 안테나를 사용할 수 있어 야외 수신 테스트에 적합하다.
- RC카 위에 탑재하여 독립 GPS 단말처럼 구성할 수 있다.

예상 구성:

```text
NEO-7M GPS 모듈
→ Pico 2 W 또는 ESP32
→ Python/MicroPython Logger
→ Spring Boot API
→ PostgreSQL 저장
```

## 28. NEO-7M 금일 테스트 결과

금일 NEO-7M GPS 모듈을 이용해 실내 및 외부 환경에서 GPS 수신 테스트를 진행하였다.

### 28.1 실내 테스트 결과

테스트 환경:
- 실내 창가 근처
- 안테나가 하늘을 바라보도록 배치
- NEO-7M 모듈 연결 후 GPS 로그 수신 확인

결과:
- GPS 위성이 1개만 수신됨
- 유효한 GPS Fix가 잡히지 않음
- 서버로 전송 가능한 GPS 로그 수신 불가

판단:
- 실내 환경에서는 NEO-7M 모듈이 위성을 충분히 확보하지 못했다.
- GPS 로그가 DB에 저장될 수준의 좌표 데이터가 생성되지 않았다.

### 28.2 외부 공원 테스트 결과

테스트 환경:
- 외부 공원
- 하늘이 비교적 개방된 장소
- GPS 모듈을 외부에서 일정 시간 대기

결과:
- GPS 위성은 약 9개까지 수신됨
- 그러나 에페메리스(Ephemeris) 이슈로 인해 즉시 유효 좌표 로그가 생성되지 않음
- 위성 수는 확보되었지만 GPS Fix 및 로그 수신이 지연되는 이벤트 발생

확인된 문제:
- NEO-7M은 전원을 켠 직후 바로 안정적인 위치 로그가 나오지 않을 수 있다.
- 에페메리스 데이터를 수신하고 위치를 안정화하기까지 시간이 필요하다.
- 테스트 환경에 따라 10분 이상 대기해야 유효 GPS 로그를 수신할 수 있다.

## 29. 시연 관점에서의 최종 판단

프로젝트 시연은 빠르게 장비를 켜고 GPS 로그가 서버와 DB에 들어오는 것을 보여줘야 한다.

하지만 NEO-7M 기반 구성은 다음 문제가 있었다.

- 실내에서는 위성 수가 부족해 GPS 로그 수신이 불가능했다.
- 외부에서는 위성 9개가 잡혀도 에페메리스 이슈로 즉시 로그가 들어오지 않았다.
- 유효 좌표 수신까지 10분 이상 대기해야 할 수 있다.
- 시연 시간 안에 안정적으로 GPS Fix를 보장하기 어렵다.

따라서 빠른 시연과 안정적인 로그 수집을 우선해야 하는 현재 프로젝트 상황에서는 GPS 모듈 기반 방식이 적합하지 않다고 판단하였다.

최종 결정:

```text
NEO-7M GPS 모듈 기반 시연 보류
→ Android 스마트폰 내장 GPS + Termux 방식으로 복귀
```

최종 시연 파이프라인:

```text
Android GPS
→ Termux:API
→ Python Logger
→ CSV 저장
→ Spring Boot API
→ PostgreSQL 저장
```

이 방식은 별도 GPS 모듈의 초기 수신 대기 시간, 에페메리스 문제, 실내 수신 불안정성을 피할 수 있으며, 시연 환경에서 더 안정적으로 GPS 로그를 확보할 수 있다.
