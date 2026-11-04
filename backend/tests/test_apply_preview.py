import os

import pytest
from fastapi import HTTPException

from conftest import add_scanned, write
from services.action_service import build_preview, is_occupied


def test_preview_uses_requested_folder_as_base(home, db):
    add_scanned(db, write(f"{home}/root/sub/deep/e.txt", "본문"))
    tree = build_preview(db, "scan_t", f"{home}/root")["preview_tree"]
    assert [t["folder"] for t in tree] == ["문서"]


def test_preview_rejects_file_outside_folder(home, db):
    os.makedirs(f"{home}/root")
    add_scanned(db, write(f"{home}/other/e.txt", "본문"))
    with pytest.raises(HTTPException) as raised:
        build_preview(db, "scan_t", f"{home}/root")
    assert raised.value.status_code == 403


def test_preview_rejects_folder_outside_home(home, db):
    add_scanned(db, write(f"{home}/root/e.txt", "본문"))
    with pytest.raises(HTTPException) as raised:
        build_preview(db, "scan_t", "/etc")
    assert raised.value.status_code == 403


def test_preview_missing_folder_is_not_found(home, db):
    add_scanned(db, write(f"{home}/root/e.txt", "본문"))
    with pytest.raises(HTTPException) as raised:
        build_preview(db, "scan_t", f"{home}/없는폴더")
    assert raised.value.status_code == 404


def test_preview_reports_stale_row_as_conflict(home, db):
    add_scanned(db, write(f"{home}/root/a.txt", "본문"))
    add_scanned(db, f"{home}/root/문서/a.txt", scan_id="scan_old")
    conflicts = build_preview(db, "scan_t", f"{home}/root")["conflicts"]
    assert [c["filename"] for c in conflicts] == ["a.txt"]


def test_stale_row_counts_as_occupied(home, db):
    file = add_scanned(db, f"{home}/root/문서/a.txt")
    assert is_occupied(db, file.path, own_file_id=None)


def test_own_row_does_not_count_as_occupied(home, db):
    file = add_scanned(db, f"{home}/root/문서/a.txt")
    assert not is_occupied(db, file.path, own_file_id=file.id)


def test_broken_symlink_counts_as_occupied(home, db):
    os.symlink(f"{home}/없음", f"{home}/깨진링크")
    assert is_occupied(db, f"{home}/깨진링크", own_file_id=None)


def test_preview_endpoint_requires_folder_path(client):
    assert client.get("/apply/preview", params={"scan_id": "scan_t"}).status_code == 422


def test_preview_does_not_count_file_already_in_place(home, db):
    add_scanned(db, write(f"{home}/root/문서/a.txt", "본문"))
    add_scanned(db, write(f"{home}/root/b.txt", "본문"))
    preview = build_preview(db, "scan_t", f"{home}/root")
    assert preview["total_files"] == 1
    assert [c["file"] for c in preview["preview_tree"][0]["children"]] == ["b.txt"]
