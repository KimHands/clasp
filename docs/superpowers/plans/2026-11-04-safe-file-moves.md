# 파일 이동 안전 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clasp의 정리와 되돌리기가 파일을 덮어쓰거나, 다른 파일을 옮기거나, 기록과 실제 파일을 어긋난 채로 두지 않게 하고 이를 pytest로 고정한다.

**Architecture:** 덮어쓰지 않는 이동 연산을 `services/safe_move.py`로 분리하고, `action_service`는 파일 식별값과 함께 `pending` 로그를 남긴 뒤 이 연산만 쓴다. 정리 기준은 요청의 `folder_path`로 고정하고, 경로 검사는 `utils/paths.py`로 모은다. 중단된 작업의 조정은 `services/move_recovery.py`가 맡는다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, pytest, React 19, Zustand

**Spec:** `docs/superpowers/specs/2026-11-04-safe-file-moves-design.md`

## Global Constraints

- 충돌 처리 값은 `rename`, `skip`만 허용하고 `overwrite`는 `INVALID_TYPE`(400)으로 거부한다.
- 이동 코드에서 `shutil.move`를 쓰지 않는다. 대체 이동 경로와 충돌 재시도를 두지 않는다.
- `confidence_score < 0.31`인 파일은 이동에서 제외한다.
- 기존 테이블을 바꾸지 않는다. 추가는 `action_log_identities` 테이블 하나뿐이다.
- 파일 동일성 판정은 `os.lstat`의 `st_ino`로 한다. `os.path.samefile`을 쓰지 않는다.
- 테스트는 임베딩 모델을 불러오지 않고, 실제 홈의 앱 DB를 건드리지 않는다.
- 업무 로직 주석은 한국어, 기술 구현 주석은 영어로 쓴다.
- 공개 레포다. 절대 경로와 개인 파일명을 커밋하지 않는다.
- 커밋 메시지는 `gitmsg` 초안을 사실과 대조해 고쳐 쓰고, 작성자는 noreply를 유지한다. 푸시는 사용자 승인 후에만 한다.
- 앱을 띄울 때 5173, 8000 포트의 소유자를 먼저 확인한다. 다른 프로젝트 프로세스는 종료하지 않는다.

## Review Focus

- macOS 한글 경로의 NFC/NFD 차이: 같은 폴더가 다른 정규화로 들어와도 "범위 밖"으로 거부되면 안 된다. Task 2 테스트로 고정.
- 같은 스캔의 두 파일이 같은 대상 이름을 가질 때: 둘 다 남아야 한다. Task 3 테스트로 고정.
- `문서`라는 일반 파일이 대상 폴더 자리에 있을 때: 그 파일만 `failed`이고 요청은 성공해야 한다. Task 3 테스트로 고정.
- 하드링크를 지원하지 않는 파일시스템: 원본이 남고 실패 사유가 보고돼야 한다. Task 1, Task 3 테스트로 고정.
- 정리 후 사용자가 파일을 제자리에서 수정한 경우: 식별값이 유지되어 되돌릴 수 있어야 한다. Task 4 테스트로 고정.

---

### Task 1: 테스트 기반과 덮어쓰지 않는 이동

**Files:**
- Create: `backend/pytest.ini`, `backend/requirements-dev.txt`, `backend/tests/conftest.py`, `backend/tests/test_safe_move.py`, `backend/services/safe_move.py`

**Interfaces:**
- Produces: `move_no_clobber(src: str, dst: str) -> None`. 대상이 있으면 `FileExistsError`, 원본이 바뀌면 `ConcurrentChange(OSError)`, 그 외 실패는 `OSError`. 호출자가 대상 폴더를 만든다.
- Produces (conftest): 픽스처 `home`(임시 폴더를 `HOME`으로 설정하고 `realpath` 문자열 반환), `db`(임시 SQLite 세션), `client`(`get_db`를 `db`로 바꾼 `TestClient`, lifespan 미실행). 헬퍼 `add_scanned(db, path, scan_id="scan_t", category="문서", confidence=0.7) -> File`(파일이 있으면 `size`, `modified_at`을 스캔과 같은 방식으로 채움), `write(path, text) -> str`, `read(path) -> str`.

- [ ] **Step 1: 설정과 픽스처 작성**

`pytest.ini`는 `pythonpath = .`, `testpaths = tests`. `requirements-dev.txt`는 `pytest>=8.0`, `httpx>=0.27`. `conftest.py` 맨 위에서 프로젝트를 import하기 전에 `os.environ["HOME"]`을 `tempfile.mkdtemp()`로 바꾼다. `database.py`가 import 시점에 앱 데이터 폴더를 만들기 때문이다.

- [ ] **Step 2: 실패하는 테스트 작성**

```python
def test_moves_file_and_removes_source(tmp_path):
    src = write(tmp_path / "a.txt", "본문"); dst = str(tmp_path / "b.txt")
    move_no_clobber(src, dst)
    assert not os.path.exists(src) and read(dst) == "본문"

def test_existing_destination_raises_and_changes_nothing(tmp_path):
    src = write(tmp_path / "a.txt", "새 파일"); dst = write(tmp_path / "b.txt", "기존 파일")
    with pytest.raises(FileExistsError):
        move_no_clobber(src, dst)
    assert read(src) == "새 파일" and read(dst) == "기존 파일"

@pytest.mark.parametrize("code", [errno.ENOTSUP, errno.EPERM, errno.EXDEV])
def test_link_failure_propagates_and_keeps_source(tmp_path, monkeypatch, code):
    # os.link가 OSError(code)를 내면 그대로 전파, 원본 불변, 대상 없음

def test_source_replaced_after_link_is_kept(tmp_path, monkeypatch):
    # os.link 래퍼가 링크 직후 원본을 지우고 내용 B로 다시 만든다
    # ConcurrentChange 발생, 원본은 B 유지, 대상은 A 유지

def test_unlink_failure_removes_own_link(tmp_path, monkeypatch):
    # os.unlink(src)가 PermissionError → 예외 전파, 원본 유지, 대상 없음

def test_cleanup_keeps_replaced_destination(tmp_path, monkeypatch):
    # 링크 직후 대상이 내용 B의 다른 파일로 바뀌고 os.unlink(src)가 PermissionError
    # 대상 B가 지워지지 않음

def test_windows_uses_rename(tmp_path, monkeypatch):
    # sys.platform을 "win32"로 바꾸면 os.link를 호출하지 않고 os.rename을 호출
```

- [ ] **Step 3: 실패 확인**

Run: `venv/bin/pip install -q -r requirements-dev.txt && venv/bin/python -m pytest tests/test_safe_move.py -v`
Expected: `ModuleNotFoundError: services.safe_move`로 FAIL

- [ ] **Step 4: `services/safe_move.py` 구현**

설계 문서 "이동 원자 연산"대로 구현한다. 호출 시점에 `sys.platform`을 읽어 분기한다. 같은 파일 판정은 `os.path.samestat(os.lstat(a), os.lstat(b))`이다.

- [ ] **Step 5: 통과 확인**

Run: `venv/bin/python -m pytest tests/test_safe_move.py -v`
Expected: 전부 PASS

- [ ] **Step 6: 커밋** — `feat: 덮어쓰지 않는 파일 이동 연산과 테스트 기반 추가`

### Task 2: 정리 기준 폴더, 점유 판단, 심볼릭 링크 제외

**Files:**
- Create: `backend/utils/paths.py`, `backend/tests/test_paths.py`, `backend/tests/test_apply_preview.py`, `backend/tests/test_scan_collect.py`
- Modify: `backend/routers/scan.py:32-45`, `backend/routers/apply.py:31-35`, `backend/services/action_service.py:25-36,76-132,135-158,198-254`, `backend/services/scan_service.py:43-49`

**Interfaces:**
- Consumes: 픽스처 `home`, `db`, `client`, `add_scanned`
- Produces: `is_within(path: str, root: str) -> bool`(양쪽 `realpath`와 NFC 정규화 뒤 `commonpath` 비교), `validate_folder_path(folder_path: str) -> str | None`(허용 범위면 `realpath`, 아니면 `None`, 홈은 호출 시점에 읽음)
- Produces: `resolve_base_dir(folder_path: str, files: list[File]) -> str`(범위 밖 `PERMISSION_DENIED`, 폴더 아니면 `FOLDER_NOT_FOUND`, 파일 하나라도 벗어나면 `PERMISSION_DENIED`), `is_occupied(db, path: str, own_file_id: int | None) -> bool`, `_resolve_conflict(db, dest_path, resolution, own_file_id) -> str | None`, `build_preview(db, scan_id: str, folder_path: str) -> dict`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_is_within_rejects_sibling_prefix(home):
    assert not is_within(f"{home}/bc/x", f"{home}/b")

def test_is_within_treats_nfc_and_nfd_as_same(home):
    assert is_within(unicodedata.normalize("NFD", f"{home}/문서/x"), unicodedata.normalize("NFC", f"{home}/문서"))

def test_validate_rejects_outside_home(home):
    assert validate_folder_path("/etc") is None

def test_preview_uses_requested_folder_as_base(home, db):
    add_scanned(db, write(f"{home}/root/sub/deep/e.txt", "본문"))
    tree = build_preview(db, "scan_t", f"{home}/root")["preview_tree"]
    assert [t["folder"] for t in tree] == ["문서"]

def test_preview_rejects_file_outside_folder(home, db):
    os.makedirs(f"{home}/root")
    add_scanned(db, write(f"{home}/other/e.txt", "본문"))
    with pytest.raises(HTTPException) as e:
        build_preview(db, "scan_t", f"{home}/root")
    assert e.value.status_code == 403

def test_stale_row_counts_as_occupied(home, db):
    add_scanned(db, f"{home}/root/문서/a.txt")  # 디스크에는 없는 행
    assert is_occupied(db, f"{home}/root/문서/a.txt", own_file_id=None)

def test_preview_endpoint_requires_folder_path(client):
    assert client.get("/apply/preview", params={"scan_id": "scan_t"}).status_code == 422

def test_collect_skips_file_symlinks(home):
    write(f"{home}/outside/secret.txt", "비밀"); write(f"{home}/r/a.txt", "본문")
    os.symlink(f"{home}/outside/secret.txt", f"{home}/r/link.txt")
    assert [os.path.basename(p) for p in _collect_files(f"{home}/r")] == ["a.txt"]
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_paths.py tests/test_apply_preview.py tests/test_scan_collect.py -v`
Expected: import 오류 또는 FAIL

- [ ] **Step 3: 구현**

`scan.py`의 `_validate_folder_path`를 `validate_folder_path`로 옮겨 쓰고, `_find_common_base`를 지운다. `_get_destination`의 `startswith` 검사를 `is_within`으로 바꾼다. `is_occupied`는 `os.path.lexists(path)` 또는 다른 `File` 행의 같은 경로로 판단한다. 미리보기의 충돌 판단도 `is_occupied`를 쓴다. `/apply/preview`에 `folder_path: str = Query(...)`를 더한다. `_collect_files`는 `os.path.islink`인 파일을 건너뛴다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋** — `fix: 정리 기준을 요청 폴더로 고정하고 심볼릭 링크 제외`

### Task 3: 식별값 기록과 정리 실행

**Files:**
- Create: `backend/tests/test_apply.py`
- Modify: `backend/models/schema.py`, `backend/services/action_service.py:257-352`, `backend/routers/apply.py:18,38-52`

**Interfaces:**
- Consumes: `move_no_clobber`, `resolve_base_dir`, `is_within`, `_resolve_conflict`
- Produces: 모델 `ActionLogIdentity`(`action_log_identities`, `log_id` PK·FK `action_logs.id`, `inode` String), `ActionLog.identity` 관계, 헬퍼 `inode_of(path: str) -> str`(`str(os.lstat(path).st_ino)`)
- Produces: `apply_organize(db, scan_id, conflict_resolution, folder_path) -> {"moved", "skipped", "failed", "action_log_id"}`, `_finalize_move(db, log: ActionLog, file: File, final_dest: str) -> None`. `ActionBatch.folder_path`에는 정규화한 경로를 저장한다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_overwrite_rejected(client, home):
    r = client.post("/apply", json={"scan_id": "s", "conflict_resolution": "overwrite", "folder_path": home})
    assert r.status_code == 400

def test_scanned_conflict_renames_and_keeps_both(home, db):
    add_scanned(db, write(f"{home}/r/a.txt", "새 파일"))
    add_scanned(db, write(f"{home}/r/문서/a.txt", "기존 파일"))
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert read(f"{home}/r/문서/a.txt") == "기존 파일"
    assert read(f"{home}/r/문서/a_1.txt") == "새 파일"
    assert result["failed"] == 0

def test_conflict_skip_leaves_files(home, db): ...          # 양쪽 내용 불변, skip 로그 1건
def test_stale_row_path_gets_number(home, db): ...          # 디스크에 없는 대상 경로의 행이 있어도 500 없이 _1
def test_low_confidence_excluded(home, db): ...             # confidence=0.30 파일은 제자리, skipped 증가
def test_symlink_row_is_skipped(home, db): ...              # 경로가 심볼릭 링크인 행은 옮기지 않고 skip
def test_replaced_after_scan_is_skipped(home, db):
    # 스캔 후 같은 경로를 크기와 수정 시각이 다른 파일로 교체 → skip, 파일 제자리
def test_missing_scan_metadata_skips_comparison(home, db): ...  # size, modified_at이 없는 행은 그대로 이동
def test_two_files_same_name_both_survive(home, db): ...    # r/x/a.txt, r/y/a.txt 내용이 모두 남음
def test_category_path_is_regular_file(home, db): ...       # r/문서가 일반 파일이면 failed 1, 응답 정상, 원본 불변
def test_symlink_folder_escape_fails_without_writing(home, db):
    # r/문서가 home/outside를 가리키면 failed 1, outside 비어 있고 원본 불변
def test_hardlink_unsupported_reports_failure(home, db, monkeypatch):
    # os.link가 OSError(ENOTSUP)를 내면 failed 1, 원본 불변, 로그 failed
def test_one_failure_does_not_stop_rest(home, db, monkeypatch): ...  # 특정 파일만 OSError, 나머지 move
def test_destination_appearing_mid_move_is_failed_not_retried(home, db, monkeypatch):
    # move_no_clobber가 FileExistsError → failed 1, 호출 1회, 원본 불변
def test_pending_and_identity_logged_before_move(home, db, monkeypatch):
    # move_no_clobber 호출 시점에 다른 세션에서 pending 로그와 원본 inode가 조회됨
def test_finalize_failure_keeps_pending(home, db, monkeypatch):
    # _finalize_move가 SQLAlchemyError를 내면 failed 집계, 로그는 pending, 파일은 대상에 존재
def test_cannot_lose_content(home, db):
    # 위 충돌 시나리오 전후로 모든 시작 파일의 해시가 트리 어딘가에 남음
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_apply.py -v`
Expected: `test_overwrite_rejected`, `test_scanned_conflict_renames_and_keeps_both` 등 FAIL

- [ ] **Step 3: 구현**

`VALID_RESOLUTIONS = {"rename", "skip"}`로 바꾸고 오류 문구에서 overwrite를 뺀다. 파일별 순서는 설계 문서 "이동 전 기록"을 따른다. 심볼릭 링크, 낮은 신뢰도, 스캔 후 바뀐 파일을 먼저 거른 뒤 대상 폴더의 `realpath`를 만들기 전에 검사한다. `move_no_clobber`의 `OSError`(`FileExistsError` 포함)는 `failed`로 바꾼다. `_finalize_move`가 `SQLAlchemyError`를 내면 롤백만 하고 `pending`을 남긴다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋** — `fix: 이동 전 식별값을 기록하고 덮어쓰기 옵션 제거`

### Task 4: 되돌리기와 이력 상태

**Files:**
- Create: `backend/tests/test_undo.py`
- Modify: `backend/services/action_service.py:355-451`, `backend/routers/apply.py:62-69`

**Interfaces:**
- Consumes: `move_no_clobber`, `is_occupied`, `apply_organize`, `inode_of`, `ActionLog.identity`
- Produces: `undo_organize(db, action_log_id) -> {"restored", "failed", "unrestorable": [{"filename", "reason"}]}`. 사유는 `destination_file_not_found`, `identity_mismatch`, `source_outside_root`, `source_occupied`, `move_failed`. `get_folder_history(db, folder_path)` 각 항목에 `undo_state: "none" | "partial" | "undone"` 추가.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_undo_does_not_clobber_new_file(home, db):
    src = write(f"{home}/r/b.txt", "원본")
    add_scanned(db, src)
    res = apply_organize(db, "scan_t", "rename", f"{home}/r")
    write(src, "새로 만든 파일")
    out = undo_organize(db, res["action_log_id"])
    assert read(src) == "새로 만든 파일"
    assert read(f"{home}/r/문서/b.txt") == "원본"
    assert out["unrestorable"][0]["reason"] == "source_occupied"

def test_old_batch_undo_does_not_move_other_file(home, db):
    # 배치 A: X를 문서/a.txt로, 배치 B: X를 기타로, 배치 C: Y를 문서/a.txt로
    # A undo → identity_mismatch, Y는 문서/a.txt에 그대로, 원위치 없음

def test_undo_refuses_source_folder_outside_root(home, db):
    # r/sub/a.txt 정리 후 r/sub를 바깥 폴더를 가리키는 링크로 교체, undo
    # source_outside_root, 파일은 정리된 위치에 그대로, 바깥 폴더 비어 있음

def test_undo_after_in_place_edit_restores(home, db):
    # 정리 후 같은 inode로 내용 수정, undo → 수정된 내용이 원위치로 복귀

def test_partial_undo_state_and_retry(home, db):
    # 2개 이동, 원위치 하나를 막고 undo → undo_state "partial", ActionBatch.is_undone False
    # 막은 파일을 치우고 재시도 → restored 1, undo_state "undone", is_undone True

def test_second_undo_after_complete_raises_conflict(home, db): ...  # 409
def test_missing_destination_is_reported(home, db): ...             # destination_file_not_found, partial
def test_stale_row_on_source_is_occupied(home, db): ...             # 원위치 경로의 다른 File 행 → source_occupied
def test_undo_updates_file_path(home, db): ...                      # File.path가 원래 경로로 돌아옴
def test_undo_marks_undo_pending_before_move(home, db, monkeypatch): ...  # 이동 시점에 로그가 undo_pending
def test_history_finds_raw_and_normalized_path(home, db):
    # 심볼릭 링크 경로로 조회해도 정규화 경로의 이력이 나오고, 옛 행의 비정규화 경로도 나옴
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_undo.py -v`
Expected: `test_undo_does_not_clobber_new_file` 등 FAIL

- [ ] **Step 3: 구현**

설계 문서 "되돌리기" 표의 순서로 판단한다. 로그를 `undo_pending`으로 커밋한 뒤 `move_no_clobber`를 호출한다. `FileExistsError`는 `source_occupied`로 보고하고 로그를 `move`로 되돌린다. 성공하면 로그를 `move`, `is_undone=True`로 하고 `File.path`와 함께 커밋한다. 이 커밋이 실패하면 롤백하고 `move_failed`로 보고하며 `undo_pending`을 남긴다. `batch.is_undone = all(log.is_undone for log in move_logs)`. 이력 조회는 원본 경로와 `realpath` 두 값을 `in_`으로 찾는다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋** — `fix: 되돌리기 전 파일 식별을 확인하고 부분 상태 표시`

### Task 5: 조정 절차

**Files:**
- Create: `backend/services/move_recovery.py`, `backend/tests/test_recovery.py`
- Modify: `backend/main.py:9-12`, `backend/services/action_service.py`, `backend/services/scan_service.py:74-78`, `backend/utils/errors.py`

**Interfaces:**
- Consumes: `pending`, `undo_pending` 로그, `ActionLog.identity`
- Produces: `reconcile_pending(db) -> int`(처리하지 못하고 남은 로그 수). 예외를 호출자에게 전파하지 않는다. `repoint_file(db, old_path: str, new_path: str) -> None`(new_path를 다른 행이 쓰면 건너뛰고 경고. 행을 지우지 않음)
- Produces: `ErrorCode.MOVES_UNRESOLVED`(409, "완료되지 않은 파일 이동을 먼저 확인해야 합니다")

- [ ] **Step 1: 실패하는 테스트 작성**

설계 문서의 두 판정 표를 그대로 매개변수화한다. 각 케이스는 이동 함수를 쓰지 않고 파일과 로그를 직접 구성한다.

```python
# pending
def test_pending_dest_match_source_gone_becomes_move(home, db): ...      # File.path 갱신, moved_count 1
def test_pending_hardlink_midway_removes_dest_only(home, db): ...        # 원본 유지, 대상 없음, failed
def test_pending_source_replaced_keeps_both(home, db): ...               # 양쪽 내용 불변, move
def test_pending_dest_missing_becomes_failed(home, db): ...
def test_pending_dest_other_file_is_untouched(home, db): ...             # inode 불일치, 원본 있음, 양쪽 불변, failed
def test_pending_dest_replaced_source_gone_is_unverified(home, db): ...  # inode 불일치, 원본 없음, 대상 불변, unverified, 실패로 집계, undo 대상 아님

# undo_pending
def test_undo_pending_source_match_dest_gone_completes(home, db): ...    # is_undone True, File.path 원위치
def test_undo_pending_midway_removes_source_link(home, db): ...          # 대상 유지, move로 복귀
def test_undo_pending_dest_replaced_keeps_both(home, db): ...            # 양쪽 불변, is_undone True
def test_undo_pending_not_moved_reverts(home, db): ...                   # 파일 불변, move, is_undone False

# 상호작용
def test_repoint_never_deletes_other_row(home, db):
    # 대상 경로를 쓰는 다른 행과 그 수동 분류가 조정 후에도 남음, 파일 불변
def test_unresolved_blocks_apply_and_undo(home, db, monkeypatch):
    # 조정 커밋을 실패시켜 pending을 남기면 apply_organize, undo_organize가 409, 파일 불변
def test_unresolved_blocks_scan(home, db, monkeypatch):
    # run_scan이 stage -1로 끝나고 새 File 행을 만들지 않음
def test_one_bad_log_does_not_stop_others(home, db, monkeypatch): ...
def test_counts_recalculated(home, db): ...                              # moved_count, failed_count가 로그와 일치
def test_startup_runs_reconcile(home, monkeypatch):
    # with TestClient(app): lifespan에서 호출됨
def test_apply_undo_scan_run_reconcile_first(home, db, monkeypatch):
    # apply_organize, undo_organize, run_scan 시작 시 호출됨. pending이 남은 파일을 재정리해도 기록이 어긋나지 않음
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_recovery.py -v`
Expected: `ModuleNotFoundError`로 FAIL

- [ ] **Step 3: 구현**

`os.path.lexists`와 `os.lstat`으로 표를 판정한다. 로그마다 따로 커밋하고, 예외가 나면 롤백 후 경고를 남기고 다음으로 넘어간다. `lifespan`에서는 `init_db()` 다음에 별도 세션으로 실행하고, 남은 수와 무관하게 앱을 시작한다. `apply_organize`, `undo_organize`, `run_scan` 맨 앞에서도 호출하고, 반환값이 0이 아니면 앞의 둘은 `MOVES_UNRESOLVED`를 내고 스캔은 `stage: -1`로 끝낸다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋** — `feat: 중단된 이동과 되돌리기를 실제 파일과 조정`

### Task 6: Apply 화면과 API 문서

**Files:**
- Modify: `frontend/src/api/apply.js:3-5`, `frontend/src/store/applyStore.js:16-21`, `frontend/src/pages/Apply.jsx:14-18,213-268,300-310,351-365,412-430`, `docs/API_명세서.md`

**Interfaces:**
- Consumes: `undo_state`, 되돌리기 사유 값, `/apply/preview`의 `folder_path`
- Produces: `getApplyPreview(scanId, folderPath)`

- [ ] **Step 1: API와 스토어 수정**

미리보기에 `folder_path`를 넘기고, `markHistoryUndone`을 지운다. `handleUndo`는 응답 뒤 항상 `setUndoResult(result)`와 `loadHistory()`를 호출하고, 마지막 배치일 때만 `setApplyResult(null)`을 호출한다.

- [ ] **Step 2: 화면 수정**

`RESOLUTION_OPTIONS`에서 덮어쓰기를 뺀다. `RESOLUTION_LABELS.overwrite`는 유지한다. 배지와 도트는 `undo_state`로 표시한다.

| `undo_state` | 배지 | 버튼 |
|---|---|---|
| `none` | 없음 | 되돌리기 |
| `partial` | 일부 되돌림 | 다시 시도 |
| `undone` | 되돌림 | 없음 |

결과 카드 제목은 `failed > 0`이면 "일부만 되돌렸습니다", 아니면 "되돌리기 완료"로 한다. 복구 불가 사유는 다음 문구로 바꾼다.

| 사유 | 문구 |
|---|---|
| `source_occupied` | 원래 위치에 다른 파일이 있어 옮기지 않았습니다 |
| `identity_mismatch` | 정리된 위치의 파일이 그때 옮긴 파일이 아니어서 옮기지 않았습니다 |
| `source_outside_root` | 원래 위치가 정리한 폴더 밖을 가리켜 옮기지 않았습니다 |
| `destination_file_not_found` | 정리된 위치에서 파일을 찾을 수 없습니다 |
| `move_failed` | 파일을 옮기지 못했습니다 |

- [ ] **Step 3: 빌드와 lint 확인**

Run: `cd ../frontend && npm run build && npx eslint src/pages/Apply.jsx src/store/applyStore.js src/api/apply.js`
Expected: 빌드 성공. 수정한 파일에 새 lint 오류 없음

- [ ] **Step 4: API 문서 수정**

`conflict_resolution`에서 `overwrite`를 빼고, `/apply/preview`의 `folder_path`, 이력의 `undo_state`, 되돌리기 사유 값을 코드와 맞춘다.

- [ ] **Step 5: 실제 앱에서 확인**

임시 `HOME`과 샘플 폴더로 Electron을 띄워 확인한다. 충돌 모달에 덮어쓰기가 없고, 원위치를 막은 뒤 과거 배치를 되돌리면 결과 카드에 사유가 나오며, "일부 되돌림"과 "다시 시도"가 표시되고, 막은 파일을 치우고 다시 시도하면 "되돌림"으로 바뀌어야 한다. 콘솔 오류가 없어야 한다.

- [ ] **Step 6: 커밋** — `feat: Apply 화면에 되돌리기 결과와 부분 상태 표시`

### Task 7: 재현 시나리오 재측정과 검증

**Files:**
- Modify: `docs/superpowers/specs/2026-11-04-safe-file-moves-design.md`(리뷰 반영 표)

**Interfaces:**
- Consumes: Task 1~6 전체

- [ ] **Step 1: 재현 재측정**

임시 `HOME`에서 실제 백엔드를 띄워 설계 문서 "현재 문제" 표의 모든 시나리오를 다시 돌린다. 포트가 다른 프로젝트에 점유돼 있으면 스크래치 복사본에서 포트만 바꿔 실행한다.
Expected: `overwrite`는 400, 나머지는 파일 손실과 잘못된 이동 없음, 500 없음

- [ ] **Step 2: 전체 테스트**

Run: `venv/bin/python -m pytest tests -q`
Expected: 전부 PASS

- [ ] **Step 3: 구현 완료 리뷰**

`codex exec`에 변경 파일을 주고 "동의하지 말고 반박하라"로 사실오류, 실패 시나리오, 빠진 것, 과잉설계를 묻는다. 검증 가능한 지적은 실측 후 반영하고, 수용·기각을 설계 문서 표에 남긴다. 반영 루프는 2회까지다.

- [ ] **Step 4: 커밋** — `docs: 파일 이동 안전 검증 결과 반영`
