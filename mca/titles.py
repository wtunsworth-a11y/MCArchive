"""Flag inadequate document titles and suggest better, descriptive ones.

Three cases are flagged (never auto-renamed — flagged for human review):

  * ``generic``      — an uninformative name like ``scan001``, ``IMG_1234``,
                       ``Document1``, ``untitled`` or a bare date.
  * ``mismatch``     — a name made of real words, none of which appear anywhere
                       in the document's own text.
  * ``insufficient`` — a name that states only the document *type* (``request
                       letter``, ``MoA``, ``minutes``) without saying what it is
                       about or who it involves.

For each, ``compose_title`` builds a descriptive "what + who" suggestion from the
content — document type, the parties/sender, the subject, and a year — for a
reviewer to accept or edit. It is a heuristic first draft, not a final title.
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


# ── descriptive-title composition ───────────────────────────────────────────
# Pull the pieces a good archive title needs — document type, the parties/sender,
# the subject, and a year — out of the document's own text and assemble them.

_ORG_TAIL = (r"Government|Provincial Government|Group|Limited|Ltd|Incorporated|Inc|"
             r"Association|Company|Ministry|Department|Office|Council|Committee|"
             r"Board|Foundation|Trust|Authority|Unit|Agency|Corporation|"
             r"Cooperative|Society|Church|Province|District|LLG|ILG|NGO|Secretariat")
_ORG_RE = re.compile(
    r"\b([A-Z][A-Za-z&.'\-]+(?:\s+[A-Z][A-Za-z&.'\-]+){0,5}\s+(?:" + _ORG_TAIL + r"))\b")
_SUBJECT_RE = re.compile(r"(?im)^\s*(?:re|ref|reference|subject)\s*[:\-]\s*(.+)$")
_BETWEEN_RE = re.compile(
    r"(?is)\bbetween\s+(.+?)\s+and\s+(.+?)(?=[\.\n;,]|\s+(?:to|for|on|regarding|"
    r"hereby|whereas|dated))")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_ACTION_RE = re.compile(
    r"(?is)\b(?:agree(?:d|s)?\s+to|hereby\s+agree\s+to|to\s+establish|"
    r"endorse(?:s|d)?|support(?:s|ed)?|request(?:s|ed|ing)?\s+(?:for|that|the)?|"
    r"recognis(?:e|ing|es)|approv(?:e|ing|es|ed))\s+(.+?)(?=[\.\n;]|$)")


_TYPE_LEAD = {"memorandum", "agreement", "understanding", "minutes", "letter",
              "memo", "report", "invoice", "submission", "proposal", "notice",
              "circular", "of", "the", "for", "a", "an", "and"}


def _clean(s: str, limit: int = 80) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip(" .,:;-—"))
    if len(s) > limit:  # trim at a word boundary, not mid-word
        s = s[:limit].rsplit(" ", 1)[0]
    return s.strip(" .,:;-—")


def _norm(s: str) -> str:
    """Title-case ALL-CAPS words (common on scanned headers), leave the rest."""
    s = _clean(s, 120)

    small = {"of", "the", "and", "for", "to", "in", "on", "at", "a", "an", "by"}

    def fix(w: str) -> str:
        letters = [c for c in w if c.isalpha()]
        if w.lower() in small:                       # function words → lowercase
            return w.lower()
        # Title-case long ALL-CAPS words (OFFICE, PREMIER) but keep short
        # all-caps tokens as acronyms (PNG, LLG, MCA, ILG, NEC).
        if len(letters) >= 5 and all(c.isupper() for c in letters):
            return w.capitalize()
        return w

    return " ".join(fix(w) for w in s.split())


def _strip_type(s: str) -> str:
    """Drop leading document-type / filler words from a phrase."""
    words = s.split()
    while words and re.sub(r"[^a-z]", "", words[0].lower()) in _TYPE_LEAD:
        words.pop(0)
    return " ".join(words).strip()


def _first_heading(text: str) -> str:
    """First substantive heading line (past the document-type word)."""
    for line in text.splitlines():
        core = _strip_type(_norm(line))
        if len(_tokens(core)) >= 2:
            return _clean(core, 90)
    return ""


def _doc_type(text: str) -> str:
    t = text.lower()
    if re.search(r"memorandum of agreement|memorandum of understanding|\bmo[ua]\b", t):
        return "agreement"
    if re.search(r"\bminutes\b", t):
        return "minutes"
    if re.search(r"dear\s+\w|yours\s+(faithfully|sincerely|truly)|we\s+write|we\s+are\s+writing", t):
        return "letter"
    if re.search(r"\bnews\b|\bthe national\b|\bpost.?courier\b|reporter|by\s+staff", t):
        return "article"
    if re.search(r"annual report|program report|progress report|\breport\b", t):
        return "report"
    if "invoice" in t:
        return "invoice"
    if re.search(r"submission|proposal", t):
        return "submission"
    return "document"


def _orgs(text: str, limit: int = 3) -> list[str]:
    seen: list[str] = []
    for m in _ORG_RE.finditer(text[:2500]):
        name = _strip_type(_norm(m.group(1)))
        name = re.sub(r"^(the)\s+", "", name, flags=re.I)
        if name and name not in seen and len(name) > 4:
            seen.append(name)
        if len(seen) >= limit:
            break
    return seen


def _party(s: str) -> str:
    return re.sub(r"^(the)\s+", "", _strip_type(_norm(s)), flags=re.I)


def compose_title(text: str, keywords: list[str], fallback: str = "") -> str:
    """Build a descriptive 'what + who' title from the document's content."""
    text = text or ""
    typ = _doc_type(text)
    orgs = _orgs(text)
    year_m = _YEAR_RE.search(text)
    year = year_m.group(0) if year_m else ""

    subject = ""
    ms = _SUBJECT_RE.search(text)
    if ms:
        subject = _norm(ms.group(1))
    if not subject:
        ma = _ACTION_RE.search(text)
        if ma:
            subject = _norm(ma.group(1))

    parts: list[str] = []
    if typ == "agreement":
        mb = _BETWEEN_RE.search(text)
        if mb:
            parties = f"between {_party(mb.group(1))} and {_party(mb.group(2))}"
        elif len(orgs) >= 2:
            parties = f"between {orgs[0]} and {orgs[1]}"
        elif orgs:
            parties = f"({orgs[0]})"
        else:
            parties = ""
        mp = re.search(
            r"(?is)\bto\s+(establish|develop|create|manage|protect|implement|"
            r"provide|support|deliver|formalis|conserv)\w*\s+(.+?)(?=[\.\n;]|$)", text)
        if mp:
            purpose = _norm(f"{mp.group(1).lower()} {mp.group(2)}")
        else:
            purpose = subject or _first_heading(text)
        parts = ["Memorandum of Agreement", parties,
                 (f"to {purpose}" if purpose else "")]
    elif typ == "letter":
        frm = f"from {orgs[0]}" if orgs else ""
        re_ = subject or _first_heading(text)
        parts = ["Letter", frm, (f"re: {re_}" if re_ else "")]
    elif typ == "minutes":
        org = orgs[0] if orgs else _first_heading(text)
        parts = ["Minutes of", org]
    elif typ == "article":
        parts = ["News article:", subject or _first_heading(text)]
    else:  # report / submission / invoice / document
        label = {"report": "Report", "submission": "Submission",
                 "invoice": "Invoice"}.get(typ, "")
        head = subject or _first_heading(text)
        lead = f"{label}:" if (label and head) else label
        tail = orgs[0] if (orgs and orgs[0] not in head) else ""
        parts = [lead, head, (f"({tail})" if tail else "")]

    title = re.sub(r"\s{2,}", " ", " ".join(p for p in parts if p).strip())
    title = _clean(title, 130).rstrip(" .,:;-—")           # trim body at a word
    if len(_tokens(title) - _GENRE_WORDS) < 1:             # too thin — fall back
        return _title_case(keywords[:5]) if keywords else (_norm(fallback) or "")
    if year and year not in title:                         # append year last
        title = f"{title} ({year})"
    return title


def suggest_title(content_text: str, keywords: list[str], guessed_title: str) -> str:
    """A descriptive 'what + who' title derived from the document content."""
    return compose_title(content_text, keywords, fallback=guessed_title)


def _is_specific(title: str) -> bool:
    """A title is specific if it names a subject or party beyond its genre word."""
    return len(_tokens(title) - _GENRE_WORDS) >= 1


def check_title(
    source_name: str,
    content_text: str,
    keywords: list[str],
    guessed_title: str,
) -> dict:
    """Return ``{flag, reason, suggested, overlap}``. ``flag`` is '' if adequate.

    Flags: ``generic`` (uninformative name), ``mismatch`` (name's topic absent
    from the content), ``insufficient`` (name is only a document-type/genre word
    and does not say *what* the document is about or *who* it involves).
    """
    stem = Path(source_name).stem.strip()
    result = {"flag": "", "reason": "", "suggested": "", "overlap": None}
    has_content = bool(content_text and content_text.strip()) or bool(keywords)
    suggestion = suggest_title(content_text, keywords, guessed_title) if has_content else ""

    # 1) Generic / junk names.
    if _GENERIC_RE.match(stem) or _DATEISH_RE.match(stem) or len(stem.replace(" ", "")) < 4:
        result.update(flag="generic",
                      reason="file name is generic / uninformative",
                      suggested=suggestion)
        return result

    if not has_content:
        return result  # e.g. a photo with no text — nothing more to judge

    fn_tokens = _tokens(stem)
    fn_content = fn_tokens - _GENRE_WORDS

    # 2) Content mismatch — the name's own topic words appear nowhere.
    if len(fn_content) >= 2:
        content_tokens = set(keywords) | _tokens(guessed_title) | _tokens(content_text[:1500])
        overlap = len(fn_content & content_tokens) / len(fn_content)
        result["overlap"] = round(overlap, 2)
        if overlap == 0.0:
            result.update(flag="mismatch",
                          reason="file name topic does not appear in the document",
                          suggested=suggestion)
            return result

    # 3) Insufficient — the name is only a document type (no subject / party).
    #    e.g. "request letter", "MoA", "meeting minutes", "final report".
    if not fn_content and _is_specific(suggestion) and suggestion.lower() != stem.lower():
        result.update(flag="insufficient",
                      reason="name states the document type but not its subject or parties",
                      suggested=suggestion)

    return result
