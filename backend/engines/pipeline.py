from sqlalchemy.orm import Session
from typing import Optional
from engines import tier1_rule, tier2_embedding, tier3_llm

# Tier 1 → Tier 2 전환 임계값
TIER1_CONFIDENCE_THRESHOLD = 0.80
# Tier 2 → Tier 3 전환 임계값
TIER2_CONFIDENCE_THRESHOLD = 0.50
# 미분류 임계값 (이 이하면 미분류 처리)
UNCLASSIFIED_THRESHOLD = 0.31


async def classify(
    file_path: str,
    filename: str,
    extension: str,
    extracted_text: Optional[str],
    db: Session,
    manual_category: Optional[str] = None,
) -> dict:
    """
    Tier 1 → 2 → 3 순차 실행
    각 Tier 결과의 confidence_score 기준으로 다음 Tier 실행 여부 결정
    반환: { category, tag, tier_used, confidence_score }
    """

    # Tier 1: 규칙 기반
    t1 = tier1_rule.run(
        file_path=file_path,
        filename=filename,
        extension=extension,
        db=db,
        manual_category=manual_category,
    )

    if t1["confidence_score"] >= TIER1_CONFIDENCE_THRESHOLD:
        return {**t1, "tier_used": 1}

    # Tier 2: 임베딩 유사도 (텍스트 있을 때만)
    if extracted_text:
        t2 = tier2_embedding.run(extracted_text)

        if t2["confidence_score"] >= TIER2_CONFIDENCE_THRESHOLD:
            return {
                "category": t2["category"],
                "tag": t2["tag"],
                "tier_used": 2,
                "confidence_score": t2["confidence_score"],
            }

        # Tier 3: 클라우드 LLM (Tier 2 threshold 미달 + API Key 있을 때)
        if tier3_llm.is_available():
            t3 = await tier3_llm.run(extracted_text, filename)
            if t3["confidence_score"] > max(t1["confidence_score"], t2["confidence_score"]):
                return {**t3, "tier_used": 3}

        # Tier 1과 Tier 2 중 신뢰도가 높은 결과 채택
        if t2["confidence_score"] > t1["confidence_score"]:
            return {
                "category": t2["category"],
                "tag": t2["tag"],
                "tier_used": 2,
                "confidence_score": t2["confidence_score"],
            }

    # Tier 1 결과 사용 (텍스트 없거나 Tier 2 미개선)
    return {**t1, "tier_used": 1}
