import os
import unicodedata


def _normalized_real(path: str) -> str:
    # macOS can report the same Korean path as NFC or NFD
    return unicodedata.normalize("NFC", os.path.realpath(path))


def is_within(path: str, root: str) -> bool:
    real_path = _normalized_real(path)
    real_root = _normalized_real(root)
    try:
        return os.path.commonpath([real_path, real_root]) == real_root
    except ValueError:
        return False


def validate_folder_path(folder_path: str) -> str | None:
    """
    경로를 정규화하고 허용 범위(사용자 홈 하위)인지 검증.
    유효하면 정규화된 경로 반환, 아니면 None.
    """
    real = os.path.realpath(os.path.expanduser(folder_path))
    return real if is_within(real, os.path.expanduser("~")) else None
