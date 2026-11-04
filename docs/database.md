# 데이터베이스

SQLite를 쓰고 SQLAlchemy ORM으로 다룬다. WAL 모드이며 위치는 macOS 기준 `~/Library/Application Support/Clasp/clasp.db`다. 앱 시작 시 없는 테이블을 만든다.

아래 표는 `backend/models/schema.py`에서 생성했다.

## action_batches

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `id` | INTEGER | PK |
| `action_log_id` | VARCHAR | UNIQUE, NOT NULL |
| `folder_path` | VARCHAR | NOT NULL |
| `scan_id` | VARCHAR | NOT NULL |
| `moved_count` | INTEGER | NOT NULL |
| `skipped_count` | INTEGER | NOT NULL |
| `failed_count` | INTEGER | NOT NULL |
| `conflict_resolution` | VARCHAR |  |
| `executed_at` | DATETIME | NOT NULL |
| `is_undone` | BOOLEAN | NOT NULL |

## app_settings

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `key` | VARCHAR | PK |
| `value` | VARCHAR | NOT NULL |

## custom_categories

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `id` | INTEGER | PK |
| `name` | VARCHAR | UNIQUE, NOT NULL |
| `keywords` | TEXT | NOT NULL |

## custom_extensions

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `id` | INTEGER | PK |
| `extension` | VARCHAR | UNIQUE, NOT NULL |
| `category` | VARCHAR | NOT NULL |

## files

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `id` | INTEGER | PK |
| `path` | VARCHAR | UNIQUE, NOT NULL |
| `filename` | VARCHAR | NOT NULL |
| `extension` | VARCHAR |  |
| `created_at` | DATETIME |  |
| `modified_at` | DATETIME |  |
| `size` | INTEGER |  |
| `extracted_text_summary` | TEXT |  |

## rules

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `id` | INTEGER | PK |
| `priority` | INTEGER | NOT NULL |
| `type` | VARCHAR | NOT NULL |
| `value` | VARCHAR | NOT NULL |
| `folder_name` | VARCHAR | NOT NULL |
| `parent_id` | INTEGER | FK rules.id |

## sensitive_keywords

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `id` | INTEGER | PK |
| `keyword` | VARCHAR | UNIQUE, NOT NULL |

## action_logs

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `id` | INTEGER | PK |
| `action_log_id` | VARCHAR | NOT NULL, FK action_batches.action_log_id |
| `action_type` | VARCHAR | NOT NULL |
| `source_path` | VARCHAR | NOT NULL |
| `destination_path` | VARCHAR |  |
| `executed_at` | DATETIME | NOT NULL |
| `is_undone` | BOOLEAN | NOT NULL |

## classifications

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `id` | INTEGER | PK |
| `file_id` | INTEGER | NOT NULL, FK files.id |
| `scan_id` | VARCHAR | NOT NULL |
| `category` | VARCHAR |  |
| `tag` | VARCHAR |  |
| `tier_used` | INTEGER | NOT NULL |
| `confidence_score` | FLOAT | NOT NULL |
| `is_manual` | BOOLEAN | NOT NULL |
| `classified_at` | DATETIME | NOT NULL |

## cover_pages

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `id` | INTEGER | PK |
| `file_id` | INTEGER | UNIQUE, NOT NULL, FK files.id |
| `cover_text` | TEXT |  |
| `embedding` | TEXT |  |
| `detected_at` | DATETIME | NOT NULL |

## cover_similarity_groups

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `id` | INTEGER | PK |
| `group_id` | VARCHAR | NOT NULL |
| `file_id` | INTEGER | NOT NULL, FK files.id |
| `similarity_score` | FLOAT | NOT NULL |
| `auto_tag` | VARCHAR |  |

## action_log_identities

| 컬럼 | 타입 | 제약 |
|---|---|---|
| `log_id` | INTEGER | PK, FK action_logs.id |
| `inode` | VARCHAR | NOT NULL |

## action_type 값

| 값 | 의미 |
|---|---|
| `pending` | 이동 직전 기록. 조정 절차가 확정한다 |
| `move` | 이동 완료 |
| `undo_pending` | 되돌리기 직전 기록. 조정 절차가 확정한다 |
| `skip` | 충돌, 심볼릭 링크, 스캔 후 변경으로 건너뜀 |
| `failed` | 이동 실패 |
| `unverified` | 원본은 없고 대상은 다른 파일이라 판단 불가 |
