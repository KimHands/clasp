import errno
import os

import pytest

from conftest import posix_only, read, write
from services import safe_move
from services.safe_move import ConcurrentChange, move_no_clobber


def test_moves_file_and_removes_source(tmp_path):
    src = write(tmp_path / "a.txt", "본문")
    dst = str(tmp_path / "b.txt")
    move_no_clobber(src, dst)
    assert not os.path.exists(src)
    assert read(dst) == "본문"


def test_existing_destination_raises_and_changes_nothing(tmp_path):
    src = write(tmp_path / "a.txt", "새 파일")
    dst = write(tmp_path / "b.txt", "기존 파일")
    with pytest.raises(FileExistsError):
        move_no_clobber(src, dst)
    assert read(src) == "새 파일"
    assert read(dst) == "기존 파일"


@posix_only
@pytest.mark.parametrize("code", [errno.ENOTSUP, errno.EPERM, errno.EXDEV])
def test_link_failure_propagates_and_keeps_source(tmp_path, monkeypatch, code):
    src = write(tmp_path / "a.txt", "본문")
    dst = str(tmp_path / "b.txt")

    def failing_link(*args, **kwargs):
        raise OSError(code, "link failed")

    monkeypatch.setattr(os, "link", failing_link)
    with pytest.raises(OSError) as raised:
        move_no_clobber(src, dst)
    assert raised.value.errno == code
    assert read(src) == "본문"
    assert not os.path.lexists(dst)


@posix_only
def test_source_replaced_after_link_is_kept(tmp_path, monkeypatch):
    src = write(tmp_path / "a.txt", "A")
    dst = str(tmp_path / "b.txt")
    real_link = os.link

    def link_then_replace_source(s, d, **kwargs):
        real_link(s, d, **kwargs)
        os.remove(s)
        write(s, "B")

    monkeypatch.setattr(os, "link", link_then_replace_source)
    with pytest.raises(ConcurrentChange):
        move_no_clobber(src, dst)
    assert read(src) == "B"
    assert read(dst) == "A"


@posix_only
def test_unlink_failure_removes_own_link(tmp_path, monkeypatch):
    src = write(tmp_path / "a.txt", "본문")
    dst = str(tmp_path / "b.txt")
    real_unlink = os.unlink

    def refuse_source(path, **kwargs):
        if path == src:
            raise PermissionError(errno.EACCES, "read only")
        real_unlink(path, **kwargs)

    monkeypatch.setattr(os, "unlink", refuse_source)
    with pytest.raises(PermissionError):
        move_no_clobber(src, dst)
    assert read(src) == "본문"
    assert not os.path.lexists(dst)


@posix_only
def test_cleanup_keeps_replaced_destination(tmp_path, monkeypatch):
    src = write(tmp_path / "a.txt", "A")
    dst = str(tmp_path / "b.txt")
    real_unlink = os.unlink

    def replace_destination_then_refuse(path, **kwargs):
        if path == src:
            real_unlink(dst)
            write(dst, "B")
            raise PermissionError(errno.EACCES, "read only")
        real_unlink(path, **kwargs)

    monkeypatch.setattr(os, "unlink", replace_destination_then_refuse)
    with pytest.raises(PermissionError):
        move_no_clobber(src, dst)
    assert read(src) == "A"
    assert read(dst) == "B"


def test_windows_uses_rename(tmp_path, monkeypatch):
    src = write(tmp_path / "a.txt", "본문")
    dst = str(tmp_path / "b.txt")

    def unexpected_link(*args, **kwargs):
        raise AssertionError("os.link must not be used on Windows")

    monkeypatch.setattr(os, "link", unexpected_link)
    monkeypatch.setattr(safe_move.sys, "platform", "win32")
    move_no_clobber(src, dst)
    assert not os.path.exists(src)
    assert read(dst) == "본문"
