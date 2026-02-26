from sqlalchemy.orm import Session
from models.schema import Classification, File
from utils.errors import ErrorCode, raise_error


def update_manual_classification(
    db: Session,
    file_id: int,
    category: str | None,
    tag: str | None,
) -> dict:
    """
    UC-04: 수동 분류 수정
    - is_manual=True 로 저장 → 다음 스캔 시 Tier 1에서 우선 참조
    - 기존 수동 분류가 있으면 업데이트, 없으면 신규 생성
    """
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise_error(ErrorCode.FILE_NOT_FOUND)

    # 최신 자동 분류에서 scan_id, tier_used, confidence_score 참조
    latest_auto = (
        db.query(Classification)
        .filter(Classification.file_id == file_id, Classification.is_manual == False)
        .order_by(Classification.classified_at.desc())
        .first()
    )

    scan_id = latest_auto.scan_id if latest_auto else "manual"

    # 기존 수동 분류 업데이트
    existing_manual = (
        db.query(Classification)
        .filter(Classification.file_id == file_id, Classification.is_manual == True)
        .first()
    )

    try:
        if existing_manual:
            if category is not None:
                existing_manual.category = category
            if tag is not None:
                existing_manual.tag = tag
            db.commit()
            db.refresh(existing_manual)
            cls = existing_manual
        else:
            cls = Classification(
                file_id=file_id,
                scan_id=scan_id,
                category=category,
                tag=tag,
                tier_used=0,
                confidence_score=1.0,
                is_manual=True,
            )
            db.add(cls)
            db.commit()
            db.refresh(cls)
    except Exception:
        db.rollback()
        raise_error(ErrorCode.SAVE_FAILED)

    return {
        "id": file_id,
        "filename": file.filename,
        "category": cls.category,
        "tag": cls.tag,
        "tier_used": cls.tier_used,
        "confidence_score": cls.confidence_score,
        "is_manual": cls.is_manual,
    }
