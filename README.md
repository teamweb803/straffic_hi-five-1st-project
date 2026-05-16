# HIFIVE Smart Tolling

차량 번호판 인식과 GPS 기반 통행 판정을 활용한 스마트 톨링 프로젝트입니다.

## 구성

- Jetson Edge: 영상 입력 및 차량/번호판 인식
- Python/FastAPI Ingress: Edge 이벤트 수신
- Spring Boot Backend: 통행 이벤트, GPS 판정, 정산 API
- Vue Frontend: 운영자/관리자 화면
- PostgreSQL: 통행 및 운영 데이터 저장

