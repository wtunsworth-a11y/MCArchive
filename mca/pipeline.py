"""End-to-end processing of a mixed document archive on the local filesystem.

Walks a folder tree (mirroring subfolders), and per file:

  * PDF                    → rotate/deskew + OCR (skip pages with text) → PDF/A, tag
  * scanned image          → wrap to PDF → rotate/OCR → PDF/A, tag
  * Office doc (Word/…)    → convert to PDF (LibreOffice) → OCR-skip-text, tag
  * photo / video / audio  → catalogued (listed, not converted)
  * junk (Thumbs.db, …)    → skipped

Across the set it flags exact and near-duplicate documents (never deletes) and
emits ``manifest.json``, a searchable ``index.html`` and — for every image/map —
an ``image_tagging.html`` sheet for capturing event/people metadata by hand.

Google Drive I/O is handled by the caller; this module is pure local processing.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import dedup, index, inputs, metadata, ocr, office, tagger, text, titles


@dataclass
class DocRecord:
    id: str                       # relative path from the input root (stable id)
    source_name: str
    rel_folder: str
    file_type: str                # lower-case extension without dot
    action: str                   # ocr | office2pdf | pdf | catalogued
    output_name: str = ""
    sha256: str = ""
    ok: bool = True
    error: str = ""
    ocr_mode: str = ""
    output_type: str = ""
    rotated: bool = False
    rotations: list[int] = field(default_factory=list)
    pages: int = 0
    title: str = ""
    keywords: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    snippet: str = ""
    text: str = ""
    size_bytes: int = 0
    is_image: bool = False
    title_flag: str = ""          # "" | generic | mismatch
    title_reason: str = ""
    title_suggested: str = ""
    duplicate_group: int | None = None
    duplicate_kind: str = ""
    duplicate_matches: list[str] = field(default_factory=list)
    url: str = ""                 # Drive view URL, filled in by the orchestrator
    drive_id: str = ""            # Drive file id, filled in by the orchestrator

    def public_dict(self) -> dict:
        return dict(self.__dict__)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def process_folder(
    input_dir: str | Path,
    output_dir: str | Path,
    language: str = "eng",
    jobs: int = 2,
    rotate_threshold: float = 4.0,
    ocr_images: bool = True,
    folder_name: str = "MCA Document Archive",
    log=print,
) -> list[DocRecord]:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in input_dir.rglob("*") if p.is_file())
    records: list[DocRecord] = []
    n = len(files)

    for i, src in enumerate(files, 1):
        rel = src.relative_to(input_dir)
        kind = inputs.classify(src.name)
        if kind == "junk":
            log(f"[{i}/{n}] skip junk: {rel}")
            continue

        rec = DocRecord(
            id=str(rel),
            source_name=src.name,
            rel_folder=str(rel.parent) if str(rel.parent) != "." else "",
            file_type=src.suffix.lower().lstrip("."),
            action=kind,
            sha256=_sha256(src),
            size_bytes=src.stat().st_size,
            is_image=inputs.is_image(src.name),
        )
        log(f"[{i}/{n}] {rel}  ({kind})")

        try:
            if kind in ("pdf-tag", "ocr", "office"):
                _process_to_searchable_pdf(src, rel, output_dir, rec,
                                           language, jobs, rotate_threshold,
                                           ocr_images, log)
            else:  # media / other → catalogue only
                rec.action = "catalogued"
                rec.title = src.stem
        except Exception as e:  # never let one file kill the batch
            rec.ok = False
            rec.error = f"{type(e).__name__}: {e}"
            log(f"    ! failed: {rec.error}")

        records.append(rec)

    _flag_duplicates(records, log)
    write_outputs(records, output_dir, folder_name)
    return records


def _process_to_searchable_pdf(src, rel, output_dir, rec, language, jobs,
                               rotate_threshold, ocr_images, log):
    """Normalise input to a PDF, OCR/tag it, and record extracted text."""
    out_rel = rel.with_suffix(".pdf")
    out_path = output_dir / out_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rec.output_name = out_rel.name

    with tempfile.TemporaryDirectory() as td:
        pdf_src = Path(src)

        if rec.action == "office":
            conv = Path(td) / (Path(src).stem + ".pdf")
            ok, msg = office.convert_to_pdf(src, conv)
            if not ok:
                rec.ok = False
                rec.error = f"office conversion failed: {msg}"
                log(f"    ! {rec.error}")
                return
            pdf_src = conv
        elif rec.action == "ocr" and rec.is_image:
            if not ocr_images:
                rec.action = "catalogued"
                rec.title = Path(src).stem
                return
            pdf_src = inputs.image_to_pdf(src, Path(td) / "img.pdf")

        # rotation detection (reporting only) then OCR
        try:
            rec.rotations = ocr.detect_page_rotations(pdf_src, threshold=rotate_threshold)
            rec.rotated = any(r % 360 != 0 for r in rec.rotations)
        except Exception:
            rec.rotations = []

        res = ocr.ocr_pdf(pdf_src, out_path, language=language, jobs=jobs,
                          rotate_threshold=rotate_threshold)
        if not res.ok:
            rec.ok = False
            rec.error = res.error
            log(f"    ! OCR failed: {(res.error or 'unknown').splitlines()[-1]}")
            return
        rec.ocr_mode = res.mode
        rec.output_type = res.output_type

    body = text.extract_text(out_path)
    rec.pages = text.page_count(out_path)
    rec.keywords = text.extract_keywords(body)
    rec.title = text.guess_title(body, rec.source_name)
    rec.dates = text.extract_dates(body)
    rec.snippet = text.snippet(body)
    rec.text = body
    rec.size_bytes = out_path.stat().st_size

    tc = titles.check_title(rec.source_name, body, rec.keywords, rec.title)
    rec.title_flag = tc["flag"]
    rec.title_reason = tc["reason"]
    rec.title_suggested = tc["suggested"]
    if tc["flag"]:
        log(f"    ⚠ title check: {tc['reason']}"
            + (f" → suggested: {tc['suggested']}" if tc["suggested"] else ""))

    try:
        metadata.apply_metadata(out_path, rec.title, rec.keywords,
                                subject=text.snippet(body, 200))
    except Exception as e:
        log(f"    ~ metadata embed skipped: {e}")

    rot = f", rotated {[r for r in rec.rotations if r]}" if rec.rotated else ""
    extra = " (from office)" if rec.action == "office" else (" (from image)" if rec.is_image else "")
    log(f"    ok ({rec.pages}pp, {res.mode}{rot}){extra} keywords: {', '.join(rec.keywords[:6])}")


def _flag_duplicates(records: list[DocRecord], log=print) -> None:
    # Only documents with real text participate in near-duplicate matching.
    cand = [r for r in records if r.ok and r.text.strip()]
    dup_docs = [dedup.DupDoc(id=r.id, sha256=r.sha256, text=r.text) for r in cand]
    flags = dedup.find_duplicates(dup_docs)
    n_flagged = 0
    for r in cand:
        f = flags.get(r.id, {})
        r.duplicate_group = f.get("group")
        r.duplicate_kind = f.get("kind", "")
        r.duplicate_matches = f.get("matches", [])
        if r.duplicate_group:
            n_flagged += 1
    if n_flagged:
        log(f"Flagged {n_flagged} document(s) as possible duplicates (not deleted).")


def write_outputs(records: list[DocRecord], output_dir: Path, folder_name: str) -> None:
    output_dir = Path(output_dir)
    docs = [r.public_dict() for r in records]
    manifest = {"folder": folder_name, "count": len(records), "documents": docs}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    (output_dir / "index.html").write_text(
        index.build_index([r.public_dict() for r in records if r.ok], folder_name),
        encoding="utf-8")

    images = [
        {"id": r.drive_id or r.id, "name": r.source_name,
         "folder": r.rel_folder, "view_url": r.url}
        for r in records if r.is_image and r.ok
    ]
    if images:
        (output_dir / "image_tagging.html").write_text(
            tagger.build_tagger(images, folder_name), encoding="utf-8")
