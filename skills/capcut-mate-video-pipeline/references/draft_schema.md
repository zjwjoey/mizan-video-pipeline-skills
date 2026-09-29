# Jianying local draft QC

Inspect both `draft_info.json` and `draft_content.json` in the copied draft folder. They should parse as JSON and be byte-identical after edits.

## Required invariants

- `canvas_config.width` and `.height` match the requested canvas.
- `fps` matches the requested frame rate, normally `30`.
- `duration` equals the final shot end in microseconds.
- `materials.videos` contains one entry per imported clip; every `path` exists under the draft's own `assets/videos` directory.
- Video tracks contain segments in shot order. `target_timerange.start` and `duration` match the shot board.
- Caption tracks have `type: "text"`, one segment per caption item, and matching `target_timerange` values.
- `materials.texts[].content` is a JSON string. Its first style should carry `bold`/`italic` flags and the requested size; the material should expose the requested local font name.
- Caption segment `clip.transform.y` is normalized. Convert back to pixels as `y * canvas_config.height` when reporting a QC result.

## Copying a draft

The API output is usually under `capcut-mate/output/draft/<draft_id>`. Copy it to:

`%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft\<draft-name>`

After copying, rewrite absolute media paths in both JSON files from the API output directory to the copied draft's `assets/videos` directory. Do not rewrite IDs, segment timings, or material names.
