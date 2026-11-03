# Asana desktop app: UI/UX audit

Scope: the ttkbootstrap app launched with `python asana_task_app.py`. The Flask estimator, source workbooks, saved projects and existing exported CSV files were not modified for this audit.

## Findings and changes

| Area | Finding | Implemented improvement |
| --- | --- | --- |
| Task editing | Thirteen fields, inline help and a description box exceeded the original 560-pixel dialog. Save/Cancel could fall below the window. | Three focused tabs, reusable field controls, a draft before commit, and an always-visible action footer. |
| Export predictability | Merely selecting a row silently changed export from all rows to selected rows. | Explicit All tasks / Selected tasks scope and live export count. All tasks includes filtered-out rows. |
| Recovery | Bulk edits, deletion, option renames and loading another project had no undo. | Up to 30 undo snapshots covering rows, options and project context. Prompts before replacing or closing unexported work. |
| Loading feedback | qBOM loading ran on the Tk event thread, freezing interaction. | Background worker, progress indicator, disabled mutation controls and atomic result commit. A failed load preserves existing work. |
| Visual hierarchy | Description occupied an early wide column while estimated hours and labels were difficult to locate. | Overview prioritizes names, estimates, labels and assignments; All fields exposes every export column. CSV headers/order are unchanged. |
| Table navigation | No search or sorting; selection state had little context. | Debounced search across all fields, sortable headings, visible/total/selected counts, selected hours, zebra rows and a full-name detail area. |
| Empty state | A blank task appeared on startup and could be accidentally exported. | Guided empty state. Add task creates a draft; canceling adds no row. A separate no-results state resets filters. |
| Multi-select fields | Project and Labels required remembering and typing option strings. | Checkbox menus plus free text. Batch controls explicitly replace, add or remove values. Exact-token matching keeps BOM and BOM/WT distinct. |
| Option management | Renaming a multi-select option did not update that token in combined task values. | Token-aware renaming and undo; session-only scope and delete behavior are explained in the dialog. |
| Error prevention | Invalid dates/numbers and missing names could reach export with no explanation. | Actionable validation on Save, batch apply and export. Blank optional dates and estimates remain supported. |
| Estimate transparency | Zero-hour tasks appeared without an explanation. | Needs review filter and textual notes for zero/missing estimates and manual values outside the generation rule. Review does not alter calculations. |
| Smaller windows | The original minimum width was 1180px. Wide table requests could squeeze the batch controls. | 960×620 minimum, screen-aware dialog placement, controlled pane width, horizontal table scroll and scrollable batch content with fixed actions. |
| Keyboard use | Editing depended on discovering double-click; selection and workflow shortcuts were absent. | Enter to edit, Ctrl+A for visible rows, Ctrl+Z undo, Delete, Escape, Ctrl+O/N/F/S, Ctrl+Enter to save, and F1 Help. Native input text undo remains available. |
| Feedback | Counts and destructive-action recovery were unclear. | Contextual status messages, disabled unavailable actions, explicit unexported indicator, and progress without unnecessary success dialogs. |

## Preserved contracts

- DHE and `generate_estimated_tasks.py` share the current quantity weights: Primary 1.00, Secondary 0.25, and Tertiary 0.10. Estimates round half-up before being split into rows capped at 40; task suffixes and distinct BOM / BOM/WT labels remain intact.
- The CSV serializer, header order, date normalization and number formatting are unchanged. The screen's column order is independent of the export schema.
- Source projects and qBOMs are still loaded by the existing generator. Existing CSVs and workbook calculations were not rewritten.
- Product, Project, Assignee, Priority, Status, Labels and Task Type option CRUD remains session-only. All original fields remain editable.
- The UI does not change zero hours to one, remove zero-hour rows, or round/split manual numeric edits. These are review hints. Invalid field syntax is blocked; numeric review hints are advisory.
- Search and sorting do not mutate source values. Full export retains model/generator order.

## Verification

The 12 existing tests cover CSV field/date/number formatting, multiplier calculations, qBOM resolution, contribution components, distinct BOM/WT labeling, capped splits and summary totals. Twelve additional tests cover selection/export scope, filtered export behavior, batch edits/undo, editor save/cancel, exact multi-select token handling, option rename recovery, background load success/failure, dirty state after partial/failed/full exports, and minimum-window action visibility.

Tk runtime checks exercise a 960×620 main window and a 600×530 editor, including action-button bounds and usable batch-input width. These are real widget geometry/workflow checks, not pixel screenshots.

Native screenshot inspection was attempted with the Computer Use skill, but desktop app access approval timed out. Consequently pixel-level visual inspection, alternate Windows DPI settings, and screen-reader testing remain unverified. No Asana upload was performed during this UI-only change.
