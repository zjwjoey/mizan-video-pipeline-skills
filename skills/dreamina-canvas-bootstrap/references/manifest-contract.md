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
| `image_asset_ids`, `video_asset_id` | Ordered execution-image IDs (exactly `image_count` unique IDs) and downstream video ID. `approved_asset_id` is legacy metadata, not an execution-image selector. Versions resolve through Canvas's `approved_versions`. |

Each selected input asset requires `asset_id`, `asset_type`, `local_path`, `description`, `source_type: existing|generated`, `qc_status`. Types: `character`, `scene`, `product`, `scene_anchor`, `storyboard_image`, `first_frame`, `last_frame`, `audio`, `video`. Add `shot_id` or reusable `shot_ids`, `sku_id`, `character_id`, and provenance as appropriate. Product assets not referenced by any shot are filtered out. No recursive library upload is performed. Output declarations use the same identity/type/description fields but do not assert a file exists.

QC values map to visible Chinese names: `pending_check` → 待核对; `pending_review` → 待审核; `approved` → 已批准; `redo` → 需重做; `retired` → 已停用. Initial approved inputs require `qc_evidence`. Old `pass/revise/fail/not_started` records require explicit evidence-aware migration, not silent approval.

## Canvas state

Top level: `project_id`, `canvas_project_id`, `canvas_project_name`, `canvas_url` if supplied by CLI, timestamps, `sync_status`, `capabilities`, `organization_mode`, `nodes`, `assets`, `approved_versions`, `tasks`, `history`, request IDs. No credentials, signed resource URLs or credit tokens.

`nodes` maps stable business keys (overview/full_script/shot:P01/section:0) to node IDs, update IDs, exact text/content hashes, script version, text history, measured layout and sync verification. A changed locked script requires a new `script_version` and edits the existing node. Prior text remains in local history.

`assets[asset_id]` is an ordered version list. Each entry records `asset_type`, `local_path`, source and shot/SKU IDs, SHA256 `file_hash`, `canvas_node_id`, `canvas_resource_id`, `group_name`, `version`, `qc_status`, `sync_status`, `submit_id`, `update_id`, evidence and verification timestamps. `approved_versions[asset_id]` points to the currently approved version. Hash-identical entries may share a resource/node; their logical IDs and QC records remain distinct. The first logical entry owns the shared node's visible title.

`node_owners` durably binds each shared node to its first registered asset/version, including when a later version of an earlier logical asset reuses that content. A new file cannot inherit an old approval declaration: it enters pending review. Initial approved inputs require evidence and are selected only after successful resource/node verification.

The nine sections are: `00｜项目总览与脚本`, `01｜人物参考`, `02｜门店场景素材`, `03｜商品素材`, `04｜场景锚点`, `05｜分镜图片`, `06｜西语音频`, `07｜视频片段`, `08｜历史版本`. Empty future regions have clearly labeled text placeholders, never fake completed media.

## Versions and recovery

Display names use `镜头/角色/SKU编号｜素材类型｜内容描述｜原有/新生成｜v01｜审核状态`. IDs are independent of these editable names. New generated files are copied to project-local `generated/<asset_id>/`; existing inputs also receive immutable byte-verified copies under `snapshots/<asset_id>/`. Version records use those copies and retain `source_local_path`. If a source is overwritten, the old approved version remains recoverable but project preview is invalidated. A missing original may use its verified snapshot. Still-valid legacy records are migrated on sync; already-lost legacy bytes cannot be reconstructed. Filenames preserve the complete asset ID and trailing version/extension, truncating only descriptions within a Windows-safe UTF-16 budget. Original files are never renamed, moved, overwritten or deleted.

```powershell
python canvas_bootstrap.py register --production production_manifest.json --asset-id P03_IMAGE --file "D:\新图.png"
python canvas_bootstrap.py review --production production_manifest.json --asset-id P03_IMAGE --version v02 --qc-status approved --evidence "负责人确认，检查人物、SKU、构图：2026-10-19"
```

Same hash returns the same version. Different content increments v01/v02. A new pending version does not replace the old approved version. `review` selects a verified approved version and moves the previous node to the history region without deleting it or changing references. History approval facts stay intact. Refusing/retiring the currently selected version clears its approved pointer; it does not pick a different version silently.

All mutations freeze identities and atomically save state before the CLI call. An OS file lock prevents simultaneous updates. Lost Canvas-create response recovers by the original Canvas UUID; lost upload response recovers by resource status; lost node-save response recovers by node query. Never choose new IDs merely due to a timeout. Current CLI `service.6` resource-not-found behavior was verified; other service errors stop, retain the record and require resume after their cause is resolved. No localized error-message matching.

Run `reconcile` to see remote drift and `resume` to repair nonpaid operations. Recorded generation tasks are observed by original `submit_id` only. `resume` must not replay generation calls, including absent/unknown submissions. Download failures keep that original submission; use the currently supported public media export capability. CLI 1.0.3 only documents image download; video export is a separately verified/manual step, not an invented endpoint.

## DOCX and template 2

Template 1 stays unchanged. Template 2 maps canonical project/shot fields from labeled two-column cards or a wide shot table with a `shot_id` header. Stage headings `Stage A`, `Stage B`, `START FRAME`, `END FRAME` select stage records; `ANCHOR PROMPT`, `FINAL PROMPT`, `NEGATIVE / 禁止项` map verbatim. Lists/objects must be explicit JSON, not guessed filenames or free-form separators. `owner_confirmed` is accepted as an alias of `confirmed_by_owner`; contradictory values stop validation. `duration_target`, `host_anchor_id`, `scene_group` map with provenance. An optional `MIZAN_PRODUCTION_JSON_BEGIN` / `MIZAN_PRODUCTION_JSON_END` block remains supported.

`extract-docx` returns exact `full_text`, `source_blocks`, `candidate`, `unresolved_fields`, `conflicts`, `validation_errors` and source coordinates. It sets `production` only after full validation with no unresolved/conflicting cells. Blank templates and ordinary prose are not auto-approved production. A person must resolve missing asset IDs, image mapping, exact staged prompts, audio roles and owner confirmation before production; do not fill them creatively.

## Lossless image-stage handoff

Each shot has `image_generation` with separate stage objects. Every executed stage requires exact `prompt`, explicit `negative_prompt` (empty only if intentionally none), ordered `reference_asset_ids`, `keep_fixed`, `add_elements` and `output_asset_ids`. Strings are not rewritten or merged. Optional `output_prompts` maps output IDs to distinct exact prompts for multi-image recipes. `incremental`, `start` and `end` require `base_asset_id` equal to the shot's `scene_anchor_id`.

- `ANCHOR_ONLY`: `anchor`, producing the ordered execution image(s); an explicit `reuse_asset_id` may reuse the approved scene anchor.
- `ANCHOR_CHARACTER`, `ANCHOR_PRODUCT`, `ANCHOR_CHARACTER_PRODUCT`: `anchor` then `incremental`. Shared scene anchors use identical recipes or explicit `anchor: {"reuse_asset_id": "ANCHOR_STORE"}`. Conflicting recipes for one output ID stop.
- `START_END_FRAME`: `anchor`, `start`, `end`; distinct `start_frame_asset_id` and `end_frame_asset_id`; `image_asset_ids` must be exactly `[start_frame_asset_id, end_frame_asset_id]`. Both need independent approval. Both frame stages inherit the same anchor, locks and explicit references.
- `DIRECT_PRODUCT`, `MULTI_REFERENCE`: `direct`; all outputs are explicitly ordered, no single-image fallback.

Run `pipeline_handoff.py image-anchor --production ... --output stage_a.json`, register/review anchors, then `image-incremental` for Stage B/start/end/direct tasks. Plans retain prompt/negative/locks/additions/reference IDs, node references and immutable local reference paths. Required real SKU references cannot be omitted. These are executable task inputs, not an automatic paid batch runner. The chosen generator must support every constraint; do not discard negatives/locks or alter the approved prompt to fit an unsupported API.

Video plans use every approved execution image. First/last-frame plans expose `frame_refs`, ordered `frame_roles`, `context_refs` and a separate audio association; never put scene/product context into the two frame slots. Verify current model/mode support for the combination of two frames, context and prepared audio. If unsupported, block the shot: do not silently drop audio, frames or products or substitute another strategy.

## Whole-Canvas preview approval

### Image recipe identity and explicit reuse

Every image task includes `generation_fingerprint: sha256:...`, derived from the exact stage recipe (prompt, negative, ordered refs, locks, additions, optional generation parameters), output ID, format/image engine, and selected reference versions/content hashes/Canvas identities. Freeze the actual image task in the project journal before the independently authorized submission, then register its **new output** by task key:

```powershell
python pipeline_handoff.py record-task --production production_manifest.json --output prepared_task.json --task-key P03-image-v01 --node-id <actual-generation-node> --model <verified-model> --task-stage image-incremental --asset-id P03_IMAGE --shot-id P03 --parameters parameters.json
# Run the authorized original submit ID externally, then reconcile/observe success.
python canvas_bootstrap.py register --production production_manifest.json --asset-id P03_IMAGE --file "D:\新图.png" --task-key P03-image-v01
```

The journal freezes plan recipe/fingerprint, complete consumer scope, output asset, generation node/model, public parameters and original submit ID. Image prompt and ordered references must exactly match that pending production-plan task. Registration derives the fingerprint from the journal, requires an observed successful original operation (`success`/`succeeded`), matching output/type, and binds the result's verified bytes/hash to the task. Prepared, unknown, failed or unsupported terminal states stop; do not mark them successful manually in production. `--generation-fingerprint` alone is rejected; with `--task-key` it only asserts equality. One task cannot certify another asset or different result bytes. Registering identical legacy bytes cannot retroactively attach new provenance.

Normal `reconcile` observes public CLI tasks without resubmission. External image-provider journals do not automatically acquire successful Canvas-operation status: a future verified provider bridge must correlate its real submission/result before this trusted route can be used. Until then, import external/manual images without a generation fingerprint and explicitly review/reuse them; do not pretend this patch certifies autonomous external-provider execution. Linkage is not visual QC or proof that arbitrary local bytes visually match the generated resource; inspect the actual export and its origin before approval.

Do not recalculate a fingerprint after generation from a changed manifest or attach one retroactively to an unknown legacy image. Asset QC and generation-configuration identity are separate checks.

An approved output skips generation only if its saved fingerprint matches the current task **and** its task key/submit ID/output ID/result hash remain bound in the journal. A missing/different fingerprint or missing provenance binding stops with `IMAGE_REUSE_DECISION_REQUIRED`, including the current fingerprint. This also applies to old unbound fingerprint records. The owner can explicitly select reuse of that approved version or regeneration via the stage's `output_decisions` map:

```json
{"output_decisions": {"P03_IMAGE": {
  "choice": "reuse",
  "version": "v01",
  "fingerprint": "sha256:<current task fingerprint>",
  "reviewer": "负责人",
  "evidence": "已对照本次新提示词/参考版本核对旧图，明确选择复用"
}}}
```

Use `choice: regenerate` for a new task; the old version remains approved until the new output passes QC. This decision is bound to both the old approved version and the **current** fingerprint; another recipe/reference change invalidates it. Record the owner decision in the source manifest, increment the script version, sync and obtain the required preview confirmation; a fresh script/preview approval alone does not supply an image reuse decision. `reuse_asset_id` remains an explicit source-anchor reuse specification, not a new generated-output recipe.

### Scoped paid-task preparation

`pipeline_handoff.py record-task --shot-id P01 ...` (repeatable for a genuinely shared task) or `parameters.shot_id` must name known nonempty shot scope; contradictory declarations fail. `--task-stage image-anchor|image-incremental --asset-id ...` binds an image output to its actual pending plan. The scope must equal the complete consumer set derived from shot recipes, reused anchors/base/reference dependencies and output declarations; omitting P02 from a P01/P02 anchor is rejected even if only P01 is currently approved. Video scope similarly matches the declared `video_asset_id` (inferred only for a single-shot video). `record_task` accepts corresponding `task_stage` and `output_asset_id` arguments. The preview gate checks those consumers only, so an unrelated P02 source change need not block a genuinely independent P01 task. Old journals without bindings remain queryable by `reconcile`, but cannot be rebound or certify trusted new image provenance.

All `refs` and `{{node:...}}`/`{{res:...}}` prompt placeholders must resolve to approved synchronized versions actually declared for those shots: stage references/base/reused anchor, execution images, character, scene, real SKU or prepared audio. Arbitrary nodes/resources, other shots' products, unapproved versions and stale/corrupted snapshots are rejected before any journal write. The persisted task records `shot_ids`, and a task key cannot be rebound to another scope. These checks prepare a journal only; model capability and paid authorization remain separate gates.

Synchronization alone leaves `CANVAS_PREVIEW_PENDING`. After the owner actually previews the current Canvas, run:

```powershell
python canvas_bootstrap.py approve-preview --production production_manifest.json --owner-confirmed --reviewer "负责人" --evidence "本轮画布链接、脚本版本和素材全集已人工确认"
```

Approval requires synchronized script/shot text and selected media. `canvas_preview` records owner evidence/time, exact script version, SHA256 material-manifest version and an immutable approved snapshot. `preview_history` preserves approvals. `pipeline_handoff` and paid-task journaling require this project gate in addition to individual asset QC. There is no auto-approval switch in `sync`/`resume`.

Script/rules/shot-prompt/input bytes or selected input versions change the status to `CANVAS_PREVIEW_REVIEW_REQUIRED`, with changed components and affected shot IDs. Generated outputs not declared as initial inputs do not by themselves invalidate the initial preview. A selected unaffected shot can proceed with `--shot-id`; global changes block all shots. Reconcile drift also blocks production until repaired, including visible names, version/QC labels, spatial location and category intent. Canvas availability and synchronization status are separate; reusing a Canvas does not reset `synced` to `bootstrapped`.

## Readiness evidence

`CANVAS_BOOTSTRAP_READY` requires verified real nonpaid Canvas import/readback/recovery and actual owner preview for the production project. Offline synthetic approvals test the gate but never approve a real creative project. `VIDEO_PIPELINE_READY` additionally requires real Stage A/B generation/QC, prepared-audio video generation and sound/lip-sync checks, actual export, editable draft and Jianying GUI verification. Report the two outcomes separately; a task plan, mock test or valid draft JSON cannot certify a finished video pipeline.

## Capability boundaries

The runtime validates commands/flags against the current `schema`. Image/audio/video extensions are a local allowlist, not a claim the service accepts every encoding. Actual resource get plus node show must succeed; rejected uploads remain incomplete with service error facts. New group APIs are never guessed. Current grouping is `spatial_sections`; schema without coordinates uses `name_prefixes`. A newly appearing native Group command is reported as an unverified adapter limitation until its membership contract is inspected and implemented.
