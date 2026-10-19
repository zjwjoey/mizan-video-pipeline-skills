# MIZAN Video Pipeline Skills

Windows video workflow Skills for Codex and other agents that support the `SKILL.md` convention. V2 Lite contains five Skills, including a non-generating Canvas Bootstrap stage, and deliberately excludes the NanoBanana Skill.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the complete workflow, dependencies, and installation steps.

## One-command install on Windows

```powershell
git clone https://github.com/zjwjoey/mizan-video-pipeline-skills.git
if ($LASTEXITCODE -eq 0) { & ".\mizan-video-pipeline-skills\install.ps1" }
```

To install somewhere other than the default Codex skills directory:

```powershell
& ".\mizan-video-pipeline-skills\install.ps1" -SkillRoot "D:\AgentSkills"
```

The installer backs up existing skills with the same names before replacing them. It installs Skill files only; API credentials, Dreamina sign-in, Jianying, Python/uv, and CapCut Mate need their own setup as described in [DEPLOYMENT.md](DEPLOYMENT.md).

## Included Skills

- `video-storyboard-compiler` — compile an approved script or validate an owner-authored structured storyboard.
- `dreamina-canvas-bootstrap` — create/reuse the video's Chinese Canvas, synchronize exact scripts and selected local media, track versions, reconcile and resume without duplicate uploads.
- `gpt-image-ext-material-generation` — generate stills from approved prompts and references with GPT Image 2.5 Ext.
- `dreamina-cli` — generate MIZAN videos through Dreamina Canvas, using the owner's prepared per-shot audio as a generation reference.
- `capcut-mate-video-pipeline` — assemble approved sound-bearing videos into a Jianying/CapCut draft. Visible subtitles and rendering require explicit configuration/request.

The installer copies all five folders under `<skill-root>`; the original four standalone entry points remain available.

## V2 Lite workflow

Template 1 topic → template 2 confirmed script → **Stage 02.5 Canvas Bootstrap** → scene anchors / execution images + QC → Dreamina videos + QC → editable Jianying draft.

The two [manifest files](skills/dreamina-canvas-bootstrap/references/manifest-contract.md) share a stable project ID. Production owns locked creative choices; Canvas owns nodes, resource mappings, sync state, approved-version pointers and recovery records. The source script and original media remain unchanged. Prepared audio is required at the relevant video gate, not for syncing the script/images. Chinese translations are internal review text, not automatic subtitles.

```powershell
$bootstrap = '.\skills\dreamina-canvas-bootstrap\scripts\canvas_bootstrap.py'
python $bootstrap dry-run --production 'D:\视频项目\production_manifest.json'
python $bootstrap bootstrap --production 'D:\视频项目\production_manifest.json'
python $bootstrap sync --production 'D:\视频项目\production_manifest.json'
python $bootstrap reconcile --production 'D:\视频项目\production_manifest.json'
python $bootstrap resume --production 'D:\视频项目\production_manifest.json'
python $bootstrap status --production 'D:\视频项目\production_manifest.json'
```

Pass `--cli 'C:\Users\你的用户名\bin\dreamina-canvas.exe'` and/or `--canvas-skill '...\dreamina-canvas-cli\SKILL.md'` when discovery needs an explicit path. Follow the installed official Canvas Skill's login flow when `auth status` is not logged in. Bootstrap never calls a generation or credit-approval command.

Canvas CLI 1.0.3 has no native Group command: this release uses Chinese section headers and measured spatial placement (`spatial_sections`), or name prefixes when coordinates are unavailable. It does not claim native grouping. Resource upload must be followed by node import and remote verification before the material is marked synchronized.

## Example and validation

```powershell
python .\examples\mizan-family-party\create_example.py --out 'D:\MIZAN测试项目'
# Add --ffmpeg '...\ffmpeg.exe' to include an offline synthetic MP4.
python .\skills\dreamina-canvas-bootstrap\scripts\canvas_bootstrap.py dry-run --production 'D:\MIZAN测试项目\production_manifest.json'
python -m unittest discover -s tests -v
```

The three-shot [example](examples/mizan-family-party/production_manifest.json) is explicitly synthetic; its null audio mappings and pending QC must be completed before real video generation. [Validation evidence and limitations](docs/V2_LITE_VALIDATION.md) distinguish real CLI passes from mocks and manual steps. [Baseline audit](docs/V2_LITE_AUDIT.md) lists the narrowly scoped changes.
