import os
from typing import Optional

SYSTEM_PROMPT = """당신은 파일 분류 전문가입니다.
주어진 파일의 텍스트 요약을 보고 가장 적합한 카테고리와 태그를 JSON으로 반환하세요.

응답 형식 (JSON만 반환):
{
  "category": "카테고리명",
  "tag": "태그명 (없으면 null)",
  "confidence_score": 0.0~1.0
}

카테고리 예시: 보안, 데이터베이스, 네트워크, 알고리즘, 머신러닝, 운영체제, 프로그래밍, 문서, 프레젠테이션, 데이터
"""


def is_available() -> bool:
    """OpenAI API Key 설정 여부 확인"""
    return bool(os.environ.get("OPENAI_API_KEY"))


async def run(text: str, filename: str) -> dict:
    """
    OpenAI API로 파일 분류 (API Key 있을 때만 실행)
    반환: { category, tag, confidence_score }
    """
    if not is_available():
        return {"category": None, "tag": None, "confidence_score": 0.0}

    try:
        from openai import AsyncOpenAI
        import json

        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

        user_message = f"파일명: {filename}\n\n텍스트 요약:\n{text[:800]}"

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=200,
        )

        content = response.choices[0].message.content.strip()
        # JSON 블록 추출
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        result = json.loads(content)
        return {
            "category": result.get("category"),
            "tag": result.get("tag"),
            "confidence_score": float(result.get("confidence_score", 0.8)),
        }
    except Exception:
        return {"category": None, "tag": None, "confidence_score": 0.0}
