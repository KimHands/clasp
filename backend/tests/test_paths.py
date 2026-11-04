import unicodedata

from utils.paths import is_within, validate_folder_path


def test_is_within_accepts_child_and_self(home):
    assert is_within(f"{home}/b/x", f"{home}/b")
    assert is_within(f"{home}/b", f"{home}/b")


def test_is_within_rejects_sibling_prefix(home):
    assert not is_within(f"{home}/bc/x", f"{home}/b")


def test_is_within_treats_nfc_and_nfd_as_same(home):
    assert is_within(
        unicodedata.normalize("NFD", f"{home}/문서/x"),
        unicodedata.normalize("NFC", f"{home}/문서"),
    )


def test_validate_rejects_outside_home(home):
    assert validate_folder_path("/etc") is None


def test_validate_returns_real_path_inside_home(home):
    assert validate_folder_path(f"{home}/a/../b") == f"{home}/b"
