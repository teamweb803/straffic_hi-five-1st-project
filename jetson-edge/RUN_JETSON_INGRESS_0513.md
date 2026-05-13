# HI-FIVE LAN End-to-End Runbook

기준 구조:

```text
Jetson source(MP4 demo or camera)
-> DeepStream nvinfer YOLO
-> Python TensorRT OCR worker
-> PassageEvent protobuf
-> WebTransport
-> Python Ingress
-> Spring REST POST
```

MP4는 카메라 대체 source다. 운영 파이프라인은 카메라와 같은 경로를 탄다.

## 1. Jetson 파일 반영

Windows PC:

```powershell
cd "C:\Users\ez\Desktop\민진깃\straffic_hi-five-1st-project\jetson-edge"
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_runtime_to_jetson.ps1 -JetsonHost jetson@192.168.10.99 -JetsonApp /home/jetson/hifive/app
```

Jetson:

```bash
cd ~/hifive/app/deepstream_plugins
make clean
make
make install
```

`.so` 결과:

```text
/home/jetson/hifive/deepstream_plugins/libnvdsinfer_custom_hifive.so
```

## 2. Python Ingress 실행

Ingress PC:

```powershell
cd "C:\Users\ez\Desktop\민진깃\straffic_hi-five-1st-project\fastapi-edge\webtransport_ingress"
python run_webtransport_ingress.py --host 0.0.0.0 --port 4433 --cert certs\ingress.crt --key certs\ingress.key --spring-url http://127.0.0.1:8585/api/ingest/passage-events --ops-host 0.0.0.0 --ops-port 8000
```

Spring에 status endpoint가 준비된 뒤에는 아래 옵션을 추가한다.

```powershell
--spring-edge-status-url http://127.0.0.1:8585/api/edge/status --spring-ingress-status-url http://127.0.0.1:8585/api/ingress/status --ingress-status-forward-interval-sec 1
```

현재 Spring에 확실히 있는 endpoint는 PassageEvent:

```text
POST /api/ingest/passage-events
Content-Type: application/x-protobuf
X-Event-Id: {event_id}
```

## 3. Jetson 서비스 실행

Jetson:

```bash
pkill -f run_edge_service.py || true
pkill -f run_deepstream_nvinfer.py || true
cd ~/hifive/app
source ~/hifive/.venv/bin/activate
PYTHONPATH=. python run_edge_service.py --config example_runtime_config.py --runtime-runner deepstream-nvinfer --ingress-host 192.168.10.96 --ingress-port 4433 --transport-queue-size 256 --status-interval-sec 1
```

서비스형 실행의 기본 source 시작은 display를 켜지 않는다. 화면 확인이 필요할 때만 source 호출에 `display=true`를 붙인다.

## 4. MP4 source 시작

Jetson 새 터미널:

```bash
curl -X POST "http://127.0.0.1:8010/source/video?video=/home/jetson/hifive/videos/IMG_4806.mp4&display=false"
```

DeepStream 화면 확인:

```bash
curl -X POST "http://127.0.0.1:8010/source/video?video=/home/jetson/hifive/videos/IMG_4806.mp4&display=true"
```

상태:

```bash
curl http://127.0.0.1:8010/status
```

중단:

```bash
curl -X POST "http://127.0.0.1:8010/source/stop?wait_sec=3"
```

카메라 source는 config의 camera source를 사용한다.

```bash
curl -X POST "http://127.0.0.1:8010/source/camera?camera_index=0&display=false"
```

## 5. Ingress 확인

Ingress PC:

```powershell
$s = Invoke-RestMethod http://127.0.0.1:8000/status
$s.received_events
$s.acked_events
$s.edge_status_events
$s.spring_forward | ConvertTo-Json -Depth 10
$s.latest_edge_status | ConvertTo-Json -Depth 10
```

실제 인식 이벤트만 보기:

```powershell
$s.recent_events | Where-Object { $_.event_id -notlike "edge-status-*" -and $_.event_id -notlike "network-transition-*" }
```

정상 기준:

```text
received_events 증가
acked_events 증가
spring_forward.status = accepted
edge_status_events 증가
latest_edge_status.runtime.processed_frames 증가
```
