import re
from typing import Optional


# 날짜 패턴: 2024-01-01, 2024/01/01, 2024.01.01, 2024년 1월
_DATE_PATTERN = re.compile(
    r"\d{4}[-./년]\s*\d{1,2}[-./월]?\s*\d{0,2}일?"
)

# 학번 패턴: 20XX + 6~8자리 숫자
_STUDENT_ID_PATTERN = re.compile(r"\b20\d{6,8}\b")

COVER_TEXT_MAX_LEN = 300


def is_cover_page(text: str) -> bool:
    """
    표지 판정 기준:
    1. 텍스트 길이 300자 미만
    2. 날짜 패턴 또는 학번 패턴 포함
    """
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) >= COVER_TEXT_MAX_LEN:
        return False
    has_date = bool(_DATE_PATTERN.search(stripped))
    has_student_id = bool(_STUDENT_ID_PATTERN.search(stripped))
    return has_date or has_student_id


def extract_cover_text(file_path: str) -> Optional[str]:
    """
    PDF 첫 페이지 텍스트 추출 후 표지 여부 판정
    표지로 판정되면 텍스트 반환, 아니면 None
    """
    ext = file_path.lower().rsplit(".", 1)[-1]
    if ext != "pdf":
        return None

    try:
        import fitz
        doc = fitz.open(file_path)
        if len(doc) == 0:
            doc.close()
            return None
        first_page_text = doc[0].get_text("text").strip()
        doc.close()
        if is_cover_page(first_page_text):
            return first_page_text
    except Exception:
        pass
    return None
