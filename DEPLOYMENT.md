# 部署说明：流程、依赖与执行规则

本文说明如何部署四个 MIZAN 视频流程 Skills，以及各阶段需要的本机工具和外部账号。安装 Skill 不会替用户登录第三方账号或配置密钥。

## 端到端流程

```text
用户确认脚本和结构化分镜
  → 锚定人物与场景
  → 按镜头 image_count 生成执行图
  → 人工/QC确认图片
  → 将用户准备好的逐镜西班牙语音频导入即梦画布并作为视频生成参考
  → 人工检查画面与口型
  → 使用已带生成音轨的 AI 视频编排时间线和多语言字幕
  → 生成并检查剪映/CapCut草稿
  → 用户要求时再渲染最终视频
```

### 阶段对应

| 阶段 | Skill | 输入 / 输出 |
|---|---|---|
| 分镜 | `video-storyboard-compiler` | 读取脚本与负责人确认的分镜；输出镜头表、锚点、素材清单和QC交接字段。 |
| 图片 | `gpt-image-ext-material-generation` | 读取已批准提示词、人物/场景锚点和商品参考图；严格按每镜 `image_count` 生成。 |
| 视频 | `dreamina-cli` | 读取通过图片QC的镜头素材，将已准备的 `audio_ref` 上传/导入目标即梦画布并关联至视频生成节点；按当前模型规格、`target_duration` 与 `motion_instruction` 生成带音频的视频。 |
| 时间线、字幕、草稿 | `capcut-mate-video-pipeline` | 按镜头顺序导入已批准且带生成音轨的视频，依据 `subtitle_es` / `subtitle_zh` 创建字幕轨，保存并校验剪映草稿；不再单独导入本地原音频或合成音视频。 |

## 负责人确认与结构化分镜

脚本和分镜由项目负责人先确认。下游素材生成前，项目级字段应声明：

- `confirmed_by_owner: yes`
- `codex_start_stage: material_generation`（或明确的后续起始阶段）
- `script_file`、`storyboard_source_file`
- `aspect_ratio`、`fps`、`resolution`
- `language_voiceover`、`subtitle_tracks`
- `image_engine`、`video_engine`、QC 标准

镜头记录建议包含 `shot_id`、`scene_group`、`scene_anchor_id`、`host_anchor_id`、起止时间、`product_refs`、`image_count`、`image_priority`、`material_mode`、`image_prompt_core`、`negative_prompt`、`voiceover_es`、`subtitle_es`、`subtitle_zh`、`target_duration`、`motion_instruction`、`audio_ref`、`audio_role`、`lip_sync_required` 和 `qc_focus`。音频文件由负责人在视频生成前准备；缺少逐镜音频映射时不得启动该镜视频生成。

Agent 执行已确认内容，不重做创意解释或擅自改变镜头数、动作、商品、提示词、时长、字幕和音频映射。`image_count` 是每个镜头的图片数量，不是固定的项目图片总数。

## 锚点和人工 QC 闸门

先解析全片引用的 `host_anchor_id`、`scene_anchor_id` 和 `product_refs`，生成或选定人物、场景锚点。人物锚点应确认身份、发型、服装和体态；场景锚点应确认空间布局、货架、灯光和商品密度；商品锚点应确认引用商品的类别、形态和颜色。

负责人确认锚点后，再按镜头生成执行图。执行图通过人物、场景、商品、手脸、构图和文字检查并标记 `qc_status: pass` 后，才允许进入视频生成。拒绝项记录 `revise` 或 `fail`，保留旧版本并通过 `revision_of` 追踪。

## 西班牙语音频和口型同步规则

- 西班牙语音频由用户在视频生成前准备；镜头必须使用分镜 `audio_ref` 对应的文件，并在目标即梦画布中创建/导入音频素材节点，再把该节点实际接入支持音频参考的视频生成模式。仅在提示词或记录中写本地路径不算接入成功。
- 默认 `audio_role: dialogue`、`lip_sync_required: yes`。视频生成要求画面人物根据该音频自然说话并同步口型。
- 只有负责人明确标记 `audio_role: narration` /“旁白音”时，才设置 `lip_sync_required: no`。
- 不生成、替换、混入音乐或加入其他音频，除非用户明确提出。每次使用前读取即梦画布当前模型规格，确认所选视频模式接受音频参考，且音频符合时长和素材数量限制。
- 缺失 `audio_ref`、`audio_role` 或同步要求时，先补齐分镜，不推测。
- 口型提示只是生成要求，不能当作已同步的证据。下载后需人工检查口型、音频是否存在且对应指定输入，以及是否出现额外音轨。

## 即梦画布与剪映的音频边界

- 视频阶段使用本机安装的 `dreamina-canvas-cli` Skill 和 `dreamina-canvas` CLI；不要用另一套旧版 `dreamina` 生成 CLI 代替。CLI 登录、画布选择、文件导入、模型/模式和可用参数，以本机已安装 Skill 与当前 CLI `schema` / `model list` 为准。
- 逐镜用户音频在即梦画布中作为视频生成参考输入。生成结果应带有由该参考音频产生的声音。
- CapCut Mate/剪映阶段只导入通过 QC 的音视频一体 AI 视频和字幕，不导入 `audio_ref` 原文件，不另建原音频轨，也不使用 FFmpeg 或其他本地工具把原音频与 AI 视频二次合成。若生成视频缺音或音频不符，退回视频 QC/生成阶段处理。

## 依赖项

| 依赖 | 用途 | 必需条件 |
|---|---|---|
| 支持 `SKILL.md` 的 AI Agent | 读取并运行 Skill 指令 | 必需；安装脚本默认部署到 Codex Skills 目录。其他 Agent 可从 `skills/` 复制 Skill 文件夹到自己的 Skills 路径。 |
| Git | 克隆仓库 | 首次下载必需。 |
| Python 3.11+ | CapCut Mate 本地服务；GPT Image 客户端脚本仅使用标准库 | 需要本地创建剪映草稿时必需。 |
| CapCut Mate | 草稿 API，默认 `http://127.0.0.1:30000` | 创建剪映草稿时必需。需单独安装和启动，见下文。 |
| 剪映专业版（Windows） | 打开本地草稿 | Windows 本地草稿工作流必需。 |
| Dreamina Canvas CLI、`dreamina-canvas-cli` Skill 和授权账号 | 画布管理、音频/图片素材导入、视频生成、任务查询和下载 | 使用即梦画布阶段时必需；先检查 `auth status`，首次使用需用户完成授权登录。 |
| GPT Image API Key | GPT Image 2.5 Ext 图片生成和本地参考图上传 | 图片生成时必需；不要写入仓库或分镜文件。 |
| FFmpeg / ffprobe | 视频编码、尺寸、时长、音频轨检查 | 建议安装；只在需要本地媒体 QC 时使用。 |
| 可访问 API 的网络与服务额度 | GPT Image 与 Dreamina 任务 | 生成阶段必需；付费请求提交前应确认参数和参考素材。 |

## 一键安装 Skills

### Windows PowerShell

```powershell
git clone https://github.com/zjwjoey/mizan-video-pipeline-skills.git
if ($LASTEXITCODE -eq 0) { & ".\mizan-video-pipeline-skills\install.ps1" }
```

如需安装到自定义 Skill 根目录：

```powershell
& ".\mizan-video-pipeline-skills\install.ps1" -SkillRoot "D:\AgentSkills"
```

默认安装路径为 `%CODEX_HOME%\skills`，未设置 `CODEX_HOME` 时为用户目录 `.codex\skills`。如存在同名 Skill，脚本会先移动到相邻 `skill-backups` 目录，再复制仓库版本。

### macOS / Linux / Git Bash

```bash
git clone https://github.com/zjwjoey/mizan-video-pipeline-skills.git && ./mizan-video-pipeline-skills/install.sh
```

脚本部署四个 Skill 文件夹，不会安装/登录外部生成服务，也不会改写 API 密钥。

## 配置外部依赖

### GPT Image API

将 API Key 配置为进程/用户环境变量：

```powershell
[Environment]::SetEnvironmentVariable('GPT_IMAGE_API_KEY', 'YOUR_API_KEY', 'User')
```

客户端兼容旧变量名 `NANOBANANA2_API_KEY`。远端仓库和示例中不得保存真实密钥。

### Dreamina CLI

安装并读取官方即梦画布 CLI & Skill。登录使用 `dreamina-canvas` 的认证流程，不使用另一套 `dreamina` CLI。每次运行前按已安装 `dreamina-canvas-cli` Skill 检查版本、`schema`、`auth status` 和目标视频模型的当前规格；模型、模式、参考音频、比例、分辨率及时长限制可能变化。不要把认证状态或密钥写入仓库。

### CapCut Mate / Jianying

CapCut Mate 是独立依赖，不能仅靠这四个 Skill 文件夹自动部署。按其上游说明安装 Python 3.11+、`uv`，克隆 [CapCut Mate](https://github.com/Hommy-master/capcut-mate)，运行 `uv sync`；Windows 再按上游要求执行 `uv pip install -e .[windows]`，然后 `uv run main.py`。API 文档默认在 `http://127.0.0.1:30000/docs`。剪映草稿输出路径在 Windows 上通常为 `%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft`。

## 单独使用 GPT Image 客户端

```powershell
python .\skills\gpt-image-ext-material-generation\scripts\gpt_image_ext.py -h
python .\skills\gpt-image-ext-material-generation\scripts\gpt_image_ext.py upload .\reference.png
python .\skills\gpt-image-ext-material-generation\scripts\gpt_image_ext.py generate --prompt "approved prompt" --image-url "https://..." --resolution 1K --size 9:16 --n 1 --record .\task.json
python .\skills\gpt-image-ext-material-generation\scripts\gpt_image_ext.py status TASK_ID
```

每个图片生成 POST 都会建立新任务并计费；任务未终结时只查询同一任务 ID，不要重复提交。
