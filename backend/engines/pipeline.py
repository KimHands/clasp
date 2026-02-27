from sqlalchemy.orm import Session
from typing import Optional
from engines import tier1_rule, tier2_embedding, tier3_llm
from engines.tier2_embedding import infer_tag

# 텍스트 추출이 불가능한 확장자 — 텍스트 없으면 Tier 1만 사용
_NON_TEXT_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "svg", "webp", "bmp",
    "mp4", "mov", "avi", "mkv", "webm",
    "mp3", "wav", "flac", "aac", "ogg",
    "zip", "tar", "gz", "rar", "7z",
}
UNCLASSIFIED_THRESHOLD = 0.31


async def classify(
    file_path: str,
    filename: str,
    extension: str,
    extracted_text: Optional[str],
    db: Session,
    manual_category: Optional[str] = None,
    cover_text: Optional[str] = None,
    custom_category_names: list[str] | None = None,
) -> dict:
    """
    Tier 1 + 2 항상 병렬 실행, API Key 있으면 Tier 3도 항상 실행.
    모든 Tier 결과 중 최적의 카테고리/태그를 선택하여 반환.
    cover_text: 표지 탐지 결과 — 본문 추출이 없는 경우 T2/T3 입력으로 fallback 활용
    반환: { category, tag, tier_used, confidence_score }
    """

    # ── Tier 1: 규칙 기반 (항상 실행) ──
    t1 = tier1_rule.run(
        file_path=file_path,
        filename=filename,
        extension=extension,
        db=db,
        manual_category=manual_category,
        extracted_text=extracted_text,
    )

    # T2/T3에 사용할 텍스트 결정
    t2_input = extracted_text or cover_text
    ext_lower = extension.lstrip(".").lower()

    # 텍스트가 전혀 없는 비텍스트 확장자는 T1만 반환
    if ext_lower in _NON_TEXT_EXTENSIONS and not t2_input:
        return {**t1, "tier_used": 1}

    if not t2_input:
        return {**t1, "tier_used": 1}

    # ── Tier 2: 임베딩 유사도 (텍스트 있으면 항상 실행) ──
    t2 = tier2_embedding.run(t2_input)

    # T1 + T2 결과 조합 → best 선정
    if t1["category"] and t2["category"] and t1["category"] == t2["category"]:
        boosted_score = min(1.0, (t1["confidence_score"] + t2["confidence_score"]) / 2 + 0.10)
        content_tag = infer_tag(t2_input, t1["category"])
        best = {
            "category": t1["category"],
            "tag": content_tag or t1["tag"],
            "tier_used": 2,
            "confidence_score": boosted_score,
        }
    elif t2["category"] and t2["confidence_score"] > t1["confidence_score"]:
        content_tag = infer_tag(t2_input, t2["category"])
        best = {
            "category": t2["category"],
            "tag": content_tag or t1["tag"],
            "tier_used": 2,
            "confidence_score": t2["confidence_score"],
        }
    else:
        tag_category = t1["category"] or t2["category"]
        content_tag = infer_tag(t2_input, tag_category) if tag_category else None
        # 규칙 카테고리가 TAG_CANDIDATES에 없으면 T2 카테고리로 태그 추론 재시도
        if not content_tag and t2.get("category") and t2["category"] != tag_category:
            content_tag = infer_tag(t2_input, t2["category"])
        best = {**t1, "tag": content_tag or t1["tag"], "tier_used": 1}

    # ── Tier 3: 클라우드 LLM (API Key 등록 시 항상 실행) ──
    if tier3_llm.is_available():
        t3 = await tier3_llm.run(t2_input, filename, extra_categories=custom_category_names)
        if t3.get("category") and t3["confidence_score"] > best["confidence_score"]:
            if not t3.get("tag"):
                t3["tag"] = infer_tag(t2_input, t3["category"])
            best = {**t3, "tier_used": 3}

    return best
