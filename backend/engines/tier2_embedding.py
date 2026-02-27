import json
import logging
import os
import re
import sys
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

# 세부 태그 후보 — 카테고리별로 내용 기반 태그를 임베딩 유사도로 선택
TAG_CANDIDATES = {
    "문서": [
        "논문", "보고서", "기획서", "계획서", "회의록", "계약서",
        "매뉴얼", "제안서", "안내문", "공문", "설명서", "협약서",
        "과제", "레포트", "학술", "연구",
    ],
    "프레젠테이션": [
        "발표자료", "세미나", "강의", "컨퍼런스", "시연",
        "교육", "워크숍", "프로젝트발표", "연구발표", "업무보고",
    ],
    "스프레드시트": [
        "예산", "정산", "매출", "재무", "통계", "집계",
        "가계부", "재고", "일정", "현황",
    ],
    "코드": [
        "보안", "네트워크", "알고리즘", "머신러닝", "데이터베이스",
        "운영체제", "암호화", "웹개발", "시스템", "인공지능",
    ],
    "데이터": [
        "분석결과", "로그", "설문", "통계데이터", "실험데이터",
        "수집데이터", "전처리", "시각화", "파이프라인",
    ],
}

# 태그 임베딩 캐시
_tag_embeddings: dict[str, dict[str, np.ndarray]] = {}
# 커스텀 카테고리의 키워드를 태그 후보로 사용
_custom_tag_candidates: dict[str, list[str]] = {}

_model = None
_category_embeddings = None


# ── 피드백 영속화 ──────────────────────────────────────────────────────────────

def _get_feedback_path() -> str:
    """보정된 카테고리 임베딩을 저장할 경로 (database.py의 DB_DIR과 동일 위치)"""
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/Clasp")
    elif sys.platform == "win32":
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Clasp")
    else:
        base = os.path.join(
            os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "Clasp"
        )
    return os.path.join(base, "feedback_embeddings.json")


def _load_feedback_to_embeddings(cat_embeddings: dict[str, np.ndarray]) -> None:
    """
    저장된 피드백 임베딩을 cat_embeddings에 덮어씀.
    파일이 없거나 손상된 경우 무시하고 계속 진행.
    """
    path = _get_feedback_path()
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        applied = 0
        for category, vec in saved.items():
            if category in cat_embeddings:
                cat_embeddings[category] = np.array(vec, dtype=np.float32)
                applied += 1
        logger.info("피드백 임베딩 로드 완료: %d개 카테고리", applied)
    except Exception as e:
        logger.warning("피드백 임베딩 로드 실패 (초기값 사용): %s", e)


def _save_feedback_embeddings(cat_embeddings: dict[str, np.ndarray]) -> None:
    """보정된 카테고리 임베딩 전체를 JSON으로 저장"""
    path = _get_feedback_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        serializable = {k: v.tolist() for k, v in cat_embeddings.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable, f)
        logger.info("피드백 임베딩 저장 완료: %s", path)
    except Exception as e:
        logger.warning("피드백 임베딩 저장 실패: %s", e)


# ──────────────────────────────────────────────────────────────────────────────


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
        # 이전 세션에서 저장된 피드백 적용 (없으면 무시)
        _load_feedback_to_embeddings(_category_embeddings)
    return _category_embeddings


def _get_tag_embeddings(category: str) -> dict[str, np.ndarray]:
    """카테고리별 태그 후보 임베딩 캐시 반환 (내장 + 커스텀 태그 후보 통합)"""
    global _tag_embeddings
    if category not in _tag_embeddings:
        candidates = list(TAG_CANDIDATES.get(category, []))
        candidates.extend(_custom_tag_candidates.get(category, []))
        seen = set()
        unique = [c for c in candidates if not (c in seen or seen.add(c))]
        if not unique:
            return {}
        model = _get_model()
        _tag_embeddings[category] = {
            tag: model.encode(tag)
            for tag in unique
        }
    return _tag_embeddings[category]


def infer_tag(text: str, category: str, threshold: float = 0.35) -> Optional[str]:
    """
    텍스트 임베딩과 태그 후보 임베딩 간 코사인 유사도로 세부 태그 추론.
    threshold 이상인 후보 중 가장 유사한 태그 반환, 없으면 None.
    """
    if not text or not category:
        return None
    candidates = _get_tag_embeddings(category)
    if not candidates:
        return None

    try:
        model = _get_model()
        text_emb = model.encode(text.strip()[:2000])

        best_tag = None
        best_score = 0.0
        for tag, tag_emb in candidates.items():
            score = float(
                cosine_similarity(
                    text_emb.reshape(1, -1),
                    tag_emb.reshape(1, -1),
                )[0][0]
            )
            if score > best_score:
                best_score = score
                best_tag = tag

        return best_tag if best_score >= threshold else None
    except Exception as e:
        logger.warning("태그 추론 실패: %s", e)
        return None


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


def load_custom_categories(custom_categories: list[dict]) -> None:
    """
    사용자 정의 카테고리를 임베딩 캐시에 추가.
    내장 카테고리는 유지하고 커스텀 카테고리만 갱신(이전 커스텀 제거 후 재추가).
    키워드가 있으면 태그 후보로도 등록하여 infer_tag에서 사용 가능.
    custom_categories: [{"name": "...", "keywords": ["...", ...]}, ...]
    """
    global _custom_tag_candidates, _tag_embeddings

    # 이전 커스텀 태그 캐시 정리
    for cat_name in list(_custom_tag_candidates.keys()):
        _tag_embeddings.pop(cat_name, None)
    _custom_tag_candidates.clear()

    cat_embeddings = _get_category_embeddings()
    builtin = set(CATEGORY_KEYWORDS.keys())

    # 이전 커스텀 카테고리 제거 (내장 카테고리는 유지)
    for key in list(cat_embeddings.keys()):
        if key not in builtin:
            _tag_embeddings.pop(key, None)
            del cat_embeddings[key]

    if not custom_categories:
        return

    model = _get_model()

    for entry in custom_categories:
        name = entry.get("name", "").strip()
        keywords = [kw for kw in entry.get("keywords", []) if kw.strip()]
        if not name:
            continue
        if keywords:
            kw_embs = model.encode(keywords)
            cat_embeddings[name] = kw_embs.mean(axis=0)
            _custom_tag_candidates[name] = keywords
        else:
            cat_embeddings[name] = model.encode(name)

    _load_feedback_to_embeddings(cat_embeddings)
    logger.info("커스텀 카테고리 %d개 임베딩 완료", len(custom_categories))


def apply_feedback(text: str, correct_category: str) -> None:
    """
    수동 분류 피드백 반영 — 해당 카테고리 임베딩을 파일 텍스트 방향으로 점진적 보정.
    learning_rate=0.05: 기존 임베딩 95% + 새 텍스트 임베딩 5% 가중 이동 평균.
    카테고리 임베딩 캐시와 feedback_embeddings.json 파일을 모두 갱신하므로 재시작 후에도 유지됨.
    내장 카테고리와 커스텀 카테고리 모두 지원.
    """
    if not text or not text.strip():
        return
    cat_embeddings = _get_category_embeddings()
    if correct_category not in cat_embeddings:
        return

    try:
        model = _get_model()

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
        # 보정 결과를 파일로 저장 — 재시작 후에도 유지됨
        _save_feedback_embeddings(cat_embeddings)
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
