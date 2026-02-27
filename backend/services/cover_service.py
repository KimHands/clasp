import json
import uuid

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as _cosine_similarity_matrix
from sqlalchemy.orm import Session

from models.schema import CoverPage, CoverSimilarityGroup, Classification
from engines.tier2_embedding import compute_embedding, infer_tag

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

    최적화: 임베딩 JSON을 한 번씩만 역직렬화해 (n×384) 행렬을 구성하고,
    sklearn cosine_similarity(matrix, matrix)로 전체 유사도를 1회 일괄 계산.
    기존 O(n²) JSON 역직렬화 + sklearn 호출을 O(n) 역직렬화 + 1회 행렬 연산으로 단축.
    """
    covers: list[CoverPage] = db.query(CoverPage).filter(
        CoverPage.embedding.isnot(None)
    ).all()

    if len(covers) < 2:
        return

    db.query(CoverSimilarityGroup).delete()
    db.commit()

    # 임베딩 JSON → numpy 벡터 일괄 변환, 파싱 실패 항목 제외
    valid_covers: list[CoverPage] = []
    vectors: list[np.ndarray] = []
    for cover in covers:
        try:
            vec = np.array(json.loads(cover.embedding), dtype=np.float32)
            valid_covers.append(cover)
            vectors.append(vec)
        except Exception:
            continue

    if len(valid_covers) < 2:
        return

    # (n × 384) 행렬 구성 후 전체 유사도 행렬 1회 계산
    matrix = np.stack(vectors)                              # shape: (n, 384)
    sim_matrix = _cosine_similarity_matrix(matrix, matrix)  # shape: (n, n)

    n = len(valid_covers)
    idx_map = {cover.file_id: i for i, cover in enumerate(valid_covers)}
    parent = {c.file_id: c.file_id for c in valid_covers}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    # 유사도 행렬에서 상삼각 영역만 순회해 Union-Find 구성
    for i in range(n):
        for j in range(i + 1, n):
            if float(sim_matrix[i, j]) >= SIMILARITY_THRESHOLD:
                union(valid_covers[i].file_id, valid_covers[j].file_id)

    group_map: dict[int, str] = {}
    for cover in valid_covers:
        root = find(cover.file_id)
        if root not in group_map:
            group_map[root] = str(uuid.uuid4())

    root_counts: dict[int, list] = {}
    for cover in valid_covers:
        root = find(cover.file_id)
        root_counts.setdefault(root, []).append(cover)

    for root, group_covers in root_counts.items():
        if len(group_covers) < 2:
            continue
        group_id = group_map[root]

        # 그룹 대표 auto_tag: 그룹 내 표지 텍스트를 합쳐 카테고리 기반 태그 추론
        group_cover_texts = " ".join(
            c.cover_text for c in group_covers if c.cover_text
        )
        group_category = _get_group_category(db, [c.file_id for c in group_covers])
        auto_tag = infer_tag(group_cover_texts, group_category) if group_category else None

        for cover in group_covers:
            i = idx_map[cover.file_id]
            other_indices = [
                idx_map[other.file_id]
                for other in group_covers
                if other.file_id != cover.file_id
            ]
            # 사전 계산된 행렬에서 직접 읽기 — 재계산 없음
            avg_score = float(np.mean([sim_matrix[i, j] for j in other_indices])) if other_indices else 0.0

            entry = CoverSimilarityGroup(
                group_id=group_id,
                file_id=cover.file_id,
                similarity_score=avg_score,
                auto_tag=auto_tag,
            )
            db.add(entry)

    db.commit()


def _get_group_category(db: Session, file_ids: list[int]) -> str | None:
    """그룹 내 파일들의 분류 카테고리 중 최빈값 반환"""
    from collections import Counter
    rows = (
        db.query(Classification.category)
        .filter(
            Classification.file_id.in_(file_ids),
            Classification.is_manual == False,
            Classification.category.isnot(None),
        )
        .all()
    )
    if not rows:
        return None
    counter = Counter(r.category for r in rows)
    return counter.most_common(1)[0][0]
