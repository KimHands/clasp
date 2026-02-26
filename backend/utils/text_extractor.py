import os
from typing import Optional


def extract_text(file_path: str) -> Optional[str]:
    """
    파일 확장자에 따라 텍스트 추출 전략 선택
    - PDF: 1~2페이지 스킵 후 4구간 샘플링 (30/45/65/85%)
    - DOCX: 단락 기반 추출
    - TXT/MD: 전체 읽기 (최대 5000자)
    """
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            return _extract_pdf(file_path)
        elif ext == ".docx":
            return _extract_docx(file_path)
        elif ext in (".txt", ".md"):
            return _extract_plain(file_path)
    except Exception:
        return None
    return None


def _extract_pdf(file_path: str) -> Optional[str]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    doc = None
    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)

        if total_pages == 0:
            return None

        # 3페이지 이상인 경우 1~2페이지(표지/목차) 스킵
        start_page = 2 if total_pages >= 3 else 0
        effective_pages = list(range(start_page, total_pages))

        if not effective_pages:
            return None

        # 4구간 샘플링 위치 (30%, 45%, 65%, 85%)
        sample_ratios = [0.30, 0.45, 0.65, 0.85]
        n = len(effective_pages)
        sampled_indices = {effective_pages[min(int(r * n), n - 1)] for r in sample_ratios}

        chunks = []
        for page_idx in sorted(sampled_indices):
            page = doc[page_idx]
            text = page.get_text("text")
            if text:
                chunks.append(text[:300])

        return "\n".join(chunks) if chunks else None
    finally:
        if doc:
            doc.close()


def _extract_docx(file_path: str) -> Optional[str]:
    try:
        from docx import Document
    except ImportError:
        return None

    doc = Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)[:5000] if paragraphs else None


def _extract_plain(file_path: str) -> Optional[str]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(5000)
    except Exception:
        return None
