# MCA Document Archive

A processing pipeline that turns a folder of **scanned PDFs** into a clean,
searchable, archival document collection:

1. **Auto-rotate & deskew** — pages scanned sideways or upside-down are
   straightened using tesseract orientation detection.
2. **OCR** — an invisible text layer is added so every document is fully
   searchable, and files are saved as **PDF/A-2B** (the archival standard).
3. **Keyword tagging** — a title, keywords and any dates are inferred from the
   OCR text and embedded in each PDF's metadata (`/Title`, `/Keywords`, XMP).
4. **Duplicate flagging** — exact copies (byte hash) and near-duplicate
   re-scans (OCR-text similarity) are detected and **flagged for review — never
   deleted**.
5. **Searchable HTML index** — a single self-contained `index.html` with all
   document metadata and full text embedded, plus a client-side search box and
   a "duplicates only" filter. No server required; works locally or from Drive.

## Usage

```bash
python process.py --input ./in --output ./out --name "My Archive"
```

Options:

| flag | default | meaning |
|------|---------|---------|
| `--input`, `-i` | — | folder of source PDFs |
| `--output`, `-o` | — | destination folder (processed PDFs + `manifest.json` + `index.html`) |
| `--language`, `-l` | `eng` | tesseract OCR language(s), e.g. `eng+fra` |
| `--jobs`, `-j` | `2` | OCR worker threads per file |
| `--rotate-threshold` | `4.0` | min OSD confidence to auto-rotate a page (lower = more aggressive) |
| `--name` | `MCA Document Archive` | title shown in the index |

The command is **idempotent**: pages that already contain real text are skipped
on re-runs, so you can safely re-process a folder as new scans are added.

## Outputs

- `out/*.pdf` — rotated, OCR'd, keyword-tagged PDF/A copies of every source.
- `out/manifest.json` — full machine-readable record per document (title,
  keywords, dates, page count, rotation, duplicate group, OCR text).
- `out/index.html` — the searchable archive index.

## Requirements

System: `tesseract-ocr` (+ `osd` data), `ghostscript`, `poppler-utils`,
`qpdf`, `unpaper`, `pngquant`.
Python: see `requirements.txt` (`ocrmypdf`, `PyMuPDF`, `pikepdf`, `Pillow`).

```bash
sudo apt-get install -y tesseract-ocr ghostscript poppler-utils qpdf unpaper pngquant
pip install -r requirements.txt
```

## Layout

```
mca/
  ocr.py        rotate + deskew + OCR (ocrmypdf), OSD rotation detection
  text.py       OCR text extraction, keyword/title/date inference
  metadata.py   embed title/keywords/subject into PDF (docinfo + XMP)
  dedup.py      exact + near-duplicate detection (flag, don't delete)
  index.py      self-contained searchable HTML index
  pipeline.py   orchestration over a local folder
process.py      command-line entry point
```

## Google Drive

Drive download/upload is driven separately (the source folder is pulled down,
processed locally, and the results uploaded back). The pipeline itself operates
on local folders so it is easy to test and re-run offline.
