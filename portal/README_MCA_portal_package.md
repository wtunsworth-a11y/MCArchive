# MCA_Portal handover package

**Version 1.1.0 · 2026-11-13** · 70 records · see `MANIFEST.json` for checksums

Searchable-text package for the MCA data portal. Each record carries a Drive
`drive_id` + `current_url` (both unchanged in Drive) and the document's
`clean_text`, so the portal can index/display real content. **Join on
`drive_id`; replace the portal's stored text with `clean_text`.**

## Contents (70 records)

- **51 recovered** — "From PWM" PDFs whose embedded text layer was corrupt;
  re-OCR'd from the page images (`status: recovered`).
- **19 added this session** — documents that existed only as non-PDF/other
  formats or were missing from the indexed archive, now converted to
  searchable PDFs and filed in `PwM Indexed Documents` (`status:
  added_this_session`).

### Columns
| field | meaning |
|---|---|
| `drive_id` | Drive file ID — the portal join key |
| `current_url` | Drive view URL |
| `collection` | where it sits in the archive |
| `title` | file title |
| `char_count` | characters of searchable text |
| `status` | `recovered` or `added_this_session` |
| `clean_text` | the searchable text |

## Changelog — v1.0.0 → v1.1.0 (this session)

**Added to the indexed archive (converted to searchable PDF):**
- Vanilla Quality Assurance Training Report (Oct 2018)
- Script Writing under Theatre Training Report
- 6 zone-to-zone awareness reports (Zones 5, 6, 7A, 7B, 8, 9 — 2014)
- DEC meeting Summary
- 4 QABB documents (The butterfly cowboy; QABB review paper WWP 2004;
  Managalas Barlow visit report 2017; Acknowledgements) — added to both
  QABB mirror collections
- Managalas plant survey findings presentation (from .ppt)
- PiasManagalas Report 2005 (full quality, user-uploaded)
- Plants survey (full quality, user-uploaded; image-heavy, limited text)

**Filenames corrected in Drive (IDs/URLs unchanged):**
- `STATUS~1.pdf` → "Status Report (Desktop Study) on Queen Alexandra Birdwing
  Butterfly (QABB)… T. Mala, UPNG (May 2008)"
- `2nd Phrase Report…` → `2nd Phase Report…`

## Exclusions (do NOT index)

- **`O_alexandrae_MANUSCRIPT`** — licensed to the project but copyrighted and
  not shareable. Left in Drive, deliberately **not** OCR'd, converted, or
  indexed. All copies listed in `portal/exclusions.json`.

## Known gaps / notes

- **"Partners with Melanesia (2004). Coarse Scale Analysis of HCV1-6 of
  Managalas Plateau CA Project"** — referenced by the Pias report but **not
  present** in the archive. Likely to be requested from PwM.
- A handful of Theodist re-scans and scanned maps were flagged during the
  Original-Files → Indexed reconciliation and need a human eyeball — see the
  separately delivered `final_reconciliation_review.csv`.
- Scope: this package covers the `PwM Indexed Documents` archive only.
