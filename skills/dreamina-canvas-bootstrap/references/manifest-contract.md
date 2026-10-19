# V2 Lite manifest contract

`production_manifest.json` is the confirmed creative specification. `canvas_manifest.json` is mutable operational state. Both carry `schema_version: 2` and the same stable `project_id`. Never renumber a shot at a handoff. Files are UTF-8 JSON; paths resolve relative to production_manifest's directory. The runtime state defaults beside that file, outside the skill installation.

## Production fields

Required project fields: `project_id`, Chinese `topic`, `confirmed_by_owner: true`, `script_version` (`v01`, etc.), exact nonempty `full_script`, ordered `shots`, selected `assets`. Optional: `canvas_project_id` to reuse an existing authorized Canvas, `format` (`width`, `height`, `fps`, default output fps 30), `production_rules`, `subtitles` (`enabled: false`, `languages: []`), `outputs` (logical output declarations, no pretend local files).

Each shot requires these keys, even when an explicit null/empty list is appropriate:

| Key | Contract |
| --- | --- |
| `shot_id`, `scene_id`, `scene_anchor_id`, `character_id` | Stable source identifiers; no downstream reinterpretation. |
| `duration` | Positive finite seconds on final timeline. Generated clip may be longer and explicitly trimmed later. |
| `product_refs` | Exact SKU IDs; `[]` for no product. Never invent a SKU. |
| `voiceover_es`, `translation_zh` | Confirmed text; Chinese translation is not a subtitle instruction. |
| `visual_description`, `action`, `motion_intention`, `generation_strategy` | Exact confirmed content. |
| `image_count` | Number of execution images; reused scene anchor is not a new execution image. |
| `audio_ref` | Stable audio asset ID, or null while missing/explicitly silent. Legacy local-path audio maps must be deliberately converted with provenance. |
| `audio_role`, `lip_sync_required` | `dialogue/true`, `narration/false`, or explicit `none/false`. Null decisions can synchronize scripts but cannot pass the video gate. Silent mode requires live model validation. |
| `approved_asset_id`, `video_asset_id` | Optional stable logical image/video ID for downstream selection; version resolves through Canvas's `approved_versions`. |

Each selected input asset requires `asset_id`, `asset_type`, `local_path`, `description`, `source_type: existing|generated`, `qc_status`. Types: `character`, `scene`, `product`, `scene_anchor`, `storyboard_image`, `first_frame`, `last_frame`, `audio`, `video`. Add `shot_id` or reusable `shot_ids`, `sku_id`, `character_id`, and provenance as appropriate. Product assets not referenced by any shot are filtered out. No recursive library upload is performed. Output declarations use the same identity/type/description fields but do not assert a file exists.

QC values map to visible Chinese names: `pending_check` → 待核对; `pending_review` → 待审核; `approved` → 已批准; `redo` → 需重做; `retired` → 已停用. Initial approved inputs require `qc_evidence`. Old `pass/revise/fail/not_started` records require explicit evidence-aware migration, not silent approval.

## Canvas state

Top level: `project_id`, `canvas_project_id`, `canvas_project_name`, `canvas_url` if supplied by CLI, timestamps, `sync_status`, `capabilities`, `organization_mode`, `nodes`, `assets`, `approved_versions`, `tasks`, `history`, request IDs. No credentials, signed resource URLs or credit tokens.

`nodes` maps stable business keys (overview/full_script/shot:P01/section:0) to node IDs, update IDs, exact text/content hashes, script version, text history, measured layout and sync verification. A changed locked script requires a new `script_version` and edits the existing node. Prior text remains in local history.

`assets[asset_id]` is an ordered version list. Each entry records `asset_type`, `local_path`, source and shot/SKU IDs, SHA256 `file_hash`, `canvas_node_id`, `canvas_resource_id`, `group_name`, `version`, `qc_status`, `sync_status`, `submit_id`, `update_id`, evidence and verification timestamps. `approved_versions[asset_id]` points to the currently approved version. Hash-identical entries may share a resource/node; their logical IDs and QC records remain distinct. The first logical entry owns the shared node's visible title.

`node_owners` durably binds each shared node to its first registered asset/version, including when a later version of an earlier logical asset reuses that content. A new file cannot inherit an old approval declaration: it enters pending review. Initial approved inputs require evidence and are selected only after successful resource/node verification.

The nine sections are: `00｜项目总览与脚本`, `01｜人物参考`, `02｜门店场景素材`, `03｜商品素材`, `04｜场景锚点`, `05｜分镜图片`, `06｜西语音频`, `07｜视频片段`, `08｜历史版本`. Empty future regions have clearly labeled text placeholders, never fake completed media.

## Versions and recovery

Display names use `镜头/角色/SKU编号｜素材类型｜内容描述｜原有/新生成｜v01｜审核状态`. IDs are independent of these editable names. New generated files are copied to an immutable project-local `generated/<asset_id>/MIZAN_P03_分镜图片_描述_v02.png`; statuses are not in filenames. Original files are never renamed, moved, overwritten or deleted.

```powershell
python canvas_bootstrap.py register --production production_manifest.json --asset-id P03_IMAGE --file "D:\新图.png"
python canvas_bootstrap.py review --production production_manifest.json --asset-id P03_IMAGE --version v02 --qc-status approved --evidence "负责人确认，检查人物、SKU、构图：2026-10-19"
```

Same hash returns the same version. Different content increments v01/v02. A new pending version does not replace the old approved version. `review` selects a verified approved version and moves the previous node to the history region without deleting it or changing references. History approval facts stay intact. Refusing/retiring the currently selected version clears its approved pointer; it does not pick a different version silently.

All mutations freeze identities and atomically save state before the CLI call. An OS file lock prevents simultaneous updates. Lost Canvas-create response recovers by the original Canvas UUID; lost upload response recovers by resource status; lost node-save response recovers by node query. Never choose new IDs merely due to a timeout. Current CLI `service.6` resource-not-found behavior was verified; other service errors stop, retain the record and require resume after their cause is resolved. No localized error-message matching.

Run `reconcile` to see remote drift and `resume` to repair nonpaid operations. Recorded generation tasks are observed by original `submit_id` only. `resume` must not replay generation calls, including absent/unknown submissions. Download failures keep that original submission; use the currently supported public media export capability. CLI 1.0.3 only documents image download; video export is a separately verified/manual step, not an invented endpoint.

## DOCX and template 2

Template 1 stays unchanged. Add a short Canvas block to template 2: stable project ID, topic, script version, selected local asset paths and the confirmed shot IDs. Put the structured manifest beside Word. An optional `MIZAN_PRODUCTION_JSON_BEGIN` / `MIZAN_PRODUCTION_JSON_END` block allows strict automatic extraction. Ordinary prose/tables are extracted verbatim with paragraph/cell order retained; extraction deliberately does not guess shot semantics. Map all required fields with source paragraph/table coordinates and preserve the original text before saving a confirmed production manifest.

## Capability boundaries

The runtime validates commands/flags against the current `schema`. Image/audio/video extensions are a local allowlist, not a claim the service accepts every encoding. Actual resource get plus node show must succeed; rejected uploads remain incomplete with service error facts. New group APIs are never guessed. Current grouping is `spatial_sections`; schema without coordinates uses `name_prefixes`. A newly appearing native Group command is reported as an unverified adapter limitation until its membership contract is inspected and implemented.
