# 챗봇 DB 스키마/데이터

팀원이 챗봇을 독립 실행할 때 필요한 PostgreSQL 테이블과 seed 데이터입니다.

## 적용 순서

PostgreSQL DB가 실행 중인 상태에서 아래 순서로 실행합니다.

```powershell
psql -h 127.0.0.1 -p 5433 -U hifive -d hifive -f C:\Users\A\Desktop\chatbot\db\01_schema.sql
psql -h 127.0.0.1 -p 5433 -U hifive -d hifive -f C:\Users\A\Desktop\chatbot\db\02_seed_dashboard_data.sql
```

Docker 컨테이너 안에서 실행한다면 예시는 아래와 같습니다.

```powershell
docker cp C:\Users\A\Desktop\chatbot\db\01_schema.sql hifive-postgres:/tmp/01_schema.sql
docker cp C:\Users\A\Desktop\chatbot\db\02_seed_dashboard_data.sql hifive-postgres:/tmp/02_seed_dashboard_data.sql
docker exec -it hifive-postgres psql -U hifive -d hifive -f /tmp/01_schema.sql
docker exec -it hifive-postgres psql -U hifive -d hifive -f /tmp/02_seed_dashboard_data.sql
```

## 들어있는 데이터

날짜는 `CURRENT_DATE` 기준으로 생성됩니다.

- 오늘 통행 이벤트
  - 상행 684대
  - 하행 564대
- 오늘 GPS 정상
  - 상행 667건
  - 하행 545건
- 오늘 검수 대기
  - 상행 17건
  - 하행 19건
- 오늘 통행료
  - 상행 1,342,600원
  - 하행 1,108,200원
- 어제 통행/정산 데이터
- 지난달 GPS 판정 903건
- 최신 GPS 수신 데이터 1건
- 회원 대시보드 현재 상태 1건
- 상행/하행 현장 알림 6건

## 주의

`02_seed_dashboard_data.sql`은 `CHATBOT-SEED-%`로 시작하는 기존 seed 이벤트와 관련 정산 데이터를 지운 뒤 다시 넣습니다. 운영 DB가 아니라 개발/테스트 DB에서 사용하세요.
