"""Flag documents whose *file name* is misleading vs. their actual content.

Two cases are flagged (never auto-renamed — flagged for human review):

  * ``generic``  — an uninformative name like ``scan001``, ``IMG_1234``,
                   ``Document1``, ``untitled``, ``0007`` or a bare date.
  * ``mismatch`` — a name made of real words, none of which appear anywhere in
                   the document's own text/keywords.

In both cases a ``suggested`` title is derived from the document's content so a
reviewer can accept or edit it.
"""

from __future__ import annotations

import re
from pathlib import Path

from .text import STOPWORDS

_GENERIC_RE = re.compile(
    r"^(scan|scanned|img|image|imag|dsc|dscn|photo|pic|picture|doc|document|"
    r"file|untitled|new|copy|final|draft|page|pages|attachment|download|"
    r"screenshot|capture)[\s_\-]*\d*$",
    re.IGNORECASE,
)
_DATEISH_RE = re.compile(r"^\d{2,4}[\s_\-.]?\d{0,2}[\s_\-.]?\d{0,4}$")
_TOKEN_RE = re.compile(r"[A-Za-z]{3,}")

# Words that describe a document's *form/genre*, not its subject. A name made
# only of these is a fair descriptor even if the words never appear in the body,
# so it should not be flagged as a content mismatch.
_GENRE_WORDS = {
    "letter", "letters", "request", "requests", "reply", "response",
    "article", "articles", "report", "reports", "memo", "memorandum",
    "minutes", "submission", "submissions", "agreement", "mou", "note", "notes",
    "summary", "form", "forms", "application", "proposal", "plan", "plans",
    "presentation", "invoice", "receipt", "agenda", "draft", "final", "review",
    "correspondence", "doc", "document", "file", "scan", "scanned", "copy",
    "version", "page", "pages", "attachment", "signed", "updated", "revised",
    "notice", "circular", "bulletin", "statement", "meeting", "cover", "letterhead",
    "map", "maps", "photo", "photos", "picture", "pictures", "image", "images",
    "video", "videos", "pic", "pics", "img",
}


def _tokens(s: str) -> set[str]:
    return {w.lower() for w in _TOKEN_RE.findall(s) if w.lower() not in STOPWORDS}


def _title_case(words: list[str]) -> str:
    return " ".join(w.capitalize() for w in words)


def suggest_title(guessed_title: str, keywords: list[str], source_name: str) -> str:
    """Best-effort human-readable title from document content."""
    gt = (guessed_title or "").strip()
    # A good heading has a few words and isn't just the file name echoed back.
    if len(_tokens(gt)) >= 2 and gt.lower() != Path(source_name).stem.lower():
        return gt
    if keywords:
        return _title_case(keywords[:5])
    return gt or Path(source_name).stem


def check_title(
    source_name: str,
    content_text: str,
    keywords: list[str],
    guessed_title: str,
) -> dict:
    """Return ``{flag, reason, suggested, overlap}``. ``flag`` is '' if fine."""
    stem = Path(source_name).stem.strip()
    result = {"flag": "", "reason": "", "suggested": "", "overlap": None}

    # No usable content (e.g. a photo) → only a generic-name check is meaningful.
    has_content = bool(content_text and content_text.strip()) or bool(keywords)

    if _GENERIC_RE.match(stem) or _DATEISH_RE.match(stem) or len(stem.replace(" ", "")) < 4:
        result["flag"] = "generic"
        result["reason"] = "file name is generic / uninformative"
        result["suggested"] = suggest_title(guessed_title, keywords, source_name) if has_content else ""
        return result

    if not has_content:
        return result

    fn_tokens = _tokens(stem)
    # Judge the mismatch on *content* words only — drop generic genre words,
    # which describe the document type and need not appear in the body.
    fn_content = fn_tokens - _GENRE_WORDS
    if len(fn_content) < 2:
        return result  # name is genre-only or too short to judge reliably

    content_tokens = set(keywords) | _tokens(guessed_title) | _tokens(content_text[:1500])
    hit = fn_content & content_tokens
    overlap = len(hit) / len(fn_content)
    result["overlap"] = round(overlap, 2)

    if overlap == 0.0:
        result["flag"] = "mismatch"
        result["reason"] = "file name topic does not appear in the document"
        result["suggested"] = suggest_title(guessed_title, keywords, source_name)

    return result
