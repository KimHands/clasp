import re
import os
from typing import Optional
from sqlalchemy.orm import Session
from models.schema import Classification, Rule

# 확장자 → 기본 카테고리 매핑
_EXT_CATEGORY_MAP = {
    "pdf": "문서",
    "docx": "문서",
    "doc": "문서",
    "txt": "문서",
    "md": "문서",
    "pptx": "프레젠테이션",
    "ppt": "프레젠테이션",
    "xlsx": "스프레드시트",
    "xls": "스프레드시트",
    "csv": "데이터",
    "json": "데이터",
    "xml": "데이터",
    "py": "코드",
    "js": "코드",
    "ts": "코드",
    "java": "코드",
    "cpp": "코드",
    "c": "코드",
    "h": "코드",
    "go": "코드",
    "rs": "코드",
    "jpg": "이미지",
    "jpeg": "이미지",
    "png": "이미지",
    "gif": "이미지",
    "svg": "이미지",
    "mp4": "영상",
    "mov": "영상",
    "avi": "영상",
    "mp3": "오디오",
    "wav": "오디오",
    "zip": "압축",
    "tar": "압축",
    "gz": "압축",
}

# 파일명에서 연도 추출 패턴
_YEAR_PATTERN = re.compile(r"(20\d{2}|19\d{2})")


def run(
    file_path: str,
    filename: str,
    extension: str,
    db: Session,
    manual_category: Optional[str] = None,
) -> dict:
    """
    Tier 1 규칙 기반 분류
    - 수동 분류 결과 우선 참조
    - 사용자 정의 규칙 적용
    - 확장자 기본 매핑 fallback
    반환: { category, tag, confidence_score }
    """

    # 수동 분류 결과 최우선 적용 (is_manual=True)
    if manual_category:
        return {
            "category": manual_category,
            "tag": None,
            "confidence_score": 1.0,
        }

    # 사용자 정의 규칙 적용 (우선순위 오름차순)
    rules: list[Rule] = db.query(Rule).order_by(Rule.priority).all()
    for rule in rules:
        matched = _match_rule(rule, file_path, filename, extension)
        if matched:
            return {
                "category": rule.folder_name,
                "tag": None,
                "confidence_score": 0.85,
            }

    # 확장자 기본 매핑
    ext_lower = extension.lstrip(".").lower()
    if ext_lower in _EXT_CATEGORY_MAP:
        category = _EXT_CATEGORY_MAP[ext_lower]
        # 파일명에서 연도 추출해 태그 생성
        year_match = _YEAR_PATTERN.search(filename)
        tag = f"{category}_{year_match.group()}" if year_match else None
        return {
            "category": category,
            "tag": tag,
            "confidence_score": 0.70,
        }

    return {
        "category": None,
        "tag": None,
        "confidence_score": 0.0,
    }


def _match_rule(rule: Rule, file_path: str, filename: str, extension: str) -> bool:
    """규칙 유형별 매칭"""
    rule_type = rule.type
    value = rule.value.lower()

    if rule_type == "extension":
        return extension.lstrip(".").lower() == value

    if rule_type == "date":
        year_match = _YEAR_PATTERN.search(filename)
        return bool(year_match and year_match.group() == value)

    if rule_type == "content":
        # 파일명에 키워드 포함 여부 (내용 기반은 Tier 2에서 처리)
        return value in filename.lower()

    return False
