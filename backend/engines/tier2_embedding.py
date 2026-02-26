from typing import Optional
import json

# 카테고리별 대표 키워드 (임베딩 비교 기준)
CATEGORY_KEYWORDS = {
    "보안": ["보안", "security", "암호화", "취약점", "방화벽", "인증", "접근제어"],
    "데이터베이스": ["데이터베이스", "database", "SQL", "쿼리", "테이블", "인덱스", "ORM"],
    "네트워크": ["네트워크", "network", "TCP", "IP", "라우터", "프로토콜", "소켓"],
    "알고리즘": ["알고리즘", "algorithm", "정렬", "탐색", "복잡도", "자료구조"],
    "머신러닝": ["머신러닝", "machine learning", "딥러닝", "신경망", "모델", "학습", "AI"],
    "운영체제": ["운영체제", "OS", "프로세스", "스레드", "메모리", "스케줄링"],
    "프로그래밍": ["프로그래밍", "programming", "코드", "함수", "클래스", "객체"],
    "문서": ["보고서", "report", "논문", "paper", "제안서", "명세서"],
    "프레젠테이션": ["발표", "presentation", "슬라이드", "PPT"],
    "데이터": ["데이터", "data", "분석", "통계", "CSV", "엑셀"],
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
            text = " ".join(keywords)
            _category_embeddings[category] = model.encode(text)
    return _category_embeddings


def run(text: str) -> dict:
    """
    텍스트 임베딩 후 카테고리별 코사인 유사도 계산
    반환: { category, tag, confidence_score, embedding }
    """
    if not text or not text.strip():
        return {"category": None, "tag": None, "confidence_score": 0.0, "embedding": None}

    try:
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        model = _get_model()
        cat_embeddings = _get_category_embeddings()

        text_embedding = model.encode(text.strip()[:1000])

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
    except Exception:
        return {"category": None, "tag": None, "confidence_score": 0.0, "embedding": None}


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
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity

        a = np.array(json.loads(embedding_json_a))
        b = np.array(json.loads(embedding_json_b))
        return float(cosine_similarity(a.reshape(1, -1), b.reshape(1, -1))[0][0])
    except Exception:
        return 0.0
