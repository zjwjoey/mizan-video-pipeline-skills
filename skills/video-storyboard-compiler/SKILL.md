---
name: video-storyboard-compiler
description: "Compile an approved video script into shot-level production boards, generation prompts, asset manifests, and QC-ready handoffs. Use after scripting and before footage or AI asset generation."
---

# Video Storyboard Compiler

Turn a locked narration script into an executable visual plan. The deliverable must let a separate asset-generation, QC, editing, or CapCut-draft step continue without reinterpreting the creative brief.

## Scope and input check

- Treat the script as the source of truth for message, language, total runtime, format, and mandatory products. Do not silently rewrite its claims or voiceover.
- When the user supplies a shot list and/or image-prompt package, treat both as locked production input. Do not split, consolidate, rewrite, embellish, or substitute the user's shot count, scene action, products, or prompt wording. Validate their identifiers and timing, then carry them forward unchanged.
- Extract delivery constraints before inventing visuals: aspect ratio, duration, locale, presenter, setting, brand, intended platform, and tone.
- Flag a missing decision only when it changes production materially. Otherwise use explicit, reversible assumptions in `Production lock`.

## Compile the board

1. Retain the script's scene IDs and time boundaries. Split each scene into 2–4 atomic shots only when the user has not supplied atomic shots; the child IDs should be stable (for example, `P03-A`, `P03-B`).
2. Give every shot exact in/out timecode, planned duration, framing, camera movement, subject action, visible products, and an edit purpose. Sum all shots to the scripted duration with no gaps or overlaps. When the owner will supply per-shot audio before video generation, map the exact local file to `audio_ref` for every shot and preserve its `audio_role` and `lip_sync_required` values; do not invent or generate missing audio.
3. Establish a `Continuity lock` and `Anchor plan` before per-shot prompts. The lock covers presenter, wardrobe, store/location, lighting palette, product condition, camera language, and safety/brand restrictions. The anchor plan assigns one stable `host_anchor_id` and one `scene_anchor_id` to every contiguous sequence, plus optional product reference IDs. Asset generation must use those anchors as its first references rather than recreating the scene from prose each time.
4. Use the user's supplied image prompt verbatim when one exists. If no prompt is supplied, write one in the language preferred by the selected generation tool. In either case, keep continuity anchors, text/VO/caption layers, and API parameters outside the user-authored creative prompt unless the user asks to change it.
5. Specify a `Material manifest` with stable IDs. For each requested asset, include its source (`generate`, `capture`, `brand-supplied`, or `record`), required duration, aspect ratio, shot consumers, and acceptance test. Treat the owner's prepared audio as a required video-generation input: record `audio_ref` per shot so the downstream Dreamina Canvas stage can upload it, associate its Canvas audio node with the video node, and verify the selected model mode accepts audio references.
6. Include a scene-level QC checklist and a machine-readable handoff table containing at least `shot_id`, `source_asset_id`, `time_in`, `time_out`, `duration_s`, `voiceover`, `caption`, `transition_in`, `transition_out`, and `qc_status`.

## Output contract

Save the compiled board beside the input script unless the user specifies another location. Use a descriptive `*_分镜编译.md` filename. It must contain, in this order:

1. `Production lock` and assumptions.
2. A timing ledger that proves the runtime.
3. A shot board with prompts and edit instructions.
4. A material manifest for the next stage.
5. A continuity-anchor table, QC gates, and an explicit `Next handoff` section.

Read [references/handoff-schema.md](references/handoff-schema.md) when a project will continue through AI asset generation, QC, NLE/CapCut assembly, or automated rendering.

## Quality bar

- Do not let a product list become a static shelf montage: every scene needs a clear visual action or reveal.
- The host's identity, wardrobe, screen direction, store geography, and time of day must not drift between shots unless the board calls for a transition.
- For AI-generated image sequences intended for video, define a fully stocked scene-master frame and a host identity frame before batching the child shots. Preserve them as explicit inputs; a text-only continuity instruction is insufficient.
- Prefer 1.5–3.5-second atomic shots for vertical social video; retain a longer shot only when the scripted action genuinely needs it.
- Reserve readable campaign copy, legal text, price, and exact SKU information for provided assets or editable overlays; mark those as `needs_brand_asset` rather than fabricating them.
- Mark every asset `pending` until material generation/capture and QC actually confirm it. A board is a plan, not evidence that footage exists.

## Audio handoff for Canvas video generation

- The owner prepares the audio files before video generation. Each video shot must map to its exact existing `audio_ref`, `audio_role`, and `lip_sync_required` setting; a missing mapping blocks that shot from video generation.
- The Dreamina Canvas stage uploads/imports each audio file into the target canvas and records the resulting `canvas_audio_node_id`; it must attach that node to the shot's video-generation node using a currently supported model mode. The storyboard compiler records the mapping but does not assume a local path is automatically available to Canvas.
- The AI-generated video handed to CapCut Mate is expected to carry the generated audio. CapCut Mate must not add the local source audio as a separate track or locally mux/mix it with the generated video.

## Owner-confirmed structured storyboard

- Treat a user-confirmed storyboard MD as a locked execution spec. Do not reinterpret or change its shot count, action, products, prompt, timing, voiceover, subtitles, or audio mapping.
- Start downstream work only when `confirmed_by_owner: yes` and the declared `codex_start_stage` is reached.
- Preserve project fields such as `script_file`, `storyboard_source_file`, `aspect_ratio`, `fps`, `resolution`, `language_voiceover`, `subtitle_tracks`, `image_engine`, `video_engine`, and QC rules.
- Preserve shot fields including `shot_id`, `scene_group`, `scene_anchor_id`, `host_anchor_id`, timing, `product_refs`, `image_count`, `image_priority`, `material_mode`, `image_prompt_core`, `negative_prompt`, `voiceover_es`, `subtitle_es`, `subtitle_zh`, `target_duration`, `audio_ref`, and `qc_focus`.
- `image_count` is the number of execution images for that shot, not a fixed project-wide total. Resolve and approve host/scene anchors before generating child-shot images.

## V2 Lite handoff

When using the five-stage MIZAN workflow, write the confirmed `production_manifest.json` using the sibling [Canvas contract](../dreamina-canvas-bootstrap/references/manifest-contract.md). Keep `shot_id`, `scene_id`, `scene_anchor_id`, `character_id`, exact `product_refs`, `generation_strategy`, actual execution `image_count`, `audio_ref`, `audio_role`, `lip_sync_required`, `qc_status`, `approved_asset_id` and `version` stable. Record any legacy `host_anchor_id`/`scene_group` mapping with provenance instead of renumbering.

Run Canvas Bootstrap at Stage 02.5 before scene-anchor generation. Missing audio does not block script/image synchronization; it gates only the affected video shot. `audio_role: none` must be an explicit owner decision and later requires verified model support. Chinese review text is never automatically a subtitle track; default `subtitles.enabled` is false. A source DOCX without unambiguous structured fields must retain exact extracted text and report the missing fields. Do not infer production approval from extraction.
