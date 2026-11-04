"""
분류 평가 실행.
  python -m eval.run --split tune
  python -m eval.run --split holdout --min-accuracy 0.8
  python -m eval.run --llm-url http://127.0.0.1:1234/v1 --llm-model <모델>
  python -m eval.run --output result.json
"""
import argparse
import asyncio
import csv
import json
import logging
import os
import sys
import tempfile

logging.disable(logging.WARNING)
os.environ["HOME"] = os.environ["USERPROFILE"] = tempfile.mkdtemp(prefix="clasp-eval-home-")

import fitz
from docx import Document
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from engines import pipeline
from engines.tier3_llm import LocalLlmConfig, Tier3Session
from eval.dataset import ITEMS
from models.schema import Base
from utils.cover_detector import extract_cover_text
from utils.text_extractor import extract_text

UNCLASSIFIED_THRESHOLD = pipeline.UNCLASSIFIED_THRESHOLD
HIGH_CONFIDENCE = 0.7
BASE_CATEGORIES = ["문서", "프레젠테이션", "스프레드시트", "코드", "데이터"]


def _write_pdf(path, text):
    doc = fitz.open()
    remaining = text
    while remaining:
        page = doc.new_page()
        chunk, remaining = remaining[:1500], remaining[1500:]
        page.insert_textbox(fitz.Rect(40, 40, 555, 800), chunk, fontname="korea", fontsize=11)
    doc.save(path)
    doc.close()


def _write_docx(path, text):
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(path)


def _write_xlsx(path, rows):
    book = Workbook()
    for row in rows:
        book.active.append(row)
    book.save(path)


def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def _write_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


WRITERS = {
    "pdf": _write_pdf, "docx": _write_docx, "xlsx": _write_xlsx, "csv": _write_csv,
    "txt": _write_text, "md": _write_text, "bin": _write_bytes,
}


async def _classify_all(items, folder, db, tier3):
    results = []
    for item in items:
        path = os.path.join(folder, item.name)
        WRITERS[item.kind](path, item.content)
        result = await pipeline.classify(
            file_path=path,
            filename=item.name,
            extension=os.path.splitext(item.name)[1].lower(),
            extracted_text=extract_text(path),
            cover_text=extract_cover_text(path),
            db=db,
            tier3=tier3,
        )
        below_threshold = result["confidence_score"] < UNCLASSIFIED_THRESHOLD
        predicted = None if below_threshold else result["category"]
        results.append({
            "name": item.name,
            "split": item.split,
            "expected": item.expected,
            "predicted": predicted,
            "tier": result["tier_used"],
            "confidence": round(result["confidence_score"], 3),
            "correct": predicted == item.expected,
        })
    return results


def summarize(results):
    total = len(results)
    correct = sum(r["correct"] for r in results)
    confident = [r for r in results if r["confidence"] >= HIGH_CONFIDENCE]
    by_tier = {}
    for r in results:
        by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + 1
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else 0.0,
        "confident_wrong": sum(not r["correct"] for r in confident),
        "confident": len(confident),
        "by_tier": by_tier,
        "errors": [
            f"{r['name']}: 기대 {r['expected']}, 결과 {r['predicted']} (T{r['tier']}, {r['confidence']})"
            for r in results if not r["correct"]
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["tune", "holdout", "all"], default="tune")
    parser.add_argument("--min-accuracy", type=float, default=None)
    parser.add_argument("--llm-url", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    items = [i for i in ITEMS if args.split == "all" or i.split == args.split]
    tier3 = None
    if args.llm_url:
        tier3 = Tier3Session(LocalLlmConfig(True, args.llm_url, args.llm_model), BASE_CATEGORIES)

    # Tier 1 runs in a worker thread, so every thread must share one in-memory connection
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    with tempfile.TemporaryDirectory(prefix="clasp-eval-") as folder:
        results = asyncio.run(_classify_all(items, folder, db, tier3))

    summary = summarize(results)
    text = json.dumps({"split": args.split, "llm_model": args.llm_model, **summary}, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    if args.min_accuracy is not None and summary["accuracy"] < args.min_accuracy:
        sys.exit(1)


if __name__ == "__main__":
    main()
