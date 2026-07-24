#!/usr/bin/env python3
"""CLI entry point: process a local folder of scanned PDFs into a searchable,
OCR'd, keyword-tagged, duplicate-flagged archive with an HTML index.

    python process.py --input ./in --output ./out

Google Drive sync is done separately by the session orchestrator; this command
operates purely on local folders so it can be run and re-run offline.
"""

from __future__ import annotations

import argparse

from mca.pipeline import process_folder


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", "-i", required=True, help="folder of source PDFs")
    ap.add_argument("--output", "-o", required=True, help="destination folder")
    ap.add_argument("--language", "-l", default="eng", help="tesseract language (default eng)")
    ap.add_argument("--jobs", "-j", type=int, default=2, help="OCR worker threads per file")
    ap.add_argument("--rotate-threshold", type=float, default=4.0,
                    help="min OSD confidence to auto-rotate a page (default 4.0)")
    ap.add_argument("--no-ocr-images", action="store_true",
                    help="catalogue image files instead of OCR-ing them (faster for large photo sets)")
    ap.add_argument("--name", default="MCA Document Archive", help="archive title for the index")
    args = ap.parse_args()

    records = process_folder(
        args.input, args.output,
        language=args.language, jobs=args.jobs,
        rotate_threshold=args.rotate_threshold, ocr_images=not args.no_ocr_images,
        folder_name=args.name,
    )
    ok = sum(1 for r in records if r.ok)
    dup = sum(1 for r in records if r.duplicate_group)
    imgs = sum(1 for r in records if r.is_image and r.ok)
    print(f"\nDone: {ok}/{len(records)} processed, {dup} flagged as possible duplicates.")
    print(f"Index: {args.output}/index.html")
    if imgs:
        print(f"Image tagging sheet ({imgs} images): {args.output}/image_tagging.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
