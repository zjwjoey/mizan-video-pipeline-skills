# V2 Lite validation and delivery

Validation date: 2026-10-19, Asia/Shanghai. Baseline main: `2ae7ed3`. Development branch: `feature/mizan-canvas-bootstrap-v2`. No paid image/video generation or cloud rendering was performed.

## Delivery status: CANVAS_BOOTSTRAP_PARTIAL

### PR review repair round (2026-10-19)

CI exposed a Windows runner 8.3-path alias (`RUNNER~1`) versus resolved long-path mismatch in CapCut preflight. Both the media root and file now canonicalize before containment and URL checks; an additional regression preserves outside-directory rejection. The updated suite has **63 distinct tests**. The initial run's Ubuntu jobs passed; its Windows failure is retained in GitHub history rather than reported as a pass. Check the latest follow-up run for the repaired matrix outcome.

The four P0 contract/gate changes and four P1 state/version changes are implemented on the original V2 branch, without a sixth Skill or main merge. Bootstrap remains **PARTIAL for real production readiness** until the owner approves the real project's preview. **VIDEO_PIPELINE_READY is not established**: paid generation/audio/lip-sync/export and actual Jianying GUI validation remain outstanding. A synthetic gate approval is not real production approval.

| Review item | Repair / observed evidence |
| --- | --- |
| P0-1 template contract | Canonical `confirmed_by_owner`, explicit alias conflict rejection, labeled DOCX cards/tables and strict JSON mapping, cell provenance and unresolved/placeholder reports. Complete explicit-table DOCX regression passes; blank source template remains incomplete, not fabricated production. |
| P0-2 Stage A/B prompts | Explicit stage prompt/negative/refs/locks/additions/output fields; guarded exact-text task plans; approved anchors required before incremental tasks; shared recipes deduplicate or reject conflicts. No claim of a paid batch runner acceptance. |
| P0-3 frame mapping | Ordered `image_asset_ids`, independent start/end approvals and frame roles; identical deduplicated first/end nodes rejected; multi-image order preserved. Current public CLI only allows two total first/last-frame references: prepared audio with two frames is blocked pending a verified compatible adapter, not silently discarded. |
| P0-4 whole preview | Explicit reviewer/evidence/owner gate bound to script version, shot order, prompts, selected input hashes/versions and material-manifest SHA256. Critical changes invalidate affected shots. Image/video/CapCut plans and task journaling check the gate. |
| P1 state | Canvas availability separated from synchronization; reuse preserves `synced`. |
| P1 drift | Name/version/QC label, position and category placement checked; drift blocks production and nonpaid resume repairs cached placement. |
| P1 snapshots | Existing inputs now receive immutable byte-verified snapshots, as generated outputs already did; source replacement preserves old approval bytes, missing originals recover from verified copies. Legacy lost bytes cannot be recovered retroactively. |
| P1 filenames | Truncate descriptions only; full stable ID and trailing version/extension preserved within UTF-16 filename budget. |
| Offline regression | 62 distinct tests passed locally, five official Skill metadata validations passed, compileall passed. Independent reviewer found shot-order and identical-frame edge cases; fixes and regressions included. |
| Real nonpaid CLI repeat test | 15:41 +08:00: CLI 1.0.3, existing synthetic Canvas, 21 nodes / 6 media versions, exact script roundtrip, zero repeat mutations, no new upload/version, original bytes unchanged. |
| Synthetic preview gate on actual synced state | Opt-in `tests/live_preview_smoke.py` verified snapshots and gate acceptance, plus shot-order rejection. Reviewer explicitly labeled AUTOMATED SYNTHETIC FIXTURE TEST; no real owner's creative decision recorded. |
| CI | Added `.github/workflows/offline-tests.yml`: Windows/Linux, Python 3.11/3.12, unittest, compileall and Linux installer syntax; no account credentials or paid operations. Remote run outcome must be checked separately. |

New local ignored reports: `.local-validation/live_review_cli_report.json` and `.local-validation/live_preview_report.json`. Earlier records below describe the previous 42-test baseline, not this round's new total. Use the [current contract](../skills/dreamina-canvas-bootstrap/references/manifest-contract.md) for changed mapping/preview/snapshot behavior.

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
