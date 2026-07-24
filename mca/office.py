"""Convert Office documents (Word/PowerPoint/Excel/…) to PDF via LibreOffice.

Runs ``soffice --headless --convert-to pdf`` in an isolated profile so it works
unattended in a container. The resulting PDF already has a real text layer, so
the OCR stage runs in ``--skip-text`` mode (no re-OCR) and simply tags it.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def soffice_bin() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def convert_to_pdf(src: Path, dst_pdf: Path, timeout: int = 180) -> tuple[bool, str]:
    """Convert ``src`` (any LibreOffice-readable doc) to ``dst_pdf``.

    Returns ``(ok, message)``.
    """
    src = Path(src)
    dst_pdf = Path(dst_pdf)
    dst_pdf.parent.mkdir(parents=True, exist_ok=True)

    binary = soffice_bin()
    if not binary:
        return False, "LibreOffice (soffice) not installed"

    with tempfile.TemporaryDirectory() as profile, tempfile.TemporaryDirectory() as outdir:
        cmd = [
            binary,
            "--headless", "--norestore", "--nolockcheck",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to", "pdf", "--outdir", outdir, str(src),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, f"conversion timed out after {timeout}s"

        produced = list(Path(outdir).glob("*.pdf"))
        if not produced:
            return False, (proc.stderr or proc.stdout or "no PDF produced").strip()[:400]
        shutil.move(str(produced[0]), str(dst_pdf))
        return True, "ok"
