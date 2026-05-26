# HiFive 챗봇 분리본

이 폴더는 메인 프로젝트에 챗봇을 붙이기 위해 필요한 파일만 남긴 구성입니다.

## 포함 항목

```text
app/
db/
frontend-integration/
.env.example
.gitignore
README.md
requirements.txt
```

## 역할

- `app/`
  - FastAPI 챗봇 API 코드입니다.
  - PostgreSQL을 직접 조회해서 답변합니다.
- `db/`
  - 챗봇이 조회하는 PostgreSQL 테이블 스키마와 seed 데이터입니다.
  - 팀원이 같은 데이터로 테스트할 수 있도록 포함합니다.
- `frontend-integration/`
  - Vue 프로젝트에 붙일 챗봇 API 파일과 플로팅 위젯 컴포넌트입니다.
- `.env.example`
  - 로컬 실행용 환경변수 예시입니다.

## DB 적용

PostgreSQL이 실행 중이어야 합니다.

```powershell
psql -h 127.0.0.1 -p 5433 -U hifive -d hifive -f C:\Users\A\Desktop\chatbot\db\01_schema.sql
psql -h 127.0.0.1 -p 5433 -U hifive -d hifive -f C:\Users\A\Desktop\chatbot\db\02_seed_dashboard_data.sql
```

## 챗봇 API 실행

```powershell
cd C:\Users\A\Desktop\chatbot
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## API

```text
POST /api/chat
POST /api/chatbot
POST /api/chatbot/ask
GET  /healthz
GET  /status
GET  /video/status
```

요청 예시:

```json
{
  "question": "오늘 정산 현황 알려줘"
}
```

## 프론트 적용

메인 Vue 프로젝트에 아래 파일을 붙입니다.

```text
frontend-integration/api/chatbot.js
frontend-integration/components/ChatbotFloatingWidget.vue
```

Vite proxy는 `/chatbot-api`를 FastAPI `http://localhost:8000`으로 보내면 됩니다.

```js
'/chatbot-api': {
  target: 'http://localhost:8000',
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/chatbot-api/, '')
}
```

## 제외한 파일 위치

구버전 테스트 파일과 불필요한 파일은 아래로 옮겼습니다.

```text
C:\Users\A\Desktop\no\chatbot_excluded_20260526
```
