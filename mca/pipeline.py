"""End-to-end processing of a local folder of scanned PDFs.

For each PDF: auto-rotate + deskew + OCR (searchable PDF/A), infer a title,
keywords and dates, embed them as PDF metadata. Across the set: flag exact and
near-duplicate documents. Emit ``manifest.json`` and a searchable
``index.html``.

Google Drive I/O is handled by the caller (the orchestrator downloads sources
into ``input_dir`` and uploads ``output_dir`` back); this module is pure local
processing so it is easy to test and re-run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import dedup, index, metadata, ocr, text


@dataclass
class DocRecord:
    id: str
    source_name: str
    output_name: str
    sha256: str
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
    duplicate_group: int | None = None
    duplicate_kind: str = ""
    duplicate_matches: list[str] = field(default_factory=list)

    def public_dict(self) -> dict:
        d = self.__dict__.copy()
        d["url"] = ""  # filled in by the orchestrator after Drive upload
        return d


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
    folder_name: str = "MCA Document Archive",
    log=print,
) -> list[DocRecord]:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(p for p in input_dir.iterdir() if p.suffix.lower() == ".pdf")
    records: list[DocRecord] = []

    for i, src in enumerate(pdfs, 1):
        out_name = src.name
        out_path = output_dir / out_name
        log(f"[{i}/{len(pdfs)}] {src.name}")
        rec = DocRecord(
            id=src.stem,
            source_name=src.name,
            output_name=out_name,
            sha256=_sha256(src),
            size_bytes=src.stat().st_size,
        )

        try:
            rec.rotations = ocr.detect_page_rotations(src, threshold=rotate_threshold)
            rec.rotated = any(r % 360 != 0 for r in rec.rotations)
        except Exception:
            rec.rotations = []

        res = ocr.ocr_pdf(src, out_path, language=language, jobs=jobs,
                          rotate_threshold=rotate_threshold)
        if not res.ok:
            rec.ok = False
            rec.error = res.error
            log(f"    ! OCR failed: {res.error.splitlines()[-1] if res.error else 'unknown'}")
            records.append(rec)
            continue

        rec.ocr_mode = res.mode
        rec.output_type = res.output_type

        body = text.extract_text(out_path)
        rec.pages = text.page_count(out_path)
        rec.keywords = text.extract_keywords(body)
        rec.title = text.guess_title(body, src.name)
        rec.dates = text.extract_dates(body)
        rec.snippet = text.snippet(body)
        rec.text = body
        rec.size_bytes = out_path.stat().st_size

        try:
            metadata.apply_metadata(
                out_path, rec.title, rec.keywords,
                subject=text.snippet(body, 200),
            )
        except Exception as e:  # metadata is best-effort; never fail the doc for it
            log(f"    ~ metadata embed skipped: {e}")

        rot = f", rotated {[r for r in rec.rotations if r]}" if rec.rotated else ""
        log(f"    ok ({rec.pages}pp, {res.mode}{rot}) keywords: {', '.join(rec.keywords[:6])}")
        records.append(rec)

    _flag_duplicates(records, log)
    write_outputs(records, output_dir, folder_name)
    return records


def _flag_duplicates(records: list[DocRecord], log=print) -> None:
    ok_recs = [r for r in records if r.ok]
    dup_docs = [dedup.DupDoc(id=r.id, sha256=r.sha256, text=r.text) for r in ok_recs]
    flags = dedup.find_duplicates(dup_docs)
    n_flagged = 0
    for r in ok_recs:
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
    manifest = {
        "folder": folder_name,
        "count": len(records),
        "documents": docs,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    html = index.build_index([r.public_dict() for r in records if r.ok], folder_name)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
