# V2 Lite validation and delivery

Validation date: 2026-10-19, Asia/Shanghai. Baseline main: `2ae7ed3`. Development branch: `feature/mizan-canvas-bootstrap-v2`. No paid image/video generation or cloud rendering was performed.

## Delivery status: CANVAS_BOOTSTRAP_PARTIAL

The core Bootstrap has passed real nonpaid Canvas tests: Chinese project creation, exact script roundtrip, visible image/audio/video nodes, repeat deduplication, version approval/rollback and reconciliation. The full video-to-Jianying production chain is not claimed fully verified: current CLI video export and actual Jianying GUI opening remain separate limitations. This status is deliberately more conservative than “code complete”.

## Implemented

- New fifth Skill `dreamina-canvas-bootstrap`, `canvas_bootstrap.py` and `pipeline_handoff.py`.
- Modes: local-only dry-run/status; bootstrap; script/media sync; read-only remote reconcile; safe resume; generated-output register; evidence-based review; strict DOCX text extraction.
- Runtime version/schema/auth discovery, stable preallocated project/resource/node/update/submit IDs, atomic JSON state, OS project lock, request-ID records and per-item interrupted state.
- Exact original script and ordered shot nodes, Chinese labels and nine spatial regions, measured card placement, SHA256 upload/node dedup and original-file preservation.
- Durable content owner for shared nodes; v01/v02 immutable generated files; evidence-aware approved pointers; pending new versions preserve old approvals; rollback restores the active region; old nodes and references survive archival.
- Original four Skills preserve their entry points. V2 handoffs share stable IDs, approved-only node references, real SKU mappings and explicit audio roles. Stage A/B image composition is retained. GPT Image records before POST and blocks repeat submissions on uncertainty.
- CapCut defaults to no subtitles, validates inputs before API writes, preserves embedded sound, rejects separate audio tracks and wrong timing/media, checks both draft JSON files before editing, and uses a real local font file rather than relabeling a fallback font.
- Both installation scripts deploy all five Skills and preserve recoverable backups. README, deployment, manifest contract, baseline audit and a three-shot synthetic example are included.

## Actual capabilities and tests

| Test | Evidence class | Result |
| --- | --- | --- |
| CLI version/schema/auth and real Canvas creation | Real public CLI 1.0.3, logged-in test account | Passed |
| Native Group support | Real schema inspection | Not present; actual organization is `spatial_sections`, not native Group |
| Chinese project/section/asset names and Chinese filesystem paths | Real CLI + files | Passed |
| Overview/full script/rules and P01/P02/P03 text | Real `node show` roundtrip | Passed; HTML entities decoded once for exact visible-text comparison, no whitespace trimming |
| PNG, WAV, MP4 upload + visible media nodes | Real resource get + node show | Passed for 3 images, 1 audio, 1 video |
| Repeated synchronization | Real second run, command audit + node/version counts | Zero uploads, zero node creates/edits, zero version increases |
| Original input media | SHA256 before/after | Unchanged |
| v01 → pending v02 → approve v02 → rollback v01 | Real CLI on explicitly synthetic test media | Passed; earlier node retained; history/active placement roundtrips |
| Reconcile after version changes | Real remote queries | Passed; final test Canvas has 21 nodes and 6 media-version entries |
| JPEG/JPG, WEBP and MP3 individual encodings | Not exercised remotely in this run | Local candidate formats only; service must accept each file before sync is reported complete |
| Interrupted Canvas creation/node save/upload/review response | Offline fault-injection fixtures | Passed; stable identities and archival intents retained |
| Unknown paid submission recovery | Offline operation fixture | Only the existing submit ID is queried; no new paid call |
| Approved-only image/product/scene/character/video plans | Offline fixtures | Passed; unapproved, missing-evidence and changed-file sources rejected |
| Prepared dialogue/narration/silent-model admission | Offline gates + live capability discovery responsibility | No paid model run; final model/audio/lip-sync result remains unverified |
| Editable draft: three 4s clips, 1080×1920, 30fps | Real local CapCut Mate API + ffprobe | Passed structural/timing/media/audio checks; zero text tracks despite populated review-caption keys |
| Explicit ES/ZH caption draft | Real local API + JSON verification | Passed two tracks, exact text, timing, size 8 and Y=-700/-500 |
| Georgia Bold Italic local file | Real installed georgiaz.ttf + copied font paths/styles | Passed file/path/style checks; glyph rendering still needs GUI inspection |
| Open copied draft inside Jianying | Not performed | Pending manual GUI validation; structural success is not GUI-open proof |
| Windows install/reinstall and backup | Real isolated Chinese-path installation root | All five Skills installed; previous versions backed up |
| Bash installation | Real Git Bash syntax + isolated installation | All five Skills installed; native macOS/Linux not exercised |
| Skill metadata | Official quick_validate on all five Skills | Passed |
| Automated suite | Python unittest, 42 tests | Passed; independent reviewer additionally verified the approval/rollback/alias fault cases |

The nonpaid test Canvas is [MIZAN synthetic family-party validation](https://jimeng.jianying.com/ai-tool/ai-canvas/01d348a5-d11b-5952-9985-b3dca611df42). All materials there are labeled synthetic; fixture approvals are code-validation events, not real creative approval.

Detailed runtime evidence is kept locally in the ignored `.local-validation/` directory: production/Canvas manifests, live CLI report, live version report and two test drafts. Original account credentials, provider payloads, signed media URLs and credit tokens are not stored in Git. The temporary local CapCut API used for verification was stopped afterwards.

## Windows use

1. Check out this development branch to review it; main is unchanged. Run `install.ps1` only when ready to install the branch's five Skills (existing versions are backed up).
2. Put a confirmed structured `production_manifest.json` beside template 2, with an explicit allowlist of this project's real local materials. Preserve existing shot/SKU/audio IDs.
3. Run `dry-run`, then `bootstrap`, `sync`, and `reconcile`. Review the visible Canvas before generating scene anchors.
4. Register new images/videos in the same project and review their versions. Run the approved-only handoff adapter for video or CapCut. Authorize any paid generation separately.
5. Resume with the same manifests after interruption. Do not delete the state file or start another Canvas to “retry”.

```powershell
$tool = '.\skills\dreamina-canvas-bootstrap\scripts\canvas_bootstrap.py'
python $tool dry-run --production 'D:\视频项目\production_manifest.json'
python $tool bootstrap --production 'D:\视频项目\production_manifest.json'
python $tool sync --production 'D:\视频项目\production_manifest.json'
python $tool reconcile --production 'D:\视频项目\production_manifest.json'
python $tool resume --production 'D:\视频项目\production_manifest.json'
```

Use Python 3.11+; if `python` is not on PATH, invoke its full executable path with PowerShell `&`. `--cli` and `--canvas-skill` accept explicit installed paths. No runtime dependency beyond Python's standard library is required for Bootstrap. ffprobe is required for actual video preflight.

Reproduce offline tests with `python -m unittest discover -s tests -v`. The opt-in `tests/live_cli_smoke.py` and `tests/live_version_smoke.py` require a dedicated `simulation_only` project and perform nonpaid Canvas writes. Example `create_example.py --out ... --ffmpeg ...` prepares local synthetic images/audio/video; it never calls a model. `examples/mizan-family-party/capcut_config.json` can build the sample draft against a separately running local CapCut Mate API.

## Remaining boundaries

- Native grouping is unavailable in this release; a future group contract must be inspected before implementing its adapter. No private group API is used.
- General prose DOCX is extracted faithfully but needs an explicit field mapping when it lacks the delimited production JSON. Missing fields are reported; no creative reconstruction is attempted.
- CLI 1.0.3 publicly documents image download only. Video files require a verified Canvas UI export or a later officially supported CLI route; the manifest stays incomplete until a real export is obtained.
- Real paid generation, generated audio correspondence/lip-sync and actual Jianying GUI rendering/opening were not certified. They cannot be marked PASS from a prompt, API acceptance or JSON structure.
