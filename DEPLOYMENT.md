# 部署说明：流程、依赖与执行规则

本文说明如何部署五个 MIZAN 视频流程 Skills，以及各阶段需要的本机工具和外部账号。安装 Skill 不会替用户登录第三方账号或配置密钥。

## 端到端流程

```text
用户确认脚本和结构化分镜
  → Canvas Bootstrap：创建/复用中文画布，同步完整脚本与本次真实素材并供预览
  → 锚定人物与场景
  → 按镜头 image_count 生成执行图
  → 人工/QC确认图片
  → 将用户准备好的逐镜西班牙语音频导入即梦画布并作为视频生成参考
  → 人工检查画面与口型
  → 使用已带生成音轨的 AI 视频编排时间线（明确要求时才添加字幕）
  → 生成并检查剪映/CapCut草稿
  → 用户要求时再渲染最终视频
```

### 阶段对应

| 阶段 | Skill | 输入 / 输出 |
|---|---|---|
| 分镜 | `video-storyboard-compiler` | 读取脚本与负责人确认的分镜；输出镜头表、锚点、素材清单和QC交接字段。 |
| Stage 02.5 画布初始化 | `dreamina-canvas-bootstrap` | 读取 production_manifest，创建/复用中文画布、文本脚本和可见媒体节点；记录 canvas_manifest。 |
| 图片 | `gpt-image-ext-material-generation` | 读取已批准提示词、人物/场景锚点和商品参考图；严格按每镜 `image_count` 生成。 |
| 视频 | `dreamina-cli` | 读取通过图片QC的镜头素材，将已准备的 `audio_ref` 上传/导入目标即梦画布并关联至视频生成节点；按当前模型规格、`target_duration` 与 `motion_instruction` 生成带音频的视频。 |
| 时间线、草稿 | `capcut-mate-video-pipeline` | 按镜头顺序导入当前已批准视频，保留生成音轨；明确启用字幕时按语言创建字幕轨。保存并校验草稿，不另导入本地原音频。 |

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

脚本部署五个 Skill 文件夹，不会安装/登录外部生成服务，也不会改写 API 密钥。

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

CapCut Mate 是独立依赖，不能仅靠这五个 Skill 文件夹自动部署。按其上游说明安装 Python 3.11+、`uv`，克隆 [CapCut Mate](https://github.com/Hommy-master/capcut-mate)，运行 `uv sync`；Windows 再按上游要求执行 `uv pip install -e .[windows]`，然后 `uv run main.py`。API 文档默认在 `http://127.0.0.1:30000/docs`。剪映草稿输出路径在 Windows 上通常为 `%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft`。

## 单独使用 GPT Image 客户端

```powershell
python .\skills\gpt-image-ext-material-generation\scripts\gpt_image_ext.py -h
python .\skills\gpt-image-ext-material-generation\scripts\gpt_image_ext.py upload .\reference.png
python .\skills\gpt-image-ext-material-generation\scripts\gpt_image_ext.py generate --prompt "approved prompt" --image-url "https://..." --resolution 1K --size 9:16 --n 1 --record .\task.json --allow-paid
python .\skills\gpt-image-ext-material-generation\scripts\gpt_image_ext.py status TASK_ID
```

每个图片生成 POST 都会建立新任务并计费；任务未终结时只查询同一任务 ID，不要重复提交。

## V2 Lite：两份清单和 Stage 02.5

模板1继续确认选题；模板2继续确认完整脚本与逐镜执行规格。只需在模板2增加项目ID、中文主题、脚本版本、本次素材路径的简短配置区，并在同目录保存 `production_manifest.json`。完整字段见 [Manifest contract](skills/dreamina-canvas-bootstrap/references/manifest-contract.md)。旧版四个 Skill 的独立用法保留；V2 不把旧 `pass` 状态静默升级成有证据的批准。

```powershell
$tool = '.\skills\dreamina-canvas-bootstrap\scripts\canvas_bootstrap.py'
python $tool extract-docx --file 'D:\项目\模板2.docx' --output 'D:\项目\extracted.json'
python $tool dry-run --production 'D:\项目\production_manifest.json'
python $tool bootstrap --production 'D:\项目\production_manifest.json'
python $tool sync --production 'D:\项目\production_manifest.json'
python $tool status --production 'D:\项目\production_manifest.json'
```

普通Word会完整提取段落和表格文本，但没有明确结构化JSON时返回需映射字段，不猜测重写。Agent读取提取结果，按原文建立并确认生产清单。Canvas Bootstrap不要求先补齐西语音频才同步脚本和图片；有可见讲话人物的视频仍必须使用确认音频和口型规则，明确旁白/无音频的镜头则遵循其实际模型准入要求。

`canvas_manifest.json`由程序建立，保存画布项目ID、节点/资源映射、文件哈希、当前批准版本、历史和恢复ID。命名为 `镜头/角色/SKU｜素材类型｜描述｜原有/新生成｜v01｜审核状态`。文件名不含审核状态。相同哈希不重复上传或增加版本；新内容产生新版本，新版待审核时旧批准版保持有效。新生成文件复制到项目的 `generated/<asset_id>/` 内，原始文件保持不变。

新图片/视频回来后运行：

```powershell
python $tool register --production 'D:\项目\production_manifest.json' --asset-id P03_IMAGE --file 'D:\输出\新图片.png'
python $tool review --production 'D:\项目\production_manifest.json' --asset-id P03_IMAGE --version v02 --qc-status approved --evidence '负责人检查人物、真实SKU和构图后确认'
```

`register`只接收清单中声明的输入或逻辑outputs；新版本不能沿用旧版的审核证据。只在新版本同步且审批通过后切换引用。回退时重新批准旧版本，它会恢复到活动区；旧节点保留，引用不会被破坏。相同内容可共享节点，节点名称由首次注册该内容的逻辑素材控制，别名保留独立的审核记录。

## 中文分区与实际能力

统一使用00项目总览与脚本、01人物参考、02门店场景素材、03商品素材、04场景锚点、05分镜图片、06西语音频、07视频片段、08历史版本。本机1.0.3没有原生Group API，实际使用中文标题节点和空间分区；坐标不支持时退化到命名前缀。每次读取当前schema，不调用猜测的group命令。将来出现新编组接口时需先验证其成员操作契约，不能直接宣称原生编组可用。

本地文件使用显式清单，商品按镜头SKU过滤。支持的本地候选扩展为JPG/JPEG/PNG/WEBP、MP3/WAV、MP4，实际是否接受以当前CLI及单文件远端结果为准。资源上传成功后还必须创建可见媒体节点并回读资源，不能只登记本地路径。

## 恢复、下游与验收

```powershell
python $tool reconcile --production 'D:\项目\production_manifest.json'
python $tool resume --production 'D:\项目\production_manifest.json'
python .\skills\dreamina-canvas-bootstrap\scripts\pipeline_handoff.py video --production 'D:\项目\production_manifest.json' --output 'D:\项目\video_plan.json'
python .\skills\dreamina-canvas-bootstrap\scripts\pipeline_handoff.py capcut --production 'D:\项目\production_manifest.json' --output 'D:\项目\capcut_config.json'
```

`reconcile`只读远端并登记差异；`resume`只修复非付费同步，记录过的视频任务按同一个submit ID查询。画布创建、上传和节点保存前会先持久化稳定ID；响应丢失也不更换身份。GPT Image响应丢失时保留不确定状态，禁止自动重发POST。脚本改动必须显式递增script_version，内容相同的节点不会重复创建。

下游计划只解析有证据、已同步、文件哈希未变化的批准版本。视频阶段还需读取实时模型规格、验证真实节点连线和音频限制，并在用户授权后才执行付费任务。CLI 1.0.3公开下载仅覆盖图片，视频需要通过已验证的画布导出入口取得文件后再登记；尚未导出不能假装交付完成。

剪映默认30fps，`subtitle_tracks: []`；显式双语才设为 `["es", "zh"]`。运行草稿脚本前配置ffprobe；可用`--dry-run`先检查素材。字幕字体可通过`caption_style.font_path`提供真实本地字体文件；Windows上的Georgia预设自动选择已安装的对应粗体/斜体文件并复制到草稿素材目录。结构检查与剪映GUI实际打开验证分别记录。

离线示例及可复现命令在 [README](README.md#example-and-validation)。最终真实验收、Mock测试及尚需人工验证的边界见 [V2_LITE_VALIDATION.md](docs/V2_LITE_VALIDATION.md)。
