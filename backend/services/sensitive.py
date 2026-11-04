import unicodedata

from sqlalchemy.orm import Session

from models.schema import CoverPage, CoverSimilarityGroup, File, SensitiveKeyword


def _folded(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def load_keywords(db: Session) -> list[str]:
    return [row.keyword for row in db.query(SensitiveKeyword).all()]


def is_sensitive(filename: str, keywords: list[str]) -> bool:
    name = _folded(filename)
    return any(_folded(keyword) in name for keyword in keywords)


def purge_stored_content(db: Session, file: File) -> bool:
    """민감 파일에 이미 저장된 본문과 표지를 지운다. 지운 것이 있으면 True"""
    purged = file.extracted_text_summary is not None
    file.extracted_text_summary = None
    for model in (CoverPage, CoverSimilarityGroup):
        purged = db.query(model).filter(model.file_id == file.id).delete() > 0 or purged
    return purged
