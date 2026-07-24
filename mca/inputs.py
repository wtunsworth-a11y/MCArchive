"""Input classification and normalisation for a mixed document archive.

The archive contains far more than scanned PDFs — Office documents, photos,
scanned images, videos and Windows junk files. This module decides how each
file should be treated and converts scanned images into PDFs so they can go
through the same OCR pipeline.
"""

from __future__ import annotations

from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif", ".webp"}
PDF_EXTS = {".pdf"}
OFFICE_EXTS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".odt",
               ".ods", ".odp", ".rtf", ".txt", ".csv"}
MEDIA_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".mp3",
              ".wav", ".m4a", ".aac", ".ogg"}

# Windows/macOS/Office cruft that should never be archived.
JUNK_NAMES = {"thumbs.db", ".ds_store", "desktop.ini"}
JUNK_EXTS = {".tmp", ".ini"}


def classify(name: str) -> str:
    """Return how a file should be handled:

    ``"ocr"``        — scanned PDF or document image → full OCR pipeline
    ``"pdf-tag"``    — a PDF (may already have text) → OCR-skip-text + tag
    ``"office"``     — Office/text document → index text in place
    ``"media"``      — photo/video/audio → catalogue by name only
    ``"junk"``       — skip entirely
    ``"other"``      — unknown type → catalogue by name only
    """
    base = name.lower()
    ext = Path(base).suffix
    if base in JUNK_NAMES or ext in JUNK_EXTS or base.startswith("~$"):
        return "junk"
    if ext in PDF_EXTS:
        return "pdf-tag"
    if ext in IMAGE_EXTS:
        return "ocr"
    if ext in OFFICE_EXTS:
        return "office"
    if ext in MEDIA_EXTS:
        return "media"
    return "other"


def is_image(name: str) -> bool:
    return Path(name.lower()).suffix in IMAGE_EXTS


def image_to_pdf(src: Path, dst_pdf: Path) -> Path:
    """Wrap a raster image (jpg/png/bmp/tiff/…) into a single-page PDF.

    Uses PyMuPDF so odd formats like BMP are handled uniformly. The result is
    a normal image-only PDF ready for the OCR pipeline.
    """
    import fitz  # PyMuPDF

    dst_pdf.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(src) as img:
        pdf_bytes = img.convert_to_pdf()
    with fitz.open("pdf", pdf_bytes) as pdf:
        pdf.save(dst_pdf)
    return dst_pdf
