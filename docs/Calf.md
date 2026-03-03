# Clasp 파일 분류 시스템 상세 분석

> **Calf (Clasp Analysis & Logic File)**  
> 작성일: 2026-02-26  
> 목적: Clasp의 파일 분류 원리, 신뢰도 산출 방식, 데이터 파이프라인 전 과정 정리

---

## 1. 전체 아키텍처 개요

Clasp의 분류 시스템은 **3단계 Tier 파이프라인**으로 구성됩니다.  
각 Tier는 이전 Tier의 신뢰도(confidence_score)를 기준으로 다음 단계 실행 여부를 결정합니다.

```
파일 입력
  │
  ▼
[Tier 1] 규칙 기반 분류 ──────────────────────────────────────┐
  │ confidence ≥ 0.80                                          │
  │ 또는 텍스트 추출 불가 확장자                                │
  │                                                            │
  ▼ confidence < 0.80                                          │
[Tier 2] 임베딩 유사도 분류 ─────────────────────────────────┐ │
  │ confidence ≥ 0.50                                          │ │
  │ 또는 T1·T2 카테고리 일치 시 앙상블 보정                    │ │
  │                                                            │ │
  ▼ confidence < 0.50                                          │ │
[Tier 3] 클라우드 LLM 분류 (API Key 필요)                     │ │
  │                                                            │ │
  ▼                                                            │ │
최종 결과 ◄──────────────────────────────────────────────────┘ ┘
  │
  ▼
confidence < 0.31 → 미분류(격리)
confidence ≥ 0.31 → 분류 결과 저장
```

---

## 2. 스캔 파이프라인 (7단계)

스캔 시작(`POST /scan/start`) 후 SSE로 실시간 진행 상황이 프론트엔드에 전달됩니다.

| Stage | 작업 | 설명 |
|-------|------|------|
| 1 | 파일 목록 수집 | 폴더 재귀 탐색, 시스템 디렉토리 제외 |
| 2 | 메타데이터 분석 | 파일 크기, 생성/수정일 수집 → DB 저장 |
| 3 | 표지 탐지 | PDF/DOCX 첫 페이지 표지 여부 판정 |
| 4 | 본문 추출 | PDF 4구간 샘플링, DOCX 단락 추출 |
| 5 | 분류 엔진 처리 | Tier 1→2→3 파이프라인 실행 |
| 6 | 유사도 계산 | 표지 임베딩 코사인 유사도로 그룹화 |
| 7 | 완료 | 결과 저장 완료 |

### 제외 대상

```python
# 제외 디렉토리
EXCLUDED_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "dist", "build", "release", ".cache", ...
}

# 제외 확장자 (바이너리/컴파일 결과물)
EXCLUDED_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".so", ".dylib", ".dll", ".exe"}
```

---

## 3. 텍스트 추출 전략

분류 품질은 텍스트 추출 품질에 직결됩니다. 파일 형식별 전략이 다릅니다.

### 3-1. PDF — 4구간 샘플링

```
총 페이지: N
  ├── 1~2페이지 스킵 (표지/목차, 3페이지 이상인 경우)
  └── 유효 페이지에서 4구간 샘플링
        ├── 30% 지점 → 300자
        ├── 45% 지점 → 300자
        ├── 65% 지점 → 300자
        └── 85% 지점 → 300자
        총 최대 1,200자
```

**설계 의도:** 표지/목차는 내용이 없거나 오해를 유발할 수 있어 스킵합니다.  
본문 전체를 읽으면 느리므로, 4개 지점을 균등하게 샘플링해 내용을 추론합니다.

### 3-2. DOCX — 단락 기반 추출

```
python-docx로 단락(paragraph) 단위 추출
빈 단락 제거 후 최대 5,000자
```

### 3-3. TXT / MD — 전체 읽기

```
UTF-8 인코딩, 최대 5,000자
```

### 3-4. 이미지·영상·오디오·압축 파일

텍스트 추출 불가 → Tier 1 결과만 사용 (확장자 기반 분류)

---

## 4. 표지 탐지 (Cover Detection)

표지 탐지는 분류 품질 향상과 유사 파일 그룹화에 활용됩니다.

### 표지 판정 기준

```python
def is_cover_page(text: str) -> bool:
    # 조건 1: 텍스트 길이 300자 미만
    if len(stripped) >= 300:
        return False
    # 조건 2: 날짜 패턴 또는 학번 패턴 포함
    has_date = bool(_DATE_PATTERN.search(stripped))      # 2024-01-01, 2024년 1월 등
    has_student_id = bool(_STUDENT_ID_PATTERN.search(stripped))  # 20XXXXXXXX
    return has_date or has_student_id
```

표지로 판정된 경우:
- `cover_pages` 테이블에 텍스트 + 임베딩 벡터 저장
- 본문 추출이 없는 파일의 경우, 표지 텍스트를 Tier 2 입력으로 fallback 활용
- Stage 6에서 표지 임베딩 간 코사인 유사도 ≥ 0.75인 파일을 같은 그룹으로 묶어 `auto_tag` 부여

---

## 5. Tier 1 — 규칙 기반 분류

**파일:** `backend/engines/tier1_rule.py`

### 신뢰도 산출 규칙

| 조건 | confidence_score | 설명 |
|------|-----------------|------|
| 수동 분류 (`is_manual=True`) | **1.0** | 사용자가 직접 지정한 분류 |
| 사용자 정의 규칙 매칭 | **0.85** | Rules 테이블에 등록된 규칙 |
| 파일명 키워드 패턴 매칭 | **0.82** | 아래 키워드 패턴 참조 |
| 확장자 기본 매핑 | **0.70** | 확장자 → 카테고리 딕셔너리 |
| 매핑 없음 | **0.0** | 미분류 후보 |

### 파일명 키워드 패턴 (confidence 0.82)

| 패턴 | 카테고리 |
|------|---------|
| 과제, 레포트, report, assignment | 문서 |
| 발표, presentation, 슬라이드 | 프레젠테이션 |
| 회의록, minutes, meeting | 문서 |
| 기획서, proposal, 계획서, 사업계획 | 문서 |
| 계약서, contract, 협약 | 문서 |
| 논문, thesis, dissertation, paper | 문서 |
| 매뉴얼, manual, 지침서, 가이드, guide | 문서 |

### 확장자 기본 매핑 (confidence 0.70)

| 확장자 | 카테고리 |
|--------|---------|
| pdf, docx, doc, txt, md, hwp, rtf | 문서 |
| pptx, ppt, key | 프레젠테이션 |
| xlsx, xls, csv | 스프레드시트 |
| json, xml, yaml, sql | 데이터 |
| py, js, ts, java, cpp, go, rs, html, css | 코드 |
| jpg, png, gif, svg, webp | 이미지 |
| mp4, mov, avi, mkv | 영상 |
| mp3, wav, flac, aac | 오디오 |
| zip, tar, gz, rar, 7z | 압축 |

### 연도 태그 자동 생성

파일명에서 연도 패턴(`20XX` 또는 `19XX`)이 발견되면 자동으로 태그를 생성합니다.

```
파일명: "2024_운영체제_과제.pdf"
  → category: "문서"
  → tag: "문서_2024"
  → confidence: 0.82 (파일명 키워드 "과제" 매칭)
```

### 사용자 정의 규칙 유형

| 규칙 유형 | 매칭 방식 |
|----------|---------|
| `extension` | 확장자 완전 일치 |
| `date` | 파일명에서 연도 추출 후 비교 |
| `content` | 추출된 텍스트 또는 파일명에 키워드 포함 여부 |

---

## 6. Tier 2 — 임베딩 유사도 분류

**파일:** `backend/engines/tier2_embedding.py`  
**모델:** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers)

### 동작 원리

```
1. 추출된 텍스트 → 384차원 임베딩 벡터 생성 (최대 2,000자 입력)
2. 5개 카테고리별 대표 키워드 임베딩의 평균 벡터와 코사인 유사도 계산
3. 가장 높은 유사도를 가진 카테고리 선택
4. 유사도 > 0.3이면 해당 카테고리 반환, 이하면 None
```

### 카테고리별 대표 키워드

| 카테고리 | 대표 키워드 (일부) |
|---------|-----------------|
| 문서 | 보고서, report, 논문, paper, 과제, 레포트, 계획서, 회의록, 계약서, 매뉴얼 |
| 프레젠테이션 | 발표, presentation, 슬라이드, PPT, keynote, 덱, 세미나 |
| 스프레드시트 | 스프레드시트, 엑셀, excel, 통계, 집계, 예산, 정산, 재무 |
| 코드 | 프로그래밍, 코드, 함수, 알고리즘, 보안, 데이터베이스, 머신러닝 |
| 데이터 | 데이터, data, 분석, CSV, JSON, SQL, ETL, 로그, 전처리 |

### 카테고리 임베딩 계산 방식

```python
# 키워드별 개별 임베딩 후 평균 — 단순 문자열 결합보다 각 키워드 의미가 고르게 반영됨
keyword_embs = model.encode(keywords)
category_embedding = keyword_embs.mean(axis=0)
```

### 세부 태그 추론 (infer_tag)

카테고리가 결정된 후, 텍스트와 태그 후보 임베딩 간 유사도로 세부 태그를 추론합니다.

```
threshold: 0.45 이상인 후보 중 최고 유사도 태그 선택

예시 (카테고리: 문서)
  태그 후보: 논문, 보고서, 기획서, 계획서, 회의록, 계약서, 매뉴얼, 제안서 ...
  텍스트 임베딩과 각 태그 임베딩 코사인 유사도 계산
  → 최고 유사도 태그 반환 (0.45 미만이면 None)
```

### 피드백 학습 (apply_feedback)

사용자가 수동으로 분류를 수정하면, 해당 카테고리의 임베딩이 점진적으로 보정됩니다.

```python
learning_rate = 0.05
updated_emb = (1 - 0.05) * current_emb + 0.05 * text_emb
# L2 정규화로 코사인 유사도 계산 안정성 유지
```

> 기존 임베딩 95% + 새 텍스트 임베딩 5% 가중 이동 평균  
> 재시작 전까지 즉시 효과 발생 (메모리 캐시 직접 갱신)

---

## 7. Tier 3 — 클라우드 LLM 분류

**파일:** `backend/engines/tier3_llm.py`  
**지원 모델:** OpenAI GPT-4o-mini (우선), Google Gemini 2.5 Flash

### 실행 조건

- Tier 2 confidence < 0.50
- OpenAI API Key 또는 Gemini API Key가 환경변수에 설정된 경우

### 입력 구성

```
[파일명]
2024_운영체제_과제.pdf

[텍스트 요약]
(추출된 본문 텍스트, 최대 2,000자)
```

### 시스템 프롬프트 핵심

- 5개 카테고리 중 하나만 반환
- JSON 형식 강제 (`category`, `tag`, `confidence_score`)
- 프롬프트 인젝션 방어: 텍스트 내 분류 지시 변경 시도 무시
- temperature=0.1 (결정적 응답)

### Tier 3 채택 조건

```python
if t3["confidence_score"] > max(t1["confidence_score"], t2["confidence_score"]):
    return {**t3, "tier_used": 3}
```

Tier 3 결과가 Tier 1, Tier 2 모두보다 높을 때만 채택합니다.

---

## 8. 파이프라인 의사결정 흐름 (pipeline.py)

```
classify() 호출
    │
    ▼
[Tier 1 실행]
    │
    ├── confidence ≥ 0.80 → Tier 1 결과 반환 (tier_used=1)
    │
    ├── 텍스트 추출 불가 확장자 (이미지/영상/오디오/압축) + 표지 텍스트 없음
    │   → Tier 1 결과 반환 (tier_used=1)
    │
    └── 그 외 (텍스트 있거나 표지 텍스트 있음)
            │
            ▼
        [Tier 2 실행] (입력: 본문 텍스트 우선, 없으면 표지 텍스트 fallback)
            │
            ├── T1·T2 카테고리 일치 → 앙상블 신뢰도 보정
            │   boosted = min(1.0, (T1 + T2) / 2 + 0.10)
            │   → Tier 2 결과 반환 (tier_used=2)
            │
            ├── T2 confidence ≥ 0.50 → Tier 2 결과 반환 (tier_used=2)
            │
            └── T2 confidence < 0.50
                    │
                    ├── API Key 있음 → [Tier 3 실행]
                    │       │
                    │       ├── T3 > max(T1, T2) → Tier 3 결과 반환 (tier_used=3)
                    │       └── T3 ≤ max(T1, T2) → T1·T2 중 높은 것 반환
                    │
                    └── API Key 없음 → T1·T2 중 높은 것 반환
```

### 앙상블 보정 예시

```
T1: category="문서", confidence=0.70 (확장자 .pdf)
T2: category="문서", confidence=0.62 (임베딩 유사도)

→ 같은 카테고리 일치!
→ boosted = min(1.0, (0.70 + 0.62) / 2 + 0.10) = min(1.0, 0.76) = 0.76
→ 최종: category="문서", confidence=0.76, tier_used=2
```

---

## 9. 신뢰도 기준표 (전체 정리)

| confidence_score | 의미 | 처리 |
|-----------------|------|------|
| **1.0** | 수동 분류 | 다음 스캔에서도 우선 참조 |
| **0.85** | 사용자 정의 규칙 매칭 | 즉시 저장 |
| **0.82** | 파일명 키워드 패턴 | Tier 2 스킵 가능 (≥0.80) |
| **0.80** | Tier 1 → Tier 2 전환 임계값 | 이 이상이면 Tier 2 불필요 |
| **0.76** | 앙상블 보정 예시 | T1+T2 일치 시 보정 결과 |
| **0.70** | 확장자 기본 매핑 | Tier 2 호출 트리거 |
| **0.50** | Tier 2 → Tier 3 전환 임계값 | 이 이상이면 Tier 3 불필요 |
| **0.31** | 미분류 임계값 | 이하면 격리 처리 |
| **0.0** | 분류 불가 | 미분류 격리 |

---

## 10. 실제 파일별 신뢰도 산출 예시

### 예시 1: `2024_운영체제_과제.pdf`

```
확장자: .pdf → Tier 1 확장자 매핑 → "문서", confidence=0.70
파일명: "과제" 키워드 매칭 → "문서", confidence=0.82 (키워드 패턴이 우선 적용)

→ T1 결과: category="문서", confidence=0.82, tag="문서_2024"
→ 0.82 ≥ 0.80 → Tier 2 스킵
→ 최종: tier_used=1, confidence=0.82
```

### 예시 2: `report_final.docx` (표지 없음, 본문 있음)

```
확장자: .docx → 확장자 매핑 → "문서", confidence=0.70
파일명: "report" 키워드 매칭 → "문서", confidence=0.82

→ T1 결과: confidence=0.82 ≥ 0.80 → Tier 2 스킵
→ 최종: tier_used=1, confidence=0.82
```

### 예시 3: `data_analysis_2023.xlsx`

```
확장자: .xlsx → 확장자 매핑 → "스프레드시트", confidence=0.70
파일명: 키워드 패턴 미매칭

→ T1 결과: confidence=0.70 < 0.80 → Tier 2 호출
→ 텍스트 추출 불가 확장자(.xlsx는 TEXT_EXTRACTABLE에 없음)
   → 표지 텍스트도 없음
→ Tier 2 스킵, T1 결과 반환
→ 최종: tier_used=1, confidence=0.70
```

### 예시 4: `강의노트.pdf` (표지 없음, 본문 추출됨)

```
확장자: .pdf → "문서", confidence=0.70
파일명: 키워드 패턴 미매칭

→ T1 결과: confidence=0.70 < 0.80 → Tier 2 호출
→ 본문 텍스트 임베딩 → 카테고리 유사도 계산
   예: "문서" 유사도=0.58, "프레젠테이션" 유사도=0.41
→ T2 결과: category="문서", confidence=0.58

→ T1·T2 카테고리 일치 ("문서" == "문서")
→ 앙상블 보정: (0.70 + 0.58) / 2 + 0.10 = 0.74
→ 태그 추론: infer_tag(텍스트, "문서") → "보고서" (임베딩 유사도 0.51)
→ 최종: tier_used=2, confidence=0.74, tag="보고서"
```

### 예시 5: `unknown_file.pdf` (본문 추출됨, 내용 불명확)

```
확장자: .pdf → "문서", confidence=0.70
→ T1 confidence < 0.80 → Tier 2 호출
→ T2 최고 유사도: 0.38 (모든 카테고리와 낮은 유사도)
→ T2 confidence=0.38 < 0.50

→ API Key 없음 → T1(0.70) vs T2(0.38) → T1 채택
→ 최종: tier_used=1, confidence=0.70

→ 0.70 ≥ 0.31 → 분류 저장 (미분류 아님)
```

### 예시 6: `이상한파일.xyz` (알 수 없는 확장자)

```
확장자: .xyz → 매핑 없음 → confidence=0.0
파일명: 키워드 패턴 미매칭
→ T1 결과: category=None, confidence=0.0

→ 텍스트 추출 불가 (알 수 없는 확장자)
→ Tier 2 스킵
→ 최종: confidence=0.0 < 0.31 → 미분류 격리
```

---

## 11. 미분류 처리 정책

```
confidence_score < 0.31
  → category = None
  → 파일 이동 대상에서 제외
  → UI에서 "미분류" 별도 표시
  → 사용자가 수동으로 카테고리 지정 가능
```

미분류 파일은 `POST /apply` 실행 시 이동 대상에서 자동 제외됩니다.

---

## 12. 수동 분류 및 피드백 루프

```
사용자 수동 분류 수정 (PATCH /files/{id})
    │
    ▼
classify_service.update_manual_classification()
    │
    ├── Classification 테이블에 is_manual=True, confidence=1.0 저장
    │
    └── tier2_embedding.apply_feedback(텍스트, 수정된_카테고리)
            │
            └── 해당 카테고리 임베딩 벡터를 텍스트 방향으로 5% 보정
                (재시작 전까지 즉시 효과, 재시작 후 초기화)

다음 스캔 시:
    → Tier 1에서 is_manual=True 분류 우선 참조
    → confidence=1.0으로 즉시 확정
```

---

## 13. 표지 유사도 그룹화

Stage 6에서 실행되며, 같은 과목/프로젝트의 파일들을 자동으로 묶어줍니다.

```
cover_pages 테이블의 모든 임베딩 벡터 로드
    │
    ▼
모든 쌍(pair) 간 코사인 유사도 계산
    │
    ▼
유사도 ≥ 0.75인 쌍을 같은 그룹으로 분류
    │
    ▼
그룹 내 대표 텍스트에서 auto_tag 생성
    │
    ▼
태그가 없는 파일의 Classification.tag에 auto_tag 반영
```

**활용 예시:**
- `2024_운영체제_과제1.pdf`, `2024_운영체제_과제2.pdf`, `2024_운영체제_최종.pdf`
- 세 파일의 표지 임베딩 유사도가 모두 ≥ 0.75
- → 같은 그룹으로 묶여 동일한 `auto_tag` 부여
- → `GET /files/{id}/similar`로 유사 파일 목록 조회 가능

---

## 14. 데이터베이스 스키마와 분류 결과 저장

```sql
-- 분류 결과 핵심 컬럼
classifications (
    file_id          -- 파일 참조
    scan_id          -- 스캔 세션 ID
    category         -- 분류 카테고리 (문서/프레젠테이션/스프레드시트/코드/데이터)
    tag              -- 세부 태그 (논문, 보고서, 예산 등)
    tier_used        -- 사용된 Tier (0=수동, 1, 2, 3)
    confidence_score -- 신뢰도 0.0 ~ 1.0
    is_manual        -- 수동 수정 여부
    classified_at    -- 분류 시각
)
```

한 파일에 여러 Classification 레코드가 존재할 수 있습니다:
- 자동 분류 레코드 (scan_id별로 최신 1개 유지)
- 수동 분류 레코드 (is_manual=True, 1개)

스캔 시 이전 자동 분류는 삭제되고 새 결과로 교체됩니다.  
수동 분류는 삭제되지 않고 다음 스캔에서 우선 참조됩니다.

---

## 15. 핵심 임계값 요약

```python
TIER1_CONFIDENCE_THRESHOLD = 0.80   # Tier 1 → Tier 2 전환
TIER2_CONFIDENCE_THRESHOLD = 0.50   # Tier 2 → Tier 3 전환
UNCLASSIFIED_THRESHOLD     = 0.31   # 미분류 격리 기준
TAG_INFER_THRESHOLD        = 0.45   # 태그 추론 최소 유사도
COVER_SIMILARITY_THRESHOLD = 0.75   # 표지 유사도 그룹화 기준
FEEDBACK_LEARNING_RATE     = 0.05   # 임베딩 피드백 학습률
```
