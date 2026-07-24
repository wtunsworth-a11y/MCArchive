"""Embed inferred metadata (title, keywords, subject) into a PDF.

Uses pikepdf (bundled with ocrmypdf) so both the classic ``/Info`` dictionary
and the XMP packet are updated, keeping PDF/A files consistent.
"""

from __future__ import annotations

from pathlib import Path

import pikepdf


def apply_metadata(
    path: Path,
    title: str,
    keywords: list[str],
    subject: str = "",
    author: str = "MCA Document Archive",
) -> None:
    kw = ", ".join(keywords)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with pdf.open_metadata() as meta:
            if title:
                meta["dc:title"] = title
            if subject:
                meta["dc:description"] = subject
            if kw:
                meta["pdf:Keywords"] = kw
            if author:
                meta["dc:creator"] = [author]
        info = pdf.docinfo
        if title:
            info["/Title"] = title
        if kw:
            info["/Keywords"] = kw
        if subject:
            info["/Subject"] = subject
        if author:
            info["/Author"] = author
        pdf.save(path)
