---
name: dreamina-cli
description: Generate MIZAN storyboard videos through the installed Dreamina Canvas CLI, using the owner's prepared per-shot audio as a video-generation reference. Use after storyboard images and audio are approved and before CapCut Mate assembly.
---

# Dreamina Canvas video generation

This MIZAN pipeline stage uses the Dreamina Canvas CLI and its installed `dreamina-canvas-cli` Skill. Do not substitute the separate legacy `dreamina` generator CLI. Read the Canvas Skill before operating, and treat its installed CLI schema, model discovery, authentication instructions, and safety gates as authoritative.

## Required inputs and gate

- Start only from an owner-confirmed storyboard and image assets with `qc_status: pass`.
- The owner prepares the Spanish audio before video generation. Every shot must have a real, existing `audio_ref` and an explicit `audio_role` (`dialogue` or `narration`) and `lip_sync_required` value. Do not synthesize, translate, trim, pad, replace, or infer audio unless the owner explicitly requests that change.
- Before submitting a shot, verify the audio file and duration, then import/upload it into the target Dreamina Canvas using the installed Canvas CLI's documented resource/node workflow. Record the resulting Canvas audio node ID alongside the shot's `audio_ref`.
- Query the target video model's current specification. Select a video mode that accepts audio references, then connect the shot's Canvas audio node to that shot's video-generation node in the Canvas. A local path in a prompt or task note does not count as an attached audio reference.
- If audio is missing, inaccessible, too short/long for the selected model, or cannot be attached through the model's supported mode, stop that shot and report the precise issue. Do not generate a silent substitute.

## Generation and verification

1. Follow `dreamina-canvas-cli` for version/schema checks, `auth status`, model discovery, node references, pricing confirmation, submission, and recovery. For V2 Lite read `canvas_manifest.json` and reuse its `canvas_project_id`; do not create another Canvas or re-upload an already synchronized image/audio.
2. Resolve the approved shot image, host/scene anchors, and product references to Canvas-supported references. Preserve storyboard order and exact `shot_id`, approved prompt, `target_duration`, aspect ratio, resolution, and motion instructions.
3. Attach the prepared per-shot audio node as a reference to the video generation. For dialogue, request natural visible speech matching that audio; for explicitly declared narration, do not direct visible speech. Do not add music or other audio.
4. Save the Canvas project and record its project ID, video node ID, audio node ID, submitted operation ID, selected model/mode, parameters, and final status for every shot.
5. Wait for terminal success and inspect/download the actual video. Confirm the clip contains the expected audio, timing, visual content, and requested speech behavior. A prompt or successful submission alone is not proof of audio inclusion or lip sync.
6. Mark the output `qc_status: pass` only after review. Hand off the AI-generated video with its generated audio intact to CapCut Mate.

## Handoff fields

Retain at least `shot_id`, `source_image_ids`, `audio_ref`, `audio_role`, `lip_sync_required`, `canvas_project_id`, `canvas_audio_node_id`, `canvas_video_node_id`, `target_duration`, `video_asset_id`, `video_file`, `qc_status`, and `notes`. Do not store access tokens or private authentication material in project records.

## Audio boundary for editing

The generated video is the audio-bearing source clip. CapCut Mate imports that video and subtitles only. Never add the original local `audio_ref` as a separate CapCut/Jianying audio track or locally mux/mix it with the generated video. If the generated video lacks or mishandles its audio, return the shot to review/regeneration; do not repair it by silently compositing the local audio during draft assembly.

## V2 Lite execution and recovery

Use the sibling Bootstrap `pipeline_handoff.py video` to resolve only currently approved image, scene, character, SKU and audio versions. Read its returned node references rather than rewriting confirmed prompts or resolving arbitrary local filenames. Verify the live video model's reference types/counts, audio duration, ratio, resolution and allowed modes before saving generation parameters. After save, read the node back: `generation.references` and `upstreamNodeIds` must include the actual intended source nodes.

The normal rule above remains dialogue with prepared audio. Explicit narration uses its prepared audio and `lip_sync_required: false`. Only a source shot explicitly set to `audio_role: none`, `audio_ref: null`, `lip_sync_required: false` can request a silent mode, and only when the current model actually supports it. Missing audio does not imply that exception. Never generate missing audio or append music.

Before an authorized paid run, use `pipeline_handoff.py record-task` with a stable task key, node, actual model and public parameters; persist the submit ID before sending it to `node run`. Lost responses and resume use `operation status/wait` on the same submit ID only, including unknown/absent states. Do not replay a paid submission automatically. Keep generation evidence separate from QC approval.

Import successful exported video files with Bootstrap `register` into `07｜视频片段`, then review and update the approved version with evidence. CLI download support must be checked by media type: 1.0.3 only documents image downloads, so video export may require the Canvas's verified UI export. Report that step as pending until a real file exists and media QC passes. Preserve all source-image approvals on video failure.
