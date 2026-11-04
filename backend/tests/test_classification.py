import asyncio

import pytest

from engines import pipeline, tier1_rule
from engines.tier3_llm import LocalLlmConfig, Tier3Session, build_system_prompt
from models.schema import Rule


def _t1(db, filename):
    extension = "." + filename.rsplit(".", 1)[-1]
    return tier1_rule.run(file_path=filename, filename=filename, extension=extension, db=db)


@pytest.mark.parametrize("filename,category", [
    ("report_template.py", "코드"),
    ("paper_cup_order.xlsx", "스프레드시트"),
    ("발표_사진.jpg", "이미지"),
    ("meeting.mp3", "오디오"),
])
def test_format_extension_beats_filename_pattern(db, filename, category):
    assert _t1(db, filename)["category"] == category


@pytest.mark.parametrize("filename", ["wallpaper_collection.pdf", "newspaper.txt", "reporter.docx"])
def test_keyword_inside_a_word_does_not_match(db, filename):
    assert _t1(db, filename)["confidence_score"] == tier1_rule.CONTAINER_CONFIDENCE


@pytest.mark.parametrize("filename", ["final_report.pdf", "paper-v2.pdf", "회의록_0304.docx", "2026 논문.pdf"])
def test_filename_pattern_still_applies_to_general_formats(db, filename):
    assert _t1(db, filename)["confidence_score"] == 0.82


def test_general_format_is_weak_evidence(db):
    assert _t1(db, "scan_0412.pdf")["confidence_score"] < 0.6


def test_specific_format_is_strong_evidence(db):
    assert _t1(db, "budget.xlsx")["confidence_score"] == tier1_rule.FORMAT_CONFIDENCE


def test_user_rule_still_comes_first(db):
    db.add(Rule(priority=1, type="extension", value="py", folder_name="스크립트"))
    db.commit()
    assert _t1(db, "main.py")["category"] == "스크립트"


def _classify(db, monkeypatch, filename, t2_category, t2_score, tier3=None):
    monkeypatch.setattr(
        pipeline.tier2_embedding, "run",
        lambda text: {"category": t2_category, "tag": None, "confidence_score": t2_score, "embedding": None},
    )
    monkeypatch.setattr(pipeline, "infer_tag", lambda text, category: None)
    return asyncio.run(pipeline.classify(
        file_path=filename, filename=filename, extension="." + filename.rsplit(".", 1)[-1],
        extracted_text="본문", db=db, tier3=tier3,
    ))


def test_embedding_overrides_general_format(db, monkeypatch):
    result = _classify(db, monkeypatch, "scan.pdf", "프레젠테이션", 0.57)
    assert (result["category"], result["tier_used"]) == ("프레젠테이션", 2)


def test_weak_embedding_does_not_override(db, monkeypatch):
    result = _classify(db, monkeypatch, "scan.pdf", "프레젠테이션", 0.40)
    assert result["category"] == "문서"


def test_embedding_does_not_override_specific_format(db, monkeypatch):
    assert _classify(db, monkeypatch, "budget.xlsx", "문서", 0.60)["category"] == "스프레드시트"


@pytest.mark.parametrize("filename,t2_score", [("회의록.docx", 0.39), ("a.pdf", 0.45), ("budget.xlsx", 0.40)])
def test_agreement_never_lowers_confidence(db, monkeypatch, filename, t2_score):
    category = "스프레드시트" if filename.endswith("xlsx") else "문서"
    t1_score = _t1(db, filename)["confidence_score"]
    result = _classify(db, monkeypatch, filename, category, t2_score)
    assert result["confidence_score"] > t1_score


def test_agreement_stays_below_manual_confidence(db, monkeypatch):
    assert _classify(db, monkeypatch, "budget.xlsx", "스프레드시트", 0.99)["confidence_score"] < 1.0


def test_llm_is_not_asked_about_specific_formats(db, monkeypatch, fake_llm):
    session = Tier3Session(LocalLlmConfig(True, fake_llm.base_url, "m"), ["문서", "스프레드시트"])
    _classify(db, monkeypatch, "budget.xlsx", None, 0.1, tier3=session)
    assert fake_llm.requests == []


def test_llm_prompt_separates_topic_from_format():
    prompt = build_system_prompt(["문서", "코드"])
    code_line = next(line for line in prompt.split("\n") if line.startswith("- 코드"))
    assert "보안" not in code_line and "네트워크" not in code_line
    assert "주제와 상관없이" in prompt
