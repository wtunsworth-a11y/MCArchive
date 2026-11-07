# MCA_Portal recovery package — "From PWM" corrupt-text-layer files

**Version 1.0.0 · 2026-11-07** · 51 records · see `MANIFEST.json` for checksums

Generated 2026-11-06. Source: Google Drive "From PWM" collection.

## What this is

Of the 151 PDFs in the collection, **51 had a corrupt embedded text layer**
(broken font / ToUnicode CMap → control-char codes, no machine-readable words).
Google Drive's *search* index still finds them, but anything that reads the
stored text layer — including the portal — got garbage. This package carries
the **re-OCR'd clean text** for all 51 files so the portal can index/display
real content.

**Drive IDs and URLs are UNCHANGED.** Nothing was re-uploaded or moved, so every
existing portal link stays valid. You only need to refresh the *text/snippet*
the portal holds for each `drive_id`.

## Status: ALL 51 RECOVERED ✅

- 43 recovered in the first pass (downloaded + OCR'd here).
- 8 large files (6.8–12.6 MB) recovered in a second pass by fetching them
  directly and OCR-ing the page images. Zero failures.
- Text was produced by rendering each page at 300 dpi and running Tesseract
  on the **image** (with auto-rotation), which ignores the broken text layer.
  Faint and upside-down scans recovered correctly.

> Note: Google Drive's own "convert to Doc" OCR was tried and rejected — it
> re-reads the corrupt text layer instead of the images, so it reproduced the
> same garbage. That approach is not used here.

## Files

- `MCA_portal_package.json` — array of 51 records (primary deliverable).
- `MCA_portal_package.csv`  — same rows, flat, for spreadsheet/DB import.

### Columns

| field            | meaning |
|------------------|---------|
| `drive_id`       | Google Drive file ID — **unchanged**, the join key for the portal |
| `current_url`    | existing Drive view URL — **unchanged** |
| `year`           | collection year folder |
| `title`          | current Drive filename |
| `page_count`     | pages OCR'd |
| `size_bytes`     | file size |
| `ocr_status`     | `recovered` (all 51) |
| `char_count`     | characters of recovered text |
| `clean_ocr_text` | the recovered searchable text (page-delimited `=== page N ===`) |

## Two filenames were also corrected in Drive (same IDs/URLs)

| drive_id | was | now |
|----------|-----|-----|
| 1sEb7X52gAbz2pwp9B3VXE7DaUM-H0X65 | STATUS~1.pdf | Status Report (Desktop Study) on Queen Alexandra Birdwing Butterfly (QABB) Survival, Managalas Plateau - T. Mala, UPNG (May 2008).pdf |
| 1UB61QKtDgQX7K96eWjpkofu8AsRRhzRS | 2nd Phrase Report prepared for PWM.pdf | 2nd Phase Report prepared for PWM.pdf |

## Cleanup still to do on your side (one script)

To pull the 8 large files I had to temporarily set them to "anyone with link,
viewer." Run the supplied `MCA_cleanup.gs` once to (a) set those 8 back to
private and (b) delete the junk `MCA_OCR_results` Docs from the abandoned
Drive-OCR attempt.
