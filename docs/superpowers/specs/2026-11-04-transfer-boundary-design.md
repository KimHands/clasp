# 전송 경계 설계

개편 범위 B의 두 번째 묶음이다. 구현 순서를 문서 끝에 함께 적는다.

## 목표

파일 내용이 이 컴퓨터 밖으로 나가는 코드 경로를 없애고, 이를 테스트로 고정한다. 같은 컴퓨터의 다른 프로그램이나 웹 페이지가 인증 없이 앱의 로컬 API를 쓰지 못하게 한다.

### 보장 범위

- 보장한다: 분류 과정에서 파일 내용과 파일명이 루프백이 아닌 주소로 전송되지 않는다.
- 보장하지 않는다: 임베딩 모델이 없을 때의 첫 다운로드는 Hugging Face와 통신한다. 파일 내용은 포함되지 않으며, 받은 뒤에는 캐시만 쓴다.
- 보장하지 않는다: 사용자가 지정한 로컬 LLM 서버가 받은 내용을 어떻게 처리하는지. 루프백 주소의 프록시가 외부로 전달하는 경우도 막을 수 없다.
- 위협 모델 밖: 같은 사용자 권한으로 실행 중인 악성 프로세스. 토큰은 환경 변수와 프로세스 메모리에 있으므로 이를 읽을 수 있는 프로세스는 막지 못한다.

## 현재 문제

임시 폴더에서 실제 백엔드를 실행해 재현했다.

| 시나리오 | 현재 결과 |
|---|---|
| API 키 등록 후 스캔 | 본문이 있는 파일 10개 전부 외부로 전송. 가상 주민번호가 평문으로 포함 |
| 주입에 성공한 LLM 응답 | `../../탈출`, 신뢰도 1.0이 그대로 저장되고 그 이름의 폴더로 이동 |
| 민감 파일 키워드 등록 | `localStorage`에만 저장되고 백엔드로 전달되지 않음 |
| 토큰 없는 API 호출 | API 키 교체 성공 |
| 위조한 Host 헤더 | 통과 |
| 8000 포트를 다른 앱이 사용 | 저장된 API 키를 그 앱으로 전송하는 코드 경로 존재 |

## 결정

### Tier 3는 로컬 LLM 전용

- OpenAI, Gemini 코드와 `openai`, `google-genai` 의존성, API 키 저장·동기화 코드, 설정 UI를 제거한다.
- OpenAI 호환 `/chat/completions`를 `httpx`로 호출한다. LM Studio와 Ollama가 해당한다.
- `validate_local_base_url(url)`은 `http`, `https`만 허용하고, 호스트가 `127.0.0.1`, `localhost`, `::1`이 아니거나 사용자 정보가 있으면 거부한다. 저장할 때와 호출할 때 모두 검사한다.
- 클라이언트는 `trust_env=False`, `follow_redirects=False`, 읽기 제한 60초와 호출 전체 상한 120초를 둔다. 프록시 환경 변수와 리다이렉트로 외부에 나가지 않기 위해서다.
- 기본값은 꺼짐이다. 설정은 새 테이블 `app_settings`(`key` PK, `value`)에 저장한다.
- 스캔마다 `Tier3Session`을 하나 만든다. 호출이 2회 연속 실패하면 그 스캔의 남은 파일은 Tier 3를 건너뛴다.

### LLM 출력 가드레일

LLM 응답은 신뢰하지 않는 입력으로 다룬다.

- 카테고리가 허용 목록(기본 5개 + 사용자 정의)에 없으면 응답 전체를 버린다.
- 신뢰도는 숫자가 아니면 버리고, `[0, 0.85]`로 자른다. 수동 분류(1.0)나 사용자 규칙(0.85)을 넘지 못하게 하기 위해서다.
- 태그는 문자열이고 1~40자이며 경로 구분자와 제어 문자가 없을 때만 받는다. 아니면 태그만 버린다.
- `<think>...</think>`를 제거한 뒤 JSON을 파싱한다.
- 파일 내용과 파일명은 `<file_content>`, `<file_name>`으로 감싸고, 안에 같은 태그가 있으면 지운다. 시스템 프롬프트는 태그 안을 데이터로만 다루라고 지시한다. 이 지시로 주입을 막을 수 있다고 보지 않으며, 방어선은 위 출력 검증이다.

### 민감 파일 키워드

- 새 테이블 `sensitive_keywords`(`id`, `keyword` 유니크)에 저장하고 `GET`, `POST`, `DELETE /settings/sensitive-keywords`로 다룬다. 비교는 대소문자를 구분하지 않고 NFC로 맞춘다.
- 파일명에 키워드가 있으면 표지와 본문을 읽지 않고 Tier 1만 쓴다.
- 이미 저장된 `extracted_text_summary`, `CoverPage`, `CoverSimilarityGroup`은 그 스캔에서 지우고 재분류한다.
- 기존 `localStorage` 값은 옮기지 않는다. 저장된 적만 있고 동작한 적이 없는 값이라, 이전하지 않아도 동작이 나빠지지 않는다.

### 로컬 API 통제

- Electron이 실행마다 `crypto.randomBytes(32)` 토큰과 빈 포트를 정해 `CLASP_API_TOKEN`, `CLASP_PORT`로 백엔드에 넘긴다.
- ASGI 미들웨어 `LocalAccessMiddleware`가 모든 HTTP 요청을 검사한다.
  - Host 호스트명이 `127.0.0.1`, `localhost`, `[::1]`이 아니면 403.
  - `X-Clasp-Token`이 환경 변수와 같지 않으면 401. 비교는 `hmac.compare_digest`로 한다.
  - 환경 변수가 없으면 모든 요청을 401로 거부한다.
  - CORS 사전 요청은 CORS 미들웨어가 먼저 처리한다.
- 허용 Origin은 `CLASP_ALLOWED_ORIGIN` 하나로 Electron이 정한다. 개발은 Vite 주소, 배포는 `null`(`file://`)이다. 토큰이 실제 인증이고 Origin은 추가 방어다.
- `docs_url`, `redoc_url`, `openapi_url`을 끈다.
- Electron은 토큰을 붙인 `GET /health` 응답의 `service`가 `clasp-backend`일 때만 준비된 것으로 본다.
- 렌더러는 `electronAPI.getBackendConfig()`로 주소와 토큰을 받는다. SSE는 `fetch` 스트리밍으로 바꿔 URL에 토큰을 남기지 않는다.
- Vite는 `CLASP_VITE_PORT`(기본 5173)와 `strictPort`로 뜨고, `dev:electron`은 `concurrently -k`로 실패 시 함께 끝난다. 다른 프로젝트의 서버를 불러오는 일을 막는다.

### Electron 보강

- `sandbox: true`를 켜고, 새 창은 모두 거부하며, 앱 주소 밖으로의 이동을 막는다.
- 배포 빌드의 `index.html`에 CSP를 넣는다. `default-src 'self'`, `connect-src http://127.0.0.1:*`, `style-src 'self' 'unsafe-inline'`, `img-src 'self' data:`. 개발 서버는 Vite의 인라인 스크립트가 필요해 적용하지 않는다.
- `SIGTERM`, `SIGINT`에서 앱을 정상 종료해 백엔드가 남지 않게 한다.
- `HF_HUB_DISABLE_TELEMETRY=1`을 설정한다.

### 범위 밖

- 이전 버전이 저장한 `clasp-settings.json`은 읽지 않을 뿐 지우지 않는다. 사용자 파일을 지우는 일이기 때문이다.
- 키워드 변경 후 변경 없는 파일의 재분류, 신뢰도 결합: 분류 품질 묶음.

## 테스트

- `validate_local_base_url`: 루프백 허용, 외부 주소, 루프백처럼 보이는 호스트(`127.0.0.1.evil.example`, `localhost@evil.example`), 사용자 정보 거부.
- 출력 가드레일: 허용 밖 카테고리, 경로 조작 카테고리, 신뢰도 1.0·문자열·NaN, 잘못된 태그, `<think>` 포함 응답.
- 전송 경계(가짜 로컬 LLM):
  - 파이프라인 전체를 도는 동안 `sys.addaudithook` 대신 `socket.socket.connect`를 감싸 루프백이 아닌 연결을 기록하고 0건을 확인한다.
  - 프록시 환경 변수를 외부 주소로 설정해도 그 주소로 연결하지 않는다.
  - 로컬 서버의 외부 리다이렉트를 따라가지 않는다.
  - 2회 연속 실패 후 호출을 멈춘다.
- 정적 검사: `backend/`(venv, tests 제외) AST에 `openai`, `google`, `requests`, `aiohttp`, `urllib.request`, `socket` import가 없고 `httpx`는 `engines/tier3_llm.py`에만 있다.
- 민감 키워드: 본문과 표지를 읽지 않음, 저장된 내용 삭제, 대소문자·NFC, 본문이 LLM으로 전달되지 않음.
- 접근 통제: 토큰 없음·틀림 401, 환경 변수 없음 401, Host 위조 403, 정상 200, `/docs` 404, 악성 Origin에 CORS 헤더 없음.
- 실제 측정: 실제 앱과 실제 모델로 스캔하며 감사 훅으로 소켓 연결을 기록해 외부 연결 0건을 확인한다.

## 완료 기준

- 위 테스트가 통과한다.
- "현재 문제" 표의 시나리오를 다시 돌렸을 때 재현되지 않는다.
- 실제 앱에서 스캔, 로컬 LLM 연결 시험, 민감 키워드가 동작한다.

## 구현 순서

1. 접근 통제 미들웨어와 `main.py`, `run.py`, 테스트 클라이언트.
2. `tier3_llm.py` 재작성, 출력 가드레일, `pipeline`과 `scan_service` 연결, 의존성 제거.
3. 민감 키워드와 설정 API.
4. Electron, preload, `client.js`, SSE, 설정 화면, Vite 설정.
5. 전송 경계 테스트, 실제 측정, API 문서와 `AGENTS.md` 수정.

## 다른 벤더 리뷰와 실측

| 지적·발견 | 판정 | 근거·조치 |
|---|---|---|
| httpx 제한 시간은 조금씩 오는 응답의 전체 시간을 제한하지 못한다 | 수용 | `asyncio.wait_for`로 전체 상한 추가 |
| 인증 헤더가 CORS 허용 헤더에 없으면 사전 요청이 막힌다 | 수용 | 허용 헤더에 추가하고 회귀 테스트 |
| 입력 태그 포장은 전송 경계에 기여하지 않는다 | 기각 | 사실이지만 프롬프트 품질에 쓰이고 비용이 작아 유지. 방어선으로 세지 않음 |
| (실측) 감사 훅이 uvloop 연결을 보지 못해 첫 측정이 불완전했다 | 조치 | asyncio 루프로 재측정. 스캔 전체에서 소켓 연결은 로컬 LLM 10건뿐 |
| (실측) 모델이 있어도 Hugging Face에 연결한다 | 조치 | 캐시를 먼저 사용하고 없을 때만 내려받음 |
