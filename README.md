# Clasp — 파일 정리 및 시각화 도구

> 로컬 파일을 자동으로 분류하고, 분류 결과를 마인드맵으로 시각화하는 **프라이버시 우선** 데스크톱 애플리케이션

---

## 프로젝트 소개

### 해결하려는 문제

대학생, 직장인, 개발자 모두 공통적으로 겪는 문제가 있습니다:

- 다운로드 폴더에 쌓인 수백 개의 파일을 수동으로 분류하는 **시간 낭비**
- 어떤 파일이 어떤 과목/프로젝트에 속하는지 **파악이 어려움**
- 파일 정리를 위해 클라우드 서비스에 파일을 업로드하면 **프라이버시 침해** 우려

### 해결 방향

Clasp은 **3단계 AI 분류 엔진**을 통해 파일을 자동으로 분류하고, 그 결과를 **마인드맵 시각화**로 직관적으로 보여줍니다. 모든 처리는 로컬에서 이루어지며, 파일 원문은 외부 서버로 전송되지 않습니다.

### 타겟 사용자

| 사용자 | 주요 시나리오 | 기대 효과 |
|---|---|---|
| 대학생 | 과제·강의 자료 정리, 과목별 파일 묶음 파악 | 학기별 자료를 자동 그룹화하여 시험 기간 자료 탐색 시간 단축 |
| 직장인 | 업무 문서 정리, 프로젝트별 파일 분류 | 프로젝트 산출물을 체계적으로 관리 |
| 개발자 | 기술 스택별 자료 정리, 폴더 계층 시각화 | 기술 문서와 코드 자료를 카테고리별로 자동 정리 |

---

## 주요 기능

### 1. 3단계 Tier 자동 분류 엔진

```
Tier 1 — 규칙 기반 (항상 동작)
  ├── 사용자 정의 규칙 (우선순위 적용) + 파일명 연도 태그 자동 생성
  ├── 확장자 매핑 (기본 55개 + 사용자 커스텀)
  └── 파일명 날짜 정규식
      → 신뢰도 ≥ 0.80: 분류 확정
      → 신뢰도 < 0.80: Tier 2 호출

Tier 2 — 임베딩 유사도 (텍스트 추출 가능 파일)
  └── sentence-transformers 임베딩 + 코사인 유사도
      → 신뢰도 ≥ 0.50: 분류 확정
      → 신뢰도 < 0.50 + API 키 있음: Tier 3 호출
      → 신뢰도 < 0.50 + API 키 없음: 미분류 처리

태그 추론: 규칙 카테고리가 TAG_CANDIDATES에 없으면 T2 카테고리로 fallback
Tier 3 — 클라우드 LLM (선택적, API 키 필요)
  └── OpenAI API 분류

미분류: confidence_score < 0.31 → 격리, 파일 이동 제외
```

### 2. 마인드맵 시각화

- React SVG 기반 커스텀 마인드맵 — 카드형 노드, S자 곡선 연결
- 카테고리 → 태그 → 파일 계층 구조를 트리 형태로 시각화
- 노드 접기/펼치기, 클릭 시 파일 상세 정보 패널 표시
- 신뢰도 낮은 파일은 색상으로 강조 표시
- **ref 기반 DOM 직접 조작**으로 드래그 시 리렌더 제거 (60fps)
- **Pointer Capture** 적용 — 빠른 드래그 시에도 커서 이탈 없이 안정적 조작
- **커서 위치 기준 줌** — 마우스가 가리키는 지점을 중심으로 확대/축소

### 3. 표지 유사도 탐지

- PDF·DOCX 첫 페이지(표지)를 자동 탐지하여 임베딩 생성
- 표지 간 코사인 유사도 ≥ 0.75인 파일을 같은 태그 그룹으로 자동 묶음
- 같은 과목의 과제·강의 자료를 자동으로 그룹화

### 4. 규칙 관리 & 확장자 커스텀

- 날짜·내용·확장자 기반 정리 규칙을 **드래그 앤 드롭**으로 우선순위 설정
- 규칙 추가 시 카테고리별 주요 확장자 드롭다운 제공 (55개 기본 내장)
- 설정에서 확장자 추가/삭제 — 분류 엔진에 자동 반영

### 5. 정리 적용 & 폴더별 Undo 이력

- 분류 결과에 따라 실제 파일 이동 실행
- 이동 전 트리뷰 미리보기 (이동 파일 수, 생성 폴더 수 요약)
- **폴더별 정리 이력 자동 기록** — 폴더를 다시 열면 과거 모든 적용 이력 조회 가능
- **선택적 Undo** — 최신뿐 아니라 과거 어떤 적용이든 독립적으로 되돌리기 가능
- 타임라인 UI로 이력 시각화 (이동 건수, 시각, 충돌 처리 방식, 되돌림 상태 표시)

### 6. 실시간 진행 표시

- SSE(Server-Sent Events) 스트림으로 스캔 7단계 진행 상황 실시간 표시
- 현재 처리 중인 파일명, 완료 수/전체 수 실시간 업데이트

---

## 기술 스택

### 아키텍처 개요

```
┌─────────────────────────────────────────────────┐
│                  Electron Shell                  │
│  ┌───────────────────────────────────────────┐   │
│  │           React + Vite (Renderer)         │   │
│  │  ┌─────────┐ ┌──────────┐ ┌───────────┐  │   │
│  │  │ Zustand  │ │ shadcn/ui│ │ SVG 마인드│  │   │
│  │  │  Store   │ │ Tailwind │ │    맵     │  │   │
│  │  └────┬─────┘ └──────────┘ └───────────┘  │   │
│  │       │  API 호출 (axios)                  │   │
│  └───────┼───────────────────────────────────┘   │
│          │  IPC (preload.js)                     │
└──────────┼───────────────────────────────────────┘
           │  HTTP (localhost:8000)
┌──────────▼───────────────────────────────────────┐
│              Python FastAPI Backend               │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │ Routers  │ │   Services   │ │   Engines    │  │
│  │ scan     │ │ scan_service │ │ tier1_rule   │  │
│  │ files    │ │ classify_svc │ │ tier2_embed  │  │
│  │ rules    │ │ cover_svc    │ │ tier3_llm    │  │
│  │ apply    │ │ action_svc   │ │ pipeline     │  │
│  └──────────┘ └──────────────┘ └──────────────┘  │
│  ┌──────────────────────────────────────────────┐ │
│  │  SQLite + SQLAlchemy ORM (clasp.db)          │ │
│  └──────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────┘
```

### Frontend

| 기술 | 버전 | 역할 |
|---|---|---|
| Electron | 40.x | 데스크톱 앱 셸, IPC 통신, 백엔드 프로세스 관리 |
| React | 19.x | UI 프레임워크 |
| Vite | 7.x | 빌드 도구 (HMR 개발 서버) |
| Zustand | 5.x | 전역 상태 관리 (scan, file, rule, apply, extension, theme) |
| shadcn/ui + Tailwind CSS | 4.x | UI 컴포넌트 라이브러리 |
| @dnd-kit | 6.x | 드래그 앤 드롭 (규칙 우선순위 설정) |
| React Router | 7.x | 페이지 라우팅 (HashRouter) |
| Lucide React | — | 아이콘 라이브러리 |

### Backend

| 기술 | 버전 | 역할 |
|---|---|---|
| Python FastAPI | 0.115+ | 비동기 REST API 서버 (localhost:8000) |
| SQLite + SQLAlchemy | 2.0+ | 로컬 데이터베이스 ORM |
| PyMuPDF | 1.24+ | PDF 텍스트 추출 (페이지 단위) |
| python-docx | 1.1+ | DOCX 단락 추출 |
| sentence-transformers | 3.0+ | Tier 2 임베딩 (paraphrase-multilingual-MiniLM-L12-v2) |
| scikit-learn | 1.5+ | 코사인 유사도 계산 |
| OpenAI API | 1.40+ | Tier 3 LLM 분류 (선택적) |
| sse-starlette | 2.1+ | SSE 스트리밍 |
| PyInstaller | — | 백엔드 바이너리 번들링 (사용자 Python 설치 불필요) |

---

## AI 도구 활용

본 프로젝트는 **바이브코딩(Vibe Coding)** 방식으로 개발되었으며, 여러 AI 도구를 목적에 맞게 연계 활용하였습니다.

| AI 도구 | 활용 목적 | 활용 내용 |
|---|---|---|
| Cursor (AI IDE) | 코드 생성 및 리팩토링 | 프로젝트 전체 코드 생성, 아키텍처 설계, 코드 리뷰 및 개선 |
| sentence-transformers | Tier 2 임베딩 분류 | 다국어 경량 모델로 파일 내용 기반 자동 분류 구현 |
| OpenAI API | Tier 3 LLM 분류 | 임베딩으로 분류 어려운 파일에 대해 클라우드 LLM 보조 분류 |
| Claude | 기획 및 문서 작성 | 요구사항 명세서, API 명세서, README 구조화 |

### AI 결과물의 독자적 활용

- AI가 생성한 코드를 그대로 사용하지 않고, **프로젝트 구조에 맞게 재구성**
- Tier 시스템의 임계값(0.80, 0.50, 0.31)은 실제 파일 테스트를 통해 **경험적으로 조정**
- 표지 유사도 탐지 로직은 대학 과제 파일의 특성을 분석하여 **도메인 특화 설계**

---

## 프로젝트 구조

```
Clasp/
├── frontend/                        # Electron + React 프론트엔드
│   ├── electron/
│   │   ├── main.js                  # Electron 메인 프로세스 (백엔드 자동 시작, IPC)
│   │   └── preload.js               # IPC 브릿지 (폴더 선택, API Key 관리)
│   ├── src/
│   │   ├── api/                     # FastAPI 호출 함수 (중앙화)
│   │   │   ├── client.js            # Axios 인스턴스
│   │   │   ├── scan.js              # 스캔 API
│   │   │   ├── files.js             # 파일 API
│   │   │   ├── rules.js             # 규칙 API
│   │   │   ├── apply.js             # 정리 적용 API
│   │   │   └── settings.js          # 설정 API
│   │   ├── components/              # 공통 컴포넌트
│   │   │   ├── GraphView.jsx        # SVG 마인드맵 시각화
│   │   │   ├── FileDetailPanel.jsx  # 파일 상세 슬라이드 패널
│   │   │   └── ui/                  # shadcn/ui (Button, Badge, Dialog, Toast 등)
│   │   ├── pages/                   # 페이지 컴포넌트
│   │   │   ├── Home.jsx             # 홈 — 폴더 선택, 최근 작업
│   │   │   ├── Scan.jsx             # 스캔 — 실시간 진행 표시
│   │   │   ├── Result.jsx           # 결과 — 리스트/마인드맵 뷰
│   │   │   ├── RuleManager.jsx      # 규칙 — 드래그 앤 드롭 관리
│   │   │   ├── Apply.jsx            # 정리 — 미리보기 및 실행
│   │   │   └── Settings.jsx         # 설정 — 확장자/API Key 관리
│   │   ├── store/                   # Zustand 상태 관리
│   │   │   ├── scanStore.js         # 스캔 상태
│   │   │   ├── fileStore.js         # 파일 목록 상태
│   │   │   ├── ruleStore.js         # 규칙 상태
│   │   │   ├── applyStore.js        # 정리 적용 상태
│   │   │   ├── extensionStore.js    # 확장자 상태
│   │   │   └── themeStore.js        # 테마 상태
│   │   └── graph/                   # 마인드맵 데이터 변환
│   ├── package.json
│   └── vite.config.js
│
├── backend/                         # Python FastAPI 백엔드
│   ├── routers/                     # API 라우터
│   │   ├── scan.py                  # 스캔 시작 + SSE 진행 스트림
│   │   ├── files.py                 # 파일 조회/수정
│   │   ├── rules.py                 # 규칙 CRUD
│   │   ├── apply.py                 # 정리 적용/되돌리기
│   │   └── settings.py              # 확장자 관리
│   ├── services/                    # 비즈니스 로직
│   │   ├── scan_service.py          # 폴더 스캔 + 메타데이터 수집
│   │   ├── classify_service.py      # 분류 파이프라인 실행
│   │   ├── cover_service.py         # 표지 탐지 + 유사도 그룹화
│   │   └── action_service.py        # 파일 이동/되돌리기
│   ├── engines/                     # 분류 엔진
│   │   ├── pipeline.py              # Tier 1→2→3 파이프라인 조율
│   │   ├── tier1_rule.py            # 규칙 기반 분류
│   │   ├── tier2_embedding.py       # 임베딩 유사도 분류
│   │   └── tier3_llm.py             # OpenAI LLM 분류
│   ├── models/
│   │   └── schema.py                # SQLAlchemy 모델 정의
│   ├── utils/
│   │   ├── text_extractor.py        # PDF/DOCX 텍스트 추출
│   │   ├── cover_detector.py        # 표지 탐지 로직
│   │   ├── response.py              # 공통 응답 포맷
│   │   └── errors.py                # 에러 코드 정의
│   ├── main.py                      # FastAPI 앱 진입점
│   ├── database.py                  # DB 초기화 (SQLite)
│   ├── run.py                       # 개발 서버 실행
│   └── requirements.txt             # Python 의존성
│
├── build.sh                         # 전체 빌드 스크립트
├── 요구사항_명세서.md                # 기능/비기능 요구사항 및 Use Case
└── API_명세서.md                    # REST API 엔드포인트 상세 명세
```

---

## 데이터베이스 스키마

```sql
-- 스캔된 파일 메타데이터
files (id, path, filename, extension, created_at, modified_at, size, extracted_text_summary)

-- 분류 결과 (Tier 정보 + 신뢰도 포함)
classifications (file_id, category, tag, tier_used, confidence_score, is_manual)

-- 표지 텍스트 및 임베딩 벡터
cover_pages (file_id, cover_text, embedding, detected_at)

-- 표지 유사도 기반 자동 그룹
cover_similarity_groups (group_id, file_id, similarity_score, auto_tag)

-- 폴더별 정리 적용 배치 (이력 조회 및 선택적 Undo 단위)
action_batches (action_log_id, folder_path, scan_id, moved_count, skipped_count, failed_count, conflict_resolution, executed_at, is_undone)

-- 파일 이동 로그 (Undo 지원, action_batches FK)
action_logs (id, action_log_id, action_type, source_path, destination_path, executed_at, is_undone)

-- 사용자 정의 정리 규칙
rules (id, priority, type, value, folder_name, parent_id)

-- 사용자 커스텀 확장자
custom_extensions (id, extension, category)
```

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/scan/start` | 스캔 시작 (BackgroundTask) |
| `GET` | `/scan/progress` | SSE 진행 상황 스트림 (7단계) |
| `GET` | `/files` | 분류 결과 목록 조회 (필터/페이지네이션) |
| `PATCH` | `/files/{id}` | 수동 분류 수정 (is_manual = true) |
| `GET` | `/files/{id}/similar` | 표지 유사 파일 목록 |
| `GET` | `/rules` | 규칙 목록 조회 |
| `POST` | `/rules` | 규칙 추가 |
| `PATCH` | `/rules/{id}` | 규칙 수정 |
| `DELETE` | `/rules/{id}` | 규칙 삭제 |
| `GET` | `/settings/extensions` | 확장자 목록 조회 (기본 + 커스텀) |
| `POST` | `/settings/extensions` | 커스텀 확장자 추가 |
| `DELETE` | `/settings/extensions/{id}` | 커스텀 확장자 삭제 |
| `GET` | `/apply/preview` | 정리 적용 미리보기 (트리뷰) |
| `POST` | `/apply` | 정리 적용 실행 |
| `POST` | `/undo` | 되돌리기 |
| `GET` | `/apply/history` | 폴더별 정리 적용 이력 조회 |

> 자세한 요청/응답 형식은 [API 명세서](./API_명세서.md)를 참고하세요.

---

## 시작하기

### 사전 요구사항

- **Node.js** 18 이상
- **Python** 3.11 이상
- (선택) **OpenAI API Key** — Tier 3 분류 사용 시

### 1단계: 저장소 클론

```bash
git clone https://github.com/<username>/Clasp.git
cd Clasp
```

### 2단계: 백엔드 설정

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

> 백엔드가 `http://localhost:8000`에서 실행됩니다.  
> 첫 실행 시 sentence-transformers 모델(약 500MB)이 자동 다운로드됩니다.

### 3단계: 프론트엔드 개발 실행

```bash
cd frontend
npm install
npm run dev:electron
```

> Vite 개발 서버(5173)와 Electron 앱이 동시에 실행됩니다.

### 4단계: 프로덕션 빌드

```bash
chmod +x build.sh
./build.sh
```

> 빌드 과정:
> 1. PyInstaller로 백엔드 바이너리 번들
> 2. Vite로 프론트엔드 프로덕션 빌드
> 3. electron-builder로 앱 패키징
>
> 결과물: `frontend/release/` (macOS DMG / Windows NSIS)

---

## 사용 흐름

```
1. 폴더 선택        사용자가 정리할 폴더를 선택
       ↓
2. 스캔 시작        파일 수집 → 메타데이터 분석 → 표지 탐지 → 본문 추출 → 분류 → 유사도 계산
       ↓
3. 결과 확인        리스트 뷰 또는 마인드맵 뷰로 분류 결과 확인
       ↓
4. 분류 수정        필요 시 카테고리/태그 수동 수정 (다음 스캔에 학습 반영)
       ↓
5. 규칙 설정        날짜 → 내용 → 확장자 순서로 정리 규칙 우선순위 설정
       ↓
6. 정리 적용        미리보기 확인 후 실제 파일 이동 실행
       ↓
7. 되돌리기         문제 발생 시 원클릭 Undo
```

---

## 기본 확장자 매핑 (55개)

| 카테고리 | 확장자 |
|---|---|
| 문서 | pdf, docx, doc, txt, md, hwp, rtf |
| 프레젠테이션 | pptx, ppt, key |
| 스프레드시트 | xlsx, xls, csv |
| 데이터 | json, xml, yaml, sql |
| 코드 | py, js, ts, jsx, tsx, java, cpp, c, h, go, rs, html, css |
| 이미지 | jpg, jpeg, png, gif, svg, webp, bmp |
| 영상 | mp4, mov, avi, mkv, webm |
| 오디오 | mp3, wav, flac, aac, ogg |
| 압축 | zip, tar, gz, rar, 7z |

---

## 비기능 요구사항

| 분류 | 항목 | 기준 |
|---|---|---|
| 성능 | 스캔 속도 | 파일 100개 기준 60초 이내 분류 완료 |
| 성능 | 그래프 렌더링 | 파일 100개 이상에서 3초 이내 렌더링 |
| 보안 | 파일 원문 외부 전송 | Tier 3 사용 시에도 요약 텍스트만 전송, 원문 전송 금지 |
| 호환성 | 지원 운영체제 | macOS (arm64/x64), Windows (x64) |
| 호환성 | Python 설치 | 사용자 별도 Python 설치 불필요 (PyInstaller 번들) |
| 안정성 | Undo | 정리 적용 후 원상복구 보장 (복구 불가 항목은 명시) |
| 사용성 | 미분류 파일 | 신뢰도 31% 미만 파일은 이동 대상 자동 제외 |
| 사용성 | 실시간 진행 | SSE로 스캔 7단계 진행 상황 실시간 표시 |

---

## 제약 사항

| 항목 | 내용 |
|---|---|
| HWP 지원 | 공개 파서 불안정으로 메타데이터 기반 처리만 지원 |
| 비텍스트 파일 | 이미지/영상/exe는 내용 분류 불가, Tier 1만 사용 |
| 대용량 폴더 | 파일 수천 개 이상 시 Tier 2 처리 속도 저하 가능 |
| 표지 탐지 | 정형화된 표지가 없는 파일은 탐지 누락 가능 |
| Local LLM | 하드웨어 제한으로 미지원, 경량 임베딩 모델(Tier 2)로 대체 |

---

## 지원 플랫폼

| 플랫폼 | 아키텍처 | 패키징 형식 |
|---|---|---|
| macOS | arm64, x64 | DMG |
| Windows | x64 | NSIS |

---

## 관련 문서

- [요구사항 명세서](./요구사항_명세서.md) — 기능/비기능 요구사항, Use Case 정의
- [API 명세서](./API_명세서.md) — REST API 엔드포인트 상세 명세

---

## 라이선스

Private — All rights reserved.
