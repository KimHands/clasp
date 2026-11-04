import os

from conftest import write
from services.scan_service import _collect_files


def test_collect_skips_file_symlinks(home):
    write(f"{home}/outside/secret.txt", "비밀")
    write(f"{home}/r/a.txt", "본문")
    os.symlink(f"{home}/outside/secret.txt", f"{home}/r/link.txt")
    assert [os.path.basename(p) for p in _collect_files(f"{home}/r")] == ["a.txt"]
