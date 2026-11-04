import os
import sys


class ConcurrentChange(OSError):
    """이동 도중 원본이 다른 파일로 바뀌어 원본을 지우지 않았음"""


def inode_of(path: str) -> str:
    """이동 후에도 유지되는 파일 식별값 (Windows 값은 정수 컬럼 범위를 넘을 수 있어 문자열)"""
    return str(os.lstat(path).st_ino)


def _is_same_file(a: str, b: str) -> bool:
    try:
        return os.path.samestat(os.lstat(a), os.lstat(b))
    except FileNotFoundError:
        return False


def move_no_clobber(src: str, dst: str) -> None:
    """
    대상을 덮어쓰지 않고 파일을 옮긴다.
    대상이 있으면 FileExistsError를 내고 양쪽 파일을 바꾸지 않는다.
    호출자가 대상 폴더를 만들어 둬야 한다.
    """
    if sys.platform == "win32":
        # os.rename refuses an existing destination on Windows
        os.rename(src, dst)
        return

    os.link(src, dst, follow_symlinks=False)
    if not _is_same_file(src, dst):
        raise ConcurrentChange(f"source changed during move: {src}")
    try:
        os.unlink(src)
    except OSError:
        # 경로 이름만 믿지 않고, 방금 만든 링크일 때만 지운다
        if _is_same_file(src, dst):
            os.unlink(dst)
        raise
