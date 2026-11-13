# MCA_Portal handover — update (2026-11-13)

Document-management update for the data portal. All items below are Drive
files with stable IDs; merge them into the portal index by `drive_id`.

## Files included
- `HANDOVER_session_additions.json` / `.csv` — **20 documents** newly added to
  the indexed archive this session (Drive id, URL, folder, title, char_count,
  clean_text). Merge each into the portal index by `drive_id`.
- (Prior) `MCA_portal_package.json` — the original 51 recovered "From PWM"
  files. Still valid; unchanged IDs/URLs.
- `exclusions.json` — one document that must stay OUT of the index (below).

## What changed in the archive this session

**20 documents converted to searchable PDF and filed into the indexed archive:**

| folder | count | items |
|---|--:|---|
| 3.Program Reports | 2 | Vanilla QA Training (2018); Script Writing under Theatre Training |
| 3.Program Reports / MCA Zone Activity Reports | 6 | Zone 5, 6, 7A, 7B, 8, 9 awareness reports (2014) |
| 1.CA Submission | 1 | DEC meeting Summary |
| 4.Survey Docxs | 2 | PiasManagalas Report 2005; Plants (full quality) |
| 8.PWM Presentations | 1 | Managalas plant survey findings presentation |
| QABB Indexed Documents | 4 | butterfly cowboy; QABB review paper 2004; Barlow visit report 2017; Acknowledgements |
| Qabb docs (mirror) | 4 | same 4 QABB items, mirror collection |

All were born-digital Word/PPT sources that had **no PDF in the index**; text
is clean (no OCR needed) except the Plants survey, which is image-heavy
(~1,400 chars of caption text; photos at 220 ppi).

## Earlier in the session (for context)
- The 51 corrupt-text "From PWM" PDFs were re-OCR'd — already in
  `MCA_portal_package.json`; IDs/URLs unchanged.
- Two filenames corrected in place (same IDs): `STATUS~1.pdf` → QABB status
  report; `2nd Phrase…` → `2nd Phase…`.

## EXCLUSION — do NOT index
`O_alexandrae_MANUSCRIPT` (all copies) is licensed but **not redistributable**.
Keep it out of the portal index, search, crosswalk and any extract. IDs are in
`exclusions.json`. An existing `O_alexandrae_MANUSCRIPT_OCR.pdf` also exists in
Drive — flagged for the owner; do not surface its text in the portal.

## Scope note
This update covers documents filed under the **PwM Indexed Documents**,
**QABB Indexed Documents**, and **Qabb docs** collections only. Nothing was
pulled from outside those folders.
