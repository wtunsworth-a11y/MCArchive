# MCA_Portal handover — v1.1.0 (2026-11-13)

Feed `MCA_portal_handover.json` (or `.csv`) to the portal. Every record has an
**`action`** telling the portal what to do. Join on **`drive_id`** (all ids/urls
are live Drive values).

## How to apply each action

| action | count | what the portal should do |
|--------|------:|---------------------------|
| `recovered` | 51 | **Replace** the indexed text for this `drive_id` with `clean_text`. These are the "From PWM" files whose embedded text layer was corrupt; id/url are unchanged. |
| `added` | 20 | **Insert** a new entry: new `drive_id`, `current_url`, `collection`, `title`, `clean_text`. These are documents converted to PDF and added to the indexed archive this session. |
| `renamed` | 2 | **Update the title** for this `drive_id` (`old_title` → `title`). Same id/url. |
| `excluded` | 4 | **Remove / never index** this `drive_id`. Copyrighted, not shareable. |

## Schema
`action, drive_id, current_url, collection, title, old_title, char_count, note, clean_text`

## Notes on the added (20)
- Program Reports: Vanilla QA Training, Script Writing report.
- MCA Zone Activity Reports: Zone 5, 6, 7A, 7B, 8, 9 (2014 awareness reports).
- 1.CA Submission: DEC meeting Summary.
- QABB Indexed Documents + Qabb docs (mirror): The butterfly cowboy, QABB review
  paper WWP 2004, Managalas Barlow visit report, 0_Acknowledgements (added to both mirrors).
- 8.PWM Presentations: Managalas plant survey findings presentation.
- 4.Survey Docxs: PiasManagalas Report 2005, Plants (full quality).

## Excluded (4)
All copies of `O_alexandrae_MANUSCRIPT` — licensed to the project but copyrighted
and not shareable. Must stay out of the searchable index. See `exclusions.json`.

## Superseded
v1.0.0 (`MCA_portal_package.json`, 51 recovered) is fully contained in this
handover's `recovered` rows.
