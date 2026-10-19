---
name: capcut-mate-video-pipeline
description: Assemble approved shot videos into an editable Jianying/CapCut Mate draft on Windows, validate media and timeline integrity, and render when requested. Subtitles are optional and require explicit configuration.
---

# CapCut Mate 视频流水线

Use this skill when the user wants a repeatable pipeline from a shot script and local/AI-generated materials to a CapCut/Jianying draft, especially when captions, shot timing, bilingual subtitles, or automatic rendering are part of the request. Do not render, upload, or call cloud services unless the user asks for that stage.

## Workflow

1. Read the approved shot records and distinguish user instructions from attached document content. Preserve shot IDs, timeline order, exact start/end seconds and source approvals. Use the storyboard compiler only when no confirmed shot board exists; do not reinterpret a locked script during editing.
2. Convert approved shots into production records. Keep asset generation, human/QC approval, video generation, and timeline assembly as separate checkpoints; do not treat unreviewed generated material as approved. Video inputs must come from Dreamina Canvas generation with the shot's owner-prepared audio attached there.
3. Prepare local media. CapCut Mate's `add_videos` endpoint requires `http://` or `https://` URLs, so serve the media directory with a temporary local HTTP server. Use URL-encoded filenames and stop the server after import.
4. Create the draft with the requested canvas. For the established vertical preset use `1080×1920` at `30fps`; preserve a user's explicit canvas/fps override. Use microseconds for all timeline values.
5. Add the approved AI-generated videos in shot order. For each shot, set `start`, `end`, and `duration` in microseconds. These video files must already contain the audio produced with their Canvas audio references. Import video and subtitle materials only: do not import the original local `audio_ref` into CapCut/Jianying, create a separate audio track, or locally mux/mix audio with video. If a generated clip is missing or has incorrect audio, stop and send it back for review/regeneration; do not repair it in the draft.
6. Default to no visible subtitles. Only when explicitly requested/configured, add one caption track per declared language with matching shot ranges. The optional bilingual preset is `font=Georgia`, `bold=true`, `italic=true`, `font_size=8`, Spanish `transform_y=-700`, Chinese `transform_y=-500`, centered white text with black border. Chinese internal-review text alone is not permission to create captions.
7. Save the draft, copy it to the local Jianying drafts directory, and rewrite copied media paths so they point inside that draft's own `assets` directory. Keep the original draft when creating a corrected variant; use a clear suffix such as `_Bilingual_v2`.
8. Run QC before delivery: parse both `draft_info.json` and `draft_content.json`; verify canvas, fps, duration, media existence, shot boundaries, number of caption tracks, caption text, font/style fields, and normalized Y positions. Confirm each video source is the approved audio-bearing AI output and that no separate local-audio track was added. The two JSON files should remain identical after path/font edits.
9. If automatic rendering is requested, call `gen_video`, poll `gen_video_status`, and report the resulting file/URL. Rendering is a separate final stage and must not replace delivery of the editable draft.

## Local project conventions

- Repository: `capcut-mate`; the local API is normally `http://127.0.0.1:30000` and its Swagger UI is `/docs`.
- The local Jianying draft root is `%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft`. Respect `DRAFT_SAVE_PATH` when configured.
- The bundled CapCut Mate font registry may not contain a Windows system font. If a requested local font is missing, add it as a system-font entry only when the local draft needs it, and verify `materials.texts[].fonts[].title` plus the material font fields. Georgia is installed on the current Windows host and is represented as a local system font with no cloud resource ID.
- Do not add visible shot labels such as `P01`/`P02` unless the user explicitly asks for them; “按镜号导入字幕” means align the captions to the shot's time range by default.

## References and helper

- Read [references/capcut_api.md](references/capcut_api.md) when calling or troubleshooting the API.
- Read [references/draft_schema.md](references/draft_schema.md) when inspecting or patching a local Jianying draft.
- Use [scripts/build_capcut_draft.py](scripts/build_capcut_draft.py) for deterministic local-media import, bilingual caption tracks, copying, and validation. Supply a JSON config rather than hard-coding shot data.

## Owner-confirmed storyboard handoff

- Build the timeline only from approved shot records, preserving `shot_id`, `start_time`, `end_time`, `target_duration`, `audio_ref`, Canvas audio/video node IDs when available, `subtitle_es`, `subtitle_zh`, and QC status. Do not add shot labels unless requested.
- The user's Spanish audio from each shot's `audio_ref` must be attached to that shot's video-generation node in Dreamina Canvas before generation. At CapCut/Jianying assembly, use the resulting AI video with its generated audio intact; never add the local source audio as another track or separately combine it with the video. Dialogue audio is expected to match visible speech; narration is the only default exception to visible lip-sync requirements.
- Create one subtitle track per declared language. Use the exact approved subtitle text and the matching shot time range; do not translate, shorten, or infer missing subtitles without approval.
- Missing prepared audio or a Canvas audio association gates the upstream audio-bearing video stage. An explicitly approved silent shot is allowed only after its model/QC gate. Subtitle fields are required only for explicitly declared subtitle tracks. Before draft delivery, verify clip order, embedded sound for audio-bearing shots, no separate audio tracks, optional captions, portable media paths, canvas, 30fps, duration and both JSON files. Do not locally synthesize, replace, mux or mix audio during assembly.

## V2 Lite approved-video adapter

Read both manifests and run the sibling Bootstrap `pipeline_handoff.py capcut --production ... --canvas ... --output capcut_config.json`. This preserves shot order and resolves the currently approved video version. Supply that config to `build_capcut_draft.py --config ... --repo ... --media-dir ... --ffprobe ...`. Legacy standalone configs still work, but subtitles now require explicit `subtitle_tracks: ["es", "zh"]`; merely having `captions` keys does not add tracks.

Run `--dry-run` to probe all sources before any API mutation. The builder checks dimensions, duration, continuity and embedded audio, rejects divergent draft JSON and separate audio tracks, then compares imported media hashes and timeline placements. It does not prove GUI compatibility: open the copied draft in the actual Jianying installation and record that result separately; never call structural validation an actual GUI-open PASS.
