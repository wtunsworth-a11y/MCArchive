"""Text extraction, keyword tagging and lightweight metadata inference."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

# A compact English stop-word list — deliberately dependency-free (no NLTK).
STOPWORDS = set(
    """a about above after again against all am an and any are aren't as at be
    because been before being below between both but by can't cannot could
    couldn't did didn't do does doesn't doing don't down during each few for
    from further had hadn't has hasn't have haven't having he he'd he'll he's
    her here here's hers herself him himself his how how's i i'd i'll i'm i've
    if in into is isn't it it's its itself let's me more most mustn't my myself
    no nor not of off on once only or other ought our ours ourselves out over
    own same shan't she she'd she'll she's should shouldn't so some such than
    that that's the their theirs them themselves then there there's these they
    they'd they'll they're they've this those through to too under until up very
    was wasn't we we'd we'll we're we've were weren't what what's when when's
    where where's which while who who's whom why why's will with won't would
    wouldn't you you'd you'll you're you've your yours yourself yourselves
    also may per via etc such upon shall""".split()
)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]{2,}")

# Common date formats found in documents.
_DATE_RES = [
    re.compile(r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b"),
    re.compile(
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\.?\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
]


def extract_text(pdf_path: Path) -> str:
    """Concatenated text of every page (the OCR layer for scanned PDFs)."""
    parts = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n".join(parts)


def page_count(pdf_path: Path) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def extract_keywords(text: str, top_n: int = 12) -> list[str]:
    words = [w.lower().strip("'-") for w in _WORD_RE.findall(text)]
    words = [w for w in words if len(w) > 2 and w not in STOPWORDS and not w.isdigit()]
    counts = Counter(words)
    return [w for w, _ in counts.most_common(top_n)]


def guess_title(text: str, fallback: str) -> str:
    """First substantive line of the document, else the file name."""
    for raw in text.splitlines():
        line = raw.strip()
        letters = sum(c.isalpha() for c in line)
        if len(line) >= 4 and letters >= 3 and letters >= len(line) * 0.4:
            return re.sub(r"\s+", " ", line)[:120]
    return Path(fallback).stem


def extract_dates(text: str, limit: int = 5) -> list[str]:
    found: list[str] = []
    for rx in _DATE_RES:
        for m in rx.findall(text):
            if m not in found:
                found.append(m)
    return found[:limit]


def snippet(text: str, length: int = 300) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:length]
