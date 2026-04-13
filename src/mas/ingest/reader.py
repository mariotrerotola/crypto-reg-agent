"""Whitepaper text extraction from various file formats.

Supports plain text, Markdown, and PDF (via pymupdf if installed).
"""

from __future__ import annotations

from pathlib import Path


class ExtractionError(Exception):
    """Raised when text extraction fails."""


def read_document(path: Path) -> str:
    """Extract text content from a file.

    Supported formats:
        - ``.txt`` / ``.md``: read as UTF-8 text
        - ``.pdf``: extract via pymupdf (requires ``mas[ingest]``)

    Args:
        path: Path to the document file.

    Returns:
        Extracted text content.

    Raises:
        ExtractionError: If the file format is unsupported or extraction fails.
        FileNotFoundError: If the file does not exist.
    """
    if not path.exists():
        msg = f"File not found: {path}"
        raise FileNotFoundError(msg)

    suffix = path.suffix.lower()

    if suffix in {".txt", ".md", ".markdown"}:
        return _read_text(path)
    if suffix == ".pdf":
        return _read_pdf(path)

    msg = f"Unsupported file format: {suffix}. Supported: .txt, .md, .pdf"
    raise ExtractionError(msg)


def read_text(text: str) -> str:
    """Pass-through for already-extracted text (e.g. pasted in UI).

    Strips leading/trailing whitespace and validates non-empty.
    """
    cleaned = text.strip()
    if not cleaned:
        msg = "Input text is empty."
        raise ExtractionError(msg)
    return cleaned


def _read_text(path: Path) -> str:
    """Read a plain text or Markdown file."""
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        msg = f"File is empty: {path}"
        raise ExtractionError(msg)
    return content


def _read_pdf(path: Path) -> str:
    """Extract text from a PDF file using pymupdf."""
    try:
        import pymupdf  # type: ignore[import-untyped]
    except ImportError:
        msg = "PDF support requires pymupdf. Install with: uv pip install 'mas[ingest]'"
        raise ExtractionError(msg) from None

    try:
        doc = pymupdf.open(str(path))
        pages: list[str] = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text)
        doc.close()
    except Exception as e:
        msg = f"Failed to extract text from PDF: {e}"
        raise ExtractionError(msg) from e

    if not pages:
        msg = f"No text content found in PDF: {path}"
        raise ExtractionError(msg)

    return "\n\n".join(pages)
