import uuid
from sqlalchemy.orm import Session
from models.schema import CoverPage, CoverSimilarityGroup
from engines.tier2_embedding import compute_embedding, compute_similarity

# 유사 그룹으로 묶는 최소 유사도 임계값
SIMILARITY_THRESHOLD = 0.80


def save_cover(db: Session, file_id: int, cover_text: str) -> CoverPage:
    """표지 텍스트 임베딩 계산 후 DB 저장"""
    embedding_json = compute_embedding(cover_text)

    existing = db.query(CoverPage).filter(CoverPage.file_id == file_id).first()
    if existing:
        existing.cover_text = cover_text
        existing.embedding = embedding_json
        db.commit()
        db.refresh(existing)
        return existing

    cover = CoverPage(
        file_id=file_id,
        cover_text=cover_text,
        embedding=embedding_json,
    )
    db.add(cover)
    db.commit()
    db.refresh(cover)
    return cover


def compute_similarity_groups(db: Session) -> None:
    """
    모든 표지 임베딩 간 유사도 계산 → 그룹 생성
    유사도 >= SIMILARITY_THRESHOLD 인 파일끼리 같은 group_id 부여
    """
    covers: list[CoverPage] = db.query(CoverPage).filter(
        CoverPage.embedding.isnot(None)
    ).all()

    if len(covers) < 2:
        return

    # 기존 유사도 그룹 삭제 후 재계산
    db.query(CoverSimilarityGroup).delete()
    db.commit()

    # Union-Find로 그룹 묶기
    parent = {c.file_id: c.file_id for c in covers}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(len(covers)):
        for j in range(i + 1, len(covers)):
            score = compute_similarity(covers[i].embedding, covers[j].embedding)
            if score >= SIMILARITY_THRESHOLD:
                union(covers[i].file_id, covers[j].file_id)

    # 그룹 ID 할당 (같은 루트 = 같은 그룹)
    group_map: dict[int, str] = {}
    for cover in covers:
        root = find(cover.file_id)
        if root not in group_map:
            group_map[root] = str(uuid.uuid4())[:8]

    # 2개 이상 묶인 그룹만 저장
    root_counts: dict[int, list] = {}
    for cover in covers:
        root = find(cover.file_id)
        root_counts.setdefault(root, []).append(cover)

    for root, group_covers in root_counts.items():
        if len(group_covers) < 2:
            continue
        group_id = group_map[root]
        for cover in group_covers:
            # 그룹 내 평균 유사도 계산
            scores = []
            for other in group_covers:
                if other.file_id != cover.file_id:
                    scores.append(compute_similarity(cover.embedding, other.embedding))
            avg_score = sum(scores) / len(scores) if scores else 0.0

            entry = CoverSimilarityGroup(
                group_id=group_id,
                file_id=cover.file_id,
                similarity_score=avg_score,
                auto_tag=None,
            )
            db.add(entry)

    db.commit()
