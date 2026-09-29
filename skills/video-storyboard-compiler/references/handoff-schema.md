# Closed-loop handoff schema

Use these identifiers unchanged across the workflow:

`script_id` → `shot_id` → `asset_id` → `qc_id` → `timeline_clip_id` → `capcut_item_id` → `render_id`.

## Required status values

| Stage | Allowed statuses | Ownership |
|---|---|---|
| Asset | `pending`, `generated`, `captured`, `rejected`, `approved` | material generation + QC |
| QC | `not_started`, `pass`, `revise`, `fail` | human/QC |
| Timeline | `planned`, `assembled`, `conformed`, `locked` | video generation/edit |
| Render | `not_started`, `queued`, `rendered`, `failed`, `delivered` | automation + final reviewer |

## Handoff table fields

At every handoff retain the following rows, adding stage-specific fields without renaming the shared keys:

| Field | Meaning |
|---|---|
| `shot_id` | Stable storyboard shot identifier, e.g. `P04-B`. |
| `asset_id` | Stable raw-material identifier, e.g. `AST-P04-B-01`. |
| `source_asset_id` | The approved asset actually used in the timeline. |
| `time_in` / `time_out` / `duration_s` | Target timeline placement, in seconds. |
| `voiceover` | Exact locked spoken line for the placement. |
| `caption` | Editable onscreen text, or `none`. |
| `qc_status` | Result for the asset or shot; never infer a pass. |
| `revision_of` | Previous asset ID if the item was regenerated. |
| `notes` | Decision, exception, or reason for revision. |

## Gate conditions

Do not move a clip to the editable timeline until it has an approved source asset and a `pass` QC result. Do not mark a timeline locked until its duration, voiceover coverage, captions, brand assets, and sound mix are verified. Automated rendering may run only from a locked timeline and must write back the output file, render settings, result status, and reviewer confirmation.
