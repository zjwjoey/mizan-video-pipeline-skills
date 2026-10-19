# MIZAN Video Pipeline Skills

Windows video workflow Skills for Codex and other agents that support the `SKILL.md` convention. This repository contains four Skills and deliberately excludes the NanoBanana Skill.

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
- `gpt-image-ext-material-generation` — generate stills from approved prompts and references with GPT Image 2.5 Ext.
- `dreamina-cli` — generate MIZAN videos through Dreamina Canvas, using the owner's prepared per-shot audio as a generation reference.
- `capcut-mate-video-pipeline` — assemble subtitles and a Jianying/CapCut draft, with optional rendering.

The installer copies all four folders under `<skill-root>`.
