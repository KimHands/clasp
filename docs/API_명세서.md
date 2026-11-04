# API 명세서
## 파일 정리 및 시각화 도구

---

## 목차

1. [개요](#1-개요)
2. [공통 규칙](#2-공통-규칙)
3. [스캔 API](#3-스캔-api)
4. [파일 API](#4-파일-api)
5. [규칙 API](#5-규칙-api)
6. [정리 적용 API](#6-정리-적용-api)
7. [에러 코드](#7-에러-코드)

---

## 1. 개요

- **Base URL**: `http://127.0.0.1:<port>`. 포트는 실행마다 Electron이 정한다
- **프로토콜**: HTTP/1.1 (SSE 포함)
- **데이터 형식**: JSON (SSE는 text/event-stream)
- **인증**: 실행마다 Electron이 만드는 토큰을 `X-Clasp-Token` 헤더로 보낸다. 없거나 틀리면 401, Host가 루프백이 아니면 403

---

## 2. 공통 규칙

### 공통 응답 형식

```json
{
  "success": true,
  "data": { },
  "error": null
}
```

### 공통 에러 응답 형식

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "에러 메시지"
  }
}
```

### confidence_score 기준

| 범위 | 의미 | 처리 |
|---|---|---|
| 0.80 이상 | 높은 신뢰도 | 자동 분류 확정 |
| 0.31 ~ 0.79 | 중간 신뢰도 | 분류 결과 표시, 수동 확인 권장 |
| 0.31 미만 | 낮은 신뢰도 | 미분류 그룹 격리, 파일 이동 제외 |

### tier_used 값

| 값 | 의미 |
|---|---|
| 1 | Tier 1 (규칙 기반) |
| 2 | Tier 2 (임베딩 유사도) |
| 3 | Tier 3 (클라우드 LLM) |

---

## 3. 스캔 API

### 3.1 스캔 시작

```
POST /scan/start
```

**Request Body**

```json
{
  "folder_path": "/Users/홍길동/Documents"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| folder_path | string | ✅ | 스캔할 폴더 절대 경로 |

**Response**

```json
{
  "success": true,
  "data": {
    "scan_id": "scan_20250201_143022",
    "status": "started",
    "folder_path": "/Users/홍길동/Documents"
  },
  "error": null
}
```

**예외**
- `FOLDER_NOT_FOUND`: 경로가 존재하지 않음
- `PERMISSION_DENIED`: 폴더 접근 권한 없음

---

### 3.2 스캔 진행 상황 (SSE)

```
GET /scan/progress?scan_id={scan_id}
```

**Response**: `text/event-stream`

```
data: {"stage": 1, "message": "파일 목록 수집 중", "total": 253, "completed": 0, "current_file": ""}

data: {"stage": 2, "message": "메타데이터 분석 중", "total": 253, "completed": 45, "current_file": "report.pdf"}

data: {"stage": 3, "message": "표지 탐지 중", "total": 253, "completed": 120, "current_file": "hw_01.pdf"}

data: {"stage": 4, "message": "본문 추출 중", "total": 253, "completed": 180, "current_file": "final.docx"}

data: {"stage": 5, "message": "분류 엔진 처리 중", "total": 253, "completed": 210, "current_file": "data.txt"}

data: {"stage": 6, "message": "유사도 계산 중", "total": 253, "completed": 250, "current_file": ""}

data: {"stage": 7, "message": "완료", "total": 253, "completed": 253, "current_file": ""}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| stage | integer | 현재 단계 (1~7) |
| message | string | 단계 설명 |
| total | integer | 전체 파일 수 |
| completed | integer | 완료된 파일 수 |
| current_file | string | 현재 처리 중인 파일명 |

---

## 4. 파일 API

### 4.1 분류 결과 목록 조회

```
GET /files
```

**Query Parameters**

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| scan_id | string | ✅ | 스캔 ID |
| category | string | ❌ | 카테고리 필터 |
| tag | string | ❌ | 태그 필터 |
| min_confidence | float | ❌ | 최소 신뢰도 필터 (0.0~1.0) |
| unclassified | boolean | ❌ | true 시 미분류 파일만 조회 |
| search | string | ❌ | 파일명 검색어 |
| page | integer | ❌ | 페이지 번호 (기본값: 1) |
| page_size | integer | ❌ | 페이지당 결과 수 (기본값: 50) |

**Response**

```json
{
  "success": true,
  "data": {
    "total": 253,
    "page": 1,
    "page_size": 50,
    "items": [
      {
        "id": 1,
        "filename": "report.pdf",
        "path": "/Users/홍길동/Documents/report.pdf",
        "extension": "pdf",
        "size": 2411724,
        "created_at": "2025-01-15T10:30:00",
        "modified_at": "2025-01-20T14:22:00",
        "category": "보안",
        "tag": "보안_2025_1학기",
        "tier_used": 2,
        "confidence_score": 0.92,
        "is_manual": false
      }
    ]
  },
  "error": null
}
```

---

### 4.2 수동 분류 수정

```
PATCH /files/{file_id}
```

**Path Parameters**

| 파라미터 | 타입 | 설명 |
|---|---|---|
| file_id | integer | 파일 ID |

**Request Body**

```json
{
  "category": "데이터베이스",
  "tag": "DB_2025_1학기"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| category | string | ❌ | 변경할 카테고리명 |
| tag | string | ❌ | 변경할 태그명 |

**Response**

```json
{
  "success": true,
  "data": {
    "id": 1,
    "filename": "report.pdf",
    "category": "데이터베이스",
    "tag": "DB_2025_1학기",
    "tier_used": 2,
    "confidence_score": 0.92,
    "is_manual": true
  },
  "error": null
}
```

**예외**
- `FILE_NOT_FOUND`: 해당 파일 ID 없음
- `SAVE_FAILED`: 저장 실패

---

### 4.3 표지 유사 파일 목록 조회

```
GET /files/{file_id}/similar
```

**Path Parameters**

| 파라미터 | 타입 | 설명 |
|---|---|---|
| file_id | integer | 파일 ID |

**Response**

```json
{
  "success": true,
  "data": {
    "file_id": 1,
    "similar_files": [
      {
        "id": 5,
        "filename": "hw_01.pdf",
        "similarity_score": 0.89,
        "auto_tag": "데이터베이스_2025_1학기"
      },
      {
        "id": 8,
        "filename": "hw_02.pdf",
        "similarity_score": 0.85,
        "auto_tag": "데이터베이스_2025_1학기"
      }
    ]
  },
  "error": null
}
```

**예외**
- `FILE_NOT_FOUND`: 해당 파일 ID 없음
- `NO_COVER_DATA`: 표지 데이터 없음 (표지 미탐지 파일)

---

## 5. 규칙 API

### 5.1 규칙 목록 조회

```
GET /rules
```

**Response**

```json
{
  "success": true,
  "data": {
    "rules": [
      {
        "id": 1,
        "priority": 1,
        "type": "date",
        "value": "2025",
        "folder_name": "2025"
      },
      {
        "id": 2,
        "priority": 2,
        "type": "content",
        "value": "보안",
        "folder_name": "보안"
      },
      {
        "id": 3,
        "priority": 3,
        "type": "extension",
        "value": "pdf",
        "folder_name": "PDF"
      }
    ]
  },
  "error": null
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| id | integer | 규칙 ID |
| priority | integer | 우선순위 (낮을수록 높은 우선순위) |
| type | string | 규칙 유형: `date` / `content` / `extension` |
| value | string | 규칙 값 (연도 / 카테고리명 / 확장자) |
| folder_name | string | 생성될 폴더명 |

---

### 5.2 규칙 추가

```
POST /rules
```

**Request Body**

```json
{
  "priority": 1,
  "type": "date",
  "value": "2025",
  "folder_name": "2025"
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "id": 4,
    "priority": 1,
    "type": "date",
    "value": "2025",
    "folder_name": "2025"
  },
  "error": null
}
```

**예외**
- `RULE_CONFLICT`: 동일한 type + value 규칙 중복
- `INVALID_TYPE`: 지원하지 않는 규칙 type

---

### 5.3 규칙 수정

```
PATCH /rules/{rule_id}
```

**Path Parameters**

| 파라미터 | 타입 | 설명 |
|---|---|---|
| rule_id | integer | 규칙 ID |

**Request Body**

```json
{
  "priority": 2,
  "folder_name": "2025년도"
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "id": 1,
    "priority": 2,
    "type": "date",
    "value": "2025",
    "folder_name": "2025년도"
  },
  "error": null
}
```

---

### 5.4 규칙 삭제

```
DELETE /rules/{rule_id}
```

**Response**

```json
{
  "success": true,
  "data": {
    "deleted_id": 1
  },
  "error": null
}
```

**예외**
- `RULE_NOT_FOUND`: 해당 규칙 ID 없음

---

## 6. 정리 적용 API

### 6.1 정리 적용 미리보기

```
GET /apply/preview?scan_id={scan_id}&folder_path={folder_path}
```

`folder_path`는 정리 기준 폴더다. 홈 아래 폴더만 허용하고, 대상 파일이 하나라도 이 폴더 밖이면 `PERMISSION_DENIED`로 거부한다. 심볼릭 링크와 스캔 후 바뀐 파일은 `excluded_files`로 센다.

**Response**

```json
{
  "success": true,
  "data": {
    "total_files": 250,
    "excluded_files": 3,
    "folders_to_create": 12,
    "conflicts": [
      {
        "filename": "report.pdf",
        "destination": "/Documents/2025/보안/report.pdf",
        "conflict_type": "duplicate_name"
      }
    ],
    "preview_tree": [
      {
        "folder": "2025",
        "children": [
          {
            "folder": "보안",
            "children": [
              { "file": "report.pdf" },
              { "file": "final_report.pdf" }
            ]
          }
        ]
      }
    ]
  },
  "error": null
}
```

---

### 6.2 정리 적용 실행

```
POST /apply
```

**Request Body**

```json
{
  "scan_id": "scan_20250201_143022",
  "conflict_resolution": "rename",
  "folder_path": "/Users/홍길동/Documents"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| scan_id | string | ✅ | 스캔 ID |
| conflict_resolution | string | ✅ | 충돌 처리: `rename` / `skip`. 기존 파일을 덮어쓰는 옵션은 없다 |
| folder_path | string | ✅ | 정리 기준 폴더. 미리보기와 같은 규칙으로 검증한다 |

**Response**

```json
{
  "success": true,
  "data": {
    "moved": 248,
    "skipped": 2,
    "failed": 0,
    "action_log_id": "log_20250201_150322"
  },
  "error": null
}
```

**예외**
- `SCAN_NOT_FOUND`: 해당 스캔 ID 없음
- `INVALID_TYPE`: 지원하지 않는 `conflict_resolution`
- `PERMISSION_DENIED`: 허용 범위 밖의 폴더이거나 대상 파일이 폴더 밖에 있음
- `MOVES_UNRESOLVED`: 조정하지 못한 파일 이동이 남아 있음

파일별 이동 실패는 오류가 아니라 응답의 `failed`로 센다. 심볼릭 링크와 스캔 후 바뀐 파일은 옮기지 않고 `skipped`로 센다.

---

### 6.3 되돌리기 (Undo)

```
POST /undo
```

**Request Body**

```json
{
  "action_log_id": "log_20250201_150322"
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "restored": 248,
    "failed": 0,
    "unrestorable": [
      {
        "filename": "deleted_file.pdf",
        "reason": "destination_file_not_found"
      }
    ]
  },
  "error": null
}
```

| reason | 의미 |
|---|---|
| `destination_file_not_found` | 정리된 위치에 파일이 없음 |
| `identity_mismatch` | 정리된 위치의 파일이 그때 옮긴 파일이 아님 |
| `source_outside_root` | 원래 위치가 정리한 폴더 밖을 가리킴 |
| `source_occupied` | 원래 위치를 다른 파일이나 파일 행이 쓰고 있음 |
| `move_failed` | 이동 또는 기록 실패 |

되돌리지 못한 항목은 같은 `action_log_id`로 다시 시도할 수 있다.

**예외**
- `LOG_NOT_FOUND`: 해당 로그 ID 없음
- `ALREADY_UNDONE`: 이미 되돌리기 완료된 작업
- `MOVES_UNRESOLVED`: 조정하지 못한 파일 이동이 남아 있음

---

### 6.4 정리 이력

```
GET /apply/history?folder_path={folder_path}
```

각 항목은 `action_log_id`, `scan_id`, `moved_count`, `skipped_count`, `failed_count`, `conflict_resolution`, `executed_at`, `is_undone`, `undo_state`를 담는다. `undo_state`는 `none`(되돌린 것 없음), `partial`(일부), `undone`(전체) 중 하나다.

---

## 7. 로컬 LLM·민감 키워드 설정

| 요청 | 설명 |
|---|---|
| `GET /settings/local-llm` | `enabled`, `base_url`, `model` 조회 |
| `POST /settings/local-llm` | 저장. 루프백 주소가 아니면 `INVALID_TYPE` |
| `POST /settings/local-llm/test` | `{ "base_url": ... }`로 연결 시험. `ok`, `models` 반환 |
| `GET /settings/sensitive-keywords` | 키워드 목록 |
| `POST /settings/sensitive-keywords` | `{ "keyword": ... }` 추가. 중복이면 409 |
| `DELETE /settings/sensitive-keywords/{id}` | 삭제 |
| `GET`·`POST /settings/extensions`, `DELETE /settings/extensions/{id}` | 사용자 확장자 조회·추가·삭제 |
| `GET`·`POST /settings/categories`, `DELETE /settings/categories/{id}` | 사용자 카테고리 조회·추가·삭제 |
| `GET /health` | 상태 확인. 토큰이 필요하다 |

---

## 8. 에러 코드

| 에러 코드 | HTTP 상태 | 설명 |
|---|---|---|
| FOLDER_NOT_FOUND | 404 | 폴더 경로가 존재하지 않음 |
| PERMISSION_DENIED | 403 | 파일 / 폴더 접근 권한 없음 |
| FILE_NOT_FOUND | 404 | 해당 파일 ID 없음 |
| SAVE_FAILED | 500 | SQLite 저장 실패 |
| NO_COVER_DATA | 404 | 표지 데이터 없음 |
| RULE_CONFLICT | 409 | 중복 규칙 존재 |
| INVALID_TYPE | 400 | 지원하지 않는 규칙 type |
| MOVES_UNRESOLVED | 409 | 완료되지 않은 파일 이동을 먼저 확인해야 함 |
| RULE_NOT_FOUND | 404 | 해당 규칙 ID 없음 |
| SCAN_NOT_FOUND | 404 | 해당 스캔 ID 없음 |
| MOVE_FAILED | 500 | 파일 이동 실패 |
| LOG_NOT_FOUND | 404 | 해당 로그 ID 없음 |
| ALREADY_UNDONE | 409 | 이미 되돌리기 완료 |

---

*작성일: 2025년 02월*
