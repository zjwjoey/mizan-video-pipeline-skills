# CapCut Mate API quick reference

## Base URLs

- Local service: `http://127.0.0.1:30000/openapi/capcut-mate/v1`
- Cloud service: `https://capcut-mate.jcaigc.cn/openapi/capcut-mate/v1`
- Official documentation: `https://docs.jcaigc.cn/`

Use the local service for a Windows/Jianying draft. Use the cloud service only when the user explicitly requests a remote operation or cloud rendering.

## Draft sequence

1. `POST /create_draft`
   - Body: `{ "width": 1080, "height": 1920 }` (the service defaults to 30fps).
   - Response: `{ "code": 0, "draft_url": "...get_draft?draft_id=..." }`.
2. `POST /add_videos`
   - Body fields: `draft_url`, `video_infos`.
   - `video_infos` is a JSON-encoded string, not an array object. Each item includes `video_url`, `width`, `height`, `start`, `end`, and `duration`.
   - Local media URLs must be HTTP(S), so expose the directory temporarily with `python -m http.server`.
3. `POST /add_captions`
   - Body fields: `draft_url`, `captions` (JSON-encoded string), and style fields such as `font`, `font_size`, `bold`, `italic`, `alignment`, `transform_x`, and `transform_y`.
   - Caption items use `{ "start": <microseconds>, "end": <microseconds>, "text": "..." }`.
   - Call once per language to create separate caption tracks.
4. `POST /save_draft`
   - Body: `{ "draft_url": "..." }`.
5. Optional render: `POST /gen_video`, then poll `POST /gen_video_status` using the returned task ID.

## Units and coordinate conversion

- Timeline values are integer microseconds: `5s = 5000000`.
- The service writes caption `transform_y` as `input_y / canvas_height`. For a 1920px canvas, `-700` becomes `-0.3645833333`; `-500` becomes `-0.2604166667`.
- Caption alignment `1` is centered. The established bilingual style uses white text with a black border.

## Font handling

`add_captions` resolves `font` through the repository's `FontType` registry. Unknown names fall back to the default font. A local system font should be represented by a registry entry with an empty resource ID and verified in the draft's `materials.texts[].fonts[].title`, `font_name`, and `font_title` fields. The local workflow adds `Georgia` as a system font when that preset is requested.
