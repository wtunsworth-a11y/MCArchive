"""Auto-rotate, deskew and OCR a PDF into a searchable PDF/A.

Two paths, chosen by whether the input already has a real text layer:

* **Scanned** (image-only, no text) — each page is pre-rotated to the upright
  orientation using tesseract OSD (applied by us, because ocrmypdf's own
  ``--rotate-pages`` OCRs *before* rotating in this version and yields
  upside-down gibberish), then ``--force-ocr`` rasterises and OCRs it.
* **Digital / Office-converted** (already has text) — ``--skip-text`` keeps the
  existing text and only OCRs any image-only pages; nothing is re-rasterised.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

_TEXT_THRESHOLD = 100  # chars of extractable text ⇒ treat as a digital PDF


@dataclass
class OcrResult:
    ok: bool
    mode: str = ""            # "scanned" | "digital"
    output_type: str = ""     # "pdfa" | "pdf"
    rotations: list[int] = field(default_factory=list)
    rotated: bool = False
    error: str = ""


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _text_length(pdf: Path) -> int:
    with fitz.open(pdf) as doc:
        return sum(len(page.get_text().strip()) for page in doc)


def _osd_rotation(png: Path, threshold: float) -> int:
    proc = _run(["tesseract", str(png), "-", "--psm", "0"])
    out = proc.stdout + proc.stderr
    rot = conf = 0.0
    if m := re.search(r"Rotate:\s*(\d+)", out):
        rot = int(m.group(1))
    if m := re.search(r"Orientation confidence:\s*([\d.]+)", out):
        conf = float(m.group(1))
    return int(rot) if (rot % 360 != 0 and conf >= threshold) else 0


def prerotate(src: Path, dst: Path, threshold: float = 4.0, dpi: int = 200) -> list[int]:
    """Rotate each page to upright per tesseract OSD; write to ``dst``.

    Returns the per-page rotation actually applied (0/90/180/270).
    """
    rotations: list[int] = []
    tmp = Path(tempfile.gettempdir())
    with fitz.open(src) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            p = tmp / f"_osd_{abs(hash(str(src)))%99999}_{page.number}.png"
            pix.save(p)
            try:
                rot = _osd_rotation(p, threshold)
            finally:
                p.unlink(missing_ok=True)
            if rot:
                page.set_rotation((page.rotation + rot) % 360)
            rotations.append(rot)
        doc.save(dst)
    return rotations


def ocr_pdf(
    src: Path,
    dst: Path,
    language: str = "eng",
    jobs: int = 2,
    rotate_threshold: float = 4.0,
) -> OcrResult:
    """Produce a rotated/deskewed, searchable version of ``src`` at ``dst``."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    digital = _text_length(src) > _TEXT_THRESHOLD

    base = ["ocrmypdf", "-l", language, "--jobs", str(jobs), "--quiet"]

    with tempfile.TemporaryDirectory() as td:
        if digital:
            working, rotations = src, []
            variant = ["--skip-text"]
        else:
            working = Path(td) / "prerot.pdf"
            rotations = prerotate(src, working, threshold=rotate_threshold)
            variant = ["--deskew", "--force-ocr"]

        # Primary attempt: archival PDF/A.
        proc = _run(base + variant + ["--output-type", "pdfa", str(working), str(dst)])
        if proc.returncode == 0:
            return OcrResult(True, "digital" if digital else "scanned", "pdfa",
                             rotations, any(r % 360 for r in rotations))

        # Fallback: plain PDF (more tolerant of odd input).
        proc2 = _run(base + variant + ["--output-type", "pdf", str(working), str(dst)])
        if proc2.returncode == 0:
            return OcrResult(True, "digital" if digital else "scanned", "pdf",
                             rotations, any(r % 360 for r in rotations))

        return OcrResult(False, error=((proc.stderr or "") + "\n---\n" + (proc2.stderr or "")).strip())
