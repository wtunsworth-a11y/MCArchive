"""Auto-rotate, deskew and OCR a scanned PDF into a searchable PDF/A.

Wraps ocrmypdf. The primary pass uses ``--skip-text`` so pages that already
contain a text layer are left untouched (idempotent re-runs), while
image-only pages get rotated, deskewed and OCR'd. If that pass fails —
which happens on some malformed or mixed scans — we fall back to a
``--force-ocr`` pass that rasterises every page.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OcrResult:
    ok: bool
    mode: str = ""          # "skip-text" | "force-ocr"
    output_type: str = ""   # "pdfa" | "pdf"
    error: str = ""
    warnings: list[str] = field(default_factory=list)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ocr_pdf(
    src: Path,
    dst: Path,
    language: str = "eng",
    jobs: int = 2,
    rotate_threshold: float = 4.0,
) -> OcrResult:
    """Produce a rotated/deskewed, searchable version of ``src`` at ``dst``.

    ``rotate_threshold`` is the minimum tesseract OSD orientation confidence
    required before a page is auto-rotated. ocrmypdf's own default (15) is very
    conservative and misses genuine rotations on sparse pages; 4.0 catches real
    rotations while staying above OSD noise (upright pages report a rotation of
    0 and are never touched regardless of this value).
    """
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    base = [
        "ocrmypdf",
        "-l", language,
        "--rotate-pages",          # auto-detect & correct page orientation
        "--rotate-pages-threshold", str(rotate_threshold),
        "--deskew",                # straighten slightly-skewed scans
        "--jobs", str(jobs),
        "--quiet",
    ]

    # Primary: archival PDF/A, skip pages that already have real text.
    primary = base + ["--skip-text", "--output-type", "pdfa", str(src), str(dst)]
    proc = _run(primary)
    if proc.returncode == 0:
        return OcrResult(ok=True, mode="skip-text", output_type="pdfa",
                         warnings=_warnings(proc.stderr))

    # Fallback: force OCR on every page, plain PDF (more tolerant of odd input).
    fallback = base + ["--force-ocr", "--output-type", "pdf", str(src), str(dst)]
    proc2 = _run(fallback)
    if proc2.returncode == 0:
        return OcrResult(ok=True, mode="force-ocr", output_type="pdf",
                         warnings=_warnings(proc.stderr) + _warnings(proc2.stderr))

    return OcrResult(
        ok=False,
        error=(proc.stderr or "").strip() + "\n---\n" + (proc2.stderr or "").strip(),
    )


def detect_page_rotations(src: Path, threshold: float = 4.0, dpi: int = 200) -> list[int]:
    """Per-page rotation (degrees) tesseract OSD suggests, gated by ``threshold``.

    Returns a list, one entry per page, of 0/90/180/270. Used purely to report
    which documents had their orientation corrected — the actual rotation is
    performed by ocrmypdf during OCR.
    """
    import re

    import fitz  # PyMuPDF

    rotations: list[int] = []
    with fitz.open(src) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            tmp = Path(f"/tmp/_osd_{abs(hash(str(src))) % 99999}_{page.number}.png")
            pix.save(tmp)
            try:
                proc = _run(["tesseract", str(tmp), "-", "--psm", "0"])
            finally:
                tmp.unlink(missing_ok=True)
            rot, conf = 0, 0.0
            for line in (proc.stdout + proc.stderr).splitlines():
                if m := re.search(r"Rotate:\s*(\d+)", line):
                    rot = int(m.group(1))
                if m := re.search(r"Orientation confidence:\s*([\d.]+)", line):
                    conf = float(m.group(1))
            rotations.append(rot if (rot % 360 != 0 and conf >= threshold) else 0)
    return rotations


def _warnings(stderr: str) -> list[str]:
    if not stderr:
        return []
    return [ln.strip() for ln in stderr.splitlines()
            if "warning" in ln.lower() or "error" in ln.lower()]
