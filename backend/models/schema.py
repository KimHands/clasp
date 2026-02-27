from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String, nullable=False, unique=True)
    filename = Column(String, nullable=False)
    extension = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    modified_at = Column(DateTime, nullable=True)
    size = Column(Integer, nullable=True)
    extracted_text_summary = Column(Text, nullable=True)

    classifications = relationship("Classification", back_populates="file", cascade="all, delete-orphan")
    cover_page = relationship("CoverPage", back_populates="file", uselist=False, cascade="all, delete-orphan")
    similarity_groups = relationship("CoverSimilarityGroup", back_populates="file", cascade="all, delete-orphan")


class Classification(Base):
    __tablename__ = "classifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    scan_id = Column(String, nullable=False)
    category = Column(String, nullable=True)
    tag = Column(String, nullable=True)
    tier_used = Column(Integer, nullable=False)
    confidence_score = Column(Float, nullable=False)
    is_manual = Column(Boolean, default=False, nullable=False)
    classified_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    file = relationship("File", back_populates="classifications")


class CoverPage(Base):
    __tablename__ = "cover_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, unique=True)
    cover_text = Column(Text, nullable=True)
    # JSON 직렬화된 임베딩 벡터
    embedding = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    file = relationship("File", back_populates="cover_page")


class CoverSimilarityGroup(Base):
    __tablename__ = "cover_similarity_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String, nullable=False)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    auto_tag = Column(String, nullable=True)

    file = relationship("File", back_populates="similarity_groups")


class ActionBatch(Base):
    """폴더별 정리 적용 배치 — 이력 조회 및 선택적 Undo의 단위"""
    __tablename__ = "action_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_log_id = Column(String, nullable=False, unique=True)
    folder_path = Column(String, nullable=False, index=True)
    scan_id = Column(String, nullable=False)
    moved_count = Column(Integer, default=0, nullable=False)
    skipped_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    conflict_resolution = Column(String, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_undone = Column(Boolean, default=False, nullable=False)

    logs = relationship("ActionLog", back_populates="batch", cascade="all, delete-orphan")


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_log_id = Column(String, ForeignKey("action_batches.action_log_id"), nullable=False)
    action_type = Column(String, nullable=False)
    source_path = Column(String, nullable=False)
    destination_path = Column(String, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_undone = Column(Boolean, default=False, nullable=False)

    batch = relationship("ActionBatch", back_populates="logs")


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    priority = Column(Integer, nullable=False)
    # 규칙 유형: date / content / extension
    type = Column(String, nullable=False)
    value = Column(String, nullable=False)
    folder_name = Column(String, nullable=False)
    # 부모 규칙 ID (NULL이면 루트 레벨, 값이 있으면 해당 규칙의 하위 중첩)
    parent_id = Column(Integer, ForeignKey("rules.id"), nullable=True)


class CustomExtension(Base):
    """사용자가 설정에서 추가한 확장자 → 카테고리 매핑"""
    __tablename__ = "custom_extensions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    extension = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=False)


class CustomCategory(Base):
    """사용자가 설정에서 추가한 커스텀 분류 카테고리"""
    __tablename__ = "custom_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    # JSON 배열 문자열로 저장: ["keyword1", "keyword2", ...]
    keywords = Column(Text, nullable=False, default="[]")
