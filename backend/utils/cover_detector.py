import re
from typing import Optional


# 날짜 패턴: 2024-01-01, 2024/01/01, 2024.01.01, 2024년 1월
_DATE_PATTERN = re.compile(
    r"\d{4}[-./년]\s*\d{1,2}[-./월]?\s*\d{0,2}일?"
)

# 학번 패턴 (기존): 2000년대 대학 학번 (20XX + 6~8자리)
_STUDENT_ID_PATTERN = re.compile(r"\b20\d{6,8}\b")

# 광의의 식별번호: 6~10자리 연속 숫자 — 기관별 다양한 학번/사번 형식 포함
# lookbehind/lookahead로 더 긴 숫자열의 일부를 오매칭하지 않도록 처리
_PERSONNEL_ID_PATTERN = re.compile(r"(?<!\d)\d{6,10}(?!\d)")

# 표지 고유 키워드 — 학사/직장 문서 표지에 나타나는 필드명, 본문에는 거의 등장하지 않음
_COVER_KEYWORD_PATTERN = re.compile(
    r"(학번|사번|학과|학부|소속|담당\s*교수|지도\s*교수|제출일|제출자|작성자|작성일|부서|직책|성명|교과목|과목명)",
    re.IGNORECASE,
)

COVER_TEXT_MAX_LEN = 300


def is_cover_page(text: str) -> bool:
    """
    표지 판정 기준:
    1. 텍스트 길이 300자 미만
    2. 다음 중 하나 이상 포함:
       - 날짜 패턴 (2024-01-01, 2024년 1월 등)
       - 식별번호 패턴 (6~10자리 연속 숫자 — 기관별 다양한 학번/사번 포함)
       - 표지 고유 키워드 (학번, 담당교수, 소속, 작성자, 부서 등)
    """
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) >= COVER_TEXT_MAX_LEN:
        return False
    has_date = bool(_DATE_PATTERN.search(stripped))
    has_id = bool(_STUDENT_ID_PATTERN.search(stripped)) or bool(_PERSONNEL_ID_PATTERN.search(stripped))
    has_keyword = bool(_COVER_KEYWORD_PATTERN.search(stripped))
    return has_date or has_id or has_keyword


def extract_cover_text(file_path: str) -> Optional[str]:
    """
    PDF/DOCX 첫 페이지(또는 첫 단락 블록) 텍스트 추출 후 표지 여부 판정
    표지로 판정되면 텍스트 반환, 아니면 None
    """
    import os
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _extract_pdf_cover(file_path)
    elif ext == ".docx":
        return _extract_docx_cover(file_path)
    return None


def _extract_pdf_cover(file_path: str) -> Optional[str]:
    doc = None
    try:
        import fitz
        doc = fitz.open(file_path)
        if len(doc) == 0:
            return None
        first_page_text = doc[0].get_text("text").strip()
        if is_cover_page(first_page_text):
            return first_page_text
    except Exception:
        pass
    finally:
        if doc:
            doc.close()
    return None


def _extract_docx_cover(file_path: str) -> Optional[str]:
    """DOCX 첫 페이지 구간(첫 10개 단락)에서 표지 판정"""
    try:
        from docx import Document
    except ImportError:
        return None

    try:
        doc = Document(file_path)
        first_paragraphs = [p.text.strip() for p in doc.paragraphs[:10] if p.text.strip()]
        if not first_paragraphs:
            return None
        candidate = "\n".join(first_paragraphs)
        if is_cover_page(candidate):
            return candidate
    except Exception:
        pass
    return None
