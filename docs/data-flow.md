# Clasp 데이터 흐름 요약

## 1. 전체 개요 (한 줄)

**폴더 선택 → 스캔(파일 수집 → 메타데이터 → 표지 → 본문 추출 → 분류 → 유사도) → DB 저장 → 결과 화면에서 조회**

---

## 2. 단계별 흐름

```
[프론트엔드]                    [백엔드 API]                     [DB / 로컬 파일]
     │                               │                                    │
     │  POST /scan/start             │                                    │
     │  { folder_path }  ──────────► │  scan_id 발급, 메모리에 등록       │
     │                               │                                    │
     │  GET /scan/progress (SSE)     │                                    │
     │  ?scan_id=xxx       ──────────│──► run_scan(scan_id, folder_path)   │
     │                               │         │                          │
     │                               │         ▼ Stage 1: 파일 목록 수집   │
     │                               │    _collect_files() ──────────────►│ 디스크 순회
     │                               │         │                          │
     │                               │         ▼ Stage 2: 메타데이터      │
     │                               │    _get_metadata() ───────────────►│ os.stat()
     │                               │    File 레코드 생성/갱신 ──────────►│ files 테이블
     │                               │         │                          │
     │                               │         ▼ Stage 3: 표지 탐지       │
     │                               │    extract_cover_text() ───────────►│ PDF/DOCX 첫페이지만 읽기
     │                               │    save_cover() ──────────────────►│ cover_pages
     │                               │         │                          │
     │                               │         ▼ Stage 4: 본문 추출       │
     │                               │    extract_text() ─────────────────►│ PDF/DOCX/등 실제 읽기
     │                               │    extracted_text_summary 저장 ────►│ files.extracted_text_summary
     │                               │         │                          │
     │                               │         ▼ Stage 5: 분류            │
     │                               │    pipeline.classify()              │
     │                               │      → Tier1(규칙)                  │
     │                               │      → Tier2(임베딩)  (이미 뽑은 텍스트만 사용)
     │                               │      → Tier3(LLM, 선택)             │
     │                               │    Classification 저장 ────────────►│ classifications
     │                               │         │                          │
     │                               │         ▼ Stage 6: 유사도           │
     │                               │    compute_similarity_groups() ────►│ cover_similarity_groups
     │                               │         │                          │
     │  ◄────────── SSE 이벤트 (stage, message, completed...) ────────────│
     │                               │                                    │
     │  GET /files?scan_id=xxx       │                                    │
     │  (결과 목록 조회)   ──────────►│  list_files() ────────────────────►│ files + classifications
     │  ◄────────── JSON (파일 목록 + category, tag, tier_used...) ────────│
     │                               │                                    │
```

---

## 3. “파일 내용”이 오가는 곳

| 시점 | 하는 일 | 파일을 디스크에서 읽나? | 데이터가 가는 곳 |
|------|----------|--------------------------|------------------|
| Stage 3 | 표지 탐지 | ✅ PDF/DOCX 첫 페이지만 | `cover_texts` (메모리) → `cover_pages` (DB) |
| Stage 4 | 본문 추출 | ✅ 확장자별 샘플/캡 (최대 5000자 등) | `extracted_texts` (메모리) + `files.extracted_text_summary` (DB) |
| Stage 5 | 분류 | ❌ 안 읽음 | `extracted_texts` / `cover_texts`만 pipeline에 전달 → Tier1/2/3가 사용 |

→ **파일 내용을 “읽어서 쓰는” 건 스캔의 Stage 3·4 한 번뿐**이고, Stage 5(분류)는 이미 읽은 문자열만 사용합니다.

---

## 4. DB 테이블 역할

- **files**: 경로, 파일명, 확장자, 크기, 수정일, **extracted_text_summary**(본문 요약 2000자)
- **classifications**: 파일별 카테고리, 태그, tier_used, confidence_score, is_manual (같은 파일이라도 scan_id별로 행 존재)
- **cover_pages**: 표지 텍스트 + 임베딩(JSON)
- **cover_similarity_groups**: 표지 유사한 파일끼리 그룹 (임계값 0.80), auto_tag
- **rules**: 사용자 규칙 (Tier1에서 사용)
- **custom_extensions**: 확장자→카테고리 (Tier1)
- **custom_categories**: 사용자 정의 카테고리 목록
- **action_logs**: 정리 적용/되돌리기 이력 (개별 파일 단위)
- **action_batches**: Undo 배치 단위 묶음 (action_logs 그룹화)

---

## 5. 프론트엔드 → 백엔드 호출 순서

1. **스캔 시작**: `POST /scan/start` → `scan_id` 수신
2. **진행률 수신**: `GET /scan/progress?scan_id=...` (SSE) → stage 1~7 이벤트 수신
3. **결과 조회**: `GET /files?scan_id=...` → 파일 목록 + 분류 결과
4. **수동 수정**: `PATCH /files/:id` → category/tag 변경
5. **유사 파일**: `GET /files/:id/similar` → 표지 유사 파일 목록
6. **정리 적용**: `POST /apply` → 실제 파일 이동 + action_logs 기록
7. **되돌리기**: `POST /undo` → action_logs 기반 복구

---

## 6. 요약

- **데이터가 “생성”되는 곳**: 스캔 서비스 `run_scan()` (Stage 1~6)
- **파일 내용을 “읽는” 시점**: Stage 3(표지), Stage 4(본문) — 그 후에는 전부 이미 읽은 텍스트만 사용
- **분류 결과가 “저장”되는 곳**: Stage 5에서 `classifications` 테이블
- **사용자가 “보는” 데이터**: `GET /files`로 files + classifications 조회한 결과
