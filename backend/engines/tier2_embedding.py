import json
import logging
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# 카테고리별 대표 키워드 (임베딩 비교 기준) — Tier 1 카테고리 체계와 통일
CATEGORY_KEYWORDS = {
    "문서": [
        "보고서", "report", "논문", "paper", "제안서", "명세서",
        "과제", "레포트", "계획서", "기획서", "회의록", "계약서",
        "지침서", "매뉴얼", "안내문", "공문", "설명서", "협약서", "의뢰서",
    ],
    "프레젠테이션": [
        "발표", "presentation", "슬라이드", "PPT", "피피티",
        "keynote", "덱", "deck", "발표자료", "강의", "세미나",
        "프레젠테이션", "발표문", "발표회", "시연",
    ],
    "스프레드시트": [
        "스프레드시트", "엑셀", "excel", "표", "통계",
        "집계", "수식", "셀", "시트", "데이터표",
        "가계부", "예산", "정산", "매출", "재무",
    ],
    "코드": [
        "프로그래밍", "programming", "코드", "함수", "클래스",
        "알고리즘", "algorithm", "보안", "security", "데이터베이스",
        "database", "네트워크", "network", "머신러닝", "machine learning",
        "운영체제", "OS", "소스코드", "개발", "구현",
    ],
    "데이터": [
        "데이터", "data", "분석", "CSV", "JSON", "XML",
        "쿼리", "SQL", "파이프라인", "ETL", "로그",
        "수집", "전처리", "시각화", "통계", "샘플",
    ],
}

_model = None
_category_embeddings = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


def _get_category_embeddings():
    global _category_embeddings
    if _category_embeddings is None:
        model = _get_model()
        _category_embeddings = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            # 키워드별 개별 임베딩 후 평균 — 단순 문자열 결합보다 각 키워드 의미가 고르게 반영됨
            keyword_embs = model.encode(keywords)
            _category_embeddings[category] = keyword_embs.mean(axis=0)
    return _category_embeddings


def run(text: str) -> dict:
    """
    텍스트 임베딩 후 카테고리별 코사인 유사도 계산
    반환: { category, tag, confidence_score, embedding }
    """
    if not text or not text.strip():
        return {"category": None, "tag": None, "confidence_score": 0.0, "embedding": None}

    try:
        model = _get_model()
        cat_embeddings = _get_category_embeddings()

        text_embedding = model.encode(text.strip()[:2000])

        best_category = None
        best_score = 0.0

        for category, cat_emb in cat_embeddings.items():
            score = float(
                cosine_similarity(
                    text_embedding.reshape(1, -1),
                    cat_emb.reshape(1, -1)
                )[0][0]
            )
            if score > best_score:
                best_score = score
                best_category = category

        embedding_json = json.dumps(text_embedding.tolist())

        return {
            "category": best_category if best_score > 0.3 else None,
            "tag": None,
            "confidence_score": best_score,
            "embedding": embedding_json,
        }
    except Exception as e:
        logger.warning("Tier 2 임베딩 분류 실패: %s", e)
        return {"category": None, "tag": None, "confidence_score": 0.0, "embedding": None}


def apply_feedback(text: str, correct_category: str) -> None:
    """
    수동 분류 피드백 반영 — 해당 카테고리 임베딩을 파일 텍스트 방향으로 점진적 보정.
    learning_rate=0.05: 기존 임베딩 95% + 새 텍스트 임베딩 5% 가중 이동 평균.
    카테고리 임베딩 캐시를 직접 갱신하므로 재시작 전까지 즉시 효과 발생.
    """
    if not text or not text.strip():
        return
    if correct_category not in CATEGORY_KEYWORDS:
        return

    try:
        model = _get_model()
        cat_embeddings = _get_category_embeddings()

        text_emb = model.encode(text.strip()[:2000])
        current_emb = cat_embeddings[correct_category]

        learning_rate = 0.05
        updated_emb = (1 - learning_rate) * current_emb + learning_rate * text_emb

        # L2 정규화로 코사인 유사도 계산 안정성 유지
        norm = float(np.linalg.norm(updated_emb))
        if norm > 0:
            updated_emb = updated_emb / norm

        cat_embeddings[correct_category] = updated_emb
        logger.info("피드백 반영: 카테고리='%s' 임베딩 보정 완료", correct_category)
    except Exception as e:
        logger.warning("피드백 임베딩 보정 실패: %s", e)


def compute_embedding(text: str) -> Optional[str]:
    """표지 텍스트 임베딩 계산 후 JSON 직렬화"""
    if not text:
        return None
    try:
        model = _get_model()
        emb = model.encode(text.strip()[:500])
        return json.dumps(emb.tolist())
    except Exception:
        return None


def compute_similarity(embedding_json_a: str, embedding_json_b: str) -> float:
    """두 임베딩 JSON 간 코사인 유사도 계산"""
    try:
        a = np.array(json.loads(embedding_json_a))
        b = np.array(json.loads(embedding_json_b))
        return float(cosine_similarity(a.reshape(1, -1), b.reshape(1, -1))[0][0])
    except Exception:
        return 0.0
