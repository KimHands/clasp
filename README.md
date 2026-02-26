# Clasp — 파일 정리 및 시각화 도구

로컬 파일을 자동으로 분류하고, 분류 결과를 그래프로 시각화하는 데스크톱 애플리케이션입니다.  
파일 원문을 외부 서버로 전송하지 않는 **프라이버시 우선** 설계를 기반으로 합니다.

---

## 주요 기능

- **자동 분류**: 확장자·날짜·파일 내용 기반 3단계 Tier 분류 엔진
- **그래프 시각화**: Cytoscape.js 기반 태그 클러스터 / 트리 / 포스 다이렉티드 레이아웃
- **표지 유사도 탐지**: PDF·DOCX 표지 임베딩으로 같은 과목 파일 자동 그룹화
- **규칙 관리**: 날짜·내용·확장자 기반 정리 규칙을 드래그 앤 드롭으로 우선순위 설정
- **정리 적용 & Undo**: 파일 이동 실행 후 원클릭 되돌리기 지원
- **실시간 진행 표시**: SSE 스트림으로 스캔 단계별 진행 상황 실시간 표시

---

## 타겟 사용자

| 사용자 | 주요 시나리오 |
|---|---|
| 대학생 | 과제·강의 자료 정리, 과목별 파일 묶음 파악 |
| 직장인 | 업무 문서 정리, 프로젝트별 파일 분류 |
| 개발자 | 기술 스택별 자료 정리, 폴더 계층 시각화 |

---

## 기술 스택

### Frontend
| 기술 | 역할 |
|---|---|
| Electron + electron-builder | 데스크톱 앱 패키징 |
| React 19 + Vite | UI 프레임워크 |
| Zustand | 전역 상태 관리 |
| shadcn/ui + Tailwind CSS | UI 컴포넌트 |
| Cytoscape.js + fcose | 그래프 시각화 |
| SSE | 실시간 스캔 진행 수신 |

### Backend
| 기술 | 역할 |
|---|---|
| Python FastAPI | 비동기 REST API 서버 (localhost:8000) |
| SQLite + SQLAlchemy ORM | 로컬 데이터베이스 |
| PyMuPDF | PDF 텍스트 추출 |
| python-docx | DOCX 단락 추출 |
| sentence-transformers | Tier 2 임베딩 (paraphrase-multilingual-MiniLM-L12-v2) |
| scikit-learn | 코사인 유사도 계산 |
| OpenAI API | Tier 3 LLM (선택적, API 키 필요) |
| sse-starlette | SSE 스트리밍 |
| PyInstaller | 백엔드 번들링 (사용자 Python 설치 불필요) |

---

## 분류 엔진 (Tier System)

```
Tier 1 — 규칙 기반 (항상 동작)
  ├── 확장자 매핑 딕셔너리
  └── 파일명 날짜 정규식
      → 신뢰도 높음: Tier 2 스킵
      → 신뢰도 낮음: Tier 2 호출

Tier 2 — 임베딩 유사도 (텍스트 추출 가능 파일)
  └── sentence-transformers 임베딩 + 코사인 유사도
      → 신뢰도 높음: 결과 저장
      → 신뢰도 낮음 + API 키 있음: Tier 3 호출
      → 신뢰도 낮음 + API 키 없음: 미분류 처리

Tier 3 — 클라우드 LLM (선택적)
  └── OpenAI API 분류

미분류: confidence_score < 0.31 → 격리, 파일 이동 제외
```

---

## 프로젝트 구조

```
Clasp/
├── frontend/
│   ├── src/
│   │   ├── components/       # 공유 UI 컴포넌트 (GraphView, FileDetailPanel 등)
│   │   ├── pages/            # Home, Scan, Result, RuleManager, Apply, Settings
│   │   ├── store/            # Zustand 스토어 (scan, file, rule, apply)
│   │   ├── api/              # FastAPI 호출 함수 (중앙화)
│   │   └── graph/            # Cytoscape.js 설정
│   └── electron/
│       ├── main.js           # Electron 메인 프로세스
│       └── preload.js
│
├── backend/
│   ├── routers/              # scan.py, files.py, rules.py, apply.py
│   ├── services/             # scan_service, classify_service, cover_service, action_service
│   ├── engines/              # tier1_rule, tier2_embedding, tier3_llm, pipeline
│   ├── models/               # schema.py (SQLAlchemy 모델)
│   └── utils/                # text_extractor.py, cover_detector.py
│
├── build.sh                  # 전체 빌드 스크립트
├── 요구사항_명세서.md
└── API_명세서.md
```

---

## 시작하기

### 사전 요구사항

- Node.js 18+
- Python 3.11+
- (선택) OpenAI API Key — Tier 3 분류 사용 시

### 1. 백엔드 설정

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

백엔드가 `http://localhost:8000` 에서 실행됩니다.

### 2. 프론트엔드 개발 실행

```bash
cd frontend
npm install
npm run dev:electron
```

### 3. 프로덕션 빌드

프로젝트 루트에서 실행합니다.

```bash
chmod +x build.sh
./build.sh
```

빌드 결과물은 `frontend/release/` 에 생성됩니다.

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/scan/start` | 스캔 시작 |
| `GET` | `/scan/progress` | SSE 진행 상황 스트림 |
| `GET` | `/files` | 분류 결과 목록 조회 |
| `PATCH` | `/files/{id}` | 수동 분류 수정 |
| `GET` | `/files/{id}/similar` | 표지 유사 파일 목록 |
| `GET` | `/rules` | 규칙 목록 조회 |
| `POST` | `/rules` | 규칙 추가 |
| `PATCH` | `/rules/{id}` | 규칙 수정 |
| `DELETE` | `/rules/{id}` | 규칙 삭제 |
| `GET` | `/apply/preview` | 정리 적용 미리보기 |
| `POST` | `/apply` | 정리 적용 실행 |
| `POST` | `/undo` | 되돌리기 |

자세한 내용은 [API 명세서](./API_명세서.md)를 참고하세요.

---

## 데이터베이스 스키마

```sql
files (id, path, filename, extension, created_at, modified_at, size, extracted_text_summary)

classifications (file_id, category, tag, tier_used, confidence_score, is_manual)

cover_pages (file_id, cover_text, embedding, detected_at)

cover_similarity_groups (group_id, file_id, similarity_score, auto_tag)

action_logs (id, action_type, source_path, destination_path, executed_at, is_undone)
```

---

## 지원 플랫폼

| 플랫폼 | 아키텍처 |
|---|---|
| macOS | arm64, x64 |
| Windows | x64 |

---

## 라이선스

Private — All rights reserved.
