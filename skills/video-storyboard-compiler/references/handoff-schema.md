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
| `audio_ref` | Exact owner-provided local audio file assigned to this shot; required before Canvas video generation when the workflow uses prepared audio. |
| `audio_role` / `lip_sync_required` | Owner-confirmed dialogue/narration role and whether visible speech must sync to the audio. |
| `canvas_audio_node_id` | Canvas audio node created from this shot's `audio_ref`; populate during the Canvas video-generation stage. |
| `canvas_video_node_id` | Canvas video-generation node that references the approved visual inputs and `canvas_audio_node_id`. |
| `caption` | Editable onscreen text, or `none`. |
| `qc_status` | Result for the asset or shot; never infer a pass. |
| `revision_of` | Previous asset ID if the item was regenerated. |
| `notes` | Decision, exception, or reason for revision. |

## Gate conditions

Do not move a clip to the editable timeline until it has an approved source asset and a `pass` QC result. When owner-prepared audio is part of video generation, verify it was attached through the Canvas audio node and that the approved AI video contains the expected audio. CapCut/Jianying assembly imports the audio-bearing generated video and captions only; it must not add the local `audio_ref` as a separate track or locally mux/mix audio. Automated rendering may run only from a locked timeline and must write back the output file, render settings, result status, and reviewer confirmation.
